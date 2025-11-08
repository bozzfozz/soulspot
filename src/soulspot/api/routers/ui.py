"""UI routes for serving HTML templates."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Any:
    """Dashboard page."""
    stats = {
        "playlists": 0,
        "tracks": 0,
        "downloads": 0,
        "queue_size": 0,
    }
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


@router.get("/playlists", response_class=HTMLResponse)
async def playlists(request: Request) -> Any:
    """List playlists page."""
    playlists = []  # TODO: Load from repository
    return templates.TemplateResponse("playlists.html", {"request": request, "playlists": playlists})


@router.get("/playlists/import", response_class=HTMLResponse)
async def import_playlist(request: Request) -> Any:
    """Import playlist page."""
    return templates.TemplateResponse("import_playlist.html", {"request": request})


@router.get("/downloads", response_class=HTMLResponse)
async def downloads(request: Request) -> Any:
    """Downloads page."""
    downloads = []  # TODO: Load from repository
    return templates.TemplateResponse("downloads.html", {"request": request, "downloads": downloads})


@router.get("/auth", response_class=HTMLResponse)
async def auth(request: Request) -> Any:
    """Auth page."""
    return templates.TemplateResponse("auth.html", {"request": request})
