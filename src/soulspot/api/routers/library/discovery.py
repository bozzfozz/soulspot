"""Library Discovery API endpoints - Manual triggering and status.

Hey future me - this router handles LibraryDiscoveryWorker operations:
- Manually trigger discovery cycle (POST /discovery/trigger)
- Get last discovery status (GET /discovery/status)
- Get discovered artist discographies (GET /discovery/discographies)
- Get missing albums for artist (GET /discovery/missing/{artist_id})

LibraryDiscoveryWorker is the SUPERWORKER that replaces LocalLibraryEnrichmentService:
- Phase 1: Find Deezer/Spotify IDs for artists without IDs
- Phase 2: Fetch complete discographies from providers
- Phase 3: Mark local albums that exist on streaming services
- Phase 4: Find Deezer/Spotify IDs for albums without IDs
- Phase 5: Find Deezer/Spotify IDs for tracks via ISRC

The worker runs automatically every 6 hours, but users can trigger it manually
for immediate discovery after adding new music to their library.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["library-discovery"])

# Initialize templates for HTMX responses
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# =============================================================================
# Response Models
# =============================================================================


class DiscoveryTriggerResponse(BaseModel):
    """Response from manual discovery trigger."""

    success: bool
    message: str
    triggered_at: datetime | None = None


class DiscoveryStatusResponse(BaseModel):
    """Status of library discovery worker."""

    is_running: bool
    last_run: datetime | None = None
    last_result: dict[str, Any] | None = None


class MissingAlbumItem(BaseModel):
    """A missing album from artist discography."""

    id: str
    title: str
    album_type: str
    release_date: str | None = None
    total_tracks: int | None = None
    cover_url: str | None = None
    deezer_id: str | None = None
    spotify_uri: str | None = None
    source: str


class MissingAlbumsResponse(BaseModel):
    """Response with missing albums for an artist."""

    artist_id: str
    artist_name: str
    total: int
    owned: int
    missing: int
    albums: list[MissingAlbumItem]


class DiscographyStatsResponse(BaseModel):
    """Stats about artist's discography."""

    total: int
    owned: int
    missing: int
    by_type: dict[str, dict[str, int]]


# =============================================================================
# Endpoints
# =============================================================================


# Hey future me - dieser Endpoint triggert den LibraryDiscoveryWorker manuell!
# Er ist für Power-User die nach dem Hinzufügen neuer Musik sofort Discovery
# haben wollen statt auf den 6-Stunden-Intervall zu warten.
# ACHTUNG: Nur triggern wenn nicht bereits läuft (Worker checkt das intern).
@router.post("/trigger")
async def trigger_discovery(
    request: Request,
) -> DiscoveryTriggerResponse:
    """Trigger a manual library discovery cycle.

    Runs all 5 phases of the LibraryDiscoveryWorker immediately:
    1. Artist ID discovery (Deezer/Spotify)
    2. Artist discography fetch
    3. Album ownership marking
    4. Album ID discovery (Deezer/Spotify)
    5. Track ID discovery via ISRC

    The worker normally runs every 6 hours automatically.
    Use this endpoint to trigger it immediately after adding new music.

    Returns:
        Success status and message
    """
    # Get worker from app state
    worker = getattr(request.app.state, "library_discovery_worker", None)

    if worker is None:
        raise HTTPException(
            status_code=503,
            detail="Library discovery worker not initialized. Check server logs.",
        )

    # Check if already running
    if worker._running:
        return DiscoveryTriggerResponse(
            success=False,
            message="Discovery cycle already in progress. Please wait for it to complete.",
            triggered_at=None,
        )

    try:
        # Run discovery in background (don't await - returns immediately)
        # The run_once method handles its own error logging
        import asyncio

        asyncio.create_task(worker.run_once())

        return DiscoveryTriggerResponse(
            success=True,
            message="Discovery cycle triggered. Check status for progress.",
            triggered_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.exception("Failed to trigger discovery: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger discovery: {e}",
        ) from e


@router.get("/status")
async def get_discovery_status(
    request: Request,
) -> DiscoveryStatusResponse:
    """Get the current status of the library discovery worker.

    Returns:
        Worker status including last run time and results
    """
    worker = getattr(request.app.state, "library_discovery_worker", None)

    if worker is None:
        raise HTTPException(
            status_code=503,
            detail="Library discovery worker not initialized. Check server logs.",
        )

    return DiscoveryStatusResponse(
        is_running=worker._running,
        last_run=getattr(worker, "_last_run_at", None),
        last_result=getattr(worker, "_last_run_stats", None),
    )


# =============================================================================
# Missing Albums Endpoints
# =============================================================================


# Hey future me - dieser Endpoint liefert die "Missing Albums" als HTML Fragment!
# Das sind Alben aus der provider-Discography (Deezer/Spotify), die der User NICHT
# in seiner lokalen Library hat (is_owned = False).
# Wird vom Artist-Detail UI via HTMX geladen um "Want to download?" Karten zu zeigen.
# HTMX ruft diesen Endpoint auf und ersetzt den Container mit dem HTML.
@router.get("/missing/{artist_id}", response_class=HTMLResponse)
async def get_missing_albums_html(
    request: Request,
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
    album_types: str = Query(
        default="album,ep,single,compilation",
        description="Comma-separated album types to include (album, ep, single, compilation)",
    ),
) -> HTMLResponse:
    """Get missing albums as HTML fragment for HTMX.

    This returns an HTML partial from the artist_discography table where is_owned=False.
    These are albums that exist on Deezer/Spotify but aren't in the user's local library.

    Args:
        artist_id: UUID of the artist
        album_types: Filter by type (default: all types including singles)

    Returns:
        HTML fragment with missing album cards
    """
    from soulspot.domain.entities import ArtistId
    from soulspot.infrastructure.persistence.models import ArtistModel
    from soulspot.infrastructure.persistence.repositories import (
        ArtistDiscographyRepository,
    )

    # Validate artist_id
    try:
        artist_uuid = UUID(artist_id)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "partials/missing_albums.html",
            context={"error": f"Invalid artist ID format: {artist_id}"},
        )

    # Get artist name for response
    from sqlalchemy import select

    artist_stmt = select(ArtistModel).where(ArtistModel.id == artist_id)
    artist_result = await session.execute(artist_stmt)
    artist_model = artist_result.scalar_one_or_none()

    if not artist_model:
        return templates.TemplateResponse(
            request,
            "partials/missing_albums.html",
            context={"error": f"Artist not found: {artist_id}"},
        )

    # Parse album types
    types_list = [t.strip().lower() for t in album_types.split(",") if t.strip()]
    if not types_list:
        types_list = ["album", "ep"]

    # Get missing albums from repository
    discography_repo = ArtistDiscographyRepository(session)
    artist_id_obj = ArtistId(value=artist_uuid)

    try:
        missing_albums = await discography_repo.get_missing_for_artist(
            artist_id=artist_id_obj,
            album_types=types_list,
        )

        # Get stats
        stats = await discography_repo.get_stats_for_artist(artist_id_obj)
    except Exception as e:
        logger.exception("Failed to get missing albums for artist %s: %s", artist_id, e)
        return templates.TemplateResponse(
            request,
            "partials/missing_albums.html",
            context={"error": f"Failed to load discography: {e}"},
        )

    # Convert to template-friendly format
    album_items = [
        {
            "id": str(album.id.value),
            "title": album.title,
            "album_type": album.album_type,
            "release_date": album.release_date,  # Already a string (YYYY-MM-DD format)
            "total_tracks": album.total_tracks,
            "cover_url": album.cover_url,
            "deezer_id": album.deezer_id,
            "spotify_uri": str(album.spotify_uri) if album.spotify_uri else None,
            "source": album.source,
        }
        for album in missing_albums
    ]

    return templates.TemplateResponse(
        request,
        "partials/missing_albums.html",
        context={
            "artist_name": artist_model.name,
            "albums": album_items,
            "total": stats["total"],
            "owned": stats["owned"],
            "missing": stats["missing"],
        },
    )


@router.get("/stats/{artist_id}")
async def get_discography_stats(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DiscographyStatsResponse:
    """Get discography statistics for an artist.

    Returns counts of total/owned/missing albums, broken down by type.

    Args:
        artist_id: UUID of the artist

    Returns:
        Statistics about discography coverage
    """
    from soulspot.domain.entities import ArtistId
    from soulspot.infrastructure.persistence.repositories import (
        ArtistDiscographyRepository,
    )

    # Validate artist_id
    try:
        artist_uuid = UUID(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid artist_id format: {artist_id}",
        ) from e

    # Get stats
    discography_repo = ArtistDiscographyRepository(session)
    artist_id_obj = ArtistId(value=artist_uuid)
    stats = await discography_repo.get_stats_for_artist(artist_id_obj)

    return DiscographyStatsResponse(
        total=stats["total"],
        owned=stats["owned"],
        missing=stats["missing"],
        by_type=stats["by_type"],
    )
