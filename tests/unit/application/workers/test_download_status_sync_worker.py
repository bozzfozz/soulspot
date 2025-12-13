"""Tests for DownloadStatusSyncWorker.

Tests the worker that synchronizes download status from slskd to SoulSpot DB.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.workers.download_status_sync_worker import (
    SLSKD_STATUS_TO_SOULSPOT,
    DownloadStatusSyncWorker,
)
from soulspot.domain.entities import DownloadStatus
from soulspot.domain.ports import ISlskdClient

# Hey future me - these tests verify the sync worker correctly:
# 1. Maps slskd states to SoulSpot status
# 2. Updates downloads in DB based on slskd status
# 3. Handles completion (sets Track.file_path)
# 4. Gracefully handles errors


class TestStatusMapping:
    """Test slskd status to SoulSpot status mapping."""

    def test_inprogress_maps_to_downloading(self) -> None:
        """InProgress state should map to DOWNLOADING."""
        assert SLSKD_STATUS_TO_SOULSPOT["InProgress"] == DownloadStatus.DOWNLOADING

    def test_completed_maps_to_completed(self) -> None:
        """Completed state should map to COMPLETED."""
        assert SLSKD_STATUS_TO_SOULSPOT["Completed"] == DownloadStatus.COMPLETED

    def test_succeeded_maps_to_completed(self) -> None:
        """Succeeded (alias) should map to COMPLETED."""
        assert SLSKD_STATUS_TO_SOULSPOT["Succeeded"] == DownloadStatus.COMPLETED

    def test_queued_maps_to_queued(self) -> None:
        """Queued state should map to QUEUED."""
        assert SLSKD_STATUS_TO_SOULSPOT["Queued"] == DownloadStatus.QUEUED

    def test_errored_maps_to_failed(self) -> None:
        """Errored state should map to FAILED."""
        assert SLSKD_STATUS_TO_SOULSPOT["Errored"] == DownloadStatus.FAILED

    def test_cancelled_maps_to_cancelled(self) -> None:
        """Cancelled state should map to CANCELLED."""
        assert SLSKD_STATUS_TO_SOULSPOT["Cancelled"] == DownloadStatus.CANCELLED


class TestDownloadStatusSyncWorker:
    """Test DownloadStatusSyncWorker functionality."""

    @pytest.fixture
    def mock_slskd_client(self) -> AsyncMock:
        """Create a mock slskd client."""
        client = AsyncMock(spec=ISlskdClient)
        client.get_downloads = AsyncMock(return_value={})
        return client

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        """Create a mock session factory."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        # Create async context manager
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        return mock_factory

    @pytest.fixture
    def worker(
        self,
        mock_session_factory: MagicMock,
        mock_slskd_client: AsyncMock,
    ) -> DownloadStatusSyncWorker:
        """Create a sync worker for testing."""
        return DownloadStatusSyncWorker(
            session_factory=mock_session_factory,
            slskd_client=mock_slskd_client,
            sync_interval=1,  # Fast for tests
            completed_history_hours=24,
        )

    def test_init(self, worker: DownloadStatusSyncWorker) -> None:
        """Test worker initializes with correct config."""
        assert worker._sync_interval == 1
        assert worker._completed_history_hours == 24
        assert worker._running is False

    def test_stop(self, worker: DownloadStatusSyncWorker) -> None:
        """Test stop() sets running to False."""
        worker._running = True
        worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_get_slskd_downloads_empty(
        self,
        worker: DownloadStatusSyncWorker,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test getting downloads when slskd returns empty."""
        mock_slskd_client.get_downloads.return_value = {}

        downloads = await worker._get_slskd_downloads()

        assert downloads == []
        mock_slskd_client.get_downloads.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_slskd_downloads_with_data(
        self,
        worker: DownloadStatusSyncWorker,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test getting downloads from slskd with actual data."""
        # slskd returns downloads grouped by user
        mock_slskd_client.get_downloads.return_value = {
            "testuser": {
                "directories": [
                    {
                        "files": [
                            {
                                "filename": "/path/to/song.mp3",
                                "state": "InProgress",
                                "size": 10000000,
                                "bytesTransferred": 5000000,
                                "percentComplete": 50.0,
                            }
                        ]
                    }
                ]
            }
        }

        downloads = await worker._get_slskd_downloads()

        assert len(downloads) == 1
        assert downloads[0]["username"] == "testuser"
        assert downloads[0]["filename"] == "/path/to/song.mp3"
        assert downloads[0]["state"] == "InProgress"

    @pytest.mark.asyncio
    async def test_get_slskd_downloads_handles_error(
        self,
        worker: DownloadStatusSyncWorker,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test graceful handling when slskd call fails."""
        mock_slskd_client.get_downloads.side_effect = Exception("Connection failed")

        downloads = await worker._get_slskd_downloads()

        assert downloads == []

    @pytest.mark.asyncio
    async def test_sync_cycle_no_downloads(
        self,
        worker: DownloadStatusSyncWorker,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test sync cycle when no downloads present."""
        mock_slskd_client.get_downloads.return_value = {}

        # Should not raise
        await worker._sync_cycle()

        mock_slskd_client.get_downloads.assert_called_once()

    def test_get_sync_stats_empty(self, worker: DownloadStatusSyncWorker) -> None:
        """Test get_sync_stats returns empty dict initially."""
        # Use synchronous call since it returns dict directly
        stats = asyncio.get_event_loop().run_until_complete(worker.get_sync_stats())
        assert stats == {}


class TestUpdateProgress:
    """Test progress update logic."""

    @pytest.fixture
    def worker(self) -> DownloadStatusSyncWorker:
        """Create a minimal worker for progress tests."""
        mock_factory = MagicMock()
        mock_client = AsyncMock()
        return DownloadStatusSyncWorker(
            session_factory=mock_factory,
            slskd_client=mock_client,
            sync_interval=1,
        )

    @pytest.fixture
    def mock_download_model(self) -> MagicMock:
        """Create a mock DownloadModel."""
        model = MagicMock()
        model.progress_percent = 0.0
        return model

    @pytest.mark.asyncio
    async def test_update_progress_percent(
        self,
        worker: DownloadStatusSyncWorker,
        mock_download_model: MagicMock,
    ) -> None:
        """Test progress percent is updated."""
        slskd_dl = {
            "percentComplete": 75.5,
        }

        await worker._update_progress(mock_download_model, slskd_dl)

        assert mock_download_model.progress_percent == 75.5

    @pytest.mark.asyncio
    async def test_update_progress_handles_int(
        self,
        worker: DownloadStatusSyncWorker,
        mock_download_model: MagicMock,
    ) -> None:
        """Test progress handles integer percentages."""
        slskd_dl = {
            "percentComplete": 50,  # Integer instead of float
        }

        await worker._update_progress(mock_download_model, slskd_dl)

        assert mock_download_model.progress_percent == 50.0

    @pytest.mark.asyncio
    async def test_update_progress_handles_missing(
        self,
        worker: DownloadStatusSyncWorker,
        mock_download_model: MagicMock,
    ) -> None:
        """Test progress handles missing percentComplete."""
        slskd_dl = {}  # No percentComplete

        await worker._update_progress(mock_download_model, slskd_dl)

        # Should remain at initial value
        assert mock_download_model.progress_percent == 0.0


class TestCircuitBreaker:
    """Test Circuit Breaker functionality for error recovery.

    Hey future me - these tests verify the circuit breaker:
    1. Opens after N consecutive failures
    2. Stays open for timeout period
    3. Transitions to half-open after timeout
    4. Recovers on successful sync
    5. Re-opens if half-open test fails
    """

    @pytest.fixture
    def mock_slskd_client(self) -> AsyncMock:
        """Create a mock slskd client."""
        client = AsyncMock(spec=ISlskdClient)
        client.get_downloads = AsyncMock(return_value={})
        return client

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        """Create a mock session factory."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        return mock_factory

    @pytest.fixture
    def worker(
        self,
        mock_session_factory: MagicMock,
        mock_slskd_client: AsyncMock,
    ) -> DownloadStatusSyncWorker:
        """Create a sync worker for testing."""
        return DownloadStatusSyncWorker(
            session_factory=mock_session_factory,
            slskd_client=mock_slskd_client,
            sync_interval=1,
            max_consecutive_failures=3,
            circuit_breaker_timeout=60,
        )

    def test_initial_circuit_state_is_closed(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Circuit should start in CLOSED state."""
        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_CLOSED
        assert worker._consecutive_failures == 0

    def test_handle_sync_success_resets_failures(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Successful sync should reset failure counter."""
        # Simulate some failures
        worker._consecutive_failures = 2
        worker._last_failure_time = datetime.now(UTC)

        worker._handle_sync_success()

        assert worker._consecutive_failures == 0
        assert worker._last_failure_time is None
        assert worker._last_successful_sync is not None

    def test_handle_sync_success_closes_half_open_circuit(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Successful sync in HALF_OPEN should transition to CLOSED."""
        worker._circuit_state = DownloadStatusSyncWorker.STATE_HALF_OPEN
        worker._consecutive_failures = 3

        worker._handle_sync_success()

        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_CLOSED
        assert worker._consecutive_failures == 0

    def test_handle_sync_failure_increments_counter(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Failed sync should increment failure counter."""
        error = ConnectionError("slskd offline")

        worker._handle_sync_failure(error)

        assert worker._consecutive_failures == 1
        assert worker._total_errors == 1
        assert worker._last_failure_time is not None

    def test_handle_sync_failure_opens_circuit_after_threshold(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Circuit should open after max consecutive failures."""
        error = ConnectionError("slskd offline")

        # Simulate reaching threshold
        for _ in range(3):  # max_consecutive_failures = 3
            worker._handle_sync_failure(error)

        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_OPEN
        assert worker._consecutive_failures == 3

    def test_handle_sync_failure_reopens_half_open_circuit(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Failed sync in HALF_OPEN should reopen circuit."""
        worker._circuit_state = DownloadStatusSyncWorker.STATE_HALF_OPEN
        error = ConnectionError("still offline")

        worker._handle_sync_failure(error)

        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_OPEN

    def test_check_circuit_recovery_returns_false_when_closed(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Recovery check should return False when circuit is CLOSED."""
        worker._circuit_state = DownloadStatusSyncWorker.STATE_CLOSED

        result = worker._check_circuit_recovery()

        assert result is False

    def test_check_circuit_recovery_returns_false_before_timeout(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Recovery check should return False before timeout elapsed."""
        worker._circuit_state = DownloadStatusSyncWorker.STATE_OPEN
        worker._last_failure_time = datetime.now(UTC)  # Just now

        result = worker._check_circuit_recovery()

        assert result is False
        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_OPEN

    def test_check_circuit_recovery_transitions_after_timeout(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Recovery check should transition to HALF_OPEN after timeout."""
        from datetime import timedelta

        worker._circuit_state = DownloadStatusSyncWorker.STATE_OPEN
        # Set failure time 61 seconds ago (timeout is 60s)
        worker._last_failure_time = datetime.now(UTC) - timedelta(seconds=61)

        result = worker._check_circuit_recovery()

        assert result is True
        assert worker._circuit_state == DownloadStatusSyncWorker.STATE_HALF_OPEN

    def test_get_health_status_healthy(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Health status should show healthy when circuit is CLOSED."""
        worker._handle_sync_success()  # Set last_successful_sync

        status = worker.get_health_status()

        assert status["is_healthy"] is True
        assert status["circuit_state"] == "closed"
        assert status["consecutive_failures"] == 0
        assert status["last_successful_sync"] is not None

    def test_get_health_status_unhealthy(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Health status should show unhealthy when circuit is OPEN."""
        error = ConnectionError("offline")
        for _ in range(3):
            worker._handle_sync_failure(error)

        status = worker.get_health_status()

        assert status["is_healthy"] is False
        assert status["circuit_state"] == "open"
        assert status["consecutive_failures"] == 3
        assert "seconds_until_recovery_attempt" in status

    def test_get_health_status_half_open(
        self,
        worker: DownloadStatusSyncWorker,
    ) -> None:
        """Health status should indicate HALF_OPEN state."""
        worker._circuit_state = DownloadStatusSyncWorker.STATE_HALF_OPEN

        status = worker.get_health_status()

        assert status["is_healthy"] is False
        assert status["circuit_state"] == "half_open"
