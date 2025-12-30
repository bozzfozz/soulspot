# Database Schema: Hybrid Library System

**Category:** Architecture  
**Status:** IMPLEMENTED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Plugin System ADR](./plugin-system-adr.md) | [Data Standards](./data-standards.md)

---

## Overview

The Hybrid Library System tracks download states, artist completeness, and followed artists across multiple music services.

**Key Tables:**
1. **`track_download_state`** - Track availability (local/queued/missing)
2. **`artist_completeness`** - Cached progress (80% complete)
3. **`followed_artists`** - Multi-service tracking

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
    file_format VARCHAR(20),                    -- 'mp3', 'flac', 'aac'
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
    CHECK (availability IN ('local', 'queued', 'available', 'not_found', 'failed'))
);

-- Indexes
CREATE INDEX idx_track_download_availability 
    ON track_download_state(availability);

CREATE INDEX idx_track_download_queued 
    ON track_download_state(download_queued_at) 
    WHERE availability = 'queued';
```

---

### Availability States

| State | Description | UI Display |
|-------|-------------|------------|
| `local` | File exists on disk, playable | ✅ (green) |
| `queued` | In download queue, pending | ⏳ (blue, animated) |
| `available` | Found on Soulseek, not downloaded | 🔍 (gray, can download) |
| `not_found` | Not found on Soulseek | ❓ (red, may retry later) |
| `failed` | Download failed (after retries) | ❌ (red, manual intervention) |

---

### State Transitions

```
not_found → available  (Soulseek search found results)
available → queued     (User clicked "Download")
queued → local         (Download successful)
queued → failed        (Download failed after 3 retries)
failed → queued        (User clicked "Retry Download")
local → queued         (User clicked "Re-download FLAC")
```

---

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

**Find failed downloads:**
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
    
    -- Calculated percentage
    completeness_percent DECIMAL(5,2) NOT NULL DEFAULT 0.00,  -- 0.00 to 100.00
    
    -- Metadata
    last_calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CHECK (completeness_percent BETWEEN 0 AND 100),
    CHECK (local_albums <= total_albums),
    CHECK (local_tracks <= total_tracks)
);

-- Indexes
CREATE INDEX idx_artist_completeness_percent 
    ON artist_completeness(completeness_percent)
    WHERE completeness_percent < 100;
```

---

### Calculation Logic

```python
def calculate_artist_completeness(artist_id: UUID) -> dict:
    """Calculate artist completeness statistics.
    
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
    
    for album in albums:
        album_tracks = get_album_tracks(album.id)
        total_tracks += len(album_tracks)
        
        local_count = sum(
            1 for t in album_tracks 
            if t.download_state.availability == 'local'
        )
        queued_count = sum(
            1 for t in album_tracks 
            if t.download_state.availability == 'queued'
        )
        
        local_tracks += local_count
        queued_tracks += queued_count
        
        # Classify album completeness
        if local_count == len(album_tracks):
            local_albums += 1
        elif local_count > 0:
            partial_albums += 1
        else:
            missing_albums += 1
    
    missing_tracks = total_tracks - local_tracks - queued_tracks
    completeness_percent = (
        (local_tracks / total_tracks * 100) 
        if total_tracks > 0 else 0
    )
    
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

---

### Auto-Update Strategy

**Trigger on track download state change:**

```python
# Background worker approach (preferred over DB triggers)
async def on_track_download_complete(track_id: UUID):
    """Update artist completeness when track download completes."""
    track = await track_repo.get_by_id(track_id)
    artist_id = track.artist_id
    
    # Queue recalculation (async)
    await queue_artist_completeness_update(artist_id)

# Dedicated worker processes queue
async def artist_completeness_worker():
    """Process artist completeness updates."""
    while True:
        artist_id = await dequeue_artist_completeness_update()
        if artist_id:
            stats = calculate_artist_completeness(artist_id)
            await artist_completeness_repo.upsert(artist_id, stats)
        
        await asyncio.sleep(1)
```

**Why worker instead of trigger?**
- No database overhead
- Can batch updates
- Easier to monitor/debug
- Can retry on failure

---

### Example Queries

**Get incomplete artists sorted by percentage:**
```sql
SELECT a.name, ac.*
FROM artists a
JOIN artist_completeness ac ON a.id = ac.artist_id
WHERE ac.completeness_percent < 100
ORDER BY ac.completeness_percent DESC;
```

**Find artists with partial albums:**
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
    service_type VARCHAR(50) NOT NULL,          -- 'spotify', 'deezer', 'tidal'
    service_artist_id VARCHAR(255) NOT NULL,    -- Service-specific ID
    
    -- Follow metadata
    followed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(artist_id, service_type),            -- One follow per service
    CHECK (service_type IN ('spotify', 'deezer', 'tidal'))
);

-- Indexes
CREATE INDEX idx_followed_artists_service 
    ON followed_artists(service_type);

CREATE INDEX idx_followed_artists_synced 
    ON followed_artists(last_synced_at);
```

---

### Multi-Service Support

**Example:** User follows "Queen" on both Spotify and Deezer:

```sql
-- Artist exists once
INSERT INTO artists (id, name, musicbrainz_id)
VALUES ('uuid-1', 'Queen', 'mbid-123');

-- Followed on both services
INSERT INTO followed_artists (artist_id, service_type, service_artist_id)
VALUES 
    ('uuid-1', 'spotify', 'spotify:artist:1dfeR4HaWDbWqFHLkxsg1d'),
    ('uuid-1', 'deezer', '412');

-- Query: Artists followed on ANY service
SELECT DISTINCT a.*
FROM artists a
JOIN followed_artists fa ON a.id = fa.artist_id;

-- Query: Artists followed on Spotify only
SELECT a.*
FROM artists a
JOIN followed_artists fa ON a.id = fa.artist_id
WHERE fa.service_type = 'spotify';

-- Query: Artists followed on BOTH Spotify and Deezer
SELECT a.*
FROM artists a
WHERE EXISTS (
    SELECT 1 FROM followed_artists 
    WHERE artist_id = a.id AND service_type = 'spotify'
)
AND EXISTS (
    SELECT 1 FROM followed_artists 
    WHERE artist_id = a.id AND service_type = 'deezer'
);
```

---

## Usage Patterns

### Track Download Workflow

```python
# 1. User browses albums, sees download status
album = await album_repo.get_by_id(album_id)
tracks = await track_repo.get_by_album_id(album_id)

for track in tracks:
    # Load download state (cached)
    state = await download_state_repo.get_by_track_id(track.id)
    track.download_state = state  # 'local', 'queued', etc.

# 2. User clicks "Download Album"
for track in tracks:
    if track.download_state.availability != 'local':
        await download_manager.queue_download(track.id)
        # Updates availability to 'queued'

# 3. Background worker processes queue
async def download_worker():
    while True:
        track_id = await download_queue.pop()
        
        # Search Soulseek
        results = await slskd.search_track(track_id)
        
        if results:
            # Download best result
            file_path = await slskd.download(results[0])
            
            # Update state
            await download_state_repo.update(track_id, {
                'availability': 'local',
                'local_path': file_path,
                'downloaded_at': datetime.now(timezone.utc)
            })
            
            # Trigger artist completeness update
            await queue_artist_completeness_update(track.artist_id)
        else:
            # Not found
            await download_state_repo.update(track_id, {
                'availability': 'not_found'
            })
```

---

### Artist Completeness Display

```python
# Artist detail page
artist = await artist_repo.get_by_id(artist_id)
completeness = await artist_completeness_repo.get_by_artist_id(artist_id)

# Render progress bar
progress_html = f"""
<div class="progress-bar">
    <div class="progress" style="width: {completeness.completeness_percent}%">
        {completeness.completeness_percent:.1f}%
    </div>
</div>
<div class="stats">
    <span>{completeness.local_tracks}/{completeness.total_tracks} tracks</span>
    <span>{completeness.local_albums}/{completeness.total_albums} albums</span>
</div>
"""
```

---

## Related Documentation

- **[Plugin System ADR](./plugin-system-adr.md)** - Multi-service architecture (Appendix E)
- **[Data Standards](./data-standards.md)** - DTO/Entity definitions
- **[Download Manager](./download-manager.md)** - Download queue implementation

---

**Status:** ✅ IMPLEMENTED - Core tables in production  
**Next:** Optimize artist_completeness worker (batch updates)  
**Performance:** Sub-second queries on 100K+ tracks
