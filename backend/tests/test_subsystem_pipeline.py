"""
Tests for the Subsystem Pipeline & Registry (S2-02)

Test scenarios:
1. Subsystem registration and execution order
2. Dependency cycle detection
3. Dynamic subsystem add/remove
"""
import pytest
from random import Random
from sqlalchemy.orm import Session
from src.lycia.subsystems import (
    Subsystem,
    SubsystemPhase,
    SubsystemRegistry,
    TickContext,
    TickContextImpl,
)
from src.lycia.subsystems.registry import (
    DependencyCycleError,
    SubsystemNotFoundError,
    InvalidDependencyError,
)
from src.lycia.subsystems.examples import (
    EconomyProductionSubsystem,
    TradeRoutesSubsystem,
    DiplomacySubsystem,
    WeatherSystemSubsystem,
    NotificationCleanupSubsystem,
)


class TestSubsystemRegistration:
    """Test subsystem registration and basic operations."""

    def test_register_single_subsystem(self):
        """Test registering a single subsystem."""
        registry = SubsystemRegistry()
        subsystem = EconomyProductionSubsystem()

        registry.register(subsystem)

        assert registry.count() == 1
        assert subsystem.name in registry.list_subsystems()
        assert registry.get(subsystem.name) == subsystem

    def test_register_duplicate_fails(self):
        """Test that registering a duplicate subsystem fails."""
        registry = SubsystemRegistry()
        subsystem = EconomyProductionSubsystem()

        registry.register(subsystem)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(subsystem)

    def test_unregister_subsystem(self):
        """Test unregistering a subsystem."""
        registry = SubsystemRegistry()
        subsystem = EconomyProductionSubsystem()

        registry.register(subsystem)
        assert registry.count() == 1

        registry.unregister(subsystem.name)
        assert registry.count() == 0
        assert subsystem.name not in registry.list_subsystems()

    def test_unregister_nonexistent_fails(self):
        """Test that unregistering a nonexistent subsystem fails."""
        registry = SubsystemRegistry()

        with pytest.raises(SubsystemNotFoundError):
            registry.unregister("nonexistent")

    def test_clear_registry(self):
        """Test clearing all subsystems."""
        registry = SubsystemRegistry()
        registry.register(EconomyProductionSubsystem())
        registry.register(TradeRoutesSubsystem())

        assert registry.count() == 2

        registry.clear()
        assert registry.count() == 0
        assert len(registry.list_subsystems()) == 0


class TestExecutionOrder:
    """Test subsystem execution order based on phases and dependencies."""

    def test_phase_ordering(self):
        """Test that subsystems execute in phase order."""
        registry = SubsystemRegistry()

        # Register subsystems in reverse phase order
        registry.register(NotificationCleanupSubsystem())  # CLEANUP
        registry.register(WeatherSystemSubsystem())        # WEATHER
        registry.register(DiplomacySubsystem())            # POLITICS
        registry.register(EconomyProductionSubsystem())    # ECONOMY

        order = registry.get_execution_order()

        # Should be ordered by phase
        assert len(order) == 4
        assert order[0].phase == SubsystemPhase.ECONOMY
        assert order[1].phase == SubsystemPhase.POLITICS
        assert order[2].phase == SubsystemPhase.WEATHER
        assert order[3].phase == SubsystemPhase.CLEANUP

    def test_dependency_ordering_within_phase(self):
        """Test that dependencies are respected within a phase."""
        registry = SubsystemRegistry()

        # TradeRoutes depends on EconomyProduction (both ECONOMY phase)
        registry.register(TradeRoutesSubsystem())      # Depends on economy_production
        registry.register(EconomyProductionSubsystem())  # No dependencies

        order = registry.get_execution_order()

        # Economy production should run before trade routes
        assert len(order) == 2
        assert order[0].name == "economy_production"
        assert order[1].name == "trade_routes"

    def test_mixed_phase_and_dependency_ordering(self):
        """Test complex ordering with multiple phases and dependencies."""
        registry = SubsystemRegistry()

        # Register in random order
        registry.register(NotificationCleanupSubsystem())
        registry.register(TradeRoutesSubsystem())
        registry.register(DiplomacySubsystem())
        registry.register(EconomyProductionSubsystem())
        registry.register(WeatherSystemSubsystem())

        order = registry.get_execution_order()

        assert len(order) == 5

        # Verify phase ordering
        phases = [s.phase for s in order]
        assert phases == sorted(phases)

        # Verify dependency within ECONOMY phase
        economy_subsystems = [s for s in order if s.phase == SubsystemPhase.ECONOMY]
        assert economy_subsystems[0].name == "economy_production"
        assert economy_subsystems[1].name == "trade_routes"

    def test_execution_order_is_stable(self):
        """Test that execution order is stable across multiple calls."""
        registry = SubsystemRegistry()

        registry.register(TradeRoutesSubsystem())
        registry.register(EconomyProductionSubsystem())
        registry.register(DiplomacySubsystem())

        # Get order multiple times
        order1 = [s.name for s in registry.get_execution_order()]
        order2 = [s.name for s in registry.get_execution_order()]
        order3 = [s.name for s in registry.get_execution_order()]

        # Should be identical
        assert order1 == order2 == order3


class TestDependencyValidation:
    """Test dependency cycle detection and validation."""

    def test_missing_dependency_detected(self):
        """Test that missing dependencies are detected."""
        registry = SubsystemRegistry()

        # Register TradeRoutes without its dependency
        registry.register(TradeRoutesSubsystem())  # Depends on economy_production

        with pytest.raises(SubsystemNotFoundError, match="economy_production"):
            registry.get_execution_order()

    def test_dependency_cycle_detected(self):
        """Test that dependency cycles are detected."""
        # Create subsystems with circular dependencies
        class SubsystemA:
            @property
            def name(self) -> str:
                return "subsystem_a"

            @property
            def phase(self) -> SubsystemPhase:
                return SubsystemPhase.ECONOMY

            @property
            def dependencies(self) -> list[str]:
                return ["subsystem_b"]

            def apply(self, ctx: TickContext) -> None:
                pass

        class SubsystemB:
            @property
            def name(self) -> str:
                return "subsystem_b"

            @property
            def phase(self) -> SubsystemPhase:
                return SubsystemPhase.ECONOMY

            @property
            def dependencies(self) -> list[str]:
                return ["subsystem_a"]  # Circular!

            def apply(self, ctx: TickContext) -> None:
                pass

        registry = SubsystemRegistry()
        registry.register(SubsystemA())
        registry.register(SubsystemB())

        with pytest.raises(DependencyCycleError, match="cycle"):
            registry.get_execution_order()

    def test_invalid_phase_dependency_detected(self):
        """Test that cross-phase dependencies are validated."""
        # Create subsystem that depends on a later phase
        class InvalidSubsystem:
            @property
            def name(self) -> str:
                return "invalid_subsystem"

            @property
            def phase(self) -> SubsystemPhase:
                return SubsystemPhase.ECONOMY

            @property
            def dependencies(self) -> list[str]:
                return ["weather_system"]  # Weather is AFTER economy!

            def apply(self, ctx: TickContext) -> None:
                pass

        registry = SubsystemRegistry()
        registry.register(InvalidSubsystem())
        registry.register(WeatherSystemSubsystem())

        with pytest.raises(InvalidDependencyError, match="cannot depend on"):
            registry.get_execution_order()


class TestDynamicSubsystemManagement:
    """Test adding and removing subsystems dynamically."""

    def test_add_subsystem_invalidates_cache(self):
        """Test that adding a subsystem invalidates execution order cache."""
        registry = SubsystemRegistry()
        registry.register(EconomyProductionSubsystem())

        order1 = registry.get_execution_order()
        assert len(order1) == 1

        # Add another subsystem
        registry.register(DiplomacySubsystem())

        order2 = registry.get_execution_order()
        assert len(order2) == 2

    def test_remove_subsystem_doesnt_break_tick(self):
        """Test that removing a subsystem doesn't break the tick loop."""
        registry = SubsystemRegistry()

        # Set up subsystems
        registry.register(EconomyProductionSubsystem())
        registry.register(TradeRoutesSubsystem())
        registry.register(DiplomacySubsystem())

        order1 = registry.get_execution_order()
        assert len(order1) == 3

        # Remove one subsystem
        registry.unregister("diplomacy")

        order2 = registry.get_execution_order()
        assert len(order2) == 2
        assert "diplomacy" not in [s.name for s in order2]

    def test_removing_dependency_breaks_dependent(self):
        """Test that removing a dependency causes validation error."""
        registry = SubsystemRegistry()

        registry.register(EconomyProductionSubsystem())
        registry.register(TradeRoutesSubsystem())

        # Should work fine
        order = registry.get_execution_order()
        assert len(order) == 2

        # Remove the dependency
        registry.unregister("economy_production")

        # Now should fail
        with pytest.raises(SubsystemNotFoundError):
            registry.get_execution_order()


class TestTickContext:
    """Test the TickContext implementation."""

    def test_context_provides_tick_number(self, db_session: Session):
        """Test that context provides current tick number."""
        ctx = TickContextImpl(
            tick=42,
            db=db_session,
            rng=Random(42),
            subsystem_name="test_subsystem"
        )

        assert ctx.tick == 42

    def test_context_provides_deterministic_rng(self, db_session: Session):
        """Test that context provides deterministic RNG per subsystem."""
        base_rng = Random(42)

        ctx1 = TickContextImpl(
            tick=1,
            db=db_session,
            rng=base_rng,
            subsystem_name="subsystem_a"
        )

        ctx2 = TickContextImpl(
            tick=1,
            db=db_session,
            rng=base_rng,
            subsystem_name="subsystem_b"
        )

        # Different subsystems should get different random sequences
        rand1 = [ctx1.rng.random() for _ in range(5)]
        rand2 = [ctx2.rng.random() for _ in range(5)]

        assert rand1 != rand2  # Different subsystems, different sequences

    def test_context_emit_event(self, db_session: Session):
        """Test that context can emit events."""
        ctx = TickContextImpl(
            tick=1,
            db=db_session,
            rng=Random(1),
            subsystem_name="test_subsystem"
        )

        ctx.emit("test.event", {"data": "value"})

        assert len(ctx.events) == 1
        assert ctx.events[0]["type"] == "test.event"
        assert ctx.events[0]["data"] == {"data": "value"}
        assert ctx.events[0]["tick"] == 1
        assert ctx.events[0]["subsystem"] == "test_subsystem"

    def test_context_config_access(self, db_session: Session):
        """Test that context provides config access."""
        config = {
            "economy": {
                "tax_rate": 0.2,
                "production_multiplier": 1.5
            }
        }

        ctx = TickContextImpl(
            tick=1,
            db=db_session,
            rng=Random(1),
            subsystem_name="test_subsystem",
            config=config
        )

        assert ctx.get_config("economy.tax_rate") == 0.2
        assert ctx.get_config("economy.production_multiplier") == 1.5
        assert ctx.get_config("nonexistent", "default") == "default"


class TestSubsystemExecution:
    """Test actual subsystem execution."""

    def test_subsystem_can_execute(self, db_session: Session):
        """Test that a subsystem can execute successfully."""
        subsystem = EconomyProductionSubsystem()

        ctx = TickContextImpl(
            tick=1,
            db=db_session,
            rng=Random(1),
            subsystem_name=subsystem.name
        )

        # Should not raise
        subsystem.apply(ctx)

        # Should have emitted events
        assert len(ctx.events) > 0

    def test_subsystems_execute_in_order(self, db_session: Session):
        """Test that multiple subsystems execute in correct order."""
        registry = SubsystemRegistry()
        registry.register(EconomyProductionSubsystem())
        registry.register(TradeRoutesSubsystem())

        execution_log = []

        # Mock the apply method to track execution
        original_economy_apply = EconomyProductionSubsystem.apply
        original_trade_apply = TradeRoutesSubsystem.apply

        def logged_economy_apply(self, ctx):
            execution_log.append("economy_production")
            original_economy_apply(self, ctx)

        def logged_trade_apply(self, ctx):
            execution_log.append("trade_routes")
            original_trade_apply(self, ctx)

        EconomyProductionSubsystem.apply = logged_economy_apply
        TradeRoutesSubsystem.apply = logged_trade_apply

        try:
            # Execute subsystems
            for subsystem in registry.get_execution_order():
                ctx = TickContextImpl(
                    tick=1,
                    db=db_session,
                    rng=Random(1),
                    subsystem_name=subsystem.name
                )
                subsystem.apply(ctx)

            # Verify execution order
            assert execution_log == ["economy_production", "trade_routes"]

        finally:
            # Restore original methods
            EconomyProductionSubsystem.apply = original_economy_apply
            TradeRoutesSubsystem.apply = original_trade_apply
