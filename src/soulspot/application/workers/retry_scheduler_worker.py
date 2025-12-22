"""Retry Scheduler Worker - schedules automatic retries for failed downloads.

Hey future me - this worker RESURRECTS failed downloads!

The problem: Downloads fail for many reasons (timeout, offline user, network).
Most failures are transient - retry later and it might work. But without this
worker, users have to manually click "Retry" on every failed download.

The solution: RetrySchedulerWorker runs every 30 seconds and:
1. Queries DB for retry-eligible downloads (FAILED + retry_count < max + next_retry_at <= now)
2. For each eligible download: calls download.activate_for_retry()
3. This moves status FAILED → WAITING
4. QueueDispatcherWorker picks them up and sends to slskd

BACKOFF STRATEGY (defined in Download entity):
- Retry 1: Wait 1 minute after failure
- Retry 2: Wait 5 minutes after previous failure
- Retry 3: Wait 15 minutes after previous failure
- After 3 retries: Download stays FAILED (manual intervention needed)

NON-RETRYABLE ERRORS (won't be retried):
- file_not_found: The file doesn't exist on Soulseek
- user_blocked: We're blocked by the user
- invalid_file: Downloaded file is corrupted

WHY NOT RETRY IMMEDIATELY?
- Transient issues need time to resolve (user coming online, network recovering)
- Immediate retry would hammer the same failing source
- Backoff spreads load and gives sources time to recover

FLOW:
User queues download → slskd fails → status=FAILED, next_retry_at set
  → 1 min passes → RetrySchedulerWorker finds it
  → status=WAITING → QueueDispatcherWorker picks up
  → slskd tries again → success OR fail again with longer backoff
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.repositories import DownloadRepository

logger = logging.getLogger(__name__)


class RetrySchedulerWorker:
    """Worker that activates failed downloads when their retry time arrives.

    Hey future me - this is the AUTO-RETRY engine!

    Configuration:
    - check_interval: How often to check for retry-eligible downloads (default: 30s)
    - max_retries_per_cycle: How many downloads to process per cycle (default: 10)
      This prevents overwhelming slskd if many downloads fail at once.

    Lifecycle:
    - Created in lifecycle.py during app startup
    - Runs as asyncio task via start()
    - Stopped gracefully via stop() during shutdown
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        check_interval: int = 30,
        max_retries_per_cycle: int = 10,
    ) -> None:
        """Initialize the retry scheduler worker.

        Args:
            session_factory: Factory for creating DB sessions
            check_interval: Seconds between retry checks (default: 30)
            max_retries_per_cycle: Max downloads to retry per cycle (default: 10)
        """
        self._session_factory = session_factory
        self._check_interval = check_interval
        self._max_retries_per_cycle = max_retries_per_cycle
        self._running = False
        self._stats = {
            "total_retries_scheduled": 0,
            "last_check_at": None,
            "downloads_activated_last_cycle": 0,
        }

    async def start(self) -> None:
        """Start the retry scheduler worker.

        Runs continuously until stop() is called.
        """
        self._running = True
        logger.info(
            f"RetrySchedulerWorker started (check_interval={self._check_interval}s, "
            f"max_per_cycle={self._max_retries_per_cycle})"
        )

        while self._running:
            try:
                await self._check_and_activate_retries()
            except Exception as e:
                # Log but don't crash - we'll try again next cycle
                logger.exception(f"RetrySchedulerWorker error: {e}")

            await asyncio.sleep(self._check_interval)

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
        logger.info("RetrySchedulerWorker stopping...")

    async def _check_and_activate_retries(self) -> None:
        """Check for retry-eligible downloads and activate them.

        Hey future me - this is the heart of the retry system!

        Process:
        1. Query DB for downloads ready for retry
        2. Validate each with entity.should_retry() (double-check)
        3. Call entity.activate_for_retry() to move FAILED → WAITING
        4. Save to DB
        5. QueueDispatcherWorker will pick them up next cycle
        """
        activated_count = 0

        async with self._session_factory() as session:
            repo = DownloadRepository(session)

            # Get retry-eligible downloads
            eligible_downloads = await repo.list_retry_eligible(
                limit=self._max_retries_per_cycle
            )

            if not eligible_downloads:
                logger.debug("No downloads eligible for retry")
                self._stats["last_check_at"] = datetime.now(UTC)
                self._stats["downloads_activated_last_cycle"] = 0
                return

            logger.info(f"Found {len(eligible_downloads)} downloads eligible for retry")

            for download in eligible_downloads:
                # Double-check with entity logic (includes error code check)
                if not download.should_retry():
                    logger.debug(
                        f"Download {download.id.value} not eligible for retry "
                        f"(error_code={download.last_error_code})"
                    )
                    continue

                # Activate for retry
                try:
                    download.activate_for_retry()
                    await repo.update(download)
                    activated_count += 1

                    logger.info(
                        f"Activated retry for download {download.id.value} "
                        f"(attempt {download.retry_count}/{download.max_retries})"
                    )
                except ValueError as e:
                    # Entity validation failed - log and skip
                    logger.warning(
                        f"Cannot activate retry for {download.id.value}: {e}"
                    )
                    continue

            await session.commit()

        # Update stats
        self._stats["total_retries_scheduled"] += activated_count
        self._stats["last_check_at"] = datetime.now(UTC)
        self._stats["downloads_activated_last_cycle"] = activated_count

        if activated_count > 0:
            logger.info(f"Activated {activated_count} downloads for retry")

    def get_stats(self) -> dict:
        """Get worker statistics.

        Returns:
            Dictionary with retry statistics
        """
        return {
            **self._stats,
            "running": self._running,
            "check_interval": self._check_interval,
            "max_retries_per_cycle": self._max_retries_per_cycle,
        }


# Hey future me - factory function for easy worker creation from app context
def create_retry_scheduler_worker(
    session_factory: async_sessionmaker[AsyncSession],
    check_interval: int = 30,
    max_retries_per_cycle: int = 10,
) -> RetrySchedulerWorker:
    """Create a RetrySchedulerWorker with the given configuration.

    Args:
        session_factory: Factory for creating DB sessions
        check_interval: Seconds between retry checks
        max_retries_per_cycle: Max downloads to retry per cycle

    Returns:
        Configured RetrySchedulerWorker instance
    """
    return RetrySchedulerWorker(
        session_factory=session_factory,
        check_interval=check_interval,
        max_retries_per_cycle=max_retries_per_cycle,
    )
