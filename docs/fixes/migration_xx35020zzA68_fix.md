# Migration xx35020zzA68 Fix

## Problem

The migration `xx35020zzA68_rename_image_url_to_artwork_url.py` was failing during Docker container startup with:

```
sqlite3.OperationalError: table _alembic_tmp_soulspot_artists already exists
```

## Root Cause

SQLite doesn't support direct column renaming, so Alembic uses "batch operations" that:
1. Create a temporary table with the new schema (`_alembic_tmp_*`)
2. Copy data from the original table
3. Drop the original table
4. Rename the temporary table

If the migration fails at step 3 or 4, the temporary table remains in the database. When the migration is retried, step 1 fails because the temporary table already exists.

## Solution

The migration has been enhanced with:

### 1. Automatic Cleanup of Orphaned Tables

Before attempting any batch operations, the migration now:
- Scans for tables starting with `_alembic_tmp_`
- Drops them automatically
- Logs the cleanup action

### 2. Idempotency Checks

The migration checks if columns already exist before attempting to rename them:
- If source column exists → perform rename
- If target column exists → skip rename (already done)
- If neither exists → log warning (unexpected state)

### 3. Helpful Logging

The migration now prints what it's doing:
```
Cleaning up orphaned table: _alembic_tmp_soulspot_artists
Renaming soulspot_artists.image_url → artwork_url
Column playlists.artwork_url already exists - skipping rename
```

## Files Changed

1. **alembic/versions/xx35020zzA68_rename_image_url_to_artwork_url.py**
   - Added `_cleanup_orphaned_tables()` helper
   - Added `_column_exists()` helper
   - Enhanced `upgrade()` with cleanup and checks
   - Enhanced `downgrade()` with cleanup and checks
   - Fixed table name: `playlists` not `soulspot_playlists`

2. **docs/development/MIGRATION_BEST_PRACTICES.md** (NEW)
   - Explains the root cause
   - Provides reusable patterns for future migrations
   - Documents testing and debugging procedures

3. **scripts/verify_migration_xx35020zzA68.sh** (NEW)
   - Automated test script for the migration
   - Tests fresh database, idempotency, and cleanup

## Testing

### Manual Testing

```bash
# Test the migration
cd /home/runner/work/soulspot/soulspot
./scripts/verify_migration_xx35020zzA68.sh
```

### In Docker

The migration will now succeed even if:
- It's being run for the first time
- It previously failed and is being retried
- It was partially applied
- Orphaned tables exist from previous failures

## Migration Details

### Tables Affected

1. **soulspot_artists**
   - Rename: `image_url` → `artwork_url`
   - Type: VARCHAR(512), nullable

2. **playlists**
   - Rename: `cover_url` → `artwork_url`
   - Type: VARCHAR(512), nullable

### Reversibility

The migration is fully reversible:
```bash
alembic downgrade -1
```

The downgrade also includes cleanup and idempotency checks.

## Impact

✅ **Immediate:** Fixes Docker container startup failure  
✅ **Short-term:** Makes this specific migration resilient  
✅ **Long-term:** Provides pattern for all future SQLite migrations  

## Best Practices Established

Going forward, all SQLite batch migrations should:
1. Clean up orphaned tables before operations
2. Check column/table existence before modifications
3. Be idempotent (safe to run multiple times)
4. Log their actions for debugging

See `docs/development/MIGRATION_BEST_PRACTICES.md` for complete guidelines.

## Verification

After deployment, verify the migration succeeded:

```bash
# Check current migration version
alembic current

# Expected output:
# xx35020zzA68 (head)

# Verify schema
sqlite3 /config/soulspot.db ".schema soulspot_artists" | grep artwork_url
sqlite3 /config/soulspot.db ".schema playlists" | grep artwork_url
```

Both should show `artwork_url` columns.

## Troubleshooting

If the migration still fails:

1. **Manual cleanup:**
   ```bash
   sqlite3 /config/soulspot.db
   > DROP TABLE IF EXISTS _alembic_tmp_soulspot_artists;
   > DROP TABLE IF EXISTS _alembic_tmp_playlists;
   > .quit
   ```

2. **Check current state:**
   ```bash
   sqlite3 /config/soulspot.db ".schema soulspot_artists"
   ```

3. **Retry migration:**
   ```bash
   alembic upgrade head
   ```

## Related Documentation

- [Migration Best Practices](../docs/development/MIGRATION_BEST_PRACTICES.md)
- [Alembic Batch Operations](https://alembic.sqlalchemy.org/en/latest/batch.html)
- [SQLite ALTER TABLE Limitations](https://www.sqlite.org/lang_altertable.html)
