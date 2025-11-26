# AI-Model: Copilot
"""Artist songs (singles) management API endpoints.

Hey future me - this router handles syncing and managing individual songs from followed
artists. Unlike the album sync feature, this focuses on "top tracks" / singles that
aren't necessarily part of a full album. Users can:
1. Sync songs for a single artist (fetch top tracks from Spotify)
2. Sync songs for ALL followed artists (bulk operation)
3. List songs (singles) for an artist from our DB
4. Remove a specific song
5. Remove all songs for an artist

These are READ/WRITE operations that modify our tracks table, separate from the artists
and albums features. The tracks synced here have album_id = NULL (no album association).
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
from soulspot.application.services.artist_songs_service import ArtistSongsService
from soulspot.domain.value_objects import ArtistId, TrackId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["Artist Songs"])


# Hey future me - response DTOs for the songs API. TrackResponse maps domain Track
# to API-friendly format. Keep it flat for easy JSON serialization.
class TrackResponse(BaseModel):
    """Response model for a track/song."""

    id: str = Field(..., description="Track UUID")
    title: str = Field(..., description="Track title")
    artist_id: str = Field(..., description="Artist UUID")
    duration_ms: int = Field(0, description="Duration in milliseconds")
    spotify_uri: str | None = Field(None, description="Spotify URI")
    isrc: str | None = Field(None, description="International Standard Recording Code")
    file_path: str | None = Field(None, description="Local file path if downloaded")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


class SyncSongsResponse(BaseModel):
    """Response model for song sync operation."""

    tracks: list[TrackResponse] = Field(..., description="List of synced tracks")
    stats: dict[str, int] = Field(..., description="Sync statistics")
    message: str = Field(..., description="Status message")


class SongListResponse(BaseModel):
    """Response model for listing songs."""

    tracks: list[TrackResponse] = Field(..., description="List of tracks")
    total_count: int = Field(..., description="Total number of songs")
    artist_id: str = Field(..., description="Artist UUID")


class DeleteResponse(BaseModel):
    """Response model for delete operations."""

    message: str = Field(..., description="Status message")
    deleted_count: int = Field(0, description="Number of items deleted")


# Hey future me - converts domain Track to API response DTO.
def _track_to_response(track: Any) -> TrackResponse:
    """Convert domain Track to TrackResponse DTO.

    Args:
        track: Domain Track entity

    Returns:
        TrackResponse DTO for API response
    """
    return TrackResponse(
        id=str(track.id.value),
        title=track.title,
        artist_id=str(track.artist_id.value),
        duration_ms=track.duration_ms,
        spotify_uri=str(track.spotify_uri) if track.spotify_uri else None,
        isrc=track.isrc,
        file_path=str(track.file_path) if track.file_path else None,
        created_at=track.created_at.isoformat(),
        updated_at=track.updated_at.isoformat(),
    )


# Hey future me - MAIN endpoint for syncing songs from a single artist! It fetches
# top tracks from Spotify and stores them as singles in our DB. The market param
# is important - Spotify track availability varies by region. Default is "US".
@router.post("/{artist_id}/songs/sync", response_model=SyncSongsResponse)
async def sync_artist_songs(
    artist_id: str,
    market: str = Query("US", description="ISO 3166-1 alpha-2 country code"),
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_from_session),
) -> SyncSongsResponse:
    """Sync songs (top tracks/singles) for a specific artist.

    Fetches the artist's top tracks from Spotify and stores them in the database.
    Tracks are stored without album association (as singles).

    Args:
        artist_id: Artist UUID
        market: Country code for track availability (default: US)
        session: Database session
        spotify_client: Spotify client
        access_token: Valid Spotify access token

    Returns:
        List of synced tracks and sync statistics

    Raises:
        HTTPException: 400 if invalid artist ID, 404 if artist not found
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    service = ArtistSongsService(
        session=session,
        spotify_client=spotify_client,
    )

    try:
        tracks, stats = await service.sync_artist_songs(
            artist_id=artist_id_obj,
            access_token=access_token,
            market=market,
        )

        # Commit transaction
        await session.commit()

        logger.info(
            f"Synced {len(tracks)} songs for artist {artist_id}: "
            f"{stats['created']} created, {stats['updated']} updated"
        )

        return SyncSongsResponse(
            tracks=[_track_to_response(t) for t in tracks],
            stats=stats,
            message=(
                f"Successfully synced {len(tracks)} songs. "
                f"Created: {stats['created']}, Updated: {stats['updated']}, "
                f"Errors: {stats['errors']}"
            ),
        )
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync songs for artist {artist_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync songs: {str(e)}",
        ) from e


# Hey future me - BULK sync endpoint! Syncs songs for ALL followed artists in DB.
# This can take a while for users following many artists. Consider adding progress
# reporting via SSE for large syncs. The limit param prevents runaway operations.
@router.post("/songs/sync-all", response_model=SyncSongsResponse)
async def sync_all_artists_songs(
    market: str = Query("US", description="ISO 3166-1 alpha-2 country code"),
    limit: int = Query(100, ge=1, le=500, description="Max artists to process"),
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_from_session),
) -> SyncSongsResponse:
    """Sync songs for ALL followed artists in the database.

    Iterates through all artists in DB and syncs their top tracks.
    This is a bulk operation that may take significant time.

    Args:
        market: Country code for track availability
        limit: Maximum number of artists to process
        session: Database session
        spotify_client: Spotify client
        access_token: Valid Spotify access token

    Returns:
        List of all synced tracks and aggregate statistics
    """
    service = ArtistSongsService(
        session=session,
        spotify_client=spotify_client,
    )

    try:
        tracks, stats = await service.sync_all_artists_songs(
            access_token=access_token,
            market=market,
            limit=limit,
        )

        # Commit transaction
        await session.commit()

        logger.info(
            f"Bulk song sync complete: {stats['artists_processed']} artists, "
            f"{stats['created']} tracks created"
        )

        return SyncSongsResponse(
            tracks=[_track_to_response(t) for t in tracks],
            stats=stats,
            message=(
                f"Synced songs for {stats['artists_processed']} artists. "
                f"Total tracks: {len(tracks)}, Created: {stats['created']}, "
                f"Updated: {stats['updated']}, Errors: {stats['errors']}"
            ),
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync all artists songs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync songs: {str(e)}",
        ) from e


# Hey future me - READ endpoint! Lists songs (singles) for an artist from our DB.
# No Spotify API calls here - just returns what we've already synced.
@router.get("/{artist_id}/songs", response_model=SongListResponse)
async def list_artist_songs(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> SongListResponse:
    """List all songs (singles) for an artist from the database.

    Returns tracks that have been synced and don't belong to any album.
    This is a read-only operation that doesn't call Spotify API.

    Args:
        artist_id: Artist UUID
        session: Database session

    Returns:
        List of tracks for the artist
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    service = ArtistSongsService(
        session=session,
        spotify_client=SpotifyClient.__new__(SpotifyClient),  # Dummy, not used for read
    )

    tracks = await service.get_artist_singles(artist_id_obj)

    return SongListResponse(
        tracks=[_track_to_response(t) for t in tracks],
        total_count=len(tracks),
        artist_id=artist_id,
    )


# Hey future me - DELETE a specific song! Requires both artist_id and track_id
# for validation - we don't want to accidentally delete tracks from wrong artist.
@router.delete("/{artist_id}/songs/{track_id}", response_model=DeleteResponse)
async def delete_artist_song(
    artist_id: str,
    track_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteResponse:
    """Delete a specific song from the database.

    Removes a single track from the database. The track must belong to
    the specified artist for the deletion to succeed.

    Args:
        artist_id: Artist UUID
        track_id: Track UUID to delete
        session: Database session

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: 400 if invalid ID format, 404 if track not found
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
        track_id_obj = TrackId.from_string(track_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {e}") from e

    service = ArtistSongsService(
        session=session,
        spotify_client=SpotifyClient.__new__(SpotifyClient),  # Dummy, not used for delete
    )

    try:
        await service.remove_song(track_id_obj, artist_id_obj)
        await session.commit()

        logger.info(f"Deleted song {track_id} from artist {artist_id}")

        return DeleteResponse(
            message=f"Successfully deleted song {track_id}",
            deleted_count=1,
        )
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete song {track_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete song: {str(e)}",
        ) from e


# Hey future me - BULK DELETE! Removes ALL songs (singles) for an artist.
# Use with caution - this clears synced songs but keeps the artist itself.
@router.delete("/{artist_id}/songs", response_model=DeleteResponse)
async def delete_all_artist_songs(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteResponse:
    """Delete all songs (singles) for an artist.

    Removes all tracks without album association for the specified artist.
    The artist itself is not deleted, only their synced songs.

    Args:
        artist_id: Artist UUID
        session: Database session

    Returns:
        Deletion confirmation with count

    Raises:
        HTTPException: 400 if invalid ID format
    """
    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    service = ArtistSongsService(
        session=session,
        spotify_client=SpotifyClient.__new__(SpotifyClient),  # Dummy, not used for delete
    )

    try:
        count = await service.remove_all_artist_songs(artist_id_obj)
        await session.commit()

        logger.info(f"Deleted {count} songs for artist {artist_id}")

        return DeleteResponse(
            message=f"Successfully deleted {count} songs for artist {artist_id}",
            deleted_count=count,
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete songs for artist {artist_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete songs: {str(e)}",
        ) from e
