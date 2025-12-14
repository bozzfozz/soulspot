# Table Consolidation Plan: spotify_* → soulspot_*

## Current State (REDUNDANT)

```
┌──────────────────────────────────────────────────────────────┐
│ CURRENT: Dual-Table Architecture (REDUNDANT!)                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Spotify API ──→ spotify_artists ──copy──→ soulspot_artists  │
│                  spotify_albums            soulspot_albums   │
│                  spotify_tracks            soulspot_tracks   │
│                                                              │
│  Deezer API ─────────────────────direct──→ soulspot_artists  │
│  Local Scan ─────────────────────direct──→ soulspot_artists  │
│                                                              │
│  PROBLEM: Data duplication, two sync services, complexity    │
└──────────────────────────────────────────────────────────────┘
```

## Target State (UNIFIED)

```
┌──────────────────────────────────────────────────────────────┐
│ TARGET: Single Unified Library                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Spotify API ───→ soulspot_artists (source='spotify')        │
│  Deezer API ────→ soulspot_artists (source='deezer')         │
│  Local Scan ────→ soulspot_artists (source='local')          │
│  Multi-Source ──→ soulspot_artists (source='hybrid')         │
│                                                              │
│  ProviderSyncService (replaces SpotifySyncService)           │
│  - Handles Spotify, Deezer, future providers                 │
│  - Writes ONLY to soulspot_* tables                          │
│  - source field indicates origin provider                    │
└──────────────────────────────────────────────────────────────┘
```

## Tables to KEEP

| Table | Purpose | Notes |
|-------|---------|-------|
| `soulspot_artists` | Unified artist library | Multi-provider, has `source` field |
| `soulspot_albums` | Unified album library | Multi-provider, has `source` field |
| `soulspot_tracks` | Unified track library | Multi-provider, has `source` field |
| `spotify_sessions` | OAuth browser sessions | KEEP - needed for auth |
| `spotify_tokens` | OAuth access tokens (with refresh!) | KEEP - Spotify needs refresh tokens! |
| `deezer_sessions` | OAuth session + token combined | KEEP - Deezer tokens are long-lived, no refresh needed |
| `provider_sync_status` | Sync cooldowns | RENAME from `spotify_sync_status` |

### Why no `deezer_tokens` table?
- Deezer access tokens are **long-lived** (months!)
- Deezer has **NO refresh token** - when expired, user must re-login
- Therefore `deezer_sessions` includes `access_token` field directly
- Much simpler than Spotify's OAuth with hourly token refresh

## Tables to DROP

| Table | Current Purpose | Migration |
|-------|-----------------|-----------|
| `spotify_artists` | Spotify browse cache | Migrate to `soulspot_artists` |
| `spotify_albums` | Spotify browse cache | Migrate to `soulspot_albums` |
| `spotify_tracks` | Spotify browse cache | Migrate to `soulspot_tracks` |
| `spotify_sync_status` | Sync cooldowns | RENAME to `provider_sync_status` |

## Schema Changes Required

### 1. Add sync fields to soulspot_* tables

```sql
-- soulspot_artists additions
ALTER TABLE soulspot_artists ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE soulspot_artists ADD COLUMN albums_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE soulspot_artists ADD COLUMN image_path VARCHAR(512);  -- local cached image
ALTER TABLE soulspot_artists ADD COLUMN follower_count INTEGER;

-- soulspot_albums additions  
ALTER TABLE soulspot_albums ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE soulspot_albums ADD COLUMN tracks_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE soulspot_albums ADD COLUMN image_path VARCHAR(512);  -- local cached image
ALTER TABLE soulspot_albums ADD COLUMN is_saved BOOLEAN DEFAULT FALSE;  -- user saved album

-- soulspot_tracks additions
ALTER TABLE soulspot_tracks ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE;
```

### 2. Rename sync_status table

```sql
ALTER TABLE spotify_sync_status RENAME TO provider_sync_status;
-- Add provider column if needed
ALTER TABLE provider_sync_status ADD COLUMN provider VARCHAR(32) DEFAULT 'spotify';
```

### 3. Data Migration

```sql
-- Migrate spotify_artists → soulspot_artists (if not already present)
INSERT INTO soulspot_artists (name, spotify_uri, image_url, genres, ...)
SELECT name, spotify_id as spotify_uri, image_url, genres, ...
FROM spotify_artists sa
WHERE NOT EXISTS (
    SELECT 1 FROM soulspot_artists sl 
    WHERE sl.spotify_uri = sa.spotify_id
)
ON CONFLICT DO NOTHING;

-- Similar for albums and tracks
```

### 4. Drop old tables

```sql
DROP TABLE IF EXISTS spotify_tracks CASCADE;
DROP TABLE IF EXISTS spotify_albums CASCADE;
DROP TABLE IF EXISTS spotify_artists CASCADE;
```

## Service Refactoring

### SpotifySyncService → ProviderSyncService

```python
# BEFORE: SpotifySyncService
class SpotifySyncService:
    async def sync_followed_artists(self):
        # Writes to spotify_artists
        # Then copies to soulspot_artists (redundant!)

# AFTER: ProviderSyncService  
class ProviderSyncService:
    async def sync_followed_artists(self, provider: str = "all"):
        # Writes DIRECTLY to soulspot_artists
        # No intermediate tables!
        
    async def sync_artist_albums(self, artist_id: str):
        # Writes DIRECTLY to soulspot_albums
        # Tries Spotify, falls back to Deezer
```

### Merge with FollowedArtistsService

Since `FollowedArtistsService` already writes to unified library, consider:
1. Merge `SpotifySyncService` functionality into `FollowedArtistsService`
2. Rename to `ArtistSyncService` or `ProviderSyncService`
3. One service handles all provider syncing

## Implementation Phases

### Phase 1: Schema + Models ✅ DONE
- [x] Create Alembic migration `ww34019yyz67_consolidate_spotify_tables.py`
- [x] Update `ArtistModel` with sync fields
- [x] Update `AlbumModel` with sync fields  
- [x] Update `TrackModel` with source, explicit, preview_url
- [x] Update `ui.py` New Releases to use unified models
- [x] Update `discography_service.py` to use unified models

### Phase 2: Repository Refactoring ✅ DONE
- [x] Update `SpotifyBrowseRepository` to use unified `ArtistModel`, `AlbumModel`, `TrackModel`
- [x] Update `local_library_enrichment_service.py` to use unified models
- [x] All queries now filter by `source='spotify'` instead of using separate tables

**Key changes:**
- `ProviderBrowseRepository` (formerly `SpotifyBrowseRepository`) now uses unified models with `source='spotify'` filter
- Artist/Album/Track IDs mapped via `spotify_uri` field (full URI: "spotify:artist:xxx")
- Helper methods convert Spotify IDs to URIs and vice versa

### Phase 3: Class Renaming ✅ DONE
- [x] Renamed `SpotifyBrowseRepository` → `ProviderBrowseRepository` ✅ DONE
- [x] Added backwards compatibility alias: `SpotifyBrowseRepository = ProviderBrowseRepository`
- [x] `SpotifySyncService` - KEPT AS-IS (Spotify-specific, uses SpotifyPlugin)
- [x] `SpotifySyncWorker` - KEPT AS-IS (Spotify-specific, uses SpotifyPlugin)

**Rationale for keeping Spotify-prefixed services:**
- `SpotifySyncService` uses `SpotifyPlugin` for OAuth/API calls
- `SpotifySyncWorker` orchestrates Spotify-specific sync tasks
- Future: Add `DeezerSyncService`, `TidalSyncService` for other providers
- Each provider gets its own sync service with provider-specific logic

### Phase 4: Migration + Cleanup ✅ DONE
- [x] Run Alembic migration: `alembic upgrade head`
- [x] Test all functionality
- [x] Deleted old model classes:
  - `SpotifyArtistModel` ✅ REMOVED
  - `SpotifyAlbumModel` ✅ REMOVED
  - `SpotifyTrackModel` ✅ REMOVED
- [x] Renamed `SpotifySyncStatusModel` → `ProviderSyncStatusModel`
- [x] Added backwards compatibility alias: `SpotifySyncStatusModel = ProviderSyncStatusModel`

## Completion Status: ✅ COMPLETE

All phases are complete. The table consolidation is finished:
- All Spotify data now in unified `soulspot_*` tables with `source='spotify'`
- Old `spotify_artists/albums/tracks` tables dropped
- `spotify_sync_status` renamed to `provider_sync_status`
- `SpotifyBrowseRepository` renamed to `ProviderBrowseRepository` (alias for backwards compat)
- All code updated to use unified models

## Class Naming Summary

| Old Name | New Name | Reason |
|----------|----------|--------|
| `SpotifyArtistModel` | ❌ DELETED | Use `ArtistModel` with `source='spotify'` |
| `SpotifyAlbumModel` | ❌ DELETED | Use `AlbumModel` with `source='spotify'` |
| `SpotifyTrackModel` | ❌ DELETED | Use `TrackModel` with `source='spotify'` |
| `SpotifySyncStatusModel` | `ProviderSyncStatusModel` | Multi-provider sync status |
| `SpotifyBrowseRepository` | `ProviderBrowseRepository` | Uses unified tables |
| `SpotifySyncService` | KEPT AS-IS | Spotify-specific (uses SpotifyPlugin) |
| `SpotifySyncWorker` | KEPT AS-IS | Spotify-specific (uses SpotifyPlugin) |

### Questions Answered

1. ✅ `is_saved` flag for albums? - YES, kept in unified `AlbumModel`
2. ✅ Playlists unified? - No, playlists table already multi-provider
3. ✅ Sessions merged? - No, `spotify_sessions`/`deezer_sessions` stay separate (OAuth-specific)

## Risks & Rollback

- **Risk**: Data loss during migration
- **Mitigation**: Keep old tables until verified
- **Rollback**: Restore from old tables if issues found

## Timeline

- Phase 1: 1 sprint
- Phase 2: 2 sprints  
- Phase 3: 1 sprint
- Total: ~4 sprints / 8 weeks

## Questions to Answer

1. Do we need `is_saved` flag for albums? (Saved Albums feature)
2. Should playlists also be unified? (currently separate)
3. Keep `spotify_sessions`/`deezer_sessions` separate or merge?
