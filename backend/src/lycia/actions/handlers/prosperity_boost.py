"""
Prosperity Boost action handler.

This handler allows players to boost the prosperity of a city.
Demonstrates semantic validation (checking city ownership/existence).
"""

from sqlalchemy.orm import Session
from lycia.actions.protocol import ValidationResult
from lycia.models import City


class ProsperityBoostHandler:
    """
    Boost the prosperity of a city.

    This is a demonstration handler that shows how to:
    - Validate parameters (syntactic)
    - Check world state (semantic - city exists)
    - Emit events that affect game state

    Example params:
        {
            "city_id": 1,
            "amount": 10
        }

    In a real game, this might require resources, check player ownership,
    or have cooldowns. For now, it's simplified for demonstration.
    """

    @property
    def intent(self) -> str:
        return "prosperity_boost"

    @property
    def version(self) -> int:
        return 1

    def validate_params(self, params: dict) -> ValidationResult:
        """
        Validate prosperity boost parameters.

        Required fields:
        - city_id: int (positive)
        - amount: int (1-50)
        """
        result = ValidationResult.success()

        # Validate city_id
        if "city_id" not in params:
            result.add_error("city_id", "City ID is required", "MISSING_FIELD")
        else:
            city_id = params["city_id"]
            if not isinstance(city_id, int):
                result.add_error("city_id", "City ID must be an integer", "INVALID_TYPE")
            elif city_id <= 0:
                result.add_error("city_id", "City ID must be positive", "INVALID_VALUE")

        # Validate amount
        if "amount" not in params:
            result.add_error("amount", "Amount is required", "MISSING_FIELD")
        else:
            amount = params["amount"]
            if not isinstance(amount, int):
                result.add_error("amount", "Amount must be an integer", "INVALID_TYPE")
            elif amount < 1:
                result.add_error("amount", "Amount must be at least 1", "VALUE_TOO_LOW")
            elif amount > 50:
                result.add_error("amount", "Amount cannot exceed 50", "VALUE_TOO_HIGH")

        return result

    def validate_world_state(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int
    ) -> ValidationResult:
        """
        Validate that the city exists.

        In a real implementation, we might also check:
        - Player owns or has influence over the city
        - Player has sufficient resources
        - City is not under siege
        - Cooldowns or rate limits
        """
        result = ValidationResult.success()

        city_id = params["city_id"]
        city = db.query(City).filter(City.id == city_id).first()

        if city is None:
            result.add_error(
                "city_id",
                f"City with ID {city_id} does not exist",
                "CITY_NOT_FOUND"
            )
            return result

        # Future: Check if player owns or has influence over the city
        # For now, any player can boost any city (simplified)

        # Future: Check if prosperity is already at max
        # if city.prosperity >= 100:
        #     result.add_error(
        #         "city_id",
        #         "City prosperity is already at maximum",
        #         "PROSPERITY_AT_MAX"
        #     )

        return result

    def execute(
        self,
        params: dict,
        player_id: int,
        db: Session,
        tick: int,
        command_id: int
    ) -> list[dict]:
        """
        Execute prosperity boost and emit event.

        The event will be processed by a downstream system to actually
        update the city's prosperity. This keeps the handler pure and
        ensures proper event sourcing.
        """
        city_id = params["city_id"]
        amount = params["amount"]

        # Query city for event data
        city = db.query(City).filter(City.id == city_id).first()

        return [
            {
                "type": "city.prosperity_boosted",
                "command_id": command_id,
                "tick": tick,
                "data": {
                    "city_id": city_id,
                    "city_name": city.name,
                    "player_id": player_id,
                    "amount": amount,
                    "old_prosperity": city.prosperity,
                    "new_prosperity": min(100, city.prosperity + amount),  # Cap at 100
                }
            }
        ]
