"""Last.fm HTTP client implementation."""

import hashlib
from typing import Any, cast

import httpx

from soulspot.config.settings import LastfmSettings
from soulspot.domain.ports import ILastfmClient


class LastfmClient(ILastfmClient):
    """HTTP client for Last.fm API operations."""

    API_BASE_URL = "https://ws.audioscrobbler.com/2.0/"

    # Hey future me, Last.fm client is simple compared to MusicBrainz - no crazy rate limits!
    # Just store the settings and lazy-load the HTTP client. Easy peasy.
    def __init__(self, settings: LastfmSettings) -> None:
        """
        Initialize Last.fm client.

        Args:
            settings: Last.fm configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    # Listen up, Last.fm is chill - no special headers required, 30s timeout is plenty.
    # Their API is pretty fast and reliable. No drama here!
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                timeout=30.0,
            )
        return self._client

    # Hey, cleanup - you know the drill by now!
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # Yo future me, Last.fm API signatures are WEIRD. They use MD5 (yeah, in 2024!) but it's
    # NOT for security - just for verifying request integrity. The # nosec comment tells Bandit
    # "chill, we know MD5 is broken for crypto, but that's not what this is". The signature
    # dance: 1) Sort params alphabetically 2) Concatenate key+value pairs 3) Append secret
    # 4) MD5 hash it. If you mess up the order or forget the secret, auth fails. Don't log
    # the signature or secret - that would defeat the purpose! Also, usedforsecurity=False
    # is REQUIRED in Python 3.9+ for FIPS compliance.
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

    # Hey future me, Last.fm API is quirky. The actual endpoint is empty string ""! All
    # methods go in the "method" param (like "track.getInfo"). They return JSON but ALSO
    # include an "error" field in the response if something's wrong - that's different from
    # HTTP status codes! So you need to check BOTH response.status_code AND data["error"].
    # Returning None for errors makes consuming code simpler - "not found" is just None,
    # not an exception. But real HTTP errors (500, timeouts) still raise. Makes sense?
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

    # Listen future me, Last.fm's track data is AMAZING for tags (genres, moods, etc.) and
    # listener stats. BUT their matching is fuzzy - if artist/track names don't match exactly,
    # you get None. Using MBID (MusicBrainz ID) is WAY more reliable if you have it! MBID
    # lookup bypasses the fuzzy name matching. Always prefer MBID when available. The response
    # has tons of useful data: tags, play counts, similar tracks, even wiki descriptions.
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

    # Yo, artist info from Last.fm includes bio, tags, similar artists, and stats. The bio
    # can be LONG (full Wikipedia-style text). Tags are community-voted like MB but generally
    # better quality because Last.fm has more active users. Same MBID vs name matching advice
    # applies - MBID is king if you have it!
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

    # Hey future me, album info includes tags, track list (sometimes), and wiki. But Last.fm's
    # album database is... patchy. Major albums are well-covered, but indie/obscure releases
    # might be missing or have incomplete data. Again, MBID >> name matching for reliability.
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

    # Hey, context manager for proper cleanup. Use it!
    async def __aenter__(self) -> "LastfmClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
