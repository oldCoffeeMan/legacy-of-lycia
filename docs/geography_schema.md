# Minimal Geography Schema & Lycia Map v0

## 1. Minimal Geography Schema

### Region
Represents a physical place with static and semi-static modifiers.

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| name | "Xanthos Valley" |
| kind | city, port, mountain_pass, rural_area, sea_lane |
| altitude_level | lowland, highland, mountain |
| terrain | fertile, rocky, forest, delta, coast |
| base_fertility | float 0–1 |
| base_travel_difficulty | float 0–1 |
| base_piracy_risk | (sea only) float 0–1 |
| base_bandit_risk | (land only) float 0–1 |
| culture_tags | cultural markers |
| sanctuary | bool |

### Route
Edge between two regions.

| Field | Description |
|-------|-------------|
| id | Unique |
| from_region / to_region | region ids |
| mode | land / sea |
| base_travel_time | ticks |
| danger_modifier | float 0–1 |
| status | open, blocked, dangerous |

### Building
Infrastructure that modifies geography.

| Field | Description |
|-------|-------------|
| region_id | Region |
| type | harbor, road, temple, academy, fort |
| level | 1–5 |

---

## 2. Lycia Map v0 (Prototype Map)

A simple 6-region map:

```
   Sea of Lycia
      |
 (4) Patara Port ----- Sea Lane ---- (5) Coast of Myra
      |
      | Land Route (rocky)
      |
 (1) Xanthos City --- Valley Route --- (2) Letoon Sanctuary
      |
      | Mountain Pass
      |
 (3) Tlos Highlands
```

### Regions

#### (1) Xanthos City
- fertile valley, low altitude  
- political center, key city  

#### (2) Letoon Sanctuary
- holy site, delta terrain  
- influences religion and social subsystems  

#### (3) Tlos Highlands
- high altitude, rocky terrain  
- difficult travel, naturally high unrest risk  

#### (4) Patara Port
- major port  
- affects trade volume and sea-based economics  

#### (5) Coast of Myra
- coastal region with high piracy risk  

#### (6) Sea of Lycia
- volatile weather and storms  
- affects sea routes and trade risk  

---

