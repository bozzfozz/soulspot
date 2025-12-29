# Hey future me - Image Queue Worker prozessiert die Download-Queue!
#
# Dieser Worker läuft PERMANENT (nicht interval-basiert wie ImageBackfillWorker).
# Er wacht sofort auf wenn Jobs in der Queue landen via queue.get().
#
# Key Features:
# - Parallel Downloads (konfigurierbare Concurrency)
# - Graceful Shutdown
# - Error Handling mit Continue (ein Fehler stoppt nicht alles)
# - Stats Tracking für Monitoring
# - DB-Update nach Download (image_path wird gespeichert!)
#
# Unterschied zu ImageBackfillWorker:
# - ImageBackfillWorker: Läuft alle 30 min, repariert FEHLENDE Bilder
# - ImageQueueWorker: Läuft permanent, prozessiert NEUE Bilder sofort
"""Image Queue Worker - Processes image download jobs."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.images.image_service import ImageService
    from soulspot.application.services.images.queue import (
        ImageDownloadJob,
        ImageDownloadQueue,
    )

logger = logging.getLogger(__name__)


class ImageQueueWorker:
    """Background worker that processes image download queue.

    Hey future me - this worker runs PERMANENTLY (not interval-based)!
    It wakes up immediately when jobs arrive via queue.get().

    IMPORTANT: After downloading, this worker updates the DB with image_path!
    Without session_factory, downloads work but DB won't be updated.

    Key design decisions:
    1. Multiple concurrent workers (default: 3)
       - Balances throughput vs resource usage
       - Each worker processes one job at a time
       - Workers share the same queue (thread-safe)

    2. Timeout-based polling (1 second)
       - Allows graceful shutdown check between polls
       - Not busy-waiting (efficient CPU usage)

    3. Error handling: Continue on failure
       - One failed download doesn't stop others
       - Errors are logged and counted
       - Job is marked done (not re-queued)

    4. DB Update per Job (session-per-job pattern)
       - Each download gets its own session
       - Session is committed/closed after update
       - Prevents lock contention with SQLite

    Usage:
        worker = ImageQueueWorker(queue, image_service, session_factory)
        await worker.start()
        # ... worker runs in background ...
        await worker.stop()  # Graceful shutdown
    """

    def __init__(
        self,
        queue: ImageDownloadQueue,
        image_service: ImageService,
        session_factory: Callable[[], Any] | None = None,
        max_concurrent: int = 3,
    ):
        """Initialize worker.

        Args:
            queue: The image download queue to process
            image_service: ImageService for actual downloads
            session_factory: Async context manager factory for DB sessions (e.g., db.session_scope)
            max_concurrent: Number of parallel download workers (default: 3)
        """
        self._queue = queue
        self._image_service = image_service
        self._session_factory = session_factory
        self._concurrency = max_concurrent
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._stats: dict[str, int] = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "db_updates": 0,
        }
        self._started_at: datetime | None = None

    async def start(self) -> None:
        """Start worker with multiple concurrent processors.

        Creates `concurrency` number of worker tasks that all
        pull from the same queue.
        """
        if self._running:
            logger.warning("ImageQueueWorker already running")
            return

        self._running = True
        self._started_at = datetime.now(UTC)

        # Create concurrent worker tasks
        for i in range(self._concurrency):
            task = asyncio.create_task(
                self._process_loop(worker_id=i), name=f"image-worker-{i}"
            )
            self._tasks.append(task)

        logger.info(
            "🖼️ ImageQueueWorker started with %d concurrent workers", self._concurrency
        )

    async def stop(self, drain_timeout: float = 5.0) -> None:
        """Stop worker gracefully.

        Attempts to process remaining jobs before stopping.

        Args:
            drain_timeout: Max seconds to wait for queue to empty
        """
        if not self._running:
            return

        logger.info("ImageQueueWorker stopping...")

        # Signal workers to stop
        self._running = False

        # Wait for queue to drain (with timeout)
        if not self._queue.is_empty():
            logger.info(
                "Waiting for %d remaining jobs to complete...",
                self._queue.get_stats()["queue_size"],
            )
            await self._queue.drain(timeout=drain_timeout)

        # Cancel all worker tasks
        for task in self._tasks:
            task.cancel()

        # Wait for cancellation
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._tasks.clear()
        logger.info(
            "ImageQueueWorker stopped. Stats: %d processed, %d success, %d failed",
            self._stats["processed"],
            self._stats["success"],
            self._stats["failed"],
        )

    async def _process_loop(self, worker_id: int) -> None:
        """Main processing loop for a single worker.

        Continuously polls queue for jobs and processes them.

        Args:
            worker_id: Worker identifier for logging
        """
        logger.debug("Worker %d started", worker_id)

        while self._running:
            try:
                # Wait for next job with timeout
                # Timeout allows checking self._running periodically
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Process the job
                success = await self._process_job(job, worker_id)

                # Mark job as done
                await self._queue.mark_done(job, success=success)

                # Update stats
                self._stats["processed"] += 1
                if success:
                    self._stats["success"] += 1
                else:
                    self._stats["failed"] += 1

            except TimeoutError:
                # No job available, loop continues
                # This is normal - allows shutdown check
                continue
            except asyncio.CancelledError:
                logger.debug("Worker %d cancelled", worker_id)
                break
            except Exception as e:
                # Unexpected error - log and continue
                logger.exception("Worker %d unexpected error: %s", worker_id, e)
                await asyncio.sleep(0.5)  # Brief pause on error

        logger.debug("Worker %d stopped", worker_id)

    async def _process_job(self, job: ImageDownloadJob, worker_id: int) -> bool:
        """Process a single download job.

        Downloads the image and updates the database with the new path.

        Args:
            job: The download job to process
            worker_id: Worker identifier for logging

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            path: str | None = None

            if job.entity_type == "artist":
                path = await self._image_service.download_artist_image(
                    provider_id=job.provider_id,
                    image_url=job.image_url,
                    provider=job.provider,
                )
            elif job.entity_type == "album":
                path = await self._image_service.download_album_image(
                    provider_id=job.provider_id,
                    image_url=job.image_url,
                    provider=job.provider,
                )
            elif job.entity_type == "playlist":
                path = await self._image_service.download_playlist_image(
                    provider_id=job.provider_id,
                    image_url=job.image_url,
                    provider=job.provider,
                )
            else:
                logger.warning(
                    "Worker %d: Unknown entity type: %s", worker_id, job.entity_type
                )
                return False

            if path:
                logger.debug(
                    "Worker %d: ✅ Downloaded %s image: %s → %s",
                    worker_id,
                    job.entity_type,
                    job.provider_id,
                    path,
                )

                # Update database with new image path
                if self._session_factory:
                    await self._update_db(job, path, worker_id)

                return True
            else:
                logger.warning(
                    "Worker %d: ❌ Download returned None for %s: %s",
                    worker_id,
                    job.entity_type,
                    job.provider_id,
                )
                return False

        except Exception as e:
            logger.error(
                "Worker %d: Error downloading %s/%s: %s",
                worker_id,
                job.entity_type,
                job.provider_id,
                e,
            )
            return False

    async def _update_db(
        self, job: ImageDownloadJob, path: str, worker_id: int
    ) -> None:
        """Update database with downloaded image path.

        Uses session-per-job pattern to prevent lock contention.

        Args:
            job: The download job with provider info
            path: The downloaded image path
            worker_id: Worker identifier for logging
        """
        if not self._session_factory:
            return

        try:
            async with self._session_factory() as session:
                if job.entity_type == "artist":
                    await self._update_artist_image(session, job, path)
                elif job.entity_type == "album":
                    await self._update_album_image(session, job, path)
                elif job.entity_type == "playlist":
                    await self._update_playlist_image(session, job, path)

                await session.commit()
                self._stats["db_updates"] += 1
                logger.debug(
                    "Worker %d: DB updated %s %s → %s",
                    worker_id,
                    job.entity_type,
                    job.provider_id,
                    path,
                )
        except Exception as e:
            logger.error(
                "Worker %d: DB update failed for %s/%s: %s",
                worker_id,
                job.entity_type,
                job.provider_id,
                e,
            )

    async def _update_artist_image(
        self, session: AsyncSession, job: ImageDownloadJob, path: str
    ) -> None:
        """Update artist image_path in database.

        Finds artist by provider ID (spotify_uri or deezer_id) and updates image_path.
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import ArtistModel

        # Determine which provider column to use
        if job.provider == "spotify":
            # Spotify uses spotify_uri = "spotify:artist:ID"
            spotify_uri = f"spotify:artist:{job.provider_id}"
            stmt = (
                update(ArtistModel)
                .where(ArtistModel.spotify_uri == spotify_uri)
                .values(image_path=path)
            )
        elif job.provider == "deezer":
            stmt = (
                update(ArtistModel)
                .where(ArtistModel.deezer_id == job.provider_id)
                .values(image_path=path)
            )
        else:
            logger.warning(f"Unknown provider for artist update: {job.provider}")
            return

        await session.execute(stmt)

    async def _update_album_image(
        self, session: AsyncSession, job: ImageDownloadJob, path: str
    ) -> None:
        """Update album cover_path in database.

        Finds album by provider ID (spotify_uri or deezer_id) and updates cover_path.
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import AlbumModel

        if job.provider == "spotify":
            spotify_uri = f"spotify:album:{job.provider_id}"
            stmt = (
                update(AlbumModel)
                .where(AlbumModel.spotify_uri == spotify_uri)
                .values(cover_path=path)
            )
        elif job.provider == "deezer":
            stmt = (
                update(AlbumModel)
                .where(AlbumModel.deezer_id == job.provider_id)
                .values(cover_path=path)
            )
        else:
            logger.warning(f"Unknown provider for album update: {job.provider}")
            return

        await session.execute(stmt)

    async def _update_playlist_image(
        self, session: AsyncSession, job: ImageDownloadJob, path: str
    ) -> None:
        """Update playlist cover_path in database.

        Finds playlist by provider ID (spotify_uri) and updates cover_path.
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import PlaylistModel

        if job.provider == "spotify":
            spotify_uri = f"spotify:playlist:{job.provider_id}"
            stmt = (
                update(PlaylistModel)
                .where(PlaylistModel.spotify_uri == spotify_uri)
                .values(cover_path=path)
            )
        else:
            logger.warning(f"Unknown provider for playlist update: {job.provider}")
            return

        await session.execute(stmt)

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, stats, and queue info
        """
        uptime_seconds = 0.0
        if self._started_at:
            uptime_seconds = (datetime.now(UTC) - self._started_at).total_seconds()

        return {
            "running": self._running,
            "workers": len(self._tasks),
            "concurrency": self._concurrency,
            "uptime_seconds": uptime_seconds,
            **self._stats,
            "queue": self._queue.get_stats(),
        }

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
