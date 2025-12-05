"""Deezer HTTP client implementation for metadata and artwork.

Hey future me - Deezer is AWESOME because their Public API works WITHOUT authentication!
Unlike Spotify/Tidal which require OAuth, Deezer lets us just hit their API directly.
This makes it perfect as a fallback for artwork enrichment, especially for Various Artists
compilations where Spotify matching fails.

Rate limits: 50 requests per 5 seconds (per IP). We handle this with a simple async sleep.

Key features:
- Album search and details (with artwork URLs up to 1000x1000!)
- Artist search and details (with images)
- Track search with ISRC for matching
- No OAuth dance required!

When to use Deezer:
1. Spotify enrichment finds no match
2. Various Artists / compilation albums
3. Obscure releases not on Spotify
4. Alternative artwork source
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DeezerAlbum:
    """Deezer album data."""

    id: int
    title: str
    artist_name: str
    artist_id: int | None
    cover_small: str | None  # 56x56
    cover_medium: str | None  # 250x250
    cover_big: str | None  # 500x500
    cover_xl: str | None  # 1000x1000 - the good stuff!
    release_date: str | None
    nb_tracks: int
    duration: int  # total duration in seconds
    record_type: str | None  # album, ep, single, compile
    explicit_lyrics: bool
    upc: str | None  # Universal Product Code for matching


@dataclass
class DeezerArtist:
    """Deezer artist data."""

    id: int
    name: str
    picture_small: str | None  # 56x56
    picture_medium: str | None  # 250x250
    picture_big: str | None  # 500x500
    picture_xl: str | None  # 1000x1000
    nb_album: int
    nb_fan: int
    link: str | None = None  # Deezer URL to artist page


@dataclass
class DeezerTrack:
    """Deezer track data."""

    id: int
    title: str
    artist_name: str
    artist_id: int | None
    album_title: str
    album_id: int | None
    duration: int  # in seconds
    track_position: int | None
    disk_number: int | None
    isrc: str | None  # International Standard Recording Code - GOLD for matching!
    preview: str | None  # 30-second preview URL
    explicit_lyrics: bool


class DeezerClient:
    """HTTP client for Deezer API operations.

    Deezer's public API is completely free and doesn't require authentication
    for reading metadata. Rate limit is 50 requests per 5 seconds.

    Usage:
        client = DeezerClient()
        albums = await client.search_albums("Bravo Hits 100")
        album = await client.get_album(albums[0].id)
        print(f"Artwork: {album.cover_xl}")  # 1000x1000 image!
    """

    API_BASE_URL = "https://api.deezer.com"

    # Hey future me - Deezer is lenient but let's be respectful. 50/5s limit.
    # We add 100ms between requests to be safe and not trigger IP bans.
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests

    def __init__(self) -> None:
        """Initialize Deezer client.

        No settings needed! Deezer's public API doesn't require authentication.
        """
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0
        self._rate_limit_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # Hey future me - unlike MusicBrainz, Deezer doesn't require User-Agent.
            # But we set one anyway to be a good citizen.
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                headers={
                    "User-Agent": "SoulSpot/1.0 (https://github.com/bozzfozz/soulspot)",
                    "Accept": "application/json",
                },
                timeout=15.0,  # Deezer is usually fast
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rate_limited_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Make a rate-limited request to Deezer API.

        Hey future me - simple rate limiting: 100ms between requests.
        Deezer is more lenient than MusicBrainz (50/5s vs 1/1s) but
        let's not push our luck.

        Args:
            method: HTTP method
            url: Request URL (relative to base URL)
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If the request fails
        """
        async with self._rate_limit_lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

            client = await self._get_client()
            response = await client.request(method, url, **kwargs)

            self._last_request_time = asyncio.get_event_loop().time()

            return response

    # =========================================================================
    # ALBUM METHODS
    # =========================================================================

    async def search_albums(
        self, query: str, limit: int = 25
    ) -> list[DeezerAlbum]:
        """Search for albums on Deezer.

        Hey future me - this is PERFECT for Various Artists compilations!
        Just search by album title and you'll get artwork URLs.

        Args:
            query: Search query (album title, "artist - album", etc.)
            limit: Maximum results (default 25, max 100)

        Returns:
            List of DeezerAlbum objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                "/search/album",
                params={"q": query, "limit": min(limit, 100)},
            )
            response.raise_for_status()
            data = response.json()

            albums = []
            for item in data.get("data", []):
                albums.append(self._parse_album(item))

            return albums

        except httpx.HTTPError as e:
            logger.error(f"Deezer album search failed: {e}")
            raise

    async def get_album(self, album_id: int) -> DeezerAlbum | None:
        """Get album details by ID.

        Hey future me - this returns FULL album data including:
        - High-res artwork (cover_xl = 1000x1000)
        - UPC code (for matching!)
        - Track count
        - Duration

        Args:
            album_id: Deezer album ID

        Returns:
            DeezerAlbum or None if not found
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/album/{album_id}",
            )
            response.raise_for_status()
            data = response.json()

            # Deezer returns {"error": {...}} for not found
            if "error" in data:
                return None

            return self._parse_album(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Deezer get_album failed: {e}")
            raise

    async def get_album_tracks(self, album_id: int) -> list[DeezerTrack]:
        """Get tracks for an album.

        Hey future me - useful for checking track count and ISRCs for matching.

        Args:
            album_id: Deezer album ID

        Returns:
            List of DeezerTrack objects
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/album/{album_id}/tracks",
            )
            response.raise_for_status()
            data = response.json()

            tracks = []
            for item in data.get("data", []):
                tracks.append(self._parse_track(item))

            return tracks

        except httpx.HTTPError as e:
            logger.error(f"Deezer get_album_tracks failed: {e}")
            raise

    def _parse_album(self, data: dict[str, Any]) -> DeezerAlbum:
        """Parse Deezer API album response to DeezerAlbum.

        Hey future me - Deezer returns different fields for search vs direct get.
        Search returns basic info, direct get returns full details.
        This handles both gracefully.
        """
        artist_data = data.get("artist", {})

        return DeezerAlbum(
            id=data["id"],
            title=data.get("title", ""),
            artist_name=artist_data.get("name", "Unknown Artist"),
            artist_id=artist_data.get("id"),
            cover_small=data.get("cover_small"),
            cover_medium=data.get("cover_medium"),
            cover_big=data.get("cover_big"),
            cover_xl=data.get("cover_xl"),
            release_date=data.get("release_date"),
            nb_tracks=data.get("nb_tracks", 0),
            duration=data.get("duration", 0),
            record_type=data.get("record_type"),  # album, ep, single, compile
            explicit_lyrics=data.get("explicit_lyrics", False),
            upc=data.get("upc"),  # Only in full album response
        )

    # =========================================================================
    # ARTIST METHODS
    # =========================================================================

    async def search_artists(
        self, query: str, limit: int = 25
    ) -> list[DeezerArtist]:
        """Search for artists on Deezer.

        Args:
            query: Search query (artist name)
            limit: Maximum results (default 25, max 100)

        Returns:
            List of DeezerArtist objects
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                "/search/artist",
                params={"q": query, "limit": min(limit, 100)},
            )
            response.raise_for_status()
            data = response.json()

            artists = []
            for item in data.get("data", []):
                artists.append(self._parse_artist(item))

            return artists

        except httpx.HTTPError as e:
            logger.error(f"Deezer artist search failed: {e}")
            raise

    async def get_artist(self, artist_id: int) -> DeezerArtist | None:
        """Get artist details by ID.

        Args:
            artist_id: Deezer artist ID

        Returns:
            DeezerArtist or None if not found
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/artist/{artist_id}",
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return None

            return self._parse_artist(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Deezer get_artist failed: {e}")
            raise

    async def get_artist_albums(
        self, artist_id: int, limit: int = 50
    ) -> list[DeezerAlbum]:
        """Get albums for an artist.

        Args:
            artist_id: Deezer artist ID
            limit: Maximum results (default 50, max 100)

        Returns:
            List of DeezerAlbum objects
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/artist/{artist_id}/albums",
                params={"limit": min(limit, 100)},
            )
            response.raise_for_status()
            data = response.json()

            albums = []
            for item in data.get("data", []):
                albums.append(self._parse_album(item))

            return albums

        except httpx.HTTPError as e:
            logger.error(f"Deezer get_artist_albums failed: {e}")
            raise

    def _parse_artist(self, data: dict[str, Any]) -> DeezerArtist:
        """Parse Deezer API artist response to DeezerArtist."""
        return DeezerArtist(
            id=data["id"],
            name=data.get("name", "Unknown Artist"),
            picture_small=data.get("picture_small"),
            picture_medium=data.get("picture_medium"),
            picture_big=data.get("picture_big"),
            picture_xl=data.get("picture_xl"),
            nb_album=data.get("nb_album", 0),
            nb_fan=data.get("nb_fan", 0),
            link=data.get("link"),
        )

    # =========================================================================
    # TRACK METHODS
    # =========================================================================

    async def search_tracks(
        self, query: str, limit: int = 25
    ) -> list[DeezerTrack]:
        """Search for tracks on Deezer.

        Hey future me - track search returns ISRC codes! Use these for
        high-confidence matching with local library tracks.

        Args:
            query: Search query ("artist - track", etc.)
            limit: Maximum results (default 25, max 100)

        Returns:
            List of DeezerTrack objects
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                "/search/track",
                params={"q": query, "limit": min(limit, 100)},
            )
            response.raise_for_status()
            data = response.json()

            tracks = []
            for item in data.get("data", []):
                tracks.append(self._parse_track(item))

            return tracks

        except httpx.HTTPError as e:
            logger.error(f"Deezer track search failed: {e}")
            raise

    async def get_track(self, track_id: int) -> DeezerTrack | None:
        """Get track details by ID.

        Args:
            track_id: Deezer track ID

        Returns:
            DeezerTrack or None if not found
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/track/{track_id}",
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return None

            return self._parse_track(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Deezer get_track failed: {e}")
            raise

    async def get_track_by_isrc(self, isrc: str) -> DeezerTrack | None:
        """Get track by ISRC code.

        Hey future me - this is THE GOLDEN METHOD for matching!
        ISRC is a universal track identifier, so if local file has ISRC
        and Deezer has the same ISRC, it's 100% the same recording.

        Args:
            isrc: International Standard Recording Code

        Returns:
            DeezerTrack or None if not found
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/track/isrc:{isrc}",
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return None

            return self._parse_track(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Deezer get_track_by_isrc failed: {e}")
            raise

    def _parse_track(self, data: dict[str, Any]) -> DeezerTrack:
        """Parse Deezer API track response to DeezerTrack."""
        artist_data = data.get("artist", {})
        album_data = data.get("album", {})

        return DeezerTrack(
            id=data["id"],
            title=data.get("title", ""),
            artist_name=artist_data.get("name", "Unknown Artist"),
            artist_id=artist_data.get("id"),
            album_title=album_data.get("title", ""),
            album_id=album_data.get("id"),
            duration=data.get("duration", 0),
            track_position=data.get("track_position"),
            disk_number=data.get("disk_number"),
            isrc=data.get("isrc"),  # THE GOLDEN KEY for matching!
            preview=data.get("preview"),  # 30-second preview URL
            explicit_lyrics=data.get("explicit_lyrics", False),
        )

    # =========================================================================
    # CONVENIENCE METHODS for SoulSpot Enrichment
    # =========================================================================

    async def find_album_artwork(
        self, album_title: str, artist_name: str | None = None
    ) -> str | None:
        """Find artwork URL for an album.

        Hey future me - this is the main method for library enrichment!
        Searches Deezer for the album and returns the best artwork URL.

        For Various Artists compilations, just pass album_title without artist.

        Args:
            album_title: Album title to search
            artist_name: Optional artist name for better matching

        Returns:
            High-res artwork URL (cover_xl, 1000x1000) or None
        """
        # Build search query
        if artist_name and artist_name.lower() not in [
            "various artists", "va", "v.a.", "various", "compilation", "soundtrack"
        ]:
            query = f'"{artist_name}" "{album_title}"'
        else:
            # For Various Artists, just search by title
            query = f'"{album_title}"'

        albums = await self.search_albums(query, limit=5)

        if not albums:
            return None

        # Find best match by title similarity
        # Hey future me - for now just return first result's artwork.
        # TODO: Add fuzzy matching like Spotify enrichment service
        best_album = albums[0]

        # Prefer cover_xl (1000x1000) but fall back to smaller sizes
        return (
            best_album.cover_xl
            or best_album.cover_big
            or best_album.cover_medium
            or best_album.cover_small
        )

    async def find_artist_image(self, artist_name: str) -> str | None:
        """Find image URL for an artist.

        Args:
            artist_name: Artist name to search

        Returns:
            High-res artist image URL or None
        """
        artists = await self.search_artists(artist_name, limit=5)

        if not artists:
            return None

        best_artist = artists[0]

        return (
            best_artist.picture_xl
            or best_artist.picture_big
            or best_artist.picture_medium
            or best_artist.picture_small
        )

    async def get_album_tracks(self, album_id: int) -> list[DeezerTrack]:
        """Get all tracks from an album.

        Hey future me - this is for tracklist verification! Compare local album
        tracks with Deezer tracklist to find missing or extra tracks.

        Args:
            album_id: Deezer album ID

        Returns:
            List of DeezerTrack objects
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/album/{album_id}/tracks")
                response.raise_for_status()
                data = response.json()

            tracks = []
            for track_data in data.get("data", []):
                track = self._parse_track(track_data)
                if track:
                    tracks.append(track)

            logger.debug(f"Fetched {len(tracks)} tracks for Deezer album {album_id}")
            return tracks

        except Exception as e:
            logger.error(f"Deezer get_album_tracks failed: {e}")
            return []

    # =========================================================================
    # TRACKLIST VERIFICATION
    # =========================================================================

    async def compare_tracklists(
        self,
        deezer_album_id: int,
        local_tracks: list[tuple[str, int | None]],  # (title, track_number)
    ) -> dict[str, Any]:
        """Compare local tracklist with Deezer album tracklist.

        Hey future me - this helps identify:
        - Missing tracks in local collection
        - Extra tracks (bonus tracks, deluxe editions)
        - Track ordering issues
        - Naming differences

        Args:
            deezer_album_id: Deezer album ID to compare against
            local_tracks: List of (title, track_number) tuples from local library

        Returns:
            Comparison result dict with matched, missing, extra tracks
        """
        from rapidfuzz import fuzz

        deezer_tracks = await self.get_album_tracks(deezer_album_id)

        if not deezer_tracks:
            return {
                "success": False,
                "error": "Could not fetch Deezer tracklist",
                "matched": [],
                "missing": [],
                "extra": [],
            }

        # Build lookup by track position and title
        matched = []
        missing = []
        extra = list(local_tracks)  # Start with all local as "extra"

        for deezer_track in deezer_tracks:
            best_match = None
            best_score = 0

            for i, (local_title, local_num) in enumerate(extra):
                # Score by title similarity
                score = fuzz.ratio(
                    deezer_track.title.lower(),
                    local_title.lower()
                )

                # Bonus if track number matches
                if local_num and deezer_track.track_position == local_num:
                    score = min(100, score + 20)

                if score > best_score and score >= 70:  # 70% minimum match
                    best_match = i
                    best_score = score

            if best_match is not None:
                matched.append({
                    "deezer_title": deezer_track.title,
                    "local_title": extra[best_match][0],
                    "position": deezer_track.track_position,
                    "score": best_score,
                })
                extra.pop(best_match)
            else:
                missing.append({
                    "title": deezer_track.title,
                    "position": deezer_track.track_position,
                    "isrc": deezer_track.isrc,
                    "duration": deezer_track.duration,
                })

        return {
            "success": True,
            "deezer_album_id": deezer_album_id,
            "total_deezer_tracks": len(deezer_tracks),
            "total_local_tracks": len(local_tracks),
            "matched": matched,
            "missing_from_local": missing,
            "extra_in_local": [{"title": t[0], "position": t[1]} for t in extra],
            "match_rate": len(matched) / len(deezer_tracks) if deezer_tracks else 0,
        }

    # =========================================================================
    # PREVIEW URLs (30-second audio previews)
    # =========================================================================

    async def get_track_preview_url(self, track_id: int) -> str | None:
        """Get 30-second preview URL for a track.

        Hey future me - Deezer provides 30s MP3 previews for most tracks!
        Could be used for:
        - Audio fingerprinting to verify local file matches
        - Preview playback in UI before download
        - Quality comparison between local file and streaming version

        Args:
            track_id: Deezer track ID

        Returns:
            Preview URL (MP3, 128kbps, 30 seconds) or None if not available
        """
        track = await self.get_track(track_id)
        return track.preview if track else None

    async def get_album_preview_urls(self, album_id: int) -> list[dict[str, Any]]:
        """Get preview URLs for all tracks in an album.

        Args:
            album_id: Deezer album ID

        Returns:
            List of dicts with track info and preview URLs
        """
        tracks = await self.get_album_tracks(album_id)

        return [
            {
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist_name,
                "position": track.track_position,
                "duration": track.duration,
                "preview_url": track.preview,
                "isrc": track.isrc,
            }
            for track in tracks
            if track.preview  # Only include tracks with previews
        ]

    # =========================================================================
    # UPC/BARCODE MATCHING
    # =========================================================================

    async def get_album_by_upc(self, upc: str) -> DeezerAlbum | None:
        """Get album by UPC (Universal Product Code / Barcode).

        Hey future me - UPC is the barcode on physical CDs!
        If user scans a CD barcode, we can find the exact album on Deezer.
        Perfect for:
        - Physical CD collection import
        - Barcode scanner integration
        - 100% accurate album identification

        Args:
            upc: Universal Product Code (barcode) - typically 12-13 digits

        Returns:
            DeezerAlbum if found, None otherwise
        """
        try:
            await self._rate_limit()

            # Deezer uses /album/upc:{upc} endpoint
            async with self._client as client:
                response = await client.get(f"/album/upc:{upc}")
                response.raise_for_status()
                data = response.json()

            # Check if we got an error response
            if "error" in data:
                logger.debug(f"No Deezer album found for UPC: {upc}")
                return None

            return self._parse_album(data)

        except Exception as e:
            logger.error(f"Deezer get_album_by_upc failed: {e}")
            return None

    async def search_by_barcode(
        self,
        barcode: str,
    ) -> dict[str, Any]:
        """Search for album by barcode and return full enrichment data.

        Convenience method that searches by UPC and returns all relevant
        data for library enrichment (artwork, tracklist, metadata).

        Args:
            barcode: UPC/EAN barcode (from CD packaging)

        Returns:
            Dict with album info, artwork URLs, tracklist, or error
        """
        # Normalize barcode (remove dashes, spaces)
        clean_barcode = "".join(c for c in barcode if c.isdigit())

        album = await self.get_album_by_upc(clean_barcode)

        if not album:
            return {
                "success": False,
                "error": f"No album found for barcode: {clean_barcode}",
            }

        # Get full tracklist
        tracks = await self.get_album_tracks(album.id)

        return {
            "success": True,
            "barcode": clean_barcode,
            "album": {
                "deezer_id": album.id,
                "title": album.title,
                "artist": album.artist_name,
                "release_date": album.release_date,
                "total_tracks": album.nb_tracks,
                "record_type": album.record_type,
                "explicit": album.explicit_lyrics,
                "upc": album.upc,
                "link": album.link,
            },
            "artwork": {
                "small": album.cover_small,
                "medium": album.cover_medium,
                "big": album.cover_big,
                "xl": album.cover_xl,
            },
            "tracks": [
                {
                    "position": t.track_position,
                    "title": t.title,
                    "artist": t.artist_name,
                    "duration": t.duration,
                    "isrc": t.isrc,
                    "preview": t.preview,
                }
                for t in tracks
            ],
        }

    # =========================================================================
    # CHARTS & NEW RELEASES (Spotify Browse Fallback)
    # =========================================================================

    async def get_chart_tracks(self, limit: int = 50) -> list[DeezerTrack]:
        """Get top chart tracks (global).

        Hey future me - this is the Deezer fallback for Spotify's "New Releases"!
        Free, no OAuth, shows what's popular globally.

        Args:
            limit: Maximum tracks to return (max 100)

        Returns:
            List of top chart tracks
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/chart/0/tracks?limit={limit}")
                response.raise_for_status()
                data = response.json()

            tracks = []
            for track_data in data.get("data", []):
                track = self._parse_track(track_data)
                if track:
                    tracks.append(track)

            logger.debug(f"Fetched {len(tracks)} chart tracks from Deezer")
            return tracks

        except Exception as e:
            logger.error(f"Deezer get_chart_tracks failed: {e}")
            return []

    async def get_chart_albums(self, limit: int = 50) -> list[DeezerAlbum]:
        """Get top chart albums (global).

        Args:
            limit: Maximum albums to return (max 100)

        Returns:
            List of top chart albums
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/chart/0/albums?limit={limit}")
                response.raise_for_status()
                data = response.json()

            albums = []
            for album_data in data.get("data", []):
                album = self._parse_album(album_data)
                if album:
                    albums.append(album)

            logger.debug(f"Fetched {len(albums)} chart albums from Deezer")
            return albums

        except Exception as e:
            logger.error(f"Deezer get_chart_albums failed: {e}")
            return []

    async def get_chart_artists(self, limit: int = 50) -> list[DeezerArtist]:
        """Get top chart artists (global).

        Args:
            limit: Maximum artists to return (max 100)

        Returns:
            List of top chart artists
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/chart/0/artists?limit={limit}")
                response.raise_for_status()
                data = response.json()

            artists = []
            for artist_data in data.get("data", []):
                artist = self._parse_artist(artist_data)
                if artist:
                    artists.append(artist)

            logger.debug(f"Fetched {len(artists)} chart artists from Deezer")
            return artists

        except Exception as e:
            logger.error(f"Deezer get_chart_artists failed: {e}")
            return []

    # =========================================================================
    # EDITORIAL / NEW RELEASES
    # =========================================================================

    async def get_editorial_releases(self, limit: int = 50) -> list[DeezerAlbum]:
        """Get editorial selection of new releases.

        This is the Deezer equivalent of Spotify's "New Releases" section.
        Returns curated new album releases.

        Args:
            limit: Maximum albums to return

        Returns:
            List of new release albums
        """
        try:
            await self._rate_limit()

            # /editorial/0/releases gives new releases from editorial team
            async with self._client as client:
                response = await client.get(f"/editorial/0/releases?limit={limit}")
                response.raise_for_status()
                data = response.json()

            albums = []
            for album_data in data.get("data", []):
                album = self._parse_album(album_data)
                if album:
                    albums.append(album)

            logger.debug(f"Fetched {len(albums)} editorial releases from Deezer")
            return albums

        except Exception as e:
            logger.error(f"Deezer get_editorial_releases failed: {e}")
            return []

    async def get_editorial_selection(self, limit: int = 50) -> list[DeezerAlbum]:
        """Get editorial selection (staff picks).

        Returns curated album selections from Deezer's editorial team.

        Args:
            limit: Maximum albums to return

        Returns:
            List of selected albums
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/editorial/0/selection?limit={limit}")
                response.raise_for_status()
                data = response.json()

            albums = []
            for item in data.get("data", []):
                # Selection can contain albums directly or wrapped in objects
                if "album" in item:
                    album = self._parse_album(item["album"])
                else:
                    album = self._parse_album(item)
                if album:
                    albums.append(album)

            logger.debug(f"Fetched {len(albums)} editorial selection from Deezer")
            return albums

        except Exception as e:
            logger.error(f"Deezer get_editorial_selection failed: {e}")
            return []

    # =========================================================================
    # GENRES
    # =========================================================================

    async def get_genres(self) -> list[dict[str, Any]]:
        """Get list of all Deezer genres.

        Returns:
            List of genre dicts with id, name, picture URLs
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get("/genre")
                response.raise_for_status()
                data = response.json()

            genres = []
            for genre_data in data.get("data", []):
                genres.append({
                    "id": genre_data.get("id"),
                    "name": genre_data.get("name"),
                    "picture": genre_data.get("picture"),
                    "picture_small": genre_data.get("picture_small"),
                    "picture_medium": genre_data.get("picture_medium"),
                    "picture_big": genre_data.get("picture_big"),
                    "picture_xl": genre_data.get("picture_xl"),
                })

            logger.debug(f"Fetched {len(genres)} genres from Deezer")
            return genres

        except Exception as e:
            logger.error(f"Deezer get_genres failed: {e}")
            return []

    async def get_genre_artists(
        self, genre_id: int, limit: int = 50
    ) -> list[DeezerArtist]:
        """Get top artists for a specific genre.

        Args:
            genre_id: Deezer genre ID
            limit: Maximum artists to return

        Returns:
            List of artists in that genre
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/genre/{genre_id}/artists?limit={limit}")
                response.raise_for_status()
                data = response.json()

            artists = []
            for artist_data in data.get("data", []):
                artist = self._parse_artist(artist_data)
                if artist:
                    artists.append(artist)

            logger.debug(f"Fetched {len(artists)} artists for genre {genre_id}")
            return artists

        except Exception as e:
            logger.error(f"Deezer get_genre_artists failed: {e}")
            return []

    async def get_genre_radios(
        self, genre_id: int, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Get radio stations for a specific genre.

        Radio stations are like endless playlists - continuous music in that genre.

        Args:
            genre_id: Deezer genre ID
            limit: Maximum radios to return

        Returns:
            List of radio station info dicts
        """
        try:
            await self._rate_limit()

            async with self._client as client:
                response = await client.get(f"/genre/{genre_id}/radios?limit={limit}")
                response.raise_for_status()
                data = response.json()

            radios = []
            for radio_data in data.get("data", []):
                radios.append({
                    "id": radio_data.get("id"),
                    "title": radio_data.get("title"),
                    "description": radio_data.get("description"),
                    "picture": radio_data.get("picture"),
                    "picture_medium": radio_data.get("picture_medium"),
                    "picture_big": radio_data.get("picture_big"),
                    "picture_xl": radio_data.get("picture_xl"),
                    "tracklist_url": radio_data.get("tracklist"),
                })

            logger.debug(f"Fetched {len(radios)} radios for genre {genre_id}")
            return radios

        except Exception as e:
            logger.error(f"Deezer get_genre_radios failed: {e}")
            return []

    # =========================================================================
    # CONVENIENCE: BROWSE FALLBACK FOR SPOTIFY
    # =========================================================================

    async def get_browse_new_releases(
        self,
        limit: int = 50,
        include_compilations: bool = True,
    ) -> dict[str, Any]:
        """Get new releases as fallback for Spotify Browse.

        Hey future me - this is the MAIN fallback for Spotify's Browse/New Releases!
        Combines editorial releases and chart albums for a good mix.
        No OAuth needed, works for any user!

        Args:
            limit: Maximum albums to return
            include_compilations: Whether to include compilations

        Returns:
            Dict with new release albums, organized like Spotify's response
        """
        try:
            # Fetch from multiple sources for variety
            editorial = await self.get_editorial_releases(limit=limit // 2)
            charts = await self.get_chart_albums(limit=limit // 2)

            # Deduplicate by album ID
            seen_ids: set[int] = set()
            albums = []

            for album in editorial + charts:
                if album.id not in seen_ids:
                    seen_ids.add(album.id)

                    # Filter compilations if requested
                    if not include_compilations and album.record_type == "compile":
                        continue

                    albums.append({
                        "deezer_id": album.id,
                        "title": album.title,
                        "artist_name": album.artist_name,
                        "artist_id": album.artist_id,
                        "release_date": album.release_date,
                        "total_tracks": album.nb_tracks,
                        "record_type": album.record_type,
                        "cover_small": album.cover_small,
                        "cover_medium": album.cover_medium,
                        "cover_big": album.cover_big,
                        "cover_xl": album.cover_xl,
                        "link": album.link,
                        "explicit": album.explicit_lyrics,
                    })

                    if len(albums) >= limit:
                        break

            return {
                "success": True,
                "source": "deezer",
                "total": len(albums),
                "albums": albums,
            }

        except Exception as e:
            logger.error(f"Deezer get_browse_new_releases failed: {e}")
            return {
                "success": False,
                "source": "deezer",
                "error": str(e),
                "albums": [],
            }

    async def get_browse_by_genre(
        self,
        genre_name: str | None = None,
        genre_id: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get genre-specific content as fallback for Spotify Browse.

        Args:
            genre_name: Genre name to search for (if genre_id not provided)
            genre_id: Deezer genre ID (preferred, more accurate)
            limit: Maximum items to return

        Returns:
            Dict with genre artists, radios, and top tracks
        """
        try:
            # If no genre_id, try to find it by name
            if not genre_id and genre_name:
                genres = await self.get_genres()
                for g in genres:
                    if genre_name.lower() in g["name"].lower():
                        genre_id = g["id"]
                        break

            if not genre_id:
                return {
                    "success": False,
                    "error": f"Genre not found: {genre_name}",
                }

            # Fetch genre content
            artists = await self.get_genre_artists(genre_id, limit=limit // 2)
            radios = await self.get_genre_radios(genre_id, limit=10)

            return {
                "success": True,
                "source": "deezer",
                "genre_id": genre_id,
                "artists": [
                    {
                        "deezer_id": a.id,
                        "name": a.name,
                        "nb_fan": a.nb_fan,
                        "nb_album": a.nb_album,
                        "picture_xl": a.picture_xl,
                        "link": a.link,
                    }
                    for a in artists
                ],
                "radios": radios,
            }

        except Exception as e:
            logger.error(f"Deezer get_browse_by_genre failed: {e}")
            return {
                "success": False,
                "source": "deezer",
                "error": str(e),
            }
