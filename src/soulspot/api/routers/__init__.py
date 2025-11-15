"""API router initialization."""

from fastapi import APIRouter

from soulspot.api.routers import (
    auth,
    downloads,
    library,
    metadata,
    playlists,
    settings,
    tracks,
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

__all__ = [
    "api_router",
    "auth",
    "downloads",
    "library",
    "metadata",
    "playlists",
    "settings",
    "tracks",
]
