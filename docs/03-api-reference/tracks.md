# Track Management API Reference

> **Code Verified:** 2025-12-30  
> **Source:** `src/soulspot/api/routers/tracks.py`  
> **Status:** ✅ Active - All endpoints validated against source code

---

## Overview

The Track Management API provides:
- ⬇️ **Download Tracks** - Queue track download via Soulseek
- 🎵 **Metadata Enrichment** - Fetch metadata from MusicBrainz
- 🔍 **Search Tracks** - Search Spotify for tracks
- 📝 **Manual Editing** - Update track metadata + ID3 tags
- 📊 **Track Details** - Get full track information

**Total:** 5 endpoints

---

## Endpoints

### 1. POST `/api/tracks/{track_id}/download`

**Purpose:** Download a track via Soulseek.

**Source Code:** `tracks.py` lines 33-67

**Query Parameters:**
- `quality` (default: "best") - Quality preference: `best`, `good`, `any`

**Response:**
```json
{
  "message": "Download started",
  "track_id": "abc123...",
  "download_id": "dl456...",
  "quality": "best",
  "status": "queued",
  "search_results_count": 10
}
```

**Quality Preferences:**
- `best` - Highest bitrate result
- `good` - Good quality (e.g., 320kbps MP3)
- `any` - First available result

**Implementation:**
```python
# src/soulspot/api/routers/tracks.py:34-43
# Hey future me, this endpoint kicks off a track download! It uses the SearchAndDownloadTrackUseCase which
# searches Soulseek, picks best result based on quality preference ("best"=highest bitrate, "any"=first match),
# and queues the download. If search finds nothing or download fails to start, we return 400 error. The response
# includes download_id for tracking and search_results_count so you know if search was good (10 results) or
# weak (1 result = might be wrong file!). This is ASYNC - download happens in background, don't wait for completion!

request = SearchAndDownloadTrackRequest(
    track_id=track_id_obj,
    quality_preference=quality,
)
response = await use_case.execute(request)
```

**Errors:**
- `400` - Download failed or search returned no results

---

### 2. POST `/api/tracks/{track_id}/enrich`

**Purpose:** Enrich track metadata from MusicBrainz.

**Source Code:** `tracks.py` lines 70-118

**Query Parameters:**
- `force_refresh` (default: false) - Force refresh even if already enriched

**Response:**
```json
{
  "message": "Track enriched successfully",
  "track_id": "abc123...",
  "enriched": true,
  "enriched_fields": ["genre", "release_date", "artwork_url"],
  "musicbrainz_id": "mb123...",
  "errors": []
}
```

**Response (Not Found in MusicBrainz):**
```json
{
  "message": "Track not found in MusicBrainz",
  "track_id": "abc123...",
  "enriched": false,
  "enriched_fields": [],
  "musicbrainz_id": null,
  "errors": ["Track not found in MusicBrainz"]
}
```

**Important:**
```python
# src/soulspot/api/routers/tracks.py:75-80
# Yo, this enriches ONE track with metadata from MusicBrainz (genres, release dates, artwork URLs, etc).
# The force_refresh flag bypasses cache - only use if metadata is wrong! MusicBrainz has STRICT rate limits
# (1 req/sec), so this can take 1-3 seconds. If track not found in MB, we return enriched=false but 200 OK
# (not 404 - track exists in our DB, just no MB data). The enriched_fields list tells you what changed. This
# updates our DB but doesn't write to file tags - use the PATCH endpoint for that!

# MusicBrainz rate limit: 1 request per second!
# Use sparingly to avoid blocking
```

**Errors:**
- `400` - Invalid track ID
- `500` - MusicBrainz API failure

---

### 3. GET `/api/tracks/search`

**Purpose:** Search for tracks on Spotify.

**Source Code:** `tracks.py` lines 121-181

**Query Parameters:**
- `query` (required) - Search query (track name, "artist - track", ISRC)
- `limit` (default: 20, max: 100) - Number of results

**Response:**
```json
{
  "tracks": [
    {
      "id": "spotify_track_id",
      "name": "Song Title",
      "artists": [
        {"name": "Artist Name"},
        {"name": "Featured Artist"}
      ],
      "album": {"name": "Album Name"},
      "duration_ms": 240000,
      "uri": "spotify:track:ID"
    }
  ],
  "total": 10,
  "query": "nirvana smells like teen spirit",
  "limit": 20
}
```

**Auth Requirements:**
- ✅ Spotify provider must be enabled
- ✅ User must be authenticated with Spotify
- Uses `PluginCapability.SEARCH_TRACKS`

**Use Cases:**
- Search then download workflow
- Add to playlist features
- ISRC code lookup

**Errors:**
- `503` - Spotify provider disabled
- `401` - Not authenticated with Spotify
- `500` - Search failed

---

### 4. GET `/api/tracks/{track_id}`

**Purpose:** Get track details with artist/album info.

**Source Code:** `tracks.py` lines 184-239

**Response:**
```json
{
  "id": "abc123...",
  "title": "Song Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "album_artist": "Album Artist",
  "genre": "Rock",
  "year": 2025,
  "artist_id": "artist_uuid",
  "album_id": "album_uuid",
  "duration_ms": 240000,
  "track_number": 5,
  "disc_number": 1,
  "spotify_uri": "spotify:track:ID",
  "musicbrainz_id": "mb123...",
  "isrc": "USRC12345678",
  "file_path": "/music/Artist/Album/Track.flac",
  "created_at": "2025-12-30T10:00:00Z",
  "updated_at": "2025-12-30T10:00:00Z"
}
```

**Implementation:**
```python
# src/soulspot/api/routers/tracks.py:194-212
# Yo future me, this gets ONE track's full details with artist/album names! Uses Depends(get_db_session)
# to properly manage DB session lifecycle. joinedload() eagerly loads relationships to avoid N+1 queries.
# The hasattr checks on album are because Album model might not have "artist" or "year" fields depending
# on how it's set up. genre field now comes from TrackModel.genre (populated by library scanner from
# audio file tags). Returns flat dict which is easy for frontend to consume. The unique() call prevents
# duplicate results when joins create multiple rows. scalar_one_or_none() returns Track or None - perfect for 404 check.

stmt = (
    select(TrackModel)
    .where(TrackModel.id == track_id)
    .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
)
```

**Errors:**
- `400` - Invalid track ID
- `404` - Track not found

---

### 5. PATCH `/api/tracks/{track_id}/metadata` ⭐ MANUAL EDITOR

**Purpose:** Update track metadata manually and write to ID3 tags.

**Source Code:** `tracks.py` lines 242-341

**Request (JSON):**
```json
{
  "title": "New Song Title",
  "artist": "New Artist",
  "album": "New Album",
  "genre": "Rock",
  "year": 2025,
  "track_number": 5,
  "disc_number": 1
}
```

**Response:**
```json
{
  "message": "Metadata updated successfully",
  "track_id": "abc123...",
  "updated_fields": ["title", "artist", "genre"]
}
```

**Critical Feature:**
```python
# src/soulspot/api/routers/tracks.py:247-258
# Yo future me, this is the MANUAL metadata editor - update track info by hand! We have an allowed_fields list
# to prevent users from modifying internal fields (spotify_id, created_at, etc). After updating our DB, we ALSO
# write to file's ID3 tags using mutagen! This is CRITICAL - if you only update DB, the file still has old tags
# and re-scans will overwrite your changes! The mutagen code uses add() not set() because we want to REPLACE
# tags, not append. If file doesn't exist or tag writing fails, we LOG warning but DON'T fail the request (DB
# update succeeded, that's what matters!). Encoding=3 means UTF-8 for international characters.

# 1. Update DB
for field in allowed_fields:
    if field in metadata:
        setattr(track, field, metadata[field])
await track_repository.update(track)

# 2. Update file ID3 tags (if file exists)
if track.file_path and track.file_path.exists():
    audio = MP3(str(track.file_path), ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    
    # Update tags (encoding=3 = UTF-8)
    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
    # ... etc
    audio.save()
```

**Allowed Fields:**
- `title`, `artist`, `album`, `album_artist`
- `genre`, `year`, `track_number`, `disc_number`

**Protected Fields (cannot modify):**
- `id`, `spotify_uri`, `musicbrainz_id`, `isrc`
- `created_at`, `updated_at`, `file_path`

**ID3 Tags Written:**
- `TIT2` - Title
- `TPE1` - Artist
- `TALB` - Album
- `TPE2` - Album Artist
- `TCON` - Genre
- `TDRC` - Year
- `TRCK` - Track Number
- `TPOS` - Disc Number

**Important:**
- If file doesn't exist → DB updated, no file error
- If ID3 write fails → DB updated, warning logged
- UTF-8 encoding for international characters

---

## Common Workflows

### Workflow 1: Search + Download

```
1. GET /tracks/search?query=nirvana+smells
   → Get track list from Spotify

2. (User imports track to library via Playlist or Library API)

3. POST /tracks/{id}/download?quality=best
   → Queue download via Soulseek

4. (Poll /downloads/{id} for progress)
```

### Workflow 2: Enrich Metadata

```
1. GET /tracks/{id}
   → Check current metadata

2. POST /tracks/{id}/enrich?force_refresh=false
   → Fetch from MusicBrainz

3. GET /tracks/{id}
   → Verify enriched data
```

### Workflow 3: Manual Edit + Tag Write

```
1. GET /tracks/{id}
   → Get current metadata

2. PATCH /tracks/{id}/metadata
   Body: {"genre": "Rock", "year": 2025}
   → Update DB + write ID3 tags

3. (Re-scan library to verify tags persist)
```

---

## Error Handling

### Common Errors

**400 Bad Request (Invalid ID):**
```json
{
  "detail": "Invalid track ID: ..."
}
```

**404 Not Found:**
```json
{
  "detail": "Track not found"
}
```

**503 Service Unavailable (Spotify Disabled):**
```json
{
  "detail": "Spotify provider is disabled in settings."
}
```

**401 Unauthorized (Spotify Not Connected):**
```json
{
  "detail": "Not authenticated with Spotify. Please connect your account first."
}
```

---

## Database Schema

**Table:** `tracks`

```sql
CREATE TABLE tracks (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    artist_id UUID REFERENCES artists(id) ON DELETE CASCADE,
    album_id UUID REFERENCES albums(id) ON DELETE CASCADE,
    track_number INTEGER,
    disc_number INTEGER DEFAULT 1,
    duration_ms INTEGER,
    spotify_uri TEXT UNIQUE,
    musicbrainz_id TEXT,
    isrc TEXT,
    genre VARCHAR(100),
    file_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tracks_artist ON tracks(artist_id);
CREATE INDEX idx_tracks_album ON tracks(album_id);
CREATE INDEX idx_tracks_spotify_uri ON tracks(spotify_uri);
CREATE INDEX idx_tracks_isrc ON tracks(isrc);
```

---

## Summary

**5 Endpoints** for track management:

| Category | Endpoints | Purpose |
|----------|-----------|---------|
| **Download** | 1 | Search & download via Soulseek |
| **Metadata** | 2 | Enrich from MusicBrainz, manual edit |
| **Search** | 1 | Spotify track search |
| **Details** | 1 | Get full track info |

**Best Practices:**
- ✅ Use `quality=best` for downloads (highest bitrate)
- ✅ Enrich metadata AFTER import (MusicBrainz rate limit)
- ✅ Manual edits write to ID3 tags (persist across re-scans)
- ✅ Check `search_results_count` (low = potential mismatch)
- ❌ Don't spam enrichment (MusicBrainz 1 req/sec limit)
- ❌ Don't modify protected fields (id, spotify_uri, etc.)

**Related Routers:**
- **Downloads** (`/api/downloads/*`) - Download queue management
- **Library** (`/api/library/*`) - Library scanning + stats
- **Metadata** (`/api/metadata/*`) - Advanced metadata operations

---

**Code Verification:**
- ✅ All 5 endpoints documented match actual implementation
- ✅ Code snippets extracted from actual source (lines 33-341)
- ✅ ID3 tag writing validated (mutagen integration)
- ✅ Auth requirements documented from can_use() checks
- ✅ No pseudo-code or assumptions - all validated

**Last Verified:** 2025-12-30  
**Verified Against:** `src/soulspot/api/routers/tracks.py` (341 lines total)  
**Verification Method:** Full file read + endpoint extraction + documentation comparison
