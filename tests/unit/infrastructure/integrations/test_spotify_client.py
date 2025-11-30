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
            "images": [
                {"url": "https://example.com/image.jpg", "height": 640, "width": 640}
            ],
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


class TestSpotifyClientArtistAPI:
    """Test Spotify Artist API operations."""

    async def test_get_artist_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting single artist details."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "artist-123",
            "name": "Test Artist",
            "genres": ["rock", "indie"],
            "popularity": 75,
            "followers": {"total": 1000000},
            "images": [
                {"url": "https://example.com/image.jpg", "height": 640, "width": 640}
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_artist("artist-123", "test-token")

        assert result["id"] == "artist-123"
        assert result["name"] == "Test Artist"
        assert result["genres"] == ["rock", "indie"]
        assert result["popularity"] == 75

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "artists/artist-123" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_several_artists_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test batch fetching multiple artists."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artists": [
                {"id": "artist-1", "name": "Artist One"},
                {"id": "artist-2", "name": "Artist Two"},
                None,  # Deleted/invalid artist returns null
                {"id": "artist-3", "name": "Artist Three"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_several_artists(
            ["artist-1", "artist-2", "artist-invalid", "artist-3"], "test-token"
        )

        # Should filter out null entries
        assert len(result) == 3
        assert result[0]["id"] == "artist-1"
        assert result[1]["id"] == "artist-2"
        assert result[2]["id"] == "artist-3"

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "artists" in call_args[0][0]
        assert (
            call_args[1]["params"]["ids"] == "artist-1,artist-2,artist-invalid,artist-3"
        )
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_several_artists_clamps_to_50(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that get_several_artists clamps to max 50 IDs."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artists": [
                {"id": f"artist-{i}", "name": f"Artist {i}"} for i in range(50)
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        # Pass 60 IDs, should be clamped to 50
        artist_ids = [f"artist-{i}" for i in range(60)]
        await spotify_client.get_several_artists(artist_ids, "test-token")

        call_args = mock_client.get.call_args
        ids_sent = call_args[1]["params"]["ids"].split(",")
        assert len(ids_sent) == 50  # Should be clamped to 50

    async def test_get_artist_albums_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting artist albums."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"id": "album-1", "name": "Album One", "album_type": "album"},
                {"id": "album-2", "name": "Single One", "album_type": "single"},
            ],
            "total": 2,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_artist_albums(
            "artist-123", "test-token", limit=50
        )

        assert len(result) == 2
        assert result[0]["id"] == "album-1"
        assert result[1]["id"] == "album-2"

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "artists/artist-123/albums" in call_args[0][0]
        assert call_args[1]["params"]["include_groups"] == "album,single"
        assert call_args[1]["params"]["limit"] == 50
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_artist_top_tracks_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting artist top tracks."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tracks": [
                {"id": "track-1", "name": "Hit Song", "popularity": 90},
                {"id": "track-2", "name": "Another Hit", "popularity": 85},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_artist_top_tracks(
            "artist-123", "test-token", market="US"
        )

        assert len(result) == 2
        assert result[0]["id"] == "track-1"
        assert result[0]["popularity"] == 90

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "artists/artist-123/top-tracks" in call_args[0][0]
        assert call_args[1]["params"]["market"] == "US"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_get_related_artists_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test getting related artists."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artists": [
                {"id": "related-1", "name": "Similar Artist 1", "genres": ["rock"]},
                {"id": "related-2", "name": "Similar Artist 2", "genres": ["indie"]},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.get_related_artists("artist-123", "test-token")

        assert len(result) == 2
        assert result[0]["id"] == "related-1"
        assert result[0]["name"] == "Similar Artist 1"
        assert result[1]["id"] == "related-2"

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "artists/artist-123/related-artists" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    async def test_search_artist_success(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test searching for artists."""
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artists": {
                "items": [
                    {"id": "artist-1", "name": "Searched Artist", "popularity": 80},
                    {"id": "artist-2", "name": "Similar Name", "popularity": 60},
                ],
                "total": 100,
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.get.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.search_artist(
            "test artist query", "test-token", limit=10
        )

        assert "artists" in result
        assert len(result["artists"]["items"]) == 2
        assert result["artists"]["items"][0]["name"] == "Searched Artist"

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "search" in call_args[0][0]
        assert call_args[1]["params"]["q"] == "test artist query"
        assert call_args[1]["params"]["type"] == "artist"
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"


class TestSpotifyClientTokenRefreshErrors:
    """Test Spotify client token refresh error handling.

    Hey future me - these tests verify that the client properly handles
    invalid refresh tokens by raising TokenRefreshException. This is CRITICAL
    for the re-authentication flow!
    """

    async def test_refresh_token_invalid_grant_error(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that invalid_grant error raises TokenRefreshException.

        This happens when the refresh token has been revoked (user removed
        app access in Spotify settings) or has expired.
        """
        from soulspot.domain.exceptions import TokenRefreshException

        mock_client = AsyncMock()

        # Spotify returns 400 with invalid_grant when refresh token is revoked
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token revoked",
        }

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        with pytest.raises(TokenRefreshException) as exc_info:
            await spotify_client.refresh_token("revoked-refresh-token")

        # Verify exception details
        assert exc_info.value.error_code == "invalid_grant"
        assert exc_info.value.http_status == 400
        assert exc_info.value.requires_reauth is True
        assert "Refresh token invalid" in str(exc_info.value)

    async def test_refresh_token_401_unauthorized_error(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that 401 error raises TokenRefreshException."""
        from soulspot.domain.exceptions import TokenRefreshException

        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": "unauthorized",
            "error_description": "Access denied",
        }

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        with pytest.raises(TokenRefreshException) as exc_info:
            await spotify_client.refresh_token("bad-refresh-token")

        assert exc_info.value.http_status == 401
        assert exc_info.value.requires_reauth is True

    async def test_refresh_token_403_forbidden_error(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that 403 error raises TokenRefreshException."""
        from soulspot.domain.exceptions import TokenRefreshException

        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": "forbidden",
            "error_description": "Forbidden",
        }

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        with pytest.raises(TokenRefreshException) as exc_info:
            await spotify_client.refresh_token("forbidden-refresh-token")

        assert exc_info.value.http_status == 403
        assert exc_info.value.requires_reauth is True

    async def test_refresh_token_400_non_invalid_grant_error(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that other 400 errors fall through to raise_for_status.

        If Spotify returns 400 but it's NOT invalid_grant, we should
        let raise_for_status handle it (might be a temporary issue).
        """
        import httpx

        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "bad_request",
            "error_description": "Malformed request",
        }
        # Make raise_for_status actually raise
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        with pytest.raises(httpx.HTTPStatusError):
            await spotify_client.refresh_token("malformed-request")

    async def test_refresh_token_stores_new_refresh_token(
        self, spotify_client: SpotifyClient, mocker: MagicMock
    ) -> None:
        """Test that new refresh token from Spotify is included in response.

        Hey future me - Spotify MAY return a new refresh_token when refreshing!
        The caller MUST store the new refresh_token if provided, because
        the old one might be invalidated (token rotation).
        """
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new-rotated-refresh-token",  # Spotify rotated the token!
            "scope": "user-follow-read playlist-read-private",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.post.return_value = mock_response

        mocker.patch.object(spotify_client, "_get_client", return_value=mock_client)

        result = await spotify_client.refresh_token("old-refresh-token")

        # Verify the new refresh token is in the response
        assert result["access_token"] == "new-access-token"
        assert result["refresh_token"] == "new-rotated-refresh-token"
        assert result["expires_in"] == 3600
