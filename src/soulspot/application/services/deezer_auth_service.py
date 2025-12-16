"""Deezer OAuth Authentication Service.

Hey future me - this service encapsulates ALL Deezer OAuth operations!
Similar to SpotifyAuthService, but with Deezer-specific differences.

KEY DIFFERENCES FROM SPOTIFY:
1. NO PKCE - Deezer uses simple OAuth 2.0 (no code_verifier)
2. NO REFRESH TOKENS - Deezer tokens are long-lived but can expire/be revoked
3. SIMPLER FLOW - Just state for CSRF protection, no code_challenge

OAuth Flow:
1. generate_auth_url() -> Get URL + state
2. User visits URL, grants access
3. exchange_code() -> Get access_token (no refresh_token!)
4. validate_token() -> Check if token still works

Token Storage:
- This service does NOT store tokens!
- Caller (auth router) stores in SessionStore + Database
- Service is stateless for better testability

NOTE: Unlike Spotify, Deezer tokens can last months with offline_access
permission. But they CAN be revoked or expire eventually. Handle gracefully!
"""

import logging
import secrets
from dataclasses import dataclass

from soulspot.infrastructure.integrations.deezer_client import (
    DeezerClient,
    DeezerOAuthConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class DeezerAuthUrlResult:
    """Result of auth URL generation.

    Hey future me - simpler than Spotify! No code_verifier needed.
    Just store state for CSRF verification in callback.
    """

    authorization_url: str
    state: str


@dataclass
class DeezerTokenResult:
    """Result of token exchange.

    Hey future me - NO REFRESH TOKEN! Deezer tokens are long-lived.
    expires_in=0 means "never" (with offline_access permission).
    """

    access_token: str
    expires_in: int  # 0 = never expires (with offline_access)


class DeezerAuthService:
    """Service for Deezer OAuth authentication.

    Hey future me - this is the CLEAN interface for Deezer OAuth!
    Similar to SpotifyAuthService but without PKCE complexity.
    """

    def __init__(self, oauth_config: DeezerOAuthConfig) -> None:
        """Initialize auth service.

        Args:
            oauth_config: Deezer OAuth configuration (app_id, secret, redirect_uri)
        """
        self._client = DeezerClient(oauth_config=oauth_config)

    # Hey future me - simpler than Spotify! No PKCE, just state.
    async def generate_auth_url(
        self, state: str | None = None
    ) -> DeezerAuthUrlResult:
        """Generate OAuth authorization URL.

        Creates a cryptographically secure state for CSRF protection.
        Unlike Spotify, Deezer doesn't use PKCE!

        Args:
            state: Optional CSRF state (generated if None)

        Returns:
            DeezerAuthUrlResult with URL and state

        Raises:
            ValueError: If OAuth is not configured
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        authorization_url = self._client.get_authorization_url(state)

        logger.debug(f"Generated Deezer auth URL with state={state[:8]}...")

        return DeezerAuthUrlResult(
            authorization_url=authorization_url,
            state=state,
        )

    # Hey future me - simpler than Spotify! No code_verifier needed.
    async def exchange_code(self, code: str) -> DeezerTokenResult:
        """Exchange authorization code for access token.

        Unlike Spotify:
        - No code_verifier needed (no PKCE)
        - No refresh_token returned (tokens are long-lived)
        - expires=0 means "never expires" (with offline_access)

        Args:
            code: Authorization code from Deezer callback

        Returns:
            DeezerTokenResult with access_token

        Raises:
            ValueError: If OAuth is not configured
            httpx.HTTPError: If token exchange fails
        """
        token_data = await self._client.exchange_code(code)

        logger.info("Successfully exchanged Deezer code for token")

        return DeezerTokenResult(
            access_token=token_data["access_token"],
            expires_in=token_data.get("expires", 0),  # 0 = never expires
        )

    # Hey future me - Deezer has no refresh! User must re-auth if revoked.
    async def validate_token(self, access_token: str) -> bool:
        """Validate an access token by making a test API call.

        Makes a lightweight API call to /user/me to check if token is valid.

        Args:
            access_token: Token to validate

        Returns:
            True if token is valid, False if expired/revoked
        """
        try:
            await self._client.get_user_me(access_token)
            return True
        except Exception:
            return False

    async def get_user_info(self, access_token: str) -> dict:
        """Get current user's profile using token.

        Wrapper for get_user_me that returns user profile.
        Useful for displaying username after auth.

        Args:
            access_token: Valid OAuth token

        Returns:
            User profile dict (id, name, email, etc.)

        Raises:
            httpx.HTTPError: If token is invalid
        """
        return await self._client.get_user_me(access_token)

    async def close(self) -> None:
        """Close the underlying HTTP client.

        Call this when done with the service to free resources.
        """
        await self._client.close()

    # Context manager support for clean resource management
    async def __aenter__(self) -> "DeezerAuthService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
