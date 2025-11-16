"""Tests for SearchAndDownloadTrackUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from soulspot.application.use_cases.search_and_download import (
    DownloadStatus,
    SearchAndDownloadTrackRequest,
    SearchAndDownloadTrackUseCase,
)
from soulspot.domain.entities import Track
from soulspot.domain.value_objects import ArtistId, TrackId


@pytest.fixture
def mock_slskd_client():
    """Mock slskd client."""
    return AsyncMock()


@pytest.fixture
def mock_track_repository():
    """Mock track repository."""
    return AsyncMock()


@pytest.fixture
def mock_download_repository():
    """Mock download repository."""
    return AsyncMock()


@pytest.fixture
def use_case(mock_slskd_client, mock_track_repository, mock_download_repository):
    """Create use case instance with mocked dependencies."""
    return SearchAndDownloadTrackUseCase(
        slskd_client=mock_slskd_client,
        track_repository=mock_track_repository,
        download_repository=mock_download_repository,
    )


@pytest.fixture
def sample_track():
    """Create a sample track."""
    return Track(
        id=TrackId.generate(),
        title="Test Song",
        artist_id=ArtistId.generate(),
        duration_ms=240000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestSearchAndDownloadTrackUseCase:
    """Tests for SearchAndDownloadTrackUseCase."""

    async def test_execute_success_with_results(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test successful download with search results."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "testuser",
                "filename": "/path/to/Test Song.mp3",
                "size": 5000000,
                "bitrate": 320,
            }
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(track_id=track_id)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.search_results_count == 1
        assert response.selected_file is not None
        assert response.selected_file["username"] == "testuser"
        assert response.download is not None
        mock_download_repository.add.assert_called_once()

    async def test_execute_track_not_found(
        self,
        use_case,
        mock_track_repository,
    ):
        """Test when track is not found."""
        # Arrange
        track_id = TrackId.generate()
        mock_track_repository.get_by_id.return_value = None

        request = SearchAndDownloadTrackRequest(track_id=track_id)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.FAILED
        assert "Track not found" in response.error_message
        assert response.download is None

    async def test_execute_search_failed(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        sample_track,
    ):
        """Test when search fails."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track
        mock_slskd_client.search.side_effect = Exception("Search timeout")

        request = SearchAndDownloadTrackRequest(track_id=track_id)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.FAILED
        assert "Search failed" in response.error_message

    async def test_execute_no_suitable_files(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        sample_track,
    ):
        """Test when no suitable files are found."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track
        mock_slskd_client.search.return_value = []

        request = SearchAndDownloadTrackRequest(track_id=track_id)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.FAILED
        assert "No suitable files found" in response.error_message

    async def test_execute_download_initiation_failed(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        sample_track,
    ):
        """Test when download initiation fails."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "testuser",
                "filename": "/path/to/Test Song.mp3",
                "size": 5000000,
                "bitrate": 320,
            }
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.side_effect = Exception("Connection failed")

        request = SearchAndDownloadTrackRequest(track_id=track_id)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.FAILED
        assert "Failed to initiate download" in response.error_message

    async def test_select_best_file_prefers_flac(self, use_case):
        """Test that FLAC files are preferred."""
        # Arrange
        results = [
            {"filename": "song.mp3", "bitrate": 320, "size": 10000000},
            {"filename": "song.flac", "bitrate": 1000, "size": 30000000},
        ]

        request = SearchAndDownloadTrackRequest(
            track_id=TrackId.generate(), use_advanced_search=False
        )

        # Act
        selected = use_case._select_best_file_legacy(
            results, request.quality_preference
        )

        # Assert
        assert selected is not None
        assert selected["filename"] == "song.flac"

    async def test_select_best_file_prefers_higher_bitrate(self, use_case):
        """Test that higher bitrate is preferred."""
        # Arrange
        results = [
            {"filename": "song_128.mp3", "bitrate": 128, "size": 4000000},
            {"filename": "song_320.mp3", "bitrate": 320, "size": 10000000},
        ]

        request = SearchAndDownloadTrackRequest(
            track_id=TrackId.generate(), use_advanced_search=False
        )

        # Act
        selected = use_case._select_best_file_legacy(
            results, request.quality_preference
        )

        # Assert
        assert selected is not None
        assert selected["filename"] == "song_320.mp3"

    async def test_select_best_file_good_quality_filters(self, use_case):
        """Test that good quality preference filters low bitrate."""
        # Arrange
        results = [
            {"filename": "song_128.mp3", "bitrate": 128, "size": 4000000},
            {"filename": "song_320.mp3", "bitrate": 320, "size": 10000000},
        ]

        request = SearchAndDownloadTrackRequest(
            track_id=TrackId.generate(),
            quality_preference="good",
            use_advanced_search=False,
        )

        # Act
        selected = use_case._select_best_file_legacy(
            results, request.quality_preference
        )

        # Assert
        assert selected is not None
        assert selected["bitrate"] >= 256

    async def test_select_best_file_no_results(self, use_case):
        """Test with no results."""
        request = SearchAndDownloadTrackRequest(
            track_id=TrackId.generate(), use_advanced_search=False
        )

        # Act
        selected = use_case._select_best_file_legacy([], request.quality_preference)

        # Assert
        assert selected is None

    async def test_select_best_file_non_audio_files(self, use_case):
        """Test that non-audio files are filtered out."""
        # Arrange
        results = [
            {"filename": "image.jpg", "bitrate": 0, "size": 1000000},
            {"filename": "readme.txt", "bitrate": 0, "size": 5000},
        ]

        request = SearchAndDownloadTrackRequest(
            track_id=TrackId.generate(), use_advanced_search=False
        )

        # Act
        selected = use_case._select_best_file_legacy(
            results, request.quality_preference
        )

        # Assert
        assert selected is None

    async def test_advanced_search_filters_low_bitrate(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test advanced search with minimum bitrate filter."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/path/to/Test Song - Low Quality.mp3",
                "size": 4_000_000,
                "bitrate": 128,
            },
            {
                "username": "user2",
                "filename": "/path/to/Test Song.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            min_bitrate=256,  # Require at least 256 kbps
            use_advanced_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        assert response.selected_file["bitrate"] >= 256

    async def test_advanced_search_excludes_live_versions(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test advanced search excludes live versions by default."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/path/to/Song (Live).mp3",
                "size": 7_000_000,
                "bitrate": 320,
            },
            {
                "username": "user2",
                "filename": "/path/to/Song.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            use_advanced_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        assert "live" not in response.selected_file["filename"].lower()

    async def test_advanced_search_format_filter(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test advanced search with format filter."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/path/to/Song.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
            {
                "username": "user2",
                "filename": "/path/to/Song.flac",
                "size": 25_000_000,
                "bitrate": 1000,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            formats=["flac"],  # Only FLAC
            use_advanced_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        assert response.selected_file["filename"].endswith(".flac")

    async def test_advanced_search_custom_exclusions(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test advanced search with custom exclusion keywords."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/path/to/Song (Radio Edit).mp3",
                "size": 5_000_000,
                "bitrate": 320,
            },
            {
                "username": "user2",
                "filename": "/path/to/Song.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            exclusion_keywords=["radio"],  # Exclude radio edits
            use_advanced_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        assert "radio" not in response.selected_file["filename"].lower()

    async def test_advanced_search_fuzzy_matching(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test advanced search with fuzzy matching."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/music/The Beatles - Let It Be.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
            {
                "username": "user2",
                "filename": "/music/Beatles - Let It Be.mp3",
                "size": 7_000_000,
                "bitrate": 320,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            search_query="Beatles Let It Be",  # Without "The"
            fuzzy_threshold=75,
            use_advanced_search=True,
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        # Should match despite missing "The"
        assert "let it be" in response.selected_file["filename"].lower()

    async def test_advanced_search_disabled_uses_legacy(
        self,
        use_case,
        mock_slskd_client,
        mock_track_repository,
        mock_download_repository,
        sample_track,
    ):
        """Test that disabling advanced search uses legacy logic."""
        # Arrange
        track_id = sample_track.id
        mock_track_repository.get_by_id.return_value = sample_track

        search_results = [
            {
                "username": "user1",
                "filename": "/path/to/Song (Live).mp3",  # Would be excluded by advanced search
                "size": 7_200_000,
                "bitrate": 320,
            },
        ]
        mock_slskd_client.search.return_value = search_results
        mock_slskd_client.download.return_value = "download-123"

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            use_advanced_search=False,  # Disable advanced search
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.status == DownloadStatus.QUEUED
        assert response.selected_file is not None
        # Should NOT exclude live version when advanced search is disabled
        assert "live" in response.selected_file["filename"].lower()
