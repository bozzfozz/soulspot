"""Library scan and import endpoints - LOCAL ONLY, NO PLUGINS!

Hey future me - this file handles all library scanning operations:
- Starting scans (full or incremental)
- Polling scan status (JSON, HTML, SSE)
- Listing and cancelling scan jobs
- Getting scan summary

All operations here work with LOCAL files only:
- Reads from filesystem (music directory)
- Writes to database (track/album/artist entities)
- NO external API calls (Spotify, Deezer, etc.)

External enrichment happens AFTER scan, via separate EnrichmentService.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from soulspot.api.dependencies import (
    get_job_queue,
    get_library_scanner_service,
)
from soulspot.application.services.library_scanner_service import LibraryScannerService
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType

logger = logging.getLogger(__name__)

# Initialize templates locally (avoids circular import from main.py)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["library-scan"])


# =============================================================================
# Response Models
# =============================================================================


class ImportScanResponse(BaseModel):
    """Response from import scan start."""

    job_id: str
    status: str
    message: str


class ScanRequest(BaseModel):
    """Request to start a library scan (legacy)."""

    scan_path: str | None = None


class ScanResponse(BaseModel):
    """Response from scan status (legacy)."""

    scan_id: str
    status: str
    scan_path: str | None = None
    total_files: int = 0
    scanned_files: int = 0
    broken_files: int = 0
    duplicate_files: int = 0
    progress_percent: float = 0.0


# =============================================================================
# DEPRECATED ENDPOINTS (for backward compatibility)
# =============================================================================


@router.post("/scan")
async def start_library_scan(
    request: ScanRequest,
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """Start a library scan (DEPRECATED - use /import/scan instead).

    Hey future me - this endpoint is deprecated!
    Use POST /library/import/scan for new integrations.
    This exists only for backward compatibility with old clients.

    Args:
        request: Scan request with path (IGNORED - always scans configured music_path)
        job_queue: Job queue for background processing

    Returns:
        Job information (returns job_id for compatibility)
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
    """Get library scan status (DEPRECATED - use /import/status/{job_id} instead).

    Hey future me - this endpoint is deprecated!
    Use GET /library/import/status/{job_id} for new integrations.

    Args:
        scan_id: Scan/Job ID (accepts both old scan_id and new job_id)
        job_queue: Job queue for background processing

    Returns:
        Scan status (legacy format)
    """
    logger.warning(
        "DEPRECATED: /library/scan/{scan_id} endpoint called. "
        "Use /library/import/status/{job_id} instead!"
    )

    job = await job_queue.get_job(scan_id)

    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Extract progress from job result
    progress = 0.0
    stats: dict[str, Any] = {}
    if job.result and isinstance(job.result, dict):
        progress = job.result.get("progress", 0.0)
        stats = job.result.get("stats", {})

    return ScanResponse(
        scan_id=scan_id,
        status=job.status.value,
        scan_path=None,
        total_files=stats.get("total_files", 0),
        scanned_files=stats.get("processed_files", 0),
        broken_files=stats.get("broken_files", 0),
        duplicate_files=stats.get("duplicate_files", 0),
        progress_percent=progress,
    )


# =============================================================================
# NEW IMPORT ENDPOINTS (with JobQueue)
# =============================================================================


@router.post("/import/scan", response_model=ImportScanResponse)
async def start_import_scan(
    incremental: bool | None = Form(None),  # None = auto-detect!
    defer_cleanup: bool = Form(True),
    job_queue: JobQueue = Depends(get_job_queue),
) -> ImportScanResponse:
    """Start a library import scan as background job.

    Hey future me - this is the MAIN scan endpoint!
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

        mode_str = (
            "auto-detect" if incremental is None else f"incremental={incremental}"
        )
        return ImportScanResponse(
            job_id=job_id,
            status="pending",
            message=f"Library import scan queued ({mode_str}, defer_cleanup={defer_cleanup})",
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

    response: dict[str, Any] = {
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

    Hey future me - this is for the UI!
    Returns an HTML fragment that can be swapped into the page.

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


@router.get("/import/status/{job_id}/stream")
async def stream_import_scan_status(
    job_id: str,
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """Stream import scan job status via Server-Sent Events (SSE).

    Hey future me - SSE is way better than polling!
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

            event_data: dict[str, Any] = {
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
