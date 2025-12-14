# AI-Model: Copilot
"""Unified Search API endpoints for Spotify and Soulseek.

Hey future me - this router provides a UNIFIED search experience across:
1. Spotify (artists, albums, tracks) - metadata from Spotify's catalog
2. Soulseek (files) - downloadable files from P2P network

The Search Page UI uses these endpoints to show combined results. Spotify results
give us metadata (artist images, popularity, etc.) while Soulseek gives us actual
downloadable files. The frontend can then:
- Show Spotify artist → user clicks "Follow" → syncs to our DB
- Show Spotify track → user clicks "Download" → searches Soulseek for that track

Single-user architecture: Uses SpotifyPlugin (token management built-in) so any
device can search without per-browser sessions.
"""

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_slskd_client,
    get_spotify_plugin,
)
from soulspot.infrastructure.integrations.slskd_client import SlskdClient

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class SpotifyArtistResult(BaseModel):
    """Spotify artist search result."""

    id: str = Field(..., description="Spotify artist ID")
    name: str = Field(..., description="Artist name")
    popularity: int = Field(0, description="Popularity score (0-100)")
    followers: int = Field(0, description="Number of followers")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    image_url: str | None = Field(None, description="Artist profile image URL")
    spotify_url: str | None = Field(None, description="Spotify profile URL")


class SpotifyAlbumResult(BaseModel):
    """Spotify album search result."""

    id: str = Field(..., description="Spotify album ID")
    name: str = Field(..., description="Album name")
    artist_name: str = Field(..., description="Primary artist name")
    artist_id: str | None = Field(None, description="Primary artist ID")
    release_date: str | None = Field(None, description="Release date")
    album_type: str | None = Field(None, description="album, single, compilation")
    total_tracks: int = Field(0, description="Number of tracks")
    image_url: str | None = Field(None, description="Album artwork URL")
    spotify_url: str | None = Field(None, description="Spotify album URL")


class SpotifyTrackResult(BaseModel):
    """Spotify track search result."""

    id: str = Field(..., description="Spotify track ID")
    name: str = Field(..., description="Track name")
    artist_name: str = Field(..., description="Primary artist name")
    artist_id: str | None = Field(None, description="Primary artist ID")
    album_name: str | None = Field(None, description="Album name")
    album_id: str | None = Field(None, description="Album ID")
    duration_ms: int = Field(0, description="Track duration in milliseconds")
    popularity: int = Field(0, description="Popularity score (0-100)")
    preview_url: str | None = Field(None, description="30s preview URL")
    spotify_url: str | None = Field(None, description="Spotify track URL")
    isrc: str | None = Field(None, description="ISRC code for matching")


class SpotifySearchResponse(BaseModel):
    """Combined Spotify search response."""

    artists: list[SpotifyArtistResult] = Field(default_factory=list)
    albums: list[SpotifyAlbumResult] = Field(default_factory=list)
    tracks: list[SpotifyTrackResult] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")


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
# SPOTIFY SEARCH ENDPOINTS
# =============================================================================


@router.get("/spotify/artists", response_model=SpotifySearchResponse)
async def search_spotify_artists(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> SpotifySearchResponse:
    """Search for artists on Spotify.

    Returns artists matching the query with images, genres, and popularity.
    Use the returned artist_id for follow/unfollow operations.

    Args:
        query: Search query (artist name)
        limit: Maximum number of results (1-50)
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        List of matching artists with metadata
    """
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    if not await settings.is_provider_enabled("spotify"):
        raise HTTPException(status_code=503, detail="Spotify provider is disabled")
    # can_use() checks capability + auth in one call
    if not spotify_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
        raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

    try:
        # search_artist returns PaginatedResponse[ArtistDTO]
        result = await spotify_plugin.search_artist(query, limit=limit)

        artists = []
        for artist_dto in result.items:
            # Get Spotify URL from external_urls dict
            spotify_url = artist_dto.external_urls.get("spotify", "")

            artists.append(
                SpotifyArtistResult(
                    id=artist_dto.spotify_id or "",
                    name=artist_dto.name,
                    popularity=artist_dto.popularity or 0,
                    followers=artist_dto.followers or 0,
                    genres=artist_dto.genres or [],
                    image_url=artist_dto.image_url,
                    spotify_url=spotify_url,
                )
            )

        return SpotifySearchResponse(artists=artists, query=query)

    except Exception as e:
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.error(
            LogMessages.sync_failed(
                entity="Artist Search",
                source="Spotify",
                error=str(e),
                hint="Check Spotify API status and authentication"
            ),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Spotify search failed: {str(e)}",
        ) from e


@router.get("/spotify/tracks", response_model=SpotifySearchResponse)
async def search_spotify_tracks(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> SpotifySearchResponse:
    """Search for tracks on Spotify.

    Returns tracks matching the query with artist info, duration, and ISRC.
    ISRC codes can be used to find the same track on Soulseek.

    Args:
        query: Search query (track name, "artist - track", ISRC)
        limit: Maximum number of results (1-50)
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        List of matching tracks with metadata
    """
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    if not await settings.is_provider_enabled("spotify"):
        raise HTTPException(status_code=503, detail="Spotify provider is disabled")
    if not spotify_plugin.can_use(PluginCapability.SEARCH_TRACKS):
        raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

    try:
        # search_track returns PaginatedResponse[TrackDTO]
        result = await spotify_plugin.search_track(query, limit=limit)

        tracks = []
        for track_dto in result.items:
            # Extract artist info from DTO
            artist_name = track_dto.artist_name or "Unknown"
            artist_id = track_dto.artist_spotify_id

            # Get Spotify URL from external_urls dict
            spotify_url = track_dto.external_urls.get("spotify", "")

            tracks.append(
                SpotifyTrackResult(
                    id=track_dto.spotify_id or "",
                    name=track_dto.title,
                    artist_name=artist_name,
                    artist_id=artist_id,
                    album_name=track_dto.album_name,
                    album_id=track_dto.album_spotify_id,
                    duration_ms=track_dto.duration_ms or 0,
                    popularity=track_dto.popularity or 0,
                    preview_url=track_dto.preview_url,
                    spotify_url=spotify_url,
                    isrc=track_dto.isrc,
                )
            )

        return SpotifySearchResponse(tracks=tracks, query=query)

    except Exception as e:
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.error(
            LogMessages.sync_failed(
                entity="Track Search",
                source="Spotify",
                error=str(e),
                hint="Check Spotify API status and authentication"
            ),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Spotify search failed: {str(e)}",
        ) from e


@router.get("/spotify/albums", response_model=SpotifySearchResponse)
async def search_spotify_albums(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> SpotifySearchResponse:
    """Search for albums on Spotify.

    Returns albums matching the query with artwork and track count.
    Use album_id to fetch full track list for download.

    Args:
        query: Search query (album name, "artist - album")
        limit: Maximum number of results (1-50)
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        List of matching albums with metadata
    """
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    if not await settings.is_provider_enabled("spotify"):
        raise HTTPException(status_code=503, detail="Spotify provider is disabled")
    if not spotify_plugin.can_use(PluginCapability.SEARCH_ALBUMS):
        raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

    try:
        # search_album returns PaginatedResponse[AlbumDTO]
        result = await spotify_plugin.search_album(query, limit=limit)

        albums = []
        for album_dto in result.items:
            # Extract artist info from DTO
            artist_name = album_dto.artist_name or "Unknown"
            artist_id = album_dto.artist_spotify_id

            # Get Spotify URL from external_urls dict
            spotify_url = album_dto.external_urls.get("spotify", "")

            albums.append(
                SpotifyAlbumResult(
                    id=album_dto.spotify_id or "",
                    name=album_dto.title,
                    artist_name=artist_name,
                    artist_id=artist_id,
                    release_date=album_dto.release_date,
                    album_type=album_dto.album_type,
                    total_tracks=album_dto.total_tracks or 0,
                    image_url=album_dto.artwork_url,
                    spotify_url=spotify_url,
                )
            )

        return SpotifySearchResponse(albums=albums, query=query)

    except Exception as e:
        logger.error(f"Spotify album search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Spotify search failed: {str(e)}",
        ) from e


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
                hint="Check if slskd container is running: docker ps | grep slskd"
            ),
            exc_info=True
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
    id: str | None = Field(None, description="Spotify ID if available")


@router.get("/suggestions", response_model=list[SearchSuggestion])
async def get_search_suggestions(
    query: str = Query(..., min_length=2, description="Partial search query"),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> list[SearchSuggestion]:
    """Get search autocomplete suggestions from Spotify.

    Returns quick suggestions for autocomplete dropdown. Combines
    top artist, album, and track matches.

    Args:
        query: Partial search query (minimum 2 characters)
        spotify_plugin: SpotifyPlugin handles token management internally

    Returns:
        List of suggestions with type indicators
    """
    # Provider + Auth checks using can_use() - return empty list gracefully
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    settings = AppSettingsService(session)
    if not await settings.is_provider_enabled("spotify"):
        return []
    # can_use() checks capability + auth - graceful return if not available
    if not spotify_plugin.can_use(PluginCapability.SEARCH_ARTISTS):
        return []

    try:
        suggestions: list[SearchSuggestion] = []

        # Search artists (top 3)
        artist_results = await spotify_plugin.search_artist(query, limit=3)
        for artist_dto in artist_results.items[:3]:
            suggestions.append(
                SearchSuggestion(
                    text=artist_dto.name,
                    type="artist",
                    id=artist_dto.spotify_id,
                )
            )

        # Search tracks (top 5)
        track_results = await spotify_plugin.search_track(query, limit=5)
        for track_dto in track_results.items[:5]:
            artist_name = track_dto.artist_name or ""
            text = f"{track_dto.title} - {artist_name}" if artist_name else track_dto.title
            suggestions.append(
                SearchSuggestion(text=text, type="track", id=track_dto.spotify_id)
            )

        return suggestions

    except Exception as e:
        logger.error(f"Search suggestions failed: {e}", exc_info=True)
        # Return empty list on error (graceful degradation)
        return []
