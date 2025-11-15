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


class PauseResumeResponse(BaseModel):
    """Response model for pause/resume operations."""

    message: str
    status: str


class BatchDownloadRequest(BaseModel):
    """Request model for batch download operations."""

    track_ids: list[str]
    priority: int = 0


class BatchDownloadResponse(BaseModel):
    """Response model for batch download operations."""

    message: str
    job_ids: list[str]
    total_tracks: int


class UpdatePriorityRequest(BaseModel):
    """Request model for updating download priority."""

    priority: int


class BatchActionRequest(BaseModel):
    """Request model for batch operations on downloads."""

    download_ids: list[str]
    action: str  # "cancel", "pause", "resume", "priority"
    priority: int | None = None


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
    try:
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
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid download ID: {str(e)}"
        ) from e


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
