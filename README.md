# Legacy of Lycia

[![CI](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml/badge.svg)](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

AI-driven multiplayer real-time strategy game set in ancient Lycia. Players submit actions through a command queue system, with the game world evolving continuously through an authoritative tick loop. An AI Game Master will narrate events and provide historical context using RAG (Retrieval-Augmented Generation).

## Features

- **Real-Time Tick System**: Authoritative server-side tick loop with deterministic execution
- **Action Command Queue**: Submit actions with temporal constraints for predictable outcomes
- **Event Sourcing**: Complete audit trail of all game mutations with snapshot-based state reconstruction
- **Interactive Map**: Leaflet-based map showing ancient Lycian cities
- **Player Authentication**: Secure registration and login with bcrypt
- **Subsystem Pipeline**: Modular game logic organized by execution phase (INTENTS → ECONOMY → POLITICS → WEATHER → CLEANUP)
- **AI Narration**: Historical context and event narration (coming soon)
- **RESTful API**: FastAPI backend with comprehensive test coverage (121 tests)

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

**Current Sprint: Sprint 2**

✅ **Sprint 1 (v0.1-sprint1)** - Completed
- Basic game map and city display
- World state management
- Initial database schema
- Design documentation

✅ **Sprint 2** - Core Systems Complete
- ✅ Player authentication (registration, login, logout)
- ✅ Authoritative tick loop system (S2-01)
- ✅ Subsystem pipeline with dependency resolution (S2-02)
- ✅ Action command queue with temporal constraints (S2-03)
- ✅ Event sourcing and snapshot system (S2-04)
- ✅ Comprehensive test suite (121 tests passing)
- ✅ CI/CD pipeline with GitHub Actions
- ✅ Migration documentation and strategy
- ⏳ Economy, politics, and weather subsystems (S2-05 to S2-15)
- ⏳ AI Game Master integration (planned)

## Development

### Running Tests

```bash
cd backend
TESTING=1 PYTHONPATH=src pytest tests/ -v --cov=lycia
```

**Test Coverage (121 tests):**
- 30 action command tests (queue, handlers, validation, temporal constraints)
- 25 authentication tests (password hashing, login, registration, profile)
- 17 event sourcing tests (persistence, snapshots, replay, state reconstruction)
- 21 subsystem pipeline tests (registration, ordering, dependencies, execution)
- 18 tick system tests (singleton guarantee, determinism, crash recovery, latency)
- 6 world snapshot API tests
- 2 health endpoint tests
- 2 miscellaneous integration tests

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
       │ HTTP (REST API)
┌──────▼──────────────────────────┐
│      FastAPI Backend             │
│  ┌────────────────────────────┐ │
│  │  Authentication System     │ │
│  │  Action Command Queue      │ │
│  │  API Routes                │ │
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

## License

Apache-2.0

## Acknowledgments

- Historical context from ancient Lycian civilization
- Built with FastAPI, PostgreSQL, and modern web technologies
- AI-assisted development workflow using Claude Code

---

**Ancient Lycia Strategy Game - Open Source Project**
