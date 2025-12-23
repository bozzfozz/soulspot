"""Docker Logs Viewer API Router.

Hey future me - this router provides a web UI to view Docker container logs!
Instead of `docker logs -f soulspot`, users can view logs in their browser.
Implements:
1. GET /logs - HTML page with log viewer UI
2. GET /api/logs/stream - SSE endpoint for real-time log streaming
3. GET /api/logs/download - Download logs as file

The logs are read from Docker container using subprocess (docker logs command).
Real-time streaming uses SSE (Server-Sent Events) like download_manager.py does.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])

# Initialize Jinja2 templates (same pattern as ui.py)
templates_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# Hey future me - this is the main logs viewer page!
# Shows a web-based log viewer with filtering, search, and auto-refresh.
# Users can select log level (DEBUG, INFO, WARNING, ERROR), search by text,
# and toggle auto-refresh (SSE streaming).
@router.get("", response_class=HTMLResponse)
async def logs_viewer_page(request: Request) -> Any:
    """Logs viewer page with filtering and search."""
    return templates.TemplateResponse(
        request,
        "logs.html",
        context={
            "title": "Docker Logs",
            "container_name": "soulspot",
        },
    )


# Hey future me - SSE endpoint for real-time log streaming!
# Runs `docker logs -f soulspot` and streams output to browser.
# Each log line is sent as SSE event. Filter by log level via query param.
# Connection stays open until client disconnects or error occurs.
@router.get("/stream")
async def stream_logs(
    level: str = Query("ALL", description="Filter by log level: ALL, DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    search: str = Query("", description="Search filter (case-insensitive)"),
    tail: int = Query(100, ge=0, le=1000, description="Number of lines to show initially"),
) -> EventSourceResponse:
    """Stream Docker logs via SSE (Server-Sent Events)."""

    async def event_generator():
        """Generate SSE events from Docker logs."""
        try:
            # Start docker logs command (tail + follow)
            # Hey future me - we use subprocess with async I/O!
            # The `-f` flag follows logs (like `tail -f`), `--tail` limits initial lines.
            # stderr=STDOUT combines both streams (Docker logs can write to stderr too).
            process = await asyncio.create_subprocess_exec(
                "docker",
                "logs",
                "-f",
                "--tail",
                str(tail),
                "soulspot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Send initial heartbeat
            yield {
                "event": "connected",
                "data": {"timestamp": datetime.now().isoformat(), "status": "streaming"},
            }

            # Stream log lines as they arrive
            assert process.stdout is not None  # for mypy
            while True:
                line = await process.stdout.readline()
                if not line:
                    # Process ended or no more output
                    break

                log_line = line.decode("utf-8", errors="replace").rstrip()

                # Apply filters
                if level != "ALL" and level not in log_line:
                    continue
                if search and search.lower() not in log_line.lower():
                    continue

                # Send log line as SSE event
                yield {
                    "event": "log",
                    "data": {"line": log_line, "timestamp": datetime.now().isoformat()},
                }

                # Small delay to prevent overwhelming browser
                await asyncio.sleep(0.01)

            # Process ended
            await process.wait()
            yield {
                "event": "disconnected",
                "data": {"reason": "docker logs process ended", "exit_code": process.returncode},
            }

        except Exception as e:
            logger.exception("Error streaming Docker logs: %s", e)
            yield {
                "event": "error",
                "data": {"error": str(e), "timestamp": datetime.now().isoformat()},
            }

    return EventSourceResponse(event_generator())


# Hey future me - download logs as text file!
# Useful for sharing logs with support or analyzing offline.
# Runs `docker logs --tail <lines> soulspot` once (no streaming).
@router.get("/download")
async def download_logs(
    tail: int = Query(1000, ge=100, le=10000, description="Number of lines to download"),
) -> StreamingResponse:
    """Download Docker logs as text file."""

    async def log_generator():
        """Generate log file content."""
        try:
            # Run docker logs command (one-shot, no follow)
            result = await asyncio.create_subprocess_exec(
                "docker",
                "logs",
                "--tail",
                str(tail),
                "soulspot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Read all output
            assert result.stdout is not None  # for mypy
            while True:
                line = await result.stdout.readline()
                if not line:
                    break
                yield line

            await result.wait()

        except Exception as e:
            logger.exception("Error downloading Docker logs: %s", e)
            error_msg = f"Error downloading logs: {e}\n"
            yield error_msg.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"soulspot_logs_{timestamp}.txt"

    return StreamingResponse(
        log_generator(),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
