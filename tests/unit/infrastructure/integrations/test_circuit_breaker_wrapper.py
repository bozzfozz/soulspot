"""Tests for circuit breaker wrapper implementations."""

from unittest.mock import AsyncMock

import pytest

from soulspot.config.settings import Settings
from soulspot.infrastructure.integrations.circuit_breaker_wrapper import (
    CircuitBreakerMusicBrainzClient,
    CircuitBreakerSlskdClient,
    CircuitBreakerSpotifyClient,
)
from soulspot.infrastructure.observability.circuit_breaker import CircuitBreakerError


@pytest.fixture
def settings() -> Settings:
    """Create settings for testing."""
    return Settings()


@pytest.fixture
def mock_slskd_client() -> AsyncMock:
    """Create mock slskd client."""
    client = AsyncMock()
    client.search = AsyncMock(return_value=[{"file": "test.mp3"}])
    client.download = AsyncMock(return_value="download-123")
    client.get_download_status = AsyncMock(return_value={"status": "completed"})
    client.list_downloads = AsyncMock(return_value=[])
    client.cancel_download = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_spotify_client() -> AsyncMock:
    """Create mock Spotify client."""
    client = AsyncMock()
    client.get_authorization_url = AsyncMock(return_value="https://auth.url")
    client.exchange_code = AsyncMock(return_value={"access_token": "token"})
    client.refresh_token = AsyncMock(return_value={"access_token": "new_token"})
    client.get_playlist = AsyncMock(return_value={"id": "playlist-123"})
    client.get_track = AsyncMock(return_value={"id": "track-123"})
    client.search_track = AsyncMock(return_value={"tracks": []})
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_musicbrainz_client() -> AsyncMock:
    """Create mock MusicBrainz client."""
    client = AsyncMock()
    client.lookup_recording_by_isrc = AsyncMock(return_value={"id": "rec-123"})
    client.search_recording = AsyncMock(return_value=[])
    client.lookup_release = AsyncMock(return_value={"id": "rel-123"})
    client.lookup_artist = AsyncMock(return_value={"id": "artist-123"})
    client.close = AsyncMock()
    return client


class TestCircuitBreakerSlskdClient:
    """Test circuit breaker wrapper for slskd client."""

    async def test_search_success(
        self, mock_slskd_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful search through circuit breaker."""
        wrapper = CircuitBreakerSlskdClient(mock_slskd_client, settings)

        result = await wrapper.search("test query")

        assert result == [{"file": "test.mp3"}]
        mock_slskd_client.search.assert_called_once_with(query="test query", timeout=30)

    async def test_download_success(
        self, mock_slskd_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful download through circuit breaker."""
        wrapper = CircuitBreakerSlskdClient(mock_slskd_client, settings)

        result = await wrapper.download("user", "file.mp3")

        assert result == "download-123"
        mock_slskd_client.download.assert_called_once_with(
            username="user", filename="file.mp3"
        )

    async def test_circuit_opens_after_failures(
        self, mock_slskd_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that circuit opens after threshold failures."""
        mock_slskd_client.search.side_effect = Exception("API error")

        wrapper = CircuitBreakerSlskdClient(mock_slskd_client, settings)

        # Trigger failures up to threshold (default 5)
        for _ in range(5):
            with pytest.raises(Exception, match="API error"):
                await wrapper.search("test")

        # Next call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError) as exc_info:
            await wrapper.search("test")

        assert exc_info.value.service_name == "slskd-api"

    async def test_close_calls_underlying_client(
        self, mock_slskd_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that close calls underlying client."""
        wrapper = CircuitBreakerSlskdClient(mock_slskd_client, settings)

        await wrapper.close()

        mock_slskd_client.close.assert_called_once()


class TestCircuitBreakerSpotifyClient:
    """Test circuit breaker wrapper for Spotify client."""

    async def test_get_playlist_success(
        self, mock_spotify_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful get_playlist through circuit breaker."""
        wrapper = CircuitBreakerSpotifyClient(mock_spotify_client, settings)

        result = await wrapper.get_playlist("playlist-123", "token")

        assert result == {"id": "playlist-123"}
        mock_spotify_client.get_playlist.assert_called_once_with(
            playlist_id="playlist-123", access_token="token"
        )

    async def test_exchange_code_success(
        self, mock_spotify_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful exchange_code through circuit breaker."""
        wrapper = CircuitBreakerSpotifyClient(mock_spotify_client, settings)

        result = await wrapper.exchange_code("code", "verifier")

        assert result == {"access_token": "token"}
        mock_spotify_client.exchange_code.assert_called_once_with(
            code="code", code_verifier="verifier"
        )

    async def test_circuit_opens_after_failures(
        self, mock_spotify_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that circuit opens after threshold failures."""
        mock_spotify_client.get_track.side_effect = Exception("API error")

        wrapper = CircuitBreakerSpotifyClient(mock_spotify_client, settings)

        # Trigger failures up to threshold
        for _ in range(5):
            with pytest.raises(Exception, match="API error"):
                await wrapper.get_track("track-123", "token")

        # Next call should be blocked
        with pytest.raises(CircuitBreakerError) as exc_info:
            await wrapper.get_track("track-123", "token")

        assert exc_info.value.service_name == "spotify-api"

    async def test_close_calls_underlying_client(
        self, mock_spotify_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that close calls underlying client."""
        wrapper = CircuitBreakerSpotifyClient(mock_spotify_client, settings)

        await wrapper.close()

        mock_spotify_client.close.assert_called_once()


class TestCircuitBreakerMusicBrainzClient:
    """Test circuit breaker wrapper for MusicBrainz client."""

    async def test_search_recording_success(
        self, mock_musicbrainz_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful search_recording through circuit breaker."""
        wrapper = CircuitBreakerMusicBrainzClient(mock_musicbrainz_client, settings)

        result = await wrapper.search_recording("artist", "title")

        assert result == []
        mock_musicbrainz_client.search_recording.assert_called_once_with(
            artist="artist", title="title", limit=10
        )

    async def test_lookup_recording_by_isrc_success(
        self, mock_musicbrainz_client: AsyncMock, settings: Settings
    ) -> None:
        """Test successful lookup_recording_by_isrc through circuit breaker."""
        wrapper = CircuitBreakerMusicBrainzClient(mock_musicbrainz_client, settings)

        result = await wrapper.lookup_recording_by_isrc("ISRC123")

        assert result == {"id": "rec-123"}
        mock_musicbrainz_client.lookup_recording_by_isrc.assert_called_once_with(
            isrc="ISRC123"
        )

    async def test_circuit_opens_after_failures(
        self, mock_musicbrainz_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that circuit opens after threshold failures."""
        mock_musicbrainz_client.lookup_artist.side_effect = Exception("API error")

        wrapper = CircuitBreakerMusicBrainzClient(mock_musicbrainz_client, settings)

        # Trigger failures up to threshold
        for _ in range(5):
            with pytest.raises(Exception, match="API error"):
                await wrapper.lookup_artist("artist-123")

        # Next call should be blocked
        with pytest.raises(CircuitBreakerError) as exc_info:
            await wrapper.lookup_artist("artist-123")

        assert exc_info.value.service_name == "musicbrainz-api"

    async def test_close_calls_underlying_client(
        self, mock_musicbrainz_client: AsyncMock, settings: Settings
    ) -> None:
        """Test that close calls underlying client."""
        wrapper = CircuitBreakerMusicBrainzClient(mock_musicbrainz_client, settings)

        await wrapper.close()

        mock_musicbrainz_client.close.assert_called_once()


class TestCircuitBreakerContextManager:
    """Test circuit breaker wrapper context manager support."""

    async def test_slskd_context_manager(
        self, mock_slskd_client: AsyncMock, settings: Settings
    ) -> None:
        """Test slskd wrapper as context manager."""
        wrapper = CircuitBreakerSlskdClient(mock_slskd_client, settings)

        async with wrapper as client:
            result = await client.search("test")
            assert result == [{"file": "test.mp3"}]

        mock_slskd_client.close.assert_called_once()

    async def test_spotify_context_manager(
        self, mock_spotify_client: AsyncMock, settings: Settings
    ) -> None:
        """Test Spotify wrapper as context manager."""
        wrapper = CircuitBreakerSpotifyClient(mock_spotify_client, settings)

        async with wrapper as client:
            result = await client.get_track("track-123", "token")
            assert result == {"id": "track-123"}

        mock_spotify_client.close.assert_called_once()

    async def test_musicbrainz_context_manager(
        self, mock_musicbrainz_client: AsyncMock, settings: Settings
    ) -> None:
        """Test MusicBrainz wrapper as context manager."""
        wrapper = CircuitBreakerMusicBrainzClient(mock_musicbrainz_client, settings)

        async with wrapper as client:
            result = await client.lookup_artist("artist-123")
            assert result == {"id": "artist-123"}

        mock_musicbrainz_client.close.assert_called_once()
