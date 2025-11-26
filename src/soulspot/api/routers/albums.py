# AI-Model: Copilot
"""Album management API endpoints.

Hey future me - this router handles syncing and managing albums from followed artists on Spotify.
The flow is: User syncs artists first → then clicks "sync albums" → we fetch all albums for those
artists from Spotify → create/update them in our albums table. Albums can also be listed, fetched
individually, or deleted. This is separate from tracks (albums are lighter-weight metadata).
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
from soulspot.application.services.album_sync_service import AlbumSyncService
from soulspot.domain.value_objects import AlbumId, ArtistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import AlbumRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/albums", tags=["Albums"])


# Hey future me - these are the response DTOs for the albums API. AlbumResponse maps
# the domain Album entity to what the frontend needs. Keep it flat for easy JSON serialization.
class AlbumResponse(BaseModel):
    """Response model for an album."""

    id: str = Field(..., description="Album UUID")
    title: str = Field(..., description="Album title")
    artist_id: str = Field(..., description="Artist UUID")
    release_year: int | None = Field(None, description="Release year")
    spotify_uri: str | None = Field(
        None, description="Spotify URI (e.g., spotify:album:xxxx)"
    )
    musicbrainz_id: str | None = Field(None, description="MusicBrainz ID")
    artwork_path: str | None = Field(None, description="Local path to album artwork")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


class SyncAlbumsResponse(BaseModel):
    """Response model for album sync operation."""

    albums: list[AlbumResponse] = Field(..., description="List of synced albums")
    stats: dict[str, int] = Field(..., description="Sync statistics")
    message: str = Field(..., description="Status message")


class AlbumListResponse(BaseModel):
    """Response model for listing albums."""

    albums: list[AlbumResponse] = Field(..., description="List of albums")
    total_count: int = Field(..., description="Total number of albums in DB")
    limit: int = Field(..., description="Pagination limit used")
    offset: int = Field(..., description="Pagination offset used")


# Hey future me - this converts a domain Album entity to an AlbumResponse DTO.
# The datetime formatting is done here to keep the domain clean.
def _album_to_response(album: Any) -> AlbumResponse:
    """Convert domain Album to AlbumResponse DTO.

    Args:
        album: Domain Album entity

    Returns:
        AlbumResponse DTO for API response
    """
    return AlbumResponse(
        id=str(album.id.value),
        title=album.title,
        artist_id=str(album.artist_id.value),
        release_year=album.release_year,
        spotify_uri=str(album.spotify_uri) if album.spotify_uri else None,
        musicbrainz_id=album.musicbrainz_id,
        artwork_path=str(album.artwork_path) if album.artwork_path else None,
        created_at=album.created_at.isoformat(),
        updated_at=album.updated_at.isoformat(),
    )


# Yo, this is the MAIN sync endpoint! It fetches ALL albums from Spotify for every followed
# artist in our DB and creates/updates them locally. POST because it modifies DB state.
# This can be slow for users with many followed artists (100+ artists × 10+ albums each).
# Returns the full list of synced albums plus stats (created/updated counts).
@router.post("/sync", response_model=SyncAlbumsResponse)
async def sync_albums_for_followed_artists(
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_from_session),
) -> SyncAlbumsResponse:
    """Sync albums from all followed artists on Spotify to the database.

    Fetches all artists from the local database (previously synced via /artists/sync),
    then for each artist fetches their albums from Spotify and creates/updates them
    in the local database. Uses spotify_uri as unique key to prevent duplicates.

    Args:
        session: Database session
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of synced albums and sync statistics

    Raises:
        HTTPException: If Spotify API fails or authentication issues
    """
    try:
        service = AlbumSyncService(
            session=session,
            spotify_client=spotify_client,
        )

        albums, stats = await service.sync_albums_for_followed_artists(access_token)

        # Commit the transaction to persist changes
        await session.commit()

        logger.info(
            f"Synced {len(albums)} albums from {stats['artists_processed']} artists: "
            f"{stats['albums_created']} created, {stats['albums_updated']} updated"
        )

        return SyncAlbumsResponse(
            albums=[_album_to_response(a) for a in albums],
            stats=stats,
            message=(
                f"Successfully synced {len(albums)} albums from "
                f"{stats['artists_processed']} artists. "
                f"Created: {stats['albums_created']}, Updated: {stats['albums_updated']}, "
                f"Errors: {stats['errors']}"
            ),
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync albums: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync albums: {str(e)}",
        ) from e


# Hey future me - this syncs albums for a single artist. Useful for "refresh" button
# on artist detail page. More efficient than syncing ALL artists when user only wants
# one artist's albums updated.
@router.post("/sync/artist/{artist_id}", response_model=SyncAlbumsResponse)
async def sync_albums_for_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_from_session),
) -> SyncAlbumsResponse:
    """Sync albums for a specific artist from Spotify.

    Args:
        artist_id: Artist UUID to sync albums for
        session: Database session
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of synced albums and sync statistics

    Raises:
        HTTPException: 404 if artist not found, 400 if invalid ID, 500 if sync fails
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    try:
        service = AlbumSyncService(
            session=session,
            spotify_client=spotify_client,
        )

        albums, stats = await service.sync_albums_for_artist(artist_id_obj, access_token)

        await session.commit()

        logger.info(
            f"Synced {len(albums)} albums for artist {artist_id}: "
            f"{stats['albums_created']} created, {stats['albums_updated']} updated"
        )

        return SyncAlbumsResponse(
            albums=[_album_to_response(a) for a in albums],
            stats=stats,
            message=(
                f"Successfully synced {len(albums)} albums. "
                f"Created: {stats['albums_created']}, Updated: {stats['albums_updated']}, "
                f"Errors: {stats['errors']}"
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync albums for artist {artist_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync albums: {str(e)}",
        ) from e


# Hey future me - this lists albums from our DB (not Spotify!). Use this to show
# albums that have been synced. Supports pagination via limit/offset. Returns total
# count for UI pagination controls. Sorted alphabetically by title in repository.
@router.get("", response_model=AlbumListResponse)
async def list_albums(
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of albums to return"
    ),
    offset: int = Query(0, ge=0, description="Number of albums to skip"),
    session: AsyncSession = Depends(get_db_session),
) -> AlbumListResponse:
    """List all albums from the database.

    Returns paginated list of albums that have been synced to the local database.
    Albums are sorted alphabetically by title.

    Args:
        limit: Maximum number of albums to return (1-500)
        offset: Number of albums to skip for pagination
        session: Database session

    Returns:
        Paginated list of albums with total count
    """
    repo = AlbumRepository(session)

    albums = await repo.list_all(limit=limit, offset=offset)
    total_count = await repo.count_all()

    return AlbumListResponse(
        albums=[_album_to_response(a) for a in albums],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


# Hey future me - this returns albums for a specific artist. Useful for artist detail
# page to show their discography. Returns albums sorted by release year.
@router.get("/artist/{artist_id}", response_model=AlbumListResponse)
async def list_albums_by_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AlbumListResponse:
    """List all albums by a specific artist.

    Args:
        artist_id: Artist UUID
        session: Database session

    Returns:
        List of albums for the artist (sorted by release year)

    Raises:
        HTTPException: 400 if invalid artist ID format
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    repo = AlbumRepository(session)
    albums = await repo.get_by_artist(artist_id_obj)

    return AlbumListResponse(
        albums=[_album_to_response(a) for a in albums],
        total_count=len(albums),
        limit=len(albums),
        offset=0,
    )


@router.get("/count", response_model=dict[str, int])
async def count_albums(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Get total count of albums in the database.

    Args:
        session: Database session

    Returns:
        Dictionary with total_count key
    """
    repo = AlbumRepository(session)
    total = await repo.count_all()

    return {"total_count": total}


@router.get("/{album_id}", response_model=AlbumResponse)
async def get_album(
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AlbumResponse:
    """Get a specific album by ID.

    Args:
        album_id: Album UUID
        session: Database session

    Returns:
        Album details

    Raises:
        HTTPException: 404 if album not found, 400 if invalid ID format
    """
    repo = AlbumRepository(session)

    try:
        album_id_obj = AlbumId.from_string(album_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid album ID format: {e}"
        ) from e

    album = await repo.get_by_id(album_id_obj)

    if not album:
        raise HTTPException(status_code=404, detail=f"Album not found: {album_id}")

    return _album_to_response(album)


@router.delete("/{album_id}", status_code=204)
async def delete_album(
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an album from the database.

    Removes the album and cascades to delete associated tracks.
    This is a destructive operation - use with caution!

    Args:
        album_id: Album UUID to delete
        session: Database session

    Raises:
        HTTPException: 404 if album not found, 400 if invalid ID format
    """
    repo = AlbumRepository(session)

    try:
        album_id_obj = AlbumId.from_string(album_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid album ID format: {e}"
        ) from e

    # Check if album exists first
    album = await repo.get_by_id(album_id_obj)
    if not album:
        raise HTTPException(status_code=404, detail=f"Album not found: {album_id}")

    await repo.delete(album_id_obj)
    await session.commit()

    logger.info(f"Deleted album: {album.title} (id: {album_id})")
