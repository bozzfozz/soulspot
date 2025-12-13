"""Tests for QueueAlbumDownloadsUseCase.

Tests the use case that queues all tracks of an album for download.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.use_cases.queue_album_downloads import (
    QueueAlbumDownloadsRequest,
    QueueAlbumDownloadsResponse,
    QueueAlbumDownloadsUseCase,
)
from soulspot.application.workers.job_queue import JobQueue
from soulspot.domain.dtos import AlbumDTO, TrackDTO
from soulspot.infrastructure.persistence.repositories import TrackRepository

# Hey future me - these tests verify the album download use case:
# 1. Handles missing plugins gracefully
# 2. Queues tracks from Spotify/Deezer albums
# 3. Skips already downloaded tracks
# 4. Creates new tracks in DB when needed
# 5. Returns proper statistics


class TestQueueAlbumDownloadsRequest:
    """Test request validation."""

    def test_request_with_spotify_id(self) -> None:
        """Request with spotify_id should be valid."""
        request = QueueAlbumDownloadsRequest(
            spotify_id="2noRn2Aes5aoNVsU6iWThc",
            title="Abbey Road",
            artist="The Beatles",
        )
        assert request.spotify_id == "2noRn2Aes5aoNVsU6iWThc"
        assert request.deezer_id is None

    def test_request_with_deezer_id(self) -> None:
        """Request with deezer_id should be valid."""
        request = QueueAlbumDownloadsRequest(
            deezer_id="123456",
            title="Abbey Road",
            artist="The Beatles",
        )
        assert request.deezer_id == "123456"
        assert request.spotify_id is None

    def test_request_with_album_id(self) -> None:
        """Request with local album_id should be valid."""
        album_uuid = str(uuid4())
        request = QueueAlbumDownloadsRequest(
            album_id=album_uuid,
        )
        assert request.album_id == album_uuid


class TestQueueAlbumDownloadsUseCase:
    """Test the use case functionality."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_job_queue(self) -> AsyncMock:
        """Create a mock job queue."""
        queue = AsyncMock(spec=JobQueue)
        queue.enqueue = AsyncMock(return_value="job-123")
        return queue

    @pytest.fixture
    def mock_track_repository(self) -> AsyncMock:
        """Create a mock track repository."""
        repo = AsyncMock(spec=TrackRepository)
        repo.get_by_spotify_uri = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def use_case(
        self,
        mock_session: AsyncMock,
        mock_job_queue: AsyncMock,
        mock_track_repository: AsyncMock,
    ) -> QueueAlbumDownloadsUseCase:
        """Create use case with mocked dependencies."""
        return QueueAlbumDownloadsUseCase(
            session=mock_session,
            job_queue=mock_job_queue,
            track_repository=mock_track_repository,
            spotify_plugin=None,  # Will be set per test
            deezer_plugin=None,
        )

    @pytest.mark.asyncio
    async def test_execute_no_identifier_fails(
        self,
        use_case: QueueAlbumDownloadsUseCase,
    ) -> None:
        """Should fail when no album identifier provided."""
        request = QueueAlbumDownloadsRequest()

        result = await use_case.execute(request)

        assert result.success is False
        assert result.failed_count == 1
        assert "Must provide" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_spotify_no_plugin_fails(
        self,
        use_case: QueueAlbumDownloadsUseCase,
    ) -> None:
        """Should fail when Spotify album requested but plugin not configured."""
        request = QueueAlbumDownloadsRequest(
            spotify_id="abc123",
            title="Test Album",
            artist="Test Artist",
        )

        result = await use_case.execute(request)

        assert result.success is False
        assert "Spotify plugin not configured" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_deezer_no_plugin_fails(
        self,
        use_case: QueueAlbumDownloadsUseCase,
    ) -> None:
        """Should fail when Deezer album requested but plugin not configured."""
        request = QueueAlbumDownloadsRequest(
            deezer_id="123456",
            title="Test Album",
            artist="Test Artist",
        )

        result = await use_case.execute(request)

        assert result.success is False
        assert "Deezer plugin not configured" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_spotify_album_queues_tracks(
        self,
        mock_session: AsyncMock,
        mock_job_queue: AsyncMock,
        mock_track_repository: AsyncMock,
    ) -> None:
        """Should queue tracks from Spotify album."""
        # Create mock Spotify plugin
        mock_spotify = AsyncMock()

        # Create test tracks
        track1 = TrackDTO(
            title="Come Together",
            artist_name="The Beatles",
            source_service="spotify",
            spotify_uri="spotify:track:abc1",
            isrc="GBAYE0601498",
        )
        track2 = TrackDTO(
            title="Something",
            artist_name="The Beatles",
            source_service="spotify",
            spotify_uri="spotify:track:abc2",
            isrc="GBAYE0601499",
        )

        # Create test album
        mock_album = AlbumDTO(
            title="Abbey Road",
            artist_name="The Beatles",
            source_service="spotify",
            spotify_id="2noRn2Aes5aoNVsU6iWThc",
            tracks=[track1, track2],
        )
        mock_spotify.get_album = AsyncMock(return_value=mock_album)

        use_case = QueueAlbumDownloadsUseCase(
            session=mock_session,
            job_queue=mock_job_queue,
            track_repository=mock_track_repository,
            spotify_plugin=mock_spotify,
        )

        request = QueueAlbumDownloadsRequest(
            spotify_id="2noRn2Aes5aoNVsU6iWThc",
        )

        result = await use_case.execute(request)

        assert result.success is True
        assert result.album_title == "Abbey Road"
        assert result.artist_name == "The Beatles"
        assert result.total_tracks == 2
        assert result.queued_count == 2
        assert len(result.job_ids) == 2
        assert mock_job_queue.enqueue.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_skips_already_downloaded(
        self,
        mock_session: AsyncMock,
        mock_job_queue: AsyncMock,
        mock_track_repository: AsyncMock,
    ) -> None:
        """Should skip tracks that are already downloaded."""
        # Create mock Spotify plugin
        mock_spotify = AsyncMock()

        # Create test track
        track1 = TrackDTO(
            title="Come Together",
            artist_name="The Beatles",
            source_service="spotify",
            spotify_uri="spotify:track:abc1",
        )

        mock_album = AlbumDTO(
            title="Abbey Road",
            artist_name="The Beatles",
            source_service="spotify",
            tracks=[track1],
        )
        mock_spotify.get_album = AsyncMock(return_value=mock_album)

        # Mock existing track with file_path (already downloaded)
        existing_track = MagicMock()
        existing_track.id = uuid4()
        existing_track.file_path = "/music/abbey_road/come_together.flac"
        mock_track_repository.get_by_spotify_uri = AsyncMock(return_value=existing_track)

        use_case = QueueAlbumDownloadsUseCase(
            session=mock_session,
            job_queue=mock_job_queue,
            track_repository=mock_track_repository,
            spotify_plugin=mock_spotify,
        )

        request = QueueAlbumDownloadsRequest(
            spotify_id="2noRn2Aes5aoNVsU6iWThc",
        )

        result = await use_case.execute(request)

        assert result.success is True
        assert result.queued_count == 0
        assert result.already_downloaded == 1
        assert mock_job_queue.enqueue.call_count == 0

    @pytest.mark.asyncio
    async def test_execute_handles_empty_album(
        self,
        mock_session: AsyncMock,
        mock_job_queue: AsyncMock,
        mock_track_repository: AsyncMock,
    ) -> None:
        """Should handle album with no tracks gracefully."""
        mock_spotify = AsyncMock()

        mock_album = AlbumDTO(
            title="Empty Album",
            artist_name="Test Artist",
            source_service="spotify",
            tracks=[],  # No tracks
        )
        mock_spotify.get_album = AsyncMock(return_value=mock_album)

        use_case = QueueAlbumDownloadsUseCase(
            session=mock_session,
            job_queue=mock_job_queue,
            track_repository=mock_track_repository,
            spotify_plugin=mock_spotify,
        )

        request = QueueAlbumDownloadsRequest(
            spotify_id="abc123",
        )

        result = await use_case.execute(request)

        assert result.total_tracks == 0
        assert result.queued_count == 0
        assert mock_job_queue.enqueue.call_count == 0


class TestQueueAlbumDownloadsResponse:
    """Test response object."""

    def test_success_when_tracks_queued(self) -> None:
        """Response should indicate success when tracks queued."""
        response = QueueAlbumDownloadsResponse(
            album_title="Test",
            artist_name="Test",
            total_tracks=10,
            queued_count=5,
            already_downloaded=3,
            skipped_count=1,
            failed_count=1,
        )
        assert response.success is True

    def test_success_when_all_downloaded(self) -> None:
        """Response should indicate success when all tracks already downloaded."""
        response = QueueAlbumDownloadsResponse(
            album_title="Test",
            artist_name="Test",
            total_tracks=10,
            queued_count=0,
            already_downloaded=10,
            skipped_count=0,
            failed_count=0,
        )
        assert response.success is True

    def test_not_success_when_nothing_queued(self) -> None:
        """Response should indicate failure when nothing queued or downloaded."""
        response = QueueAlbumDownloadsResponse(
            album_title="Test",
            artist_name="Test",
            total_tracks=0,
            queued_count=0,
            already_downloaded=0,
            skipped_count=0,
            failed_count=1,
            errors=["Some error"],
        )
        assert response.success is False
