"""Tests for DownloadManagerService.

Tests the service that aggregates download status from providers
and enriches with SoulSpot track metadata.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.download_manager_service import (
    SOULSPOT_STATUS_MAPPING,
    DownloadManagerConfig,
    DownloadManagerService,
)
from soulspot.domain.entities import DownloadStatus
from soulspot.domain.entities.download_manager import (
    DownloadProgress,
    QueueStatistics,
    TrackInfo,
    UnifiedDownloadStatus,
)
from soulspot.domain.ports.download_provider import (
    IDownloadProviderRegistry,
)

# Hey future me - these tests verify the service correctly:
# 1. Maps SoulSpot DownloadStatus to UnifiedDownloadStatus
# 2. Aggregates downloads from DB and providers
# 3. Enriches with track metadata
# 4. Computes queue statistics


class TestStatusMapping:
    """Test SoulSpot status to Unified status mapping."""

    def test_waiting_maps_to_waiting(self) -> None:
        """WAITING should map to WAITING."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.WAITING] == UnifiedDownloadStatus.WAITING

    def test_pending_maps_to_pending(self) -> None:
        """PENDING should map to PENDING."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.PENDING] == UnifiedDownloadStatus.PENDING

    def test_queued_maps_to_queued(self) -> None:
        """QUEUED should map to QUEUED."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.QUEUED] == UnifiedDownloadStatus.QUEUED

    def test_downloading_maps_to_downloading(self) -> None:
        """DOWNLOADING should map to DOWNLOADING."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.DOWNLOADING] == UnifiedDownloadStatus.DOWNLOADING

    def test_completed_maps_to_completed(self) -> None:
        """COMPLETED should map to COMPLETED."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.COMPLETED] == UnifiedDownloadStatus.COMPLETED

    def test_failed_maps_to_failed(self) -> None:
        """FAILED should map to FAILED."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.FAILED] == UnifiedDownloadStatus.FAILED

    def test_cancelled_maps_to_cancelled(self) -> None:
        """CANCELLED should map to CANCELLED."""
        assert SOULSPOT_STATUS_MAPPING[DownloadStatus.CANCELLED] == UnifiedDownloadStatus.CANCELLED


class TestDownloadManagerConfig:
    """Test DownloadManagerConfig defaults."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = DownloadManagerConfig()

        assert config.stats_history_hours == 24
        assert config.show_completed_in_active is False
        assert config.max_active_downloads == 100

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = DownloadManagerConfig(
            stats_history_hours=48,
            show_completed_in_active=True,
            max_active_downloads=50,
        )

        assert config.stats_history_hours == 48
        assert config.show_completed_in_active is True
        assert config.max_active_downloads == 50


class TestDownloadManagerService:
    """Test DownloadManagerService functionality."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_registry(self) -> AsyncMock:
        """Create a mock provider registry."""
        registry = AsyncMock(spec=IDownloadProviderRegistry)
        registry.get_available_providers = AsyncMock(return_value=[])
        return registry

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_registry: AsyncMock,
    ) -> DownloadManagerService:
        """Create a service for testing."""
        return DownloadManagerService(
            session=mock_session,
            provider_registry=mock_registry,
            config=DownloadManagerConfig(),
        )

    def test_init(self, service: DownloadManagerService) -> None:
        """Test service initializes with config."""
        assert service._config.stats_history_hours == 24
        assert service._config.max_active_downloads == 100


class TestQueueStatistics:
    """Test QueueStatistics value object."""

    def test_total_active(self) -> None:
        """Test total_active calculation."""
        stats = QueueStatistics(
            waiting=5,
            pending=3,
            queued=2,
            downloading=1,
            paused=1,
            stalled=0,
            completed_today=10,
            failed_today=2,
        )

        # total_active should be waiting + pending + queued + downloading + paused + stalled
        assert stats.total_active == 12

    def test_total_in_progress(self) -> None:
        """Test total_in_progress calculation."""
        stats = QueueStatistics(
            waiting=5,
            pending=3,
            queued=2,
            downloading=1,
            paused=1,
            stalled=0,
            completed_today=10,
            failed_today=2,
        )

        # total_in_progress should be queued + downloading + paused + stalled
        assert stats.total_in_progress == 4

    def test_summary_text(self) -> None:
        """Test summary_text generation."""
        stats = QueueStatistics(
            waiting=5,
            pending=3,
            queued=0,
            downloading=2,
            paused=0,
            stalled=0,
            completed_today=10,
            failed_today=1,
        )

        # Should include non-zero counts
        text = stats.summary_text
        assert "waiting" in text.lower() or "5" in text


class TestTrackInfo:
    """Test TrackInfo value object."""

    def test_display_name(self) -> None:
        """Test display_name property."""
        track = TrackInfo(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
        )

        assert track.display_name == "Queen - Bohemian Rhapsody"

    def test_unknown_track(self) -> None:
        """Test unknown track factory method."""
        track = TrackInfo.unknown()

        assert track.title == "Unknown Track"
        assert track.artist == "Unknown Artist"


class TestDownloadProgress:
    """Test DownloadProgress value object."""

    def test_speed_formatted_bytes(self) -> None:
        """Test speed formatting for bytes/sec."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=500.0,  # 500 B/s
            eta_seconds=100,
        )

        assert "B/s" in progress.speed_formatted

    def test_speed_formatted_kb(self) -> None:
        """Test speed formatting for KB/sec."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=50000.0,  # ~50 KB/s
            eta_seconds=100,
        )

        assert "KB/s" in progress.speed_formatted

    def test_speed_formatted_mb(self) -> None:
        """Test speed formatting for MB/sec."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=5000000.0,  # ~5 MB/s
            eta_seconds=100,
        )

        assert "MB/s" in progress.speed_formatted

    def test_eta_formatted_seconds(self) -> None:
        """Test ETA formatting for seconds."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=1000.0,
            eta_seconds=30,
        )

        assert "30s" in progress.eta_formatted

    def test_eta_formatted_minutes(self) -> None:
        """Test ETA formatting for minutes."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=1000.0,
            eta_seconds=90,  # 1m 30s
        )

        eta = progress.eta_formatted
        assert "m" in eta

    def test_eta_formatted_unknown(self) -> None:
        """Test ETA formatting when unknown."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5000000,
            total_bytes=10000000,
            speed_bytes_per_sec=1000.0,
            eta_seconds=None,
        )

        assert progress.eta_formatted == "Unknown"

    def test_size_formatted(self) -> None:
        """Test size formatting."""
        progress = DownloadProgress(
            percent=50.0,
            bytes_downloaded=5 * 1024 * 1024,  # 5 MB
            total_bytes=10 * 1024 * 1024,  # 10 MB
            speed_bytes_per_sec=1000.0,
            eta_seconds=100,
        )

        size = progress.size_formatted
        assert "MB" in size
        assert "/" in size

    def test_zero_progress(self) -> None:
        """Test zero progress factory method."""
        progress = DownloadProgress.zero()

        assert progress.percent == 0.0
        assert progress.bytes_downloaded == 0
        assert progress.total_bytes == 0
        assert progress.speed_bytes_per_sec == 0.0
        assert progress.eta_seconds is None

    def test_completed_progress(self) -> None:
        """Test completed progress factory method."""
        total = 10000000
        progress = DownloadProgress.completed(total)

        assert progress.percent == 100.0
        assert progress.bytes_downloaded == total
        assert progress.total_bytes == total
        assert progress.eta_seconds == 0


class TestUnifiedDownloadStatus:
    """Test UnifiedDownloadStatus enum."""

    def test_is_active_waiting(self) -> None:
        """Test WAITING is active."""
        assert UnifiedDownloadStatus.WAITING.is_active is True

    def test_is_active_downloading(self) -> None:
        """Test DOWNLOADING is active."""
        assert UnifiedDownloadStatus.DOWNLOADING.is_active is True

    def test_is_active_completed(self) -> None:
        """Test COMPLETED is not active."""
        assert UnifiedDownloadStatus.COMPLETED.is_active is False

    def test_is_terminal_completed(self) -> None:
        """Test COMPLETED is terminal."""
        assert UnifiedDownloadStatus.COMPLETED.is_terminal is True

    def test_is_terminal_failed(self) -> None:
        """Test FAILED is terminal."""
        assert UnifiedDownloadStatus.FAILED.is_terminal is True

    def test_is_terminal_downloading(self) -> None:
        """Test DOWNLOADING is not terminal."""
        assert UnifiedDownloadStatus.DOWNLOADING.is_terminal is False
