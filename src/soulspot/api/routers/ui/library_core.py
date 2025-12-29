"""Library core UI routes.

Hey future me - this module contains the main library pages:
- Library overview (/library)
- Library stats partial
- Library import redirect
- Import jobs list
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_job_queue,
    get_library_scanner_service,
    get_track_repository,
)
from soulspot.api.routers.ui._shared import templates
from soulspot.application.services.library_scanner import LibraryScannerService
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)
from soulspot.infrastructure.persistence.repositories import TrackRepository

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter()


# Yo, this is the library overview page with aggregated stats!
# IMPORTANT: Shows ONLY local files (tracks with file_path)!
# Uses efficient SQL COUNT queries instead of loading all data into memory.
# Merged with library_import.html for a single unified view!
@router.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    track_repository: TrackRepository = Depends(get_track_repository),  # noqa: ARG001
    session: AsyncSession = Depends(get_db_session),
    scanner: LibraryScannerService = Depends(get_library_scanner_service),
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """Library browser page - shows stats, scan controls, and management."""
    # Hey future me - After Unified Library (2025-12), we count ALL entities in DB!
    # Artists/Albums/Tracks show TOTAL count, "Local Files" shows tracks with file_path.

    # Count ALL tracks in DB (not just with file_path)
    total_tracks_stmt = select(func.count(TrackModel.id))
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count tracks WITH local files (for "Verfügbar" stat)
    tracks_with_files_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    tracks_with_files_result = await session.execute(tracks_with_files_stmt)
    tracks_with_files = tracks_with_files_result.scalar() or 0

    # Count ALL artists in DB (not filtered by file_path anymore!)
    artists_stmt = select(func.count(ArtistModel.id))
    artists_result = await session.execute(artists_stmt)
    total_artists = artists_result.scalar() or 0

    # Count ALL albums in DB (not filtered by file_path anymore!)
    albums_stmt = select(func.count(AlbumModel.id))
    albums_result = await session.execute(albums_stmt)
    total_albums = albums_result.scalar() or 0

    # Count broken tracks (local files that are broken)
    broken_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None),
        TrackModel.is_broken == True,  # noqa: E712
    )
    broken_result = await session.execute(broken_stmt)
    broken_tracks = broken_result.scalar() or 0

    # Get music path from scanner summary
    summary = await scanner.get_scan_summary()

    # Check for active scan job
    active_job = None
    jobs = await job_queue.list_jobs(job_type=JobType.LIBRARY_SCAN, limit=1)
    if jobs and jobs[0].status in (JobStatus.PENDING, JobStatus.RUNNING):
        job = jobs[0]
        active_job = {
            "job_id": job.id,
            "status": job.status.value,
            "progress": job.result.get("progress", 0) if job.result else 0,
            "stats": job.result.get("stats") if job.result else None,
        }

    stats = {
        "total_tracks": total_tracks,  # ALL tracks in DB
        "total_artists": total_artists,  # ALL artists in DB
        "total_albums": total_albums,  # ALL albums in DB
        "tracks_with_files": tracks_with_files,  # Tracks with local file_path
        "broken_tracks": broken_tracks,
        "music_path": summary.get("music_path", "/music"),
    }

    return templates.TemplateResponse(
        request,
        "library.html",
        context={"stats": stats, "active_job": active_job},
    )


# =============================================================================
# LIBRARY IMPORT UI ROUTES
# =============================================================================


@router.get("/library/stats-partial", response_class=HTMLResponse)
async def library_stats_partial(
    _request: Request,  # noqa: ARG001
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """HTMX partial: Returns updated stats HTML for library overview.

    Hey future me - this endpoint returns the stats cards HTML for refresh!
    Used by HTMX to update stats without full page reload after scans.
    NOW uses StatsService! Clean Architecture.
    """
    from soulspot.application.services.stats_service import StatsService

    stats_service = StatsService(session)

    # Basic counts via StatsService
    total_tracks = await stats_service.get_total_tracks()
    total_artists = await stats_service.get_total_artists()
    total_albums = await stats_service.get_total_albums()

    # Tracks with local files (custom query - not in StatsService yet)
    tracks_with_files = (
        await session.execute(
            select(func.count(TrackModel.id)).where(TrackModel.file_path.isnot(None))
        )
    ).scalar() or 0

    # Broken tracks (custom query - not in StatsService yet)
    broken_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None),
        TrackModel.is_broken == True,  # noqa: E712
    )
    broken_tracks = (await session.execute(broken_stmt)).scalar() or 0

    # Return stats HTML with updated values
    return HTMLResponse(f"""
    <div class="stat-card stat-card-animated" style="--delay: 0;">
        <div class="stat-icon stat-icon-artists"><i class="bi bi-person"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_artists:,}</span>
            <span class="stat-label">Artists</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 1;">
        <div class="stat-icon stat-icon-albums"><i class="bi bi-disc"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_albums:,}</span>
            <span class="stat-label">Albums</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 2;">
        <div class="stat-icon stat-icon-tracks"><i class="bi bi-music-note"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_tracks:,}</span>
            <span class="stat-label">Tracks</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 3;">
        <div class="stat-icon stat-icon-files"><i class="bi bi-file-earmark-music"></i></div>
        <div class="stat-content">
            <span class="stat-value">{tracks_with_files:,}</span>
            <span class="stat-label">Verfügbar</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 4;">
        <div class="stat-icon stat-icon-broken"><i class="bi bi-exclamation-triangle"></i></div>
        <div class="stat-content">
            <span class="stat-value">{broken_tracks:,}</span>
            <span class="stat-label">Broken</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    """)


@router.get("/library/import", response_class=HTMLResponse)
async def library_import_page(request: Request) -> Any:  # noqa: ARG001
    """Redirect to unified library page (merged with import)."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/library", status_code=302)


@router.get("/library/import/jobs-list", response_class=HTMLResponse)
async def library_import_jobs_list(
    _request: Request,  # noqa: ARG001
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """HTMX partial: Recent import jobs list with beautiful styling."""
    jobs = await job_queue.list_jobs(job_type=JobType.LIBRARY_SCAN, limit=10)

    jobs_data: list[dict[str, Any]] = [
        {
            "job_id": job.id,
            "status": job.status.value,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "stats": job.result
            if isinstance(job.result, dict) and "progress" not in job.result
            else None,
        }
        for job in jobs
    ]

    # Return empty state with nice styling
    if not jobs_data:
        return HTMLResponse(
            """<div class="empty-scans">
                <i class="bi bi-inbox"></i>
                <p>No recent scans found</p>
                <p style="font-size: 0.85rem;">Start a scan to see your import history here</p>
            </div>"""
        )

    # Build beautiful table HTML
    html = """<table class="recent-scans-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Files</th>
                <th>Imported</th>
                <th>Errors</th>
            </tr>
        </thead>
        <tbody>"""

    for job in jobs_data:
        # Format date nicely
        date_str = job["created_at"].strftime("%b %d, %Y")
        time_str = job["created_at"].strftime("%H:%M")

        # Status badge styling
        status = job["status"]
        status_config = {
            "completed": ("check-circle-fill", "completed", "Completed"),
            "failed": ("x-circle-fill", "failed", "Failed"),
            "running": ("arrow-repeat", "running", "Running"),
            "pending": ("hourglass", "pending", "Pending"),
        }.get(status, ("question-circle", "pending", status.title()))

        icon, badge_class, label = status_config

        # Stats
        stats = job["stats"] or {}
        scanned = stats.get("scanned", "-")
        imported = stats.get("imported", "-")
        errors = stats.get("errors", 0)

        # Format numbers with locale
        if isinstance(scanned, int):
            scanned = f"{scanned:,}"
        if isinstance(imported, int):
            imported = f"{imported:,}"
        if isinstance(errors, int):
            errors_display = f"{errors:,}"
            errors_class = "has-errors" if errors > 0 else ""
        else:
            errors_display = str(errors)
            errors_class = ""

        html += f"""
            <tr>
                <td>
                    <div class="scan-date">
                        <span class="scan-date-main">{date_str}</span>
                        <span class="scan-date-time">{time_str}</span>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-badge-{badge_class}">
                        <i class="bi bi-{icon}"></i>
                        {label}
                    </span>
                </td>
                <td class="stat-cell">{scanned}</td>
                <td class="stat-cell stat-cell-imported">{imported}</td>
                <td class="stat-cell stat-cell-errors {errors_class}">{errors_display}</td>
            </tr>"""

    html += "</tbody></table>"
    return HTMLResponse(html)
