"""Download Queue Worker - Unified queue management (Lidarr-inspired).

Hey future me - THIS MANAGES THE DOWNLOAD QUEUE!

REPLACES:
- queue_dispatcher_worker.py (352 lines) - dispatched WAITING downloads
- retry_scheduler_worker.py (214 lines) - retried FAILED downloads

TOTAL BEFORE: ~566 lines
TOTAL AFTER: ~350 lines (this file)

WHY MERGE?
1. Both workers manage the same download queue
2. Both transition downloads between states
3. Separate workers meant race conditions possible
4. Retry logic is part of queue management

ARCHITECTURE (Lidarr-inspired):
- Single queue manager (like Lidarr's Download Client Handler)
- Handles dispatch AND retry in one cycle
- Blocklist pattern for permanent failures
- Priority-based queue ordering

FEATURES PRESERVED:
From QueueDispatcherWorker:
- Check slskd availability
- Query WAITING downloads
- Transition WAITING → PENDING
- Enqueue jobs in JobQueue
- Priority ordering
- Dispatch delay

From RetrySchedulerWorker:
- Query retry-eligible downloads
- Check non-retryable errors
- Activate for retry (FAILED → WAITING)
- Backoff calculation

NEW FEATURES:
- Blocklist pattern: permanent failures get BLOCKLISTED status
- Unified stats tracking
- Single transaction per cycle
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from soulspot.application.workers.job_queue import JobQueue, JobType
from soulspot.domain.entities import DownloadStatus
from soulspot.domain.value_objects import TrackId
from soulspot.infrastructure.observability.logger_template import log_worker_health
from soulspot.infrastructure.persistence.models import DownloadModel
from soulspot.infrastructure.persistence.repositories import DownloadRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from soulspot.domain.ports import ISlskdClient

logger = logging.getLogger(__name__)


# =============================================================================
# BLOCKLIST ERRORS (Lidarr-inspired)
# =============================================================================
# Hey future me - these errors should NEVER be retried!
# Like Lidarr's blocklist, we permanently fail these downloads.
# User can manually de-blocklist via UI if needed.

BLOCKLIST_ERRORS = {
    "file_not_found",      # File doesn't exist on Soulseek
    "user_blocked",        # User has blocked us
    "corrupted_file",      # Downloaded file is corrupt
    "invalid_format",      # Not a valid audio format
    "no_free_slots",       # User has no free upload slots (after many retries)
    "access_denied",       # Permission denied
}

# Maximum retry attempts before blocklisting
MAX_RETRIES = 3


class DownloadQueueWorker:
    """Unified download queue management - Lidarr-inspired.

    Hey future me - THIS MANAGES THE DOWNLOAD QUEUE!
    Like Lidarr's Download Client Handler, we manage dispatch + retry.

    Responsibilities:
    1. Dispatch: WAITING → PENDING → JobQueue
    2. Retry: FAILED → WAITING (after backoff)
    3. Blocklist: Permanent failures → BLOCKLISTED

    Features:
    - Single cycle handles both dispatch and retry
    - Priority-based queue ordering
    - Blocklist for permanent failures
    - Graceful degradation when slskd offline
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker[AsyncSession]",
        slskd_client: "ISlskdClient",
        job_queue: JobQueue,
        check_interval: int = 30,
        dispatch_delay: float = 2.0,
        max_dispatch_per_cycle: int = 5,
        max_retries_per_cycle: int = 10,
    ) -> None:
        """Initialize the download queue worker.

        Args:
            session_factory: Factory for creating DB sessions
            slskd_client: Client for checking slskd availability
            job_queue: Job queue for enqueueing download jobs
            check_interval: Seconds between queue checks (default 30)
            dispatch_delay: Seconds between dispatches (default 2)
            max_dispatch_per_cycle: Max downloads to dispatch per cycle (default 5)
            max_retries_per_cycle: Max retries to activate per cycle (default 10)

        Hey future me - session_factory is crucial! Don't pass a single session because
        sessions shouldn't live across async sleeps.
        """
        self._session_factory = session_factory
        self._slskd_client = slskd_client
        self._job_queue = job_queue
        self._check_interval = check_interval
        self._dispatch_delay = dispatch_delay
        self._max_dispatch_per_cycle = max_dispatch_per_cycle
        self._max_retries_per_cycle = max_retries_per_cycle
        self._running = False

        # Track slskd availability state
        self._last_available: bool | None = None

        # Lifecycle tracking
        self._cycles_completed = 0
        self._errors_total = 0
        self._start_time = time.time()

        # Stats
        self._stats: dict[str, int | str | None] = {
            "dispatched_total": 0,
            "retries_activated": 0,
            "blocklisted_total": 0,
            "last_cycle_at": None,
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the queue worker.

        Runs continuously until stop() is called.
        """
        self._running = True
        self._start_time = time.time()

        logger.info(
            "worker.started",
            extra={
                "worker": "download_queue",
                "check_interval_seconds": self._check_interval,
                "max_dispatch_per_cycle": self._max_dispatch_per_cycle,
                "max_retries_per_cycle": self._max_retries_per_cycle,
            },
        )

        while self._running:
            try:
                await self._queue_cycle()
                self._cycles_completed += 1
                self._stats["last_cycle_at"] = datetime.now(UTC).isoformat()

                # Log health every 10 cycles
                if self._cycles_completed % 10 == 0:
                    log_worker_health(
                        logger=logger,
                        worker_name="download_queue",
                        cycles_completed=self._cycles_completed,
                        errors_total=self._errors_total,
                        uptime_seconds=time.time() - self._start_time,
                        extra_stats={
                            "dispatched_total": self._stats.get("dispatched_total", 0),
                            "retries_activated": self._stats.get("retries_activated", 0),
                        },
                    )

            except Exception as e:
                self._errors_total += 1
                logger.error(
                    "download_queue.loop_error",
                    exc_info=True,
                    extra={"error_type": type(e).__name__, "cycle": self._cycles_completed},
                )

            await asyncio.sleep(self._check_interval)

        uptime = time.time() - self._start_time
        logger.info(
            "worker.stopped",
            extra={
                "worker": "download_queue",
                "cycles_completed": self._cycles_completed,
                "errors_total": self._errors_total,
                "uptime_seconds": round(uptime, 2),
                "dispatched_total": self._stats.get("dispatched_total", 0),
            },
        )

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    def get_status(self) -> dict[str, Any]:
        """Get current worker status for monitoring."""
        return {
            "name": "Download Queue (Unified)",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self._check_interval,
            "slskd_available": self._last_available,
            "stats": self._stats.copy(),
        }

    # =========================================================================
    # MAIN CYCLE
    # =========================================================================

    async def _queue_cycle(self) -> None:
        """Run one queue management cycle.

        Hey future me - THIS IS THE KEY CHANGE!
        We handle BOTH dispatch AND retry in one cycle.
        Old workers ran separately (potential race conditions).

        Flow:
        1. Check slskd availability
        2. Process retries (FAILED → WAITING) - always runs
        3. Process blocklist (permanent failures)
        4. Dispatch waiting downloads (only if slskd available)
        """
        async with self._session_factory() as session:
            # 1. Process retries (runs even if slskd offline)
            await self._process_retries(session)

            # 2. Check slskd availability
            is_available = await self._check_slskd_available()

            # Log state changes
            if self._last_available is not None and is_available != self._last_available:
                if is_available:
                    logger.info("slskd is now AVAILABLE - will dispatch waiting downloads")
                else:
                    logger.warning("slskd is now UNAVAILABLE - downloads will wait")
            self._last_available = is_available

            # 3. Dispatch waiting downloads (only if slskd available)
            if is_available:
                dispatched = await self._dispatch_waiting(session)
                if dispatched > 0:
                    logger.info(f"Dispatched {dispatched} downloads to slskd")

            await session.commit()

    # =========================================================================
    # RETRY PROCESSING (from RetrySchedulerWorker)
    # =========================================================================

    async def _process_retries(self, session: "AsyncSession") -> None:
        """Process retry-eligible and blocklist downloads.

        Hey future me - this handles ALL retry logic:
        1. Find retry-eligible downloads
        2. Check for blocklist errors → permanent fail
        3. Check retry count → blocklist if exceeded
        4. Activate valid retries → FAILED → WAITING
        """
        repo = DownloadRepository(session)

        # Get retry-eligible downloads
        eligible = await repo.list_retry_eligible(limit=self._max_retries_per_cycle)

        if not eligible:
            return

        logger.debug(f"Found {len(eligible)} downloads eligible for retry")

        activated = 0
        blocklisted = 0

        for download in eligible:
            try:
                # Check for blocklist errors
                if download.last_error_code and download.last_error_code in BLOCKLIST_ERRORS:
                    # Permanent failure → blocklist
                    download.status = DownloadStatus.BLOCKLISTED
                    await repo.update(download)
                    blocklisted += 1
                    logger.info(
                        f"Blocklisted download {download.id.value}: {download.last_error_code}"
                    )
                    continue

                # Check retry count
                if download.retry_count >= MAX_RETRIES:
                    # Max retries reached → blocklist
                    download.status = DownloadStatus.BLOCKLISTED
                    await repo.update(download)
                    blocklisted += 1
                    logger.info(
                        f"Blocklisted download {download.id.value} after {MAX_RETRIES} retries"
                    )
                    continue

                # Entity validation
                if not download.should_retry():
                    continue

                # Activate for retry
                download.activate_for_retry()
                await repo.update(download)
                activated += 1
                logger.info(
                    f"Activated retry for download {download.id.value} "
                    f"(attempt {download.retry_count}/{download.max_retries})"
                )

            except ValueError as e:
                logger.warning(f"Cannot activate retry for {download.id.value}: {e}")
            except Exception as e:
                logger.error(f"Error processing retry for {download.id.value}: {e}")

        # Update stats
        self._stats["retries_activated"] = (
            int(self._stats.get("retries_activated") or 0) + activated
        )
        self._stats["blocklisted_total"] = (
            int(self._stats.get("blocklisted_total") or 0) + blocklisted
        )

        if activated > 0:
            logger.info(f"Activated {activated} downloads for retry")
        if blocklisted > 0:
            logger.info(f"Blocklisted {blocklisted} downloads")

    # =========================================================================
    # DISPATCH (from QueueDispatcherWorker)
    # =========================================================================

    async def _check_slskd_available(self) -> bool:
        """Check if slskd is available and accepting downloads."""
        try:
            result = await self._slskd_client.test_connection()
            return result.get("success", False)
        except Exception as e:
            logger.debug(f"slskd availability check failed: {e}")
            return False

    async def _dispatch_waiting(self, session: "AsyncSession") -> int:
        """Dispatch WAITING downloads to PENDING and enqueue jobs.

        Returns:
            Number of downloads dispatched.
        """
        dispatched = 0

        for _ in range(self._max_dispatch_per_cycle):
            # Get oldest WAITING download (respecting priority)
            stmt = (
                select(DownloadModel)
                .where(DownloadModel.status == DownloadStatus.WAITING.value)
                .order_by(
                    DownloadModel.priority.desc(),
                    DownloadModel.created_at.asc(),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            download = result.scalar_one_or_none()

            if not download:
                break

            # Dispatch: WAITING → PENDING
            download.status = DownloadStatus.PENDING.value
            download.updated_at = datetime.now(UTC)

            # Enqueue job
            track_id = TrackId.from_string(download.track_id)
            await self._job_queue.enqueue(
                job_type=JobType.DOWNLOAD,
                payload={
                    "track_id": str(track_id.value),
                    "search_query": None,
                    "max_results": 10,
                    "timeout_seconds": 30,
                    "quality_preference": "best",
                },
                max_retries=3,
                priority=download.priority,
            )

            logger.debug(
                f"Dispatched download {download.id} (track_id={download.track_id})"
            )

            dispatched += 1
            self._stats["dispatched_total"] = (
                int(self._stats.get("dispatched_total") or 0) + 1
            )

            # Brief delay between dispatches
            if dispatched < self._max_dispatch_per_cycle:
                await asyncio.sleep(self._dispatch_delay)

        return dispatched

    # =========================================================================
    # QUEUE STATS
    # =========================================================================

    async def get_waiting_count(self) -> int:
        """Get count of downloads waiting for dispatch."""
        async with self._session_factory() as session:
            from sqlalchemy import func

            stmt = select(func.count(DownloadModel.id)).where(
                DownloadModel.status == DownloadStatus.WAITING.value
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_queue_stats(self) -> dict[str, int]:
        """Get statistics about the download queue."""
        async with self._session_factory() as session:
            from sqlalchemy import func

            stmt = select(DownloadModel.status, func.count(DownloadModel.id)).group_by(
                DownloadModel.status
            )
            result = await session.execute(stmt)
            stats = dict(result.all())

            return {
                "waiting": stats.get(DownloadStatus.WAITING.value, 0),
                "pending": stats.get(DownloadStatus.PENDING.value, 0),
                "queued": stats.get(DownloadStatus.QUEUED.value, 0),
                "downloading": stats.get(DownloadStatus.DOWNLOADING.value, 0),
                "completed": stats.get(DownloadStatus.COMPLETED.value, 0),
                "failed": stats.get(DownloadStatus.FAILED.value, 0),
                "blocklisted": stats.get(DownloadStatus.BLOCKLISTED.value, 0),
            }


# Factory function
def create_download_queue_worker(
    session_factory: "async_sessionmaker[AsyncSession]",
    slskd_client: "ISlskdClient",
    job_queue: JobQueue,
    check_interval: int = 30,
) -> DownloadQueueWorker:
    """Create a DownloadQueueWorker with default settings.

    Args:
        session_factory: Factory for creating DB sessions
        slskd_client: Client for slskd operations
        job_queue: Job queue for enqueueing download jobs
        check_interval: Seconds between checks (default 30)

    Returns:
        Configured DownloadQueueWorker instance
    """
    return DownloadQueueWorker(
        session_factory=session_factory,
        slskd_client=slskd_client,
        job_queue=job_queue,
        check_interval=check_interval,
        dispatch_delay=2.0,
        max_dispatch_per_cycle=5,
        max_retries_per_cycle=10,
    )
