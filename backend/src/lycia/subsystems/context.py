"""
Tick Context Implementation

Concrete implementation of TickContext provided to subsystems.
"""
import hashlib
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

        # Create subsystem-specific RNG using deterministic seeding
        # Combine tick number and subsystem name for isolation
        self._rng = self._create_subsystem_rng(tick, subsystem_name, rng)

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

    @staticmethod
    def _create_subsystem_rng(tick: int, subsystem_name: str, base_rng: Random) -> Random:
        """
        Create a deterministic RNG for a specific subsystem.

        The RNG is seeded using a combination of:
        - Current tick number
        - Subsystem name
        - Base RNG state (to ensure global tick seed influences all subsystems)

        This ensures:
        1. Same tick + same subsystem + same global seed → same RNG sequence
        2. Different subsystems get different RNG sequences (even in same tick)
        3. Different ticks get different RNG sequences (even in same subsystem)

        Args:
            tick: Current tick number
            subsystem_name: Name of the subsystem
            base_rng: Base RNG seeded with tick seed

        Returns:
            Random instance with subsystem-specific seed
        """
        # Create deterministic seed from tick, subsystem name, and base RNG state
        # Use first element of base_rng state tuple (the main seed value)
        base_state = base_rng.getstate()
        base_seed_value = base_state[1][0] if len(base_state) > 1 else 0

        # Combine tick, subsystem name, and base seed
        seed_string = f"tick_{tick}:subsystem_{subsystem_name}:base_{base_seed_value}"

        # Generate numeric seed from string using SHA256
        seed_hash = hashlib.sha256(seed_string.encode()).hexdigest()
        numeric_seed = int(seed_hash, 16) % (2**32)

        # Create and return new Random instance
        subsystem_rng = Random()
        subsystem_rng.seed(numeric_seed)
        return subsystem_rng

    # Helper methods for common RNG operations
    def random_int(self, min_val: int, max_val: int) -> int:
        """
        Generate a random integer in the range [min_val, max_val] (inclusive).

        This is a convenience wrapper around ctx.rng.randint().

        Args:
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive)

        Returns:
            Random integer between min_val and max_val
        """
        return self._rng.randint(min_val, max_val)

    def random_float(self, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """
        Generate a random float in the range [min_val, max_val).

        This is a convenience wrapper around ctx.rng.uniform().

        Args:
            min_val: Minimum value (inclusive)
            max_val: Maximum value (exclusive)

        Returns:
            Random float between min_val and max_val
        """
        return self._rng.uniform(min_val, max_val)

    def random_choice(self, choices: list[Any]) -> Any:
        """
        Choose a random element from a non-empty sequence.

        This is a convenience wrapper around ctx.rng.choice().

        Args:
            choices: Non-empty list of choices

        Returns:
            Random element from choices

        Raises:
            IndexError: If choices is empty
        """
        return self._rng.choice(choices)

    def random_bool(self, probability: float = 0.5) -> bool:
        """
        Generate a random boolean with specified probability of True.

        Args:
            probability: Probability of returning True (0.0 to 1.0)

        Returns:
            True with given probability, False otherwise
        """
        return self._rng.random() < probability
