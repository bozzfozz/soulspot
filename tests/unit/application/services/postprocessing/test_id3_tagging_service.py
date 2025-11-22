"""Unit tests for ID3 tagging service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from soulspot.application.services.postprocessing.id3_tagging_service import (
    ID3TaggingService,
)
from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


class TestID3TaggingService:
    """Test ID3TaggingService class."""

    @pytest.fixture
    def settings(self, tmp_path: Path) -> Settings:
        """Create test settings."""
        settings = Settings(
            app_env="development",
            database={"url": "sqlite+aiosqlite:///:memory:"},
        )
        # Mock storage paths
        settings.storage = MagicMock()
        settings.storage.download_path = tmp_path / "downloads"
        settings.storage.music_path = tmp_path / "music"
        settings.storage.download_path.mkdir(parents=True, exist_ok=True)
        settings.storage.music_path.mkdir(parents=True, exist_ok=True)
        return settings

    @pytest.fixture
    def service(self, settings: Settings) -> ID3TaggingService:
        """Create ID3TaggingService instance."""
        return ID3TaggingService(settings)

    @pytest.fixture
    def sample_track(self) -> Track:
        """Create sample track entity."""
        return Track(
            id=TrackId.generate(),
            title="Test Track",
            artist_id=ArtistId.generate(),
            album_id=AlbumId.generate(),
            track_number=1,
            duration_ms=180000,
            spotify_id="test-spotify-id",
            isrc="USTEST1234567",
        )

    @pytest.fixture
    def sample_artist(self) -> Artist:
        """Create sample artist entity."""
        return Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_id="artist-spotify-id",
        )

    @pytest.fixture
    def sample_album(self) -> Album:
        """Create sample album entity."""
        return Album(
            id=AlbumId.generate(),
            title="Test Album",
            artist_id=ArtistId.generate(),
            release_date="2024-01-01",
            total_tracks=10,
            spotify_id="album-spotify-id",
        )

    def test_init(self, service: ID3TaggingService, settings: Settings):
        """Test service initialization."""
        assert service._settings == settings

    @pytest.mark.asyncio
    async def test_write_tags_invalid_path(
        self, service: ID3TaggingService, sample_track: Track, sample_artist: Artist
    ):
        """Test writing tags with invalid path."""
        # Path outside allowed directories
        invalid_path = Path("/tmp/outside/test.mp3")

        with pytest.raises(ValueError, match="not in allowed directories"):
            await service.write_tags(
                file_path=invalid_path,
                track=sample_track,
                artist=sample_artist,
            )

    @pytest.mark.asyncio
    async def test_write_tags_file_not_found(
        self, service: ID3TaggingService, settings: Settings,
        sample_track: Track, sample_artist: Artist
    ):
        """Test writing tags when file doesn't exist."""
        # File in valid directory but doesn't exist
        nonexistent_file = settings.storage.music_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            await service.write_tags(
                file_path=nonexistent_file,
                track=sample_track,
                artist=sample_artist,
            )

    @pytest.mark.asyncio
    async def test_write_tags_basic(
        self, service: ID3TaggingService, settings: Settings,
        sample_track: Track, sample_artist: Artist, tmp_path: Path
    ):
        """Test basic tag writing."""
        # Create a dummy MP3 file
        test_file = settings.storage.music_path / "test.mp3"
        test_file.touch()

        # Mock mutagen classes
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3") as mock_mp3:
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy_id3:
                with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3:
                    # Setup mocks
                    mock_audio = MagicMock()
                    mock_mp3.return_value = mock_audio
                    mock_tags = MagicMock()
                    mock_easy_id3.return_value = mock_tags
                    mock_id3_tags = MagicMock()
                    mock_id3.return_value = mock_id3_tags

                    await service.write_tags(
                        file_path=test_file,
                        track=sample_track,
                        artist=sample_artist,
                    )

                    # Verify MP3 was loaded
                    mock_mp3.assert_called_once()
                    # Verify tags were saved
                    mock_tags.save.assert_called()

    @pytest.mark.asyncio
    async def test_write_tags_with_album(
        self, service: ID3TaggingService, settings: Settings,
        sample_track: Track, sample_artist: Artist, sample_album: Album
    ):
        """Test tag writing with album information."""
        test_file = settings.storage.music_path / "test_album.mp3"
        test_file.touch()

        with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy_id3:
                with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3"):
                    mock_tags = MagicMock()
                    mock_easy_id3.return_value = mock_tags

                    await service.write_tags(
                        file_path=test_file,
                        track=sample_track,
                        artist=sample_artist,
                        album=sample_album,
                    )

                    # Album info should be in tags
                    assert mock_tags.save.called

    @pytest.mark.asyncio
    async def test_write_tags_with_artwork(
        self, service: ID3TaggingService, settings: Settings,
        sample_track: Track, sample_artist: Artist
    ):
        """Test tag writing with artwork."""
        test_file = settings.storage.music_path / "test_artwork.mp3"
        test_file.touch()
        artwork_data = b"\x89PNG\r\n\x1a\n"  # PNG header

        with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3"):
                with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3:
                    mock_id3_tags = MagicMock()
                    mock_id3.return_value = mock_id3_tags

                    await service.write_tags(
                        file_path=test_file,
                        track=sample_track,
                        artist=sample_artist,
                        artwork_data=artwork_data,
                    )

                    # ID3 tags should be saved
                    mock_id3_tags.save.assert_called()

    @pytest.mark.asyncio
    async def test_write_tags_with_lyrics(
        self, service: ID3TaggingService, settings: Settings,
        sample_track: Track, sample_artist: Artist
    ):
        """Test tag writing with lyrics."""
        test_file = settings.storage.music_path / "test_lyrics.mp3"
        test_file.touch()
        lyrics = "Test lyrics line 1\nTest lyrics line 2"

        with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3"):
                with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3:
                    mock_id3_tags = MagicMock()
                    mock_id3.return_value = mock_id3_tags

                    await service.write_tags(
                        file_path=test_file,
                        track=sample_track,
                        artist=sample_artist,
                        lyrics=lyrics,
                    )

                    # ID3 tags should be saved
                    mock_id3_tags.save.assert_called()

    @pytest.mark.asyncio
    async def test_read_tags(
        self, service: ID3TaggingService, settings: Settings
    ):
        """Test reading tags from file."""
        test_file = settings.storage.music_path / "test_read.mp3"
        test_file.touch()

        with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy_id3:
            mock_tags = MagicMock()
            mock_tags.__getitem__ = MagicMock(side_effect=lambda x: {
                "title": ["Test Title"],
                "artist": ["Test Artist"],
                "album": ["Test Album"],
            }.get(x, []))
            mock_easy_id3.return_value = mock_tags

            tags = await service.read_tags(test_file)

            assert tags is not None
            mock_easy_id3.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_tags_no_tags(
        self, service: ID3TaggingService, settings: Settings
    ):
        """Test reading tags from file without tags."""
        test_file = settings.storage.music_path / "test_no_tags.mp3"
        test_file.touch()

        with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy_id3:
            from mutagen.id3 import ID3NoHeaderError
            mock_easy_id3.side_effect = ID3NoHeaderError("No ID3 header")

            tags = await service.read_tags(test_file)

            # Should return empty dict or None when no tags
            assert tags is None or tags == {}
