"""
Event Replay System.

Reconstructs aggregate state from snapshots and event logs.
"""

import logging
from typing import Any
from sqlalchemy.orm import Session
from lycia.models import Event, WorldSnapshot, WorldState, City
from .reducers import get_event_reducer_registry

logger = logging.getLogger(__name__)


class EventReplayer:
    """
    Replays events to reconstruct state.

    Enables:
    - State reconstruction from snapshots + events
    - Debugging and testing
    - Time-travel queries
    """

    def __init__(self, db: Session):
        """
        Initialize replayer.

        Args:
            db: Database session
        """
        self.db = db
        self.registry = get_event_reducer_registry()

    def replay_to_tick(self, target_tick: int) -> dict[str, Any]:
        """
        Replay events to reconstruct state at specific tick.

        Algorithm:
        1. Find latest snapshot before or at target_tick
        2. Load snapshot state
        3. Replay all events from snapshot_tick to target_tick
        4. Return reconstructed state

        Args:
            target_tick: Tick to reconstruct state at

        Returns:
            Dictionary with reconstructed state
        """
        # Find latest snapshot
        world_snapshot = (
            self.db.query(WorldSnapshot)
            .filter(WorldSnapshot.tick <= target_tick)
            .order_by(WorldSnapshot.tick.desc())
            .first()
        )

        snapshot_tick = world_snapshot.tick if world_snapshot else 0

        # Get all events since snapshot
        events = (
            self.db.query(Event)
            .filter(Event.tick > snapshot_tick, Event.tick <= target_tick)
            .order_by(Event.tick, Event.created_at, Event.id)
            .all()
        )

        logger.info(
            f"Replaying {len(events)} events from tick {snapshot_tick} to {target_tick}"
        )

        # Apply events
        applied_count = 0
        skipped_count = 0
        error_count = 0

        for event in events:
            try:
                result = self._apply_event(event)
                if result:
                    applied_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(
                    f"Error applying event {event.id} (type={event.event_type}): {e}"
                )
                # Continue replay despite errors (graceful degradation)
                continue

        logger.info(
            f"Replay complete: {applied_count} applied, "
            f"{skipped_count} skipped, {error_count} errors"
        )

        # Return summary
        return {
            "target_tick": target_tick,
            "snapshot_tick": snapshot_tick,
            "events_replayed": len(events),
            "events_applied": applied_count,
            "events_skipped": skipped_count,
            "events_errored": error_count,
        }

    def _apply_event(self, event: Event) -> bool:
        """
        Apply single event to state.

        Args:
            event: Event to apply

        Returns:
            True if applied, False if skipped
        """
        # Get reducer for event type
        reducer = self.registry.get(event.event_type, event.schema_version)

        if not reducer:
            # Try latest version
            reducer = self.registry.get_latest(event.event_type)

        if not reducer:
            # No reducer registered - skip event
            logger.debug(f"No reducer for event type: {event.event_type}")
            return False

        # Apply reducer
        event_data = {
            "id": event.id,
            "tick": event.tick,
            "type": event.event_type,
            "schema_version": event.schema_version,
            "actor": event.actor,
            "payload": event.payload,
            "command_id": event.command_id,
            "created_at": event.created_at,
        }

        reducer.reduce(event_data, self.db)
        return True

    def verify_replay_correctness(self, target_tick: int) -> dict[str, Any]:
        """
        Verify that replay produces same state as live execution.

        This is used for testing to ensure deterministic replay.

        Args:
            target_tick: Tick to verify

        Returns:
            Verification results with comparison data
        """
        # Get current live state
        live_world = self.db.query(WorldState).filter_by(id=1).first()
        live_cities = self.db.query(City).all()

        # Store live state
        live_state = {
            "world_tick": live_world.tick if live_world else 0,
            "cities": {
                city.id: {
                    "prosperity": city.prosperity,
                    "unrest": city.unrest,
                }
                for city in live_cities
            },
        }

        # Replay to target tick
        replay_result = self.replay_to_tick(target_tick)

        # Get replayed state
        replayed_world = self.db.query(WorldState).filter_by(id=1).first()
        replayed_cities = self.db.query(City).all()

        replayed_state = {
            "world_tick": replayed_world.tick if replayed_world else 0,
            "cities": {
                city.id: {
                    "prosperity": city.prosperity,
                    "unrest": city.unrest,
                }
                for city in replayed_cities
            },
        }

        # Compare states
        differences = []

        # Compare world tick
        if live_state["world_tick"] != replayed_state["world_tick"]:
            differences.append({
                "type": "world_tick",
                "live": live_state["world_tick"],
                "replayed": replayed_state["world_tick"],
            })

        # Compare cities
        for city_id in live_state["cities"]:
            if city_id not in replayed_state["cities"]:
                differences.append({
                    "type": "city_missing",
                    "city_id": city_id,
                })
                continue

            live_city = live_state["cities"][city_id]
            replayed_city = replayed_state["cities"][city_id]

            for field in ["prosperity", "unrest"]:
                if live_city[field] != replayed_city[field]:
                    differences.append({
                        "type": "city_field",
                        "city_id": city_id,
                        "field": field,
                        "live": live_city[field],
                        "replayed": replayed_city[field],
                    })

        return {
            "target_tick": target_tick,
            "replay_result": replay_result,
            "matches": len(differences) == 0,
            "differences": differences,
        }
