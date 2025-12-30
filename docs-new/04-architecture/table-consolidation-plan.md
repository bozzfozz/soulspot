# Table Consolidation Plan

**Category:** Architecture  
**Status:** PLANNED 📋  
**Last Updated:** 2025-01-XX  
**Priority:** MEDIUM - Technical debt reduction  
**Related Docs:** [Database Schema](./database-schema-hybrid-library.md) | [Service Agnostic Backend](./service-agnostic-backend.md)

---

## Problem: Redundant spotify_* Tables

### Current State (REDUNDANT)

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

**Issues:**
- **Data duplication:** Same artist exists in both `spotify_artists` and `soulspot_artists`
- **Sync complexity:** Two-step process (Spotify → spotify_* → soulspot_*)
- **Inconsistency risk:** Intermediate tables can get out of sync
- **Extra storage:** Redundant data consumes disk space
- **Maintenance burden:** Migrations must update both table sets

---

### Target State (UNIFIED)

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

---

## Tables to KEEP

| Table | Purpose | Notes |
|-------|---------|-------|
| `soulspot_artists` | Unified artist library | Multi-provider, has `source` field |
| `soulspot_albums` | Unified album library | Multi-provider, has `source` field |
| `soulspot_tracks` | Unified track library | Multi-provider, has `source` field |
| `spotify_sessions` | OAuth browser sessions | KEEP - needed for auth |
| `spotify_tokens` | OAuth access tokens with refresh | KEEP - Spotify needs refresh tokens! |
| `deezer_sessions` | OAuth session + token combined | KEEP - Deezer tokens are long-lived |
| `provider_sync_status` | Sync cooldowns | RENAME from `spotify_sync_status` |

---

### Why Keep Separate Token Tables?

**Spotify Tokens (`spotify_tokens`):**
- Spotify access tokens expire **hourly**
- Requires **refresh token** to get new access token
- Complex OAuth flow with token rotation
- Separate table justified for refresh token management

**Deezer Sessions (`deezer_sessions`):**
- Deezer access tokens are **long-lived** (months!)
- Deezer has **NO refresh token** mechanism
- When expired, user must re-login manually
- `access_token` stored directly in `deezer_sessions` table
- Much simpler than Spotify's OAuth

**Key Difference:**
```
Spotify: hourly refresh → separate tokens table needed
Deezer:  monthly re-auth → token in sessions table OK
```

---

## Tables to DROP

| Table | Current Purpose | Migration Path |
|-------|-----------------|----------------|
| `spotify_artists` | Spotify browse cache | Migrate data → DROP |
| `spotify_albums` | Spotify browse cache | Migrate data → DROP |
| `spotify_tracks` | Spotify browse cache | Migrate data → DROP |
| `spotify_sync_status` | Sync cooldowns | RENAME to `provider_sync_status` |

---

## Schema Changes Required

### Step 1: Add Sync Fields to soulspot_* Tables

```sql
-- soulspot_artists additions
ALTER TABLE soulspot_artists 
    ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS albums_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS image_path VARCHAR(512),     -- local cached image
    ADD COLUMN IF NOT EXISTS follower_count INTEGER;

CREATE INDEX idx_artists_last_synced 
    ON soulspot_artists(last_synced_at);

-- soulspot_albums additions  
ALTER TABLE soulspot_albums 
    ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS tracks_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS image_path VARCHAR(512),     -- local cached image
    ADD COLUMN IF NOT EXISTS is_saved BOOLEAN DEFAULT FALSE;  -- user saved album

CREATE INDEX idx_albums_last_synced 
    ON soulspot_albums(last_synced_at);

-- soulspot_tracks additions
ALTER TABLE soulspot_tracks 
    ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;

CREATE INDEX idx_tracks_last_synced 
    ON soulspot_tracks(last_synced_at);
```

**Purpose:**
- `last_synced_at`: Track when entity was last updated from provider
- `albums_synced_at`: Track when artist's albums were last synced
- `tracks_synced_at`: Track when album's tracks were last synced
- `image_path`: Local cached image (WebP format)
- `follower_count`: Spotify/Deezer follower count
- `is_saved`: User saved this album (Spotify "Saved Albums")

---

### Step 2: Rename Sync Status Table

```sql
-- Rename table
ALTER TABLE spotify_sync_status 
    RENAME TO provider_sync_status;

-- Add provider column (if not exists)
ALTER TABLE provider_sync_status 
    ADD COLUMN IF NOT EXISTS provider VARCHAR(32) DEFAULT 'spotify';

-- Add index for provider filtering
CREATE INDEX idx_provider_sync_provider 
    ON provider_sync_status(provider);
```

**Schema:**
```sql
CREATE TABLE provider_sync_status (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,      -- 'artist', 'album', 'track', 'playlist'
    entity_id VARCHAR(255) NOT NULL,       -- Service-specific ID
    provider VARCHAR(32) NOT NULL,         -- 'spotify', 'deezer', 'tidal'
    last_sync_at TIMESTAMPTZ NOT NULL,
    next_sync_allowed_at TIMESTAMPTZ NOT NULL,
    
    UNIQUE(provider, entity_type, entity_id)
);
```

---

### Step 3: Data Migration

```sql
-- Migrate spotify_artists → soulspot_artists (avoid duplicates)
INSERT INTO soulspot_artists (
    name, spotify_uri, image_url, genres, 
    follower_count, last_synced_at
)
SELECT 
    name, 
    spotify_id as spotify_uri, 
    image_url, 
    genres, 
    follower_count,
    NOW() as last_synced_at
FROM spotify_artists sa
WHERE NOT EXISTS (
    SELECT 1 FROM soulspot_artists sl 
    WHERE sl.spotify_uri = sa.spotify_id
)
ON CONFLICT (spotify_uri) DO UPDATE SET
    image_url = EXCLUDED.image_url,
    genres = EXCLUDED.genres,
    follower_count = EXCLUDED.follower_count,
    last_synced_at = EXCLUDED.last_synced_at;

-- Similar for albums
INSERT INTO soulspot_albums (
    title, spotify_uri, release_date, total_tracks,
    cover_url, artist_id, last_synced_at
)
SELECT 
    title,
    spotify_id as spotify_uri,
    release_date,
    total_tracks,
    cover_url,
    (SELECT id FROM soulspot_artists WHERE spotify_uri = sa.artist_spotify_id),
    NOW() as last_synced_at
FROM spotify_albums sa
WHERE NOT EXISTS (
    SELECT 1 FROM soulspot_albums sl 
    WHERE sl.spotify_uri = sa.spotify_id
)
ON CONFLICT (spotify_uri) DO UPDATE SET
    cover_url = EXCLUDED.cover_url,
    total_tracks = EXCLUDED.total_tracks,
    last_synced_at = EXCLUDED.last_synced_at;

-- Similar for tracks (ISRC deduplication!)
INSERT INTO soulspot_tracks (
    title, isrc, spotify_uri, duration_ms, 
    explicit, artist_id, album_id, last_synced_at
)
SELECT 
    title,
    isrc,
    spotify_id as spotify_uri,
    duration_ms,
    explicit,
    (SELECT id FROM soulspot_artists WHERE spotify_uri = st.artist_spotify_id),
    (SELECT id FROM soulspot_albums WHERE spotify_uri = st.album_spotify_id),
    NOW() as last_synced_at
FROM spotify_tracks st
WHERE NOT EXISTS (
    -- Prefer ISRC match over Spotify URI match
    SELECT 1 FROM soulspot_tracks sl 
    WHERE (st.isrc IS NOT NULL AND sl.isrc = st.isrc)
       OR sl.spotify_uri = st.spotify_id
)
ON CONFLICT (isrc) DO UPDATE SET
    spotify_uri = EXCLUDED.spotify_uri,
    duration_ms = EXCLUDED.duration_ms,
    last_synced_at = EXCLUDED.last_synced_at
WHERE soulspot_tracks.spotify_uri IS NULL;  -- Only update if Spotify URI not set
```

**Migration Notes:**
- Use `ON CONFLICT DO UPDATE` to handle existing entities
- Prioritize ISRC matches for tracks (universal identifier)
- Set `last_synced_at = NOW()` to mark migration timestamp
- Link foreign keys via service URIs

---

### Step 4: Drop Old Tables

```sql
-- Drop old Spotify cache tables (after migration verified!)
DROP TABLE IF EXISTS spotify_tracks CASCADE;
DROP TABLE IF EXISTS spotify_albums CASCADE;
DROP TABLE IF EXISTS spotify_artists CASCADE;
```

**⚠️ CRITICAL:** Only drop after verifying migration success!

---

## Service Refactoring

### Before: SpotifySyncService (Redundant)

```python
class SpotifySyncService:
    async def sync_followed_artists(self):
        """Sync followed artists - TWO steps!"""
        # Step 1: Write to spotify_artists
        spotify_artists = await self._spotify.get_followed_artists()
        for artist in spotify_artists:
            await self._spotify_artist_repo.create(artist)
        
        # Step 2: Copy to soulspot_artists (redundant!)
        for artist in spotify_artists:
            soulspot_artist = self._convert_to_soulspot_artist(artist)
            await self._soulspot_artist_repo.create(soulspot_artist)
```

**Problems:**
- Two database writes per artist
- Data duplication risk
- Extra complexity

---

### After: ProviderSyncService (Unified)

```python
class ProviderSyncService:
    """Generic provider sync service (Spotify, Deezer, Tidal)."""
    
    async def sync_followed_artists(
        self,
        provider: str = "all",
    ) -> list[Artist]:
        """Sync followed artists - ONE step!"""
        artists = []
        
        # Spotify
        if provider in ("all", "spotify") and self._spotify.is_authenticated():
            spotify_artists = await self._spotify_plugin.get_followed_artists()
            for artist_dto in spotify_artists.items:
                # Write DIRECTLY to soulspot_artists
                artist = await self._import_artist(artist_dto, source="spotify")
                artists.append(artist)
        
        # Deezer
        if provider in ("all", "deezer") and self._deezer.is_authenticated():
            deezer_artists = await self._deezer_plugin.get_followed_artists()
            for artist_dto in deezer_artists.items:
                artist = await self._import_artist(artist_dto, source="deezer")
                artists.append(artist)
        
        return artists
    
    async def _import_artist(
        self,
        artist_dto: ArtistDTO,
        source: str,
    ) -> Artist:
        """Import artist with deduplication."""
        # Check if exists (by service URI or MusicBrainz ID)
        existing = await self._find_existing_artist(artist_dto)
        
        if existing:
            # Update existing artist with new data
            await self._update_artist(existing, artist_dto, source)
            return existing
        
        # Create new artist
        artist = Artist(
            id=uuid4(),
            name=artist_dto.name,
            spotify_uri=artist_dto.spotify_id,
            deezer_id=artist_dto.deezer_id,
            genres=artist_dto.genres,
            image_url=artist_dto.image_url,
            follower_count=artist_dto.follower_count,
            source=source,
            last_synced_at=datetime.now(timezone.utc),
        )
        await self._artist_repo.create(artist)
        return artist
```

**Benefits:**
- One database write per artist
- No data duplication
- Works with any provider
- Unified deduplication logic

---

## Implementation Phases

### Phase 1: Schema Changes (1 day)

1. Add sync fields to `soulspot_*` tables
2. Rename `spotify_sync_status` → `provider_sync_status`
3. Run Alembic migration

---

### Phase 2: Data Migration (1-2 days)

1. Write migration script (SQL above)
2. Test migration on dev database
3. Run migration on production
4. Verify data integrity (spot checks)

---

### Phase 3: Service Refactoring (3-5 days)

1. Create `ProviderSyncService`
2. Update `SpotifySyncService` to use unified tables
3. Update `DeezerSyncService` to use unified tables
4. Update all routes to use new service
5. Test full sync workflows

---

### Phase 4: Cleanup (1 day)

1. Verify all code uses `soulspot_*` tables only
2. Drop old `spotify_*` tables
3. Remove deprecated services
4. Update documentation

---

## Benefits

### Storage Savings

**Before:**
```
spotify_artists:  1000 rows × 2 KB = 2 MB
soulspot_artists: 1000 rows × 2 KB = 2 MB
Total: 4 MB (50% redundant!)
```

**After:**
```
soulspot_artists: 1000 rows × 2 KB = 2 MB
Total: 2 MB (50% savings)
```

For large libraries (10,000+ artists), savings are significant.

---

### Sync Performance

**Before:**
```
Sync 100 artists:
- Write 100 rows to spotify_artists
- Write 100 rows to soulspot_artists
Total: 200 DB writes
```

**After:**
```
Sync 100 artists:
- Write 100 rows to soulspot_artists
Total: 100 DB writes (50% faster!)
```

---

### Code Simplicity

**Before:**
- `SpotifySyncService` (1839 LOC)
- `SpotifyArtistRepository`
- `SoulspotArtistRepository`
- Two sets of models (`SpotifyArtistModel`, `ArtistModel`)

**After:**
- `ProviderSyncService` (unified, ~500 LOC)
- `ArtistRepository` (one repo)
- One model (`ArtistModel`)

---

## Migration Checklist

- [ ] **Phase 1: Schema Changes**
  - [ ] Add sync fields to `soulspot_artists`
  - [ ] Add sync fields to `soulspot_albums`
  - [ ] Add sync fields to `soulspot_tracks`
  - [ ] Rename `spotify_sync_status` → `provider_sync_status`
  - [ ] Create Alembic migration
  - [ ] Run migration on dev environment

- [ ] **Phase 2: Data Migration**
  - [ ] Write migration SQL script
  - [ ] Test migration on dev database
  - [ ] Verify data integrity (spot checks)
  - [ ] Run migration on production
  - [ ] Backup old tables (before dropping)

- [ ] **Phase 3: Service Refactoring**
  - [ ] Create `ProviderSyncService`
  - [ ] Update `SpotifySyncService` consumers
  - [ ] Update `DeezerSyncService` consumers
  - [ ] Update all routes
  - [ ] Test full sync workflows (Spotify + Deezer)

- [ ] **Phase 4: Cleanup**
  - [ ] Verify no code references `spotify_*` tables
  - [ ] Drop `spotify_artists` table
  - [ ] Drop `spotify_albums` table
  - [ ] Drop `spotify_tracks` table
  - [ ] Remove deprecated services
  - [ ] Update documentation

---

## Related Documentation

- **[Database Schema](./database-schema-hybrid-library.md)** - Unified library schema
- **[Service Agnostic Backend](./service-agnostic-backend.md)** - Multi-service architecture
- **[Transaction Patterns](./transaction-patterns.md)** - Migration transaction handling

---

**Status:** 📋 PLANNED - Not yet implemented  
**Priority:** MEDIUM - Technical debt, not blocking features  
**Estimated Effort:** 6-9 days total  
**Risk:** MEDIUM - Data migration requires careful testing
