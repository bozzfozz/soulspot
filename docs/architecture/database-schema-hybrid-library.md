# Database Schema: Hybrid Library System

**Purpose:** Track download states, artist completeness, and followed artists across services

**Related:** [Plugin System ADR - Appendix E](../architecture/plugin-system-adr.md#appendix-e-hybrid-library-concept)

---

## Schema Overview

```
track_download_state     ← Track availability (local/queued/missing)
     │
     ├─── tracks (existing)
     │
artist_completeness      ← Cached progress (80% complete)
     │
     ├─── artists (existing)
     │
followed_artists         ← Multi-service tracking
     │
     └─── artists (existing)
```

---

## Table: `track_download_state`

**Purpose:** Track availability and download status for each track.

### Schema

```sql
CREATE TABLE track_download_state (
    track_id UUID PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
    
    -- Availability status
    availability VARCHAR(50) NOT NULL,
    
    -- Local file information
    local_path TEXT,
    file_size_bytes BIGINT,
    file_format VARCHAR(20),                    -- 'mp3', 'flac', 'aac', etc.
    bitrate_kbps INT,
    
    -- Download tracking
    download_queued_at TIMESTAMPTZ,
    download_started_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    download_attempts INT DEFAULT 0,
    last_error TEXT,
    
    -- Soulseek search results
    soulseek_search_results_count INT,
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CHECK (availability IN ('local', 'queued', 'available', 'not_found', 'failed')),
    CHECK (file_size_bytes >= 0),
    CHECK (bitrate_kbps >= 0),
    CHECK (download_attempts >= 0)
);

-- Indexes for common queries
CREATE INDEX idx_track_download_availability 
    ON track_download_state(availability);

CREATE INDEX idx_track_download_queued 
    ON track_download_state(download_queued_at) 
    WHERE availability = 'queued';

CREATE INDEX idx_track_download_failed 
    ON track_download_state(availability, download_attempts) 
    WHERE availability = 'failed';
```

### Availability States

| State | Description | UI Display |
|-------|-------------|------------|
| `local` | File exists on disk, playable | ✅ (green) |
| `queued` | In download queue, pending | ⏳ (blue, animated) |
| `available` | Found on Soulseek, not downloaded | 🔍 (gray, can download) |
| `not_found` | Not found on Soulseek | ❓ (red, may retry later) |
| `failed` | Download failed (after retries) | ❌ (red, needs manual intervention) |

### State Transitions

```
not_found → available  (Soulseek search found results)
available → queued     (User clicked "Download")
queued → local         (Download successful)
queued → failed        (Download failed after 3 retries)
failed → queued        (User clicked "Retry Download")
local → queued         (User clicked "Re-download FLAC")
```

### Example Queries

**Get all tracks ready to download:**
```sql
SELECT t.*, tds.* 
FROM tracks t
JOIN track_download_state tds ON t.id = tds.track_id
WHERE tds.availability = 'queued'
ORDER BY tds.download_queued_at ASC
LIMIT 10;
```

**Find failed downloads needing manual review:**
```sql
SELECT t.title, t.artist, tds.last_error, tds.download_attempts
FROM tracks t
JOIN track_download_state tds ON t.id = tds.track_id
WHERE tds.availability = 'failed' 
  AND tds.download_attempts >= 3;
```

---

## Table: `artist_completeness`

**Purpose:** Pre-calculated artist download progress for fast UI rendering.

### Schema

```sql
CREATE TABLE artist_completeness (
    artist_id UUID PRIMARY KEY REFERENCES artists(id) ON DELETE CASCADE,
    
    -- Album statistics
    total_albums INT NOT NULL DEFAULT 0,
    local_albums INT NOT NULL DEFAULT 0,
    partial_albums INT NOT NULL DEFAULT 0,
    missing_albums INT NOT NULL DEFAULT 0,
    
    -- Track statistics
    total_tracks INT NOT NULL DEFAULT 0,
    local_tracks INT NOT NULL DEFAULT 0,
    queued_tracks INT NOT NULL DEFAULT 0,
    missing_tracks INT NOT NULL DEFAULT 0,
    
    -- Calculated percentages
    completeness_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,  -- 0.00 to 100.00
    
    -- Metadata
    last_calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CHECK (completeness_percent BETWEEN 0 AND 100),
    CHECK (total_albums >= 0),
    CHECK (local_albums >= 0),
    CHECK (local_albums <= total_albums),
    CHECK (total_tracks >= 0),
    CHECK (local_tracks >= 0),
    CHECK (local_tracks <= total_tracks)
);

-- Index for filtering incomplete artists
CREATE INDEX idx_artist_completeness_percent 
    ON artist_completeness(completeness_percent)
    WHERE completeness_percent < 100;

-- Index for sorting by completeness
CREATE INDEX idx_artist_completeness_sorted 
    ON artist_completeness(completeness_percent DESC);
```

### Calculation Logic

```python
def calculate_artist_completeness(artist_id: UUID) -> dict:
    """
    Calculates artist completeness statistics.
    
    Returns:
        {
            'total_albums': 20,
            'local_albums': 16,      # 100% complete albums
            'partial_albums': 2,     # 1-99% complete albums
            'missing_albums': 2,     # 0% complete albums
            'total_tracks': 225,
            'local_tracks': 180,
            'queued_tracks': 10,
            'missing_tracks': 35,
            'completeness_percent': 80.00
        }
    """
    albums = get_artist_albums(artist_id)
    
    total_albums = len(albums)
    local_albums = 0
    partial_albums = 0
    missing_albums = 0
    total_tracks = 0
    local_tracks = 0
    queued_tracks = 0
    missing_tracks = 0
    
    for album in albums:
        album_tracks = get_album_tracks(album.id)
        total_tracks += len(album_tracks)
        
        local_count = sum(1 for t in album_tracks if t.download_state.availability == 'local')
        queued_count = sum(1 for t in album_tracks if t.download_state.availability == 'queued')
        
        local_tracks += local_count
        queued_tracks += queued_count
        missing_tracks += len(album_tracks) - local_count - queued_count
        
        # Classify album completeness
        if local_count == len(album_tracks):
            local_albums += 1
        elif local_count > 0:
            partial_albums += 1
        else:
            missing_albums += 1
    
    completeness_percent = (local_tracks / total_tracks * 100) if total_tracks > 0 else 0
    
    return {
        'total_albums': total_albums,
        'local_albums': local_albums,
        'partial_albums': partial_albums,
        'missing_albums': missing_albums,
        'total_tracks': total_tracks,
        'local_tracks': local_tracks,
        'queued_tracks': queued_tracks,
        'missing_tracks': missing_tracks,
        'completeness_percent': round(completeness_percent, 2)
    }
```

### Auto-Update Trigger

**Trigger on track download state change:**
```sql
CREATE OR REPLACE FUNCTION trigger_update_artist_completeness()
RETURNS TRIGGER AS $$
BEGIN
    -- Find artist_id for this track
    WITH track_artist AS (
        SELECT DISTINCT artist_id 
        FROM tracks 
        WHERE id = NEW.track_id
    )
    -- Mark for recalculation (async job will handle actual update)
    INSERT INTO artist_completeness_recalc_queue (artist_id)
    SELECT artist_id FROM track_artist
    ON CONFLICT (artist_id) DO UPDATE SET queued_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_track_download_state_change
AFTER INSERT OR UPDATE OF availability ON track_download_state
FOR EACH ROW
EXECUTE FUNCTION trigger_update_artist_completeness();
```

### Example Queries

**Get incomplete artists sorted by percentage:**
```sql
SELECT a.name, ac.*
FROM artists a
JOIN artist_completeness ac ON a.id = ac.artist_id
WHERE ac.completeness_percent < 100
ORDER BY ac.completeness_percent DESC;
```

**Find artists with partial albums (needs attention):**
```sql
SELECT a.name, ac.partial_albums, ac.completeness_percent
FROM artists a
JOIN artist_completeness ac ON a.id = ac.artist_id
WHERE ac.partial_albums > 0
ORDER BY ac.partial_albums DESC;
```

---

## Table: `followed_artists`

**Purpose:** Track which artists user follows from which services.

### Schema

```sql
CREATE TABLE followed_artists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core references
    artist_id UUID NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    service_type VARCHAR(50) NOT NULL,
    service_artist_id VARCHAR(255) NOT NULL,
    
    -- User preferences (per service)
    auto_download_enabled BOOLEAN DEFAULT FALSE,
    monitor_new_releases BOOLEAN DEFAULT TRUE,
    quality_preference VARCHAR(50),              -- 'any', '320kbps', 'flac_only'
    
    -- Sync tracking
    followed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ,
    last_new_release_check TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE (artist_id, service_type),
    CHECK (service_type IN ('spotify', 'tidal', 'deezer')),
    CHECK (quality_preference IN ('any', '320kbps', 'flac_only') OR quality_preference IS NULL)
);

-- Indexes
CREATE INDEX idx_followed_artists_service 
    ON followed_artists(service_type);

CREATE INDEX idx_followed_artists_auto_download 
    ON followed_artists(auto_download_enabled) 
    WHERE auto_download_enabled = TRUE;

CREATE INDEX idx_followed_artists_new_release_check 
    ON followed_artists(last_new_release_check) 
    WHERE monitor_new_releases = TRUE;
```

### Settings Integration

**Global defaults (in app settings):**
```python
class FollowedArtistDefaults:
    auto_download_new_releases: bool = False
    monitor_new_releases: bool = True
    quality_preference: str = 'any'
```

**Per-artist overrides stored in `followed_artists` table.**

### Multi-Service Following

**Same artist followed on Spotify AND Tidal:**
```sql
-- Two rows in followed_artists:
INSERT INTO followed_artists (artist_id, service_type, service_artist_id)
VALUES 
    ('uuid-pink-floyd', 'spotify', 'spotify:artist:0k17h0D3J5VfsdmQ1iZtE9'),
    ('uuid-pink-floyd', 'tidal', 'tidal:artist:3950');

-- UI Badge shows: "Followed on 2 services"
```

### Example Queries

**Get all followed artists with auto-download enabled:**
```sql
SELECT a.name, fa.service_type, fa.quality_preference
FROM followed_artists fa
JOIN artists a ON fa.artist_id = a.id
WHERE fa.auto_download_enabled = TRUE;
```

**Find artists to check for new releases:**
```sql
SELECT a.name, fa.service_type, fa.last_new_release_check
FROM followed_artists fa
JOIN artists a ON fa.artist_id = a.id
WHERE fa.monitor_new_releases = TRUE
  AND (fa.last_new_release_check IS NULL 
       OR fa.last_new_release_check < NOW() - INTERVAL '1 day');
```

---

## Migration Strategy

### From Existing Schema

**Current `spotify_sessions` → new `service_sessions`:**
```sql
-- Already exists in ADR, no change needed
```

**New tables (no migration needed):**
```sql
-- Phase 1: Create new tables
CREATE TABLE track_download_state ...;
CREATE TABLE artist_completeness ...;
CREATE TABLE followed_artists ...;

-- Phase 2: Populate from existing data
-- Backfill track_download_state from local library scan
INSERT INTO track_download_state (track_id, availability, local_path, ...)
SELECT id, 'local', local_path, ... FROM tracks WHERE local_path IS NOT NULL;

-- Backfill followed_artists from current Spotify follows
INSERT INTO followed_artists (artist_id, service_type, service_artist_id, followed_at)
SELECT artist_id, 'spotify', spotify_artist_id, created_at 
FROM current_followed_artists_table;

-- Phase 3: Initial completeness calculation (async job)
-- Run calculate_artist_completeness() for all artists
```

---

## Performance Optimization

### Caching Strategy

**Artist completeness is cached:**
- Calculated once per download state change
- Queued for recalculation via `artist_completeness_recalc_queue`
- Background worker processes queue every 5 minutes

**Why cache?**
- Calculating completeness for 1000 artists = 1000+ queries (slow)
- UI needs instant rendering (<50ms)
- Progress bars don't change frequently

### Index Coverage

**Critical indexes:**
```sql
-- Filter by availability (Library filters)
idx_track_download_availability

-- Sort by completeness (UI sorting)
idx_artist_completeness_sorted

-- Find incomplete artists (default view)
idx_artist_completeness_percent WHERE completeness_percent < 100

-- New release checks (background worker)
idx_followed_artists_new_release_check WHERE monitor_new_releases = TRUE
```

---

## Data Integrity

### Orphan Prevention

**Cascade deletes:**
```sql
-- If artist deleted → followed_artists deleted
ON DELETE CASCADE

-- If track deleted → track_download_state deleted
ON DELETE CASCADE
```

### Consistency Checks

**Periodic validation:**
```sql
-- Find completeness records without artists
SELECT ac.artist_id 
FROM artist_completeness ac
LEFT JOIN artists a ON ac.artist_id = a.id
WHERE a.id IS NULL;

-- Find download states without tracks
SELECT tds.track_id
FROM track_download_state tds
LEFT JOIN tracks t ON tds.track_id = t.id
WHERE t.id IS NULL;
```

---

## Testing Data

### Seed Data (Development)

```sql
-- Artist with 100% completeness
INSERT INTO artist_completeness (artist_id, total_albums, local_albums, total_tracks, local_tracks, completeness_percent)
VALUES ('uuid-complete-artist', 10, 10, 120, 120, 100.00);

-- Artist with 50% completeness
INSERT INTO artist_completeness (artist_id, total_albums, local_albums, partial_albums, total_tracks, local_tracks, completeness_percent)
VALUES ('uuid-partial-artist', 20, 8, 6, 225, 112, 50.00);

-- Artist with 0% completeness (followed, not downloaded)
INSERT INTO artist_completeness (artist_id, total_albums, missing_albums, total_tracks, completeness_percent)
VALUES ('uuid-remote-artist', 15, 15, 180, 0.00);
```

---

## Related Documentation

- [Plugin System ADR](../architecture/plugin-system-adr.md) - Architecture decisions
- [Library Artists View](../feat-ui/library-artists-view.md) - UI mockups
- [Migration Guide](./migrations/README.md) - How to upgrade database

---

**Last Updated:** 2025-12-10  
**Schema Version:** 2.0  
**Status:** Design Approved, Awaiting Implementation
