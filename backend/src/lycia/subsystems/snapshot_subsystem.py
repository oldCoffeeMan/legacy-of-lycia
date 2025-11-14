"""
Snapshot Creation Subsystem - CLEANUP Phase.

This subsystem creates periodic snapshots of aggregate state to enable
fast state reconstruction (S2-04).
"""

from datetime import datetime, timezone
from lycia.models import WorldState, City, WorldSnapshot, CitySnapshot
from lycia.settings import settings
from .phase import SubsystemPhase
from .protocol import TickContext


class SnapshotSubsystem:
    """
    Creates periodic snapshots of game state.

    Snapshots enable fast state reconstruction by loading the latest
    snapshot and replaying only events since that snapshot.

    Frequency: Configurable via settings.snapshot_frequency
    Default: Every 60 ticks
    """

    @property
    def name(self) -> str:
        """Subsystem identifier."""
        return "snapshot_creation"

    @property
    def phase(self) -> SubsystemPhase:
        """Execute in CLEANUP phase (after all game logic)."""
        return SubsystemPhase.CLEANUP

    @property
    def dependencies(self) -> list[str]:
        """Depends on event persistence to ensure events are saved first."""
        return ["event_persistence"]

    def apply(self, ctx: TickContext) -> None:
        """
        Create snapshots if current tick is a snapshot tick.

        Snapshots are created every K ticks (configurable).
        Both world state and all city states are snapshotted.

        Args:
            ctx: Tick context with DB access
        """
        current_tick = ctx.tick

        # Check if this is a snapshot tick
        if current_tick % settings.snapshot_frequency != 0:
            return

        # Create world snapshot
        self._create_world_snapshot(ctx)

        # Create city snapshots
        self._create_city_snapshots(ctx)

        # Commit all snapshots
        ctx.db.commit()

        # Emit event
        ctx.emit("snapshots.created", {
            "tick": current_tick,
            "frequency": settings.snapshot_frequency
        })

    def _create_world_snapshot(self, ctx: TickContext) -> None:
        """
        Create snapshot of world state.

        Args:
            ctx: Tick context
        """
        # Get current world state
        world_state = ctx.db.query(WorldState).filter_by(id=1).first()
        if not world_state:
            return

        # Check if snapshot already exists for this tick
        existing = ctx.db.query(WorldSnapshot).filter_by(tick=ctx.tick).first()
        if existing:
            return  # Already snapshotted

        # Create snapshot
        snapshot = WorldSnapshot(
            tick=ctx.tick,
            current_tick=world_state.tick,
            snapshot_version=1,
            created_at=datetime.now(timezone.utc)
        )
        ctx.db.add(snapshot)

    def _create_city_snapshots(self, ctx: TickContext) -> None:
        """
        Create snapshots of all cities.

        Args:
            ctx: Tick context
        """
        # Get all cities
        cities = ctx.db.query(City).all()

        for city in cities:
            # Check if snapshot already exists
            existing = ctx.db.query(CitySnapshot).filter_by(
                tick=ctx.tick,
                city_id=city.id
            ).first()

            if existing:
                continue  # Already snapshotted

            # Create snapshot
            snapshot = CitySnapshot(
                tick=ctx.tick,
                city_id=city.id,
                name=city.name,
                region=city.region,
                prosperity=city.prosperity,
                unrest=city.unrest,
                latitude=city.latitude,
                longitude=city.longitude,
                snapshot_version=1,
                created_at=datetime.now(timezone.utc)
            )
            ctx.db.add(snapshot)
