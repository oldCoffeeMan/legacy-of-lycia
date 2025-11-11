# Legacy of Lycia

[![CI](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml/badge.svg)](https://github.com/oldCoffeeMan/legacy-of-lycia/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

AI-driven multiplayer strategy-simulation game set in ancient Lycia. Players manage cities, armies, and diplomacy while an AI Game Master narrates events and historical context using RAG (Retrieval-Augmented Generation).

## Features

- **Interactive Map**: Leaflet-based map showing ancient Lycian cities
- **Player Authentication**: Secure registration and login with bcrypt
- **Real-time Game State**: Turn-based gameplay with city management
- **AI Narration**: Historical context and event narration (coming soon)
- **RESTful API**: FastAPI backend with comprehensive test coverage

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

🚧 **Sprint 2** - In Progress
- ✅ Player authentication (registration, login, logout)
- ✅ Comprehensive test suite (33 tests passing)
- ✅ CI/CD pipeline with GitHub Actions
- ✅ Migration documentation and strategy
- ⏳ AI Game Master integration (planned)
- ⏳ Turn-based gameplay mechanics (planned)

## Development

### Running Tests

```bash
cd backend
TESTING=1 PYTHONPATH=src pytest tests/ -v --cov=lycia
```

**Test Coverage:**
- 25 authentication tests (password hashing, login, registration, profile)
- 2 health endpoint tests
- 6 world snapshot API tests

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

## API Endpoints

- **GET /** - Home page
- **GET /game** - Interactive game map
- **GET /register** - Registration page
- **POST /register** - Create new account
- **GET /login** - Login page
- **POST /login** - Authenticate user
- **POST /logout** - End session
- **GET /profile** - User profile
- **GET /api/world** - World state snapshot
- **GET /health** - Health check

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

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP
┌──────▼──────────────┐
│   FastAPI Backend   │
│  ┌───────────────┐  │
│  │ Auth System   │  │
│  │ Game Logic    │  │
│  │ API Routes    │  │
│  └───────────────┘  │
└──┬──────────────┬───┘
   │              │
   │ SQL      Redis
   │ Alchemy     Cache
┌──▼───────┐  ┌──▼────┐
│PostgreSQL│  │ Redis │
└──────────┘  └───────┘
```

## License

Apache-2.0

## Acknowledgments

- Historical context from ancient Lycian civilization
- Built with FastAPI, PostgreSQL, and modern web technologies
- AI-assisted development workflow using Claude Code

---

**Ancient Lycia Strategy Game - Open Source Project**
