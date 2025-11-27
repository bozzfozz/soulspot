"""Token management service for OAuth tokens."""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from soulspot.domain.ports import ISpotifyClient

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Information about an OAuth token."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime
    token_type: str = "Bearer"
    scope: str | None = None
    is_valid: bool = True  # Added for DB-backed tokens

    # Hey future me, this is a simple expiry check - is NOW >= expires_at? Returns True if expired.
    # Important: we compare using UTC everywhere to avoid timezone headaches! Don't mix timezone-aware
    # and timezone-naive datetimes or you'll get weird comparison errors. If expires_at is None (shouldn't
    # happen but defensive), this will crash - but that's a bug we want to know about!
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.now(UTC) >= self.expires_at

    # Yo, this is for PROACTIVE refresh - don't wait until token is expired, refresh it BEFORE! Default
    # threshold is 5 minutes (300s). So if token expires at 3:00pm and it's 2:56pm, this returns True.
    # Why? Network delays, clock drift, processing time - better to refresh early than get 401 errors
    # mid-request! You can tune threshold per use case - background jobs might use longer (10 min),
    # user-facing API calls might use shorter (1 min).
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


@dataclass
class TokenStatus:
    """Token status for UI display and API responses."""

    exists: bool
    is_valid: bool
    needs_reauth: bool
    expires_in_minutes: int | None
    last_error: str | None
    last_error_at: datetime | None


class TokenManager:
    """Service for managing OAuth tokens with automatic refresh.

    This service:
    1. Stores OAuth tokens (access and refresh tokens)
    2. Checks token expiration
    3. Automatically refreshes expired tokens
    4. Generates OAuth PKCE parameters
    5. Handles authorization flow
    """

    # Listen up future me, this TokenManager is ALSO in-memory storage (dict)! Same problems as SessionStore -
    # server restart loses all tokens, no sharing across app instances. The _tokens dict is keyed by user_id
    # (which is... what exactly? Session ID? Spotify user ID? Be careful!). In production, move to Redis
    # or encrypted DB storage. Tokens are SECRETS - if someone steals them, they can access Spotify as that user!
    def __init__(self, spotify_client: ISpotifyClient) -> None:
        """Initialize token manager.

        Args:
            spotify_client: Spotify client for token operations
        """
        self._spotify_client = spotify_client
        self._tokens: dict[str, TokenInfo] = {}

    # Hey, this generates the OAuth "state" parameter for CSRF protection. It's a random 32-byte string
    # (urlsafe encoding). We send this to Spotify, they return it in callback, we verify it matches.
    # If it doesn't match, someone is trying to replay an old auth code! Use secrets module NOT random -
    # secrets is cryptographically secure, random is predictable and DANGEROUS for security tokens!
    def generate_auth_state(self) -> str:
        """Generate a random state parameter for OAuth.

        Returns:
            Random state string for CSRF protection
        """
        return secrets.token_urlsafe(32)

    # Yo, this is the FIRST step of OAuth PKCE flow - generate auth URL with state and code_verifier.
    # If state is None, we auto-generate one (convenient for callers). The code_verifier is generated
    # HERE but must be stored somewhere (session, DB) because we need it later to exchange the code!
    # Don't lose the code_verifier or OAuth flow fails! Returns all three (URL, state, verifier) so
    # caller can store state+verifier before redirecting user.
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

    # Listen future me, this is the OAuth callback handler - we got an auth code from Spotify, now exchange
    # it for access+refresh tokens. The code_verifier MUST be the same one used in get_authorization_url!
    # Spotify verifies the PKCE challenge - if verifier doesn't match, you get 400 error. The user_id is
    # OPTIONAL - if provided, we auto-store the token in our dict. If not, caller must store it manually.
    # expires_in from Spotify is usually 3600 (1 hour). We calculate absolute expires_at timestamp.
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

    # Hey, this is your "give me a valid token" helper - handles ALL the refresh logic automatically!
    # If token doesn't exist, returns None. If token exists but is expired/expiring-soon, tries to refresh
    # it using refresh_token. If refresh fails (network error, invalid refresh token, etc), logs warning
    # and returns None. This means callers get None for BOTH "no token" and "refresh failed" - they can't
    # distinguish! The expires_soon() check (5 min threshold) means we proactively refresh before expiry.
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
                    refreshed_token = self._tokens.get(user_id)
                    if refreshed_token:
                        return refreshed_token.access_token
                    return None
                except (httpx.HTTPError, ValueError) as e:
                    # If refresh fails, token might be invalid
                    logger.warning(
                        "Failed to refresh token for user %s: %s",
                        user_id,
                        e,
                        exc_info=True,
                    )
                    return None
            else:
                # No refresh token available
                return None

        return token_info.access_token

    # Yo, this is the low-level refresh operation - call Spotify's token endpoint with refresh_token,
    # get new access_token (and maybe new refresh_token). If no token found or no refresh_token, raises
    # ValueError. The new refresh_token from Spotify is OPTIONAL - if they don't provide one, we keep
    # using the old one (important!). We preserve scope if Spotify doesn't return it. Updates the stored
    # token in _tokens dict. This can fail with httpx errors if Spotify is down or refresh_token is invalid.
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

    # Hey, this is a simple setter - store token for user_id. Overwrites existing token if any. Use this
    # after manual token acquisition or when migrating tokens from another storage. No validation here -
    # we trust the caller to provide valid TokenInfo! Could store expired tokens, None tokens, etc.
    def store_token(self, user_id: str, token_info: TokenInfo) -> None:
        """Store token information for a user.

        Args:
            user_id: User ID to associate token with
            token_info: Token information to store
        """
        self._tokens[user_id] = token_info

    # Yo, simple getter - returns TokenInfo for user or None if not found. The returned TokenInfo might
    # be expired! Caller should check is_expired() or use get_valid_token() instead if they need a fresh
    # token. This is for inspection/debugging more than actual use.
    def get_token_info(self, user_id: str) -> TokenInfo | None:
        """Get token information for a user.

        Args:
            user_id: User ID

        Returns:
            TokenInfo if available, None otherwise
        """
        return self._tokens.get(user_id)

    # Listen, revoke means DELETE - the token is removed from our storage. We don't actually call Spotify's
    # token revocation endpoint! The token is still valid on Spotify's side, we just forget about it locally.
    # If you want true revocation (invalidate token at Spotify), you need to add that API call! Returns
    # True if deleted, False if user_id not found (idempotent).
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

    # Hey, this is for admin/debugging - list all user_ids that have tokens stored. Useful for cleanup,
    # monitoring, or finding orphaned tokens. The list could be HUGE if you have thousands of users!
    # Consider pagination if this grows large. Returns list of dict keys - order is not guaranteed.
    def list_user_ids(self) -> list[str]:
        """List all user IDs with stored tokens.

        Returns:
            List of user IDs
        """
        return list(self._tokens.keys())


# =============================================================================
# DATABASE TOKEN MANAGER (Background Worker Token Storage)
# =============================================================================
# Hey future me - THIS is the NEW token manager for production! Replaces in-memory dict
# with database persistence. Single-user architecture: one token for all background workers.
#
# Key differences from TokenManager:
# - Tokens survive server restarts (DB-backed)
# - Background workers use get_token_for_background() to get THE token
# - is_valid flag controls UI warning banner
# - TokenRefreshWorker calls refresh_expiring_tokens() every 5 min
#
# The workflow:
# 1. User logs in via OAuth → store_from_oauth() saves token to DB
# 2. Background workers call get_token_for_background() → get valid token or None
# 3. TokenRefreshWorker calls refresh_expiring_tokens() every 5 min
# 4. If refresh fails → mark_invalid() sets is_valid=False → UI shows warning
# 5. User re-authenticates → store_from_oauth() resets is_valid=True
# =============================================================================


class DatabaseTokenManager:
    """Database-backed token manager for background workers.

    Single-user architecture: manages exactly one token for all background work.
    Background workers call get_token_for_background() to get a valid access token.

    The is_valid flag triggers UI warning when False (user must re-authenticate).
    Workers gracefully skip work when token is invalid (no crash loop).

    Key methods:
    - get_token_for_background(): Get valid token for workers (None if invalid)
    - store_from_oauth(): Save token after OAuth callback
    - refresh_expiring_tokens(): Proactive refresh (called by TokenRefreshWorker)
    - get_status(): Get token status for UI display
    """

    def __init__(
        self,
        spotify_client: ISpotifyClient,
        get_db_session: Any,  # Async generator function that yields AsyncSession
    ) -> None:
        """Initialize database token manager.

        Args:
            spotify_client: Spotify client for refresh operations
            get_db_session: Async function that yields database sessions
        """
        self._spotify_client = spotify_client
        self._get_db_session = get_db_session

    # Hey future me - THIS is the main method for background workers! Returns access_token string
    # if valid token exists, None otherwise. Workers should check for None and skip work gracefully.
    # Does NOT auto-refresh - that's TokenRefreshWorker's job (runs every 5 min).
    async def get_token_for_background(self) -> str | None:
        """Get valid access token for background workers.

        Returns the access_token string if a valid token exists.
        Returns None if:
        - No token exists (user never authenticated)
        - Token is invalid (refresh failed, user revoked access)
        - Token is expired (shouldn't happen if TokenRefreshWorker is running)

        Background workers should check for None and skip work gracefully.

        Returns:
            Access token string or None
        """
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        async for db_session in self._get_db_session():
            try:
                repo = SpotifyTokenRepository(db_session)
                token_model = await repo.get_active_token()

                if not token_model:
                    logger.debug("No active token available for background work")
                    return None

                # Check if expired (shouldn't happen with TokenRefreshWorker)
                if token_model.is_expired():
                    logger.warning(
                        "Token is expired - TokenRefreshWorker may not be running"
                    )
                    return None

                return token_model.access_token

            finally:
                await db_session.close()
            break

        return None

    # Yo - OAuth callback calls this! Stores new token after successful authentication.
    # Sets is_valid=True and clears any previous errors. This is the "reset" point.
    async def store_from_oauth(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        scope: str | None = None,
    ) -> None:
        """Store token after successful OAuth authentication.

        Called by auth callback after user completes Spotify OAuth flow.
        Creates or updates the single token row. Sets is_valid=True.

        Args:
            access_token: Access token from Spotify
            refresh_token: Refresh token from Spotify
            expires_in: Token lifetime in seconds (usually 3600)
            scope: Space-separated scopes granted (optional)
        """
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        async for db_session in self._get_db_session():
            try:
                repo = SpotifyTokenRepository(db_session)
                await repo.upsert_token(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=expires_at,
                    scopes=scope,
                )
                await db_session.commit()
                logger.info("Stored OAuth token (expires in %d seconds)", expires_in)
            except Exception as e:
                logger.error(f"Failed to store OAuth token: {e}")
                await db_session.rollback()
                raise
            finally:
                await db_session.close()
            break

    # Listen - TokenRefreshWorker calls this every 5 min! Checks if token expires soon
    # and proactively refreshes it. If refresh fails, marks token invalid (triggers UI warning).
    async def refresh_expiring_tokens(self, threshold_minutes: int = 10) -> bool:
        """Proactively refresh tokens expiring soon.

        Called by TokenRefreshWorker every 5 minutes. Checks if token expires
        within threshold_minutes and refreshes if needed.

        If refresh fails (401, 403, network error), marks token as invalid
        which triggers the UI warning banner.

        Args:
            threshold_minutes: Refresh tokens expiring within this many minutes

        Returns:
            True if refresh was performed, False if no refresh needed/possible
        """
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        async for db_session in self._get_db_session():
            try:
                repo = SpotifyTokenRepository(db_session)
                token_model = await repo.get_expiring_soon(minutes=threshold_minutes)

                if not token_model:
                    # No token expiring soon, nothing to do
                    return False

                logger.info(
                    "Token expires at %s, refreshing proactively",
                    token_model.token_expires_at.isoformat(),
                )

                try:
                    # Call Spotify to refresh
                    token_response = await self._spotify_client.refresh_token(
                        token_model.refresh_token
                    )

                    # Calculate new expiration
                    expires_in = token_response.get("expires_in", 3600)
                    new_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

                    # Update in DB
                    await repo.update_after_refresh(
                        access_token=token_response["access_token"],
                        token_expires_at=new_expires_at,
                        refresh_token=token_response.get(
                            "refresh_token"
                        ),  # Spotify may rotate
                    )
                    await db_session.commit()

                    logger.info(
                        "Token refreshed successfully (expires in %ds)", expires_in
                    )
                    return True

                except httpx.HTTPStatusError as e:
                    # HTTP error from Spotify (401, 403 = user revoked access)
                    error_msg = f"Spotify refresh failed: HTTP {e.response.status_code}"
                    logger.error(error_msg)
                    await repo.mark_invalid(error_msg)
                    await db_session.commit()
                    return False

                except httpx.HTTPError as e:
                    # Network error (timeout, connection refused, etc.)
                    error_msg = f"Network error during refresh: {str(e)}"
                    logger.error(error_msg)
                    # Don't mark invalid for network errors - might be temporary
                    # Let next refresh cycle retry
                    return False

                except Exception as e:
                    # Unexpected error
                    error_msg = f"Unexpected refresh error: {str(e)}"
                    logger.exception(error_msg)
                    await repo.mark_invalid(error_msg)
                    await db_session.commit()
                    return False

            finally:
                await db_session.close()
            break

        return False

    # Hey - UI calls this for the token status endpoint and warning banner!
    # Returns structured status info regardless of token validity.
    async def get_status(self) -> TokenStatus:
        """Get token status for UI display and /api/auth/token-status.

        Returns comprehensive status including:
        - Whether token exists
        - Whether token is valid
        - Whether re-authentication is needed
        - Time until expiration
        - Last error (if any)

        Returns:
            TokenStatus dataclass with all status info
        """
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        async for db_session in self._get_db_session():
            try:
                repo = SpotifyTokenRepository(db_session)
                token_model = await repo.get_token_status()

                if not token_model:
                    return TokenStatus(
                        exists=False,
                        is_valid=False,
                        needs_reauth=True,
                        expires_in_minutes=None,
                        last_error=None,
                        last_error_at=None,
                    )

                # Calculate expires_in_minutes
                now = datetime.now(UTC)
                if token_model.token_expires_at > now:
                    delta = token_model.token_expires_at - now
                    expires_in_minutes = int(delta.total_seconds() / 60)
                else:
                    expires_in_minutes = 0

                return TokenStatus(
                    exists=True,
                    is_valid=token_model.is_valid,
                    needs_reauth=not token_model.is_valid or token_model.is_expired(),
                    expires_in_minutes=expires_in_minutes,
                    last_error=token_model.last_error,
                    last_error_at=token_model.last_error_at,
                )

            finally:
                await db_session.close()
            break

        # Fallback (shouldn't reach here)
        return TokenStatus(
            exists=False,
            is_valid=False,
            needs_reauth=True,
            expires_in_minutes=None,
            last_error=None,
            last_error_at=None,
        )

    # Yo - manually mark token as invalid (e.g., user clicked "disconnect Spotify")
    async def invalidate(self) -> bool:
        """Manually invalidate the token.

        Use this when user wants to disconnect Spotify or on explicit logout.
        Sets is_valid=False which triggers UI warning.

        Returns:
            True if token was invalidated, False if no token exists
        """
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        async for db_session in self._get_db_session():
            try:
                repo = SpotifyTokenRepository(db_session)
                result = await repo.mark_invalid("Manually invalidated by user")
                await db_session.commit()
                return result
            finally:
                await db_session.close()
            break

        return False
