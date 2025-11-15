# Legacy of Lycia

[![CI](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml/badge.svg)](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

AI-driven multiplayer real-time strategy game set in ancient Lycia. Players submit actions through a command queue system, with the game world evolving continuously through an authoritative tick loop. An AI Game Master will narrate events and provide historical context using RAG (Retrieval-Augmented Generation).

## Features

- **Real-Time Tick System**: Authoritative server-side tick loop with deterministic execution
- **Action Command Queue**: Submit actions with temporal constraints for predictable outcomes
- **Event Sourcing**: Complete audit trail of all game mutations with snapshot-based state reconstruction
- **World Diff API**: Efficient incremental state updates for clients
- **Interactive Map**: Leaflet-based map showing ancient Lycian cities with real-time polling updates
- **Player Authentication**: Secure registration and login with bcrypt
- **Subsystem Pipeline**: Modular game logic organized by execution phase (INTENTS → ECONOMY → POLITICS → WEATHER → CLEANUP)
- **Configuration System**: JSON-based tunable gameplay parameters
- **AI Narration**: Historical context and event narration (coming soon)
- **RESTful API**: FastAPI backend with comprehensive test coverage (216+ tests)

## Tech Stack

**Backend:**
- Python 3.13 with FastAPI
- PostgreSQL for persistent storage
- Redis for caching and sessions
- Alembic for database migrations
- bcrypt for password hashing

**Frontend:**
- Jinja2 templates with HTMX
- Alpine.js for interactivity
- Leaflet for map rendering
- Vanilla JavaScript

**Development:**
- Docker & Docker Compose for services
- pytest with 100% authentication test coverage
- Ruff for linting, Mypy for type checking
- GitHub Actions for CI/CD

## Quick Start

### Prerequisites
- Python 3.13+
- Docker Desktop
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/oldCoffeeMan/legacy-of-lycia.git
cd legacy-of-lycia

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e "backend[dev]"

# Start database
cd infra
docker-compose up -d db

# Run migrations and seed data
cd ../backend
alembic upgrade head
python scripts/seed.py

# Start the application
uvicorn src.lycia.app:app --reload
```

Visit http://localhost:8000 to play!

For detailed setup instructions, see [docs/HOWTO-local-dev.md](docs/HOWTO-local-dev.md)

## Project Status

**Current Sprint: Sprint 2 ✅ COMPLETE**

### ✅ Sprint 1 - Foundation & Map (Complete)
- Basic game map and city display
- World state management
- Initial database schema
- Player authentication system
- Design documentation

### ✅ Sprint 2 - Core Engine Systems (Complete)
**Event Sourcing Architecture - All 10 Items Delivered**

- ✅ **S2-01:** Authoritative tick loop system
- ✅ **S2-02:** Subsystem pipeline with dependency resolution
- ✅ **S2-03:** Action command queue with temporal constraints
- ✅ **S2-04:** Event sourcing and snapshot system
- ✅ **S2-05:** Schema versioning discipline (v1)
- ✅ **S2-06:** Deterministic RNG enforcement
- ✅ **S2-07:** Simple rules/config wiring
- ✅ **S2-08:** World Diff API & Basic Recap Contract
- ✅ **S2-09:** World Update Delivery (Polling)
- ✅ **S2-10:** Short Developer Docs (Subsystems & Actions)

**Comprehensive test suite: 216+ tests passing**
- CI/CD pipeline with GitHub Actions
- Migration documentation and strategy
- Developer documentation for extending the system

### ⏳ Upcoming Sprints
- **Sprint 3:** Economy, politics, and weather subsystems
- **Sprint 4:** AI Game Master integration (AIND)

## Development

### Running Tests

```bash
cd backend
TESTING=1 PYTHONPATH=src pytest tests/ -v --cov=lycia
```

**Test Coverage (216+ tests):**
- 30+ action command tests (queue, handlers, validation, temporal constraints)
- 25+ authentication tests (password hashing, login, registration, profile)
- 17+ event sourcing tests (persistence, snapshots, replay, state reconstruction)
- 21+ subsystem pipeline tests (registration, ordering, dependencies, execution)
- 18+ tick system tests (singleton guarantee, determinism, crash recovery, latency)
- 22+ schema versioning tests (validation, JSON schema compliance)
- 27+ world diff API tests (incremental updates, recap generation)
- 15+ polling mechanism tests (client updates, state synchronization)
- 6+ world snapshot API tests
- 2+ health endpoint tests

### Code Quality

```bash
# Linting
cd backend/src/lycia
ruff check .

# Type checking
mypy . --install-types --non-interactive
```

### Database Management

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check status
alembic current
```

See [backend/MIGRATION_NOTES.md](backend/MIGRATION_NOTES.md) for migration strategy and bcrypt upgrade notes.

## Documentation

- **[Local Development Guide](docs/HOWTO-local-dev.md)** - Complete setup instructions
- **[Migration Notes](backend/MIGRATION_NOTES.md)** - Database migrations and strategy
- **[API Contracts](docs/API_Contracts.md)** - API endpoint documentation
- **[AI Workflow](docs/07_AI_Team_Software_Development_Workflow.md)** - Development process

### Design Documents

- [01 - Prototype Concept](docs/01_Prototype_Concept_Document.md)
- [02 - AIND System Design](docs/02_AIND_System_Design_Document.md)
- [03 - Technical Design](docs/03_Technical_Design_Document.md)
- [04 - Advanced Design Addendum](docs/04_Advanced_Design_Addendum.md)
- [05 - World Building Bible](docs/05_World_Building_Bible.md)
- [06 - Prototype Development Plan](docs/06_Prototype_Development_Plan.md)

### Implementation Documents (Sprint 2)

- [S2-01 - Tick System Implementation](docs/S2-01_Tick_System_Implementation.md)
- [S2-02 - Subsystem Pipeline Implementation](docs/S2-02_Subsystem_Pipeline_Implementation.md)
- [S2-03 - Action Command Queue Implementation](docs/S2-03_Action_Command_Queue_Implementation.md)
- [S2-04 - Event Sourcing & Snapshots Implementation](docs/S2-04_Event_Sourcing_and_Snapshots_Implementation.md)
- [S2-05 - Schema Versioning Implementation](docs/s2-05-implementation-summary.md)
- [S2-06 - Deterministic RNG Implementation](docs/S2-06_Deterministic_RNG_Implementation.md)
- [S2-07 - Configuration System Implementation](docs/S2-07_Config_Wiring_Implementation.md)
- [S2-08 - World Diff API Implementation](docs/S2-08_World_Diff_API_Implementation.md)
- [S2-09 - World Update Delivery Implementation](docs/S2-09_World_Update_Delivery_Implementation.md)

### Developer Guides

- [How to Add a Subsystem](docs/howto_add_subsystem.md)
- [How to Add an Action Handler](docs/howto_add_action.md)

## API Endpoints

### Frontend Pages
- **GET /** - Home page
- **GET /game** - Interactive game map
- **GET /register** - Registration page
- **GET /login** - Login page
- **GET /profile** - User profile

### Authentication
- **POST /register** - Create new account
- **POST /login** - Authenticate user
- **POST /logout** - End session

### Game API
- **GET /api/world** - World state snapshot with all cities
- **GET /api/world/diff?sinceTick=\<n\>** - Incremental world state changes since tick N
- **GET /api/recap?sinceTick=\<n\>** - Structured event recap with highlights and summaries
- **GET /api/client/config** - Client configuration (polling interval, current tick)
- **POST /api/actions/enqueue** - Submit action command with temporal constraints
- **GET /api/actions/my-commands** - Retrieve player's command history
- **GET /health** - Health check with tick metrics

Full API documentation: http://localhost:8000/docs

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with conventional commit messages (`git commit -m 'feat: add amazing feature'`)
6. Push to your branch
7. Open a Pull Request

**Commit Prefixes:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

## Architecture

### System Overview

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP (REST API + Polling)
┌──────▼──────────────────────────┐
│      FastAPI Backend             │
│  ┌────────────────────────────┐ │
│  │  Authentication System     │ │
│  │  Action Command Queue      │ │
│  │  API Routes                │ │
│  │  World Diff API            │ │
│  └────────────────────────────┘ │
│                                  │
│  ┌────────────────────────────┐ │
│  │  Authoritative Tick Loop   │ │
│  │  ┌──────────────────────┐  │ │
│  │  │ Subsystem Pipeline   │  │ │
│  │  │  • INTENTS phase     │  │ │
│  │  │  • ECONOMY phase     │  │ │
│  │  │  • POLITICS phase    │  │ │
│  │  │  • WEATHER phase     │  │ │
│  │  │  • CLEANUP phase     │  │ │
│  │  └──────────────────────┘  │ │
│  └────────────────────────────┘ │
│                                  │
│  ┌────────────────────────────┐ │
│  │  Event Sourcing System     │ │
│  │  • Event Persistence       │ │
│  │  • Snapshot Creation       │ │
│  │  • State Replay            │ │
│  │  • Diff Calculation        │ │
│  └────────────────────────────┘ │
└──┬──────────────┬────────────────┘
   │              │
   │ SQLAlchemy   │ Redis
   │              │ (Cache/Sessions)
┌──▼───────────┐  ┌──▼────┐
│ PostgreSQL   │  │ Redis │
│ • World State│  └───────┘
│ • Events Log │
│ • Snapshots  │
│ • Commands   │
└──────────────┘
```

### Key Architectural Components

1. **Tick Loop System**: Authoritative server executes game logic at fixed intervals (2s dev, 5-15s prod)
2. **Subsystem Pipeline**: Modular game logic with dependency resolution and phase-based execution
3. **Action Command Queue**: Players submit commands with temporal constraints (valid_from_tick, expires_at_tick)
4. **Event Sourcing**: All mutations recorded as append-only events with periodic snapshots
5. **Deterministic RNG**: Seeded randomness per subsystem ensures reproducible outcomes
6. **Configuration System**: JSON-based tunable parameters for game designers
7. **Diff API**: Efficient incremental state updates using event log queries
8. **Polling System**: Client synchronization via configurable HTTP polling

## License

Apache-2.0

## Acknowledgments

- Historical context from ancient Lycian civilization
- Built with FastAPI, PostgreSQL, and modern web technologies
- AI-assisted development workflow using Claude Code

---

**Ancient Lycia Strategy Game - Open Source Project**
