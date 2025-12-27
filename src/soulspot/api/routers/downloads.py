"""Download management endpoints."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    check_slskd_available,
    get_db_session,
    get_download_repository,
    get_download_worker,
    get_job_queue,
    get_track_repository,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import JobQueue
from soulspot.domain.entities import Download, DownloadStatus
from soulspot.domain.value_objects import DownloadId, SpotifyUri, TrackId
from soulspot.infrastructure.observability.log_messages import LogMessages
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    TrackRepository,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
# action string determines what to do: "cancel", "pause", "resume", "priority", "retry".
# priority field is only used for action="priority", otherwise it's ignored.
# retry action schedules failed downloads for automatic retry (resets retry_count).
# This is a multi-purpose schema which is flexible but less type-safe than separate schemas per action.
class BatchActionRequest(BaseModel):
    """Request model for batch operations on downloads."""

    download_ids: list[str]
    action: str  # "cancel", "pause", "resume", "priority", "retry"
    priority: int | None = None


# Hey future me - Single track download request! This is what the UI sends when clicking
# "Download" on a track. Can use ANY provider ID:
# - track_id: Local DB UUID (for tracks without provider IDs)
# - spotify_id: Spotify track URI (spotify:track:ID)
# - deezer_id: Deezer track ID
# - tidal_id: Tidal track ID
# Priority: spotify_id > deezer_id > tidal_id > track_id (fallback).
# If provider ID is given, we look up the track in our DB first.
class SingleDownloadRequest(BaseModel):
    """Request for single track download."""

    track_id: str | None = None
    spotify_id: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    priority: int = 0


# Hey future me, this creates a single download entry in the queue!
# Works whether slskd is online or offline - if offline, creates with WAITING status.
# When slskd comes back online, QueueDispatcherWorker picks up WAITING downloads.
# This endpoint is called by HTMX from track cards, album pages, etc.
# Accepts either track_id (local DB) or spotify_id (Spotify tracks).
#
# WICHTIG: Pfad ist "" statt "/" um 307 redirects zu vermeiden!
# FastAPI macht sonst /api/downloads -> /api/downloads/ redirect.
@router.post("")
async def create_download(
    request: SingleDownloadRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    download_worker: DownloadWorker = Depends(get_download_worker),
    slskd_available: bool = Depends(check_slskd_available),
) -> dict[str, Any]:
    """Create a single download for a track.

    Works whether slskd is online or offline. If offline, download is queued
    with WAITING status and will be processed when slskd becomes available.

    Accepts track_id (local DB ID) OR any provider ID (spotify_id, deezer_id, tidal_id).
    If provider ID is provided, looks up the track in DB first. If not found,
    returns 404 (track must be imported first via sync or manual import).

    Args:
        request: Download request with track_id/provider_id and optional metadata
        download_repository: Download repository
        track_repository: Track repository for provider ID lookup
        download_worker: Download worker for queueing
        slskd_available: Whether slskd is currently available

    Returns:
        Created download info including ID and status
    """
    # Must provide at least one ID
    if not any(
        [request.track_id, request.spotify_id, request.deezer_id, request.tidal_id]
    ):
        raise HTTPException(
            status_code=400,
            detail="Must provide one of: track_id, spotify_id, deezer_id, tidal_id",
        )

    try:
        # Determine track_id to use
        track_id_str = request.track_id

        # Hey future me - Multi-provider lookup! Try each provider ID in priority order.
        # Priority: spotify_id > deezer_id > tidal_id > track_id (fallback).
        # This matches the frontend logic and ensures we use the most authoritative ID.
        if not track_id_str:
            existing_track = None
            provider_name = None

            # Try Spotify ID first
            if request.spotify_id:
                spotify_uri = SpotifyUri.from_string(request.spotify_id)
                existing_track = await track_repository.get_by_spotify_uri(spotify_uri)
                provider_name = "spotify"
                provider_id = request.spotify_id

            # Try Deezer ID second
            elif request.deezer_id:
                # Look up track by deezer_id
                from sqlalchemy import select

                from soulspot.infrastructure.persistence.models import TrackModel

                stmt = select(TrackModel).where(
                    TrackModel.deezer_id == request.deezer_id
                )
                result = await track_repository.session.execute(stmt)
                model = result.scalar_one_or_none()
                if model:
                    from soulspot.domain.value_objects import TrackId as DomainTrackId

                    existing_track = await track_repository.get_by_id(
                        DomainTrackId.from_string(model.id)
                    )
                provider_name = "deezer"
                provider_id = request.deezer_id

            # Try Tidal ID third
            elif request.tidal_id:
                # Look up track by tidal_id
                from sqlalchemy import select

                from soulspot.infrastructure.persistence.models import TrackModel

                stmt = select(TrackModel).where(TrackModel.tidal_id == request.tidal_id)
                result = await track_repository.session.execute(stmt)
                model = result.scalar_one_or_none()
                if model:
                    from soulspot.domain.value_objects import TrackId as DomainTrackId

                    existing_track = await track_repository.get_by_id(
                        DomainTrackId.from_string(model.id)
                    )
                provider_name = "tidal"
                provider_id = request.tidal_id

            if existing_track:
                # Found track - use its ID
                track_id_str = str(existing_track.id.value)
                logger.debug(
                    f"Found track by {provider_name}_id: {provider_id} -> {track_id_str}"
                )
            else:
                # Track not in DB - user needs to import it first
                logger.warning(
                    LogMessages.file_operation_failed(
                        operation="track_lookup",
                        path=f"{provider_name}:{provider_id}",
                        reason="Track not found in database",
                        hint="Import track first via sync or manual import",
                    ).format()
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Track with {provider_name}_id '{provider_id}' not found in database. "
                    "Please import the track first (via sync or manual import).",
                )

        track_id = TrackId.from_string(track_id_str)

        # Check if download already exists for this track
        existing = await download_repository.get_by_track(track_id)
        if existing and existing.status not in [
            DownloadStatus.COMPLETED,
            DownloadStatus.CANCELLED,
            DownloadStatus.FAILED,
        ]:
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
            except Exception as e:
                # Log the error for debugging but fall through to WAITING status
                logger.warning(
                    LogMessages.download_failed(
                        download_id="<new>",
                        track_name="<unknown>",
                        reason="Failed to queue download immediately",
                        hint="Download will be created in WAITING status for later retry",
                    ).format(),
                    exc_info=e,
                )

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
        raise HTTPException(
            status_code=500, detail=f"Failed to create download: {str(e)}"
        ) from e


# =========================================================================
# Album Download Endpoint
# =========================================================================


class AlbumDownloadRequest(BaseModel):
    """Request for downloading all tracks of an album.

    Hey future me - provide ONE of these IDs:
    - spotify_id: Spotify album ID (from new_releases page)
    - deezer_id: Deezer album ID
    - album_id: Our local DB album UUID

    The endpoint will fetch all tracks and queue them individually.
    """

    spotify_id: str | None = None
    deezer_id: str | None = None
    album_id: str | None = None
    title: str | None = None
    artist: str | None = None
    quality_filter: str | None = None  # "flac", "320", "any"
    priority: int = 10


class AlbumDownloadResponse(BaseModel):
    """Response from album download queue operation."""

    message: str
    album_title: str
    artist_name: str
    total_tracks: int
    queued_count: int
    already_downloaded: int
    skipped_count: int
    failed_count: int
    job_ids: list[str]
    errors: list[str]
    success: bool


@router.post("/album")
async def create_album_download(
    request: AlbumDownloadRequest,
    session: AsyncSession = Depends(get_db_session),
    job_queue: JobQueue = Depends(get_job_queue),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> AlbumDownloadResponse:
    """Queue all tracks of an album for download.

    Hey future me - this is the "Download Album" button endpoint!
    Called from new_releases.html, album detail pages, etc.

    Supports albums from:
    - Spotify (provide spotify_id)
    - Deezer (provide deezer_id)
    - Local library (provide album_id)

    The use case fetches all tracks, creates them in DB if needed,
    and queues each track individually for download.

    Returns details about what was queued:
    - queued_count: Number of tracks added to download queue
    - already_downloaded: Tracks that already have file_path
    - failed_count: Tracks that failed to queue
    """
    from soulspot.application.use_cases.queue_album_downloads import (
        QueueAlbumDownloadsRequest,
        QueueAlbumDownloadsUseCase,
    )
    from soulspot.config.settings import get_settings

    # Validate request
    if not request.spotify_id and not request.deezer_id and not request.album_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide one of: spotify_id, deezer_id, or album_id",
        )

    # Initialize plugins based on what ID was provided
    spotify_plugin = None
    deezer_plugin = None

    settings = get_settings()

    if request.spotify_id:
        try:
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )
            from soulspot.infrastructure.plugins import SpotifyPlugin

            # Get token from session (via app state or request)
            # For now, create plugin without token - it will fail if auth required
            spotify_client = SpotifyClient(settings.spotify)
            spotify_plugin = SpotifyPlugin(client=spotify_client, access_token=None)
            logger.debug("Created SpotifyPlugin for album download")
        except Exception as e:
            logger.warning(
                LogMessages.connection_failed(
                    service="SpotifyPlugin",
                    target="Plugin initialization",
                    reason="Failed to create SpotifyPlugin instance",
                    hint="Check Spotify API credentials in app settings",
                ).format(),
                exc_info=e,
            )

    if request.deezer_id:
        try:
            from soulspot.infrastructure.plugins import DeezerPlugin

            deezer_plugin = DeezerPlugin()
            logger.debug("Created DeezerPlugin for album download")
        except Exception as e:
            logger.warning(
                LogMessages.connection_failed(
                    service="DeezerPlugin",
                    target="Plugin initialization",
                    reason="Failed to create DeezerPlugin instance",
                    hint="Check Deezer API availability",
                ).format(),
                exc_info=e,
            )

    # Create and execute use case
    use_case = QueueAlbumDownloadsUseCase(
        session=session,
        job_queue=job_queue,
        track_repository=track_repository,
        spotify_plugin=spotify_plugin,
        deezer_plugin=deezer_plugin,
    )

    use_case_request = QueueAlbumDownloadsRequest(
        spotify_id=request.spotify_id,
        deezer_id=request.deezer_id,
        album_id=request.album_id,
        title=request.title,
        artist=request.artist,
        quality_filter=request.quality_filter,
        priority=request.priority,
    )

    result = await use_case.execute(use_case_request)

    # Build response message
    if result.success:
        message = f"Queued {result.queued_count} tracks for download"
        if result.already_downloaded > 0:
            message += f" ({result.already_downloaded} already downloaded)"
    else:
        message = "Failed to queue album for download"
        if result.errors:
            message += f": {result.errors[0]}"

    return AlbumDownloadResponse(
        message=message,
        album_title=result.album_title,
        artist_name=result.artist_name,
        total_tracks=result.total_tracks,
        queued_count=result.queued_count,
        already_downloaded=result.already_downloaded,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
        job_ids=result.job_ids,
        errors=result.errors,
        success=result.success,
    )


# Hey future me, this lists downloads with optional status filter and PROPER DB-LEVEL pagination!
# Previously we loaded ALL downloads and sliced in Python - that's O(N) memory! Now we push limit/offset
# to DB which is O(limit) memory. For large queues (1000+ downloads), this makes a HUGE difference.


# Default limit is 100 (user requested), max is 500 to prevent abuse. Total count is fetched separately
# for pagination UI. Status filter can be: waiting, pending, queued, downloading, completed, failed, cancelled.
#
# WICHTIG: Pfad ist "" statt "/" um 307 redirects zu vermeiden!
@router.get("")
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


# Hey future me - download history shows recently COMPLETED downloads!
# Unlike list_downloads which shows active queue, this shows finished work.
# Useful for: "what did I download this week?", analytics, re-download.
# Results sorted by completed_at DESC (newest first).
@router.get("/history")
async def get_download_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    days: int = Query(7, ge=1, le=90, description="History days to include"),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get download history (completed downloads).

    Shows recently completed downloads sorted by completion time.
    Useful for reviewing what was downloaded recently.

    Args:
        page: Page number (1-indexed)
        limit: Results per page (max 200)
        days: How many days of history to include (max 90)
        download_repository: Download repository

    Returns:
        Paginated list of completed downloads with stats
    """
    from datetime import timedelta

    offset = (page - 1) * limit
    since = datetime.now(UTC) - timedelta(days=days)

    # Get completed downloads within time range
    downloads = await download_repository.list_by_status(
        status=DownloadStatus.COMPLETED.value,
        limit=limit,
        offset=offset,
    )

    # Filter by date (if repository doesn't support it)
    downloads_in_range = [
        d for d in downloads if d.completed_at and d.completed_at >= since
    ]

    total = await download_repository.count_by_status(DownloadStatus.COMPLETED.value)
    total_pages = (total + limit - 1) // limit

    # Calculate stats
    total_size_mb = sum(
        d.file_size_bytes / (1024 * 1024)
        for d in downloads_in_range
        if d.file_size_bytes
    )

    return {
        "downloads": [
            {
                "id": str(d.id.value),
                "track_id": str(d.track_id.value),
                "title": d.title,
                "artist": d.artist,
                "album": d.album,
                "file_path": d.file_path,
                "file_size_mb": round(d.file_size_bytes / (1024 * 1024), 2)
                if d.file_size_bytes
                else None,
                "duration_seconds": (
                    (d.completed_at - d.started_at).total_seconds()
                    if d.completed_at and d.started_at
                    else None
                ),
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in downloads_in_range
        ],
        "stats": {
            "total_downloads": len(downloads_in_range),
            "total_size_mb": round(total_size_mb, 2),
            "period_days": days,
        },
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }


# Hey future me - comprehensive download statistics endpoint!
# Shows overall download performance, success rates, queue health.
# Used by dashboard for download analytics widget.
@router.get("/statistics")
async def get_download_statistics(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get comprehensive download statistics.

    Returns detailed statistics about download performance:
    - Queue status (pending, active, failed)
    - Success/failure rates
    - Average download times
    - Historical trends (today, week, all-time)

    Returns:
        Download statistics dashboard data
    """
    from datetime import timedelta

    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import DownloadModel

    session = download_repository.session
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Current queue status
    queue_pending = await download_repository.count_by_status(
        DownloadStatus.WAITING.value
    )
    queue_pending += await download_repository.count_by_status(
        DownloadStatus.PENDING.value
    )
    queue_pending += await download_repository.count_by_status(
        DownloadStatus.QUEUED.value
    )

    active_downloading = await download_repository.count_by_status(
        DownloadStatus.DOWNLOADING.value
    )
    total_completed = await download_repository.count_by_status(
        DownloadStatus.COMPLETED.value
    )
    total_failed = await download_repository.count_by_status(
        DownloadStatus.FAILED.value
    )
    total_cancelled = await download_repository.count_by_status(
        DownloadStatus.CANCELLED.value
    )

    # Downloads today
    stmt_today = (
        select(func.count())
        .select_from(DownloadModel)
        .where(
            DownloadModel.status == DownloadStatus.COMPLETED.value,
            DownloadModel.completed_at >= today_start,
        )
    )
    result = await session.execute(stmt_today)
    completed_today = result.scalar() or 0

    # Downloads this week
    stmt_week = (
        select(func.count())
        .select_from(DownloadModel)
        .where(
            DownloadModel.status == DownloadStatus.COMPLETED.value,
            DownloadModel.completed_at >= week_ago,
        )
    )
    result = await session.execute(stmt_week)
    completed_this_week = result.scalar() or 0

    # Average download time (from completed downloads)
    stmt_avg = select(
        func.avg(
            func.julianday(DownloadModel.completed_at)
            - func.julianday(DownloadModel.started_at)
        )
        * 86400  # Convert days to seconds
    ).where(
        DownloadModel.status == DownloadStatus.COMPLETED.value,
        DownloadModel.started_at.isnot(None),
        DownloadModel.completed_at.isnot(None),
    )
    result = await session.execute(stmt_avg)
    avg_download_time = result.scalar() or 0

    # Retry statistics
    stmt_retries = select(func.sum(DownloadModel.retry_count)).where(
        DownloadModel.retry_count > 0,
    )
    result = await session.execute(stmt_retries)
    total_retries = result.scalar() or 0

    # Calculate success rate
    total_attempted = total_completed + total_failed
    success_rate = (
        (total_completed / total_attempted * 100) if total_attempted > 0 else 0
    )

    return {
        "queue": {
            "pending": queue_pending,
            "active": active_downloading,
            "total_queued": queue_pending + active_downloading,
        },
        "completed": {
            "total": total_completed,
            "today": completed_today,
            "this_week": completed_this_week,
        },
        "failed": {
            "total": total_failed,
            "cancelled": total_cancelled,
        },
        "performance": {
            "success_rate_percent": round(success_rate, 1),
            "average_download_seconds": round(avg_download_time, 1),
            "total_retries": total_retries,
        },
        "timestamp": now.isoformat(),
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


# -------------------------------------------------------------------------
# Individual Download Actions (for Download Manager UI)
# -------------------------------------------------------------------------


@router.post("/{download_id}/cancel")
async def cancel_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Cancel a single download.

    Hey future me – this endpoint is called by Download Manager UI (HTMX)!
    The cancel button in download_manager_list.html hits this endpoint.

    Cancelling sets status to CANCELLED and triggers slskd cancel if active.
    Already completed/failed/cancelled downloads are ignored (no error).

    Args:
        download_id: UUID of the download to cancel

    Returns:
        Cancel result with updated status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid download ID format") from e

    download = await download_repository.get_by_id(download_id_obj)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Check if download can be cancelled
    if download.status in [
        DownloadStatus.COMPLETED,
        DownloadStatus.CANCELLED,
    ]:
        return {
            "success": True,
            "message": f"Download already {download.status.value}",
            "status": download.status.value,
        }

    # Cancel in slskd if download is active and has external ID
    if download.slskd_id and download.status in [
        DownloadStatus.QUEUED,
        DownloadStatus.DOWNLOADING,
    ]:
        try:
            from soulspot.config.settings import get_settings
            from soulspot.infrastructure.integrations.slskd_client import SlskdClient

            settings = get_settings()
            if settings.slskd.url:
                async with SlskdClient(settings.slskd) as slskd:
                    await slskd.cancel_download(download.slskd_id)
                    logger.info(
                        LogMessages.download_completed(
                            download_id=str(download.slskd_id),
                            track_name="<cancelled>",
                            size_mb=0,
                        )
                        .format()
                        .replace("Download Completed", "Download Cancelled in slskd")
                    )
        except Exception as e:
            logger.warning(
                LogMessages.download_failed(
                    download_id=str(download.slskd_id)
                    if download.slskd_id
                    else "<unknown>",
                    track_name="<cancelled>",
                    reason="Failed to cancel in slskd",
                    hint="Download will still be marked cancelled in local database",
                ).format(),
                exc_info=e,
            )

    # Update status in our DB
    download.cancel()
    await download_repository.update(download)

    logger.info(
        LogMessages.download_completed(
            download_id=str(download_id),
            track_name=f"Track {download.track_id}",
            size_mb=0,
        )
        .format()
        .replace("Download Completed", "Download Cancelled")
    )

    return {
        "success": True,
        "message": "Download cancelled",
        "status": DownloadStatus.CANCELLED.value,
    }


@router.post("/{download_id}/retry")
async def retry_download(
    download_id: str,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Retry a failed or cancelled download.

    Hey future me – this endpoint resets a failed/cancelled download!
    Useful for "Try Again" buttons in the UI.

    Sets status back to WAITING so QueueDispatcherWorker picks it up.

    Args:
        download_id: UUID of the download to retry

    Returns:
        Retry result with updated status
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid download ID format") from e

    download = await download_repository.get_by_id(download_id_obj)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Only retry failed or cancelled downloads
    if download.status not in [
        DownloadStatus.FAILED,
        DownloadStatus.CANCELLED,
    ]:
        return {
            "success": False,
            "message": f"Cannot retry download with status {download.status.value}",
            "status": download.status.value,
        }

    # Reset to WAITING for re-processing
    download.status = DownloadStatus.WAITING
    download.error_message = None
    download.slskd_id = None
    download.source_url = None
    await download_repository.update(download)

    logger.info(
        LogMessages.download_started(
            download_id=str(download_id), track_name=f"Track {download.track_id}"
        )
        .format()
        .replace("Download Started", "Download Retry Queued")
    )

    return {
        "success": True,
        "message": "Download re-queued for retry",
        "status": DownloadStatus.WAITING.value,
    }


@router.patch("/{download_id}/priority")
async def update_download_priority(
    download_id: str,
    request: UpdatePriorityRequest,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Update priority of a single download.

    Hey future me – this endpoint is for priority drag & drop!
    Higher priority = processed first. Default is 0, range typically 0-100.

    Args:
        download_id: UUID of the download
        request: New priority value

    Returns:
        Updated priority confirmation
    """
    try:
        download_id_obj = DownloadId.from_string(download_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid download ID format") from e

    download = await download_repository.get_by_id(download_id_obj)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Can only change priority for non-terminal downloads
    if download.status in [
        DownloadStatus.COMPLETED,
        DownloadStatus.CANCELLED,
        DownloadStatus.FAILED,
    ]:
        return {
            "success": False,
            "message": f"Cannot change priority of {download.status.value} download",
            "status": download.status.value,
        }

    old_priority = download.priority
    download.update_priority(request.priority)
    await download_repository.update(download)

    logger.info(
        f"🔄 Download Priority Changed\n"
        f"├─ Download ID: {download_id}\n"
        f"├─ Old Priority: {old_priority}\n"
        f"└─ New Priority: {request.priority}"
    )

    return {
        "success": True,
        "message": f"Priority updated to {request.priority}",
        "priority": request.priority,
    }


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
            if existing and existing.status not in [
                DownloadStatus.COMPLETED,
                DownloadStatus.CANCELLED,
                DownloadStatus.FAILED,
            ]:
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
        "message": f"Downloads: {', '.join(message_parts)}"
        if message_parts
        else "No tracks to download",
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
            elif request.action == "retry":
                # Retry failed downloads - schedules for immediate retry
                if download.status != DownloadStatus.FAILED:
                    errors.append(
                        {
                            "id": download_id,
                            "error": f"Cannot retry - status is {download.status.value}, not FAILED",
                        }
                    )
                    continue
                download.schedule_retry()
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
