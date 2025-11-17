"""Server-Sent Events (SSE) endpoints for real-time widget updates."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_download_repository
from soulspot.infrastructure.persistence.repositories import DownloadRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ui/sse", tags=["sse"])


class SSEEvent:
    """Server-Sent Event wrapper."""

    def __init__(
        self,
        data: dict[str, Any],
        event: str | None = None,
        id: str | None = None,
        retry: int | None = None,
    ):
        """Initialize SSE event.

        Args:
            data: Event data as dictionary (will be JSON-serialized)
            event: Event type/name
            id: Event ID for client tracking
            retry: Reconnection time in milliseconds
        """
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def encode(self) -> str:
        """Encode event as SSE format.

        Returns:
            SSE-formatted string
        """
        message = ""
        if self.event:
            message += f"event: {self.event}\n"
        if self.id:
            message += f"id: {self.id}\n"
        if self.retry:
            message += f"retry: {self.retry}\n"

        # Encode data as JSON
        data_str = json.dumps(self.data)
        # SSE spec requires each line to start with "data: "
        for line in data_str.split("\n"):
            message += f"data: {line}\n"

        message += "\n"  # Empty line to signal end of event
        return message


async def event_generator(
    request: Request,
    download_repository: DownloadRepository,
    poll_interval: float = 2.0,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for real-time updates.

    Args:
        request: FastAPI request object (to detect client disconnect)
        download_repository: Repository for download data
        poll_interval: Seconds between updates

    Yields:
        SSE-formatted event strings
    """
    client_id = id(request)
    logger.info(f"SSE connection established: client_id={client_id}")

    # Send initial connection event
    yield SSEEvent(
        data={"message": "Connected to event stream", "timestamp": datetime.now(UTC).isoformat()},
        event="connected",
        id=str(client_id),
    ).encode()

    # Heartbeat counter
    heartbeat_counter = 0

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"SSE client disconnected: client_id={client_id}")
                break

            # Send heartbeat every 30 seconds (15 iterations * 2s)
            heartbeat_counter += 1
            if heartbeat_counter >= 15:
                yield SSEEvent(
                    data={"timestamp": datetime.now(UTC).isoformat()},
                    event="heartbeat",
                ).encode()
                heartbeat_counter = 0

            # Get active downloads
            try:
                downloads = await download_repository.list_active()

                # Prepare download data
                downloads_data = [
                    {
                        "id": str(download.id.value),
                        "track_id": str(download.track_id.value),
                        "status": download.status.value,
                        "progress_percent": download.progress_percent or 0,
                        "priority": download.priority,
                        "created_at": download.created_at.isoformat(),
                    }
                    for download in downloads[:10]  # Limit to 10 most recent
                ]

                # Send download update event
                yield SSEEvent(
                    data={
                        "downloads": downloads_data,
                        "total_count": len(downloads),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    event="downloads_update",
                ).encode()

            except Exception as e:
                logger.exception(f"Error generating SSE event: {e}")
                yield SSEEvent(
                    data={"error": str(e), "timestamp": datetime.now(UTC).isoformat()},
                    event="error",
                ).encode()

            # Wait before next update
            await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        logger.info(f"SSE connection cancelled: client_id={client_id}")
    except Exception as e:
        logger.exception(f"Error in SSE event stream: client_id={client_id}, error={e}")
    finally:
        logger.info(f"SSE connection closed: client_id={client_id}")


@router.get("/stream")
async def event_stream(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time updates.

    This endpoint establishes an SSE connection and streams events to the client.
    Events include download status updates, job completions, and heartbeats.

    Example client-side usage:
    ```javascript
    const eventSource = new EventSource('/api/ui/sse/stream');

    eventSource.addEventListener('downloads_update', (event) => {
        const data = JSON.parse(event.data);
        console.log('Downloads:', data.downloads);
    });

    eventSource.addEventListener('heartbeat', (event) => {
        console.log('Heartbeat received');
    });

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
    };
    ```

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return StreamingResponse(
        event_generator(request, download_repository),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/test")
async def sse_test(request: Request) -> StreamingResponse:
    """Simple SSE test endpoint for debugging.

    Sends a counter event every second for 10 seconds.

    Returns:
        StreamingResponse with test events
    """

    async def test_generator() -> AsyncGenerator[str, None]:
        """Generate test SSE events."""
        for i in range(10):
            if await request.is_disconnected():
                break

            yield SSEEvent(
                data={"counter": i, "timestamp": datetime.now(UTC).isoformat()},
                event="test_event",
                id=str(i),
            ).encode()

            await asyncio.sleep(1)

        yield SSEEvent(
            data={"message": "Test completed", "timestamp": datetime.now(UTC).isoformat()},
            event="test_complete",
        ).encode()

    return StreamingResponse(
        test_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
