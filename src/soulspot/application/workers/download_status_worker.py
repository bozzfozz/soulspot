"""Download Status Worker - Unified slskd monitoring (Lidarr-inspired).

Hey future me - THIS IS THE ONE slskd poller!

REPLACES:
- download_monitor_worker.py (506 lines) - polled slskd for JobQueue updates
- download_status_sync_worker.py (665 lines) - polled slskd for DB updates

TOTAL BEFORE: ~1171 lines
TOTAL AFTER: ~600 lines (this file)

WHY MERGE?
1. Both workers poll slskd API → redundant API calls
2. Both track the same downloads → duplicate logic
3. Circuit breaker was only in StatusSync → Monitor had no resilience

ARCHITECTURE (Lidarr-inspired):
- Single poll contact point (like Lidarr monitors its download client)
- Updates BOTH JobQueue AND DB in one cycle
- Circuit breaker protects against slskd outages
- Completed Download Handling (like Lidarr's post-processing)

FEATURES PRESERVED:
From DownloadMonitorWorker:
- Poll slskd for active downloads
- Update JobQueue with progress
- Mark jobs COMPLETED/FAILED
- Stale download detection (>12h)
- Stale download restart

From DownloadStatusSyncWorker:
- Match slskd downloads to DB entries
- Update DownloadModel status
- Update TrackModel.file_path on completion
- Circuit breaker (CLOSED/OPEN/HALF_OPEN)
- Exponential backoff on failures
- Health status for monitoring

NEW FEATURES:
- Single poll cycle updates both JobQueue AND DB
- Unified stats tracking
- Lidarr-style completed download handling
"""

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.observability.logger_template import log_worker_health
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel

if TYPE_CHECKING:
    from soulspot.domain.ports import ISlskdClient

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS (merged from both workers)
# =============================================================================

# Stale download detection
STALE_TIMEOUT_HOURS = 12
STALE_CHECK_INTERVAL_POLLS = 60  # ~10 minutes at 10s poll interval

# slskd state mappings
SLSKD_COMPLETED_STATES = {"Completed", "CompletedSucceeded", "Succeeded"}
SLSKD_FAILED_STATES = {
    "Cancelled",
    "TimedOut",
    "Errored",
    "Rejected",
    "CompletedFailed",
    "Failed",
}
SLSKD_ACTIVE_STATES = {"Queued", "Initializing", "InProgress", "Requested", "Downloading"}

# Map slskd states to our DownloadStatus enum
SLSKD_STATUS_TO_SOULSPOT = {
    "Queued": DownloadStatus.QUEUED,
    "Requested": DownloadStatus.QUEUED,
    "Initializing": DownloadStatus.DOWNLOADING,
    "InProgress": DownloadStatus.DOWNLOADING,
    "Downloading": DownloadStatus.DOWNLOADING,
    "Completed": DownloadStatus.COMPLETED,
    "Succeeded": DownloadStatus.COMPLETED,
    "CompletedSucceeded": DownloadStatus.COMPLETED,
    "Errored": DownloadStatus.FAILED,
    "Failed": DownloadStatus.FAILED,
    "Cancelled": DownloadStatus.CANCELLED,
    "TimedOut": DownloadStatus.FAILED,
    "Rejected": DownloadStatus.FAILED,
    "CompletedFailed": DownloadStatus.FAILED,
}


class DownloadStatusWorker:
    """Unified slskd monitoring worker - Lidarr-inspired.

    Hey future me - THIS IS THE ONE slskd poller!
    Like Lidarr monitors its download client, we monitor slskd.

    Single Responsibility: slskd status → SoulSpot (JobQueue + DB)

    Features:
    - Polls slskd ONCE per cycle (instead of 2x with old workers)
    - Updates JobQueue with progress (for UI)
    - Updates DownloadModel in DB (for persistence)
    - Updates TrackModel.file_path on completion
    - Circuit breaker for resilience
    - Stale download detection and restart
    """

    # Circuit breaker states
    STATE_CLOSED = "closed"  # Normal operation
    STATE_OPEN = "open"  # slskd is down, skip sync
    STATE_HALF_OPEN = "half_open"  # Testing if slskd is back

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        slskd_client: "ISlskdClient",
        job_queue: JobQueue,
        poll_interval_seconds: int = 5,
        stale_timeout_hours: int = STALE_TIMEOUT_HOURS,
        max_consecutive_failures: int = 5,
        circuit_breaker_timeout: int = 60,
    ) -> None:
        """Initialize the unified download status worker.

        Args:
            session_factory: Factory for creating DB sessions
            slskd_client: Client for slskd API calls
            job_queue: Job queue for status updates
            poll_interval_seconds: How often to poll slskd (default 5s)
            stale_timeout_hours: Hours without progress before restart (default 12)
            max_consecutive_failures: Failures before circuit opens (default 5)
            circuit_breaker_timeout: Seconds before recovery attempt (default 60)

        Hey future me - poll_interval=5s is aggressive but needed for good UX.
        Users expect to see progress update quickly.
        """
        self._session_factory = session_factory
        self._slskd_client = slskd_client
        self._job_queue = job_queue
        self._poll_interval = poll_interval_seconds
        self._stale_timeout = timedelta(hours=stale_timeout_hours)
        self._max_consecutive_failures = max_consecutive_failures
        self._circuit_breaker_timeout = circuit_breaker_timeout

        # State
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._poll_count = 0

        # Lifecycle tracking
        self._cycles_completed = 0
        self._errors_total = 0
        self._start_time = time.time()

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_state = self.STATE_CLOSED
        self._last_failure_time: datetime | None = None
        self._last_successful_sync: datetime | None = None

        # Stats for monitoring
        self._stats: dict[str, int | str | None] = {
            "polls_completed": 0,
            "downloads_completed": 0,
            "downloads_failed": 0,
            "downloads_restarted": 0,
            "db_synced": 0,
            "last_poll_at": None,
            "last_error": None,
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the download status worker.

        Creates a background task that polls slskd periodically.
        Uses circuit breaker pattern for resilience.
        """
        if self._running:
            logger.warning("DownloadStatusWorker already running")
            return

        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._run_loop())

        logger.info(
            "worker.started",
            extra={
                "worker": "download_status",
                "poll_interval_seconds": self._poll_interval,
                "max_consecutive_failures": self._max_consecutive_failures,
            },
        )

    async def stop(self) -> None:
        """Stop the download status worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        uptime = time.time() - self._start_time
        logger.info(
            "worker.stopped",
            extra={
                "worker": "download_status",
                "cycles_completed": self._cycles_completed,
                "errors_total": self._errors_total,
                "uptime_seconds": round(uptime, 2),
                "downloads_completed": self._stats.get("downloads_completed", 0),
                "downloads_failed": self._stats.get("downloads_failed", 0),
            },
        )

    def get_status(self) -> dict[str, Any]:
        """Get current worker status for monitoring/UI."""
        return {
            "name": "Download Status (Unified)",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "poll_interval_seconds": self._poll_interval,
            "circuit_state": self._circuit_state,
            "stats": self._stats.copy(),
        }

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    async def _run_loop(self) -> None:
        """Main worker loop - polls slskd and updates JobQueue + DB.

        Hey future me - diese Loop ist das Herzstück!
        Auf jedem Durchlauf:
        1. Check circuit breaker state
        2. Poll slskd EINMAL
        3. Update JobQueue (für UI Progress)
        4. Update DB (für Persistenz)
        5. Handle completions (file_path update)
        6. Check for stale downloads (periodisch)
        """
        # Short delay on startup
        await asyncio.sleep(5)

        logger.info("DownloadStatusWorker loop started")

        while self._running:
            try:
                # Check circuit breaker state
                if self._circuit_state == self.STATE_OPEN:
                    if self._should_attempt_recovery():
                        self._circuit_state = self.STATE_HALF_OPEN
                        logger.info("Circuit breaker half-open, testing slskd")
                    else:
                        await asyncio.sleep(self._poll_interval)
                        continue

                # Run poll cycle
                success = await self._poll_cycle()

                if success:
                    self._handle_sync_success()
                else:
                    self._handle_sync_failure(Exception("Poll cycle failed"))

                self._poll_count += 1
                self._cycles_completed += 1
                self._stats["polls_completed"] = self._cycles_completed
                self._stats["last_poll_at"] = datetime.now(UTC).isoformat()

                # Log health every 10 cycles
                if self._cycles_completed % 10 == 0:
                    log_worker_health(
                        logger=logger,
                        worker_name="download_status",
                        cycles_completed=self._cycles_completed,
                        errors_total=self._errors_total,
                        uptime_seconds=time.time() - self._start_time,
                        extra_stats={
                            "downloads_completed": self._stats.get("downloads_completed", 0),
                            "db_synced": self._stats.get("db_synced", 0),
                        },
                    )

                # Check for stale downloads periodically
                if self._poll_count % STALE_CHECK_INTERVAL_POLLS == 0:
                    await self._check_stale_downloads()

            except Exception as e:
                self._errors_total += 1
                self._handle_sync_failure(e)
                
                # Hey future me - Connection errors are already logged in _poll_cycle()!
                # Only log non-connection errors here to avoid spam.
                # Connection errors: ConnectError, ConnectionError, OSError, TimeoutError
                is_connection_error = any(
                    err in type(e).__name__
                    for err in ["ConnectError", "ConnectionError", "OSError", "TimeoutError"]
                )
                
                if not is_connection_error:
                    # Non-connection errors (DB issues, unexpected exceptions) - log with trace
                    logger.error(
                        "download_status.loop_error",
                        exc_info=True,
                        extra={"error_type": type(e).__name__, "cycle": self._cycles_completed},
                    )
                # Connection errors: already logged appropriately in _poll_cycle()
                # Circuit breaker handles the retry logic
                
                self._stats["last_error"] = str(e)

            # Dynamic sleep with backoff
            sleep_time = self._calculate_backoff_interval()
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

        logger.info("DownloadStatusWorker loop exited")

    async def _poll_cycle(self) -> bool:
        """Run one poll cycle - fetch slskd status and update JobQueue + DB.

        Returns:
            True if successful, False on error.

        Hey future me - THIS IS THE KEY CHANGE!
        We poll slskd ONCE and update BOTH systems.
        Old workers polled twice (10s + 5s intervals).
        """
        try:
            # 1. Poll slskd EINMAL
            all_downloads = await self._fetch_slskd_downloads()

            if not all_downloads:
                # No downloads but connection succeeded
                return True

            # Create lookup maps
            download_map = self._build_download_map(all_downloads)

            # 2. Update JobQueue (from DownloadMonitorWorker)
            await self._update_job_queue(download_map)

            # 3. Update DB (from DownloadStatusSyncWorker)
            async with self._session_factory() as session:
                await self._update_db_downloads(session, all_downloads)
                await session.commit()

            return True

        except Exception as e:
            # Hey future me - Smart error logging to avoid log spam!
            # Connection errors are EXPECTED when slskd is not running.
            # We only log:
            # - First connection error (warning)
            # - Every 10th consecutive failure (info) to show it's still trying
            # - Non-connection errors (error with trace)
            is_connection_error = any(
                err in type(e).__name__
                for err in ["ConnectError", "ConnectionError", "OSError", "TimeoutError"]
            )

            if is_connection_error:
                if self._consecutive_failures == 0:
                    # First failure - log warning
                    logger.warning(
                        "⚠️ slskd not available (expected if not configured). "
                        "Configure SLSKD_URL and SLSKD_API_KEY in settings. "
                        "Circuit breaker will handle retries silently."
                    )
                elif self._consecutive_failures % 10 == 0:
                    # Every 10th failure - brief status
                    logger.info(
                        f"slskd still unavailable (attempt {self._consecutive_failures + 1}), "
                        f"circuit: {self._circuit_state}"
                    )
                # Otherwise: silent - circuit breaker handles it
            else:
                # Non-connection error - always log with details
                logger.error(
                    f"slskd poll error (attempt {self._consecutive_failures + 1}): {e}",
                    exc_info=True
                )

            raise

    # =========================================================================
    # SLSKD DATA FETCHING
    # =========================================================================

    async def _fetch_slskd_downloads(self) -> list[dict[str, Any]]:
        """Fetch all downloads from slskd.

        Returns:
            List of download dicts with username attached.
        """
        response = await self._slskd_client.list_downloads()

        all_downloads = []
        if isinstance(response, dict):
            for username, user_data in response.items():
                if isinstance(user_data, dict):
                    directories = user_data.get("directories", [])
                    for directory in directories:
                        files = directory.get("files", [])
                        for file in files:
                            file["username"] = username
                            all_downloads.append(file)

        return all_downloads

    def _build_download_map(self, downloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build lookup map: download_id -> download data."""
        return {d.get("id", ""): d for d in downloads if d.get("id")}

    # =========================================================================
    # JOBQUEUE UPDATES (from DownloadMonitorWorker)
    # =========================================================================

    async def _update_job_queue(self, download_map: dict[str, dict[str, Any]]) -> None:
        """Update JobQueue with slskd progress."""
        running_jobs = await self._job_queue.list_jobs(
            status=JobStatus.RUNNING,
            job_type=JobType.DOWNLOAD,
        )

        if not running_jobs:
            return

        for job in running_jobs:
            try:
                await self._update_job_status(job, download_map)
            except Exception as e:
                logger.error(f"Error updating job {job.id}: {e}")

    async def _update_job_status(
        self, job: Any, download_map: dict[str, dict[str, Any]]
    ) -> None:
        """Update a single job's status based on slskd data."""
        if not job.result:
            return

        slskd_download_id = job.result.get("slskd_download_id")
        if not slskd_download_id:
            return

        slskd_status = download_map.get(slskd_download_id)

        if slskd_status is None:
            # Download not found - check existing state
            existing_state = job.result.get("slskd_state")
            if existing_state in SLSKD_COMPLETED_STATES:
                await self._mark_job_completed(job)
            elif existing_state in SLSKD_FAILED_STATES:
                await self._mark_job_failed(job, f"Download failed: {existing_state}")
            return

        # Update job result with progress
        state = slskd_status.get("state", "unknown")
        progress = slskd_status.get("progress", 0)
        bytes_transferred = slskd_status.get("bytes_transferred", 0)
        total_size = slskd_status.get("size", 0)

        job.result.update({
            "slskd_state": state,
            "progress_percent": progress,
            "bytes_downloaded": bytes_transferred,
            "total_bytes": total_size,
            "last_updated": datetime.now(UTC).isoformat(),
        })

        # Check if finished
        if state in SLSKD_COMPLETED_STATES:
            await self._mark_job_completed(job)
        elif state in SLSKD_FAILED_STATES:
            await self._mark_job_failed(job, f"Download failed: {state}")

    async def _mark_job_completed(self, job: Any) -> None:
        """Mark a job as successfully completed."""
        job.status = JobStatus.COMPLETED
        job.result["completed_at"] = datetime.now(UTC).isoformat()
        completed = self._stats.get("downloads_completed") or 0
        self._stats["downloads_completed"] = int(completed) + 1
        logger.info(f"Download job {job.id} completed successfully")

    async def _mark_job_failed(self, job: Any, error_message: str) -> None:
        """Mark a job as failed."""
        job.status = JobStatus.FAILED
        job.result["error"] = error_message
        job.result["failed_at"] = datetime.now(UTC).isoformat()
        failed = self._stats.get("downloads_failed") or 0
        self._stats["downloads_failed"] = int(failed) + 1
        logger.warning(f"Download job {job.id} failed: {error_message}")

    # =========================================================================
    # DATABASE UPDATES (from DownloadStatusSyncWorker)
    # =========================================================================

    async def _update_db_downloads(
        self, session: AsyncSession, slskd_downloads: list[dict[str, Any]]
    ) -> None:
        """Update DownloadModel entries from slskd data."""
        synced = 0

        for slskd_dl in slskd_downloads:
            result = await self._sync_single_download(session, slskd_dl)
            if result in ("updated", "completed"):
                synced += 1

        self._stats["db_synced"] = synced

    async def _sync_single_download(
        self, session: AsyncSession, slskd_dl: dict[str, Any]
    ) -> str:
        """Sync a single slskd download to DB.

        Returns:
            Result type: "updated", "completed", "failed", "not_found"
        """
        username = slskd_dl.get("username", "")
        filename = slskd_dl.get("filename", "")
        state = slskd_dl.get("state", "Unknown")

        if not username or not filename:
            return "not_found"

        # Find matching Download by source_url
        source_url_pattern = f"slskd://{username}/{filename}"
        stmt = select(DownloadModel).where(
            DownloadModel.source_url == source_url_pattern
        )
        result = await session.execute(stmt)
        download = result.scalar_one_or_none()

        # Try alternative matching
        if not download:
            stmt_alt = select(DownloadModel).where(
                DownloadModel.source_url.contains(filename)
            )
            result_alt = await session.execute(stmt_alt)
            download = result_alt.scalar_one_or_none()

        if not download:
            return "not_found"

        # Map state
        new_status = SLSKD_STATUS_TO_SOULSPOT.get(state)
        if not new_status:
            return "not_found"

        # Update status
        old_status = DownloadStatus(download.status)
        download.status = new_status.value
        download.updated_at = datetime.now(UTC)

        # Update progress
        percent = slskd_dl.get("percentComplete", 0.0)
        if isinstance(percent, (int, float)):
            download.progress_percent = float(percent)

        # Handle completion
        if new_status == DownloadStatus.COMPLETED:
            await self._handle_completion(session, download, slskd_dl)
            return "completed"

        if new_status == DownloadStatus.FAILED:
            download.error_message = slskd_dl.get("error", "Download failed")
            return "failed"

        return "updated" if old_status != new_status else "not_found"

    async def _handle_completion(
        self,
        session: AsyncSession,
        download: DownloadModel,
        slskd_dl: dict[str, Any],
    ) -> None:
        """Handle download completion - update Track.file_path.

        Hey future me - THIS IS LIDARR-STYLE COMPLETED DOWNLOAD HANDLING!
        Like Lidarr's post-processing, we update the track with the file path.
        """
        download.progress_percent = 100.0
        download.completed_at = datetime.now(UTC)

        local_path = slskd_dl.get("localPath") or slskd_dl.get("filename")

        if local_path and download.track_id:
            stmt = (
                update(TrackModel)
                .where(TrackModel.id == download.track_id)
                .values(file_path=local_path, updated_at=datetime.now(UTC))
            )
            await session.execute(stmt)
            logger.info(f"Download completed: track_id={download.track_id}, file={local_path}")

    # =========================================================================
    # STALE DOWNLOAD HANDLING (from DownloadMonitorWorker)
    # =========================================================================

    async def _check_stale_downloads(self) -> None:
        """Check for stale downloads and restart them."""
        try:
            jobs = await self._job_queue.list_jobs(
                status=JobStatus.RUNNING, job_type=JobType.DOWNLOAD
            )
        except Exception as e:
            logger.error(f"Failed to list jobs for stale check: {e}")
            return

        now = datetime.now(UTC)

        for job in jobs:
            try:
                ref_time = self._get_job_reference_time(job)
                if not ref_time:
                    continue

                age = now - ref_time
                if age > self._stale_timeout:
                    logger.warning(
                        f"Stale download: Job {job.id} - "
                        f"last activity {age.total_seconds() / 3600:.1f}h ago"
                    )
                    await self._restart_stale_download(job)

            except Exception as e:
                logger.error(f"Error checking job {job.id} for staleness: {e}")

    def _get_job_reference_time(self, job: Any) -> datetime | None:
        """Get reference timestamp for staleness check."""
        if not job.result:
            return None

        for field in ["last_updated", "started_at"]:
            ts_str = job.result.get(field)
            if ts_str:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                return ts

        if hasattr(job, "created_at") and job.created_at:
            ts = job.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            return ts

        return None

    async def _restart_stale_download(self, job: Any) -> None:
        """Restart a stale download by cancelling and re-queueing."""
        try:
            # Cancel at slskd
            slskd_id = job.result.get("slskd_download_id")
            if slskd_id:
                with contextlib.suppress(Exception):
                    await self._slskd_client.cancel_download(slskd_id)

            # Mark old job failed
            await self._mark_job_failed(
                job,
                f"Timed out after {self._stale_timeout.total_seconds() / 3600:.0f}h - restarting",
            )

            # Create new job
            payload = {
                "track_id": job.result.get("track_id"),
                "spotify_id": job.result.get("spotify_id"),
                "title": job.result.get("title"),
                "artist": job.result.get("artist"),
                "album": job.result.get("album"),
                "retry_of": str(job.id),
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            if payload.get("track_id") or payload.get("spotify_id"):
                new_job = await self._job_queue.create_job(
                    job_type=JobType.DOWNLOAD,
                    payload=payload,
                    priority=getattr(job, "priority", 0),
                )
                logger.info(f"Created retry job {new_job.id} for stale download")
                restarted = self._stats.get("downloads_restarted") or 0
                self._stats["downloads_restarted"] = int(restarted) + 1

        except Exception as e:
            logger.error(f"Failed to restart stale download {job.id}: {e}")

    # =========================================================================
    # CIRCUIT BREAKER (from DownloadStatusSyncWorker)
    # =========================================================================

    def _handle_sync_success(self) -> None:
        """Handle successful sync - reset circuit breaker."""
        if self._circuit_state == self.STATE_HALF_OPEN:
            logger.info("Circuit breaker: Recovery confirmed, closing")

        self._consecutive_failures = 0
        self._circuit_state = self.STATE_CLOSED
        self._last_failure_time = None
        self._last_successful_sync = datetime.now(UTC)
        self._stats["last_error"] = None

    def _handle_sync_failure(self, error: Exception) -> None:
        """Handle failed sync - update circuit breaker state."""
        self._consecutive_failures += 1
        self._errors_total += 1
        self._last_failure_time = datetime.now(UTC)

        if self._circuit_state == self.STATE_HALF_OPEN:
            logger.warning(f"Circuit breaker: Recovery failed, reopening ({error})")
            self._circuit_state = self.STATE_OPEN
        elif (
            self._circuit_state == self.STATE_CLOSED
            and self._consecutive_failures >= self._max_consecutive_failures
        ):
            logger.error(
                f"Circuit breaker: Opening after {self._consecutive_failures} failures"
            )
            self._circuit_state = self.STATE_OPEN

    def _should_attempt_recovery(self) -> bool:
        """Check if circuit should attempt recovery."""
        if self._circuit_state != self.STATE_OPEN:
            return False

        if self._last_failure_time is None:
            return True

        try:
            elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        except (ValueError, OverflowError):
            return True

        return elapsed >= self._circuit_breaker_timeout

    def _calculate_backoff_interval(self) -> float:
        """Calculate sleep interval with exponential backoff."""
        if self._consecutive_failures == 0:
            return float(self._poll_interval)

        backoff = self._poll_interval * (2 ** self._consecutive_failures)
        return min(float(backoff), float(self._circuit_breaker_timeout))

    def get_health_status(self) -> dict[str, Any]:
        """Get circuit breaker health status for monitoring."""
        now = datetime.now(UTC)
        has_connection = self._last_successful_sync is not None
        is_healthy = self._circuit_state == self.STATE_CLOSED and has_connection

        status = {
            "circuit_state": self._circuit_state,
            "is_healthy": is_healthy,
            "consecutive_failures": self._consecutive_failures,
            "total_errors": self._errors_total,
            "has_successful_connection": has_connection,
        }

        if self._last_successful_sync:
            status["last_successful_sync"] = self._last_successful_sync.isoformat()
            status["seconds_since_last_sync"] = int(
                (now - self._last_successful_sync).total_seconds()
            )

        if self._last_failure_time:
            status["last_failure_time"] = self._last_failure_time.isoformat()
            if self._circuit_state == self.STATE_OPEN:
                elapsed = (now - self._last_failure_time).total_seconds()
                remaining = max(0, self._circuit_breaker_timeout - elapsed)
                status["seconds_until_recovery_attempt"] = int(remaining)

        return status


# Factory function
def create_download_status_worker(
    session_factory: async_sessionmaker[AsyncSession],
    slskd_client: "ISlskdClient",
    job_queue: JobQueue,
    poll_interval: int = 5,
) -> DownloadStatusWorker:
    """Create a DownloadStatusWorker with default settings.

    Args:
        session_factory: Factory for creating DB sessions
        slskd_client: Client for slskd API
        job_queue: Job queue for status updates
        poll_interval: Seconds between polls (default 5)

    Returns:
        Configured DownloadStatusWorker instance
    """
    return DownloadStatusWorker(
        session_factory=session_factory,
        slskd_client=slskd_client,
        job_queue=job_queue,
        poll_interval_seconds=poll_interval,
    )
