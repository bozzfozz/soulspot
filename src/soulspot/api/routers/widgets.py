"""Widget content endpoints for dashboard widgets."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from soulspot.api.dependencies import (
    get_download_repository,
    get_playlist_repository,
)
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
)

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter(prefix="/api/ui/widgets", tags=["widget-content"])


@router.get("/active-jobs/content", response_class=HTMLResponse)
async def active_jobs_content(
    request: Request,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Get active jobs widget content."""
    # Get active downloads
    downloads = await download_repository.list_active()

    # Convert to template-friendly format
    jobs = [
        {
            "id": str(download.id.value),
            "title": f"Track {download.track_id.value}",  # TODO: Get actual track info
            "artist": "Unknown Artist",  # TODO: Get actual artist info
            "status": download.status.value,
            "progress_percent": download.progress_percent or 0,
        }
        for download in downloads[:10]  # Limit to 10 most recent
    ]

    return templates.TemplateResponse(
        "partials/widgets/active_jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "jobs_count": len(downloads),
        },
    )


@router.get("/spotify-search/content", response_class=HTMLResponse)
async def spotify_search_content(
    request: Request,
) -> Any:
    """Get Spotify search widget content."""
    return templates.TemplateResponse(
        "partials/widgets/spotify_search.html",
        {
            "request": request,
            "results": [],
        },
    )


@router.get("/missing-tracks/content", response_class=HTMLResponse)
async def missing_tracks_content(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> Any:
    """Get missing tracks widget content."""
    # Get all playlists
    playlists = await playlist_repository.list_all()

    # Convert to template-friendly format
    playlists_data = [
        {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "track_count": len(playlist.track_ids),
        }
        for playlist in playlists
    ]

    return templates.TemplateResponse(
        "partials/widgets/missing_tracks.html",
        {
            "request": request,
            "playlists": playlists_data,
            "missing_tracks": [],  # TODO: Implement missing tracks detection
        },
    )


@router.get("/quick-actions/content", response_class=HTMLResponse)
async def quick_actions_content(
    request: Request,
) -> Any:
    """Get quick actions widget content."""
    return templates.TemplateResponse(
        "partials/widgets/quick_actions.html",
        {
            "request": request,
        },
    )


@router.get("/metadata-manager/content", response_class=HTMLResponse)
async def metadata_manager_content(
    request: Request,
) -> Any:
    """Get metadata manager widget content."""
    return templates.TemplateResponse(
        "partials/widgets/metadata_manager.html",
        {
            "request": request,
            "issues": [],  # TODO: Implement metadata issue detection
        },
    )
