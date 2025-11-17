"""Playlist management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from soulspot.api.dependencies import (
    get_import_playlist_use_case,
    get_playlist_repository,
    get_spotify_token_from_session,
    get_track_repository,
)
from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistRequest,
    ImportSpotifyPlaylistUseCase,
)
from soulspot.domain.value_objects import PlaylistId
from soulspot.infrastructure.persistence.repositories import (
    PlaylistRepository,
    TrackRepository,
)

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


@router.get("/{playlist_id}/export/m3u")
async def export_playlist_m3u(
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Export playlist as M3U file.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository
        track_repository: Track repository

    Returns:
        M3U file as plain text
    """
    from fastapi.responses import Response

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Build M3U content
        m3u_lines = ["#EXTM3U"]
        m3u_lines.append(f"#PLAYLIST:{playlist.name}")

        for track_id in playlist.track_ids:
            track = await track_repository.get_by_id(track_id)
            if track and track.file_path:
                duration = int(track.duration_ms / 1000) if track.duration_ms else -1
                artist = track.artist or "Unknown Artist"  # type: ignore[attr-defined]
                title = track.title or "Unknown Title"
                m3u_lines.append(f"#EXTINF:{duration},{artist} - {title}")
                m3u_lines.append(str(track.file_path))

        m3u_content = "\n".join(m3u_lines)

        return Response(
            content=m3u_content,
            media_type="audio/x-mpegurl",
            headers={
                "Content-Disposition": f'attachment; filename="{playlist.name}.m3u"'
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e


@router.get("/{playlist_id}/export/csv")
async def export_playlist_csv(
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Export playlist as CSV file.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository
        track_repository: Track repository

    Returns:
        CSV file
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Build CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Title", "Artist", "Album", "Duration (ms)", "File Path"])

        for track_id in playlist.track_ids:
            track = await track_repository.get_by_id(track_id)
            if track:
                writer.writerow(
                    [
                        track.title or "Unknown",
                        track.artist or "Unknown",  # type: ignore[attr-defined]
                        track.album or "Unknown",  # type: ignore[attr-defined]
                        track.duration_ms or "",
                        track.file_path or "",
                    ]
                )

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{playlist.name}.csv"'
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e


@router.get("/{playlist_id}/export/json")
async def export_playlist_json(
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Export playlist as JSON.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository
        track_repository: Track repository

    Returns:
        JSON with playlist and track details
    """
    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Build track list
        tracks = []
        for track_id in playlist.track_ids:
            track = await track_repository.get_by_id(track_id)
            if track:
                tracks.append(
                    {
                        "id": str(track.id.value),
                        "title": track.title,
                        "artist": track.artist,  # type: ignore[attr-defined]
                        "album": track.album,  # type: ignore[attr-defined]
                        "duration_ms": track.duration_ms,
                        "file_path": track.file_path,
                        "spotify_uri": str(track.spotify_uri)
                        if track.spotify_uri
                        else None,
                    }
                )

        return {
            "playlist": {
                "id": str(playlist.id.value),
                "name": playlist.name,
                "description": playlist.description,
                "source": playlist.source.value,
                "created_at": playlist.created_at.isoformat(),
                "updated_at": playlist.updated_at.isoformat(),
            },
            "tracks": tracks,
            "track_count": len(tracks),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e


@router.get("/{playlist_id}/missing-tracks")
async def get_missing_tracks(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Get tracks that are in the playlist but not downloaded to the library.

    Args:
        playlist_id: Playlist ID
        playlist_repository: Playlist repository
        track_repository: Track repository

    Returns:
        List of missing tracks
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get session for direct DB query
        session: AsyncSession = await anext(get_db_session(request))

        # Find tracks without file_path
        missing_tracks = []
        for track_id in playlist.track_ids:
            stmt = (
                select(TrackModel)
                .where(TrackModel.id == str(track_id.value))
                .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            )
            result = await session.execute(stmt)
            track_model = result.unique().scalar_one_or_none()

            if track_model and not track_model.file_path:
                missing_tracks.append(
                    {
                        "id": track_model.id,
                        "title": track_model.title,
                        "artist": track_model.artist.name
                        if track_model.artist
                        else "Unknown Artist",
                        "album": track_model.album.title
                        if track_model.album
                        else "Unknown Album",
                        "duration_ms": track_model.duration_ms,
                        "spotify_uri": track_model.spotify_uri,
                    }
                )

        return {
            "playlist_id": str(playlist.id.value),
            "playlist_name": playlist.name,
            "missing_tracks": missing_tracks,
            "missing_count": len(missing_tracks),
            "total_tracks": len(playlist.track_ids),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid playlist ID: {str(e)}"
        ) from e
