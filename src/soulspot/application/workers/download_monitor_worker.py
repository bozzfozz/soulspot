# Hey future me - dieser Worker ÜBERWACHT laufende Downloads!
#
# Problem: DownloadWorker startet Downloads via slskd, aber wir wissen nicht wann sie fertig sind.
# Die UI zeigt keine echten Progress-Bars, Jobs bleiben ewig in "RUNNING" Status.
#
# Lösung: DownloadMonitorWorker pollt slskd alle X Sekunden und:
# 1. Holt Status aller aktiven Downloads via slskd API
# 2. Aktualisiert Job.result mit echtem Progress (bytes_downloaded, percent)
# 3. Markiert Jobs als COMPLETED wenn Download fertig
# 4. Markiert Jobs als FAILED wenn Download fehlschlägt
# 5. Triggert AutoImportService bei Completion (optional)
#
# WICHTIG: Dieser Worker ist READ-ONLY für Jobs! Er modifiziert nur result/status,
# startet keine neuen Downloads. Das macht DownloadWorker.
"""Download monitor worker for tracking slskd download progress."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.infrastructure.integrations.slskd_client import SlskdClient

from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType

logger = logging.getLogger(__name__)


# slskd Download States (from API docs)
# - Queued: Waiting in queue
# - Initializing: Starting transfer
# - InProgress: Actively downloading
# - Completed: Successfully finished
# - Cancelled: User cancelled
# - TimedOut: Connection timed out
# - Errored: Generic error
# - Rejected: User rejected transfer
SLSKD_COMPLETED_STATES = {"Completed", "CompletedSucceeded"}
SLSKD_FAILED_STATES = {
    "Cancelled",
    "TimedOut",
    "Errored",
    "Rejected",
    "CompletedFailed",
}
SLSKD_ACTIVE_STATES = {"Queued", "Initializing", "InProgress", "Requested"}


class DownloadMonitorWorker:
    """Background worker that monitors slskd downloads and updates job status.

    This worker:
    1. Polls slskd API for download status every `poll_interval_seconds`
    2. Updates job progress with bytes_downloaded, percent_complete
    3. Marks jobs as COMPLETED when download finishes
    4. Marks jobs as FAILED when download errors
    5. Provides real-time progress data for UI

    The worker does NOT start downloads - that's DownloadWorker's job.
    This is purely for monitoring and status updates.
    """

    def __init__(
        self,
        job_queue: JobQueue,
        slskd_client: "SlskdClient",
        poll_interval_seconds: int = 10,
    ) -> None:
        """Initialize download monitor worker.

        Args:
            job_queue: Job queue to update job statuses
            slskd_client: Client for slskd API calls
            poll_interval_seconds: How often to poll slskd (default 10s)
        """
        self._job_queue = job_queue
        self._slskd_client = slskd_client
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Stats for monitoring - values can be int, str, or None
        self._stats: dict[str, int | str | None] = {
            "polls_completed": 0,
            "downloads_completed": 0,
            "downloads_failed": 0,
            "last_poll_at": None,
            "last_error": None,
        }

    async def start(self) -> None:
        """Start the download monitor worker.

        Creates a background task that polls slskd periodically.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("Download monitor worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Download monitor worker started (polling every {self._poll_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the download monitor worker.

        Cancels the background task and waits for cleanup.
        Safe to call multiple times (idempotent).
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Download monitor worker stopped")

    def get_status(self) -> dict[str, Any]:
        """Get current worker status for monitoring/UI.

        Returns:
            Dict with running state, stats, and config
        """
        return {
            "name": "Download Monitor",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "poll_interval_seconds": self._poll_interval,
            "stats": self._stats.copy(),
        }

    async def _run_loop(self) -> None:
        """Main worker loop - polls slskd and updates jobs.

        Hey future me - diese Loop läuft EWIG bis stop() aufgerufen wird!
        Auf jedem Durchlauf:
        1. Hole alle RUNNING download jobs aus JobQueue
        2. Für jeden Job: Hole Status von slskd
        3. Update Job mit Progress
        4. Wenn fertig: Markiere als COMPLETED/FAILED
        """
        # Short delay on startup to let other services initialize
        await asyncio.sleep(5)

        logger.info("Download monitor worker entering main loop")

        while self._running:
            try:
                await self._poll_downloads()
                polls = self._stats.get("polls_completed")
                self._stats["polls_completed"] = (int(polls) if polls else 0) + 1
                self._stats["last_poll_at"] = datetime.now(UTC).isoformat()
                self._stats["last_error"] = None
            except Exception as e:
                # Don't crash the loop on errors
                logger.error(f"Error in download monitor loop: {e}", exc_info=True)
                self._stats["last_error"] = str(e)

            # Wait for next poll
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    async def _poll_downloads(self) -> None:
        """Poll slskd and update all running download jobs.

        Hey future me - diese Methode ist das Herzstück!
        Sie holt den Status von slskd und updated die Jobs entsprechend.
        """
        # Get all RUNNING download jobs
        running_jobs = await self._job_queue.list_jobs(
            status=JobStatus.RUNNING,
            job_type=JobType.DOWNLOAD,
        )

        if not running_jobs:
            logger.debug("No running download jobs to monitor")
            return

        logger.debug(f"Monitoring {len(running_jobs)} running download jobs")

        # Get all downloads from slskd in one call (more efficient than per-job)
        try:
            all_downloads = await self._slskd_client.list_downloads()
        except Exception as e:
            logger.error(f"Failed to fetch downloads from slskd: {e}")
            return

        # Create lookup map: download_id -> status
        download_map = {d["id"]: d for d in all_downloads}

        # Update each job
        for job in running_jobs:
            try:
                await self._update_job_status(job, download_map)
            except Exception as e:
                logger.error(f"Error updating job {job.id}: {e}")

    async def _update_job_status(
        self, job: Any, download_map: dict[str, dict[str, Any]]
    ) -> None:
        """Update a single job's status based on slskd data.

        Args:
            job: The job to update
            download_map: Map of download_id -> slskd status
        """
        # Get slskd_download_id from job result
        if not job.result:
            logger.debug(f"Job {job.id} has no result yet, skipping")
            return

        slskd_download_id = job.result.get("slskd_download_id")
        if not slskd_download_id:
            logger.debug(f"Job {job.id} has no slskd_download_id, skipping")
            return

        # Look up in download map
        slskd_status = download_map.get(slskd_download_id)

        if slskd_status is None:
            # Download not found in slskd - might be completed and cleaned up
            # Or never started. Check if we already have a terminal state.
            existing_state = job.result.get("slskd_state")
            if existing_state in SLSKD_COMPLETED_STATES:
                # Already completed, just not in active list anymore
                await self._mark_job_completed(job)
            elif existing_state in SLSKD_FAILED_STATES:
                # Already failed
                await self._mark_job_failed(job, f"Download failed: {existing_state}")
            else:
                # Unknown state - download disappeared
                logger.warning(
                    f"Download {slskd_download_id} not found in slskd for job {job.id}"
                )
            return

        # Update job result with progress
        state = slskd_status.get("state", "unknown")
        progress = slskd_status.get("progress", 0)
        bytes_transferred = slskd_status.get("bytes_transferred", 0)
        total_size = slskd_status.get("size", 0)

        # Update job.result with progress info
        job.result.update(
            {
                "slskd_state": state,
                "progress_percent": progress,
                "bytes_downloaded": bytes_transferred,
                "total_bytes": total_size,
                "last_updated": datetime.now(UTC).isoformat(),
            }
        )

        # Check if download finished
        if state in SLSKD_COMPLETED_STATES:
            await self._mark_job_completed(job)
        elif state in SLSKD_FAILED_STATES:
            await self._mark_job_failed(job, f"Download failed with state: {state}")
        else:
            # Still in progress - job stays RUNNING
            logger.debug(
                f"Job {job.id}: {state} - {progress}% ({bytes_transferred}/{total_size} bytes)"
            )

    async def _mark_job_completed(self, job: Any) -> None:
        """Mark a job as successfully completed.

        Args:
            job: The job to mark as completed
        """
        job.status = JobStatus.COMPLETED
        job.result["completed_at"] = datetime.now(UTC).isoformat()
        completed = self._stats.get("downloads_completed")
        self._stats["downloads_completed"] = (int(completed) if completed else 0) + 1
        logger.info(f"Download job {job.id} completed successfully")

        # Note: AutoImportService will pick up the file from downloads folder
        # We don't need to trigger it explicitly

    async def _mark_job_failed(self, job: Any, error_message: str) -> None:
        """Mark a job as failed.

        Args:
            job: The job to mark as failed
            error_message: Error description
        """
        job.status = JobStatus.FAILED
        job.result["error"] = error_message
        job.result["failed_at"] = datetime.now(UTC).isoformat()
        failed = self._stats.get("downloads_failed")
        self._stats["downloads_failed"] = (int(failed) if failed else 0) + 1
        logger.warning(f"Download job {job.id} failed: {error_message}")
