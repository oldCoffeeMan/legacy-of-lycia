"""
World Diff and Recap API Logic (S2-08)

This module provides functionality for generating "what changed since tick X" diffs
and structured recap objects for returning players.

The diff system uses the event log to track changes since a given tick, focusing on:
- High-level city metrics (prosperity, unrest)
- Notable events that occurred
- Threshold crossings and important state changes

The recap system provides structured data (NOT prose) that AIND can use to generate
narration, including highlights, summary items, and suggested follow-up actions.
"""

from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .models import Event, WorldState, City


# ============================================================================
# PYDANTIC MODELS FOR API RESPONSES
# ============================================================================

class CityMetricChange(BaseModel):
    """
    Represents a change in a city metric since the previous tick.
    """
    metric: str = Field(..., description="Metric name (e.g., 'prosperity', 'unrest')")
    old_value: int | None = Field(None, description="Previous value (None if not available)")
    new_value: int = Field(..., description="Current value")
    delta: int = Field(..., description="Change amount (new - old)")


class CityEventSummary(BaseModel):
    """
    Summary of a notable event that occurred in a city.
    """
    event_id: int = Field(..., description="Event ID from event log")
    tick: int = Field(..., description="Tick when event occurred")
    event_type: str = Field(..., description="Event type (e.g., 'city.prosperity_boosted')")
    description: str = Field(..., description="Human-readable event description")
    data: dict = Field(default_factory=dict, description="Additional event-specific data")


class CityDiffItem(BaseModel):
    """
    Diff information for a single city since a given tick.
    """
    city_id: int = Field(..., description="City ID")
    city_name: str = Field(..., description="City name")
    metric_changes: list[CityMetricChange] = Field(
        default_factory=list,
        description="List of metric changes (prosperity, unrest, etc.)"
    )
    events: list[CityEventSummary] = Field(
        default_factory=list,
        description="List of notable events that occurred in this city"
    )


class WorldDiffResponse(BaseModel):
    """
    Response model for GET /api/world/diff endpoint.

    Returns high-level changes since a given tick.
    """
    current_tick: int = Field(..., description="Current world tick")
    since_tick: int = Field(..., description="Tick from which diff was calculated")
    tick_range: int = Field(..., description="Number of ticks covered (current - since)")
    cities: list[CityDiffItem] = Field(
        default_factory=list,
        description="Per-city changes and events"
    )
    total_events: int = Field(..., description="Total number of events in this period")


class RecapHighlight(BaseModel):
    """
    An important event or threshold crossing worthy of highlighting.
    """
    type: str = Field(..., description="Highlight type (e.g., 'prosperity_spike', 'unrest_warning')")
    city_id: int | None = Field(None, description="Related city ID (None for world-level)")
    city_name: str | None = Field(None, description="Related city name")
    tick: int = Field(..., description="Tick when highlight occurred")
    severity: str = Field(..., description="Severity level: 'low', 'medium', 'high'")
    description: str = Field(..., description="Human-readable description")
    data: dict = Field(default_factory=dict, description="Additional structured data")


class RecapSummaryItem(BaseModel):
    """
    A short, bullet-like piece of information suitable for narration.
    """
    category: str = Field(..., description="Category (e.g., 'economic', 'social', 'military')")
    text: str = Field(..., description="Summary text (short, factual)")
    related_city_ids: list[int] = Field(
        default_factory=list,
        description="IDs of cities this summary relates to"
    )


class RecapSuggestedFollowup(BaseModel):
    """
    A suggested action or area of focus for the player.
    Currently a simple stub; can be enhanced later with AI recommendations.
    """
    action_type: str = Field(..., description="Suggested action type (e.g., 'investigate', 'boost')")
    target: str = Field(..., description="What to focus on (e.g., city name, metric)")
    reason: str = Field(..., description="Why this is suggested")
    priority: str = Field(..., description="Priority level: 'low', 'medium', 'high'")


class RecapResponse(BaseModel):
    """
    Response model for GET /api/recap endpoint.

    Returns structured data (NOT prose) that AIND can use to generate narration.
    """
    current_tick: int = Field(..., description="Current world tick")
    since_tick: int = Field(..., description="Tick from which recap was calculated")
    highlights: list[RecapHighlight] = Field(
        default_factory=list,
        description="Important events or threshold crossings"
    )
    summary_items: list[RecapSummaryItem] = Field(
        default_factory=list,
        description="Short bullet-like pieces suitable for narration"
    )
    suggested_followups: list[RecapSuggestedFollowup] = Field(
        default_factory=list,
        description="Placeholder suggestions for actions"
    )


# ============================================================================
# DIFF CALCULATION LOGIC
# ============================================================================

# Define which event types are considered "notable" for diff summaries
NOTABLE_EVENT_TYPES = {
    "city.prosperity_changed",
    "city.prosperity_boosted",
    "city.unrest_changed",
    "action.processed",
    "action.rejected",
}

# Define thresholds for highlighting
PROSPERITY_CHANGE_THRESHOLD = 10  # Highlight if prosperity changes by more than this
UNREST_CHANGE_THRESHOLD = 10      # Highlight if unrest changes by more than this


def generate_event_description(event: Event) -> str:
    """
    Generate a human-readable description for an event.

    Args:
        event: Event object from database

    Returns:
        Human-readable description string
    """
    event_type = event.type
    payload = event.payload

    if event_type == "city.prosperity_changed":
        city_name = payload.get("city_name", "Unknown City")
        old_val = payload.get("old_value", 0)
        new_val = payload.get("new_value", 0)
        delta = new_val - old_val
        direction = "increased" if delta > 0 else "decreased"
        return f"{city_name} prosperity {direction} by {abs(delta)} (from {old_val} to {new_val})"

    elif event_type == "city.prosperity_boosted":
        city_name = payload.get("city_name", "Unknown City")
        amount = payload.get("amount", 0)
        return f"{city_name} received prosperity boost of {amount}"

    elif event_type == "city.unrest_changed":
        city_name = payload.get("city_name", "Unknown City")
        old_val = payload.get("old_value", 0)
        new_val = payload.get("new_value", 0)
        delta = new_val - old_val
        direction = "increased" if delta > 0 else "decreased"
        return f"{city_name} unrest {direction} by {abs(delta)} (from {old_val} to {new_val})"

    elif event_type == "action.processed":
        intent = payload.get("intent", "unknown")
        return f"Action '{intent}' was successfully processed"

    elif event_type == "action.rejected":
        intent = payload.get("intent", "unknown")
        reason = payload.get("reason", "unknown reason")
        return f"Action '{intent}' was rejected: {reason}"

    else:
        # Generic description for unknown event types
        return f"Event of type '{event_type}' occurred"


def calculate_city_diff(
    db: Session,
    city: City,
    since_tick: int,
    current_tick: int,
    events_for_city: list[Event]
) -> CityDiffItem:
    """
    Calculate diff for a single city.

    Args:
        db: Database session
        city: City object
        since_tick: Starting tick for diff
        current_tick: Current tick
        events_for_city: List of events for this city in the tick range

    Returns:
        CityDiffItem with metric changes and notable events
    """
    metric_changes: list[CityMetricChange] = []
    event_summaries: list[CityEventSummary] = []

    # Track initial and final values for metrics
    prosperity_changes: dict[str, Any] = {"initial": None, "final": city.prosperity}
    unrest_changes: dict[str, Any] = {"initial": None, "final": city.unrest}

    # Process events to extract metric changes
    for event in events_for_city:
        event_type = event.type
        payload = event.payload

        # Track metric changes
        if event_type == "city.prosperity_changed" or event_type == "city.prosperity_boosted":
            if prosperity_changes["initial"] is None:
                prosperity_changes["initial"] = payload.get("old_value", city.prosperity)

        if event_type == "city.unrest_changed":
            if unrest_changes["initial"] is None:
                unrest_changes["initial"] = payload.get("old_value", city.unrest)

        # Add notable events to summary
        if event_type in NOTABLE_EVENT_TYPES:
            event_summaries.append(CityEventSummary(
                event_id=event.id,
                tick=event.tick,
                event_type=event_type,
                description=generate_event_description(event),
                data=payload
            ))

    # Create metric change objects
    if prosperity_changes["initial"] is not None:
        delta = prosperity_changes["final"] - prosperity_changes["initial"]
        if delta != 0:  # Only include if there was actual change
            metric_changes.append(CityMetricChange(
                metric="prosperity",
                old_value=prosperity_changes["initial"],
                new_value=prosperity_changes["final"],
                delta=delta
            ))

    if unrest_changes["initial"] is not None:
        delta = unrest_changes["final"] - unrest_changes["initial"]
        if delta != 0:  # Only include if there was actual change
            metric_changes.append(CityMetricChange(
                metric="unrest",
                old_value=unrest_changes["initial"],
                new_value=unrest_changes["final"],
                delta=delta
            ))

    return CityDiffItem(
        city_id=city.id,
        city_name=city.name,
        metric_changes=metric_changes,
        events=event_summaries
    )


def get_world_diff(db: Session, since_tick: int) -> WorldDiffResponse:
    """
    Generate world diff since a given tick.

    Args:
        db: Database session
        since_tick: Tick to calculate diff from

    Returns:
        WorldDiffResponse with all changes since since_tick

    Raises:
        ValueError: If since_tick is invalid (future or negative)
    """
    # Get current world state
    world_state = db.get(WorldState, 1)
    if world_state is None:
        raise ValueError("World state not found")

    current_tick = world_state.tick

    # Validate since_tick
    if since_tick < 0:
        raise ValueError("since_tick cannot be negative")

    if since_tick > current_tick:
        raise ValueError(f"since_tick ({since_tick}) cannot be in the future (current tick: {current_tick})")

    # If since_tick equals current_tick, return empty diff
    if since_tick == current_tick:
        return WorldDiffResponse(
            current_tick=current_tick,
            since_tick=since_tick,
            tick_range=0,
            cities=[],
            total_events=0
        )

    # Query events in the tick range
    events = db.query(Event).filter(
        Event.tick > since_tick,
        Event.tick <= current_tick
    ).order_by(Event.tick, Event.created_at).all()

    # Group events by city_id
    events_by_city: dict[int, list[Event]] = {}
    world_events: list[Event] = []  # Events not tied to a specific city

    for event in events:
        city_id = event.payload.get("city_id")
        if city_id:
            if city_id not in events_by_city:
                events_by_city[city_id] = []
            events_by_city[city_id].append(event)
        else:
            world_events.append(event)

    # Get all cities
    cities = db.query(City).order_by(City.name).all()

    # Calculate diff for each city
    city_diffs: list[CityDiffItem] = []
    for city in cities:
        city_events = events_by_city.get(city.id, [])
        if city_events or True:  # Include all cities, even without events
            city_diff = calculate_city_diff(
                db=db,
                city=city,
                since_tick=since_tick,
                current_tick=current_tick,
                events_for_city=city_events
            )
            # Only include cities with actual changes or events
            if city_diff.metric_changes or city_diff.events:
                city_diffs.append(city_diff)

    return WorldDiffResponse(
        current_tick=current_tick,
        since_tick=since_tick,
        tick_range=current_tick - since_tick,
        cities=city_diffs,
        total_events=len(events)
    )


# ============================================================================
# RECAP GENERATION LOGIC
# ============================================================================

def generate_recap_highlights(
    db: Session,
    since_tick: int,
    current_tick: int,
    events: list[Event]
) -> list[RecapHighlight]:
    """
    Generate highlights from events.

    Highlights are important events or threshold crossings worthy of attention.

    Args:
        db: Database session
        since_tick: Starting tick
        current_tick: Current tick
        events: List of events to analyze

    Returns:
        List of RecapHighlight objects
    """
    highlights: list[RecapHighlight] = []

    # Get city name lookup
    cities = db.query(City).all()
    city_lookup = {c.id: c.name for c in cities}

    for event in events:
        event_type = event.type
        payload = event.payload
        city_id = payload.get("city_id")
        city_name = city_lookup.get(city_id) if city_id else None

        # Prosperity changes above threshold
        if event_type == "city.prosperity_changed":
            old_value = payload.get("old_value", 0)
            new_value = payload.get("new_value", 0)
            delta = new_value - old_value

            if abs(delta) >= PROSPERITY_CHANGE_THRESHOLD:
                severity = "high" if abs(delta) >= 20 else "medium"
                highlight_type = "prosperity_spike" if delta > 0 else "prosperity_drop"

                highlights.append(RecapHighlight(
                    type=highlight_type,
                    city_id=city_id,
                    city_name=city_name,
                    tick=event.tick,
                    severity=severity,
                    description=f"{city_name} prosperity changed by {delta:+d}",
                    data={"old_value": old_value, "new_value": new_value, "delta": delta}
                ))

        # Unrest changes above threshold
        elif event_type == "city.unrest_changed":
            old_value = payload.get("old_value", 0)
            new_value = payload.get("new_value", 0)
            delta = new_value - old_value

            if abs(delta) >= UNREST_CHANGE_THRESHOLD:
                severity = "high" if delta > 0 and new_value >= 70 else "medium"
                highlight_type = "unrest_spike" if delta > 0 else "unrest_calmed"

                highlights.append(RecapHighlight(
                    type=highlight_type,
                    city_id=city_id,
                    city_name=city_name,
                    tick=event.tick,
                    severity=severity,
                    description=f"{city_name} unrest changed by {delta:+d}",
                    data={"old_value": old_value, "new_value": new_value, "delta": delta}
                ))

        # Prosperity boosts are always notable
        elif event_type == "city.prosperity_boosted":
            amount = payload.get("amount", 0)
            highlights.append(RecapHighlight(
                type="prosperity_boosted",
                city_id=city_id,
                city_name=city_name,
                tick=event.tick,
                severity="medium",
                description=f"{city_name} received a prosperity boost of {amount}",
                data={"amount": amount}
            ))

    # Sort by severity and tick
    severity_order = {"high": 0, "medium": 1, "low": 2}
    highlights.sort(key=lambda h: (severity_order[h.severity], h.tick))

    return highlights


def generate_recap_summary_items(
    db: Session,
    highlights: list[RecapHighlight],
    events: list[Event]
) -> list[RecapSummaryItem]:
    """
    Generate summary items from highlights and events.

    Summary items are short, bullet-like pieces suitable for narration.

    Args:
        db: Database session
        highlights: List of highlights
        events: List of all events

    Returns:
        List of RecapSummaryItem objects
    """
    summary_items: list[RecapSummaryItem] = []

    # Count events by category
    prosperity_events = sum(1 for e in events if "prosperity" in e.type)
    unrest_events = sum(1 for e in events if "unrest" in e.type)
    action_events = sum(1 for e in events if e.type.startswith("action."))

    # Generate summaries based on event counts
    if prosperity_events > 0:
        cities_affected = list({
            e.payload.get("city_id")
            for e in events
            if "prosperity" in e.type and e.payload.get("city_id")
        })
        summary_items.append(RecapSummaryItem(
            category="economic",
            text=f"{prosperity_events} prosperity change(s) across {len(cities_affected)} city/cities",
            related_city_ids=cities_affected
        ))

    if unrest_events > 0:
        cities_affected = list({
            e.payload.get("city_id")
            for e in events
            if "unrest" in e.type and e.payload.get("city_id")
        })
        summary_items.append(RecapSummaryItem(
            category="social",
            text=f"{unrest_events} unrest change(s) across {len(cities_affected)} city/cities",
            related_city_ids=cities_affected
        ))

    if action_events > 0:
        summary_items.append(RecapSummaryItem(
            category="player_actions",
            text=f"{action_events} player action(s) processed",
            related_city_ids=[]
        ))

    # Add highlight-based summaries
    high_severity_highlights = [h for h in highlights if h.severity == "high"]
    if high_severity_highlights:
        summary_items.insert(0, RecapSummaryItem(
            category="alerts",
            text=f"{len(high_severity_highlights)} high-priority event(s) require attention",
            related_city_ids=[h.city_id for h in high_severity_highlights if h.city_id]
        ))

    return summary_items


def generate_suggested_followups(
    db: Session,
    highlights: list[RecapHighlight]
) -> list[RecapSuggestedFollowup]:
    """
    Generate suggested follow-up actions based on highlights.

    Currently returns simple stubs; can be enhanced with AI recommendations later.

    Args:
        db: Database session
        highlights: List of highlights

    Returns:
        List of RecapSuggestedFollowup objects
    """
    followups: list[RecapSuggestedFollowup] = []

    # Suggest investigating high unrest
    high_unrest_highlights = [
        h for h in highlights
        if h.type == "unrest_spike" and h.severity == "high"
    ]
    for highlight in high_unrest_highlights[:3]:  # Max 3 suggestions
        followups.append(RecapSuggestedFollowup(
            action_type="investigate",
            target=highlight.city_name or "Unknown City",
            reason=f"High unrest detected (tick {highlight.tick})",
            priority="high"
        ))

    # Suggest boosting cities with prosperity drops
    prosperity_drops = [
        h for h in highlights
        if h.type == "prosperity_drop" and h.severity in ("high", "medium")
    ]
    for highlight in prosperity_drops[:2]:  # Max 2 suggestions
        followups.append(RecapSuggestedFollowup(
            action_type="boost",
            target=highlight.city_name or "Unknown City",
            reason=f"Prosperity declined (tick {highlight.tick})",
            priority="medium"
        ))

    return followups


def get_recap(db: Session, since_tick: int) -> RecapResponse:
    """
    Generate structured recap since a given tick.

    Args:
        db: Database session
        since_tick: Tick to calculate recap from

    Returns:
        RecapResponse with highlights, summaries, and suggestions

    Raises:
        ValueError: If since_tick is invalid (future or negative)
    """
    # Get current world state
    world_state = db.get(WorldState, 1)
    if world_state is None:
        raise ValueError("World state not found")

    current_tick = world_state.tick

    # Validate since_tick
    if since_tick < 0:
        raise ValueError("since_tick cannot be negative")

    if since_tick > current_tick:
        raise ValueError(f"since_tick ({since_tick}) cannot be in the future (current tick: {current_tick})")

    # If since_tick equals current_tick, return empty recap
    if since_tick == current_tick:
        return RecapResponse(
            current_tick=current_tick,
            since_tick=since_tick,
            highlights=[],
            summary_items=[],
            suggested_followups=[]
        )

    # Query events in the tick range
    events = db.query(Event).filter(
        Event.tick > since_tick,
        Event.tick <= current_tick
    ).order_by(Event.tick, Event.created_at).all()

    # Generate recap components
    highlights = generate_recap_highlights(db, since_tick, current_tick, events)
    summary_items = generate_recap_summary_items(db, highlights, events)
    suggested_followups = generate_suggested_followups(db, highlights)

    return RecapResponse(
        current_tick=current_tick,
        since_tick=since_tick,
        highlights=highlights,
        summary_items=summary_items,
        suggested_followups=suggested_followups
    )
