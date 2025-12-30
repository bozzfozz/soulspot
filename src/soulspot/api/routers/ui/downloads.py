"""Downloads UI routes.

Hey future me - this module contains all download-related UI routes:
- Downloads page (/downloads)
- Download manager page (/download-manager)
- Download center page (/download-center)
- Queue partials for HTMX auto-refresh
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soulspot.api.dependencies import get_db_session, get_download_repository
from soulspot.api.routers.ui._shared import templates
from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel
from soulspot.infrastructure.persistence.repositories import DownloadRepository

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_downloads_data(
    download_repository: DownloadRepository,
    session: AsyncSession,
    page: int,
    limit: int,
) -> dict[str, Any]:
    """Shared helper to get downloads data with pagination.

    Hey future me - this is used by both /downloads (full page) and
    /downloads/queue-partial (HTMX partial). Keeps logic DRY!
    """
    offset = (page - 1) * limit

    # Query downloads with track info
    # Hey future me - TrackModel.artist and TrackModel.album are relationship() attributes,
    # NOT functions! Must use direct attribute access (not lambda) for selectinload().
    # Lambda syntax like "lambda t: t.artist" causes SQLAlchemy ArgumentError because
    # selectinload() expects ORM mapped attributes (relationship/mapped_column), not callables.
    stmt = (
        select(DownloadModel)
        .options(
            selectinload(DownloadModel.track).selectinload(TrackModel.artist),
            selectinload(DownloadModel.track).selectinload(TrackModel.album),
        )
        .where(
            DownloadModel.status.in_(
                [
                    DownloadStatus.WAITING.value,
                    DownloadStatus.PENDING.value,
                    DownloadStatus.QUEUED.value,
                    DownloadStatus.DOWNLOADING.value,
                    DownloadStatus.COMPLETED.value,
                    DownloadStatus.FAILED.value,
                ]
            )
        )
        .order_by(
            DownloadModel.priority.desc(),
            DownloadModel.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    download_models = result.unique().scalars().all()

    total_count = await download_repository.count_active()

    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    has_next = page < total_pages
    has_previous = page > 1

    # Fetch stats for the cards at the top
    active_count = await download_repository.count_by_status(
        DownloadStatus.DOWNLOADING.value
    )
    queue_count = (
        await download_repository.count_by_status(DownloadStatus.QUEUED.value)
        + await download_repository.count_by_status(DownloadStatus.PENDING.value)
        + await download_repository.count_by_status(DownloadStatus.WAITING.value)
    )
    failed_count = await download_repository.count_by_status(
        DownloadStatus.FAILED.value
    )
    completed_count = await download_repository.count_by_status(
        DownloadStatus.COMPLETED.value
    )

    # Convert to template-friendly format with track info
    downloads_data = []
    for dl in download_models:
        track = dl.track
        downloads_data.append(
            {
                "id": dl.id,
                "track_id": dl.track_id,
                "status": dl.status,
                "priority": dl.priority,
                "progress_percent": dl.progress_percent or 0,
                "error_message": dl.error_message,
                "started_at": dl.started_at.isoformat() if dl.started_at else None,
                "created_at": dl.created_at.isoformat() if dl.created_at else None,
                # Track info for display
                "title": track.title if track else f"Track {dl.track_id[:8]}",
                "artist": track.artist.name
                if track and track.artist
                else "Unknown Artist",
                "album": track.album.title
                if track and track.album
                else "Unknown Album",
                "album_art": track.album.cover_url if track and track.album else None,
                # Hey future me - album_art_path enables get_display_url() local cache
                "album_art_path": track.album.cover_path
                if track and track.album
                else None,
            }
        )

    return {
        "downloads": downloads_data,
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "active_count": active_count,
        "queue_count": queue_count,
        "failed_count": failed_count,
        "completed_today": completed_count,
    }


@router.get("/downloads", response_class=HTMLResponse)
async def downloads(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500, description="Items per page"),
    download_repository: DownloadRepository = Depends(get_download_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Downloads page with pagination - full page with header, stats, tabs.

    Args:
        request: FastAPI request
        page: Page number (1-indexed)
        limit: Items per page (default 100, max 500)
        download_repository: Download repository
        session: DB session for direct queries
    """
    data = await _get_downloads_data(download_repository, session, page, limit)

    return templates.TemplateResponse(
        request,
        "downloads.html",
        context=data,
    )


@router.get("/downloads/queue-partial", response_class=HTMLResponse)
async def downloads_queue_partial(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500, description="Items per page"),
    download_repository: DownloadRepository = Depends(get_download_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Downloads queue partial - ONLY the queue list for HTMX auto-refresh.

    Hey future me - dieser Endpoint gibt NUR die Queue-Liste zurück, nicht die ganze Seite!
    Das Template downloads_queue_partial.html rendert nur die Items ohne Header/Stats/Tabs.
    Das löst das Duplikations-Problem beim Auto-Refresh.
    """
    data = await _get_downloads_data(download_repository, session, page, limit)

    return templates.TemplateResponse(
        request,
        "downloads_queue_partial.html",
        context=data,
    )


# Hey future me - this is the Download Manager page showing unified download status!
# It aggregates downloads from slskd (and future providers like SABnzbd) into one view.
# The page uses HTMX auto-refresh to poll /api/downloads/manager/htmx/* endpoints.
@router.get("/download-manager", response_class=HTMLResponse)
async def download_manager_page(request: Request) -> Any:
    """Download Manager page - unified view of all provider downloads."""
    return templates.TemplateResponse(request, "download_manager.html")


# Hey future me - NEW Download Center with professional UI!
# This is the redesigned download management page with:
# - Lidarr/Radarr-inspired queue design
# - Glassmorphism stats bar
# - Cards/Table view toggle
# - Real-time HTMX updates
# - Sidebar with filters and provider health
# Replaces the old download_manager.html eventually.
@router.get("/download-center", response_class=HTMLResponse)
async def download_center_page(request: Request) -> Any:
    """Download Center page - professional unified download management UI."""
    return templates.TemplateResponse(request, "download_center.html")
