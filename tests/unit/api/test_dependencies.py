"""Tests for session-based Spotify token dependency."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from soulspot.api.dependencies import get_spotify_token_from_session
from soulspot.application.services.session_store import SessionStore
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient


@pytest.fixture
def session_store() -> SessionStore:
    """Create a session store for testing."""
    return SessionStore(session_timeout_seconds=3600)


@pytest.fixture
def spotify_client_mock() -> SpotifyClient:
    """Create a mock Spotify client."""
    mock = AsyncMock(spec=SpotifyClient)
    mock.refresh_token = AsyncMock(
        return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
    )
    return mock


@pytest.mark.asyncio
async def test_get_token_from_valid_session(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test retrieving token from a valid session with non-expired token."""
    # Create a session with valid token
    session = session_store.create_session()
    session.set_tokens(
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        expires_in=3600,
    )

    # Call dependency
    token = await get_spotify_token_from_session(
        session_id=session.session_id,
        session_store=session_store,
        spotify_client=spotify_client_mock,
    )

    # Assert token is returned
    assert token == "valid_access_token"
    # Assert no refresh was called
    spotify_client_mock.refresh_token.assert_not_called()


@pytest.mark.asyncio
async def test_get_token_refreshes_expired_token(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that expired token is automatically refreshed."""
    # Create a session with expired token
    session = session_store.create_session()
    session.access_token = "expired_access_token"
    session.refresh_token = "valid_refresh_token"
    session.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)  # Expired

    # Call dependency
    token = await get_spotify_token_from_session(
        session_id=session.session_id,
        session_store=session_store,
        spotify_client=spotify_client_mock,
    )

    # Assert new token is returned
    assert token == "new_access_token"
    # Assert refresh was called
    spotify_client_mock.refresh_token.assert_called_once_with("valid_refresh_token")
    # Assert session was updated
    updated_session = session_store.get_session(session.session_id)
    assert updated_session is not None
    assert updated_session.access_token == "new_access_token"
    assert updated_session.refresh_token == "new_refresh_token"


@pytest.mark.asyncio
async def test_get_token_raises_on_no_session_id(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that 401 is raised when no session ID is provided."""
    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_from_session(
            session_id=None,
            session_store=session_store,
            spotify_client=spotify_client_mock,
        )

    assert exc_info.value.status_code == 401
    assert "No session found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_token_raises_on_invalid_session_id(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that 401 is raised when session ID is invalid."""
    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_from_session(
            session_id="invalid_session_id",
            session_store=session_store,
            spotify_client=spotify_client_mock,
        )

    assert exc_info.value.status_code == 401
    assert "Invalid or expired session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_token_raises_on_no_access_token(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that 401 is raised when session has no access token."""
    # Create session without setting tokens
    session = session_store.create_session()

    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_from_session(
            session_id=session.session_id,
            session_store=session_store,
            spotify_client=spotify_client_mock,
        )

    assert exc_info.value.status_code == 401
    assert "No Spotify token in session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_token_raises_on_expired_without_refresh(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that 401 is raised when token is expired and no refresh token available."""
    # Create session with expired token but no refresh token
    session = session_store.create_session()
    session.access_token = "expired_access_token"
    session.refresh_token = None  # No refresh token
    session.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)  # Expired

    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_from_session(
            session_id=session.session_id,
            session_store=session_store,
            spotify_client=spotify_client_mock,
        )

    assert exc_info.value.status_code == 401
    assert "Token expired and no refresh token available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_token_raises_on_refresh_failure(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that 401 is raised when token refresh fails."""
    # Create session with expired token
    session = session_store.create_session()
    session.access_token = "expired_access_token"
    session.refresh_token = "valid_refresh_token"
    session.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)  # Expired

    # Mock refresh to fail
    spotify_client_mock.refresh_token.side_effect = Exception("Spotify API error")

    with pytest.raises(HTTPException) as exc_info:
        await get_spotify_token_from_session(
            session_id=session.session_id,
            session_store=session_store,
            spotify_client=spotify_client_mock,
        )

    assert exc_info.value.status_code == 401
    assert "Failed to refresh token" in exc_info.value.detail
    assert "Spotify API error" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_token_updates_session_on_successful_refresh(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that session is properly updated after successful token refresh."""
    # Create session with expired token
    session = session_store.create_session()
    session.access_token = "expired_access_token"
    session.refresh_token = "old_refresh_token"
    session.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)  # Expired

    # Call dependency
    token = await get_spotify_token_from_session(
        session_id=session.session_id,
        session_store=session_store,
        spotify_client=spotify_client_mock,
    )

    # Verify token
    assert token == "new_access_token"

    # Verify session was updated
    updated_session = session_store.get_session(session.session_id)
    assert updated_session is not None
    assert updated_session.access_token == "new_access_token"
    assert updated_session.refresh_token == "new_refresh_token"

    # Verify new token is not expired
    assert not updated_session.is_token_expired()

    # Verify expiration time is in the future
    assert updated_session.token_expires_at is not None
    assert updated_session.token_expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_get_token_preserves_old_refresh_token_if_not_provided(
    session_store: SessionStore, spotify_client_mock: SpotifyClient
) -> None:
    """Test that old refresh token is preserved if new one is not provided."""
    # Create session with expired token
    session = session_store.create_session()
    session.access_token = "expired_access_token"
    session.refresh_token = "old_refresh_token"
    session.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)  # Expired

    # Mock refresh to not return new refresh token
    spotify_client_mock.refresh_token.return_value = {
        "access_token": "new_access_token",
        # No refresh_token in response
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    # Call dependency
    await get_spotify_token_from_session(
        session_id=session.session_id,
        session_store=session_store,
        spotify_client=spotify_client_mock,
    )

    # Verify old refresh token was preserved
    updated_session = session_store.get_session(session.session_id)
    assert updated_session is not None
    assert updated_session.refresh_token == "old_refresh_token"
