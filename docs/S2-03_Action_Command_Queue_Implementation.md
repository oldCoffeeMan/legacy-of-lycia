# S2-03: Action Command Queue Implementation

**Sprint:** Sprint 2
**Status:** ✅ Complete
**Date:** 2025-11-14

## Overview

S2-03 implements a robust action command queue system that allows players and AI to submit actions that are validated and applied on the next eligible tick. This implementation follows event sourcing principles and ensures exactly-once processing with structured validation errors.

## User Story

> As a player (and as AI/NPC), I want to submit actions that are validated and applied on the next eligible tick, so outcomes are predictable and fair.

## Acceptance Criteria

✅ **AC1: REST endpoint to enqueue an ActionCommand**
- Implemented `POST /api/actions/enqueue` endpoint
- Accepts `intent`, `params`, `valid_from_tick`, `expires_at_tick`
- Returns `command_id`, `status`, and `submitted_at`

✅ **AC2: Commands are consumed exactly once by the INTENTS phase**
- `ActionCommandSubsystem` processes commands during INTENTS phase
- Status tracking prevents double processing
- Expired commands are ignored without execution

✅ **AC3: Rejected commands return structured validation errors (no side-effects)**
- Syntactic validation via `handler.validate_params()`
- Semantic validation via `handler.validate_world_state()`
- Errors stored in `validation_errors` JSON field
- Failed validation has no side effects on game state

✅ **AC4: Processing a command produces one or more events (append-only)**
- Handlers return event dictionaries
- Events emitted via `TickContext.emit()`
- Event format: `{"type": str, "command_id": int, "tick": int, "data": dict}`

## Architecture

### 1. Database Model

**File:** [`backend/src/lycia/models.py`](../backend/src/lycia/models.py:107-172)

```python
class ActionCommand(Base):
    __tablename__ = "action_commands"

    # Primary key
    id: Mapped[int]

    # Player identification
    player_id: Mapped[int]  # FK to players

    # Command specification
    intent: Mapped[str]  # e.g., "move_unit"
    version: Mapped[int]  # Handler version
    params: Mapped[dict]  # JSON parameters

    # Temporal constraints
    valid_from_tick: Mapped[int]  # First eligible tick
    expires_at_tick: Mapped[int]  # Last eligible tick

    # Processing state
    status: Mapped[ActionCommandStatus]  # PENDING/PROCESSED/REJECTED/EXPIRED
    submitted_at: Mapped[datetime]
    processed_at: Mapped[datetime | None]
    processed_at_tick: Mapped[int | None]
    validation_errors: Mapped[dict | None]  # Structured error details

    # Constraints
    UniqueConstraint('player_id', 'intent', 'valid_from_tick')  # Prevent duplicates
    Index('ix_action_commands_queue_processing', 'status', 'valid_from_tick', 'expires_at_tick')
```

**Key Design Decisions:**
- **Unique Constraint:** Prevents duplicate submissions for same (player, intent, tick)
- **Status Enum:** Explicit state machine for command lifecycle
- **JSON Fields:** Flexible parameter storage and structured error reporting
- **Composite Index:** Optimizes queue processing queries

### 2. ActionHandler Protocol

**File:** [`backend/src/lycia/actions/protocol.py`](../backend/src/lycia/actions/protocol.py)

```python
class ActionHandler(Protocol):
    @property
    def intent(self) -> str: ...  # e.g., "move_unit"

    @property
    def version(self) -> int: ...  # Handler version

    def validate_params(self, params: dict) -> ValidationResult:
        """Syntactic validation (schema, types, ranges)"""
        ...

    def validate_world_state(
        self, params: dict, player_id: int, db: Session, tick: int
    ) -> ValidationResult:
        """Semantic validation (business rules, ownership, resources)"""
        ...

    def execute(
        self, params: dict, player_id: int, db: Session, tick: int, command_id: int
    ) -> list[dict]:
        """Execute action and return events"""
        ...
```

**Design Principles:**
- **Two-Phase Validation:** Separate syntactic (cheap) from semantic (expensive)
- **Idempotency:** Execute must produce same events for same inputs
- **Event Sourcing:** Returns events instead of directly modifying state
- **Versioning:** Support multiple handler versions for backward compatibility

### 3. ActionHandler Registry

**File:** [`backend/src/lycia/actions/registry.py`](../backend/src/lycia/actions/registry.py)

```python
class ActionHandlerRegistry:
    def register(self, handler: ActionHandler) -> None:
        """Register handler with key: {intent}@{version}"""
        ...

    def get(self, intent: str, version: int) -> ActionHandler | None:
        """Get specific handler version"""
        ...

    def get_latest(self, intent: str) -> ActionHandler | None:
        """Get handler with highest version"""
        ...
```

**Features:**
- **Singleton Pattern:** Global registry via `get_action_handler_registry()`
- **Versioned Handlers:** Support `intent@version` key format
- **Duplicate Prevention:** Raises error if same `intent@version` registered twice

### 4. INTENTS Phase Subsystem

**File:** [`backend/src/lycia/subsystems/action_command_subsystem.py`](../backend/src/lycia/subsystems/action_command_subsystem.py)

```python
class ActionCommandSubsystem:
    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.INTENTS  # First phase

    def apply(self, ctx: TickContext) -> None:
        """Process all pending commands for current tick"""
        ...
```

**Processing Algorithm:**
1. Query all `PENDING` commands where `valid_from_tick <= current_tick`
2. For each command:
   - **Check expiration:** If `expires_at_tick < current_tick`, mark `EXPIRED`
   - **Get handler:** From registry by `intent@version`
   - **Syntactic validation:** Call `handler.validate_params()`
   - **Semantic validation:** Call `handler.validate_world_state()`
   - **Execute:** Call `handler.execute()` and emit events
   - **Update status:** Mark as `PROCESSED` or `REJECTED`
3. Commit all changes atomically

**Key Features:**
- **Pessimistic Locking:** Uses `SELECT FOR UPDATE` to prevent race conditions
- **Exactly-Once Processing:** Status != PENDING prevents re-processing
- **Structured Errors:** Validation failures stored in `validation_errors` field
- **Event Emission:** All events collected and logged

### 5. REST API Endpoints

**File:** [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:156-394)

#### POST /api/actions/enqueue

Enqueue an action command for processing.

**Request Body:**
```json
{
  "intent": "test_action",
  "version": 1,
  "params": {"message": "Hello, world!"},
  "valid_from_tick": 10,
  "expires_at_tick": 15
}
```

**Response (200 OK):**
```json
{
  "command_id": 123,
  "status": "pending",
  "message": "Command queued successfully. Will be processed on tick 10.",
  "submitted_at": "2025-11-14T20:00:00.000Z"
}
```

**Error Responses:**
- `401 Unauthorized`: Not logged in
- `400 Bad Request`: Invalid parameters or temporal constraints
- `409 Conflict`: Duplicate command submission
- `500 Internal Server Error`: Database error

**Validation Steps:**
1. **Authentication:** Verify player session
2. **Temporal:** Ensure `valid_from_tick <= expires_at_tick`
3. **Handler Exists:** Check registry for `intent@version`
4. **Syntactic:** Validate params via handler
5. **Duplicate Check:** Unique constraint on (player, intent, valid_from_tick)

#### GET /api/actions/my-commands

Retrieve player's action commands.

**Query Parameters:**
- `status`: Filter by status (optional)
- `limit`: Max results (default: 50, max: 100)

**Response:**
```json
{
  "commands": [
    {
      "id": 123,
      "intent": "test_action",
      "version": 1,
      "params": {"message": "Hello"},
      "valid_from_tick": 10,
      "expires_at_tick": 15,
      "status": "processed",
      "submitted_at": "2025-11-14T20:00:00.000Z",
      "processed_at": "2025-11-14T20:00:02.000Z",
      "processed_at_tick": 10,
      "validation_errors": null
    }
  ]
}
```

### 6. Example Action Handlers

#### TestActionHandler

**File:** [`backend/src/lycia/actions/handlers/test_action.py`](../backend/src/lycia/actions/handlers/test_action.py)

Simple handler for testing that accepts a `message` parameter.

**Example Usage:**
```python
{
  "intent": "test_action",
  "version": 1,
  "params": {"message": "Hello, world!"}
}
```

**Events Emitted:**
```python
{
  "type": "test.action_executed",
  "command_id": 123,
  "tick": 10,
  "data": {
    "player_id": 1,
    "message": "Hello, world!"
  }
}
```

#### ProsperityBoostHandler

**File:** [`backend/src/lycia/actions/handlers/prosperity_boost.py`](../backend/src/lycia/actions/handlers/prosperity_boost.py)

Boosts a city's prosperity, demonstrating semantic validation.

**Example Usage:**
```python
{
  "intent": "prosperity_boost",
  "version": 1,
  "params": {
    "city_id": 1,
    "amount": 10
  }
}
```

**Validation:**
- **Syntactic:** `city_id` must be positive int, `amount` must be 1-50
- **Semantic:** City must exist in database

**Events Emitted:**
```python
{
  "type": "city.prosperity_boosted",
  "command_id": 123,
  "tick": 10,
  "data": {
    "city_id": 1,
    "city_name": "Athens",
    "player_id": 1,
    "amount": 10,
    "old_prosperity": 50,
    "new_prosperity": 60
  }
}
```

## Implementation Details

### Database Migration

**File:** [`backend/alembic/versions/73d3f5e150bd_add_action_commands_table_for_s2_03.py`](../backend/alembic/versions/73d3f5e150bd_add_action_commands_table_for_s2_03.py)

```bash
# Generate migration
cd backend
alembic revision --autogenerate -m "add action_commands table for S2-03"

# Apply migration
alembic upgrade head
```

**Migration Includes:**
- Create `action_commands` table with all fields
- Create 6 indexes for query optimization
- Create unique constraint for duplicate prevention
- Create foreign key to `players` table

### Application Startup Registration

**File:** [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:45-56)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("TESTING") != "1":
        # Register action handlers
        action_registry = get_action_handler_registry()
        action_registry.register(TestActionHandler())
        action_registry.register(ProsperityBoostHandler())

        # Register action command subsystem
        subsystem_registry = get_subsystem_registry()
        subsystem_registry.register(ActionCommandSubsystem())

        # Start tick loop
        await start_tick_loop()
    yield
    ...
```

### Test Coverage

**File:** [`backend/tests/test_action_commands.py`](../backend/tests/test_action_commands.py)

**Test Classes:**
1. `TestActionHandlerRegistry` (6 tests) - Registry functionality
2. `TestValidationFramework` (6 tests) - Syntactic and semantic validation
3. `TestActionCommandAPI` (8 tests) - REST endpoint behavior
4. `TestActionCommandSubsystem` (6 tests) - Subsystem processing logic
5. `TestAcceptanceCriteria` (4 tests) - User story test scenarios

**Total Tests:** 30 comprehensive tests covering all acceptance criteria

**Key Test Scenarios:**
- ✅ Commands processed exactly on `valid_from_tick`
- ✅ Past `valid_from_tick` with future expiry still processes
- ✅ Expired commands marked as EXPIRED without execution
- ✅ Duplicate submissions rejected with 409 error
- ✅ Syntactic validation errors returned with structured details
- ✅ Semantic validation checks world state constraints
- ✅ Events emitted during successful processing
- ✅ Exactly-once processing guarantee

## Test Scenarios (from User Story)

### ✅ Scenario 1: Enqueue with valid_from_tick=T → applied exactly on tick T

**Test:** [`test_scenario_enqueue_with_valid_from_tick`](../backend/tests/test_action_commands.py:765-810)

```python
# Enqueue command for tick 10
command = ActionCommand(
    intent="test_action",
    params={"message": "Execute on tick 10"},
    valid_from_tick=10,
    expires_at_tick=15
)

# Process at tick 9 → Still PENDING
subsystem.apply(ctx_tick_9)
assert command.status == ActionCommandStatus.PENDING

# Process at tick 10 → PROCESSED
subsystem.apply(ctx_tick_10)
assert command.status == ActionCommandStatus.PROCESSED
assert command.processed_at_tick == 10
```

### ✅ Scenario 2: Enqueue with past valid_from_tick or future expiry → correct behavior

**Test:** [`test_scenario_past_valid_from_tick`](../backend/tests/test_action_commands.py:812-849)

```python
# Command with past valid_from_tick=1, future expires_at_tick=100
command = ActionCommand(
    valid_from_tick=1,   # Past
    expires_at_tick=100  # Future
)

# Process at tick 50 → PROCESSED (still within window)
subsystem.apply(ctx_tick_50)
assert command.status == ActionCommandStatus.PROCESSED
```

**Test:** [`test_scenario_future_expiry`](../backend/tests/test_action_commands.py:851-886)

```python
# Command with future window: ticks 10-100
command = ActionCommand(
    valid_from_tick=10,
    expires_at_tick=100
)

# Process at tick 50 → PROCESSED
subsystem.apply(ctx_tick_50)
assert command.status == ActionCommandStatus.PROCESSED
```

### ✅ Scenario 3: Duplicate command submission → processed once

**Test:** [`test_scenario_duplicate_command_submission`](../backend/tests/test_action_commands.py:888-924)

```python
# First command
command1 = ActionCommand(
    player_id=1,
    intent="test_action",
    valid_from_tick=10
)
db.add(command1)
db.commit()

# Duplicate (same player, intent, tick)
command2 = ActionCommand(
    player_id=1,
    intent="test_action",
    valid_from_tick=10  # Same!
)

# Raises IntegrityError due to unique constraint
with pytest.raises(Exception):
    db.add(command2)
    db.commit()
```

**API Test:** [`test_enqueue_duplicate_command_rejected`](../backend/tests/test_action_commands.py:283-308)

```python
# First enqueue succeeds
response1 = client.post("/api/actions/enqueue", json=payload)
assert response1.status_code == 200

# Duplicate enqueue fails
response2 = client.post("/api/actions/enqueue", json=payload)
assert response2.status_code == 409
assert "Duplicate command" in response2.json()["detail"]
```

## Files Modified/Created

### Created Files

**Models & Database:**
- ✨ [`backend/src/lycia/models.py`](../backend/src/lycia/models.py) - Added `ActionCommand` and `ActionCommandStatus`
- ✨ [`backend/alembic/versions/73d3f5e150bd_add_action_commands_table_for_s2_03.py`](../backend/alembic/versions/73d3f5e150bd_add_action_commands_table_for_s2_03.py) - Migration

**Action Framework:**
- ✨ [`backend/src/lycia/actions/__init__.py`](../backend/src/lycia/actions/__init__.py)
- ✨ [`backend/src/lycia/actions/protocol.py`](../backend/src/lycia/actions/protocol.py) - ActionHandler protocol, ValidationResult
- ✨ [`backend/src/lycia/actions/registry.py`](../backend/src/lycia/actions/registry.py) - ActionHandlerRegistry
- ✨ [`backend/src/lycia/actions/handlers/__init__.py`](../backend/src/lycia/actions/handlers/__init__.py)
- ✨ [`backend/src/lycia/actions/handlers/test_action.py`](../backend/src/lycia/actions/handlers/test_action.py) - Example handler
- ✨ [`backend/src/lycia/actions/handlers/prosperity_boost.py`](../backend/src/lycia/actions/handlers/prosperity_boost.py) - Example handler

**Subsystems:**
- ✨ [`backend/src/lycia/subsystems/action_command_subsystem.py`](../backend/src/lycia/subsystems/action_command_subsystem.py) - INTENTS phase processor

**Tests:**
- ✨ [`backend/tests/test_action_commands.py`](../backend/tests/test_action_commands.py) - 30 comprehensive tests

**Documentation:**
- ✨ [`docs/S2-03_Action_Command_Queue_Implementation.md`](../docs/S2-03_Action_Command_Queue_Implementation.md) - This file

### Modified Files

**API & Application:**
- 📝 [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:13) - Added ActionCommand imports
- 📝 [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:22-24) - Added action framework imports
- 📝 [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:45-56) - Register handlers and subsystem at startup
- 📝 [`backend/src/lycia/app.py`](../backend/src/lycia/app.py:156-394) - Added `/api/actions/*` endpoints

## How to Use

### 1. For Developers: Creating a New Action Handler

```python
from lycia.actions.protocol import ActionHandler, ValidationResult
from sqlalchemy.orm import Session

class MyActionHandler:
    @property
    def intent(self) -> str:
        return "my_action"

    @property
    def version(self) -> int:
        return 1

    def validate_params(self, params: dict) -> ValidationResult:
        result = ValidationResult.success()

        # Check required fields
        if "field" not in params:
            result.add_error("field", "Field is required", "MISSING_FIELD")
            return result

        # Check types and ranges
        if not isinstance(params["field"], int):
            result.add_error("field", "Must be an integer", "INVALID_TYPE")
        elif params["field"] < 0:
            result.add_error("field", "Must be non-negative", "INVALID_VALUE")

        return result

    def validate_world_state(
        self, params: dict, player_id: int, db: Session, tick: int
    ) -> ValidationResult:
        result = ValidationResult.success()

        # Check business rules
        entity = db.query(MyEntity).filter_by(id=params["field"]).first()
        if not entity:
            result.add_error("field", "Entity not found", "NOT_FOUND")
        elif entity.owner_id != player_id:
            result.add_error("field", "Not owned by player", "NOT_OWNED")

        return result

    def execute(
        self, params: dict, player_id: int, db: Session, tick: int, command_id: int
    ) -> list[dict]:
        # Execute action and return events
        return [
            {
                "type": "my_action.executed",
                "command_id": command_id,
                "tick": tick,
                "data": {
                    "player_id": player_id,
                    "field": params["field"]
                }
            }
        ]
```

**Register at startup:**
```python
# In app.py lifespan
from myapp.handlers import MyActionHandler

action_registry = get_action_handler_registry()
action_registry.register(MyActionHandler())
```

### 2. For API Clients: Submitting Actions

**JavaScript/TypeScript Example:**
```typescript
async function submitAction(intent: string, params: object, fromTick: number, toTick: number) {
  const response = await fetch('/api/actions/enqueue', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      intent,
      version: 1,
      params,
      valid_from_tick: fromTick,
      expires_at_tick: toTick
    })
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('Action submission failed:', error);
    return null;
  }

  const result = await response.json();
  console.log(`Command ${result.command_id} queued for tick ${fromTick}`);
  return result;
}

// Usage
await submitAction('prosperity_boost', { city_id: 1, amount: 10 }, 100, 105);
```

**Python Example:**
```python
import requests

def submit_action(intent, params, from_tick, to_tick):
    response = requests.post('http://localhost:8000/api/actions/enqueue', json={
        'intent': intent,
        'version': 1,
        'params': params,
        'valid_from_tick': from_tick,
        'expires_at_tick': to_tick
    })

    if response.status_code == 200:
        result = response.json()
        print(f"Command {result['command_id']} queued for tick {from_tick}")
        return result
    else:
        print(f"Error: {response.json()}")
        return None

# Usage
submit_action('test_action', {'message': 'Hello!'}, 100, 105)
```

### 3. For Players: Checking Command Status

```bash
# Get all your commands
curl -X GET http://localhost:8000/api/actions/my-commands

# Get only pending commands
curl -X GET http://localhost:8000/api/actions/my-commands?status=pending

# Get last 10 commands
curl -X GET http://localhost:8000/api/actions/my-commands?limit=10
```

## Performance Considerations

### Database Indexes

The implementation includes optimized indexes for common queries:

1. **Queue Processing Index:** `(status, valid_from_tick, expires_at_tick)`
   - Used by: `ActionCommandSubsystem.apply()`
   - Query: `WHERE status='PENDING' AND valid_from_tick <= ?`
   - Impact: O(log n) instead of O(n) for queue queries

2. **Player Commands Index:** `(player_id)`
   - Used by: `/api/actions/my-commands`
   - Query: `WHERE player_id = ?`
   - Impact: Fast lookup of player's command history

3. **Status Index:** `(status)`
   - Used by: Status filtering in API
   - Query: `WHERE status = ?`
   - Impact: Efficient filtering by command state

### Concurrency Safety

**Pessimistic Locking:**
```python
commands = (
    db.query(ActionCommand)
    .filter(...)
    .with_for_update()  # SELECT FOR UPDATE
    .all()
)
```

This prevents race conditions if multiple workers somehow acquire the tick lock simultaneously (shouldn't happen, but defense in depth).

**Unique Constraints:**
```python
UniqueConstraint('player_id', 'intent', 'valid_from_tick')
```

Prevents duplicate command submissions at the database level, even under high concurrency.

### Memory Usage

- Commands are processed in a single query (batch operation)
- Events are collected in memory during tick, then emitted
- For large volumes (>10k commands/tick), consider:
  - Pagination in subsystem processing
  - Chunked event emission
  - Priority queues for critical actions

## Future Enhancements

### 1. Command Cancellation

Allow players to cancel pending commands:

```python
@app.delete("/api/actions/cancel/{command_id}")
def cancel_command(command_id: int, request: Request, db: Session = Depends(get_db)):
    player = get_current_player(request, db)
    command = db.query(ActionCommand).filter_by(id=command_id, player_id=player.id).first()

    if not command:
        raise HTTPException(404, "Command not found")
    if command.status != ActionCommandStatus.PENDING:
        raise HTTPException(400, "Command already processed")

    command.status = ActionCommandStatus.CANCELLED
    db.commit()
    return {"message": "Command cancelled"}
```

### 2. Action Cost/Resources

Extend handlers to check and consume resources:

```python
class CostlyActionHandler:
    def validate_world_state(self, params, player_id, db, tick):
        player = db.query(Player).get(player_id)
        cost = self.calculate_cost(params)

        if player.gold < cost:
            return ValidationResult.failure(
                ValidationError("gold", f"Insufficient gold (need {cost})", "INSUFFICIENT_RESOURCES")
            )

        return ValidationResult.success()

    def execute(self, params, player_id, db, tick, command_id):
        cost = self.calculate_cost(params)
        return [
            {"type": "resource.consumed", "data": {"player_id": player_id, "gold": -cost}},
            {"type": "action.executed", "data": {...}}
        ]
```

### 3. Command Priority

Add priority field for urgent actions:

```python
class ActionCommand(Base):
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = more urgent
```

Process high-priority commands first:

```python
commands = (
    db.query(ActionCommand)
    .filter(...)
    .order_by(ActionCommand.priority.desc(), ActionCommand.submitted_at.asc())
    .all()
)
```

### 4. Batch Actions

Allow submitting multiple related actions atomically:

```python
@app.post("/api/actions/batch")
def enqueue_batch(batch: list[EnqueueActionRequest], ...):
    # All succeed or all fail
    ...
```

### 5. Action Templates

Predefined action combinations:

```python
@app.post("/api/actions/templates/raid_city")
def raid_city(city_id: int, army_id: int):
    # Creates multiple actions: move_army, attack_city, loot
    ...
```

## Conclusion

S2-03 successfully implements a robust action command queue system that meets all acceptance criteria:

✅ REST API for command enqueueing
✅ Exactly-once processing in INTENTS phase
✅ Structured validation errors
✅ Event sourcing architecture
✅ Temporal constraints (valid_from_tick, expires_at_tick)
✅ Duplicate prevention
✅ Comprehensive test coverage (30 tests)
✅ Example handlers (TestAction, ProsperityBoost)
✅ Full documentation

The implementation follows best practices from the existing codebase:
- SQLAlchemy 2.0 patterns
- Pydantic validation
- Protocol-based design
- Subsystem architecture
- Comprehensive testing
- Clear documentation

The system is extensible, performant, and ready for production use. Future sprints can build on this foundation to implement game-specific action handlers (move units, build structures, trade, diplomacy, etc.).
