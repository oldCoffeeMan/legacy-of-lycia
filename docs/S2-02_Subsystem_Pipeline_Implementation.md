# S2-02: Subsystem Pipeline & Registry Implementation

**Sprint:** Sprint 2
**Status:** ✅ Completed
**Date:** 2025-11-13

## Overview

This document details the implementation of the Subsystem Pipeline & Registry (S2-02), an extensibility framework that allows developers to add game mechanics without modifying the core tick loop.

## User Story

> As a developer, I need to plug new game mechanics (economy, politics, weather) without editing the tick loop, so the system evolves safely.

## Acceptance Criteria

✅ **AC1:** Registry supports subsystems with: name, phase (INTENTS, ECONOMY, POLITICS, WEATHER, CLEANUP), and after dependencies
✅ **AC2:** Tick runner topologically sorts subsystems once at startup; stable order across runs
✅ **AC3:** Subsystem API provides apply(ctx) with read/query helpers and emit(event) for side-effects
✅ **AC4:** Adding/removing a subsystem requires registration only; tick runner code unchanged

## Architecture

### Core Components

1. **SubsystemPhase** - Fixed execution phases (enum)
2. **Subsystem** - Protocol defining subsystem interface
3. **TickContext** - Context provided to subsystems during execution
4. **SubsystemRegistry** - Manages registration and execution order
5. **TickExecutor** - Integrated with subsystem pipeline

### Execution Flow

```
Tick Start
    │
    ▼
Get Subsystems (sorted once at startup)
    │
    ├─► INTENTS Phase
    │   └─► Execute subsystems in dependency order
    │
    ├─► ECONOMY Phase
    │   └─► Execute subsystems in dependency order
    │
    ├─► POLITICS Phase
    │   └─► Execute subsystems in dependency order
    │
    ├─► WEATHER Phase
    │   └─► Execute subsystems in dependency order
    │
    └─► CLEANUP Phase
        └─► Execute subsystems in dependency order
```

## Implementation Details

### 1. Phases (Fixed Execution Order)

```python
class SubsystemPhase(str, Enum):
    INTENTS = "intents"    # Player/NPC intent collection
    ECONOMY = "economy"    # Production, trade, consumption
    POLITICS = "politics"  # Diplomacy, alliances
    WEATHER = "weather"    # Environmental effects
    CLEANUP = "cleanup"    # Post-processing, notifications
```

### 2. Subsystem Protocol

```python
class Subsystem(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def phase(self) -> SubsystemPhase: ...

    @property
    def dependencies(self) -> list[str]: ...

    def apply(self, ctx: TickContext) -> None: ...
```

### 3. TickContext API

```python
class TickContext:
    @property
    def tick(self) -> int: ...           # Current tick number

    @property
    def db(self) -> Session: ...          # Database session

    @property
    def rng(self) -> Random: ...          # Deterministic RNG

    def query(self, model, **filters): ...  # Query helper

    def emit(self, event_type, data): ...   # Event emission

    def get_config(self, key, default): ... # Config access
```

### 4. Topological Sorting

The registry uses **Kahn's algorithm** to sort subsystems:

1. Group subsystems by phase
2. Within each phase, build dependency graph
3. Topologically sort using in-degree tracking
4. Detect cycles and validate cross-phase dependencies
5. Cache result for performance

### 5. Example Subsystem

```python
class EconomyProductionSubsystem:
    @property
    def name(self) -> str:
        return "economy_production"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.ECONOMY

    @property
    def dependencies(self) -> list[str]:
        return []  # No dependencies

    def apply(self, ctx: TickContext) -> None:
        # Use deterministic RNG
        production = ctx.rng.randint(100, 200)

        # Query database
        cities = ctx.query(City)

        # Emit event
        ctx.emit("economy.production", {
            "amount": production
        })
```

## Testing

### Test Coverage: 21 tests across 5 categories

#### 1. Subsystem Registration (5 tests)
- ✅ Register single subsystem
- ✅ Prevent duplicate registration
- ✅ Unregister subsystem
- ✅ Handle unregister of nonexistent
- ✅ Clear registry

#### 2. Execution Order (4 tests)
- ✅ Phase ordering
- ✅ Dependency ordering within phase
- ✅ Mixed phase and dependency ordering
- ✅ Stable execution order

#### 3. Dependency Validation (3 tests)
- ✅ Missing dependency detection
- ✅ Dependency cycle detection
- ✅ Invalid cross-phase dependency detection

#### 4. Dynamic Management (3 tests)
- ✅ Add subsystem invalidates cache
- ✅ Remove subsystem doesn't break tick
- ✅ Removing dependency breaks dependent

#### 5. Context & Execution (6 tests)
- ✅ Context provides tick number
- ✅ Deterministic RNG per subsystem
- ✅ Event emission
- ✅ Config access
- ✅ Subsystem execution
- ✅ Execution order verification

### Running Tests

```bash
cd backend
TESTING=1 PYTHONPATH=src pytest tests/test_subsystem_pipeline.py -v
```

All 21 tests pass ✅
**Total test suite: 74 tests (53 existing + 21 new)**

## Design Decisions

### 1. Protocol vs Abstract Base Class

**Decision:** Use Protocol (structural typing)
**Rationale:**
- More flexible - no inheritance required
- Duck typing - works with any compatible class
- Better for testing and mocking
- Pythonic approach

### 2. Fixed Phases vs Dynamic Phases

**Decision:** Fixed phases defined as enum
**Rationale:**
- Predictable execution order
- Easier to reason about
- Prevents phase proliferation
- Clear separation of concerns

### 3. Topological Sort vs Manual Ordering

**Decision:** Automatic topological sorting
**Rationale:**
- Eliminates manual ordering errors
- Scales to many subsystems
- Detects dependency issues at startup
- Self-documenting through dependencies

### 4. Cached vs On-Demand Sorting

**Decision:** Cache execution order after first sort
**Rationale:**
- Performance - sort once, use many times
- Deterministic - same order every tick
- Invalidate on registry changes
- Startup validation of all dependencies

### 5. Event Emission vs Direct State Modification

**Decision:** Emit events for side-effects
**Rationale:**
- Decouples subsystems
- Enables async processing
- Audit trail of actions
- Future AI narrator integration

## Adherence to Acceptance Criteria

### AC1: Registry with name, phase, and dependencies ✅

Implemented via `Subsystem` protocol:
```python
@property
def name(self) -> str: ...
@property
def phase(self) -> SubsystemPhase: ...  # Fixed phases
@property
def dependencies(self) -> list[str]: ...  # After dependencies
```

Tested in: `test_register_single_subsystem`, `test_phase_ordering`

### AC2: Topological sort with stable order ✅

Implemented in `SubsystemRegistry._topological_sort()`:
- Kahn's algorithm for dependency resolution
- Grouped by phase with phase-order enforcement
- Cached after first sort
- Deterministic order

Tested in: `test_execution_order_is_stable`, `test_dependency_ordering_within_phase`

### AC3: Subsystem API with apply(ctx) ✅

Implemented via `TickContext`:
```python
def apply(self, ctx: TickContext) -> None:
    cities = ctx.query(City, prosperity__gt=50)  # Read/query
    value = ctx.rng.randint(1, 100)              # Deterministic RNG
    ctx.emit("event.type", {"data": value})       # Emit events
```

Tested in: `test_context_provides_deterministic_rng`, `test_context_emit_event`

### AC4: Add/remove without tick loop changes ✅

Implementation:
- Register: `registry.register(MySubsystem())`
- Unregister: `registry.unregister("subsystem_name")`
- Tick loop unchanged - uses `registry.get_execution_order()`

Tested in: `test_remove_subsystem_doesnt_break_tick`, `test_add_subsystem_invalidates_cache`

## Integration with Tick Executor

The tick executor was updated to support subsystems:

```python
class TickExecutor:
    def __init__(self, registry: Optional[SubsystemRegistry] = None):
        self.registry = registry or SubsystemRegistry()

    def _process_tick_logic(self, db, tick, seed):
        # Get sorted subsystems
        subsystems = self.registry.get_execution_order()

        # Execute each with its own context
        for subsystem in subsystems:
            ctx = TickContextImpl(
                tick=tick,
                db=db,
                rng=base_rng,
                subsystem_name=subsystem.name
            )
            subsystem.apply(ctx)
```

## Files Modified/Created

### New Files
- `backend/src/lycia/subsystems/__init__.py` - Package initialization
- `backend/src/lycia/subsystems/phase.py` - Phase definitions
- `backend/src/lycia/subsystems/protocol.py` - Subsystem and Context protocols
- `backend/src/lycia/subsystems/context.py` - TickContext implementation
- `backend/src/lycia/subsystems/registry.py` - Registry with topological sort
- `backend/src/lycia/subsystems/examples.py` - Example subsystems
- `backend/tests/test_subsystem_pipeline.py` - Comprehensive test suite
- `docs/S2-02_Subsystem_Pipeline_Implementation.md` - This document

### Modified Files
- `backend/src/lycia/tick_executor.py` - Integrated subsystem execution

## Usage Examples

### Registering a Subsystem

```python
from lycia.subsystems import get_subsystem_registry
from lycia.subsystems.examples import EconomyProductionSubsystem

# Get global registry
registry = get_subsystem_registry()

# Register subsystem
registry.register(EconomyProductionSubsystem())
```

### Creating a New Subsystem

```python
from lycia.subsystems import Subsystem, SubsystemPhase, TickContext

class MyCustomSubsystem:
    @property
    def name(self) -> str:
        return "my_custom_subsystem"

    @property
    def phase(self) -> SubsystemPhase:
        return SubsystemPhase.ECONOMY

    @property
    def dependencies(self) -> list[str]:
        return ["economy_production"]  # Runs after production

    def apply(self, ctx: TickContext) -> None:
        # Your game logic here
        cities = ctx.query(City)
        for city in cities:
            # Update city based on deterministic RNG
            growth = ctx.rng.random() * 0.1
            city.prosperity += int(city.prosperity * growth)

        ctx.db.commit()
        ctx.emit("custom.processed", {"cities": len(cities)})
```

## Future Enhancements

1. **Config System**
   - Load subsystem config from YAML/JSON
   - Hot-reload configuration
   - Per-subsystem config validation

2. **Event Processing**
   - Event bus for cross-subsystem communication
   - Async event handlers
   - Event persistence for AI narrator

3. **Performance Monitoring**
   - Per-subsystem execution time tracking
   - Performance budgets and warnings
   - Profiling integration

4. **Conditional Execution**
   - Enable/disable subsystems based on game state
   - Feature flags for experimental subsystems
   - A/B testing framework

5. **Parallel Execution**
   - Execute independent subsystems in parallel
   - Thread pool for CPU-bound subsystems
   - Lock-free state updates

## Lessons Learned

1. **Protocol over ABC:** Structural typing provides more flexibility than inheritance

2. **Early Validation:** Validating dependencies at startup prevents runtime failures

3. **Immutable Execution Order:** Caching sorted order improves performance and determinism

4. **Subsystem Isolation:** Each subsystem gets its own RNG context for determinism

## Conclusion

The Subsystem Pipeline & Registry (S2-02) has been successfully implemented with all acceptance criteria met. The system provides:

- ✅ Clean plugin architecture for game mechanics
- ✅ Automatic dependency resolution
- ✅ Strong validation and error detection
- ✅ Deterministic execution order
- ✅ Comprehensive test coverage (21 tests, 100% pass)
- ✅ Zero changes required to tick loop when adding subsystems

The implementation establishes a robust extensibility framework that will support all future game mechanics in a safe, maintainable way.

---

**Implemented by:** Claude Code
**Reviewed by:** [Pending]
**Date Completed:** 2025-11-13
