# Simulation Architecture Overview (Lean & Simple)

## 1. Purpose
This document explains the core simulation architecture of Legacy of Lycia in a clear, high-level, developer-friendly way:
- Tick loop and phase system
- Subsystems and shared world state
- How complex behavior emerges from independent modules
- How AIND injects dynamic events and actions
- How all of this fits the prototype and long-term design

---

## 2. Core Concept: A Clockwork World
The entire simulation functions like a **clock**:
- Every few seconds, the simulation advances by one **tick**.
- Each subsystem reads shared world state, makes decisions, and emits events.
- CLEANUP phase persists these events, updates snapshots, and finalizes the tick.

Subsystems **do not call each other directly** — they interact only through:
- Shared world state (cities, regions, routes, resources, etc.)
- Events emitted during the tick

This keeps subsystems simple but creates rich, emergent behavior.

---

## 3. Tick Loop (The Heartbeat)
Each tick:
1. Increment `world.tick`.
2. Run subsystems in **Phase Order**:
   ```
   INTENTS → ENVIRONMENT → ECONOMY → POLITICS → SOCIAL → CLEANUP
   ```
3. Each subsystem receives a TickContext with:
   - tick number
   - deterministic RNG
   - DB access
   - query helpers
   - config values
   - event emitter
4. Subsystems add events to a **shared per-tick buffer**.
5. CLEANUP persists events and snapshots.

---

## 4. Phase Model Overview
### INTENTS
Players, AI, NPCs express intentions (actions). Handlers validate and schedule effects.

### ENVIRONMENT
Nature operates: storms, droughts, floods, earthquakes, celestial omens.

### ECONOMY
Production, trade, resource flow, travel costs.

### POLITICS
Governance, unrest, faction influence, rebellions.

### SOCIAL
Religion, culture, education, festivals, mood.

### CLEANUP
Persist events and snapshots; reset tick variables.

This ordering reflects historical and causal relationships in ancient Lycia.

---

## 5. How Subsystems Interact Through Shared State
Subsystems never call each other; instead:
- ECONOMY might change prosperity → POLITICS reacts to prosperity → SOCIAL reacts to unrest.
- ENVIRONMENT might introduce drought → ECONOMY lowers harvest → POLITICS raises unrest → SOCIAL generates religious interpretations.

This chain reaction emerges purely from shared state + event history.

---

## 6. AIND Integration: Dynamic Events & Actions
AIND can produce:
- **Dynamic Events** with narrative content and effect verbs.
- **Dynamic Actions** with creative parameters.

AIND output is always validated and translated into **known effect verbs** in the simulation:
- `prosperity_delta`
- `unrest_delta`
- `piety_delta`
- `culture_shift`
- `route_blocked`
- etc.

Example dynamic event:
```
"Omen at the Sun Temple"
effects:
  - +5 piety
  - +3 unrest
  - spawn rumor
```

Example dynamic action:
```
ai.dynamic.smuggle
params:
  from_city: Xanthos
  cargo: cedar
```

The simulation safely maps these into internal event types and processes them like any other subsystem effect.

---

## 7. Why This Architecture Works
- Modular and easy to extend
- Deterministic and replayable
- Supports dynamic AI-driven creativity
- Prototype-friendly but production-ready
- Keeps the world always alive and evolving

---

