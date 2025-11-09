"""Token management service for OAuth tokens."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from soulspot.domain.ports import ISpotifyClient


@dataclass
class TokenInfo:
    """Information about an OAuth token."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime
    token_type: str = "Bearer"
    scope: str | None = None

    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.now(UTC) >= self.expires_at

    def expires_soon(self, threshold_seconds: int = 300) -> bool:
        """Check if token expires within threshold.

        Args:
            threshold_seconds: Time threshold in seconds (default 5 minutes)

        Returns:
            True if token expires within threshold
        """
        return datetime.now(UTC) >= (
            self.expires_at - timedelta(seconds=threshold_seconds)
        )


class TokenManager:
    """Service for managing OAuth tokens with automatic refresh.

    This service:
    1. Stores OAuth tokens (access and refresh tokens)
    2. Checks token expiration
    3. Automatically refreshes expired tokens
    4. Generates OAuth PKCE parameters
    5. Handles authorization flow
    """

    def __init__(self, spotify_client: ISpotifyClient) -> None:
        """Initialize token manager.

        Args:
            spotify_client: Spotify client for token operations
        """
        self._spotify_client = spotify_client
        self._tokens: dict[str, TokenInfo] = {}

    def generate_auth_state(self) -> str:
        """Generate a random state parameter for OAuth.

        Returns:
            Random state string for CSRF protection
        """
        return secrets.token_urlsafe(32)

    async def get_authorization_url(
        self, state: str | None = None
    ) -> tuple[str, str, str]:
        """Get Spotify authorization URL for OAuth PKCE flow.

        Args:
            state: Optional state parameter, generated if not provided

        Returns:
            Tuple of (authorization URL, state, code verifier)
        """
        if not state:
            state = self.generate_auth_state()

        # Generate PKCE code verifier
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

        code_verifier = SpotifyClient.generate_code_verifier()

        # Get authorization URL
        auth_url = await self._spotify_client.get_authorization_url(
            state, code_verifier
        )

        return auth_url, state, code_verifier

    async def exchange_authorization_code(
        self,
        code: str,
        code_verifier: str,
        user_id: str | None = None,
    ) -> TokenInfo:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier used in authorization
            user_id: Optional user ID to associate token with

        Returns:
            TokenInfo with access and refresh tokens
        """
        # Exchange code for tokens
        token_response = await self._spotify_client.exchange_code(code, code_verifier)

        # Calculate expiration time
        expires_in = token_response.get("expires_in", 3600)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        # Create TokenInfo
        token_info = TokenInfo(
            access_token=token_response["access_token"],
            refresh_token=token_response.get("refresh_token"),
            expires_at=expires_at,
            token_type=token_response.get("token_type", "Bearer"),
            scope=token_response.get("scope"),
        )

        # Store token if user_id provided
        if user_id:
            self._tokens[user_id] = token_info

        return token_info

    async def get_valid_token(self, user_id: str) -> str | None:
        """Get a valid access token, refreshing if necessary.

        Args:
            user_id: User ID associated with the token

        Returns:
            Valid access token or None if not available
        """
        token_info = self._tokens.get(user_id)
        if not token_info:
            return None

        # Refresh if expired or expiring soon
        if token_info.expires_soon():
            if token_info.refresh_token:
                try:
                    await self.refresh_token(user_id)
                    token_info = self._tokens.get(user_id)
                    if token_info:
                        return token_info.access_token
                except Exception:
                    # If refresh fails, token might be invalid
                    return None
            else:
                # No refresh token available
                return None

        return token_info.access_token

    async def refresh_token(self, user_id: str) -> TokenInfo:
        """Refresh an expired access token.

        Args:
            user_id: User ID associated with the token

        Returns:
            New TokenInfo with refreshed access token

        Raises:
            ValueError: If no token found for user or no refresh token available
        """
        token_info = self._tokens.get(user_id)
        if not token_info:
            raise ValueError(f"No token found for user: {user_id}")

        if not token_info.refresh_token:
            raise ValueError(f"No refresh token available for user: {user_id}")

        # Refresh the token
        token_response = await self._spotify_client.refresh_token(
            token_info.refresh_token
        )

        # Calculate new expiration time
        expires_in = token_response.get("expires_in", 3600)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        # Update token info
        new_token_info = TokenInfo(
            access_token=token_response["access_token"],
            refresh_token=token_response.get("refresh_token", token_info.refresh_token),
            expires_at=expires_at,
            token_type=token_response.get("token_type", "Bearer"),
            scope=token_response.get("scope", token_info.scope),
        )

        # Store updated token
        self._tokens[user_id] = new_token_info

        return new_token_info

    def store_token(self, user_id: str, token_info: TokenInfo) -> None:
        """Store token information for a user.

        Args:
            user_id: User ID to associate token with
            token_info: Token information to store
        """
        self._tokens[user_id] = token_info

    def get_token_info(self, user_id: str) -> TokenInfo | None:
        """Get token information for a user.

        Args:
            user_id: User ID

        Returns:
            TokenInfo if available, None otherwise
        """
        return self._tokens.get(user_id)

    def revoke_token(self, user_id: str) -> bool:
        """Revoke (delete) token for a user.

        Args:
            user_id: User ID

        Returns:
            True if token was revoked, False if no token found
        """
        if user_id in self._tokens:
            del self._tokens[user_id]
            return True
        return False

    def list_user_ids(self) -> list[str]:
        """List all user IDs with stored tokens.

        Returns:
            List of user IDs
        """
        return list(self._tokens.keys())
