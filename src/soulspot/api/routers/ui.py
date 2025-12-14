"""UI routes for serving HTML templates."""

import json
import logging
from datetime import UTC
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
    get_job_queue,
    get_library_scanner_service,
    get_playlist_repository,
    get_spotify_browse_repository,
    get_spotify_plugin,
    get_spotify_sync_service,
    get_track_repository,
)
from soulspot.application.services.library_scanner_service import LibraryScannerService
from soulspot.application.services.spotify_sync_service import SpotifySyncService
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    SpotifyBrowseRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager
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
            "cover_url": p.cover_url,
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

        if track_model:
            if track_model.artist:
                artist_name = track_model.artist.name
            if track_model.album and track_model.album.artwork_url:
                album_art_url = track_model.album.artwork_url

        recent_activity.append(
            {
                "title": track_model.title if track_model else "Unknown Track",
                "artist": artist_name,
                "album_art": album_art_url,
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
            "image_url": album.artwork_url,
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
    # Hey future me - cover_url is essential for the grid view!
    # Without it, all playlists show placeholder images even though covers exist.
    playlists_data = [
        {
            "id": str(playlist.id.value),
            "name": playlist.name,
            "description": playlist.description,
            "track_count": len(playlist.track_ids),
            "source": playlist.source.value,
            "cover_url": playlist.cover_url,
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
# The cover_url comes from Playlist entity for Spotify playlists (extracted during sync).
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
        # Hey future me - this avoids the N+1 problem! We join playlist_tracks → tracks → artist/album
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
        # Hey future me - album_art comes from the Album's artwork_url!
        # We eager-load the album relationship and grab its cover image.
        tracks = [
            {
                "id": track.id,
                "title": track.title,
                "artist": track.artist.name if track.artist else "Unknown Artist",
                "album": track.album.title if track.album else "Unknown Album",
                "album_art": track.album.artwork_url if track.album else None,
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
            "cover_url": playlist.cover_url,  # Spotify playlist cover image
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
            "album_art": track.album.artwork_url if track and track.album and hasattr(track.album, "artwork_url") else None,
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

    from soulspot.infrastructure.persistence.models import TrackModel

    # Count tracks with local files
    total_tracks_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    total_tracks_result = await session.execute(total_tracks_stmt)
    total_tracks = total_tracks_result.scalar() or 0

    # Count unique artists with local files
    artists_stmt = select(func.count(func.distinct(TrackModel.artist_id))).where(
        TrackModel.file_path.isnot(None)
    )
    artists_result = await session.execute(artists_stmt)
    total_artists = artists_result.scalar() or 0

    # Count unique albums with local files
    albums_stmt = select(func.count(func.distinct(TrackModel.album_id))).where(
        TrackModel.file_path.isnot(None),
        TrackModel.album_id.isnot(None),
    )
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
        "total_tracks": total_tracks,
        "total_artists": total_artists,
        "total_albums": total_albums,
        "tracks_with_files": total_tracks,  # Same as total since we filter by file_path
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
    """
    from sqlalchemy import func, select

    from soulspot.infrastructure.persistence.models import TrackModel

    # Same queries as library() but just returns the stats section
    total_tracks_stmt = select(func.count(TrackModel.id)).where(
        TrackModel.file_path.isnot(None)
    )
    total_tracks = (await session.execute(total_tracks_stmt)).scalar() or 0

    artists_stmt = select(func.count(func.distinct(TrackModel.artist_id))).where(
        TrackModel.file_path.isnot(None)
    )
    total_artists = (await session.execute(artists_stmt)).scalar() or 0

    albums_stmt = select(func.count(func.distinct(TrackModel.album_id))).where(
        TrackModel.file_path.isnot(None),
        TrackModel.album_id.isnot(None),
    )
    total_albums = (await session.execute(albums_stmt)).scalar() or 0

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
            <span class="stat-value">{total_tracks:,}</span>
            <span class="stat-label">Local Files</span>
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
# IMPORTANT: Only shows artists with at least ONE local file (file_path IS NOT NULL)!
# Hey future me - this now checks for unenriched artists and passes enrichment_needed flag!
@router.get("/library/artists", response_class=HTMLResponse)
async def library_artists(
    request: Request,
    source: str | None = None,  # Filter by source (local/spotify/hybrid/all)
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=10, le=200, description="Items per page"),
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Unified artists browser page - shows LOCAL + SPOTIFY + HYBRID artists.

    Hey future me - This is now the UNIFIED Music Manager artist view!
    It shows ALL artists regardless of source (local file scan OR Spotify followed).

    Filter by source param:
    - ?source=local → Only artists from local file scans (with or without Spotify)
    - ?source=spotify → Only artists followed on Spotify (with or without local files)
    - ?source=hybrid → Only artists that exist in BOTH local + Spotify
    - ?source=all OR no param → Show ALL artists (default unified view)

    Each artist card shows badges:
    🎵 Local (has local files)
    🎧 Spotify (followed on Spotify)
    🌟 Both (hybrid)
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
    # else: source == "all" or None → Show ALL artists (no filter)

    # Get total count BEFORE applying pagination (for pagination controls)
    # Hey future me - count_stmt shares same filters but no joins needed
    count_stmt = select(func.count(ArtistModel.id))
    if source == "local":
        count_stmt = count_stmt.where(ArtistModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        count_stmt = count_stmt.where(ArtistModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        count_stmt = count_stmt.where(ArtistModel.source == "hybrid")
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    # Apply ordering and pagination
    stmt = stmt.order_by(ArtistModel.name).offset(offset).limit(per_page)
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
            "genres": artist.genres,  # JSON list of genres (from Spotify)
        }
        for artist, total_tracks, local_tracks, total_albums, local_albums in rows
    ]

    # Check for unenriched artists on THIS PAGE (have local files but no image)
    # Hey future me - count artists that need Spotify enrichment for artwork!
    artists_without_image = sum(1 for a in artists if not a["image_url"])
    enrichment_needed = artists_without_image > 0

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
            "current_source": source or "all",  # Active filter
            "source_counts": source_counts,  # For filter badge counts
            # Pagination context
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    )


# Hey future me – refactored to load AlbumModel directly with artist join!
# This gives us access to artwork_url from Spotify CDN. SQL does the grouping via
# relationship, not manual Python dict. Uses pagination (page/per_page params) for
# big libraries - defaults to 50 per page. artwork_url comes from Spotify sync – if
# album wasn't synced, falls back to None.
# IMPORTANT: Only shows albums with at least ONE local file (file_path IS NOT NULL)!
# Also handles "Various Artists" compilations properly via album_artist field.
@router.get("/library/albums", response_class=HTMLResponse)
async def library_albums(
    request: Request,
    source: str | None = None,  # Filter by source (local/spotify/hybrid/all)
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=10, le=200, description="Items per page"),
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Unified library albums browser page - shows ALL albums with local/total counts.
    
    Hey future me - After Table Consolidation (2025-12), shows ALL albums!
    Filter by source param like /library/artists.
    Shows "X/Y local" badge (e.g. "3/10 tracks" = 3 downloaded, 10 total).
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

    # Get total count for pagination
    count_stmt = select(func.count(AlbumModel.id))
    if source == "local":
        count_stmt = count_stmt.where(AlbumModel.source.in_(["local", "hybrid"]))
    elif source == "spotify":
        count_stmt = count_stmt.where(AlbumModel.source.in_(["spotify", "hybrid"]))
    elif source == "hybrid":
        count_stmt = count_stmt.where(AlbumModel.source == "hybrid")
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar() or 0

    # Calculate pagination
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    # Apply ordering and pagination
    stmt = stmt.order_by(AlbumModel.title).offset(offset).limit(per_page)
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
            "artwork_url": album.artwork_url,  # Spotify CDN URL or None
            "artwork_path": album.artwork_path,  # Local file path or None
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
            # Pagination context
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
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
            "artwork_url": album.artwork_url,
            "artwork_path": album.artwork_path,
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
    - Albums with local files → Show tracks
    - Spotify albums (no local files yet) → Show album card with download button

    This works for all source types:
    - LOCAL artists → Show albums from file scans
    - SPOTIFY artists → Show albums from Spotify API sync
    - HYBRID artists → Show ALL albums (merged)
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

    # Hey future me - AUTO-SYNC Spotify albums if artist has none yet!
    # If artist is from Spotify (source='spotify' or 'hybrid') and has NO albums in DB,
    # fetch albums from Spotify API on-demand. This ensures Spotify followed artists
    # show their discography immediately without manual sync button.
    if not album_models and artist_model.source in ["spotify", "hybrid"] and artist_model.spotify_uri:
        try:
            # Get Spotify plugin and token
            from soulspot.application.services.followed_artists_service import (
                FollowedArtistsService,
            )
            from soulspot.config import get_settings
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )
            from soulspot.infrastructure.persistence.database import (
                DatabaseTokenManager,
            )
            from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

            if hasattr(request.app.state, "db_token_manager"):
                db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
                access_token = await db_token_manager.get_token_for_background()

                if access_token:
                    # Use FollowedArtistsService with SpotifyPlugin + Deezer fallback
                    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
                    
                    app_settings = get_settings()
                    spotify_client = SpotifyClient(app_settings.spotify)
                    spotify_plugin = SpotifyPlugin(client=spotify_client, access_token=access_token)
                    deezer_plugin = DeezerPlugin()  # NO AUTH NEEDED!
                    followed_service = FollowedArtistsService(
                        session, spotify_plugin, deezer_plugin=deezer_plugin
                    )

                    # Sync albums for this artist (albums, singles, EPs, compilations)
                    # No access_token param - plugin has it!
                    await followed_service.sync_artist_albums(artist_model.id)
                    await session.commit()  # Commit new albums

                    # Re-query albums after sync
                    albums_result = await session.execute(albums_stmt)
                    album_models = albums_result.scalars().all()
        except Exception as e:
            logger.warning(f"Failed to auto-sync Spotify albums for {artist_model.name}: {e}")
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
            "artwork_url": album.artwork_url if hasattr(album, "artwork_url") else None,
            "spotify_id": album.spotify_uri if hasattr(album, "spotify_uri") else None,
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
        "name": artist_model.name,
        "source": artist_model.source,  # NEW: Show source badge
        "disambiguation": artist_model.disambiguation,
        "albums": albums,
        "tracks": tracks_data,
        "track_count": len(tracks_data),
        "album_count": len(albums),
        "image_url": artist_model.image_url,  # Spotify CDN URL or None
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
            request,
            "error.html",
            context={
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
            "disc_number": track.disc_number if hasattr(track, "disc_number") else 1,
            "duration_ms": track.duration_ms,
            "file_path": track.file_path,
            "is_broken": track.is_broken,
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

    # Hey future me – get artwork_url from album model for Spotify CDN cover
    artwork_url = (
        track_models[0].album.artwork_url
        if track_models
        and track_models[0].album
        and hasattr(track_models[0].album, "artwork_url")
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
# The flow: /spotify/artists → auto-sync → show grid → click artist → /spotify/artists/{id}
# → auto-sync albums → show albums → click album → /spotify/artists/{a}/albums/{b} → show tracks
# =============================================================================


@router.get("/spotify/artists", response_class=HTMLResponse)
async def spotify_artists_page(
    request: Request,
    sync_service: SpotifySyncService = Depends(get_spotify_sync_service),
) -> Any:
    """Spotify followed artists page with auto-sync.

    Auto-syncs followed artists from Spotify on page load (with cooldown).
    Shows all followed artists from DB after sync.

    Uses SHARED server-side token from DatabaseTokenManager, so any device
    on the network can access this page without per-browser session cookies.

    Hey future me - IMPORTANT: Sync FIRST, then load from DB!
    This ensures freshly synced data is visible immediately without refresh.
    The flow is: Sync (if needed/cooldown) → Commit → Load from DB → Render.
    """
    artists = []
    sync_stats = None
    error = None

    # Hey future me - Database-First architecture:
    # 1. TRY to sync to DB (if token available and cooldown passed)
    # 2. ALWAYS load from DB for display - even if sync fails or token is invalid!
    # This ensures data is visible even without a valid Spotify token.

    # Step 1: Try to sync if SpotifyPlugin has valid token (OPTIONAL - failures don't block DB load)
    try:
        # Hey future me - SpotifySyncService now uses SpotifyPlugin internally!
        # No more access_token passing - plugin handles auth internally.
        # Auto-sync (respects cooldown) - updates DB and commits
        sync_stats = await sync_service.sync_followed_artists()
    except Exception as sync_error:
        # Sync failed (token invalid, API error, etc.) - log but don't block
        # We'll still load existing data from DB below
        logger.warning(f"Spotify sync failed (will show cached data): {sync_error}")

    # Step 2: ALWAYS load from DB - even if sync failed or token is invalid!
    # This is the key Database-First principle: cached data must always be available.
    try:
        artist_models = await sync_service.get_artists(limit=500)

        # Convert to template-friendly format
        for artist in artist_models:
            genres = []
            if artist.genres:
                try:
                    genres = (
                        json.loads(artist.genres)
                        if isinstance(artist.genres, str)
                        else artist.genres
                    )
                except (json.JSONDecodeError, TypeError):
                    genres = []

            artists.append(
                {
                    "spotify_id": artist.spotify_id,
                    "name": artist.name,
                    "image_url": artist.image_url,
                    "genres": genres[:3],  # Max 3 genres for display
                    "genres_count": len(genres),
                    "popularity": artist.popularity,
                    "follower_count": artist.follower_count,
                }
            )
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request,
        "spotify_artists.html",
        context={
            "artists": artists,
            "sync_stats": sync_stats,
            "error": error,
            "total_count": len(artists),
        },
    )


@router.get("/browse/new-releases", response_class=HTMLResponse)
async def browse_new_releases_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    days: int = Query(default=90, ge=7, le=365, description="Days to look back"),
    include_compilations: bool = Query(default=True, description="Include compilations"),
    include_singles: bool = Query(default=True, description="Include singles"),
) -> Any:
    """New Releases from MULTIPLE SOURCES - combines Deezer + Spotify releases.

    Hey future me - this aggregates releases from ALL music services!
    1. Deezer: Global new releases (editorial + charts) - NO AUTH NEEDED
    2. Spotify: Releases from YOUR followed artists (from DB)

    We deduplicate by artist_name + album_title (normalized) to avoid
    showing the same album twice from different sources.

    The source badge on each album shows where it came from.
    Users get the best of both worlds:
    - Discovery of popular new releases (Deezer)
    - Personal releases from followed artists (Spotify)

    Args:
        request: FastAPI request
        session: Database session for Spotify data
        deezer_plugin: DeezerPlugin for global releases
        days: How many days back to look for releases (default 90)
        include_compilations: Include compilation albums
        include_singles: Include singles/EPs

    Returns:
        HTML page with combined new releases from all sources
    """
    from datetime import datetime, timedelta

    from sqlalchemy import select

    # Hey future me - nach Table Consolidation nutzen wir die unified models!
    # Spotify-Daten sind jetzt in soulspot_artists/albums mit source='spotify'
    from soulspot.infrastructure.persistence.models import (
        AlbumModel,
        ArtistModel,
    )

    error: str | None = None
    all_releases: list[dict[str, Any]] = []
    seen_keys: set[str] = set()  # For deduplication
    source_counts: dict[str, int] = {"deezer": 0, "spotify": 0}  # Track contributions

    def normalize_key(artist: str, album: str) -> str:
        """Create normalized key for deduplication."""
        return f"{artist.lower().strip()}::{album.lower().strip()}"

    # Check provider availability via AppSettingsService
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings_service = AppSettingsService(session)
    deezer_enabled = await settings_service.is_provider_enabled("deezer")
    spotify_enabled = await settings_service.is_provider_enabled("spotify")

    # -------------------------------------------------------------------------
    # 1. DEEZER: Global New Releases (no auth required! - uses can_use())
    # -------------------------------------------------------------------------
    # Use can_use() which checks: 1) capability supported 2) auth available if needed
    # For Deezer BROWSE_NEW_RELEASES, no auth is needed (returns True without token)
    if deezer_enabled and deezer_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
        try:
            deezer_result = await deezer_plugin.get_browse_new_releases(
                limit=50,
                include_compilations=include_compilations,
            )

            if deezer_result.get("success") and deezer_result.get("albums"):
                for album in deezer_result["albums"]:
                    # Filter singles if not wanted
                    record_type = album.get("record_type", "album")
                    if not include_singles and record_type in ("single", "ep"):
                        continue

                    key = normalize_key(
                        album.get("artist_name", ""),
                        album.get("title", ""),
                    )
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_releases.append({
                            "id": album.get("deezer_id") or album.get("id"),
                            "name": album.get("title"),
                            "artist_name": album.get("artist_name"),
                            "artist_id": album.get("artist_id"),
                            "artwork_url": album.get("cover_big") or album.get("cover_medium"),
                        "release_date": album.get("release_date"),
                        "album_type": record_type,
                        "total_tracks": album.get("total_tracks") or album.get("nb_tracks"),
                        "external_url": album.get("link") or f"https://www.deezer.com/album/{album.get('id')}",
                        "source": "deezer",
                    })
                    source_counts["deezer"] += 1

            logger.info(f"New Releases: Got {source_counts['deezer']} from Deezer (using can_use)")

        except Exception as e:
            logger.warning(f"New Releases: Deezer fetch failed: {e}")
    else:
        # Log why skipped: provider disabled or capability not available
        skip_reason = "provider disabled" if not deezer_enabled else "capability not available"
        logger.debug(f"New Releases: Deezer skipped ({skip_reason})")

    # -------------------------------------------------------------------------
    # 2. SPOTIFY: Releases from followed artists (from unified library)
    # Hey future me - nach Table Consolidation sind Spotify-Daten in soulspot_albums!
    # Wir filtern nach source='spotify' und Alben von gefolgten Künstlern
    # -------------------------------------------------------------------------
    if spotify_enabled:
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")

            # Build album type filter
            allowed_types = ["album"]
            if include_singles:
                allowed_types.extend(["single", "ep"])
            if include_compilations:
                allowed_types.append("compilation")

            # Hey future me - jetzt nutzen wir unified models!
            # AlbumModel.source='spotify' UND artist hat spotify_uri (= followed artist)
            stmt = (
                select(AlbumModel, ArtistModel)
                .join(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
                .where(AlbumModel.source == "spotify")  # Nur Spotify-synced albums
                .where(AlbumModel.release_date >= cutoff_str)
                .where(AlbumModel.album_type.in_(allowed_types))
                .where(ArtistModel.spotify_uri.isnot(None))  # Nur artists mit Spotify URI
                .order_by(AlbumModel.release_date.desc())
                .limit(100)
            )

            result = await session.execute(stmt)
            rows = result.all()

            for album, artist in rows:
                key = normalize_key(artist.name, album.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    # Extract spotify_id from URI: "spotify:album:xxx" -> "xxx"
                    spotify_album_id = album.spotify_uri.split(":")[-1] if album.spotify_uri else album.id
                    spotify_artist_id = artist.spotify_uri.split(":")[-1] if artist.spotify_uri else artist.id
                    all_releases.append({
                        "id": spotify_album_id,
                        "name": album.title,
                        "artist_name": artist.name,
                        "artist_id": spotify_artist_id,
                        "artwork_url": album.artwork_url or album.image_path,
                        "release_date": album.release_date,
                        "album_type": album.primary_type,
                        "total_tracks": album.total_tracks,
                        "external_url": f"https://open.spotify.com/album/{spotify_album_id}",
                        "source": "spotify",
                    })
                    source_counts["spotify"] += 1

            logger.info(f"New Releases: Got {source_counts['spotify']} from Spotify unified library (after dedup)")

        except Exception as e:
            logger.warning(f"New Releases: Spotify unified library fetch failed: {e}")
    else:
        logger.debug("New Releases: Spotify provider disabled, skipping")

    # -------------------------------------------------------------------------
    # 3. SORT BY RELEASE DATE (newest first)
    # -------------------------------------------------------------------------
    def parse_date(release: dict) -> str:
        """Get sortable date string, default to old date if missing."""
        date = release.get("release_date") or "1900-01-01"
        # Handle YYYY, YYYY-MM, YYYY-MM-DD formats
        if len(date) == 4:
            return f"{date}-12-31"
        elif len(date) == 7:
            return f"{date}-28"
        return date[:10]

    all_releases.sort(key=lambda r: parse_date(r), reverse=True)

    # -------------------------------------------------------------------------
    # 4. GROUP BY WEEK for better display
    # -------------------------------------------------------------------------
    from collections import defaultdict

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

    # source_counts already tracked above during aggregation

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
            "source": f"Deezer ({source_counts['deezer']}) + Spotify ({source_counts['spotify']})",
            "error": error,
        },
    )


@router.get("/spotify/discover", response_class=HTMLResponse)
async def spotify_discover_page(
    request: Request,
    sync_service: SpotifySyncService = Depends(get_spotify_sync_service),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Discover Similar Artists page.

    Hey future me - this is the REAL discovery page! Shows artists similar to your favorites.
    Fetches related artists from SpotifyPlugin for your followed artists and aggregates
    the suggestions, filtering out ones you already follow.
    SpotifyPlugin handles auth internally - no more manual token passing!
    Uses can_use() for elegant capability checking.
    """
    import random

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    # Provider + Auth checks using can_use() - checks both capability support AND auth
    settings = AppSettingsService(session)
    if not await settings.is_provider_enabled("spotify"):
        return templates.TemplateResponse(
            request,
            "spotify_discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "error": "Spotify provider is disabled. Enable it in Settings to discover artists.",
            },
        )

    # can_use() checks: 1) capability supported 2) is_authenticated if required
    if not spotify_plugin.can_use(PluginCapability.GET_RELATED_ARTISTS):
        return templates.TemplateResponse(
            request,
            "spotify_discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "error": "Not authenticated with Spotify. Connect your account in Settings.",
            },
        )

    # Get all followed artists (limit to 1000 for performance)
    artists = await sync_service.get_artists(limit=1000)

    logger.info(f"Discover page: Found {len(artists) if artists else 0} artists in DB")

    if not artists:
        return templates.TemplateResponse(
            request,
            "spotify_discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "error": "No followed artists found. Sync your Spotify artists first in Settings!",
            },
        )

    # Pick random artists to base discovery on (max 5 to avoid rate limits)
    sample_size = min(5, len(artists))
    sample_artists = random.sample(artists, sample_size)

    logger.info(
        f"Discover page: Sampling {sample_size} artists for related lookup: "
        f"{[a.name for a in sample_artists]}"
    )

    # Get followed artist IDs for filtering
    followed_ids = {a.spotify_id for a in artists}

    # Aggregate similar artists from sampled followed artists
    discoveries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    error: str | None = None
    api_errors: int = 0

    for artist in sample_artists:
        if not artist.spotify_id:
            logger.warning(f"Artist {artist.name} has no spotify_id, skipping")
            continue
        try:
            # SpotifyPlugin returns list[ArtistDTO] - clean DTO access!
            related_dtos = await spotify_plugin.get_related_artists(artist.spotify_id)
            logger.debug(f"Got {len(related_dtos)} related artists for {artist.name}")
            for r in related_dtos:
                rid = r.spotify_id
                # Skip if already following or already in discoveries
                if rid and rid not in followed_ids and rid not in seen_ids:
                    seen_ids.add(rid)
                    discoveries.append(
                        {
                            "spotify_id": rid,
                            "name": r.name,
                            "image_url": r.image_url,
                            "genres": (r.genres or [])[:3],
                            "popularity": r.popularity or 0,
                            "based_on": artist.name,
                        }
                    )
        except Exception as e:
            api_errors += 1
            # Hey future me - Spotify returns 404 for some artists (no related data available).
            # This is normal - not all artists have related artist data in Spotify's database.
            # Log as DEBUG for 404s (expected), WARNING for other errors (unexpected).
            error_str = str(e)
            if "404" in error_str:
                logger.debug(
                    f"No related artists available for {artist.name} "
                    "(Spotify has no data for this artist)"
                )
            else:
                logger.warning(f"Failed to get related artists for {artist.name}: {e}")
            continue

    # Log summary at INFO level only if there were discoveries or errors worth noting
    if discoveries or api_errors > sample_size // 2:
        logger.info(
            f"Discover page: Found {len(discoveries)} unique discoveries, "
            f"{api_errors} API calls skipped (no data available)"
        )

    # If all API calls failed, show error
    if api_errors == sample_size and not discoveries:
        error = "Could not fetch recommendations. Please check your Spotify connection."

    # Sort by popularity (most popular first)
    discoveries.sort(key=lambda x: x["popularity"], reverse=True)

    # Limit to top 50
    discoveries = discoveries[:50]

    return templates.TemplateResponse(
        request,
        "spotify_discover.html",
        context={
            "discoveries": discoveries,
            "based_on_count": sample_size,
            "total_discoveries": len(discoveries),
            "error": error,
        },
    )


@router.get("/spotify/artists/{artist_id}", response_class=HTMLResponse)
async def spotify_artist_detail_page(
    request: Request,
    artist_id: str,
    sync_service: SpotifySyncService = Depends(get_spotify_sync_service),
) -> Any:
    """Spotify artist detail page with albums.

    Hey future me - refactored to use SpotifyPlugin via SpotifySyncService!
    Auto-syncs artist's albums from Spotify on page load (with cooldown).
    Shows artist info and album grid.

    SpotifyPlugin handles auth internally - no more manual token fetching!
    """
    artist = None
    albums = []
    sync_stats = None
    error = None

    try:
        # Get artist from DB
        artist_model = await sync_service.get_artist(artist_id)

        if not artist_model:
            return templates.TemplateResponse(
                request,
                "error.html",
                context={
                    "error_code": 404,
                    "error_message": f"Artist {artist_id} nicht gefunden",
                },
                status_code=404,
            )

        # Parse artist data
        genres = []
        if artist_model.genres:
            try:
                genres = (
                    json.loads(artist_model.genres)
                    if isinstance(artist_model.genres, str)
                    else artist_model.genres
                )
            except (json.JSONDecodeError, TypeError):
                genres = []

        artist = {
            "spotify_id": artist_model.spotify_id,
            "name": artist_model.name,
            "image_url": artist_model.image_url,
            "genres": genres,
            "popularity": artist_model.popularity,
            "follower_count": artist_model.follower_count,
        }

        # Hey future me - SpotifyPlugin handles auth internally!
        # No more "if access_token:" checks needed.
        # Auto-sync albums (respects cooldown)
        try:
            sync_stats = await sync_service.sync_artist_albums(artist_id)
        except Exception as sync_error:
            # Sync failed but we can still show cached data
            logger.warning(f"Album sync failed (showing cached): {sync_error}")

        # Get albums from DB
        album_models = await sync_service.get_artist_albums(artist_id, limit=200)

        for album in album_models:
            albums.append(
                {
                    "spotify_id": album.spotify_uri,
                    "name": album.title,
                    "image_url": album.artwork_url,
                    "release_date": album.release_date,
                    "album_type": album.primary_type,
                    "total_tracks": album.total_tracks,
                }
            )

        # Sort: albums first, then singles, by release date desc
        type_order = {"album": 0, "single": 1, "compilation": 2}
        albums.sort(
            key=lambda a: (
                type_order.get(a["album_type"], 99),
                a["release_date"] or "",
            ),
            reverse=True,
        )

    except Exception as e:
        error = str(e)

    # Hey future me - fetch related artists for "Fans Also Like" section!
    # This runs AFTER main artist/albums load to not block the page.
    # We only fetch if we have a valid access_token.
    related_artists: list[dict[str, Any]] = []
    try:
        access_token = None
        if hasattr(request.app.state, "db_token_manager"):
            db_token_manager_ra: DatabaseTokenManager = (
                request.app.state.db_token_manager
            )
            access_token = await db_token_manager_ra.get_token_for_background()

        if access_token:
            # Fetch related artists from Spotify
            related_raw = await spotify_client.get_related_artists(
                artist_id, access_token
            )

            # Batch check following status
            related_ids: list[str] = [
                str(a.get("id")) for a in related_raw if a.get("id") is not None
            ]
            following_statuses: list[bool] = []
            if related_ids:
                following_statuses = await spotify_client.check_if_following_artists(
                    related_ids, access_token
                )

            # Build simplified list for template
            for idx, ra in enumerate(related_raw[:12]):  # Limit to 12 for UI
                images = ra.get("images", [])
                image_url = images[0]["url"] if images else None

                related_artists.append(
                    {
                        "spotify_id": ra.get("id", ""),
                        "name": ra.get("name", "Unknown"),
                        "image_url": image_url,
                        "genres": ra.get("genres", [])[:2],  # Limit genres
                        "popularity": ra.get("popularity", 0),
                        "is_following": following_statuses[idx]
                        if idx < len(following_statuses)
                        else False,
                    }
                )
    except Exception as e:
        # Don't fail the whole page if related artists fail
        logger.warning(f"Failed to fetch related artists for {artist_id}: {e}")

    return templates.TemplateResponse(
        request,
        "spotify_artist_detail.html",
        context={
            "artist": artist,
            "albums": albums,
            "sync_stats": sync_stats,
            "error": error,
            "album_count": len(albums),
            "related_artists": related_artists,
        },
    )


@router.get(
    "/spotify/artists/{artist_id}/albums/{album_id}", response_class=HTMLResponse
)
async def spotify_album_detail_page(
    request: Request,
    artist_id: str,
    album_id: str,
    sync_service: SpotifySyncService = Depends(get_spotify_sync_service),
) -> Any:
    """Spotify album detail page with tracks.

    Hey future me - refactored to use SpotifyPlugin via SpotifySyncService!
    Auto-syncs album's tracks from Spotify on page load (with cooldown).
    Shows album info and track list with download buttons.

    SpotifyPlugin handles auth internally - no more manual token fetching!
    """
    artist = None
    album = None
    tracks = []
    sync_stats = None
    error = None

    try:
        # Get artist from DB
        artist_model = await sync_service.get_artist(artist_id)
        if artist_model:
            artist = {
                "spotify_id": artist_model.spotify_id,
                "name": artist_model.name,
            }

        # Get album from DB
        album_model = await sync_service.get_album(album_id)

        if not album_model:
            return templates.TemplateResponse(
                request,
                "error.html",
                context={
                    "error_code": 404,
                    "error_message": f"Album {album_id} nicht gefunden",
                },
                status_code=404,
            )

        album = {
            "spotify_id": album_model.spotify_id,
            "name": album_model.name,
            "image_url": album_model.image_url,
            "release_date": album_model.release_date,
            "album_type": album_model.album_type,
            "total_tracks": album_model.total_tracks,
        }

        # Hey future me - SpotifyPlugin handles auth internally!
        # No more "if access_token:" checks needed.
        # Auto-sync tracks (respects cooldown)
        try:
            sync_stats = await sync_service.sync_album_tracks(album_id)
        except Exception as sync_error:
            # Sync failed but we can still show cached data
            logger.warning(f"Track sync failed (showing cached): {sync_error}")

        # Get tracks from DB
        track_models = await sync_service.get_album_tracks(album_id, limit=100)

        for track in track_models:
            # Format duration
            duration_sec = track.duration_ms // 1000
            duration_min = duration_sec // 60
            duration_sec_rem = duration_sec % 60
            duration_str = f"{duration_min}:{duration_sec_rem:02d}"

            tracks.append(
                {
                    "spotify_id": track.spotify_id,
                    "name": track.name,
                    "track_number": track.track_number,
                    "disc_number": track.disc_number,
                    "duration_ms": track.duration_ms,
                    "duration_str": duration_str,
                    "explicit": track.explicit,
                    "preview_url": track.preview_url,
                    "isrc": track.isrc,
                    "local_track_id": track.local_track_id,
                    "is_downloaded": track.local_track_id is not None,
                }
            )

        # Sort by disc number, then track number
        tracks.sort(key=lambda t: (t["disc_number"], t["track_number"]))

        # Calculate total duration
        total_ms = sum(t["duration_ms"] for t in tracks)
        total_min = total_ms // 60000
        total_sec = (total_ms % 60000) // 1000

    except Exception as e:
        error = str(e)
        total_min = 0
        total_sec = 0

    return templates.TemplateResponse(
        request,
        "spotify_album_detail.html",
        context={
            "artist": artist,
            "album": album,
            "tracks": tracks,
            "sync_stats": sync_stats,
            "error": error,
            "track_count": len(tracks),
            "total_duration": f"{total_min} min {total_sec} sec",
        },
    )


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
