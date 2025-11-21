"""Download management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from soulspot.api.dependencies import (
    get_download_repository,
    get_download_worker,
    get_job_queue,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import JobQueue
from soulspot.domain.entities import DownloadStatus
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


# Hey future me, this lists downloads with optional status filter and pagination. If status is provided,
# we filter to just that status (queued, downloading, completed, failed). If not, we get all "active" downloads
# (probably means not completed/cancelled - check the repo method!). The pagination here is in-memory slicing
# [skip:skip+limit] which is INEFFICIENT - we fetch ALL downloads then slice! Should push limit/offset to DB
# query. Total is len(downloads) BEFORE slicing, so pagination math is correct. Don't cache this - download
# status changes constantly!
@router.get("/")
async def list_downloads(
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of downloads to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of downloads to return"),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """List all downloads.

    Args:
        status: Filter by status (queued, downloading, completed, failed)
        skip: Number of downloads to skip
        limit: Number of downloads to return
        download_repository: Download repository

    Returns:
        List of downloads
    """
    if status:
        downloads = await download_repository.list_by_status(status)
    else:
        downloads = await download_repository.list_active()

    # Apply pagination
    paginated_downloads = downloads[skip : skip + limit]

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
            for download in paginated_downloads
        ],
        "total": len(downloads),
        "status": status,
        "skip": skip,
        "limit": limit,
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
# queueing faster than downloading (increase concurrency or downloads are failing). Poll this every few seconds
# for live dashboard.
@router.get("/status")
async def get_queue_status(
    job_queue: JobQueue = Depends(get_job_queue),
) -> dict[str, Any]:
    """Get download queue status.

    Returns information about the current state of the download queue,
    including pause status and concurrent download settings.

    Args:
        job_queue: Job queue dependency

    Returns:
        Queue status information
    """
    stats = job_queue.get_stats()
    return {
        "paused": job_queue.is_paused(),
        "max_concurrent_downloads": job_queue.get_max_concurrent_jobs(),
        "active_downloads": stats.get("running", 0),
        "queued_downloads": stats.get("pending", 0),
        "total_jobs": stats.get("total_jobs", 0),
        "completed": stats.get("completed", 0),
        "failed": stats.get("failed", 0),
        "cancelled": stats.get("cancelled", 0),
    }


# Yo, batch download is for "download this whole playlist" or "download my favorites" - multiple tracks at
# once! We loop and call enqueue_download for each track_id. ALL tracks get same priority (no per-track
# priority in batch). If ANY track_id is invalid, we fail IMMEDIATELY with 400 - this is all-or-nothing!
# Consider changing to "enqueue what we can, return errors for bad IDs" for better UX. The job_ids list
# lets caller track each download separately. For huge batches (1000+ tracks), this could timeout - consider
# async job for batch operations.
@router.post("/batch")
async def batch_download(
    request: BatchDownloadRequest,
    download_worker: DownloadWorker = Depends(get_download_worker),
) -> BatchDownloadResponse:
    """Batch download multiple tracks.

    Enqueues multiple tracks for download with the specified priority.
    All tracks in the batch will have the same priority level.

    Args:
        request: Batch download request with track IDs and priority
        download_worker: Download worker dependency

    Returns:
        Batch download response with job IDs
    """
    from soulspot.domain.exceptions import ValidationException

    if not request.track_ids:
        raise HTTPException(
            status_code=400, detail="At least one track ID must be provided"
        )

    job_ids = []
    for track_id_str in request.track_ids:
        try:
            track_id = TrackId.from_string(track_id_str)
            job_id = await download_worker.enqueue_download(
                track_id=track_id,
                priority=request.priority,
            )
            job_ids.append(job_id)
        except (ValueError, ValidationException) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid track ID '{track_id_str}': {str(e)}",
            ) from e

    return BatchDownloadResponse(
        message=f"Batch download initiated for {len(request.track_ids)} tracks",
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
        "started_at": download.started_at.isoformat()
        if download.started_at
        else None,
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
