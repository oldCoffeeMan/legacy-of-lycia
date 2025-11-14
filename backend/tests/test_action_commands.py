"""
Tests for S2-03: Action Command Queue (Players & AI Intents).

This module tests the complete action command system including:
- REST API for enqueueing commands
- ActionHandler registry and validation
- INTENTS phase subsystem processing
- Exactly-once processing guarantees
- Temporal validation (valid_from_tick, expires_at_tick)
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from lycia.models import ActionCommand, ActionCommandStatus, WorldState, Player
from lycia.actions import (
    ActionHandler,
    ValidationResult,
    ActionHandlerRegistry,
    get_action_handler_registry,
)
from lycia.actions.handlers import TestActionHandler, ProsperityBoostHandler
from lycia.subsystems.action_command_subsystem import ActionCommandSubsystem
from lycia.subsystems.context import TickContextImpl
from lycia.auth import hash_password, create_session
import random


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_player(db_session: Session) -> Player:
    """Create a test player for authentication."""
    player = Player(
        username="testplayer",
        email="test@example.com",
        password_hash=hash_password("password123")
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    return player


@pytest.fixture
def authenticated_client(client: TestClient, test_player: Player) -> TestClient:
    """Create a test client with authenticated session."""
    # Simulate login by setting session cookie
    with client:
        response = client.post(
            "/login",
            data={"username": "testplayer", "password": "password123"},
            follow_redirects=False
        )
        # Login may return 302 (redirect) or 200 (depending on test mode/client)
        assert response.status_code in [200, 302]
    return client


@pytest.fixture(autouse=True)
def clear_action_registry():
    """Clear the global action registry before each test for isolation."""
    registry = get_action_handler_registry()
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def action_registry():
    """Get the global action handler registry for tests."""
    registry = get_action_handler_registry()
    # Clear and setup handlers for tests that need them
    registry.clear()
    return registry


@pytest.fixture
def action_subsystem():
    """Create action command subsystem for testing."""
    return ActionCommandSubsystem()


# =============================================================================
# TEST: ActionHandler Registry
# =============================================================================

class TestActionHandlerRegistry:
    """Test the ActionHandler registry functionality."""

    def test_register_and_get_handler(self):
        """Test registering and retrieving a handler."""
        registry = ActionHandlerRegistry()
        handler = TestActionHandler()

        registry.register(handler)

        retrieved = registry.get("test_action", 1)
        assert retrieved is not None
        assert retrieved.intent == "test_action"
        assert retrieved.version == 1

    def test_register_duplicate_handler_fails(self):
        """Test that registering duplicate intent@version raises error."""
        registry = ActionHandlerRegistry()
        handler1 = TestActionHandler()
        handler2 = TestActionHandler()

        registry.register(handler1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(handler2)

    def test_get_latest_handler(self):
        """Test getting the latest version of a handler."""
        registry = ActionHandlerRegistry()

        # Create multiple versions (simulated)
        class TestActionV2(TestActionHandler):
            @property
            def version(self) -> int:
                return 2

        registry.register(TestActionHandler())  # v1
        registry.register(TestActionV2())       # v2

        latest = registry.get_latest("test_action")
        assert latest is not None
        assert latest.version == 2

    def test_get_nonexistent_handler(self):
        """Test getting a handler that doesn't exist."""
        registry = ActionHandlerRegistry()

        result = registry.get("nonexistent", 1)
        assert result is None

    def test_unregister_handler(self):
        """Test unregistering a handler."""
        registry = ActionHandlerRegistry()
        handler = TestActionHandler()

        registry.register(handler)
        assert registry.has_handler("test_action", 1)

        registry.unregister("test_action", 1)
        assert not registry.has_handler("test_action", 1)

    def test_list_handlers(self):
        """Test listing all registered handlers."""
        registry = ActionHandlerRegistry()
        registry.register(TestActionHandler())
        registry.register(ProsperityBoostHandler())

        handlers = registry.list_handlers()
        assert len(handlers) == 2
        assert ("test_action", 1) in handlers
        assert ("prosperity_boost", 1) in handlers


# =============================================================================
# TEST: Validation Framework
# =============================================================================

class TestValidationFramework:
    """Test the validation framework (syntactic and semantic)."""

    def test_test_action_handler_validates_message_required(self):
        """Test that test_action handler requires message."""
        handler = TestActionHandler()

        result = handler.validate_params({})
        assert not result.valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "message"
        assert result.errors[0].code == "MISSING_FIELD"

    def test_test_action_handler_validates_message_type(self):
        """Test that test_action handler validates message type."""
        handler = TestActionHandler()

        result = handler.validate_params({"message": 123})
        assert not result.valid
        assert result.errors[0].code == "INVALID_TYPE"

    def test_test_action_handler_validates_message_length(self):
        """Test that test_action handler validates message length."""
        handler = TestActionHandler()

        # Too long
        result = handler.validate_params({"message": "x" * 501})
        assert not result.valid
        assert result.errors[0].code == "VALUE_TOO_LONG"

        # Empty
        result = handler.validate_params({"message": ""})
        assert not result.valid
        assert result.errors[0].code == "EMPTY_VALUE"

    def test_test_action_handler_validates_successfully(self):
        """Test that test_action handler validates valid params."""
        handler = TestActionHandler()

        result = handler.validate_params({"message": "Hello, world!"})
        assert result.valid
        assert len(result.errors) == 0

    def test_prosperity_boost_validates_params(self, db_session):
        """Test prosperity_boost handler parameter validation."""
        handler = ProsperityBoostHandler()

        # Missing fields
        result = handler.validate_params({})
        assert not result.valid
        assert len(result.errors) == 2  # city_id and amount

        # Invalid types
        result = handler.validate_params({"city_id": "1", "amount": "10"})
        assert not result.valid

        # Invalid values
        result = handler.validate_params({"city_id": -1, "amount": 100})
        assert not result.valid

        # Valid params
        result = handler.validate_params({"city_id": 1, "amount": 10})
        assert result.valid

    def test_prosperity_boost_validates_world_state(self, db_session, sample_cities):
        """Test prosperity_boost handler world state validation."""
        handler = ProsperityBoostHandler()

        # City exists
        city = sample_cities[0]
        result = handler.validate_world_state(
            {"city_id": city.id, "amount": 10},
            player_id=1,
            db=db_session,
            tick=1
        )
        assert result.valid

        # City doesn't exist
        result = handler.validate_world_state(
            {"city_id": 99999, "amount": 10},
            player_id=1,
            db=db_session,
            tick=1
        )
        assert not result.valid
        assert result.errors[0].code == "CITY_NOT_FOUND"


# =============================================================================
# TEST: REST API Endpoints
# =============================================================================

class TestActionCommandAPI:
    """Test the REST API for enqueueing action commands."""

    def test_enqueue_command_requires_authentication(self, client: TestClient, sample_world_state):
        """Test that enqueueing a command requires authentication."""
        response = client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "params": {"message": "Hello"},
                "valid_from_tick": 1,
                "expires_at_tick": 5
            }
        )
        assert response.status_code == 401

    def test_enqueue_valid_command(
        self,
        authenticated_client: TestClient,
        action_registry,
        sample_world_state,
        test_player
    ):
        """Test enqueueing a valid action command (AC: Commands return structured validation results)."""
        # Temporarily inject action registry (in real app, it's registered at startup)
        from lycia import app as lycia_app
        original_registry = get_action_handler_registry()

        # Register handlers
        original_registry.register(TestActionHandler())

        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "params": {"message": "Hello, world!"},
                "valid_from_tick": 10,
                "expires_at_tick": 15
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "command_id" in data
        assert data["status"] == "pending"
        assert "submitted_at" in data

    def test_enqueue_command_validates_temporal_constraints(
        self,
        authenticated_client: TestClient,
        action_registry,
        sample_world_state
    ):
        """Test that temporal validation works (valid_from_tick <= expires_at_tick)."""
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "params": {"message": "Hello"},
                "valid_from_tick": 10,
                "expires_at_tick": 5  # Expires before valid
            }
        )

        assert response.status_code == 400
        assert "valid_from_tick must be <= expires_at_tick" in response.json()["detail"]

    def test_enqueue_command_validates_handler_exists(
        self,
        authenticated_client: TestClient,
        sample_world_state
    ):
        """Test that handler existence is validated."""
        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "nonexistent_action",
                "version": 1,
                "params": {},
                "valid_from_tick": 1,
                "expires_at_tick": 5
            }
        )

        assert response.status_code == 400
        assert "No handler registered" in response.json()["detail"]

    def test_enqueue_command_validates_params(
        self,
        authenticated_client: TestClient,
        sample_world_state
    ):
        """Test that syntactic validation works (AC: Rejected commands return structured validation errors)."""
        # Register handler
        registry = get_action_handler_registry()
        registry.register(TestActionHandler())

        response = authenticated_client.post(
            "/api/actions/enqueue",
            json={
                "intent": "test_action",
                "version": 1,
                "params": {},  # Missing 'message'
                "valid_from_tick": 1,
                "expires_at_tick": 5
            }
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "validation_errors" in detail
        errors = detail["validation_errors"]["errors"]
        assert len(errors) > 0
        assert errors[0]["field"] == "message"
        assert errors[0]["code"] == "MISSING_FIELD"

    def test_enqueue_duplicate_command_rejected(
        self,
        authenticated_client: TestClient,
        action_registry,
        sample_world_state
    ):
        """Test that duplicate commands are rejected (AC: Duplicate command submission processed once)."""
        # Register handler
        registry = get_action_handler_registry()
        registry.register(TestActionHandler())

        payload = {
            "intent": "test_action",
            "version": 1,
            "params": {"message": "Hello"},
            "valid_from_tick": 10,
            "expires_at_tick": 15
        }

        # First submission succeeds
        response1 = authenticated_client.post("/api/actions/enqueue", json=payload)
        assert response1.status_code == 200

        # Duplicate submission fails
        response2 = authenticated_client.post("/api/actions/enqueue", json=payload)
        assert response2.status_code == 409
        assert "Duplicate command" in response2.json()["detail"]

    def test_get_my_commands(
        self,
        authenticated_client: TestClient,
        db_session: Session,
        test_player: Player,
        sample_world_state
    ):
        """Test retrieving player's commands."""
        # Create some commands
        cmd1 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Test 1"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        cmd2 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Test 2"},
            valid_from_tick=6,
            expires_at_tick=10,
            status=ActionCommandStatus.PROCESSED
        )
        db_session.add_all([cmd1, cmd2])
        db_session.commit()

        response = authenticated_client.get("/api/actions/my-commands")
        assert response.status_code == 200

        data = response.json()
        assert "commands" in data
        assert len(data["commands"]) == 2

    def test_get_my_commands_filters_by_status(
        self,
        authenticated_client: TestClient,
        db_session: Session,
        test_player: Player,
        sample_world_state
    ):
        """Test filtering commands by status."""
        cmd1 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Test 1"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        cmd2 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Test 2"},
            valid_from_tick=6,
            expires_at_tick=10,
            status=ActionCommandStatus.PROCESSED
        )
        db_session.add_all([cmd1, cmd2])
        db_session.commit()

        response = authenticated_client.get("/api/actions/my-commands?status=pending")
        assert response.status_code == 200

        data = response.json()
        assert len(data["commands"]) == 1
        assert data["commands"][0]["status"] == "pending"


# =============================================================================
# TEST: INTENTS Phase Subsystem
# =============================================================================

class TestActionCommandSubsystem:
    """Test the INTENTS phase subsystem that processes commands."""

    def test_subsystem_properties(self, action_subsystem):
        """Test subsystem basic properties."""
        assert action_subsystem.name == "action_commands"
        assert action_subsystem.phase.value == "intents"
        assert action_subsystem.dependencies == []

    def test_process_pending_command(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test processing a pending command on its valid tick (AC: Commands consumed on eligible tick)."""
        # Register handler
        action_registry.register(TestActionHandler())

        # Create pending command for tick 5
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Process me!"},
            valid_from_tick=5,
            expires_at_tick=10,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        # Update world state to tick 5
        ws = db_session.get(WorldState, 1)
        ws.tick = 5
        db_session.commit()

        # Create context
        events = []
        def emit_event(event_type, data):
            events.append({"type": event_type, "data": data})

        ctx = TickContextImpl(
            tick=5,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="action_commands",
            config={}
        )
        # Patch the action registry
        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            # Command should be processed
            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PROCESSED
            assert command.processed_at_tick == 5
            assert command.processed_at is not None
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_expire_old_command(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test that expired commands are marked as EXPIRED (AC: Expired commands are ignored)."""
        # Create command that expires at tick 5
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Will expire"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        # Process at tick 10 (after expiry)
        ctx = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="action_commands",
            config={}
        )

        # Patch registry
        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            # Command should be expired
            db_session.refresh(command)
            assert command.status == ActionCommandStatus.EXPIRED
            assert command.processed_at_tick == 10
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_reject_command_with_invalid_params(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test that commands with invalid params are rejected (AC: Rejected commands return structured errors)."""
        action_registry.register(TestActionHandler())

        # Create command with invalid params
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"wrong_field": "value"},  # Missing 'message'
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        ctx = TickContextImpl(
            tick=1,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="action_commands",
            config={}
        )

        # Patch registry
        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            # Command should be rejected with validation errors
            db_session.refresh(command)
            assert command.status == ActionCommandStatus.REJECTED
            assert command.validation_errors is not None
            assert len(command.validation_errors["errors"]) > 0
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_commands_processed_exactly_once(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test that commands are processed exactly once (AC: Commands consumed exactly once)."""
        action_registry.register(TestActionHandler())

        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Once only"},
            valid_from_tick=1,
            expires_at_tick=10,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()
        command_id = command.id

        ctx = TickContextImpl(
            tick=1,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="action_commands",
            config={}
        )

        # Patch registry
        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()

            # First execution
            subsystem.apply(ctx)
            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PROCESSED

            # Second execution (simulating idempotency check)
            # The command should not be re-processed because status != PENDING
            first_processed_at = command.processed_at

            subsystem.apply(ctx)
            db_session.refresh(command)

            # Status unchanged, processed_at unchanged
            assert command.status == ActionCommandStatus.PROCESSED
            assert command.processed_at == first_processed_at
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_events_emitted_on_processing(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test that processing a command produces events (AC: Processing produces events)."""
        action_registry.register(TestActionHandler())

        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Emit event"},
            valid_from_tick=1,
            expires_at_tick=5,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        # Track emitted events
        emitted_events = []

        class EventTrackingContext(TickContextImpl):
            def emit(self, event_type: str, data: dict):
                emitted_events.append({"type": event_type, "data": data})

        ctx = EventTrackingContext(
            tick=1,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="action_commands",
            config={}
        )

        # Patch registry
        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            # Check events were emitted
            assert len(emitted_events) > 0
            # Should have handler events + processing summary event
            assert any(e["type"] == "test.action_executed" for e in emitted_events)
            assert any(e["type"] == "action.processed" for e in emitted_events)
        finally:
            acs_module.get_action_handler_registry = original_get_registry


# =============================================================================
# TEST: Test Scenarios from User Story
# =============================================================================

class TestAcceptanceCriteria:
    """Test all acceptance criteria and test scenarios from S2-03."""

    def test_scenario_enqueue_with_valid_from_tick(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test Scenario: Enqueue with valid_from_tick=T → applied exactly on tick T."""
        action_registry.register(TestActionHandler())

        # Enqueue command for tick 10
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Execute on tick 10"},
            valid_from_tick=10,
            expires_at_tick=15,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        # Process at tick 9 (too early)
        ctx = TickContextImpl(tick=9, db=db_session, rng=random.Random(42), subsystem_name="action_commands", config={})

        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PENDING  # Not processed yet

            # Process at tick 10 (valid)
            ctx = TickContextImpl(tick=10, db=db_session, rng=random.Random(42), subsystem_name="action_commands", config={})
            subsystem.apply(ctx)

            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PROCESSED
            assert command.processed_at_tick == 10
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_scenario_past_valid_from_tick(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test Scenario: Enqueue with past valid_from_tick → should still process if not expired."""
        action_registry.register(TestActionHandler())

        # Enqueue command with past valid_from_tick but not expired
        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Past valid_from_tick"},
            valid_from_tick=1,  # Past
            expires_at_tick=100,  # Future
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        # Process at tick 50
        ctx = TickContextImpl(tick=50, db=db_session, rng=random.Random(42), subsystem_name="action_commands", config={})

        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PROCESSED
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_scenario_future_expiry(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state,
        action_registry
    ):
        """Test Scenario: Enqueue with future expiry → processes when valid."""
        action_registry.register(TestActionHandler())

        command = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Future expiry"},
            valid_from_tick=10,
            expires_at_tick=100,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command)
        db_session.commit()

        ctx = TickContextImpl(tick=50, db=db_session, rng=random.Random(42), subsystem_name="action_commands", config={})

        import lycia.subsystems.action_command_subsystem as acs_module
        original_get_registry = acs_module.get_action_handler_registry
        acs_module.get_action_handler_registry = lambda: action_registry

        try:
            subsystem = ActionCommandSubsystem()
            subsystem.apply(ctx)

            db_session.refresh(command)
            assert command.status == ActionCommandStatus.PROCESSED
        finally:
            acs_module.get_action_handler_registry = original_get_registry

    def test_scenario_duplicate_command_submission(
        self,
        db_session: Session,
        test_player: Player,
        sample_world_state
    ):
        """Test Scenario: Duplicate command submission → processed once."""
        # First command
        command1 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "First"},
            valid_from_tick=10,
            expires_at_tick=15,
            status=ActionCommandStatus.PENDING
        )
        db_session.add(command1)
        db_session.commit()

        # Attempt duplicate (same player, intent, valid_from_tick)
        command2 = ActionCommand(
            player_id=test_player.id,
            intent="test_action",
            version=1,
            params={"message": "Duplicate"},  # Different params but same key
            valid_from_tick=10,  # Same tick
            expires_at_tick=15,
            status=ActionCommandStatus.PENDING
        )

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.add(command2)
            db_session.commit()

        db_session.rollback()
