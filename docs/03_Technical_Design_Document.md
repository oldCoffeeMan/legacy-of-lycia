---
title: Legacy of Lycia – Technical Design Document
version: 1.1
status: Living Document
updated: 2025-11-10
license: CC BY 4.0
---

# ⚙️ Technical Design Document

## 1. Overview
Defines architecture, data models, API structure, and development environment for the *Legacy of Lycia* prototype.

---

## 2. Core Stack

| Layer | Tool / Framework |
|--------|------------------|
| Language | Python 3.14 |
| Web Framework | FastAPI |
| ORM / Migrations | SQLAlchemy + Alembic |
| Cache / Queue | Redis |
| Database | PostgreSQL |
| Vector Search | Qdrant |
| Graph Store | Neo4j |
| AI Services | GPT-5 (design) + Claude Code (development) |
| Frontend | Jinja + HTMX + Leaflet (Node-less) |
| IDE | VS Code with Claude Code extension |

---

## 3. Service Layout

```text
legacy-of-lycia/
├─ backend/
│  ├─ src/lycia/
│  │   ├─ app.py
│  │   ├─ routes/
│  │   ├─ models/
│  │   ├─ services/
│  │   └─ simulation/
│  └─ tests/
├─ frontend/
│  ├─ templates/
│  └─ static/
└─ infra/
   ├─ docker-compose.yml
   └─ migrations/
```

---

## 4. Key Services

| Service              | Description                                             |
| -------------------- | ------------------------------------------------------- |
| **Game API**         | REST + WebSocket endpoints for client interactions.     |
| **AIND Service**     | Dialogue and event generation via LLM JSON interface.   |
| **Simulation Service** | Runs world ticks, economic & environmental models.    |
| **Historian Service** | Educational RAG Q&A with verified sources.             |

---

## 5. Data Model Highlights
| Table / Entity  | Fields (Simplified)                                     | Notes                        |
| --------------- | ------------------------------------------------------- | ---------------------------- |
| **City**        | `id`, `name`, `prosperity`, `unrest`, `coin_type`       | Simulation core unit.        |
| **Player**      | `id`, `role`, `attributes_json`, `wealth`, `reputation` | Player state.                |
| **WorldState**  | `id=1`, `season`, `tick`                                | Global variables.            |
| **Event**       | `id`, `type`, `payload_json`                            | Dynamic world events.        |
| **DialogueLog** | `id`, `player_id`, `content_json`                       | Stores past conversations.   |
| **Faction**     | `id`, `name`, `reputation_map_json`                     | League and faction politics. |

---

## 6. Simulation Tick

```python
def tick(session):
    """Advance world simulation every 30 seconds."""
    world = session.get(WorldState, 1)
    world.tick += 1
    for city in session.query(City).all():
        city.prosperity += random.gauss(0, 0.3)
        city.unrest = max(0, city.unrest + random.uniform(-0.1, 0.1))
    session.commit()
```

---

## 7. Initial API Endpoints

| Method | Route             | Description                             |
| ------ | ----------------- | --------------------------------------- |
| GET    | `/health`         | Health check                            |
| GET    | `/world/snapshot` | Return world and cities summary         |
| GET    | `/cities/{id}`    | City details                            |
| POST   | `/players`        | Create or load player                   |
| POST   | `/dialogue/turn`  | Submit player action, return dialogue   |

---

## 8. Deployment

- **Containerization:** Docker + docker-compose (db, redis, backend).
- **CI/CD:** GitHub Actions → lint (ruff), types (mypy), tests (pytest).
- **Hosting:** Fly.io / Render for staging; scalable later to Kubernetes.
- **Monitoring:** OpenTelemetry + Grafana/Loki stack for logs & metrics.

---

## 9. Licensing & Contribution

| Area   | License      |
| ------ | ------------ |
| Code   | Apache-2.0   |
| Assets | CC BY 4.0    |
| Docs   | CC BY 4.0    |

### Development workflow:
1. Design & spec → GPT-5
2. Implement & test → VS Code + Claude Code
3. Review → GitHub PRs

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0