"""Library statistics and health endpoints.

Hey future me - this file provides read-only statistics about the local library:
- Track/Album/Artist counts
- Storage size calculations
- Broken files detection
- Album completeness checking (uses external APIs)

Broken files and incomplete albums help identify issues in the library.
The stats endpoint is called frequently by the UI dashboard.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_plugin,
)
from soulspot.application.use_cases.check_album_completeness import (
    CheckAlbumCompletenessUseCase,
)
from soulspot.application.use_cases.re_download_broken import (
    ReDownloadBrokenFilesUseCase,
)
from soulspot.application.use_cases.scan_library import GetBrokenFilesUseCase

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["library-stats"])


# =============================================================================
# Response Models
# =============================================================================


class ReDownloadRequest(BaseModel):
    """Request to re-download broken files."""

    priority: int = 5  # Default medium priority
    max_files: int | None = None  # None = all broken files


# =============================================================================
# STATISTICS ENDPOINTS
# =============================================================================


@router.get("/stats")
async def get_library_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get library statistics.

    Hey future me - this uses StatsService for Clean Architecture.
    All DB queries are efficient aggregate functions (COUNT, SUM).
    No full table scans!

    Args:
        session: Database session

    Returns:
        Library statistics including track counts, file sizes, etc.
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


# =============================================================================
# BROKEN FILES ENDPOINTS
# =============================================================================


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

    Args:
        session: Database session

    Returns:
        List of broken files with paths and error info
    """
    use_case = GetBrokenFilesUseCase(session)
    broken_files = await use_case.execute()

    return {
        "broken_files": broken_files,
        "total_count": len(broken_files),
    }


@router.get("/broken-files-summary")
async def get_broken_files_summary(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get summary of broken files and their download status.

    Args:
        session: Database session

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

    Args:
        request: Re-download options (priority, max_files)
        session: Database session

    Returns:
        Summary of queued downloads
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


# =============================================================================
# ALBUM COMPLETENESS ENDPOINTS
# =============================================================================


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

    Hey future me - this endpoint uses EXTERNAL API (Spotify)!
    It compares local track count vs Spotify's album track count.
    min_track_count=3 filters out singles (2-track EPs are ignored).

    ARCHITECTURE NOTE: This uses SpotifyPlugin (external API),
    so it's borderline for "library stats". Could be moved to enrichment
    module in future refactoring.

    Args:
        incomplete_only: Only return incomplete albums
        min_track_count: Minimum track count to consider
        session: Database session
        spotify_plugin: SpotifyPlugin (handles token internally)

    Returns:
        List of albums with completeness information
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


@router.get("/incomplete-albums/{album_id}")
async def get_album_completeness(
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> dict[str, Any]:
    """Get completeness information for a specific album.

    Args:
        album_id: Album ID
        session: Database session
        spotify_plugin: SpotifyPlugin (handles token internally)

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
