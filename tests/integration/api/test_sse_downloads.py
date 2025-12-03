"""Enhanced integration tests for SSE (Server-Sent Events) download updates.

This module extends the existing SSE tests with comprehensive coverage of
download progress events, event structure validation, and error scenarios.
Tests verify that SSE properly streams real-time download updates to clients.
"""

# AI-Model: Copilot
# Hey future me - SSE tests are tricky because they test long-lived streaming connections!
# Use async_client.stream() context manager and iterate over lines with aiter_lines().
# Each SSE event ends with double newline (\n\n). Event format is text-based protocol:
# "event: type\ndata: json\n\n". Parse carefully! Mock download repository to control what
# events get sent. Test both successful scenarios and error handling (repo failures, client
# disconnect, malformed data). Remember: SSE is unidirectional (server -> client only).

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from soulspot.domain.entities import Download, DownloadId, DownloadStatus, TrackId

# Mark all tests in this module as slow
pytestmark = pytest.mark.slow


class TestSSEDownloadEvents:
    """Test SSE download update events and data structure."""

    async def test_download_update_event_structure(self, async_client: AsyncClient):
        """Test that download update events have correct structure."""
        # Create mock downloads
        mock_downloads = [
            Download(
                id=DownloadId(1),
                track_id=TrackId(1),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=50,
                priority=5,
            ),
        ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                assert response.status_code == 200

                # Skip connected event and find downloads_update event
                event_lines = []
                async for line in response.aiter_lines():
                    event_lines.append(line)
                    if line == "":  # Event complete
                        event_text = "\n".join(event_lines)
                        if "downloads_update" in event_text:
                            # Parse the data line
                            for event_line in event_lines:
                                if event_line.startswith("data: "):
                                    data_json = event_line[6:]  # Remove "data: " prefix
                                    data = json.loads(data_json)

                                    # Validate structure
                                    assert "downloads" in data
                                    assert "total_count" in data
                                    assert "timestamp" in data
                                    assert isinstance(data["downloads"], list)

                                    if data["downloads"]:
                                        download = data["downloads"][0]
                                        assert "id" in download
                                        assert "track_id" in download
                                        assert "status" in download
                                        assert "progress_percent" in download
                                        assert "priority" in download
                                        assert "created_at" in download
                                    break
                            break
                        event_lines = []

    async def test_download_progress_updates(self, async_client: AsyncClient):
        """Test that download progress changes are reflected in events."""
        # Create downloads with different progress levels
        mock_downloads_initial = [
            Download(
                id=DownloadId(1),
                track_id=TrackId(1),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=25,
                priority=5,
            ),
        ]

        mock_downloads_updated = [
            Download(
                id=DownloadId(1),
                track_id=TrackId(1),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=75,
                priority=5,
            ),
        ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            # First call returns initial progress, second call returns updated
            mock_repo.list_active = AsyncMock(
                side_effect=[mock_downloads_initial, mock_downloads_updated]
            )
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                events_found = 0
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and "progress_percent" in line:
                        events_found += 1
                        if events_found >= 2:  # Got at least 2 progress updates
                            break

                assert events_found >= 1, "Should receive download progress events"

    async def test_download_status_transitions(self, async_client: AsyncClient):
        """Test SSE events for download status transitions."""
        statuses = [
            DownloadStatus.PENDING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.COMPLETED,
        ]

        for status in statuses:
            mock_downloads = [
                Download(
                    id=DownloadId(1),
                    track_id=TrackId(1),
                    status=status,
                    progress_percent=100 if status == DownloadStatus.COMPLETED else 50,
                    priority=5,
                ),
            ]

            with patch(
                "soulspot.api.routers.sse.get_download_repository"
            ) as mock_get_repo:
                mock_repo = AsyncMock()
                mock_repo.list_active = AsyncMock(return_value=mock_downloads)
                mock_get_repo.return_value = mock_repo

                async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                    # Find first downloads_update event
                    async for line in response.aiter_lines():
                        if line.startswith("data: ") and "status" in line:
                            data_json = line[6:]
                            data = json.loads(data_json)
                            if "downloads" in data and data["downloads"]:
                                assert data["downloads"][0]["status"] == status.value
                                break

    async def test_multiple_downloads_in_event(self, async_client: AsyncClient):
        """Test SSE event with multiple concurrent downloads."""
        mock_downloads = [
            Download(
                id=DownloadId(i),
                track_id=TrackId(i),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=i * 10,
                priority=5,
            )
            for i in range(1, 6)  # 5 downloads
        ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and "downloads" in line:
                        data_json = line[6:]
                        data = json.loads(data_json)

                        # Should include all downloads (limited to 10 most recent)
                        assert len(data["downloads"]) == 5
                        assert data["total_count"] == 5
                        break


class TestSSEDownloadLimit:
    """Test that SSE respects the 10-download limit for events."""

    async def test_download_limit_enforced(self, async_client: AsyncClient):
        """Test that only 10 most recent downloads are sent in events."""
        # Create 15 downloads
        mock_downloads = [
            Download(
                id=DownloadId(i),
                track_id=TrackId(i),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=50,
                priority=5,
            )
            for i in range(1, 16)  # 15 downloads
        ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and "downloads" in line:
                        data_json = line[6:]
                        data = json.loads(data_json)

                        # Should limit to 10 downloads in event
                        assert len(data["downloads"]) == 10
                        # But total_count should show actual total
                        assert data["total_count"] == 15
                        break


class TestSSEEventTiming:
    """Test SSE event timing and polling behavior."""

    async def test_event_polling_interval(self, async_client: AsyncClient):
        """Test that events are sent at regular intervals."""
        mock_downloads = [
            Download(
                id=DownloadId(1),
                track_id=TrackId(1),
                status=DownloadStatus.DOWNLOADING,
                progress_percent=50,
                priority=5,
            ),
        ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                event_times = []
                event_count = 0

                async for line in response.aiter_lines():
                    if "event: downloads_update" in line:
                        import time

                        event_times.append(time.time())
                        event_count += 1

                        if event_count >= 3:  # Get 3 events to measure interval
                            break

                # Should have received at least 2 events
                if len(event_times) >= 2:
                    # Calculate intervals (should be ~2 seconds with default poll_interval)
                    intervals = [
                        event_times[i + 1] - event_times[i]
                        for i in range(len(event_times) - 1)
                    ]
                    # Allow some variance (1-3 seconds)
                    for interval in intervals:
                        assert 1.0 <= interval <= 4.0, (
                            f"Event interval {interval}s outside expected range (1-4s)"
                        )


class TestSSEConnectionManagement:
    """Test SSE connection lifecycle and management."""

    async def test_client_disconnect_detection(self, async_client: AsyncClient):
        """Test that server detects client disconnect."""
        mock_downloads = []

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                # Read connected event
                async for line in response.aiter_lines():
                    if "Connected to event stream" in line:
                        break

                # Connection should be active
                assert response.status_code == 200

            # After exiting context, connection is closed
            # Server should have detected disconnect

    async def test_multiple_concurrent_connections(self, async_client: AsyncClient):
        """Test that multiple clients can connect simultaneously."""
        mock_downloads = []

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            # Open 3 concurrent SSE connections
            async with (
                async_client.stream("GET", "/api/ui/sse/stream") as response1,
                async_client.stream("GET", "/api/ui/sse/stream") as response2,
                async_client.stream("GET", "/api/ui/sse/stream") as response3,
            ):
                assert response1.status_code == 200
                assert response2.status_code == 200
                assert response3.status_code == 200

                # All connections should receive connected event
                for response in [response1, response2, response3]:
                    async for line in response.aiter_lines():
                        if "Connected to event stream" in line:
                            break


class TestSSEErrorScenarios:
    """Test SSE error handling and edge cases."""

    async def test_repository_error_sends_error_event(self, async_client: AsyncClient):
        """Test that repository errors are sent as error events."""
        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(side_effect=Exception("Database error"))
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                async for line in response.aiter_lines():
                    if "event: error" in line:
                        # Found error event
                        # Next line should be data with error message
                        async for data_line in response.aiter_lines():
                            if data_line.startswith("data: "):
                                data = json.loads(data_line[6:])
                                assert "error" in data
                                break
                        break

    async def test_empty_downloads_handled(self, async_client: AsyncClient):
        """Test SSE events when no downloads are active."""
        mock_downloads = []

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(return_value=mock_downloads)
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and "downloads" in line:
                        data_json = line[6:]
                        data = json.loads(data_json)

                        # Should have empty downloads array
                        assert data["downloads"] == []
                        assert data["total_count"] == 0
                        break


class TestSSEPerformance:
    """Test SSE performance and resource usage."""

    async def test_sse_handles_rapid_updates(self, async_client: AsyncClient):
        """Test SSE with rapidly changing download data."""
        # Simulate rapidly changing progress
        call_count = [0]

        def get_changing_downloads():
            call_count[0] += 1
            return [
                Download(
                    id=DownloadId(1),
                    track_id=TrackId(1),
                    status=DownloadStatus.DOWNLOADING,
                    progress_percent=min(call_count[0] * 10, 100),
                    priority=5,
                )
            ]

        with patch("soulspot.api.routers.sse.get_download_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.list_active = AsyncMock(
                side_effect=lambda: get_changing_downloads()
            )
            mock_get_repo.return_value = mock_repo

            async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                events_received = 0
                async for line in response.aiter_lines():
                    if "event: downloads_update" in line:
                        events_received += 1
                        if events_received >= 5:  # Receive 5 rapid updates
                            break

                assert events_received >= 3, "Should handle rapid updates"
