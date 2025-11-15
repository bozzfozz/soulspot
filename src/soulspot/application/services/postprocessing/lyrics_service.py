"""Lyrics fetching service with multiple sources."""

import logging
from typing import Any

import httpx

from soulspot.config import Settings
from soulspot.domain.entities import Track

logger = logging.getLogger(__name__)


class LyricsService:
    """Service for fetching lyrics from multiple sources.

    This service implements a fallback chain:
    1. LRClib (primary - has synced lyrics)
    2. Genius (secondary - comprehensive database)
    3. Musixmatch (fallback - large database)
    """

    # API endpoints
    LRCLIB_API_BASE = "https://lrclib.net/api"
    GENIUS_API_BASE = "https://api.genius.com"
    MUSIXMATCH_API_BASE = "https://api.musixmatch.com/ws/1.1"

    def __init__(
        self,
        settings: Settings,
        genius_api_key: str | None = None,
        musixmatch_api_key: str | None = None,
    ) -> None:
        """Initialize lyrics service.

        Args:
            settings: Application settings
            genius_api_key: Optional Genius API key
            musixmatch_api_key: Optional Musixmatch API key
        """
        self._settings = settings
        self._genius_api_key = genius_api_key
        self._musixmatch_api_key = musixmatch_api_key

    async def fetch_lyrics(
        self,
        track: Track,
        artist_name: str,
        album_name: str | None = None,
    ) -> tuple[str | None, bool]:
        """Fetch lyrics for a track.

        Tries multiple sources in order until lyrics are found.

        Args:
            track: Track entity
            artist_name: Artist name
            album_name: Optional album name

        Returns:
            Tuple of (lyrics text, is_synced)
            Returns (None, False) if no lyrics found
        """
        # Try LRClib first (has synced lyrics)
        logger.info("Trying LRClib for: %s - %s", artist_name, track.title)
        lyrics, is_synced = await self._fetch_from_lrclib(
            artist_name, track.title, album_name, track.duration_ms
        )
        if lyrics:
            logger.info("Found lyrics on LRClib (synced: %s)", is_synced)
            return lyrics, is_synced

        # Try Genius as fallback
        if self._genius_api_key:
            logger.info("Trying Genius for: %s - %s", artist_name, track.title)
            lyrics = await self._fetch_from_genius(artist_name, track.title)
            if lyrics:
                logger.info("Found lyrics on Genius")
                return lyrics, False

        # Try Musixmatch as last resort
        if self._musixmatch_api_key:
            logger.info("Trying Musixmatch for: %s - %s", artist_name, track.title)
            lyrics = await self._fetch_from_musixmatch(artist_name, track.title)
            if lyrics:
                logger.info("Found lyrics on Musixmatch")
                return lyrics, False

        logger.warning("No lyrics found for: %s - %s", artist_name, track.title)
        return None, False

    async def _fetch_from_lrclib(
        self,
        artist: str,
        title: str,
        album: str | None,
        duration_ms: int,
    ) -> tuple[str | None, bool]:
        """Fetch lyrics from LRClib.

        Args:
            artist: Artist name
            title: Track title
            album: Optional album name
            duration_ms: Track duration in milliseconds

        Returns:
            Tuple of (lyrics, is_synced)
        """
        try:
            params: dict[str, Any] = {
                "artist_name": artist,
                "track_name": title,
            }

            if album:
                params["album_name"] = album

            # Convert duration to seconds for LRClib
            if duration_ms > 0:
                params["duration"] = duration_ms // 1000

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.LRCLIB_API_BASE}/get",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                # LRClib returns synced lyrics (LRC format) and plain lyrics
                synced_lyrics = data.get("syncedLyrics")
                plain_lyrics = data.get("plainLyrics")

                if synced_lyrics:
                    return synced_lyrics, True
                elif plain_lyrics:
                    return plain_lyrics, False

                return None, False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug("No lyrics found on LRClib")
            else:
                logger.warning("Error fetching from LRClib: %s", e)
            return None, False
        except Exception as e:
            logger.exception("Error fetching lyrics from LRClib: %s", e)
            return None, False

    async def _fetch_from_genius(
        self,
        artist: str,
        title: str,
    ) -> str | None:
        """Fetch lyrics from Genius.

        Note: This is a simplified implementation. Full implementation would:
        1. Search for the song to get its ID and URL
        2. Scrape the lyrics page (Genius doesn't provide lyrics via API)

        Args:
            artist: Artist name
            title: Track title

        Returns:
            Lyrics text or None
        """
        if not self._genius_api_key:
            return None

        try:
            # Search for song
            search_query = f"{artist} {title}"
            headers = {"Authorization": f"Bearer {self._genius_api_key}"}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.GENIUS_API_BASE}/search",
                    params={"q": search_query},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Get first hit
                hits = data.get("response", {}).get("hits", [])
                if not hits:
                    return None

                # Note: We would need to scrape the lyrics URL here
                # For now, just return None to indicate not implemented
                logger.debug("Genius API integration requires web scraping")
                return None

        except Exception as e:
            logger.exception("Error fetching lyrics from Genius: %s", e)
            return None

    async def _fetch_from_musixmatch(
        self,
        artist: str,
        title: str,
    ) -> str | None:
        """Fetch lyrics from Musixmatch.

        Args:
            artist: Artist name
            title: Track title

        Returns:
            Lyrics text or None
        """
        if not self._musixmatch_api_key:
            return None

        try:
            # Search for track
            params: dict[str, str | int] = {
                "apikey": self._musixmatch_api_key,
                "q_artist": artist,
                "q_track": title,
                "f_has_lyrics": 1,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # First, search for the track
                response = await client.get(
                    f"{self.MUSIXMATCH_API_BASE}/track.search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                track_list = (
                    data.get("message", {}).get("body", {}).get("track_list", [])
                )
                if not track_list:
                    return None

                # Get track ID
                track_id = track_list[0].get("track", {}).get("track_id")
                if not track_id:
                    return None

                # Fetch lyrics
                lyrics_params: dict[str, str | int] = {
                    "apikey": self._musixmatch_api_key,
                    "track_id": track_id,
                }
                lyrics_response = await client.get(
                    f"{self.MUSIXMATCH_API_BASE}/track.lyrics.get",
                    params=lyrics_params,
                )
                lyrics_response.raise_for_status()
                lyrics_data = lyrics_response.json()

                lyrics_body: str | None = (
                    lyrics_data.get("message", {})
                    .get("body", {})
                    .get("lyrics", {})
                    .get("lyrics_body")
                )

                return lyrics_body

        except Exception as e:
            logger.exception("Error fetching lyrics from Musixmatch: %s", e)
            return None
