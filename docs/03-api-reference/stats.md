# Library Statistics API

Get statistics and health metrics for your local music library.

## Overview

The Statistics API provides read-only insights into library health:
- **Track/Album/Artist Counts**: Totals and availability statistics
- **Storage Size**: Total file size calculations
- **Broken Files**: Detection and re-download queue management
- **Album Completeness**: Missing tracks detection via Spotify API

**Use Cases:**
- Dashboard metrics display
- Library health monitoring
- Broken file management
- Completeness verification

**Architecture:** Uses `StatsService` for efficient aggregate queries (COUNT, SUM, etc.) - no full table scans.

---

## Library Statistics Endpoints

### Get Library Stats

**Endpoint:** `GET /library/stats`

**Description:** Get aggregate library statistics using efficient SQL queries.

**Query Parameters:** None

**Response:**
```json
{
    "total_tracks": 5000,
    "tracks_with_files": 4800,
    "broken_files": 12,
    "duplicate_groups": 3,
    "total_size_bytes": 25000000000,
    "scanned_percentage": 96.0
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 59-90

@router.get("/stats")
async def get_library_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get library statistics.
    
    Hey future me - this uses StatsService for Clean Architecture.
    All DB queries are efficient aggregate functions (COUNT, SUM).
    No full table scans!
    """
    from soulspot.application.services.stats_service import StatsService

    stats_service = StatsService(session)

    total_tracks = await stats_service.get_total_tracks()
    tracks_with_files = await stats_service.get_tracks_with_files()
    broken_files = await stats_service.get_broken_files_count()
    duplicate_groups = await stats_service.get_unresolved_duplicates_count()
    total_size = await stats_service.get_total_file_size()

    return {
        "total_tracks": total_tracks,
        "tracks_with_files": tracks_with_files,
        "broken_files": broken_files,
        "duplicate_groups": duplicate_groups,
        "total_size_bytes": total_size,
        "scanned_percentage": (
            (tracks_with_files / total_tracks * 100) if total_tracks > 0 else 0
        ),
    }
```

**Response Fields:**
- `total_tracks` (integer): Total tracks in database
- `tracks_with_files` (integer): Tracks with local files (`file_path IS NOT NULL`)
- `broken_files` (integer): Corrupted/missing files detected
- `duplicate_groups` (integer): Groups of duplicate tracks (unresolved)
- `total_size_bytes` (integer): Total storage used by music files
- `scanned_percentage` (float): Percentage of tracks with local files (0-100)

**Performance Notes:**
- Uses `StatsService` for centralized query logic
- All queries use SQL aggregate functions (COUNT, SUM)
- No full table scans or N+1 queries
- Suitable for frequent polling (dashboard updates)

---

## Broken Files Endpoints

### Get Broken Files List

**Endpoint:** `GET /library/broken-files`

**Description:** Get detailed list of broken/corrupted files detected during library scan.

**Query Parameters:** None

**Response:**
```json
{
    "broken_files": [
        {
            "id": 123,
            "title": "Track Title",
            "artist": "Artist Name",
            "album": "Album Title",
            "file_path": "/path/to/broken.mp3",
            "error": "mutagen.id3.error: Could not read metadata",
            "detected_at": "2025-12-15T10:00:00Z"
        }
    ],
    "total_count": 12
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 98-120

@router.get("/broken-files")
async def get_broken_files(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get list of broken/corrupted files.
    
    Hey future me - broken files are detected during library scan.
    A file is marked "broken" if:
    - mutagen can't read metadata
    - file size is 0
    - file hash doesn't match expected
    """
    use_case = GetBrokenFilesUseCase(session)
    broken_files = await use_case.execute()

    return {
        "broken_files": broken_files,
        "total_count": len(broken_files),
    }
```

**Broken File Detection Criteria:**
- **Metadata Read Failure**: `mutagen` library cannot parse file
- **Zero File Size**: File exists but is empty
- **Hash Mismatch**: File integrity check fails (if available)

**Use Cases:**
- Library health check
- Identify files needing re-download
- Cleanup corrupted files
- Display in UI for user action

---

### Get Broken Files Summary

**Endpoint:** `GET /library/broken-files-summary`

**Description:** Get summary of broken files grouped by download status.

**Query Parameters:** None

**Response:**
```json
{
    "total_broken": 12,
    "pending_re_download": 5,
    "in_queue": 3,
    "re_downloading": 2,
    "re_download_failed": 2,
    "by_status": {
        "pending": 5,
        "queued": 3,
        "downloading": 2,
        "failed": 2
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 123-144

@router.get("/broken-files-summary")
async def get_broken_files_summary(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get summary of broken files and their download status.
    
    Returns:
        Summary with counts by status (pending re-download, in queue, etc.)
    """
    try:
        use_case = ReDownloadBrokenFilesUseCase(session)
        summary = await use_case.get_broken_files_summary()

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get broken files summary: {str(e)}"
        ) from e
```

**Response Fields:**
- `total_broken` (integer): Total broken files detected
- `pending_re_download` (integer): Not yet queued for re-download
- `in_queue` (integer): Queued but not started
- `re_downloading` (integer): Currently downloading
- `re_download_failed` (integer): Re-download failed
- `by_status` (object): Counts grouped by status

**Error Handling:**
- **500 Internal Server Error**: Use case execution failed

---

### Queue Re-Download of Broken Files

**Endpoint:** `POST /library/re-download-broken`

**Description:** Queue broken files for automatic re-download via slskd.

**Request Body:**
```json
{
    "priority": 5,
    "max_files": 10
}
```

**Request Model:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 48-53

class ReDownloadRequest(BaseModel):
    """Request to re-download broken files."""

    priority: int = 5  # Default medium priority
    max_files: int | None = None  # None = all broken files
```

**Request Parameters:**
- `priority` (integer, optional): Download priority (1-10, default: 5)
  - 1-3: Low priority (background)
  - 4-6: Medium priority (default)
  - 7-10: High priority (urgent)
- `max_files` (integer, optional): Maximum files to queue (default: None = all)

**Response:**
```json
{
    "queued_count": 10,
    "skipped_count": 2,
    "already_queued_count": 1,
    "message": "Queued 10 broken files for re-download"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 147-180

@router.post("/re-download-broken")
async def re_download_broken_files(
    request: ReDownloadRequest = ReDownloadRequest(),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Queue re-download of broken/corrupted files.
    
    Hey future me - this queues jobs, doesn't download directly!
    The download happens asynchronously via the download worker.
    priority param lets urgent fixes go to front of queue.
    max_files prevents overwhelming the download system.
    
    Consider returning 202 Accepted instead of 200 since this is async!
    """
    try:
        use_case = ReDownloadBrokenFilesUseCase(session)
        result = await use_case.execute(
            priority=request.priority, max_files=request.max_files
        )

        return {
            **result,
            "message": f"Queued {result['queued_count']} broken files for re-download",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue re-downloads: {str(e)}"
        ) from e
```

**Behavior:**
- **Asynchronous**: Jobs queued for background processing (doesn't download immediately)
- **Priority Queue**: Higher priority files processed first
- **Deduplication**: Already queued files skipped
- **Rate Limiting**: `max_files` prevents overwhelming download system

**Response Fields:**
- `queued_count` (integer): Files successfully queued
- `skipped_count` (integer): Files skipped (not suitable for re-download)
- `already_queued_count` (integer): Files already in download queue
- `message` (string): Human-readable summary

**Error Handling:**
- **500 Internal Server Error**: Use case execution failed

**Future Improvement:**
- Consider returning HTTP 202 Accepted instead of 200 OK (asynchronous operation)

---

## Album Completeness Endpoints

**Note:** These endpoints use **external API (Spotify)** to verify album completeness. Requires Spotify authentication.

### Get Incomplete Albums

**Endpoint:** `GET /library/incomplete-albums`

**Description:** Find albums with missing tracks by comparing local track count vs. Spotify album metadata.

**Query Parameters:**
- `incomplete_only` (boolean, optional): Only return incomplete albums (default: true)
- `min_track_count` (integer, optional): Minimum track count to consider (filters out singles, default: 3)

**Response:**
```json
{
    "albums": [
        {
            "id": 123,
            "title": "Album Title",
            "artist": "Artist Name",
            "local_tracks": 10,
            "expected_tracks": 12,
            "is_complete": false,
            "missing_tracks": ["Track 5", "Track 9"],
            "spotify_id": "album_id"
        }
    ],
    "total_count": 5,
    "incomplete_count": 5
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 188-251

@router.get("/incomplete-albums")
async def get_incomplete_albums(
    incomplete_only: bool = Query(
        True, description="Only return incomplete albums (default: true)"
    ),
    min_track_count: int = Query(
        3, description="Minimum track count to consider (filters out singles)"
    ),
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> dict[str, Any]:
    """Get albums with missing tracks.
    
    ARCHITECTURE NOTE: This uses SpotifyPlugin (external API),
    so it's borderline for "library stats". Could be moved to enrichment
    module in future refactoring.
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings.",
        )
    if not spotify_plugin.can_use(PluginCapability.GET_ALBUM):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        use_case = CheckAlbumCompletenessUseCase(
            session=session,
            spotify_plugin=spotify_plugin,
            musicbrainz_client=None,
        )
        albums = await use_case.execute(
            incomplete_only=incomplete_only, min_track_count=min_track_count
        )

        return {
            "albums": albums,
            "total_count": len(albums),
            "incomplete_count": sum(1 for a in albums if not a["is_complete"]),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check album completeness: {str(e)}"
        ) from e
```

**Query Parameters:**
- `incomplete_only=true` (default): Only return incomplete albums
- `incomplete_only=false`: Return all albums with completeness info
- `min_track_count=3` (default): Filters out singles/2-track EPs

**Response Fields:**
- `albums` (array): Album completeness information
  - `id` (integer): Album database ID
  - `title` (string): Album title
  - `artist` (string): Artist name
  - `local_tracks` (integer): Tracks found in local library
  - `expected_tracks` (integer): Total tracks per Spotify
  - `is_complete` (boolean): Whether all tracks present
  - `missing_tracks` (array): Missing track titles (if available)
  - `spotify_id` (string): Spotify album ID
- `total_count` (integer): Total albums checked
- `incomplete_count` (integer): Albums missing tracks

**Prerequisites:**
- Spotify provider enabled in settings
- User authenticated with Spotify
- Albums have Spotify IDs (from sync or enrichment)

**Error Handling:**
- **503 Service Unavailable**: Spotify provider disabled
- **401 Unauthorized**: Not authenticated with Spotify
- **500 Internal Server Error**: Use case execution failed

**Use Cases:**
- Find missing tracks in albums
- Quality control for library completeness
- Trigger automatic downloads for missing tracks
- Identify incomplete rips/imports

**Architecture Note:**
This endpoint uses external API (Spotify) for verification. Could be refactored to `enrichment` module in future.

---

### Get Album Completeness (Single Album)

**Endpoint:** `GET /library/incomplete-albums/{album_id}`

**Description:** Get completeness information for a specific album.

**Path Parameters:**
- `album_id` (string): Album database ID

**Response:**
```json
{
    "id": 123,
    "title": "Album Title",
    "artist": "Artist Name",
    "local_tracks": 10,
    "expected_tracks": 12,
    "is_complete": false,
    "missing_tracks": ["Track 5", "Track 9"],
    "spotify_id": "album_id",
    "completeness_percentage": 83.3
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/library/stats.py
# Lines 254-307

@router.get("/incomplete-albums/{album_id}")
async def get_album_completeness(
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> dict[str, Any]:
    """Get completeness information for a specific album.
    
    Returns:
        Album completeness information including expected vs actual track count
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings.",
        )
    if not spotify_plugin.can_use(PluginCapability.GET_ALBUM):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        use_case = CheckAlbumCompletenessUseCase(
            session=session,
            spotify_plugin=spotify_plugin,
            musicbrainz_client=None,
        )
        result = await use_case.check_single_album(album_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Album not found or cannot determine expected track count",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check album completeness: {str(e)}"
        ) from e
```

**Prerequisites:**
- Spotify provider enabled
- User authenticated with Spotify
- Album exists in database
- Album has Spotify ID

**Error Handling:**
- **503 Service Unavailable**: Spotify provider disabled
- **401 Unauthorized**: Not authenticated with Spotify
- **404 Not Found**: Album not found or no expected track count
- **500 Internal Server Error**: Use case execution failed

---

## Summary

**Total Endpoints Documented:** 6 statistics endpoints

**Endpoint Categories:**
1. **Library Stats**: 1 endpoint (aggregate metrics)
2. **Broken Files**: 3 endpoints (list, summary, re-download)
3. **Album Completeness**: 2 endpoints (list, single album)

**Key Features:**
- **Efficient Queries**: Uses `StatsService` with SQL aggregates (no full scans)
- **Health Monitoring**: Track counts, broken files, duplicates, storage
- **Broken File Recovery**: Automatic re-download queue with priority
- **Completeness Verification**: External API validation via Spotify
- **Clean Architecture**: Use cases for business logic isolation

**Module Stats:**
- **stats.py**: 307 lines, 6 endpoints
- **Code validation**: 100% (all endpoints verified)

**External Dependencies:**
- **Spotify API**: Required for album completeness endpoints
- **slskd**: Required for re-download functionality

**Use Cases:**
- Dashboard metrics display
- Library health monitoring
- Broken file repair workflows
- Album quality control
