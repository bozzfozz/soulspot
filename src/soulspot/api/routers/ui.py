"""UI routes for serving HTML templates."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from soulspot.api.dependencies import (
    get_download_repository,
    get_playlist_repository,
    get_track_repository,
)
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    TrackRepository,
)

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Dashboard page with real statistics."""
    # Get real statistics from repositories
    playlists = await playlist_repository.list_all()
    tracks = await track_repository.list_all()
    active_downloads = await download_repository.list_active()

    stats = {
        "playlists": len(playlists),
        "tracks": len(tracks),
        "downloads": len(active_downloads),
        "queue_size": sum(
            1 for d in active_downloads if d.status.value in ["pending", "queued"]
        ),
    }
    return templates.TemplateResponse(
        "index.html", {"request": request, "stats": stats}
    )


@router.get("/playlists", response_class=HTMLResponse)
async def playlists(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> Any:
    """List playlists page with real data."""
    playlists_list = await playlist_repository.list_all()

    # Convert to template-friendly format
    playlists_data = [
        {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "track_count": len(playlist.track_ids),
            "source": playlist.source.value,
            "created_at": playlist.created_at.isoformat(),
        }
        for playlist in playlists_list
    ]

    return templates.TemplateResponse(
        "playlists.html", {"request": request, "playlists": playlists_data}
    )


@router.get("/playlists/import", response_class=HTMLResponse)
async def import_playlist(request: Request) -> Any:
    """Import playlist page."""
    return templates.TemplateResponse("import_playlist.html", {"request": request})


@router.get("/downloads", response_class=HTMLResponse)
async def downloads(
    request: Request,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Downloads page with real data."""
    downloads_list = await download_repository.list_active()

    # Convert to template-friendly format
    downloads_data = [
        {
            "id": str(download.id.value),
            "track_id": str(download.track_id.value),
            "status": download.status.value,
            "progress_percent": download.progress_percent,
            "error_message": download.error_message,
            "started_at": download.started_at.isoformat()
            if download.started_at
            else None,
            "created_at": download.created_at.isoformat(),
        }
        for download in downloads_list
    ]

    return templates.TemplateResponse(
        "downloads.html", {"request": request, "downloads": downloads_data}
    )


@router.get("/auth", response_class=HTMLResponse)
async def auth(request: Request) -> Any:
    """Auth page."""
    return templates.TemplateResponse("auth.html", {"request": request})


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> Any:
    """Advanced search page."""
    return templates.TemplateResponse("search.html", {"request": request})


@router.get("/theme-sample", response_class=HTMLResponse)
async def theme_sample(request: Request) -> Any:
    """Harmony theme sample page with component showcase."""
    return templates.TemplateResponse("theme-sample.html", {"request": request})
