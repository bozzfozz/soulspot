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

    # Hey future me - AUTO-SYNC albums + tracks using MULTI-SERVICE PATTERN!
    # If artist has NO albums in DB, fetch from available services:
    # 1. Try Spotify (if authenticated + artist has spotify_uri)
    # 2. Fallback to Deezer (NO AUTH NEEDED - public API)
    #
    # This enables album browsing EVEN WITHOUT Spotify login!
    # Deezer can fetch albums by artist name for any artist.
    #
    # Dec 2025 UPDATE: Now uses sync_artist_discography_complete(include_tracks=True)
    # which fetches BOTH albums AND tracks - so clicking an album shows tracks immediately!
    if not album_models:
        try:
            # MULTI-SERVICE PATTERN: Try available services
            from soulspot.application.services.followed_artists_service import (
                FollowedArtistsService,
            )
            from soulspot.application.services.token_manager import (
                DatabaseTokenManager,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
            from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

            # 1. Try to get Spotify token (optional - service works without it)
            spotify_plugin = None
            access_token = None
            if hasattr(request.app.state, "db_token_manager"):
                db_token_manager: DatabaseTokenManager = (
                    request.app.state.db_token_manager
                )
                access_token = await db_token_manager.get_token_for_background()

            if access_token:
                app_settings = get_settings()
                spotify_client = SpotifyClient(app_settings.spotify)
                spotify_plugin = SpotifyPlugin(
                    client=spotify_client, access_token=access_token
                )
                logger.debug(
                    f"Spotify plugin available for album sync of {artist_model.name}"
                )
            else:
                logger.debug(
                    f"No Spotify token - using Deezer only for {artist_model.name}"
                )

            # 2. Deezer is ALWAYS available (no auth needed!)
            deezer_plugin = DeezerPlugin()

            # 3. Create service with available plugins (spotify_plugin can be None!)
            followed_service = FollowedArtistsService(
                session,
                spotify_plugin=spotify_plugin,  # May be None - service handles this
                deezer_plugin=deezer_plugin,  # Always available
            )

            # Sync albums AND tracks using available services
            # Hey future me - This is the KEY CHANGE! We now use sync_artist_discography_complete
            # with include_tracks=True so ALL album tracks are fetched and stored in DB.
            # When user clicks an album, tracks load from DB (no API call needed)!
            sync_stats = await followed_service.sync_artist_discography_complete(
                artist_id=str(artist_model.id),
                include_tracks=True,  # CRITICAL: Fetch tracks for ALL albums!
            )
            await session.commit()  # Commit new albums + tracks

            logger.info(
                f"[ARTIST_DETAIL_SYNC] Synced discography for {artist_model.name}: "
                f"albums={sync_stats.get('albums_added', 0)}, "
                f"tracks={sync_stats.get('tracks_added', 0)}, "
                f"source={sync_stats.get('source', 'none')}"
            )

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
                    hint=f"Artist: {artist_model.name}",
                )
            )
            # Continue anyway - show empty albums list

    # Step 3: Get tracks for these albums (for LOCAL/HYBRID artists)
    # Hey future me - This runs AFTER sync so it includes freshly fetched tracks!
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

    # Build unified albums list from discography
    albums: list[dict[str, Any]] = []
    for disc_entry in all_discography:
        title_key = disc_entry.title.lower().strip()
        local_album = local_albums_by_title.get(title_key)
        owned_tracks = tracks_per_album.get(title_key, 0)  # Total in DB
        local_tracks = local_tracks_per_album.get(title_key, 0)  # Only with file_path

        album_data = {
            "id": f"{artist_name}::{disc_entry.title}",
            "title": disc_entry.title,
            "track_count": owned_tracks,  # Total tracks in DB for this album
            "local_tracks": local_tracks,  # Tracks with file_path (downloaded)
            "total_tracks": disc_entry.total_tracks or 0,
            "year": int(disc_entry.release_date[:4])
            if disc_entry.release_date and len(disc_entry.release_date) >= 4
            else None,
            "artwork_url": disc_entry.cover_url,
            "artwork_path": local_album.cover_path
            if local_album and hasattr(local_album, "cover_path")
            else None,
            "spotify_id": str(disc_entry.spotify_uri)
            if disc_entry.spotify_uri
            else None,
            "deezer_id": disc_entry.deezer_id,
            "primary_type": disc_entry.album_type.title()
            if disc_entry.album_type
            else "Album",
            "secondary_types": [],  # Discography doesn't track secondary types
            "is_owned": disc_entry.is_owned,
            "source": disc_entry.source,
        }
        albums.append(album_data)

    # If no discography entries, fall back to local albums (backward compat)
    if not albums and album_models:
        for album in album_models:
            title_key = album.title.lower().strip()
            owned_tracks = tracks_per_album.get(title_key, 0)
            local_tracks = local_tracks_per_album.get(title_key, 0)
            albums.append(
                {
                    "id": f"{artist_name}::{album.title}",
                    "title": album.title,
                    "track_count": owned_tracks,  # Total tracks in DB
                    "local_tracks": local_tracks,  # Tracks with file_path
                    "total_tracks": album.total_tracks
                    if hasattr(album, "total_tracks")
                    else None,
                    "year": album.release_year,
                    "artwork_url": album.cover_url
                    if hasattr(album, "cover_url")
                    else None,
                    "artwork_path": album.cover_path
                    if hasattr(album, "cover_path")
                    else None,
                    "spotify_id": album.spotify_uri
                    if hasattr(album, "spotify_uri")
                    else None,
                    "deezer_id": album.deezer_id
                    if hasattr(album, "deezer_id")
                    else None,
                    "primary_type": album.primary_type
                    if hasattr(album, "primary_type")
                    else "album",
                    "secondary_types": album.secondary_types
                    if hasattr(album, "secondary_types")
                    else [],
                    "is_owned": True,  # If in local albums, user owns it
                    "source": album.source if hasattr(album, "source") else "local",
                }
            )

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

    # Hey future me - AUTO-FETCH TRACKS FROM PROVIDER! (PARALLEL MULTI-SOURCE!)
    # If album exists in DB but has no local tracks, we fetch the track list
    # from available providers IN PARALLEL so users see tracks FAST!
    #
    # Dec 2025 Update: Now uses asyncio.gather() for parallel fetching!
    # All providers are queried simultaneously, first successful result wins.
    # Priority if multiple succeed: Deezer by ID > Deezer Search > Spotify
    #
    # This reduces latency from ~2-3s (sequential) to ~0.5-1s (parallel)!
    streaming_tracks: list[dict[str, Any]] = []
    provider_used = None
    discovered_deezer_id: str | None = None  # To save if we find one via search

    # Hey future me - ALWAYS fetch streaming tracks!
    # This enables track merging to show which tracks are downloaded vs available.
    # Even if we have local tracks, we want the FULL tracklist from the provider.
    # If no provider ID exists, we'll search by artist+album name.

    # DEBUG: Log album info for tracking
    logger.info(
        f"[ALBUM_DETAIL] Album: '{album_title}' by '{artist_name}' | "
        f"deezer_id={album_model.deezer_id}, spotify_uri={album_model.spotify_uri}, "
        f"local_tracks={len(track_models)}"
    )

    if True:  # Always try to fetch streaming tracks
        from soulspot.api.dependencies import (
            get_credentials_service,
            get_spotify_plugin_optional,
        )
        from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

        # Define async fetchers for each source
        async def fetch_deezer_by_id() -> tuple[str, list[dict[str, Any]], str | None]:
            """Fetch tracks from Deezer using album ID."""
            logger.info(
                f"[FETCH_DEEZER_ID] Attempting with deezer_id={album_model.deezer_id}"
            )
            if not album_model.deezer_id:
                logger.info("[FETCH_DEEZER_ID] Skipped - no deezer_id")
                return ("deezer_id", [], None)
            try:
                deezer_plugin = DeezerPlugin()
                response = await deezer_plugin.get_album_tracks(album_model.deezer_id)
                logger.info(
                    f"[FETCH_DEEZER_ID] Got {len(response.items)} tracks from Deezer"
                )
                tracks = [
                    {
                        "id": f"deezer:{track.deezer_id}",
                        "title": track.title,
                        "artist": track.artist_name,
                        "album": album_title,
                        "track_number": track.track_number,
                        "disc_number": track.disc_number,
                        "duration_ms": track.duration_ms,
                        "file_path": None,
                        "is_broken": False,
                        "source": "deezer",
                        "spotify_id": None,
                        "deezer_id": track.deezer_id,
                        "tidal_id": None,
                        "is_downloaded": False,
                        "is_streaming": True,
                    }
                    for track in response.items
                ]
                return ("deezer_id", tracks, None)
            except Exception as e:
                logger.warning(f"[FETCH_DEEZER_ID] Failed: {e}")
                return ("deezer_id", [], None)

        async def fetch_deezer_by_search() -> tuple[
            str, list[dict[str, Any]], str | None
        ]:
            """Fetch tracks from Deezer by searching artist + album."""
            # Skip if we already have deezer_id (fetch_deezer_by_id will handle it)
            if album_model.deezer_id:
                logger.info("[FETCH_DEEZER_SEARCH] Skipped - already have deezer_id")
                return ("deezer_search", [], None)
            try:
                deezer_plugin = DeezerPlugin()
                search_query = f"{artist_name} {album_title}"
                logger.info(f"[FETCH_DEEZER_SEARCH] Searching: '{search_query}'")
                search_results = await deezer_plugin.search(
                    query=search_query,
                    types=["album"],
                    limit=5,
                )
                logger.info(
                    f"[FETCH_DEEZER_SEARCH] Got {len(search_results.albums)} albums from search"
                )

                # Find best matching album
                matched_album = None
                for album in search_results.albums:
                    logger.info(
                        f"[FETCH_DEEZER_SEARCH] Checking album: '{album.title}' (deezer_id={album.deezer_id})"
                    )
                    if album.title.lower().strip() == album_title.lower().strip():
                        matched_album = album
                        logger.info(
                            f"[FETCH_DEEZER_SEARCH] EXACT MATCH: '{album.title}'"
                        )
                        break
                    if album_title.lower() in album.title.lower():
                        matched_album = album
                        logger.info(
                            f"[FETCH_DEEZER_SEARCH] PARTIAL MATCH: '{album.title}'"
                        )

                if matched_album and matched_album.deezer_id:
                    logger.info(
                        f"[FETCH_DEEZER_SEARCH] Fetching tracks for matched album: deezer_id={matched_album.deezer_id}"
                    )
                    response = await deezer_plugin.get_album_tracks(
                        matched_album.deezer_id
                    )
                    logger.info(
                        f"[FETCH_DEEZER_SEARCH] Got {len(response.items)} tracks"
                    )
                    tracks = [
                        {
                            "id": f"deezer:{track.deezer_id}",
                            "title": track.title,
                            "artist": track.artist_name,
                            "album": album_title,
                            "track_number": track.track_number,
                            "disc_number": track.disc_number,
                            "duration_ms": track.duration_ms,
                            "file_path": None,
                            "is_broken": False,
                            "source": "deezer",
                            "spotify_id": None,
                            "deezer_id": track.deezer_id,
                            "tidal_id": None,
                            "is_downloaded": False,
                            "is_streaming": True,
                        }
                        for track in response.items
                    ]
                    # Return discovered deezer_id to save later
                    return ("deezer_search", tracks, matched_album.deezer_id)
                logger.info("[FETCH_DEEZER_SEARCH] No matching album found")
                return ("deezer_search", [], None)
            except Exception as e:
                logger.warning(f"[FETCH_DEEZER_SEARCH] Failed: {e}")
                return ("deezer_search", [], None)

        async def fetch_spotify() -> tuple[str, list[dict[str, Any]], str | None]:
            """Fetch tracks from Spotify (requires auth)."""
            logger.info(
                f"[FETCH_SPOTIFY] Attempting with spotify_uri={album_model.spotify_uri}"
            )
            if not album_model.spotify_uri:
                logger.info("[FETCH_SPOTIFY] Skipped - no spotify_uri")
                return ("spotify", [], None)
            try:
                # Hey future me - get_credentials_service needs BOTH session AND settings!
                # Calling it with just session leaves settings as an unresolved Depends object.
                # We get settings via get_settings() which is synchronous.
                settings = get_settings()
                credentials_service = await get_credentials_service(session, settings)
                spotify_plugin = await get_spotify_plugin_optional(
                    request, credentials_service
                )

                if not spotify_plugin or not spotify_plugin.is_authenticated:
                    logger.info("[FETCH_SPOTIFY] Skipped - not authenticated")
                    return ("spotify", [], None)

                spotify_album_id = album_model.spotify_uri.split(":")[-1]
                logger.info(
                    f"[FETCH_SPOTIFY] Fetching tracks for album_id={spotify_album_id}"
                )
                response = await spotify_plugin.get_album_tracks(spotify_album_id)
                logger.info(f"[FETCH_SPOTIFY] Got {len(response.items)} tracks")
                tracks = [
                    {
                        "id": f"spotify:{track.spotify_id}",
                        "title": track.title,
                        "artist": track.artist_name,
                        "album": album_title,
                        "track_number": track.track_number,
                        "disc_number": track.disc_number,
                        "duration_ms": track.duration_ms,
                        "file_path": None,
                        "is_broken": False,
                        "source": "spotify",
                        "spotify_id": track.spotify_id,
                        "deezer_id": None,
                        "tidal_id": None,
                        "is_downloaded": False,
                        "is_streaming": True,
                    }
                    for track in response.items
                ]
                return ("spotify", tracks, None)
            except Exception as e:
                logger.warning(f"[FETCH_SPOTIFY] Failed: {e}")
                return ("spotify", [], None)

        # Run ALL fetchers in parallel!
        # Hey future me - this is the magic! All providers query simultaneously.
        # asyncio.gather returns results in same order as input tasks.
        logger.info("[ALBUM_DETAIL] Running parallel fetchers...")
        results = await asyncio.gather(
            fetch_deezer_by_id(),
            fetch_deezer_by_search(),
            fetch_spotify(),
            return_exceptions=True,  # Don't fail if one raises
        )

        # Process results in priority order: deezer_id > deezer_search > spotify
        # Use first successful result (has tracks)
        priority_order = ["deezer_id", "deezer_search", "spotify"]
        results_by_source: dict[str, tuple[list[dict[str, Any]], str | None]] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[ALBUM_DETAIL] Fetcher exception: {r}")
                continue
            source, tracks, found_deezer_id = r
            results_by_source[source] = (tracks, found_deezer_id)
            logger.info(f"[ALBUM_DETAIL] Result from {source}: {len(tracks)} tracks")

        for source in priority_order:
            if source in results_by_source:
                tracks, found_deezer_id = results_by_source[source]
                if tracks:
                    streaming_tracks = tracks
                    provider_used = "deezer" if source.startswith("deezer") else source
                    discovered_deezer_id = found_deezer_id
                    logger.info(
                        f"Fetched {len(streaming_tracks)} tracks from {source} for album '{album_title}'"
                    )
                    break

        # Save discovered deezer_id if we found one via search
        if discovered_deezer_id and not album_model.deezer_id:
            try:
                album_model.deezer_id = discovered_deezer_id
                await session.commit()
                logger.debug(
                    f"Saved discovered deezer_id {discovered_deezer_id} for album '{album_title}'"
                )
            except Exception:
                pass  # Don't fail if we can't save

        # ==========================================================================
        # AUTO-SAVE: Persist streaming tracks via AutoFetchService (Application Layer)
        # Hey future me - business logic lives in Service, not in Route!
        # ==========================================================================
        if streaming_tracks and provider_used:
            try:
                from soulspot.application.services import AutoFetchService

                app_settings = get_settings()
                auto_fetch = AutoFetchService(session, app_settings)
                await auto_fetch.save_streaming_tracks_to_db(
                    album_id=str(album_model.id),
                    artist_id=str(album_model.artist_id),
                    tracks=streaming_tracks,
                    source=provider_used,
                )
            except Exception as e:
                logger.warning(f"[AUTO_SAVE_TRACKS] Failed to save tracks: {e}")
                # Don't fail the page load if saving fails

    # If no tracks found (neither local nor streaming), show empty album with sync prompt
    logger.info(
        f"[ALBUM_DETAIL] Final state: local_tracks={len(track_models)}, "
        f"streaming_tracks={len(streaming_tracks)}, provider={provider_used}"
    )
    if not track_models and not streaming_tracks:
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
            "needs_sync": True,  # Flag to show "Sync required" message
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

    # Hey future me - MERGE streaming tracks with local tracks!
    # This shows which tracks are downloaded AND which are available for download.
    # Uses track_number + disc_number for matching (more reliable than title fuzzy match).

    # Helper to normalize title for fuzzy matching
    def normalize_title(title: str) -> str:
        """Normalize title for comparison (lowercase, strip punctuation)."""
        return re.sub(r"[^\w\s]", "", title.lower()).strip()

    # Build lookup from local tracks by (disc, track_number) AND normalized title
    local_by_position: dict[tuple[int, int], Any] = {}
    local_by_title: dict[str, Any] = {}

    for track in track_models:
        disc = (
            track.disc_number
            if hasattr(track, "disc_number") and track.disc_number
            else 1
        )
        track_num = track.track_number or 0
        if track_num > 0:
            local_by_position[(disc, track_num)] = track
        local_by_title[normalize_title(track.title)] = track

    # If we have streaming tracks, merge with local info
    if streaming_tracks:
        merged_tracks = []
        matched_local_ids: set[Any] = set()

        for streaming_track in streaming_tracks:
            disc = streaming_track.get("disc_number") or 1
            track_num = streaming_track.get("track_number") or 0

            # Try to find matching local track
            local_track = None

            # 1. Match by position (disc + track_number)
            if track_num > 0:
                local_track = local_by_position.get((disc, track_num))

            # 2. Fallback: Match by normalized title
            if not local_track:
                norm_title = normalize_title(streaming_track["title"])
                local_track = local_by_title.get(norm_title)

            if local_track:
                # Found matching local track - merge info
                matched_local_ids.add(local_track.id)
                merged_tracks.append(
                    {
                        "id": local_track.id,
                        "title": local_track.title,
                        "artist": local_track.artist.name
                        if local_track.artist
                        else streaming_track.get("artist", "Unknown"),
                        "album": album_title,
                        "track_number": track_num or local_track.track_number,
                        "disc_number": disc,
                        "duration_ms": local_track.duration_ms
                        or streaming_track.get("duration_ms"),
                        "file_path": local_track.file_path,
                        "is_broken": local_track.is_broken
                        if hasattr(local_track, "is_broken")
                        else False,
                        "source": local_track.source
                        if hasattr(local_track, "source")
                        else "local",
                        "spotify_id": streaming_track.get("spotify_id")
                        or (
                            local_track.spotify_uri.split(":")[-1]
                            if local_track.spotify_uri
                            else None
                        ),
                        "deezer_id": streaming_track.get("deezer_id")
                        or local_track.deezer_id,
                        "tidal_id": local_track.tidal_id
                        if hasattr(local_track, "tidal_id")
                        else None,
                        "is_downloaded": bool(local_track.file_path),
                        "is_streaming": False,  # We have local file!
                    }
                )
            else:
                # No local match - show as streaming-only (available for download)
                merged_tracks.append(
                    {
                        **streaming_track,
                        "is_downloaded": False,
                        "is_streaming": True,
                    }
                )

        # Add any local tracks that weren't matched (orphan local files)
        for track in track_models:
            if track.id not in matched_local_ids:
                merged_tracks.append(
                    {
                        "id": track.id,
                        "title": track.title,
                        "artist": track.artist.name
                        if track.artist
                        else "Unknown Artist",
                        "album": album_title,
                        "track_number": track.track_number,
                        "disc_number": track.disc_number
                        if hasattr(track, "disc_number")
                        else 1,
                        "duration_ms": track.duration_ms,
                        "file_path": track.file_path,
                        "is_broken": track.is_broken
                        if hasattr(track, "is_broken")
                        else False,
                        "source": "local",
                        "spotify_id": track.spotify_uri.split(":")[-1]
                        if track.spotify_uri
                        else None,
                        "deezer_id": track.deezer_id
                        if hasattr(track, "deezer_id")
                        else None,
                        "tidal_id": track.tidal_id
                        if hasattr(track, "tidal_id")
                        else None,
                        "is_downloaded": bool(track.file_path),
                        "is_streaming": False,
                    }
                )

        # Sort merged tracks
        merged_tracks.sort(
            key=lambda x: (
                x.get("disc_number") or 1,
                x.get("track_number") or 999,
                (x.get("title") or "").lower(),
            )
        )

        # Calculate stats
        total_duration_ms = sum(t.get("duration_ms") or 0 for t in merged_tracks)
        downloaded_count = sum(1 for t in merged_tracks if t.get("is_downloaded"))
        total_count = len(merged_tracks)

        album_data = {
            "id": str(album_model.id),
            "title": album_title,
            "artist": artist_name,
            "artist_slug": artist_name,
            "tracks": merged_tracks,
            "year": album_model.release_year
            if hasattr(album_model, "release_year")
            else None,
            "total_duration_ms": total_duration_ms,
            "artwork_url": album_model.cover_url
            if hasattr(album_model, "cover_url")
            else None,
            "artwork_path": album_model.cover_path
            if hasattr(album_model, "cover_path")
            else None,
            "is_compilation": "compilation" in (album_model.secondary_types or []),
            "needs_sync": False,
            "source": album_model.source,
            "spotify_uri": album_model.spotify_uri,
            "deezer_id": album_model.deezer_id,
            "is_streaming_only": downloaded_count == 0,  # All streaming, none local
            "is_hybrid": 0
            < downloaded_count
            < total_count,  # Some downloaded, some not
            "is_complete": downloaded_count == total_count,  # All downloaded
            "streaming_provider": provider_used,
            "downloaded_count": downloaded_count,
            "total_count": total_count,
        }
        return templates.TemplateResponse(
            request, "library_album_detail.html", context={"album": album_data}
        )

    # Convert tracks to template format (local tracks from DB, no streaming available)
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
            "spotify_id": track.spotify_uri.split(":")[-1]
            if track.spotify_uri
            else None,
            "deezer_id": track.deezer_id,
            "tidal_id": track.tidal_id,
            "is_downloaded": bool(track.file_path),
            "is_streaming": not bool(track.file_path),  # True if no local file
        }
        for track in track_models
    ]

    # Sort by disc number, then track number, then title
    tracks_data.sort(
        key=lambda x: (x["disc_number"], x["track_number"] or 999, x["title"].lower())  # type: ignore[union-attr]
    )

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
        "source": album_model.source if hasattr(album_model, "source") else "local",
        "spotify_uri": album_model.spotify_uri
        if hasattr(album_model, "spotify_uri")
        else None,
        "deezer_id": album_model.deezer_id
        if hasattr(album_model, "deezer_id")
        else None,
        "is_streaming_only": False,  # We have local tracks
        "is_hybrid": False,  # No streaming tracks fetched
        "is_complete": True,  # All local (no comparison to streaming possible)
        "streaming_provider": None,
        "downloaded_count": len(tracks_data),
        "total_count": len(tracks_data),
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
