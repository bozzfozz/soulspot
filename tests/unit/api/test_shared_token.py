"""Tests for shared server-side Spotify token dependency.

Hey future me - this tests the NEW get_spotify_token_shared dependency that uses
DatabaseTokenManager instead of per-session tokens. This is the key fix for
multi-device access: any device on the network can use Spotify features without
needing its own OAuth session cookie.

The flow is:
1. One user authenticates with Spotify on any device
2. Token is stored server-side in DatabaseTokenManager (spotify_tokens table)
3. ALL devices use this shared token via get_spotify_token_shared
4. Background workers also use the same token
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from soulspot.api.dependencies import get_spotify_token_shared


class MockAppState:
    """Mock for FastAPI app.state."""

    def __init__(self) -> None:
        self.db_token_manager: AsyncMock | None = None


class MockRequest:
    """Mock for FastAPI Request."""

    def __init__(self, app_state: MockAppState) -> None:
        self.app = MagicMock()
        self.app.state = app_state


@pytest.fixture
def app_state() -> MockAppState:
    """Create app state with mocked token manager."""
    return MockAppState()


@pytest.fixture
def request_with_token_manager(app_state: MockAppState) -> MockRequest:
    """Create a mock request with db_token_manager initialized."""
    app_state.db_token_manager = AsyncMock()
    return MockRequest(app_state)


@pytest.fixture
def request_without_token_manager() -> MockRequest:
    """Create a mock request without db_token_manager initialized."""
    # Create app state without db_token_manager attribute at all
    app_state = MagicMock(spec=[])  # Empty spec means no attributes
    request = MockRequest.__new__(MockRequest)
    request.app = MagicMock()
    request.app.state = app_state
    return request


@pytest.mark.asyncio
async def test_get_shared_token_returns_valid_token(
    request_with_token_manager: MockRequest,
) -> None:
    """Test that shared token is returned when available."""
    # Setup: Token manager returns a valid token
    request_with_token_manager.app.state.db_token_manager.get_token_for_background = (
        AsyncMock(return_value="valid_shared_token")
    )

    # Call dependency
    token = await get_spotify_token_shared(request_with_token_manager)  # type: ignore[arg-type]

    # Assert token is returned
    assert token == "valid_shared_token"
    request_with_token_manager.app.state.db_token_manager.get_token_for_background.assert_called_once()


@pytest.mark.asyncio
async def test_get_shared_token_raises_401_when_no_token(
    request_with_token_manager: MockRequest,
) -> None:
    """Test that 401 is raised when no token exists (user hasn't authenticated)."""
    # Setup: Token manager returns None (no token stored)
    request_with_token_manager.app.state.db_token_manager.get_token_for_background = (
        AsyncMock(return_value=None)
    )

    # Call dependency - expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_shared(request_with_token_manager)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 401
    assert "Spotify" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_shared_token_raises_503_when_manager_not_initialized(
    request_without_token_manager: MockRequest,
) -> None:
    """Test that 503 is raised when token manager isn't initialized (server starting)."""
    # Call dependency - expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_shared(request_without_token_manager)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 503
    assert "not initialized" in exc_info.value.detail


@pytest.mark.asyncio
async def test_shared_token_does_not_require_session_cookie() -> None:
    """Test that shared token works without any session/cookie.

    This is the KEY TEST - proves multi-device access works. The shared token
    is stored server-side and accessible to any request, regardless of cookies.
    """
    # Setup: Create fresh request with token manager
    app_state = MockAppState()
    app_state.db_token_manager = AsyncMock()
    app_state.db_token_manager.get_token_for_background = AsyncMock(
        return_value="shared_token_for_all_devices"
    )

    # Create a "naked" request - no cookies, no session
    request = MockRequest(app_state)
    # Note: We're NOT setting any session_id or cookies

    # Call dependency
    token = await get_spotify_token_shared(request)  # type: ignore[arg-type]

    # Assert token works without cookies
    assert token == "shared_token_for_all_devices"
