"""Unit tests for domain entities."""

from datetime import datetime

import pytest

from soulspot.domain.entities import (
    Album,
    Artist,
    Download,
    DownloadStatus,
    Playlist,
    PlaylistSource,
    Track,
)
from soulspot.domain.value_objects import AlbumId, ArtistId, DownloadId, FilePath, PlaylistId, TrackId


class TestArtist:
    """Tests for Artist entity."""

    def test_create_artist(self) -> None:
        """Test creating an artist."""
        artist = Artist(id=ArtistId.generate(), name="Test Artist")
        assert artist.name == "Test Artist"
        assert artist.spotify_uri is None
        assert isinstance(artist.created_at, datetime)

    def test_artist_empty_name_raises_error(self) -> None:
        """Test that empty name raises error."""
        with pytest.raises(ValueError):
            Artist(id=ArtistId.generate(), name="")

    def test_update_artist_name(self) -> None:
        """Test updating artist name."""
        artist = Artist(id=ArtistId.generate(), name="Test Artist")
        old_updated_at = artist.updated_at
        artist.update_name("New Name")
        assert artist.name == "New Name"
        assert artist.updated_at > old_updated_at


class TestAlbum:
    """Tests for Album entity."""

    def test_create_album(self) -> None:
        """Test creating an album."""
        album = Album(
            id=AlbumId.generate(),
            title="Test Album",
            artist_id=ArtistId.generate(),
            release_year=2023,
        )
        assert album.title == "Test Album"
        assert album.release_year == 2023

    def test_album_empty_title_raises_error(self) -> None:
        """Test that empty title raises error."""
        with pytest.raises(ValueError):
            Album(id=AlbumId.generate(), title="", artist_id=ArtistId.generate())

    def test_album_invalid_year_raises_error(self) -> None:
        """Test that invalid year raises error."""
        with pytest.raises(ValueError):
            Album(
                id=AlbumId.generate(),
                title="Test Album",
                artist_id=ArtistId.generate(),
                release_year=1800,
            )


class TestTrack:
    """Tests for Track entity."""

    def test_create_track(self) -> None:
        """Test creating a track."""
        track = Track(
            id=TrackId.generate(),
            title="Test Track",
            artist_id=ArtistId.generate(),
            duration_ms=180000,
            track_number=1,
        )
        assert track.title == "Test Track"
        assert track.duration_ms == 180000
        assert track.track_number == 1

    def test_track_is_downloaded(self) -> None:
        """Test is_downloaded method."""
        track = Track(id=TrackId.generate(), title="Test Track", artist_id=ArtistId.generate())
        assert not track.is_downloaded()

        track.update_file_path(FilePath.from_string("/tmp/test.mp3"))
        # Will be False because file doesn't exist
        assert not track.is_downloaded()


class TestPlaylist:
    """Tests for Playlist entity."""

    def test_create_playlist(self) -> None:
        """Test creating a playlist."""
        playlist = Playlist(id=PlaylistId.generate(), name="Test Playlist")
        assert playlist.name == "Test Playlist"
        assert playlist.track_count() == 0
        assert playlist.source == PlaylistSource.MANUAL

    def test_add_track_to_playlist(self) -> None:
        """Test adding tracks to playlist."""
        playlist = Playlist(id=PlaylistId.generate(), name="Test Playlist")
        track_id = TrackId.generate()

        playlist.add_track(track_id)
        assert playlist.track_count() == 1
        assert track_id in playlist.track_ids

        # Adding same track again should not increase count
        playlist.add_track(track_id)
        assert playlist.track_count() == 1

    def test_remove_track_from_playlist(self) -> None:
        """Test removing tracks from playlist."""
        playlist = Playlist(id=PlaylistId.generate(), name="Test Playlist")
        track_id = TrackId.generate()

        playlist.add_track(track_id)
        playlist.remove_track(track_id)
        assert playlist.track_count() == 0

    def test_clear_playlist(self) -> None:
        """Test clearing all tracks from playlist."""
        playlist = Playlist(id=PlaylistId.generate(), name="Test Playlist")
        playlist.add_track(TrackId.generate())
        playlist.add_track(TrackId.generate())

        playlist.clear_tracks()
        assert playlist.track_count() == 0


class TestDownload:
    """Tests for Download entity."""

    def test_create_download(self) -> None:
        """Test creating a download."""
        download = Download(id=DownloadId.generate(), track_id=TrackId.generate())
        assert download.status == DownloadStatus.PENDING
        assert download.progress_percent == 0.0

    def test_download_lifecycle(self) -> None:
        """Test download status transitions."""
        download = Download(id=DownloadId.generate(), track_id=TrackId.generate())

        # Start download
        download.start()
        assert download.status == DownloadStatus.DOWNLOADING
        assert download.started_at is not None

        # Update progress
        download.update_progress(50.0)
        assert download.progress_percent == 50.0

        # Complete download
        download.complete(FilePath.from_string("/tmp/test.mp3"))
        assert download.status == DownloadStatus.COMPLETED
        assert download.progress_percent == 100.0
        assert download.completed_at is not None
        assert download.is_finished()

    def test_download_failure(self) -> None:
        """Test download failure."""
        download = Download(id=DownloadId.generate(), track_id=TrackId.generate())
        download.start()
        download.fail("Connection error")

        assert download.status == DownloadStatus.FAILED
        assert download.error_message == "Connection error"
        assert download.is_finished()

    def test_download_cancellation(self) -> None:
        """Test download cancellation."""
        download = Download(id=DownloadId.generate(), track_id=TrackId.generate())
        download.start()
        download.cancel()

        assert download.status == DownloadStatus.CANCELLED
        assert download.is_finished()

    def test_invalid_progress_raises_error(self) -> None:
        """Test that invalid progress raises error."""
        download = Download(id=DownloadId.generate(), track_id=TrackId.generate())
        download.start()

        with pytest.raises(ValueError):
            download.update_progress(-10.0)

        with pytest.raises(ValueError):
            download.update_progress(150.0)
