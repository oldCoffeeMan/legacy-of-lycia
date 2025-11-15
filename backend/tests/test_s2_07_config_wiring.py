"""
Test suite for S2-07: Simple Rules/Config Wiring

Tests verify that:
1. Central configuration loads from JSON file
2. TickContext.get_config() returns values from central config
3. Subsystems use get_config() for tunable values
4. Changing config values changes behavior
5. Missing config keys return defaults and log warnings
"""
import json
import logging
from pathlib import Path
from random import Random
from sqlalchemy.orm import Session
from lycia.config_loader import GameplayConfig, _get_default_config
from lycia.subsystems import TickContextImpl
from lycia.subsystems.snapshot_subsystem import SnapshotSubsystem
from lycia.subsystems.event_persistence_subsystem import EventPersistenceSubsystem
from lycia.subsystems.action_command_subsystem import ActionCommandSubsystem
from lycia.models import WorldState, City, ActionCommand, ActionCommandStatus
from datetime import datetime, timezone


def test_config_loads_from_json_file(tmp_path: Path) -> None:
    """
    Test that GameplayConfig loads from JSON file.

    AC: Configuration object loads from JSON file.
    """
    # Create temp config file
    config_file = tmp_path / "test_config.json"
    test_config = {
        "version": "1.0.0-test",
        "snapshots": {
            "frequency": 30
        },
        "events": {
            "enable_persistence": False
        }
    }

    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Load config
    config = GameplayConfig.load(config_file)

    # Verify values
    assert config.get("snapshots.frequency") == 30
    assert config.get("events.enable_persistence") is False
    assert config.get("version") == "1.0.0-test"


def test_config_supports_dot_notation() -> None:
    """
    Test that config supports dot notation for nested keys.

    AC: get_config supports dot notation (e.g., "snapshots.frequency").
    """
    config_data = {
        "level1": {
            "level2": {
                "level3": "deep_value"
            }
        },
        "simple": "value"
    }

    config = GameplayConfig(config_data)

    assert config.get("simple") == "value"
    assert config.get("level1.level2.level3") == "deep_value"
    assert config.get("level1.level2") == {"level3": "deep_value"}


def test_config_returns_default_when_key_missing() -> None:
    """
    Test that get_config returns default when key not found.

    AC: When config key doesn't exist, get_config returns default.
    """
    config = GameplayConfig({"existing_key": "value"})

    # Missing key should return default
    result = config.get("nonexistent_key", default=42)
    assert result == 42

    # Missing nested key
    result = config.get("missing.nested.key", default="fallback")
    assert result == "fallback"


def test_config_warns_on_missing_key(caplog) -> None:
    """
    Test that missing config keys log warnings.

    AC: When requested config key doesn't exist, logs warning.
    """
    config = GameplayConfig({"existing_key": "value"})

    with caplog.at_level(logging.WARNING):
        config.get("missing_key", default="default_value")

    # Should have logged warning
    assert len(caplog.records) > 0
    assert "missing_key" in caplog.text
    assert "default_value" in caplog.text


def test_tick_context_get_config_integration(db_session: Session) -> None:
    """
    Test that TickContext.get_config() works correctly.

    AC: TickContext exposes get_config(key, default) returning values from central config.
    """
    # Create config
    config_dict = {
        "test_param": 123,
        "nested": {
            "value": "hello"
        }
    }

    # Create context with config
    base_rng = Random()
    base_rng.seed(12345)

    ctx = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng,
        subsystem_name="test",
        config=config_dict
    )

    # Test get_config
    assert ctx.get_config("test_param") == 123
    assert ctx.get_config("nested.value") == "hello"
    assert ctx.get_config("missing", default=999) == 999


def test_snapshot_subsystem_uses_config(db_session: Session) -> None:
    """
    Test that SnapshotSubsystem uses ctx.get_config for frequency.

    AC: At least one subsystem uses get_config for tunable value.
    """
    # Create world state
    world = WorldState(id=1, tick=0)
    db_session.add(world)
    db_session.commit()

    # Create city
    city = City(
        name="Test City",
        region="Test Region",
        prosperity=50,
        unrest=10,
        latitude=0.0,
        longitude=0.0
    )
    db_session.add(city)
    db_session.commit()

    # Create subsystem
    subsystem = SnapshotSubsystem()

    # Config with frequency=10
    config_dict = {
        "snapshots": {
            "frequency": 10
        }
    }

    base_rng = Random()
    base_rng.seed(12345)

    # Test at tick 10 (should snapshot)
    ctx1 = TickContextImpl(
        tick=10,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config_dict
    )

    subsystem.apply(ctx1)
    events1 = ctx1.events

    # Should have created snapshot
    assert len(events1) > 0
    assert any(e["type"] == "snapshots.created" for e in events1)
    assert events1[0]["data"]["frequency"] == 10

    # Test at tick 11 (should not snapshot)
    ctx2 = TickContextImpl(
        tick=11,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config_dict
    )

    subsystem.apply(ctx2)
    events2 = ctx2.events

    # Should not have created snapshot
    assert len(events2) == 0


def test_config_change_affects_behavior(db_session: Session) -> None:
    """
    Test that changing config value changes subsystem behavior.

    AC: Changing config value (e.g., snapshot frequency) leads to different behavior.
    """
    # Create world state
    world = WorldState(id=1, tick=0)
    db_session.add(world)
    db_session.commit()

    # Create city
    city = City(
        name="Test City",
        region="Test",
        prosperity=50,
        unrest=10,
        latitude=0.0,
        longitude=0.0
    )
    db_session.add(city)
    db_session.commit()

    subsystem = SnapshotSubsystem()
    base_rng = Random()
    base_rng.seed(12345)

    # Config 1: frequency=20
    config1 = {"snapshots": {"frequency": 20}}
    ctx1 = TickContextImpl(
        tick=20,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config1
    )

    subsystem.apply(ctx1)
    # Should create snapshot at tick 20 with frequency 20
    assert len(ctx1.events) > 0

    # Config 2: frequency=30
    config2 = {"snapshots": {"frequency": 30}}
    ctx2 = TickContextImpl(
        tick=20,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config2
    )

    subsystem.apply(ctx2)
    # Should NOT create snapshot at tick 20 with frequency 30
    assert len(ctx2.events) == 0


def test_event_persistence_uses_config(db_session: Session) -> None:
    """
    Test that EventPersistenceSubsystem uses config.

    AC: Subsystem uses get_config for tunable value.
    """
    subsystem = EventPersistenceSubsystem()
    base_rng = Random()
    base_rng.seed(12345)

    # Config with persistence disabled
    config_disabled = {
        "events": {
            "enable_persistence": False
        }
    }

    ctx1 = TickContextImpl(
        tick=10,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config_disabled
    )

    # Emit some events
    ctx1.emit("test.event", {"value": 123})

    # Apply subsystem - should NOT persist (config disabled)
    subsystem.apply(ctx1)

    # Verify no events persisted to database
    from lycia.models import Event
    events = db_session.query(Event).all()
    assert len(events) == 0

    # Config with persistence enabled
    config_enabled = {
        "events": {
            "enable_persistence": True
        }
    }

    ctx2 = TickContextImpl(
        tick=20,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config_enabled
    )

    # Emit event
    ctx2.emit("test.event", {"value": 456})

    # Apply subsystem - should persist (config enabled)
    subsystem.apply(ctx2)

    # Verify event persisted
    events = db_session.query(Event).all()
    assert len(events) > 0


def test_action_command_subsystem_uses_config(db_session: Session) -> None:
    """
    Test that ActionCommandSubsystem uses config for max_per_tick.

    AC: Subsystem uses get_config for tunable value.
    """
    # Create world state
    world = WorldState(id=1, tick=100)
    db_session.add(world)

    # Create player for commands
    from lycia.models import Player
    from lycia.auth import hash_password

    player = Player(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(player)
    db_session.commit()

    # Register test action handler first
    from lycia.actions import get_action_handler_registry
    from lycia.actions.handlers import TestActionHandler

    registry = get_action_handler_registry()
    if not registry.has_handler("test_action", 1):
        registry.register(TestActionHandler())

    # Create 5 pending commands with unique combinations
    for i in range(5):
        cmd = ActionCommand(
            player_id=player.id,
            intent="test_action",
            schema_version=1,
            version=1,
            params={"message": f"test {i}"},
            status=ActionCommandStatus.PENDING,
            valid_from_tick=90 + i,  # Different valid_from_tick
            expires_at_tick=110
        )
        db_session.add(cmd)

    db_session.commit()

    subsystem = ActionCommandSubsystem()
    base_rng = Random()
    base_rng.seed(12345)

    # Config with max_per_tick=2
    config = {
        "action_commands": {
            "max_per_tick": 2
        }
    }

    ctx = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng,
        subsystem_name=subsystem.name,
        config=config
    )

    # Apply subsystem
    subsystem.apply(ctx)

    # Should have processed only 2 commands (limited by config)
    # All 5 commands are eligible (valid_from_tick <= 100)
    # But max_per_tick=2 limits processing
    processed = db_session.query(ActionCommand).filter(
        ActionCommand.status == ActionCommandStatus.PROCESSED
    ).count()

    assert processed == 2  # Limited by max_per_tick config


def test_config_fallback_to_defaults() -> None:
    """
    Test that config system falls back to defaults if file missing.

    AC: System gracefully handles missing config file.
    """
    # Try to load from nonexistent path
    config = GameplayConfig.load_with_fallback(Path("/nonexistent/config.json"))

    # Should have loaded defaults
    assert config.get("snapshots.frequency") is not None
    assert config.get("events.enable_persistence") is not None


def test_config_tracks_accessed_keys() -> None:
    """
    Test that config tracks which keys have been accessed.

    Useful for debugging and understanding config usage.
    """
    config = GameplayConfig({"key1": "value1", "key2": "value2"})

    # Access some keys
    config.get("key1")
    config.get("key2")
    config.get("missing_key", default="default")

    # Check accessed keys
    accessed = config.get_accessed_keys()
    assert "key1" in accessed
    assert "key2" in accessed
    assert "missing_key" in accessed


def test_default_config_structure() -> None:
    """
    Test that default config has expected structure.

    AC: Default config covers all required tunables.
    """
    defaults = _get_default_config()

    # Verify required sections exist
    assert "snapshots" in defaults
    assert "events" in defaults
    assert "action_commands" in defaults

    # Verify required values
    assert "frequency" in defaults["snapshots"]
    assert "enable_persistence" in defaults["events"]
    assert "max_per_tick" in defaults["action_commands"]


def test_context_warns_on_missing_config_key(caplog, db_session: Session) -> None:
    """
    Test that TickContext logs warning when config key missing.

    AC: When requested config key doesn't exist, logs warning.
    """
    base_rng = Random()
    base_rng.seed(12345)

    ctx = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng,
        subsystem_name="test_subsystem",
        config={}  # Empty config
    )

    with caplog.at_level(logging.WARNING):
        value = ctx.get_config("nonexistent.key", default=42)

    assert value == 42
    assert "nonexistent.key" in caplog.text
    assert "test_subsystem" in caplog.text  # Includes subsystem name in log


def test_config_get_all() -> None:
    """
    Test that get_all() returns entire config.

    Useful for debugging and exporting config.
    """
    config_data = {
        "key1": "value1",
        "nested": {
            "key2": "value2"
        }
    }

    config = GameplayConfig(config_data)
    all_config = config.get_all()

    assert all_config == config_data
    assert "key1" in all_config
    assert "nested" in all_config
    assert all_config["nested"]["key2"] == "value2"
