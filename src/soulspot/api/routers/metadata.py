"""API routes for metadata management and conflict resolution."""

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from soulspot.api.dependencies import (
    get_album_repository,
    get_artist_repository,
    get_lastfm_client,
    get_musicbrainz_client,
    get_spotify_plugin,
    get_track_repository,
)
from soulspot.api.schemas.metadata import (
    EnrichMetadataMultiSourceRequest,
    MetadataConflict,
    MetadataEnrichmentResponse,
    MetadataSourceEnum,
    ResolveConflictRequest,
    TagNormalizationResult,
)
from soulspot.application.services.metadata_merger import MetadataMerger
from soulspot.application.use_cases.enrich_metadata_multi_source import (
    EnrichMetadataMultiSourceRequest as UseCaseRequest,
)
from soulspot.application.use_cases.enrich_metadata_multi_source import (
    EnrichMetadataMultiSourceUseCase,
)
from soulspot.domain.entities import Album, Artist, MetadataSource, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId
from soulspot.infrastructure.integrations.lastfm_client import LastfmClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter()


# Hey, MetadataMerger is the smart engine that combines metadata from multiple sources! It uses the
# authority hierarchy (Manual > MusicBrainz > Spotify > Last.fm) to decide which value wins when sources
# disagree. Creates new instance per request - no state to share. The merger handles field-level merging
# (not just replacing whole objects), conflict detection, and data normalization. Complex logic lives here!
def get_metadata_merger() -> MetadataMerger:
    """Get metadata merger instance."""
    return MetadataMerger()


# Yo, this is the FULL-FEATURED metadata enrichment dependency! Gets metadata from ALL three sources
# (MusicBrainz, Last.fm, Spotify) and merges them intelligently. Note Last.fm is optional (can be None)
# - the use case must handle that! SpotifyPlugin handles token management internally!
# All three repositories (track/artist/album) are needed because enrichment cascades - enriching a track
# might also update its artist and album metadata. Standard Clean Architecture pattern.
def get_enrich_use_case(
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
    musicbrainz_client: MusicBrainzClient = Depends(get_musicbrainz_client),
    lastfm_client: LastfmClient | None = Depends(get_lastfm_client),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    metadata_merger: MetadataMerger = Depends(get_metadata_merger),
) -> EnrichMetadataMultiSourceUseCase:
    """Get metadata enrichment use case instance."""
    return EnrichMetadataMultiSourceUseCase(
        track_repository=track_repository,
        artist_repository=artist_repository,
        album_repository=album_repository,
        musicbrainz_client=musicbrainz_client,
        lastfm_client=lastfm_client,
        spotify_plugin=spotify_plugin,
        metadata_merger=metadata_merger,
    )


# Hey future me, main metadata enrichment endpoint! Converts API request to use case request which
# seems redundant but keeps API layer separate from domain. SpotifyPlugin handles token internally!
# No more manual session/token extraction needed. Authority hierarchy is Manual > MusicBrainz > Spotify > Last.fm.
# Conflict detection IS IMPLEMENTED - MetadataMerger._detect_conflicts() finds disagreements between sources.
@router.post(
    "/enrich",
    response_model=MetadataEnrichmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Enrich track metadata from multiple sources",
    description="Fetch and merge metadata from Spotify, MusicBrainz, and Last.fm using authority hierarchy",
)
async def enrich_metadata(
    request: EnrichMetadataMultiSourceRequest,
    use_case: EnrichMetadataMultiSourceUseCase = Depends(get_enrich_use_case),
) -> MetadataEnrichmentResponse:
    """
    Enrich track metadata from multiple sources.

    Authority Hierarchy: Manual > MusicBrainz > Spotify > Last.fm

    SpotifyPlugin handles token management internally - no session required!

    Args:
        request: Enrichment request with track ID and options
        use_case: Metadata enrichment use case

    Returns:
        Enrichment response with results and any conflicts

    Raises:
        HTTPException: If track not found or enrichment fails
    """
    try:
        # Convert API request to use case request
        # No more spotify_access_token - plugin handles it!
        use_case_request = UseCaseRequest(
            track_id=TrackId(UUID(request.track_id)),
            force_refresh=request.force_refresh,
            enrich_artist=request.enrich_artist,
            enrich_album=request.enrich_album,
            use_spotify=request.use_spotify,
            use_musicbrainz=request.use_musicbrainz,
            use_lastfm=request.use_lastfm,
            manual_overrides=request.manual_overrides,
        )

        response = await use_case.execute(use_case_request)

        if not response.track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Track not found: {request.track_id}",
            )

        # Hey - convert conflicts dict to MetadataConflict objects for API response
        conflict_objects = []
        for field_name, conflicting_values in response.conflicts.items():
            # Get current value and source from track
            current_source_str = response.track.metadata_sources.get(field_name)
            if not current_source_str:
                continue  # Skip if no source tracked

            current_source = MetadataSourceEnum(current_source_str)
            current_value = getattr(response.track, field_name, None)

            # Build conflicting_values dict with MetadataSourceEnum keys
            conflicting_dict = {
                MetadataSourceEnum(source): value
                for source, value in conflicting_values.items()
            }

            conflict_objects.append(
                MetadataConflict(
                    field_name=field_name,
                    current_value=current_value,
                    current_source=current_source,
                    conflicting_values=conflicting_dict,
                )
            )

        return MetadataEnrichmentResponse(
            track_id=request.track_id,
            enriched_fields=response.enriched_fields,
            sources_used=response.sources_used,
            conflicts=conflict_objects,  # Hey - now returns actual conflicts!
            errors=response.errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to enrich metadata: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich metadata: {str(e)}",
        ) from e


# Listen up - this resolves metadata conflicts manually! You can pick which source to trust OR
# provide a custom value. The entity_type checks (track_id vs artist_id vs album_id) are mutually
# exclusive - only one should be provided but there's no validation that EXACTLY one is provided.
# Could get weird if someone passes multiple IDs. Using setattr() to dynamically set field is
# powerful but unsafe - no validation that field_name exists on entity! Could crash or create bogus
# attributes. MetadataSource.MANUAL marking for custom values makes sense but there's no audit trail
# of WHO made the change or WHEN. Consider adding user_id and timestamp to metadata_sources dict.
@router.post(
    "/resolve-conflict",
    status_code=status.HTTP_200_OK,
    summary="Resolve metadata conflict",
    description="Manually resolve a metadata conflict by selecting a source or providing custom value",
)
async def resolve_conflict(
    request: ResolveConflictRequest,
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
) -> dict[str, Any]:
    """
    Resolve a metadata conflict by selecting a source or providing custom value.

    Args:
        request: Conflict resolution request
        track_repository: Track repository
        artist_repository: Artist repository
        album_repository: Album repository

    Returns:
        Success message with updated entity

    Raises:
        HTTPException: If entity not found or resolution fails
    """
    try:
        # Determine entity type and fetch
        entity: Track | Artist | Album | None = None
        entity_type: str | None = None

        if request.track_id:
            entity = await track_repository.get_by_id(TrackId(UUID(request.track_id)))
            entity_type = "track"
        elif request.artist_id:
            entity = await artist_repository.get_by_id(
                ArtistId(UUID(request.artist_id))
            )
            entity_type = "artist"
        elif request.album_id:
            entity = await album_repository.get_by_id(AlbumId(UUID(request.album_id)))
            entity_type = "album"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide track_id, artist_id, or album_id",
            )

        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{entity_type.capitalize()} not found",
            )

        # Apply resolution
        if (
            request.selected_source == MetadataSourceEnum.MANUAL
            and request.custom_value
        ):
            # Use custom value
            setattr(entity, request.field_name, request.custom_value)
            entity.metadata_sources[request.field_name] = MetadataSource.MANUAL.value
        else:
            # Mark the selected source as authoritative
            entity.metadata_sources[request.field_name] = request.selected_source.value

        # Update entity
        if entity_type == "track" and isinstance(entity, Track):
            await track_repository.update(entity)
        elif entity_type == "artist" and isinstance(entity, Artist):
            await artist_repository.update(entity)
        elif entity_type == "album" and isinstance(entity, Album):
            await album_repository.update(entity)

        return {
            "message": "Conflict resolved successfully",
            "entity_type": entity_type,
            "field_name": request.field_name,
            "selected_source": request.selected_source.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to resolve conflict: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve conflict: {str(e)}",
        ) from e


# Yo simple normalizer endpoint! Takes array of artist/track names and standardizes "feat" vs "ft"
# vs "featuring" formats. Good for cleaning up inconsistent metadata. Returns list of results with
# original/normalized/changed flag which is nice for UI feedback. No rate limiting - someone could
# send 10000 tags and bog down the server. Should add max length validation. The normalize_artist_name
# uses regex which could be slow for huge inputs. Results are synchronous (no await) even though
# function is async - could be made sync. Pretty straightforward utility endpoint though!
@router.post(
    "/normalize-tags",
    response_model=list[TagNormalizationResult],
    status_code=status.HTTP_200_OK,
    summary="Normalize artist/track tags",
    description="Apply tag normalization rules (e.g., feat./ft. standardization)",
)
async def normalize_tags(
    tags: list[str],
    metadata_merger: MetadataMerger = Depends(get_metadata_merger),
) -> list[TagNormalizationResult]:
    """
    Normalize a list of tags/artist names.

    Args:
        tags: List of tags to normalize
        metadata_merger: Metadata merger service

    Returns:
        List of normalization results
    """
    results = []
    for tag in tags:
        normalized = metadata_merger.normalize_artist_name(tag)
        results.append(
            TagNormalizationResult(
                original=tag,
                normalized=normalized,
                changed=(tag != normalized),
            )
        )
    return results


@router.get(
    "/sources/hierarchy",
    status_code=status.HTTP_200_OK,
    summary="Get metadata source hierarchy",
    description="Get the configured authority hierarchy for metadata sources",
)
async def get_source_hierarchy() -> dict[str, int]:
    """
    Get the metadata source authority hierarchy.

    Returns:
        Dictionary mapping source names to priority values (lower = higher priority)
    """
    return {
        source.value: priority
        for source, priority in MetadataMerger.AUTHORITY_HIERARCHY.items()
    }


# Hey heads up, this is basically the "fix this one track" button! force_refresh=True means we'll
# hit external APIs even if we have cached data. enrich_artist/album=True means we'll also update
# related entities. All three sources enabled (Spotify, MusicBrainz, Last.fm) so maximum data.
# No access token though (uses None) so Spotify enrichment will fail! The ValidationException import
# is INSIDE the exception handler which is weird but works. The "Invalid TrackId" string check is
# fragile - should use proper exception types. Returns 400 for validation errors, 500 for everything
# else which is reasonable. Success=True in response but track might not actually be "fixed"!
@router.post(
    "/{track_id}/auto-fix",
    status_code=status.HTTP_200_OK,
    summary="Auto-fix track metadata",
    description="Automatically fix metadata issues for a single track by enriching from external sources",
)
async def auto_fix_track_metadata(
    track_id: str,
    use_case: EnrichMetadataMultiSourceUseCase = Depends(get_enrich_use_case),
) -> dict[str, Any]:
    """
    Auto-fix metadata for a single track.

    Attempts to enrich metadata from MusicBrainz, Spotify, and Last.fm.

    Args:
        track_id: Track ID to fix
        use_case: Metadata enrichment use case

    Returns:
        Result of metadata enrichment

    Raises:
        HTTPException: If track not found or enrichment fails
    """
    try:
        track_id_obj = TrackId.from_string(track_id)
        request = UseCaseRequest(
            track_id=track_id_obj,
            force_refresh=True,
            enrich_artist=True,
            enrich_album=True,
            use_spotify=True,
            use_musicbrainz=True,
            use_lastfm=True,
        )
        result = await use_case.execute(request)

        return {
            "track_id": track_id,
            "success": True,
            "enriched_fields": result.enriched_fields,
            "sources_used": result.sources_used,
            "message": "Metadata auto-fixed successfully",
        }
    except (ValueError, Exception) as e:
        # Check if it's a validation error
        from soulspot.domain.exceptions import ValidationException

        if isinstance(e, ValidationException) or "Invalid TrackId" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid track ID: {str(e)}",
            ) from e
        logger.exception(f"Failed to auto-fix metadata for track {track_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to auto-fix metadata: {str(e)}",
        ) from e


# WARNING: This fixes ALL tracks with issues - could run for HOURS! Returns 202 ACCEPTED which is
# good (acknowledges request without waiting) but then actually processes synchronously! Should be
# async background job. Limited to first 100 tracks with [:100] slice to prevent timeout - but no
# way to process the rest! Missing title/artist/album checks use hasattr() because Track entity uses
# ORM relationships - confusing. Only fixes tracks with spotify_uri which makes sense (need source
# for enrichment) but silently skips others. No progress tracking, no way to cancel. The fixed_count
# vs failed_count is useful but failures just log warnings, don't return details. "no_tracks_fixed"
# status if fixed_count=0 is confusing - might mean nothing needed fixing OR everything failed!
@router.post(
    "/fix-all",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fix all track metadata",
    description="Batch fix metadata for all tracks with issues by enriching from external sources",
)
async def fix_all_track_metadata(
    track_repository: TrackRepository = Depends(get_track_repository),
    use_case: EnrichMetadataMultiSourceUseCase = Depends(get_enrich_use_case),
) -> dict[str, Any]:
    """
    Fix metadata for all tracks with issues.

    This is an asynchronous operation that processes tracks in the background.

    Args:
        track_repository: Track repository
        use_case: Metadata enrichment use case

    Returns:
        Status message with count of tracks to process
    """
    try:
        # Get all tracks
        tracks = await track_repository.list_all()

        # Filter tracks that need metadata fixes
        tracks_to_fix = []
        for track in tracks:
            # Check if track has missing or incomplete metadata
            needs_fix = False
            if not track.title or track.title.strip() == "":
                needs_fix = True
            # Note: artist and album are ORM relationships in the Track entity
            # We need to check if they exist and are not empty
            if hasattr(track, "artist") and (
                not track.artist or track.artist.strip() == ""
            ):
                needs_fix = True
            if hasattr(track, "album") and (
                not track.album or track.album.strip() == ""
            ):
                needs_fix = True

            if needs_fix and track.spotify_uri:
                # Only fix tracks that have a Spotify URI for enrichment
                tracks_to_fix.append(track)

        # Process tracks (in a real implementation, this should be queued as background jobs)
        fixed_count = 0
        failed_count = 0
        for track in tracks_to_fix[:100]:  # Limit to first 100 to avoid timeout
            try:
                request = UseCaseRequest(
                    track_id=track.id,
                    force_refresh=True,
                    enrich_artist=True,
                    enrich_album=True,
                    use_spotify=True,
                    use_musicbrainz=True,
                    use_lastfm=True,
                )
                await use_case.execute(request)
                fixed_count += 1
            except Exception as e:
                logger.warning(f"Failed to fix metadata for track {track.id}: {e}")
                failed_count += 1

        return {
            "message": "Metadata fix operation completed",
            "total_tracks": len(tracks),
            "tracks_to_fix": len(tracks_to_fix),
            "fixed_count": fixed_count,
            "failed_count": failed_count,
            "status": "completed" if fixed_count > 0 else "no_tracks_fixed",
        }
    except Exception as e:
        logger.exception(f"Failed to fix all metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix all metadata: {str(e)}",
        ) from e
