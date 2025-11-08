"""Playlist management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from soulspot.config import Settings, get_settings

router = APIRouter()


@router.post("/import")
async def import_playlist(
    playlist_id: str = Query(..., description="Spotify playlist ID"),
    access_token: str = Query(..., description="Spotify access token"),  # noqa: ARG001
    fetch_all_tracks: bool = Query(True, description="Fetch all tracks in playlist"),
    settings: Settings = Depends(get_settings),  # noqa: ARG001
) -> dict[str, Any]:
    """Import a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID
        access_token: Valid Spotify access token
        fetch_all_tracks: Whether to fetch all tracks

    Returns:
        Import status and statistics
    """
    # TODO: Initialize use case with proper dependencies
    # For now, return a placeholder response

    return {
        "message": "Playlist import started",
        "playlist_id": playlist_id,
        "status": "pending",
        "tracks_imported": 0,
        "tracks_failed": 0,
    }


@router.get("/")
async def list_playlists(
    skip: int = Query(0, ge=0, description="Number of playlists to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of playlists to return"),
) -> dict[str, Any]:
    """List all playlists.

    Args:
        skip: Number of playlists to skip
        limit: Number of playlists to return

    Returns:
        List of playlists
    """
    # TODO: Implement with repository
    return {
        "playlists": [],
        "total": 0,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{playlist_id}")
async def get_playlist(
    playlist_id: str,
) -> dict[str, Any]:
    """Get playlist details.

    Args:
        playlist_id: Playlist ID

    Returns:
        Playlist details with tracks
    """
    # TODO: Implement with repository
    raise HTTPException(status_code=404, detail="Playlist not found")
