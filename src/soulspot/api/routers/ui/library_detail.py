"""Library detail UI routes - Artist and Album detail pages.

Hey future me - this module contains detail pages for single artists/albums:
- Artist detail (/library/artists/{artist_name}) - shows artist's albums + tracks
- Album detail (/library/albums/{album_key}) - shows album's tracks
- Metadata editor (/tracks/{track_id}/metadata-editor) - edit track metadata
"""

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soulspot.api.dependencies import get_db_session, get_track_repository
from soulspot.api.routers.ui._shared import templates
from soulspot.config import get_settings
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)
from soulspot.infrastructure.persistence.repositories import TrackRepository

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter()


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
    artist_name = unquote(artist_name)

    # Step 1: Get artist by name (case-insensitive)
    artist_stmt = select(ArtistModel).where(
        func.lower(ArtistModel.name) == artist_name.lower()
    )
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

    # Hey future me - WORKER-FIRST PATTERN! (Jan 2026 design change)
    # ================================================================
    # DESIGN DECISION: NO on-demand API calls in routes!
    # 
    # The UnifiedLibraryManager worker keeps DB up-to-date in background.
    # Routes ONLY read from DB - fast, consistent, no rate limit issues!
    #
    # If artist has no albums yet:
    # - Worker will sync them in the next cycle (max 5 min wait)
    # - UI shows "Sync in progress" message
    # - User can manually trigger sync from Settings → Spotify → Sync Now
    #
    # Benefits:
    # - No API calls on page load → Fast!
    # - No rate limiting issues → Reliable!
    # - Worker handles retries, errors, rate limits → Robust!
    # - DB is single source of truth → Consistent!
    # ================================================================
    
    # If no albums in DB, don't fetch on-demand - let Worker handle it
    # Just show empty state with "sync pending" message
    if not album_models:
        logger.info(
            f"[ARTIST_DETAIL] No albums in DB for {artist_model.name} - "
            "Worker will sync in background"
        )

    # Step 3: Get tracks for these albums
    tracks_stmt = (
        select(TrackModel)
        .where(TrackModel.artist_id == artist_model.id)
        .options(joinedload(TrackModel.album))
    )
    tracks_result = await session.execute(tracks_stmt)
    track_models = tracks_result.unique().scalars().all()

    # Log track count for debugging
    logger.debug(
        f"[ARTIST_DETAIL] Loaded {len(track_models)} tracks for {artist_model.name}"
    )

    # Hey future me - UNIFIED ALBUM VIEW from artist_discography!
    # Shows ALL albums (owned + missing) with availability badges.
    # We merge data from:
    # - artist_discography: all known albums from providers (source of truth for "what exists")
    # - soulspot_albums: local albums (for artwork paths and extra metadata)
    # - tracks: count of locally available tracks per album
    from soulspot.domain.value_objects import ArtistId
    from soulspot.infrastructure.persistence.repositories import (
        ArtistDiscographyRepository,
    )

    discography_repo = ArtistDiscographyRepository(session)
    artist_id_obj = ArtistId(artist_model.id)

    # Get complete discography (all albums from all providers)
    all_discography = await discography_repo.get_all_for_artist(artist_id_obj)
    discography_stats = await discography_repo.get_stats_for_artist(artist_id_obj)

    # Build a lookup for local albums (from soulspot_albums) by title
    local_albums_by_title: dict[str, Any] = {}
    for album in album_models:
        key = album.title.lower().strip()
        local_albums_by_title[key] = album

    # Count LOCAL tracks per album title (only tracks with file_path = downloaded files)
    # Hey future me - tracks_per_album counts TOTAL tracks in DB, local_tracks_per_album
    # counts only tracks WITH file_path (actually downloaded). This powers the "X/Y local" badge!
    tracks_per_album: dict[str, int] = {}  # Total tracks in DB
    local_tracks_per_album: dict[str, int] = {}  # Only with file_path (local files)
    for track in track_models:
        if track.album:
            key = track.album.title.lower().strip()
            tracks_per_album[key] = tracks_per_album.get(key, 0) + 1
            # Count only if track has a local file
            if track.file_path:
                local_tracks_per_album[key] = local_tracks_per_album.get(key, 0) + 1

    # Build unified albums list from LOCAL albums (soulspot_albums)
    # Hey future me - CHANGED Jan 2026!
    # Previously: Used artist_discography as primary source with fallback to soulspot_albums
    # Problem: artist_discography is never populated by current sync code!
    # Fix: Use soulspot_albums DIRECTLY - these have proper FK to tracks in soulspot_tracks
    #
    # artist_discography is now ONLY used for:
    # - "Missing Albums" discovery view (what EXISTS on provider but user doesn't OWN)
    # - NOT for displaying user's library
    albums: list[dict[str, Any]] = []
    for album in album_models:
        title_key = album.title.lower().strip()
        owned_tracks = tracks_per_album.get(title_key, 0)  # Total tracks in DB
        local_tracks = local_tracks_per_album.get(title_key, 0)  # Only with file_path
        albums.append(
            {
                "id": f"{artist_name}::{album.title}",
                "title": album.title,
                "track_count": owned_tracks,  # Total tracks in DB
                "local_tracks": local_tracks,  # Tracks with file_path (downloaded)
                "total_tracks": album.total_tracks
                if hasattr(album, "total_tracks") and album.total_tracks
                else 0,
                "year": album.release_year,
                "artwork_url": album.cover_url
                if hasattr(album, "cover_url")
                else None,
                "artwork_path": album.cover_path
                if hasattr(album, "cover_path")
                else None,
                "spotify_id": str(album.spotify_uri)
                if hasattr(album, "spotify_uri") and album.spotify_uri
                else None,
                "deezer_id": album.deezer_id
                if hasattr(album, "deezer_id")
                else None,
                "primary_type": album.primary_type
                if hasattr(album, "primary_type") and album.primary_type
                else "Album",
                "secondary_types": album.secondary_types
                if hasattr(album, "secondary_types") and album.secondary_types
                else [],
                "is_owned": True,  # If in soulspot_albums, user owns it
                "source": album.source if hasattr(album, "source") else "local",
            }
        )

    # Note: artist_discography is still queried above for stats display
    # and could be used for "Missing Albums" feature in the future

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
        "id": str(
            artist_model.id
        ),  # CRITICAL: Needed for /api/library/discovery/missing/{artist_id}
        "name": artist_model.name,
        "source": artist_model.source,  # NEW: Show source badge
        "disambiguation": artist_model.disambiguation,
        "albums": albums,
        "tracks": tracks_data,
        "track_count": len(tracks_data),
        "album_count": len(albums),
        # Hey future me - discography_stats for "X/Y albums" badge!
        # total_albums = ALL known releases from providers (artist_discography table)
        # owned_albums = how many of those the user has (is_owned=true)
        "total_albums": discography_stats.get("total", 0),
        "owned_albums": discography_stats.get("owned", 0),
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
    # Hey future me - use CASE-INSENSITIVE matching!
    # Album titles in URLs may have different casing than in DB.
    album_stmt = (
        select(AlbumModel)
        .join(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
        .where(
            func.lower(ArtistModel.name) == artist_name.lower(),
            func.lower(AlbumModel.title) == album_title.lower(),
        )
        .options(joinedload(AlbumModel.artist))
    )
    album_result = await session.execute(album_stmt)
    album_model = album_result.unique().scalar_one_or_none()

    if not album_model:
        # Hey future me - instead of 404, redirect to search!
        # This happens when user clicks a link to an album that hasn't been synced yet.
        # Better UX: redirect to search page with the album query prefilled.
        search_query = f"{artist_name} {album_title}"
        return templates.TemplateResponse(
            request,
            "error.html",
            context={
                "error_code": 404,
                "error_message": f"Album '{album_title}' by '{artist_name}' not found in library",
                "suggestion": "Try searching for it: ",
                "search_url": f"/search?q={quote(search_query)}",
                "search_query": search_query,
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

    # Hey future me - WORKER-FIRST PATTERN! (Jan 2026 design change)
    # ================================================================
    # NO on-demand API calls! Worker keeps DB up-to-date.
    # Routes ONLY read from DB - fast, consistent, no rate limits!
    #
    # If album has no tracks yet:
    # - Worker will sync them in the next cycle (TRACK_SYNC task)
    # - UI shows "Sync pending" message
    # ================================================================
    
    logger.info(
        f"[ALBUM_DETAIL] Album: '{album_title}' by '{artist_name}' | "
        f"db_tracks={len(track_models)}"
    )

    # If no tracks in DB, show empty state (Worker will sync)
    if not track_models:
        logger.info(
            f"[ALBUM_DETAIL] No tracks in DB for '{album_title}' - "
            "Worker TRACK_SYNC task will sync in background"
        )
        album_data = {
            "id": str(album_model.id),
            "title": album_title,
            "artist": artist_name,
            "artist_slug": artist_name,
            "tracks": [],
            "year": album_model.release_year
            if hasattr(album_model, "release_year")
            else None,
            "total_duration_ms": 0,
            "artwork_url": album_model.cover_url
            if hasattr(album_model, "cover_url")
            else None,
            "artwork_path": album_model.cover_path
            if hasattr(album_model, "cover_path")
            else None,
            "is_compilation": "compilation" in (album_model.secondary_types or []),
            "needs_sync": True,  # Flag to show "Sync pending" message in UI
            "source": album_model.source,
            "spotify_uri": album_model.spotify_uri,
            "deezer_id": album_model.deezer_id,
            "is_streaming_only": False,
            "is_hybrid": False,
            "is_complete": False,
            "streaming_provider": None,
            "downloaded_count": 0,
            "total_count": 0,
        }
        return templates.TemplateResponse(
            request, "library_album_detail.html", context={"album": album_data}
        )

    # Tracks exist in DB - display them directly (no API call needed!)
    logger.info(
        f"[ALBUM_DETAIL] Loaded {len(track_models)} tracks from DB for '{album_title}'"
    )

    # Convert DB tracks to template format
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
            "source": track.source,
            "spotify_id": track.spotify_uri.split(":")[-1]
            if track.spotify_uri
            else None,
            "deezer_id": track.deezer_id,
            "tidal_id": track.tidal_id,
            "is_downloaded": bool(track.file_path),
            "is_streaming": not bool(track.file_path),
        }
        for track in track_models
    ]

    # Sort by disc number, then track number, then title
    tracks_data.sort(
        key=lambda x: (x["disc_number"], x["track_number"] or 999, x["title"].lower())  # type: ignore[union-attr]
    )

    # Calculate total duration
    total_duration_ms = sum(t["duration_ms"] or 0 for t in tracks_data)  # type: ignore[misc]

    # Count downloaded vs streaming
    downloaded_count = sum(1 for t in tracks_data if t.get("is_downloaded"))
    total_count = len(tracks_data)

    # Get year and artwork from album model
    year = album_model.release_year if hasattr(album_model, "release_year") else None
    artwork_url = album_model.cover_url if hasattr(album_model, "cover_url") else None
    artwork_path = album_model.cover_path if hasattr(album_model, "cover_path") else None

    # Check if album is a compilation
    is_compilation = False
    secondary_types = getattr(album_model, "secondary_types", None) or []
    is_compilation = "compilation" in secondary_types

    album_data = {
        "id": str(album_model.id),
        "title": album_title,
        "artist": artist_name,
        "artist_slug": artist_name,
        "tracks": tracks_data,
        "year": year,
        "total_duration_ms": total_duration_ms,
        "artwork_url": artwork_url,
        "artwork_path": artwork_path,
        "is_compilation": is_compilation,
        "source": album_model.source if hasattr(album_model, "source") else "local",
        "spotify_uri": album_model.spotify_uri
        if hasattr(album_model, "spotify_uri")
        else None,
        "deezer_id": album_model.deezer_id
        if hasattr(album_model, "deezer_id")
        else None,
        "is_streaming_only": downloaded_count == 0,
        "is_hybrid": 0 < downloaded_count < total_count,
        "is_complete": downloaded_count == total_count,
        "streaming_provider": None,  # No API call, so no provider
        "downloaded_count": downloaded_count,
        "total_count": total_count,
        "needs_sync": False,  # We have tracks!
    }

    return templates.TemplateResponse(
        request, "library_album_detail.html", context={"album": album_data}
    )


# =============================================================================
# METADATA EDITOR ROUTE
# =============================================================================


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
            "album_artist": track_model.album.album_artist
            if track_model.album
            else None,
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
