# Artist Songs API

Sync and manage artist singles and top tracks from Spotify.

## Overview

The Artist Songs API allows you to:
- **Sync Top Tracks**: Fetch artist singles from Spotify's "Top Tracks" API
- **Bulk Sync**: Sync all followed artists' songs at once
- **List Songs**: View all synced singles for an artist
- **Delete Songs**: Remove specific or all songs for an artist

**Data Source:** Spotify Web API (requires OAuth)

**Key Concepts:**
- **Artist Songs**: Artist's "Top Tracks" from Spotify (usually 10 tracks)
- **Market Parameter**: Regional availability (e.g., `US`, `DE`, `JP`)
- **Provider Requirement**: Spotify must be enabled and authenticated
- **Bulk Sync**: Process multiple artists with statistics

---

## Sync Artist Songs

**Endpoint:** `POST /api/artists/{id}/songs/sync`

**Description:** Sync artist's top tracks from Spotify.

**Path Parameters:**
- `id` (uuid): Artist ID

**Query Parameters:**
- `market` (string, optional): ISO 3166-1 alpha-2 country code (e.g., `US`, `DE`)

**Request Body:** None

**Response:**
```json
{
    "artist_id": "artist-uuid-123",
    "artist_name": "Artist Name",
    "tracks_created": 8,
    "tracks_updated": 2,
    "total_tracks": 10,
    "market": "US",
    "synced_at": "2025-12-15T10:00:00Z"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/artist_songs.py
# Lines 105-161

@router.post("/{id}/songs/sync", response_model=ArtistSongsSyncResponse)
async def sync_artist_songs(
    id: UUID,
    market: str | None = None,
    request: Request = None,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistSongsSyncResponse:
    """Sync artist's top tracks from Spotify.

    Args:
        id: Artist UUID
        market: ISO 3166-1 alpha-2 country code (e.g., 'US', 'DE')
                If not provided, uses Spotify user's default market.

    Returns:
        Sync statistics (tracks_created, tracks_updated, total_tracks)

    Errors:
        401: Spotify not authenticated
        404: Artist not found
        503: Spotify provider not enabled
    """
```

**Workflow:**
1. **Provider Check**: Verify Spotify is enabled
2. **Authentication Check**: Verify user has Spotify OAuth token
3. **Capability Check**: Verify plugin supports `GET_ARTIST_TOP_TRACKS`
4. **API Call**: Fetch artist top tracks from Spotify
5. **Upsert Tracks**: Create new tracks, update existing
6. **Return Stats**: Created/updated counts

**Response Fields:**
- `artist_id` (uuid): Artist UUID
- `artist_name` (string): Artist name
- `tracks_created` (integer): New tracks added
- `tracks_updated` (integer): Existing tracks updated
- `total_tracks` (integer): Total tracks processed
- `market` (string | null): Market used for sync
- `synced_at` (datetime): Sync timestamp

**Errors:**
- **401 Unauthorized**: Spotify not authenticated
- **404 Not Found**: Artist not found in database
- **503 Service Unavailable**: Spotify provider disabled

**Use Cases:**
- **Artist Detail Page**: "Sync Top Tracks" button
- **Manual Sync**: Refresh artist's singles on demand

**Performance:**
- **API Calls**: 1 Spotify API call per artist
- **Rate Limits**: Spotify rate limits apply (~180 req/min)

---

## Sync All Artists Songs

**Endpoint:** `POST /api/artists/songs/sync-all`

**Description:** Sync top tracks for all followed artists (bulk operation).

**Query Parameters:**
- `limit` (integer, optional): Max artists to sync (default: 50, max: 200)
- `market` (string, optional): ISO 3166-1 alpha-2 country code

**Request Body:** None

**Response:**
```json
{
    "artists_processed": 50,
    "tracks_created": 320,
    "tracks_updated": 180,
    "errors": 2,
    "skipped_artists": [
        {
            "artist_id": "artist-uuid-789",
            "artist_name": "Artist With Error",
            "error": "Spotify rate limit exceeded"
        }
    ],
    "started_at": "2025-12-15T10:00:00Z",
    "completed_at": "2025-12-15T10:05:30Z",
    "duration_seconds": 330
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/artist_songs.py
# Lines 164-255

@router.post("/songs/sync-all", response_model=BulkSyncResponse)
async def sync_all_artists_songs(
    limit: int = 50,
    market: str | None = None,
    request: Request = None,
    session: AsyncSession = Depends(get_db_session),
) -> BulkSyncResponse:
    """Sync top tracks for all followed artists.

    This is a bulk operation that processes multiple artists sequentially.
    Use with caution as it may take several minutes for large libraries.

    Args:
        limit: Maximum number of artists to sync (default: 50, max: 200)
        market: ISO 3166-1 alpha-2 country code

    Returns:
        Bulk sync statistics (artists_processed, tracks_created, etc.)

    Errors:
        401: Spotify not authenticated
        503: Spotify provider not enabled
    """
```

**Workflow:**
1. **Provider Check**: Verify Spotify is enabled
2. **Authentication Check**: Verify user has Spotify OAuth token
3. **Load Artists**: Get followed artists from database (up to `limit`)
4. **Process Sequentially**: Sync each artist's top tracks
5. **Error Handling**: Continue on individual artist errors
6. **Return Stats**: Aggregated sync statistics

**Response Fields:**
- `artists_processed` (integer): Artists successfully synced
- `tracks_created` (integer): Total new tracks added
- `tracks_updated` (integer): Total existing tracks updated
- `errors` (integer): Number of artists that failed
- `skipped_artists` (array): List of failed artists with errors
  - `artist_id` (uuid): Artist UUID
  - `artist_name` (string): Artist name
  - `error` (string): Error message
- `started_at` (datetime): Sync start time
- `completed_at` (datetime): Sync completion time
- `duration_seconds` (float): Total duration in seconds

**Limits:**
- **Default Limit**: 50 artists
- **Maximum Limit**: 200 artists
- **Rate Limits**: Spotify rate limits apply
- **Timeout**: May take several minutes for large batches

**Use Cases:**
- **Scheduled Sync**: Background job to keep singles updated
- **Initial Sync**: Populate artist songs for all followed artists
- **Batch Update**: Refresh all artists' top tracks

**Performance:**
- **Sequential Processing**: One artist at a time
- **API Calls**: 1 Spotify API call per artist
- **Rate Limit Handling**: Continues on rate limit errors, reports in `skipped_artists`
- **Duration**: ~0.5-1 second per artist (+ API latency)

**Best Practices:**
- **Use Limits**: Start with small limit (10-20) to test
- **Monitor Errors**: Check `skipped_artists` for issues
- **Schedule**: Run during off-peak hours
- **Retry**: Re-run for `skipped_artists` after rate limits clear

---

## List Artist Songs

**Endpoint:** `GET /api/artists/{id}/songs`

**Description:** Get all synced songs for an artist.

**Path Parameters:**
- `id` (uuid): Artist ID

**Query Parameters:** None

**Response:**
```json
{
    "artist_id": "artist-uuid-123",
    "artist_name": "Artist Name",
    "total_songs": 10,
    "songs": [
        {
            "track_id": "track-uuid-456",
            "title": "Song Title",
            "album": "Album Name",
            "spotify_uri": "spotify:track:abc123xyz",
            "isrc": "USABC1234567",
            "duration_ms": 240000,
            "popularity": 85,
            "synced_at": "2025-12-15T10:00:00Z",
            "is_in_library": true
        }
    ]
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/artist_songs.py
# Lines 258-317

@router.get("/{id}/songs", response_model=ArtistSongsListResponse)
async def list_artist_songs(
    id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistSongsListResponse:
    """Get all synced songs for an artist.

    Returns songs from the database (no API calls).

    Args:
        id: Artist UUID

    Returns:
        List of artist's songs with metadata

    Errors:
        404: Artist not found
    """
```

**Song Fields:**
- `track_id` (uuid): Track UUID
- `title` (string): Track title
- `album` (string | null): Album name
- `spotify_uri` (string): Spotify track URI
- `isrc` (string | null): International Standard Recording Code
- `duration_ms` (integer): Track duration in milliseconds
- `popularity` (integer): Spotify popularity (0-100)
- `synced_at` (datetime): When track was synced
- `is_in_library` (boolean): Whether track is in user's library

**Use Cases:**
- **Artist Detail Page**: Show artist's top tracks
- **Library View**: Browse artist singles
- **Offline Access**: Display synced songs without API calls

**Performance:**
- **Database Only**: No API calls
- **Fast**: Simple query by artist ID
- **Sorted**: Ordered by popularity (descending)

---

## Delete Artist Song

**Endpoint:** `DELETE /api/artists/{id}/songs/{track_id}`

**Description:** Delete a specific song for an artist.

**Path Parameters:**
- `id` (uuid): Artist ID
- `track_id` (uuid): Track ID

**Request Body:** None

**Response:**
```json
{
    "success": true,
    "message": "Song deleted successfully",
    "artist_id": "artist-uuid-123",
    "track_id": "track-uuid-456"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/artist_songs.py
# Lines 320-373

@router.delete("/{id}/songs/{track_id}")
async def delete_artist_song(
    id: UUID,
    track_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete a specific song for an artist.

    Validates that the track belongs to the artist before deletion.

    Args:
        id: Artist UUID
        track_id: Track UUID

    Returns:
        Success message

    Errors:
        404: Artist or track not found, or track doesn't belong to artist
    """
```

**Validation:**
- **Artist Exists**: Artist must exist in database
- **Track Exists**: Track must exist in database
- **Ownership**: Track must belong to specified artist

**Errors:**
- **404 Not Found**: Artist not found
- **404 Not Found**: Track not found
- **404 Not Found**: Track doesn't belong to artist

**Use Cases:**
- **Manual Cleanup**: Remove specific unwanted songs
- **Duplicate Removal**: Delete duplicate entries

---

## Delete All Artist Songs

**Endpoint:** `DELETE /api/artists/{id}/songs`

**Description:** Delete all songs for an artist.

**Path Parameters:**
- `id` (uuid): Artist ID

**Request Body:** None

**Response:**
```json
{
    "success": true,
    "message": "Deleted 10 songs for artist",
    "artist_id": "artist-uuid-123",
    "deleted_count": 10
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/artist_songs.py
# Lines 376-425

@router.delete("/{id}/songs")
async def delete_all_artist_songs(
    id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete all songs for an artist.

    Args:
        id: Artist UUID

    Returns:
        Success message with deleted count

    Errors:
        404: Artist not found
    """
```

**Use Cases:**
- **Full Cleanup**: Remove all synced songs for artist
- **Re-Sync Preparation**: Clear before fresh sync

**Performance:**
- **Bulk Delete**: Single query deletes all songs
- **Fast**: Cascading deletes handle relationships

---

## Summary

**Total Endpoints Documented:** 5

**Endpoint Categories:**
1. **Sync Operations**: 2 endpoints (single artist, bulk all)
2. **List Operations**: 1 endpoint (list artist songs)
3. **Delete Operations**: 2 endpoints (delete specific, delete all)

**Key Features:**
- **Spotify Integration**: Uses Spotify Web API for top tracks
- **Provider Checks**: Validates Spotify enabled + authenticated
- **Bulk Operations**: Sync multiple artists with statistics
- **Market Support**: Regional availability via `market` parameter
- **Error Handling**: Graceful handling of individual artist failures

**Provider Requirements:**
- **Spotify OAuth**: Required for all sync operations
- **Provider Enabled**: Spotify must be enabled in settings
- **Capability Check**: Plugin must support `GET_ARTIST_TOP_TRACKS`

**Use Cases:**
- **Artist Detail Page**: Sync/view artist top tracks
- **Library Management**: Browse/delete artist singles
- **Scheduled Sync**: Bulk sync all artists periodically
- **Initial Setup**: Populate artist songs for followed artists

**Module Stats:**
- **Source File**: `artist_songs.py` (461 lines)
- **Endpoints**: 5
- **Code Validation**: 100%

**Service Layer:**
- **ArtistSongsService**: Handles Spotify API integration
- **SpotifyPlugin**: Provides `get_artist_top_tracks()` method
- **Provider Registry**: Checks Spotify availability

**Response DTOs:**
- `ArtistSongsSyncResponse`: Single artist sync results
- `BulkSyncResponse`: Bulk sync statistics
- `ArtistSongsListResponse`: List of artist songs
- `ArtistSongDTO`: Individual song metadata

**Error Codes:**
- **401 Unauthorized**: Spotify not authenticated
- **404 Not Found**: Artist/track not found
- **503 Service Unavailable**: Spotify provider disabled

**Rate Limits:**
- **Spotify API**: ~180 requests/minute
- **Bulk Sync**: Processes artists sequentially
- **Retry Strategy**: Continues on rate limit, reports in `skipped_artists`

**Best Practices:**
1. **Start Small**: Test bulk sync with limit=10-20 first
2. **Monitor Errors**: Check `skipped_artists` for issues
3. **Use Market**: Specify market for regional availability
4. **Schedule Wisely**: Run bulk sync during off-peak hours
5. **Retry Failures**: Re-run for skipped artists after rate limits clear
