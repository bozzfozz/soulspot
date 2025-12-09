# Artist Songs API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/artist_songs.py`  
> **Related Service:** `src/soulspot/application/services/artist_songs_service.py`

---

## Overview

The Artist Songs API manages **individual songs/singles** from followed artists, separate from full album management. It focuses on "top tracks" that aren't necessarily part of a complete album.

**Key Features:**
- 🎵 **Top Tracks Sync** - Fetch artist's most popular tracks from Spotify
- 📦 **Bulk Operations** - Sync songs for ALL followed artists
- 🗑️ **Track Management** - List, delete individual tracks or all tracks for an artist
- 💿 **Album-Independent** - Stores tracks without album association (`album_id = NULL`)

**Use Cases:**
- Fetch singles/EPs not included in full albums
- Build "top tracks" playlists
- Discover popular songs from new artists
- Manage non-album releases

---

## Endpoints

### 1. POST `/api/artists/{artist_id}/songs/sync`

**Purpose:** Sync songs (top tracks/singles) for a specific artist from Spotify.

**Path Parameters:**
- `artist_id` *(string, UUID)* - Artist UUID from database

**Query Parameters:**
- `market` *(string, optional)* - ISO 3166-1 alpha-2 country code for regional track availability (default: `"US"`)

**Authentication:** Uses **shared server-side Spotify token** (no user auth required)

**Request:**
```http
POST /api/artists/550e8400-e29b-41d4-a716-446655440000/songs/sync?market=GB HTTP/1.1
```

**Response:**
```json
{
  "tracks": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "title": "Comfortably Numb",
      "artist_id": "550e8400-e29b-41d4-a716-446655440000",
      "duration_ms": 384000,
      "spotify_uri": "spotify:track:abc123",
      "isrc": "GBAYE8200109",
      "file_path": null,
      "created_at": "2025-12-09T10:30:00Z",
      "updated_at": "2025-12-09T10:30:00Z"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "title": "Wish You Were Here",
      "artist_id": "550e8400-e29b-41d4-a716-446655440000",
      "duration_ms": 334000,
      "spotify_uri": "spotify:track:def456",
      "isrc": "GBAYE7500287",
      "file_path": null,
      "created_at": "2025-12-09T10:30:05Z",
      "updated_at": "2025-12-09T10:30:05Z"
    }
  ],
  "stats": {
    "total_fetched": 10,
    "new_tracks": 2,
    "updated_tracks": 0,
    "skipped_tracks": 8
  },
  "message": "Successfully synced 2 new tracks for artist"
}
```

**Behavior:**
- Fetches **top 10 tracks** from Spotify (via `GET /artists/{id}/top-tracks`)
- Stores tracks with `album_id = NULL` (album-independent)
- De-duplicates by ISRC (if track already exists, skips)
- Uses **shared server token** (no user session required)
- Respects `market` parameter (regional availability)

**Errors:**
- `400 Bad Request` - Invalid artist_id format (not UUID)
- `404 Not Found` - Artist not found in database
- `401 Unauthorized` - Shared Spotify token expired/invalid
- `500 Internal Server Error` - Spotify API error

**Code Reference:**
```python
# src/soulspot/api/routers/artist_songs.py (lines 102-175)
@router.post("/{artist_id}/songs/sync", response_model=SyncSongsResponse)
async def sync_artist_songs(
    artist_id: str,
    market: str = Query("US", description="ISO 3166-1 alpha-2 country code"),
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> SyncSongsResponse:
    """Sync songs (top tracks/singles) for a specific artist."""
    ...
```

---

### 2. POST `/api/artists/songs/sync-all`

**Purpose:** Sync songs for ALL followed artists (bulk operation).

**Query Parameters:**
- `market` *(string, optional)* - ISO 3166-1 alpha-2 country code (default: `"US"`)
- `limit` *(integer, optional)* - Maximum number of artists to sync (default: unlimited)

**Authentication:** Uses **shared server-side Spotify token**

**Request:**
```http
POST /api/artists/songs/sync-all?market=US&limit=50 HTTP/1.1
```

**Response:**
```json
{
  "tracks": [],
  "stats": {
    "total_artists": 50,
    "artists_synced": 48,
    "artists_failed": 2,
    "total_tracks_fetched": 500,
    "new_tracks": 120,
    "updated_tracks": 5,
    "skipped_tracks": 375
  },
  "message": "Synced 120 new tracks from 48 artists (2 failed)"
}
```

**Behavior:**
- Fetches **all followed artists** from database
- Syncs top tracks for **each artist** (same as single artist sync)
- Runs sequentially (no parallelism to avoid rate limiting)
- Returns **aggregated stats** across all artists
- Skips artists with no Spotify URI
- Logs individual artist failures (continues processing others)

**Use Cases:**
- Initial bulk import of top tracks
- Periodic refresh of popular songs
- Discovery of new singles from followed artists

**Errors:**
- `401 Unauthorized` - Shared Spotify token expired/invalid
- `500 Internal Server Error` - Database or Spotify API error

**Code Reference:**
```python
# src/soulspot/api/routers/artist_songs.py (lines 180-239)
@router.post("/songs/sync-all", response_model=SyncSongsResponse)
async def sync_all_artist_songs(
    market: str = Query("US", description="ISO 3166-1 alpha-2 country code"),
    limit: int | None = Query(None, description="Max artists to sync"),
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> SyncSongsResponse:
    """Sync songs for all followed artists (bulk operation)."""
    ...
```

---

### 3. GET `/api/artists/{artist_id}/songs`

**Purpose:** List all songs (singles) for a specific artist from database.

**Path Parameters:**
- `artist_id` *(string, UUID)* - Artist UUID

**Query Parameters:**
- `skip` *(integer, optional)* - Number of records to skip for pagination (default: `0`)
- `limit` *(integer, optional)* - Maximum number of records to return (default: `100`)

**Request:**
```http
GET /api/artists/550e8400-e29b-41d4-a716-446655440000/songs?skip=0&limit=20 HTTP/1.1
```

**Response:**
```json
{
  "tracks": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "title": "Comfortably Numb",
      "artist_id": "550e8400-e29b-41d4-a716-446655440000",
      "duration_ms": 384000,
      "spotify_uri": "spotify:track:abc123",
      "isrc": "GBAYE8200109",
      "file_path": "/music/Pink Floyd/Comfortably Numb.flac",
      "created_at": "2025-12-09T10:30:00Z",
      "updated_at": "2025-12-09T10:35:00Z"
    }
  ],
  "total_count": 12,
  "artist_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Behavior:**
- Returns **only album-independent tracks** (`album_id = NULL`)
- Ordered by `created_at DESC` (newest first)
- Supports pagination via `skip` and `limit`
- Includes downloaded tracks (`file_path` not null)

**Use Cases:**
- Display artist's singles in UI
- Check which tracks are already downloaded
- Pagination for large artist track lists

**Errors:**
- `400 Bad Request` - Invalid artist_id format
- `404 Not Found` - Artist not found in database

**Code Reference:**
```python
# src/soulspot/api/routers/artist_songs.py (lines 244-279)
@router.get("/{artist_id}/songs", response_model=SongListResponse)
async def list_artist_songs(
    artist_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> SongListResponse:
    """List all songs for a specific artist."""
    ...
```

---

### 4. DELETE `/api/artists/{artist_id}/songs/{track_id}`

**Purpose:** Delete a specific song from database.

**Path Parameters:**
- `artist_id` *(string, UUID)* - Artist UUID
- `track_id` *(string, UUID)* - Track UUID to delete

**Request:**
```http
DELETE /api/artists/550e8400-e29b-41d4-a716-446655440000/songs/770e8400-e29b-41d4-a716-446655440001 HTTP/1.1
```

**Response:**
```json
{
  "message": "Successfully deleted track",
  "deleted_count": 1
}
```

**Behavior:**
- Deletes track from database
- Does **NOT** delete associated file (if downloaded)
- Verifies track belongs to specified artist (safety check)

**Errors:**
- `400 Bad Request` - Invalid artist_id or track_id format
- `404 Not Found` - Track not found or doesn't belong to artist

**Code Reference:**
```python
# src/soulspot/api/routers/artist_songs.py (lines 282-335)
@router.delete("/{artist_id}/songs/{track_id}", response_model=DeleteResponse)
async def delete_artist_song(
    artist_id: str,
    track_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteResponse:
    """Delete a specific song from artist."""
    ...
```

---

### 5. DELETE `/api/artists/{artist_id}/songs`

**Purpose:** Delete **ALL songs** for a specific artist from database.

**Path Parameters:**
- `artist_id` *(string, UUID)* - Artist UUID

**Request:**
```http
DELETE /api/artists/550e8400-e29b-41d4-a716-446655440000/songs HTTP/1.1
```

**Response:**
```json
{
  "message": "Successfully deleted 12 tracks for artist",
  "deleted_count": 12
}
```

**Behavior:**
- Deletes **all album-independent tracks** for artist (`album_id = NULL`)
- Does **NOT** delete associated files (if downloaded)
- Returns count of deleted tracks

**Use Cases:**
- Clean up artist's singles before re-syncing
- Remove artist's non-album tracks
- Bulk cleanup operation

**Errors:**
- `400 Bad Request` - Invalid artist_id format
- `404 Not Found` - Artist not found in database
- `500 Internal Server Error` - Database error

**Code Reference:**
```python
# src/soulspot/api/routers/artist_songs.py (lines 337-384)
@router.delete("/{artist_id}/songs", response_model=DeleteResponse)
async def delete_all_artist_songs(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteResponse:
    """Delete all songs for a specific artist."""
    ...
```

---

## Data Models

### TrackResponse

```python
class TrackResponse(BaseModel):
    """Response model for a track/song."""
    id: str                  # Track UUID
    title: str               # Track title
    artist_id: str           # Artist UUID
    duration_ms: int         # Duration in milliseconds
    spotify_uri: str | None  # Spotify URI (e.g., "spotify:track:abc123")
    isrc: str | None         # International Standard Recording Code
    file_path: str | None    # Local file path if downloaded
    created_at: str          # ISO 8601 timestamp
    updated_at: str          # ISO 8601 timestamp
```

### SyncSongsResponse

```python
class SyncSongsResponse(BaseModel):
    """Response model for song sync operation."""
    tracks: list[TrackResponse]  # List of synced tracks
    stats: dict[str, int]        # Sync statistics
    message: str                 # Status message
```

**Stats Dictionary:**
```python
{
    "total_fetched": 10,      # Total tracks fetched from Spotify
    "new_tracks": 2,          # New tracks added to database
    "updated_tracks": 0,      # Existing tracks updated
    "skipped_tracks": 8,      # Tracks already in database (duplicates)
    # Bulk sync only:
    "total_artists": 50,      # Total artists processed
    "artists_synced": 48,     # Artists successfully synced
    "artists_failed": 2       # Artists that failed to sync
}
```

### SongListResponse

```python
class SongListResponse(BaseModel):
    """Response model for listing songs."""
    tracks: list[TrackResponse]  # List of tracks
    total_count: int             # Total number of songs (for pagination)
    artist_id: str               # Artist UUID
```

### DeleteResponse

```python
class DeleteResponse(BaseModel):
    """Response model for delete operations."""
    message: str          # Status message
    deleted_count: int    # Number of items deleted
```

---

## Code Examples

### Example 1: Sync Top Tracks for Single Artist

```python
import httpx

async def sync_artist_top_tracks(artist_id: str, market: str = "US"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/artists/{artist_id}/songs/sync",
            params={"market": market}
        )
        return response.json()

# Sync top tracks for Pink Floyd (US market)
result = await sync_artist_top_tracks("550e8400-e29b-41d4-a716-446655440000", "US")
print(f"Synced {result['stats']['new_tracks']} new tracks")
print(f"Skipped {result['stats']['skipped_tracks']} duplicates")
```

### Example 2: Bulk Sync All Followed Artists

```python
async def sync_all_artists_top_tracks(limit: int | None = None):
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout
        response = await client.post(
            "http://localhost:8000/api/artists/songs/sync-all",
            params={"market": "GB", "limit": limit}
        )
        return response.json()

# Sync top tracks for all followed artists (limit to 50)
result = await sync_all_artists_top_tracks(limit=50)
print(f"Processed {result['stats']['total_artists']} artists")
print(f"Added {result['stats']['new_tracks']} new tracks")
print(f"Failed: {result['stats']['artists_failed']} artists")
```

### Example 3: List Artist's Singles

```python
async def list_artist_singles(artist_id: str, page: int = 0, page_size: int = 20):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/artists/{artist_id}/songs",
            params={
                "skip": page * page_size,
                "limit": page_size
            }
        )
        return response.json()

# Get first page of singles for artist
result = await list_artist_singles("550e8400-e29b-41d4-a716-446655440000", page=0)
print(f"Total singles: {result['total_count']}")
for track in result['tracks']:
    print(f"- {track['title']} ({track['duration_ms'] / 1000:.0f}s)")
```

### Example 4: Delete Specific Track

```python
async def delete_track(artist_id: str, track_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"http://localhost:8000/api/artists/{artist_id}/songs/{track_id}"
        )
        return response.json()

# Delete a specific track
result = await delete_track(
    "550e8400-e29b-41d4-a716-446655440000",
    "770e8400-e29b-41d4-a716-446655440001"
)
print(result["message"])  # "Successfully deleted track"
```

### Example 5: Delete All Artist's Singles

```python
async def delete_all_artist_singles(artist_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"http://localhost:8000/api/artists/{artist_id}/songs"
        )
        return response.json()

# Delete all singles for artist (before re-sync)
result = await delete_all_artist_singles("550e8400-e29b-41d4-a716-446655440000")
print(f"Deleted {result['deleted_count']} tracks")
```

---

## Technical Notes

### ISRC De-duplication

Tracks are de-duplicated using **ISRC** (International Standard Recording Code):

```python
# src/soulspot/application/services/artist_songs_service.py
if track.isrc:
    existing = await self._get_track_by_isrc(track.isrc)
    if existing:
        stats["skipped_tracks"] += 1
        continue  # Skip duplicate
```

**Benefit:** Prevents duplicate tracks when same song synced from multiple sources (albums, singles, compilations).

### Album-Independent Storage

Tracks synced via this API have **no album association**:

```python
track = Track(
    id=TrackId.generate(),
    title=spotify_track["name"],
    artist_id=artist_id,
    album_id=None,  # ← No album association
    duration_ms=spotify_track["duration_ms"],
    spotify_uri=spotify_track["uri"],
    isrc=spotify_track.get("external_ids", {}).get("isrc"),
)
```

**Use Cases:**
- Singles not part of an album
- Promotional tracks
- Live recordings
- Compilation appearances

### Shared Server Token

All endpoints use **shared server-side Spotify token** (not user session):

```python
access_token: str = Depends(get_spotify_token_shared)
```

**Benefits:**
- No user authentication required
- Works even when no user logged in
- Server manages token refresh automatically

**Limitation:** Uses **server's** Spotify account for API calls (not user's account).

---

## Related Endpoints

**Related Features:**
- [Artists API](./spotify-artist-api.md) - Manage artists (CRUD operations)
- [Automation API](../features/automation-watchlists.md) - Auto-sync new singles for followed artists
- [Downloads API](./download-management.md) - Queue tracks for download
- [Tracks API](./tracks-api.md) - Track metadata and search

**Workflow Integration:**
```
1. Follow Artist (Artists API)
   ↓
2. Sync Top Tracks (Artist Songs API) ← YOU ARE HERE
   ↓
3. Queue Tracks for Download (Downloads API)
   ↓
4. Download via Soulseek
```

---

## Summary

**5 Endpoints** for artist singles management:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/artists/{artist_id}/songs/sync` | POST | Sync top tracks for single artist |
| `/artists/songs/sync-all` | POST | Sync top tracks for ALL followed artists |
| `/artists/{artist_id}/songs` | GET | List artist's singles |
| `/artists/{artist_id}/songs/{track_id}` | DELETE | Delete specific track |
| `/artists/{artist_id}/songs` | DELETE | Delete all artist's singles |

**Key Features:**
- ✅ **ISRC-based de-duplication** (prevents duplicates)
- ✅ **Album-independent storage** (`album_id = NULL`)
- ✅ **Shared server token** (no user auth required)
- ✅ **Bulk operations** (sync all followed artists)
- ✅ **Pagination support** (list endpoint)
