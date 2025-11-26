"""Playlist management endpoints."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from soulspot.api.dependencies import (
    get_import_playlist_use_case,
    get_playlist_repository,
    get_spotify_client,
    get_spotify_token_from_session,
    get_track_repository,
    get_queue_playlist_downloads_use_case,
)
from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistRequest,
    ImportSpotifyPlaylistUseCase,
)
from soulspot.application.use_cases.queue_playlist_downloads import (
    QueuePlaylistDownloadsRequest,
    QueuePlaylistDownloadsResponse,
    QueuePlaylistDownloadsUseCase,
)
from soulspot.domain.entities import Playlist, PlaylistSource
from soulspot.domain.exceptions import ValidationException
from soulspot.domain.value_objects import PlaylistId, SpotifyUri
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import (
    PlaylistRepository,
    TrackRepository,
)

router = APIRouter()


# Hey future me, this helper extracts playlist ID from either a full Spotify URL or a bare ID!
# Users paste URLs like "https://open.spotify.com/playlist/ABC123" but our API expects just "ABC123".
# We detect URLs by checking for "://" (protocol indicator) and use SpotifyUri.from_url() to parse.
# If it's already a bare ID (no protocol), return it as-is. This makes the API user-friendly while
# keeping backward compatibility. SpotifyUri validates the format so invalid URLs/IDs throw
# ValidationException which converts to 422 error. DON'T cache results - function is cheap!
def _extract_playlist_id(playlist_id_or_url: str) -> str:
    """Extract Spotify playlist ID from either a URL or bare ID.

    This function accepts both:
    - Full Spotify URLs: https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl
    - Bare playlist IDs: 2ZBCi09CSeWMBOoHZdN6Nl

    Args:
        playlist_id_or_url: Spotify playlist URL or ID

    Returns:
        Spotify playlist ID (the alphanumeric string)

    Raises:
        ValidationException: If the URL or ID format is invalid
    """
    # If it looks like a URL (contains protocol), parse it
    # Using "://" to detect URLs is more robust than checking for domain substring
    if "://" in playlist_id_or_url:
        spotify_uri = SpotifyUri.from_url(playlist_id_or_url)
        # Validate it's a playlist URI, not track/album/etc
        if spotify_uri.resource_type != "playlist":
            raise ValidationException(
                f"URL must be a playlist, got {spotify_uri.resource_type}"
            )
        return spotify_uri.resource_id
    # Otherwise assume it's already a bare ID
    return playlist_id_or_url


# Hey future me, this is the main playlist import endpoint! Access token comes from SESSION not
# a header - super important for security. The token dependency will auto-refresh if expired,
# which is slick but can cause weird timing issues if the refresh fails. fetch_all_tracks=True
# means we'll fetch EVERY track even if playlist has 1000+ songs - could timeout for huge playlists.
# Consider adding pagination or background job queueing for massive playlists. Also this returns
# dict not Pydantic model - less type safety but more flexible for errors array. NOW accepts both
# bare playlist IDs AND full Spotify URLs - extracts ID automatically via _extract_playlist_id()!
@router.post("/import")
async def import_playlist(
    playlist_id: str = Query(
        ..., description="Spotify playlist ID or URL (e.g., https://open.spotify.com/playlist/ID)"
    ),
    fetch_all_tracks: bool = Query(True, description="Fetch all tracks in playlist"),
    auto_queue_downloads: bool = Query(
        False, description="Automatically queue missing tracks for download"
    ),
    quality_filter: str | None = Query(
        None, description="Quality filter for downloads (flac, 320, any)"
    ),
    access_token: str = Depends(get_spotify_token_from_session),
    use_case: ImportSpotifyPlaylistUseCase = Depends(get_import_playlist_use_case),
    queue_downloads_use_case: QueuePlaylistDownloadsUseCase = Depends(
        get_queue_playlist_downloads_use_case
    ),
) -> dict[str, Any]:
    """Import a Spotify playlist using session-based authentication.

    The access token is automatically retrieved from your session.
    If your token is expired, it will be automatically refreshed.
    If you don't have a valid session, you'll receive a 401 error
    and need to authenticate at /auth first.

    Accepts both:
    - Spotify playlist URLs: https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl
    - Bare playlist IDs: 2ZBCi09CSeWMBOoHZdN6Nl

    Args:
        playlist_id: Spotify playlist ID or full URL
        fetch_all_tracks: Whether to fetch all tracks
        auto_queue_downloads: Automatically queue missing tracks for download
        quality_filter: Quality filter for downloads (flac, 320, any)
        access_token: Automatically retrieved from session
        use_case: Import playlist use case
        queue_downloads_use_case: Queue downloads use case

    Returns:
        Import status and statistics
    """
    try:
        # Extract ID from URL if needed
        extracted_id = _extract_playlist_id(playlist_id)

        request = ImportSpotifyPlaylistRequest(
            playlist_id=extracted_id,
            access_token=access_token,
            fetch_all_tracks=fetch_all_tracks,
        )
        response = await use_case.execute(request)

        result = {
            "message": "Playlist imported successfully",
            "playlist_id": str(response.playlist.id.value),
            "playlist_name": response.playlist.name,
            "tracks_imported": response.tracks_imported,
            "tracks_failed": response.tracks_failed,
            "errors": response.errors,
        }

        # Auto-queue downloads if requested
        if auto_queue_downloads:
            queue_request = QueuePlaylistDownloadsRequest(
                playlist_id=str(response.playlist.id.value),
                quality_filter=quality_filter,
            )
            queue_response = await queue_downloads_use_case.execute(queue_request)
            result["download_queue"] = {
                "queued_count": queue_response.queued_count,
                "already_downloaded": queue_response.already_downloaded,
                "skipped_count": queue_response.skipped_count,
                "failed_count": queue_response.failed_count,
            }
            if queue_response.errors:
                result["errors"].extend(queue_response.errors)

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# Hey future me, this is the manual trigger for the Smart Download Queue!
# Useful if you imported a playlist earlier without auto-download, or if you added new tracks
# and want to sync them up. It's idempotent (skips already downloaded tracks) so safe to call
# multiple times. The quality_filter is passed to the Soulseek searcher.
@router.post("/{playlist_id}/queue-downloads")
async def queue_downloads(
    playlist_id: str,
    quality_filter: str | None = Query(
        None, description="Quality filter for downloads (flac, 320, any)"
    ),
    use_case: QueuePlaylistDownloadsUseCase = Depends(
        get_queue_playlist_downloads_use_case
    ),
) -> dict[str, Any]:
    """Queue missing tracks from a playlist for download.

    Args:
        playlist_id: Playlist ID
        quality_filter: Quality filter (flac, 320, any)
        use_case: Queue downloads use case

    Returns:
        Queue statistics
    """
    try:
        request = QueuePlaylistDownloadsRequest(
            playlist_id=playlist_id,
            quality_filter=quality_filter,
        )
        response = await use_case.execute(request)

        return {
            "message": "Downloads queued successfully",
            "queued_count": response.queued_count,
            "already_downloaded": response.already_downloaded,
            "skipped_count": response.skipped_count,
            "failed_count": response.failed_count,
            "errors": response.errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to import playlist: {str(e)}"
        ) from e


# Hey future me, this is THE PLAYLIST LIBRARY SYNC endpoint! Unlike single playlist import above,
# this fetches ALL user playlists from Spotify and stores ONLY the metadata (no tracks yet). Think
# of it as creating a "catalog" of available playlists - user can browse and later choose which to
# fully import with tracks. We handle Spotify pagination automatically (max 50 per request), store/
# update playlist metadata in DB, and mark which are already fully imported vs metadata-only. This
# is FAST because we're not fetching thousands of tracks - just playlist names, IDs, descriptions,
# image URLs, and track counts. Perfect for the "browse my playlists" UI!
@router.post("/sync-library")
async def sync_playlist_library(
    access_token: str = Depends(get_spotify_token_from_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Sync user's playlist library from Spotify (metadata only, no tracks).

    Fetches all playlists from the authenticated user's Spotify account and
    stores their metadata in the local database. This creates a "library" of
    available playlists without downloading any tracks yet. Users can then
    browse their playlists and choose which ones to fully import later.

    Args:
        access_token: Automatically retrieved from session
        spotify_client: Spotify API client
        playlist_repository: Playlist repository

    Returns:
        Sync statistics including number of playlists synced and their status
    """
    try:
        all_playlists: list[dict[str, Any]] = []
        offset = 0
        limit = 50  # Spotify max

        # Fetch all user playlists with pagination
        while True:
            response = await spotify_client.get_user_playlists(
                access_token=access_token, limit=limit, offset=offset
            )

            items = response.get("items", [])
            all_playlists.extend(items)

            # Check if there are more pages - 'next' is authoritative
            if not response.get("next"):
                break

            offset += limit

        # Process each playlist
        synced_count = 0
        updated_count = 0
        results = []

        for playlist_data in all_playlists:
            try:
                # Use consistent timestamp for this iteration
                now = datetime.now(UTC)

                # Extract playlist metadata
                spotify_playlist_id = playlist_data["id"]
                spotify_uri = SpotifyUri(f"spotify:playlist:{spotify_playlist_id}")

                # Check if playlist already exists
                existing_playlist = await playlist_repository.get_by_spotify_uri(
                    spotify_uri
                )

                if existing_playlist:
                    # Update existing playlist metadata
                    existing_playlist.name = playlist_data["name"]
                    existing_playlist.description = playlist_data.get("description")
                    existing_playlist.updated_at = now
                    await playlist_repository.update(existing_playlist)
                    updated_count += 1
                    status = "updated"
                else:
                    # Create new playlist entry (metadata only, no tracks)
                    playlist = Playlist(
                        id=PlaylistId.generate(),
                        name=playlist_data["name"],
                        description=playlist_data.get("description"),
                        source=PlaylistSource.SPOTIFY,
                        spotify_uri=spotify_uri,
                        created_at=now,
                        updated_at=now,
                    )
                    await playlist_repository.add(playlist)
                    synced_count += 1
                    status = "synced"

                results.append(
                    {
                        "spotify_id": spotify_playlist_id,
                        "name": playlist_data["name"],
                        "track_count": playlist_data["tracks"]["total"],
                        "status": status,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "spotify_id": playlist_data.get("id", "unknown"),
                        "name": playlist_data.get("name", "unknown"),
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return {
            "message": "Playlist library synced successfully",
            "total_playlists": len(all_playlists),
            "synced_count": synced_count,
            "updated_count": updated_count,
            "results": results,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync playlist library: {str(e)}"
        ) from e


# Yo, classic pagination endpoint here. Default 20 items is reasonable but limit is capped at 100
# to prevent someone requesting 10000 playlists and killing the DB. No cursor-based pagination
# though - so if someone adds/deletes playlists while paginating you might get duplicates or gaps.
# The len(playlists) for total is wrong if there are more results! Should do separate count query.
# Also we're calling str() on URIs which assumes they exist - None would crash. type: ignore needed.
# Yo, classic pagination endpoint here. Default 20 items is reasonable but limit is capped at 100
# to prevent someone requesting 10000 playlists and killing the DB. No cursor-based pagination
# though - so if someone adds/deletes playlists while paginating you might get duplicates or gaps.
# The len(playlists) for total is wrong if there are more results! Should do separate count query.
# Also we're calling str() on URIs which assumes they exist - None would crash. type: ignore needed.
@router.get("/")
async def list_playlists(
    skip: int = Query(0, ge=0, description="Number of playlists to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of playlists to return"),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """List all playlists.

    Args:
        skip: Number of playlists to skip
        limit: Number of playlists to return
        playlist_repository: Playlist repository

    Returns:
        List of playlists
    """
    playlists = await playlist_repository.list_all(limit=limit, offset=skip)

    return {
        "playlists": [
            {
                "id": str(playlist.id.value),
                "name": playlist.name,
                "description": playlist.description,
                "source": playlist.source.value,
                "track_count": len(playlist.track_ids),
                "spotify_uri": str(playlist.spotify_uri)
                if playlist.spotify_uri
                else None,
                "created_at": playlist.created_at.isoformat(),
                "updated_at": playlist.updated_at.isoformat(),
            }
            for playlist in playlists
        ],
        "total": len(playlists),
        "skip": skip,
        "limit": limit,
    }


# Hey future me, this gets ONE playlist by ID! PlaylistId.from_string() validates the UUID format -
# it'll throw ValueError if malformed. We return 404 if playlist doesn't exist. The str() calls on
# spotify_uri and track_ids assume they're not None - could crash! type: ignore to silence mypy.
# Track IDs are just UUIDs here, not actual track data - frontend needs separate API calls to hydrate.
@router.get("/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Get playlist details.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository

    Returns:
        Playlist details with tracks
    """
    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        return {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "source": playlist.source.value,
            "spotify_uri": str(playlist.spotify_uri) if playlist.spotify_uri else None,
            "track_ids": [str(track_id.value) for track_id in playlist.track_ids],
            "track_count": len(playlist.track_ids),
            "created_at": playlist.created_at.isoformat(),
            "updated_at": playlist.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e


# CAUTION: This function has a weird pattern - uses anext() to get DB session from generator!
# That's because get_db_session is an async generator for FastAPI dependency injection. The anext()
# grabs the first yielded session but NEVER calls it again, so cleanup might not happen properly.
# Should use Depends(get_db_session) instead and let FastAPI handle it. Also does N queries in a
# loop for track lookups - SUPER inefficient. Should be a single JOIN query. The joinedload is good
# for eager loading relations though. Track without file_path = missing which makes sense.
@router.get("/{playlist_id}/missing-tracks")
async def get_missing_tracks(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Get tracks that are in the playlist but not downloaded to the library.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository
        track_repository: Track repository

    Returns:
        List of missing tracks
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get session for direct DB query
        session: AsyncSession = await anext(get_db_session(request))

        # Find tracks without file_path
        missing_tracks = []
        for track_id in playlist.track_ids:
            stmt = (
                select(TrackModel)
                .where(TrackModel.id == str(track_id.value))
                .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            )
            result = await session.execute(stmt)
            track_model = result.unique().scalar_one_or_none()

            if track_model and not track_model.file_path:
                missing_tracks.append(
                    {
                        "id": track_model.id,
                        "title": track_model.title,
                        "artist": track_model.artist.name
                        if track_model.artist
                        else "Unknown Artist",
                        "album": track_model.album.title
                        if track_model.album
                        else "Unknown Album",
                        "duration_ms": track_model.duration_ms,
                        "spotify_uri": track_model.spotify_uri,
                    }
                )

        return {
            "playlist_id": str(playlist.id.value),
            "playlist_name": playlist.name,
            "missing_tracks": missing_tracks,
            "missing_count": len(missing_tracks),
            "total_tracks": len(playlist.track_ids),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e


# Yo this is basically a "refresh from Spotify" endpoint. It extracts the Spotify ID from the
# spotify_uri which is formatted as "spotify:playlist:ACTUAL_ID" - that split(":")[-1] grabs the
# last part. If the URI format ever changes this breaks silently! Also re-imports the ENTIRE
# playlist which could be slow. No incremental sync to just get new/removed tracks. The internal
# playlist_id (UUID) vs Spotify's playlist ID (string) can be confusing - make sure you're using
# the right one. Setting fetch_all_tracks=True means we always get everything, no pagination.
@router.post("/{playlist_id}/sync")
async def sync_playlist(
    playlist_id: str,
    access_token: str = Depends(get_spotify_token_from_session),
    use_case: ImportSpotifyPlaylistUseCase = Depends(get_import_playlist_use_case),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Sync a single playlist with Spotify.

    Re-imports the playlist from Spotify to update track list and metadata.

    Args:
        playlist_id: Internal playlist ID
        access_token: Automatically retrieved from session
        use_case: Import playlist use case
        playlist_repository: Playlist repository

    Returns:
        Sync status and statistics
    """
    try:
        # Get existing playlist
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get Spotify playlist ID
        if not playlist.spotify_uri:
            raise HTTPException(
                status_code=400,
                detail="Playlist has no Spotify URI. Cannot sync.",
            )

        # Extract Spotify playlist ID from URI (format: spotify:playlist:ID)
        spotify_playlist_id = str(playlist.spotify_uri.value).split(":")[-1]

        # Re-import the playlist
        request = ImportSpotifyPlaylistRequest(
            playlist_id=spotify_playlist_id,
            access_token=access_token,
            fetch_all_tracks=True,
        )
        response = await use_case.execute(request)

        return {
            "message": "Playlist synced successfully",
            "playlist_id": str(response.playlist.id.value),
            "playlist_name": response.playlist.name,
            "total_tracks": response.tracks_imported,
            "tracks_failed": response.tracks_failed,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync playlist: {str(e)}"
        ) from e


# WARNING: This syncs ALL playlists sequentially - could take FOREVER if you have 100+ playlists!
# Should be a background job, not a synchronous HTTP request. Will definitely timeout with many
# playlists. The try/except per playlist is good so one failure doesn't kill the whole batch.
# Continues on error which is resilient. Results array lets you see what succeeded/failed but could
# get huge. No rate limiting here - hammering Spotify API could get you throttled. Consider adding
# delays between playlists or using batch import if Spotify supports it. The str() conversions in
# results assume values exist - could fail. skipped_count tracks playlists with no Spotify URI.
@router.post("/sync-all")
async def sync_all_playlists(
    access_token: str = Depends(get_spotify_token_from_session),
    use_case: ImportSpotifyPlaylistUseCase = Depends(get_import_playlist_use_case),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Sync all playlists with Spotify.

    Re-imports all playlists from Spotify to update track lists and metadata.

    Args:
        access_token: Automatically retrieved from session
        use_case: Import playlist use case
        playlist_repository: Playlist repository

    Returns:
        Sync status and statistics for all playlists
    """
    try:
        # Get all playlists
        playlists = await playlist_repository.list_all()

        synced_count = 0
        failed_count = 0
        skipped_count = 0
        results = []

        for playlist in playlists:
            if not playlist.spotify_uri:
                skipped_count += 1
                results.append(
                    {
                        "playlist_id": str(playlist.id.value),
                        "playlist_name": playlist.name,
                        "status": "skipped",
                        "message": "No Spotify URI",
                    }
                )
                continue

            try:
                # Extract Spotify playlist ID from URI
                spotify_playlist_id = str(playlist.spotify_uri.value).split(":")[-1]

                # Re-import the playlist
                request = ImportSpotifyPlaylistRequest(
                    playlist_id=spotify_playlist_id,
                    access_token=access_token,
                    fetch_all_tracks=True,
                )
                response = await use_case.execute(request)

                synced_count += 1
                results.append(
                    {
                        "playlist_id": str(response.playlist.id.value),
                        "playlist_name": response.playlist.name,
                        "status": "synced",
                        "total_tracks": str(response.tracks_imported),
                        "tracks_failed": str(response.tracks_failed),
                    }
                )
            except Exception as e:
                failed_count += 1
                results.append(
                    {
                        "playlist_id": str(playlist.id.value),
                        "playlist_name": playlist.name,
                        "status": "failed",
                        "message": str(e),
                    }
                )

        return {
            "message": "Playlist sync completed",
            "total_playlists": len(playlists),
            "synced_count": synced_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync playlists: {str(e)}"
        ) from e


# Important note in the docstring - this IDENTIFIES missing tracks but doesn't actually queue
# downloads! The actual queueing should happen in frontend or a separate background job. This is
# half-implemented basically. Uses the same anext() pattern which is sketchy. Returns just the IDs
# which frontend can then POST to download endpoint. Would be more useful to have a
# "queue_all=true" param that actually kicks off downloads. Same N+1 query antipattern as other
# missing-tracks endpoint. Consider consolidating these two similar functions.
@router.post("/{playlist_id}/download-missing")
async def download_missing_tracks(
    playlist_id: str,
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Download all missing tracks from a playlist.

    Queues downloads for all tracks in the playlist that don't have files.

    Note: This is a simplified implementation that returns the list of
    missing tracks that need to be downloaded. The actual download queueing
    should be handled by the frontend or a background job.

    Args:
        playlist_id: Playlist ID
        request: Request object
        playlist_repository: Playlist repository

    Returns:
        Download status with list of missing tracks
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get session from dependency
        session_gen = get_db_session(request)
        session: AsyncSession = await anext(session_gen)

        # Find tracks without file_path
        missing_track_ids = []
        for track_id in playlist.track_ids:
            stmt = (
                select(TrackModel)
                .where(TrackModel.id == str(track_id.value))
                .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            )
            result = await session.execute(stmt)
            track_model = result.unique().scalar_one_or_none()

            if track_model and not track_model.file_path:
                missing_track_ids.append(str(track_id.value))

        return {
            "message": "Missing tracks identified",
            "playlist_id": str(playlist.id.value),
            "playlist_name": playlist.name,
            "total_tracks": len(playlist.track_ids),
            "missing_tracks": missing_track_ids,
            "missing_count": len(missing_track_ids),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to identify missing tracks: {str(e)}"
        ) from e
