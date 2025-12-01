"""Library management API endpoints."""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_job_queue,
    get_library_scanner_service,
)
from soulspot.application.services.library_scanner_service import LibraryScannerService
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
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Initialize templates (same pattern as ui.py)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

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


# =============================================================================
# LIBRARY IMPORT ENDPOINTS (NEW - with fuzzy matching and background jobs)
# =============================================================================


class ImportScanResponse(BaseModel):
    """Response from import scan start."""

    job_id: str
    status: str
    message: str


# Hey future me - this starts a BACKGROUND JOB for library import!
# Uses JobQueue for async processing (large libraries can take hours).
# The job uses LibraryScannerService which has:
# - Fuzzy matching (85% threshold) for artists/albums
# - Incremental scan (only new/modified files based on mtime)
# - Metadata extraction via mutagen
# Poll /import/status/{job_id} to check progress!
# NOTE: Accepts Form data (from HTMX hx-vals) instead of JSON body for browser compatibility.
@router.post("/import/scan", response_model=ImportScanResponse)
async def start_import_scan(
    incremental: bool = Form(True),
    job_queue: JobQueue = Depends(get_job_queue),
) -> ImportScanResponse:
    """Start a library import scan as background job.

    Scans the music directory, extracts metadata, and imports tracks
    into the database with fuzzy artist/album matching.

    Args:
        incremental: If True, only scan new/modified files (default: True)
        job_queue: Job queue for background processing

    Returns:
        Job ID for status polling
    """
    try:
        # Queue the scan job
        job_id = await job_queue.enqueue(
            job_type=JobType.LIBRARY_SCAN,
            payload={"incremental": incremental},
            max_retries=1,  # Don't retry full scans
            priority=5,  # Medium priority
        )

        return ImportScanResponse(
            job_id=job_id,
            status="pending",
            message=f"Library import scan queued (incremental={incremental})",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start import scan: {str(e)}"
        ) from e


@router.get("/import/status/{job_id}")
async def get_import_scan_status(
    job_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """Get import scan job status (JSON API).

    Args:
        job_id: Job ID from start_import_scan
        job_queue: Job queue instance

    Returns:
        Job status and progress
    """
    job = await job_queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job.id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
    }

    if job.started_at:
        response["started_at"] = job.started_at.isoformat()
    if job.completed_at:
        response["completed_at"] = job.completed_at.isoformat()
    if job.error:
        response["error"] = job.error

    # Include progress from result if available
    if job.result and isinstance(job.result, dict):
        if "progress" in job.result:
            response["progress"] = job.result["progress"]
        response["stats"] = job.result.get("stats", job.result)

    return response


@router.get("/import/status/{job_id}/html", response_class=HTMLResponse)
async def get_import_scan_status_html(
    request: Request,
    job_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> HTMLResponse:
    """Get import scan job status as HTML fragment for HTMX.

    Args:
        request: FastAPI request
        job_id: Job ID from start_import_scan
        job_queue: Job queue instance

    Returns:
        HTML fragment with scan progress
    """
    job = await job_queue.get_job(job_id)

    if not job:
        return templates.TemplateResponse(
            request,
            "fragments/scan_status_error.html",
            context={"error": "Job not found"},
        )

    # Build context for template
    context = {
        "job_id": job.id,
        "status": job.status.value,
        "is_running": job.status == JobStatus.RUNNING,
        "is_completed": job.status == JobStatus.COMPLETED,
        "is_failed": job.status == JobStatus.FAILED,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error": job.error,
        "progress": 0,
        "stats": {},
    }

    # Extract progress and stats from job result
    if job.result and isinstance(job.result, dict):
        context["progress"] = job.result.get("progress", 0)
        context["stats"] = job.result.get("stats", {})

    return templates.TemplateResponse(
        request,
        "fragments/scan_status.html",
        context=context,
    )


@router.get("/import/summary")
async def get_import_summary(
    scanner: LibraryScannerService = Depends(get_library_scanner_service),
) -> dict[str, Any]:
    """Get current library import summary.

    Returns counts of artists, albums, tracks, and local files.

    Args:
        scanner: Library scanner service

    Returns:
        Summary statistics
    """
    try:
        summary = await scanner.get_scan_summary()
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get import summary: {str(e)}"
        ) from e


@router.get("/import/jobs")
async def list_import_jobs(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(20, description="Max jobs to return"),
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """List recent library import jobs.

    Args:
        status: Optional status filter
        limit: Maximum jobs to return
        job_queue: Job queue instance

    Returns:
        List of import jobs
    """
    status_filter = JobStatus(status) if status else None

    jobs = await job_queue.list_jobs(
        status=status_filter,
        job_type=JobType.LIBRARY_SCAN,
        limit=limit,
    )

    return {
        "jobs": [
            {
                "job_id": job.id,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "error": job.error,
            }
            for job in jobs
        ],
        "total": len(jobs),
    }


@router.post("/import/cancel/{job_id}")
async def cancel_import_job(
    job_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """Cancel a running import job.

    Args:
        job_id: Job ID to cancel
        job_queue: Job queue instance

    Returns:
        Cancellation result
    """
    success = await job_queue.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job not found or cannot be cancelled (already completed/failed)",
        )

    return {"job_id": job_id, "cancelled": True}


@router.delete("/clear")
async def clear_local_library(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Clear all local library data (tracks, albums, artists with file_path).
    
    Hey future me - this is the NUCLEAR OPTION! Use when you want to:
    1. Start fresh with a clean library scan
    2. Fix corrupted/fragmented album assignments
    3. Remove all imported local files without touching Spotify data
    
    This ONLY deletes entities that were imported from local files (have file_path).
    Spotify-synced data (playlists, spotify_* tables) is NOT affected!
    
    Returns:
        Statistics about deleted entities
    """
    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel, 
        TrackModel,
    )
    
    stats = {
        "deleted_tracks": 0,
        "deleted_albums": 0,
        "deleted_artists": 0,
    }
    
    logger.info("Starting local library clear operation...")
    
    # Step 1: Delete all tracks that have a file_path (local imports)
    # Tracks without file_path are from Spotify sync and should be kept
    count_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    count_result = await session.execute(count_stmt)
    stats["deleted_tracks"] = count_result.scalar() or 0
    
    if stats["deleted_tracks"] > 0:
        delete_tracks_stmt = delete(TrackModel).where(
            TrackModel.file_path.isnot(None)
        )
        await session.execute(delete_tracks_stmt)
        logger.info(f"Deleted {stats['deleted_tracks']} local tracks")
    
    # Step 2: Delete orphaned albums (albums with no remaining tracks)
    orphan_albums_stmt = (
        select(AlbumModel.id)
        .outerjoin(TrackModel, AlbumModel.id == TrackModel.album_id)
        .group_by(AlbumModel.id)
        .having(func.count(TrackModel.id) == 0)
    )
    orphan_albums_result = await session.execute(orphan_albums_stmt)
    orphan_album_ids = [row[0] for row in orphan_albums_result.all()]
    
    if orphan_album_ids:
        stats["deleted_albums"] = len(orphan_album_ids)
        delete_albums_stmt = delete(AlbumModel).where(
            AlbumModel.id.in_(orphan_album_ids)
        )
        await session.execute(delete_albums_stmt)
        logger.info(f"Deleted {stats['deleted_albums']} orphaned albums")
    
    # Step 3: Delete orphaned artists (artists with no tracks AND no albums)
    orphan_artists_stmt = (
        select(ArtistModel.id)
        .outerjoin(TrackModel, ArtistModel.id == TrackModel.artist_id)
        .outerjoin(AlbumModel, ArtistModel.id == AlbumModel.artist_id)
        .group_by(ArtistModel.id)
        .having(
            (func.count(TrackModel.id) == 0) &
            (func.count(AlbumModel.id) == 0)
        )
    )
    orphan_artists_result = await session.execute(orphan_artists_stmt)
    orphan_artist_ids = [row[0] for row in orphan_artists_result.all()]
    
    if orphan_artist_ids:
        stats["deleted_artists"] = len(orphan_artist_ids)
        delete_artists_stmt = delete(ArtistModel).where(
            ArtistModel.id.in_(orphan_artist_ids)
        )
        await session.execute(delete_artists_stmt)
        logger.info(f"Deleted {stats['deleted_artists']} orphaned artists")
    
    await session.commit()
    
    logger.info(
        f"Local library cleared: {stats['deleted_tracks']} tracks, "
        f"{stats['deleted_albums']} albums, {stats['deleted_artists']} artists"
    )
    
    return {
        "success": True,
        "message": "Local library cleared successfully",
        **stats,
    }


# =====================================================
# Duplicate Detection Endpoints
# =====================================================


class DuplicateCandidate(BaseModel):
    """A pair of tracks that might be duplicates."""

    id: str
    track_1_id: str
    track_1_title: str
    track_1_artist: str
    track_1_file_path: str | None
    track_2_id: str
    track_2_title: str
    track_2_artist: str
    track_2_file_path: str | None
    similarity_score: int  # 0-100
    match_type: str  # metadata, fingerprint
    status: str  # pending, confirmed, dismissed
    created_at: str


class DuplicateCandidatesResponse(BaseModel):
    """Response with list of duplicate candidates."""

    candidates: list[DuplicateCandidate]
    total: int
    pending_count: int
    confirmed_count: int
    dismissed_count: int


class ResolveDuplicateRequest(BaseModel):
    """Request to resolve a duplicate candidate."""

    action: str  # keep_first, keep_second, keep_both, dismiss


# Hey future me – dieser Endpoint gibt alle Duplicate Candidates zurück.
# Die Candidates werden vom DuplicateDetectorWorker erstellt und hier für Review angezeigt.
@router.get("/duplicates")
async def list_duplicate_candidates(
    status: str | None = Query(
        None, description="Filter by status: pending, confirmed, dismissed"
    ),
    limit: int = Query(50, description="Max candidates to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session),
) -> DuplicateCandidatesResponse:
    """List duplicate track candidates for review.

    Args:
        status: Optional status filter
        limit: Maximum candidates to return
        offset: Pagination offset
        db: Database session

    Returns:
        List of duplicate candidates with statistics
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import (
        DuplicateCandidateModel,
        TrackModel,
    )

    # Build query
    query = select(DuplicateCandidateModel)
    if status:
        query = query.where(DuplicateCandidateModel.status == status)
    query = query.order_by(DuplicateCandidateModel.similarity_score.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    models = result.scalars().all()

    # Get counts
    count_query = select(
        func.count()
        .filter(DuplicateCandidateModel.status == "pending")
        .label("pending"),
        func.count()
        .filter(DuplicateCandidateModel.status == "confirmed")
        .label("confirmed"),
        func.count()
        .filter(DuplicateCandidateModel.status == "dismissed")
        .label("dismissed"),
        func.count().label("total"),
    ).select_from(DuplicateCandidateModel)
    count_result = await db.execute(count_query)
    counts = count_result.one()

    # Load track details for each candidate
    candidates = []
    for model in models:
        # Get track 1 with artist relationship loaded
        track_1_query = (
            select(TrackModel)
            .where(TrackModel.id == model.track_id_1)
            .options(joinedload(TrackModel.artist))
        )
        track_1_result = await db.execute(track_1_query)
        track_1 = track_1_result.unique().scalar_one_or_none()

        # Get track 2 with artist relationship loaded
        track_2_query = (
            select(TrackModel)
            .where(TrackModel.id == model.track_id_2)
            .options(joinedload(TrackModel.artist))
        )
        track_2_result = await db.execute(track_2_query)
        track_2 = track_2_result.unique().scalar_one_or_none()

        candidates.append(
            DuplicateCandidate(
                id=model.id,
                track_1_id=model.track_id_1,
                track_1_title=track_1.title if track_1 else "Unknown",
                track_1_artist=track_1.artist.name
                if track_1 and track_1.artist
                else "Unknown",
                track_1_file_path=track_1.file_path if track_1 else None,
                track_2_id=model.track_id_2,
                track_2_title=track_2.title if track_2 else "Unknown",
                track_2_artist=track_2.artist.name
                if track_2 and track_2.artist
                else "Unknown",
                track_2_file_path=track_2.file_path if track_2 else None,
                similarity_score=model.similarity_score,
                match_type=model.match_type,
                status=model.status,
                created_at=model.created_at.isoformat(),
            )
        )

    return DuplicateCandidatesResponse(
        candidates=candidates,
        total=counts.total,
        pending_count=counts.pending,
        confirmed_count=counts.confirmed,
        dismissed_count=counts.dismissed,
    )


# Hey future me – dieser Endpoint resolved einen Duplicate Candidate.
# Actions: keep_first (Track 1 behalten), keep_second (Track 2 behalten),
# keep_both (beide behalten, als "nicht duplikat" markieren), dismiss (ignorieren).
@router.post("/duplicates/{candidate_id}/resolve")
async def resolve_duplicate(
    candidate_id: str,
    request: ResolveDuplicateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Resolve a duplicate candidate.

    Args:
        candidate_id: Candidate ID
        request: Resolution action
        db: Database session

    Returns:
        Resolution result
    """
    from datetime import UTC, datetime

    from soulspot.infrastructure.persistence.models import DuplicateCandidateModel

    # Get candidate
    candidate = await db.get(DuplicateCandidateModel, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    action = request.action.lower()

    if action == "dismiss":
        candidate.status = "dismissed"
        candidate.resolution_action = "dismissed"
    elif action == "keep_both":
        candidate.status = "dismissed"
        candidate.resolution_action = "keep_both"
    elif action == "keep_first":
        candidate.status = "confirmed"
        candidate.resolution_action = "keep_first"
        # TODO: Queue deletion of track 2
    elif action == "keep_second":
        candidate.status = "confirmed"
        candidate.resolution_action = "keep_second"
        # TODO: Queue deletion of track 1
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    candidate.reviewed_at = datetime.now(UTC)
    await db.commit()

    return {
        "candidate_id": candidate_id,
        "action": action,
        "status": candidate.status,
        "message": f"Duplicate resolved with action: {action}",
    }


# Hey future me – dieser Endpoint triggert einen manuellen Duplicate Scan.
# Nützlich wenn der User nicht auf den nächsten automatischen Scan warten will.
@router.post("/duplicates/scan")
async def trigger_duplicate_scan(
    request: Any,  # Request object for app.state access
) -> dict[str, Any]:
    """Trigger a manual duplicate scan.

    Returns:
        Scan job information
    """
    if not hasattr(request.app.state, "duplicate_detector_worker"):
        raise HTTPException(
            status_code=503,
            detail="Duplicate detector worker not available",
        )

    worker = request.app.state.duplicate_detector_worker
    job_id = await worker.trigger_scan_now()

    return {
        "message": "Duplicate scan started",
        "job_id": job_id,
    }


# ========================
# Batch Rename Endpoints
# ========================

# Hey future me – Batch Rename ermöglicht das Umbenennen bestehender Dateien
# nach neuen Naming-Templates. Preview zeigt erst, was passieren würde.
# Wichtig: Nur mit dry_run=False werden tatsächlich Dateien umbenannt!
# Das ist ein destruktiver Vorgang - Lidarr könnte Dateien verlieren wenn
# es nicht synchronisiert ist. Daher: IMMER erst Preview, dann mit dry_run=False bestätigen.


class BatchRenamePreviewRequest(BaseModel):
    """Request to preview batch rename operation."""

    limit: int = 100  # Max files to preview


class BatchRenamePreviewItem(BaseModel):
    """Single file rename preview."""

    track_id: str
    current_path: str
    new_path: str
    will_change: bool


class BatchRenamePreviewResponse(BaseModel):
    """Response with batch rename preview."""

    total_files: int
    files_to_rename: int
    preview: list[BatchRenamePreviewItem]


class BatchRenameRequest(BaseModel):
    """Request to execute batch rename."""

    dry_run: bool = True  # Safety: default to dry run
    limit: int | None = None  # Limit files to rename (None = all)


class BatchRenameResult(BaseModel):
    """Single file rename result."""

    track_id: str
    old_path: str
    new_path: str
    success: bool
    error: str | None = None


class BatchRenameResponse(BaseModel):
    """Response from batch rename operation."""

    dry_run: bool
    total_processed: int
    successful: int
    failed: int
    results: list[BatchRenameResult]


# Hey future me - Helper function to convert TrackModel to Track entity
# This centralizes the conversion logic and avoids code duplication.
def _track_model_to_entity(track_model: Any) -> Any:
    """Convert a TrackModel ORM object to a Track domain entity.

    Args:
        track_model: The TrackModel ORM object

    Returns:
        Track domain entity
    """
    from soulspot.domain.entities import Track
    from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId

    return Track(
        id=TrackId.from_string(track_model.id),
        title=track_model.title,
        artist_id=ArtistId.from_string(track_model.artist_id),
        album_id=AlbumId.from_string(track_model.album_id)
        if track_model.album_id
        else None,
        track_number=track_model.track_number,
        disc_number=track_model.disc_number,
    )


@router.post("/batch-rename/preview", response_model=BatchRenamePreviewResponse)
async def preview_batch_rename(
    request: BatchRenamePreviewRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BatchRenamePreviewResponse:
    """Preview batch rename operation.

    Hey future me – zeigt was passieren würde, ohne tatsächlich umzubenennen.
    Lädt die aktuellen Naming-Templates aus der DB und berechnet die neuen
    Pfade für alle Tracks mit file_path. Vergleicht alt vs neu und zeigt
    nur die Dateien die sich ändern würden.

    Args:
        request: Preview request with limit
        db: Database session
        settings: Application settings

    Returns:
        Preview of files that would be renamed
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.postprocessing.renaming_service import (
        RenamingService,
    )
    from soulspot.infrastructure.persistence.models import (
        TrackModel,
    )
    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
    )

    # Initialize services
    app_settings_service = AppSettingsService(db)
    renaming_service = RenamingService(settings)
    renaming_service.set_app_settings_service(app_settings_service)

    # Check if renaming is enabled
    rename_enabled = await app_settings_service.is_rename_tracks_enabled()
    if not rename_enabled:
        return BatchRenamePreviewResponse(
            total_files=0,
            files_to_rename=0,
            preview=[],
        )

    # Get tracks with file paths
    from sqlalchemy import select

    stmt = (
        select(TrackModel).where(TrackModel.file_path.isnot(None)).limit(request.limit)
    )
    result = await db.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(db)
    album_repo = AlbumRepository(db)

    preview_items: list[BatchRenamePreviewItem] = []
    files_to_rename = 0

    for track_model in tracks:
        # Use the model directly instead of converting to entity
        if not track_model.file_path:
            continue

        # Get artist
        from soulspot.domain.value_objects import AlbumId as DomainAlbumId
        from soulspot.domain.value_objects import ArtistId as DomainArtistId

        artist = await artist_repo.get_by_id(
            DomainArtistId.from_string(track_model.artist_id)
        )
        if not artist:
            continue

        # Get album (optional)
        album = None
        if track_model.album_id:
            album = await album_repo.get_by_id(
                DomainAlbumId.from_string(track_model.album_id)
            )

        # Get current path
        current_path = str(track_model.file_path)
        extension = current_path.rsplit(".", 1)[-1] if "." in current_path else "mp3"

        # Generate new filename using async method (uses DB templates)
        track = _track_model_to_entity(track_model)

        try:
            new_relative_path = await renaming_service.generate_filename_async(
                track, artist, album, f".{extension}"
            )
            new_path = str(settings.storage.music_path / new_relative_path)
        except (ValueError, OSError, KeyError) as e:
            # Hey future me - log and skip files where renaming service fails (e.g., bad template,
            # missing metadata, or invalid characters). Continue processing other tracks.
            logger.debug(
                "Skipping track %s in batch rename preview: %s", track_model.id, e
            )
            continue

        # Check if path would change
        will_change = current_path != new_path

        preview_items.append(
            BatchRenamePreviewItem(
                track_id=str(track_model.id),
                current_path=current_path,
                new_path=new_path,
                will_change=will_change,
            )
        )

        if will_change:
            files_to_rename += 1

    return BatchRenamePreviewResponse(
        total_files=len(preview_items),
        files_to_rename=files_to_rename,
        preview=preview_items,
    )


@router.post("/batch-rename", response_model=BatchRenameResponse)
async def execute_batch_rename(
    request: BatchRenameRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BatchRenameResponse:
    """Execute batch rename operation.

    Hey future me – ACHTUNG: Mit dry_run=False werden TATSÄCHLICH Dateien umbenannt!
    Das ist destruktiv. Stelle sicher dass Lidarr nicht gleichzeitig scannt.
    Der Endpoint:
    1. Lädt Naming-Templates aus DB
    2. Iteriert über Tracks mit file_path
    3. Berechnet neue Pfade
    4. Benennt Dateien um (wenn dry_run=False)
    5. Updated Track.file_path in DB

    Bei dry_run=True wird nur simuliert, keine Änderungen.

    Args:
        request: Rename request with dry_run flag
        db: Database session
        settings: Application settings

    Returns:
        Results of rename operation
    """
    import shutil
    from pathlib import Path

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.postprocessing.renaming_service import (
        RenamingService,
    )
    from soulspot.infrastructure.persistence.models import TrackModel
    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
    )

    # Initialize services
    app_settings_service = AppSettingsService(db)
    renaming_service = RenamingService(settings)
    renaming_service.set_app_settings_service(app_settings_service)

    # Check if renaming is enabled
    rename_enabled = await app_settings_service.is_rename_tracks_enabled()
    if not rename_enabled:
        return BatchRenameResponse(
            dry_run=request.dry_run,
            total_processed=0,
            successful=0,
            failed=0,
            results=[],
        )

    # Get tracks with file paths
    from sqlalchemy import select

    stmt = select(TrackModel).where(TrackModel.file_path.isnot(None))
    if request.limit:
        stmt = stmt.limit(request.limit)

    result = await db.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(db)
    album_repo = AlbumRepository(db)

    results: list[BatchRenameResult] = []
    successful = 0
    failed = 0

    for track_model in tracks:
        if not track_model.file_path:
            continue

        current_path = Path(str(track_model.file_path))
        if not current_path.exists() and not request.dry_run:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error="File not found",
                )
            )
            failed += 1
            continue

        # Get artist
        from soulspot.domain.value_objects import AlbumId as DomainAlbumId
        from soulspot.domain.value_objects import ArtistId as DomainArtistId

        artist = await artist_repo.get_by_id(
            DomainArtistId.from_string(track_model.artist_id)
        )
        if not artist:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error="Artist not found",
                )
            )
            failed += 1
            continue

        # Get album (optional)
        album = None
        if track_model.album_id:
            album = await album_repo.get_by_id(
                DomainAlbumId.from_string(track_model.album_id)
            )

        # Create track entity for renaming service
        track = _track_model_to_entity(track_model)

        # Generate new filename
        try:
            extension = current_path.suffix
            new_relative_path = await renaming_service.generate_filename_async(
                track, artist, album, extension
            )
            new_path = settings.storage.music_path / new_relative_path
        except Exception as e:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path="",
                    success=False,
                    error=f"Template error: {e}",
                )
            )
            failed += 1
            continue

        # Skip if path unchanged
        if current_path == new_path:
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path=str(new_path),
                    success=True,
                    error=None,
                )
            )
            successful += 1
            continue

        # Execute rename (if not dry run)
        if not request.dry_run:
            try:
                # Create target directory
                new_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(current_path), str(new_path))

                # Update track in database
                track_model.file_path = str(new_path)
                await db.commit()

                results.append(
                    BatchRenameResult(
                        track_id=str(track_model.id),
                        old_path=str(current_path),
                        new_path=str(new_path),
                        success=True,
                        error=None,
                    )
                )
                successful += 1
            except Exception as e:
                await db.rollback()
                results.append(
                    BatchRenameResult(
                        track_id=str(track_model.id),
                        old_path=str(current_path),
                        new_path=str(new_path),
                        success=False,
                        error=str(e),
                    )
                )
                failed += 1
        else:
            # Dry run - just report what would happen
            results.append(
                BatchRenameResult(
                    track_id=str(track_model.id),
                    old_path=str(current_path),
                    new_path=str(new_path),
                    success=True,
                    error=None,
                )
            )
            successful += 1

    return BatchRenameResponse(
        dry_run=request.dry_run,
        total_processed=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )


# =============================================================================
# LIBRARY ENRICHMENT ENDPOINTS
# =============================================================================
# Hey future me - these endpoints handle Spotify enrichment for local library!
# Enrichment matches local items with Spotify to add artwork, genres, URIs.
# =============================================================================


class EnrichmentStatusResponse(BaseModel):
    """Status of library enrichment."""

    artists_unenriched: int
    albums_unenriched: int
    pending_candidates: int
    is_enrichment_needed: bool


class EnrichmentTriggerResponse(BaseModel):
    """Response after triggering enrichment job."""

    job_id: str
    message: str


class EnrichmentCandidateResponse(BaseModel):
    """A potential Spotify match for review."""

    id: str
    entity_type: str  # 'artist' or 'album'
    entity_id: str
    entity_name: str  # Local entity name (for display)
    spotify_uri: str
    spotify_name: str
    spotify_image_url: str | None
    confidence_score: float
    extra_info: dict[str, Any]


class EnrichmentCandidatesListResponse(BaseModel):
    """List of enrichment candidates."""

    candidates: list[EnrichmentCandidateResponse]
    total: int


class ApplyCandidateRequest(BaseModel):
    """Request to apply a selected candidate."""

    candidate_id: str


@router.get(
    "/enrichment/status",
    response_model=EnrichmentStatusResponse,
    summary="Get library enrichment status",
)
async def get_enrichment_status(
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentStatusResponse:
    """Get current status of library enrichment.

    Returns counts of:
    - Unenriched artists (have local files but no Spotify URI)
    - Unenriched albums (have local files but no Spotify URI)
    - Pending candidates (ambiguous matches waiting for user review)
    """
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        EnrichmentCandidateModel,
        TrackModel,
    )

    # Count unenriched artists (with local tracks)
    has_local_artist_tracks = (
        select(TrackModel.id)
        .where(TrackModel.artist_id == ArtistModel.id)
        .where(TrackModel.file_path.isnot(None))
        .exists()
    )
    artists_stmt = (
        select(func.count(ArtistModel.id))
        .where(ArtistModel.spotify_uri.is_(None))
        .where(has_local_artist_tracks)
    )
    artists_result = await db.execute(artists_stmt)
    artists_unenriched = artists_result.scalar() or 0

    # Count unenriched albums (with local tracks)
    has_local_album_tracks = (
        select(TrackModel.id)
        .where(TrackModel.album_id == AlbumModel.id)
        .where(TrackModel.file_path.isnot(None))
        .exists()
    )
    albums_stmt = (
        select(func.count(AlbumModel.id))
        .where(AlbumModel.spotify_uri.is_(None))
        .where(has_local_album_tracks)
    )
    albums_result = await db.execute(albums_stmt)
    albums_unenriched = albums_result.scalar() or 0

    # Count pending candidates
    candidates_stmt = select(func.count(EnrichmentCandidateModel.id)).where(
        EnrichmentCandidateModel.is_selected == False,  # noqa: E712
        EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
    )
    candidates_result = await db.execute(candidates_stmt)
    pending_candidates = candidates_result.scalar() or 0

    return EnrichmentStatusResponse(
        artists_unenriched=artists_unenriched,
        albums_unenriched=albums_unenriched,
        pending_candidates=pending_candidates,
        is_enrichment_needed=(artists_unenriched + albums_unenriched) > 0,
    )


@router.post(
    "/enrichment/trigger",
    response_model=EnrichmentTriggerResponse,
    summary="Trigger library enrichment job",
)
async def trigger_enrichment(
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentTriggerResponse:
    """Manually trigger a library enrichment job.

    This queues a background job that will:
    1. Find unenriched artists and albums
    2. Search Spotify for matches
    3. Apply high-confidence matches automatically
    4. Create candidates for ambiguous matches (user review needed)
    """
    job = await job_queue.enqueue(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        payload={"triggered_by": "manual_api"},
    )

    return EnrichmentTriggerResponse(
        job_id=str(job.id),
        message="Enrichment job queued successfully",
    )


@router.get(
    "/enrichment/candidates",
    response_model=EnrichmentCandidatesListResponse,
    summary="Get enrichment candidates for review",
)
async def get_enrichment_candidates(
    entity_type: str | None = Query(None, description="Filter by 'artist' or 'album'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentCandidatesListResponse:
    """Get pending enrichment candidates for user review.

    Returns candidates where multiple Spotify matches were found
    and user needs to select the correct one.
    """
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        EnrichmentCandidateModel,
    )

    # Build query for pending candidates
    stmt = (
        select(EnrichmentCandidateModel)
        .where(EnrichmentCandidateModel.is_selected == False)  # noqa: E712
        .where(EnrichmentCandidateModel.is_rejected == False)  # noqa: E712
        .order_by(EnrichmentCandidateModel.confidence_score.desc())
        .limit(limit)
        .offset(offset)
    )

    if entity_type:
        stmt = stmt.where(EnrichmentCandidateModel.entity_type == entity_type)

    result = await db.execute(stmt)
    candidates = result.scalars().all()

    # Count total
    count_stmt = select(func.count(EnrichmentCandidateModel.id)).where(
        EnrichmentCandidateModel.is_selected == False,  # noqa: E712
        EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
    )
    if entity_type:
        count_stmt = count_stmt.where(
            EnrichmentCandidateModel.entity_type == entity_type
        )

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get entity names for display
    response_candidates = []
    for candidate in candidates:
        # Get entity name
        if candidate.entity_type == "artist":
            entity_stmt = select(ArtistModel.name).where(
                ArtistModel.id == candidate.entity_id
            )
        else:
            entity_stmt = select(AlbumModel.title).where(
                AlbumModel.id == candidate.entity_id
            )

        entity_result = await db.execute(entity_stmt)
        entity_name = entity_result.scalar() or "Unknown"

        response_candidates.append(
            EnrichmentCandidateResponse(
                id=candidate.id,
                entity_type=candidate.entity_type,
                entity_id=candidate.entity_id,
                entity_name=entity_name,
                spotify_uri=candidate.spotify_uri,
                spotify_name=candidate.spotify_name,
                spotify_image_url=candidate.spotify_image_url,
                confidence_score=candidate.confidence_score,
                extra_info=candidate.extra_info or {},
            )
        )

    return EnrichmentCandidatesListResponse(
        candidates=response_candidates,
        total=total,
    )


@router.post(
    "/enrichment/candidates/{candidate_id}/apply",
    summary="Apply selected enrichment candidate",
)
async def apply_enrichment_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Apply a user-selected enrichment candidate.

    This will:
    1. Mark the candidate as selected
    2. Update the entity (artist/album) with Spotify URI and image
    3. Reject other candidates for the same entity
    """
    from datetime import UTC, datetime

    from sqlalchemy import select, update

    from soulspot.application.services.spotify_image_service import SpotifyImageService
    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        EnrichmentCandidateModel,
    )

    # Get candidate
    stmt = select(EnrichmentCandidateModel).where(
        EnrichmentCandidateModel.id == candidate_id
    )
    result = await db.execute(stmt)
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.is_selected or candidate.is_rejected:
        raise HTTPException(status_code=400, detail="Candidate already processed")

    # Update entity with Spotify data
    image_service = SpotifyImageService(settings)
    image_downloaded = False

    if candidate.entity_type == "artist":
        model_stmt = select(ArtistModel).where(ArtistModel.id == candidate.entity_id)
        model_result = await db.execute(model_stmt)
        model = model_result.scalar_one_or_none()

        if model:
            model.spotify_uri = candidate.spotify_uri
            model.image_url = candidate.spotify_image_url
            model.updated_at = datetime.now(UTC)

            # Download image
            if candidate.spotify_image_url:
                try:
                    spotify_id = candidate.spotify_uri.split(":")[-1]
                    await image_service.download_artist_image(
                        spotify_id, candidate.spotify_image_url
                    )
                    image_downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download artist image: {e}")

    else:  # album
        model_stmt = select(AlbumModel).where(AlbumModel.id == candidate.entity_id)
        model_result = await db.execute(model_stmt)
        model = model_result.scalar_one_or_none()

        if model:
            model.spotify_uri = candidate.spotify_uri
            model.artwork_url = candidate.spotify_image_url
            model.updated_at = datetime.now(UTC)

            # Download image
            if candidate.spotify_image_url:
                try:
                    spotify_id = candidate.spotify_uri.split(":")[-1]
                    local_path = await image_service.download_album_image(
                        spotify_id, candidate.spotify_image_url
                    )
                    model.artwork_path = str(local_path)
                    image_downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download album image: {e}")

    # Mark candidate as selected
    candidate.is_selected = True
    candidate.updated_at = datetime.now(UTC)

    # Reject other candidates for same entity
    reject_stmt = (
        update(EnrichmentCandidateModel)
        .where(EnrichmentCandidateModel.entity_type == candidate.entity_type)
        .where(EnrichmentCandidateModel.entity_id == candidate.entity_id)
        .where(EnrichmentCandidateModel.id != candidate_id)
        .where(EnrichmentCandidateModel.is_selected == False)  # noqa: E712
        .values(is_rejected=True, updated_at=datetime.now(UTC))
    )
    await db.execute(reject_stmt)

    await db.commit()

    return {
        "success": True,
        "message": f"Applied enrichment for {candidate.entity_type}",
        "spotify_uri": candidate.spotify_uri,
        "image_downloaded": image_downloaded,
    }


@router.post(
    "/enrichment/candidates/{candidate_id}/reject",
    summary="Reject an enrichment candidate",
)
async def reject_enrichment_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reject an enrichment candidate.

    Use this when the suggested Spotify match is incorrect.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from soulspot.infrastructure.persistence.models import EnrichmentCandidateModel

    stmt = select(EnrichmentCandidateModel).where(
        EnrichmentCandidateModel.id == candidate_id
    )
    result = await db.execute(stmt)
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.is_selected or candidate.is_rejected:
        raise HTTPException(status_code=400, detail="Candidate already processed")

    candidate.is_rejected = True
    candidate.updated_at = datetime.now(UTC)
    await db.commit()

    return {
        "success": True,
        "message": "Candidate rejected",
    }
