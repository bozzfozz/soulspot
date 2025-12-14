"""Download Status Sync Worker - synchronizes download status between slskd and SoulSpot DB.

Hey future me - this worker FIXES the "stuck status" bug! The SearchAndDownloadUseCase creates
downloads with QUEUED status, but never updates them to DOWNLOADING/COMPLETED. This worker:

1. Polls slskd for all active/completed downloads
2. Matches them to SoulSpot Download entries via source_url or external_id
3. Updates SoulSpot DB status to reflect reality
4. Handles completion: updates file_path on track when download finishes

WHY is this separate from QueueDispatcherWorker?
- QueueDispatcher: WAITING → PENDING → enqueue job (OUTBOUND flow)
- StatusSyncWorker: QUEUED → DOWNLOADING → COMPLETED (INBOUND flow from slskd)

Without this worker:
- User queues download → status=QUEUED → slskd downloads it → status stays QUEUED forever
- Download Manager shows wrong info
- "Completed today" count is always 0
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soulspot.domain.entities import DownloadStatus
from soulspot.domain.ports import ISlskdClient
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel

logger = logging.getLogger(__name__)


# Hey future me - slskd uses different status names than us. This maps them to our enum.
# "InProgress" is their DOWNLOADING, "Completed" or "Succeeded" is our COMPLETED.
# Keep this in sync with slskd_provider.py SLSKD_STATUS_MAP!
SLSKD_STATUS_TO_SOULSPOT = {
    "Queued": DownloadStatus.QUEUED,
    "Requested": DownloadStatus.QUEUED,
    "InProgress": DownloadStatus.DOWNLOADING,
    "Downloading": DownloadStatus.DOWNLOADING,  # alias
    "Completed": DownloadStatus.COMPLETED,
    "Succeeded": DownloadStatus.COMPLETED,  # alias
    "Errored": DownloadStatus.FAILED,
    "Failed": DownloadStatus.FAILED,
    "Cancelled": DownloadStatus.CANCELLED,
    "TimedOut": DownloadStatus.FAILED,
    "Rejected": DownloadStatus.FAILED,
}


class DownloadStatusSyncWorker:
    """Worker that synchronizes download status from slskd to SoulSpot DB.

    This worker:
    1. Periodically polls slskd for all downloads
    2. Matches slskd downloads to SoulSpot Download entries
    3. Updates status, progress, and timestamps
    4. Handles completion: links downloaded file to track

    Error Recovery Features:
    - Exponential backoff on repeated failures
    - Circuit breaker pattern when slskd is offline
    - Graceful degradation (continues running, waits for recovery)
    - Health status reporting for monitoring
    """

    # Circuit breaker states
    STATE_CLOSED = "closed"  # Normal operation
    STATE_OPEN = "open"  # slskd is down, skip sync
    STATE_HALF_OPEN = "half_open"  # Testing if slskd is back

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        slskd_client: ISlskdClient,
        sync_interval: int = 5,
        completed_history_hours: int = 24,
        max_consecutive_failures: int = 5,
        circuit_breaker_timeout: int = 60,
    ) -> None:
        """Initialize the sync worker.

        Args:
            session_factory: Factory for creating DB sessions
            slskd_client: Client for querying slskd
            sync_interval: Seconds between sync cycles
            completed_history_hours: How far back to check completed downloads
            max_consecutive_failures: Failures before circuit breaker opens
            circuit_breaker_timeout: Seconds to wait before testing recovery

        Hey future me - sync_interval=5s is aggressive but needed for good UX.
        Users expect to see progress update quickly. If this causes performance
        issues, increase to 10-15s but never more than 30s.
        """
        self._session_factory = session_factory
        self._slskd_client = slskd_client
        self._sync_interval = sync_interval
        self._completed_history_hours = completed_history_hours
        self._running = False
        self._last_sync_stats: dict[str, int] = {}

        # Error recovery state
        self._consecutive_failures = 0
        self._max_consecutive_failures = max_consecutive_failures
        self._circuit_breaker_timeout = circuit_breaker_timeout
        self._circuit_state = self.STATE_CLOSED
        self._last_failure_time: datetime | None = None
        self._total_errors = 0
        self._last_successful_sync: datetime | None = None

    async def start(self) -> None:
        """Start the sync worker.

        Runs continuously until stop() is called.
        Uses circuit breaker pattern for resilience when slskd goes offline.
        """
        self._running = True
        logger.info(
            "DownloadStatusSyncWorker started (sync_interval=%ds, max_failures=%d)",
            self._sync_interval,
            self._max_consecutive_failures,
        )

        while self._running:
            try:
                # Check circuit breaker state
                if self._circuit_state == self.STATE_OPEN:
                    # Check if timeout has passed to try recovery
                    if await self._should_attempt_recovery():
                        self._circuit_state = self.STATE_HALF_OPEN
                        logger.info("Circuit breaker half-open, testing slskd connection")
                    else:
                        # Still in cooldown, skip this cycle
                        await asyncio.sleep(self._sync_interval)
                        continue

                # Run sync cycle
                success = await self._sync_cycle()

                if success:
                    self._on_sync_success()
                else:
                    await self._on_sync_failure("Sync cycle returned failure")

            except Exception as e:
                await self._on_sync_failure(str(e))
                logger.exception("DownloadStatusSyncWorker error: %s", e)

            # Calculate dynamic sleep interval based on failures
            sleep_time = self._calculate_backoff_interval()
            await asyncio.sleep(sleep_time)

        logger.info("DownloadStatusSyncWorker stopped")

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    async def _sync_cycle(self) -> bool:
        """Run one sync cycle.

        Returns:
            True if sync was successful, False if there were errors.

        Hey future me – this is the core sync logic. It gets downloads from
        slskd and updates our DB to match. The critical part for error
        recovery: we return True/False so start() knows whether to call
        _handle_sync_success() or _handle_sync_failure(). An empty response
        from slskd is still considered "success" - the connection worked.

        Steps:
        1. Get all downloads from slskd
        2. Update matching SoulSpot downloads
        3. Log summary
        4. Return True on success, False on failure
        """
        stats = {"updated": 0, "completed": 0, "failed": 0, "not_found": 0}

        try:
            # Get all downloads from slskd
            # This can raise if slskd is unreachable
            slskd_downloads = await self._get_slskd_downloads()

            # Even if empty, the connection succeeded
            if not slskd_downloads:
                self._last_sync_stats = stats
                return True

            async with self._session_factory() as session:
                for slskd_dl in slskd_downloads:
                    result = await self._sync_single_download(session, slskd_dl)
                    stats[result] += 1

                await session.commit()

        except Exception as e:
            logger.error("Sync cycle failed: %s", e, exc_info=True)
            self._last_sync_stats = stats
            raise  # Re-raise so start() can handle circuit breaker

        # Log if anything changed
        if stats["updated"] > 0 or stats["completed"] > 0:
            logger.debug(
                "Sync cycle: updated=%d, completed=%d, failed=%d, not_found=%d",
                stats["updated"],
                stats["completed"],
                stats["failed"],
                stats["not_found"],
            )

        self._last_sync_stats = stats
        return True

    async def _get_slskd_downloads(self) -> list[dict[str, Any]]:
        """Get all downloads from slskd.

        Returns list of download dicts with structure:
        {
            "username": str,
            "filename": str,
            "state": str (Queued|InProgress|Completed|...),
            "bytesTransferred": int,
            "size": int,
            "averageSpeed": float,
            "percentComplete": float,
            ...
        }

        Hey future me – this is where network errors happen when slskd is down.
        We now RE-RAISE exceptions instead of swallowing them, so the circuit
        breaker in start() can detect failures. The old code returned [] on
        error which made it impossible to distinguish "no downloads" from
        "slskd is offline".
        """
        # Get active downloads - let exceptions propagate for circuit breaker
        response = await self._slskd_client.list_downloads()

        # slskd returns downloads grouped by user
        # Format: {username: {directories: [...downloads...]}}
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

    async def _sync_single_download(
        self, session: AsyncSession, slskd_dl: dict[str, Any]
    ) -> str:
        """Sync a single slskd download to SoulSpot DB.

        Args:
            session: DB session
            slskd_dl: slskd download dict

        Returns:
            Result type: "updated", "completed", "failed", "not_found"
        """
        username = slskd_dl.get("username", "")
        filename = slskd_dl.get("filename", "")
        state = slskd_dl.get("state", "Unknown")

        if not username or not filename:
            return "not_found"

        # Build the source_url pattern to match
        # SearchAndDownloadUseCase sets: source_url=f"slskd://{username}/{filename}"
        source_url_pattern = f"slskd://{username}/{filename}"

        # Find matching Download in SoulSpot DB
        stmt = select(DownloadModel).where(
            DownloadModel.source_url == source_url_pattern
        )
        result = await session.execute(stmt)
        download = result.scalar_one_or_none()

        if not download:
            # Try alternative matching: filename contains pattern
            # (for cases where source_url format differs)
            stmt_alt = select(DownloadModel).where(
                DownloadModel.source_url.contains(filename)
            )
            result_alt = await session.execute(stmt_alt)
            download = result_alt.scalar_one_or_none()

        if not download:
            return "not_found"

        # Map slskd state to SoulSpot status
        new_status = SLSKD_STATUS_TO_SOULSPOT.get(state)
        if not new_status:
            logger.warning("Unknown slskd state: %s", state)
            return "not_found"

        # Check if status actually changed
        old_status = DownloadStatus(download.status)
        if old_status == new_status:
            # Still update progress even if status same
            await self._update_progress(download, slskd_dl)
            return "updated"

        # Update status
        download.status = new_status.value
        download.updated_at = datetime.now(UTC)

        # Update progress metrics
        await self._update_progress(download, slskd_dl)

        # Handle completion
        if new_status == DownloadStatus.COMPLETED:
            await self._handle_completion(session, download, slskd_dl)
            return "completed"

        if new_status == DownloadStatus.FAILED:
            download.error_message = slskd_dl.get("error", "Download failed")
            return "failed"

        return "updated"

    async def _update_progress(
        self, download: DownloadModel, slskd_dl: dict[str, Any]
    ) -> None:
        """Update progress metrics on download.

        Args:
            download: SoulSpot download model
            slskd_dl: slskd download dict

        Note: DownloadModel only has progress_percent field.
        Bytes and speed are not persisted (only shown in real-time via provider polling).
        """
        # Progress percent
        percent = slskd_dl.get("percentComplete", 0.0)
        if isinstance(percent, (int, float)):
            download.progress_percent = float(percent)

    async def _handle_completion(
        self,
        session: AsyncSession,
        download: DownloadModel,
        slskd_dl: dict[str, Any],
    ) -> None:
        """Handle download completion: update track with file path.

        Args:
            session: DB session
            download: SoulSpot download model
            slskd_dl: slskd download dict
        """
        download.progress_percent = 100.0
        download.completed_at = datetime.now(UTC)

        # Get the local file path from slskd
        # slskd stores completed files in its download directory
        local_path = slskd_dl.get("localPath") or slskd_dl.get("filename")

        if local_path and download.track_id:
            # Update track with file path
            stmt = (
                update(TrackModel)
                .where(TrackModel.id == download.track_id)
                .values(
                    file_path=local_path,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            logger.info(
                "Download completed: track_id=%s, file=%s",
                download.track_id,
                local_path,
            )

    async def get_sync_stats(self) -> dict[str, int]:
        """Get stats from last sync cycle.

        Returns:
            Dict with counts of updated/completed/failed/not_found
        """
        return self._last_sync_stats.copy()

    # =========================================================================
    # Circuit Breaker Methods
    # =========================================================================

    def _handle_sync_success(self) -> None:
        """Handle successful sync cycle - reset failure counters.

        Called after a successful sync cycle to reset the circuit breaker
        state and track the last successful sync time.

        Hey future me – this is the happy path. If we got here, slskd is
        responding and we should reset all the failure tracking. The tricky
        part is transitioning from HALF_OPEN back to CLOSED - we do a single
        test request in half-open, and if it succeeds, we fully reset.
        """
        if self._circuit_state == self.STATE_HALF_OPEN:
            logger.info(
                "Circuit breaker: Recovery confirmed, transitioning to CLOSED"
            )

        self._consecutive_failures = 0
        self._circuit_state = self.STATE_CLOSED
        self._last_failure_time = None
        self._last_successful_sync = datetime.now(UTC)

    def _handle_sync_failure(self, error: Exception) -> None:
        """Handle failed sync cycle - track failures and potentially open circuit.

        Args:
            error: The exception that caused the failure

        Hey future me – this tracks consecutive failures and opens the circuit
        breaker if we hit the threshold. The key insight: we only care about
        CONSECUTIVE failures. One success resets everything. This prevents
        flapping when slskd has intermittent issues vs being truly down.
        """
        self._consecutive_failures += 1
        self._total_errors += 1
        self._last_failure_time = datetime.now(UTC)

        if self._circuit_state == self.STATE_HALF_OPEN:
            # Failed during recovery test - go back to OPEN
            logger.warning(
                "Circuit breaker: Recovery test failed (%s), reopening circuit",
                type(error).__name__,
            )
            self._circuit_state = self.STATE_OPEN

        elif (
            self._circuit_state == self.STATE_CLOSED
            and self._consecutive_failures >= self._max_consecutive_failures
        ):
            # Threshold reached - open the circuit
            logger.error(
                "Circuit breaker: Opening after %d consecutive failures. "
                "Last error: %s. Will retry after %ds",
                self._consecutive_failures,
                str(error)[:100],
                self._circuit_breaker_timeout,
            )
            self._circuit_state = self.STATE_OPEN

    def _check_circuit_recovery(self) -> bool:
        """Check if circuit breaker should transition to HALF_OPEN for recovery test.

        Returns:
            True if circuit is ready for recovery test, False otherwise

        Hey future me – this is called when circuit is OPEN to check if we've
        waited long enough to try again. The timeout (default 60s) gives slskd
        time to recover. After timeout, we go HALF_OPEN and test with one sync.
        Don't confuse this with the exponential backoff in start() - that's
        for CLOSED state failures. This is for OPEN state recovery.
        """
        if self._circuit_state != self.STATE_OPEN:
            return False

        if self._last_failure_time is None:
            # Shouldn't happen, but handle gracefully
            return True

        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()

        if elapsed >= self._circuit_breaker_timeout:
            logger.info(
                "Circuit breaker: Timeout elapsed (%.1fs), transitioning to HALF_OPEN",
                elapsed,
            )
            self._circuit_state = self.STATE_HALF_OPEN
            return True

        return False

    def get_health_status(self) -> dict[str, Any]:
        """Get circuit breaker health status for monitoring.

        Returns:
            Dict with health metrics for display in UI/monitoring

        Hey future me – this is what the Download Manager UI calls to show
        the slskd connection status in the provider health widget. The
        circuit_state tells you if we're healthy (CLOSED), in trouble (OPEN),
        or testing recovery (HALF_OPEN).
        """
        now = datetime.now(UTC)
        status = {
            "circuit_state": self._circuit_state,
            "is_healthy": self._circuit_state == self.STATE_CLOSED,
            "consecutive_failures": self._consecutive_failures,
            "total_errors": self._total_errors,
            "max_failures_threshold": self._max_consecutive_failures,
            "recovery_timeout_seconds": self._circuit_breaker_timeout,
        }

        # Add timing info
        if self._last_successful_sync:
            seconds_since_sync = (now - self._last_successful_sync).total_seconds()
            status["last_successful_sync"] = self._last_successful_sync.isoformat()
            status["seconds_since_last_sync"] = int(seconds_since_sync)
        else:
            status["last_successful_sync"] = None
            status["seconds_since_last_sync"] = None

        if self._last_failure_time:
            status["last_failure_time"] = self._last_failure_time.isoformat()

            # If circuit is open, show time until recovery attempt
            if self._circuit_state == self.STATE_OPEN:
                elapsed = (now - self._last_failure_time).total_seconds()
                remaining = max(0, self._circuit_breaker_timeout - elapsed)
                status["seconds_until_recovery_attempt"] = int(remaining)
        else:
            status["last_failure_time"] = None

        return status
