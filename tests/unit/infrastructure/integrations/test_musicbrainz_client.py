"""Tests for MusicBrainz client implementation."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from soulspot.config.settings import MusicBrainzSettings
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient


@pytest.fixture
def musicbrainz_settings() -> MusicBrainzSettings:
    """Create MusicBrainz settings for testing."""
    return MusicBrainzSettings(
        app_name="TestApp",
        app_version="1.0.0",
        contact="test@example.com",
    )


@pytest.fixture
def musicbrainz_client(musicbrainz_settings: MusicBrainzSettings) -> MusicBrainzClient:
    """Create MusicBrainz client for testing."""
    return MusicBrainzClient(musicbrainz_settings)


class TestMusicBrainzClientInit:
    """Test MusicBrainz client initialization."""

    def test_init_with_settings(
        self, musicbrainz_settings: MusicBrainzSettings
    ) -> None:
        """Test client initialization with settings."""
        client = MusicBrainzClient(musicbrainz_settings)
        assert client.settings == musicbrainz_settings
        assert client.RATE_LIMIT_DELAY == 1.0


class TestMusicBrainzClientRecording:
    """Test MusicBrainz recording operations."""

    async def test_lookup_recording_by_isrc_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test successful ISRC lookup."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recordings": [
                {
                    "id": "recording-123",
                    "title": "Test Song",
                    "length": 180000,
                    "artist-credit": [{"artist": {"name": "Test Artist"}}],
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        result = await musicbrainz_client.lookup_recording_by_isrc("USRC12345678")

        assert result is not None
        assert result["id"] == "recording-123"
        assert result["title"] == "Test Song"

    async def test_lookup_recording_by_isrc_not_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test ISRC lookup when recording not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"recordings": []}
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        result = await musicbrainz_client.lookup_recording_by_isrc("USRC99999999")

        assert result is None

    async def test_lookup_recording_by_isrc_404(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test ISRC lookup with 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        async def mock_request(*args, **kwargs):  # type: ignore
            raise httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            side_effect=mock_request,
        )

        result = await musicbrainz_client.lookup_recording_by_isrc("USRC99999999")

        assert result is None

    async def test_search_recording_success(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test successful recording search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recordings": [
                {
                    "id": "recording-1",
                    "title": "Song 1",
                    "score": 100,
                },
                {
                    "id": "recording-2",
                    "title": "Song 2",
                    "score": 95,
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        results = await musicbrainz_client.search_recording("Test Artist", "Test Song")

        assert len(results) == 2
        assert results[0]["id"] == "recording-1"
        assert results[1]["id"] == "recording-2"

    async def test_search_recording_no_results(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test recording search with no results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"recordings": []}
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        results = await musicbrainz_client.search_recording("Unknown", "Unknown")

        assert results == []


class TestMusicBrainzClientRelease:
    """Test MusicBrainz release operations."""

    async def test_lookup_release_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test successful release lookup."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "release-123",
            "title": "Test Album",
            "artist-credit": [{"artist": {"name": "Test Artist"}}],
            "date": "2023-01-01",
        }
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        result = await musicbrainz_client.lookup_release("release-123")

        assert result is not None
        assert result["id"] == "release-123"
        assert result["title"] == "Test Album"

    async def test_lookup_release_not_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test release lookup when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        async def mock_request(*args, **kwargs):  # type: ignore
            raise httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            side_effect=mock_request,
        )

        result = await musicbrainz_client.lookup_release("nonexistent")

        assert result is None


class TestMusicBrainzClientArtist:
    """Test MusicBrainz artist operations."""

    async def test_lookup_artist_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test successful artist lookup."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "artist-123",
            "name": "Test Artist",
            "country": "US",
            "type": "Person",
        }
        mock_response.raise_for_status = MagicMock()

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            return_value=mock_response,
        )

        result = await musicbrainz_client.lookup_artist("artist-123")

        assert result is not None
        assert result["id"] == "artist-123"
        assert result["name"] == "Test Artist"

    async def test_lookup_artist_not_found(
        self, musicbrainz_client: MusicBrainzClient, mocker: MagicMock
    ) -> None:
        """Test artist lookup when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        async def mock_request(*args, **kwargs):  # type: ignore
            raise httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

        mocker.patch.object(
            musicbrainz_client,
            "_rate_limited_request",
            side_effect=mock_request,
        )

        result = await musicbrainz_client.lookup_artist("nonexistent")

        assert result is None


class TestMusicBrainzClientContext:
    """Test MusicBrainz client context manager."""

    async def test_context_manager(
        self, musicbrainz_settings: MusicBrainzSettings
    ) -> None:
        """Test using client as context manager."""
        async with MusicBrainzClient(musicbrainz_settings) as client:
            assert client is not None
            assert client.settings == musicbrainz_settings

    async def test_close(self, musicbrainz_client: MusicBrainzClient) -> None:
        """Test client close."""
        mock_http_client = AsyncMock()
        musicbrainz_client._client = mock_http_client

        await musicbrainz_client.close()

        mock_http_client.aclose.assert_called_once()
        assert musicbrainz_client._client is None
