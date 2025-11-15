# Prototype Development Plan
---
title: Legacy of Lycia – Prototype Development Plan
version: 1.2
status: Living Document
updated: 2025-11-15
license: CC BY 4.0
---

# 🚀 Prototype Development Plan

## Overview
Development follows seven 2-week sprints in VS Code with Claude Code as AI pair-programmer, guided by these documents.

---

## Sprint Summary

| Sprint | Theme | MVP Goal | Status |
|--------|--------|----------|--------|
| 1 | Foundation & Map | World map + tick loop running | ✅ Complete |
| 2 | Core Engine Systems | Event sourcing + action queue + subsystems | ✅ Complete |
| 3 | Economy & Politics | Simulation subsystems + gameplay actions | Planned |
| 4 | AI Game Master | AIND integration + event narration | Planned |
| 5 | Multiplayer & Council | WebSocket + shared world + voting | Planned |
| 6 | Dynamic Events | AI-generated quests & actions | Planned |
| 7 | Educational Mode | Historian Q&A + Discovery Mode | Planned |

---

## Sprint 1 Deliverables (✅ Complete)

**Theme:** Foundation & Map ("Hello Lycia")

### Implemented
- Repository setup with FastAPI backend
- PostgreSQL database with Alembic migrations
- Redis for caching and sessions
- Interactive Leaflet-based map showing ancient Lycian cities
- Basic world state management and city data
- Player authentication (registration, login, logout, profile)
- Initial API endpoints (`/api/world`, `/health`)
- CI/CD pipeline with GitHub Actions
- Comprehensive design documentation (6 core documents)

### Key Deliverables
- Interactive map UI with Leaflet + Alpine.js
- Player authentication with bcrypt
- Database schema with migrations
- GitHub Actions CI pipeline
- Design documentation foundation

### Files
- `backend/src/lycia/app.py` - FastAPI application
- `backend/src/lycia/models.py` - Database models (Player, City, WorldState)
- `backend/src/lycia/templates/game.html` - Interactive map UI
- `docs/01-06_*.md` - Design documents

---

## Sprint 2 Deliverables (✅ Complete)

**Theme:** Core Engine Systems (Event Sourcing Architecture)

### Implemented Features

#### S2-01: Authoritative Tick Loop ✅
- Singleton tick loop with guaranteed single-instance execution
- Deterministic tick advancement with subsystem pipeline
- Crash recovery with graceful shutdown handling
- Configurable tick interval (2s dev, 5-15s prod)
- Tick metrics exposed via `/health` endpoint
- **Documentation:** [S2-01_Tick_System_Implementation.md](S2-01_Tick_System_Implementation.md)

#### S2-02: Subsystem Pipeline ✅
- Phase-based execution (INTENTS → ECONOMY → POLITICS → WEATHER → CLEANUP)
- Dependency resolution with topological sorting
- Cycle detection for subsystem dependencies
- Modular subsystem architecture with TickContext protocol
- **Documentation:** [S2-02_Subsystem_Pipeline_Implementation.md](S2-02_Subsystem_Pipeline_Implementation.md)

#### S2-03: Action Command Queue ✅
- Temporal constraint system (`valid_from_tick`, `expires_at_tick`)
- Command status lifecycle (PENDING → PROCESSED/REJECTED/EXPIRED)
- Versioned action handlers with registry
- Two-stage validation (syntactic params + semantic world state)
- Exactly-once processing guarantee
- **Documentation:** [S2-03_Action_Command_Queue_Implementation.md](S2-03_Action_Command_Queue_Implementation.md)

#### S2-04: Event Sourcing & Snapshots ✅
- Append-only event log for complete audit trail
- Periodic snapshot system for faster state reconstruction
- Event aggregation and state replay
- Event persistence subsystem in CLEANUP phase
- **Documentation:** [S2-04_Event_Sourcing_and_Snapshots_Implementation.md](S2-04_Event_Sourcing_and_Snapshots_Implementation.md)

#### S2-05: Schema Versioning ✅
- Explicit `schema_version` field on ActionCommand and Event
- JSON Schema definitions for v1 contracts (`backend/schemas/`)
- Version validation with clear error messages
- Future-proof format evolution support
- **Documentation:** [s2-05-implementation-summary.md](s2-05-implementation-summary.md)

#### S2-06: Deterministic RNG ✅
- Subsystem-specific seeded randomness
- Reproducible outcomes for testing and replay
- TickContext RNG helpers (uniform, randint, choice, random)
- **Documentation:** [S2-06_Deterministic_RNG_Implementation.md](S2-06_Deterministic_RNG_Implementation.md)

#### S2-07: Configuration System ✅
- Centralized `config/gameplay.json` for tunable parameters
- Runtime config loading with validation
- Designer-friendly parameter exposure
- Config access via TickContext
- **Documentation:** [S2-07_Config_Wiring_Implementation.md](S2-07_Config_Wiring_Implementation.md)

#### S2-08: World Diff API ✅
- `/api/world/diff?sinceTick=<n>` - Incremental state updates
- `/api/recap?sinceTick=<n>` - Structured event recap
- Efficient event log queries
- City metric change tracking
- **Documentation:** [S2-08_World_Diff_API_Implementation.md](S2-08_World_Diff_API_Implementation.md)

#### S2-09: World Update Delivery (Polling) ✅
- `/api/client/config` - Polling configuration endpoint
- Client-side JavaScript polling (3-second default interval)
- Real-time map updates via diff application
- Configurable polling interval via `gameplay.json`
- **Documentation:** [S2-09_World_Update_Delivery_Implementation.md](S2-09_World_Update_Delivery_Implementation.md)

#### S2-10: Developer Documentation ✅
- `docs/howto_add_subsystem.md` - Subsystem implementation guide
- `docs/howto_add_action.md` - Action handler implementation guide
- Example-driven documentation with file references
- Testing patterns and best practices

### Test Coverage
- **216+ tests passing** across all Sprint 2 features
- **100% authentication test coverage**
- Test categories:
  - Action command queue (30+ tests)
  - Authentication (25+ tests)
  - Event sourcing (17+ tests)
  - Subsystem pipeline (21+ tests)
  - Tick system (18+ tests)
  - Schema versioning (22+ tests)
  - World diff API (27+ tests)
  - Polling mechanism (15+ tests)
  - World snapshot API (6+ tests)
  - Health endpoint (2+ tests)

### Architecture Components
1. **Tick Loop System**: Authoritative server executes game logic at fixed intervals
2. **Subsystem Pipeline**: Modular game logic with dependency resolution and phase-based execution
3. **Action Command Queue**: Players submit commands with temporal constraints
4. **Event Sourcing**: All mutations recorded as append-only events with periodic snapshots
5. **Deterministic RNG**: Seeded randomness per subsystem ensures reproducible outcomes
6. **Configuration System**: JSON-based tunable parameters for designers
7. **Diff API**: Efficient incremental state updates for clients
8. **Polling System**: Client synchronization via HTTP polling

### Key Files
- `backend/src/lycia/tick/` - Tick loop system
- `backend/src/lycia/subsystems/` - Subsystem pipeline
- `backend/src/lycia/actions/` - Action command system
- `backend/src/lycia/event_sourcing/` - Event log and snapshots
- `backend/src/lycia/world_diff.py` - Diff API implementation
- `backend/config/gameplay.json` - Configuration file
- `backend/schemas/` - JSON Schema definitions (v1)
- `docs/howto_add_subsystem.md` - Developer guide
- `docs/howto_add_action.md` - Developer guide
- `docs/S2-01_*.md` through `docs/S2-09_*.md` - Implementation docs

---

## Sprint 3–7 Plan (Updated Based on Sprint 2 Architecture)

### Sprint 3: Economy & Political Subsystems
**Goal:** Implement core gameplay simulation systems

- Implement economy subsystem (production, trade, consumption, prosperity decay)
- Implement politics subsystem (unrest tracking, rebellions, diplomatic events)
- Add weather/disaster subsystem (random events affecting cities)
- Create gameplay action handlers:
  - Prosperity boost (economic investment)
  - Trade route establishment
  - Political edicts
  - City development
- Configuration tuning for game balance
- Comprehensive testing of subsystem interactions

### Sprint 4: AI Game Master (AIND Integration)
**Goal:** Add AI narration and dynamic content generation

- RAG system for historical context (ancient Lycia knowledge base)
- Event narration with LLM integration (GPT-4/Claude)
- AI-driven NPC decision making
- Dynamic quest/event generation based on game state
- Historian character for educational Q&A
- Prompt engineering for consistent narrative tone

### Sprint 5: Multiplayer & Real-Time Updates
**Goal:** Enable multi-player shared world experience

- WebSocket support for real-time updates (alternative to polling)
- Session management for multiple concurrent players
- Shared world state with conflict resolution
- Player-to-player interactions
- Council voting system for collective decisions
- Faction/alliance mechanics

### Sprint 6: Dynamic Content & Advanced Features
**Goal:** Add depth and replayability

- Dynamic event system (AI-generated scenarios)
- Quest mechanics with branching outcomes
- Achievement system
- Historical knowledge points
- Discovery Mode for exploration
- Advanced visualizations (charts, timelines)

### Sprint 7: Educational Mode & Polish
**Goal:** Final polish and educational features

- Historian Q&A interface with RAG
- Tutorial system for new players
- Discovery Mode enhancements
- Performance optimization
- UI/UX polish
- Documentation finalization
- Deployment preparation

---

## Development Workflow

1. **Design Phase:** Plan features in design documents (GPT-5 assisted)
2. **Implementation:** Code + tests in VS Code (Claude Code pair programming)
3. **Testing:** Comprehensive pytest coverage for all features
4. **Documentation:** Update implementation docs and READMEs
5. **Commit & Push:** Version control with GitHub (conventional commits)
6. **Review:** Sprint retrospective and planning

### Quality Standards
- All features must have test coverage
- Implementation documentation for major features
- Code passes linting (ruff) and type checking (mypy)
- CI/CD pipeline must pass before merge
- Design documents updated to reflect actual implementation

---

## Documentation Structure

### Design Documents (Foundational)
- `01_Prototype_Concept_Document.md` - Vision and goals
- `02_AIND_System_Design_Document.md` - AI Game Master design
- `03_Technical_Design_Document.md` - Architecture overview
- `04_Advanced_Design_Addendum.md` - Advanced features
- `05_World_Building_Bible.md` - Historical context and lore
- `06_Prototype_Development_Plan.md` - This document
- `07_AI_Team_Software_Development_Workflow.md` - Development process

### Implementation Documents (Sprint Deliverables)
- `S2-01` through `S2-09` - Sprint 2 implementation summaries
- `howto_add_subsystem.md` - Developer guide for subsystems
- `howto_add_action.md` - Developer guide for actions
- `HOWTO-local-dev.md` - Local development setup
- `API_Contracts.md` - API endpoint documentation

### Code Documentation
- Backend migration notes (`backend/MIGRATION_NOTES.md`)
- JSON Schemas (`backend/schemas/`)
- Inline code documentation and type hints

---

## License & Collaboration

- **Code:** Apache-2.0
- **Assets:** CC BY 4.0
- **Docs:** CC BY 4.0

All documents under `docs/` are living documents, versioned with commits and reviewed alongside code.

### Contributing
See [README.md](../README.md) for contribution guidelines, commit conventions, and development workflow.

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
