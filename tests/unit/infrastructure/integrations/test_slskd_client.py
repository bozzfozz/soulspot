"""Tests for slskd client implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from soulspot.config.settings import SlskdSettings
from soulspot.infrastructure.integrations.slskd_client import SlskdClient


@pytest.fixture
def slskd_settings() -> SlskdSettings:
    """Create slskd settings for testing."""
    return SlskdSettings(
        url="http://localhost:5030",
        username="testuser",
        password="testpass",
    )


@pytest.fixture
def slskd_client(slskd_settings: SlskdSettings) -> SlskdClient:
    """Create slskd client for testing."""
    return SlskdClient(slskd_settings)


class TestSlskdClientInit:
    """Test slskd client initialization."""

    def test_init_with_settings(self, slskd_settings: SlskdSettings) -> None:
        """Test client initialization with settings."""
        client = SlskdClient(slskd_settings)
        assert client.settings == slskd_settings
        assert client.base_url == "http://localhost:5030"

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slash is stripped from URL."""
        settings = SlskdSettings(
            url="http://localhost:5030/",
            username="testuser",
            password="testpass",
        )
        client = SlskdClient(settings)
        assert client.base_url == "http://localhost:5030"


class TestSlskdClientSearch:
    """Test slskd search operations."""

    async def test_search_success(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test successful search operation."""
        # Mock HTTP responses
        mock_client = AsyncMock()

        # Mock search creation
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"id": "search-123"}
        mock_search_response.raise_for_status = MagicMock()

        # Mock search results
        mock_results_response = MagicMock()
        mock_results_response.json.return_value = {
            "responses": [
                {
                    "username": "user1",
                    "files": [
                        {
                            "filename": "/music/song1.mp3",
                            "size": 5000000,
                            "bitRate": 320,
                            "length": 180,
                            "quality": 5,
                        },
                    ],
                },
            ],
        }
        mock_results_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_search_response
        mock_client.get.return_value = mock_results_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        # Execute search
        results = await slskd_client.search("test query")

        # Verify
        assert len(results) == 1
        assert results[0]["username"] == "user1"
        assert results[0]["filename"] == "/music/song1.mp3"
        assert results[0]["size"] == 5000000
        assert results[0]["bitrate"] == 320

        mock_client.post.assert_called_once()
        mock_client.get.assert_called_once()

    async def test_search_no_results(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test search with no results."""
        mock_client = AsyncMock()

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"id": "search-123"}
        mock_search_response.raise_for_status = MagicMock()

        mock_results_response = MagicMock()
        mock_results_response.json.return_value = {"responses": []}
        mock_results_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_search_response
        mock_client.get.return_value = mock_results_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        results = await slskd_client.search("nonexistent")

        assert results == []


class TestSlskdClientDownload:
    """Test slskd download operations."""

    async def test_download_success(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test successful download initiation."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        download_id = await slskd_client.download("user1", "/music/song.mp3")

        assert download_id == "user1//music/song.mp3"
        mock_client.post.assert_called_once_with(
            "/api/v0/transfers/downloads",
            json={
                "username": "user1",
                "files": ["/music/song.mp3"],
            },
        )

    async def test_get_download_status_found(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test getting download status when download exists."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "username": "user1",
                "filename": "/music/song.mp3",
                "state": "Completed",
                "percentComplete": 100,
                "bytesTransferred": 5000000,
                "size": 5000000,
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        status = await slskd_client.get_download_status("user1//music/song.mp3")

        assert status["id"] == "user1//music/song.mp3"
        assert status["state"] == "Completed"
        assert status["progress"] == 100
        assert status["size"] == 5000000

    async def test_get_download_status_not_found(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test getting download status when download doesn't exist."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        status = await slskd_client.get_download_status("user1//music/song.mp3")

        assert status["state"] == "not_found"
        assert status["progress"] == 0

    async def test_get_download_status_invalid_id(
        self, slskd_client: SlskdClient
    ) -> None:
        """Test getting download status with invalid ID format."""
        with pytest.raises(ValueError, match="Invalid download_id format"):
            await slskd_client.get_download_status("invalid-id")

    async def test_list_downloads(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test listing all downloads."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "username": "user1",
                "filename": "/music/song1.mp3",
                "state": "InProgress",
                "percentComplete": 50,
                "bytesTransferred": 2500000,
                "size": 5000000,
            },
            {
                "username": "user2",
                "filename": "/music/song2.mp3",
                "state": "Completed",
                "percentComplete": 100,
                "bytesTransferred": 3000000,
                "size": 3000000,
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        downloads = await slskd_client.list_downloads()

        assert len(downloads) == 2
        assert downloads[0]["id"] == "user1//music/song1.mp3"
        assert downloads[0]["state"] == "InProgress"
        assert downloads[1]["id"] == "user2//music/song2.mp3"
        assert downloads[1]["state"] == "Completed"

    async def test_cancel_download(
        self, slskd_client: SlskdClient, mocker: MagicMock
    ) -> None:
        """Test cancelling a download."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client.delete.return_value = mock_response

        mocker.patch.object(slskd_client, "_get_client", return_value=mock_client)

        await slskd_client.cancel_download("user1//music/song.mp3")

        mock_client.delete.assert_called_once()

    async def test_cancel_download_invalid_id(self, slskd_client: SlskdClient) -> None:
        """Test cancelling download with invalid ID format."""
        with pytest.raises(ValueError, match="Invalid download_id format"):
            await slskd_client.cancel_download("invalid-id")


class TestSlskdClientContext:
    """Test slskd client context manager."""

    async def test_context_manager(self, slskd_settings: SlskdSettings) -> None:
        """Test using client as context manager."""
        async with SlskdClient(slskd_settings) as client:
            assert client is not None
            assert client.settings == slskd_settings

    async def test_close(self, slskd_client: SlskdClient) -> None:
        """Test client close."""
        # Create a mock client
        mock_http_client = AsyncMock()
        slskd_client._client = mock_http_client

        await slskd_client.close()

        mock_http_client.aclose.assert_called_once()
        assert slskd_client._client is None
