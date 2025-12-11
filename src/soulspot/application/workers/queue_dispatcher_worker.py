"""Queue Dispatcher Worker - dispatches waiting downloads when download manager becomes available.

Hey future me - this worker solves the "slskd offline" problem! When users queue downloads but slskd
is unavailable (offline, not running, network issues), downloads go to WAITING status instead of
failing immediately. This worker monitors slskd availability and dispatches waiting downloads
one-by-one when slskd becomes available.

Flow:
1. User queues download → if slskd unavailable → status = WAITING (stored in DB, NOT job queue)
2. QueueDispatcherWorker runs every N seconds
3. Checks slskd health (via test_connection)
4. If healthy:
   a. Get one WAITING download (oldest first, respecting priority)
   b. Change status to PENDING
   c. Enqueue a DOWNLOAD job in the job queue
   d. Repeat

Why one-by-one? Because:
- We need to verify slskd actually accepts the download
- If we send 100 downloads and slskd crashes, they all fail
- Controlled flow prevents overwhelming slskd's queue
- Better user feedback (progress is visible)

Future extension: This design allows swapping slskd for other download managers (Nicotine+, etc.)
by implementing the IDownloadManager interface.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from soulspot.application.workers.job_queue import JobQueue, JobType
from soulspot.domain.entities import DownloadStatus
from soulspot.domain.value_objects import TrackId
from soulspot.infrastructure.persistence.models import DownloadModel

logger = logging.getLogger(__name__)


class QueueDispatcherWorker:
    """Worker that dispatches waiting downloads when download manager is available.

    This worker:
    1. Periodically checks if download manager (slskd) is available
    2. When available, dispatches one WAITING download at a time
    3. Creates job in job queue so DownloadWorker can process it
    4. Tracks availability state changes for logging
    5. Handles graceful shutdown
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker",  # type: ignore[name-defined]
        slskd_client: "ISlskdClient",  # type: ignore[name-defined]
        job_queue: JobQueue,
        check_interval: int = 30,
        dispatch_delay: float = 2.0,
        max_dispatch_per_cycle: int = 5,
    ) -> None:
        """Initialize dispatcher worker.

        Args:
            session_factory: Factory for creating DB sessions
            slskd_client: Client for checking slskd availability
            job_queue: Job queue for enqueueing download jobs
            check_interval: Seconds between availability checks
            dispatch_delay: Seconds to wait between dispatching downloads
            max_dispatch_per_cycle: Max downloads to dispatch per cycle (prevents overload)

        Hey future me - session_factory is crucial! Don't pass a single session because:
        1. Sessions shouldn't live across async sleeps (can timeout/disconnect)
        2. Each dispatch should be its own transaction
        3. Allows proper cleanup on errors
        """
        self._session_factory = session_factory
        self._slskd_client = slskd_client
        self._job_queue = job_queue
        self._check_interval = check_interval
        self._dispatch_delay = dispatch_delay
        self._max_dispatch_per_cycle = max_dispatch_per_cycle
        self._running = False
        self._last_available: bool | None = None  # Track state changes for logging

    async def start(self) -> None:
        """Start the dispatcher worker.

        Runs continuously until stop() is called.
        """
        self._running = True
        logger.info(
            "QueueDispatcherWorker started (check_interval=%ds, dispatch_delay=%.1fs)",
            self._check_interval,
            self._dispatch_delay,
        )

        while self._running:
            try:
                await self._dispatch_cycle()
            except Exception as e:
                # Don't crash the worker on errors - log and continue
                logger.exception("QueueDispatcherWorker error: %s", e)

            await asyncio.sleep(self._check_interval)

        logger.info("QueueDispatcherWorker stopped")

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    async def _dispatch_cycle(self) -> None:
        """Run one dispatch cycle.

        1. Check slskd availability
        2. If available, dispatch waiting downloads
        3. Log state changes
        """
        # Check slskd health
        is_available = await self._check_slskd_available()

        # Log state changes
        if self._last_available is not None and is_available != self._last_available:
            if is_available:
                logger.info("Download manager (slskd) is now AVAILABLE - will dispatch waiting downloads")
            else:
                logger.warning("Download manager (slskd) is now UNAVAILABLE - downloads will wait")

        self._last_available = is_available

        if not is_available:
            return

        # Dispatch waiting downloads
        dispatched = await self._dispatch_waiting_downloads()
        if dispatched > 0:
            logger.info("Dispatched %d waiting download(s) to download manager", dispatched)

    async def _check_slskd_available(self) -> bool:
        """Check if slskd is available and accepting downloads.

        Returns:
            True if slskd is healthy and can accept downloads
        """
        try:
            result = await self._slskd_client.test_connection()
            return result.get("success", False)
        except Exception as e:
            logger.debug("slskd availability check failed: %s", e)
            return False

    async def _dispatch_waiting_downloads(self) -> int:
        """Dispatch waiting downloads to PENDING status and enqueue jobs.

        Returns:
            Number of downloads dispatched
        """
        dispatched = 0

        async with self._session_factory() as session:
            for _ in range(self._max_dispatch_per_cycle):
                # Get oldest WAITING download (respecting priority: higher priority first)
                # Hey future me - we ORDER BY priority DESC (high priority first), then created_at ASC (oldest first)
                stmt = (
                    select(DownloadModel)
                    .where(DownloadModel.status == DownloadStatus.WAITING.value)
                    .order_by(DownloadModel.priority.desc(), DownloadModel.created_at.asc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                download = result.scalar_one_or_none()

                if not download:
                    # No more waiting downloads
                    break

                # Dispatch: WAITING → PENDING
                download.status = DownloadStatus.PENDING.value
                download.updated_at = datetime.now(UTC)
                await session.commit()

                # Enqueue job in job queue so DownloadWorker picks it up
                # Hey future me - the job_queue.enqueue creates the actual background job that
                # DownloadWorker.handle_download_job will process. We pass track_id so it can
                # look up the track and search for it on Soulseek.
                track_id = TrackId.from_string(download.track_id)
                await self._job_queue.enqueue(
                    job_type=JobType.DOWNLOAD,
                    payload={
                        "track_id": str(track_id.value),
                        "search_query": None,  # Will be auto-generated from track metadata
                        "max_results": 10,
                        "timeout_seconds": 30,
                        "quality_preference": "best",
                    },
                    max_retries=3,
                    priority=download.priority,
                )

                logger.debug(
                    "Dispatched download %s (track_id=%s) from WAITING to PENDING, job enqueued",
                    download.id,
                    download.track_id,
                )

                dispatched += 1

                # Brief delay between dispatches to prevent overwhelming
                if dispatched < self._max_dispatch_per_cycle:
                    await asyncio.sleep(self._dispatch_delay)

        return dispatched

    async def get_waiting_count(self) -> int:
        """Get count of downloads waiting for dispatch.

        Returns:
            Number of downloads in WAITING status
        """
        async with self._session_factory() as session:
            from sqlalchemy import func

            stmt = select(func.count(DownloadModel.id)).where(
                DownloadModel.status == DownloadStatus.WAITING.value
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_queue_stats(self) -> dict[str, int]:
        """Get statistics about the download queue.

        Returns:
            Dict with counts per status
        """
        async with self._session_factory() as session:
            from sqlalchemy import func

            stmt = (
                select(DownloadModel.status, func.count(DownloadModel.id))
                .group_by(DownloadModel.status)
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
            }


# Hey future me - factory function for easy worker creation from app context
def create_queue_dispatcher_worker(
    session_factory: "async_sessionmaker",  # type: ignore[name-defined]
    slskd_client: "ISlskdClient",  # type: ignore[name-defined]
    job_queue: JobQueue,
) -> QueueDispatcherWorker:
    """Create a QueueDispatcherWorker with default settings.

    Args:
        session_factory: Factory for creating DB sessions
        slskd_client: Client for slskd operations
        job_queue: Job queue for enqueueing download jobs

    Returns:
        Configured QueueDispatcherWorker instance
    """
    return QueueDispatcherWorker(
        session_factory=session_factory,
        slskd_client=slskd_client,
        job_queue=job_queue,
        check_interval=30,  # Check every 30 seconds
        dispatch_delay=2.0,  # 2 seconds between dispatches
        max_dispatch_per_cycle=5,  # Max 5 downloads per cycle
    )
