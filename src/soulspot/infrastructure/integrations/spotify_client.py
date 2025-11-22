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
    TOKEN_URL = "https://accounts.spotify.com/api/token"  # nosec B105 - this is a public API endpoint URL, not a password
    API_BASE_URL = "https://api.spotify.com/v1"

    # Hey future me, this init is deceptively simple - we DON'T create the HTTP client here
    # because we need to be async-friendly. The actual client gets lazy-loaded in _get_client().
    # If you try to create httpx.AsyncClient here, you'll get weird asyncio loop issues.
    def __init__(self, settings: SpotifySettings) -> None:
        """
        Initialize Spotify client.

        Args:
            settings: Spotify configuration settings
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    # Listen up, future me: This is our lazy HTTP client factory. Timeout is 30s because
    # Spotify can be SLOW sometimes, especially for playlist fetches with tons of tracks.
    # Don't reduce this timeout unless you like getting random timeouts on big playlists.
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    # Hey, this close() is IMPORTANT - if you don't call it, you'll leak connections and
    # eventually run out of file descriptors. Always use this client as an async context
    # manager (async with) or explicitly call close() in finally blocks. Trust me on this.
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # Yo future me, PKCE is that OAuth security dance Spotify requires. This generates a
    # random 32-byte code verifier. We strip the "=" padding because OAuth specs say so.
    # The verifier MUST be stored securely - if someone steals it during auth flow, they
    # can hijack the token exchange. Don't log this value or put it in URLs!
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

    # Hey, this is the other half of PKCE - we SHA256 hash the verifier to create the
    # challenge. The challenge goes in the auth URL (public), but only we know the verifier
    # (secret). Spotify will verify them later. Again, strip "=" padding for OAuth compliance.
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

    # Listen future me, this builds the URL to send users to Spotify for auth. The scopes
    # listed here are MINIMAL - we only ask for read permissions. If you need write access
    # (like modifying playlists), you'll need to add more scopes. But remember: users get
    # scared by too many permissions, so only add what you actually need. The state param
    # prevents CSRF attacks - ALWAYS validate it matches when the user comes back!
    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """
        Generate Spotify OAuth authorization URL.

        Args:
            state: State parameter for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            Authorization URL

        Raises:
            ValueError: If redirect_uri is not configured
        """
        # Hey future me, ALWAYS validate redirect_uri is set before building auth URL!
        # Empty redirect_uri causes cryptic Spotify errors. Better to fail fast here
        # with a clear message than let user hit Spotify's error page.
        if not self.settings.redirect_uri or not self.settings.redirect_uri.strip():
            raise ValueError(
                "SPOTIFY_REDIRECT_URI is not configured. "
                "Set it in .env to match your callback URL "
                "(e.g., http://localhost:8000/api/auth/callback)"
            )

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

    # Yo future me, this is THE critical step after user auth. We send the code + verifier
    # to Spotify and get back tokens. IMPORTANT: This code is single-use and expires in 10
    # minutes! If the user takes forever on the auth screen, this will fail. Also, the
    # redirect_uri MUST match EXACTLY what we used in get_authorization_url(), or Spotify
    # will reject it. And yeah, it HAS to be form-urlencoded, not JSON. Don't ask why.
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

    # Hey future me, access tokens expire after 1 hour. This is how you get a new one without
    # making the user re-authorize. The refresh token is long-lived (usually doesn't expire).
    # BUT if the user revokes access or your app gets de-authorized, this will fail with 400.
    # Handle that gracefully by redirecting them back to the auth flow. Don't spam this
    # endpoint - only refresh when you actually need a new token, not preemptively!
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

    # Listen up, this fetches a playlist with ALL its details. Beware: Spotify paginates track
    # lists after 100 tracks. So if you have a massive playlist (500+ tracks), you'll only get
    # the first 100 here. You'll need to follow the 'next' URL in the response to get more.
    # This has bitten me before - don't assume you got everything! Also, private playlists
    # require the playlist-read-private scope or you'll get 403.
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

    # Hey, straightforward track fetch. Nothing tricky here. But remember: if a track gets
    # removed from Spotify (regional licensing, artist request, etc.), this returns 404.
    # Don't panic - it's not a bug. Just handle it gracefully and mark the track as unavailable.
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

    # Yo future me, Spotify search is... interesting. It uses their own query syntax with
    # operators like "artist:" and "album:". The default limit is 20 which is usually fine.
    # Pro tip: Search quality REALLY improves if you include artist name in the query.
    # Also, search results are ranked by "popularity" which doesn't always match what you
    # want - sometimes the obscure live version ranks higher than the studio version. Fun!
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

    # Listen future me, this gets an artist's albums AND singles (hence include_groups).
    # Default limit is 50 but artists like Bob Dylan have 500+ releases (compilations, live,
    # etc.). You'll need pagination for prolific artists. Also, Spotify groups "appears_on"
    # separately - we DON'T include those here because that's features/compilations and would
    # flood the results. If you need those, add "appears_on" to include_groups. You've been
    # warned: it's a LOT of data for some artists!
    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get albums for an artist.

        Args:
            artist_id: Spotify artist ID
            access_token: OAuth access token
            limit: Maximum number of albums to return

        Returns:
            List of album objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        params: dict[str, str | int] = {
            "include_groups": "album,single",
            "limit": limit,
        }

        response = await client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}/albums",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result = cast(dict[str, Any], response.json())
        return cast(list[dict[str, Any]], result.get("items", []))

    # Hey future me, these context manager methods let you use this client with
    # "async with SpotifyClient(...) as client:" syntax. This is THE preferred way
    # to use this client - it guarantees cleanup even if exceptions happen. Use it!
    async def __aenter__(self) -> "SpotifyClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
