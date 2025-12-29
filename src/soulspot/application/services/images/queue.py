# Hey future me - Image Download Queue für sofortige Bild-Downloads!
#
# Das ist das HERZ des "Eager Image Loading" Systems.
# Sync-Services queuen hier Jobs statt blockierend zu downloaden.
# ImageQueueWorker prozessiert die Queue parallel im Hintergrund.
#
# Warum Queue statt direkter Download?
# 1. Sync bleibt schnell (kein Warten auf HTTP/PIL)
# 2. Parallelität (3+ gleichzeitige Downloads)
# 3. Deduplication (gleiche Entity nicht doppelt)
# 4. Priority (User-Requests vor Background-Jobs)
#
# Flow:
#   SpotifySyncService.sync_artist_albums()
#       └─► queue.enqueue(ImageDownloadJob.for_album(...))
#           └─► ImageQueueWorker._process_loop()
#               └─► ImageService.download_album_image()
"""Image Download Queue - Async processing for immediate image downloads."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ImagePriority(IntEnum):
    """Download priority levels.

    Hey future me - lower number = higher priority (processed first)!

    Use cases:
    - HIGH: User clicked on artist/album, wants to see image NOW
    - NORMAL: Auto-sync (followed artists, album sync)
    - LOW: Background repair jobs, backfill
    """

    HIGH = 0  # User-requested (e.g., clicked artist detail page)
    NORMAL = 1  # Auto-sync (followed artists, album sync)
    LOW = 2  # Background (repair jobs, backfill)


@dataclass(order=True)
class ImageDownloadJob:
    """Job for image download queue.

    Hey future me - this is a PriorityQueue item!
    The `order=True` makes dataclass comparable by field order.
    We put priority first so jobs sort by priority, then by created_at.

    Fields marked `compare=False` are NOT used for sorting.
    """

    # For priority queue ordering (lower = higher priority)
    priority: int = field(compare=True)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC), compare=True
    )

    # Job data (not used for ordering)
    entity_type: Literal["artist", "album", "playlist"] = field(
        default="album", compare=False
    )
    entity_id: str = field(default="", compare=False)  # Internal UUID
    provider_id: str = field(default="", compare=False)  # Spotify/Deezer ID
    provider: str = field(default="spotify", compare=False)  # "spotify", "deezer"
    image_url: str = field(default="", compare=False)  # CDN URL to download

    @classmethod
    def for_artist(
        cls,
        entity_id: str,
        provider_id: str,
        url: str,
        provider: str = "spotify",
        priority: int = ImagePriority.NORMAL,
    ) -> ImageDownloadJob:
        """Create job for artist image download.

        Args:
            entity_id: Internal SoulSpot UUID
            provider_id: Spotify ID, Deezer ID, etc.
            url: CDN URL to download from
            provider: Provider name for path organization
            priority: Download priority (default: NORMAL)
        """
        return cls(
            priority=priority,
            entity_type="artist",
            entity_id=entity_id,
            provider_id=provider_id,
            provider=provider,
            image_url=url,
        )

    @classmethod
    def for_album(
        cls,
        entity_id: str,
        provider_id: str,
        url: str,
        provider: str = "spotify",
        priority: int = ImagePriority.NORMAL,
    ) -> ImageDownloadJob:
        """Create job for album cover download."""
        return cls(
            priority=priority,
            entity_type="album",
            entity_id=entity_id,
            provider_id=provider_id,
            provider=provider,
            image_url=url,
        )

    @classmethod
    def for_playlist(
        cls,
        entity_id: str,
        provider_id: str,
        url: str,
        provider: str = "spotify",
        priority: int = ImagePriority.NORMAL,
    ) -> ImageDownloadJob:
        """Create job for playlist cover download."""
        return cls(
            priority=priority,
            entity_type="playlist",
            entity_id=entity_id,
            provider_id=provider_id,
            provider=provider,
            image_url=url,
        )


class ImageDownloadQueue:
    """Thread-safe async queue for image downloads.

    Hey future me - this is the HEART of eager image loading!

    Key features:
    - Priority-based ordering (HIGH > NORMAL > LOW)
    - Deduplication (same entity won't be queued twice)
    - Batch enqueue for efficiency
    - Graceful shutdown support
    - Stats tracking for monitoring

    Usage:
        queue = ImageDownloadQueue()

        # Enqueue single job
        await queue.enqueue(ImageDownloadJob.for_artist(...))

        # Enqueue batch (e.g., all album covers)
        jobs = [ImageDownloadJob.for_album(...) for album in albums]
        count = await queue.enqueue_batch(jobs)

        # Worker gets jobs
        job = await queue.get()  # Blocks until job available
        # ... process job ...
        await queue.mark_done(job)
    """

    def __init__(self, max_size: int = 10000):
        """Initialize queue.

        Args:
            max_size: Maximum queue size (prevents memory explosion)
        """
        self._queue: asyncio.PriorityQueue[ImageDownloadJob] = asyncio.PriorityQueue(
            maxsize=max_size
        )
        self._pending: set[str] = set()  # entity keys for deduplication
        self._lock = asyncio.Lock()
        self._stats: dict[str, int] = {
            "enqueued": 0,
            "processed": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }

    def _job_key(self, job: ImageDownloadJob) -> str:
        """Generate unique key for deduplication.

        Key format: "{entity_type}:{entity_id}"
        This ensures we don't queue the same entity twice.
        """
        return f"{job.entity_type}:{job.entity_id}"

    async def enqueue(self, job: ImageDownloadJob) -> bool:
        """Add job to queue.

        Returns False if job is duplicate (already in queue).

        Args:
            job: The download job to enqueue

        Returns:
            True if enqueued, False if duplicate
        """
        async with self._lock:
            key = self._job_key(job)
            if key in self._pending:
                self._stats["duplicates_skipped"] += 1
                logger.debug("Skipping duplicate job: %s", key)
                return False

            self._pending.add(key)

        # Put outside lock to avoid blocking
        try:
            await self._queue.put(job)
            self._stats["enqueued"] += 1
            logger.debug(
                "Enqueued %s image job: %s (priority=%d, queue_size=%d)",
                job.entity_type,
                job.provider_id,
                job.priority,
                self._queue.qsize(),
            )
            return True
        except asyncio.QueueFull:
            # Remove from pending if queue is full
            async with self._lock:
                self._pending.discard(key)
            logger.warning("Image queue is full, dropping job: %s", key)
            return False

    async def enqueue_batch(self, jobs: list[ImageDownloadJob]) -> int:
        """Add multiple jobs to queue.

        Returns count of actually enqueued jobs (excludes duplicates).

        Args:
            jobs: List of download jobs

        Returns:
            Number of jobs actually enqueued
        """
        count = 0
        for job in jobs:
            if await self.enqueue(job):
                count += 1

        if jobs:
            logger.info(
                "Batch enqueued %d/%d image jobs (queue_size=%d)",
                count,
                len(jobs),
                self._queue.qsize(),
            )
        return count

    async def get(self) -> ImageDownloadJob:
        """Get next job from queue.

        Blocks until a job is available.
        Use with timeout in worker loop.

        Returns:
            Next job to process (highest priority first)
        """
        job = await self._queue.get()
        return job

    async def get_nowait(self) -> ImageDownloadJob | None:
        """Get next job without blocking.

        Returns:
            Next job or None if queue is empty
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def mark_done(self, job: ImageDownloadJob, success: bool = True) -> None:
        """Mark job as processed.

        Must be called after processing each job!
        This removes from pending set and updates stats.

        Args:
            job: The processed job
            success: Whether processing succeeded
        """
        async with self._lock:
            key = self._job_key(job)
            self._pending.discard(key)
            self._stats["processed"] += 1
            if not success:
                self._stats["errors"] += 1

        self._queue.task_done()

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics for monitoring.

        Returns:
            Dict with enqueued, processed, duplicates_skipped,
            errors, pending count, and current queue size
        """
        return {
            **self._stats,
            "pending": len(self._pending),
            "queue_size": self._queue.qsize(),
        }

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    async def drain(self, timeout: float = 5.0) -> bool:
        """Wait for queue to empty (with timeout).

        Useful for graceful shutdown.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if queue emptied, False if timeout
        """
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            return True
        except TimeoutError:
            logger.warning(
                "Queue drain timeout after %.1fs, %d jobs remaining",
                timeout,
                self._queue.qsize(),
            )
            return False

    async def clear(self) -> int:
        """Clear all pending jobs from queue.

        Returns:
            Number of jobs cleared
        """
        cleared = 0
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                cleared += 1
            except asyncio.QueueEmpty:
                break

        async with self._lock:
            self._pending.clear()

        logger.info("Cleared %d jobs from image queue", cleared)
        return cleared
