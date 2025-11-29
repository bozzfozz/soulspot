# Hey future me - this worker handles LIBRARY_SCAN jobs from the JobQueue!
# It instantiates LibraryScannerService and runs the scan in background.
# The worker is registered with the JobQueue during app startup (like DownloadWorker).
# Progress is tracked via job.result updates.
"""Library scan worker for background scanning jobs."""

import logging
from typing import TYPE_CHECKING, Any

from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.config import Settings

if TYPE_CHECKING:
    from soulspot.infrastructure.persistence.database import Database

logger = logging.getLogger(__name__)


class LibraryScanWorker:
    """Worker for processing library scan jobs.

    This worker:
    1. Receives LIBRARY_SCAN jobs from JobQueue
    2. Creates LibraryScannerService with fresh DB session
    3. Runs scan (full or incremental based on payload)
    4. Updates job progress and result

    Similar pattern to DownloadWorker - call register() after init!
    """

    def __init__(
        self,
        job_queue: JobQueue,
        db: "Database",
        settings: Settings,
    ) -> None:
        """Initialize worker.

        Args:
            job_queue: Job queue for background processing
            db: Database instance for creating sessions
            settings: Application settings
        """
        self._job_queue = job_queue
        self.db = db
        self.settings = settings

    def register(self) -> None:
        """Register handler with job queue.

        Call this AFTER app is fully initialized!
        """
        self._job_queue.register_handler(JobType.LIBRARY_SCAN, self._handle_scan_job)

    async def _handle_scan_job(self, job: Job) -> dict[str, Any]:
        """Handle a library scan job.

        Called by JobQueue when a LIBRARY_SCAN job is ready.

        Args:
            job: The job to process

        Returns:
            Scan statistics dict
        """
        from soulspot.application.services.library_scanner_service import (
            LibraryScannerService,
        )

        payload = job.payload
        incremental = payload.get("incremental", True)

        logger.info(
            f"Starting library scan job {job.id} " f"(incremental={incremental})"
        )

        # Create fresh session for this job using session_scope context manager
        # Hey future me - using session_scope ensures proper connection cleanup!
        async with self.db.session_scope() as session:
            try:
                service = LibraryScannerService(
                    session=session,
                    settings=self.settings,
                )

                # Define progress callback that updates job result
                async def progress_callback(
                    progress: float, stats: dict[str, Any]
                ) -> None:
                    job.result = {
                        "progress": progress,
                        "stats": stats,
                    }

                # Run scan
                stats = await service.scan_library(
                    incremental=incremental,
                    progress_callback=progress_callback,
                )

                logger.info(
                    f"Library scan job {job.id} complete: "
                    f"{stats['imported']} imported, {stats['errors']} errors"
                )

                return stats

            except Exception as e:
                logger.error(f"Library scan job {job.id} failed: {e}")
                raise
