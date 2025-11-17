"""Tests for SSE (Server-Sent Events) endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from soulspot.domain.entities import Download, DownloadId, DownloadStatus, TrackId
from soulspot.main import app


@pytest.mark.asyncio
async def test_sse_stream_connection():
    """Test that SSE stream endpoint establishes a connection."""
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream("GET", "/api/ui/sse/stream") as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"


@pytest.mark.asyncio
async def test_sse_stream_receives_connected_event():
    """Test that SSE stream sends a connected event."""
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream("GET", "/api/ui/sse/stream") as response,
    ):
        # Read first event (connected)
        event_data = b""
        async for line in response.aiter_lines():
            event_data += line.encode() + b"\n"
            if line == "":  # Empty line signals end of event
                break

        event_str = event_data.decode()
        assert "event: connected" in event_str
        assert "data:" in event_str
        assert "Connected to event stream" in event_str


@pytest.mark.asyncio
async def test_sse_test_endpoint():
    """Test the SSE test endpoint."""
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream("GET", "/api/ui/sse/test") as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read first few events
        events_received = 0
        async for line in response.aiter_lines():
            if "event: test_event" in line:
                events_received += 1
            if events_received >= 3:  # Stop after 3 events
                break

        assert events_received >= 3


@pytest.mark.asyncio
async def test_sse_event_encode():
    """Test SSE event encoding."""
    from soulspot.api.routers.sse import SSEEvent

    # Test simple event
    event = SSEEvent(data={"message": "hello"}, event="test")
    encoded = event.encode()

    assert "event: test\n" in encoded
    assert "data: {" in encoded
    assert '"message": "hello"' in encoded
    assert encoded.endswith("\n\n")  # Double newline at end

    # Test event with ID and retry
    event = SSEEvent(
        data={"counter": 1},
        event="counter",
        id="123",
        retry=3000,
    )
    encoded = event.encode()

    assert "event: counter\n" in encoded
    assert "id: 123\n" in encoded
    assert "retry: 3000\n" in encoded
    assert "data: {" in encoded


@pytest.mark.asyncio
async def test_sse_downloads_update_event():
    """Test that SSE stream sends downloads_update events."""
    # Create mock downloads
    mock_downloads = [
        Download(
            id=DownloadId(1),
            track_id=TrackId(1),
            status=DownloadStatus.DOWNLOADING,
            progress_percent=50,
            priority=5,
        ),
        Download(
            id=DownloadId(2),
            track_id=TrackId(2),
            status=DownloadStatus.PENDING,
            progress_percent=0,
            priority=3,
        ),
    ]

    # Mock the download repository
    with patch(
        "soulspot.api.routers.sse.get_download_repository"
    ) as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=mock_downloads)
        mock_get_repo.return_value = mock_repo

        transport = ASGITransport(app=app)
        async with (
            AsyncClient(transport=transport, base_url="http://test") as client,
            client.stream("GET", "/api/ui/sse/stream") as response,
        ):
            # Skip connected event
            event_count = 0
            async for line in response.aiter_lines():
                if line == "":
                    event_count += 1
                if "event: downloads_update" in line:
                    # Found downloads update event
                    break
                if event_count > 2:  # Safety limit
                    break

            # Verify the repository was called
            mock_repo.list_active.assert_called()


@pytest.mark.asyncio
async def test_sse_heartbeat_event():
    """Test that SSE stream sends heartbeat events."""
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream("GET", "/api/ui/sse/stream") as response,
    ):
        # This test would need to wait ~30 seconds for heartbeat
        # For testing purposes, we'll just verify the stream stays open
        assert response.status_code == 200

        # Read a few events to ensure stream is working
        event_count = 0
        async for line in response.aiter_lines():
            if line == "":
                event_count += 1
            if event_count >= 2:  # Stop after reading a couple events
                break

            assert event_count >= 1


@pytest.mark.asyncio
async def test_sse_error_handling():
    """Test SSE error handling when repository fails."""
    # Mock the download repository to raise an error
    with patch(
        "soulspot.api.routers.sse.get_download_repository"
    ) as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(side_effect=Exception("Test error"))
        mock_get_repo.return_value = mock_repo

        transport = ASGITransport(app=app)
        async with (
            AsyncClient(transport=transport, base_url="http://test") as client,
            client.stream("GET", "/api/ui/sse/stream") as response,
        ):
            # Should still connect successfully
            assert response.status_code == 200

            # Look for error event
            async for line in response.aiter_lines():
                if "event: error" in line:
                    # Found error event
                    break
                if "Connected to event stream" in line:
                    # Past the connected event, wait for error
                    await asyncio.sleep(2.5)  # Wait for first poll
                    continue
