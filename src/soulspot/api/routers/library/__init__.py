"""Library management API - LOCAL DATA ONLY!

Hey future me - this router package handles ONLY local library operations:
- Filesystem scanning (LibraryScannerService)
- DB queries on local data (Repositories)
- Statistics and health checks
- Batch operations on local files
- Entity duplicate detection (Artist/Album merge)

This router does NOT:
- Call Spotify/Deezer/Tidal APIs (that's EnrichmentRouter in api/routers/enrichment.py)
- Stream music (that's PlaybackRouter)
- Sync with providers (that's in provider-specific routers)

Structure:
- scan.py: Import/Scan endpoints (/import/*, deprecated /scan)
- stats.py: Statistics, broken files, album completeness (/stats, /broken-*, /incomplete-*)
- duplicates.py: Track duplicate detection (/duplicates/files, /duplicates/candidates)
- batch_operations.py: Batch rename, clear operations (/batch-rename, /clear*)
- library_duplicates (external): Entity duplicate merge (/duplicates/artists, /duplicates/albums)

The original monolithic library.py (1900+ LOC) has been split into these modules
for better maintainability and clearer separation of concerns.

NOTE: Enrichment endpoints are in a SEPARATE router (/api/enrichment/*) since
they use external APIs (Spotify, Deezer) - violates "LocalLibrary = local only" rule.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

from .scan import router as scan_router
from .stats import router as stats_router
from .duplicates import router as duplicates_router
from .batch_operations import router as batch_router
from .discovery import router as discovery_router

# Hey future me - Entity duplicate router lives in parent directory!
# Imports /duplicates/artists and /duplicates/albums merge endpoints.
from soulspot.api.routers.library_duplicates import router as entity_duplicates_router

# Initialize templates (needed by scan.py for HTML fragments)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Main library router - aggregates all sub-routers
router = APIRouter(prefix="/library", tags=["library"])

# Include all sub-routers (LOCAL ONLY!)
router.include_router(scan_router)
router.include_router(stats_router)
router.include_router(duplicates_router)
router.include_router(batch_router)
router.include_router(discovery_router)  # ID discovery + discography fetch
router.include_router(entity_duplicates_router)  # Artist/Album merge

# Re-export templates for sub-routers
__all__ = ["router", "templates"]
