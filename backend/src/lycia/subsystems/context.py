"""
Tick Context Implementation

Concrete implementation of TickContext provided to subsystems.
"""
from typing import Any
from random import Random
from sqlalchemy.orm import Session


class TickContextImpl:
    """
    Concrete implementation of TickContext.

    Provides subsystems with access to game state and utilities.
    """

    def __init__(
        self,
        tick: int,
        db: Session,
        rng: Random,
        subsystem_name: str,
        config: dict[str, Any] | None = None,
        events: list[dict[str, Any]] | None = None
    ):
        """
        Initialize tick context.

        Args:
            tick: Current tick number
            db: Database session
            rng: Base RNG (will be re-seeded per subsystem)
            subsystem_name: Name of the subsystem using this context
            config: Configuration dictionary
            events: Shared event buffer for the tick (if None, creates new list)
        """
        self._tick = tick
        self._db = db
        self._base_rng = rng
        self._subsystem_name = subsystem_name
        self._config = config or {}
        # Use shared event buffer if provided, otherwise create new list
        self._events: list[dict[str, Any]] = events if events is not None else []

        # Create subsystem-specific RNG
        self._rng = Random(f"{rng.getstate()}_{subsystem_name}")

    @property
    def tick(self) -> int:
        """Current tick number."""
        return self._tick

    @property
    def db(self) -> Session:
        """Database session for queries."""
        return self._db

    @property
    def rng(self) -> Random:
        """Subsystem-specific seeded RNG."""
        return self._rng

    def query(self, model_class: type, **filters: Any) -> list[Any]:
        """
        Query the database for entities.

        Args:
            model_class: SQLAlchemy model class to query
            **filters: Filter conditions

        Returns:
            List of matching entities
        """
        query = self._db.query(model_class)

        # Apply simple equality filters
        for key, value in filters.items():
            if hasattr(model_class, key):
                query = query.filter(getattr(model_class, key) == value)

        return query.all()

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Emit an event to be processed later.

        Args:
            event_type: Type of event
            data: Event payload
        """
        event = {
            "type": event_type,
            "data": data,
            "tick": self._tick,
            "subsystem": self._subsystem_name,
        }
        self._events.append(event)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        # Support dot notation for nested config
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def events(self) -> list[dict[str, Any]]:
        """Get all events emitted by this subsystem."""
        return self._events

    def clear_events(self) -> None:
        """Clear all emitted events."""
        self._events.clear()
