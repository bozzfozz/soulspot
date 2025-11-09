"""Spotify HTTP client implementation with OAuth PKCE."""

import base64
import hashlib
import secrets
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from soulspot.config.settings import SpotifySettings
from soulspot.domain.ports import ISpotifyClient


class SpotifyClient(ISpotifyClient):
    """HTTP client for Spotify API operations with OAuth PKCE."""

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE_URL = "https://api.spotify.com/v1"

    def __init__(self, settings: SpotifySettings) -> None:
        """
        Initialize Spotify client.

        Args:
            settings: Spotify configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a PKCE code verifier.

        Returns:
            Random code verifier string
        """
        return (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )

    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        """
        Generate a PKCE code challenge from verifier.

        Args:
            code_verifier: Code verifier string

        Returns:
            SHA256 hash of code verifier as base64 URL-safe string
        """
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """
        Generate Spotify OAuth authorization URL.

        Args:
            state: State parameter for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            Authorization URL
        """
        code_challenge = self.generate_code_challenge(code_verifier)

        params = {
            "client_id": self.settings.client_id,
            "response_type": "code",
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "scope": " ".join(
                [
                    "playlist-read-private",
                    "playlist-read-collaborative",
                    "user-library-read",
                    "user-read-private",
                ]
            ),
        }

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            code_verifier: PKCE code verifier

        Returns:
            Token response with access_token, refresh_token, expires_in

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": code_verifier,
        }

        response = await client.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Token response with new access_token and expires_in

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
        }

        response = await client.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def get_playlist(self, playlist_id: str, access_token: str) -> dict[str, Any]:
        """
        Get playlist details.

        Args:
            playlist_id: Spotify playlist ID
            access_token: OAuth access token

        Returns:
            Playlist information including tracks

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/playlists/{playlist_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """
        Get track details.

        Args:
            track_id: Spotify track ID
            access_token: OAuth access token

        Returns:
            Track information

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get(
            f"{self.API_BASE_URL}/tracks/{track_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def search_track(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """
        Search for tracks.

        Args:
            query: Search query
            access_token: OAuth access token
            limit: Maximum number of results

        Returns:
            Search results

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        params: dict[str, str | int] = {
            "q": query,
            "type": "track",
            "limit": limit,
        }

        response = await client.get(
            f"{self.API_BASE_URL}/search",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def __aenter__(self) -> "SpotifyClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
