"""Unit tests for domain value objects."""

import pytest

from soulspot.domain.exceptions import ValidationException
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    DownloadId,
    FilePath,
    PlaylistId,
    SpotifyUri,
    TrackId,
)


class TestArtistId:
    """Tests for ArtistId value object."""

    def test_generate_creates_unique_ids(self) -> None:
        """Test that generate creates unique IDs."""
        id1 = ArtistId.generate()
        id2 = ArtistId.generate()
        assert id1 != id2

    def test_from_string_valid_uuid(self) -> None:
        """Test creating ArtistId from valid UUID string."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        artist_id = ArtistId.from_string(uuid_str)
        assert str(artist_id) == uuid_str

    def test_from_string_invalid_uuid(self) -> None:
        """Test creating ArtistId from invalid UUID string."""
        with pytest.raises(ValidationException):
            ArtistId.from_string("not-a-uuid")


class TestSpotifyUri:
    """Tests for SpotifyUri value object."""

    def test_valid_track_uri(self) -> None:
        """Test creating valid track URI."""
        uri = SpotifyUri.from_string("spotify:track:1234567890")
        assert uri.resource_type == "track"
        assert uri.resource_id == "1234567890"

    def test_valid_playlist_uri(self) -> None:
        """Test creating valid playlist URI."""
        uri = SpotifyUri.from_string("spotify:playlist:abcdefghij")
        assert uri.resource_type == "playlist"
        assert uri.resource_id == "abcdefghij"

    def test_invalid_uri_format(self) -> None:
        """Test invalid URI format."""
        with pytest.raises(ValidationException):
            SpotifyUri.from_string("not-a-spotify-uri")

    def test_invalid_uri_missing_parts(self) -> None:
        """Test URI with missing parts."""
        with pytest.raises(ValidationException):
            SpotifyUri.from_string("spotify:track")

    def test_from_url(self) -> None:
        """Test creating URI from Spotify URL."""
        url = "https://open.spotify.com/track/1234567890?si=xyz"
        uri = SpotifyUri.from_url(url)
        assert uri.resource_type == "track"
        assert uri.resource_id == "1234567890"

    def test_from_invalid_url(self) -> None:
        """Test creating URI from invalid URL."""
        with pytest.raises(ValidationException):
            SpotifyUri.from_url("https://example.com/track/123")


class TestFilePath:
    """Tests for FilePath value object."""

    def test_create_from_string(self) -> None:
        """Test creating FilePath from string."""
        path = FilePath.from_string("/path/to/file.mp3")
        assert str(path) == "/path/to/file.mp3"

    def test_empty_path_raises_exception(self) -> None:
        """Test that empty path raises exception."""
        with pytest.raises(ValidationException):
            FilePath.from_string("")

    def test_path_operations(self) -> None:
        """Test path operation methods."""
        path = FilePath.from_string("/tmp/test.txt")
        # These will return False on non-existent paths
        assert not path.exists()
        assert not path.is_file()
        assert not path.is_directory()
