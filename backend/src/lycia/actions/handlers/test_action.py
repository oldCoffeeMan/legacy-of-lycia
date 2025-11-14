"""
Test action handler for demonstration and testing.

This is a simple handler that validates a message parameter and emits an event.
"""

from sqlalchemy.orm import Session
from lycia.actions.protocol import ValidationResult, ValidationError


class TestActionHandler:
    """
    Simple test action handler.

    This handler accepts a single 'message' parameter and emits a test event.
    It's useful for testing the action command system without complex game logic.

    Example params:
        {"message": "Hello, world!"}
    """

    @property
    def intent(self) -> str:
        return "test_action"

    @property
    def version(self) -> int:
        return 1

    def validate_params(self, params: dict) -> ValidationResult:
        """
        Validate that params contains a 'message' string.

        Required fields:
        - message: str (1-500 characters)
        """
        result = ValidationResult.success()

        # Check message field
        if "message" not in params:
            result.add_error("message", "Message is required", "MISSING_FIELD")
            return result

        message = params["message"]

        # Check message type
        if not isinstance(message, str):
            result.add_error("message", "Message must be a string", "INVALID_TYPE")
            return result

        # Check message length
        if len(message) < 1:
            result.add_error("message", "Message cannot be empty", "EMPTY_VALUE")
        elif len(message) > 500:
            result.add_error("message", "Message too long (max 500 characters)", "VALUE_TOO_LONG")

        return result

    def validate_world_state(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int
    ) -> ValidationResult:
        """
        No world state validation needed for test action.

        This handler doesn't interact with game entities, so all
        world states are valid.
        """
        return ValidationResult.success()

    def execute(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int,
        command_id: int
    ) -> list[dict]:
        """
        Execute test action and emit event.

        Returns a single event containing the message.
        """
        return [
            {
                "type": "test.action_executed",
                "command_id": command_id,
                "tick": tick,
                "data": {
                    "player_id": player_id,
                    "message": params["message"],
                }
            }
        ]
