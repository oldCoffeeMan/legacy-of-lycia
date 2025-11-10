# Prototype Development Plan
---
title: Legacy of Lycia – Prototype Development Plan
version: 1.1
status: Living Document
updated: 2025-11-10
license: CC BY 4.0
---

# 🚀 Prototype Development Plan

## Overview
Development follows seven 2-week sprints in VS Code with Claude Code as AI pair-programmer, guided by these documents.

---

## Sprint Summary

| Sprint | Theme | MVP Goal |
|--------|--------|----------|
| 1 | Foundation & Map | World map + tick loop running |
| 2 | Roles & AI Character | AI Q&A character creation |
| 3 | Narrative System | Dialogue scenario via AIND |
| 4 | Simulation Integration | Economy & morale react to actions |
| 5 | Multiplayer & Council | Shared world + voting |
| 6 | Dynamic Events | AI-generated actions & quests |
| 7 | Educational Mode | Historian Q&A + Discovery Mode |

---

## Sprint 1 Tasks ("Hello Lycia")
- Setup repo, FastAPI backend, Postgres, Redis, map UI.  
- Implement tick loop and `/world/snapshot` endpoint.  
- Verify CI/CD with GitHub Actions.

---

## Sprint 2–7 Highlights

- **Sprint 2:** AI character builder → store JSON attributes.
- **Sprint 3:** Dialogue engine (prompt + schema + parser).
- **Sprint 4:** Connect actions ↔ simulation.
- **Sprint 5:** Add WebSocket multiplayer & council votes.
- **Sprint 6:** Event generator & dynamic actions.
- **Sprint 7:** Historian integration (RAG Q&A + knowledge points).

---

## Development Workflow
1. Design here (GPT-5)  
2. Code + tests in VS Code (Claude Code assists)  
3. Commit & push to GitHub (`docs/` updates included)  
4. Review deliverables at sprint end  

---

## Documentation & Learning

Each sprint deliverable includes:
- **`HOWTO.md`** – step-by-step implementation
- **`TESTS/`** – pytest scripts
- **`PROMPTS/`** – Claude/GPT prompt templates
- **`LESSONS.md`** – learning summary for new contributors

---

## License & Collaboration
- **Code:** Apache-2.0  
- **Assets:** CC BY 4.0  
- **Docs:** CC BY 4.0  

All documents under `docs/` are living, versioned with commits and reviewed alongside code.

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
