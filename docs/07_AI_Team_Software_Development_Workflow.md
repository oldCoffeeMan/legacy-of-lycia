---
title: Legacy of Lycia – AI Team Software Development Workflow
version: 1.0
status: Living Document
updated: 2025-11-11
license: CC BY 4.0
---

# 🤖 AI Team Software Development Workflow

## 1. Overview

This document defines how *Legacy of Lycia* is developed by a hybrid human-AI team.
Two AI environments collaborate:

| Role                     | Tool                | Primary Use                                                                      |
| ------------------------ | ------------------- | -------------------------------------------------------------------------------- |
| **GPT-5 (here)**         | ChatGPT / API       | Design, planning, documentation, architecture reviews, learning materials        |
| **Claude Code + VS Code** | VS Code Extension   | Implementation, testing, refactors, and in-IDE assistance                        |

Human contributors manage coordination, version control, and learning resources.

---

## 2. General Workflow

1. **Design & Spec (GPT-5)**
   - Plan sprints, architecture, test strategies, and prompts.
   - Produce/update design documents under `docs/`.

2. **Implementation (VS Code + Claude Code)**
   - Develop features in branches.
   - Use Claude's inline explanations and code generation.

3. **Review & Integrate**
   - Commit frequently.
   - Create PRs in GitHub for every sprint deliverable.
   - GPT-5 provides architectural or code reviews (see section 5).

4. **Document & Learn**
   - Update `docs/` and `docs/learning/` after each sprint.
   - Keep README and roadmap synced.

---

## 3. Sprint Flow

| Stage        | Tool                  | Output                                  |
| ------------ | --------------------- | --------------------------------------- |
| **Planning** | GPT-5                 | Sprint backlog + test plan              |
| **Coding**   | VS Code + Claude Code | Feature branch, unit tests              |
| **Review**   | GPT-5                 | Architectural feedback, integration advice |
| **Delivery** | GitHub                | Tagged release (v0.x-sprintN)           |
| **Learning** | GPT-5                 | Updated HOWTOs and Lessons.md           |

---

## 4. Using GPT-5 Chats Effectively

Each chat thread acts as a **specialized workspace**.

| Thread Type      | Purpose                                                         |
| ---------------- | --------------------------------------------------------------- |
| **Design Hub**   | Gameplay & lore design, world-building, AIND narrative tuning   |
| **Tech Hub**     | Backend architecture, APIs, database models, CI/CD              |
| **Frontend UI**  | HTMX + Leaflet map design or later React migration              |
| **AI Systems**   | Prompt engineering, simulation AI, historian integration        |
| **Sprint Tracker** | Planning, backlog, test plan, and retrospectives              |
| **Learning Hub** | Tutorials and onboarding material generation                    |

When starting a new topic, open a new chat with that title and paste the GitHub doc link being referenced.

---

## 5. Code Review with GPT-5

### What GPT-5 Can Do
- Review **public PRs or commits** by link.
- Or analyze **pasted diffs / key files** (app.py, models, routes, tick loop, CI YAML).

### Best-Practice Steps
1. In GitHub, create a PR for your sprint branch.
2. Share the PR link here → GPT-5 reviews architecture, cohesion, and test coverage.
3. For private repos, paste:
   - `tree -L 2`
   - key backend files (`app.py`, `models/`, `simulation/`, `routes/`, `tests/`)
   - any diff (`git diff base..head`)

GPT-5 then provides:
- High-level integrity assessment
- Security & maintainability notes
- Actionable fix list (severity → priority)

---

## 6. Test Planning and Automation

Every sprint backlog includes:
- **Test Plan.md** → defines scope, risks, types (unit/integration/performance).
- **pytest skeletons** → one test per endpoint/feature.
- **Contract Schemas** → JSON schemas for API responses.
- **Continuous Testing** via GitHub Actions.

### Example layout
```text
backend/tests/
├─ test_health.py
├─ test_players.py
├─ conftest.py
└─ schemas/
   └─ player_v1.json
```

---

## 7. Learning & HOWTO Documentation

### Folder Layout
```text
docs/
└─ learning/
   ├─ HOWTO_Git_Basics.md
   ├─ HOWTO_GitHub_CLI.md
   ├─ HOWTO_Python_Venv.md
   ├─ HOWTO_FastAPI_Basics.md
   ├─ HOWTO_PostgreSQL_Alembic.md
   ├─ HOWTO_Docker_Compose.md
   ├─ HOWTO_Leaflet_Map_Starter.md
   └─ HOWTO_VSCode_Claude_Workflow.md
```

### Purpose
- Each HOWTO is **standalone** and **beginner-friendly**.
- GPT-5 generates drafts; Claude Code can add code snippets.
- Updated after each sprint to reflect lessons learned.

---

## 8. Version Control Strategy

### Branching Model
- **main** – stable, deployable code
- **sprint-N** – development branch for each sprint
- **feature/name** – individual feature branches (optional)

### Commit Conventions
Use conventional commit prefixes:
- `feat:` – new feature
- `fix:` – bug fix
- `refactor:` – code restructure
- `test:` – test additions/changes
- `docs:` – documentation only
- `chore:` – tooling, dependencies

### Pull Request Process
1. Create PR from `sprint-N` → `main`
2. GPT-5 reviews architecture (optional)
3. Claude Code performs inline refactors if needed
4. Merge after CI passes + review approval
5. Tag release: `v0.1-sprint1`, `v0.2-sprint2`, etc.

---

## 9. AI Pair Programming Best Practices

### When to Use GPT-5
- High-level design decisions
- Multi-file architecture changes
- Test plan and strategy design
- Learning material creation
- Code review and security audit

### When to Use Claude Code
- Line-by-line implementation
- Debugging and error fixing
- Refactoring within files
- Writing unit tests
- Quick prototypes and iterations

### Coordination
- Keep both AIs informed of major architectural decisions
- Share key files and schemas between environments
- Use `docs/` as single source of truth
- Update documentation immediately after implementation

---

## 10. Quality Gates

Before merging any sprint:

| Gate | Requirement |
|------|-------------|
| **Tests** | All pytest tests pass |
| **Linting** | Ruff reports no errors |
| **Types** | Mypy validates type hints |
| **Docs** | README and docs/ reflect changes |
| **Review** | At least one architectural review (GPT-5 or human) |

---

## 11. Continuous Integration

### GitHub Actions Workflow
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.14'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy backend/src
      - name: Test
        run: pytest backend/tests
```

---

## 12. Documentation Maintenance

All documents under `docs/` are:
- **Living** – updated continuously
- **Versioned** – track changes via git
- **Reviewed** – validated each sprint
- **Licensed** – CC BY 4.0

### Update Triggers
- After each sprint completion
- When architecture changes
- After major refactors
- When new features are added

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
