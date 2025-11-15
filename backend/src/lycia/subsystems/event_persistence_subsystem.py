"""
Event Persistence Subsystem - CLEANUP Phase.

This subsystem runs at the end of each tick to persist all emitted events
to the database. This is part of the event sourcing implementation (S2-04).
"""

from datetime import datetime, timezone
from lycia.models import Event
from .phase import SubsystemPhase
from .protocol import TickContext


class EventPersistenceSubsystem:
    """
    Persists emitted events to the database.

    This subsystem runs in the CLEANUP phase (last phase) to ensure all
    events from the current tick are persisted atomically.

    Events are the only source of truth for state changes, enabling:
    - State reconstruction via replay
    - Audit trails and debugging
    - Time-travel queries
    """

    @property
    def name(self) -> str:
        """Subsystem identifier."""
        return "event_persistence"

    @property
    def phase(self) -> SubsystemPhase:
        """Execute in CLEANUP phase (last phase)."""
        return SubsystemPhase.CLEANUP

    @property
    def dependencies(self) -> list[str]:
        """No dependencies - runs in CLEANUP phase."""
        return []

    def apply(self, ctx: TickContext) -> None:
        """
        Persist all events collected during this tick.

        Events are collected from the context and persisted to the
        events table with proper metadata (tick, actor, schema version).

        Args:
            ctx: Tick context (events already collected)
        """
        # Check if event sourcing is enabled (S2-07)
        enable_persistence = ctx.get_config("events.enable_persistence", default=True)
        if not enable_persistence:
            return

        # Get all events collected during this tick
        # Note: In the full implementation, we'd collect events from all subsystems
        # For now, we work with events from this context
        events_to_persist = ctx.events

        if not events_to_persist:
            return

        # Persist each event
        for event_data in events_to_persist:
            event = Event(
                tick=ctx.tick,
                type=event_data.get("type", "unknown"),
                schema_version=event_data.get("schema_version", 1),
                actor=event_data.get("subsystem", event_data.get("actor", "system")),
                payload=event_data.get("data", {}),
                command_id=event_data.get("command_id"),
                created_at=datetime.now(timezone.utc)
            )
            ctx.db.add(event)

        # Commit all events atomically
        ctx.db.commit()

        # Emit summary event
        ctx.emit("events.persisted", {
            "count": len(events_to_persist),
            "tick": ctx.tick
        })
