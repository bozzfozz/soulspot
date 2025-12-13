"""Tests for SlskdDownloadProvider.

Tests the provider that fetches download status from slskd API
and converts it to our unified model.
"""

from unittest.mock import AsyncMock

import pytest

from soulspot.domain.entities.download_manager import (
    DownloadProvider,
    UnifiedDownloadStatus,
)
from soulspot.domain.ports import ISlskdClient
from soulspot.infrastructure.providers.slskd_provider import (
    SLSKD_STATE_MAPPING,
    SlskdDownloadProvider,
)

# Hey future me - these tests verify the slskd provider correctly:
# 1. Maps slskd status strings to UnifiedDownloadStatus
# 2. Calculates download speed from byte deltas
# 3. Handles slskd connection errors gracefully
# 4. Returns empty list when slskd is offline


class TestStatusMapping:
    """Test slskd state to unified status mapping."""

    def test_inprogress_maps_to_downloading(self) -> None:
        """InProgress should map to DOWNLOADING."""
        assert SLSKD_STATE_MAPPING["inprogress"] == UnifiedDownloadStatus.DOWNLOADING

    def test_downloading_maps_to_downloading(self) -> None:
        """Downloading alias should map to DOWNLOADING."""
        assert SLSKD_STATE_MAPPING["downloading"] == UnifiedDownloadStatus.DOWNLOADING

    def test_completed_maps_to_completed(self) -> None:
        """Completed should map to COMPLETED."""
        assert SLSKD_STATE_MAPPING["completed"] == UnifiedDownloadStatus.COMPLETED

    def test_succeeded_maps_to_completed(self) -> None:
        """Succeeded alias should map to COMPLETED."""
        assert SLSKD_STATE_MAPPING["succeeded"] == UnifiedDownloadStatus.COMPLETED

    def test_queued_maps_to_queued(self) -> None:
        """Queued should map to QUEUED."""
        assert SLSKD_STATE_MAPPING["queued"] == UnifiedDownloadStatus.QUEUED

    def test_errored_maps_to_failed(self) -> None:
        """Errored should map to FAILED."""
        assert SLSKD_STATE_MAPPING["errored"] == UnifiedDownloadStatus.FAILED

    def test_cancelled_maps_to_cancelled(self) -> None:
        """Cancelled should map to CANCELLED."""
        assert SLSKD_STATE_MAPPING["cancelled"] == UnifiedDownloadStatus.CANCELLED


class TestSlskdDownloadProvider:
    """Test SlskdDownloadProvider functionality."""

    @pytest.fixture
    def mock_slskd_client(self) -> AsyncMock:
        """Create a mock slskd client."""
        client = AsyncMock(spec=ISlskdClient)
        client.test_connection = AsyncMock(return_value={"success": True})
        client.list_downloads = AsyncMock(return_value=[])
        client.get_download_status = AsyncMock(return_value={})
        return client

    @pytest.fixture
    def provider(self, mock_slskd_client: AsyncMock) -> SlskdDownloadProvider:
        """Create a provider for testing."""
        return SlskdDownloadProvider(mock_slskd_client)

    def test_provider_type(self, provider: SlskdDownloadProvider) -> None:
        """Test provider returns correct type."""
        assert provider.provider_type == DownloadProvider.SOULSEEK

    def test_provider_name(self, provider: SlskdDownloadProvider) -> None:
        """Test provider returns correct name."""
        assert provider.provider_name == "slskd"

    @pytest.mark.asyncio
    async def test_is_available_true(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test is_available returns True when slskd is reachable."""
        mock_slskd_client.test_connection.return_value = {"success": True}

        result = await provider.is_available()

        assert result is True
        mock_slskd_client.test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_available_false(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test is_available returns False when slskd fails."""
        mock_slskd_client.test_connection.return_value = {"success": False}

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_exception(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test is_available returns False on exception."""
        mock_slskd_client.test_connection.side_effect = Exception("Connection failed")

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_downloads_empty(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test get_active_downloads returns empty list when no downloads."""
        mock_slskd_client.list_downloads.return_value = []

        result = await provider.get_active_downloads()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_active_downloads_error(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test get_active_downloads returns empty on error."""
        mock_slskd_client.list_downloads.side_effect = Exception("API error")

        result = await provider.get_active_downloads()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_download_progress_not_found(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test get_download_progress returns None when not found."""
        mock_slskd_client.get_download_status.return_value = {"state": "not_found"}

        result = await provider.get_download_progress("unknown/file.mp3")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_download_progress_error(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test get_download_progress returns None on error."""
        mock_slskd_client.get_download_status.side_effect = Exception("API error")

        result = await provider.get_download_progress("user/file.mp3")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_completed_downloads_empty(
        self,
        provider: SlskdDownloadProvider,
        mock_slskd_client: AsyncMock,
    ) -> None:
        """Test get_completed_downloads returns empty when no completed."""
        mock_slskd_client.list_downloads.return_value = []

        result = await provider.get_completed_downloads(since_hours=24)

        assert result == []


class TestSpeedCalculation:
    """Test download speed calculation logic."""

    @pytest.fixture
    def provider(self) -> SlskdDownloadProvider:
        """Create a provider for speed calculation tests."""
        mock_client = AsyncMock(spec=ISlskdClient)
        return SlskdDownloadProvider(mock_client)

    def test_convert_to_provider_download_with_speed(
        self, provider: SlskdDownloadProvider
    ) -> None:
        """Test speed calculation from byte delta."""
        # First poll - establish baseline
        raw1 = {
            "username": "testuser",
            "filename": "/Music/song.mp3",
            "state": "InProgress",
            "size": 10000000,
            "bytesTransferred": 1000000,
            "percentComplete": 10.0,
        }

        # Set up last_bytes for speed calculation
        external_id = "testuser///Music/song.mp3"
        provider._last_bytes[external_id] = 500000  # Previous bytes

        # Convert with time delta
        result = provider._convert_to_provider_download(raw1, time_delta_secs=1.0)

        assert result is not None
        # Speed should be (1000000 - 500000) / 1.0 = 500000 B/s
        assert result.speed_bytes_per_sec == 500000.0

    def test_convert_to_provider_download_zero_delta(
        self, provider: SlskdDownloadProvider
    ) -> None:
        """Test speed is zero when time delta is zero."""
        raw = {
            "username": "testuser",
            "filename": "/Music/song.mp3",
            "state": "InProgress",
            "size": 10000000,
            "bytesTransferred": 1000000,
            "percentComplete": 10.0,
        }

        result = provider._convert_to_provider_download(raw, time_delta_secs=0.0)

        assert result is not None
        assert result.speed_bytes_per_sec == 0.0

    def test_convert_to_provider_download_none_on_missing_data(
        self, provider: SlskdDownloadProvider
    ) -> None:
        """Test returns None when required fields missing."""
        raw = {
            "state": "InProgress",
            # Missing username and filename
        }

        result = provider._convert_to_provider_download(raw, time_delta_secs=1.0)

        assert result is None
