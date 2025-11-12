"""
Subsystem Protocol and Context Definitions

Defines the interfaces that subsystems must implement and the context
they receive during execution.
"""
from typing import Protocol, Any, runtime_checkable
from random import Random
from sqlalchemy.orm import Session


class TickContext(Protocol):
    """
    Context provided to subsystems during tick execution.

    Provides read-only access to game state, RNG, configuration,
    and methods to emit events/side-effects.
    """

    @property
    def tick(self) -> int:
        """Current tick number."""
        ...

    @property
    def db(self) -> Session:
        """Database session for queries (read-only recommended)."""
        ...

    @property
    def rng(self) -> Random:
        """Subsystem-specific seeded RNG for deterministic randomness."""
        ...

    def query(self, model_class: type, **filters: Any) -> list[Any]:
        """
        Query the database for entities.

        Args:
            model_class: SQLAlchemy model class to query
            **filters: Filter conditions (e.g., city_id=1, prosperity__gt=50)

        Returns:
            List of matching entities
        """
        ...

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Emit an event/side-effect to be processed later.

        Events are collected during tick execution and can be used for:
        - Notifications
        - Logging
        - AI narrator triggers
        - Deferred state updates

        Args:
            event_type: Type of event (e.g., "city.prosperity_changed")
            data: Event payload data
        """
        ...

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (e.g., "economy.tax_rate")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        ...


@runtime_checkable
class Subsystem(Protocol):
    """
    Protocol that all subsystems must implement.

    Subsystems are pure functions that receive context and apply game logic.
    They should not directly modify state outside of the database session.
    """

    @property
    def name(self) -> str:
        """
        Unique identifier for this subsystem.

        Should be lowercase with underscores (e.g., "economy_production").
        """
        ...

    @property
    def phase(self) -> "SubsystemPhase":  # type: ignore
        """
        Execution phase for this subsystem.

        Determines when this subsystem runs relative to others.
        """
        ...

    @property
    def dependencies(self) -> list[str]:
        """
        List of subsystem names this depends on.

        This subsystem will execute after all its dependencies.
        Dependencies must be in the same phase or earlier phases.

        Returns:
            List of subsystem names (e.g., ["economy_production", "trade_routes"])
        """
        ...

    def apply(self, ctx: TickContext) -> None:
        """
        Apply this subsystem's logic for the current tick.

        This is the main entry point called by the tick executor.

        Args:
            ctx: Context providing access to state, RNG, and utilities

        Raises:
            Exception: If subsystem execution fails
        """
        ...
