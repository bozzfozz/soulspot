"""Library maintenance UI routes - Duplicates, Broken Files, Incomplete Albums.

Hey future me - this module contains library maintenance pages:
- Duplicates review (/library/duplicates)
- Broken files review (/library/broken-files)
- Incomplete albums review (/library/incomplete-albums)
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from soulspot.api.routers.ui._shared import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# DUPLICATE REVIEW ROUTES
# =============================================================================
# Hey future me - these routes are for the duplicate detection feature!
# The DuplicateDetectorWorker runs periodically and populates duplicate_candidates table.
# This page shows those candidates and lets users resolve them (keep one, keep both, dismiss).
# API endpoints in library.py do the actual work, this just renders the UI.
# =============================================================================


@router.get("/library/duplicates", response_class=HTMLResponse)
async def library_duplicates_page(request: Request) -> Any:
    """Duplicate review page for resolving duplicate artists/albums.

    Shows detected duplicate artists and albums (same name, different DB entries).
    Users can merge duplicates or dismiss false positives.

    Detection groups entities by normalized name - if multiple DB entries share
    the same normalized name, they're shown as potential duplicates.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with duplicate review UI
    """
    # Initial stats will be loaded via HTMX from /api/library/duplicates/artists
    return templates.TemplateResponse(
        request,
        "library_duplicates.html",
        context={
            "stats": None,  # Loaded via HTMX
        },
    )


# Hey future me - this is the broken files review page! Shows tracks that have a file_path but the
# file is corrupted, unreadable, or missing on disk. Data loads via HTMX from /api/library/broken-files.
# Users can re-download individual broken files or bulk re-download all. The LibraryCleanupWorker
# detects these and marks them as is_broken=True. UI shows file path, error type, and re-download button.
@router.get("/library/broken-files", response_class=HTMLResponse)
async def library_broken_files_page(request: Request) -> Any:
    """Broken files review page for re-downloading corrupted tracks.

    Shows tracks where file exists in DB but is corrupted/unreadable on disk.
    Users can review broken files and trigger re-downloads.

    The LibraryCleanupWorker detects broken files during maintenance scans.
    Users can also trigger manual scans from settings.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with broken files review UI
    """
    # Stats and broken files list loaded via HTMX from /api/library/broken-files
    return templates.TemplateResponse(
        request,
        "broken_files.html",
        context={},
    )


# Hey future me - this shows albums with missing tracks! An album is "incomplete" when we have some
# tracks but not all (e.g., 8 of 12 tracks). Data loads via HTMX from /api/library/incomplete-albums.
# Shows album cover, title, artist, progress bar of completion, and "download missing" button.
# Useful for finding albums that need gap-filling. Filters let users set minimum track count threshold.
@router.get("/library/incomplete-albums", response_class=HTMLResponse)
async def library_incomplete_albums_page(request: Request) -> Any:
    """Incomplete albums review page for finding albums with missing tracks.

    Shows albums where we have some tracks but not all (partial downloads).
    Users can see completion percentage and download missing tracks.

    Useful for gap-filling albums that were partially downloaded or
    albums where some tracks failed to download.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with incomplete albums review UI
    """
    # Album data loaded via HTMX from /api/library/incomplete-albums
    return templates.TemplateResponse(
        request,
        "incomplete_albums.html",
        context={},
    )
