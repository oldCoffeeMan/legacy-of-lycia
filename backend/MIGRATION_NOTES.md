# Migration Notes

## bcrypt 5.0.0 Upgrade (2025-11-11)

### What Changed
Replaced `passlib` with direct `bcrypt` usage for password hashing due to compatibility issues with bcrypt 5.0.0.

### Impact
**Existing user accounts will need to re-register.**

Old password hashes (created with passlib's `bcrypt_sha256`) are incompatible with the new direct bcrypt implementation.

### Action Required

**For Development:**
1. Drop and recreate the database:
   ```bash
   cd infra
   docker-compose down -v
   docker-compose up -d db
   cd ../backend
   alembic upgrade head
   ```

2. Re-register test accounts via the `/register` endpoint

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
