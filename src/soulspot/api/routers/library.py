"""Library management API endpoints."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.observability.log_messages import LogMessages

from soulspot.api.dependencies import (
    get_db_session,
    get_job_queue,
    get_library_scanner_service,
    get_spotify_plugin,
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

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

# Initialize templates (same pattern as ui.py)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/library", tags=["library"])

# Hey future me - keep the giant library router readable by splitting feature areas.
# This sub-router owns the duplicate artist/album merge endpoints (still mounted under /library/*).
from soulspot.api.routers.library_duplicates import router as duplicates_router

router.include_router(duplicates_router)


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
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """Start a library scan (DEPRECATED - use /library/import/scan instead).
    
    This endpoint is deprecated and redirects to the new JobQueue-based scan.
    Use POST /library/import/scan for new integrations!

    Args:
        request: Scan request with path (IGNORED - always scans configured music_path)
        job_queue: Job queue for background processing

    Returns:
        Job information (NEW: returns job_id instead of scan_id for consistency)
    """
    logger.warning(
        "DEPRECATED: /library/scan endpoint called. Use /library/import/scan instead!"
    )
    
    try:
        # Queue the scan job using new JobQueue system
        job_id = await job_queue.enqueue(
            job_type=JobType.LIBRARY_SCAN,
            payload={
                "incremental": None,  # Auto-detect
                "defer_cleanup": True,
            },
            max_retries=1,
            priority=5,
        )

        return {
            "scan_id": job_id,  # Backward compatibility (actually job_id)
            "job_id": job_id,  # New field for clarity
            "status": "pending",
            "scan_path": str(request.scan_path) if request.scan_path else "auto",
            "total_files": 0,  # Will be calculated during scan
            "message": "Library scan started (using new JobQueue backend)",
            "_deprecated": True,
            "_use_instead": "/api/library/import/scan",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start library scan: {str(e)}"
        ) from e


@router.get("/scan/{scan_id}")
async def get_scan_status(
    scan_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> ScanResponse:
    """Get library scan status (DEPRECATED - use /library/import/status/{job_id} instead).
    
    This endpoint is deprecated and redirects to the new JobQueue-based status.
    Use GET /library/import/status/{job_id} for new integrations!

    Args:
        scan_id: Scan/Job ID (accepts both old scan_id and new job_id)
        job_queue: Job queue for background processing

    Returns:
        Scan status and progress (adapted to old format for backward compatibility)
    """
    logger.warning(
        "DEPRECATED: /library/scan/{scan_id} endpoint called. "
        "Use /library/import/status/{job_id} instead!"
    )
    
    try:
        # Try to get job from queue (scan_id is actually job_id now)
        job = await job_queue.get_job(scan_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Scan/Job not found")
        
        result = job.result or {}
        stats = result.get("stats", {})
        
        return ScanResponse(
            scan_id=scan_id,
            status=job.status,
            scan_path="auto",  # Not tracked in new system
            total_files=stats.get("scanned", 0),
            scanned_files=stats.get("imported", 0),
            broken_files=stats.get("errors", 0),
            duplicate_files=0,  # Not tracked in library scan
            progress_percent=result.get("progress", 0.0) * 100,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get scan status: {str(e)}"
        ) from e

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
    # Hey future me - NOW uses StatsService! Clean Architecture.
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
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> dict[str, Any]:
    """Get albums with missing tracks.

    Args:
        incomplete_only: Only return incomplete albums
        min_track_count: Minimum track count to consider
        session: Database session
        spotify_plugin: SpotifyPlugin (handles token internally)

    Returns:
        List of albums with completeness information
    """
    # Provider + Auth checks using can_use()
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
        # SpotifyPlugin handles token management internally!
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
        Album completeness information
    """
    # Provider + Auth checks using can_use()
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
# - Exact name matching for artists/albums (from Lidarr folder structure)
# - Incremental scan (only new/modified files based on mtime)
# - Metadata extraction via mutagen (in ThreadPool for performance)
# - Deferred cleanup (runs as separate job for UI responsiveness)
# Poll /import/status/{job_id} to check progress!
# NOTE: Accepts Form data (from HTMX hx-vals) instead of JSON body for browser compatibility.
@router.post("/import/scan", response_model=ImportScanResponse)
async def start_import_scan(
    incremental: bool | None = Form(None),  # None = auto-detect!
    defer_cleanup: bool = Form(True),
    job_queue: JobQueue = Depends(get_job_queue),
) -> ImportScanResponse:
    """Start a library import scan as background job.

    Scans the music directory, extracts metadata, and imports tracks
    into the database using Lidarr folder structure.

    SMART AUTO-DETECT MODE (Dec 2025):
    - If incremental=None (default): Auto-detects based on existing data
      - Empty DB → Full scan (process all files)
      - Has tracks → Incremental (only new/modified files)
    - Explicit True/False still works for manual override

    Args:
        incremental: Scan mode (None=auto, True=incremental, False=full)
        defer_cleanup: If True, cleanup runs as separate job (default: True).
        job_queue: Job queue for background processing

    Returns:
        Job ID for status polling
    """
    try:
        # Queue the scan job
        job_id = await job_queue.enqueue(
            job_type=JobType.LIBRARY_SCAN,
            payload={
                "incremental": incremental,  # None = auto-detect in worker
                "defer_cleanup": defer_cleanup,
            },
            max_retries=1,  # Don't retry full scans
            priority=5,  # Medium priority
        )

        mode_str = "auto-detect" if incremental is None else f"incremental={incremental}"
        return ImportScanResponse(
            job_id=job_id,
            status="pending",
            message=f"Library import scan queued ({mode_str}, defer_cleanup={defer_cleanup})",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start import scan: {str(e)}"
        ) from e

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
    context: dict[str, Any] = {
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


# Hey future me - SSE endpoint for real-time scan progress!
# Replaces inefficient polling (every 2s) with server-pushed events.
# Browser opens persistent connection, we push JSON events as progress changes.
# Format: "data: {...json...}\n\n" - standard SSE protocol.
# Connection closes automatically when scan completes/fails.
@router.get("/import/status/{job_id}/stream")
async def stream_import_scan_status(
    job_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """Stream import scan job status via Server-Sent Events (SSE).

    Real-time progress updates without polling overhead. Browser receives
    push notifications as scan progresses. Much more efficient than
    polling every 2 seconds!

    Args:
        job_id: Job ID from start_import_scan
        job_queue: Job queue instance

    Returns:
        SSE event stream with progress updates

    Event format:
        data: {"status": "running", "progress": 45.5, "stats": {...}}

    Final event when complete:
        data: {"status": "completed", "progress": 100, "stats": {...}, "done": true}
    """
    import asyncio
    import json

    from starlette.responses import StreamingResponse

    async def event_generator() -> Any:
        """Generate SSE events as scan progresses."""
        last_progress = -1.0
        poll_interval = 0.3  # Check every 300ms, but only send if changed

        while True:
            job = await job_queue.get_job(job_id)

            if not job:
                # Job not found - send error and close
                yield f"data: {json.dumps({'error': 'Job not found', 'done': True})}\n\n"
                break

            # Build event data
            progress = 0.0
            stats: dict[str, Any] = {}

            if job.result and isinstance(job.result, dict):
                progress = job.result.get("progress", 0.0)
                stats = job.result.get("stats", {})

            event_data = {
                "job_id": job.id,
                "status": job.status.value,
                "progress": round(progress, 1),
                "stats": stats,
                "is_running": job.status == JobStatus.RUNNING,
                "is_completed": job.status == JobStatus.COMPLETED,
                "is_failed": job.status == JobStatus.FAILED,
            }

            # Add timestamps if available
            if job.started_at:
                event_data["started_at"] = job.started_at.isoformat()
            if job.completed_at:
                event_data["completed_at"] = job.completed_at.isoformat()
            if job.error:
                event_data["error"] = job.error

            # Only send if progress changed (avoid flooding)
            # Or if status changed (completed/failed)
            if progress != last_progress or job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
            ):
                last_progress = progress
                yield f"data: {json.dumps(event_data)}\n\n"

            # Check if scan finished
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                # Send final "done" event so client knows to close
                event_data["done"] = True
                yield f"data: {json.dumps(event_data)}\n\n"
                break

            # Wait before next check
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
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
    # Hey future me - NOW uses LibraryCleanupService! Clean Architecture.
    from soulspot.application.services.library_cleanup_service import (
        LibraryCleanupService,
    )

    service = LibraryCleanupService(session)
    stats = await service.clear_local_library()

    return {
        "success": True,
        "message": "Local library cleared successfully",
        **stats,
    }


@router.delete("/clear-all")
async def clear_entire_library(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """⚠️ DEV ONLY: Clear ENTIRE library (local + Spotify + Deezer + Tidal).
    
    Hey future me - this is the ULTRA NUCLEAR OPTION! Only for development/testing!
    DELETES EVERYTHING:
    - ALL artists (local + Spotify + Deezer + hybrid)
    - ALL albums (local + Spotify + Deezer + hybrid)
    - ALL tracks (local + Spotify + Deezer + hybrid)
    
    ⚠️ TODO: REMOVE THIS ENDPOINT BEFORE PRODUCTION!
    This is ONLY for development to quickly reset the entire library.
    
    Returns:
        Statistics about deleted entities
    """
    from sqlalchemy import delete, func, select
    from soulspot.infrastructure.persistence.models import (
        ArtistModel,
        AlbumModel,
        TrackModel,
    )
    
    # Count before deletion
    artists_count = await session.scalar(select(func.count(ArtistModel.id)))
    albums_count = await session.scalar(select(func.count(AlbumModel.id)))
    tracks_count = await session.scalar(select(func.count(TrackModel.id)))
    
    # Nuclear option: DELETE EVERYTHING (CASCADE will handle relationships)
    await session.execute(delete(TrackModel))
    await session.execute(delete(AlbumModel))
    await session.execute(delete(ArtistModel))
    await session.commit()
    
    return {
        "success": True,
        "message": "⚠️ ENTIRE library cleared (local + Spotify + Deezer + Tidal)",
        "deleted_artists": artists_count or 0,
        "deleted_albums": albums_count or 0,
        "deleted_tracks": tracks_count or 0,
        "warning": "This was a COMPLETE wipe. Sync from providers to restore data.",
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
    session: AsyncSession = Depends(get_db_session),
) -> DuplicateCandidatesResponse:
    """List duplicate track candidates for review.

    Args:
        status: Optional status filter
        limit: Maximum candidates to return
        offset: Pagination offset
        session: Database session

    Returns:
        List of duplicate candidates with statistics
    """
    # Hey future me - NOW uses DuplicateService! Clean Architecture.
    from soulspot.application.services.duplicate_service import DuplicateService

    service = DuplicateService(session)
    result = await service.list_candidates(status, limit, offset)

    # Convert to response format
    candidates = [
        DuplicateCandidate(
            id=c["id"],
            track_1_id=c["track_1"]["id"],
            track_1_title=c["track_1"]["title"],
            track_1_artist=c["track_1"]["artist"],
            track_1_file_path=c["track_1"]["file_path"],
            track_2_id=c["track_2"]["id"],
            track_2_title=c["track_2"]["title"],
            track_2_artist=c["track_2"]["artist"],
            track_2_file_path=c["track_2"]["file_path"],
            similarity_score=c["similarity_score"],
            match_type=c["match_type"],
            status=c["status"],
            created_at=c["created_at"],
        )
        for c in result["candidates"]
    ]

    counts = result["counts"]
    return DuplicateCandidatesResponse(
        candidates=candidates,
        total=result["total"],
        pending_count=counts["pending"],
        confirmed_count=counts["confirmed"],
        dismissed_count=counts["dismissed"],
    )


# Hey future me – dieser Endpoint resolved einen Duplicate Candidate.
# Actions: keep_first (Track 1 behalten), keep_second (Track 2 behalten),
# keep_both (beide behalten, als "nicht duplikat" markieren), dismiss (ignorieren).
@router.post("/duplicates/{candidate_id}/resolve")
async def resolve_duplicate(
    candidate_id: str,
    request: ResolveDuplicateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Resolve a duplicate candidate.

    Args:
        candidate_id: Candidate ID
        request: Resolution action
        session: Database session

    Returns:
        Resolution result
    """
    # Hey future me - NOW uses DuplicateService! Clean Architecture.
    from soulspot.application.services.duplicate_service import DuplicateService
    from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError

    service = DuplicateService(session)

    try:
        result = await service.resolve_candidate(candidate_id, request.action)
        return {
            "candidate_id": candidate_id,
            "action": request.action,
            "message": f"Duplicate resolved with action: {request.action}",
            "deleted_track_id": result.get("deleted_track_id"),
        }
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Hey future me – dieser Endpoint triggert einen manuellen Duplicate Scan.
# Nützlich wenn der User nicht auf den nächsten automatischen Scan warten will.
@router.post("/duplicates/scan")
async def trigger_duplicate_scan(
    request: Request,
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
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BatchRenamePreviewResponse:
    """Preview batch rename operation.

    Hey future me – zeigt was passieren würde, ohne tatsächlich umzubenennen.
    Lädt die aktuellen Naming-Templates aus der DB und berechnet die neuen
    Pfade für alle Tracks mit file_path. Vergleicht alt vs neu und zeigt
    nur die Dateien die sich ändern würden.

    Args:
        request: Preview request with limit
        session: Database session
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
    app_settings_service = AppSettingsService(session)
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
    result = await session.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)

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
    session: AsyncSession = Depends(get_db_session),
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
        session: Database session
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
    app_settings_service = AppSettingsService(session)
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

    result = await session.execute(stmt)
    tracks = result.scalars().all()

    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)

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
                await session.commit()

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
                await session.rollback()
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
    is_running: bool = False  # True if enrichment job is currently running
    last_job_completed: bool | None = None  # True if last job succeeded, False if failed


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
    session: AsyncSession = Depends(get_db_session),
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentStatusResponse:
    """Get current status of library enrichment.

    Returns counts of:
    - Unenriched artists (have local files but no Spotify URI)
    - Unenriched albums (have local files but no Spotify URI)
    - Pending candidates (ambiguous matches waiting for user review)
    - is_running: True if enrichment job is currently running
    - last_job_completed: True if last job succeeded, False if failed, None if no jobs
    """
    # Hey future me - NOW uses EnrichmentService! Clean Architecture.
    from soulspot.application.services.enrichment_service import EnrichmentService
    from soulspot.application.workers.job_queue import JobStatus, JobType

    service = EnrichmentService(session)
    status_dto = await service.get_enrichment_status()

    # Check job queue status
    is_running = False
    last_job_completed: bool | None = None

    enrichment_jobs = await job_queue.list_jobs(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        limit=1,
    )

    if enrichment_jobs:
        latest_job = enrichment_jobs[0]
        if latest_job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            is_running = True
        elif latest_job.status == JobStatus.COMPLETED:
            last_job_completed = True
        elif latest_job.status == JobStatus.FAILED:
            last_job_completed = False

    return EnrichmentStatusResponse(
        artists_unenriched=status_dto.artists_unenriched,
        albums_unenriched=status_dto.albums_unenriched,
        pending_candidates=status_dto.pending_candidates,
        is_enrichment_needed=status_dto.is_enrichment_needed,
        is_running=is_running,
        last_job_completed=last_job_completed,
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
    job_id = await job_queue.enqueue(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        payload={"triggered_by": "manual_api"},
    )

    return EnrichmentTriggerResponse(
        job_id=job_id,
        message="Enrichment job queued successfully",
    )


@router.post(
    "/enrichment/repair-artwork",
    summary="Repair missing artwork for enriched artists",
)
async def repair_missing_artwork(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Re-download artwork for artists that have Spotify URI but missing artwork.

    Hey future me - this fixes artists whose initial enrichment succeeded (got Spotify URI)
    but artwork download failed (network issues, rate limits, etc.).

    Use case: "DJ Paul Elstak" was enriched to "Paul Elstak" but has no image.
    """
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings.",
        )
    if not spotify_plugin.can_use(PluginCapability.GET_ARTIST):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    from soulspot.application.services.local_library_enrichment_service import (
        LocalLibraryEnrichmentService,
    )

    service = LocalLibraryEnrichmentService(
        session=session,
        spotify_plugin=spotify_plugin,
        settings=settings,
    )

    result = await service.repair_missing_artwork(limit=100)
    return result


@router.get(
    "/enrichment/candidates",
    response_model=EnrichmentCandidatesListResponse,
    summary="Get enrichment candidates for review",
)
async def get_enrichment_candidates(
    entity_type: str | None = Query(None, description="Filter by 'artist' or 'album'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> EnrichmentCandidatesListResponse:
    """Get pending enrichment candidates for user review.

    Returns candidates where multiple Spotify matches were found
    and user needs to select the correct one.
    """
    # Hey future me - NOW uses EnrichmentService! Clean Architecture.
    from soulspot.application.services.enrichment_service import EnrichmentService

    service = EnrichmentService(session)
    dtos, total = await service.list_candidates(
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    # Convert DTOs to response models
    response_candidates = [
        EnrichmentCandidateResponse(
            id=dto.id,
            entity_type=dto.entity_type,
            entity_id=dto.entity_id,
            entity_name=dto.entity_name,
            spotify_uri=dto.spotify_uri,
            spotify_name=dto.spotify_name,
            spotify_image_url=dto.spotify_image_url,
            confidence_score=dto.confidence_score,
            extra_info=dto.extra_info,
        )
        for dto in dtos
    ]

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
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Apply a user-selected enrichment candidate.

    This will:
    1. Mark the candidate as selected
    2. Update the entity (artist/album) with Spotify URI and image
    3. Reject other candidates for the same entity

    Hey future me - provider check is implicit here because enrichment candidates
    only exist if Spotify enrichment ran (which checks is_provider_enabled).
    But we still check before downloading images in case settings changed.
    """
    # Hey future me - NOW uses EnrichmentService! Clean Architecture.
    from soulspot.application.services.enrichment_service import EnrichmentService
    from soulspot.application.services.artwork_service import ArtworkService
    from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError

    service = EnrichmentService(session)
    image_service = ArtworkService(settings)

    try:
        result = await service.apply_candidate(candidate_id, image_service)
        return {
            "success": True,
            "message": result["message"],
            "spotify_uri": result["spotify_uri"],
        }
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/enrichment/candidates/{candidate_id}/reject",
    summary="Reject an enrichment candidate",
)
async def reject_enrichment_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reject an enrichment candidate.

    Use this when the suggested Spotify match is incorrect.
    """
    # Hey future me - NOW uses EnrichmentCandidateRepository! Clean Architecture.
    from soulspot.infrastructure.persistence.repositories import (
        EnrichmentCandidateRepository,
    )

    repo = EnrichmentCandidateRepository(session)

    try:
        await repo.mark_rejected(candidate_id)
        await session.commit()
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Candidate not found")
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Candidate rejected",
    }


# =============================================================================
# MUSICBRAINZ DISAMBIGUATION ENRICHMENT
# =============================================================================


class DisambiguationEnrichmentRequest(BaseModel):
    """Request to enrich disambiguation from MusicBrainz."""
    limit: int = 50


@router.post("/enrich-disambiguation")
async def enrich_disambiguation(
    request: DisambiguationEnrichmentRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Enrich artists and albums with MusicBrainz disambiguation data.

    Hey future me - this is for Lidarr-style naming templates that use {ArtistDisambiguation}!
    MusicBrainz provides disambiguation strings like "(US rock band)" to differentiate
    artists with the same name (e.g., multiple artists named "Nirvana").

    This endpoint:
    1. Finds artists/albums without disambiguation
    2. Searches MusicBrainz for matches
    3. Stores disambiguation strings from MB results

    Note: Respects MusicBrainz 1 req/sec rate limit, so large batches take time.
    Returns HTML for HTMX integration on the library page.
    """
    from soulspot.application.services.local_library_enrichment_service import (
        LocalLibraryEnrichmentService,
    )

    service = LocalLibraryEnrichmentService(
        session=session,
        spotify_plugin=None,
        settings=settings,
    )

    try:
        result = await service.enrich_disambiguation_batch(limit=request.limit)

        # Hey future me - return HTML for HTMX integration!
        # This shows directly in the library page status area.
        artists_enriched = result.get("artists_enriched", 0)
        albums_enriched = result.get("albums_enriched", 0)

        if result.get("skipped"):
            # Provider disabled
            return HTMLResponse(
                '''<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #3b82f6; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                    <i class="bi bi-info-circle"></i>
                    <span>MusicBrainz provider is disabled in Settings.</span>
                </div>'''
            )

        if artists_enriched == 0 and albums_enriched == 0:
            return HTMLResponse(
                '''<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #3b82f6; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                    <i class="bi bi-check-circle"></i>
                    <span>All items already have disambiguation data or no matches found.</span>
                </div>'''
            )

        return HTMLResponse(
            f'''<div class="musicbrainz-result" style="background: rgba(186, 83, 45, 0.1); border: 1px solid rgba(186, 83, 45, 0.2); color: #e69d3c; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                <i class="bi bi-check-circle-fill"></i>
                <span>Enriched <strong>{artists_enriched}</strong> artists and <strong>{albums_enriched}</strong> albums with disambiguation data.</span>
            </div>'''
        )

    except Exception as e:
        logger.error(
            LogMessages.sync_failed(
                sync_type="disambiguation_enrichment",
                reason="MusicBrainz enrichment failed",
                hint="Check MusicBrainz API availability and rate limits (1 req/sec)"
            ).format(),
            exc_info=True
        )
        return HTMLResponse(
            f'''<div class="musicbrainz-result" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #ef4444; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                <i class="bi bi-exclamation-triangle"></i>
                <span>Error: {str(e)}</span>
            </div>''',
            status_code=500,
        )

