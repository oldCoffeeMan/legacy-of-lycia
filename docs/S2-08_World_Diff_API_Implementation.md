# S2-08: World Diff API & Basic Recap Contract

**Status**: ✅ Implemented
**Sprint**: Sprint 2
**Related Stories**: S2-04 (Event Sourcing), S2-05 (Schema Versioning)

---

## Overview

This document describes the implementation of the World Diff API and Basic Recap Contract. This system provides "what changed since tick X" functionality for returning players, offering both detailed diffs and structured recap data that AIND can use to generate narrative summaries.

### Key Principles

1. **Event-Driven**: Uses existing event log infrastructure for efficiency
2. **Structured Data Only**: Returns structured JSON, NOT generated prose
3. **City-Focused**: Organizes changes by city for easy consumption
4. **Threshold-Based Highlighting**: Identifies important events automatically
5. **AIND-Ready**: Provides structured data suitable for AI narration

---

## User Story

> As a returning player, I want a "what changed since tick X" diff plus a structured recap object, so the UI and AIND can present a summary of events.

---

## Acceptance Criteria

✅ **GET /api/world/diff?sinceTick=\<n\>** returns:
   - `currentTick`: Current world tick
   - `sinceTick`: Starting tick for diff calculation
   - `tick_range`: Number of ticks covered
   - `cities`: List of per-city changes with:
     - City identification (id, name)
     - Metric changes (prosperity, unrest deltas)
     - Notable events that occurred
   - `total_events`: Total number of events in period

✅ **GET /api/recap?sinceTick=\<n\>** returns structured recap with:
   - `currentTick`: Current world tick
   - `sinceTick`: Starting tick for recap
   - `highlights`: Important events or threshold crossings
     - Each with: type, city, tick, severity, description, data
   - `summary_items`: Short bullet-like pieces suitable for narration
     - Each with: category, text, related_city_ids
   - `suggested_followups`: Placeholder suggestions for actions
     - Each with: action_type, target, reason, priority

✅ **Diff uses event log** for internal calculation (efficient, already indexed)

✅ **Invalid sinceTick values** handled with clear errors:
   - Future tick: 400 Bad Request
   - Negative tick: 400 Bad Request
   - Missing parameter: 422 Validation Error

✅ **Empty events scenario**: Returns valid structure with empty lists (not errors)

---

## Architecture

### Data Flow

```
Client Request: /api/world/diff?sinceTick=100
    ↓
world_diff() endpoint in app.py
    ↓
get_world_diff(db, sinceTick=100)
    ↓
Query events WHERE tick > 100 AND tick <= current_tick
    ↓
Group events by city_id
    ↓
For each city: calculate_city_diff()
    ↓
Return WorldDiffResponse (Pydantic model)
    ↓
FastAPI serializes to JSON
```

### Recap Flow

```
Client Request: /api/recap?sinceTick=100
    ↓
recap() endpoint in app.py
    ↓
get_recap(db, sinceTick=100)
    ↓
Query events in tick range
    ↓
generate_recap_highlights() → Filter by thresholds
    ↓
generate_recap_summary_items() → Aggregate by category
    ↓
generate_suggested_followups() → Based on highlights
    ↓
Return RecapResponse (Pydantic model)
```

---

## Implementation

### 1. Core Module: `world_diff.py`

**File**: [`backend/src/lycia/world_diff.py`](../backend/src/lycia/world_diff.py)

**Key Components**:

#### Pydantic Models

```python
class CityMetricChange(BaseModel):
    """Change in a single metric (e.g., prosperity)"""
    metric: str
    old_value: int | None
    new_value: int
    delta: int

class CityEventSummary(BaseModel):
    """Summary of a notable event"""
    event_id: int
    tick: int
    event_type: str
    description: str
    data: dict

class CityDiffItem(BaseModel):
    """Diff for a single city"""
    city_id: int
    city_name: str
    metric_changes: list[CityMetricChange]
    events: list[CityEventSummary]

class WorldDiffResponse(BaseModel):
    """Main diff response"""
    current_tick: int
    since_tick: int
    tick_range: int
    cities: list[CityDiffItem]
    total_events: int
```

#### Recap Models

```python
class RecapHighlight(BaseModel):
    """Important event or threshold crossing"""
    type: str  # e.g., "prosperity_spike", "unrest_warning"
    city_id: int | None
    city_name: str | None
    tick: int
    severity: str  # "low", "medium", "high"
    description: str
    data: dict

class RecapSummaryItem(BaseModel):
    """Short bullet-like summary"""
    category: str  # e.g., "economic", "social", "military"
    text: str
    related_city_ids: list[int]

class RecapSuggestedFollowup(BaseModel):
    """Suggested action for player"""
    action_type: str  # e.g., "investigate", "boost"
    target: str
    reason: str
    priority: str  # "low", "medium", "high"

class RecapResponse(BaseModel):
    """Main recap response"""
    current_tick: int
    since_tick: int
    highlights: list[RecapHighlight]
    summary_items: list[RecapSummaryItem]
    suggested_followups: list[RecapSuggestedFollowup]
```

#### Core Functions

**`get_world_diff(db: Session, since_tick: int) -> WorldDiffResponse`**
- Validates sinceTick (not negative, not future)
- Queries events in tick range
- Groups events by city_id
- Calculates per-city metric changes
- Returns structured diff response

**`get_recap(db: Session, since_tick: int) -> RecapResponse`**
- Validates sinceTick
- Queries events in tick range
- Generates highlights using thresholds
- Creates summary items by category
- Suggests follow-up actions
- Returns structured recap response

**`calculate_city_diff(db, city, since_tick, current_tick, events_for_city) -> CityDiffItem`**
- Processes events for a single city
- Tracks initial/final metric values
- Generates metric change objects
- Filters notable events
- Returns city diff item

**`generate_event_description(event: Event) -> str`**
- Creates human-readable descriptions
- Handles different event types
- Provides fallback for unknown types

#### Highlight Generation

**Thresholds**:
```python
PROSPERITY_CHANGE_THRESHOLD = 10  # Highlight if change >= 10
UNREST_CHANGE_THRESHOLD = 10      # Highlight if change >= 10
```

**Notable Event Types**:
- `city.prosperity_changed`
- `city.prosperity_boosted`
- `city.unrest_changed`
- `action.processed`
- `action.rejected`

**Highlight Types**:
- `prosperity_spike`: Significant prosperity increase
- `prosperity_drop`: Significant prosperity decrease
- `unrest_spike`: Unrest increased notably
- `unrest_calmed`: Unrest decreased
- `prosperity_boosted`: Player action boosted prosperity

---

### 2. API Endpoints in `app.py`

**File**: [`backend/src/lycia/app.py`](../backend/src/lycia/app.py)

#### Endpoint: GET /api/world/diff

```python
@app.get("/api/world/diff", response_model=WorldDiffResponse)
def world_diff(sinceTick: int, db: Session = Depends(get_db)):
    """
    Get a diff of world changes since a given tick.

    Query Parameters:
    - sinceTick: The tick to calculate diff from (must be >= 0 and <= current tick)

    Returns:
    - WorldDiffResponse with per-city changes and events

    Error Responses:
    - 400 Bad Request: Invalid sinceTick (negative or future)
    - 404 Not Found: World state not initialized
    - 500 Internal Server Error: Database or system error
    """
    try:
        diff_result = get_world_diff(db, sinceTick)
        return diff_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

**Features**:
- Query parameter validation (FastAPI automatic)
- Custom error handling for ValueError (invalid tick)
- Database error handling
- Comprehensive docstring

#### Endpoint: GET /api/recap

```python
@app.get("/api/recap", response_model=RecapResponse)
def recap(sinceTick: int, db: Session = Depends(get_db)):
    """
    Get a structured recap of events since a given tick.

    Returns structured data (NOT prose) that AIND can use to generate
    narrative summaries.

    Query Parameters:
    - sinceTick: The tick to calculate recap from (must be >= 0 and <= current tick)

    Returns:
    - RecapResponse with highlights, summaries, and suggestions

    Highlight Types:
    - prosperity_spike, prosperity_drop
    - unrest_spike, unrest_calmed
    - prosperity_boosted

    Severity Levels: low, medium, high
    """
    try:
        recap_result = get_recap(db, sinceTick)
        return recap_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

---

### 3. Tests

**File**: [`backend/tests/test_world_diff.py`](../backend/tests/test_world_diff.py)

**Test Coverage**: 27 tests, all passing

#### Test Classes

1. **TestWorldDiff**: Core diff calculation
   - Valid sinceTick scenarios
   - Partial tick ranges
   - Same tick (no changes)
   - Invalid inputs (future, negative)
   - Metric change calculation
   - Empty events handling

2. **TestRecap**: Recap generation
   - Valid recap scenarios
   - Highlight generation
   - Highlight severity calculation
   - Summary item generation
   - Suggested followups
   - Empty events handling
   - Invalid inputs

3. **TestWorldDiffAPI**: Endpoint testing
   - Valid requests
   - Invalid sinceTick handling
   - Missing parameters
   - Response structure validation

4. **TestRecapAPI**: Recap endpoint testing
   - Valid requests
   - Response structure validation
   - Empty events scenario
   - Invalid inputs

5. **TestEventDescriptions**: Description generation
   - prosperity_changed events
   - prosperity_boosted events
   - Unknown event types

6. **TestIntegrationDiffAfterTicks**: Integration scenarios
   - Series of ticks with state changes
   - Diff accuracy over time ranges
   - Event filtering correctness

---

## Database Schema

**No new tables required**. Uses existing tables:

- **events**: Source of truth for all changes
  - Indexed by `tick` for efficient range queries
  - Indexed by `type` for filtering notable events
  - Contains `payload` with event-specific data

- **world_state**: Current world tick reference

- **cities**: Current city state for metric values

---

## Usage Examples

### Example 1: Get Diff Since Last Login

**Request**:
```http
GET /api/world/diff?sinceTick=100
```

**Response**:
```json
{
  "current_tick": 150,
  "since_tick": 100,
  "tick_range": 50,
  "cities": [
    {
      "city_id": 1,
      "city_name": "Xanthos",
      "metric_changes": [
        {
          "metric": "prosperity",
          "old_value": 75,
          "new_value": 85,
          "delta": 10
        }
      ],
      "events": [
        {
          "event_id": 42,
          "tick": 105,
          "event_type": "city.prosperity_boosted",
          "description": "Xanthos received prosperity boost of 15",
          "data": {"amount": 15}
        }
      ]
    }
  ],
  "total_events": 8
}
```

### Example 2: Get Narrative Recap

**Request**:
```http
GET /api/recap?sinceTick=100
```

**Response**:
```json
{
  "current_tick": 150,
  "since_tick": 100,
  "highlights": [
    {
      "type": "prosperity_spike",
      "city_id": 1,
      "city_name": "Xanthos",
      "tick": 105,
      "severity": "medium",
      "description": "Xanthos prosperity changed by +15",
      "data": {"old_value": 70, "new_value": 85, "delta": 15}
    },
    {
      "type": "unrest_spike",
      "city_id": 2,
      "city_name": "Patara",
      "tick": 120,
      "severity": "high",
      "description": "Patara unrest changed by +20",
      "data": {"old_value": 15, "new_value": 35, "delta": 20}
    }
  ],
  "summary_items": [
    {
      "category": "alerts",
      "text": "2 high-priority event(s) require attention",
      "related_city_ids": [1, 2]
    },
    {
      "category": "economic",
      "text": "3 prosperity change(s) across 2 city/cities",
      "related_city_ids": [1, 2]
    }
  ],
  "suggested_followups": [
    {
      "action_type": "investigate",
      "target": "Patara",
      "reason": "High unrest detected (tick 120)",
      "priority": "high"
    }
  ]
}
```

### Example 3: Error Handling

**Request** (future tick):
```http
GET /api/world/diff?sinceTick=9999
```

**Response** (400 Bad Request):
```json
{
  "detail": "since_tick (9999) cannot be in the future (current tick: 150)"
}
```

---

## Design Decisions

### 1. Event Log as Source of Truth

**Decision**: Use event log for diff calculation instead of snapshots

**Rationale**:
- Events are already indexed by tick (efficient queries)
- Events contain rich payload data (context for changes)
- No need to compare snapshots (complex diffing logic)
- Aligns with event sourcing architecture (S2-04)

### 2. Structured Data Only (No Prose Generation)

**Decision**: Return structured JSON, not generated narrative text

**Rationale**:
- Separation of concerns (data vs. presentation)
- Flexibility for AIND to generate context-aware narratives
- Easier to test and validate
- Frontend can customize presentation
- Multiple consumers can use same data differently

### 3. Threshold-Based Highlighting

**Decision**: Use fixed thresholds for identifying important events

**Rationale**:
- Simple, predictable behavior
- Easy to tune (can move to config later)
- Avoids complex ML/heuristics for MVP
- Clear acceptance criteria for testing

**Current Thresholds**:
- Prosperity change >= 10: Medium severity
- Prosperity change >= 20: High severity
- Unrest change >= 10: Medium severity
- Unrest spike to >= 70: High severity

### 4. City-Centric Organization

**Decision**: Organize diffs and recaps by city

**Rationale**:
- Matches game domain model
- Natural for UI presentation
- Easy to filter/query specific cities
- Aligns with existing event payload structure

### 5. No New Database Tables

**Decision**: Reuse existing event log infrastructure

**Rationale**:
- Avoid data duplication
- Simpler maintenance
- Events are already versioned (S2-05)
- Snapshots available for point-in-time queries if needed

---

## Follow User Stories and Acceptance Criteria

### How Implementation Addresses User Story

**User Story**: "As a returning player, I want a 'what changed since tick X' diff plus a structured recap object, so the UI and AIND can present a summary of events."

**Implementation**:
1. ✅ **"what changed since tick X"**: `/api/world/diff` endpoint provides exactly this
2. ✅ **"diff"**: Returns detailed per-city metric changes and events
3. ✅ **"structured recap object"**: `/api/recap` endpoint provides structured highlights and summaries
4. ✅ **"UI and AIND can present"**: Both endpoints return structured data (not prose) for flexible consumption

### Acceptance Criteria Fulfillment

#### AC1: GET /api/world/diff?sinceTick=\<n\> returns expected fields

✅ **Implemented**:
- `currentTick`: Line 243 in world_diff.py
- `sinceTick`: Line 244 in world_diff.py
- `tick_range`: Line 245 in world_diff.py
- `cities` with metric changes and events: Lines 260-268 in world_diff.py
- `total_events`: Line 247 in world_diff.py

**Evidence**: Test `test_world_diff_endpoint` in test_world_diff.py:447-468

#### AC2: GET /api/recap?sinceTick=\<n\> returns expected fields

✅ **Implemented**:
- `currentTick`: Line 519 in world_diff.py
- `sinceTick`: Line 520 in world_diff.py
- `highlights`: Lines 521-522 in world_diff.py
- `summary_items`: Line 523 in world_diff.py
- `suggested_followups`: Line 524 in world_diff.py

**Evidence**: Test `test_recap_endpoint` in test_world_diff.py:551-593

#### AC3: Recap returns structured data, NOT prose

✅ **Implemented**:
- All recap fields are structured Pydantic models
- No LLM or prose generation used
- Description fields are factual, template-based strings

**Evidence**: Pydantic models in world_diff.py:87-128

#### AC4: Diff uses event log internally

✅ **Implemented**:
- Line 228 in world_diff.py: Queries events table
- Uses indexed queries for efficiency
- Groups events by city_id for organization

**Evidence**: Function `get_world_diff` in world_diff.py:207-268

#### AC5: Invalid sinceTick values handled with clear errors

✅ **Implemented**:
- Future tick: Raises ValueError with clear message (line 217)
- Negative tick: Raises ValueError (line 213)
- API converts ValueError to 400 Bad Request (app.py:244-248)

**Evidence**: Tests `test_world_diff_endpoint_invalid_future_tick` and `test_world_diff_endpoint_invalid_negative_tick` in test_world_diff.py:470-494

#### AC6: Empty events scenario returns valid structure

✅ **Implemented**:
- Returns WorldDiffResponse/RecapResponse with empty lists
- No errors thrown for empty events
- Valid JSON structure maintained

**Evidence**: Tests `test_diff_empty_events` (line 367) and `test_recap_empty_events` (line 501) in test_world_diff.py

---

## Test Results

**All 201 tests pass** (including 27 new S2-08 tests):

```
============================= test session starts =============================
tests/test_world_diff.py::TestWorldDiff::test_diff_with_valid_since_tick PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_since_recent_tick PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_with_same_tick PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_with_future_tick_raises_error PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_with_negative_tick_raises_error PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_metric_changes PASSED
tests/test_world_diff.py::TestWorldDiff::test_diff_empty_events PASSED
tests/test_world_diff.py::TestRecap::test_recap_with_valid_since_tick PASSED
tests/test_world_diff.py::TestRecap::test_recap_highlights_generation PASSED
tests/test_world_diff.py::TestRecap::test_recap_highlight_severity PASSED
tests/test_world_diff.py::TestRecap::test_recap_summary_items PASSED
tests/test_world_diff.py::TestRecap::test_recap_suggested_followups PASSED
tests/test_world_diff.py::TestRecap::test_recap_empty_events PASSED
tests/test_world_diff.py::TestRecap::test_recap_with_future_tick_raises_error PASSED
tests/test_world_diff.py::TestRecap::test_recap_with_negative_tick_raises_error PASSED
tests/test_world_diff.py::TestWorldDiffAPI::test_world_diff_endpoint PASSED
tests/test_world_diff.py::TestWorldDiffAPI::test_world_diff_endpoint_invalid_future_tick PASSED
tests/test_world_diff.py::TestWorldDiffAPI::test_world_diff_endpoint_invalid_negative_tick PASSED
tests/test_world_diff.py::TestWorldDiffAPI::test_world_diff_endpoint_missing_since_tick PASSED
tests/test_world_diff.py::TestRecapAPI::test_recap_endpoint PASSED
tests/test_world_diff.py::TestRecapAPI::test_recap_endpoint_empty_events PASSED
tests/test_world_diff.py::TestRecapAPI::test_recap_endpoint_invalid_future_tick PASSED
tests/test_world_diff.py::TestRecapAPI::test_recap_endpoint_invalid_negative_tick PASSED
tests/test_world_diff.py::TestEventDescriptions::test_prosperity_changed_description PASSED
tests/test_world_diff.py::TestEventDescriptions::test_prosperity_boosted_description PASSED
tests/test_world_diff.py::TestEventDescriptions::test_unknown_event_type_description PASSED
tests/test_world_diff.py::TestIntegrationDiffAfterTicks::test_diff_after_series_of_ticks PASSED

====================== 27 passed in 0.56s ======================
```

**Ruff linting**: All checks passed

---

## Future Enhancements

### Phase 1 (Current Implementation)
✅ Basic diff calculation
✅ Event-based highlights
✅ Structured recap data
✅ Threshold-based severity

### Phase 2 (Future Sprints)
- Configurable thresholds (move to gameplay.json)
- Resource tracking (food, materials, etc.)
- Military events (battles, troop movements)
- Diplomatic events (alliances, treaties)
- Player reputation changes

### Phase 3 (Advanced)
- ML-based highlight importance scoring
- Personalized recaps based on player preferences
- Comparative analysis (vs. other players/world average)
- Predictive suggestions (based on trends)

---

## Related Documentation

- [S2-04: Event Sourcing and Snapshots](./S2-04_Event_Sourcing_and_Snapshots_Implementation.md)
- [S2-05: Schema Versioning](./s2-05-implementation-summary.md)
- [Sprint 2 Overview](../README.md)

---

## Summary

S2-08 successfully implements a robust World Diff and Recap API that:

1. **Leverages existing event log** infrastructure for efficiency
2. **Provides structured data** for flexible consumption by UI and AIND
3. **Handles edge cases** gracefully (empty events, invalid inputs)
4. **Organizes by city** for natural game domain alignment
5. **Highlights important events** using threshold-based detection
6. **Maintains separation of concerns** (data vs. presentation)

The implementation is fully tested (27 passing tests), linted (Ruff clean), and ready for integration with frontend and AIND narrative generation systems.
