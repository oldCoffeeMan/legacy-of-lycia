"""
Tests for S2-05: Minimal Schema & Versioning Discipline (v1 Only).

This module tests the schema versioning implementation for both
Event and ActionCommand records:
- Schema version field presence and defaults
- Validation logic to reject non-v1 schemas
- JSON Schema validation for example payloads
"""

import pytest
import json
from pathlib import Path
from jsonschema import validate, ValidationError as JsonSchemaValidationError
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from lycia.models import ActionCommand, ActionCommandStatus, Event, Player, WorldState, City
from lycia.auth import hash_password


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_player(db_session: Session) -> Player:
    """Create a test player for authentication."""
    player = Player(
        username="testplayer_s205",
        email="test_s205@example.com",
        password_hash=hash_password("password123")
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    return player


@pytest.fixture
def test_city(db_session: Session) -> City:
    """Create a test city for event examples."""
    city = City(
        name="Rome_S205",
        region="Latium",
        prosperity=50,
        unrest=10
    )
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)
    return city


@pytest.fixture
def authenticated_client(client: TestClient, test_player: Player) -> TestClient:
    """Create an authenticated test client."""
    # Login to get session cookie (Form data, not JSON)
    with client:
        response = client.post(
            "/login",
            data={"username": "testplayer_s205", "password": "password123"},
            follow_redirects=False
        )
        # Login redirects on success
        assert response.status_code in (200, 302)
    return client


@pytest.fixture
def world_state(db_session: Session) -> WorldState:
    """Ensure world state exists."""
    ws = db_session.query(WorldState).first()
    if not ws:
        ws = WorldState(id=1, tick=0)
        db_session.add(ws)
        db_session.commit()
        db_session.refresh(ws)
    return ws


@pytest.fixture
def action_command_schema_v1():
    """Load ActionCommand JSON Schema v1."""
    schema_path = Path(__file__).parent.parent / "schemas" / "action_command_v1.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def event_schema_v1():
    """Load Event JSON Schema v1."""
    schema_path = Path(__file__).parent.parent / "schemas" / "event_v1.json"
    with open(schema_path) as f:
        return json.load(f)


# =============================================================================
# TESTS: ActionCommand Schema Version
# =============================================================================

class TestActionCommandSchemaVersion:
    """Tests for ActionCommand schema_version field and validation."""

    def test_action_command_has_schema_version_field(self, db_session: Session, test_player: Player):
        """Verify ActionCommand model has schema_version field with default=1."""
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            # schema_version should default to 1
            params={"message": "test"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()
        db_session.refresh(command)

        assert hasattr(command, "schema_version")
        assert command.schema_version == 1

    def test_action_command_explicit_schema_version(self, db_session: Session, test_player: Player):
        """Verify ActionCommand can be created with explicit schema_version=1."""
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            schema_version=1,
            params={"message": "test"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()
        db_session.refresh(command)

        assert command.schema_version == 1

    def test_enqueue_command_with_schema_version_1_succeeds(
        self,
        authenticated_client: TestClient,
        world_state: WorldState
    ):
        """
        Test Scenario 1: Submitting a command with schema_version=1 succeeds when payload is valid.
        """
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "schema_version": 1,
                "params": {"message": "Hello from v1 schema"},
                "valid_from_tick": 10,
                "expires_at_tick": 20
            }
        )

        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert "command_id" in data
        assert data["status"] == "pending"
        assert "schema_version" not in data  # Response doesn't expose internal fields

    def test_enqueue_command_with_schema_version_2_fails(
        self,
        authenticated_client: TestClient,
        world_state: WorldState
    ):
        """
        Test Scenario 2: Submitting a command with schema_version≠1 returns a 4xx error with a clear message.
        """
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "schema_version": 2,  # Invalid: only v1 supported
                "params": {"message": "Hello from v2 schema"},
                "valid_from_tick": 10,
                "expires_at_tick": 20
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "schema_version" in data["detail"].lower()
        assert "2" in str(data["detail"])
        assert "only schema_version=1" in data["detail"].lower() or "unsupported" in data["detail"].lower()

    def test_enqueue_command_with_schema_version_0_fails(
        self,
        authenticated_client: TestClient,
        world_state: WorldState
    ):
        """
        Test Scenario 2 (variant): Submitting a command with schema_version=0 fails.
        """
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "schema_version": 0,
                "params": {"message": "Hello from v0 schema"},
                "valid_from_tick": 10,
                "expires_at_tick": 20
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "schema_version" in data["detail"].lower()

    def test_enqueue_command_with_schema_version_99_fails(
        self,
        authenticated_client: TestClient,
        world_state: WorldState
    ):
        """
        Test Scenario 2 (variant): Submitting a command with schema_version=99 fails.
        """
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "schema_version": 99,
                "params": {"message": "Hello from future schema"},
                "valid_from_tick": 10,
                "expires_at_tick": 20
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "schema_version" in data["detail"].lower()
        assert "99" in str(data["detail"])

    def test_enqueue_command_defaults_to_schema_version_1(
        self,
        authenticated_client: TestClient,
        world_state: WorldState,
        db_session: Session
    ):
        """Verify that when schema_version is omitted, it defaults to 1."""
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                # schema_version omitted - should default to 1
                "params": {"message": "Default schema version"},
                "valid_from_tick": 10,
                "expires_at_tick": 20
            }
        )

        assert response.status_code == 200
        command_id = response.json()["command_id"]

        # Verify in database
        command = db_session.query(ActionCommand).filter_by(id=command_id).first()
        assert command is not None
        assert command.schema_version == 1


# =============================================================================
# TESTS: Event Schema Version
# =============================================================================

class TestEventSchemaVersion:
    """Tests for Event schema_version field and type field."""

    def test_event_has_type_and_schema_version_fields(self, db_session: Session):
        """Verify Event model has 'type' and 'schema_version' fields."""
        event = Event(
            tick=1,
            type="test.event",
            schema_version=1,
            actor="test_system",
            payload={"test": "data"}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert hasattr(event, "type")
        assert hasattr(event, "schema_version")
        assert event.type == "test.event"
        assert event.schema_version == 1

    def test_event_schema_version_defaults_to_1(self, db_session: Session):
        """Verify Event schema_version defaults to 1."""
        event = Event(
            tick=1,
            type="test.default_version",
            # schema_version omitted - should default to 1
            actor="test_system",
            payload={"test": "data"}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.schema_version == 1

    def test_event_type_field_renamed_from_event_type(self, db_session: Session):
        """
        Verify that Event uses 'type' field (not 'event_type').
        This ensures the migration worked correctly.
        """
        event = Event(
            tick=1,
            type="city.prosperity_boosted",
            schema_version=1,
            actor="player:1",
            payload={"city_id": 1, "amount": 10}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        # Should have 'type' attribute
        assert hasattr(event, "type")
        assert event.type == "city.prosperity_boosted"

        # Should NOT have 'event_type' attribute
        assert not hasattr(event, "event_type")


# =============================================================================
# TESTS: JSON Schema Validation
# =============================================================================

class TestJSONSchemaValidation:
    """Tests for JSON Schema files and validation."""

    def test_action_command_schema_file_exists(self, action_command_schema_v1):
        """Verify ActionCommand JSON Schema v1 file exists and is valid JSON."""
        assert action_command_schema_v1 is not None
        assert "$schema" in action_command_schema_v1
        assert action_command_schema_v1["title"] == "ActionCommand"

    def test_event_schema_file_exists(self, event_schema_v1):
        """Verify Event JSON Schema v1 file exists and is valid JSON."""
        assert event_schema_v1 is not None
        assert "$schema" in event_schema_v1
        assert event_schema_v1["title"] == "Event"

    def test_action_command_valid_payload_passes_schema_validation(self, action_command_schema_v1):
        """
        Test Scenario 3: JSON Schema files validate the example payloads successfully.

        Valid ActionCommand payload should pass schema validation.
        """
        valid_payload = {
            "intent": "prosperity_boost",
            "schema_version": 1,
            "version": 1,
            "params": {
                "city_id": 1,
                "amount": 10
            },
            "valid_from_tick": 100,
            "expires_at_tick": 105
        }

        # Should not raise ValidationError
        validate(instance=valid_payload, schema=action_command_schema_v1)

    def test_action_command_invalid_schema_version_fails_validation(self, action_command_schema_v1):
        """ActionCommand with schema_version≠1 should fail schema validation."""
        invalid_payload = {
            "intent": "prosperity_boost",
            "schema_version": 2,  # Invalid: must be 1
            "version": 1,
            "params": {
                "city_id": 1,
                "amount": 10
            },
            "valid_from_tick": 100,
            "expires_at_tick": 105
        }

        with pytest.raises(JsonSchemaValidationError) as exc_info:
            validate(instance=invalid_payload, schema=action_command_schema_v1)

        assert "schema_version" in str(exc_info.value).lower() or "const" in str(exc_info.value).lower()

    def test_action_command_missing_required_fields_fails_validation(self, action_command_schema_v1):
        """ActionCommand missing required fields should fail schema validation."""
        invalid_payload = {
            "intent": "prosperity_boost",
            "schema_version": 1,
            # Missing: version, params, valid_from_tick, expires_at_tick
        }

        with pytest.raises(JsonSchemaValidationError):
            validate(instance=invalid_payload, schema=action_command_schema_v1)

    def test_event_valid_payload_passes_schema_validation(self, event_schema_v1):
        """
        Test Scenario 3: JSON Schema files validate the example payloads successfully.

        Valid Event payload should pass schema validation.
        """
        valid_payload = {
            "type": "city.prosperity_boosted",
            "schema_version": 1,
            "tick": 42,
            "actor": "player:1",
            "payload": {
                "city_id": 1,
                "city_name": "Rome",
                "player_id": 1,
                "amount": 10,
                "old_prosperity": 50,
                "new_prosperity": 60
            },
            "command_id": 123
        }

        # Should not raise ValidationError
        validate(instance=valid_payload, schema=event_schema_v1)

    def test_event_invalid_schema_version_fails_validation(self, event_schema_v1):
        """Event with schema_version≠1 should fail schema validation."""
        invalid_payload = {
            "type": "city.prosperity_boosted",
            "schema_version": 99,  # Invalid: must be 1
            "tick": 42,
            "actor": "player:1",
            "payload": {
                "city_id": 1,
                "amount": 10
            }
        }

        with pytest.raises(JsonSchemaValidationError) as exc_info:
            validate(instance=invalid_payload, schema=event_schema_v1)

        assert "schema_version" in str(exc_info.value).lower() or "const" in str(exc_info.value).lower()

    def test_event_missing_required_fields_fails_validation(self, event_schema_v1):
        """Event missing required fields should fail schema validation."""
        invalid_payload = {
            "type": "city.prosperity_boosted",
            "schema_version": 1,
            # Missing: tick, actor, payload
        }

        with pytest.raises(JsonSchemaValidationError):
            validate(instance=invalid_payload, schema=event_schema_v1)

    def test_event_with_null_command_id_passes_validation(self, event_schema_v1):
        """Event with command_id=null should pass validation (it's optional)."""
        valid_payload = {
            "type": "tick.completed",
            "schema_version": 1,
            "tick": 42,
            "actor": "system",
            "payload": {
                "duration_ms": 150
            },
            "command_id": None  # Optional field
        }

        # Should not raise ValidationError
        validate(instance=valid_payload, schema=event_schema_v1)

    def test_action_command_all_examples_validate(self, action_command_schema_v1):
        """All example payloads in ActionCommand schema should validate."""
        examples = action_command_schema_v1.get("examples", [])
        assert len(examples) > 0, "Schema should have examples"

        for example in examples:
            # Should not raise ValidationError
            validate(instance=example, schema=action_command_schema_v1)

    def test_event_all_examples_validate(self, event_schema_v1):
        """All example payloads in Event schema should validate."""
        examples = event_schema_v1.get("examples", [])
        assert len(examples) > 0, "Schema should have examples"

        for example in examples:
            # Should not raise ValidationError
            validate(instance=example, schema=event_schema_v1)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSchemaVersioningIntegration:
    """Integration tests for schema versioning across the system."""

    def test_end_to_end_command_with_schema_version(
        self,
        authenticated_client: TestClient,
        db_session: Session,
        test_city: City,
        world_state: WorldState
    ):
        """
        End-to-end test: Submit command with schema_version=1,
        verify it's stored correctly in database with proper schema_version.
        """
        # Submit command with schema_version=1
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "prosperity_boost",
                "version": 1,
                "schema_version": 1,
                "params": {"city_id": test_city.id, "amount": 10},
                "valid_from_tick": 1,
                "expires_at_tick": 5
            }
        )

        assert response.status_code == 200
        command_id = response.json()["command_id"]

        # Verify command in database has correct schema_version
        command = db_session.query(ActionCommand).filter_by(id=command_id).first()
        assert command is not None
        assert command.intent == "prosperity_boost"
        assert command.schema_version == 1
        assert command.version == 1

        # Create an event manually to test Event model has correct fields
        event = Event(
            tick=1,
            type="city.prosperity_boosted",
            schema_version=1,
            actor="test",
            payload={"test": "data"}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        # Verify event has proper fields with correct values
        assert event.type == "city.prosperity_boosted"
        assert event.schema_version == 1
        assert hasattr(event, "type")
        assert hasattr(event, "schema_version")
        assert not hasattr(event, "event_type")  # Old field should not exist
