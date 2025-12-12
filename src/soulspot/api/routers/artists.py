# AI-Model: Copilot
"""Artist management API endpoints.

Hey future me - this router handles syncing followed artists from Spotify to our DB.
The flow is: User clicks "sync" → we fetch all followed artists from Spotify → create/update
them in our artists table → return the list. Artists can also be deleted individually.
This is separate from watchlists (which track NEW releases) - this is just the artist catalog!
"""

import logging

# Hey future me - we use TYPE_CHECKING for SpotifyPlugin to avoid circular imports!
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_plugin,
)
from soulspot.application.services.followed_artists_service import (
    FollowedArtistsService,
)
from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.persistence.repositories import ArtistRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["Artists"])


# Hey future me - these are the response DTOs for the artists API. ArtistResponse maps
# the domain Artist entity to what the frontend needs. Keep it flat (no nested objects)
# for easy JSON serialization. genres is list[str] from the DB JSON field.
# Hey - source field shows where artist comes from! 'local' = file scan, 'spotify' = followed,
# 'hybrid' = both. UI uses this for badges (🎵 Local | 🎧 Spotify | 🌟 Both).
class ArtistResponse(BaseModel):
    """Response model for an artist."""

    id: str = Field(..., description="Artist UUID")
    name: str = Field(..., description="Artist name")
    source: str = Field(..., description="Artist source: local, spotify, or hybrid")
    spotify_uri: str | None = Field(
        None, description="Spotify URI (e.g., spotify:artist:xxxx)"
    )
    musicbrainz_id: str | None = Field(None, description="MusicBrainz ID")
    image_url: str | None = Field(None, description="Artist profile image URL")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


class SyncArtistsResponse(BaseModel):
    """Response model for sync operation."""

    artists: list[ArtistResponse] = Field(..., description="List of synced artists")
    stats: dict[str, int] = Field(..., description="Sync statistics")
    message: str = Field(..., description="Status message")


class ArtistListResponse(BaseModel):
    """Response model for listing artists."""

    artists: list[ArtistResponse] = Field(..., description="List of artists")
    total_count: int = Field(..., description="Total number of artists in DB")
    limit: int = Field(..., description="Pagination limit used")
    offset: int = Field(..., description="Pagination offset used")


# Hey future me - this converts a domain Artist entity to an ArtistResponse DTO.
# The datetime formatting is done here to keep the domain clean. Spotify URI is
# converted to string if present. This is called for each artist in lists.
# The source field is converted from enum to string for JSON serialization.
def _artist_to_response(artist: Any) -> ArtistResponse:
    """Convert domain Artist to ArtistResponse DTO.

    Args:
        artist: Domain Artist entity

    Returns:
        ArtistResponse DTO for API response
    """
    return ArtistResponse(
        id=str(artist.id.value),
        name=artist.name,
        source=artist.source.value,  # Convert enum to string: 'local', 'spotify', 'hybrid'
        spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
        musicbrainz_id=artist.musicbrainz_id,
        image_url=artist.image_url,
        genres=artist.genres or [],
        created_at=artist.created_at.isoformat(),
        updated_at=artist.updated_at.isoformat(),
    )


# Yo, this is the MAIN sync endpoint! It fetches ALL followed artists from Spotify (paginated
# internally) and creates/updates them in our DB. Uses shared server-side token so any device
# can trigger sync. Returns the full list of synced artists plus stats (created/updated counts).
# This is idempotent - safe to call multiple times. Duplicate prevention is by spotify_uri.
# POST because it modifies DB state.
@router.post("/sync", response_model=SyncArtistsResponse)
async def sync_followed_artists(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> SyncArtistsResponse:
    """Sync followed artists from Spotify to the database.

    Hey future me - refactored to use SpotifyPlugin!
    No more access_token - plugin handles auth internally.
    Fetches all artists the user follows on Spotify and creates/updates them
    in the local database. Uses spotify_uri as unique key to prevent duplicates.

    Also respects is_provider_enabled("spotify") - if Spotify is disabled in settings,
    returns early with a message instead of making API calls.

    Args:
        session: Database session
        spotify_plugin: SpotifyPlugin for Spotify API calls

    Returns:
        List of synced artists and sync statistics

    Raises:
        HTTPException: If Spotify API fails or authentication issues
    """
    # Check if Spotify provider is enabled
    from soulspot.application.services.app_settings_service import AppSettingsService

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings. Enable it to sync artists.",
        )

    try:
        service = FollowedArtistsService(
            session=session,
            spotify_plugin=spotify_plugin,
        )

        artists, stats = await service.sync_followed_artists()

        # Commit the transaction to persist changes
        await session.commit()

        logger.info(
            f"Synced {len(artists)} followed artists from Spotify: "
            f"{stats['created']} created, {stats['updated']} updated"
        )

        return SyncArtistsResponse(
            artists=[_artist_to_response(a) for a in artists],
            stats=stats,
            message=(
                f"Successfully synced {len(artists)} artists. "
                f"Created: {stats['created']}, Updated: {stats['updated']}, "
                f"Errors: {stats['errors']}"
            ),
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync followed artists: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync followed artists: {str(e)}",
        ) from e


# Hey future me - this lists artists from unified Music Manager view (LOCAL + SPOTIFY)!
# Uses get_all_artists_unified() which returns artists with correct source field.
# Supports filtering by source: ?source=local (only local files), ?source=spotify (followed),
# ?source=hybrid (both), or no filter (all artists). Sorted alphabetically by name.
# Pagination via limit/offset. Returns total count for UI pagination controls.
@router.get("", response_model=ArtistListResponse)
async def list_artists(
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of artists to return"
    ),
    offset: int = Query(0, ge=0, description="Number of artists to skip"),
    source: str | None = Query(
        None,
        description="Filter by source: 'local', 'spotify', 'hybrid', or None for all",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> ArtistListResponse:
    """List all artists from unified Music Manager view (LOCAL + SPOTIFY).

    Returns paginated list of artists with source field indicating origin:
    - 'local': Artist from local file scan only
    - 'spotify': Followed artist on Spotify only
    - 'hybrid': Artist exists in both local library and Spotify

    Artists are sorted alphabetically by name.

    Args:
        limit: Maximum number of artists to return (1-500)
        offset: Number of artists to skip for pagination
        source: Optional filter by source type ('local', 'spotify', 'hybrid')
        session: Database session

    Returns:
        Paginated list of artists with total count
    """
    repo = ArtistRepository(session)

    # Use unified view that includes source field
    artists = await repo.get_all_artists_unified(
        limit=limit, offset=offset, source_filter=source
    )
    total_count = await repo.count_by_source(source=source)

    return ArtistListResponse(
        artists=[_artist_to_response(a) for a in artists],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/count", response_model=dict[str, int])
async def count_artists(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Get total count of artists in the database.

    Args:
        session: Database session

    Returns:
        Dictionary with total_count key
    """
    repo = ArtistRepository(session)
    total = await repo.count_all()

    return {"total_count": total}


@router.get("/{artist_id}", response_model=ArtistResponse)
async def get_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistResponse:
    """Get a specific artist by ID.

    Args:
        artist_id: Artist UUID
        session: Database session

    Returns:
        Artist details

    Raises:
        HTTPException: 404 if artist not found
    """
    repo = ArtistRepository(session)

    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    artist = await repo.get_by_id(artist_id_obj)

    if not artist:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")

    return _artist_to_response(artist)


@router.delete("/{artist_id}", status_code=204)
async def delete_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an artist from the database.

    Removes the artist and cascades to delete their albums and tracks.
    This is a destructive operation - use with caution!

    Args:
        artist_id: Artist UUID to delete
        session: Database session

    Raises:
        HTTPException: 404 if artist not found, 400 if invalid ID format
    """
    repo = ArtistRepository(session)

    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    # Check if artist exists first (repository.delete raises exception if not found)
    artist = await repo.get_by_id(artist_id_obj)
    if not artist:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")

    await repo.delete(artist_id_obj)
    await session.commit()

    logger.info(f"Deleted artist: {artist.name} (id: {artist_id})")


# =========================================================================
# SPOTIFY FOLLOW/UNFOLLOW ENDPOINTS
# =========================================================================
# Hey future me - these endpoints let users follow/unfollow artists on Spotify directly!
# This is for the Search Page "Add to Followed Artists" feature.
# - POST /artists/spotify/{spotify_id}/follow → Follow artist on Spotify
# - DELETE /artists/spotify/{spotify_id}/follow → Unfollow artist on Spotify
# - GET /artists/spotify/following-status → Check if following multiple artists
# All use the shared token since we have single-user architecture.
# =========================================================================


class FollowArtistResponse(BaseModel):
    """Response model for follow/unfollow operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    spotify_id: str = Field(..., description="Spotify artist ID")
    message: str = Field(..., description="Status message")


class FollowingStatusRequest(BaseModel):
    """Request model for checking following status."""

    artist_ids: list[str] = Field(
        ..., description="List of Spotify artist IDs to check", max_length=50
    )


class FollowingStatusResponse(BaseModel):
    """Response model for following status check."""

    statuses: dict[str, bool] = Field(
        ..., description="Map of artist_id → is_following"
    )


@router.post(
    "/spotify/{spotify_id}/follow",
    response_model=FollowArtistResponse,
    summary="Follow an artist on Spotify",
)
async def follow_artist_on_spotify(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> FollowArtistResponse:
    """Follow an artist on Spotify.

    Adds the artist to the user's followed artists on Spotify. After following,
    the artist will appear in the user's Spotify library and in sync_followed_artists().

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        Success status and message

    Raises:
        HTTPException: 400 if invalid artist ID, 500 if Spotify API fails
    """
    try:
        await spotify_plugin.follow_artists([spotify_id])

        logger.info(f"Followed artist on Spotify: {spotify_id}")

        return FollowArtistResponse(
            success=True,
            spotify_id=spotify_id,
            message="Successfully followed artist on Spotify",
        )
    except Exception as e:
        logger.error(f"Failed to follow artist {spotify_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to follow artist: {str(e)}",
        ) from e


@router.delete(
    "/spotify/{spotify_id}/follow",
    response_model=FollowArtistResponse,
    summary="Unfollow an artist on Spotify",
)
async def unfollow_artist_on_spotify(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> FollowArtistResponse:
    """Unfollow an artist on Spotify.

    Removes the artist from the user's followed artists on Spotify. After unfollowing,
    the artist will no longer appear in sync_followed_artists().

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        Success status and message

    Raises:
        HTTPException: 400 if invalid artist ID, 500 if Spotify API fails
    """
    try:
        await spotify_plugin.unfollow_artists([spotify_id])

        logger.info(f"Unfollowed artist on Spotify: {spotify_id}")

        return FollowArtistResponse(
            success=True,
            spotify_id=spotify_id,
            message="Successfully unfollowed artist on Spotify",
        )
    except Exception as e:
        logger.error(f"Failed to unfollow artist {spotify_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unfollow artist: {str(e)}",
        ) from e


@router.post(
    "/spotify/following-status",
    response_model=FollowingStatusResponse,
    summary="Check if user follows multiple artists",
)
async def check_following_status(
    request: FollowingStatusRequest,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> FollowingStatusResponse:
    """Check if user follows one or more artists on Spotify.

    Use this to display "Following" vs "Follow" button states in the search results.
    Returns a map of artist_id → is_following for efficient batch checking.

    Args:
        request: List of Spotify artist IDs to check (max 50)
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        Map of artist_id → is_following status

    Raises:
        HTTPException: 400 if too many IDs, 500 if Spotify API fails
    """
    if len(request.artist_ids) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 artist IDs per request",
        )

    try:
        # SpotifyPlugin.check_following_artists returns dict[str, bool] directly!
        statuses = await spotify_plugin.check_following_artists(request.artist_ids)

        return FollowingStatusResponse(statuses=statuses)
    except Exception as e:
        logger.error(f"Failed to check following status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check following status: {str(e)}",
        ) from e


# =============================================================================
# RELATED ARTISTS (Similar Artists / Fans Also Like)
# Hey future me - this fetches artists that Spotify thinks are SIMILAR to a given artist!
# Uses Spotify's recommendation engine based on listener overlap, genres, etc. Returns up
# to 20 artists. Perfect for "Fans Also Like" sections in artist detail pages. The response
# includes following status for each artist so UI can show correct button states.
# =============================================================================


class RelatedArtistResponse(BaseModel):
    """Response model for a related/similar artist."""

    spotify_id: str = Field(..., description="Spotify artist ID")
    name: str = Field(..., description="Artist name")
    image_url: str | None = Field(None, description="Artist profile image URL")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    popularity: int = Field(..., description="Spotify popularity score 0-100")
    is_following: bool = Field(..., description="Whether user follows this artist")


class RelatedArtistsResponse(BaseModel):
    """Response model for related artists list."""

    artist_id: str = Field(..., description="Source artist Spotify ID")
    artist_name: str = Field(..., description="Source artist name")
    related_artists: list[RelatedArtistResponse] = Field(
        ..., description="List of similar artists"
    )
    total: int = Field(..., description="Number of related artists returned")


@router.get(
    "/spotify/{spotify_id}/related",
    response_model=RelatedArtistsResponse,
    summary="Get artists similar to a given artist",
)
async def get_related_artists(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> RelatedArtistsResponse:
    """Get up to 20 artists similar to the given artist.

    Spotify's recommendation engine determines similarity based on listener overlap,
    genre tags, and other factors. Perfect for "Fans Also Like" sections.

    Also checks if user follows each related artist to display correct button states.

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        List of similar artists with following status

    Raises:
        HTTPException: 404 if artist not found, 500 if Spotify API fails
    """
    try:
        # Get the source artist details first (for name in response)
        source_artist = await spotify_plugin.get_artist(spotify_id)

        # Get related artists (returns list[ArtistDTO])
        related_dtos = await spotify_plugin.get_related_artists(spotify_id)

        if not related_dtos:
            return RelatedArtistsResponse(
                artist_id=spotify_id,
                artist_name=source_artist.name,
                related_artists=[],
                total=0,
            )

        # Batch check following status for all related artists
        related_ids: list[str] = [a.spotify_id for a in related_dtos if a.spotify_id]
        following_statuses: dict[str, bool] = {}
        if related_ids:
            following_statuses = await spotify_plugin.check_following_artists(
                related_ids
            )

        # Build response with following status
        related_artists: list[RelatedArtistResponse] = []
        for artist_dto in related_dtos:
            related_artists.append(
                RelatedArtistResponse(
                    spotify_id=artist_dto.spotify_id or "",
                    name=artist_dto.name,
                    image_url=artist_dto.image_url,
                    genres=artist_dto.genres[:3] if artist_dto.genres else [],
                    popularity=artist_dto.popularity or 0,
                    is_following=following_statuses.get(artist_dto.spotify_id or "", False),
                )
            )

        return RelatedArtistsResponse(
            artist_id=spotify_id,
            artist_name=source_artist.name,
            related_artists=related_artists,
            total=len(related_artists),
        )

    except Exception as e:
        logger.error(f"Failed to get related artists for {spotify_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get related artists: {str(e)}",
        ) from e
