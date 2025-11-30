"""Tests for Token Manager service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from soulspot.application.services.token_manager import TokenInfo, TokenManager


@pytest.fixture
def spotify_client_mock() -> AsyncMock:
    """Create mock Spotify client."""
    return AsyncMock()


@pytest.fixture
def token_manager(spotify_client_mock: AsyncMock) -> TokenManager:
    """Create token manager with mocked Spotify client."""
    return TokenManager(spotify_client=spotify_client_mock)


class TestTokenInfo:
    """Test TokenInfo dataclass."""

    def test_is_expired_false(self) -> None:
        """Test token not expired."""
        token = TokenInfo(
            access_token="test-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert token.is_expired() is False

    def test_is_expired_true(self) -> None:
        """Test token is expired."""
        token = TokenInfo(
            access_token="test-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert token.is_expired() is True

    def test_expires_soon_false(self) -> None:
        """Test token does not expire soon."""
        token = TokenInfo(
            access_token="test-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        # Default threshold is 300 seconds (5 minutes)
        assert token.expires_soon() is False

    def test_expires_soon_true(self) -> None:
        """Test token expires soon."""
        token = TokenInfo(
            access_token="test-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )
        # Default threshold is 300 seconds (5 minutes)
        assert token.expires_soon() is True

    def test_expires_soon_custom_threshold(self) -> None:
        """Test token expires soon with custom threshold."""
        token = TokenInfo(
            access_token="test-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )
        # Custom threshold of 60 seconds
        assert token.expires_soon(threshold_seconds=60) is True
        # Threshold of 10 seconds - should not expire soon
        assert token.expires_soon(threshold_seconds=10) is False


class TestTokenManager:
    """Test TokenManager service."""

    def test_generate_auth_state(self, token_manager: TokenManager) -> None:
        """Test generation of auth state."""
        state1 = token_manager.generate_auth_state()
        state2 = token_manager.generate_auth_state()

        # States should be non-empty
        assert len(state1) > 0
        assert len(state2) > 0

        # States should be unique
        assert state1 != state2

    async def test_get_authorization_url_with_state(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test getting authorization URL with provided state."""
        # Mock Spotify client
        spotify_client_mock.get_authorization_url.return_value = (
            "https://accounts.spotify.com/authorize?..."
        )

        # Get authorization URL with custom state
        state = "custom-state-123"
        (
            auth_url,
            returned_state,
            code_verifier,
        ) = await token_manager.get_authorization_url(state)

        # Assert
        assert auth_url == "https://accounts.spotify.com/authorize?..."
        assert returned_state == state
        assert len(code_verifier) > 0
        spotify_client_mock.get_authorization_url.assert_called_once()

    async def test_get_authorization_url_without_state(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test getting authorization URL without provided state."""
        # Mock Spotify client
        spotify_client_mock.get_authorization_url.return_value = (
            "https://accounts.spotify.com/authorize?..."
        )

        # Get authorization URL without state
        auth_url, state, code_verifier = await token_manager.get_authorization_url()

        # Assert
        assert auth_url == "https://accounts.spotify.com/authorize?..."
        assert len(state) > 0
        assert len(code_verifier) > 0

    async def test_exchange_authorization_code_success(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test successful authorization code exchange."""
        # Mock Spotify client response
        spotify_client_mock.exchange_code.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "playlist-read-private",
        }

        # Exchange code
        token_info = await token_manager.exchange_authorization_code(
            code="auth-code-123",
            code_verifier="code-verifier-123",
            user_id="user-123",
        )

        # Assert
        assert isinstance(token_info, TokenInfo)
        assert token_info.access_token == "new-access-token"
        assert token_info.refresh_token == "new-refresh-token"
        assert token_info.token_type == "Bearer"
        assert token_info.scope == "playlist-read-private"
        assert not token_info.is_expired()

        # Verify Spotify client was called
        spotify_client_mock.exchange_code.assert_called_once_with(
            "auth-code-123", "code-verifier-123"
        )

    async def test_get_valid_token_when_valid(
        self,
        token_manager: TokenManager,
    ) -> None:
        """Test getting valid token when token is valid."""
        # Store a valid token
        token_info = TokenInfo(
            access_token="valid-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        token_manager._tokens["user-123"] = token_info

        # Get valid token
        token = await token_manager.get_valid_token("user-123")

        # Assert
        assert token == "valid-token"

    async def test_get_valid_token_when_expired(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test getting valid token when token is expired."""
        # Store an expired token
        token_info = TokenInfo(
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        token_manager._tokens["user-123"] = token_info

        # Mock refresh token response
        spotify_client_mock.refresh_token.return_value = {
            "access_token": "refreshed-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        # Get valid token (should trigger refresh)
        token = await token_manager.get_valid_token("user-123")

        # Assert
        assert token == "refreshed-token"
        spotify_client_mock.refresh_token.assert_called_once_with("refresh-token")

    async def test_get_valid_token_when_expires_soon(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test getting valid token when token expires soon."""
        # Store a token that expires soon (in 2 minutes)
        token_info = TokenInfo(
            access_token="expiring-soon-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )
        token_manager._tokens["user-123"] = token_info

        # Mock refresh token response
        spotify_client_mock.refresh_token.return_value = {
            "access_token": "refreshed-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        # Get valid token (should trigger refresh)
        token = await token_manager.get_valid_token("user-123")

        # Assert
        assert token == "refreshed-token"
        spotify_client_mock.refresh_token.assert_called_once_with("refresh-token")

    async def test_get_valid_token_no_token(
        self,
        token_manager: TokenManager,
    ) -> None:
        """Test getting valid token when no token exists."""
        # Get valid token for user without token
        token = await token_manager.get_valid_token("nonexistent-user")

        # Assert
        assert token is None

    async def test_refresh_token_success(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test successful token refresh."""
        # Store a token with refresh token
        token_info = TokenInfo(
            access_token="old-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        token_manager._tokens["user-123"] = token_info

        # Mock refresh token response
        spotify_client_mock.refresh_token.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "playlist-read-private",
        }

        # Refresh token
        new_token_info = await token_manager.refresh_token("user-123")

        # Assert
        assert isinstance(new_token_info, TokenInfo)
        assert new_token_info.access_token == "new-token"
        assert new_token_info.refresh_token == "new-refresh-token"
        assert not new_token_info.is_expired()

        # Verify token was updated in storage
        assert token_manager._tokens["user-123"].access_token == "new-token"

    async def test_refresh_token_no_token(
        self,
        token_manager: TokenManager,
    ) -> None:
        """Test refreshing token when no token exists."""
        # Try to refresh non-existent token
        with pytest.raises(ValueError, match="No token found for user"):
            await token_manager.refresh_token("nonexistent-user")

    async def test_refresh_token_no_refresh_token(
        self,
        token_manager: TokenManager,
    ) -> None:
        """Test refreshing token when no refresh token available."""
        # Store a token without refresh token
        token_info = TokenInfo(
            access_token="old-token",
            refresh_token=None,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        token_manager._tokens["user-123"] = token_info

        # Try to refresh token
        with pytest.raises(ValueError, match="No refresh token available"):
            await token_manager.refresh_token("user-123")

    async def test_get_valid_token_when_refresh_token_invalid(
        self,
        token_manager: TokenManager,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test getting valid token when refresh token is invalid/revoked.

        Hey future me - this tests the scenario where user revoked access in Spotify settings.
        The refresh token is dead - spotify_client.refresh_token() raises TokenRefreshException.
        get_valid_token() should return None and mark token as invalid (is_valid=False).
        """
        from soulspot.domain.exceptions import TokenRefreshException

        # Store an expired token (will trigger refresh)
        token_info = TokenInfo(
            access_token="expired-token",
            refresh_token="invalid-refresh-token",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        token_manager._tokens["user-123"] = token_info

        # Mock refresh token to raise TokenRefreshException (invalid refresh token)
        spotify_client_mock.refresh_token.side_effect = TokenRefreshException(
            message="Refresh token invalid: Token has been revoked",
            error_code="invalid_grant",
            http_status=400,
        )

        # Get valid token (should fail and return None)
        token = await token_manager.get_valid_token("user-123")

        # Assert
        assert token is None
        spotify_client_mock.refresh_token.assert_called_once_with("invalid-refresh-token")

        # Token should be marked as invalid
        stored_token = token_manager._tokens.get("user-123")
        assert stored_token is not None
        assert stored_token.is_valid is False


class TestTokenRefreshException:
    """Test TokenRefreshException behavior."""

    def test_exception_with_invalid_grant(self) -> None:
        """Test exception for invalid_grant error."""
        from soulspot.domain.exceptions import TokenRefreshException

        exc = TokenRefreshException(
            message="Refresh token invalid",
            error_code="invalid_grant",
            http_status=400,
        )

        assert exc.error_code == "invalid_grant"
        assert exc.http_status == 400
        assert exc.requires_reauth is True
        assert "Refresh token invalid" in str(exc)

    def test_exception_with_401_error(self) -> None:
        """Test exception for 401 unauthorized error."""
        from soulspot.domain.exceptions import TokenRefreshException

        exc = TokenRefreshException(
            message="Access denied",
            error_code="access_denied",
            http_status=401,
        )

        assert exc.http_status == 401
        assert exc.requires_reauth is True

    def test_exception_with_403_error(self) -> None:
        """Test exception for 403 forbidden error."""
        from soulspot.domain.exceptions import TokenRefreshException

        exc = TokenRefreshException(
            message="Forbidden",
            error_code=None,
            http_status=403,
        )

        assert exc.http_status == 403
        assert exc.requires_reauth is True

    def test_exception_default_values(self) -> None:
        """Test exception with default values."""
        from soulspot.domain.exceptions import TokenRefreshException

        exc = TokenRefreshException()

        assert exc.error_code is None
        assert exc.http_status is None
        assert exc.requires_reauth is False
        assert "Please re-authenticate with Spotify" in str(exc)
