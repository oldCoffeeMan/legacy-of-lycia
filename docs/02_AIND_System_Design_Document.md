# AIND System Design Document
---
title: Legacy of Lycia – AI Narrative & Dialogue System (AIND)
version: 1.1
status: Living Document
updated: 2025-11-10
license: CC BY 4.0
---

# 🧠 AI Narrative & Dialogue System (AIND)

## 1. Purpose
The **AI Narrative & Dialogue System (AIND)** dynamically generates all story content, dialogue, and events.  
It fuses player intent, simulation state, and the knowledge base of Lycian history into interactive, educational storytelling.

---

## 2. System Architecture

```text
Player Input
     │
     ▼
Dialogue Manager ──► Context Builder ──► GPT-5 LLM + RAG
     │                                       │
     ▼                                       ▼
Simulation Service ◄── Validation & Effects ◄── Parsed JSON Output
     │
     ▼
Game Database → Player UI
```

## Main Components

| Component            | Description                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| **Dialogue Manager** | Handles incoming messages, builds prompts, parses LLM JSON responses.                          |
| **Narrative Engine** | GPT-5 or Claude Code backend with RAG access to the Lycian lore dataset.                       |
| **Memory Graph**     | Stores persistent memories (player, NPC, faction, world). Implemented with Neo4j + PostgreSQL. |
| **Historian Module** | Educational AI for factual Q&A and contextual notes. Uses RAG indexing of academic sources.    |

## 3. Dialogue Flow Example

**Player Action:** "Negotiate trade with Xanthos."

1. **Context Fetch:** Retrieve character attributes, city prosperity, and political state.
2. **Prompt Construction:** Compose system + user messages per schema.
3. **LLM Generation:** Dialogue text, educational annotation, and structured options.
4. **Simulation Update:** Apply economic and reputation effects.

### Example JSON Output
```json
{
  "speaker": "Governor Arkkis",
  "text": "Patara's ships grow bold; the League must watch its harbors.",
  "educational_note": "Lycians were known for their maritime trade in cedar and olive oil.",
  "choices": [
    {"label": "Offer alliance", "intent": "diplomacy", "effect": "+5 trust"},
    {"label": "Threaten ban", "intent": "conflict", "effect": "-3 relation"}
  ]
}
```

---

## 4. Memory Layers
| Layer                | Scope                                 | Example                                    |
| -------------------- | ------------------------------------- | ------------------------------------------ |
| **Session Memory**   | Current dialogue context              | “You promised the priest grain.”           |
| **Character Memory** | Player/NPC personality & past actions | “Governor Arkkis distrusts you.”           |
| **Faction Memory**   | Political alignment & votes           | “League divided on piracy.”                |
| **World Memory**     | Long-term history & artifacts         | "Patara rebuilt its harbor after a storm." |

---

## 5. Prompt Template

```
System:
You are the Narrator of *Legacy of Lycia*.
Generate historically grounded dialogue set in 5th-century BCE Lycia.
Respect the provided world state and maintain tone consistency.
Respond in valid JSON conforming to schema <dialogue_schema_v1>.
```

---

## 6. Integration with Development Workflow

- **Prompt & Schema Storage:** under `/prompts/` (editable in VS Code).
- **Claude Code Usage:** assists in schema authoring, validation functions, and unit tests.
- **Testing:** each dialogue turn validated by JSON schema + pytest integration tests to confirm consistency with simulation updates.
- **Versioning:** each prompt/schema pair tagged (e.g., `aind_v1.1`) to keep model fine-tuning reproducible.

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0