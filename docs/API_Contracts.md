---
title: Legacy of Lycia – API Contracts
version: 1.0
status: Living Document
updated: 2025-11-11
license: CC BY 4.0
---

# 📡 API Contracts

## Overview

This document defines the API contracts for Legacy of Lycia endpoints. All contracts are validated via JSON schemas in `backend/tests/schemas/`.

---

## Health Check

### Endpoint
```
GET /health
```

### Description
Simple health check endpoint to verify API is running.

### Authentication
None required

### Response
```json
{
  "status": "ok"
}
```

### Status Codes
- `200 OK` - Service is healthy

---

## World Snapshot

### Endpoint
```
GET /api/world/snapshot
```

### Description
Returns current state of the world including tick count and all cities.

### Authentication
None required (will require auth in future sprints)

### Response Schema
See `backend/tests/schemas/world_snapshot_v1.json`

### Response Example
```json
{
  "tick": 42,
  "cities": [
    {
      "id": 1,
      "name": "Xanthos",
      "region": "Eastern Lycia",
      "prosperity": 0.75,
      "unrest": 0.15,
      "lat": 36.3572,
      "lon": 29.3175
    },
    {
      "id": 2,
      "name": "Patara",
      "region": "Western Lycia",
      "prosperity": 0.68,
      "unrest": 0.22,
      "lat": 36.2669,
      "lon": 29.3183
    }
  ]
}
```

### Field Definitions

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `tick` | integer | Current simulation tick | ≥ 0 |
| `cities` | array | List of all cities | - |
| `cities[].id` | integer | Unique city identifier | - |
| `cities[].name` | string | City name | Length ≥ 1 |
| `cities[].region` | string | Geographic region | - |
| `cities[].prosperity` | number | Prosperity level | 0.0 - 1.0 |
| `cities[].unrest` | number | Unrest level | 0.0 - 1.0 |
| `cities[].lat` | number | Latitude | -90 to 90 |
| `cities[].lon` | number | Longitude | -180 to 180 |

### Status Codes
- `200 OK` - Successful response
- `404 Not Found` - World state not initialized
- `500 Internal Server Error` - Database or unexpected error

### Error Response Format
```json
{
  "detail": "Error message description"
}
```

---

## Contract Versioning

All API contracts are versioned via schema files:
- `world_snapshot_v1.json` - Current version
- Future versions will increment: `v2`, `v3`, etc.

Tests validate responses against these schemas to ensure stability.

---

## Testing

Contract compliance is validated in:
- `backend/tests/test_world_snapshot.py`
- Uses `jsonschema` library for validation
- All responses must pass schema validation

Example test:
```python
from jsonschema import validate

validate(instance=response_data, schema=WORLD_SNAPSHOT_SCHEMA)
```

---

© 2025 Legacy of Lycia Project Contributors — Licensed CC BY 4.0
