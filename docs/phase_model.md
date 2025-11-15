# Phase Model & Initial Subsystems (For Sprint 3 Planning)

## 1. Final Phase Order
```
INTENTS
→ ENVIRONMENT
→ ECONOMY
→ POLITICS
→ SOCIAL
→ CLEANUP
```

---

## 2. Rationale for Ordering

### INTENTS
All decisions (players, AI) are evaluated upfront.

### ENVIRONMENT
Nature acts independently and influences all following phases:
- storms affect sea routes  
- drought affects crops  
- quakes affect infrastructure

### ECONOMY
Crops, trade, production depend heavily on environment.

### POLITICS
Political systems respond to economic conditions:
- scarcity → unrest  
- prosperity → stability  

### SOCIAL
Religion, culture, festivals react to political mood and influence future behaviors.

### CLEANUP
Events and snapshots persisted for replay and summarization.

---

## 3. Initial Subsystems by Phase

### INTENTS Phase
- ActionCommandSubsystem
- AIIntentSubsystem
- StandingOrdersSubsystem (optional)

### ENVIRONMENT Phase
- ClimateSubsystem
- DisasterSubsystem
- CelestialSubsystem
- SeasonSubsystem

### ECONOMY Phase
- AgricultureSubsystem
- TradeSubsystem
- ResourceSubsystem
- InfrastructureSubsystem

### POLITICS Phase
- UnrestSubsystem
- GovernanceSubsystem
- FactionSubsystem
- SecuritySubsystem

### SOCIAL Phase
- ReligionSubsystem
- CultureSubsystem
- EducationSubsystem
- FestivalSubsystem

### CLEANUP Phase
- EventPersistenceSubsystem
- SnapshotSubsystem
- TickMetricsSubsystem

---

## 4. Simulation Flow Example

### Scenario: Drought + Political Unrest

1. **INTENTS**  
   Player sends caravan. AI proposes ritual.

2. **ENVIRONMENT**  
   Drought severity increases.

3. **ECONOMY**  
   Crops -30%. Trade cost +20%.

4. **POLITICS**  
   Unrest +6 due to scarcity.

5. **SOCIAL**  
   Religion interprets drought as omen → piety +5.

6. **CLEANUP**  
   All events persisted.

---


