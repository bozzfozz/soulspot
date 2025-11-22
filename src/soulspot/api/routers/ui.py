"""UI routes for serving HTML templates."""

from pathlib import Path
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

# AI-Model: Copilot
# Hey future me - compute templates directory relative to THIS file so it works both in
# development (source tree) and production (installed package). The old hardcoded
# "src/soulspot/templates" breaks when package is installed because that path doesn't exist!
# Path(__file__).parent goes up to api/routers/, then .parent.parent goes to soulspot/,
# then / "templates" gets us to soulspot/templates/. This works whether code runs from
# source or site-packages. Don't change back to string literal path or it'll break again!
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


# Listen, the big dashboard index page! Gets REAL stats from repositories instead of hardcoded numbers
# which is great. Counts playlists, tracks, active downloads. queue_size filters downloads by status
# "pending" or "queued" - nice detailed metric. The stats dict is passed to template for display. This
# hits DB on every page load - no caching. Could be slow with large library. Active downloads query
# might be expensive if there are thousands of historical downloads (needs index on status field). The
# stats are current snapshot, could be stale by time page renders. Consider WebSocket updates? Returns
# full HTML page via Jinja2 template. Template must exist at src/soulspot/templates/index.html or crash!
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


# Yo this is HTMX partial for missing tracks in a playlist! Uses anext() to get session from generator
# which is sketchy (same pattern as before). Does N queries in loop for each track - bad performance.
# joinedload helps but still not great. Returns error.html template for 404/400 errors which is clean
# HTMX pattern. Track model has artist/album relationships so we check if track_model.artist exists
# before accessing .name. Missing tracks are those without file_path. Built for HTMX so returns HTML
# partial not full page. The missing_tracks list could be huge if playlist has 100s of missing tracks -
# no pagination! Template must handle long lists gracefully (scrolling, lazy loading, etc).
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


# Hey this just renders a static template - no DB lookups! The actual import logic happens via
# API POST to /playlists/import endpoint (different router). This is just the UI form page.
# IMPORTANT: This route MUST come before /playlists/{playlist_id} to avoid route conflicts!
# FastAPI matches routes in order, so specific paths like /import must be defined before
# parametric paths like /{playlist_id} to prevent "import" being treated as a playlist ID.
@router.get("/playlists/import", response_class=HTMLResponse)
async def import_playlist(request: Request) -> Any:
    """Import playlist page."""
    return templates.TemplateResponse("import_playlist.html", {"request": request})


# Listen, this renders the full playlist detail page with ALL tracks! Does N queries in a loop
# (one per track_id) which is SLOW for big playlists. Should batch fetch tracks in one query.
# The type: ignore comments are for accessing Track.artist/album which are relationships not
# direct attributes. track.is_broken is also a computed property that might not exist on all
# Track entities. Returns error.html template for 404/400 - nice UX pattern. The isoformat()
# calls convert datetimes to ISO strings for template rendering. This builds entire playlist
# data in memory before passing to template - could be huge for 1000+ track playlists!
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


# Yo, downloads page fetches ALL active downloads! list_active() might return thousands of downloads
# if your download history is long (needs DB index on status + created_at). The isoformat() calls
# can fail if started_at is None - we handle with ternary. progress_percent and error_message can
# also be None. This renders ALL downloads at once - no pagination! Could freeze browser with 1000s
# of rows. Should use virtual scrolling or pagination. Template gets full list in memory.
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


# Static template pages - no logic, just render HTML. These are lightweight routes.
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


# Hey, this is the new customizable dashboard! page=None means content loads via HTMX after initial
# render. edit_mode controls whether user sees widget drag-drop editor or read-only view. The actual
# widgets are loaded dynamically via widget template API, not embedded in this response. This keeps
# the initial page load fast - widgets hydrate themselves via data endpoints or SSE connections.
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


# This is the first-run wizard for new users! Shows "connect Spotify" flow and basic setup. Should
# only show once per user but we don't track "has completed onboarding" flag yet. Future: add user
# preferences table to track onboarding state and skip redirect to this page if already done.
@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request) -> Any:
    """First-run onboarding page for new users."""
    return templates.TemplateResponse("onboarding.html", {"request": request})


# Yo, this is the library overview page with aggregated stats! Loads ALL tracks into memory using
# list_all() - could be 10000s of tracks! The set() operations to count unique artists/albums work
# but require loading everything first. Should use DB aggregation queries (COUNT DISTINCT) instead.
# The track.artist/album type: ignore is for relationship attributes. broken_tracks uses is_broken
# property that might not exist on all Track entities. Stats are recalculated on every page load - no
# caching! This gets slow with big libraries. Consider Redis caching or pre-computing stats.
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


# Listen up - this groups ALL tracks by artist name in Python! Loads entire track library into memory
# which is super inefficient. Should be a SQL GROUP BY query with COUNT and DISTINCT. The artists_dict
# accumulates track counts and unique album names using set(). Converting set to len() for album_count
# works but we lose the actual album list. Sorting happens in Python after grouping - should be in SQL.
# No pagination means this returns ALL artists - could be 1000s! Will freeze browser with big library.
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


# Yo - same problem as artists! Loads ALL tracks, groups in Python, returns ALL albums unfiltered.
# The album_key uses "::" delimiter to combine artist+album (ugly but works). "Unknown" fallback for
# missing artist is good. year field is hardcoded None because Track doesn't have year (should pull
# from Album relationship). Sorting by artist then album in Python - should be SQL ORDER BY. No
# pagination! This is doomed with 1000+ albums. Needs DB-level aggregation or pagination badly!
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


# IMPORTANT: Library tracks page with SQLAlchemy direct queries! Uses anext() to get session - same
# sketchy pattern. select() with joinedload() is proper way to eagerly load relationships and avoid N+1.
# unique() on result prevents duplicate Track objects when joins create multiple rows. scalars().all()
# gets list of Track models. The track data extraction handles None values gracefully with "Unknown".
# Sorts by artist/album/title in memory using .sort() with lambda - could be slow for 10000s of tracks!
# Should use ORDER BY in SQL query instead. The type: ignore is needed for .lower() on potentially None
# values. Good use of joinedload to prevent N+1 queries. Returns full HTML page with all tracks - could
# be HUGE! Should paginate or use virtual scrolling for big libraries. This loads everything into memory!
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


# Hey heads up - this shows ONE artist's albums+tracks! unquote() handles URL-encoded artist names (e.g.,
# "AC%2FDC" becomes "AC/DC"). The SQL query uses join + where to filter by artist.name - efficient!
# joinedload() prevents N+1 by eagerly loading relationships. unique() prevents duplicate Track objects
# from joins. has() is SQLAlchemy syntax for filtering on relationship (WHERE EXISTS subquery). The
# albums_dict groups tracks by album in Python - could be SQL but OK since we already filtered by artist.
# hasattr checks for year field that might not exist on Album model. Returns 404 if no tracks found for
# artist. Sort by album then track number (or title if no track_number). Album key uses "::" delimiter.
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


# Listen, this shows ONE album's tracks! album_key format is "artist::album" (e.g., "Pink Floyd::The Wall").
# We split on "::" to extract both parts - if format is wrong we return 400 error. unquote() handles
# URL encoding. SQL query joins artist AND album, filters both, uses joinedload for eager loading.
# unique() prevents duplicates from joins. Returns 404 if no tracks found. Sorts by track_number (or
# title if missing). Calculates total_duration_ms by summing all track durations (or 0 if None). Gets
# year from first track's album (assumes all tracks same album) - fragile if Album has no year field!
# Track number 999 is used as fallback sort value for tracks missing track_number - pushes to end.
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


# Yo, this returns an HTMX partial for the metadata editor modal! Uses anext() to grab DB session
# (sketchy pattern). Queries one track with joinedload for artist/album. Returns error.html partial
# for 404/400 instead of raising HTTPException - nice HTMX pattern. album_artist and genre are hardcoded
# None (TODOs) - should add these fields to Track/Album models. year comes from album relationship if
# it exists. The track_data dict matches what the metadata_editor.html template expects. This is a
# modal fragment, not full page. Template should have form fields pre-filled with current values.
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


# Hey future me, this renders the followed artists sync page! It's a simple GET that loads the template
# with empty state. The actual sync happens client-side via HTMX POST to /api/automation/followed-artists/sync
# which returns JSON that gets rendered by JavaScript in the template. No DB queries on initial page load -
# keeps it fast. Users see empty state with "Sync from Spotify" button. After sync, artists list populates
# and users can select which artists to add to watchlists. The bulk create uses POST to /api/automation/
# followed-artists/watchlists/bulk. This page requires Spotify OAuth token in session or sync will fail!
@router.get("/automation/followed-artists", response_class=HTMLResponse)
async def followed_artists_page(request: Request) -> Any:
    """Followed artists sync and watchlist creation page.

    Args:
        request: FastAPI request object

    Returns:
        HTML page for managing followed artists
    """
    return templates.TemplateResponse(
        "followed_artists.html",
        {"request": request},
    )
