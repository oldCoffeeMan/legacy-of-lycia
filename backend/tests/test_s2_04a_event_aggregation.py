"""
Tests for S2-04A: Per-Tick Event Aggregation Fix.

This test module verifies that all events emitted by all subsystems
during a tick are collected into a single shared buffer and persisted
correctly.
"""

from sqlalchemy.orm import Session

from lycia.models import Event
from lycia.subsystems.protocol import TickContext
from lycia.subsystems.phase import SubsystemPhase
from lycia.subsystems.context import TickContextImpl
from lycia.subsystems.event_persistence_subsystem import EventPersistenceSubsystem
import random


# Test subsystems that emit different events
class TestSubsystemA:
    """Test subsystem that emits event type 'test.a'."""

    @property
    def name(self) -> str:
        return "test_subsystem_a"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.ECONOMY

    @property
    def dependencies(self) -> list[str]:
        return []

    def apply(self, ctx: TickContext) -> None:
        """Emit test event A."""
        ctx.emit("test.a", {"source": "subsystem_a", "value": 42})


class TestSubsystemB:
    """Test subsystem that emits event type 'test.b'."""

    @property
    def name(self) -> str:
        return "test_subsystem_b"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.POLITICS

    @property
    def dependencies(self) -> list[str]:
        return []

    def apply(self, ctx: TickContext) -> None:
        """Emit test event B."""
        ctx.emit("test.b", {"source": "subsystem_b", "value": 99})


class TestSubsystemMultiEvent:
    """Test subsystem that emits multiple events."""

    @property
    def name(self) -> str:
        return "test_subsystem_multi"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.INTENTS

    @property
    def dependencies(self) -> list[str]:
        return []

    def apply(self, ctx: TickContext) -> None:
        """Emit multiple test events."""
        ctx.emit("test.multi.1", {"index": 1})
        ctx.emit("test.multi.2", {"index": 2})
        ctx.emit("test.multi.3", {"index": 3})


# =============================================================================
# TESTS
# =============================================================================

class TestMultiSubsystemEventAggregation:
    """Test that events from multiple subsystems are aggregated correctly."""

    def test_events_from_multiple_subsystems_aggregated(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that events from multiple subsystems appear in same tick."""
        # Create shared event buffer (simulating TickExecutor behavior)
        tick_events: list[dict] = []

        # Create contexts for multiple subsystems with SHARED buffer
        ctx_a = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_a",
            config={},
            events=tick_events  # Shared
        )

        ctx_b = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_b",
            config={},
            events=tick_events  # Same shared list
        )

        # Execute subsystems
        subsystem_a = TestSubsystemA()
        subsystem_b = TestSubsystemB()

        subsystem_a.apply(ctx_a)
        subsystem_b.apply(ctx_b)

        # Verify both events are in the shared buffer
        assert len(tick_events) == 2
        assert tick_events[0]["type"] == "test.a"
        assert tick_events[0]["subsystem"] == "test_subsystem_a"
        assert tick_events[1]["type"] == "test.b"
        assert tick_events[1]["subsystem"] == "test_subsystem_b"

        # Now persist using EventPersistenceSubsystem
        ctx_persist = TickContextImpl(
            tick=10,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="event_persistence",
            config={},
            events=tick_events  # Same shared list
        )

        persistence = EventPersistenceSubsystem()
        persistence.apply(ctx_persist)

        # Verify both events were persisted to database
        events = db_session.query(Event).filter_by(tick=10).all()
        assert len(events) == 2

        event_types = {e.type for e in events}
        assert "test.a" in event_types
        assert "test.b" in event_types

        # Verify actors (subsystem names)
        actors = {e.actor for e in events}
        assert "test_subsystem_a" in actors
        assert "test_subsystem_b" in actors

    def test_multiple_events_from_single_subsystem(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that a single subsystem can emit multiple events."""
        tick_events: list[dict] = []

        ctx = TickContextImpl(
            tick=15,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_multi",
            config={},
            events=tick_events
        )

        subsystem = TestSubsystemMultiEvent()
        subsystem.apply(ctx)

        # Verify 3 events emitted
        assert len(tick_events) == 3
        assert all(e["subsystem"] == "test_subsystem_multi" for e in tick_events)

        # Persist
        ctx_persist = TickContextImpl(
            tick=15,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="event_persistence",
            config={},
            events=tick_events
        )

        persistence = EventPersistenceSubsystem()
        persistence.apply(ctx_persist)

        # Verify all 3 persisted
        events = db_session.query(Event).filter_by(tick=15).all()
        assert len(events) == 3

    def test_event_ordering_matches_subsystem_execution_order(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that events appear in the order subsystems executed."""
        tick_events: list[dict] = []

        # Execute subsystems in specific order
        # INTENTS phase first
        ctx_multi = TickContextImpl(
            tick=20,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_multi",
            config={},
            events=tick_events
        )
        TestSubsystemMultiEvent().apply(ctx_multi)

        # Then ECONOMY
        ctx_a = TickContextImpl(
            tick=20,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_a",
            config={},
            events=tick_events
        )
        TestSubsystemA().apply(ctx_a)

        # Then POLITICS
        ctx_b = TickContextImpl(
            tick=20,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_b",
            config={},
            events=tick_events
        )
        TestSubsystemB().apply(ctx_b)

        # Verify ordering in buffer
        assert len(tick_events) == 5
        # First 3 from multi
        assert tick_events[0]["subsystem"] == "test_subsystem_multi"
        assert tick_events[1]["subsystem"] == "test_subsystem_multi"
        assert tick_events[2]["subsystem"] == "test_subsystem_multi"
        # Then from A
        assert tick_events[3]["subsystem"] == "test_subsystem_a"
        # Then from B
        assert tick_events[4]["subsystem"] == "test_subsystem_b"


class TestNoDoubleWriting:
    """Test that events are not duplicated across ticks."""

    def test_events_not_duplicated_across_ticks(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that running multiple ticks doesn't duplicate events."""
        # Tick 1
        tick1_events: list[dict] = []

        ctx1 = TickContextImpl(
            tick=1,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_a",
            config={},
            events=tick1_events
        )
        TestSubsystemA().apply(ctx1)

        ctx1_persist = TickContextImpl(
            tick=1,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="event_persistence",
            config={},
            events=tick1_events
        )
        EventPersistenceSubsystem().apply(ctx1_persist)

        # Tick 2 (fresh event buffer)
        tick2_events: list[dict] = []

        ctx2 = TickContextImpl(
            tick=2,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_a",
            config={},
            events=tick2_events
        )
        TestSubsystemA().apply(ctx2)

        ctx2_persist = TickContextImpl(
            tick=2,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="event_persistence",
            config={},
            events=tick2_events
        )
        EventPersistenceSubsystem().apply(ctx2_persist)

        # Verify each tick has exactly one event
        tick1_persisted = db_session.query(Event).filter_by(tick=1).all()
        tick2_persisted = db_session.query(Event).filter_by(tick=2).all()

        assert len(tick1_persisted) == 1
        assert len(tick2_persisted) == 1

        # Verify tick numbers are correct
        assert tick1_persisted[0].tick == 1
        assert tick2_persisted[0].tick == 2

    def test_correct_tick_values_in_persisted_events(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that persisted events have correct tick values."""
        for tick_num in [5, 10, 15]:
            tick_events: list[dict] = []

            ctx = TickContextImpl(
                tick=tick_num,
                db=db_session,
                rng=random.Random(42),
                subsystem_name="test_subsystem_a",
                config={},
                events=tick_events
            )
            TestSubsystemA().apply(ctx)

            ctx_persist = TickContextImpl(
                tick=tick_num,
                db=db_session,
                rng=random.Random(42),
                subsystem_name="event_persistence",
                config={},
                events=tick_events
            )
            EventPersistenceSubsystem().apply(ctx_persist)

            # Verify tick number
            events = db_session.query(Event).filter_by(tick=tick_num).all()
            assert len(events) == 1
            assert events[0].tick == tick_num


class TestBackwardCompatibility:
    """Test that the fix doesn't break existing functionality."""

    def test_context_without_shared_events_still_works(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that TickContextImpl works without events parameter (backward compat)."""
        # Create context WITHOUT providing events parameter
        ctx = TickContextImpl(
            tick=25,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="test_subsystem_a",
            config={}
            # Note: no events parameter
        )

        # Should create its own event list
        subsystem = TestSubsystemA()
        subsystem.apply(ctx)

        # Should have event in its own buffer
        assert len(ctx.events) == 1
        assert ctx.events[0]["type"] == "test.a"

    def test_persistence_subsystem_sees_all_events(
        self,
        db_session: Session,
        sample_world_state
    ):
        """Test that EventPersistenceSubsystem sees all tick events (AC from patch)."""
        tick_events: list[dict] = []

        # Multiple subsystems emit events
        for subsystem_class in [TestSubsystemA, TestSubsystemB, TestSubsystemMultiEvent]:
            subsystem = subsystem_class()
            ctx = TickContextImpl(
                tick=30,
                db=db_session,
                rng=random.Random(42),
                subsystem_name=subsystem.name,
                config={},
                events=tick_events
            )
            subsystem.apply(ctx)

        # EventPersistenceSubsystem should see all 5 events (1+1+3)
        ctx_persist = TickContextImpl(
            tick=30,
            db=db_session,
            rng=random.Random(42),
            subsystem_name="event_persistence",
            config={},
            events=tick_events
        )

        # Before persistence, context should see all events
        assert len(ctx_persist.events) == 5

        persistence = EventPersistenceSubsystem()
        persistence.apply(ctx_persist)

        # All 5 should be persisted
        events = db_session.query(Event).filter_by(tick=30).all()
        assert len(events) == 5
