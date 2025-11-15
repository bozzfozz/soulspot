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
    lastfm_client: LastfmClient = Depends(get_lastfm_client),
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
            spotify_access_token=None,  # TODO: Get from auth context
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
            conflicts=[],  # TODO: Implement conflict detection
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
            entity = await artist_repository.get_by_id(ArtistId(UUID(request.artist_id)))
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
