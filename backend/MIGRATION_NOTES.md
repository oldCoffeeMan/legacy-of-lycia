# Migration Notes

## Alembic Migration Strategy

### Current Migration Chain
```
3e21767ad59d (init) -> 70c70888b30a (empty) -> fbdaf365c867 (add_player_table)
```

**Migration Details:**
1. **3e21767ad59d_init.py** - Creates initial schema (cities, world_state tables)
2. **70c70888b30a_init_schema_cities_world_state.py** - Empty migration (redundant, but cannot be deleted)
3. **fbdaf365c867_add_player_table.py** - Adds players table for authentication

### Important Notes
- **Migrations only define schema**, NOT data
- **Data seeding** is handled separately via `backend/scripts/seed.py`
- The middle migration (70c70888b30a) is empty but must remain in the chain
- Never delete applied migrations - it breaks the revision history

### Running Migrations

**Fresh database:**
```bash
cd backend
alembic upgrade head
python scripts/seed.py  # Populate initial data
```

**Check current version:**
```bash
alembic current
alembic history
```

**After pulling new migrations:**
```bash
alembic upgrade head
```

### Creating New Migrations

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description"

# Review the generated file before committing!
# Alembic may not detect all changes correctly
```

---

## bcrypt 5.0.0 Upgrade (2025-11-11)

### What Changed
Replaced `passlib` with direct `bcrypt` usage for password hashing due to compatibility issues with bcrypt 5.0.0.

### Impact
**Existing user accounts will need to re-register.**

Old password hashes (created with passlib's `bcrypt_sha256`) are incompatible with the new direct bcrypt implementation.

### Action Required

**For Development:**
1. Clear player data (if database already exists):
   ```bash
   docker exec lycia-postgres psql -U postgres -d lycia -c "TRUNCATE TABLE players RESTART IDENTITY CASCADE;"
   ```

2. OR drop and recreate the database:
   ```bash
   cd infra
   docker-compose down -v
   docker-compose up -d db
   cd ../backend
   alembic upgrade head
   python scripts/seed.py
   ```

3. Re-register test accounts via the `/register` endpoint

**For Production (when deployed):**
- This migration should happen **before** production launch
- No user data exists yet, so no migration needed
- All future passwords will use bcrypt directly

### Technical Details
- **Old**: passlib's `CryptContext` with `bcrypt_sha256` scheme
- **New**: Direct `bcrypt.hashpw()` with automatic salting
- **Security**: bcrypt's 72-byte limit is now explicitly handled
- **Format**: Standard bcrypt `$2b$` hashes

### Why This Change?
- bcrypt 5.0.0 removed `__about__.__version__` attribute
- passlib hasn't been updated to support bcrypt 5.0.0
- Using bcrypt directly is simpler and more maintainable
- Eliminates the passlib dependency

---

## Testing Strategy

### Test Suite Organization
- **Unit tests**: `test_auth.py` (password hashing, authentication logic)
- **Integration tests**: Currently 16/25 passing (endpoint tests have fixture issues)
- **API tests**: `test_world_snapshot.py` (JSON Schema validation)

### Test Coverage
- ✅ Password hashing (bcrypt) - 7 tests passing
- ✅ Player authentication logic - 5 tests passing
- ✅ Registration form validation - 4 tests passing
- ⚠️ Login/logout endpoints - Needs fixture refactoring
- ⚠️ Profile page - Needs fixture refactoring

### Known Issues
- Integration tests for endpoints need fixture refactoring
- TestClient and db_session fixtures create separate database instances
- This causes data isolation issues between test setup and endpoint execution

### Running Tests
```bash
cd backend
PYTHONPATH=src pytest tests/ -v
```
