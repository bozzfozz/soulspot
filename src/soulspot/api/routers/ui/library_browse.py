"""Library browse UI routes - Artists, Albums, Tracks, Compilations.

Hey future me - this module contains the library browsing pages:
- Artists list (/library/artists)
- Albums list (/library/albums)  
- Tracks list (/library/tracks)
- Compilations list (/library/compilations)
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soulspot.api.dependencies import get_db_session, get_track_repository
from soulspot.api.routers.ui._shared import templates
from soulspot.domain.value_objects.album_types import VARIOUS_ARTISTS_PATTERNS
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
        .outerjoin(
            total_track_count_subq, ArtistModel.id == total_track_count_subq.c.artist_id
        )
        .outerjoin(
            local_track_count_subq, ArtistModel.id == local_track_count_subq.c.artist_id
        )
        .outerjoin(
            total_album_count_subq, ArtistModel.id == total_album_count_subq.c.artist_id
        )
        .outerjoin(
            local_album_count_subq, ArtistModel.id == local_album_count_subq.c.artist_id
        )
    )

    # Exclude Various Artists patterns from artist view
    # Hey future me - VA/Compilations have their own section, don't clutter artist list!
    stmt = stmt.where(~func.lower(ArtistModel.name).in_(list(VARIOUS_ARTISTS_PATTERNS)))

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

    # ==========================================================================
    # AUTO-FETCH: Background image fetch via AutoFetchService (Application Layer)
    # Hey future me - business logic lives in Service, not in Route!
    # ==========================================================================
    if artists_without_image > 0:
        try:
            from soulspot.application.services import AutoFetchService
            from soulspot.config import get_settings

            app_settings = get_settings()
            auto_fetch = AutoFetchService(session, app_settings)
            result = await auto_fetch.fetch_missing_artist_images(limit=10)
            repaired = result.get("repaired", 0)
            if repaired > 0:
                artists_without_image = max(0, artists_without_image - repaired)
        except Exception as e:
            # Fail silently - this is a background optimization
            logger.debug(f"[AUTO_FETCH_ARTISTS] Background fetch failed: {e}")

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
        .outerjoin(
            total_track_count_subq, AlbumModel.id == total_track_count_subq.c.album_id
        )
        .outerjoin(
            local_track_count_subq, AlbumModel.id == local_track_count_subq.c.album_id
        )
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
        select(func.count(AlbumModel.id)).where(
            AlbumModel.source.in_(["local", "hybrid"])
        )
    )
    count_spotify = await session.execute(
        select(func.count(AlbumModel.id)).where(
            AlbumModel.source.in_(["spotify", "hybrid"])
        )
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

    # ==========================================================================
    # AUTO-FETCH: Background cover fetch via AutoFetchService (Application Layer)
    # Hey future me - business logic lives in Service, not in Route!
    # ==========================================================================
    albums_without_cover = sum(1 for a in albums if not a["artwork_url"])
    if albums_without_cover > 0:
        try:
            from soulspot.application.services import AutoFetchService
            from soulspot.config import get_settings

            app_settings = get_settings()
            auto_fetch = AutoFetchService(session, app_settings)
            await auto_fetch.fetch_missing_album_covers(limit=10)
        except Exception as e:
            # Fail silently - this is a background optimization
            logger.debug(f"[AUTO_FETCH_ALBUMS] Background fetch failed: {e}")

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
            func.lower(
                func.coalesce(ArtistModel.name, "zzz")
            ),  # Artists first, null last
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
