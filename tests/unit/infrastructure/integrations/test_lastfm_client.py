"""Tests for Last.fm client."""


import pytest
from pytest_httpx import HTTPXMock

from soulspot.config.settings import LastfmSettings
from soulspot.infrastructure.integrations.lastfm_client import LastfmClient


@pytest.fixture
def lastfm_settings():
    """Create Last.fm settings for testing."""
    return LastfmSettings(api_key="test_api_key", api_secret="test_api_secret")


@pytest.fixture
def lastfm_client(lastfm_settings):
    """Create Last.fm client instance."""
    return LastfmClient(lastfm_settings)


class TestLastfmClient:
    """Tests for LastfmClient."""

    async def test_get_track_info_success(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test successful track info retrieval."""
        # Arrange
        mock_response = {
            "track": {
                "name": "Test Track",
                "artist": {"name": "Test Artist"},
                "toptags": {
                    "tag": [
                        {"name": "rock", "count": 100},
                        {"name": "indie", "count": 50},
                    ]
                },
            }
        }
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_track_info(
            artist="Test Artist", track="Test Track"
        )

        # Assert
        assert result is not None
        assert result["name"] == "Test Track"
        assert result["artist"]["name"] == "Test Artist"

    async def test_get_track_info_by_mbid(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test track info retrieval by MusicBrainz ID."""
        # Arrange
        mock_response = {
            "track": {
                "name": "Test Track",
                "mbid": "test-mbid-123",
            }
        }
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_track_info(
            artist="", track="", mbid="test-mbid-123"
        )

        # Assert
        assert result is not None
        assert result["mbid"] == "test-mbid-123"

    async def test_get_track_info_not_found(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test track info when track not found."""
        # Arrange
        httpx_mock.add_response(status_code=404)

        # Act
        result = await lastfm_client.get_track_info(
            artist="Unknown Artist", track="Unknown Track"
        )

        # Assert
        assert result is None

    async def test_get_track_info_api_error(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test track info when API returns error."""
        # Arrange
        mock_response = {"error": 6, "message": "Track not found"}
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_track_info(
            artist="Test Artist", track="Test Track"
        )

        # Assert
        assert result is None

    async def test_get_artist_info_success(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test successful artist info retrieval."""
        # Arrange
        mock_response = {
            "artist": {
                "name": "Test Artist",
                "tags": {
                    "tag": [
                        {"name": "rock", "count": 100},
                        {"name": "alternative", "count": 80},
                    ]
                },
            }
        }
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_artist_info(artist="Test Artist")

        # Assert
        assert result is not None
        assert result["name"] == "Test Artist"
        assert "tags" in result

    async def test_get_artist_info_by_mbid(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test artist info retrieval by MusicBrainz ID."""
        # Arrange
        mock_response = {
            "artist": {
                "name": "Test Artist",
                "mbid": "artist-mbid-456",
            }
        }
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_artist_info(artist="", mbid="artist-mbid-456")

        # Assert
        assert result is not None
        assert result["mbid"] == "artist-mbid-456"

    async def test_get_album_info_success(self, lastfm_client, httpx_mock: HTTPXMock):
        """Test successful album info retrieval."""
        # Arrange
        mock_response = {
            "album": {
                "name": "Test Album",
                "artist": "Test Artist",
                "tags": {
                    "tag": [
                        {"name": "rock", "count": 100},
                    ]
                },
            }
        }
        httpx_mock.add_response(json=mock_response)

        # Act
        result = await lastfm_client.get_album_info(
            artist="Test Artist", album="Test Album"
        )

        # Assert
        assert result is not None
        assert result["name"] == "Test Album"

    async def test_close_client(self, lastfm_client):
        """Test client cleanup."""
        # Arrange
        await lastfm_client._get_client()

        # Act
        await lastfm_client.close()

        # Assert
        assert lastfm_client._client is None

    async def test_context_manager(self, lastfm_settings):
        """Test async context manager usage."""
        # Act & Assert
        async with LastfmClient(lastfm_settings) as client:
            assert client is not None
        # Client should be closed after exiting context
