"""API routes for metadata management and conflict resolution."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from soulspot.api.dependencies import (
    get_album_repository,
    get_artist_repository,
    get_lastfm_client,
    get_musicbrainz_client,
    get_spotify_client,
    get_track_repository,
)
from soulspot.api.schemas.metadata import (
    EnrichMetadataMultiSourceRequest,
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
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metadata", tags=["metadata"])


def get_metadata_merger() -> MetadataMerger:
    """Get metadata merger instance."""
    return MetadataMerger()


def get_enrich_use_case(
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
    musicbrainz_client: MusicBrainzClient = Depends(get_musicbrainz_client),
    lastfm_client: LastfmClient | None = Depends(get_lastfm_client),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    metadata_merger: MetadataMerger = Depends(get_metadata_merger),
) -> EnrichMetadataMultiSourceUseCase:
    """Get metadata enrichment use case instance."""
    return EnrichMetadataMultiSourceUseCase(
        track_repository=track_repository,
        artist_repository=artist_repository,
        album_repository=album_repository,
        musicbrainz_client=musicbrainz_client,
        lastfm_client=lastfm_client,
        spotify_client=spotify_client,
        metadata_merger=metadata_merger,
    )


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
        use_case_request = UseCaseRequest(
            track_id=TrackId(UUID(request.track_id)),
            force_refresh=request.force_refresh,
            enrich_artist=request.enrich_artist,
            enrich_album=request.enrich_album,
            use_spotify=request.use_spotify,
            use_musicbrainz=request.use_musicbrainz,
            use_lastfm=request.use_lastfm,
            spotify_access_token=None,  # TODO: Get from auth context - requires session/JWT token extraction
            manual_overrides=request.manual_overrides,
        )

        response = await use_case.execute(use_case_request)

        if not response.track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Track not found: {request.track_id}",
            )

        return MetadataEnrichmentResponse(
            track_id=request.track_id,
            enriched_fields=response.enriched_fields,
            sources_used=response.sources_used,
            conflicts=[],  # TODO: Implement conflict detection - compare values across sources to identify discrepancies
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid track ID: {str(e)}",
        ) from e
    except Exception as e:
        logger.exception(f"Failed to auto-fix metadata for track {track_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to auto-fix metadata: {str(e)}",
        ) from e


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
