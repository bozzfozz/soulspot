"""UI routes for serving HTML templates."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_deezer_plugin,
    get_download_repository,
    get_image_service,
    get_job_queue,
    get_library_scanner_service,
    get_playlist_repository,
    get_spotify_browse_repository,
    get_spotify_plugin_optional,
    get_spotify_sync_service,
    get_track_repository,
)
from soulspot.application.services.library_scanner_service import LibraryScannerService
from soulspot.application.services.spotify_sync_service import SpotifySyncService
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.config import get_settings
from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    SpotifyBrowseRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

# AI-Model: Copilot
# Hey future me - compute templates directory relative to THIS file so it works both in
# development (source tree) and production (installed package). The old hardcoded
# "src/soulspot/templates" breaks when package is installed because that path doesn't exist!
# Path(__file__).parent goes up to api/routers/, then .parent.parent goes to soulspot/,
# then / "templates" gets us to soulspot/templates/. This works whether code runs from
# source or site-packages. Don't change back to string literal path or it'll break again!
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Hey future me - ImageService provides centralized image URL resolution!
# We add get_display_url as a global template function so templates can call:
#   {{ get_display_url(artist.image_url, artist.image_path, 'artist') }}
# This replaces scattered inline logic with a single source of truth.
# See: docs/architecture/IMAGE_SERVICE_DETAILED_PLAN.md
#
# NOTE: Using module-level instance for SYNC template methods (get_display_url).
# For ASYNC methods (download_and_cache), use Depends(get_image_service_with_session).
_image_service = get_image_service(get_settings())


def _get_display_url(
    source_url: str | None,
    local_path: str | None,
    entity_type: str = "album",
) -> str:
    """Template helper for image URL resolution.

    Usage in Jinja2:
        {{ get_display_url(album.cover_url, album.cover_path, 'album') }}
        {{ get_display_url(artist.image_url, artist.image_path, 'artist') }}
        {{ get_display_url(playlist.cover_url, playlist.cover_path, 'playlist') }}
    """
    return _image_service.get_display_url(source_url, local_path, entity_type)  # type: ignore[arg-type]


# Register as global template function
templates.env.globals["get_display_url"] = _get_display_url
templates.env.globals["get_placeholder"] = _image_service.get_placeholder

router = APIRouter()


# Listen, the big dashboard index page! Gets REAL stats from repositories instead of hardcoded numbers
# which is great. Counts playlists, tracks, active downloads. queue_size filters downloads by status
# "pending" or "queued" - nice detailed metric. The stats dict is passed to template for display. This
# hits DB on every page load - no caching. Could be slow with large library. Active downloads query
# might be expensive if there are thousands of historical downloads (needs index on status field). The
# stats are current snapshot, could be stale by time page renders. Consider WebSocket updates? Returns
# full HTML page via Jinja2 template.
# UPDATE: Now uses dashboard.html with animated UI and real DB stats!
@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    download_repository: DownloadRepository = Depends(get_download_repository),
    spotify_repository: SpotifyBrowseRepository = Depends(
        get_spotify_browse_repository
    ),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Main dashboard page with real statistics and animated UI."""
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        DownloadModel,
        PlaylistModel,
        PlaylistTrackModel,
        TrackModel,
    )

    # Count playlists
    playlists_stmt = select(func.count(PlaylistModel.id))
    playlists_result = await session.execute(playlists_stmt)
    playlist_count = playlists_result.scalar() or 0

    # Count tracks with local files (downloaded)
    tracks_with_files_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    tracks_result = await session.execute(tracks_with_files_stmt)
    tracks_downloaded = tracks_result.scalar() or 0

    # Count total tracks in playlists
    total_tracks_stmt = select(func.count(func.distinct(PlaylistTrackModel.track_id)))
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count completed downloads
    completed_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "completed"
    )
    completed_result = await session.execute(completed_stmt)
    completed_downloads = completed_result.scalar() or 0

    # Count queue (pending/queued downloads)
    queue_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status.in_(["pending", "queued", "downloading"])
    )
    queue_result = await session.execute(queue_stmt)
    queue_size = queue_result.scalar() or 0

    # Count active downloads
    active_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "downloading"
    )
    active_result = await session.execute(active_stmt)
    active_downloads = active_result.scalar() or 0

    # Get Spotify synced data counts
    spotify_artists = await spotify_repository.count_artists()
    spotify_albums = await spotify_repository.count_albums()
    spotify_tracks = await spotify_repository.count_tracks()

    # Get recent playlists for display (limit 6)
    playlists_list = await playlist_repository.list_all()
    recent_playlists = [
        {
            "id": str(p.id.value),
            "name": p.name,
            "description": p.description,
            "track_count": p.track_count(),
            "cover_url": p.cover.url if p.cover else None,
            # Hey future me - cover_path enables get_display_url() to prefer local cache
            "cover_path": p.cover.path if p.cover else None,
            "downloaded_count": 0,
        }
        for p in playlists_list[:6]
    ]

    # Get recent activity (completed downloads)
    recent_downloads = await download_repository.list_recent(limit=5)
    recent_activity = []
    for d in recent_downloads:
        # Fetch track info for this download with artist and album relationships
        from sqlalchemy.orm import selectinload

        track_stmt = (
            select(TrackModel)
            .options(
                selectinload(TrackModel.artist),
                selectinload(TrackModel.album),
            )
            .where(TrackModel.id == str(d.track_id.value))
        )
        track_result = await session.execute(track_stmt)
        track_model = track_result.scalar_one_or_none()

        # Extract artist name and album art
        artist_name = "Unknown Artist"
        album_art_url = None
        album_art_path = None

        if track_model:
            if track_model.artist:
                artist_name = track_model.artist.name
            if track_model.album:
                album_art_url = track_model.album.cover_url
                album_art_path = track_model.album.cover_path

        recent_activity.append(
            {
                "title": track_model.title if track_model else "Unknown Track",
                "artist": artist_name,
                "album_art": album_art_url,
                # Hey future me - album_art_path enables get_display_url() local cache
                "album_art_path": album_art_path,
                "status": d.status.value,
                "timestamp": d.completed_at.strftime("%H:%M")
                if d.completed_at
                else "--:--",
            }
        )

    stats = {
        "playlists": playlist_count,
        "tracks": total_tracks,
        "tracks_downloaded": tracks_downloaded,
        "downloads": completed_downloads,
        "queue_size": queue_size,
        "active_downloads": active_downloads,
        "spotify_artists": spotify_artists,
        "spotify_albums": spotify_albums,
        "spotify_tracks": spotify_tracks,
    }

    # Get latest releases from followed artists for the dashboard card
    # Hey future me - this is the "New Releases" feature! We fetch latest albums/singles
    # from spotify_albums table (pre-synced data), sorted by release_date descending.
    # Limit to 12 for a nice 4x3 or 6x2 grid display.
    latest_releases_raw = await spotify_repository.get_latest_releases(limit=12)
    latest_releases = [
        {
            "spotify_id": album.spotify_uri,
            "name": album.title,
            "artist_name": artist_name,
            "artist_id": album.artist_id,
            "image_url": album.cover_url,
            # Hey future me - image_path is for local cache. These are browse albums
            # from spotify_albums table, not library albums, so no local cache yet.
            # Template uses: get_display_url(image_url, image_path, 'album')
            "image_path": album.cover_path,
            "release_date": album.release_date,
            "album_type": album.primary_type,
            "total_tracks": album.total_tracks,
        }
        for album, artist_name in latest_releases_raw
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "stats": stats,
            "playlists": recent_playlists,
            "recent_activity": recent_activity,
            "latest_releases": latest_releases,
        },
    )


@router.get("/playlists", response_class=HTMLResponse)
async def playlists(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """List playlists page with real data."""
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        PlaylistTrackModel,
        TrackModel,
    )

    playlists_list = await playlist_repository.list_all()

    # Hey future me - calculate aggregate stats for the dashboard!
    # We need total_tracks, downloaded_tracks, pending_tracks across ALL playlists.
    # Using a single query with joins is way more efficient than N+1 queries.
    # Note: playlist_tracks is PlaylistTrackModel, not a raw table!

    # Count total tracks across all playlists (tracks can be in multiple playlists)
    total_tracks_stmt = select(func.count(func.distinct(PlaylistTrackModel.track_id)))
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count downloaded tracks (have file_path) that are in any playlist
    downloaded_stmt = (
        select(func.count(func.distinct(PlaylistTrackModel.track_id)))
        .select_from(PlaylistTrackModel)
        .join(TrackModel, TrackModel.id == PlaylistTrackModel.track_id)
        .where(TrackModel.file_path.isnot(None))
    )
    downloaded_result = await session.execute(downloaded_stmt)
    downloaded_tracks = downloaded_result.scalar() or 0

    pending_tracks = total_tracks - downloaded_tracks

    # Convert to template-friendly format
    # Hey future me - cover_url field in API response is for template compatibility!
    # It gets its value from playlist.cover.url (ImageRef value object).
    # Without it, all playlists show placeholder images even though covers exist.
    # cover_path enables get_display_url() to prefer local cache over CDN.
    playlists_data = [
        {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "track_count": len(playlist.track_ids),
            "source": playlist.source.value,
            "cover_url": playlist.cover.url if playlist.cover else None,
            "cover_path": playlist.cover.path if playlist.cover else None,
            "created_at": playlist.created_at.isoformat(),
        }
        for playlist in playlists_list
    ]

    return templates.TemplateResponse(
        request,
        "playlists.html",
        context={
            "playlists": playlists_data,
            "total_tracks": total_tracks,
            "downloaded_tracks": downloaded_tracks,
            "pending_tracks": pending_tracks,
        },
    )


# Yo this is HTMX partial for missing tracks in a playlist! Uses Depends(get_db_session) to properly
# manage DB session lifecycle. Does N queries in loop for each track - bad performance. joinedload helps
# but still not great. Returns error.html template for 404/400 errors which is clean HTMX pattern.
# Track model has artist/album relationships so we check if track_model.artist exists before accessing
# .name. Missing tracks are those without file_path. Built for HTMX so returns HTML partial not full page.
# The missing_tracks list could be huge if playlist has 100s of missing tracks - no pagination! Template
# must handle long lists gracefully (scrolling, lazy loading, etc).
@router.get("/playlists/{playlist_id}/missing-tracks", response_class=HTMLResponse)
async def playlist_missing_tracks(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Return missing tracks partial for a playlist."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.domain.value_objects import PlaylistId
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            return templates.TemplateResponse(
                request,
                "error.html",
                context={
                    "error_code": 404,
                    "error_message": "Playlist not found",
                },
                status_code=404,
            )

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
            request,
            "partials/missing_tracks.html",
            context={"missing_tracks": missing_tracks},
        )

    except ValueError:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
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
    return templates.TemplateResponse(request, "import_playlist.html")


# Listen, this renders the full playlist detail page with ALL tracks! Uses batch query with
# joinedload to avoid N+1 queries - we fetch all tracks with artist/album in ONE query.
# The cover_url API field comes from Playlist.cover.url (ImageRef) for Spotify playlists.
# Returns error.html template for 404/400 - nice UX pattern. This builds entire playlist
# data in memory before passing to template - could be huge for 1000+ track playlists!
@router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
async def playlist_detail(
    request: Request,
    playlist_id: str,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Playlist detail page with tracks."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.domain.value_objects import PlaylistId
    from soulspot.infrastructure.persistence.models import (
        PlaylistTrackModel,
        TrackModel,
    )

    try:
        playlist_id_obj = PlaylistId.from_string(playlist_id)
        playlist = await playlist_repository.get_by_id(playlist_id_obj)

        if not playlist:
            # Return 404 page or redirect
            return templates.TemplateResponse(
                request,
                "error.html",
                context={
                    "error_code": 404,
                    "error_message": "Playlist not found",
                },
                status_code=404,
            )

        # Batch fetch all tracks with artist/album in ONE query via PlaylistTrackModel
        # Hey future me - this avoids the N+1 problem! We join playlist_tracks -> tracks -> artist/album
        stmt = (
            select(TrackModel)
            .join(PlaylistTrackModel, PlaylistTrackModel.track_id == TrackModel.id)
            .where(PlaylistTrackModel.playlist_id == playlist_id)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            .order_by(PlaylistTrackModel.position)
        )
        result = await session.execute(stmt)
        track_models = result.unique().scalars().all()

        # Convert ORM models to template-friendly dicts
        # Hey future me - album_art comes from the Album's cover_url!
        # We eager-load the album relationship and grab its cover image.
        # album_art_path enables get_display_url() local cache preference.
        tracks = [
            {
                "id": track.id,
                "title": track.title,
                "artist": track.artist.name if track.artist else "Unknown Artist",
                "album": track.album.title if track.album else "Unknown Album",
                "album_art": track.album.cover_url if track.album else None,
                "album_art_path": track.album.cover_path if track.album else None,
                "duration_ms": track.duration_ms,
                "spotify_uri": track.spotify_uri,
                "file_path": track.file_path,
                "is_broken": track.is_broken,
            }
            for track in track_models
        ]

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
            "cover_url": playlist.cover.url if playlist.cover else None,  # Spotify playlist cover image (ImageRef)
            "cover_path": playlist.cover.path if playlist.cover else None,
        }

        return templates.TemplateResponse(
            request, "playlist_detail.html", context={"playlist": playlist_data}
        )

    except ValueError:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 400,
                "error_message": "Invalid playlist ID",
            },
            status_code=400,
        )


# Yo, downloads page fetches ALL active downloads! list_active() might return thousands of downloads
# if your download history is long (needs DB index on status + created_at). The isoformat() calls
# can fail if started_at is None - we handle with ternary. progress_percent and error_message can
# Hey future me - Downloads page now has DB-LEVEL pagination! Default 100 per page, max 500.
# We pass pagination metadata to template for rendering page navigation. Stats (active, queue,
# completed, failed) are fetched separately for the stats cards at the top of the page.
# Track info (title, artist, album_art) is loaded via joinedload for display in queue items.


async def _get_downloads_data(
    download_repository: DownloadRepository,
    session: AsyncSession,
    page: int = 1,
    limit: int = 100,
) -> dict[str, Any]:
    """Shared helper to fetch downloads data for both full page and partial.

    Hey future me - das ist extrahiert weil wir 2 Endpoints brauchen:
    1. /downloads - Volle Seite mit Header, Stats, Tabs
    2. /downloads/queue-partial - Nur die Queue-Liste für HTMX auto-refresh

    Returns dict with: downloads, page, limit, total, total_pages, has_next, has_previous,
    active_count, queue_count, failed_count, completed_today
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel

    # Calculate offset
    offset = (page - 1) * limit

    # Fetch downloads with track info directly (bypassing repository for richer data)
    stmt = (
        select(DownloadModel)
        .options(
            joinedload(DownloadModel.track).joinedload(TrackModel.artist),
            joinedload(DownloadModel.track).joinedload(TrackModel.album),
        )
        .where(
            DownloadModel.status.in_(
                [
                    DownloadStatus.WAITING.value,
                    DownloadStatus.PENDING.value,
                    DownloadStatus.QUEUED.value,
                    DownloadStatus.DOWNLOADING.value,
                    DownloadStatus.COMPLETED.value,
                    DownloadStatus.FAILED.value,
                ]
            )
        )
        .order_by(
            DownloadModel.priority.desc(),
            DownloadModel.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    download_models = result.unique().scalars().all()

    total_count = await download_repository.count_active()

    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    has_next = page < total_pages
    has_previous = page > 1

    # Fetch stats for the cards at the top
    active_count = await download_repository.count_by_status(
        DownloadStatus.DOWNLOADING.value
    )
    queue_count = (
        await download_repository.count_by_status(DownloadStatus.QUEUED.value)
        + await download_repository.count_by_status(DownloadStatus.PENDING.value)
        + await download_repository.count_by_status(DownloadStatus.WAITING.value)
    )
    failed_count = await download_repository.count_by_status(DownloadStatus.FAILED.value)
    completed_count = await download_repository.count_by_status(
        DownloadStatus.COMPLETED.value
    )

    # Convert to template-friendly format with track info
    downloads_data = []
    for dl in download_models:
        track = dl.track
        downloads_data.append({
            "id": dl.id,
            "track_id": dl.track_id,
            "status": dl.status,
            "priority": dl.priority,
            "progress_percent": dl.progress_percent or 0,
            "error_message": dl.error_message,
            "started_at": dl.started_at.isoformat() if dl.started_at else None,
            "created_at": dl.created_at.isoformat() if dl.created_at else None,
            # Track info for display
            "title": track.title if track else f"Track {dl.track_id[:8]}",
            "artist": track.artist.name if track and track.artist else "Unknown Artist",
            "album": track.album.title if track and track.album else "Unknown Album",
            "album_art": track.album.cover_url if track and track.album else None,
            # Hey future me - album_art_path enables get_display_url() local cache
            "album_art_path": track.album.cover_path if track and track.album else None,
        })

    return {
        "downloads": downloads_data,
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "active_count": active_count,
        "queue_count": queue_count,
        "failed_count": failed_count,
        "completed_today": completed_count,
    }


@router.get("/downloads", response_class=HTMLResponse)
async def downloads(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500, description="Items per page"),
    download_repository: DownloadRepository = Depends(get_download_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Downloads page with pagination - full page with header, stats, tabs.

    Args:
        request: FastAPI request
        page: Page number (1-indexed)
        limit: Items per page (default 100, max 500)
        download_repository: Download repository
        session: DB session for direct queries
    """
    data = await _get_downloads_data(download_repository, session, page, limit)

    return templates.TemplateResponse(
        request,
        "downloads.html",
        context=data,
    )


@router.get("/downloads/queue-partial", response_class=HTMLResponse)
async def downloads_queue_partial(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500, description="Items per page"),
    download_repository: DownloadRepository = Depends(get_download_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Downloads queue partial - ONLY the queue list for HTMX auto-refresh.

    Hey future me - dieser Endpoint gibt NUR die Queue-Liste zurück, nicht die ganze Seite!
    Das Template downloads_queue_partial.html rendert nur die Items ohne Header/Stats/Tabs.
    Das löst das Duplikations-Problem beim Auto-Refresh.
    """
    data = await _get_downloads_data(download_repository, session, page, limit)

    return templates.TemplateResponse(
        request,
        "downloads_queue_partial.html",
        context=data,
    )


# Static template pages - no logic, just render HTML. These are lightweight routes.
@router.get("/auth", response_class=HTMLResponse)
async def auth(request: Request) -> Any:
    """Auth page."""
    return templates.TemplateResponse(request, "auth.html")


# Hey future me - this is the Download Manager page showing unified download status!
# It aggregates downloads from slskd (and future providers like SABnzbd) into one view.
# The page uses HTMX auto-refresh to poll /api/downloads/manager/htmx/* endpoints.
@router.get("/download-manager", response_class=HTMLResponse)
async def download_manager_page(request: Request) -> Any:
    """Download Manager page - unified view of all provider downloads."""
    return templates.TemplateResponse(request, "download_manager.html")


# Hey future me - this is the UI styleguide page showing all components! Use it to verify the
# design system (colors, buttons, cards, badges, etc.) is working. Doesn't hit DB, pure template.
# Good for debugging CSS issues or showing designers what's available in the component library.
@router.get("/styleguide", response_class=HTMLResponse)
async def styleguide(request: Request) -> Any:
    """UI Styleguide page showing all components and design tokens."""
    return templates.TemplateResponse(request, "styleguide.html")


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> Any:
    """Advanced search page."""
    return templates.TemplateResponse(request, "search.html")


# Hey future me - this is the HTMX quick-search endpoint for the header search bar! It returns a
# dropdown partial with local library results (tracks, artists, playlists). NOT Spotify search -
# that would be slow and require auth. The q param comes from input field via hx-get. We search
# library only if query is at least 2 chars to avoid noise. Results limited to 5 per type for
# quick display. The partial renders into #search-results dropdown in base.html header.
@router.get("/search/quick", response_class=HTMLResponse)
async def quick_search(
    request: Request,
    q: str = "",
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Quick search partial for header search bar.

    Searches local library (tracks, artists, playlists) and returns
    HTML partial for HTMX dropdown. Minimum query length is 2 characters.

    Args:
        request: FastAPI request
        q: Search query string
        session: Database session

    Returns:
        HTML partial with search results dropdown
    """
    from sqlalchemy import or_, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import (
        ArtistModel,
        PlaylistModel,
        TrackModel,
    )

    results: list[dict[str, Any]] = []
    query = q.strip()

    if len(query) >= 2:
        search_term = f"%{query}%"

        # Search tracks (title or artist name)
        stmt = (
            select(TrackModel)
            .join(TrackModel.artist)
            .options(joinedload(TrackModel.artist))
            .where(
                or_(
                    TrackModel.title.ilike(search_term),
                    ArtistModel.name.ilike(search_term)
                )
            )
            .limit(5)
        )
        result = await session.execute(stmt)
        tracks = result.scalars().all()

        for track in tracks:
            results.append({
                "type": "track",
                "name": track.title,
                "subtitle": track.artist.name if track.artist else "Unknown Artist",
                "url": f"/library/tracks/{track.id}",
            })

        # Search playlists by name
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.name.ilike(search_term))
            .limit(5)
        )
        result = await session.execute(stmt)
        playlists = result.scalars().all()

        for playlist in playlists:
            results.append({
                "type": "playlist",
                "name": playlist.name,
                "subtitle": "Playlist",
                "url": f"/playlists/{playlist.id}",
            })

        # Sort: exact matches first, then by type (playlist > track)
        type_order = {"playlist": 0, "artist": 1, "album": 2, "track": 3}
        results.sort(
            key=lambda x: (
                0 if x["name"].lower() == query.lower() else 1,
                type_order.get(x["type"], 99),
            )
        )

    return templates.TemplateResponse(
        request,
        "partials/quick_search_results.html",
        context={"query": query, "results": results},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> Any:
    """Settings configuration page."""
    return templates.TemplateResponse(request, "settings.html")


@router.get("/settings/quality-profiles", response_class=HTMLResponse)
async def quality_profiles_page(request: Request) -> Any:
    """Quality profiles management page.

    Hey future me - this page lets users manage download quality preferences!
    - List all profiles (builtin + custom)
    - Create/edit/delete custom profiles
    - Set active profile for downloads
    """
    return templates.TemplateResponse(request, "quality_profiles.html")


@router.get("/settings/blocklist", response_class=HTMLResponse)
async def blocklist_page(request: Request) -> Any:
    """Blocklist management page.

    Hey future me - this page shows blocked Soulseek sources!
    - Auto-blocks from failed downloads
    - Manual blocks for known bad sources
    - Clear expired blocks
    """
    return templates.TemplateResponse(request, "blocklist.html")


# Alias for /dashboard - redirects to main page (/) for backwards compatibility
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Any:  # noqa: ARG001
    """Dashboard alias - redirects to main page."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/", status_code=302)


# This is the first-run wizard for new users! Shows "connect Spotify" flow and basic setup. Should
# only show once per user but we don't track "has completed onboarding" flag yet. Future: add user
# preferences table to track onboarding state and skip redirect to this page if already done.
@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request) -> Any:
    """First-run onboarding page for new users."""
    return templates.TemplateResponse(request, "onboarding.html")


# Yo, this is the library overview page with aggregated stats!
# IMPORTANT: Shows ONLY local files (tracks with file_path)!
# Uses efficient SQL COUNT queries instead of loading all data into memory.
# Merged with library_import.html for a single unified view!
@router.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    track_repository: TrackRepository = Depends(get_track_repository),  # noqa: ARG001
    session: AsyncSession = Depends(get_db_session),
    scanner: LibraryScannerService = Depends(get_library_scanner_service),
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """Library browser page - shows stats, scan controls, and management."""
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        TrackModel,
    )

    # Hey future me - After Unified Library (2025-12), we count ALL entities in DB!
    # Artists/Albums/Tracks show TOTAL count, "Local Files" shows tracks with file_path.

    # Count ALL tracks in DB (not just with file_path)
    total_tracks_stmt = select(func.count(TrackModel.id))
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count tracks WITH local files (for "Verfügbar" stat)
    tracks_with_files_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    tracks_with_files_result = await session.execute(tracks_with_files_stmt)
    tracks_with_files = tracks_with_files_result.scalar() or 0

    # Count ALL artists in DB (not filtered by file_path anymore!)
    artists_stmt = select(func.count(ArtistModel.id))
    artists_result = await session.execute(artists_stmt)
    total_artists = artists_result.scalar() or 0

    # Count ALL albums in DB (not filtered by file_path anymore!)
    albums_stmt = select(func.count(AlbumModel.id))
    albums_result = await session.execute(albums_stmt)
    total_albums = albums_result.scalar() or 0

    # Count broken tracks (local files that are broken)
    broken_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None),
        TrackModel.is_broken == True,  # noqa: E712
    )
    broken_result = await session.execute(broken_stmt)
    broken_tracks = broken_result.scalar() or 0

    # Get music path from scanner summary
    summary = await scanner.get_scan_summary()

    # Check for active scan job
    active_job = None
    jobs = await job_queue.list_jobs(job_type=JobType.LIBRARY_SCAN, limit=1)
    if jobs and jobs[0].status in (JobStatus.PENDING, JobStatus.RUNNING):
        job = jobs[0]
        active_job = {
            "job_id": job.id,
            "status": job.status.value,
            "progress": job.result.get("progress", 0) if job.result else 0,
            "stats": job.result.get("stats") if job.result else None,
        }

    stats = {
        "total_tracks": total_tracks,  # ALL tracks in DB
        "total_artists": total_artists,  # ALL artists in DB
        "total_albums": total_albums,  # ALL albums in DB
        "tracks_with_files": tracks_with_files,  # Tracks with local file_path
        "broken_tracks": broken_tracks,
        "music_path": summary.get("music_path", "/music"),
    }

    return templates.TemplateResponse(
        request,
        "library.html",
        context={"stats": stats, "active_job": active_job},
    )


# =============================================================================
# LIBRARY IMPORT UI ROUTES
# =============================================================================


@router.get("/library/stats-partial", response_class=HTMLResponse)
async def library_stats_partial(
    _request: Request,  # noqa: ARG001
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """HTMX partial: Returns updated stats HTML for library overview.

    Hey future me - this endpoint returns the stats cards HTML for refresh!
    Used by HTMX to update stats without full page reload after scans.
    NOW uses StatsService! Clean Architecture.
    """
    from sqlalchemy import func, select

    from soulspot.application.services.stats_service import StatsService
    from soulspot.infrastructure.persistence.models import TrackModel

    stats_service = StatsService(session)

    # Basic counts via StatsService
    total_tracks = await stats_service.get_total_tracks()
    total_artists = await stats_service.get_total_artists()
    total_albums = await stats_service.get_total_albums()

    # Tracks with local files (custom query - not in StatsService yet)
    tracks_with_files = (
        await session.execute(
            select(func.count(TrackModel.id)).where(TrackModel.file_path.isnot(None))
        )
    ).scalar() or 0

    # Broken tracks (custom query - not in StatsService yet)
    broken_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None),
        TrackModel.is_broken == True,  # noqa: E712
    )
    broken_tracks = (await session.execute(broken_stmt)).scalar() or 0

    # Return stats HTML with updated values
    return HTMLResponse(f"""
    <div class="stat-card stat-card-animated" style="--delay: 0;">
        <div class="stat-icon stat-icon-artists"><i class="bi bi-person"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_artists:,}</span>
            <span class="stat-label">Artists</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 1;">
        <div class="stat-icon stat-icon-albums"><i class="bi bi-disc"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_albums:,}</span>
            <span class="stat-label">Albums</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 2;">
        <div class="stat-icon stat-icon-tracks"><i class="bi bi-music-note"></i></div>
        <div class="stat-content">
            <span class="stat-value">{total_tracks:,}</span>
            <span class="stat-label">Tracks</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 3;">
        <div class="stat-icon stat-icon-files"><i class="bi bi-file-earmark-music"></i></div>
        <div class="stat-content">
            <span class="stat-value">{tracks_with_files:,}</span>
            <span class="stat-label">Verfügbar</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    <div class="stat-card stat-card-animated" style="--delay: 4;">
        <div class="stat-icon stat-icon-broken"><i class="bi bi-exclamation-triangle"></i></div>
        <div class="stat-content">
            <span class="stat-value">{broken_tracks:,}</span>
            <span class="stat-label">Broken</span>
        </div>
        <div class="stat-shine"></div>
    </div>
    """)


@router.get("/library/import", response_class=HTMLResponse)
async def library_import_page(request: Request) -> Any:  # noqa: ARG001
    """Redirect to unified library page (merged with import)."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/library", status_code=302)


@router.get("/library/import/jobs-list", response_class=HTMLResponse)
async def library_import_jobs_list(
    _request: Request,  # noqa: ARG001
    job_queue: JobQueue = Depends(get_job_queue),
) -> Any:
    """HTMX partial: Recent import jobs list with beautiful styling."""
    jobs = await job_queue.list_jobs(job_type=JobType.LIBRARY_SCAN, limit=10)

    jobs_data: list[dict[str, Any]] = [
        {
            "job_id": job.id,
            "status": job.status.value,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "stats": job.result
            if isinstance(job.result, dict) and "progress" not in job.result
            else None,
        }
        for job in jobs
    ]

    # Return empty state with nice styling
    if not jobs_data:
        return HTMLResponse(
            """<div class="empty-scans">
                <i class="bi bi-inbox"></i>
                <p>No recent scans found</p>
                <p style="font-size: 0.85rem;">Start a scan to see your import history here</p>
            </div>"""
        )

    # Build beautiful table HTML
    html = """<table class="recent-scans-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Files</th>
                <th>Imported</th>
                <th>Errors</th>
            </tr>
        </thead>
        <tbody>"""

    for job in jobs_data:
        # Format date nicely
        date_str = job["created_at"].strftime("%b %d, %Y")
        time_str = job["created_at"].strftime("%H:%M")

        # Status badge styling
        status = job["status"]
        status_config = {
            "completed": ("check-circle-fill", "completed", "Completed"),
            "failed": ("x-circle-fill", "failed", "Failed"),
            "running": ("arrow-repeat", "running", "Running"),
            "pending": ("hourglass", "pending", "Pending"),
        }.get(status, ("question-circle", "pending", status.title()))

        icon, badge_class, label = status_config

        # Stats
        stats = job["stats"] or {}
        scanned = stats.get("scanned", "-")
        imported = stats.get("imported", "-")
        errors = stats.get("errors", 0)

        # Format numbers with locale
        if isinstance(scanned, int):
            scanned = f"{scanned:,}"
        if isinstance(imported, int):
            imported = f"{imported:,}"
        if isinstance(errors, int):
            errors_display = f"{errors:,}"
            errors_class = "has-errors" if errors > 0 else ""
        else:
            errors_display = str(errors)
            errors_class = ""

        html += f"""
            <tr>
                <td>
                    <div class="scan-date">
                        <span class="scan-date-main">{date_str}</span>
                        <span class="scan-date-time">{time_str}</span>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-badge-{badge_class}">
                        <i class="bi bi-{icon}"></i>
                        {label}
                    </span>
                </td>
                <td class="stat-cell">{scanned}</td>
                <td class="stat-cell stat-cell-imported">{imported}</td>
                <td class="stat-cell stat-cell-errors {errors_class}">{errors_display}</td>
            </tr>"""

    html += "</tbody></table>"
    return HTMLResponse(html)


# Hey future me – refactored to load ArtistModel directly with album/track counts!
# Now includes image_url from Spotify CDN. SQL does aggregation via subqueries instead
# of loading all tracks into Python memory. Uses pagination (page/per_page params) for
# big libraries - defaults to 50 per page. image_url comes from Spotify sync – falls back
# to None if artist wasn't synced.
# UNIFIED LIBRARY (2025-12): Shows ALL artists in DB, not filtered by file_path!
# Hey future me - this now checks for unenriched artists and passes enrichment_needed flag!
@router.get("/library/artists", response_class=HTMLResponse)
async def library_artists(
    request: Request,
    source: str | None = None,  # Filter by source (local/spotify/hybrid/all)
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Unified artists browser page - shows LOCAL + SPOTIFY + HYBRID artists.

    Hey future me - This is now the UNIFIED Music Manager artist view!
    It shows ALL artists regardless of source (local file scan OR Spotify followed).
    NO PAGINATION - shows all artists on one page (pagination only for download queue).

    Filter by source param:
    - ?source=local -> Only artists from local file scans (with or without Spotify)
    - ?source=spotify -> Only artists followed on Spotify (with or without local files)
    - ?source=hybrid -> Only artists that exist in BOTH local + Spotify
    - ?source=all OR no param -> Show ALL artists (default unified view)
    """
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        TrackModel,
    )

    # Subquery for total track count per artist (ALL tracks including Spotify-only)
    # Hey future me - After Table Consolidation (2025-12), we show ALL tracks now!
    # We also count how many are local (have file_path) for the "X/Y local" badge.
    total_track_count_subq = (
        select(TrackModel.artist_id, func.count(TrackModel.id).label("total_tracks"))
        .group_by(TrackModel.artist_id)
        .subquery()
    )

    # Subquery for LOCAL track count per artist (tracks with file_path)
    local_track_count_subq = (
        select(TrackModel.artist_id, func.count(TrackModel.id).label("local_tracks"))
        .where(TrackModel.file_path.isnot(None))
        .group_by(TrackModel.artist_id)
        .subquery()
    )

    # Subquery for total album count per artist (ALL albums)
    total_album_count_subq = (
        select(AlbumModel.artist_id, func.count(AlbumModel.id).label("total_albums"))
        .group_by(AlbumModel.artist_id)
        .subquery()
    )

    # Subquery for LOCAL album count (albums with at least one local track)
    albums_with_files_subq = (
        select(func.distinct(TrackModel.album_id))
        .where(TrackModel.file_path.isnot(None))
        .where(TrackModel.album_id.isnot(None))
        .subquery()
    )
    local_album_count_subq = (
        select(AlbumModel.artist_id, func.count(AlbumModel.id).label("local_albums"))
        .where(AlbumModel.id.in_(select(albums_with_files_subq)))
        .group_by(AlbumModel.artist_id)
        .subquery()
    )

    # Main query - SHOW ALL ARTISTS (unified view)
    # Hey future me - After Table Consolidation (2025-12), we show BOTH local AND total counts!
    # This allows "X/Y" badges like "3/5 local" meaning 3 of 5 tracks have local files.
    stmt = (
        select(
            ArtistModel,
            total_track_count_subq.c.total_tracks,
            local_track_count_subq.c.local_tracks,
            total_album_count_subq.c.total_albums,
            local_album_count_subq.c.local_albums,
        )
        .outerjoin(total_track_count_subq, ArtistModel.id == total_track_count_subq.c.artist_id)
        .outerjoin(local_track_count_subq, ArtistModel.id == local_track_count_subq.c.artist_id)
        .outerjoin(total_album_count_subq, ArtistModel.id == total_album_count_subq.c.artist_id)
        .outerjoin(local_album_count_subq, ArtistModel.id == local_album_count_subq.c.artist_id)
    )

    # Exclude Various Artists patterns from artist view
    # Hey future me - VA/Compilations have their own section, don't clutter artist list!
    from soulspot.domain.value_objects.album_types import VARIOUS_ARTISTS_PATTERNS

    stmt = stmt.where(
        ~func.lower(ArtistModel.name).in_(list(VARIOUS_ARTISTS_PATTERNS))
    )

    # Apply source filter if requested
    if source == "local":
        # Only artists with local files (source='local' OR 'hybrid')
        stmt = stmt.where(ArtistModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        # Only Spotify followed artists (source='spotify' OR 'hybrid')
        stmt = stmt.where(ArtistModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        # Only artists in BOTH sources
        stmt = stmt.where(ArtistModel.source == "hybrid")
    # else: source == "all" or None -> Show ALL artists (no filter)

    # Get total count for display (no pagination, so just count)
    # Also exclude VA patterns from count
    count_stmt = select(func.count(ArtistModel.id)).where(
        ~func.lower(ArtistModel.name).in_(list(VARIOUS_ARTISTS_PATTERNS))
    )
    if source == "local":
        count_stmt = count_stmt.where(ArtistModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        count_stmt = count_stmt.where(ArtistModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        count_stmt = count_stmt.where(ArtistModel.source == "hybrid")
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar() or 0

    # NO PAGINATION - load all artists, just order alphabetically
    # Hey future me - removed pagination (2025-12), all artists shown on one page!

    # Apply ordering only (no pagination)
    stmt = stmt.order_by(ArtistModel.name)
    result = await session.execute(stmt)
    rows = result.all()

    # Convert to template-friendly format with image_url + source
    # Hey future me - name is CLEAN (no disambiguation), disambiguation is stored separately!
    # After Dec 2025 folder parsing fixes, new scans store clean names. Old entries might
    # still have disambiguation in name - re-scan library to fix.
    # NEW (2025-12): Shows BOTH total AND local counts for "X/Y local" badges!
    artists = [
        {
            "name": artist.name,
            "disambiguation": artist.disambiguation,  # Text like "English rock band"
            "source": artist.source,  # 'local', 'spotify', or 'hybrid'
            "total_tracks": total_tracks or 0,  # ALL tracks (incl. Spotify-only)
            "local_tracks": local_tracks or 0,  # Only tracks with file_path
            "total_albums": total_albums or 0,  # ALL albums
            "local_albums": local_albums or 0,  # Only albums with local tracks
            "image_url": artist.image_url,  # Spotify CDN URL or None
            "image_path": artist.image_path,  # Local cached image path or None
            "genres": artist.genres,  # JSON list of genres (from Spotify)
        }
        for artist, total_tracks, local_tracks, total_albums, local_albums in rows
    ]

    # Check for missing artwork (artists + albums)
    # Hey future me - the enrichment button fetches BOTH artist images and album covers.
    artists_without_image = sum(1 for a in artists if not a["image_url"])

    has_local_album_tracks = (
        select(TrackModel.id)
        .where(TrackModel.album_id == AlbumModel.id)
        .where(TrackModel.file_path.isnot(None))
        .exists()
    )
    albums_without_cover_stmt = (
        select(func.count(AlbumModel.id))
        .where(has_local_album_tracks)
        .where((AlbumModel.cover_url.is_(None)) | (AlbumModel.cover_url == ""))
    )
    albums_without_cover_result = await session.execute(albums_without_cover_stmt)
    albums_without_cover = albums_without_cover_result.scalar() or 0

    enrichment_needed = (artists_without_image + albums_without_cover) > 0

    # Count ALL artists by source for filter badges (not just current page!)
    # Hey future me - these counts come from DB, not from current page data
    count_all = await session.execute(select(func.count(ArtistModel.id)))
    count_local = await session.execute(
        select(func.count(ArtistModel.id)).where(
            ArtistModel.source.in_(["local", "hybrid"])
        )
    )
    count_spotify = await session.execute(
        select(func.count(ArtistModel.id)).where(
            ArtistModel.source.in_(["spotify", "hybrid"])
        )
    )
    count_hybrid = await session.execute(
        select(func.count(ArtistModel.id)).where(ArtistModel.source == "hybrid")
    )
    source_counts = {
        "all": count_all.scalar() or 0,
        "local": count_local.scalar() or 0,
        "spotify": count_spotify.scalar() or 0,
        "hybrid": count_hybrid.scalar() or 0,
    }

    return templates.TemplateResponse(
        request,
        "library_artists.html",
        context={
            "artists": artists,
            "enrichment_needed": enrichment_needed,
            "artists_without_image": artists_without_image,
            "albums_without_cover": albums_without_cover,
            "current_source": source or "all",  # Active filter
            "source_counts": source_counts,  # For filter badge counts
            "total_count": total_count,  # Total artists shown
        },
    )


# Hey future me – refactored to load AlbumModel directly with artist join!
# This gives us access to artwork_url from Spotify CDN. SQL does the grouping via
# relationship, not manual Python dict. Uses pagination (page/per_page params) for
# big libraries - defaults to 50 per page. artwork_url comes from Spotify sync – if
# album wasn't synced, falls back to None.
# UNIFIED LIBRARY (2025-12): Shows ALL albums in DB, not filtered by file_path!
# Also handles "Various Artists" compilations properly via album_artist field.
# NO PAGINATION - all albums shown on one page!
@router.get("/library/albums", response_class=HTMLResponse)
async def library_albums(
    request: Request,
    source: str | None = None,  # Filter by source (local/spotify/hybrid/all)
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Unified library albums browser page - shows ALL albums with local/total counts.

    Hey future me - After Table Consolidation (2025-12), shows ALL albums!
    NO PAGINATION - all albums on one page (pagination only for download queue).
    Filter by source param like /library/artists.
    Shows "X/Y local" badge (e.g. "3/10 tracks" = 3 verfügbar, 10 total).
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import AlbumModel, TrackModel

    # Subquery for total track count per album (ALL tracks)
    total_track_count_subq = (
        select(TrackModel.album_id, func.count(TrackModel.id).label("total_tracks"))
        .group_by(TrackModel.album_id)
        .subquery()
    )

    # Subquery for local track count per album (tracks with file_path)
    local_track_count_subq = (
        select(TrackModel.album_id, func.count(TrackModel.id).label("local_tracks"))
        .where(TrackModel.file_path.isnot(None))
        .group_by(TrackModel.album_id)
        .subquery()
    )

    # Build main query
    stmt = (
        select(
            AlbumModel,
            total_track_count_subq.c.total_tracks,
            local_track_count_subq.c.local_tracks,
        )
        .outerjoin(total_track_count_subq, AlbumModel.id == total_track_count_subq.c.album_id)
        .outerjoin(local_track_count_subq, AlbumModel.id == local_track_count_subq.c.album_id)
        .options(joinedload(AlbumModel.artist))
    )

    # Apply source filter
    if source == "local":
        stmt = stmt.where(AlbumModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        stmt = stmt.where(AlbumModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        stmt = stmt.where(AlbumModel.source == "hybrid")
    # else: show all

    # Get total count for display
    count_stmt = select(func.count(AlbumModel.id))
    if source == "local":
        count_stmt = count_stmt.where(AlbumModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        count_stmt = count_stmt.where(AlbumModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        count_stmt = count_stmt.where(AlbumModel.source == "hybrid")
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar() or 0

    # NO PAGINATION - load all albums, just order alphabetically
    # Hey future me - removed pagination (2025-12), all albums shown on one page!
    stmt = stmt.order_by(AlbumModel.title)
    result = await session.execute(stmt)
    rows = result.unique().all()

    # Convert to template-friendly format with artwork_url
    # Hey future me - album_artist overrides artist.name for compilations/Various Artists!
    # artwork_path is local file, artwork_url is Spotify CDN - template prefers local
    # NEW (2025-12): Shows BOTH total AND local track counts for "X/Y local" badge!
    albums = [
        {
            "title": album.title,
            "artist": album.album_artist
            or (album.artist.name if album.artist else "Unknown Artist"),
            "source": album.source,  # 'local', 'spotify', or 'hybrid'
            "total_tracks": total_tracks or 0,  # ALL tracks
            "local_tracks": local_tracks or 0,  # Only tracks with file_path
            "year": album.release_year,
            "artwork_url": album.cover_url,  # Spotify CDN URL or None
            "artwork_path": album.cover_path,  # Local file path or None
            "is_compilation": "compilation" in (album.secondary_types or []),
            "primary_type": album.primary_type or "album",
            "secondary_types": album.secondary_types or [],
        }
        for album, total_tracks, local_tracks in rows
    ]

    # Count albums by source for filter badges
    count_all = await session.execute(select(func.count(AlbumModel.id)))
    count_local = await session.execute(
        select(func.count(AlbumModel.id)).where(AlbumModel.source.in_(["local", "hybrid"]))
    )
    count_spotify = await session.execute(
        select(func.count(AlbumModel.id)).where(AlbumModel.source.in_(["spotify", "hybrid"]))
    )
    count_hybrid = await session.execute(
        select(func.count(AlbumModel.id)).where(AlbumModel.source == "hybrid")
    )
    source_counts = {
        "all": count_all.scalar() or 0,
        "local": count_local.scalar() or 0,
        "spotify": count_spotify.scalar() or 0,
        "hybrid": count_hybrid.scalar() or 0,
    }

    return templates.TemplateResponse(
        request,
        "library_albums.html",
        context={
            "albums": albums,
            "current_source": source or "all",
            "source_counts": source_counts,
            "total_count": total_count,  # Total albums shown
        },
    )


# Hey future me - Compilations browser page! Shows only albums that are compilations.
# Compilations are albums where secondary_types contains "compilation".
# These are typically "Various Artists" albums with mixed artists.
# The UI groups them separately from regular artist albums for better organization.
# This replaces the need to browse "Various Artists" as an artist - more intuitive!
@router.get("/library/compilations", response_class=HTMLResponse)
async def library_compilations(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Library compilations browser page - only compilation albums with local files."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import AlbumModel, TrackModel

    # Subquery for track count - ONLY count tracks with local files
    track_count_subq = (
        select(TrackModel.album_id, func.count(TrackModel.id).label("track_count"))
        .where(TrackModel.file_path.isnot(None))
        .group_by(TrackModel.album_id)
        .subquery()
    )

    # Only get compilation albums that have at least one local track
    # SQLite JSON containment check: secondary_types LIKE '%"compilation"%'
    stmt = (
        select(AlbumModel, track_count_subq.c.track_count)
        .join(track_count_subq, AlbumModel.id == track_count_subq.c.album_id)
        .where(track_count_subq.c.track_count > 0)
        .where(AlbumModel.secondary_types.contains(["compilation"]))
        .options(joinedload(AlbumModel.artist))
        .order_by(AlbumModel.title)
    )
    result = await session.execute(stmt)
    rows = result.unique().all()

    # Convert to template-friendly format
    # For compilations, album_artist is more relevant than artist (often "Various Artists")
    compilations = [
        {
            "id": album.id,
            "title": album.title,
            "album_artist": album.album_artist or "Various Artists",
            "artist": album.artist.name if album.artist else "Unknown Artist",
            "track_count": track_count or 0,
            "year": album.release_year,
            "artwork_url": album.cover_url,
            "artwork_path": album.cover_path,
            "primary_type": album.primary_type,
            "secondary_types": album.secondary_types or [],
        }
        for album, track_count in rows
    ]

    # Sort alphabetically by title
    compilations.sort(key=lambda x: x["title"].lower())

    return templates.TemplateResponse(
        request,
        "library_compilations.html",
        context={"compilations": compilations, "total_count": len(compilations)},
    )


# IMPORTANT: Library tracks page with SQLAlchemy direct queries! Uses Depends(get_db_session) to
# properly manage DB session lifecycle. select() with joinedload() is proper way to eagerly load
# relationships and avoid N+1. unique() on result prevents duplicate Track objects when joins create
# multiple rows. Uses pagination (page/per_page params) for big libraries - defaults to 100 per page.
# The track data extraction handles None values gracefully with "Unknown". Sort by artist/album/title
# is done in SQL ORDER BY for efficiency. Good use of joinedload to prevent N+1 queries.
# IMPORTANT: Only shows tracks with local files (file_path IS NOT NULL)!
@router.get("/library/tracks", response_class=HTMLResponse)
async def library_tracks(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(100, ge=10, le=500, description="Items per page"),
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Library tracks browser page - only tracks with local files."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import (
        ArtistModel,
        TrackModel,
    )

    # Get total count of tracks with local files (for pagination)
    count_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    # Query with joined loads for artist and album - ONLY tracks with local files!
    # Sort in SQL for efficiency (not in Python memory)
    stmt = (
        select(TrackModel)
        .where(TrackModel.file_path.isnot(None))
        .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        .join(TrackModel.artist, isouter=True)
        .join(TrackModel.album, isouter=True)
        .order_by(
            func.lower(func.coalesce(ArtistModel.name, "zzz")),  # Artists first, null last
            func.lower(func.coalesce(TrackModel.title, "")),
        )
        .offset(offset)
        .limit(per_page)
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

    return templates.TemplateResponse(
        request,
        "library_tracks.html",
        context={
            "tracks": tracks_data,
            # Pagination context
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
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
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Artist detail page with albums and tracks.

    Hey future me - UNIFIED Music Manager view!
    Shows ALL albums for this artist (LOCAL + SPOTIFY):
    - Albums with local files -> Show tracks
    - Spotify albums (no local files yet) -> Show album card with download button

    This works for all source types:
    - LOCAL artists -> Show albums from file scans
    - SPOTIFY artists -> Show albums from Spotify API sync
    - HYBRID artists -> Show ALL albums (merged)
    """
    from urllib.parse import unquote

    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
        TrackModel,
    )

    artist_name = unquote(artist_name)

    # Step 1: Get artist by name (case-insensitive)
    artist_stmt = select(ArtistModel).where(func.lower(ArtistModel.name) == artist_name.lower())
    artist_result = await session.execute(artist_stmt)
    artist_model = artist_result.scalar_one_or_none()

    if not artist_model:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 404,
                "error_message": f"Artist '{artist_name}' not found",
            },
            status_code=404,
        )

    # Step 2: Get ALL albums for this artist (including Spotify albums without local files)
    albums_stmt = (
        select(AlbumModel)
        .where(AlbumModel.artist_id == artist_model.id)
        .order_by(AlbumModel.release_year.desc().nullslast(), AlbumModel.title)
    )
    albums_result = await session.execute(albums_stmt)
    album_models = albums_result.scalars().all()

    # Hey future me - AUTO-SYNC albums using MULTI-SERVICE PATTERN!
    # If artist has NO albums in DB, fetch from available services:
    # 1. Try Spotify (if authenticated + artist has spotify_uri)
    # 2. Fallback to Deezer (NO AUTH NEEDED - public API)
    #
    # This enables album browsing EVEN WITHOUT Spotify login!
    # Deezer can fetch albums by artist name for any artist.
    if not album_models:
        try:
            # MULTI-SERVICE PATTERN: Try available services
            from soulspot.application.services.followed_artists_service import (
                FollowedArtistsService,
            )
            from soulspot.application.services.token_manager import (
                DatabaseTokenManager,
            )
            from soulspot.config import get_settings
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
            from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

            # 1. Try to get Spotify token (optional - service works without it)
            spotify_plugin = None
            access_token = None
            if hasattr(request.app.state, "db_token_manager"):
                db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
                access_token = await db_token_manager.get_token_for_background()

            if access_token:
                app_settings = get_settings()
                spotify_client = SpotifyClient(app_settings.spotify)
                spotify_plugin = SpotifyPlugin(client=spotify_client, access_token=access_token)
                logger.debug(f"Spotify plugin available for album sync of {artist_model.name}")
            else:
                logger.debug(f"No Spotify token - using Deezer only for {artist_model.name}")

            # 2. Deezer is ALWAYS available (no auth needed!)
            deezer_plugin = DeezerPlugin()

            # 3. Create service with available plugins (spotify_plugin can be None!)
            followed_service = FollowedArtistsService(
                session,
                spotify_plugin=spotify_plugin,  # May be None - service handles this
                deezer_plugin=deezer_plugin,    # Always available
            )

            # Sync albums using available services
            # Service will try Spotify if available, fall back to Deezer
            await followed_service.sync_artist_albums(artist_model.id)
            await session.commit()  # Commit new albums

            # Re-query albums after sync
            albums_result = await session.execute(albums_stmt)
            album_models = albums_result.scalars().all()
        except Exception as e:
            # Log with structured message
            from soulspot.infrastructure.observability.log_messages import LogMessages
            logger.warning(
                LogMessages.sync_failed(
                    entity="Albums",
                    source="deezer/spotify",
                    error=str(e),
                    hint=f"Artist: {artist_model.name}"
                )
            )
            # Continue anyway - show empty albums list

    # Step 3: Get tracks for these albums (for LOCAL/HYBRID artists)
    tracks_stmt = (
        select(TrackModel)
        .where(TrackModel.artist_id == artist_model.id)
        .options(joinedload(TrackModel.album))
    )
    tracks_result = await session.execute(tracks_stmt)
    track_models = tracks_result.unique().scalars().all()

    # Build albums list with track counts
    albums_dict: dict[str, dict[str, Any]] = {}
    for album in album_models:
        album_key = album.title
        albums_dict[album_key] = {
            "id": f"{artist_name}::{album.title}",
            "title": album.title,
            "track_count": 0,  # Will be updated from tracks
            "year": album.release_year,
            "artwork_url": album.cover_url if hasattr(album, "cover_url") else None,
            "artwork_path": album.cover_path if hasattr(album, "cover_path") else None,
            "spotify_id": album.spotify_uri if hasattr(album, "spotify_uri") else None,
            "primary_type": album.primary_type if hasattr(album, "primary_type") else "album",
            "secondary_types": album.secondary_types if hasattr(album, "secondary_types") else [],
        }

    # Count tracks per album
    for track in track_models:
        if track.album:
            album_key = track.album.title
            if album_key in albums_dict:
                albums_dict[album_key]["track_count"] += 1

    # Convert to list (already sorted by SQL query)
    albums = list(albums_dict.values())

    # Convert tracks to template format
    tracks_data = [
        {
            "id": track.id,
            "title": track.title,
            "artist": artist_model.name,
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
        "id": str(artist_model.id),  # CRITICAL: Needed for /api/library/discovery/missing/{artist_id}
        "name": artist_model.name,
        "source": artist_model.source,  # NEW: Show source badge
        "disambiguation": artist_model.disambiguation,
        "albums": albums,
        "tracks": tracks_data,
        "track_count": len(tracks_data),
        "album_count": len(albums),
        "image_url": artist_model.image_url,  # Spotify CDN URL or None
        "image_path": artist_model.image_path,  # Local cached image path or None
        "genres": artist_model.genres,  # Spotify genres
    }

    return templates.TemplateResponse(
        request, "library_artist_detail.html", context={"artist": artist_data}
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
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Album detail page with track listing."""
    from urllib.parse import unquote

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import TrackModel

    album_key = unquote(album_key)

    # Split key into artist and album
    if "::" not in album_key:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 400,
                "error_message": "Invalid album key format",
            },
            status_code=400,
        )

    artist_name, album_title = album_key.split("::", 1)

    # Get album first to check if we need to sync tracks
    from soulspot.infrastructure.persistence.models import AlbumModel

    album_stmt = (
        select(AlbumModel)
        .join(AlbumModel.artist)
        .where(
            AlbumModel.artist.has(name=artist_name),
            AlbumModel.title == album_title,
        )
        .options(joinedload(AlbumModel.artist))
    )
    album_result = await session.execute(album_stmt)
    album_model = album_result.unique().scalar_one_or_none()

    if not album_model:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 404,
                "error_message": f"Album '{album_title}' by '{artist_name}' not found",
            },
            status_code=404,
        )

    # Query tracks for this album - include ALL tracks, not just those with file_path
    stmt = (
        select(TrackModel)
        .where(TrackModel.album_id == album_model.id)
        .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        .order_by(TrackModel.disc_number, TrackModel.track_number)
    )
    result = await session.execute(stmt)
    track_models = result.unique().scalars().all()

    # If no tracks found, show empty album with sync prompt instead of 404
    # (Album exists in DB but tracks not synced yet)
    if not track_models:
        # Return album page with empty tracks and sync prompt
        album_data = {
            "id": str(album_model.id),
            "title": album_title,
            "artist": artist_name,
            "artist_slug": artist_name,
            "tracks": [],
            "year": album_model.release_year if hasattr(album_model, "release_year") else None,
            "total_duration_ms": 0,
            "artwork_url": album_model.cover_url if hasattr(album_model, "cover_url") else None,
            "artwork_path": album_model.cover_path if hasattr(album_model, "cover_path") else None,
            "is_compilation": "compilation" in (album_model.secondary_types or []),
            "needs_sync": True,  # Flag to show "Sync required" message
            "source": album_model.source,
            "spotify_uri": album_model.spotify_uri,
        }
        return templates.TemplateResponse(
            request, "library_album_detail.html", context={"album": album_data}
        )

    # Convert tracks to template format
    tracks_data = [
        {
            "id": track.id,
            "title": track.title,
            "artist": track.artist.name if track.artist else "Unknown Artist",
            "album": track.album.title if track.album else "Unknown Album",
            "track_number": track.track_number,
            "disc_number": track.disc_number if hasattr(track, "disc_number") else 1,
            "duration_ms": track.duration_ms,
            "file_path": track.file_path,
            "is_broken": track.is_broken,
            "source": track.source,  # 'local', 'spotify', 'deezer', 'tidal', 'hybrid'
            # Extract provider IDs for download support
            "spotify_id": track.spotify_uri.split(":")[-1] if track.spotify_uri else None,
            "deezer_id": track.deezer_id,
            "tidal_id": track.tidal_id,
            "is_downloaded": bool(track.file_path),
        }
        for track in track_models
    ]

    # Sort by disc number, then track number, then title
    tracks_data.sort(key=lambda x: (x["disc_number"], x["track_number"] or 999, x["title"].lower()))  # type: ignore[union-attr]

    # Calculate total duration
    total_duration_ms = sum(t["duration_ms"] or 0 for t in tracks_data)  # type: ignore[misc]

    # Get year and artwork_url from first track's album
    year = (
        track_models[0].album.release_year
        if track_models
        and track_models[0].album
        and hasattr(track_models[0].album, "release_year")
        else None
    )

    # Hey future me – get cover_url from album model for Spotify CDN cover
    artwork_url = (
        track_models[0].album.cover_url
        if track_models
        and track_models[0].album
        and hasattr(track_models[0].album, "cover_url")
        else None
    )

    # Get local artwork path
    artwork_path = (
        track_models[0].album.cover_path
        if track_models
        and track_models[0].album
        and hasattr(track_models[0].album, "cover_path")
        else None
    )

    # Get album ID and is_compilation for compilation features
    album_id = (
        track_models[0].album.id if track_models and track_models[0].album else None
    )

    # Check if album is a compilation (secondary_types contains "compilation")
    is_compilation = False
    if track_models and track_models[0].album:
        secondary_types = getattr(track_models[0].album, "secondary_types", None) or []
        is_compilation = "compilation" in secondary_types

    album_data = {
        "id": album_id,  # Needed for API calls
        "title": album_title,
        "artist": artist_name,
        "artist_slug": artist_name,
        "tracks": tracks_data,
        "year": year,
        "total_duration_ms": total_duration_ms,
        "artwork_url": artwork_url,  # Spotify CDN URL or None
        "artwork_path": artwork_path,  # Local cached image path or None
        "is_compilation": is_compilation,  # For compilation badge and override UI
    }

    return templates.TemplateResponse(
        request, "library_album_detail.html", context={"album": album_data}
    )


# Yo, this returns an HTMX partial for the metadata editor modal! Uses Depends(get_db_session) to
# properly manage DB session lifecycle. Queries one track with joinedload for artist/album. Returns
# error.html partial for 404/400 instead of raising HTTPException - nice HTMX pattern. album_artist
# comes from AlbumModel if available, genre comes from TrackModel.genre (populated from audio file
# tags during library scan). year comes from album relationship if it exists. The track_data dict
# matches what the metadata_editor.html template expects. This is a modal fragment, not full page.
# Template should have form fields pre-filled with current values.
@router.get("/tracks/{track_id}/metadata-editor", response_class=HTMLResponse)
async def track_metadata_editor(
    request: Request,
    track_id: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Return metadata editor modal for a track."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        stmt = (
            select(TrackModel)
            .where(TrackModel.id == track_id)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        )
        result = await session.execute(stmt)
        track_model = result.unique().scalar_one_or_none()

        if not track_model:
            return templates.TemplateResponse(
                request,
                "error.html",
                context={
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
            "album_artist": track_model.album.album_artist if track_model.album else None,
            "genre": track_model.genre,
            "year": track_model.album.year
            if track_model.album and hasattr(track_model.album, "year")
            else None,
            "track_number": track_model.track_number,
            "disc_number": track_model.disc_number,
            "file_path": track_model.file_path,
        }

        return templates.TemplateResponse(
            request,
            "partials/metadata_editor.html",
            context={"track": track_data},
        )

    except ValueError:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 400,
                "error_message": "Invalid track ID",
            },
            status_code=400,
        )


# =============================================================================
# DUPLICATE REVIEW ROUTES
# =============================================================================
# Hey future me - these routes are for the duplicate detection feature!
# The DuplicateDetectorWorker runs periodically and populates duplicate_candidates table.
# This page shows those candidates and lets users resolve them (keep one, keep both, dismiss).
# API endpoints in library.py do the actual work, this just renders the UI.
# =============================================================================


@router.get("/library/duplicates", response_class=HTMLResponse)
async def library_duplicates_page(request: Request) -> Any:
    """Duplicate review page for resolving duplicate artists/albums.

    Shows detected duplicate artists and albums (same name, different DB entries).
    Users can merge duplicates or dismiss false positives.

    Detection groups entities by normalized name - if multiple DB entries share
    the same normalized name, they're shown as potential duplicates.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with duplicate review UI
    """
    # Initial stats will be loaded via HTMX from /api/library/duplicates/artists
    return templates.TemplateResponse(
        request,
        "library_duplicates.html",
        context={
            "stats": None,  # Loaded via HTMX
        },
    )


# Hey future me - this is the broken files review page! Shows tracks that have a file_path but the
# file is corrupted, unreadable, or missing on disk. Data loads via HTMX from /api/library/broken-files.
# Users can re-download individual broken files or bulk re-download all. The LibraryCleanupWorker
# detects these and marks them as is_broken=True. UI shows file path, error type, and re-download button.
@router.get("/library/broken-files", response_class=HTMLResponse)
async def library_broken_files_page(request: Request) -> Any:
    """Broken files review page for re-downloading corrupted tracks.

    Shows tracks where file exists in DB but is corrupted/unreadable on disk.
    Users can review broken files and trigger re-downloads.

    The LibraryCleanupWorker detects broken files during maintenance scans.
    Users can also trigger manual scans from settings.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with broken files review UI
    """
    # Stats and broken files list loaded via HTMX from /api/library/broken-files
    return templates.TemplateResponse(
        request,
        "broken_files.html",
        context={},
    )


# Hey future me - this shows albums with missing tracks! An album is "incomplete" when we have some
# tracks but not all (e.g., 8 of 12 tracks). Data loads via HTMX from /api/library/incomplete-albums.
# Shows album cover, title, artist, progress bar of completion, and "download missing" button.
# Useful for finding albums that need gap-filling. Filters let users set minimum track count threshold.
@router.get("/library/incomplete-albums", response_class=HTMLResponse)
async def library_incomplete_albums_page(request: Request) -> Any:
    """Incomplete albums review page for finding albums with missing tracks.

    Shows albums where we have some tracks but not all (partial downloads).
    Users can see completion percentage and download missing tracks.

    Useful for gap-filling albums that were partially downloaded or
    albums where some tracks failed to download.

    Args:
        request: FastAPI request object

    Returns:
        HTML page with incomplete albums review UI
    """
    # Album data loaded via HTMX from /api/library/incomplete-albums
    return templates.TemplateResponse(
        request,
        "incomplete_albums.html",
        context={},
    )


# =============================================================================
# SPOTIFY BROWSE ROUTES
# =============================================================================
# Hey future me - these routes are for browsing SPOTIFY data (followed artists, their albums,
# tracks). Data comes from spotify_* tables (separate from local library!). Auto-sync happens
# on page load with cooldown to avoid hammering Spotify API. No "Sync" button needed!
# The flow: /spotify/artists -> auto-sync -> show grid -> click artist -> /spotify/artists/{id}
# -> auto-sync albums -> show albums -> click album -> /spotify/artists/{a}/albums/{b} -> show tracks
# =============================================================================


@router.get("/spotify/artists", response_class=HTMLResponse)
async def spotify_artists_page(request: Request) -> Any:
    """DEPRECATED: Redirect to unified library artists view with Spotify filter.

    Hey future me - this Spotify-specific route is deprecated (Dec 2025)!
    Use /library/artists?source=spotify for multi-provider unified view.
    """
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/library/artists?source=spotify", status_code=301)


@router.get("/browse/new-releases", response_class=HTMLResponse)
async def browse_new_releases_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    days: int = Query(default=90, ge=7, le=365, description="Days to look back"),
    include_compilations: bool = Query(default=True, description="Include compilations"),
    include_singles: bool = Query(default=True, description="Include singles"),
    force_refresh: bool = Query(default=False, description="Force refresh from API"),
) -> Any:
    """New Releases from MULTIPLE SOURCES with background caching.

    Hey future me - REFACTORED to use NewReleasesSyncWorker cache!
    Background worker syncs every 30 minutes and caches results.
    UI reads from cache for fast response. Manual refresh available via button.

    MULTI-SERVICE PATTERN: Works WITHOUT Spotify login!
    Uses get_spotify_plugin_optional → returns None if not authenticated.
    Falls back to Deezer (NO AUTH NEEDED) for new releases.

    Architecture:
        Route → Check Cache → [Fresh? Return cached] OR [Stale? Fetch live]
                      ↓
            NewReleasesSyncWorker (background sync)
                      ↓
            Cached AlbumDTOs → Template

    Args:
        request: FastAPI request
        session: Database session (for settings check)
        deezer_plugin: DeezerPlugin instance (fallback if cache miss)
        spotify_plugin: SpotifyPlugin instance (fallback if cache miss)
        days: How many days back to look for releases (default 90)
        include_compilations: Include compilation albums
        include_singles: Include singles/EPs
        force_refresh: Force refresh from API (bypass cache)

    Returns:
        HTML page with combined new releases from all sources
    """
    from collections import defaultdict
    from datetime import datetime, timedelta

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.new_releases_service import (
        NewReleasesResult,
        NewReleasesService,
    )

    error: str | None = None
    all_releases: list[dict[str, Any]] = []
    cache_info: dict[str, Any] = {}
    result: NewReleasesResult | None = None

    # Check which providers are enabled
    settings_service = AppSettingsService(session)
    enabled_providers: list[str] = []
    if await settings_service.is_provider_enabled("deezer"):
        enabled_providers.append("deezer")
    if await settings_service.is_provider_enabled("spotify"):
        enabled_providers.append("spotify")

    # -------------------------------------------------------------------------
    # TRY TO USE CACHED DATA FROM BACKGROUND WORKER
    # -------------------------------------------------------------------------
    # Hey future me - der Worker cached im Hintergrund alle 30 min!
    # Hier lesen wir aus dem Cache für schnelle Response.
    # force_refresh=True oder cache stale → fetch live.
    worker = getattr(request.app.state, "new_releases_sync_worker", None)

    if worker and not force_refresh:
        cache = worker.get_cached_releases()
        if cache.is_fresh():
            # Use cached data!
            result = cache.result
            cache_info = {
                "source": "cache",
                "age_seconds": cache.get_age_seconds(),
                "cached_at": cache.cached_at.isoformat() if cache.cached_at else None,
            }
            logger.debug(f"New Releases: Using cached data ({cache_info['age_seconds']}s old)")
        else:
            logger.debug("New Releases: Cache stale or invalid, fetching live")
            cache_info = {"source": "live", "reason": "cache_stale"}
    else:
        if force_refresh:
            logger.info("New Releases: Force refresh requested")
            cache_info = {"source": "live", "reason": "force_refresh"}
        else:
            logger.debug("New Releases: No worker available, fetching live")
            cache_info = {"source": "live", "reason": "no_worker"}

    # -------------------------------------------------------------------------
    # FETCH LIVE IF NO CACHE OR FORCE REFRESH
    # -------------------------------------------------------------------------
    if result is None:
        # Try force sync via worker first (updates cache)
        if worker and force_refresh:
            result = await worker.force_sync()
            if result:
                cache_info["source"] = "force_synced"

        # Fallback: fetch directly via service
        if result is None:
            service = NewReleasesService(
                spotify_plugin=spotify_plugin,
                deezer_plugin=deezer_plugin,
            )
            try:
                result = await service.get_all_new_releases(
                    days=days,
                    include_singles=include_singles,
                    include_compilations=include_compilations,
                    enabled_providers=enabled_providers,
                )
            except Exception as e:
                logger.error(f"New Releases: Service failed: {e}")
                error = f"Failed to fetch new releases: {e}"
                result = None

    # -------------------------------------------------------------------------
    # CONVERT RESULT TO TEMPLATE FORMAT
    # -------------------------------------------------------------------------
    source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}

    if result:
        source_counts = result.source_counts

        # Convert AlbumDTOs to template-friendly dicts
        for album in result.albums:
            # Build external URL based on source
            if album.source_service == "spotify" and album.spotify_id:
                external_url = f"https://open.spotify.com/album/{album.spotify_id}"
                album_id = album.spotify_id
            elif album.source_service == "deezer" and album.deezer_id:
                external_url = f"https://www.deezer.com/album/{album.deezer_id}"
                album_id = album.deezer_id
            else:
                external_url = album.external_urls.get(album.source_service, "") if album.external_urls else ""
                album_id = album.deezer_id or album.spotify_id or ""

            all_releases.append({
                "id": album_id,
                "name": album.title,
                "artist_name": album.artist_name,
                "artist_id": album.artist_deezer_id or album.artist_spotify_id or "",
                "artwork_url": album.artwork_url,
                "release_date": album.release_date,
                "album_type": album.album_type or "album",
                "total_tracks": album.total_tracks,
                "external_url": external_url,
                "source": album.source_service,
            })

        # Log any errors from sync
        for provider, err in result.errors.items():
            logger.warning(f"New Releases: {provider} error: {err}")

    # -------------------------------------------------------------------------
    # GROUP BY WEEK for better display
    # -------------------------------------------------------------------------
    releases_by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for release in all_releases:
        date_str = release.get("release_date")
        if date_str:
            try:
                # Parse date (handle different precisions)
                if len(date_str) >= 10:
                    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                elif len(date_str) == 7:
                    dt = datetime.strptime(f"{date_str}-01", "%Y-%m-%d")
                else:
                    dt = datetime.strptime(f"{date_str}-01-01", "%Y-%m-%d")

                week_start = dt - timedelta(days=dt.weekday())
                week_label = week_start.strftime("%B %d, %Y")
                releases_by_week[week_label].append(release)
            except (ValueError, TypeError):
                releases_by_week["Unknown Date"].append(release)
        else:
            releases_by_week["Unknown Date"].append(release)

    if not all_releases:
        error = "No new releases found. Try syncing your Spotify artists first!"

    return templates.TemplateResponse(
        request,
        "new_releases.html",
        context={
            "releases": all_releases,
            "releases_by_week": dict(releases_by_week),
            "total_count": len(all_releases),
            "source_counts": source_counts,
            "days": days,
            "include_compilations": include_compilations,
            "include_singles": include_singles,
            "source": f"Deezer ({source_counts.get('deezer', 0)}) + Spotify ({source_counts.get('spotify', 0)})",
            "error": error,
            "cache_info": cache_info,  # NEW: Show cache status in UI
        },
    )


# NOTE: /browse/charts route REMOVED!
# Deezer Charts showed random "trending" content, not user's personal music.
# This polluted the UI with content the user doesn't care about.
# If you need charts again in the future, implement it as a separate "Discover" feature.


@router.get("/spotify/discover", response_class=HTMLResponse)
async def spotify_discover_page(
    request: Request,
    sync_service: SpotifySyncService = Depends(get_spotify_sync_service),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Discover Similar Artists page - MULTI-PROVIDER!

    Hey future me - REFACTORED to use DiscoverService for Multi-Provider discovery!
    Now aggregates related artists from BOTH Spotify AND Deezer.

    MULTI-SERVICE PATTERN: Works WITHOUT Spotify login!
    Uses get_spotify_plugin_optional → returns None if not authenticated.
    Falls back to Deezer (NO AUTH NEEDED) for artist discovery.

    Architecture:
        Route → DiscoverService
                     ↓
        [SpotifyPlugin, DeezerPlugin] (parallel fetch)
                     ↓
        Aggregate & Deduplicate by name
                     ↓
        DiscoverResult → Template

    Deezer advantage: NO AUTH NEEDED for related artists!
    Falls back to Deezer if Spotify unavailable.
    """
    import random

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.discover_service import DiscoverService

    settings = AppSettingsService(session)

    # Check which providers are enabled
    enabled_providers: list[str] = []
    if await settings.is_provider_enabled("spotify"):
        enabled_providers.append("spotify")
    if await settings.is_provider_enabled("deezer"):
        enabled_providers.append("deezer")

    if not enabled_providers:
        return templates.TemplateResponse(
            request,
            "discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "source_counts": {},
                "error": "No music providers enabled. Enable Spotify or Deezer in Settings.",
            },
        )

    # Get all followed artists (limit to 1000 for performance)
    artists = await sync_service.get_artists(limit=1000)

    logger.info(f"Discover page: Found {len(artists) if artists else 0} artists in DB")

    if not artists:
        return templates.TemplateResponse(
            request,
            "discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "source_counts": {},
                "error": "No followed artists found. Sync your Spotify artists first in Settings!",
            },
        )

    # Pick random artists to base discovery on (max 5 to avoid rate limits)
    sample_size = min(5, len(artists))
    sample_artists = random.sample(artists, sample_size)

    logger.info(
        f"Discover page (Multi-Provider): Sampling {sample_size} artists: "
        f"{[a.name for a in sample_artists]}"
    )

    # Get followed artist IDs/names for filtering
    # Extract Spotify ID from URI (format: spotify:artist:ID)
    followed_ids = {
        uri.split(":")[-1] for a in artists if (uri := a.spotify_uri)
    }
    followed_names = {a.name.lower().strip() for a in artists if a.name}

    # Use DiscoverService for Multi-Provider discovery!
    service = DiscoverService(
        spotify_plugin=spotify_plugin,
        deezer_plugin=deezer_plugin,
    )

    discoveries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    error: str | None = None
    source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}

    for artist in sample_artists:
        try:
            result = await service.discover_similar_artists(
                seed_artist_name=artist.name,
                seed_artist_spotify_id=artist.spotify_id,
                limit=20,
                enabled_providers=enabled_providers,
            )

            # Aggregate source counts
            for src, count in result.source_counts.items():
                source_counts[src] = source_counts.get(src, 0) + count

            for discovered in result.artists:
                # Skip if already following
                d_name_norm = discovered.name.lower().strip()
                if d_name_norm in followed_names:
                    continue
                if discovered.spotify_id and discovered.spotify_id in followed_ids:
                    continue

                # Skip duplicates in this batch
                key = discovered.spotify_id or discovered.deezer_id or d_name_norm
                if key in seen_ids:
                    continue
                seen_ids.add(key)

                discoveries.append({
                    "spotify_id": discovered.spotify_id,
                    "deezer_id": discovered.deezer_id,
                    "name": discovered.name,
                    "image_url": discovered.artwork_url,
                    "genres": (discovered.genres or [])[:3],
                    "popularity": discovered.popularity or 0,
                    "based_on": artist.name,
                    "source": discovered.source_service,
                })

            # Log provider errors
            for provider, err in result.errors.items():
                logger.debug(f"Discover: {provider} error for {artist.name}: {err}")

        except Exception as e:
            logger.warning(f"Discovery failed for {artist.name}: {e}")
            continue

    logger.info(
        f"Discover page: Found {len(discoveries)} unique discoveries "
        f"(Spotify: {source_counts.get('spotify', 0)}, Deezer: {source_counts.get('deezer', 0)})"
    )

    if not discoveries:
        error = "Could not find recommendations. Try syncing more artists first."

    # Sort by popularity (most popular first)
    discoveries.sort(key=lambda x: x["popularity"], reverse=True)

    # Limit to top 50
    discoveries = discoveries[:50]

    return templates.TemplateResponse(
        request,
        "discover.html",
        context={
            "discoveries": discoveries,
            "based_on_count": sample_size,
            "total_discoveries": len(discoveries),
            "source_counts": source_counts,
            "error": error,
        },
    )


@router.get(
    "/spotify/artists/{artist_id}/albums/{album_id}", response_class=HTMLResponse
)
async def spotify_album_detail_page(
    request: Request,
    artist_id: str,
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """DEPRECATED: Redirect to unified library album view.

    Hey future me - this Spotify-specific route is deprecated (Dec 2025)!
    Use /library/albums/{artist_name}::{album_title} for multi-provider unified view.
    """
    from urllib.parse import quote

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from starlette.responses import RedirectResponse

    from soulspot.infrastructure.persistence.models import AlbumModel

    # Try to find album by spotify_uri to get artist_name::album_title key
    album_uri = f"spotify:album:{album_id}"
    stmt = (
        select(AlbumModel)
        .join(AlbumModel.artist)
        .where(AlbumModel.spotify_uri == album_uri)
        .options(joinedload(AlbumModel.artist))
    )
    result = await session.execute(stmt)
    album_model = result.unique().scalar_one_or_none()

    if album_model and album_model.artist:
        # Build library album key: artist_name::album_title
        album_key = f"{album_model.artist.name}::{album_model.title}"
        return RedirectResponse(url=f"/library/albums/{quote(album_key)}", status_code=301)
    else:
        # Album not in library yet - redirect to library albums list
        return RedirectResponse(url="/library/albums", status_code=302)


# Hey future me, DEPRECATED route! Users should use /spotify/artists instead for auto-sync.
# Returns HTTP 410 Gone (permanently removed) with helpful redirect message.
# This prevents 404 confusion and guides users to the new location.
@router.get("/automation/followed-artists", response_class=JSONResponse, status_code=410)
async def followed_artists_page_deprecated(request: Request) -> Any:
    """Followed artists sync page - DEPRECATED.

    This endpoint has been permanently moved to /spotify/artists for a better
    auto-sync experience. Please update your bookmarks.

    Returns:
        HTTP 410 Gone with redirect information
    """
    return JSONResponse(
        status_code=410,
        content={
            "error": "Endpoint Deprecated",
            "message": "This endpoint has been permanently removed. Please use the new location.",
            "redirect_to": "/spotify/artists",
            "reason": "Moved to auto-sync experience",
        },
        headers={"Location": "/spotify/artists"},
    )

