"""API router initialization."""

# Hey future me, this is the MAIN API router aggregator! It collects all sub-routers (auth, playlists, tracks,
# etc) and mounts them under /api prefix (check main.py where api_router is mounted). Each include_router()
# adds a prefix ("/auth", "/playlists", etc) so endpoints become /api/auth/login, /api/playlists/import, etc.
# The tags parameter groups endpoints in OpenAPI/Swagger docs - super helpful for API exploration! Order matters
# here - routers are tried in order for route matching (but shouldn't overlap anyway). library/automation/sse
# routers have NO prefix here because they define their own prefix in their router files (e.g. prefix="/library"
# in library.py). The __all__ export makes these importable from soulspot.api.routers.

from fastapi import APIRouter

from soulspot.api.routers import (
    artist_songs,
    artists,
    artwork,
    auth,
    automation,
    compilations,
    download_manager,
    downloads,
    library,
    metadata,
    notifications,
    onboarding,
    playlists,
    search,
    settings,
    sse,
    stats,
    tracks,
    workers,
)

# Yo, this is the main API router that aggregates everything! Gets mounted at /api in main.py.
api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(artists.router, tags=["Artists"])
api_router.include_router(artist_songs.router, tags=["Artist Songs"])
api_router.include_router(artwork.router, tags=["Artwork"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["Playlists"])
api_router.include_router(tracks.router, prefix="/tracks", tags=["Tracks"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["Downloads"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(stats.router, prefix="/stats", tags=["Stats"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["Metadata"])
api_router.include_router(search.router, tags=["Search"])
api_router.include_router(library.router, tags=["Library"])
api_router.include_router(compilations.router, tags=["Compilations"])
api_router.include_router(automation.router, tags=["Automation"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(sse.router, tags=["SSE"])
api_router.include_router(workers.router, prefix="/workers", tags=["Workers"])
api_router.include_router(download_manager.router, tags=["Download Manager"])

__all__ = [
    "api_router",
    "artist_songs",
    "artists",
    "artwork",
    "auth",
    "automation",
    "compilations",
    "download_manager",
    "downloads",
    "library",
    "metadata",
    "notifications",
    "onboarding",
    "playlists",
    "search",
    "settings",
    "sse",
    "stats",
    "tracks",
    "workers",
]
