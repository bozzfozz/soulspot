"""Dashboard and core UI routes.

Hey future me - this module contains:
- Main dashboard (/)
- Playlists overview (/playlists)
- Playlist detail pages
- Static pages (auth, onboarding, styleguide, search)
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_download_repository,
    get_playlist_repository,
    get_provider_browse_repository,
)
from soulspot.api.routers.ui._shared import templates
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    ProviderBrowseRepository,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

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
    provider_repository: ProviderBrowseRepository = Depends(
        get_provider_browse_repository
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

    # Get provider synced data counts (Spotify, Deezer, etc.)
    # Hey future me - count_artists() filters by source='spotify' by default
    # Multi-provider note: Can add source parameter later for per-provider counts
    spotify_artists = await provider_repository.count_artists()
    spotify_albums = await provider_repository.count_albums()
    spotify_tracks = await provider_repository.count_tracks()

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
    # from unified albums table (pre-synced data), sorted by release_date descending.
    # Limit to 12 for a nice 4x3 or 6x2 grid display.
    # Multi-provider note: get_latest_releases() currently filters by source='spotify' by default
    latest_releases_raw = await provider_repository.get_latest_releases(limit=12)
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

        # Get missing tracks (no file_path)
        missing_tracks = []
        for track_id in playlist.track_ids:
            stmt = (
                select(TrackModel)
                .where(TrackModel.id == str(track_id.value))
                .where(TrackModel.file_path.is_(None))
                .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            )
            result = await session.execute(stmt)
            track_model = result.unique().scalar_one_or_none()
            if track_model:
                missing_tracks.append(
                    {
                        "id": track_model.id,
                        "title": track_model.title,
                        "artist": track_model.artist.name
                        if track_model.artist
                        else "Unknown",
                        "album": track_model.album.title
                        if track_model.album
                        else "Unknown",
                        "duration_ms": track_model.duration_ms,
                    }
                )

        return templates.TemplateResponse(
            request,
            "partials/missing_tracks.html",
            context={
                "playlist_id": playlist_id,
                "missing_tracks": missing_tracks,
                "total_missing": len(missing_tracks),
            },
        )

    except ValueError:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 400,
                "error_message": "Invalid playlist ID format",
            },
            status_code=400,
        )


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


# Static template pages - no logic, just render HTML. These are lightweight routes.
@router.get("/auth", response_class=HTMLResponse)
async def auth(request: Request) -> Any:
    """Auth page."""
    return templates.TemplateResponse(request, "auth.html")


# Hey future me - this is the UI styleguide page showing all components! Use it to verify the
# design system (colors, buttons, cards, badges, etc.) is working. Doesn't hit DB, pure template.
# Good for debugging CSS issues or showing designers what's available in the component library.
@router.get("/styleguide", response_class=HTMLResponse)
async def styleguide(request: Request) -> Any:
    """UI Styleguide page showing all components and design tokens."""
    return templates.TemplateResponse(request, "styleguide.html")


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
