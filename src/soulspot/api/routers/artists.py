# AI-Model: Copilot
"""Artist management API endpoints.

Hey future me - this router handles syncing followed artists from Spotify to our DB.
The flow is: User clicks "sync" → we fetch all followed artists from Spotify → create/update
them in our artists table → return the list. Artists can also be deleted individually.
This is separate from watchlists (which track NEW releases) - this is just the artist catalog!
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_client,
    get_spotify_token_from_session,
)
from soulspot.application.services.followed_artists_service import (
    FollowedArtistsService,
)
from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import ArtistRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["Artists"])


# Hey future me - these are the response DTOs for the artists API. ArtistResponse maps
# the domain Artist entity to what the frontend needs. Keep it flat (no nested objects)
# for easy JSON serialization. genres is list[str] from the DB JSON field.
class ArtistResponse(BaseModel):
    """Response model for an artist."""

    id: str = Field(..., description="Artist UUID")
    name: str = Field(..., description="Artist name")
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
        spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
        musicbrainz_id=artist.musicbrainz_id,
        image_url=artist.image_url,
        genres=artist.genres or [],
        created_at=artist.created_at.isoformat(),
        updated_at=artist.updated_at.isoformat(),
    )


# Yo, this is the MAIN sync endpoint! It fetches ALL followed artists from Spotify (paginated
# internally) and creates/updates them in our DB. The access_token comes from the session
# (auto-refreshed by get_spotify_token_from_session dependency). Returns the full list of
# synced artists plus stats (created/updated counts). This is idempotent - safe to call
# multiple times. Duplicate prevention is by spotify_uri. POST because it modifies DB state.
@router.post("/sync", response_model=SyncArtistsResponse)
async def sync_followed_artists(
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_from_session),
) -> SyncArtistsResponse:
    """Sync followed artists from Spotify to the database.

    Fetches all artists the user follows on Spotify and creates/updates them
    in the local database. Uses spotify_uri as unique key to prevent duplicates.

    Args:
        session: Database session
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of synced artists and sync statistics

    Raises:
        HTTPException: If Spotify API fails or authentication issues
    """
    try:
        service = FollowedArtistsService(
            session=session,
            spotify_client=spotify_client,
        )

        artists, stats = await service.sync_followed_artists(access_token)

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


# Hey future me - this lists artists from our DB (not Spotify!). Use this to show
# artists that have been synced. Supports pagination via limit/offset. Returns total
# count for UI pagination controls. Sorted alphabetically by name in repository.
@router.get("", response_model=ArtistListResponse)
async def list_artists(
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of artists to return"
    ),
    offset: int = Query(0, ge=0, description="Number of artists to skip"),
    session: AsyncSession = Depends(get_db_session),
) -> ArtistListResponse:
    """List all artists from the database.

    Returns paginated list of artists that have been synced to the local database.
    Artists are sorted alphabetically by name.

    Args:
        limit: Maximum number of artists to return (1-500)
        offset: Number of artists to skip for pagination
        session: Database session

    Returns:
        Paginated list of artists with total count
    """
    repo = ArtistRepository(session)

    artists = await repo.list_all(limit=limit, offset=offset)
    total_count = await repo.count_all()

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
