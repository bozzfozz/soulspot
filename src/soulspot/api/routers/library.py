"""Library management API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.use_cases.check_album_completeness import (
    CheckAlbumCompletenessUseCase,
)
from soulspot.application.use_cases.re_download_broken import (
    ReDownloadBrokenFilesUseCase,
)
from soulspot.application.use_cases.scan_library import (
    GetBrokenFilesUseCase,
    GetDuplicatesUseCase,
    ScanLibraryUseCase,
)
from soulspot.config import Settings, get_settings

router = APIRouter(prefix="/library", tags=["library"])


# Hey future me, these are DTOs for library scanning! ScanRequest is minimal - just the path to scan.
# ScanResponse tracks scan progress (scanned_files, broken_files, duplicate_files counts) and provides
# scan_id for polling status. broken_files = corrupted/unreadable audio files, duplicate_files = same
# content/fingerprint detected multiple times (helps clean up library). ReDownloadRequest controls bulk
# re-download of broken files - priority for queue ordering, max_files caps how many to fix at once
# (prevents queueing 1000 broken files and overwhelming slskd). All counts start at 0 and increment as scan
# progresses. progress_percent is 0-100 calculated from scanned/total.


class ScanRequest(BaseModel):
    """Request to start a library scan."""

    scan_path: str


# Yo, scan response format! Shows real-time scan progress. total_files is estimated/discovered count
# (might grow as scan finds subdirectories). scanned_files increments as we process each file. broken_files
# and duplicate_files are cumulative counters of issues found. progress_percent helps UI show progress bar.
# Poll GET /scan/{scan_id} repeatedly to watch this update in real-time (every 1-2 seconds). status enum
# is "running", "completed", "failed" - check that to know when to stop polling!
class ScanResponse(BaseModel):
    """Response from library scan."""

    scan_id: str
    status: str
    scan_path: str
    total_files: int
    scanned_files: int
    broken_files: int
    duplicate_files: int
    progress_percent: float


# Listen up, request to re-download broken files found by scan! priority determines queue order (higher =
# sooner). max_files limits how many broken files to fix in one batch - if scan found 500 broken files and
# you set max_files=50, only the 50 worst/first ones get queued. This prevents overwhelming the download
# system. Setting max_files=None queues ALL broken files (dangerous if you have hundreds!). Use conservative
# values like 10-20 for first run, then increase if downloads complete quickly.
class ReDownloadRequest(BaseModel):
    """Request to re-download broken files."""

    priority: int = 0
    max_files: int | None = None


# Hey future me, this kicks off a library scan! Validates scan_path and starts scanning for audio
# files. The ValueError catch handles path validation errors (like trying to scan outside allowed
# directories - security feature). Returns scan ID so you can poll for status later. Scan runs
# asynchronously (I think?) so this returns immediately. Status is an enum value converted to string.
# total_files might be 0 initially if scan hasn't discovered files yet. Generic Exception catch might
# hide real issues - consider more specific error types. This is a POST because it creates a scan
# entity, not idempotent.
@router.post("/scan")
async def start_library_scan(
    request: ScanRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Start a library scan.

    Args:
        request: Scan request with path
        session: Database session
        settings: Application settings

    Returns:
        Scan information with ID
    """
    try:
        use_case = ScanLibraryUseCase(session, settings)
        scan = await use_case.execute(request.scan_path)

        return {
            "scan_id": scan.id,
            "status": scan.status.value,
            "scan_path": scan.scan_path,
            "total_files": scan.total_files,
            "message": "Library scan started",
        }
    except ValueError as e:
        # Path validation errors
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start library scan: {str(e)}"
        ) from e


@router.get("/scan/{scan_id}")
async def get_scan_status(
    scan_id: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ScanResponse:
    """Get library scan status.

    Args:
        scan_id: Scan ID
        session: Database session
        settings: Application settings

    Returns:
        Scan status and progress
    """
    use_case = ScanLibraryUseCase(session, settings)
    scan = await use_case.get_scan_status(scan_id)

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return ScanResponse(
        scan_id=scan.id,
        status=scan.status.value,
        scan_path=scan.scan_path,
        total_files=scan.total_files,
        scanned_files=scan.scanned_files,
        broken_files=scan.broken_files,
        duplicate_files=scan.duplicate_files,
        progress_percent=scan.get_progress_percent(),
    )


# Yo, finds duplicate files in the library! Optional resolved filter lets you show only unresolved
# duplicates (which need action) or resolved ones (already handled). Returns duplicate_count per group
# and calculates wasted_bytes (size of duplicates minus one copy you need). The wasted bytes formula
# total_size - (size / count) is clever - keeps one copy, counts rest as waste. Sum aggregates across
# all duplicate groups. No pagination - could return thousands of duplicates and blow up memory! Should
# add limit/offset. Duplicate detection is by hash, so identical content = duplicate even if different
# filenames/metadata. Be careful - a re-release might be detected as duplicate of original!
@router.get("/duplicates")
async def get_duplicates(
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get duplicate files.

    Args:
        resolved: Filter by resolved status
        session: Database session

    Returns:
        List of duplicate files
    """
    use_case = GetDuplicatesUseCase(session)
    duplicates = await use_case.execute(resolved=resolved)

    return {
        "duplicates": duplicates,
        "total_count": len(duplicates),
        "total_duplicate_files": sum(d["duplicate_count"] for d in duplicates),
        "total_wasted_bytes": sum(
            d["total_size_bytes"] - (d["total_size_bytes"] // d["duplicate_count"])
            for d in duplicates
        ),
    }


@router.get("/broken-files")
async def get_broken_files(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get broken/corrupted files.

    Args:
        session: Database session

    Returns:
        List of broken files
    """
    use_case = GetBrokenFilesUseCase(session)
    broken_files = await use_case.execute()

    return {
        "broken_files": broken_files,
        "total_count": len(broken_files),
    }


# Listen up! Library overview stats endpoint. Uses SQLAlchemy func.count() for efficient aggregation
# instead of fetching all records. The .scalar() unwraps single value from result. The "or 0" handles
# None from empty tables. is_broken check uses == True explicitly which looks weird but is necessary
# for SQLAlchemy (prevents Python truthiness issues). E712 noqa disables flake8 warning about that.
# scanned_percentage could divide by zero if total_tracks is 0 - the if prevents that. Stats are
# real-time, not cached, so hitting this frequently could be slow on large libraries. Consider caching!
@router.get("/stats")
async def get_library_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get library statistics.

    Args:
        session: Database session

    Returns:
        Library statistics
    """
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        FileDuplicateModel,
        TrackModel,
    )

    # Count total tracks
    total_tracks_stmt = select(func.count(TrackModel.id))
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count tracks with files
    tracks_with_files_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    tracks_with_files_result = await session.execute(tracks_with_files_stmt)
    tracks_with_files = tracks_with_files_result.scalar() or 0

    # Count broken files
    broken_files_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.is_broken == True  # noqa: E712
    )
    broken_files_result = await session.execute(broken_files_stmt)
    broken_files = broken_files_result.scalar() or 0

    # Count duplicate groups
    duplicates_stmt = select(func.count(FileDuplicateModel.id)).where(
        FileDuplicateModel.resolved == False  # noqa: E712
    )
    duplicates_result = await session.execute(duplicates_stmt)
    duplicate_groups = duplicates_result.scalar() or 0

    # Total file size
    total_size_stmt = select(func.sum(TrackModel.file_size)).where(
        TrackModel.file_size.isnot(None)
    )
    total_size_result = await session.execute(total_size_stmt)
    total_size = total_size_result.scalar() or 0

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


# HEADS UP: This checks album completeness but creates use case with None clients! The comment says
# "requires Spotify client configuration" and "returns empty results without credentials". This is
# basically non-functional without proper setup. Should probably return 503 Service Unavailable or
# require auth. min_track_count filter is smart - avoids flagging 2-track singles as "incomplete".
# But what if a single is actually missing a B-side? incomplete_only=True by default is sensible (most
# users care about incomplete, not complete albums). Sum in incomplete_count counts albums where
# is_complete=False - nice use of generator expression. This endpoint is half-implemented!
@router.get("/incomplete-albums")
async def get_incomplete_albums(
    incomplete_only: bool = Query(
        True, description="Only return incomplete albums (default: true)"
    ),
    min_track_count: int = Query(
        3, description="Minimum track count to consider (filters out singles)"
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get albums with missing tracks.

    Args:
        incomplete_only: Only return incomplete albums
        min_track_count: Minimum track count to consider
        session: Database session

    Returns:
        List of albums with completeness information
    """
    try:
        # Note: This endpoint requires Spotify client configuration
        # For now, it returns empty results without credentials
        use_case = CheckAlbumCompletenessUseCase(
            session=session,
            spotify_client=None,
            musicbrainz_client=None,
            access_token=None,
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
) -> dict[str, Any]:
    """Get completeness information for a specific album.

    Args:
        album_id: Album ID
        session: Database session

    Returns:
        Album completeness information
    """
    try:
        use_case = CheckAlbumCompletenessUseCase(
            session=session,
            spotify_client=None,
            musicbrainz_client=None,
            access_token=None,
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


# Yo this queues broken files for re-download! priority param lets you put urgent fixes at front of
# queue. max_files limits how many to queue at once (prevents overwhelming download system). Default
# request object with =ReDownloadRequest() is clever - makes both params optional. Returns result dict
# from use case with queued_count and then adds a friendly message. The **result spreads the dict which
# is clean. Generic Exception catch might hide specific issues. This is async operation (queues jobs)
# but returns sync response - might want to return 202 Accepted instead of 200. The message f-string
# duplicates the queued_count from result - redundant but readable.
@router.post("/re-download-broken")
async def re_download_broken_files(
    request: ReDownloadRequest = ReDownloadRequest(),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Queue re-download of broken/corrupted files.

    Args:
        request: Re-download request with options
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


@router.get("/broken-files-summary")
async def get_broken_files_summary(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get summary of broken files and their download status.

    Args:
        session: Database session

    Returns:
        Summary of broken files
    """
    try:
        use_case = ReDownloadBrokenFilesUseCase(session)
        summary = await use_case.get_broken_files_summary()

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get broken files summary: {str(e)}"
        ) from e
