"""
Event Reducers.

Reducers apply events to aggregate state, enabling state reconstruction
from event logs.
"""

from typing import Protocol, Any
from sqlalchemy.orm import Session


class EventReducer(Protocol):
    """
    Protocol for event reducers.

    Reducers apply events to aggregate state. They must be:
    - Deterministic: Same events always produce same state
    - Pure: No side effects beyond state updates
    - Versioned: Support schema evolution
    """

    @property
    def event_type(self) -> str:
        """
        Event type this reducer handles.

        Returns:
            Event type string (e.g., "city.prosperity_changed")
        """
        ...

    @property
    def version(self) -> int:
        """
        Reducer version for schema evolution.

        Returns:
            Version number
        """
        ...

    def reduce(self, event: dict[str, Any], db: Session) -> None:
        """
        Apply event to aggregate state.

        This method should update the database to reflect the event.
        It must be deterministic and idempotent.

        Args:
            event: Event data with payload
            db: Database session
        """
        ...


class EventReducerRegistry:
    """
    Registry for event reducers.

    Maps event types to reducer functions for state reconstruction.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._reducers: dict[str, EventReducer] = {}

    def _make_key(self, event_type: str, version: int) -> str:
        """Create registry key from event type and version."""
        return f"{event_type}@{version}"

    def register(self, reducer: EventReducer) -> None:
        """
        Register an event reducer.

        Args:
            reducer: The reducer to register

        Raises:
            ValueError: If reducer for this event_type@version already registered
        """
        key = self._make_key(reducer.event_type, reducer.version)
        if key in self._reducers:
            raise ValueError(
                f"Reducer for {key} already registered"
            )
        self._reducers[key] = reducer

    def get(self, event_type: str, version: int = 1) -> EventReducer | None:
        """
        Get reducer for event type and version.

        Args:
            event_type: Event type
            version: Reducer version (default: 1)

        Returns:
            Reducer if found, None otherwise
        """
        key = self._make_key(event_type, version)
        return self._reducers.get(key)

    def get_latest(self, event_type: str) -> EventReducer | None:
        """
        Get latest version of reducer for event type.

        Args:
            event_type: Event type

        Returns:
            Reducer with highest version, or None if not found
        """
        matching = [
            (r.version, r)
            for key, r in self._reducers.items()
            if r.event_type == event_type
        ]

        if not matching:
            return None

        matching.sort(key=lambda x: x[0], reverse=True)
        return matching[0][1]

    def clear(self) -> None:
        """Clear all registered reducers."""
        self._reducers.clear()


# Global singleton
_global_registry: EventReducerRegistry | None = None


def get_event_reducer_registry() -> EventReducerRegistry:
    """
    Get global event reducer registry.

    Returns:
        Global EventReducerRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = EventReducerRegistry()
    return _global_registry
