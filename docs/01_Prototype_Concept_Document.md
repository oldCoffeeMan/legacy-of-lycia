# Prototype Concept Document
---
title: Legacy of Lycia – Prototype Concept Document
version: 1.1
status: Living Document
updated: 2025-11-10
license: CC BY 4.0
---

# 🏺 Legacy of Lycia — Prototype Concept Document

## Overview
**Legacy of Lycia** is an AI-driven, multiplayer role-playing strategy-simulation game that brings the ancient **Lycian Civilization** to life.  
Players assume historically grounded roles and collaboratively build, govern, and influence the Lycian League through diplomacy, trade, faith, and exploration.

### Development Context
- **Backend:** Python 3.14 / FastAPI / PostgreSQL / Redis / Qdrant  
- **Frontend (prototype):** Python-only UI with Jinja + HTMX + Leaflet (no Node)  
- **AI Assistants:**  
  - **GPT-5 (this workspace):** design & architecture documentation  
  - **Claude Code + VS Code:** implementation & code iteration  
- **License:** Apache-2.0 (code) + CC BY 4.0 (assets)

---

## Core Design Pillars
1. **AI-Generated Civilization** – every session evolves through AI-created stories, decisions, and events.  
2. **Educational Play** – historical facts and archaeological data are woven into quests and dialogue.  
3. **Dynamic Simulation** – politics, economy, religion, and environment run continuously.  
4. **Collaborative World** – players’ combined choices form the shared Lycian narrative.  

---

## Gameplay Loop
1. **Choose Role** → AI interview creates a unique character (traits, history, ambitions).  
2. **Act on Map** → explore, trade, build, pray, fight.  
3. **Negotiate / Compete** → League councils, alliances, piracy, diplomacy.  
4. **World Evolves** → simulation and AI events update cities, economy, and morale.  
5. **Learn & Discover** → historian AI reveals real Lycian insights and artifacts.  

---

## Technical Summary
| Layer | Technology | Description |
|--------|-------------|-------------|
| Backend | FastAPI + SQLAlchemy | Core API / simulation |
| AI | GPT-5 + LangChain + RAG | Dialogue, events, historian |
| DB | PostgreSQL + Redis + Neo4j + Qdrant | State, cache, graph & facts |
| Frontend | Jinja + HTMX + Leaflet | Map + UI (Node-less) |
| Dev Env | VS Code + Claude Code | Code implementation |

---

## Prototype Milestone
1. **MVP Map** – visual map of Lycia, clickable cities.  
2. **AI Character Creation** – dynamic player backstories.  
3. **AI Dialogue System** – contextual conversations.  
4. **Simulation Link** – player actions affect world state.  
5. **Multiplayer Council** – shared world with voting.  
6. **Historian Mode** – educational Q&A.

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
