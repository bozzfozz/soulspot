"""Last.fm HTTP client implementation."""

import hashlib
from typing import Any, cast

import httpx

from soulspot.config.settings import LastfmSettings
from soulspot.domain.ports import ILastfmClient


class LastfmClient(ILastfmClient):
    """HTTP client for Last.fm API operations."""

    API_BASE_URL = "https://ws.audioscrobbler.com/2.0/"

    def __init__(self, settings: LastfmSettings) -> None:
        """
        Initialize Last.fm client.

        Args:
            settings: Last.fm configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _sign_request(self, params: dict[str, str]) -> str:
        """
        Create API signature for authenticated requests.

        Args:
            params: Request parameters

        Returns:
            MD5 signature string
        """
        # Sort params alphabetically and create signature string
        sorted_params = sorted(params.items())
        sig_string = "".join(f"{k}{v}" for k, v in sorted_params)
        sig_string += self.settings.api_secret

        # MD5 is used for Last.fm API signature, not for security purposes
        return hashlib.md5(  # nosec B324
            sig_string.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

    async def _make_request(
        self, method: str, params: dict[str, Any], auth_required: bool = False
    ) -> dict[str, Any] | None:
        """
        Make a request to Last.fm API.

        Args:
            method: API method name
            params: Request parameters
            auth_required: Whether authentication is required

        Returns:
            Response data or None if not found

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        request_params = {
            "method": method,
            "api_key": self.settings.api_key,
            "format": "json",
            **params,
        }

        if auth_required:
            request_params["api_sig"] = self._sign_request(request_params)

        try:
            response = await client.get("", params=request_params)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "error" in data:
                return None

            return cast(dict[str, Any], data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_track_info(
        self, artist: str, track: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get track information including tags.

        Args:
            artist: Artist name
            track: Track title
            mbid: Optional MusicBrainz ID

        Returns:
            Track information or None if not found
        """
        params: dict[str, Any] = {}

        if mbid:
            params["mbid"] = mbid
        else:
            params["artist"] = artist
            params["track"] = track

        response = await self._make_request("track.getInfo", params)
        return response.get("track") if response else None

    async def get_artist_info(
        self, artist: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get artist information including tags.

        Args:
            artist: Artist name
            mbid: Optional MusicBrainz ID

        Returns:
            Artist information or None if not found
        """
        params: dict[str, Any] = {}

        if mbid:
            params["mbid"] = mbid
        else:
            params["artist"] = artist

        response = await self._make_request("artist.getInfo", params)
        return response.get("artist") if response else None

    async def get_album_info(
        self, artist: str, album: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get album information including tags.

        Args:
            artist: Artist name
            album: Album title
            mbid: Optional MusicBrainz ID

        Returns:
            Album information or None if not found
        """
        params: dict[str, Any] = {}

        if mbid:
            params["mbid"] = mbid
        else:
            params["artist"] = artist
            params["album"] = album

        response = await self._make_request("album.getInfo", params)
        return response.get("album") if response else None

    async def __aenter__(self) -> "LastfmClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
