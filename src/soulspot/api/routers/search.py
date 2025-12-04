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

Single-user architecture: Uses shared token (get_spotify_token_shared) so any device
can search without per-browser sessions.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from soulspot.api.dependencies import (
    get_slskd_client,
    get_spotify_client,
    get_spotify_token_shared,
)
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

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
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> SpotifySearchResponse:
    """Search for artists on Spotify.

    Returns artists matching the query with images, genres, and popularity.
    Use the returned artist_id for follow/unfollow operations.

    Args:
        query: Search query (artist name)
        limit: Maximum number of results (1-50)
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of matching artists with metadata
    """
    try:
        results = await spotify_client.search_artist(query, access_token, limit=limit)

        artists = []
        for item in results.get("artists", {}).get("items", []):
            # Get largest image if available
            images = item.get("images", [])
            image_url = images[0]["url"] if images else None

            # Get external URL
            external_urls = item.get("external_urls", {})
            spotify_url = external_urls.get("spotify")

            artists.append(
                SpotifyArtistResult(
                    id=item["id"],
                    name=item["name"],
                    popularity=item.get("popularity", 0),
                    followers=item.get("followers", {}).get("total", 0),
                    genres=item.get("genres", []),
                    image_url=image_url,
                    spotify_url=spotify_url,
                )
            )

        return SpotifySearchResponse(artists=artists, query=query)

    except Exception as e:
        logger.error(f"Spotify artist search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Spotify search failed: {str(e)}",
        ) from e


@router.get("/spotify/tracks", response_model=SpotifySearchResponse)
async def search_spotify_tracks(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> SpotifySearchResponse:
    """Search for tracks on Spotify.

    Returns tracks matching the query with artist info, duration, and ISRC.
    ISRC codes can be used to find the same track on Soulseek.

    Args:
        query: Search query (track name, "artist - track", ISRC)
        limit: Maximum number of results (1-50)
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of matching tracks with metadata
    """
    try:
        results = await spotify_client.search_track(query, access_token, limit=limit)

        tracks = []
        for item in results.get("tracks", {}).get("items", []):
            # Primary artist
            artists = item.get("artists", [])
            artist_name = artists[0]["name"] if artists else "Unknown"
            artist_id = artists[0]["id"] if artists else None

            # Album info
            album = item.get("album", {})
            album_name = album.get("name")
            album_id = album.get("id")

            # External URLs
            external_urls = item.get("external_urls", {})
            spotify_url = external_urls.get("spotify")

            # ISRC from external_ids
            external_ids = item.get("external_ids", {})
            isrc = external_ids.get("isrc")

            tracks.append(
                SpotifyTrackResult(
                    id=item["id"],
                    name=item["name"],
                    artist_name=artist_name,
                    artist_id=artist_id,
                    album_name=album_name,
                    album_id=album_id,
                    duration_ms=item.get("duration_ms", 0),
                    popularity=item.get("popularity", 0),
                    preview_url=item.get("preview_url"),
                    spotify_url=spotify_url,
                    isrc=isrc,
                )
            )

        return SpotifySearchResponse(tracks=tracks, query=query)

    except Exception as e:
        logger.error(f"Spotify track search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Spotify search failed: {str(e)}",
        ) from e


@router.get("/spotify/albums", response_model=SpotifySearchResponse)
async def search_spotify_albums(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> SpotifySearchResponse:
    """Search for albums on Spotify.

    Returns albums matching the query with artwork and track count.
    Use album_id to fetch full track list for download.

    Args:
        query: Search query (album name, "artist - album")
        limit: Maximum number of results (1-50)
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of matching albums with metadata
    """
    try:
        # Hey future me - Spotify doesn't have a separate "album search" method in our client
        # We need to use the generic search endpoint with type=album
        # For now, we'll use search_track and filter albums, or add a search_album method
        # TODO: Add search_album to SpotifyClient for proper album search

        # Workaround: Use track search and extract unique albums
        # This is not ideal but works for MVP
        client = await spotify_client._get_client()
        response = await client.get(
            f"{spotify_client.API_BASE_URL}/search",
            params={"q": query, "type": "album", "limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        results = response.json()

        albums = []
        for item in results.get("albums", {}).get("items", []):
            # Primary artist
            artists = item.get("artists", [])
            artist_name = artists[0]["name"] if artists else "Unknown"
            artist_id = artists[0]["id"] if artists else None

            # Get largest image
            images = item.get("images", [])
            image_url = images[0]["url"] if images else None

            # External URL
            external_urls = item.get("external_urls", {})
            spotify_url = external_urls.get("spotify")

            albums.append(
                SpotifyAlbumResult(
                    id=item["id"],
                    name=item["name"],
                    artist_name=artist_name,
                    artist_id=artist_id,
                    release_date=item.get("release_date"),
                    album_type=item.get("album_type"),
                    total_tracks=item.get("total_tracks", 0),
                    image_url=image_url,
                    spotify_url=spotify_url,
                )
            )

        return SpotifySearchResponse(albums=albums, query=query)

    except Exception as e:
        logger.error(f"Spotify album search failed: {e}")
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
        logger.error(f"Soulseek search failed: {e}")
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
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    access_token: str = Depends(get_spotify_token_shared),
) -> list[SearchSuggestion]:
    """Get search autocomplete suggestions from Spotify.

    Returns quick suggestions for autocomplete dropdown. Combines
    top artist, album, and track matches.

    Args:
        query: Partial search query (minimum 2 characters)
        spotify_client: Spotify client instance
        access_token: Valid Spotify access token

    Returns:
        List of suggestions with type indicators
    """
    try:
        suggestions: list[SearchSuggestion] = []

        # Search artists (top 3)
        artist_results = await spotify_client.search_artist(
            query, access_token, limit=3
        )
        for item in artist_results.get("artists", {}).get("items", [])[:3]:
            suggestions.append(
                SearchSuggestion(text=item["name"], type="artist", id=item["id"])
            )

        # Search tracks (top 5)
        track_results = await spotify_client.search_track(query, access_token, limit=5)
        for item in track_results.get("tracks", {}).get("items", [])[:5]:
            artists = item.get("artists", [])
            artist_name = artists[0]["name"] if artists else ""
            text = f"{item['name']} - {artist_name}" if artist_name else item["name"]
            suggestions.append(SearchSuggestion(text=text, type="track", id=item["id"]))

        return suggestions

    except Exception as e:
        logger.error(f"Search suggestions failed: {e}")
        # Return empty list on error (graceful degradation)
        return []
