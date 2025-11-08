"""MusicBrainz HTTP client implementation with rate limiting."""

import asyncio
from typing import Any, cast

import httpx

from soulspot.config.settings import MusicBrainzSettings
from soulspot.domain.ports import IMusicBrainzClient


class MusicBrainzClient(IMusicBrainzClient):
    """HTTP client for MusicBrainz API operations with rate limiting."""

    API_BASE_URL = "https://musicbrainz.org/ws/2"
    RATE_LIMIT_DELAY = 1.0  # 1 request per second as per MusicBrainz guidelines

    def __init__(self, settings: MusicBrainzSettings) -> None:
        """
        Initialize MusicBrainz client.

        Args:
            settings: MusicBrainz configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0
        self._rate_limit_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # User-Agent is required by MusicBrainz
            user_agent = f"{self.settings.app_name}/{self.settings.app_version} " f"( {self.settings.contact} )"

            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rate_limited_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """
        Make a rate-limited request to MusicBrainz API.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If the request fails
        """
        async with self._rate_limit_lock:
            # Ensure we respect the rate limit
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)

            client = await self._get_client()
            response = await client.request(method, url, **kwargs)

            self._last_request_time = asyncio.get_event_loop().time()

            return response

    async def lookup_recording_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """
        Lookup a recording by ISRC code.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Recording information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                "/isrc/" + isrc,
                params={"fmt": "json", "inc": "artists+releases"},
            )
            response.raise_for_status()
            data = response.json()

            # ISRC lookup returns a list of recordings
            if "recordings" in data and data["recordings"]:
                return cast(dict[str, Any], data["recordings"][0])

            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def search_recording(self, artist: str, title: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for recordings by artist and title.

        Args:
            artist: Artist name
            title: Track title
            limit: Maximum number of results

        Returns:
            List of recording matches

        Raises:
            httpx.HTTPError: If the request fails
        """
        # Build Lucene query
        query_parts = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if title:
            query_parts.append(f'recording:"{title}"')

        query = " AND ".join(query_parts)

        response = await self._rate_limited_request(
            "GET",
            "/recording",
            params={
                "query": query,
                "fmt": "json",
                "limit": limit,
            },
        )
        response.raise_for_status()
        data = response.json()

        return cast(list[dict[str, Any]], data.get("recordings", []))

    async def lookup_release(self, release_id: str) -> dict[str, Any] | None:
        """
        Lookup a release (album) by MusicBrainz ID.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            Release information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/release/{release_id}",
                params={
                    "fmt": "json",
                    "inc": "artists+recordings+release-groups",
                },
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def lookup_artist(self, artist_id: str) -> dict[str, Any] | None:
        """
        Lookup an artist by MusicBrainz ID.

        Args:
            artist_id: MusicBrainz artist ID

        Returns:
            Artist information or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        try:
            response = await self._rate_limited_request(
                "GET",
                f"/artist/{artist_id}",
                params={
                    "fmt": "json",
                    "inc": "aliases+tags+genres",
                },
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def __aenter__(self) -> "MusicBrainzClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
