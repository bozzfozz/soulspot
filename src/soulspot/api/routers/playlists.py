"""Playlist management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from soulspot.api.dependencies import (
    get_import_playlist_use_case,
    get_playlist_repository,
    get_spotify_token_from_session,
)
from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistRequest,
    ImportSpotifyPlaylistUseCase,
)
from soulspot.domain.value_objects import PlaylistId
from soulspot.infrastructure.persistence.repositories import PlaylistRepository

router = APIRouter()


@router.post("/import")
async def import_playlist(
    playlist_id: str = Query(..., description="Spotify playlist ID"),
    fetch_all_tracks: bool = Query(True, description="Fetch all tracks in playlist"),
    access_token: str = Depends(get_spotify_token_from_session),
    use_case: ImportSpotifyPlaylistUseCase = Depends(get_import_playlist_use_case),
) -> dict[str, Any]:
    """Import a Spotify playlist using session-based authentication.

    The access token is automatically retrieved from your session.
    If your token is expired, it will be automatically refreshed.
    If you don't have a valid session, you'll receive a 401 error
    and need to authenticate at /auth first.

    Args:
        playlist_id: Spotify playlist ID
        fetch_all_tracks: Whether to fetch all tracks
        access_token: Automatically retrieved from session
        use_case: Import playlist use case

    Returns:
        Import status and statistics
    """
    try:
        request = ImportSpotifyPlaylistRequest(
            playlist_id=playlist_id,
            access_token=access_token,
            fetch_all_tracks=fetch_all_tracks,
        )
        response = await use_case.execute(request)

        return {
            "message": "Playlist imported successfully",
            "playlist_id": str(response.playlist.id.value),
            "playlist_name": response.playlist.name,
            "tracks_imported": response.tracks_imported,
            "tracks_failed": response.tracks_failed,
            "errors": response.errors,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to import playlist: {str(e)}"
        ) from e


@router.get("/")
async def list_playlists(
    skip: int = Query(0, ge=0, description="Number of playlists to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of playlists to return"),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """List all playlists.

    Args:
        skip: Number of playlists to skip
        limit: Number of playlists to return
        playlist_repository: Playlist repository

    Returns:
        List of playlists
    """
    playlists = await playlist_repository.list_all(limit=limit, offset=skip)

    return {
        "playlists": [
            {
                "id": str(playlist.id.value),
                "name": playlist.name,
                "description": playlist.description,
                "source": playlist.source.value,
                "track_count": len(playlist.track_ids),
                "spotify_uri": str(playlist.spotify_uri)
                if playlist.spotify_uri
                else None,
                "created_at": playlist.created_at.isoformat(),
                "updated_at": playlist.updated_at.isoformat(),
            }
            for playlist in playlists
        ],
        "total": len(playlists),
        "skip": skip,
        "limit": limit,
    }


@router.get("/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> dict[str, Any]:
    """Get playlist details.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository

    Returns:
        Playlist details with tracks
    """
    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        return {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "source": playlist.source.value,
            "spotify_uri": str(playlist.spotify_uri) if playlist.spotify_uri else None,
            "track_ids": [str(track_id.value) for track_id in playlist.track_ids],
            "track_count": len(playlist.track_ids),
            "created_at": playlist.created_at.isoformat(),
            "updated_at": playlist.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e
