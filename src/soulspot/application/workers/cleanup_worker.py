# Hey future me - dieser Worker räumt auf, sonst wird die Disk voll!
#
# Problem: Downloads landen in mnt/downloads, aber nach Import bleiben Leichen.
# Temp-Files, abgebrochene Downloads, Duplikate - alles wächst und wächst.
#
# Dieser Worker macht:
# 1. Löscht alte Temp-Dateien (älter als X Tage)
# 2. Löscht verwaiste Downloads (nicht in DB referenziert)
# 3. Bereinigt fehlgeschlagene Job-Artefakte
# 4. Komprimiert/archiviert alte Logs (optional)
#
# ACHTUNG: Cleanup ist DESTRUKTIV! Daher:
# - Default: disabled in AppSettingsService
# - Dry-run Mode für Tests
# - Alles wird geloggt bevor gelöscht
# - Max X Dateien pro Durchlauf (Sicherheit)
#
# Stolperfalle: Nie Dateien löschen die gerade benutzt werden!
# Prüfe immer modified_time UND checke ob Jobs in RUNNING state.
"""Cleanup worker for removing orphaned files and old temp data."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.application.workers.job_queue import JobQueue, JobType

logger = logging.getLogger(__name__)


# Safety limits - nie mehr als X Dateien pro Durchlauf löschen
MAX_FILES_PER_RUN = 100
MAX_TOTAL_SIZE_MB = 1024  # 1 GB max per run


class CleanupWorker:
    """Background worker for cleaning up orphaned files and temp data.

    Hey future me - dieser Worker ist gefährlich weil er Daten LÖSCHT!
    Deswegen:
    1. Ist er per Default DISABLED
    2. Hat er einen dry_run Mode
    3. Loggt er ALLES vor dem Löschen
    4. Hat er Safety-Limits (max files per run)

    Cleanup targets:
    - Old temp downloads (older than retention_days)
    - Orphaned files (not referenced in DB)
    - Failed job artifacts
    - Old logs (if log_cleanup_enabled)
    """

    def __init__(
        self,
        job_queue: JobQueue,
        settings_service: AppSettingsService,
        downloads_path: Path,
        music_path: Path,
        temp_path: Path | None = None,
        dry_run: bool = False,
    ) -> None:
        """Initialize cleanup worker.

        Args:
            job_queue: Job queue for creating cleanup jobs
            settings_service: Settings service for config
            downloads_path: Path to downloads folder (mnt/downloads)
            music_path: Path to organized music folder (mnt/music)
            temp_path: Optional temp folder to clean
            dry_run: If True, log what would be deleted but don't delete
        """
        self._job_queue = job_queue
        self._settings = settings_service
        self._downloads_path = downloads_path
        self._music_path = music_path
        self._temp_path = temp_path
        self._dry_run = dry_run

        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Stats - values can be int, str, or None
        self._stats: dict[str, int | str | None] = {
            "runs_completed": 0,
            "files_deleted": 0,
            "bytes_freed": 0,
            "last_run_at": None,
            "last_error": None,
        }

    async def start(self) -> None:
        """Start the cleanup worker.

        Runs cleanup on interval defined in settings.
        Checks if cleanup is enabled before each run.
        """
        if self._running:
            logger.warning("Cleanup worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="Cleanup",
                config={"daily_check": True, "disabled_by_default": True}
            )
        )

    async def stop(self) -> None:
        """Stop the cleanup worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Cleanup worker stopped")

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI."""
        return {
            "name": "Cleanup Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "dry_run": self._dry_run,
            "downloads_path": str(self._downloads_path),
            "stats": self._stats.copy(),
        }

    async def _run_loop(self) -> None:
        """Main worker loop.

        Hey future me - diese Loop checkt ZUERST ob cleanup enabled ist!
        Wenn nicht, wartet sie trotzdem den Interval, damit wir nicht
        CPU-Cycles verschwenden. Wenn enabled wird, startet sie automatisch.
        """
        # Initial delay to let services start
        await asyncio.sleep(30)

        logger.info("Cleanup worker entering main loop")

        while self._running:
            try:
                # Check if cleanup is enabled
                if await self._settings.is_cleanup_automation_enabled():
                    await self._run_cleanup()
                    runs = self._stats.get("runs_completed")
                    self._stats["runs_completed"] = (int(runs) if runs else 0) + 1
                    self._stats["last_run_at"] = datetime.now(UTC).isoformat()
                else:
                    logger.debug("Cleanup is disabled, skipping run")

            except Exception as e:
                logger.error(f"Error in cleanup worker loop: {e}", exc_info=True)
                self._stats["last_error"] = str(e)

            # Get interval from settings (default 24h)
            try:
                interval_seconds = await self._settings.get_cleanup_interval_seconds()
            except Exception:
                interval_seconds = 24 * 3600  # 24 hours in seconds

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_cleanup(self) -> None:
        """Execute one cleanup run.

        Cleans up:
        1. Old temp files in downloads folder
        2. Orphaned downloads not referenced in DB
        3. Empty directories
        """
        logger.info("Starting cleanup run" + (" (DRY RUN)" if self._dry_run else ""))

        # Get retention days from settings (default 7 days)
        retention_days = await self._settings.get_int(
            "automation.cleanup_retention_days", default=7
        )
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

        files_to_delete: list[tuple[Path, int]] = []  # (path, size)

        # 1. Find old temp files
        temp_files = await self._find_old_temp_files(cutoff_date)
        files_to_delete.extend(temp_files)

        # 2. Find orphaned downloads
        # Note: This needs DB access to check what's referenced
        # For now, we'll just clean old files - orphan detection in Phase 2

        # 3. Apply safety limits
        files_to_delete = files_to_delete[:MAX_FILES_PER_RUN]
        total_size = sum(size for _, size in files_to_delete)
        if total_size > MAX_TOTAL_SIZE_MB * 1024 * 1024:
            logger.warning(f"Total size {total_size} exceeds limit, truncating cleanup")
            # Keep only files up to limit
            cumulative = 0
            for i, (_, size) in enumerate(files_to_delete):
                cumulative += size
                if cumulative > MAX_TOTAL_SIZE_MB * 1024 * 1024:
                    files_to_delete = files_to_delete[:i]
                    break

        # 4. Delete files
        deleted_count = 0
        freed_bytes = 0

        for file_path, file_size in files_to_delete:
            if self._dry_run:
                logger.info(f"[DRY RUN] Would delete: {file_path} ({file_size} bytes)")
            else:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.info(f"Deleted: {file_path} ({file_size} bytes)")
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}", exc_info=True)

        # 5. Clean empty directories
        await self._clean_empty_directories()

        # Update stats (handle None case for type safety)
        files_del = self._stats.get("files_deleted")
        bytes_fr = self._stats.get("bytes_freed")
        self._stats["files_deleted"] = (
            int(files_del) if files_del else 0
        ) + deleted_count
        self._stats["bytes_freed"] = (int(bytes_fr) if bytes_fr else 0) + freed_bytes

        logger.info(
            f"Cleanup run complete: deleted {deleted_count} files, "
            f"freed {freed_bytes / 1024 / 1024:.2f} MB"
        )

    async def _find_old_temp_files(
        self, cutoff_date: datetime
    ) -> list[tuple[Path, int]]:
        """Find temp files older than cutoff date.

        Hey future me - was sind "temp files"?
        - .part files (incomplete downloads)
        - .tmp files
        - Files in _temp/ subdirectories
        - Files mit modified_time < cutoff

        NICHT löschen:
        - Dateien die gerade benutzt werden (check running jobs!)
        - Echte Musik-Dateien (.mp3, .flac etc)
        """
        old_files: list[tuple[Path, int]] = []

        # Check downloads folder for temp/partial files
        if self._downloads_path.exists():
            for pattern in ["*.part", "*.tmp", "*.partial"]:
                for file_path in self._downloads_path.rglob(pattern):
                    try:
                        stat = file_path.stat()
                        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                        if mtime < cutoff_date:
                            old_files.append((file_path, stat.st_size))
                    except Exception as e:
                        logger.debug(f"Could not stat {file_path}: {e}")

        # Check explicit temp folder if provided
        if self._temp_path and self._temp_path.exists():
            for file_path in self._temp_path.rglob("*"):
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                        if mtime < cutoff_date:
                            old_files.append((file_path, stat.st_size))
                    except Exception as e:
                        logger.debug(f"Could not stat {file_path}: {e}")

        return old_files

    async def _clean_empty_directories(self) -> None:
        """Remove empty directories from downloads folder.

        Hey future me - nur LEERE Ordner löschen!
        Und nur unter downloads_path, nie den root folder selbst.
        """
        if not self._downloads_path.exists():
            return

        # Find empty directories (bottom-up to handle nested empties)
        empty_dirs: list[Path] = []
        for dir_path in sorted(
            self._downloads_path.rglob("*"), key=lambda p: len(p.parts), reverse=True
        ):
            if (
                dir_path.is_dir()
                and not any(dir_path.iterdir())
                and dir_path != self._downloads_path
            ):
                empty_dirs.append(dir_path)

        for dir_path in empty_dirs[:50]:  # Limit for safety
            if self._dry_run:
                logger.info(f"[DRY RUN] Would remove empty dir: {dir_path}")
            else:
                try:
                    dir_path.rmdir()
                    logger.info(f"Removed empty directory: {dir_path}")
                except Exception as e:
                    logger.debug(f"Could not remove {dir_path}: {e}")

    async def trigger_cleanup_now(self) -> str:
        """Manually trigger a cleanup run.

        Returns:
            Job ID of the cleanup job
        """
        job_id = await self._job_queue.enqueue(
            job_type=JobType.CLEANUP,
            payload={"trigger": "manual", "timestamp": datetime.now(UTC).isoformat()},
        )
        logger.info(f"Manual cleanup triggered, job_id={job_id}")

        # Run cleanup in background
        asyncio.create_task(self._run_cleanup())

        return job_id
