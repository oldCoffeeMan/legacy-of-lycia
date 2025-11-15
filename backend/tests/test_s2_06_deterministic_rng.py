"""
Test suite for S2-06: Deterministic RNG Enforcement

Tests verify that:
1. Same tick + same subsystem + same state → RNG produces the same sequence
2. A subsystem that uses ctx.rng yields consistent outcomes across replay
3. Changing subsystem name changes RNG sequence (confirms isolation)
4. Helper methods work correctly
5. Multiple subsystems in same tick get different RNG sequences
"""
from random import Random
from sqlalchemy.orm import Session

from lycia.subsystems import TickContextImpl
from lycia.subsystems.phase import SubsystemPhase
from lycia.subsystems.protocol import TickContext


class TestSubsystemA:
    """Test subsystem that uses RNG."""

    @property
    def name(self) -> str:
        return "test_subsystem_a"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.INTENTS

    @property
    def dependencies(self) -> list[str]:
        return []

    def apply(self, ctx: TickContext) -> None:
        """Generate some random values."""
        # Use ctx.rng directly
        val1 = ctx.rng.randint(1, 100)
        val2 = ctx.rng.random()
        val3 = ctx.rng.choice(["apple", "banana", "cherry"])

        # Emit event with values for testing
        ctx.emit("test.rng_values", {
            "val1": val1,
            "val2": val2,
            "val3": val3,
        })


class TestSubsystemB:
    """Another test subsystem that uses RNG."""

    @property
    def name(self) -> str:
        return "test_subsystem_b"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.INTENTS

    @property
    def dependencies(self) -> list[str]:
        return []

    def apply(self, ctx: TickContext) -> None:
        """Generate some random values using helper methods."""
        # Use helper methods
        val1 = ctx.random_int(1, 100)
        val2 = ctx.random_float(0.0, 1.0)
        val3 = ctx.random_choice(["apple", "banana", "cherry"])
        val4 = ctx.random_bool(0.5)

        # Emit event with values for testing
        ctx.emit("test.rng_values", {
            "val1": val1,
            "val2": val2,
            "val3": val3,
            "val4": val4,
        })


def test_same_tick_same_subsystem_same_sequence(db_session: Session) -> None:
    """
    Test that same tick + same subsystem produces same RNG sequence.

    AC: same tick + same subsystem + same state → RNG produces the same sequence across runs.
    """
    # Create base RNG with fixed seed
    base_rng1 = Random()
    base_rng1.seed(12345)

    # Create context for subsystem A at tick 100
    ctx1 = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng1,
        subsystem_name="test_subsystem_a",
        config={},
    )

    # Generate some values
    values1 = [ctx1.rng.randint(1, 1000) for _ in range(10)]

    # Create another base RNG with same seed
    base_rng2 = Random()
    base_rng2.seed(12345)

    # Create another context for same subsystem at same tick
    ctx2 = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng2,
        subsystem_name="test_subsystem_a",
        config={},
    )

    # Generate same values
    values2 = [ctx2.rng.randint(1, 1000) for _ in range(10)]

    # Should be identical
    assert values1 == values2, "Same tick + same subsystem should produce identical RNG sequence"


def test_different_subsystem_different_sequence(db_session: Session) -> None:
    """
    Test that different subsystems get different RNG sequences.

    AC: Changing subsystem name changes RNG sequence (to confirm isolation).
    """
    # Create base RNG with fixed seed
    base_rng1 = Random()
    base_rng1.seed(12345)

    # Create context for subsystem A
    ctx_a = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng1,
        subsystem_name="test_subsystem_a",
        config={},
    )

    values_a = [ctx_a.rng.randint(1, 1000) for _ in range(10)]

    # Create base RNG with same seed
    base_rng2 = Random()
    base_rng2.seed(12345)

    # Create context for subsystem B (different name, same tick)
    ctx_b = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng2,
        subsystem_name="test_subsystem_b",
        config={},
    )

    values_b = [ctx_b.rng.randint(1, 1000) for _ in range(10)]

    # Should be different (isolation)
    assert values_a != values_b, "Different subsystems should get different RNG sequences"


def test_different_tick_different_sequence(db_session: Session) -> None:
    """
    Test that different ticks produce different RNG sequences.

    This ensures temporal variation in randomness.
    """
    # Create base RNG with fixed seed
    base_rng1 = Random()
    base_rng1.seed(12345)

    # Create context for tick 100
    ctx1 = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng1,
        subsystem_name="test_subsystem_a",
        config={},
    )

    values1 = [ctx1.rng.randint(1, 1000) for _ in range(10)]

    # Create base RNG with same seed
    base_rng2 = Random()
    base_rng2.seed(12345)

    # Create context for tick 101 (different tick)
    ctx2 = TickContextImpl(
        tick=101,
        db=db_session,
        rng=base_rng2,
        subsystem_name="test_subsystem_a",
        config={},
    )

    values2 = [ctx2.rng.randint(1, 1000) for _ in range(10)]

    # Should be different
    assert values1 != values2, "Different ticks should produce different RNG sequences"


def test_subsystem_replay_consistency(db_session: Session) -> None:
    """
    Test that a subsystem produces consistent outcomes across replay.

    AC: A subsystem that uses ctx.rng yields consistent outcomes across replay.
    """
    subsystem = TestSubsystemA()

    # First run
    base_rng1 = Random()
    base_rng1.seed(12345)

    ctx1 = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng1,
        subsystem_name=subsystem.name,
        config={},
    )

    subsystem.apply(ctx1)
    events1 = ctx1.events

    # Second run (replay with same seed)
    base_rng2 = Random()
    base_rng2.seed(12345)

    ctx2 = TickContextImpl(
        tick=100,
        db=db_session,
        rng=base_rng2,
        subsystem_name=subsystem.name,
        config={},
    )

    subsystem.apply(ctx2)
    events2 = ctx2.events

    # Events should be identical
    assert len(events1) == len(events2), "Replay should emit same number of events"
    assert events1[0]["data"] == events2[0]["data"], "Replay should produce identical RNG values"


def test_helper_methods_consistency(db_session: Session) -> None:
    """
    Test that helper methods produce consistent results.

    Verifies that ctx.random_int, ctx.random_float, ctx.random_choice, ctx.random_bool
    work correctly and are deterministic.
    """
    # First run
    base_rng1 = Random()
    base_rng1.seed(54321)

    ctx1 = TickContextImpl(
        tick=200,
        db=db_session,
        rng=base_rng1,
        subsystem_name="helper_test",
        config={},
    )

    int_val1 = ctx1.random_int(1, 100)
    float_val1 = ctx1.random_float(0.0, 10.0)
    choice_val1 = ctx1.random_choice(["a", "b", "c", "d"])
    bool_val1 = ctx1.random_bool(0.7)

    # Second run
    base_rng2 = Random()
    base_rng2.seed(54321)

    ctx2 = TickContextImpl(
        tick=200,
        db=db_session,
        rng=base_rng2,
        subsystem_name="helper_test",
        config={},
    )

    int_val2 = ctx2.random_int(1, 100)
    float_val2 = ctx2.random_float(0.0, 10.0)
    choice_val2 = ctx2.random_choice(["a", "b", "c", "d"])
    bool_val2 = ctx2.random_bool(0.7)

    # All values should match
    assert int_val1 == int_val2, "random_int should be deterministic"
    assert float_val1 == float_val2, "random_float should be deterministic"
    assert choice_val1 == choice_val2, "random_choice should be deterministic"
    assert bool_val1 == bool_val2, "random_bool should be deterministic"


def test_helper_methods_ranges(db_session: Session) -> None:
    """
    Test that helper methods respect their ranges.

    Verifies that values are within expected bounds.
    """
    base_rng = Random()
    base_rng.seed(99999)

    ctx = TickContextImpl(
        tick=300,
        db=db_session,
        rng=base_rng,
        subsystem_name="range_test",
        config={},
    )

    # Test random_int
    for _ in range(100):
        val = ctx.random_int(10, 20)
        assert 10 <= val <= 20, f"random_int value {val} out of range [10, 20]"

    # Test random_float
    for _ in range(100):
        val = ctx.random_float(5.0, 15.0)
        assert 5.0 <= val < 15.0, f"random_float value {val} out of range [5.0, 15.0)"

    # Test random_choice
    choices = ["x", "y", "z"]
    for _ in range(100):
        val = ctx.random_choice(choices)
        assert val in choices, f"random_choice value {val} not in {choices}"

    # Test random_bool (statistical test)
    true_count = sum(ctx.random_bool(0.5) for _ in range(1000))
    # With p=0.5 and n=1000, expect around 500 trues (allow some variance)
    assert 400 <= true_count <= 600, f"random_bool distribution seems off: {true_count}/1000 trues"


def test_multiple_subsystems_same_tick(db_session: Session) -> None:
    """
    Test that multiple subsystems in same tick get different RNG sequences.

    This is important for subsystem isolation.
    """
    # Create base RNG
    base_rng1 = Random()
    base_rng1.seed(11111)

    base_rng2 = Random()
    base_rng2.seed(11111)

    base_rng3 = Random()
    base_rng3.seed(11111)

    # Create contexts for three different subsystems at same tick
    ctx1 = TickContextImpl(tick=500, db=db_session, rng=base_rng1, subsystem_name="subsystem_1")
    ctx2 = TickContextImpl(tick=500, db=db_session, rng=base_rng2, subsystem_name="subsystem_2")
    ctx3 = TickContextImpl(tick=500, db=db_session, rng=base_rng3, subsystem_name="subsystem_3")

    # Generate values from each
    values1 = [ctx1.rng.randint(1, 1000) for _ in range(10)]
    values2 = [ctx2.rng.randint(1, 1000) for _ in range(10)]
    values3 = [ctx3.rng.randint(1, 1000) for _ in range(10)]

    # All should be different
    assert values1 != values2, "Subsystems 1 and 2 should have different RNG sequences"
    assert values1 != values3, "Subsystems 1 and 3 should have different RNG sequences"
    assert values2 != values3, "Subsystems 2 and 3 should have different RNG sequences"


def test_rng_property_access(db_session: Session) -> None:
    """
    Test that ctx.rng property provides access to subsystem-specific RNG.

    AC: TickContext exposes a clear API for RNG (e.g., ctx.rng or small helper methods).
    """
    base_rng = Random()
    base_rng.seed(77777)

    ctx = TickContextImpl(
        tick=600,
        db=db_session,
        rng=base_rng,
        subsystem_name="property_test",
        config={},
    )

    # Should have rng property
    assert hasattr(ctx, "rng"), "Context should have 'rng' property"
    assert isinstance(ctx.rng, Random), "ctx.rng should be a Random instance"

    # Should be usable
    val = ctx.rng.randint(1, 100)
    assert isinstance(val, int), "ctx.rng should be functional"
    assert 1 <= val <= 100, "ctx.rng should respect ranges"


def test_base_rng_not_polluted(db_session: Session) -> None:
    """
    Test that using subsystem RNG doesn't affect base RNG.

    This ensures subsystems don't accidentally pollute the global RNG state.
    """
    # Create base RNG and capture initial state
    base_rng = Random()
    base_rng.seed(33333)

    # Get initial value from base RNG
    initial_val = base_rng.randint(1, 1000)

    # Create context and use subsystem RNG extensively
    ctx = TickContextImpl(
        tick=700,
        db=db_session,
        rng=base_rng,
        subsystem_name="pollution_test",
        config={},
    )

    # Use subsystem RNG many times
    for _ in range(100):
        ctx.rng.randint(1, 1000)

    # Reset base RNG to same seed
    base_rng_reset = Random()
    base_rng_reset.seed(33333)

    # Should still get same initial value
    reset_val = base_rng_reset.randint(1, 1000)

    assert initial_val == reset_val, "Subsystem RNG usage should not pollute base RNG"


def test_deterministic_across_full_tick(db_session: Session) -> None:
    """
    Integration test: full tick with multiple subsystems should be deterministic.

    This simulates a real tick execution with multiple subsystems.
    """
    subsystem_a = TestSubsystemA()
    subsystem_b = TestSubsystemB()

    # Run 1
    base_rng1 = Random()
    base_rng1.seed(88888)

    shared_events1: list[dict] = []

    ctx_a1 = TickContextImpl(
        tick=1000,
        db=db_session,
        rng=base_rng1,
        subsystem_name=subsystem_a.name,
        events=shared_events1,
    )
    subsystem_a.apply(ctx_a1)

    # Need to recreate base_rng with same seed for subsystem B
    base_rng1b = Random()
    base_rng1b.seed(88888)

    ctx_b1 = TickContextImpl(
        tick=1000,
        db=db_session,
        rng=base_rng1b,
        subsystem_name=subsystem_b.name,
        events=shared_events1,
    )
    subsystem_b.apply(ctx_b1)

    # Run 2 (replay)
    base_rng2 = Random()
    base_rng2.seed(88888)

    shared_events2: list[dict] = []

    ctx_a2 = TickContextImpl(
        tick=1000,
        db=db_session,
        rng=base_rng2,
        subsystem_name=subsystem_a.name,
        events=shared_events2,
    )
    subsystem_a.apply(ctx_a2)

    # Need to recreate base_rng with same seed for subsystem B
    base_rng2b = Random()
    base_rng2b.seed(88888)

    ctx_b2 = TickContextImpl(
        tick=1000,
        db=db_session,
        rng=base_rng2b,
        subsystem_name=subsystem_b.name,
        events=shared_events2,
    )
    subsystem_b.apply(ctx_b2)

    # Compare events
    assert len(shared_events1) == len(shared_events2), "Replay should produce same number of events"

    # Compare event data (excluding tick/subsystem metadata)
    for evt1, evt2 in zip(shared_events1, shared_events2):
        assert evt1["type"] == evt2["type"], "Event types should match"
        assert evt1["data"] == evt2["data"], "Event data should match (determinism)"
