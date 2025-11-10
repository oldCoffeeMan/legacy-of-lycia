# Advanced Design Addendum
---
title: Legacy of Lycia – Advanced Design Addendum
version: 1.1
status: Living Document
updated: 2025-11-10
license: CC BY 4.0
---

# 🧩 Legacy of Lycia Advanced Design Addendum

## 1. AI-Dynamic Gameplay Systems

### 1.1 Character Creation
- AI asks 3–5 questions → generates backstory + traits.  
- Attributes: physical, mental, social, spiritual, reputation tags.  
- Stored as JSON; influences dialogue tone and outcomes.

### 1.2 Dynamic Events
- Generated from simulation deltas and narrative context.  
- Validated numerically to avoid impossible outcomes.  
- Example: “Drought → grain shortage → Famine Appeal quest”.

### 1.3 Dynamic Actions
- AI may introduce new verbs (“smuggle”, “rebuild aqueduct”).  
- Validation layers ensure resources & role compatibility.

---

## 2. Finalized Roles

**Available Roles:** Governor (Archon) | Merchant | Pirate | Artisan | Priest | Scholar | Scout | Diplomat | Farmer

Each role has educational and adventure value; all AI-generated variations differ in traits and motives.

---

## 3. Expanded Simulation Systems

### 3.1 Economy & Currency
- City-based coinage (bronze/silver).  
- Exchange rate = f(prosperity, mint output).  
- Taxation & tribute events.  

### 3.2 Population & Morale
- morale = f(food, prosperity, faith).  
- unrest = 1 − morale.

### 3.3 Religion & Omens
- Temples indexed by city and god.  
- Faith Index affects ritual success.

### 3.4 Environment & Climate
- Seasonal cycle; random droughts / storms.  
- Background agent keeps world alive without players.

### 3.5 Politics & League
- Federal votes every few ticks.  
- Persian satrap interventions via events.

### 3.6 Maritime & Piracy
- Sea routes have security index.  
- Merchant losses influence economy + morale.

---

## 4. Map Assets & Locations

### Major Cities
**Patara** | **Xanthos** | **Myra** | **Tlos** | **Pinara** | **Phaselis** | **Arycanda** | **Olympos** | **Limyra** | **Letoon**

### Asset Categories
- **Urban:** mints, markets, shipyards, granaries  
- **Agricultural:** olive presses, vineyards, cedar forests  
- **Defensive:** fortresses, walls, beacons  
- **Religious:** temples, oracles, necropoleis  
- **Natural:** rivers, mountains, bays  
- **Infrastructure:** roads, bridges, aqueducts  

---

## 5. Independence of Simulation

Autonomous NPC cities evolve even without players; player actions perturb parameters but don't drive all changes.

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
