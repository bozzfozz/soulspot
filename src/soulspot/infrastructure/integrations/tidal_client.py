"""Tidal HTTP client stub for future user integration.

Hey future me - this is a STUB for future Tidal integration!
Currently SoulSpot only supports Spotify OAuth. When you implement Tidal:

1. Get Tidal API credentials:
   - Register at https://developer.tidal.com/
   - Create OAuth application
   - Get Client ID and Client Secret

2. Implement OAuth PKCE flow:
   - Tidal uses PKCE like Spotify
   - Scopes: user.read, playlists.read, favorites.read
   - Auth URL: https://login.tidal.com/authorize
   - Token URL: https://auth.tidal.com/v1/oauth2/token

3. Add configuration:
   - TIDAL_CLIENT_ID in .env
   - TIDAL_CLIENT_SECRET in .env
   - TIDAL_REDIRECT_URI in .env

4. Create routes:
   - api/routers/tidal_auth.py (OAuth callback)
   - api/routers/tidal_sync.py (sync favorites)

5. Create session model:
   - TidalSessionModel in models.py
   - Migration for tidal_sessions table

Rate limits: 100 requests/minute
API Base: https://openapi.tidal.com/v2

Tidal-specific features to consider:
- HiFi Plus tier (Master quality, MQA/FLAC 24-bit)
- Dolby Atmos tracks
- Sony 360 Reality Audio
- Different quality tiers affect what you can play
"""

from __future__ import annotations

import logging
from typing import Any

from soulspot.domain.ports import ITidalClient

logger = logging.getLogger(__name__)


class TidalClientNotConfiguredError(Exception):
    """Raised when trying to use TidalClient without configuration."""

    pass


class TidalClient(ITidalClient):
    """Stub implementation of Tidal API client.

    This is a placeholder for future Tidal integration.
    All methods raise TidalClientNotConfiguredError until implemented.

    Hey future me - when implementing:
    1. Copy patterns from SpotifyClient (circuit breaker, rate limiting)
    2. Handle different quality tiers (HiFi vs HiFi Plus)
    3. Map Tidal responses to generic domain entities
    4. Store tidal_id on Track/Artist/Album entities
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """Initialize Tidal client.

        Args:
            client_id: Tidal OAuth client ID
            client_secret: Tidal OAuth client secret
            redirect_uri: OAuth callback URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._configured = all([client_id, client_secret, redirect_uri])

        if not self._configured:
            logger.warning(
                "TidalClient initialized without credentials. "
                "Set TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, TIDAL_REDIRECT_URI "
                "in environment to enable Tidal integration."
            )

    def _check_configured(self) -> None:
        """Raise error if client is not configured."""
        if not self._configured:
            raise TidalClientNotConfiguredError(
                "Tidal integration not configured. "
                "Set TIDAL_CLIENT_ID, TIDAL_CLIENT_SECRET, TIDAL_REDIRECT_URI."
            )

    # =========================================================================
    # OAUTH
    # =========================================================================

    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """Generate Tidal OAuth authorization URL with PKCE."""
        self._check_configured()
        # TODO: Implement Tidal OAuth PKCE
        # Base URL: https://login.tidal.com/authorize
        # Params: client_id, redirect_uri, response_type=code, scope, state, code_challenge
        raise NotImplementedError("Tidal OAuth not yet implemented")

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        self._check_configured()
        # TODO: POST to https://auth.tidal.com/v1/oauth2/token
        raise NotImplementedError("Tidal token exchange not yet implemented")

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token."""
        self._check_configured()
        # TODO: POST to https://auth.tidal.com/v1/oauth2/token with grant_type=refresh_token
        raise NotImplementedError("Tidal token refresh not yet implemented")

    # =========================================================================
    # USER DATA
    # =========================================================================

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get current user's profile and subscription info."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/users/me
        raise NotImplementedError("Tidal user info not yet implemented")

    async def get_user_playlists(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Get current user's playlists."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/users/me/playlists
        raise NotImplementedError("Tidal playlists not yet implemented")

    async def get_favorite_artists(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Get user's favorite artists."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/users/me/favorites/artists
        raise NotImplementedError("Tidal favorite artists not yet implemented")

    # =========================================================================
    # TRACKS
    # =========================================================================

    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """Get track details by Tidal ID."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/tracks/{id}
        raise NotImplementedError("Tidal track details not yet implemented")

    async def search_track(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for tracks."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/searchresults/{query}/tracks
        raise NotImplementedError("Tidal track search not yet implemented")

    # =========================================================================
    # ALBUMS
    # =========================================================================

    async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
        """Get album details including track list and quality info."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/albums/{id}
        raise NotImplementedError("Tidal album details not yet implemented")

    async def search_album(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for albums."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/searchresults/{query}/albums
        raise NotImplementedError("Tidal album search not yet implemented")

    # =========================================================================
    # ARTISTS
    # =========================================================================

    async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
        """Get artist details."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/artists/{id}
        raise NotImplementedError("Tidal artist details not yet implemented")

    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> dict[str, Any]:
        """Get artist's albums."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/artists/{id}/albums
        raise NotImplementedError("Tidal artist albums not yet implemented")

    async def search_artist(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for artists."""
        self._check_configured()
        # TODO: GET https://openapi.tidal.com/searchresults/{query}/artists
        raise NotImplementedError("Tidal artist search not yet implemented")
