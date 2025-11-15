"""
Tests for S2-04: Event Sourcing & Snapshots.

This module tests the event sourcing implementation including:
- Event persistence
- Snapshot creation
- Event replay
- State reconstruction
- Corrupt event handling
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from lycia.models import (
    Event,
    WorldSnapshot,
    CitySnapshot,
)
from lycia.subsystems.event_persistence_subsystem import EventPersistenceSubsystem
from lycia.subsystems.snapshot_subsystem import SnapshotSubsystem
from lycia.subsystems.context import TickContextImpl
from lycia.event_sourcing import EventReplayer, get_event_reducer_registry
from lycia.event_sourcing.example_reducers import (
    CityProsperityChangedReducer,
    CityProsperityBoostedReducer,
)
from lycia.settings import settings
import random


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def event_persistence_subsystem():
    """Create event persistence subsystem."""
    return EventPersistenceSubsystem()


@pytest.fixture
def snapshot_subsystem():
    """Create snapshot subsystem."""
    return SnapshotSubsystem()


@pytest.fixture
def event_replayer(db_session: Session):
    """Create event replayer."""
    return EventReplayer(db_session)


@pytest.fixture(autouse=True)
def setup_reducers():
    """Register event reducers for tests."""
    registry = get_event_reducer_registry()
    registry.clear()
    registry.register(CityProsperityChangedReducer())
    registry.register(CityProsperityBoostedReducer())
    yield
    registry.clear()


# =============================================================================
# TEST: Event Persistence
# =============================================================================

class TestEventPersistence:
    """Test event persistence subsystem."""

    def test_events_persisted_to_database(
        self,
        db_session: Session,
        event_persistence_subsystem,
        sample_world_state
    ):
        """Test that emitted events are persisted to database."""
        # Create context and emit events
        ctx = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem",
            config={}
        )

        ctx.emit("test.event", {"data": "value1"})
        ctx.emit("test.event2", {"data": "value2"})

        # Persist events
        event_persistence_subsystem.apply(ctx)

        # Verify events in database
        events = db_session.query(Event).all()
        assert len(events) == 2

        assert events[0].tick == 10
        assert events[0].type == "test.event"
        assert events[0].actor == "test_subsystem"
        assert events[0].payload == {"data": "value1"}

        assert events[1].type == "test.event2"
        assert events[1].payload == {"data": "value2"}

    def test_event_sourcing_disabled(
        self,
        db_session: Session,
        event_persistence_subsystem,
        sample_world_state,
        monkeypatch
    ):
        """Test that events are not persisted when event sourcing is disabled."""
        # Disable event sourcing
        monkeypatch.setattr(settings, "enable_event_sourcing", False)

        # Config with event persistence disabled (S2-07)
        config_disabled = {
            "events": {
                "enable_persistence": False
            }
        }

        ctx = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem",
            config=config_disabled
        )

        ctx.emit("test.event", {"data": "value"})
        event_persistence_subsystem.apply(ctx)

        # No events should be persisted
        events = db_session.query(Event).all()
        assert len(events) == 0

    def test_event_with_command_id(
        self,
        db_session: Session,
        event_persistence_subsystem,
        sample_world_state
    ):
        """Test that events can be linked to action commands."""
        ctx = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem",
            config={}
        )

        # Emit event with command_id
        ctx._events.append({
            "type": "test.event",
            "data": {"value": 123},
            "command_id": 456
        })

        event_persistence_subsystem.apply(ctx)

        # Verify command_id is stored
        event = db_session.query(Event).first()
        assert event.command_id == 456


# =============================================================================
# TEST: Snapshot Creation
# =============================================================================

class TestSnapshotCreation:
    """Test snapshot creation subsystem."""

    def test_snapshot_created_on_frequency_tick(
        self,
        db_session: Session,
        snapshot_subsystem,
        sample_world_state,
        sample_cities,
        monkeypatch
    ):
        """Test that snapshots are created every K ticks (AC: Snapshot frequency)."""
        # Set snapshot frequency to 60
        monkeypatch.setattr(settings, "snapshot_frequency", 60)

        # Tick 60 should create snapshot
        ctx = TickContextImpl(
            tick=60,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="snapshot_creation",
            config={}
        )

        snapshot_subsystem.apply(ctx)

        # Verify world snapshot created
        world_snapshot = db_session.query(WorldSnapshot).filter_by(tick=60).first()
        assert world_snapshot is not None
        assert world_snapshot.current_tick == 0  # From sample_world_state

        # Verify city snapshots created
        city_snapshots = db_session.query(CitySnapshot).filter_by(tick=60).all()
        assert len(city_snapshots) == len(sample_cities)

        # Verify city snapshot data
        city = sample_cities[0]
        snapshot = db_session.query(CitySnapshot).filter_by(
            tick=60,
            city_id=city.id
        ).first()

        assert snapshot.name == city.name
        assert snapshot.prosperity == city.prosperity
        assert snapshot.unrest == city.unrest

    def test_snapshot_not_created_on_non_frequency_tick(
        self,
        db_session: Session,
        snapshot_subsystem,
        sample_world_state,
        sample_cities,
        monkeypatch
    ):
        """Test that snapshots are not created on non-frequency ticks."""
        monkeypatch.setattr(settings, "snapshot_frequency", 60)

        # Tick 59 should NOT create snapshot
        ctx = TickContextImpl(
            tick=59,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="snapshot_creation",
            config={}
        )

        snapshot_subsystem.apply(ctx)

        # No snapshots should exist
        assert db_session.query(WorldSnapshot).filter_by(tick=59).first() is None
        assert db_session.query(CitySnapshot).filter_by(tick=59).count() == 0

    def test_snapshot_frequency_change(
        self,
        db_session: Session,
        snapshot_subsystem,
        sample_world_state,
        sample_cities,
        monkeypatch
    ):
        """Test changing snapshot frequency (AC: Snapshot frequency change does not affect correctness)."""
        # Create snapshot at tick 60 with frequency 60 (S2-07: use config)
        config_60 = {"snapshots": {"frequency": 60}}
        ctx = TickContextImpl(tick=60, db=db_session, rng=random.Random(42), subsystem_name="snapshot_creation", config=config_60)
        snapshot_subsystem.apply(ctx)

        # Change frequency to 30 (S2-07: use config)
        config_30 = {"snapshots": {"frequency": 30}}

        # Should create snapshot at tick 90 (next multiple of 30)
        ctx = TickContextImpl(tick=90, db=db_session, rng=random.Random(42), subsystem_name="snapshot_creation", config=config_30)
        snapshot_subsystem.apply(ctx)

        # Verify both snapshots exist
        assert db_session.query(WorldSnapshot).filter_by(tick=60).first() is not None
        assert db_session.query(WorldSnapshot).filter_by(tick=90).first() is not None

    def test_duplicate_snapshot_prevented(
        self,
        db_session: Session,
        snapshot_subsystem,
        sample_world_state,
        sample_cities,
        monkeypatch
    ):
        """Test that duplicate snapshots are not created."""
        monkeypatch.setattr(settings, "snapshot_frequency", 60)

        ctx = TickContextImpl(tick=60, db=db_session, rng=random.Random(42), subsystem_name="snapshot_creation", config={})

        # Create snapshot twice
        snapshot_subsystem.apply(ctx)
        snapshot_subsystem.apply(ctx)

        # Should have only one snapshot
        assert db_session.query(WorldSnapshot).filter_by(tick=60).count() == 1

        # Cities should also have only one snapshot each
        city = sample_cities[0]
        assert db_session.query(CitySnapshot).filter_by(tick=60, city_id=city.id).count() == 1


# =============================================================================
# TEST: Event Replay
# =============================================================================

class TestEventReplay:
    """Test event replay mechanism."""

    def test_replay_from_events_only(
        self,
        db_session: Session,
        event_replayer,
        sample_world_state,
        sample_cities
    ):
        """Test replay when no snapshots exist."""
        city = sample_cities[0]
        original_prosperity = city.prosperity

        # Create events
        event1 = Event(
            tick=1,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": city.id,
                "old_prosperity": original_prosperity,
                "new_prosperity": original_prosperity + 10
            },
            created_at=datetime.now(timezone.utc)
        )

        event2 = Event(
            tick=2,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": city.id,
                "old_prosperity": original_prosperity + 10,
                "new_prosperity": original_prosperity + 20
            },
            created_at=datetime.now(timezone.utc)
        )

        db_session.add_all([event1, event2])
        db_session.commit()

        # Replay to tick 2
        result = event_replayer.replay_to_tick(2)

        # Verify replay result
        assert result["target_tick"] == 2
        assert result["snapshot_tick"] == 0  # No snapshot
        assert result["events_applied"] == 2

        # Verify state was reconstructed
        db_session.refresh(city)
        assert city.prosperity == original_prosperity + 20

    def test_replay_from_snapshot_plus_events(
        self,
        db_session: Session,
        event_replayer,
        sample_world_state,
        sample_cities
    ):
        """Test replay from snapshot + subsequent events (AC: Replay from snapshot + events)."""
        city = sample_cities[0]

        # Create snapshot at tick 10
        snapshot = CitySnapshot(
            tick=10,
            city_id=city.id,
            name=city.name,
            region=city.region,
            prosperity=60,  # Snapshot value
            unrest=city.unrest,
            latitude=city.latitude,
            longitude=city.longitude,
            snapshot_version=1
        )
        db_session.add(snapshot)

        world_snapshot = WorldSnapshot(
            tick=10,
            current_tick=10,
            snapshot_version=1
        )
        db_session.add(world_snapshot)
        db_session.commit()

        # Create event after snapshot
        event = Event(
            tick=15,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": city.id,
                "old_prosperity": 60,
                "new_prosperity": 75
            },
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(event)
        db_session.commit()

        # Replay to tick 15
        result = event_replayer.replay_to_tick(15)

        # Verify used snapshot
        assert result["snapshot_tick"] == 10
        assert result["events_applied"] == 1

        # Verify state
        db_session.refresh(city)
        assert city.prosperity == 75

    def test_replay_with_corrupt_event(
        self,
        db_session: Session,
        event_replayer,
        sample_cities
    ):
        """Test graceful handling of corrupt events (AC: Corrupt event detection)."""
        city = sample_cities[0]

        # Create valid event
        event1 = Event(
            tick=1,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": city.id,
                "old_prosperity": 50,
                "new_prosperity": 60
            },
            created_at=datetime.now(timezone.utc)
        )

        # Create corrupt event (malformed payload)
        event2 = Event(
            tick=2,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={"corrupted": "data"},  # Missing required fields
            created_at=datetime.now(timezone.utc)
        )

        # Create another valid event
        event3 = Event(
            tick=3,
            type="city.prosperity_changed",
            schema_version=1,
            actor="test",
            payload={
                "city_id": city.id,
                "old_prosperity": 60,
                "new_prosperity": 70
            },
            created_at=datetime.now(timezone.utc)
        )

        db_session.add_all([event1, event2, event3])
        db_session.commit()

        # Replay should continue despite corrupt event
        result = event_replayer.replay_to_tick(3)

        # Verify replay continued (graceful skip)
        assert result["events_replayed"] == 3
        assert result["events_errored"] >= 1  # Corrupt event errored

        # Verify state from valid events was applied
        db_session.refresh(city)
        assert city.prosperity == 70  # Both valid events applied

    def test_replay_with_unknown_event_type(
        self,
        db_session: Session,
        event_replayer,
        sample_cities
    ):
        """Test that unknown event types are skipped."""
        # Create event with unregistered type
        event = Event(
            tick=1,
            type="unknown.type",
            schema_version=1,
            actor="test",
            payload={"data": "value"},
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(event)
        db_session.commit()

        # Replay should skip unknown event
        result = event_replayer.replay_to_tick(1)

        assert result["events_skipped"] >= 1


# =============================================================================
# TEST: State Reconstruction
# =============================================================================

class TestStateReconstruction:
    """Test state reconstruction from events."""

    def test_reconstruct_identical_state(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test that replay reconstructs identical state (AC: Result matches live state)."""
        city = sample_cities[0]
        original_prosperity = city.prosperity

        # Apply changes and record events
        event1 = Event(
            tick=1,
            type="city.prosperity_changed",
            schema_version=1,
            actor="economy",
            payload={
                "city_id": city.id,
                "old_prosperity": original_prosperity,
                "new_prosperity": original_prosperity + 5
            },
            created_at=datetime.now(timezone.utc)
        )

        event2 = Event(
            tick=2,
            type="city.prosperity_boosted",
            schema_version=1,
            actor="player:1",
            payload={
                "city_id": city.id,
                "amount": 10,
                "new_prosperity": original_prosperity + 15
            },
            created_at=datetime.now(timezone.utc)
        )

        db_session.add_all([event1, event2])
        db_session.commit()

        # Apply events to live state
        city.prosperity = original_prosperity + 15
        db_session.commit()

        live_prosperity = city.prosperity

        # Reset state
        city.prosperity = original_prosperity
        db_session.commit()

        # Replay events
        replayer = EventReplayer(db_session)
        replayer.replay_to_tick(2)

        # Verify reconstructed state matches
        db_session.refresh(city)
        assert city.prosperity == live_prosperity

    def test_multiple_ticks_with_events(
        self,
        db_session: Session,
        sample_world_state,
        sample_cities
    ):
        """Test reconstruction across multiple ticks (AC: Generate N ticks)."""
        city = sample_cities[0]
        starting_prosperity = city.prosperity

        # Generate events for 10 ticks
        expected_final = starting_prosperity
        for tick in range(1, 11):
            increase = tick  # Increase by tick number
            expected_final += increase

            event = Event(
                tick=tick,
                type="city.prosperity_changed",
                schema_version=1,
                actor="subsystem",
                payload={
                    "city_id": city.id,
                    "old_prosperity": expected_final - increase,
                    "new_prosperity": expected_final
                },
                created_at=datetime.now(timezone.utc)
            )
            db_session.add(event)

        db_session.commit()

        # Replay all events
        replayer = EventReplayer(db_session)
        replayer.replay_to_tick(10)

        # Verify final state
        db_session.refresh(city)
        assert city.prosperity == expected_final


# =============================================================================
# TEST: Event Reducers
# =============================================================================

class TestEventReducers:
    """Test event reducer functionality."""

    def test_reducer_registration(self):
        """Test registering and retrieving reducers."""
        registry = get_event_reducer_registry()
        registry.clear()

        reducer = CityProsperityChangedReducer()
        registry.register(reducer)

        # Retrieve by exact version
        retrieved = registry.get("city.prosperity_changed", 1)
        assert retrieved is not None
        assert retrieved.event_type == "city.prosperity_changed"

        # Retrieve latest
        latest = registry.get_latest("city.prosperity_changed")
        assert latest is not None

    def test_reducer_duplicate_prevention(self):
        """Test that duplicate reducers raise error."""
        registry = get_event_reducer_registry()
        registry.clear()

        reducer1 = CityProsperityChangedReducer()
        reducer2 = CityProsperityChangedReducer()

        registry.register(reducer1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(reducer2)


# =============================================================================
# TEST: Subsystem Properties
# =============================================================================

class TestSubsystemProperties:
    """Test subsystem basic properties."""

    def test_event_persistence_properties(self, event_persistence_subsystem):
        """Test event persistence subsystem properties."""
        assert event_persistence_subsystem.name == "event_persistence"
        assert event_persistence_subsystem.phase.value == "cleanup"
        assert event_persistence_subsystem.dependencies == []

    def test_snapshot_subsystem_properties(self, snapshot_subsystem):
        """Test snapshot subsystem properties."""
        assert snapshot_subsystem.name == "snapshot_creation"
        assert snapshot_subsystem.phase.value == "cleanup"
        assert snapshot_subsystem.dependencies == ["event_persistence"]
