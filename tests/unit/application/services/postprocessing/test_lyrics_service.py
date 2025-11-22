"""Unit tests for lyrics service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from soulspot.application.services.postprocessing.lyrics_service import LyricsService
from soulspot.config import Settings
from soulspot.domain.entities import Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


class TestLyricsService:
    """Test LyricsService class."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            app_env="development",
            database={"url": "sqlite+aiosqlite:///:memory:"},
        )

    @pytest.fixture
    def service(self, settings: Settings) -> LyricsService:
        """Create LyricsService instance."""
        return LyricsService(
            settings=settings,
            genius_api_key="test_genius_key",
            musixmatch_api_key="test_musixmatch_key",
        )

    @pytest.fixture
    def sample_track(self) -> Track:
        """Create sample track entity."""
        return Track(
            id=TrackId.generate(),
            title="Test Track",
            artist_id=ArtistId.generate(),
            album_id=AlbumId.generate(),
            track_number=1,
            duration_ms=180000,  # 3 minutes
            spotify_id="test-spotify-id",
        )

    def test_init(self, service: LyricsService, settings: Settings):
        """Test service initialization."""
        assert service._settings == settings
        assert service._genius_api_key == "test_genius_key"
        assert service._musixmatch_api_key == "test_musixmatch_key"

    def test_init_without_api_keys(self, settings: Settings):
        """Test initialization without API keys."""
        service = LyricsService(settings=settings)
        assert service._genius_api_key is None
        assert service._musixmatch_api_key is None

    @pytest.mark.asyncio
    async def test_fetch_lyrics_from_lrclib_success(
        self, service: LyricsService, sample_track: Track
    ):
        """Test successful lyrics fetch from LRClib."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "plainLyrics": "Test lyrics line 1\nTest lyrics line 2",
            "syncedLyrics": "[00:00.00] Test lyrics line 1\n[00:05.00] Test lyrics line 2",
        }

        with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("Test lyrics", True)

            lyrics, is_synced = await service.fetch_lyrics(
                track=sample_track,
                artist_name="Test Artist",
                album_name="Test Album",
            )

            assert lyrics == "Test lyrics"
            assert is_synced is True
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_lyrics_fallback_to_genius(
        self, service: LyricsService, sample_track: Track
    ):
        """Test fallback to Genius when LRClib fails."""
        with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_lrclib:
            with patch.object(service, "_fetch_from_genius", new_callable=AsyncMock) as mock_genius:
                mock_lrclib.return_value = (None, False)
                mock_genius.return_value = "Genius lyrics"

                lyrics, is_synced = await service.fetch_lyrics(
                    track=sample_track,
                    artist_name="Test Artist",
                )

                assert lyrics == "Genius lyrics"
                assert is_synced is False
                mock_lrclib.assert_called_once()
                mock_genius.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_lyrics_fallback_to_musixmatch(
        self, service: LyricsService, sample_track: Track
    ):
        """Test fallback to Musixmatch when both LRClib and Genius fail."""
        with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_lrclib:
            with patch.object(service, "_fetch_from_genius", new_callable=AsyncMock) as mock_genius:
                with patch.object(service, "_fetch_from_musixmatch", new_callable=AsyncMock) as mock_musixmatch:
                    mock_lrclib.return_value = (None, False)
                    mock_genius.return_value = None
                    mock_musixmatch.return_value = "Musixmatch lyrics"

                    lyrics, is_synced = await service.fetch_lyrics(
                        track=sample_track,
                        artist_name="Test Artist",
                    )

                    assert lyrics == "Musixmatch lyrics"
                    assert is_synced is False
                    mock_musixmatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_lyrics_all_sources_fail(
        self, service: LyricsService, sample_track: Track
    ):
        """Test when all sources fail to find lyrics."""
        with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_lrclib:
            with patch.object(service, "_fetch_from_genius", new_callable=AsyncMock) as mock_genius:
                with patch.object(service, "_fetch_from_musixmatch", new_callable=AsyncMock) as mock_musixmatch:
                    mock_lrclib.return_value = (None, False)
                    mock_genius.return_value = None
                    mock_musixmatch.return_value = None

                    lyrics, is_synced = await service.fetch_lyrics(
                        track=sample_track,
                        artist_name="Test Artist",
                    )

                    assert lyrics is None
                    assert is_synced is False

    @pytest.mark.asyncio
    async def test_fetch_lyrics_without_genius_key(
        self, settings: Settings, sample_track: Track
    ):
        """Test lyrics fetch without Genius API key."""
        service = LyricsService(settings=settings)  # No API keys

        with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_lrclib:
            mock_lrclib.return_value = (None, False)

            lyrics, is_synced = await service.fetch_lyrics(
                track=sample_track,
                artist_name="Test Artist",
            )

            # Should only try LRClib
            mock_lrclib.assert_called_once()
            assert lyrics is None

    @pytest.mark.asyncio
    async def test_fetch_from_lrclib_with_synced_lyrics(
        self, service: LyricsService
    ):
        """Test fetching synced lyrics from LRClib."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "plainLyrics": "Plain text lyrics",
            "syncedLyrics": "[00:00.00] Synced lyrics",
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            lyrics, is_synced = await service._fetch_from_lrclib(
                artist_name="Test Artist",
                track_title="Test Track",
                album_name="Test Album",
                duration_ms=180000,
            )

            assert lyrics is not None
            assert is_synced is True

    @pytest.mark.asyncio
    async def test_fetch_from_lrclib_plain_lyrics_only(
        self, service: LyricsService
    ):
        """Test fetching plain lyrics when no synced lyrics available."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "plainLyrics": "Plain text lyrics",
            "syncedLyrics": None,
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            lyrics, is_synced = await service._fetch_from_lrclib(
                artist_name="Test Artist",
                track_title="Test Track",
                album_name=None,
                duration_ms=180000,
            )

            assert lyrics == "Plain text lyrics"
            assert is_synced is False

    @pytest.mark.asyncio
    async def test_fetch_from_lrclib_not_found(
        self, service: LyricsService
    ):
        """Test LRClib when lyrics not found."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            lyrics, is_synced = await service._fetch_from_lrclib(
                artist_name="Test Artist",
                track_title="Test Track",
                album_name=None,
                duration_ms=180000,
            )

            assert lyrics is None
            assert is_synced is False

    @pytest.mark.asyncio
    async def test_fetch_from_lrclib_error(
        self, service: LyricsService
    ):
        """Test error handling in LRClib fetch."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")

            lyrics, is_synced = await service._fetch_from_lrclib(
                artist_name="Test Artist",
                track_title="Test Track",
                album_name=None,
                duration_ms=180000,
            )

            assert lyrics is None
            assert is_synced is False

    @pytest.mark.asyncio
    async def test_fetch_from_genius_success(
        self, service: LyricsService
    ):
        """Test successful lyrics fetch from Genius."""
        # Mock search response
        search_response = MagicMock(spec=Response)
        search_response.status_code = 200
        search_response.json.return_value = {
            "response": {
                "hits": [
                    {"result": {"url": "https://genius.com/test-lyrics"}}
                ]
            }
        }

        # Mock lyrics page (this is simplified - real implementation scrapes HTML)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = search_response
            with patch.object(service, "_scrape_genius_lyrics", new_callable=AsyncMock) as mock_scrape:
                mock_scrape.return_value = "Genius lyrics text"

                lyrics = await service._fetch_from_genius(
                    artist_name="Test Artist",
                    track_title="Test Track",
                )

                assert lyrics == "Genius lyrics text"

    @pytest.mark.asyncio
    async def test_fetch_from_genius_not_found(
        self, service: LyricsService
    ):
        """Test Genius when no results found."""
        search_response = MagicMock(spec=Response)
        search_response.status_code = 200
        search_response.json.return_value = {
            "response": {"hits": []}
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = search_response

            lyrics = await service._fetch_from_genius(
                artist_name="Test Artist",
                track_title="Test Track",
            )

            assert lyrics is None

    @pytest.mark.asyncio
    async def test_fetch_from_musixmatch_success(
        self, service: LyricsService
    ):
        """Test successful lyrics fetch from Musixmatch."""
        # Mock track search
        search_response = MagicMock(spec=Response)
        search_response.status_code = 200
        search_response.json.return_value = {
            "message": {
                "body": {
                    "track_list": [
                        {"track": {"track_id": 12345}}
                    ]
                }
            }
        }

        # Mock lyrics fetch
        lyrics_response = MagicMock(spec=Response)
        lyrics_response.status_code = 200
        lyrics_response.json.return_value = {
            "message": {
                "body": {
                    "lyrics": {
                        "lyrics_body": "Musixmatch lyrics text"
                    }
                }
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [search_response, lyrics_response]

            lyrics = await service._fetch_from_musixmatch(
                artist_name="Test Artist",
                track_title="Test Track",
            )

            assert lyrics == "Musixmatch lyrics text"

    @pytest.mark.asyncio
    async def test_fetch_from_musixmatch_not_found(
        self, service: LyricsService
    ):
        """Test Musixmatch when no track found."""
        search_response = MagicMock(spec=Response)
        search_response.status_code = 200
        search_response.json.return_value = {
            "message": {
                "body": {
                    "track_list": []
                }
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = search_response

            lyrics = await service._fetch_from_musixmatch(
                artist_name="Test Artist",
                track_title="Test Track",
            )

            assert lyrics is None
