"""UI routes for serving HTML templates."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from soulspot.api.dependencies import (
    get_download_repository,
    get_playlist_repository,
    get_track_repository,
)
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    TrackRepository,
)

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Dashboard page with real statistics."""
    # Get real statistics from repositories
    playlists = await playlist_repository.list_all()
    tracks = await track_repository.list_all()
    active_downloads = await download_repository.list_active()

    stats = {
        "playlists": len(playlists),
        "tracks": len(tracks),
        "downloads": len(active_downloads),
        "queue_size": sum(
            1 for d in active_downloads if d.status.value in ["pending", "queued"]
        ),
    }
    return templates.TemplateResponse(
        "index.html", {"request": request, "stats": stats}
    )


@router.get("/playlists", response_class=HTMLResponse)
async def playlists(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
) -> Any:
    """List playlists page with real data."""
    playlists_list = await playlist_repository.list_all()

    # Convert to template-friendly format
    playlists_data = [
        {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "track_count": len(playlist.track_ids),
            "source": playlist.source.value,
            "created_at": playlist.created_at.isoformat(),
        }
        for playlist in playlists_list
    ]

    return templates.TemplateResponse(
        "playlists.html", {"request": request, "playlists": playlists_data}
    )


@router.get("/playlists/{playlist_id}/export-modal", response_class=HTMLResponse)
async def playlist_export_modal(
    request: Request,
    playlist_id: str,
) -> Any:
    """Return export modal partial."""
    return templates.TemplateResponse(
        "partials/export_modal.html",
        {"request": request, "playlist_id": playlist_id},
    )


@router.get("/playlists/{playlist_id}/missing-tracks", response_class=HTMLResponse)
async def playlist_missing_tracks(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Return missing tracks partial for a playlist."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.domain.value_objects import PlaylistId
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Playlist not found",
                },
                status_code=404,
            )

        # Get session for direct DB query
        session = await anext(get_db_session(request))

        # Find tracks without file_path (missing tracks)
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

        return templates.TemplateResponse(
            "partials/missing_tracks.html",
            {"request": request, "missing_tracks": missing_tracks},
        )

    except ValueError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 400,
                "error_message": "Invalid playlist ID",
            },
            status_code=400,
        )


@router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
async def playlist_detail(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Playlist detail page with tracks."""
    from soulspot.domain.value_objects import PlaylistId

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            # Return 404 page or redirect
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Playlist not found",
                },
                status_code=404,
            )

        # Get track details for the playlist
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
                        "spotify_uri": str(track.spotify_uri)
                        if track.spotify_uri
                        else None,
                        "file_path": track.file_path,
                        "is_broken": track.is_broken,  # type: ignore[attr-defined]
                    }
                )

        playlist_data = {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "source": playlist.source.value,
            "track_count": len(playlist.track_ids),
            "tracks": tracks,
            "created_at": playlist.created_at.isoformat(),
            "updated_at": playlist.updated_at.isoformat(),
            "spotify_uri": str(playlist.spotify_uri) if playlist.spotify_uri else None,
        }

        return templates.TemplateResponse(
            "playlist_detail.html", {"request": request, "playlist": playlist_data}
        )

    except ValueError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 400,
                "error_message": "Invalid playlist ID",
            },
            status_code=400,
        )


@router.get("/playlists/import", response_class=HTMLResponse)
async def import_playlist(request: Request) -> Any:
    """Import playlist page."""
    return templates.TemplateResponse("import_playlist.html", {"request": request})


@router.get("/downloads", response_class=HTMLResponse)
async def downloads(
    request: Request,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Downloads page with real data."""
    downloads_list = await download_repository.list_active()

    # Convert to template-friendly format
    downloads_data = [
        {
            "id": str(download.id.value),
            "track_id": str(download.track_id.value),
            "status": download.status.value,
            "priority": download.priority,
            "progress_percent": download.progress_percent,
            "error_message": download.error_message,
            "started_at": download.started_at.isoformat()
            if download.started_at
            else None,
            "created_at": download.created_at.isoformat(),
        }
        for download in downloads_list
    ]

    return templates.TemplateResponse(
        "downloads.html", {"request": request, "downloads": downloads_data}
    )


@router.get("/auth", response_class=HTMLResponse)
async def auth(request: Request) -> Any:
    """Auth page."""
    return templates.TemplateResponse("auth.html", {"request": request})


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> Any:
    """Advanced search page."""
    return templates.TemplateResponse("search.html", {"request": request})


@router.get("/theme-sample", response_class=HTMLResponse)
async def theme_sample(request: Request) -> Any:
    """Harmony theme sample page with component showcase."""
    return templates.TemplateResponse("theme-sample.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> Any:
    """Settings configuration page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Any:
    """Dynamic dashboard with customizable widgets."""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page": None,  # Will be loaded via HTMX
            "edit_mode": False,
        },
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request) -> Any:
    """First-run onboarding page for new users."""
    return templates.TemplateResponse("onboarding.html", {"request": request})


@router.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Library browser page."""
    tracks = await track_repository.list_all()

    # Get unique artists and albums
    artists_set = set()
    albums_set = set()
    for track in tracks:
        if track.artist:  # type: ignore[attr-defined]
            artists_set.add(track.artist)  # type: ignore[attr-defined]
        if track.album:  # type: ignore[attr-defined]
            albums_set.add(track.album)  # type: ignore[attr-defined]

    stats = {
        "total_tracks": len(tracks),
        "total_artists": len(artists_set),
        "total_albums": len(albums_set),
        "tracks_with_files": sum(1 for t in tracks if t.file_path),
        "broken_tracks": sum(1 for t in tracks if t.is_broken),  # type: ignore[attr-defined,misc]
    }

    return templates.TemplateResponse(
        "library.html", {"request": request, "stats": stats}
    )


@router.get("/library/artists", response_class=HTMLResponse)
async def library_artists(
    request: Request,
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Library artists browser page."""
    tracks = await track_repository.list_all()

    # Group tracks by artist
    artists_dict: dict[str, dict[str, Any]] = {}
    for track in tracks:
        if not track.artist:  # type: ignore[attr-defined]
            continue
        if track.artist not in artists_dict:  # type: ignore[attr-defined]
            artists_dict[track.artist] = {  # type: ignore[attr-defined]
                "name": track.artist,  # type: ignore[attr-defined]
                "track_count": 0,
                "album_count": 0,
                "albums": set(),
            }
        artists_dict[track.artist]["track_count"] += 1  # type: ignore[attr-defined]
        if track.album:  # type: ignore[attr-defined]
            artists_dict[track.artist]["albums"].add(track.album)  # type: ignore[attr-defined]

    # Convert to list and calculate album counts
    artists = [
        {
            "name": artist_data["name"],
            "track_count": artist_data["track_count"],
            "album_count": len(artist_data["albums"]),
        }
        for artist_data in artists_dict.values()
    ]

    # Sort by name
    artists.sort(key=lambda x: x["name"].lower())

    return templates.TemplateResponse(
        "library_artists.html", {"request": request, "artists": artists}
    )


@router.get("/library/albums", response_class=HTMLResponse)
async def library_albums(
    request: Request,
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Library albums browser page."""
    tracks = await track_repository.list_all()

    # Group tracks by album
    albums_dict: dict[str, dict[str, Any]] = {}
    for track in tracks:
        if not track.album:  # type: ignore[attr-defined]
            continue
        album_key = f"{track.artist or 'Unknown'}::{track.album}"  # type: ignore[attr-defined]
        if album_key not in albums_dict:
            albums_dict[album_key] = {
                "title": track.album,  # type: ignore[attr-defined]
                "artist": track.artist or "Unknown Artist",  # type: ignore[attr-defined]
                "track_count": 0,
                "year": None,  # Could be extracted from metadata
            }
        albums_dict[album_key]["track_count"] += 1

    # Convert to list
    albums = list(albums_dict.values())

    # Sort by artist then album
    albums.sort(key=lambda x: (x["artist"].lower(), x["title"].lower()))

    return templates.TemplateResponse(
        "library_albums.html", {"request": request, "albums": albums}
    )


@router.get("/library/tracks", response_class=HTMLResponse)
async def library_tracks(
    request: Request,
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Library tracks browser page."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    # Get session for direct DB query
    session = await anext(get_db_session(request))

    # Query with joined loads for artist and album
    stmt = select(TrackModel).options(
        joinedload(TrackModel.artist), joinedload(TrackModel.album)
    )
    result = await session.execute(stmt)
    track_models = result.unique().scalars().all()

    # Convert to template-friendly format
    tracks_data = [
        {
            "id": track.id,
            "title": track.title,
            "artist": track.artist.name if track.artist else "Unknown Artist",
            "album": track.album.title if track.album else "Unknown Album",
            "duration_ms": track.duration_ms,
            "file_path": track.file_path,
            "is_broken": track.is_broken,
        }
        for track in track_models
    ]

    # Sort by artist, album, title
    tracks_data.sort(
        key=lambda x: (x["artist"].lower(), x["album"].lower(), x["title"].lower())  # type: ignore[union-attr]
    )

    return templates.TemplateResponse(
        "library_tracks.html", {"request": request, "tracks": tracks_data}
    )


@router.get("/library/artists/{artist_name}", response_class=HTMLResponse)
async def library_artist_detail(
    request: Request,
    artist_name: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Artist detail page with albums and tracks."""
    from urllib.parse import unquote

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    artist_name = unquote(artist_name)

    # Get session for direct DB query
    session = await anext(get_db_session(request))

    # Query tracks with joined loads for artist and album
    stmt = (
        select(TrackModel)
        .join(TrackModel.artist)
        .where(TrackModel.artist.has(name=artist_name))
        .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
    )
    result = await session.execute(stmt)
    track_models = result.unique().scalars().all()

    if not track_models:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 404,
                "error_message": f"Artist '{artist_name}' not found",
            },
            status_code=404,
        )

    # Group tracks by album
    albums_dict: dict[str, dict[str, Any]] = {}
    for track in track_models:
        if track.album:
            album_key = track.album.title
            if album_key not in albums_dict:
                albums_dict[album_key] = {
                    "id": f"{artist_name}::{track.album.title}",
                    "title": track.album.title,
                    "track_count": 0,
                    "year": track.album.year if hasattr(track.album, "year") else None,
                }
            albums_dict[album_key]["track_count"] += 1

    albums = sorted(albums_dict.values(), key=lambda x: x["title"].lower())

    # Convert tracks to template format
    tracks_data = [
        {
            "id": track.id,
            "title": track.title,
            "artist": track.artist.name if track.artist else "Unknown Artist",
            "album": track.album.title if track.album else "Unknown Album",
            "duration_ms": track.duration_ms,
            "file_path": track.file_path,
            "is_broken": track.is_broken,
        }
        for track in track_models
    ]

    # Sort tracks by album, then track number/title
    tracks_data.sort(key=lambda x: (x["album"] or "", x["title"].lower()))  # type: ignore[union-attr]

    artist_data = {
        "name": artist_name,
        "albums": albums,
        "tracks": tracks_data,
        "track_count": len(tracks_data),
    }

    return templates.TemplateResponse(
        "library_artist_detail.html", {"request": request, "artist": artist_data}
    )


@router.get("/library/albums/{album_key}", response_class=HTMLResponse)
async def library_album_detail(
    request: Request,
    album_key: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Album detail page with track listing."""
    from urllib.parse import unquote

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    album_key = unquote(album_key)

    # Split key into artist and album
    if "::" not in album_key:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 400,
                "error_message": "Invalid album key format",
            },
            status_code=400,
        )

    artist_name, album_title = album_key.split("::", 1)

    # Get session for direct DB query
    session = await anext(get_db_session(request))

    # Query tracks for this album
    stmt = (
        select(TrackModel)
        .join(TrackModel.artist)
        .join(TrackModel.album)
        .where(
            TrackModel.artist.has(name=artist_name),
            TrackModel.album.has(title=album_title),
        )
        .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
    )
    result = await session.execute(stmt)
    track_models = result.unique().scalars().all()

    if not track_models:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 404,
                "error_message": f"Album '{album_title}' by '{artist_name}' not found",
            },
            status_code=404,
        )

    # Convert tracks to template format
    tracks_data = [
        {
            "id": track.id,
            "title": track.title,
            "artist": track.artist.name if track.artist else "Unknown Artist",
            "album": track.album.title if track.album else "Unknown Album",
            "track_number": track.track_number,
            "duration_ms": track.duration_ms,
            "file_path": track.file_path,
            "is_broken": track.is_broken,
        }
        for track in track_models
    ]

    # Sort by track number, then title
    tracks_data.sort(key=lambda x: (x["track_number"] or 999, x["title"].lower()))  # type: ignore[union-attr]

    # Calculate total duration
    total_duration_ms = sum(t["duration_ms"] or 0 for t in tracks_data)  # type: ignore[misc]

    # Get year from first track's album
    year = (
        track_models[0].album.year
        if track_models
        and track_models[0].album
        and hasattr(track_models[0].album, "year")
        else None
    )

    album_data = {
        "title": album_title,
        "artist": artist_name,
        "artist_slug": artist_name,
        "tracks": tracks_data,
        "year": year,
        "total_duration_ms": total_duration_ms,
    }

    return templates.TemplateResponse(
        "library_album_detail.html", {"request": request, "album": album_data}
    )


@router.get("/tracks/{track_id}/metadata-editor", response_class=HTMLResponse)
async def track_metadata_editor(
    request: Request,
    track_id: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Return metadata editor modal for a track."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        # Get session for direct DB query
        session = await anext(get_db_session(request))

        stmt = (
            select(TrackModel)
            .where(TrackModel.id == track_id)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        )
        result = await session.execute(stmt)
        track_model = result.unique().scalar_one_or_none()

        if not track_model:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Track not found",
                },
                status_code=404,
            )

        track_data = {
            "id": track_model.id,
            "title": track_model.title,
            "artist": track_model.artist.name if track_model.artist else None,
            "album": track_model.album.title if track_model.album else None,
            "album_artist": None,  # TODO: Add album_artist field
            "genre": None,  # TODO: Add genre field
            "year": track_model.album.year
            if track_model.album and hasattr(track_model.album, "year")
            else None,
            "track_number": track_model.track_number,
            "disc_number": track_model.disc_number,
            "file_path": track_model.file_path,
        }

        return templates.TemplateResponse(
            "partials/metadata_editor.html",
            {"request": request, "track": track_data},
        )

    except ValueError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 400,
                "error_message": "Invalid track ID",
            },
            status_code=400,
        )
