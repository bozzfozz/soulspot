"""API router initialization."""

from fastapi import APIRouter

from soulspot.api.routers import (
    auth,
    automation,
    dashboard,
    downloads,
    library,
    metadata,
    playlists,
    settings,
    tracks,
    widgets,
)

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
api_router.include_router(tracks.router, prefix="/tracks", tags=["Tracks"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["Downloads"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["Metadata"])
api_router.include_router(library.router, tags=["Library"])
api_router.include_router(automation.router, tags=["Automation"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(widgets.router, tags=["Widgets"])

__all__ = [
    "api_router",
    "auth",
    "automation",
    "dashboard",
    "downloads",
    "library",
    "metadata",
    "playlists",
    "settings",
    "tracks",
    "widgets",
]
