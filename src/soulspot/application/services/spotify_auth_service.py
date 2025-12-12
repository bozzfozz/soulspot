"""Spotify OAuth Authentication Service.

Hey future me - this service encapsulates ALL Spotify OAuth operations!
It wraps SpotifyClient's low-level OAuth methods and provides a clean interface.

Why a separate service?
1. Keeps auth.py router thin (just HTTP handling)
2. OAuth logic is reusable (e.g., from CLI, tests)
3. Clean separation: SpotifyPlugin for API calls, SpotifyAuthService for OAuth
4. Testable - can mock the service in router tests

OAuth Flow:
1. generate_auth_url() -> Get URL + PKCE verifier
2. User visits URL, grants access
3. exchange_code() -> Get tokens from code
4. refresh_token() -> Refresh when expired

Token Storage:
- This service does NOT store tokens!
- Caller (auth router) stores in SessionStore + DatabaseTokenManager
- Service is stateless for better testability
"""

import logging
import secrets
from dataclasses import dataclass
from typing import Any

from soulspot.config import SpotifyConfig
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


@dataclass
class AuthUrlResult:
    """Result of auth URL generation.

    Hey future me - BOTH url AND code_verifier are needed!
    Store code_verifier securely (session) for token exchange.
    """

    authorization_url: str
    state: str
    code_verifier: str


@dataclass
class TokenResult:
    """Result of token operations.

    Hey future me - refresh_token might be None on refresh!
    Spotify doesn't always return a new refresh_token.
    """

    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str
    scope: str | None


class SpotifyAuthService:
    """Service for Spotify OAuth authentication.

    Hey future me - this is the CLEAN interface for OAuth!
    All OAuth complexity is hidden here. Router just calls these methods.
    """

    def __init__(self, spotify_config: SpotifyConfig) -> None:
        """Initialize auth service.

        Args:
            spotify_config: Spotify configuration with client_id, etc.
        """
        self._client = SpotifyClient(spotify_config)

    # Hey future me - this generates BOTH the URL AND the PKCE verifier!
    # The verifier is critical - without it, token exchange fails.
    # Store the verifier securely (session cookie or DB) before redirecting user.
    async def generate_auth_url(
        self, state: str | None = None
    ) -> AuthUrlResult:
        """Generate OAuth authorization URL with PKCE.

        Creates a cryptographically secure state and code_verifier.
        The state is for CSRF protection, the verifier is for PKCE.

        Args:
            state: Optional CSRF state (generated if None)

        Returns:
            AuthUrlResult with URL, state, and code_verifier

        Raises:
            Exception: If URL generation fails
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        code_verifier = SpotifyClient.generate_code_verifier()

        authorization_url = await self._client.get_authorization_url(
            state, code_verifier
        )

        logger.debug(f"Generated auth URL with state={state[:8]}...")

        return AuthUrlResult(
            authorization_url=authorization_url,
            state=state,
            code_verifier=code_verifier,
        )

    # Hey future me - this is the CRITICAL part of OAuth!
    # The code_verifier MUST match what was used for the auth URL.
    # If they don't match, Spotify rejects the request (PKCE security).
    async def exchange_code(
        self, code: str, code_verifier: str
    ) -> TokenResult:
        """Exchange authorization code for tokens.

        This is the second step of OAuth PKCE flow.
        The code_verifier must match the one used for auth URL generation.

        Args:
            code: Authorization code from Spotify callback
            code_verifier: PKCE verifier stored during auth URL generation

        Returns:
            TokenResult with access_token, refresh_token, etc.

        Raises:
            Exception: If token exchange fails
        """
        token_data = await self._client.exchange_code(code, code_verifier)

        logger.info("Successfully exchanged code for tokens")

        return TokenResult(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
        )

    # Hey future me - Spotify tokens expire after 1 hour!
    # Use refresh_token to get a new access_token without user interaction.
    # IMPORTANT: Spotify might NOT return a new refresh_token - keep the old one!
    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """Refresh an expired access token.

        Uses the refresh_token to obtain a new access_token.
        Spotify might or might not return a new refresh_token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            TokenResult with new access_token (refresh_token may be None)

        Raises:
            Exception: If refresh fails (e.g., revoked token)
        """
        token_data = await self._client.refresh_token(refresh_token)

        logger.debug("Successfully refreshed access token")

        return TokenResult(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),  # May be None!
            expires_in=token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
        )

    # Hey future me - validate tokens by making a test API call.
    # Returns True if token works, False if expired/invalid.
    # Useful for UI "connection status" checks.
    async def validate_token(self, access_token: str) -> bool:
        """Validate an access token by making a test API call.

        Makes a lightweight API call to check if the token is valid.

        Args:
            access_token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Use get_current_user as a lightweight validation call
            await self._client.get_current_user(access_token)
            return True
        except Exception:
            return False

    # Hey future me - this is a STATIC helper for PKCE!
    # Can be called without an instance for testing.
    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """Generate a PKCE code_verifier and code_challenge pair.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        verifier = SpotifyClient.generate_code_verifier()
        challenge = SpotifyClient.generate_code_challenge(verifier)
        return verifier, challenge
