"""
Tests for S2-09: World Update Delivery (Polling).

This module tests the polling mechanism for world updates including:
- Client config endpoint
- Polling simulation
- State synchronization via diffs
- Correct state reconstruction over multiple ticks
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from lycia.models import Event, City


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def advancing_world(db_session: Session, sample_world_state, sample_cities):
    """
    Create a world that advances through ticks with events.

    Returns a helper function to advance ticks and create events.
    """
    def advance_tick(prosperity_changes: dict[str, int] = None):
        """
        Advance world by one tick and optionally create prosperity change events.

        Args:
            prosperity_changes: Dict of city_name -> delta (e.g., {"Xanthos": 10})
        """
        sample_world_state.tick += 1
        current_tick = sample_world_state.tick
        db_session.commit()

        if prosperity_changes:
            for city_name, delta in prosperity_changes.items():
                city = db_session.query(City).filter_by(name=city_name).first()
                if city:
                    old_prosperity = city.prosperity
                    new_prosperity = old_prosperity + delta
                    city.prosperity = new_prosperity

                    # Create event
                    event = Event(
                        tick=current_tick,
                        type="city.prosperity_changed",
                        schema_version=1,
                        actor="test_subsystem",
                        payload={
                            "city_id": city.id,
                            "city_name": city.name,
                            "old_value": old_prosperity,
                            "new_value": new_prosperity,
                        },
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(event)

            db_session.commit()

        return current_tick

    return advance_tick


# =============================================================================
# TEST: Client Config Endpoint
# =============================================================================

class TestClientConfigEndpoint:
    """Test /api/client/config endpoint."""

    def test_client_config_returns_polling_settings(
        self,
        client: TestClient,
        sample_world_state
    ):
        """Test that client config endpoint returns polling configuration."""
        sample_world_state.tick = 42

        response = client.get("/api/client/config")

        assert response.status_code == 200
        data = response.json()

        # Verify expected fields
        assert "polling_interval_ms" in data
        assert "enable_polling" in data
        assert "current_tick" in data

        # Verify default values from gameplay.json
        assert data["polling_interval_ms"] == 3000  # Default 3 seconds
        assert data["enable_polling"] is True
        assert data["current_tick"] == 42

    def test_client_config_no_authentication_required(
        self,
        client: TestClient,
        sample_world_state
    ):
        """Test that client config is publicly accessible."""
        # No authentication session

        response = client.get("/api/client/config")

        assert response.status_code == 200
        # Should work without authentication

    def test_client_config_with_missing_world_state(
        self,
        client: TestClient,
        db_session: Session
    ):
        """Test client config when world state doesn't exist yet."""
        # Don't create sample_world_state

        response = client.get("/api/client/config")

        assert response.status_code == 200
        data = response.json()

        # Should return 0 for current_tick if no world state
        assert data["current_tick"] == 0


# =============================================================================
# TEST: Polling Simulation
# =============================================================================

class TestPollingSimulation:
    """Test polling behavior by simulating a client."""

    def test_client_polls_and_receives_updates(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities
    ):
        """
        AC: Simulate a client performing diff requests while ticks advance.

        Client should receive incremental updates for each tick.
        """
        # Initial state: tick 0
        last_known_tick = sample_world_state.tick

        # Tick 1: Xanthos prosperity +10
        advancing_world({"Xanthos": 10})

        # Client polls for updates
        response = client.get(f"/api/world/diff?sinceTick={last_known_tick}")
        assert response.status_code == 200

        diff1 = response.json()
        assert diff1["current_tick"] == 1
        assert diff1["since_tick"] == 0
        assert diff1["total_events"] > 0

        # Find Xanthos changes
        xanthos_diff = next((c for c in diff1["cities"] if c["city_name"] == "Xanthos"), None)
        assert xanthos_diff is not None

        prosperity_change = next(
            (m for m in xanthos_diff["metric_changes"] if m["metric"] == "prosperity"),
            None
        )
        assert prosperity_change is not None
        assert prosperity_change["delta"] == 10

        # Update client's last known tick
        last_known_tick = diff1["current_tick"]

        # Tick 2: Patara prosperity +5
        advancing_world({"Patara": 5})

        # Client polls again
        response = client.get(f"/api/world/diff?sinceTick={last_known_tick}")
        assert response.status_code == 200

        diff2 = response.json()
        assert diff2["current_tick"] == 2
        assert diff2["since_tick"] == 1

        # Should only contain Patara changes (not Xanthos)
        assert len(diff2["cities"]) == 1
        assert diff2["cities"][0]["city_name"] == "Patara"

    def test_client_polls_when_no_updates(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test polling when tick hasn't advanced."""
        sample_world_state.tick = 10
        last_known_tick = 10

        # Client polls at same tick
        response = client.get(f"/api/world/diff?sinceTick={last_known_tick}")
        assert response.status_code == 200

        diff = response.json()
        assert diff["current_tick"] == 10
        assert diff["since_tick"] == 10
        assert diff["tick_range"] == 0
        assert diff["total_events"] == 0
        assert len(diff["cities"]) == 0

    def test_client_can_skip_ticks_and_get_aggregate_diff(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities
    ):
        """
        Test that client can poll after multiple ticks and get aggregated diff.

        Simulates client being offline for several ticks.
        """
        # Initial tick: 0
        last_known_tick = 0

        # Advance multiple ticks with changes
        advancing_world({"Xanthos": 5})   # Tick 1
        advancing_world({"Xanthos": 3})   # Tick 2
        advancing_world({"Xanthos": -2})  # Tick 3
        advancing_world({"Patara": 10})   # Tick 4

        # Client polls after being offline
        response = client.get(f"/api/world/diff?sinceTick={last_known_tick}")
        assert response.status_code == 200

        diff = response.json()
        assert diff["current_tick"] == 4
        assert diff["since_tick"] == 0
        assert diff["tick_range"] == 4

        # Should see net change for Xanthos (+5 +3 -2 = +6)
        xanthos_diff = next((c for c in diff["cities"] if c["city_name"] == "Xanthos"), None)
        assert xanthos_diff is not None

        prosperity_change = next(
            (m for m in xanthos_diff["metric_changes"] if m["metric"] == "prosperity"),
            None
        )
        assert prosperity_change is not None
        # Initial 75 + 5 + 3 - 2 = 81
        assert prosperity_change["new_value"] == 81
        assert prosperity_change["delta"] == 6

    def test_multiple_clients_polling_independently(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities
    ):
        """Test that multiple clients can poll independently."""
        # Client A starts at tick 0
        client_a_tick = 0

        # Client B starts at tick 2
        advancing_world({"Xanthos": 5})
        advancing_world({"Patara": 3})
        client_b_tick = sample_world_state.tick

        # Advance more ticks
        advancing_world({"Myra": 7})
        advancing_world({"Xanthos": -2})

        # Client A polls (should see all changes from tick 0)
        response_a = client.get(f"/api/world/diff?sinceTick={client_a_tick}")
        diff_a = response_a.json()
        assert diff_a["since_tick"] == 0
        assert diff_a["current_tick"] == 4

        # Client B polls (should only see changes from tick 2)
        response_b = client.get(f"/api/world/diff?sinceTick={client_b_tick}")
        diff_b = response_b.json()
        assert diff_b["since_tick"] == 2
        assert diff_b["current_tick"] == 4
        assert diff_b["tick_range"] == 2


# =============================================================================
# TEST: State Reconstruction
# =============================================================================

class TestStateReconstruction:
    """Test that client can correctly rebuild state from diffs."""

    def test_client_rebuilds_state_correctly(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities
    ):
        """
        AC: Confirm the client can rebuild the current state correctly.

        Simulates client tracking state and applying diffs.
        """
        # Get initial state
        response = client.get("/api/world/snapshot")
        initial_state = response.json()

        # Build client-side state model
        client_state = {
            city["id"]: {
                "name": city["name"],
                "prosperity": city["prosperity"],
                "unrest": city["unrest"]
            }
            for city in initial_state["cities"]
        }

        last_known_tick = initial_state["tick"]

        # Record initial Xanthos prosperity
        xanthos = next(c for c in sample_cities if c.name == "Xanthos")
        initial_xanthos_prosperity = xanthos.prosperity

        # Apply several tick changes
        advancing_world({"Xanthos": 10})
        advancing_world({"Xanthos": 5})
        advancing_world({"Xanthos": -3})

        # Client polls for diff
        response = client.get(f"/api/world/diff?sinceTick={last_known_tick}")
        diff = response.json()

        # Apply diff to client state
        for city_diff in diff["cities"]:
            city_id = city_diff["city_id"]
            for metric_change in city_diff["metric_changes"]:
                if metric_change["metric"] == "prosperity":
                    client_state[city_id]["prosperity"] = metric_change["new_value"]
                elif metric_change["metric"] == "unrest":
                    client_state[city_id]["unrest"] = metric_change["new_value"]

        # Verify client state matches server state
        response = client.get("/api/world/snapshot")
        server_state = response.json()

        for server_city in server_state["cities"]:
            city_id = server_city["id"]
            assert client_state[city_id]["prosperity"] == server_city["prosperity"]
            assert client_state[city_id]["unrest"] == server_city["unrest"]

        # Verify specific change applied correctly
        expected_prosperity = initial_xanthos_prosperity + 10 + 5 - 3
        assert client_state[xanthos.id]["prosperity"] == expected_prosperity

    def test_client_applies_incremental_diffs(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities
    ):
        """Test that client can apply incremental diffs one tick at a time."""
        # Get initial snapshot
        response = client.get("/api/world/snapshot")
        initial_state = response.json()

        # Build client state
        client_state = {
            city["name"]: city["prosperity"]
            for city in initial_state["cities"]
        }

        last_tick = initial_state["tick"]

        # Advance and poll tick by tick
        for i in range(5):
            # Advance world
            advancing_world({"Xanthos": 2, "Patara": -1, "Myra": 3})

            # Poll for diff
            response = client.get(f"/api/world/diff?sinceTick={last_tick}")
            diff = response.json()

            # Apply diff incrementally
            for city_diff in diff["cities"]:
                city_name = city_diff["city_name"]
                for change in city_diff["metric_changes"]:
                    if change["metric"] == "prosperity":
                        client_state[city_name] = change["new_value"]

            last_tick = diff["current_tick"]

        # Final verification
        response = client.get("/api/world/snapshot")
        final_state = response.json()

        for city in final_state["cities"]:
            assert client_state[city["name"]] == city["prosperity"]

    def test_client_handles_mixed_metric_changes(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state,
        sample_cities,
        db_session: Session
    ):
        """Test client handles both prosperity and unrest changes."""
        # Initial state
        last_tick = sample_world_state.tick

        # Advance with prosperity change
        advancing_world({"Xanthos": 10})

        # Manually add unrest change event
        sample_world_state.tick += 1
        current_tick = sample_world_state.tick

        xanthos = db_session.query(City).filter_by(name="Xanthos").first()
        old_unrest = xanthos.unrest
        new_unrest = old_unrest + 15
        xanthos.unrest = new_unrest

        event = Event(
            tick=current_tick,
            type="city.unrest_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": xanthos.id,
                "city_name": "Xanthos",
                "old_value": old_unrest,
                "new_value": new_unrest,
            },
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(event)
        db_session.commit()

        # Client polls
        response = client.get(f"/api/world/diff?sinceTick={last_tick}")
        diff = response.json()

        # Should have both prosperity and unrest changes
        xanthos_diff = next(c for c in diff["cities"] if c["city_name"] == "Xanthos")

        prosperity_change = next(
            (m for m in xanthos_diff["metric_changes"] if m["metric"] == "prosperity"),
            None
        )
        unrest_change = next(
            (m for m in xanthos_diff["metric_changes"] if m["metric"] == "unrest"),
            None
        )

        assert prosperity_change is not None
        assert unrest_change is not None
        assert unrest_change["delta"] == 15


# =============================================================================
# TEST: Polling Edge Cases
# =============================================================================

class TestPollingEdgeCases:
    """Test edge cases in polling behavior."""

    def test_polling_with_rapid_tick_advancement(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state
    ):
        """Test polling when ticks advance rapidly."""
        last_tick = 0

        # Rapidly advance ticks
        for i in range(10):
            advancing_world({"Xanthos": 1})

        # Single poll should capture all changes
        response = client.get(f"/api/world/diff?sinceTick={last_tick}")
        diff = response.json()

        assert diff["current_tick"] == 10
        assert diff["tick_range"] == 10

        # Net prosperity change should be +10
        xanthos_diff = next(c for c in diff["cities"] if c["city_name"] == "Xanthos")
        prosperity_change = next(
            m for m in xanthos_diff["metric_changes"]
            if m["metric"] == "prosperity"
        )
        assert prosperity_change["delta"] == 10

    def test_polling_with_no_events_but_tick_advanced(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state
    ):
        """Test polling when tick advances but no events occurred."""
        last_tick = sample_world_state.tick

        # Advance tick without events
        advancing_world(None)

        response = client.get(f"/api/world/diff?sinceTick={last_tick}")
        diff = response.json()

        assert diff["current_tick"] == last_tick + 1
        assert diff["total_events"] == 0
        assert len(diff["cities"]) == 0

    def test_polling_frequency_matches_config(
        self,
        client: TestClient,
        sample_world_state
    ):
        """Test that config endpoint returns correct polling interval."""
        response = client.get("/api/client/config")
        config = response.json()

        # Verify matches gameplay.json setting
        assert config["polling_interval_ms"] == 3000

        # Verify it's within reasonable range (2-5 seconds as per spec)
        assert 2000 <= config["polling_interval_ms"] <= 5000


# =============================================================================
# TEST: Integration with S2-08 World Diff
# =============================================================================

class TestPollingIntegrationWithWorldDiff:
    """Test that polling correctly integrates with S2-08 world diff functionality."""

    def test_polling_uses_world_diff_endpoint(
        self,
        client: TestClient,
        advancing_world,
        sample_world_state
    ):
        """Verify polling uses the /api/world/diff endpoint from S2-08."""
        last_tick = 0

        advancing_world({"Xanthos": 10, "Patara": 5})

        # Poll using world diff endpoint
        response = client.get(f"/api/world/diff?sinceTick={last_tick}")

        assert response.status_code == 200
        diff = response.json()

        # Verify S2-08 response structure
        assert "current_tick" in diff
        assert "since_tick" in diff
        assert "cities" in diff
        assert "total_events" in diff

        # Verify city diff structure
        for city_diff in diff["cities"]:
            assert "city_id" in city_diff
            assert "city_name" in city_diff
            assert "metric_changes" in city_diff
            assert "events" in city_diff

    def test_polling_handles_s2_08_error_responses(
        self,
        client: TestClient,
        sample_world_state
    ):
        """Test that client handles S2-08 error responses gracefully."""
        # Try polling with invalid tick (future)
        future_tick = sample_world_state.tick + 100

        response = client.get(f"/api/world/diff?sinceTick={future_tick}")

        # Should get 400 Bad Request from S2-08
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()
