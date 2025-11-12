"""
Example subsystems for testing and demonstration.

These are simple placeholder subsystems that demonstrate the subsystem API
without implementing complex game logic.
"""
from .protocol import Subsystem, TickContext
from .phase import SubsystemPhase


class EconomyProductionSubsystem:
    """Example economy subsystem that runs in ECONOMY phase."""

    @property
    def name(self) -> str:
        return "economy_production"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.ECONOMY

    @property
    def dependencies(self) -> list[str]:
        return []  # No dependencies

    def apply(self, ctx: TickContext) -> None:
        """Simulate basic production."""
        # Example: Query cities and update prosperity
        print(f"  [{self.name}] Running at tick {ctx.tick}")

        # Emit an event
        ctx.emit("economy.production_complete", {
            "tick": ctx.tick,
            "message": "Production cycle complete"
        })


class TradeRoutesSubsystem:
    """Example trade subsystem that depends on production."""

    @property
    def name(self) -> str:
        return "trade_routes"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.ECONOMY

    @property
    def dependencies(self) -> list[str]:
        return ["economy_production"]  # Runs after production

    def apply(self, ctx: TickContext) -> None:
        """Simulate trade between cities."""
        print(f"  [{self.name}] Running at tick {ctx.tick}")

        # Use deterministic RNG
        trade_value = ctx.rng.randint(100, 1000)

        ctx.emit("economy.trade_executed", {
            "tick": ctx.tick,
            "value": trade_value
        })


class DiplomacySubsystem:
    """Example politics subsystem."""

    @property
    def name(self) -> str:
        return "diplomacy"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.POLITICS

    @property
    def dependencies(self) -> list[str]:
        return []  # No dependencies

    def apply(self, ctx: TickContext) -> None:
        """Simulate diplomatic events."""
        print(f"  [{self.name}] Running at tick {ctx.tick}")

        ctx.emit("politics.diplomacy_update", {
            "tick": ctx.tick,
            "message": "Diplomatic relations updated"
        })


class WeatherSystemSubsystem:
    """Example weather subsystem."""

    @property
    def name(self) -> str:
        return "weather_system"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.WEATHER

    @property
    def dependencies(self) -> list[str]:
        return []  # No dependencies

    def apply(self, ctx: TickContext) -> None:
        """Simulate weather effects."""
        print(f"  [{self.name}] Running at tick {ctx.tick}")

        # Use RNG for weather
        weather_type = ctx.rng.choice(["sunny", "rainy", "stormy"])

        ctx.emit("weather.update", {
            "tick": ctx.tick,
            "weather": weather_type
        })


class NotificationCleanupSubsystem:
    """Example cleanup subsystem that runs last."""

    @property
    def name(self) -> str:
        return "notification_cleanup"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.CLEANUP

    @property
    def dependencies(self) -> list[str]:
        return []  # Runs in cleanup phase, after all other phases

    def apply(self, ctx: TickContext) -> None:
        """Clean up notifications and temporary data."""
        print(f"  [{self.name}] Running at tick {ctx.tick}")

        ctx.emit("cleanup.complete", {
            "tick": ctx.tick,
            "message": "Cleanup complete"
        })
