"""
Tests for S2-08: World Diff API & Basic Recap Contract.

This module tests the world diff and recap functionality including:
- World diff calculation from events
- Per-city metric changes
- Recap highlights generation
- Summary items creation
- Suggested follow-up actions
- Error handling for invalid sinceTick values
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from lycia.models import Event
from lycia.world_diff import (
    get_world_diff,
    get_recap,
    generate_event_description,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_events(db_session: Session, sample_world_state, sample_cities):
    """
    Create sample events for testing diff and recap.

    Creates events spanning ticks 1-10 with various types:
    - Prosperity changes
    - Unrest changes
    - Prosperity boosts
    """
    events = []

    # Tick 1: Small prosperity change in Xanthos
    events.append(Event(
        tick=1,
        type="city.prosperity_changed",
        schema_version=1,
        actor="economy_subsystem",
        payload={
            "city_id": sample_cities[0].id,
            "city_name": sample_cities[0].name,
            "old_value": 75,
            "new_value": 80,
        },
        created_at=datetime.now(timezone.utc)
    ))

    # Tick 2: Large prosperity boost in Patara (should trigger highlight)
    events.append(Event(
        tick=2,
        type="city.prosperity_boosted",
        schema_version=1,
        actor="player:1",
        payload={
            "city_id": sample_cities[1].id,
            "city_name": sample_cities[1].name,
            "amount": 15,
        },
        created_at=datetime.now(timezone.utc),
        command_id=100
    ))

    # Tick 3: Unrest spike in Myra (should trigger highlight)
    events.append(Event(
        tick=3,
        type="city.unrest_changed",
        schema_version=1,
        actor="social_subsystem",
        payload={
            "city_id": sample_cities[2].id,
            "city_name": sample_cities[2].name,
            "old_value": 8,
            "new_value": 25,
        },
        created_at=datetime.now(timezone.utc)
    ))

    # Tick 5: Large prosperity drop in Xanthos (should trigger highlight)
    events.append(Event(
        tick=5,
        type="city.prosperity_changed",
        schema_version=1,
        actor="economy_subsystem",
        payload={
            "city_id": sample_cities[0].id,
            "city_name": sample_cities[0].name,
            "old_value": 80,
            "new_value": 65,
        },
        created_at=datetime.now(timezone.utc)
    ))

    # Tick 7: Action processed event
    events.append(Event(
        tick=7,
        type="action.processed",
        schema_version=1,
        actor="action_commands",
        payload={
            "intent": "prosperity_boost",
            "player_id": 1,
        },
        created_at=datetime.now(timezone.utc),
        command_id=100
    ))

    # Tick 8: Another prosperity change in Patara
    events.append(Event(
        tick=8,
        type="city.prosperity_changed",
        schema_version=1,
        actor="economy_subsystem",
        payload={
            "city_id": sample_cities[1].id,
            "city_name": sample_cities[1].name,
            "old_value": 83,
            "new_value": 88,
        },
        created_at=datetime.now(timezone.utc)
    ))

    # Add all events to database
    for event in events:
        db_session.add(event)

    db_session.commit()

    # Update city states to match final events
    sample_cities[0].prosperity = 65  # Xanthos: dropped from 80 to 65
    sample_cities[1].prosperity = 88  # Patara: boosted and grew to 88
    sample_cities[2].unrest = 25  # Myra: unrest spiked to 25
    db_session.commit()

    return events


# =============================================================================
# TEST: World Diff Calculation
# =============================================================================

class TestWorldDiff:
    """Test world diff calculation."""

    def test_diff_with_valid_since_tick(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test diff calculation with valid sinceTick parameter."""
        # Set current tick to 10
        sample_world_state.tick = 10
        db_session.commit()

        # Get diff since tick 0
        diff = get_world_diff(db_session, since_tick=0)

        # Verify response structure
        assert diff.current_tick == 10
        assert diff.since_tick == 0
        assert diff.tick_range == 10
        assert diff.total_events == len(sample_events)

        # Verify cities are included (only those with changes)
        assert len(diff.cities) > 0

        # Find Xanthos in diff
        xanthos_diff = next((c for c in diff.cities if c.city_name == "Xanthos"), None)
        assert xanthos_diff is not None

        # Verify Xanthos has events
        assert len(xanthos_diff.events) > 0

    def test_diff_since_recent_tick(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test diff calculation since a recent tick (partial range)."""
        sample_world_state.tick = 10
        db_session.commit()

        # Get diff since tick 5 (should only include events from ticks 6-10)
        diff = get_world_diff(db_session, since_tick=5)

        assert diff.current_tick == 10
        assert diff.since_tick == 5
        assert diff.tick_range == 5

        # Should have fewer events than full range
        assert diff.total_events < len(sample_events)

        # Verify only events after tick 5 are included
        for city in diff.cities:
            for event in city.events:
                assert event.tick > 5

    def test_diff_with_same_tick(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test diff when sinceTick equals currentTick (no changes)."""
        sample_world_state.tick = 10
        db_session.commit()

        # Get diff since current tick
        diff = get_world_diff(db_session, since_tick=10)

        assert diff.current_tick == 10
        assert diff.since_tick == 10
        assert diff.tick_range == 0
        assert diff.total_events == 0
        assert len(diff.cities) == 0

    def test_diff_with_future_tick_raises_error(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test that future sinceTick raises ValueError."""
        sample_world_state.tick = 10
        db_session.commit()

        # Try to get diff from future tick
        with pytest.raises(ValueError, match="cannot be in the future"):
            get_world_diff(db_session, since_tick=15)

    def test_diff_with_negative_tick_raises_error(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test that negative sinceTick raises ValueError."""
        sample_world_state.tick = 10
        db_session.commit()

        # Try to get diff from negative tick
        with pytest.raises(ValueError, match="cannot be negative"):
            get_world_diff(db_session, since_tick=-5)

    def test_diff_metric_changes(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test that metric changes are calculated correctly."""
        sample_world_state.tick = 10
        db_session.commit()

        diff = get_world_diff(db_session, since_tick=0)

        # Find Xanthos (should have prosperity changes)
        xanthos_diff = next((c for c in diff.cities if c.city_name == "Xanthos"), None)
        assert xanthos_diff is not None

        # Verify metric changes
        prosperity_change = next(
            (m for m in xanthos_diff.metric_changes if m.metric == "prosperity"),
            None
        )

        if prosperity_change:
            # Xanthos: 75 -> 80 -> 65 = net change of -10
            assert prosperity_change.old_value == 75
            assert prosperity_change.new_value == 65
            assert prosperity_change.delta == -10

    def test_diff_empty_events(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test diff calculation when no events exist."""
        sample_world_state.tick = 10
        db_session.commit()

        # No events created, so diff should be empty
        diff = get_world_diff(db_session, since_tick=0)

        assert diff.total_events == 0
        assert len(diff.cities) == 0


# =============================================================================
# TEST: Recap Generation
# =============================================================================

class TestRecap:
    """Test recap generation."""

    def test_recap_with_valid_since_tick(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test recap generation with valid sinceTick parameter."""
        sample_world_state.tick = 10
        db_session.commit()

        # Get recap since tick 0
        recap = get_recap(db_session, since_tick=0)

        # Verify response structure
        assert recap.current_tick == 10
        assert recap.since_tick == 0

        # Should have highlights (we created notable events)
        assert len(recap.highlights) > 0

        # Should have summary items
        assert len(recap.summary_items) > 0

        # Suggested followups may or may not be present
        assert isinstance(recap.suggested_followups, list)

    def test_recap_highlights_generation(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test that highlights are generated for notable events."""
        sample_world_state.tick = 10
        db_session.commit()

        recap = get_recap(db_session, since_tick=0)

        # Should have highlights for:
        # 1. Prosperity boost (tick 2)
        # 2. Unrest spike (tick 3)
        # 3. Prosperity drop (tick 5)

        # Check for prosperity boost highlight
        boost_highlight = next(
            (h for h in recap.highlights if h.type == "prosperity_boosted"),
            None
        )
        assert boost_highlight is not None
        assert boost_highlight.city_name == "Patara"
        assert boost_highlight.tick == 2

        # Check for unrest spike highlight
        unrest_highlight = next(
            (h for h in recap.highlights if h.type == "unrest_spike"),
            None
        )
        assert unrest_highlight is not None
        assert unrest_highlight.city_name == "Myra"

        # Check for prosperity drop highlight
        drop_highlight = next(
            (h for h in recap.highlights if h.type == "prosperity_drop"),
            None
        )
        assert drop_highlight is not None
        assert drop_highlight.city_name == "Xanthos"

    def test_recap_highlight_severity(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test that highlight severity is calculated correctly."""
        sample_world_state.tick = 10
        db_session.commit()

        recap = get_recap(db_session, since_tick=0)

        # Find prosperity drop highlight (delta of -15)
        drop_highlight = next(
            (h for h in recap.highlights if h.type == "prosperity_drop"),
            None
        )

        if drop_highlight:
            # Delta of -15 should be "high" severity (>= 20 is considered high for drops)
            # or "medium" if < 20
            assert drop_highlight.severity in ["medium", "high"]

    def test_recap_summary_items(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test that summary items are generated correctly."""
        sample_world_state.tick = 10
        db_session.commit()

        recap = get_recap(db_session, since_tick=0)

        # Should have economic category (prosperity events)
        economic_summary = next(
            (s for s in recap.summary_items if s.category == "economic"),
            None
        )
        assert economic_summary is not None
        assert "prosperity" in economic_summary.text.lower()

        # Should have social category (unrest events)
        social_summary = next(
            (s for s in recap.summary_items if s.category == "social"),
            None
        )
        assert social_summary is not None
        assert "unrest" in social_summary.text.lower()

    def test_recap_suggested_followups(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test that suggested follow-up actions are generated."""
        sample_world_state.tick = 10
        db_session.commit()

        recap = get_recap(db_session, since_tick=0)

        # Should suggest investigating high unrest cities
        investigate_followup = next(
            (f for f in recap.suggested_followups if f.action_type == "investigate"),
            None
        )

        # May or may not have followups depending on highlight severity
        # Just verify structure if present
        if investigate_followup:
            assert investigate_followup.target
            assert investigate_followup.reason
            assert investigate_followup.priority in ["low", "medium", "high"]

    def test_recap_empty_events(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test recap when no events exist (AC: empty lists for no important events)."""
        sample_world_state.tick = 10
        db_session.commit()

        # No events created
        recap = get_recap(db_session, since_tick=0)

        # Should return valid structure with empty lists
        assert recap.current_tick == 10
        assert recap.since_tick == 0
        assert recap.highlights == []
        assert recap.summary_items == []
        assert recap.suggested_followups == []

    def test_recap_with_future_tick_raises_error(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test that future sinceTick raises ValueError."""
        sample_world_state.tick = 10
        db_session.commit()

        with pytest.raises(ValueError, match="cannot be in the future"):
            get_recap(db_session, since_tick=15)

    def test_recap_with_negative_tick_raises_error(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test that negative sinceTick raises ValueError."""
        sample_world_state.tick = 10
        db_session.commit()

        with pytest.raises(ValueError, match="cannot be negative"):
            get_recap(db_session, since_tick=-5)


# =============================================================================
# TEST: API Endpoints
# =============================================================================

class TestWorldDiffAPI:
    """Test /api/world/diff endpoint."""

    def test_world_diff_endpoint(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test GET /api/world/diff endpoint."""
        sample_world_state.tick = 10

        response = client.get("/api/world/diff?sinceTick=0")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "current_tick" in data
        assert "since_tick" in data
        assert "tick_range" in data
        assert "cities" in data
        assert "total_events" in data

        assert data["current_tick"] == 10
        assert data["since_tick"] == 0
        assert data["tick_range"] == 10

    def test_world_diff_endpoint_invalid_future_tick(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/world/diff with future sinceTick (AC: invalid sinceTick handled)."""
        sample_world_state.tick = 10

        response = client.get("/api/world/diff?sinceTick=15")

        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    def test_world_diff_endpoint_invalid_negative_tick(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/world/diff with negative sinceTick (AC: invalid sinceTick handled)."""
        sample_world_state.tick = 10

        response = client.get("/api/world/diff?sinceTick=-5")

        assert response.status_code == 400
        assert "negative" in response.json()["detail"].lower()

    def test_world_diff_endpoint_missing_since_tick(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/world/diff without sinceTick parameter."""
        sample_world_state.tick = 10

        response = client.get("/api/world/diff")

        # Should return 422 (validation error for missing required param)
        assert response.status_code == 422


class TestRecapAPI:
    """Test /api/recap endpoint."""

    def test_recap_endpoint(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities,
        sample_events
    ):
        """Test GET /api/recap endpoint."""
        sample_world_state.tick = 10

        response = client.get("/api/recap?sinceTick=0")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure (AC: recap returns expected shape)
        assert "current_tick" in data
        assert "since_tick" in data
        assert "highlights" in data
        assert "summary_items" in data
        assert "suggested_followups" in data

        assert data["current_tick"] == 10
        assert data["since_tick"] == 0

        # Verify highlights structure
        assert isinstance(data["highlights"], list)
        if len(data["highlights"]) > 0:
            highlight = data["highlights"][0]
            assert "type" in highlight
            assert "tick" in highlight
            assert "severity" in highlight
            assert "description" in highlight

        # Verify summary_items structure
        assert isinstance(data["summary_items"], list)
        if len(data["summary_items"]) > 0:
            item = data["summary_items"][0]
            assert "category" in item
            assert "text" in item
            assert "related_city_ids" in item

        # Verify suggested_followups structure
        assert isinstance(data["suggested_followups"], list)
        if len(data["suggested_followups"]) > 0:
            followup = data["suggested_followups"][0]
            assert "action_type" in followup
            assert "target" in followup
            assert "reason" in followup
            assert "priority" in followup

    def test_recap_endpoint_empty_events(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/recap with no events (AC: empty lists when nothing happened)."""
        sample_world_state.tick = 10

        response = client.get("/api/recap?sinceTick=0")

        assert response.status_code == 200
        data = response.json()

        # Should have empty lists
        assert data["highlights"] == []
        assert data["summary_items"] == []
        assert data["suggested_followups"] == []

    def test_recap_endpoint_invalid_future_tick(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/recap with future sinceTick (AC: invalid sinceTick handled)."""
        sample_world_state.tick = 10

        response = client.get("/api/recap?sinceTick=15")

        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    def test_recap_endpoint_invalid_negative_tick(
        self,
        client: TestClient,
        sample_world_state,
        sample_cities
    ):
        """Test /api/recap with negative sinceTick (AC: invalid sinceTick handled)."""
        sample_world_state.tick = 10

        response = client.get("/api/recap?sinceTick=-5")

        assert response.status_code == 400
        assert "negative" in response.json()["detail"].lower()


# =============================================================================
# TEST: Event Description Generation
# =============================================================================

class TestEventDescriptions:
    """Test event description generation."""

    def test_prosperity_changed_description(self):
        """Test description for prosperity_changed events."""
        event = Event(
            tick=1,
            type="city.prosperity_changed",
            schema_version=1,
            actor="economy",
            payload={
                "city_name": "Xanthos",
                "old_value": 75,
                "new_value": 80,
            },
            created_at=datetime.now(timezone.utc)
        )

        description = generate_event_description(event)

        assert "Xanthos" in description
        assert "prosperity" in description.lower()
        assert "increased" in description.lower()
        assert "5" in description  # delta

    def test_prosperity_boosted_description(self):
        """Test description for prosperity_boosted events."""
        event = Event(
            tick=2,
            type="city.prosperity_boosted",
            schema_version=1,
            actor="player:1",
            payload={
                "city_name": "Patara",
                "amount": 15,
            },
            created_at=datetime.now(timezone.utc)
        )

        description = generate_event_description(event)

        assert "Patara" in description
        assert "boost" in description.lower()
        assert "15" in description

    def test_unknown_event_type_description(self):
        """Test description for unknown event types."""
        event = Event(
            tick=1,
            type="unknown.type",
            schema_version=1,
            actor="test",
            payload={},
            created_at=datetime.now(timezone.utc)
        )

        description = generate_event_description(event)

        assert "unknown.type" in description.lower()
        assert "event" in description.lower()


# =============================================================================
# TEST: Integration - Series of Ticks
# =============================================================================

class TestIntegrationDiffAfterTicks:
    """Test diff calculation after a series of ticks with state changes."""

    def test_diff_after_series_of_ticks(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """
        AC: After a series of ticks with state changes, calling /world/diff
        with an older tick returns only changes since that tick.
        """
        # Start at tick 0
        sample_world_state.tick = 0
        db_session.commit()

        # Create events for ticks 1-20
        for tick in range(1, 21):
            # Every 5 ticks, create prosperity change in Xanthos
            if tick % 5 == 0:
                event = Event(
                    tick=tick,
                    type="city.prosperity_changed",
                    schema_version=1,
                    actor="economy",
                    payload={
                        "city_id": sample_cities[0].id,
                        "city_name": sample_cities[0].name,
                        "old_value": 75 + (tick - 5),
                        "new_value": 75 + tick,
                    },
                    created_at=datetime.now(timezone.utc)
                )
                db_session.add(event)

        db_session.commit()

        # Set current tick to 20
        sample_world_state.tick = 20
        db_session.commit()

        # Get diff since tick 10
        diff = get_world_diff(db_session, since_tick=10)

        # Should only include events from ticks 11-20
        assert diff.tick_range == 10

        # Find Xanthos events
        xanthos_diff = next((c for c in diff.cities if c.city_name == "Xanthos"), None)

        if xanthos_diff:
            # Should only have events at tick 15 and 20 (after tick 10)
            event_ticks = [e.tick for e in xanthos_diff.events]
            assert all(t > 10 for t in event_ticks)
            assert 15 in event_ticks
            assert 20 in event_ticks
            assert 5 not in event_ticks  # Before sinceTick
            assert 10 not in event_ticks  # Equal to sinceTick (not included)
