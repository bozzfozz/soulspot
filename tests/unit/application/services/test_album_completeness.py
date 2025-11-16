"""Unit tests for album completeness service."""

import pytest

from soulspot.application.services.album_completeness import (
    AlbumCompletenessInfo,
    AlbumCompletenessService,
)


class TestAlbumCompletenessInfo:
    """Test AlbumCompletenessInfo class."""

    def test_init(self) -> None:
        """Test initialization."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Test Album",
            artist_name="Test Artist",
            expected_track_count=10,
            actual_track_count=8,
            missing_track_numbers=[3, 7],
            source="spotify",
        )

        assert info.album_id == "album-1"
        assert info.album_title == "Test Album"
        assert info.artist_name == "Test Artist"
        assert info.expected_track_count == 10
        assert info.actual_track_count == 8
        assert info.missing_track_numbers == [3, 7]
        assert info.source == "spotify"
        assert info.completeness_percent == 80.0

    def test_is_complete_true(self) -> None:
        """Test is_complete returns True when all tracks present."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Complete Album",
            artist_name="Test Artist",
            expected_track_count=10,
            actual_track_count=10,
            missing_track_numbers=[],
            source="spotify",
        )

        assert info.is_complete() is True

    def test_is_complete_false(self) -> None:
        """Test is_complete returns False when tracks missing."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Incomplete Album",
            artist_name="Test Artist",
            expected_track_count=10,
            actual_track_count=8,
            missing_track_numbers=[3, 7],
            source="spotify",
        )

        assert info.is_complete() is False

    def test_is_complete_more_tracks_than_expected(self) -> None:
        """Test is_complete when more tracks than expected."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Album with Bonus Tracks",
            artist_name="Test Artist",
            expected_track_count=10,
            actual_track_count=12,
            missing_track_numbers=[],
            source="spotify",
        )

        assert info.is_complete() is True

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Test Album",
            artist_name="Test Artist",
            expected_track_count=10,
            actual_track_count=8,
            missing_track_numbers=[3, 7],
            source="spotify",
        )

        result = info.to_dict()

        assert result["album_id"] == "album-1"
        assert result["album_title"] == "Test Album"
        assert result["artist_name"] == "Test Artist"
        assert result["expected_track_count"] == 10
        assert result["actual_track_count"] == 8
        assert result["missing_track_count"] == 2
        assert result["missing_track_numbers"] == [3, 7]
        assert result["completeness_percent"] == 80.0
        assert result["is_complete"] is False
        assert result["source"] == "spotify"

    def test_completeness_percent_zero_expected(self) -> None:
        """Test completeness percent when expected is zero."""
        info = AlbumCompletenessInfo(
            album_id="album-1",
            album_title="Unknown Album",
            artist_name="Test Artist",
            expected_track_count=0,
            actual_track_count=5,
            missing_track_numbers=[],
            source="unknown",
        )

        assert info.completeness_percent == 0.0


class TestAlbumCompletenessService:
    """Test AlbumCompletenessService class."""

    def test_init(self) -> None:
        """Test initialization."""
        service = AlbumCompletenessService()

        assert service.spotify_client is None
        assert service.musicbrainz_client is None

    def test_detect_missing_track_numbers_no_missing(self) -> None:
        """Test detect missing track numbers with complete album."""
        service = AlbumCompletenessService()

        local_tracks = [1, 2, 3, 4, 5]
        expected_count = 5

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == []

    def test_detect_missing_track_numbers_some_missing(self) -> None:
        """Test detect missing track numbers with gaps."""
        service = AlbumCompletenessService()

        local_tracks = [1, 2, 4, 5]
        expected_count = 5

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == [3]

    def test_detect_missing_track_numbers_multiple_missing(self) -> None:
        """Test detect missing track numbers with multiple gaps."""
        service = AlbumCompletenessService()

        local_tracks = [1, 3, 5, 7, 9]
        expected_count = 10

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == [2, 4, 6, 8, 10]

    def test_detect_missing_track_numbers_all_missing(self) -> None:
        """Test detect missing track numbers with no tracks."""
        service = AlbumCompletenessService()

        local_tracks: list[int] = []
        expected_count = 5

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == [1, 2, 3, 4, 5]

    def test_detect_missing_track_numbers_zero_expected(self) -> None:
        """Test detect missing track numbers with zero expected."""
        service = AlbumCompletenessService()

        local_tracks = [1, 2, 3]
        expected_count = 0

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == []

    def test_detect_missing_track_numbers_more_than_expected(self) -> None:
        """Test detect missing track numbers with bonus tracks."""
        service = AlbumCompletenessService()

        # Album has bonus tracks (11-13) but missing track 5 from original
        local_tracks = [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13]
        expected_count = 10

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == [5]

    def test_detect_missing_track_numbers_sorted(self) -> None:
        """Test detect missing track numbers returns sorted list."""
        service = AlbumCompletenessService()

        local_tracks = [5, 1, 3]
        expected_count = 6

        missing = service.detect_missing_track_numbers(local_tracks, expected_count)

        assert missing == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_get_expected_track_count_from_spotify_no_client(self) -> None:
        """Test get expected track count from Spotify without client."""
        service = AlbumCompletenessService()

        result = await service.get_expected_track_count_from_spotify(
            "spotify:album:123", "token"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_expected_track_count_from_musicbrainz_no_client(self) -> None:
        """Test get expected track count from MusicBrainz without client."""
        service = AlbumCompletenessService()

        result = await service.get_expected_track_count_from_musicbrainz("mb-123")

        assert result is None
