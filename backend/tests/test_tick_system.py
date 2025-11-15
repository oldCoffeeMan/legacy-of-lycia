"""
Tests for the Authoritative Tick Loop (S2-01)

Test scenarios:
1. Singleton guarantee - only one worker can execute at a time
2. Crash recovery and idempotency - reprocessing yields identical results
3. Tick latency monitoring - metrics reflect performance
"""
import pytest
import time
from datetime import datetime, timezone
from unittest.mock import patch
from src.lycia.tick_executor import (
    TickExecutor,
    get_tick_health,
)
from src.lycia.models import WorldState, TickLog, TickStatus


class TestSingletonGuarantee:
    """Test that only one worker can execute a tick at a time."""

    def test_single_worker_acquires_lock(self, db_session):
        """Test that a single worker can acquire the tick lock."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Create executor and execute tick
        executor = TickExecutor(worker_id="worker-1")
        tick_log = executor.execute_tick(db_session)

        # Verify tick executed successfully
        assert tick_log is not None
        assert tick_log.status == TickStatus.SUCCESS
        assert tick_log.tick == 1
        assert tick_log.worker_id == "worker-1"
        assert tick_log.duration_ms is not None
        assert tick_log.duration_ms >= 0

        # Verify world state updated
        db_session.refresh(world_state)
        assert world_state.tick == 1

    def test_second_worker_cannot_acquire_lock(self, db_session):
        """Test that a second worker cannot execute while first holds lock."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # First worker acquires lock
        executor1 = TickExecutor(worker_id="worker-1")
        lock_acquired = executor1._acquire_tick_lock(db_session)
        assert lock_acquired is True

        try:
            # Second worker tries to acquire lock
            executor2 = TickExecutor(worker_id="worker-2")
            lock_acquired_2 = executor2._acquire_tick_lock(db_session)

            # Second worker should fail to acquire lock
            assert lock_acquired_2 is False

        finally:
            # Clean up: release the lock
            executor1._release_tick_lock(db_session)

    def test_concurrent_tick_execution_blocks_second_worker(self, db_session):
        """Simulate two workers trying to execute tick while lock is held."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # First worker acquires lock but doesn't release yet
        executor1 = TickExecutor(worker_id="worker-1")
        lock_acquired = executor1._acquire_tick_lock(db_session)
        assert lock_acquired is True

        try:
            # While lock is held, second worker tries to execute tick
            executor2 = TickExecutor(worker_id="worker-2")
            tick_log2 = executor2.execute_tick(db_session)

            # Second worker should fail to acquire lock and return None
            assert tick_log2 is None

        finally:
            # Clean up: release the lock
            executor1._release_tick_lock(db_session)

        # Now second worker can execute
        tick_log2 = executor2.execute_tick(db_session)
        assert tick_log2 is not None
        assert tick_log2.status == TickStatus.SUCCESS
        assert tick_log2.worker_id == "worker-2"

    def test_lock_released_after_execution(self, db_session):
        """Test that lock is properly released after tick execution."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # First worker executes tick
        executor1 = TickExecutor(worker_id="worker-1")
        tick_log1 = executor1.execute_tick(db_session)
        assert tick_log1 is not None

        # Lock should be released now, second worker can execute
        executor2 = TickExecutor(worker_id="worker-2")
        tick_log2 = executor2.execute_tick(db_session)
        assert tick_log2 is not None
        assert tick_log2.tick == 2
        assert tick_log2.worker_id == "worker-2"

        # World state should be at tick 2
        db_session.refresh(world_state)
        assert world_state.tick == 2


class TestDeterministicExecution:
    """Test that tick execution is deterministic and idempotent."""

    def test_rng_seed_generation_is_deterministic(self, db_session):
        """Test that the same tick always generates the same RNG seed."""
        executor = TickExecutor()

        # Generate seeds for the same tick multiple times
        seed1 = executor._generate_tick_seed(42)
        seed2 = executor._generate_tick_seed(42)
        seed3 = executor._generate_tick_seed(42)

        # All seeds should be identical
        assert seed1 == seed2 == seed3
        assert seed1 == "tick_42"

    def test_different_ticks_generate_different_seeds(self, db_session):
        """Test that different ticks generate different seeds."""
        executor = TickExecutor()

        seed1 = executor._generate_tick_seed(1)
        seed2 = executor._generate_tick_seed(2)
        seed3 = executor._generate_tick_seed(100)

        # All seeds should be different
        assert seed1 != seed2
        assert seed2 != seed3
        assert seed1 != seed3

    def test_rng_seeding_produces_deterministic_output(self, db_session):
        """Test that seeding RNG produces reproducible random sequences."""
        import random

        executor = TickExecutor()
        seed = "tick_42"

        # First sequence
        executor._seed_rng(seed)
        sequence1 = [random.random() for _ in range(10)]

        # Second sequence with same seed
        executor._seed_rng(seed)
        sequence2 = [random.random() for _ in range(10)]

        # Sequences should be identical
        assert sequence1 == sequence2

    def test_tick_log_records_seed(self, db_session):
        """Test that tick logs record the RNG seed used."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute tick
        executor = TickExecutor()
        tick_log = executor.execute_tick(db_session)

        # Verify seed was recorded
        assert tick_log is not None
        assert tick_log.rng_seed == "tick_1"

        # Execute another tick
        tick_log2 = executor.execute_tick(db_session)
        assert tick_log2.rng_seed == "tick_2"


class TestCrashRecovery:
    """Test crash recovery and error handling."""

    def test_tick_log_created_before_execution(self, db_session):
        """Test that tick log is created at STARTED status before execution."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Mock the tick logic to check log state before completion
        executor = TickExecutor()
        original_process = executor._process_tick_logic

        tick_log_during_execution = None

        def mock_process(db, tick, seed):
            nonlocal tick_log_during_execution
            # Flush session to ensure we can see the tick log
            db.flush()
            # Check tick log state during execution
            tick_log_during_execution = db.query(TickLog).filter_by(tick=tick).first()
            # Capture the status before calling original process
            captured_status = tick_log_during_execution.status if tick_log_during_execution else None
            original_process(db, tick, seed)
            # Store the captured status for later verification
            tick_log_during_execution._captured_status = captured_status

        with patch.object(executor, '_process_tick_logic', side_effect=mock_process):
            executor.execute_tick(db_session)

        # Verify log was in STARTED state during execution
        assert tick_log_during_execution is not None
        assert tick_log_during_execution._captured_status == TickStatus.STARTED
        assert tick_log_during_execution.ended_at is None or tick_log_during_execution._captured_status == TickStatus.STARTED

    def test_failed_tick_records_error(self, db_session):
        """Test that failed tick execution records error in log."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Mock tick logic to raise an error
        executor = TickExecutor()
        error_message = "Simulated subsystem failure"

        with patch.object(executor, '_process_tick_logic', side_effect=Exception(error_message)):
            # Execute tick (should fail)
            with pytest.raises(Exception, match=error_message):
                executor.execute_tick(db_session)

        # Verify tick log recorded the error
        tick_log = db_session.query(TickLog).filter_by(tick=1).first()
        assert tick_log is not None
        assert tick_log.status == TickStatus.FAILED
        assert tick_log.error_message == error_message
        assert tick_log.ended_at is not None

        # World state should NOT have advanced
        db_session.refresh(world_state)
        assert world_state.tick == 0

    def test_lock_released_on_error(self, db_session):
        """Test that lock is released even if tick execution fails."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # First worker fails
        executor1 = TickExecutor(worker_id="worker-1")
        with patch.object(executor1, '_process_tick_logic', side_effect=Exception("Error")):
            with pytest.raises(Exception):
                executor1.execute_tick(db_session)

        # Lock should be released, second worker can execute
        executor2 = TickExecutor(worker_id="worker-2")
        tick_log = executor2.execute_tick(db_session)

        # Second worker should succeed
        assert tick_log is not None
        assert tick_log.status == TickStatus.SUCCESS
        assert tick_log.worker_id == "worker-2"


class TestTickLatencyMonitoring:
    """Test tick performance monitoring and metrics."""

    def test_tick_duration_recorded(self, db_session):
        """Test that tick execution duration is recorded."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute tick
        executor = TickExecutor()
        tick_log = executor.execute_tick(db_session)

        # Verify duration was recorded
        assert tick_log is not None
        assert tick_log.duration_ms is not None
        assert tick_log.duration_ms >= 0
        assert tick_log.started_at is not None
        assert tick_log.ended_at is not None
        assert tick_log.ended_at >= tick_log.started_at

    def test_slow_tick_reflected_in_metrics(self, db_session):
        """Test that artificially slow tick is reflected in metrics."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Mock tick logic with artificial delay
        executor = TickExecutor()
        original_process = executor._process_tick_logic

        def slow_process(db, tick, seed):
            time.sleep(0.1)  # 100ms delay
            original_process(db, tick, seed)

        with patch.object(executor, '_process_tick_logic', side_effect=slow_process):
            tick_log = executor.execute_tick(db_session)

        # Verify duration reflects the delay
        assert tick_log is not None
        assert tick_log.duration_ms >= 100  # At least 100ms

    def test_health_endpoint_returns_metrics(self, db_session):
        """Test that health endpoint returns accurate metrics."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute a few ticks
        executor = TickExecutor()
        for _ in range(3):
            executor.execute_tick(db_session)

        # Get health metrics (pass db_session for testing)
        health = get_tick_health(db=db_session)

        # Verify metrics
        assert health["current_tick"] == 3
        assert health["last_success_tick"] == 3
        assert health["last_success_time"] is not None
        assert health["p95_latency_ms"] is not None
        assert health["p95_latency_ms"] >= 0
        assert health["tick_interval_ms"] == 2000  # Default 2s

    def test_p95_latency_calculation(self, db_session):
        """Test that p95 latency is calculated correctly."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute ticks with varying durations
        executor = TickExecutor()
        durations = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        for i, duration in enumerate(durations):
            # Create tick log manually with specific duration
            tick_log = TickLog(
                tick=i + 1,
                status=TickStatus.SUCCESS,
                worker_id="test-worker",
                rng_seed=f"tick_{i+1}",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                duration_ms=duration
            )
            db_session.add(tick_log)

            # Update world state
            world_state.tick = i + 1

        db_session.commit()

        # Get health metrics (pass db_session for testing)
        health = get_tick_health(db=db_session)

        # p95 of [10,20,30,40,50,60,70,80,90,100] should be 95-100
        assert health["p95_latency_ms"] >= 90
        assert health["p95_latency_ms"] <= 100


class TestTickExecutorConfiguration:
    """Test tick executor configuration and behavior."""

    def test_worker_id_defaults_to_uuid(self, db_session):
        """Test that worker ID defaults to a UUID if not provided."""
        executor = TickExecutor()
        assert executor.worker_id is not None
        assert len(executor.worker_id) > 0

        # Should be different for each instance
        executor2 = TickExecutor()
        assert executor.worker_id != executor2.worker_id

    def test_custom_worker_id(self, db_session):
        """Test that custom worker ID is used when provided."""
        worker_id = "custom-worker-123"
        executor = TickExecutor(worker_id=worker_id)
        assert executor.worker_id == worker_id

    def test_tick_log_includes_worker_id(self, db_session):
        """Test that tick logs include the worker ID."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute tick with custom worker ID
        worker_id = "test-worker-456"
        executor = TickExecutor(worker_id=worker_id)
        tick_log = executor.execute_tick(db_session)

        # Verify worker ID is recorded
        assert tick_log is not None
        assert tick_log.worker_id == worker_id


class TestTickSystemIntegration:
    """Integration tests for the complete tick system."""

    def test_sequential_tick_execution(self, db_session):
        """Test that ticks execute sequentially and increment properly."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute 5 ticks
        executor = TickExecutor()
        for i in range(5):
            tick_log = executor.execute_tick(db_session)
            assert tick_log is not None
            assert tick_log.tick == i + 1
            assert tick_log.status == TickStatus.SUCCESS

        # Verify world state
        db_session.refresh(world_state)
        assert world_state.tick == 5

        # Verify all tick logs exist
        tick_logs = db_session.query(TickLog).order_by(TickLog.tick).all()
        assert len(tick_logs) == 5
        for i, log in enumerate(tick_logs):
            assert log.tick == i + 1
            assert log.status == TickStatus.SUCCESS

    def test_tick_system_audit_trail(self, db_session):
        """Test that tick system maintains complete audit trail."""
        # Initialize world state
        world_state = WorldState(id=1, tick=0)
        db_session.add(world_state)
        db_session.commit()

        # Execute ticks with different workers
        executor1 = TickExecutor(worker_id="worker-1")
        executor2 = TickExecutor(worker_id="worker-2")

        executor1.execute_tick(db_session)
        executor2.execute_tick(db_session)
        executor1.execute_tick(db_session)

        # Verify audit trail
        tick_logs = db_session.query(TickLog).order_by(TickLog.tick).all()
        assert len(tick_logs) == 3

        # Check audit details
        assert tick_logs[0].worker_id == "worker-1"
        assert tick_logs[1].worker_id == "worker-2"
        assert tick_logs[2].worker_id == "worker-1"

        # All should have timestamps and seeds
        for log in tick_logs:
            assert log.started_at is not None
            assert log.ended_at is not None
            assert log.rng_seed is not None
            assert log.duration_ms is not None
