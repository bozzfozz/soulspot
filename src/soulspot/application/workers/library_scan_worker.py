# Hey future me - this worker handles LIBRARY_SCAN jobs from the JobQueue!
# It instantiates LibraryScannerService and runs the scan in background.
# The worker is registered with the JobQueue during app startup (like DownloadWorker).
# Progress is tracked via job.result updates.
#
# PERFORMANCE OPTIMIZATION (Dec 2025):
# - Cleanup is now DEFERRED by default (runs as separate LIBRARY_SCAN_CLEANUP job)
# - This keeps the main scan fast and UI responsive
# - Cleanup job can be skipped if only incremental scanning
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
    5. Queues LIBRARY_SCAN_CLEANUP job if needed (deferred cleanup)

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
        """Register handlers with job queue.

        Call this AFTER app is fully initialized!
        """
        self._job_queue.register_handler(JobType.LIBRARY_SCAN, self._handle_scan_job)
        self._job_queue.register_handler(
            JobType.LIBRARY_SCAN_CLEANUP, self._handle_cleanup_job
        )

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
        defer_cleanup = payload.get("defer_cleanup", True)  # Default: deferred cleanup

        logger.info(
            f"Starting library scan job {job.id} "
            f"(incremental={incremental}, defer_cleanup={defer_cleanup})"
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

                # Run scan with deferred cleanup option
                stats = await service.scan_library(
                    incremental=incremental,
                    defer_cleanup=defer_cleanup,
                    progress_callback=progress_callback,
                )

                logger.info(
                    f"Library scan job {job.id} complete: "
                    f"{stats['imported']} imported, {stats['errors']} errors"
                )

                # Queue cleanup job if needed (deferred cleanup strategy)
                if stats.get("cleanup_needed") and stats.get("cleanup_file_paths"):
                    await self._queue_cleanup_job(stats["cleanup_file_paths"])
                    # Remove file paths from stats (too large for job result)
                    stats["cleanup_file_paths"] = None
                    stats["cleanup_job_queued"] = True

                # Trigger enrichment job if enabled
                await self._trigger_enrichment_if_enabled(session, stats)

                return stats

            except Exception as e:
                logger.error(f"Library scan job {job.id} failed: {e}")
                raise

    async def _handle_cleanup_job(self, job: Job) -> dict[str, Any]:
        """Handle a library scan cleanup job.

        Called by JobQueue when a LIBRARY_SCAN_CLEANUP job is ready.
        This is the DEFERRED cleanup that runs after scan completes.

        Args:
            job: The job to process

        Returns:
            Cleanup statistics dict
        """
        from soulspot.application.services.library_scanner_service import (
            LibraryScannerService,
        )

        payload = job.payload
        file_paths = payload.get("file_paths", [])

        if not file_paths:
            logger.warning(f"Cleanup job {job.id} has no file paths, skipping")
            return {"removed_tracks": 0, "removed_albums": 0, "removed_artists": 0}

        logger.info(
            f"Starting library cleanup job {job.id} "
            f"({len(file_paths)} existing files to check against)"
        )

        async with self.db.session_scope() as session:
            try:
                service = LibraryScannerService(
                    session=session,
                    settings=self.settings,
                )

                # Convert list back to set for efficient lookups
                file_paths_set = set(file_paths)

                # Run cleanup
                stats = await service._cleanup_missing_files(file_paths_set)

                logger.info(
                    f"Library cleanup job {job.id} complete: "
                    f"{stats['removed_tracks']} tracks, "
                    f"{stats['removed_albums']} albums, "
                    f"{stats['removed_artists']} artists removed"
                )

                return stats

            except Exception as e:
                logger.error(f"Library cleanup job {job.id} failed: {e}")
                raise

    async def _queue_cleanup_job(self, file_paths: list[str]) -> str:
        """Queue a deferred cleanup job.

        Args:
            file_paths: List of existing file paths to check against

        Returns:
            Job ID of the queued cleanup job
        """
        logger.info(f"Queuing deferred cleanup job ({len(file_paths)} files)")

        job_id = await self._job_queue.enqueue(
            job_type=JobType.LIBRARY_SCAN_CLEANUP,
            payload={"file_paths": file_paths},
            priority=3,  # Lower priority than scan itself
        )

        logger.info(f"Cleanup job queued: {job_id}")
        return job_id

    async def _trigger_enrichment_if_enabled(
        self,
        session: Any,
        scan_stats: dict[str, Any],
    ) -> None:
        """Trigger enrichment job if auto-enrichment is enabled and items were imported.

        Only triggers if:
        1. auto_enrichment_enabled setting is True
        2. At least one new artist or album was imported

        Args:
            session: Database session
            scan_stats: Stats from the completed scan
        """
        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )

        # Check if auto-enrichment is enabled
        settings_service = AppSettingsService(session)
        if not await settings_service.is_library_auto_enrichment_enabled():
            logger.debug("Auto-enrichment disabled, skipping")
            return

        # Check if anything was imported that needs enrichment
        new_artists = scan_stats.get("new_artists", 0)
        new_albums = scan_stats.get("new_albums", 0)

        if new_artists == 0 and new_albums == 0:
            logger.debug("No new items imported, skipping enrichment")
            return

        # Queue enrichment job
        logger.info(
            f"Queuing enrichment job for {new_artists} artists, {new_albums} albums"
        )

        await self._job_queue.enqueue(
            job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
            payload={
                "triggered_by": "library_scan",
                "new_artists": new_artists,
                "new_albums": new_albums,
            },
        )
