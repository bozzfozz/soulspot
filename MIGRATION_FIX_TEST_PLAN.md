# Migration & Code Fixes - Test Plan

## Overview
This document describes the fixes applied to resolve Docker container startup failures related to database schema mismatches and invalid model field usage.

## Issues Fixed

### 1. Database Schema Issues
**Problem:** Migration claimed to rename columns but database didn't have the new columns
- `soulspot_artists.artwork_url` missing (tried to select but column doesn't exist)
- `playlists.artwork_url` missing (tried to select but column doesn't exist)

**Root Cause:** SQLite's ALTER TABLE limitations caused batch operations to fail silently

**Fix Applied:** Enhanced migration with:
- `recreate="always"` strategy for reliable SQLite batch operations
- Fallback column creation if neither old nor new column exists
- Cleanup of orphaned `_alembic_tmp_*` tables
- Idempotency checks using `_column_exists()` helper

### 2. DeezerPlugin Method Name
**Problem:** `AttributeError: 'DeezerPlugin' object has no attribute '_convert_artist_to_dto'`

**Root Cause:** Method was called with wrong name (line 1342)

**Fix Applied:** Changed `_convert_artist_to_dto` to `_convert_artist` (correct method name)

### 3. DeezerSyncService Invalid Model Fields
**Problem:** `TypeError: 'is_chart' is an invalid keyword argument for TrackModel`

**Root Cause:** Code was trying to use fields that don't exist in the database models:
- `ArtistModel`: `is_chart`, `is_related`
- `AlbumModel`: `is_chart`, `is_new_release`, `name` (should be `title`)
- `TrackModel`: `is_chart`, `is_top_track`, `is_saved`

**Fix Applied:** 
- Removed all invalid field assignments
- Changed `existing.name` to `existing.title` for AlbumModel
- Added warnings for missing artist_id context
- Updated docstrings to note flag parameters kept for API compatibility

## Test Scenarios

### Scenario 1: Fresh Database (New Installation)
**Setup:**
```bash
# Delete existing database
rm -f /config/soulspot.db

# Start container
docker-compose up
```

**Expected Results:**
- ✅ All migrations run successfully
- ✅ `soulspot_artists` table has `artwork_url` column
- ✅ `playlists` table has `artwork_url` column
- ✅ All workers start without errors
- ✅ No `OperationalError: no such column` errors

### Scenario 2: Existing Database (Upgrade)
**Setup:**
```bash
# Use existing database with old schema (image_url/cover_url)
# Start container
docker-compose up
```

**Expected Results:**
- ✅ Migration detects `image_url` column in `soulspot_artists`
- ✅ Column renamed to `artwork_url` using batch recreate strategy
- ✅ Migration detects `cover_url` column in `playlists`
- ✅ Column renamed to `artwork_url` using batch recreate strategy
- ✅ All workers start without errors
- ✅ Existing data preserved in renamed columns

### Scenario 3: Partially Migrated Database
**Setup:**
```bash
# Database where migration partially succeeded
# (e.g., artists.artwork_url exists but playlists.cover_url still exists)
docker-compose up
```

**Expected Results:**
- ✅ Migration detects existing `artwork_url` in artists table
- ✅ Skips rename for artists (already migrated)
- ✅ Renames `cover_url` to `artwork_url` in playlists
- ✅ No duplicate column errors
- ✅ All workers start successfully

### Scenario 4: Inconsistent Database State
**Setup:**
```bash
# Database where neither old nor new column exists
# (rare edge case, possibly from manual schema changes)
docker-compose up
```

**Expected Results:**
- ✅ Migration detects missing columns
- ✅ Creates `artwork_url` column in affected tables
- ✅ Logs warning about missing columns
- ✅ Application continues to run
- ✅ New data can be saved successfully

### Scenario 5: Worker Functionality
**Setup:**
```bash
# Start container with valid configuration
docker-compose up
```

**Expected Results:**
- ✅ Token Refresh Worker starts
- ✅ Spotify Sync Worker starts
- ✅ **Deezer Sync Worker starts** (critical test)
- ✅ New Releases Sync Worker starts
- ✅ Download Monitor Worker starts
- ✅ All automation workers start
- ✅ No `AttributeError` from DeezerPlugin
- ✅ No `TypeError` about invalid keyword arguments

### Scenario 6: Deezer Charts Sync
**Setup:**
```bash
# Container running, trigger Deezer charts sync
# This happens automatically every 60s
```

**Expected Results:**
- ✅ Charts sync completes without errors
- ✅ Tracks saved to database (even if 0 due to missing artist_id)
- ✅ Albums saved to database (even if 0 due to missing artist_id)
- ✅ Artists saved to database with only valid fields
- ✅ No `'is_chart' is an invalid keyword argument` errors
- ✅ No `'name' is an invalid keyword argument` errors

## Validation Queries

### Check Column Existence
```sql
-- Check soulspot_artists columns
PRAGMA table_info(soulspot_artists);
-- Should see 'artwork_url' column (NOT 'image_url')

-- Check playlists columns
PRAGMA table_info(playlists);
-- Should see 'artwork_url' column (NOT 'cover_url')
```

### Check Migration History
```sql
-- Check alembic version
SELECT * FROM alembic_version;
-- Should show: xx35020zzA68
```

### Check Worker Status in Logs
```bash
docker-compose logs | grep -E "(✅|ERROR|WARNING)" | tail -100
```

**Expected Log Patterns:**
```
✅ Token Refresh Started
✅ Spotify Sync Started
✅ Deezer Sync Started
✅ New Releases Sync Started
```

**Should NOT see:**
```
ERROR: no such column: soulspot_artists.artwork_url
ERROR: no such column: playlists.artwork_url
ERROR: 'DeezerPlugin' object has no attribute '_convert_artist_to_dto'
ERROR: 'is_chart' is an invalid keyword argument
ERROR: 'name' is an invalid keyword argument
```

## Files Changed

### 1. DeezerPlugin
**File:** `src/soulspot/infrastructure/plugins/deezer_plugin.py`
**Line:** 1342
**Change:** `_convert_artist_to_dto` → `_convert_artist`

### 2. DeezerSyncService
**File:** `src/soulspot/application/services/deezer_sync_service.py`
**Changes:**
- Lines 467-480: Removed invalid ArtistModel fields
- Lines 502-524: Removed invalid AlbumModel fields, changed `name` to `title`
- Lines 553-573: Removed invalid TrackModel fields

### 3. Migration
**File:** `alembic/versions/xx35020zzA68_rename_image_url_to_artwork_url.py`
**Changes:**
- Lines 93-96: Added `recreate="always"` for soulspot_artists
- Lines 107-112: Added fallback column creation for artists
- Lines 120-125: Added `recreate="always"` for playlists
- Lines 135-140: Added fallback column creation for playlists

## Rollback Plan

If issues occur after applying these fixes:

### Option 1: Revert to Previous Database State
```bash
# Restore database backup
cp /config/soulspot.db.backup /config/soulspot.db

# Downgrade migration
docker exec soulspot_bridge alembic downgrade -1

# Restart container
docker-compose restart
```

### Option 2: Fresh Start
```bash
# Delete database
rm -f /config/soulspot.db

# Restart container (will run migrations from scratch)
docker-compose restart
```

### Option 3: Manual Schema Fix
```sql
-- Add missing columns manually
ALTER TABLE soulspot_artists ADD COLUMN artwork_url VARCHAR(512);
ALTER TABLE playlists ADD COLUMN artwork_url VARCHAR(512);

-- Copy data from old columns if they exist
UPDATE soulspot_artists SET artwork_url = image_url WHERE image_url IS NOT NULL;
UPDATE playlists SET artwork_url = cover_url WHERE cover_url IS NOT NULL;
```

## Success Criteria

The fix is considered successful when:

1. ✅ Container starts without errors
2. ✅ All workers start successfully
3. ✅ No `OperationalError: no such column` errors in logs
4. ✅ No `AttributeError` from DeezerPlugin in logs
5. ✅ No `TypeError: invalid keyword argument` errors in logs
6. ✅ Deezer sync worker completes its cycle
7. ✅ Database schema matches model definitions
8. ✅ New data can be saved successfully

## Known Limitations

1. **Album/Track Creation:** DeezerSyncService will log warnings when trying to create albums/tracks without artist_id. This is expected behavior - the sync methods that call these helpers need to provide proper artist context.

2. **Flag Parameters:** The `is_chart`, `is_new_release`, etc. parameters are kept in method signatures for API compatibility but are not stored in the database. If these flags need to be persisted in the future, new database columns must be added first.

3. **SQLite Limitations:** Column renaming in SQLite requires full table recreation. The `recreate="always"` strategy handles this but may be slower for large tables.

## Future Improvements

If chart/new release tracking is needed:

1. Add proper columns to models:
   ```python
   # models.py
   is_chart: Mapped[bool] = mapped_column(default=False, nullable=False)
   is_new_release: Mapped[bool] = mapped_column(default=False, nullable=False)
   ```

2. Create migration to add columns:
   ```python
   op.add_column('soulspot_tracks', sa.Column('is_chart', sa.Boolean(), default=False))
   op.add_column('soulspot_albums', sa.Column('is_new_release', sa.Boolean(), default=False))
   ```

3. Update DeezerSyncService to use the new columns

## Contact

For issues or questions about these fixes, refer to:
- GitHub Issue: [Link to issue]
- PR: [Link to PR]
- Architecture Guide: `docs/architecture/DATA_LAYER_PATTERNS.md`
