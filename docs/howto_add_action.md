# How to Add an Action Handler

This guide shows you how to implement and register a new player action in the Legacy of Lycia game engine.

## What is an Action Handler?

An action handler processes a specific type of player command (e.g., "boost city prosperity", "move unit", "declare war"). Handlers validate commands and emit events that modify game state.

## Key Concepts

- **Intent**: A unique identifier for the action type (e.g., `"prosperity_boost"`, `"move_unit"`)
- **Version**: Allows multiple versions of the same intent to coexist (for backward compatibility)
- **Validation**: Two-stage validation process (syntactic params validation, then semantic world state validation)
- **Event Sourcing**: Handlers don't modify state directly - they emit events that are processed later

## Implementation Steps

### 1. Implement the ActionHandler Protocol

Create a class that implements the `ActionHandler` protocol defined in [backend/src/lycia/actions/protocol.py](../backend/src/lycia/actions/protocol.py).

**Required Properties:**
- `intent` (str): Unique identifier for this action type
- `version` (int): Handler version (start at 1, increment for breaking changes)

**Required Methods:**
- `validate_params(params: dict) -> ValidationResult`: Validate parameter structure and types
- `validate_world_state(params, player_id, db, tick) -> ValidationResult`: Check if action is valid in current game state
- `execute(params, player_id, db, tick, command_id) -> list[dict]`: Emit events to modify game state

### 2. Example Implementation

Here's a complete example based on [backend/src/lycia/actions/handlers/prosperity_boost.py](../backend/src/lycia/actions/handlers/prosperity_boost.py):

```python
from sqlalchemy.orm import Session
from lycia.actions.protocol import ValidationResult
from lycia.models import City


class ProsperityBoostHandler:
    """
    Boost the prosperity of a city.

    Example command params:
        {
            "city_id": 1,
            "amount": 10
        }
    """

    @property
    def intent(self) -> str:
        """Unique action identifier."""
        return "prosperity_boost"

    @property
    def version(self) -> int:
        """Handler version (increment for breaking changes)."""
        return 1

    def validate_params(self, params: dict) -> ValidationResult:
        """
        Validate parameters (syntactic validation).

        Check:
        - Required fields are present
        - Types are correct
        - Values are in valid ranges
        - Format is correct

        DO NOT check world state here (no database queries).
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
        Validate against current world state (semantic validation).

        Check:
        - Referenced entities exist (cities, units, etc.)
        - Player has permissions/ownership
        - Player has sufficient resources
        - No conflicting states (e.g., city under siege)
        - Cooldowns or rate limits

        This is called AFTER validate_params(), so params are guaranteed valid.
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

        # Example: Check if player owns or has influence over the city
        # if city.owner_id != player_id:
        #     result.add_error(
        #         "city_id",
        #         "You do not control this city",
        #         "INSUFFICIENT_PERMISSIONS"
        #     )

        # Example: Check if prosperity is already at max
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
        Execute action and return events.

        IMPORTANT:
        - DO NOT modify database state directly
        - Return events that will be processed later
        - This keeps handlers pure and ensures event sourcing
        - You can query the database for context (read-only)

        Args:
            params: Validated parameters
            player_id: ID of player executing this action
            db: Database session (for queries only, not writes)
            tick: Current game tick
            command_id: Unique ID of this command

        Returns:
            List of event dicts to be emitted to the event log
        """
        city_id = params["city_id"]
        amount = params["amount"]

        # Query city for event data (read-only)
        city = db.query(City).filter(City.id == city_id).first()

        # Return events to be processed
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
```

### 3. Using ValidationResult

The `ValidationResult` class tracks validation errors:

```python
from lycia.actions.protocol import ValidationResult

# Start with success
result = ValidationResult.success()

# Add errors as needed
result.add_error(
    field="city_id",              # Which parameter failed
    message="City not found",      # Human-readable message
    error_code="CITY_NOT_FOUND"   # Machine-readable error code
)

# Check if valid
if not result.is_valid:
    # Handle errors
    for error in result.errors:
        print(f"{error.field}: {error.message} ({error.error_code})")
```

### 4. Register Your Handler

In [backend/src/lycia/app.py](../backend/src/lycia/app.py), register your handler with the global registry:

```python
from lycia.actions.registry import ActionHandlerRegistry
from lycia.actions.handlers.prosperity_boost import ProsperityBoostHandler
from lycia.actions.handlers.your_handler import YourHandler

# Get or create global registry
action_handler_registry = ActionHandlerRegistry()

# Register handlers
action_handler_registry.register(ProsperityBoostHandler())
action_handler_registry.register(YourHandler())  # Add your handler here
```

The registry allows multiple versions:

```python
# Register multiple versions
action_handler_registry.register(MoveUnitHandlerV1())  # version=1
action_handler_registry.register(MoveUnitHandlerV2())  # version=2

# Get specific version
handler = action_handler_registry.get("move_unit", version=1)

# Get latest version
handler = action_handler_registry.get_latest("move_unit")  # Returns v2
```

### 5. How Actions Are Processed

When a player submits a command, the [backend/src/lycia/subsystems/action_command_subsystem.py](../backend/src/lycia/subsystems/action_command_subsystem.py) processes it during the INTENTS phase:

1. **Command Created**: Client sends POST to `/api/commands` with `{intent, version, params}`
2. **Queued**: Command stored in database with status "pending"
3. **Tick Execution**: ActionCommandSubsystem runs during INTENTS phase
4. **Handler Lookup**: Registry finds handler by `intent@version`
5. **Validation**: Both `validate_params()` and `validate_world_state()` called
6. **Execution**: If valid, `execute()` is called and events are emitted
7. **Event Processing**: Events flow through subsystem pipeline to modify state

### 6. Event Naming Convention

Use dotted notation for event types:

- `city.prosperity_boosted` - City-related events
- `unit.moved` - Unit-related events
- `diplomacy.treaty_signed` - Diplomacy events
- `combat.battle_resolved` - Combat events
- `action_failed` - Generic failure event

### 7. Error Codes Convention

Use UPPER_SNAKE_CASE for error codes:

**Field Errors:**
- `MISSING_FIELD` - Required field not provided
- `INVALID_TYPE` - Wrong data type
- `INVALID_VALUE` - Value doesn't meet constraints
- `VALUE_TOO_LOW` / `VALUE_TOO_HIGH` - Out of range

**World State Errors:**
- `CITY_NOT_FOUND` / `UNIT_NOT_FOUND` - Entity doesn't exist
- `INSUFFICIENT_PERMISSIONS` - Player lacks access
- `INSUFFICIENT_RESOURCES` - Not enough gold/resources
- `INVALID_STATE` - Game state doesn't permit action
- `COOLDOWN_ACTIVE` - Action still on cooldown

## Complete Examples

See these files for working examples:

- **Prosperity Boost**: [backend/src/lycia/actions/handlers/prosperity_boost.py](../backend/src/lycia/actions/handlers/prosperity_boost.py) - Demonstrates semantic validation
- **Test Action**: [backend/src/lycia/actions/handlers/test_action.py](../backend/src/lycia/actions/handlers/test_action.py) - Simple testing handler
- **Protocol**: [backend/src/lycia/actions/protocol.py](../backend/src/lycia/actions/protocol.py) - ActionHandler interface definition

## Testing Your Handler

Example test pattern:

```python
from lycia.actions.handlers.your_handler import YourHandler

def test_your_handler_params_validation():
    handler = YourHandler()

    # Test valid params
    result = handler.validate_params({"city_id": 1, "amount": 10})
    assert result.is_valid

    # Test missing field
    result = handler.validate_params({"amount": 10})
    assert not result.is_valid
    assert any(e.error_code == "MISSING_FIELD" for e in result.errors)

    # Test invalid type
    result = handler.validate_params({"city_id": "abc", "amount": 10})
    assert not result.is_valid
    assert any(e.error_code == "INVALID_TYPE" for e in result.errors)


def test_your_handler_world_state_validation(db_session, sample_city):
    handler = YourHandler()

    # Test city exists
    result = handler.validate_world_state(
        params={"city_id": sample_city.id, "amount": 10},
        player_id=1,
        db=db_session,
        tick=1
    )
    assert result.is_valid

    # Test city doesn't exist
    result = handler.validate_world_state(
        params={"city_id": 99999, "amount": 10},
        player_id=1,
        db=db_session,
        tick=1
    )
    assert not result.is_valid
    assert any(e.error_code == "CITY_NOT_FOUND" for e in result.errors)


def test_your_handler_execution(db_session, sample_city):
    handler = YourHandler()

    events = handler.execute(
        params={"city_id": sample_city.id, "amount": 10},
        player_id=1,
        db=db_session,
        tick=1,
        command_id=123
    )

    # Verify events emitted
    assert len(events) == 1
    assert events[0]["type"] == "city.prosperity_boosted"
    assert events[0]["data"]["city_id"] == sample_city.id
    assert events[0]["data"]["amount"] == 10
```

## Common Patterns

### Resource Cost Validation

```python
def validate_world_state(self, params, player_id, db, tick):
    result = ValidationResult.success()

    # Check player resources
    player = db.query(Player).filter(Player.id == player_id).first()
    cost = params["amount"] * 10  # Example cost calculation

    if player.gold < cost:
        result.add_error(
            "amount",
            f"Insufficient gold. Need {cost}, have {player.gold}",
            "INSUFFICIENT_RESOURCES"
        )

    return result
```

### Cooldown Checking

```python
def validate_world_state(self, params, player_id, db, tick):
    result = ValidationResult.success()

    # Check for recent actions
    last_action = db.query(Event).filter(
        Event.type == "city.prosperity_boosted",
        Event.data["player_id"] == player_id,
        Event.tick > tick - 10  # 10 tick cooldown
    ).first()

    if last_action:
        result.add_error(
            "general",
            "This action is on cooldown",
            "COOLDOWN_ACTIVE"
        )

    return result
```

### Multiple Event Emission

```python
def execute(self, params, player_id, db, tick, command_id):
    return [
        {
            "type": "player.resources_consumed",
            "tick": tick,
            "data": {"player_id": player_id, "gold": -100}
        },
        {
            "type": "city.prosperity_boosted",
            "tick": tick,
            "data": {"city_id": params["city_id"], "amount": params["amount"]}
        },
        {
            "type": "player.action_completed",
            "tick": tick,
            "data": {"player_id": player_id, "action": self.intent}
        }
    ]
```
