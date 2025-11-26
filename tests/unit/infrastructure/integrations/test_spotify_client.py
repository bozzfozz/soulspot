"""Tests for Spotify client implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from soulspot.config.settings import SpotifySettings
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient


@pytest.fixture
def spotify_settings() -> SpotifySettings:
    """Create Spotify settings for testing."""
    return SpotifySettings(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8000/auth/callback",
    )


@pytest.fixture
def spotify_client(spotify_settings: SpotifySettings) -> SpotifyClient:
    """Create Spotify client for testing."""
    return SpotifyClient(spotify_settings)


class TestSpotifyClientInit:
    """Test Spotify client initialization."""

    def test_init_with_settings(self, spotify_settings: SpotifySettings) -> None:
        """Test client initialization with settings."""
        client = SpotifyClient(spotify_settings)
        assert client.settings == spotify_settings


class TestSpotifyClientPKCE:
    """Test Spotify PKCE operations."""

    def test_generate_code_verifier(self) -> None:
        """Test code verifier generation."""
        verifier = SpotifyClient.generate_code_verifier()
        assert len(verifier) > 40  # Should be at least 43 characters
        assert all(c.isalnum() or c in "-_" for c in verifier)

    def test_generate_code_challenge(self) -> None:
        """Test code challenge generation."""
        verifier = "test-verifier-123"
        challenge = SpotifyClient.generate_code_challenge(verifier)
        assert len(challenge) == 43  # SHA256 base64 URL-safe without padding
        assert all(c.isalnum() or c in "-_" for c in challenge)

    async def test_get_authorization_url(self, spotify_client: SpotifyClient) -> None:
        """Test authorization URL generation."""
        state = "test-state-123"
        code_verifier = "test-verifier-123"

        url = await spotify_client.get_authorization_url(state, code_verifier)

        assert url.startswith(SpotifyClient.AUTHORIZE_URL)
        assert "client_id=test-client-id" in url
        assert "state=test-state-123" in url
        assert "code_challenge_method=S256" in url
        assert "code_challenge=" in url
        assert "redirect_uri=" in url
        assert "scope=" in url


class TestSpotifyClientAuth:
    """Test Spotify authentication operations."""

    async def test_exchange_code_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test successful code exchange."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.exchange_code("test-code", "test-verifier")

        assert result["access_token"] == "test-access-token"
        assert result["refresh_token"] == "test-refresh-token"
        assert result["expires_in"] == 3600

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == SpotifyClient.TOKEN_URL
        assert call_args[1]["data"]["grant_type"] == "authorization_code"
        assert call_args[1]["data"]["code"] == "test-code"
        assert call_args[1]["data"]["code_verifier"] == "test-verifier"

    async def test_refresh_token_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test successful token refresh."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.refresh_token("test-refresh-token")

        assert result["access_token"] == "new-access-token"
        assert result["expires_in"] == 3600

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["data"]["grant_type"] == "refresh_token"
        assert call_args[1]["data"]["refresh_token"] == "test-refresh-token"


class TestSpotifyClientAPI:
    """Test Spotify API operations."""

    async def test_get_playlist_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting playlist details."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "playlist-123",
            "name": "Test Playlist",
            "tracks": {
                "items": [
                    {
                        "track": {
                            "id": "track-1",
                            "name": "Song 1",
                        },
                    },
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_playlist("playlist-123", "test-token")

        assert result["id"] == "playlist-123"
        assert result["name"] == "Test Playlist"
        assert len(result["tracks"]["items"]) == 1

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "playlists/playlist-123" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_track_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting track details."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "track-123",
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"},
            "duration_ms": 180000,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_track("track-123", "test-token")

        assert result["id"] == "track-123"
        assert result["name"] == "Test Song"
        assert result["duration_ms"] == 180000

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "tracks/track-123" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_search_track_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test searching for tracks."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-1",
                        "name": "Result 1",
                    },
                    {
                        "id": "track-2",
                        "name": "Result 2",
                    },
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.search_track("test query", "test-token", limit=10)

        assert "tracks" in result
        assert len(result["tracks"]["items"]) == 2

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "search" in call_args[0][0]
        assert call_args[1]["params"]["q"] == "test query"
        assert call_args[1]["params"]["type"] == "track"
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"


class TestSpotifyClientContext:
    """Test Spotify client context manager."""

    async def test_context_manager(self, spotify_settings: SpotifySettings) -> None:
        """Test using client as context manager."""
        async with SpotifyClient(spotify_settings) as client:
            assert client is not None
            assert client.settings == spotify_settings

    async def test_close(self, spotify_client: SpotifyClient) -> None:
        """Test client close."""
        mock_http_client = AsyncMock()
        spotify_client._client = mock_http_client

        await spotify_client.close()

        mock_http_client.aclose.assert_called_once()
        assert spotify_client._client is None


class TestSpotifyClientAlbumAPI:
    """Test Spotify Album API operations."""

    async def test_get_album_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting single album details."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "album-123",
            "name": "Test Album",
            "artists": [{"id": "artist-1", "name": "Test Artist"}],
            "images": [{"url": "https://example.com/image.jpg", "height": 640, "width": 640}],
            "release_date": "2023-01-15",
            "total_tracks": 12,
            "tracks": {
                "items": [{"id": "track-1", "name": "Song 1"}],
                "total": 12,
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_album("album-123", "test-token")

        assert result["id"] == "album-123"
        assert result["name"] == "Test Album"
        assert result["total_tracks"] == 12
        assert len(result["artists"]) == 1

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "albums/album-123" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_albums_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test batch fetching multiple albums."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "albums": [
                {"id": "album-1", "name": "Album One"},
                {"id": "album-2", "name": "Album Two"},
                None,  # Deleted/invalid album returns null
                {"id": "album-3", "name": "Album Three"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_albums(
            ["album-1", "album-2", "album-invalid", "album-3"], "test-token"
        )

        # Should filter out null entries
        assert len(result) == 3
        assert result[0]["id"] == "album-1"
        assert result[1]["id"] == "album-2"
        assert result[2]["id"] == "album-3"

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "albums" in call_args[0][0]
        assert call_args[1]["params"]["ids"] == "album-1,album-2,album-invalid,album-3"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_albums_clamps_to_20(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that get_albums clamps to max 20 IDs."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "albums": [{"id": f"album-{i}", "name": f"Album {i}"} for i in range(20)],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        # Pass 25 IDs, should be clamped to 20
        album_ids = [f"album-{i}" for i in range(25)]
        await spotify_client.get_albums(album_ids, "test-token")

        call_args = mock_client.get.call_args
        ids_sent = call_args[1]["params"]["ids"].split(",")
        assert len(ids_sent) == 20  # Should be clamped to 20

    async def test_get_album_tracks_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting album tracks with pagination."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"id": "track-1", "name": "Song 1", "track_number": 1},
                {"id": "track-2", "name": "Song 2", "track_number": 2},
            ],
            "total": 12,
            "limit": 50,
            "offset": 0,
            "next": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_album_tracks(
            "album-123", "test-token", limit=50, offset=0
        )

        assert len(result["items"]) == 2
        assert result["total"] == 12
        assert result["limit"] == 50
        assert result["offset"] == 0

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "albums/album-123/tracks" in call_args[0][0]
        assert call_args[1]["params"]["limit"] == 50
        assert call_args[1]["params"]["offset"] == 0
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_albums_empty_list(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that get_albums returns empty list for empty input."""
        mock_client = AsyncMock()
        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_albums([], "test-token")

        assert result == []
        # Should not make any API call
        mock_client.get.assert_not_called()
