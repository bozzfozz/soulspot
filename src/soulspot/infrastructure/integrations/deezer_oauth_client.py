"""⚠️ DEPRECATED - DO NOT USE! ⚠️

This file is DEPRECATED and scheduled for removal.

REASON: All OAuth functionality has been implemented in deezer_client.py.
This file was a stub that never got implemented - all methods raise NotImplementedError.

USE INSTEAD:
    from soulspot.infrastructure.integrations.deezer_client import DeezerClient

    # DeezerClient has ALL the OAuth functionality:
    # - get_user_favorites()
    # - get_user_playlists()
    # - get_user_albums()
    # - get_followed_artists()

DELETE THIS FILE when cleaning up the codebase.
File location: src/soulspot/infrastructure/integrations/deezer_oauth_client.py

-------------------------------------------------------------------------------
Original docstring (kept for reference):
-------------------------------------------------------------------------------

Deezer OAuth client stub for future user integration.

Hey future me - this is a STUB for future Deezer OAuth integration!
The existing DeezerClient (deezer_client.py) handles PUBLIC API calls for metadata.
THIS file handles OAuth-authenticated user operations (favorites, playlists, etc.)

When to use which:
- DeezerClient (existing): Album/artist/track metadata (no auth needed)
- DeezerOAuthClient (this): User favorites, playlists (requires OAuth)

Implementation notes:

1. Get Deezer API credentials:
   - Register at https://developers.deezer.com/
   - Create application
   - Get App ID and Secret Key

2. Implement OAuth flow:
   - Deezer uses simple OAuth 2.0 (no PKCE)
   - Auth URL: https://connect.deezer.com/oauth/auth.php
   - Token URL: https://connect.deezer.com/oauth/access_token.php
   - NOTE: Deezer tokens don't refresh! They expire after ~30 days

3. Add configuration:
   - DEEZER_APP_ID in .env
   - DEEZER_SECRET_KEY in .env
   - DEEZER_REDIRECT_URI in .env

4. Create routes:
   - api/routers/deezer_auth.py (OAuth callback)
   - api/routers/deezer_sync.py (sync favorites)

5. Create session model:
   - DeezerSessionModel in models.py
   - Migration for deezer_sessions table

Rate limits: 50 requests per 5 seconds
API Base: https://api.deezer.com

IMPORTANT difference from Spotify/Tidal:
- Deezer doesn't have refresh tokens!
- User must re-authenticate when token expires (~30 days)
- Consider prompting user to re-auth before expiry
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from soulspot.domain.ports import IDeezerClient

logger = logging.getLogger(__name__)

# Emit deprecation warning on import
warnings.warn(
    "deezer_oauth_client is DEPRECATED. Use deezer_client.DeezerClient instead. "
    "All OAuth methods are implemented there. This stub will be removed.",
    DeprecationWarning,
    stacklevel=2,
)


class DeezerOAuthNotConfiguredError(Exception):
    """Raised when trying to use DeezerOAuthClient without configuration."""

    pass


class DeezerOAuthClient(IDeezerClient):
    """⚠️ DEPRECATED - Use DeezerClient instead! ⚠️

    This class is a STUB that never got implemented.
    ALL methods raise NotImplementedError.

    Use deezer_client.DeezerClient instead - it has all OAuth functionality!

    Example:
        # ❌ DON'T USE:
        from soulspot.infrastructure.integrations.deezer_oauth_client import DeezerOAuthClient

        # ✅ USE INSTEAD:
        from soulspot.infrastructure.integrations.deezer_client import DeezerClient
        client = DeezerClient()
        favorites = await client.get_user_favorites(access_token)
    """

    def __init__(
        self,
        app_id: str | None = None,
        secret_key: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """Initialize deprecated OAuth client - emits warning."""
        warnings.warn(
            "DeezerOAuthClient is DEPRECATED. Use DeezerClient instead. "
            "All OAuth methods are implemented in deezer_client.py.",
            DeprecationWarning,
            stacklevel=2,
        )
        """Initialize Deezer OAuth client.

        Args:
            app_id: Deezer application ID
            secret_key: Deezer secret key
            redirect_uri: OAuth callback URL
        """
        self.app_id = app_id
        self.secret_key = secret_key
        self.redirect_uri = redirect_uri
        self._configured = all([app_id, secret_key, redirect_uri])

        if not self._configured:
            logger.warning(
                "DeezerOAuthClient initialized without credentials. "
                "Set DEEZER_APP_ID, DEEZER_SECRET_KEY, DEEZER_REDIRECT_URI "
                "in environment to enable Deezer OAuth integration."
            )

    def _check_configured(self) -> None:
        """Raise error if client is not configured."""
        if not self._configured:
            raise DeezerOAuthNotConfiguredError(
                "Deezer OAuth integration not configured. "
                "Set DEEZER_APP_ID, DEEZER_SECRET_KEY, DEEZER_REDIRECT_URI."
            )

    # =========================================================================
    # OAUTH
    # =========================================================================

    async def get_authorization_url(self, state: str) -> str:
        """Generate Deezer OAuth authorization URL.

        Note: Deezer doesn't use PKCE (simpler OAuth flow)
        """
        self._check_configured()
        # TODO: Build URL for https://connect.deezer.com/oauth/auth.php
        # Params: app_id, redirect_uri, perms (permissions), state
        raise NotImplementedError("Deezer OAuth not yet implemented")

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Note: Deezer doesn't provide refresh_token! Token expires in ~30 days.
        Returns: {access_token, expires}
        """
        self._check_configured()
        # TODO: GET https://connect.deezer.com/oauth/access_token.php
        # Params: app_id, secret, code
        raise NotImplementedError("Deezer token exchange not yet implemented")

    # =========================================================================
    # USER DATA
    # =========================================================================

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get current user's profile info."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/user/me
        raise NotImplementedError("Deezer user info not yet implemented")

    async def get_user_playlists(
        self, access_token: str, limit: int = 50, index: int = 0
    ) -> dict[str, Any]:
        """Get current user's playlists."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/user/me/playlists
        raise NotImplementedError("Deezer playlists not yet implemented")

    async def get_favorite_artists(
        self, access_token: str, limit: int = 50, index: int = 0
    ) -> dict[str, Any]:
        """Get user's favorite (followed) artists."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/user/me/artists
        raise NotImplementedError("Deezer favorite artists not yet implemented")

    # =========================================================================
    # TRACKS
    # =========================================================================

    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """Get track details by Deezer ID."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/track/{id}
        # Note: Public API works without access_token, but we include for consistency
        raise NotImplementedError("Deezer track details not yet implemented")

    async def search_track(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for tracks."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/search/track?q={query}
        raise NotImplementedError("Deezer track search not yet implemented")

    # =========================================================================
    # ALBUMS
    # =========================================================================

    async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
        """Get album details including track list."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/album/{id}
        raise NotImplementedError("Deezer album details not yet implemented")

    async def search_album(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for albums."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/search/album?q={query}
        raise NotImplementedError("Deezer album search not yet implemented")

    # =========================================================================
    # ARTISTS
    # =========================================================================

    async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
        """Get artist details."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/artist/{id}
        raise NotImplementedError("Deezer artist details not yet implemented")

    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> dict[str, Any]:
        """Get artist's albums."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/artist/{id}/albums
        raise NotImplementedError("Deezer artist albums not yet implemented")

    async def search_artist(
        self, query: str, access_token: str, limit: int = 25
    ) -> dict[str, Any]:
        """Search for artists."""
        self._check_configured()
        # TODO: GET https://api.deezer.com/search/artist?q={query}
        raise NotImplementedError("Deezer artist search not yet implemented")
