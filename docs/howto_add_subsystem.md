# How to Add a Subsystem

This guide shows you how to implement and register a new subsystem in the Legacy of Lycia game engine.

## What is a Subsystem?

A subsystem is a modular component that runs during each game tick to handle a specific aspect of game simulation (e.g., economy, politics, weather). Subsystems execute in phases and can depend on each other.

## Implementation Steps

### 1. Implement the Subsystem Protocol

Create a class that implements the `Subsystem` protocol defined in [backend/src/lycia/subsystems/protocol.py](../backend/src/lycia/subsystems/protocol.py).

**Required Properties:**
- `name` (str): Unique identifier for your subsystem
- `phase` (SubsystemPhase): Which phase this subsystem runs in
- `dependencies` (list[str]): Names of subsystems that must run before this one

**Required Method:**
- `apply(ctx: TickContext)`: Execute subsystem logic for the current tick

### 2. Choose a Phase

Phases execute in this fixed order (see [backend/src/lycia/subsystems/phase.py](../backend/src/lycia/subsystems/phase.py#L39-L45)):

1. **INTENTS** - Player/NPC intent collection and validation
2. **ECONOMY** - Economic simulation (production, trade, consumption)
3. **POLITICS** - Political events, diplomacy, alliances
4. **WEATHER** - Environmental effects and disasters
5. **CLEANUP** - Post-processing, notifications, cleanup

### 3. Example Implementation

Here's a complete example based on [backend/src/lycia/subsystems/action_command_subsystem.py](../backend/src/lycia/subsystems/action_command_subsystem.py):

```python
from .protocol import Subsystem, TickContext
from .phase import SubsystemPhase
from lycia.actions.registry import ActionHandlerRegistry
from lycia.models import ActionCommand


class ActionCommandSubsystem:
    """
    Processes queued action commands from players/NPCs.

    Runs in INTENTS phase to validate and execute player actions
    before the rest of the simulation runs.
    """

    def __init__(self, action_registry: ActionHandlerRegistry):
        """
        Initialize with action handler registry.

        Args:
            action_registry: Registry of available action handlers
        """
        self._action_registry = action_registry

    @property
    def name(self) -> str:
        """Unique subsystem identifier."""
        return "action_commands"

    @property
    def phase(self) -> SubsystemPhase:
        """Execute in INTENTS phase (first)."""
        return SubsystemPhase.INTENTS

    @property
    def dependencies(self) -> list[str]:
        """No dependencies - runs first in INTENTS phase."""
        return []

    def apply(self, ctx: TickContext) -> None:
        """
        Process all pending action commands for this tick.

        Args:
            ctx: Tick context with db, rng, tick number, etc.
        """
        # Get config for max commands per tick
        config = ctx.get_config()
        max_per_tick = config.get("action_commands", {}).get("max_per_tick", 100)

        # Query pending commands
        pending_commands = (
            ctx.query(ActionCommand)
            .filter(ActionCommand.status == "pending")
            .filter(ActionCommand.scheduled_tick <= ctx.tick)
            .order_by(ActionCommand.scheduled_tick, ActionCommand.id)
            .limit(max_per_tick)
            .all()
        )

        # Process each command
        for command in pending_commands:
            try:
                # Get handler for this intent
                handler = self._action_registry.get(
                    command.intent,
                    command.version
                )

                if not handler:
                    command.status = "failed"
                    ctx.emit({
                        "type": "action_failed",
                        "tick": ctx.tick,
                        "command_id": command.id,
                        "reason": f"Unknown intent: {command.intent}"
                    })
                    continue

                # Execute handler and emit events
                events = handler.execute(
                    params=command.params,
                    player_id=command.player_id,
                    db=ctx.db,
                    tick=ctx.tick,
                    command_id=command.id
                )

                for event in events:
                    ctx.emit(event)

                command.status = "completed"

            except Exception as e:
                command.status = "failed"
                ctx.emit({
                    "type": "action_failed",
                    "tick": ctx.tick,
                    "command_id": command.id,
                    "reason": str(e)
                })

        # Commit changes
        ctx.db.commit()
```

### 4. Using the TickContext

The `ctx: TickContext` parameter gives you access to:

**Properties:**
- `ctx.tick` (int): Current tick number
- `ctx.db` (Session): Database session for queries and commits
- `ctx.rng` (Random): Subsystem-specific RNG (deterministic, seeded by subsystem name)

**Methods:**
- `ctx.query(Model)`: Create SQLAlchemy query (shorthand for `ctx.db.query(Model)`)
- `ctx.emit(event: dict)`: Emit an event to the event log
- `ctx.get_config()`: Get gameplay configuration dict

**RNG Helpers:**
- `ctx.uniform(a, b)`: Random float in [a, b)
- `ctx.randint(a, b)`: Random int in [a, b]
- `ctx.choice(seq)`: Random element from sequence
- `ctx.random()`: Random float in [0.0, 1.0)

### 5. Register Your Subsystem

In [backend/src/lycia/app.py](../backend/src/lycia/app.py), add your subsystem to the registry:

```python
from lycia.subsystems.registry import SubsystemRegistry
from lycia.subsystems.your_subsystem import YourSubsystem

# Create global registry
subsystem_registry = SubsystemRegistry()

# Register built-in subsystems
subsystem_registry.register(ActionCommandSubsystem(action_handler_registry))
subsystem_registry.register(YourSubsystem())  # Add your subsystem here

# Registry automatically handles:
# - Phase ordering (INTENTS -> ECONOMY -> POLITICS -> WEATHER -> CLEANUP)
# - Dependency resolution within phases
# - Cycle detection
```

### 6. Dependency Rules

When declaring dependencies:

- **Same phase**: You can depend on subsystems in the same phase (they'll run before you)
- **Earlier phases**: You can depend on subsystems in earlier phases (always safe)
- **Later phases**: You CANNOT depend on subsystems in later phases (raises `InvalidDependencyError`)
- **Unknown subsystems**: Referencing non-existent subsystems raises `SubsystemNotFoundError`
- **Cycles**: Circular dependencies raise `DependencyCycleError`

Example with dependencies:

```python
@property
def dependencies(self) -> list[str]:
    """This subsystem needs action_commands to run first."""
    return ["action_commands"]
```

## Complete Examples

See these files for working examples:

- **Action Commands**: [backend/src/lycia/subsystems/action_command_subsystem.py](../backend/src/lycia/subsystems/action_command_subsystem.py) - Processes player actions
- **Event Persistence**: [backend/src/lycia/subsystems/event_persistence_subsystem.py](../backend/src/lycia/subsystems/event_persistence_subsystem.py) - Saves events to database
- **Snapshot**: [backend/src/lycia/subsystems/snapshot_subsystem.py](../backend/src/lycia/subsystems/snapshot_subsystem.py) - Creates periodic state snapshots

## Testing Your Subsystem

See [backend/tests/test_subsystem_pipeline.py](../backend/tests/test_subsystem_pipeline.py) for examples of testing subsystem execution order and dependency resolution.

Key test patterns:

```python
def test_my_subsystem():
    # Create registry
    registry = SubsystemRegistry()

    # Register your subsystem
    subsystem = MySubsystem()
    registry.register(subsystem)

    # Verify execution order
    order = registry.get_execution_order()
    assert subsystem in order

    # Create tick context
    ctx = create_tick_context(tick=1, db=db_session)

    # Execute subsystem
    subsystem.apply(ctx)

    # Verify effects (check db changes, emitted events, etc.)
```
