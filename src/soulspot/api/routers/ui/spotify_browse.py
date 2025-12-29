"""Spotify/Browse UI routes - New Releases, Discover, Deprecated Routes.

Hey future me - this module contains Spotify browsing and discovery pages:
- Browse new releases (/browse/new-releases)
- Discover similar artists (/spotify/discover)
- Deprecated Spotify-specific routes (redirect to unified library)
"""

import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.responses import RedirectResponse
from urllib.parse import quote

from soulspot.api.dependencies import (
    get_db_session,
    get_deezer_plugin,
    get_spotify_plugin_optional,
)
from soulspot.api.routers.ui._shared import templates
from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/spotify/artists", response_class=HTMLResponse)
async def spotify_artists_page(request: Request) -> Any:
    """DEPRECATED: Redirect to unified library artists view with Spotify filter.

    Hey future me - this Spotify-specific route is deprecated (Dec 2025)!
    Use /library/artists?source=spotify for multi-provider unified view.
    """
    return RedirectResponse(url="/library/artists?source=spotify", status_code=301)


@router.get("/browse/new-releases", response_class=HTMLResponse)
async def browse_new_releases_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    days: int = Query(default=90, ge=7, le=365, description="Days to look back"),
    include_compilations: bool = Query(
        default=True, description="Include compilations"
    ),
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
            logger.debug(
                f"New Releases: Using cached data ({cache_info['age_seconds']}s old)"
            )
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
                external_url = (
                    album.external_urls.get(album.source_service, "")
                    if album.external_urls
                    else ""
                )
                album_id = album.deezer_id or album.spotify_id or ""

            all_releases.append(
                {
                    "id": album_id,
                    "name": album.title,
                    "artist_name": album.artist_name,
                    "artist_id": album.artist_deezer_id
                    or album.artist_spotify_id
                    or "",
                    "artwork_url": album.artwork_url,
                    "release_date": album.release_date,
                    "album_type": album.album_type or "album",
                    "total_tracks": album.total_tracks,
                    "external_url": external_url,
                    "source": album.source_service,
                }
            )

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
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Discover Similar Artists page - MULTI-PROVIDER!

    Hey future me - REFACTORED to work WITHOUT Spotify auth (Dec 2025)!

    Removed dependency on SpotifySyncService - now uses direct DB access.
    This allows the page to work even if:
    - Spotify is not configured
    - User hasn't authenticated with Spotify
    - Only Deezer is available

    Architecture:
        Route → Direct DB Query for artists
              → DiscoverService (Multi-Provider)
                     ↓
        [SpotifyPlugin, DeezerPlugin] (parallel fetch)
                     ↓
        Aggregate & Deduplicate by name
                     ↓
        DiscoverResult → Template

    Deezer advantage: NO AUTH NEEDED for related artists!
    Falls back to Deezer if Spotify unavailable.
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.discover_service import DiscoverService
    from soulspot.infrastructure.persistence.repositories import ArtistRepository

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

    # Get LOCAL artists only (from library scan) - not Spotify synced!
    # Hey future me - we want discovery based on user's LOCAL music collection!
    # This makes sense: "Find artists similar to the music I actually own"
    artist_repo = ArtistRepository(session)
    # Filter by source='local' or 'hybrid' (hybrid = local + streaming match)
    # These are used as SEEDS for discovery (find similar artists to these)
    local_artists = await artist_repo.list_by_source(
        sources=["local", "hybrid"], limit=1000
    )

    logger.info(
        f"Discover page: Found {len(local_artists) if local_artists else 0} LOCAL artists in DB"
    )

    if not local_artists:
        return templates.TemplateResponse(
            request,
            "discover.html",
            context={
                "discoveries": [],
                "based_on_count": 0,
                "total_discoveries": 0,
                "source_counts": {},
                "error": "No local artists found. Scan your music library first! (Settings → Library Scanner)",
            },
        )

    # Pick random LOCAL artists to base discovery on (max 5 to avoid rate limits)
    sample_size = min(5, len(local_artists))
    sample_artists = random.sample(local_artists, sample_size)

    logger.info(
        f"Discover page (Multi-Provider): Sampling {sample_size} LOCAL artists: "
        f"{[a.name for a in sample_artists]}"
    )

    # Get artist IDs/names for filtering (exclude artists we already have LOCALLY)
    # IMPORTANT: Only exclude LOCAL/HYBRID artists - not pure Spotify-synced ones!
    # User can add artists to local library even if they follow them on Spotify.
    # Hey future me - Artist.spotify_uri is a SpotifyUri VALUE OBJECT, not a string!
    # Use .resource_id to get the ID part from "spotify:artist:ID" -> "ID"
    local_artist_ids: set[str] = set()  # LOCAL/HYBRID only
    local_artist_names: set[str] = set()  # LOCAL/HYBRID only

    # Use the same local_artists for exclusion - only exclude what user has locally!
    for a in local_artists:
        if a.spotify_uri:
            # SpotifyUri is a value object with .resource_id property
            local_artist_ids.add(a.spotify_uri.resource_id)
        if a.deezer_id:
            local_artist_ids.add(a.deezer_id)
        if a.name:
            local_artist_names.add(a.name.lower().strip())

    logger.debug(
        f"Discover filter: {len(local_artist_names)} LOCAL artist names to exclude"
    )

    # Hey future me - Also get ALL artists in DB (any source) for "is_in_db" badge!
    # This lets UI show if an artist exists in DB (even if only spotify-synced).
    # We do a direct query to get only the IDs we need (more efficient than loading full entities).
    stmt = select(ArtistModel.spotify_uri, ArtistModel.deezer_id, ArtistModel.name)
    db_result = await session.execute(stmt)
    all_db_rows = db_result.all()

    all_db_artist_ids: set[str] = set()
    all_db_artist_names: set[str] = set()
    for row in all_db_rows:
        if row.spotify_uri:
            # spotify_uri is "spotify:artist:ID" → extract ID
            parts = row.spotify_uri.split(":")
            if len(parts) == 3:
                all_db_artist_ids.add(parts[2])
        if row.deezer_id:
            all_db_artist_ids.add(row.deezer_id)
        if row.name:
            all_db_artist_names.add(row.name.lower().strip())

    logger.debug(
        f"Discover: {len(all_db_artist_names)} total artists in DB (for is_in_db badge)"
    )

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
            # Extract Spotify ID from URI if available
            # Artist Entity has spotify_uri (SpotifyUri object), not spotify_id!
            spotify_id: str | None = None
            if artist.spotify_uri:
                # SpotifyUri.value is "spotify:artist:ID" → extract ID
                spotify_id = str(artist.spotify_uri).split(":")[-1]

            # Get Deezer ID directly from entity (string or None)
            deezer_id: str | None = artist.deezer_id

            logger.debug(
                f"Discovery for {artist.name}: spotify_id={spotify_id}, deezer_id={deezer_id}"
            )

            result = await service.discover_similar_artists(
                seed_artist_name=artist.name,
                seed_artist_spotify_id=spotify_id,
                seed_artist_deezer_id=deezer_id,
                limit=20,
                enabled_providers=enabled_providers,
            )

            # Aggregate source counts
            for src, count in result.source_counts.items():
                source_counts[src] = source_counts.get(src, 0) + count

            for discovered in result.artists:
                d_name_norm = discovered.name.lower().strip()

                # Skip if already in LOCAL library (source='local' or 'hybrid')
                # These artists are already in user's local collection!
                # Hey future me - Debug logging to understand filter misses!
                should_skip = False
                skip_reason = ""

                if d_name_norm in local_artist_names:
                    should_skip = True
                    skip_reason = f"name match: '{d_name_norm}'"
                elif (
                    discovered.spotify_id
                    and discovered.spotify_id in local_artist_ids
                ):
                    should_skip = True
                    skip_reason = f"spotify_id match: '{discovered.spotify_id}'"
                elif discovered.deezer_id and discovered.deezer_id in local_artist_ids:
                    should_skip = True
                    skip_reason = f"deezer_id match: '{discovered.deezer_id}'"

                if should_skip:
                    logger.debug(
                        f"Discover: Skipping '{discovered.name}' - {skip_reason}"
                    )
                    continue

                # Skip duplicates in this batch
                key = discovered.spotify_id or discovered.deezer_id or d_name_norm
                if key in seen_ids:
                    continue
                seen_ids.add(key)

                # Hey future me - Check if artist exists in DB AT ALL (any source)!
                # If artist has source='spotify' (followed but not local), user can still
                # "Add to Library" which will upgrade them to 'hybrid'.
                # This flag helps UI show appropriate button/badge.
                is_in_db = (
                    d_name_norm in all_db_artist_names
                    or (
                        discovered.spotify_id
                        and discovered.spotify_id in all_db_artist_ids
                    )
                    or (discovered.deezer_id and discovered.deezer_id in all_db_artist_ids)
                )

                discoveries.append(
                    {
                        "spotify_id": discovered.spotify_id,
                        "deezer_id": discovered.deezer_id,
                        "name": discovered.name,
                        "image_url": discovered.image_url,
                        "genres": (discovered.genres or [])[:3],
                        "popularity": discovered.popularity or 0,
                        "based_on": artist.name,
                        "source": discovered.source_service,
                        "is_in_db": is_in_db,  # True if artist exists in DB (any source)
                    }
                )

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
        return RedirectResponse(
            url=f"/library/albums/{quote(album_key)}", status_code=301
        )
    else:
        # Album not in library yet - redirect to library albums list
        return RedirectResponse(url="/library/albums", status_code=302)


# Hey future me, DEPRECATED route! Users should use /spotify/artists instead for auto-sync.
# Returns HTTP 410 Gone (permanently removed) with helpful redirect message.
# This prevents 404 confusion and guides users to the new location.
@router.get(
    "/automation/followed-artists", response_class=JSONResponse, status_code=410
)
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
