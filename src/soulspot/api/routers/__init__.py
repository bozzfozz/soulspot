"""API router initialization."""

# Hey future me, this is the MAIN API router aggregator! It collects all sub-routers (auth, playlists, tracks,
# etc) and mounts them under /api prefix (check main.py where api_router is mounted). Each include_router()
# adds a prefix ("/auth", "/playlists", etc) so endpoints become /api/auth/login, /api/playlists/import, etc.
# The tags parameter groups endpoints in OpenAPI/Swagger docs - super helpful for API exploration! Order matters
# here - routers are tried in order for route matching (but shouldn't overlap anyway). library/automation/
# dashboard/widgets/widget_templates/sse have NO prefix because they define prefix in their own router
# (prefix="/library" in router.py). The __all__ export makes these importable from soulspot.api.routers.

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
    sse,
    tracks,
    widget_templates,
    widgets,
)

# Yo, this is the main API router that aggregates everything! Gets mounted at /api in main.py.
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
api_router.include_router(widget_templates.router, tags=["Widget-Templates"])
api_router.include_router(sse.router, tags=["SSE"])

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
    "sse",
    "tracks",
    "widget_templates",
    "widgets",
]
