"""Library enrichment endpoints - USES EXTERNAL APIS!

Hey future me - this file is SEPARATE from local library!
Enrichment uses EXTERNAL APIs (Spotify, MusicBrainz) to add metadata
to local library items. This violates the "LocalLibrary = local only" rule,
so it lives in its own router.

Enrichment adds:
- Spotify URIs (for streaming links)
- Artwork from Spotify/MB
- Disambiguation from MusicBrainz
- Genres from Spotify

Enrichment does NOT:
- Scan local files (that's LibraryScannerService)
- Modify file content (that's PostprocessingService)
- Download music files (that's SlskdClient)

Route prefix: /api/enrichment/* (NOT /api/library/enrichment/*)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_job_queue,
    get_settings,
)
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.config.settings import Settings
from soulspot.infrastructure.observability.log_messages import LogMessages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# =============================================================================
# Response Models
# =============================================================================


class EnrichmentStatusResponse(BaseModel):
    """Status of library enrichment."""

    artists_unenriched: int
    albums_unenriched: int
    pending_candidates: int
    is_enrichment_needed: bool
    is_running: bool = False
    last_job_completed: bool | None = None


class EnrichmentTriggerResponse(BaseModel):
    """Response after triggering enrichment job."""

    job_id: str
    message: str


class EnrichmentCandidateResponse(BaseModel):
    """A potential Spotify match for review."""

    id: str
    entity_type: str  # 'artist' or 'album'
    entity_id: str
    entity_name: str
    spotify_uri: str
    spotify_name: str
    spotify_image_url: str | None
    confidence_score: float
    extra_info: dict[str, Any]


class EnrichmentCandidatesListResponse(BaseModel):
    """List of enrichment candidates."""

    candidates: list[EnrichmentCandidateResponse]
    total: int


class ApplyCandidateRequest(BaseModel):
    """Request to apply a selected candidate."""

    candidate_id: str


class DisambiguationEnrichmentRequest(BaseModel):
    """Request to enrich disambiguation from MusicBrainz."""

    limit: int = 50


# =============================================================================
# STATUS ENDPOINTS
# =============================================================================


@router.get("/status", response_model=EnrichmentStatusResponse)
async def get_enrichment_status(
    session: AsyncSession = Depends(get_db_session),
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentStatusResponse:
    """Get current status of library enrichment.

    Hey future me - this shows how much work is needed!
    - Unenriched = has local files but no Spotify URI
    - Pending candidates = ambiguous matches waiting for user review
    - is_running = enrichment job currently processing

    Returns:
        Enrichment status with counts
    """
    from soulspot.application.services.enrichment_service import EnrichmentService

    service = EnrichmentService(session)
    status_dto = await service.get_enrichment_status()

    # Check job queue status
    is_running = False
    last_job_completed: bool | None = None

    enrichment_jobs = await job_queue.list_jobs(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        limit=1,
    )

    if enrichment_jobs:
        latest_job = enrichment_jobs[0]
        if latest_job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            is_running = True
        elif latest_job.status == JobStatus.COMPLETED:
            last_job_completed = True
        elif latest_job.status == JobStatus.FAILED:
            last_job_completed = False

    return EnrichmentStatusResponse(
        artists_unenriched=status_dto.artists_unenriched,
        albums_unenriched=status_dto.albums_unenriched,
        pending_candidates=status_dto.pending_candidates,
        is_enrichment_needed=status_dto.is_enrichment_needed,
        is_running=is_running,
        last_job_completed=last_job_completed,
    )


# =============================================================================
# TRIGGER ENDPOINTS
# =============================================================================


@router.post("/trigger", response_model=EnrichmentTriggerResponse)
async def trigger_enrichment(
    job_queue: JobQueue = Depends(get_job_queue),
) -> EnrichmentTriggerResponse:
    """Manually trigger a library enrichment job.

    Hey future me - this is a BACKGROUND JOB!
    The job will:
    1. Find unenriched artists and albums
    2. Search Spotify for matches
    3. Apply high-confidence matches automatically
    4. Create candidates for ambiguous matches (user review needed)

    Poll /enrichment/status to check progress.

    Returns:
        Job ID for status tracking
    """
    job_id = await job_queue.enqueue(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        payload={"triggered_by": "manual_api"},
    )

    return EnrichmentTriggerResponse(
        job_id=job_id,
        message="Enrichment job queued successfully",
    )


@router.post("/repair-artwork")
async def repair_missing_artwork(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    use_api: bool = Query(
        False,
        description="If True, use Deezer API to find missing images (slower, but finds more)",
    ),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Download missing local artwork for artists and albums.

    Hey future me - TWO MODES:
    1. CDN-only (default): Fast! Just downloads from URLs already in DB
    2. API mode (use_api=true): Slower, but searches Deezer for missing images

    CDN mode works for entities enriched via:
    - Deezer (no auth needed)
    - Spotify (if user was authenticated when enriching)
    - Any provider that saved an image_url

    API mode uses Deezer to find images for entities that:
    - Have no cover_url/image_url in DB yet
    - Were imported from local files without enrichment

    REFACTORED (Dec 2025): Now uses modern repair functions directly,
    not the deprecated ImageRepairService wrapper!

    Args:
        entity_type: 'artist', 'album', or None for both
        use_api: If True, search Deezer for missing images
        limit: Maximum number of entities to process

    Returns:
        Statistics about repaired artwork
    """
    # Use modern repair functions directly (not deprecated wrapper!)
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.images.repair import (
        repair_album_images,
        repair_artist_images,
    )

    # Create ImageService for downloading
    image_service = ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/api/images",
    )

    # Create ImageProviderRegistry if API mode enabled
    image_provider_registry = None
    if use_api:
        from soulspot.application.services.images.image_provider_registry import (
            ImageProviderRegistry,
        )
        from soulspot.infrastructure.plugins import DeezerPlugin
        from soulspot.infrastructure.providers.deezer_image_provider import (
            DeezerImageProvider,
        )

        # Create Deezer provider (NO AUTH NEEDED!)
        deezer_plugin = DeezerPlugin()
        deezer_provider = DeezerImageProvider(deezer_plugin)

        # Create registry with Deezer provider
        image_provider_registry = ImageProviderRegistry()
        image_provider_registry.register(deezer_provider, priority=1)
        logger.info("Image repair using Deezer API for missing images")

    result: dict[str, Any] = {}

    # Call modern functions directly (no deprecated wrapper!)
    if entity_type in (None, "artist"):
        artist_result = await repair_artist_images(
            session=session,
            image_service=image_service,
            image_provider_registry=image_provider_registry,
            spotify_plugin=None,
            limit=limit,
        )
        result["artists"] = artist_result

    if entity_type in (None, "album"):
        album_result = await repair_album_images(
            session=session,
            image_service=image_service,
            image_provider_registry=image_provider_registry,
            limit=limit,
        )
        result["albums"] = album_result

    # Summary stats
    total_repaired = result.get("artists", {}).get("repaired", 0) + result.get(
        "albums", {}
    ).get("repaired", 0)
    total_processed = result.get("artists", {}).get("processed", 0) + result.get(
        "albums", {}
    ).get("processed", 0)
    result["summary"] = {
        "total_processed": total_processed,
        "total_repaired": total_repaired,
        "mode": "api" if use_api else "cdn_only",
    }

    return result


@router.post("/reset-failed-images")
async def reset_failed_images(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reset FAILED image markers to allow retry.

    Hey future me - when image downloads fail, we mark them as "FAILED|reason|timestamp"
    to prevent retrying forever. This endpoint clears those markers
    so the user can trigger another repair attempt.

    The marker format is: FAILED|{reason}|{ISO timestamp}
    Example: FAILED|not_available|2025-01-15T10:30:00Z

    Args:
        entity_type: 'artist', 'album', or None for both

    Returns:
        Count of reset records
    """
    from sqlalchemy import update

    from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

    result: dict[str, Any] = {"reset_artists": 0, "reset_albums": 0}

    if entity_type in (None, "artist"):
        # Match all FAILED variants: "FAILED" and "FAILED|reason|timestamp"
        stmt = (
            update(ArtistModel)
            .where(ArtistModel.image_path.like("FAILED%"))
            .values(image_path=None)
        )
        res = await session.execute(stmt)
        result["reset_artists"] = res.rowcount  # type: ignore[attr-defined]

    if entity_type in (None, "album"):
        # Match all FAILED variants: "FAILED" and "FAILED|reason|timestamp"
        stmt = (
            update(AlbumModel)
            .where(AlbumModel.cover_path.like("FAILED%"))
            .values(cover_path=None)
        )
        res = await session.execute(stmt)
        result["reset_albums"] = res.rowcount  # type: ignore[attr-defined]

    await session.commit()
    logger.info(
        f"Reset FAILED images: {result['reset_artists']} artists, {result['reset_albums']} albums"
    )

    return result


# =============================================================================
# CANDIDATE REVIEW ENDPOINTS
# =============================================================================


@router.get("/candidates", response_model=EnrichmentCandidatesListResponse)
async def get_enrichment_candidates(
    entity_type: str | None = Query(None, description="Filter by 'artist' or 'album'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> EnrichmentCandidatesListResponse:
    """Get pending enrichment candidates for user review.

    Hey future me - these are AMBIGUOUS matches!
    Multiple Spotify results were found for one local item.
    User needs to select the correct one.

    Args:
        entity_type: Filter by 'artist' or 'album'
        limit: Max candidates to return
        offset: Pagination offset

    Returns:
        List of candidates waiting for review
    """
    from soulspot.application.services.enrichment_service import EnrichmentService

    service = EnrichmentService(session)
    dtos, total = await service.list_candidates(
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    # Convert DTOs to response models
    response_candidates = [
        EnrichmentCandidateResponse(
            id=dto.id,
            entity_type=dto.entity_type,
            entity_id=dto.entity_id,
            entity_name=dto.entity_name,
            spotify_uri=dto.spotify_uri,
            spotify_name=dto.spotify_name,
            spotify_image_url=dto.spotify_image_url,
            confidence_score=dto.confidence_score,
            extra_info=dto.extra_info,
        )
        for dto in dtos
    ]

    return EnrichmentCandidatesListResponse(
        candidates=response_candidates,
        total=total,
    )


@router.post("/candidates/{candidate_id}/apply")
async def apply_enrichment_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Apply a user-selected enrichment candidate.

    Hey future me - this confirms a Spotify match!
    Actions:
    1. Mark the candidate as selected
    2. Update the entity (artist/album) with Spotify URI and image
    3. Reject other candidates for the same entity

    Args:
        candidate_id: The candidate ID to apply

    Returns:
        Success status and applied Spotify URI
    """
    from soulspot.api.dependencies import get_image_service
    from soulspot.application.services.enrichment_service import EnrichmentService
    from soulspot.config import get_settings
    from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError

    service = EnrichmentService(session)
    image_service = get_image_service(get_settings())

    try:
        result = await service.apply_candidate(candidate_id, image_service)
        return {
            "success": True,
            "message": result["message"],
            "spotify_uri": result["spotify_uri"],
        }
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidOperationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/candidates/{candidate_id}/reject")
async def reject_enrichment_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reject an enrichment candidate.

    Use this when the suggested Spotify match is incorrect.

    Args:
        candidate_id: The candidate ID to reject

    Returns:
        Success status
    """
    from soulspot.infrastructure.persistence.repositories import (
        EnrichmentCandidateRepository,
    )

    repo = EnrichmentCandidateRepository(session)

    try:
        await repo.mark_rejected(candidate_id)
        await session.commit()
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Candidate not found") from e
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "success": True,
        "message": "Candidate rejected",
    }


# =============================================================================
# MUSICBRAINZ DISAMBIGUATION
# =============================================================================


@router.post("/disambiguation")
async def enrich_disambiguation(
    request: DisambiguationEnrichmentRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Enrich artists and albums with MusicBrainz disambiguation data.

    Hey future me - this is for Lidarr-style naming templates!
    MusicBrainz provides disambiguation strings like "(US rock band)" to differentiate
    artists with the same name (e.g., multiple artists named "Nirvana").

    This endpoint:
    1. Finds artists/albums without disambiguation
    2. Searches MusicBrainz for matches
    3. Stores disambiguation strings from MB results

    Note: Respects MusicBrainz 1 req/sec rate limit, so large batches take time.

    Returns:
        HTML response for HTMX integration
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.musicbrainz_enrichment_service import (
        MusicBrainzEnrichmentService,
    )
    from soulspot.infrastructure.integrations.musicbrainz_client import (
        MusicBrainzClient,
    )

    # Create MusicBrainz client and settings service
    mb_client = MusicBrainzClient(settings.musicbrainz)
    settings_service = AppSettingsService(session)

    service = MusicBrainzEnrichmentService(
        session=session,
        musicbrainz_client=mb_client,
        settings_service=settings_service,
    )

    try:
        result = await service.enrich_disambiguation_batch(limit=request.limit)

        artists_enriched = result.get("artists_enriched", 0)
        albums_enriched = result.get("albums_enriched", 0)

        if result.get("skipped"):
            return HTMLResponse(
                """<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #3b82f6; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                    <i class="bi bi-info-circle"></i>
                    <span>MusicBrainz provider is disabled in Settings.</span>
                </div>"""
            )

        if artists_enriched == 0 and albums_enriched == 0:
            return HTMLResponse(
                """<div class="musicbrainz-result" style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #3b82f6; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                    <i class="bi bi-check-circle"></i>
                    <span>All items already have disambiguation data or no matches found.</span>
                </div>"""
            )

        return HTMLResponse(
            f"""<div class="musicbrainz-result" style="background: rgba(186, 83, 45, 0.1); border: 1px solid rgba(186, 83, 45, 0.2); color: #e69d3c; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                <i class="bi bi-check-circle-fill"></i>
                <span>Enriched <strong>{artists_enriched}</strong> artists and <strong>{albums_enriched}</strong> albums with disambiguation data.</span>
            </div>"""
        )

    except Exception as e:
        logger.error(
            LogMessages.sync_failed(
                sync_type="disambiguation_enrichment",
                reason="MusicBrainz enrichment failed",
                hint="Check MusicBrainz API availability and rate limits (1 req/sec)",
            ).format(),
            exc_info=True,
        )
        return HTMLResponse(
            f"""<div class="musicbrainz-result" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #ef4444; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem;">
                <i class="bi bi-exclamation-triangle"></i>
                <span>Error: {str(e)}</span>
            </div>""",
            status_code=500,
        )


# =============================================================================
# AUTO-FETCH ENDPOINTS (Background fetch on page load)
# Hey future me - these endpoints are called via HTMX on page load to
# auto-fetch missing images in the background without blocking the UI!
# =============================================================================


@router.post("/auto-fetch-images", response_class=HTMLResponse)
async def auto_fetch_images(
    entity_type: str | None = Query(
        None,
        description="Filter by 'artist' or 'album', or omit for both",
    ),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Auto-fetch missing images in background (HTMX endpoint).

    Hey future me - this is the AUTO-MAGIC endpoint!
    Called via HTMX on page load to silently fetch missing images.
    Returns an empty response or minimal status update for the UI.

    Uses Deezer API (NO AUTH NEEDED!) to find images for entities
    that have deezer_id but no local image cached yet.

    Args:
        entity_type: 'artist', 'album', or None for both
        limit: Maximum entities to process (keep low for fast response)

    Returns:
        HTMX partial with status (empty if nothing to do)
    """
    from soulspot.application.services.image_repair_service import ImageRepairService
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.images.image_provider_registry import (
        ImageProviderRegistry,
    )
    from soulspot.infrastructure.plugins import DeezerPlugin
    from soulspot.infrastructure.providers.deezer_image_provider import (
        DeezerImageProvider,
    )

    try:
        # Create ImageService for downloading
        image_service = ImageService(
            cache_base_path=str(settings.storage.image_path),
            local_serve_prefix="/api/images",
        )

        # Create Deezer provider (NO AUTH NEEDED!)
        deezer_plugin = DeezerPlugin()
        deezer_provider = DeezerImageProvider(deezer_plugin)

        # Create registry with Deezer provider
        image_provider_registry = ImageProviderRegistry()
        image_provider_registry.register(deezer_provider, priority=1)

        service = ImageRepairService(
            session=session,
            image_service=image_service,
            image_provider_registry=image_provider_registry,
            spotify_plugin=None,
        )

        total_repaired = 0

        if entity_type in (None, "artist"):
            artist_result = await service.repair_artist_images(limit=limit)
            total_repaired += artist_result.get("repaired", 0)

        if entity_type in (None, "album"):
            album_result = await service.repair_album_images(limit=limit)
            total_repaired += album_result.get("repaired", 0)

        if total_repaired > 0:
            logger.info(
                f"[AUTO_FETCH_IMAGES] Repaired {total_repaired} images in background"
            )
            # Return a subtle notification that can trigger a page refresh
            return HTMLResponse(
                f"""<div id="auto-fetch-result" data-repaired="{total_repaired}"
                     hx-trigger="load" hx-get="" hx-swap="none"
                     style="display:none;">
                    <!-- Auto-fetched {total_repaired} images -->
                </div>"""
            )
        else:
            # Nothing to fetch - return empty
            return HTMLResponse("")

    except Exception as e:
        logger.warning(f"[AUTO_FETCH_IMAGES] Background fetch failed: {e}")
        # Fail silently - this is a background operation
        return HTMLResponse("")


@router.post("/auto-fetch-discography", response_class=HTMLResponse)
async def auto_fetch_discography(
    artist_id: str = Query(..., description="Artist ID to fetch discography for"),
    include_tracks: bool = Query(True, description="Also fetch tracks for each album"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Auto-fetch complete discography for an artist (HTMX endpoint).

    Hey future me - this is the AUTO-ALBUM-FETCH endpoint!
    Called when user views an artist that has no albums yet.
    Fetches ALL albums + tracks from Deezer (or Spotify if authenticated).

    Args:
        artist_id: Our internal artist ID
        include_tracks: Whether to also fetch tracks (default: True)

    Returns:
        HTMX partial with status
    """
    from soulspot.application.services.followed_artists_service import (
        FollowedArtistsService,
    )
    from soulspot.infrastructure.plugins import DeezerPlugin

    try:
        # Deezer is ALWAYS available (no auth needed!)
        deezer_plugin = DeezerPlugin()

        # Create service (without Spotify - Deezer is sufficient)
        service = FollowedArtistsService(
            session,
            spotify_plugin=None,
            deezer_plugin=deezer_plugin,
        )

        # Sync discography with tracks
        stats = await service.sync_artist_discography_complete(
            artist_id=artist_id,
            include_tracks=include_tracks,
        )

        albums_added = stats.get("albums_added", 0)
        tracks_added = stats.get("tracks_added", 0)

        if albums_added > 0 or tracks_added > 0:
            logger.info(
                f"[AUTO_FETCH_DISCOGRAPHY] artist={artist_id}: "
                f"albums={albums_added}, tracks={tracks_added}"
            )
            return HTMLResponse(
                f"""<div id="auto-fetch-result"
                     data-albums="{albums_added}" data-tracks="{tracks_added}"
                     style="display:none;">
                    <!-- Auto-fetched {albums_added} albums, {tracks_added} tracks -->
                </div>"""
            )
        else:
            return HTMLResponse("")

    except Exception as e:
        logger.warning(f"[AUTO_FETCH_DISCOGRAPHY] Failed for artist {artist_id}: {e}")
        return HTMLResponse("")
