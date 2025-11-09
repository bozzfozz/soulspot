"""Job queue management for background workers."""

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class JobType(str, Enum):
    """Type of background job."""

    DOWNLOAD = "download"
    METADATA_ENRICHMENT = "metadata_enrichment"
    PLAYLIST_SYNC = "playlist_sync"


class JobStatus(str, Enum):
    """Status of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Background job to be processed."""

    id: str
    job_type: JobType
    payload: dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any | None = None
    retries: int = 0
    max_retries: int = 3

    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def mark_completed(self, result: Any = None) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.error = error
        self.retries += 1

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now(UTC)

    def should_retry(self) -> bool:
        """Check if job should be retried."""
        return self.status == JobStatus.FAILED and self.retries < self.max_retries


class JobQueue:
    """In-memory job queue for background workers.

    This is a simple in-memory implementation. For production use,
    consider using Redis, RabbitMQ, or Celery.
    """

    def __init__(self, max_concurrent_jobs: int = 5) -> None:
        """Initialize job queue.

        Args:
            max_concurrent_jobs: Maximum number of jobs to run concurrently
        """
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._jobs: dict[str, Job] = {}
        self._running_jobs: set[str] = set()
        self._max_concurrent = max_concurrent_jobs
        self._workers: list[asyncio.Task[None]] = []
        self._shutdown = False
        self._handlers: dict[JobType, Callable[[Job], Coroutine[Any, Any, Any]]] = {}

    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[[Job], Coroutine[Any, Any, Any]],
    ) -> None:
        """Register a handler for a job type.

        Args:
            job_type: Type of job to handle
            handler: Async function to process the job
        """
        self._handlers[job_type] = handler

    async def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        max_retries: int = 3,
    ) -> str:
        """Add a job to the queue.

        Args:
            job_type: Type of job
            payload: Job data
            max_retries: Maximum retry attempts

        Returns:
            Job ID
        """
        job = Job(
            id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            max_retries=max_retries,
        )

        self._jobs[job.id] = job
        await self._queue.put(job)

        return job.id

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found, None otherwise
        """
        return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False if not found or already completed
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False

        job.mark_cancelled()
        return True

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        jobs = list(self._jobs.values())

        # Apply filters
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    async def _process_job(self, job: Job) -> None:
        """Process a single job.

        Args:
            job: Job to process
        """
        if job.status == JobStatus.CANCELLED:
            return

        job.mark_running()
        self._running_jobs.add(job.id)

        try:
            # Get handler for job type
            handler = self._handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job.job_type}")

            # Execute handler
            result = await handler(job)
            job.mark_completed(result)

        except Exception as e:
            error_msg = str(e)
            job.mark_failed(error_msg)

            # Re-queue if should retry
            if job.should_retry():
                await self._queue.put(job)

        finally:
            self._running_jobs.discard(job.id)

    async def _worker_loop(self) -> None:
        """Worker loop to process jobs from queue."""
        while not self._shutdown:
            try:
                # Wait for job with timeout to allow checking shutdown flag
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Wait if too many jobs running
                while len(self._running_jobs) >= self._max_concurrent:
                    await asyncio.sleep(0.1)

                # Process job
                asyncio.create_task(self._process_job(job))

            except TimeoutError:
                continue
            except Exception as e:
                # Log error but continue processing
                print(f"Worker error: {e}")
                continue

    async def start(self, num_workers: int = 3) -> None:
        """Start worker threads.

        Args:
            num_workers: Number of worker threads to start
        """
        self._shutdown = False
        self._workers = [asyncio.create_task(self._worker_loop()) for _ in range(num_workers)]

    async def stop(self) -> None:
        """Stop all workers and wait for completion."""
        self._shutdown = True

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers = []

    async def wait_for_job(self, job_id: str, timeout: float | None = None) -> Job:
        """Wait for a job to complete.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Completed job

        Raises:
            asyncio.TimeoutError: If timeout is reached
            ValueError: If job not found
        """
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        start_time = asyncio.get_event_loop().time()

        while job.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise TimeoutError(f"Job did not complete within {timeout}s")

            await asyncio.sleep(0.1)
            job = await self.get_job(job_id)
            if not job:
                raise ValueError(f"Job disappeared: {job_id}")

        return job

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
            "running": len(self._running_jobs),
            "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
            "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
            "cancelled": len([j for j in jobs if j.status == JobStatus.CANCELLED]),
            "queue_size": self._queue.qsize(),
        }
