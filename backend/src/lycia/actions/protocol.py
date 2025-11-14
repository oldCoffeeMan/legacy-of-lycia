"""
Action handler protocol and validation types.

This module defines the protocol that all action handlers must implement,
along with types for validation results.
"""

from dataclasses import dataclass, field
from typing import Protocol, Any
from sqlalchemy.orm import Session


@dataclass
class ValidationError:
    """
    A single validation error.

    Attributes:
        field: The field that failed validation (None for general errors)
        message: Human-readable error message
        code: Machine-readable error code
    """
    field: str | None
    message: str
    code: str


@dataclass
class ValidationResult:
    """
    Result of validation (syntactic or semantic).

    Attributes:
        valid: Whether validation passed
        errors: List of validation errors (empty if valid)
    """
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(valid=True, errors=[])

    @classmethod
    def failure(cls, *errors: ValidationError) -> "ValidationResult":
        """Create a failed validation result with errors."""
        return cls(valid=False, errors=list(errors))

    def add_error(self, field: str | None, message: str, code: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, message=message, code=code))
        self.valid = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "code": e.code
                }
                for e in self.errors
            ]
        }


class ActionHandler(Protocol):
    """
    Protocol for action handlers.

    Each handler processes a specific type of action (intent) and produces
    events that modify game state. Handlers must be:
    - Idempotent: Re-executing with same inputs produces same events
    - Pure: Only read from DB, emit events (no direct writes except event log)
    - Versioned: Support multiple versions for backward compatibility

    Example:
        class MoveUnitHandler:
            @property
            def intent(self) -> str:
                return "move_unit"

            @property
            def version(self) -> int:
                return 1

            def validate_params(self, params: dict) -> ValidationResult:
                # Syntactic validation (schema)
                if "unit_id" not in params:
                    return ValidationResult.failure(
                        ValidationError("unit_id", "Missing unit_id", "MISSING_FIELD")
                    )
                return ValidationResult.success()

            def validate_world_state(self, params: dict, player_id: int, db: Session, tick: int) -> ValidationResult:
                # Semantic validation (business rules)
                unit = db.query(Unit).filter_by(id=params["unit_id"]).first()
                if not unit or unit.player_id != player_id:
                    return ValidationResult.failure(
                        ValidationError("unit_id", "Unit not found or not owned", "INVALID_UNIT")
                    )
                return ValidationResult.success()

            def execute(self, params: dict, player_id: int, db: Session, tick: int, command_id: int) -> list[dict]:
                # Execute action and return events
                return [
                    {
                        "type": "unit.moved",
                        "command_id": command_id,
                        "tick": tick,
                        "data": {
                            "unit_id": params["unit_id"],
                            "from_position": params["from"],
                            "to_position": params["to"]
                        }
                    }
                ]
    """

    @property
    def intent(self) -> str:
        """
        The intent identifier for this handler (e.g., "move_unit").

        This is used to match commands to handlers and should be unique
        per version.
        """
        ...

    @property
    def version(self) -> int:
        """
        Handler version for backward compatibility.

        When making breaking changes to a handler, create a new version
        to support old commands in the queue.
        """
        ...

    def validate_params(self, params: dict) -> ValidationResult:
        """
        Validate command parameters (syntactic validation).

        This should check:
        - Required fields are present
        - Field types are correct
        - Value ranges are valid
        - Format constraints are met

        This should NOT check world state or business rules.

        Args:
            params: The action parameters from the command

        Returns:
            ValidationResult indicating success or failure with errors
        """
        ...

    def validate_world_state(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int
    ) -> ValidationResult:
        """
        Validate against world state (semantic validation).

        This should check:
        - Player owns referenced entities
        - Entities are in valid states
        - Business rules are satisfied
        - Resources are available

        This is called after syntactic validation passes and only if
        the command is being processed (not expired).

        Args:
            params: The action parameters (already syntactically valid)
            player_id: The ID of the player who submitted the command
            db: Database session for queries
            tick: Current tick number

        Returns:
            ValidationResult indicating success or failure with errors
        """
        ...

    def execute(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int,
        command_id: int
    ) -> list[dict]:
        """
        Execute the action and return events.

        This is called after both syntactic and semantic validation pass.
        It should:
        - Query necessary data from DB
        - Calculate outcomes
        - Return events describing state changes
        - Be idempotent (use command_id + tick as unique key)

        The returned events will be processed by downstream systems to
        actually modify game state.

        Args:
            params: The action parameters (fully validated)
            player_id: The ID of the player who submitted the command
            db: Database session for queries
            tick: Current tick number
            command_id: Unique command identifier for idempotency

        Returns:
            List of event dictionaries with structure:
                {
                    "type": str,  # Event type (e.g., "unit.moved")
                    "command_id": int,  # For idempotency
                    "tick": int,  # Tick when event occurred
                    "data": dict  # Event-specific data
                }
        """
        ...
