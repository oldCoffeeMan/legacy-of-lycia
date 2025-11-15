"""
Tick Executor - Authoritative Tick Loop Implementation

This module implements the core tick loop that advances the game world.
Key design principles:
- Single-owner guarantee via PostgreSQL advisory locks
- Deterministic execution with seeded RNG
- Durable audit trail via TickLog
- Idempotent tick processing for crash recovery
- Extensible subsystem pipeline
"""
import asyncio
import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import text, select
from sqlalchemy.orm import Session

from .db import get_db_session
from .models import WorldState, TickLog, TickStatus
from .settings import settings
from .subsystems import SubsystemRegistry, TickContextImpl
from .config_loader import get_gameplay_config


# PostgreSQL advisory lock key for tick execution
# Using a hash of "lycia_tick_lock" to get a unique int64
TICK_LOCK_KEY = int(hashlib.md5(b"lycia_tick_lock").hexdigest()[:16], 16) % (2**63)


class TickExecutor:
    """
    Manages the authoritative tick loop for the game world.

    Ensures:
    - Only one worker can execute a tick at a time
    - Each tick is logged for audit and monitoring
    - Deterministic RNG seeding per tick
    - Idempotent tick processing
    - Extensible subsystem execution
    """

    def __init__(self, worker_id: Optional[str] = None, registry: Optional[SubsystemRegistry] = None):
        """
        Initialize the tick executor with a unique worker ID.

        Args:
            worker_id: Unique identifier for this worker (auto-generated if None)
            registry: Subsystem registry (creates empty one if None)
        """
        self.worker_id = worker_id or str(uuid.uuid4())
        self.running = False
        self.registry = registry or SubsystemRegistry()

    def _acquire_tick_lock(self, db: Session) -> bool:
        """
        Acquire a distributed lock for tick execution.

        Uses PostgreSQL advisory locks in production.
        Uses a simpler table-based lock for SQLite (testing).

        Returns:
            True if lock acquired, False otherwise
        """
        # Check database dialect
        dialect = db.bind.dialect.name

        if dialect == "postgresql":
            # Use PostgreSQL advisory locks
            result = db.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": TICK_LOCK_KEY}
            )
            return result.scalar()
        else:
            # For SQLite/other databases, use a simple table-based lock
            # Try to insert a lock row (will fail if already exists)
            try:
                db.execute(
                    text("INSERT INTO tick_lock (lock_id, acquired_at) VALUES (1, datetime('now'))")
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                return False

    def _release_tick_lock(self, db: Session) -> None:
        """Release the distributed lock."""
        dialect = db.bind.dialect.name

        if dialect == "postgresql":
            # Use PostgreSQL advisory locks
            db.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": TICK_LOCK_KEY}
            )
        else:
            # For SQLite/other databases, delete the lock row
            db.execute(text("DELETE FROM tick_lock WHERE lock_id = 1"))
            db.commit()

    def _generate_tick_seed(self, tick: int) -> str:
        """
        Generate a deterministic seed for this tick's RNG.

        Uses the tick number to ensure reproducibility.
        Format: tick_{tick_number}
        """
        return f"tick_{tick}"

    def _seed_rng(self, seed: str) -> None:
        """Seed the Python random module for deterministic behavior."""
        # Create a numeric seed from the string
        numeric_seed = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (2**32)
        random.seed(numeric_seed)

    def _process_tick_logic(self, db: Session, tick: int, seed: str) -> None:
        """
        Execute the actual game logic for this tick.

        Executes all registered subsystems in their dependency order.

        Args:
            db: Database session
            tick: Current tick number
            seed: RNG seed for this tick
        """
        # Seed the base RNG for deterministic execution
        self._seed_rng(seed)
        base_rng = random.Random()
        base_rng.seed(int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (2**32))

        # Get subsystems in execution order
        subsystems = self.registry.get_execution_order()

        print(f"[Tick {tick}] Processing {len(subsystems)} subsystems with seed={seed}")

        # Create shared event buffer for this tick
        # All subsystems will append to this same list
        tick_events: list[dict[str, Any]] = []

        # Load gameplay config (S2-07)
        try:
            gameplay_config = get_gameplay_config()
            config_dict = gameplay_config.get_all()
        except RuntimeError:
            # Config not initialized - use empty dict (testing scenario)
            config_dict = {}

        # Execute each subsystem with its own context
        for subsystem in subsystems:
            # Create subsystem-specific context with shared event buffer
            ctx = TickContextImpl(
                tick=tick,
                db=db,
                rng=base_rng,
                subsystem_name=subsystem.name,
                config=config_dict,
                events=tick_events  # Pass shared buffer
            )

            try:
                # Execute subsystem
                subsystem.apply(ctx)

                # Log emitted events count (shared buffer grows across subsystems)
                event_count = len([e for e in tick_events if e.get("subsystem") == subsystem.name])
                if event_count > 0:
                    print(f"  [{subsystem.name}] Emitted {event_count} events")

            except Exception as e:
                # Log subsystem failure but continue
                print(f"  [ERROR] Subsystem '{subsystem.name}' failed: {e}")
                raise  # Re-raise to mark tick as failed

        # Log total events for this tick
        if tick_events:
            print(f"  [TICK {tick}] Total events emitted: {len(tick_events)}")

    def execute_tick(self, db: Session) -> Optional[TickLog]:
        """
        Execute a single tick of the game simulation.

        Returns:
            TickLog entry if successful, None if lock couldn't be acquired
        """
        # Try to acquire the distributed lock
        if not self._acquire_tick_lock(db):
            return None

        try:
            # Get current world state
            world_state = db.get(WorldState, 1)
            if not world_state:
                raise RuntimeError("World state not initialized")

            # Calculate next tick
            next_tick = world_state.tick + 1

            # Generate deterministic seed
            seed = self._generate_tick_seed(next_tick)

            # Create tick log entry
            tick_log = TickLog(
                tick=next_tick,
                status=TickStatus.STARTED,
                worker_id=self.worker_id,
                rng_seed=seed,
                started_at=datetime.now(timezone.utc)
            )
            db.add(tick_log)
            db.commit()
            db.refresh(tick_log)

            start_time = datetime.now(timezone.utc)

            try:
                # Execute tick logic
                self._process_tick_logic(db, next_tick, seed)

                # Update world state
                world_state.tick = next_tick
                db.commit()

                # Mark tick as successful
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

                tick_log.status = TickStatus.SUCCESS
                tick_log.ended_at = end_time
                tick_log.duration_ms = duration_ms
                db.commit()

                return tick_log

            except Exception as e:
                # Rollback on error
                db.rollback()

                # Update tick log with error
                tick_log.status = TickStatus.FAILED
                tick_log.ended_at = datetime.now(timezone.utc)
                tick_log.error_message = str(e)
                db.commit()

                raise

        finally:
            # Always release the lock
            self._release_tick_lock(db)

    async def run_forever(self) -> None:
        """
        Run the tick loop continuously at the configured interval.

        This is the main entry point for the background tick task.
        """
        self.running = True
        print(f"[TickExecutor] Starting tick loop (worker_id={self.worker_id}, interval={settings.tick_interval_seconds}s)")

        while self.running:
            try:
                # Get a database session for this tick
                with get_db_session() as db:
                    tick_log = self.execute_tick(db)

                    if tick_log:
                        print(f"[TickExecutor] Tick {tick_log.tick} completed in {tick_log.duration_ms}ms")
                    else:
                        # Another worker has the lock
                        print("[TickExecutor] Could not acquire lock (another worker is active)")

            except Exception as e:
                print(f"[TickExecutor] Error in tick loop: {e}")

            # Wait for next tick interval
            await asyncio.sleep(settings.tick_interval_seconds)

    async def stop(self) -> None:
        """Stop the tick loop gracefully."""
        print(f"[TickExecutor] Stopping tick loop (worker_id={self.worker_id})")
        self.running = False


# Global tick executor instance (will be started in app lifespan)
_tick_executor: Optional[TickExecutor] = None
_tick_task: Optional[asyncio.Task] = None
_global_registry: SubsystemRegistry = SubsystemRegistry()


def get_subsystem_registry() -> SubsystemRegistry:
    """
    Get the global subsystem registry.

    Returns:
        Global subsystem registry
    """
    return _global_registry


async def start_tick_loop(registry: Optional[SubsystemRegistry] = None) -> None:
    """
    Start the global tick executor loop.

    Args:
        registry: Optional subsystem registry (uses global if None)
    """
    global _tick_executor, _tick_task, _global_registry

    if not settings.tick_enabled:
        print("[TickExecutor] Tick loop disabled by configuration")
        return

    if registry is not None:
        _global_registry = registry

    _tick_executor = TickExecutor(registry=_global_registry)
    _tick_task = asyncio.create_task(_tick_executor.run_forever())
    print(f"[TickExecutor] Tick loop started with {_global_registry.count()} subsystems")


async def stop_tick_loop() -> None:
    """Stop the global tick executor loop."""
    global _tick_executor, _tick_task

    if _tick_executor:
        await _tick_executor.stop()

    if _tick_task:
        _tick_task.cancel()
        try:
            await _tick_task
        except asyncio.CancelledError:
            pass

    print("[TickExecutor] Tick loop stopped")


def get_tick_health(db: Optional[Session] = None) -> dict:
    """
    Get health metrics for the tick system.

    Args:
        db: Optional database session (for testing). If None, creates a new session.

    Returns:
        Dictionary with current tick, last success time, and latency stats
    """
    if db is None:
        with get_db_session() as db:
            return _get_tick_health_impl(db)
    else:
        return _get_tick_health_impl(db)


def _get_tick_health_impl(db: Session) -> dict:
    """Implementation of get_tick_health that uses a provided session."""
    # Get current world tick
    world_state = db.get(WorldState, 1)
    current_tick = world_state.tick if world_state else 0

    # Get last successful tick
    last_success = db.execute(
        select(TickLog)
        .where(TickLog.status == TickStatus.SUCCESS)
        .order_by(TickLog.tick.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Calculate p95 latency from recent ticks
    recent_ticks = db.execute(
        select(TickLog.duration_ms)
        .where(TickLog.status == TickStatus.SUCCESS)
        .where(TickLog.duration_ms.isnot(None))
        .order_by(TickLog.tick.desc())
        .limit(100)
    ).scalars().all()

    p95_latency_ms = None
    if recent_ticks:
        sorted_latencies = sorted(recent_ticks)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency_ms = sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]

    return {
        "current_tick": current_tick,
        "last_success_tick": last_success.tick if last_success else None,
        "last_success_time": last_success.ended_at.isoformat() if last_success and last_success.ended_at else None,
        "p95_latency_ms": p95_latency_ms,
        "tick_interval_ms": int(settings.tick_interval_seconds * 1000),
        "worker_id": _tick_executor.worker_id if _tick_executor else None,
        "running": _tick_executor.running if _tick_executor else False
    }
