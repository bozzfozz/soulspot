"""UI Router Package - Modular UI routes for SoulSpot.

Hey future me - this package splits the monolithic ui.py (3406 lines) into
focused submodules for better maintainability.

Module Structure:
- _shared.py      - Shared utilities (templates, helpers)
- dashboard.py    - Dashboard, playlists, auth, onboarding routes
- downloads.py    - Downloads management routes
- search.py       - Search functionality routes
- library_core.py - Library overview and import routes
- library_browse.py - Library browsing (artists, albums, tracks, compilations)
- library_detail.py - Detail pages (artist detail, album detail, metadata editor)
- library_maintenance.py - Maintenance pages (duplicates, broken files, incomplete)
- spotify_browse.py - Spotify/Deezer browse routes (new releases, discover)

Usage:
    from soulspot.api.routers.ui import router as ui_router
    app.include_router(ui_router)
"""

from fastapi import APIRouter

from soulspot.api.routers.ui.dashboard import router as dashboard_router
from soulspot.api.routers.ui.downloads import router as downloads_router
from soulspot.api.routers.ui.library_browse import router as library_browse_router
from soulspot.api.routers.ui.library_core import router as library_core_router
from soulspot.api.routers.ui.library_detail import router as library_detail_router
from soulspot.api.routers.ui.library_maintenance import (
    router as library_maintenance_router,
)
from soulspot.api.routers.ui.search import router as search_router
from soulspot.api.routers.ui.spotify_browse import router as spotify_browse_router

# Create main router that includes all submodules
# Hey future me - we include all sub-routers without prefix because the routes
# themselves define their full paths (e.g., "/library/artists", "/downloads")
router = APIRouter(tags=["UI"])

# Include all submodule routers
router.include_router(dashboard_router)
router.include_router(downloads_router)
router.include_router(search_router)
router.include_router(library_core_router)
router.include_router(library_browse_router)
router.include_router(library_detail_router)
router.include_router(library_maintenance_router)
router.include_router(spotify_browse_router)

__all__ = ["router"]
