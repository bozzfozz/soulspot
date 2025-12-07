"""Download management endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from soulspot.api.dependencies import (
    check_slskd_available,
    get_download_repository,
    get_download_worker,
    get_job_queue,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import JobQueue
from soulspot.domain.entities import Download, DownloadStatus
from soulspot.domain.value_objects import DownloadId, TrackId
from soulspot.infrastructure.persistence.repositories import DownloadRepository

router = APIRouter()


# Hey future me, these are DTOs for the download API! Simple Pydantic schemas for request/response validation
# and JSON serialization. PauseResumeResponse is used by both pause and resume endpoints (same shape). Batch
# operations use BatchDownloadRequest/Response for multi-track downloads. UpdatePriorityRequest for changing
# queue order. BatchActionRequest is for bulk operations (cancel/pause/resume multiple downloads at once).
# Keep these simple - complex business logic belongs in domain entities or use cases, not API schemas!


class PauseResumeResponse(BaseModel):
    """Response model for pause/resume operations."""

    message: str
    status: str


# Yo, batch download request schema! track_ids is list of UUID strings - no validation here that they're
# valid track IDs (that happens in the endpoint). priority applies to ALL tracks in batch - can't set
# different priorities per track. Default priority 0 is normal queue order. Higher numbers = higher priority
# (processed first). For huge batches (1000+ tracks), consider chunking or async processing!
class BatchDownloadRequest(BaseModel):
    """Request model for batch download operations."""

    track_ids: list[str]
    priority: int = 0


# Hey, batch download response! job_ids lets caller track each individual download (poll /downloads/{job_id}
# for progress). total_tracks is redundant with len(job_ids) but explicit is better than implicit! If some
# tracks failed to queue (invalid IDs), this response won't reflect that - endpoint fails all-or-nothing.
# Consider changing to partial success model where we return both succeeded and failed job_ids.
class BatchDownloadResponse(BaseModel):
    """Response model for batch download operations."""

    message: str
    job_ids: list[str]
    total_tracks: int


# Listen, super simple priority update request! Just one field - the new priority number. No validation
# constraints here (min/max), that's handled by domain layer. Priority can be negative if you want to deprioritize
# downloads (process them LAST). Common values: 0 = normal, 10 = high, 100 = urgent, -10 = low priority.
class UpdatePriorityRequest(BaseModel):
    """Request model for updating download priority."""

    priority: int


# Yo, batch actions request for bulk operations! download_ids is list of download UUIDs to operate on.
# action string determines what to do: "cancel", "pause", "resume", "priority". priority field is only used
# for action="priority", otherwise it's ignored. This is a multi-purpose schema which is flexible but less
# type-safe than separate schemas per action. Consider splitting into CancelBatchRequest, PauseBatchRequest, etc
# for better API clarity and validation!
class BatchActionRequest(BaseModel):
    """Request model for batch operations on downloads."""

    download_ids: list[str]
    action: str  # "cancel", "pause", "resume", "priority"
    priority: int | None = None


# Hey future me - Single track download request! This is what the UI sends when clicking
# "Download" on a track. Can use EITHER track_id (local DB ID) OR spotify_id (for Spotify tracks).
# If spotify_id is provided without track_id, we'll look up or create the track in our DB.
class SingleDownloadRequest(BaseModel):
    """Request for single track download."""

    track_id: str | None = None
    spotify_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    priority: int = 0


# Hey future me, this creates a single download entry in the queue!
# Works whether slskd is online or offline - if offline, creates with WAITING status.
# When slskd comes back online, QueueDispatcherWorker picks up WAITING downloads.
# This endpoint is called by HTMX from track cards, album pages, etc.
# Accepts either track_id (local DB) or spotify_id (Spotify tracks).
@router.post("/")
async def create_download(
    request: SingleDownloadRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
    download_worker: DownloadWorker = Depends(get_download_worker),
    slskd_available: bool = Depends(check_slskd_available),
) -> dict[str, Any]:
    """Create a single download for a track.
    
    Works whether slskd is online or offline. If offline, download is queued
    with WAITING status and will be processed when slskd becomes available.
    
    Accepts either track_id (local DB ID) or spotify_id (Spotify track ID).
    
    Args:
        request: Download request with track_id/spotify_id and optional metadata
        download_repository: Download repository
        download_worker: Download worker for queueing
        slskd_available: Whether slskd is currently available
    
    Returns:
        Created download info including ID and status
    """
    # Must provide either track_id or spotify_id
    if not request.track_id and not request.spotify_id:
        raise HTTPException(status_code=400, detail="Either track_id or spotify_id required")
    
    try:
        # Determine track_id to use
        track_id_str = request.track_id
        
        # If only spotify_id provided, use it as the track reference
        # (In a full implementation, we'd look up or create the track in our DB first)
        if not track_id_str and request.spotify_id:
            # For now, use spotify_id directly as track reference
            # TODO: Look up track by spotify_id or create placeholder
            track_id_str = request.spotify_id
        
        track_id = TrackId.from_string(track_id_str)
        
        # Check if download already exists for this track
        existing = await download_repository.get_by_track(track_id)
        if existing and existing.status not in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.FAILED]:
            return {
                "message": "Download already in queue",
                "id": str(existing.id.value),
                "status": existing.status.value,
            }
        
        # Create new download with appropriate status
        download_id = DownloadId.generate()
        
        # If slskd is available, try to queue immediately
        if slskd_available:
            try:
                job_id = await download_worker.enqueue_download(
                    track_id=track_id,
                    priority=request.priority,
                )
                return {
                    "message": "Download queued successfully",
                    "id": job_id,
                    "status": "queued",
                }
            except Exception:
                # Fall through to WAITING status
                pass
        
        # slskd unavailable or error - create Download with WAITING status
        download = Download(
            id=download_id,
            track_id=track_id,
            status=DownloadStatus.WAITING,
            priority=request.priority,
        )
        await download_repository.add(download)
        
        return {
            "message": "Download added to waitlist (downloader offline)",
            "id": str(download.id.value),
            "status": "waiting",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create download: {str(e)}")


# Hey future me, this lists downloads with optional status filter and PROPER DB-LEVEL pagination!
# Previously we loaded ALL downloads and sliced in Python - that's O(N) memory! Now we push limit/offset
# to DB which is O(limit) memory. For large queues (1000+ downloads), this makes a HUGE difference.
# Default limit is 100 (user requested), max is 500 to prevent abuse. Total count is fetched separately
# for pagination UI. Status filter can be: waiting, pending, queued, downloading, completed, failed, cancelled.
@router.get("/")
async def list_downloads(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(100, ge=1, le=500, description="Number of downloads per page"),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """List all downloads with pagination.

    Args:
        status: Filter by status (waiting, queued, downloading, completed, failed)
        page: Page number (1-indexed, default 1)
        limit: Number of downloads per page (default 100, max 500)
        download_repository: Download repository

    Returns:
        Paginated list of downloads with total count and page info
    """
    # Calculate offset from page number
    offset = (page - 1) * limit

    # Get paginated downloads from DB (efficient - only loads requested page)
    if status:
        downloads = await download_repository.list_by_status(
            status=status, limit=limit, offset=offset
        )
        total = await download_repository.count_by_status(status)
    else:
        downloads = await download_repository.list_active(limit=limit, offset=offset)
        total = await download_repository.count_active()

    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_previous = page > 1

    return {
        "downloads": [
            {
                "id": str(download.id.value),
                "track_id": str(download.track_id.value),
                "status": download.status.value,
                "priority": download.priority,
                "progress_percent": download.progress_percent,
                "source_url": download.source_url,
                "target_path": str(download.target_path)
                if download.target_path
                else None,
                "error_message": download.error_message,
                "started_at": download.started_at.isoformat()
                if download.started_at
                else None,
                "completed_at": download.completed_at.isoformat()
                if download.completed_at
                else None,
                "created_at": download.created_at.isoformat(),
                "updated_at": download.updated_at.isoformat(),
            }
            for download in downloads
        ],
        # Pagination metadata
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "status": status,
    }


# Yo, this is a GLOBAL pause - stops ALL download processing across the entire system! The job queue stops
# consuming download jobs. Queued jobs stay queued, running jobs finish their current operation then pause.
# This is for emergencies (network maintenance, disk full, etc). Users might expect individual download pause
# but this is all-or-nothing! Make sure UI is clear about this. Calling pause when already paused is safe
# (idempotent). No database changes here - just queue state.
@router.post("/pause")
async def pause_downloads(
    job_queue: JobQueue = Depends(get_job_queue),
) -> PauseResumeResponse:
    """Pause all download processing globally.

    This endpoint pauses the download queue, preventing any new downloads
    from starting. Currently running downloads will continue to completion.

    Args:
        job_queue: Job queue dependency

    Returns:
        Pause status message
    """
    await job_queue.pause()
    return PauseResumeResponse(
        message="Download queue paused successfully", status="paused"
    )


# Listen up, resume is the opposite of pause - starts consuming download jobs again! Queued jobs start
# processing immediately. If queue was never paused, this is a no-op (safe to call). This is GLOBAL like
# pause - all download processing resumes. If you paused because disk was full, make sure you fixed that
# before resuming or downloads will just fail again!
@router.post("/resume")
async def resume_downloads(
    job_queue: JobQueue = Depends(get_job_queue),
) -> PauseResumeResponse:
    """Resume all download processing globally.

    This endpoint resumes the download queue after it has been paused,
    allowing queued downloads to be processed.

    Args:
        job_queue: Job queue dependency

    Returns:
        Resume status message
    """
    await job_queue.resume()
    return PauseResumeResponse(
        message="Download queue resumed successfully", status="active"
    )


# Hey, this is your dashboard endpoint - shows queue health at a glance! The stats come from job queue's
# internal counters - active, queued, completed, failed. The paused flag tells you if queue is processing.
# max_concurrent_downloads is from config - how many jobs run in parallel. If active_downloads is stuck
# at max for a long time, your downloads are slow or stuck! If queued_downloads is huge and growing, you're
# queueing faster than downloading (increase concurrency or downloads are failing). NOW INCLUDES waiting_downloads
# which are downloads waiting for slskd to become available! Poll this every few seconds for live dashboard.
@router.get("/status")
async def get_queue_status(
    job_queue: JobQueue = Depends(get_job_queue),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get download queue status.

    Returns information about the current state of the download queue,
    including pause status, concurrent download settings, and waiting downloads.

    Args:
        job_queue: Job queue dependency
        download_repository: Download repository for counting waiting downloads

    Returns:
        Queue status information including waiting downloads count
    """
    stats = job_queue.get_stats()

    # Count downloads waiting for slskd to become available
    waiting_count = await download_repository.count_by_status(
        DownloadStatus.WAITING.value
    )

    return {
        "paused": job_queue.is_paused(),
        "max_concurrent_downloads": job_queue.get_max_concurrent_jobs(),
        "active_downloads": stats.get("running", 0),
        "queued_downloads": stats.get("pending", 0),
        "waiting_downloads": waiting_count,  # Downloads waiting for slskd
        "total_jobs": stats.get("total_jobs", 0),
        "completed": stats.get("completed", 0),
        "failed": stats.get("failed", 0),
        "cancelled": stats.get("cancelled", 0),
    }


# Hey future me - Bulk download request for Spotify albums/tracks!
# Uses spotify_ids (not local track_ids) because tracks may not exist in our DB yet.
# Template sends this from "Download All" button on album pages.
class BulkDownloadRequest(BaseModel):
    """Request for bulk download with Spotify IDs."""

    tracks: list[str]  # List of spotify_ids
    artist: str | None = None
    album: str | None = None
    priority: int = 0


# Hey future me - Bulk download endpoint for album "Download All" buttons!
# Accepts spotify_ids directly (not local track_ids). Creates downloads with WAITING
# status if slskd is offline. Tracks without local DB entry use spotify_id as reference.
@router.post("/bulk")
async def bulk_download(
    request: BulkDownloadRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
    download_worker: DownloadWorker = Depends(get_download_worker),
    slskd_available: bool = Depends(check_slskd_available),
) -> dict[str, Any]:
    """Bulk download tracks by Spotify ID.
    
    For album "Download All" buttons - accepts spotify_ids directly.
    Creates downloads with WAITING status if slskd is offline.
    
    Args:
        request: Bulk download request with spotify_ids
        download_repository: Download repository
        download_worker: Download worker for queueing
        slskd_available: Whether slskd is currently available
    
    Returns:
        Summary of queued downloads
    """
    if not request.tracks:
        raise HTTPException(status_code=400, detail="No tracks provided")
    
    queued = 0
    waiting = 0
    skipped = 0
    errors = []
    
    for spotify_id in request.tracks:
        try:
            # Use spotify_id as track reference (in production, look up local track)
            track_id = TrackId.from_string(spotify_id)
            
            # Check if already in queue
            existing = await download_repository.get_by_track(track_id)
            if existing and existing.status not in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.FAILED]:
                skipped += 1
                continue
            
            if slskd_available:
                try:
                    await download_worker.enqueue_download(
                        track_id=track_id,
                        priority=request.priority,
                    )
                    queued += 1
                except Exception:
                    # Fall back to WAITING
                    download = Download(
                        id=DownloadId.generate(),
                        track_id=track_id,
                        status=DownloadStatus.WAITING,
                        priority=request.priority,
                    )
                    await download_repository.add(download)
                    waiting += 1
            else:
                # slskd offline - add to waitlist
                download = Download(
                    id=DownloadId.generate(),
                    track_id=track_id,
                    status=DownloadStatus.WAITING,
                    priority=request.priority,
                )
                await download_repository.add(download)
                waiting += 1
                
        except Exception as e:
            errors.append(f"{spotify_id}: {str(e)}")
    
    total = queued + waiting
    message_parts = []
    if queued > 0:
        message_parts.append(f"{queued} queued")
    if waiting > 0:
        message_parts.append(f"{waiting} in waitlist")
    if skipped > 0:
        message_parts.append(f"{skipped} skipped (already in queue)")
    
    return {
        "message": f"Downloads: {', '.join(message_parts)}" if message_parts else "No tracks to download",
        "total": total,
        "queued": queued,
        "waiting": waiting,
        "skipped": skipped,
        "errors": errors if errors else None,
    }


# Yo, batch download is for "download this whole playlist" or "download my favorites" - multiple tracks at
# once! Now with WAITING status support: if slskd is unavailable, downloads go to WAITING status instead
# of failing. QueueDispatcherWorker will pick them up when slskd becomes available. ALL tracks get same
# priority (no per-track priority in batch). If ANY track_id is invalid, we fail IMMEDIATELY with 400 -
# this is all-or-nothing! The job_ids list lets caller track each download separately (when enqueued
# directly) or download_ids (when put in WAITING status).
@router.post("/batch")
async def batch_download(
    request: BatchDownloadRequest,
    download_worker: DownloadWorker = Depends(get_download_worker),
    download_repository: DownloadRepository = Depends(get_download_repository),
    slskd_available: bool = Depends(check_slskd_available),
) -> BatchDownloadResponse:
    """Batch download multiple tracks.

    Enqueues multiple tracks for download with the specified priority.
    If slskd is unavailable, downloads are created with WAITING status
    and will be dispatched when slskd becomes available.

    Args:
        request: Batch download request with track IDs and priority
        download_worker: Download worker dependency
        download_repository: Download repository for WAITING status
        slskd_available: Whether slskd is currently available

    Returns:
        Batch download response with job IDs or download IDs
    """
    from soulspot.domain.exceptions import ValidationException

    if not request.track_ids:
        raise HTTPException(
            status_code=400, detail="At least one track ID must be provided"
        )

    job_ids = []
    waiting_count = 0

    for track_id_str in request.track_ids:
        try:
            track_id = TrackId.from_string(track_id_str)

            if slskd_available:
                # slskd is available - enqueue job directly
                job_id = await download_worker.enqueue_download(
                    track_id=track_id,
                    priority=request.priority,
                )
                job_ids.append(job_id)
            else:
                # slskd unavailable - create Download with WAITING status
                # QueueDispatcherWorker will dispatch when slskd comes online
                download = Download(
                    id=DownloadId.from_string(str(uuid.uuid4())),
                    track_id=track_id,
                    status=DownloadStatus.WAITING,
                    priority=request.priority,
                )
                await download_repository.add(download)
                job_ids.append(str(download.id.value))
                waiting_count += 1

        except (ValueError, ValidationException) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid track ID '{track_id_str}': {str(e)}",
            ) from e

    if waiting_count > 0:
        message = (
            f"Downloads queued for {len(request.track_ids)} tracks "
            f"({waiting_count} waiting for download manager)"
        )
    else:
        message = f"Batch download initiated for {len(request.track_ids)} tracks"

    return BatchDownloadResponse(
        message=message,
        job_ids=job_ids,
        total_tracks=len(request.track_ids),
    )


# Hey, this gets status of a SINGLE download by ID. Returns full download details including progress_percent
# (0-100), status (queued/downloading/completed/failed), error_message if failed, timestamps for tracking.
# UI polls this endpoint for progress bars! Don't poll faster than 1 second or you'll hammer the DB. If
# download is completed, progress_percent should be 100 and completed_at should be set. If failed, check
# error_message for why (file not found, network timeout, slskd error, etc). 404 if download_id is invalid.
@router.get("/{download_id}")
async def get_download_status(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get download status.

    Args:
        download_id: Download ID
        download_repository: Download repository

    Returns:
        Download status and progress
    """
    download_id_obj = DownloadId.from_string(download_id)
    download = await download_repository.get_by_id(download_id_obj)

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    return {
        "id": str(download.id.value),
        "track_id": str(download.track_id.value),
        "status": download.status.value,
        "priority": download.priority,
        "progress_percent": download.progress_percent,
        "source_url": download.source_url,
        "target_path": str(download.target_path) if download.target_path else None,
        "error_message": download.error_message,
        "started_at": download.started_at.isoformat() if download.started_at else None,
        "completed_at": download.completed_at.isoformat()
        if download.completed_at
        else None,
        "created_at": download.created_at.isoformat(),
        "updated_at": download.updated_at.isoformat(),
    }


# Yo, cancel is PERMANENT - once cancelled, the download is DONE (won't auto-retry). If download is currently
# running, this DOESN'T kill the slskd download! It just marks our DB record as cancelled. The download might
# finish on slskd side anyway. We use download.cancel() domain method which enforces business rules (maybe
# can't cancel completed downloads?). The ValueError catch is for domain exceptions - invalid state transitions.
# After cancel, if user wants this track, they need to queue a NEW download (or use retry if you change cancel
# to failed status).
@router.post("/{download_id}/cancel")
async def cancel_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Cancel a download.

    Args:
        download_id: Download ID to cancel
        download_repository: Download repository

    Returns:
        Cancellation status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
        download = await download_repository.get_by_id(download_id_obj)

        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        # Use domain method to cancel download
        download.cancel()
        await download_repository.update(download)

        return {
            "message": "Download cancelled",
            "download_id": download_id,
            "status": download.status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid download ID or operation: {str(e)}"
        ) from e


# Listen up, retry is for failed downloads - requeue them to try again! We check status == FAILED because
# you can't retry a download that's queued, running, or completed (that's nonsense!). This changes status
# to QUEUED so the download worker picks it up again. DON'T clear error_message yet - keep it until new
# attempt starts (helps debug "why did it fail last time"). The download worker will retry with same params
# (search query, quality preference, etc) - if those were wrong, retry won't help! Consider letting user
# override params on retry.
@router.post("/{download_id}/retry")
async def retry_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Retry a failed download.

    Args:
        download_id: Download ID to retry
        download_repository: Download repository

    Returns:
        Retry status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
        download = await download_repository.get_by_id(download_id_obj)

        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        if download.status != DownloadStatus.FAILED:
            raise HTTPException(
                status_code=400, detail="Can only retry failed downloads"
            )

        # Update status to queued using domain enum
        download.status = DownloadStatus.QUEUED
        download.error_message = None
        await download_repository.update(download)

        return {
            "message": "Download retry initiated",
            "download_id": download_id,
            "status": download.status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid download ID: {str(e)}"
        ) from e


# Hey, priority update lets you bump a download to the front of the queue! Higher priority = processed first.
# This is useful for "I want THIS song NOW" - change priority to 999 and it jumps ahead of priority 0 downloads.
# We use download.update_priority() domain method which might have validation (priority range limits, etc).
# IMPORTANT: Changing priority of a RUNNING download doesn't pause/restart it! Priority only affects queue order.
# If download is already running or completed, priority change is basically pointless (but we allow it anyway).
@router.post("/{download_id}/priority")
async def update_download_priority(
    download_id: str,
    request: UpdatePriorityRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Update download priority.

    Args:
        download_id: Download ID
        request: Priority update request
        download_repository: Download repository

    Returns:
        Updated download status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
        download = await download_repository.get_by_id(download_id_obj)

        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        # Update priority using domain method
        download.update_priority(request.priority)
        await download_repository.update(download)

        return {
            "message": "Priority updated successfully",
            "download_id": download_id,
            "priority": download.priority,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid priority or download ID: {str(e)}"
        ) from e


# Yo, this is INDIVIDUAL download pause (unlike global /pause endpoint!). Marks this download as paused so
# worker skips it. If download is currently running, this doesn't actually stop the slskd transfer! The file
# might finish downloading anyway. We use download.pause() domain method which enforces state rules (can't
# pause a completed download, etc). Paused downloads stay paused until explicitly resumed - they don't auto-retry.
# Use case: "pause low-priority downloads to speed up high-priority ones".
@router.post("/{download_id}/pause")
async def pause_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Pause a download.

    Args:
        download_id: Download ID to pause
        download_repository: Download repository

    Returns:
        Pause status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
        download = await download_repository.get_by_id(download_id_obj)

        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        # Pause download using domain method
        download.pause()
        await download_repository.update(download)

        return {
            "message": "Download paused",
            "download_id": download_id,
            "status": download.status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid download ID or operation: {str(e)}"
        ) from e


# Listen, resume is for unpausing an individual download (not the global queue!). Changes status back to
# QUEUED so worker picks it up. If download was never paused, resume() domain method might throw ValueError
# (can't resume something that isn't paused!). After resume, download goes to back of its priority level -
# doesn't jump to front. If you want it processed NOW, resume then update priority to high number.
@router.post("/{download_id}/resume")
async def resume_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Resume a paused download.

    Args:
        download_id: Download ID to resume
        download_repository: Download repository

    Returns:
        Resume status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
        download = await download_repository.get_by_id(download_id_obj)

        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        # Resume download using domain method
        download.resume()
        await download_repository.update(download)

        return {
            "message": "Download resumed",
            "download_id": download_id,
            "status": download.status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid download ID or operation: {str(e)}"
        ) from e


# Hey future me, batch-action is for "select 50 downloads and cancel them all" or "pause these 10 downloads"
# kind of operations! It loops through download_ids and applies the action (cancel/pause/resume/priority) to
# each. This is PARTIAL SUCCESS - some downloads might succeed, some fail, we return both lists! Don't fail
# the whole batch if one download is invalid. The action is a string ("cancel", "pause", etc) - no enum, so
# invalid actions get caught in the else branch. For priority action, request.priority MUST be provided or we
# error out. This can be SLOW for hundreds of downloads - consider pagination or async job for huge batches.
@router.post("/batch-action")
async def batch_action(
    request: BatchActionRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Perform batch operations on multiple downloads.

    Args:
        request: Batch action request
        download_repository: Download repository

    Returns:
        Batch action results
    """
    if not request.download_ids:
        raise HTTPException(
            status_code=400, detail="At least one download ID must be provided"
        )

    results = []
    errors = []

    for download_id in request.download_ids:
        try:
            download_id_obj = DownloadId.from_string(download_id)
            download = await download_repository.get_by_id(download_id_obj)

            if not download:
                errors.append({"id": download_id, "error": "Not found"})
                continue

            # Perform the requested action
            if request.action == "cancel":
                download.cancel()
            elif request.action == "pause":
                download.pause()
            elif request.action == "resume":
                download.resume()
            elif request.action == "priority" and request.priority is not None:
                download.update_priority(request.priority)
            else:
                errors.append({"id": download_id, "error": "Invalid action"})
                continue

            await download_repository.update(download)
            results.append({"id": download_id, "status": "success"})

        except ValueError:
            # Sanitize error message to avoid exposing internal details
            error_msg = "Invalid operation or download ID"
            errors.append({"id": download_id, "error": error_msg})

    return {
        "message": f"Batch action '{request.action}' completed",
        "total": len(request.download_ids),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
