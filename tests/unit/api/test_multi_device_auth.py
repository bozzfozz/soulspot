"""Tests for multi-device authentication (bearer token and session export/import)."""

import pytest
from fastapi import Header
from fastapi.testclient import TestClient

from soulspot.api.dependencies import get_session_id


class TestGetSessionId:
    """Test get_session_id dependency that supports both cookie and bearer token."""

    @pytest.mark.asyncio
    async def test_get_session_id_from_bearer_token(self) -> None:
        """Test extracting session ID from Authorization header with Bearer prefix."""
        session_id = await get_session_id(
            authorization="Bearer test-session-id-123",
            session_id_cookie=None,
        )
        assert session_id == "test-session-id-123"

    @pytest.mark.asyncio
    async def test_get_session_id_from_bearer_token_no_prefix(self) -> None:
        """Test extracting session ID from Authorization header without Bearer prefix."""
        session_id = await get_session_id(
            authorization="test-session-id-123",
            session_id_cookie=None,
        )
        assert session_id == "test-session-id-123"

    @pytest.mark.asyncio
    async def test_get_session_id_from_bearer_token_case_insensitive(self) -> None:
        """Test Bearer prefix is case-insensitive."""
        session_id = await get_session_id(
            authorization="bearer test-session-id-123",
            session_id_cookie=None,
        )
        assert session_id == "test-session-id-123"

    @pytest.mark.asyncio
    async def test_get_session_id_from_bearer_token_mixed_case(self) -> None:
        """Test Bearer prefix with mixed case."""
        session_id = await get_session_id(
            authorization="BeArEr test-session-id-123",
            session_id_cookie=None,
        )
        assert session_id == "test-session-id-123"

    @pytest.mark.asyncio
    async def test_get_session_id_from_bearer_token_with_extra_spaces(self) -> None:
        """Test Bearer token with extra whitespace is trimmed."""
        session_id = await get_session_id(
            authorization="Bearer   test-session-id-123   ",
            session_id_cookie=None,
        )
        assert session_id == "test-session-id-123"

    @pytest.mark.asyncio
    async def test_get_session_id_from_cookie(self) -> None:
        """Test extracting session ID from cookie when no Authorization header."""
        session_id = await get_session_id(
            authorization=None,
            session_id_cookie="cookie-session-id-456",
        )
        assert session_id == "cookie-session-id-456"

    @pytest.mark.asyncio
    async def test_get_session_id_header_precedence_over_cookie(self) -> None:
        """Test Authorization header takes precedence over cookie."""
        session_id = await get_session_id(
            authorization="Bearer header-session-id",
            session_id_cookie="cookie-session-id",
        )
        assert session_id == "header-session-id"

    @pytest.mark.asyncio
    async def test_get_session_id_returns_none_when_both_missing(self) -> None:
        """Test returns None when both header and cookie are missing."""
        session_id = await get_session_id(
            authorization=None,
            session_id_cookie=None,
        )
        assert session_id is None

    @pytest.mark.asyncio
    async def test_get_session_id_empty_string_authorization(self) -> None:
        """Test empty authorization header falls back to cookie."""
        session_id = await get_session_id(
            authorization="",
            session_id_cookie="cookie-session-id",
        )
        # Empty string should fall back to cookie (not process as valid header)
        assert session_id == "cookie-session-id"

    @pytest.mark.asyncio
    async def test_get_session_id_whitespace_only_authorization(self) -> None:
        """Test whitespace-only authorization header falls back to cookie."""
        session_id = await get_session_id(
            authorization="   ",
            session_id_cookie="cookie-session-id",
        )
        # Whitespace-only should fall back to cookie
        assert session_id == "cookie-session-id"


# Integration tests will be in separate file that requires TestClient setup
