"""
Action Command Subsystem - INTENTS Phase.

This subsystem processes queued action commands during the INTENTS phase
of tick execution. It validates commands, executes handlers, and emits events.
"""

from datetime import datetime, timezone
from sqlalchemy import and_
from lycia.models import ActionCommand, ActionCommandStatus
from lycia.actions import get_action_handler_registry
from .phase import SubsystemPhase
from .protocol import TickContext


class ActionCommandSubsystem:
    """
    Processes action commands from the queue.

    This subsystem runs in the INTENTS phase (first phase) to ensure
    all player and AI actions are processed before other game systems.

    Responsibilities:
    - Query pending commands eligible for current tick
    - Validate commands (syntactic and semantic)
    - Execute handlers and emit events
    - Mark commands as PROCESSED/REJECTED/EXPIRED
    - Ensure exactly-once processing via status tracking
    """

    @property
    def name(self) -> str:
        """Subsystem identifier."""
        return "action_commands"

    @property
    def phase(self) -> SubsystemPhase:
        """Execute in INTENTS phase (first phase)."""
        return SubsystemPhase.INTENTS

    @property
    def dependencies(self) -> list[str]:
        """No dependencies - runs first in INTENTS phase."""
        return []

    def apply(self, ctx: TickContext) -> None:
        """
        Process action commands for current tick.

        Algorithm:
        1. Query all PENDING commands where:
           - valid_from_tick <= current_tick
           - expires_at_tick >= current_tick
        2. For each command:
           a. Check if expired (expires_at_tick < current_tick)
              → Mark as EXPIRED
           b. Validate syntactically (schema)
              → If invalid, mark as REJECTED with errors
           c. Validate semantically (world state)
              → If invalid, mark as REJECTED with errors
           d. Execute handler
              → Emit events
              → Mark as PROCESSED
        3. Commit all changes atomically

        Args:
            ctx: Tick context with DB, RNG, and event emission
        """
        current_tick = ctx.tick
        db = ctx.db
        registry = get_action_handler_registry()

        # Query eligible commands
        # Use pessimistic locking (SELECT FOR UPDATE) to prevent race conditions
        # if multiple workers somehow acquire the tick lock
        commands = (
            db.query(ActionCommand)
            .filter(
                and_(
                    ActionCommand.status == ActionCommandStatus.PENDING,
                    ActionCommand.valid_from_tick <= current_tick,
                )
            )
            .with_for_update()  # Lock rows to prevent concurrent processing
            .all()
        )

        processed_count = 0
        rejected_count = 0
        expired_count = 0

        for command in commands:
            # Check expiration
            if command.expires_at_tick < current_tick:
                self._mark_expired(command, current_tick)
                expired_count += 1
                ctx.emit("action.expired", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "valid_from_tick": command.valid_from_tick,
                    "expires_at_tick": command.expires_at_tick,
                })
                continue

            # Get handler
            handler = registry.get(command.intent, command.version)
            if handler is None:
                # No handler registered for this intent@version
                self._mark_rejected(
                    command,
                    current_tick,
                    {
                        "errors": [
                            {
                                "field": None,
                                "message": f"No handler registered for {command.intent}@{command.version}",
                                "code": "HANDLER_NOT_FOUND"
                            }
                        ]
                    }
                )
                rejected_count += 1
                ctx.emit("action.rejected", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "reason": "HANDLER_NOT_FOUND",
                })
                continue

            # Syntactic validation
            syntactic_result = handler.validate_params(command.params)
            if not syntactic_result.valid:
                self._mark_rejected(
                    command,
                    current_tick,
                    syntactic_result.to_dict()
                )
                rejected_count += 1
                ctx.emit("action.rejected", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "reason": "INVALID_PARAMS",
                    "errors": syntactic_result.to_dict()["errors"],
                })
                continue

            # Semantic validation
            semantic_result = handler.validate_world_state(
                command.params,
                command.player_id,
                db,
                current_tick
            )
            if not semantic_result.valid:
                self._mark_rejected(
                    command,
                    current_tick,
                    semantic_result.to_dict()
                )
                rejected_count += 1
                ctx.emit("action.rejected", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "reason": "INVALID_WORLD_STATE",
                    "errors": semantic_result.to_dict()["errors"],
                })
                continue

            # Execute handler
            try:
                events = handler.execute(
                    command.params,
                    command.player_id,
                    db,
                    current_tick,
                    command.id
                )

                # Mark as processed
                self._mark_processed(command, current_tick)
                processed_count += 1

                # Emit handler events
                for event in events:
                    ctx.emit(event["type"], event.get("data", {}))

                # Emit processing success event
                ctx.emit("action.processed", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "event_count": len(events),
                })

            except Exception as e:
                # Handler execution failed - mark as rejected
                self._mark_rejected(
                    command,
                    current_tick,
                    {
                        "errors": [
                            {
                                "field": None,
                                "message": f"Handler execution failed: {str(e)}",
                                "code": "EXECUTION_ERROR"
                            }
                        ]
                    }
                )
                rejected_count += 1
                ctx.emit("action.rejected", {
                    "command_id": command.id,
                    "intent": command.intent,
                    "player_id": command.player_id,
                    "reason": "EXECUTION_ERROR",
                    "error": str(e),
                })

        # Commit all changes
        db.commit()

        # Emit summary event
        ctx.emit("action_commands.processed", {
            "total": len(commands),
            "processed": processed_count,
            "rejected": rejected_count,
            "expired": expired_count,
        })

    def _mark_processed(self, command: ActionCommand, tick: int) -> None:
        """Mark command as successfully processed."""
        command.status = ActionCommandStatus.PROCESSED
        command.processed_at = datetime.now(timezone.utc)
        command.processed_at_tick = tick

    def _mark_rejected(self, command: ActionCommand, tick: int, errors: dict) -> None:
        """Mark command as rejected with validation errors."""
        command.status = ActionCommandStatus.REJECTED
        command.processed_at = datetime.now(timezone.utc)
        command.processed_at_tick = tick
        command.validation_errors = errors

    def _mark_expired(self, command: ActionCommand, tick: int) -> None:
        """Mark command as expired."""
        command.status = ActionCommandStatus.EXPIRED
        command.processed_at = datetime.now(timezone.utc)
        command.processed_at_tick = tick
