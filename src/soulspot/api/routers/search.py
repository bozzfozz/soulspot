# AI-Model: Copilot
"""Unified Search API with Multi-Provider Aggregation (Spotify + Deezer + Soulseek).

Hey future me - this router implements the MULTI-SERVICE AGGREGATION PRINCIPLE:
1. Query ALL enabled providers (Spotify + Deezer)
2. Aggregate results into unified list
3. Deduplicate by normalized keys (artist_name, title, ISRC)
4. Tag each result with its source provider
5. Graceful fallback if one provider fails

CRITICAL: Deezer search requires NO AUTH! If Spotify isn't connected, we can
still search via Deezer. This is the whole point of multi-provider support.

The Search Page UI uses these endpoints to show combined results from all providers.
Soulseek endpoints remain separate since they search the P2P network for actual files.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_deezer_plugin,
    get_slskd_client,
    get_spotify_plugin_optional,
)
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.observability.logger_template import (
    end_operation,
    start_operation,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================


# =============================================================================
# RESPONSE MODELS - Multi-Provider Support
# Hey future me - all models now have 'source' field to indicate origin provider
# =============================================================================


class ArtistSearchResult(BaseModel):
    """Unified artist search result from any provider."""

    id: str = Field(..., description="Provider-specific artist ID")
    name: str = Field(..., description="Artist name")
    popularity: int = Field(0, description="Popularity score (0-100)")
    followers: int = Field(0, description="Number of followers")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    image_url: str | None = Field(None, description="Artist profile image URL")
    external_url: str | None = Field(
        None, description="URL to artist on source provider"
    )
    source: str = Field("spotify", description="Source provider: spotify, deezer")


class AlbumSearchResult(BaseModel):
    """Unified album search result from any provider."""

    id: str = Field(..., description="Provider-specific album ID")
    name: str = Field(..., description="Album name")
    artist_name: str = Field(..., description="Primary artist name")
    artist_id: str | None = Field(None, description="Primary artist ID")
    release_date: str | None = Field(None, description="Release date")
    album_type: str | None = Field(None, description="album, single, compilation")
    total_tracks: int = Field(0, description="Number of tracks")
    image_url: str | None = Field(None, description="Album artwork URL")
    external_url: str | None = Field(
        None, description="URL to album on source provider"
    )
    source: str = Field("spotify", description="Source provider: spotify, deezer")


class TrackSearchResult(BaseModel):
    """Unified track search result from any provider."""

    id: str = Field(..., description="Provider-specific track ID")
    name: str = Field(..., description="Track name")
    artist_name: str = Field(..., description="Primary artist name")
    artist_id: str | None = Field(None, description="Primary artist ID")
    album_name: str | None = Field(None, description="Album name")
    album_id: str | None = Field(None, description="Album ID")
    duration_ms: int = Field(0, description="Track duration in milliseconds")
    popularity: int = Field(0, description="Popularity score (0-100)")
    preview_url: str | None = Field(None, description="30s preview URL")
    external_url: str | None = Field(
        None, description="URL to track on source provider"
    )
    isrc: str | None = Field(None, description="ISRC code for cross-provider matching")
    source: str = Field("spotify", description="Source provider: spotify, deezer")


class UnifiedSearchResponse(BaseModel):
    """Multi-provider search response with aggregated results."""

    artists: list[ArtistSearchResult] = Field(default_factory=list)
    albums: list[AlbumSearchResult] = Field(default_factory=list)
    tracks: list[TrackSearchResult] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")
    sources_queried: list[str] = Field(
        default_factory=list, description="Providers that were queried"
    )
    source_counts: dict[str, int] = Field(
        default_factory=dict, description="Results per provider"
    )


# Legacy alias for backwards compatibility
SpotifySearchResponse = UnifiedSearchResponse
SpotifyArtistResult = ArtistSearchResult
SpotifyAlbumResult = AlbumSearchResult
SpotifyTrackResult = TrackSearchResult


class SoulseekFileResult(BaseModel):
    """Soulseek file search result."""

    username: str = Field(..., description="Uploader username")
    filename: str = Field(..., description="Full file path")
    size: int = Field(0, description="File size in bytes")
    bitrate: int = Field(0, description="Audio bitrate (kbps)")
    length: int = Field(0, description="Track length in seconds")
    quality: int = Field(0, description="Quality score")


class SoulseekSearchResponse(BaseModel):
    """Soulseek search response."""

    files: list[SoulseekFileResult] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")
    total: int = Field(0, description="Total results found")


# =============================================================================
# MULTI-PROVIDER SEARCH ENDPOINTS
# Hey future me - These implement the Multi-Service Aggregation Principle:
# 1. Query ALL enabled providers (Spotify + Deezer)
# 2. Aggregate results, deduplicate by normalized name
# 3. Tag each result with source, graceful fallback on errors
# =============================================================================


@router.get("/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=25, description="Number of results per type"),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> UnifiedSearchResponse:
    """Unified search across all types (artists, albums, tracks) and all providers.

    Hey future me - This is the ONE endpoint the search page should use!
    Searches for artists, albums AND tracks from Spotify AND Deezer in one call.
    Deduplicates results within each type. Perfect for a search page that shows
    combined results. Limit is per type (10 artists + 10 albums + 10 tracks).

    Args:
        query: Search query
        limit: Maximum results per type (artists/albums/tracks), default 10

    Returns:
        Combined artists, albums, tracks from all providers
    """
    start_time, operation_id = start_operation(
        logger,
        "api.search.unified_search",
        query=query,
        limit=limit,
    )

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)

    artists: list[ArtistSearchResult] = []
    albums: list[AlbumSearchResult] = []
    tracks: list[TrackSearchResult] = []

    seen_artist_names: set[str] = set()
    seen_album_keys: set[str] = set()
    seen_track_isrcs: set[str] = set()
    seen_track_keys: set[str] = set()

    sources_queried: list[str] = []
    source_counts: dict[str, int] = {"deezer": 0, "spotify": 0}

    async def search_deezer() -> None:
        """Search Deezer for all types."""
        nonlocal artists, albums, tracks, sources_queried
        deezer_enabled = await settings.is_provider_enabled("deezer")
        if not deezer_enabled:
            return

        deezer_added = False

        # Artists
        if deezer_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
            try:
                result = await deezer_plugin.search_artists(query, limit=limit)
                for dto in result.items:
                    norm_name = _normalize_name(dto.name)
                    if norm_name not in seen_artist_names:
                        seen_artist_names.add(norm_name)
                        external_url = dto.external_urls.get("deezer", "")
                        artists.append(
                            ArtistSearchResult(
                                id=dto.deezer_id or "",
                                name=dto.name,
                                popularity=dto.popularity or 0,
                                followers=dto.followers or 0,
                                genres=dto.genres or [],
                                image_url=dto.image.url,  # ArtistDTO.image is ImageRef
                                external_url=external_url,
                                source="deezer",
                            )
                        )
                        source_counts["deezer"] += 1
                        deezer_added = True
            except Exception as e:
                logger.warning(f"Deezer artist search failed: {e}")

        # Albums
        if deezer_plugin.can_use(PluginCapability.SEARCH_ALBUMS):
            try:
                result = await deezer_plugin.search_albums(query, limit=limit)
                for dto in result.items:
                    key = f"{_normalize_name(dto.artist_name or '')}|{_normalize_name(dto.title)}"
                    if key not in seen_album_keys:
                        seen_album_keys.add(key)
                        external_url = dto.external_urls.get("deezer", "")
                        albums.append(
                            AlbumSearchResult(
                                id=dto.deezer_id or "",
                                name=dto.title,
                                artist_name=dto.artist_name or "Unknown",
                                artist_id=dto.artist_deezer_id,
                                release_date=dto.release_date,
                                album_type=dto.album_type,
                                total_tracks=dto.total_tracks or 0,
                                image_url=dto.cover.url,  # AlbumDTO.cover is ImageRef
                                external_url=external_url,
                                source="deezer",
                            )
                        )
                        source_counts["deezer"] += 1
                        deezer_added = True
            except Exception as e:
                logger.warning(f"Deezer album search failed: {e}")

        # Tracks
        if deezer_plugin.can_use(PluginCapability.SEARCH_TRACKS):
            try:
                result = await deezer_plugin.search_tracks(query, limit=limit)
                for dto in result.items:
                    isrc = dto.isrc
                    if isrc and isrc in seen_track_isrcs:
                        continue
                    key = f"{_normalize_name(dto.artist_name or '')}|{_normalize_name(dto.title)}"
                    if key in seen_track_keys:
                        continue
                    if isrc:
                        seen_track_isrcs.add(isrc)
                    seen_track_keys.add(key)
                    external_url = dto.external_urls.get("deezer", "")
                    tracks.append(
                        TrackSearchResult(
                            id=dto.deezer_id or "",
                            name=dto.title,
                            artist_name=dto.artist_name or "Unknown",
                            artist_id=dto.artist_deezer_id,
                            album_name=dto.album_name,
                            album_id=dto.album_deezer_id,
                            duration_ms=dto.duration_ms or 0,
                            popularity=dto.popularity or 0,
                            preview_url=dto.preview_url,
                            external_url=external_url,
                            isrc=isrc,
                            source="deezer",
                        )
                    )
                    source_counts["deezer"] += 1
                    deezer_added = True
            except Exception as e:
                logger.warning(f"Deezer track search failed: {e}")

        if deezer_added and "deezer" not in sources_queried:
            sources_queried.append("deezer")

    async def search_spotify() -> None:
        """Search Spotify for all types."""
        nonlocal artists, albums, tracks, sources_queried

        # MULTI-SERVICE: spotify_plugin can be None if not authenticated
        if spotify_plugin is None:
            logger.debug("Spotify plugin not available (not authenticated)")
            return

        spotify_enabled = await settings.is_provider_enabled("spotify")
        if not spotify_enabled:
            return

        spotify_added = False

        # Artists
        if spotify_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
            try:
                result = await spotify_plugin.search_artist(query, limit=limit)
                for dto in result.items:
                    norm_name = _normalize_name(dto.name)
                    if norm_name not in seen_artist_names:
                        seen_artist_names.add(norm_name)
                        external_url = dto.external_urls.get("spotify", "")
                        artists.append(
                            ArtistSearchResult(
                                id=dto.spotify_id or "",
                                name=dto.name,
                                popularity=dto.popularity or 0,
                                followers=dto.followers or 0,
                                genres=dto.genres or [],
                                image_url=dto.image.url,  # ArtistDTO.image is ImageRef
                                external_url=external_url,
                                source="spotify",
                            )
                        )
                        source_counts["spotify"] += 1
                        spotify_added = True
            except Exception as e:
                logger.warning(f"Spotify artist search failed: {e}")

        # Albums
        if spotify_plugin.can_use(PluginCapability.SEARCH_ALBUMS):
            try:
                result = await spotify_plugin.search_album(query, limit=limit)
                for dto in result.items:
                    key = f"{_normalize_name(dto.artist_name or '')}|{_normalize_name(dto.title)}"
                    if key not in seen_album_keys:
                        seen_album_keys.add(key)
                        external_url = dto.external_urls.get("spotify", "")
                        albums.append(
                            AlbumSearchResult(
                                id=dto.spotify_id or "",
                                name=dto.title,
                                artist_name=dto.artist_name or "Unknown",
                                artist_id=dto.artist_spotify_id,
                                release_date=dto.release_date,
                                album_type=dto.album_type,
                                total_tracks=dto.total_tracks or 0,
                                image_url=dto.cover.url,  # AlbumDTO.cover is ImageRef
                                external_url=external_url,
                                source="spotify",
                            )
                        )
                        source_counts["spotify"] += 1
                        spotify_added = True
            except Exception as e:
                logger.warning(f"Spotify album search failed: {e}")

        # Tracks
        if spotify_plugin.can_use(PluginCapability.SEARCH_TRACKS):
            try:
                result = await spotify_plugin.search_track(query, limit=limit)
                for dto in result.items:
                    isrc = dto.isrc
                    if isrc and isrc in seen_track_isrcs:
                        continue
                    key = f"{_normalize_name(dto.artist_name or '')}|{_normalize_name(dto.title)}"
                    if key in seen_track_keys:
                        continue
                    if isrc:
                        seen_track_isrcs.add(isrc)
                    seen_track_keys.add(key)
                    external_url = dto.external_urls.get("spotify", "")
                    tracks.append(
                        TrackSearchResult(
                            id=dto.spotify_id or "",
                            name=dto.title,
                            artist_name=dto.artist_name or "Unknown",
                            artist_id=dto.artist_spotify_id,
                            album_name=dto.album_name,
                            album_id=dto.album_spotify_id,
                            duration_ms=dto.duration_ms or 0,
                            popularity=dto.popularity or 0,
                            preview_url=dto.preview_url,
                            external_url=external_url,
                            isrc=isrc,
                            source="spotify",
                        )
                    )
                    source_counts["spotify"] += 1
                    spotify_added = True
            except Exception as e:
                logger.warning(f"Spotify track search failed: {e}")

        if spotify_added and "spotify" not in sources_queried:
            sources_queried.append("spotify")

    # Run both searches in parallel
    await asyncio.gather(search_deezer(), search_spotify())

    # Error if no providers available
    if not sources_queried:
        end_operation(logger, "api.search.unified_search", start_time, operation_id, success=False)
        raise HTTPException(
            status_code=503,
            detail="No search providers available. Enable Deezer or connect Spotify.",
        )

    # Sort by popularity
    artists.sort(key=lambda x: x.popularity, reverse=True)
    albums.sort(key=lambda x: x.total_tracks, reverse=True)
    tracks.sort(key=lambda x: x.popularity, reverse=True)

    response = UnifiedSearchResponse(
        artists=artists,
        albums=albums,
        tracks=tracks,
        query=query,
        sources_queried=sources_queried,
        source_counts=source_counts,
    )
    end_operation(
        logger,
        "api.search.unified_search",
        start_time,
        operation_id,
        success=True,
        artists_count=len(artists),
        albums_count=len(albums),
        tracks_count=len(tracks),
        sources=sources_queried,
        source_counts=source_counts,
    )
    return response


def _normalize_name(name: str) -> str:
    """Normalize name for deduplication. Lowercase, strip whitespace."""
    return name.strip().lower()


@router.get("/spotify/artists", response_model=UnifiedSearchResponse)
async def search_spotify_artists(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> UnifiedSearchResponse:
    """Search for artists using Multi-Provider Aggregation (Spotify + Deezer).

    Hey future me - this implements Multi-Service Aggregation Principle:
    - Query Spotify (if authenticated) AND Deezer (no auth needed!)
    - Aggregate results, deduplicate by normalized artist name
    - Fallback: If Spotify not available, Deezer alone works fine

    Args:
        query: Search query (artist name)
        limit: Maximum number of results per provider

    Returns:
        Unified list of artists from all providers with source tags
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    artists: list[ArtistSearchResult] = []
    seen_names: set[str] = set()
    sources_queried: list[str] = []
    source_counts: dict[str, int] = {}

    # 1. Deezer Search (NO AUTH NEEDED! Priority because always available)
    deezer_enabled = await settings.is_provider_enabled("deezer")
    if deezer_enabled and deezer_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
        try:
            deezer_result = await deezer_plugin.search_artists(query, limit=limit)
            sources_queried.append("deezer")
            deezer_count = 0
            for artist_dto in deezer_result.items:
                norm_name = _normalize_name(artist_dto.name)
                if norm_name not in seen_names:
                    seen_names.add(norm_name)
                    external_url = artist_dto.external_urls.get("deezer", "")
                    artists.append(
                        ArtistSearchResult(
                            id=artist_dto.deezer_id or "",
                            name=artist_dto.name,
                            popularity=artist_dto.popularity or 0,
                            followers=artist_dto.followers or 0,
                            genres=artist_dto.genres or [],
                            image_url=artist_dto.image.url,  # ArtistDTO.image is ImageRef
                            external_url=external_url,
                            source="deezer",
                        )
                    )
                    deezer_count += 1
            source_counts["deezer"] = deezer_count
            logger.debug(f"Deezer artist search: {deezer_count} results for '{query}'")
        except Exception as e:
            logger.warning(f"Deezer artist search failed (graceful fallback): {e}")

    # 2. Spotify Search (requires auth) - MULTI-SERVICE: spotify_plugin can be None
    spotify_enabled = await settings.is_provider_enabled("spotify")
    if (
        spotify_plugin is not None
        and spotify_enabled
        and spotify_plugin.can_use(PluginCapability.SEARCH_ARTISTS)
    ):
        try:
            spotify_result = await spotify_plugin.search_artist(query, limit=limit)
            sources_queried.append("spotify")
            spotify_count = 0
            for artist_dto in spotify_result.items:
                norm_name = _normalize_name(artist_dto.name)
                if norm_name not in seen_names:
                    seen_names.add(norm_name)
                    external_url = artist_dto.external_urls.get("spotify", "")
                    artists.append(
                        ArtistSearchResult(
                            id=artist_dto.spotify_id or "",
                            name=artist_dto.name,
                            popularity=artist_dto.popularity or 0,
                            followers=artist_dto.followers or 0,
                            genres=artist_dto.genres or [],
                            image_url=artist_dto.image.url,  # ArtistDTO.image is ImageRef
                            external_url=external_url,
                            source="spotify",
                        )
                    )
                    spotify_count += 1
            source_counts["spotify"] = spotify_count
            logger.debug(
                f"Spotify artist search: {spotify_count} results for '{query}'"
            )
        except Exception as e:
            logger.warning(f"Spotify artist search failed (graceful fallback): {e}")

    # 3. Error if NO providers available
    if not sources_queried:
        raise HTTPException(
            status_code=503,
            detail="No search providers available. Enable Deezer or connect Spotify.",
        )

    # Sort by popularity (higher first)
    artists.sort(key=lambda x: x.popularity, reverse=True)

    return UnifiedSearchResponse(
        artists=artists,
        query=query,
        sources_queried=sources_queried,
        source_counts=source_counts,
    )


@router.get("/spotify/tracks", response_model=UnifiedSearchResponse)
async def search_spotify_tracks(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> UnifiedSearchResponse:
    """Search for tracks using Multi-Provider Aggregation (Spotify + Deezer).

    Hey future me - ISRC is the holy grail for deduplication here! Same track
    from different providers will have the same ISRC. We use that for dedup,
    then fall back to normalized (artist + title) for tracks without ISRC.

    Args:
        query: Search query (track name, "artist - track")
        limit: Maximum number of results per provider

    Returns:
        Unified list of tracks from all providers with source tags
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    tracks: list[TrackSearchResult] = []
    seen_isrcs: set[str] = set()
    seen_keys: set[str] = set()  # Fallback: artist|title
    sources_queried: list[str] = []
    source_counts: dict[str, int] = {}

    # 1. Deezer Search (NO AUTH NEEDED!)
    deezer_enabled = await settings.is_provider_enabled("deezer")
    if deezer_enabled and deezer_plugin.can_use(PluginCapability.SEARCH_TRACKS):
        try:
            deezer_result = await deezer_plugin.search_tracks(query, limit=limit)
            sources_queried.append("deezer")
            deezer_count = 0
            for track_dto in deezer_result.items:
                # Dedup by ISRC first, then by artist|title
                isrc = track_dto.isrc
                if isrc and isrc in seen_isrcs:
                    continue
                norm_key = f"{_normalize_name(track_dto.artist_name or '')}|{_normalize_name(track_dto.title)}"
                if norm_key in seen_keys:
                    continue
                if isrc:
                    seen_isrcs.add(isrc)
                seen_keys.add(norm_key)

                external_url = track_dto.external_urls.get("deezer", "")
                tracks.append(
                    TrackSearchResult(
                        id=track_dto.deezer_id or "",
                        name=track_dto.title,
                        artist_name=track_dto.artist_name or "Unknown",
                        artist_id=track_dto.artist_deezer_id,
                        album_name=track_dto.album_name,
                        album_id=track_dto.album_deezer_id,
                        duration_ms=track_dto.duration_ms or 0,
                        popularity=track_dto.popularity or 0,
                        preview_url=track_dto.preview_url,
                        external_url=external_url,
                        isrc=isrc,
                        source="deezer",
                    )
                )
                deezer_count += 1
            source_counts["deezer"] = deezer_count
            logger.debug(f"Deezer track search: {deezer_count} results for '{query}'")
        except Exception as e:
            logger.warning(f"Deezer track search failed (graceful fallback): {e}")

    # 2. Spotify Search (requires auth) - MULTI-SERVICE: spotify_plugin can be None
    spotify_enabled = await settings.is_provider_enabled("spotify")
    if (
        spotify_plugin is not None
        and spotify_enabled
        and spotify_plugin.can_use(PluginCapability.SEARCH_TRACKS)
    ):
        try:
            spotify_result = await spotify_plugin.search_track(query, limit=limit)
            sources_queried.append("spotify")
            spotify_count = 0
            for track_dto in spotify_result.items:
                # Dedup by ISRC first, then by artist|title
                isrc = track_dto.isrc
                if isrc and isrc in seen_isrcs:
                    continue
                norm_key = f"{_normalize_name(track_dto.artist_name or '')}|{_normalize_name(track_dto.title)}"
                if norm_key in seen_keys:
                    continue
                if isrc:
                    seen_isrcs.add(isrc)
                seen_keys.add(norm_key)

                external_url = track_dto.external_urls.get("spotify", "")
                tracks.append(
                    TrackSearchResult(
                        id=track_dto.spotify_id or "",
                        name=track_dto.title,
                        artist_name=track_dto.artist_name or "Unknown",
                        artist_id=track_dto.artist_spotify_id,
                        album_name=track_dto.album_name,
                        album_id=track_dto.album_spotify_id,
                        duration_ms=track_dto.duration_ms or 0,
                        popularity=track_dto.popularity or 0,
                        preview_url=track_dto.preview_url,
                        external_url=external_url,
                        isrc=isrc,
                        source="spotify",
                    )
                )
                spotify_count += 1
            source_counts["spotify"] = spotify_count
            logger.debug(f"Spotify track search: {spotify_count} results for '{query}'")
        except Exception as e:
            logger.warning(f"Spotify track search failed (graceful fallback): {e}")

    # 3. Error if NO providers available
    if not sources_queried:
        raise HTTPException(
            status_code=503,
            detail="No search providers available. Enable Deezer or connect Spotify.",
        )

    # Sort by popularity (higher first)
    tracks.sort(key=lambda x: x.popularity, reverse=True)

    return UnifiedSearchResponse(
        tracks=tracks,
        query=query,
        sources_queried=sources_queried,
        source_counts=source_counts,
    )


@router.get("/spotify/albums", response_model=UnifiedSearchResponse)
async def search_spotify_albums(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> UnifiedSearchResponse:
    """Search for albums using Multi-Provider Aggregation (Spotify + Deezer).

    Hey future me - Deduplication by normalized (artist + album title) since
    there's no universal album ID across providers. Release dates can vary
    slightly between providers, so we use title matching.

    Args:
        query: Search query (album name, "artist - album")
        limit: Maximum number of results per provider

    Returns:
        Unified list of albums from all providers with source tags
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    albums: list[AlbumSearchResult] = []
    seen_keys: set[str] = set()  # artist|title
    sources_queried: list[str] = []
    source_counts: dict[str, int] = {}

    # 1. Deezer Search (NO AUTH NEEDED!)
    deezer_enabled = await settings.is_provider_enabled("deezer")
    if deezer_enabled and deezer_plugin.can_use(PluginCapability.SEARCH_ALBUMS):
        try:
            deezer_result = await deezer_plugin.search_albums(query, limit=limit)
            sources_queried.append("deezer")
            deezer_count = 0
            for album_dto in deezer_result.items:
                norm_key = f"{_normalize_name(album_dto.artist_name or '')}|{_normalize_name(album_dto.title)}"
                if norm_key in seen_keys:
                    continue
                seen_keys.add(norm_key)

                external_url = album_dto.external_urls.get("deezer", "")
                albums.append(
                    AlbumSearchResult(
                        id=album_dto.deezer_id or "",
                        name=album_dto.title,
                        artist_name=album_dto.artist_name or "Unknown",
                        artist_id=album_dto.artist_deezer_id,
                        release_date=album_dto.release_date,
                        album_type=album_dto.album_type,
                        total_tracks=album_dto.total_tracks or 0,
                        image_url=album_dto.cover.url,  # AlbumDTO.cover is ImageRef
                        external_url=external_url,
                        source="deezer",
                    )
                )
                deezer_count += 1
            source_counts["deezer"] = deezer_count
            logger.debug(f"Deezer album search: {deezer_count} results for '{query}'")
        except Exception as e:
            logger.warning(f"Deezer album search failed (graceful fallback): {e}")

    # 2. Spotify Search (requires auth) - MULTI-SERVICE: spotify_plugin can be None
    spotify_enabled = await settings.is_provider_enabled("spotify")
    if (
        spotify_plugin is not None
        and spotify_enabled
        and spotify_plugin.can_use(PluginCapability.SEARCH_ALBUMS)
    ):
        try:
            spotify_result = await spotify_plugin.search_album(query, limit=limit)
            sources_queried.append("spotify")
            spotify_count = 0
            for album_dto in spotify_result.items:
                norm_key = f"{_normalize_name(album_dto.artist_name or '')}|{_normalize_name(album_dto.title)}"
                if norm_key in seen_keys:
                    continue
                seen_keys.add(norm_key)

                external_url = album_dto.external_urls.get("spotify", "")
                albums.append(
                    AlbumSearchResult(
                        id=album_dto.spotify_id or "",
                        name=album_dto.title,
                        artist_name=album_dto.artist_name or "Unknown",
                        artist_id=album_dto.artist_spotify_id,
                        release_date=album_dto.release_date,
                        album_type=album_dto.album_type,
                        total_tracks=album_dto.total_tracks or 0,
                        image_url=album_dto.cover.url,  # AlbumDTO.cover is ImageRef
                        external_url=external_url,
                        source="spotify",
                    )
                )
                spotify_count += 1
            source_counts["spotify"] = spotify_count
            logger.debug(f"Spotify album search: {spotify_count} results for '{query}'")
        except Exception as e:
            logger.warning(f"Spotify album search failed (graceful fallback): {e}")

    # 3. Error if NO providers available
    if not sources_queried:
        raise HTTPException(
            status_code=503,
            detail="No search providers available. Enable Deezer or connect Spotify.",
        )

    # Sort by total_tracks (albums with more content first)
    albums.sort(key=lambda x: x.total_tracks, reverse=True)

    return UnifiedSearchResponse(
        albums=albums,
        query=query,
        sources_queried=sources_queried,
        source_counts=source_counts,
    )


# =============================================================================
# SOULSEEK SEARCH ENDPOINTS
# =============================================================================


@router.post("/soulseek", response_model=SoulseekSearchResponse)
async def search_soulseek(
    query: str = Query(..., min_length=1, description="Search query"),
    timeout: int = Query(30, ge=5, le=120, description="Search timeout in seconds"),
    slskd_client: SlskdClient = Depends(get_slskd_client),
) -> SoulseekSearchResponse:
    """Search for files on Soulseek P2P network.

    Searches the distributed Soulseek network for downloadable files.
    Results include file quality info (bitrate, size, format).

    Note: Soulseek search is asynchronous - results trickle in over time.
    Higher timeout = more results but longer wait.

    Args:
        query: Search query ("Artist - Track" format works best)
        timeout: How long to wait for results (5-120 seconds)
        slskd_client: slskd client instance

    Returns:
        List of matching files with quality info
    """
    try:
        results = await slskd_client.search(query, timeout=timeout)

        files = [
            SoulseekFileResult(
                username=r["username"],
                filename=r["filename"],
                size=r.get("size", 0),
                bitrate=r.get("bitrate", 0),
                length=r.get("length", 0),
                quality=r.get("quality", 0),
            )
            for r in results
        ]

        return SoulseekSearchResponse(
            files=files,
            query=query,
            total=len(files),
        )

    except Exception as e:
        from soulspot.infrastructure.observability.log_messages import LogMessages

        logger.error(
            LogMessages.connection_failed(
                service="slskd",
                target="Soulseek Search",
                error=str(e),
                hint="Check if slskd container is running: docker ps | grep slskd",
            ),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Soulseek search failed: {str(e)}",
        ) from e


# =============================================================================
# COMBINED/UTILITY ENDPOINTS
# =============================================================================


class SearchSuggestion(BaseModel):
    """Search autocomplete suggestion."""

    text: str = Field(..., description="Suggestion text")
    type: str = Field(..., description="artist, album, or track")
    id: str | None = Field(None, description="Provider ID if available")
    source: str = Field("spotify", description="Source provider")


@router.get("/suggestions", response_model=list[SearchSuggestion])
async def get_search_suggestions(
    query: str = Query(..., min_length=2, description="Partial search query"),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
    deezer_plugin: "DeezerPlugin" = Depends(get_deezer_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> list[SearchSuggestion]:
    """Get search autocomplete suggestions from all providers.

    Hey future me - Multi-Provider Aggregation for autocomplete too!
    Deezer needs no auth, so suggestions ALWAYS work even without Spotify.
    We limit each provider to 3 artists + 5 tracks, deduplicate by name.

    Args:
        query: Partial search query (minimum 2 characters)

    Returns:
        List of suggestions with type indicators and source tags
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    suggestions: list[SearchSuggestion] = []
    seen_texts: set[str] = set()

    # 1. Deezer Suggestions (NO AUTH NEEDED!)
    deezer_enabled = await settings.is_provider_enabled("deezer")
    if deezer_enabled and deezer_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
        try:
            # Artists from Deezer
            deezer_artists = await deezer_plugin.search_artists(query, limit=3)
            for artist_dto in deezer_artists.items[:3]:
                norm_text = _normalize_name(artist_dto.name)
                if norm_text not in seen_texts:
                    seen_texts.add(norm_text)
                    suggestions.append(
                        SearchSuggestion(
                            text=artist_dto.name,
                            type="artist",
                            id=artist_dto.deezer_id,
                            source="deezer",
                        )
                    )

            # Tracks from Deezer
            deezer_tracks = await deezer_plugin.search_tracks(query, limit=5)
            for track_dto in deezer_tracks.items[:5]:
                artist_name = track_dto.artist_name or ""
                text = (
                    f"{track_dto.title} - {artist_name}"
                    if artist_name
                    else track_dto.title
                )
                norm_text = _normalize_name(text)
                if norm_text not in seen_texts:
                    seen_texts.add(norm_text)
                    suggestions.append(
                        SearchSuggestion(
                            text=text,
                            type="track",
                            id=track_dto.deezer_id,
                            source="deezer",
                        )
                    )
        except Exception as e:
            logger.warning(f"Deezer suggestions failed (graceful fallback): {e}")

    # 2. Spotify Suggestions (requires auth)
    spotify_enabled = await settings.is_provider_enabled("spotify")
    if (
        spotify_enabled
        and spotify_plugin is not None
        and spotify_plugin.can_use(PluginCapability.SEARCH_ARTISTS)
    ):
        try:
            # Artists from Spotify
            spotify_artists = await spotify_plugin.search_artist(query, limit=3)
            for artist_dto in spotify_artists.items[:3]:
                norm_text = _normalize_name(artist_dto.name)
                if norm_text not in seen_texts:
                    seen_texts.add(norm_text)
                    suggestions.append(
                        SearchSuggestion(
                            text=artist_dto.name,
                            type="artist",
                            id=artist_dto.spotify_id,
                            source="spotify",
                        )
                    )

            # Tracks from Spotify
            spotify_tracks = await spotify_plugin.search_track(query, limit=5)
            for track_dto in spotify_tracks.items[:5]:
                artist_name = track_dto.artist_name or ""
                text = (
                    f"{track_dto.title} - {artist_name}"
                    if artist_name
                    else track_dto.title
                )
                norm_text = _normalize_name(text)
                if norm_text not in seen_texts:
                    seen_texts.add(norm_text)
                    suggestions.append(
                        SearchSuggestion(
                            text=text,
                            type="track",
                            id=track_dto.spotify_id,
                            source="spotify",
                        )
                    )
        except Exception as e:
            logger.warning(f"Spotify suggestions failed (graceful fallback): {e}")

    return suggestions
