"""Persistent Job Queue - Database-backed job queue that survives restarts.

Hey future me - this is the PERSISTENT job storage layer!

PROBLEM:
The in-memory JobQueue loses all jobs when the app restarts.
User queues 50 album downloads, container restarts, everything gone!

SOLUTION:
This class wraps the in-memory JobQueue with database persistence:
1. New jobs are written to DB AND memory queue
2. Status updates are immediately synced to DB
3. On startup, pending/running jobs are loaded from DB into memory queue
4. Running jobs that weren't completed (crashed workers) are reset to pending

ARCHITECTURE:
```
User → PersistentJobQueue.enqueue() → DB + Memory Queue
                                           ↓
                                    Worker processes job
                                           ↓
                          PersistentJobQueue.complete/fail() → DB + Memory
```

WORKER LOCKING (for horizontal scaling):
- Each worker has unique ID (e.g., "worker-a1b2c3d4")
- locked_by + locked_at prevent multiple workers processing same job
- Stale lock detection: If locked_at > 5min and still RUNNING, worker crashed

USAGE:
```python
# In lifecycle.py
queue = PersistentJobQueue(
    session_factory=db.get_session_factory(),
    max_concurrent_jobs=3,
)
await queue.recover_jobs()  # Load pending jobs from DB
await queue.start(num_workers=2)

# In worker
job_id = await queue.enqueue(JobType.DOWNLOAD, {"track_id": "..."})
```
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soulspot.application.workers.job_queue import Job, JobQueue, JobStatus, JobType

if TYPE_CHECKING:
    from soulspot.infrastructure.persistence.models import BackgroundJobModel

logger = logging.getLogger(__name__)


@dataclass
class PersistentJobQueueStats:
    """Statistics for the persistent job queue."""

    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    recovered_jobs: int = 0  # Jobs recovered from crashed workers


class PersistentJobQueue(JobQueue):
    """Database-backed job queue that survives app restarts.

    Hey future me - this EXTENDS JobQueue with persistence!

    It inherits all the in-memory queue logic (priority, handlers, etc.)
    but adds DB persistence for jobs so they survive restarts.

    Key differences from base JobQueue:
    1. enqueue() writes to DB AND memory queue
    2. complete/fail methods update DB
    3. recover_jobs() loads pending jobs on startup
    4. Worker locking for horizontal scaling
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        max_concurrent_jobs: int = 5,
        worker_id: str | None = None,
        lock_timeout_seconds: int = 300,  # 5 minutes
    ) -> None:
        """Initialize persistent job queue.

        Args:
            session_factory: Factory for creating DB sessions
            max_concurrent_jobs: Maximum concurrent jobs to process
            worker_id: Unique ID for this worker (auto-generated if None)
            lock_timeout_seconds: Timeout for stale lock detection
        """
        super().__init__(max_concurrent_jobs)
        self._session_factory = session_factory
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._lock_timeout = lock_timeout_seconds
        self._stats = PersistentJobQueueStats()

    @property
    def worker_id(self) -> str:
        """Get this worker's unique ID."""
        return self._worker_id

    async def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        max_retries: int = 3,
        priority: int = 0,
    ) -> str:
        """Add a job to the queue (persisted to DB).

        Hey future me - this overrides JobQueue.enqueue!
        Writes to DB FIRST (durability), then adds to memory queue.
        If DB write fails, job is not added at all (no orphans).

        Args:
            job_type: Type of job
            payload: Job data (will be JSON serialized)
            max_retries: Maximum retry attempts
            priority: Job priority (higher = higher priority)

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())

        # Write to DB first (durability guarantee)
        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            model = BackgroundJobModel(
                id=job_id,
                job_type=job_type.value,
                status=JobStatus.PENDING.value,
                priority=priority,
                payload=json.dumps(payload),
                retries=0,
                max_retries=max_retries,
            )
            session.add(model)
            await session.commit()

        # Now add to memory queue (parent class handles priority)
        job = Job(
            id=job_id,
            job_type=job_type,
            payload=payload,
            max_retries=max_retries,
            priority=priority,
        )
        self._jobs[job.id] = job
        await self._queue.put((-job.priority, self._counter, job))
        self._counter += 1

        self._stats.total_jobs += 1
        self._stats.pending_jobs += 1

        logger.debug(
            f"Enqueued job {job_id} ({job_type.value}) with priority {priority}"
        )

        return job_id

    async def recover_jobs(
        self,
        exclude_types: list[JobType] | None = None,
    ) -> int:
        """Load pending/running jobs from DB on startup.

        Hey future me - call this BEFORE starting workers!
        It:
        1. Cancels abandoned PENDING jobs (>24h old) 
        2. Loads recent PENDING jobs into memory queue
        3. Resets RUNNING jobs (crashed workers) to PENDING
        4. Returns count of recovered jobs

        Args:
            exclude_types: Job types to SKIP during recovery. These jobs stay
                          in DB (PENDING) but won't be loaded into memory queue.
                          Use this to prevent conflicts during startup!
                          Example: exclude_types=[JobType.LIBRARY_SCAN] prevents
                          LIBRARY_SCAN from running while UnifiedLibraryManager
                          does its initial sync.

        Returns:
            Number of jobs recovered (excluding excluded types)
        """
        recovered_count = 0
        abandoned_count = 0

        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            # STEP 0: Cancel abandoned PENDING jobs (>24h old)
            # Hey future me - Jobs that sat PENDING for >24h are probably abandoned!
            # User likely restarted container multiple times, these are "zombie" jobs.
            abandoned_threshold = datetime.now(UTC) - timedelta(hours=24)
            
            abandoned_result = await session.execute(
                update(BackgroundJobModel)
                .where(
                    BackgroundJobModel.status == JobStatus.PENDING.value,
                    BackgroundJobModel.created_at < abandoned_threshold,
                )
                .values(
                    status=JobStatus.CANCELLED.value,
                    completed_at=datetime.now(UTC),
                    error="Abandoned: Job was pending for >24h",
                )
            )
            abandoned_count = abandoned_result.rowcount or 0
            if abandoned_count > 0:
                logger.warning(
                    f"Cancelled {abandoned_count} abandoned jobs (pending >24h)"
                )

            # STEP 1: Recover stale running jobs (crashed workers)
            stale_threshold = datetime.now(UTC) - timedelta(seconds=self._lock_timeout)

            stale_result = await session.execute(
                update(BackgroundJobModel)
                .where(
                    BackgroundJobModel.status == JobStatus.RUNNING.value,
                    BackgroundJobModel.locked_at < stale_threshold,
                )
                .values(
                    status=JobStatus.PENDING.value,
                    locked_by=None,
                    locked_at=None,
                    started_at=None,
                )
            )
            stale_count = stale_result.rowcount or 0
            if stale_count > 0:
                logger.warning(
                    f"Recovered {stale_count} stale jobs from crashed workers"
                )
                self._stats.recovered_jobs += stale_count

            # Now: Load all pending jobs into memory queue
            # Hey future me - exclude_types allows skipping certain job types!
            # This prevents LIBRARY_SCAN from auto-recovering during startup,
            # which would conflict with UnifiedLibraryManager's initial sync.
            query = (
                select(BackgroundJobModel)
                .where(BackgroundJobModel.status == JobStatus.PENDING.value)
                .order_by(
                    BackgroundJobModel.priority.desc(),
                    BackgroundJobModel.created_at,
                )
            )
            
            # Filter out excluded job types
            if exclude_types:
                excluded_type_values = [jt.value for jt in exclude_types]
                query = query.where(
                    ~BackgroundJobModel.job_type.in_(excluded_type_values)
                )
                logger.info(
                    f"Excluding job types from recovery: {excluded_type_values}"
                )
            
            result = await session.execute(query)
            pending_models = result.scalars().all()

            await session.commit()

        # Add pending jobs to memory queue
        for model in pending_models:
            try:
                job = self._model_to_job(model)
                self._jobs[job.id] = job
                await self._queue.put((-job.priority, self._counter, job))
                self._counter += 1
                recovered_count += 1
            except Exception as e:
                logger.error(f"Failed to recover job {model.id}: {e}")

        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} pending jobs from database")

        self._stats.pending_jobs = recovered_count

        return recovered_count + stale_count

    async def _mark_job_running(self, job: Job) -> bool:
        """Lock job for this worker and mark as running.

        Returns True if lock acquired, False if another worker got it.
        """
        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            # Atomic lock with optimistic concurrency
            result = await session.execute(
                update(BackgroundJobModel)
                .where(
                    BackgroundJobModel.id == job.id,
                    BackgroundJobModel.status == JobStatus.PENDING.value,
                    BackgroundJobModel.locked_by.is_(None),
                )
                .values(
                    status=JobStatus.RUNNING.value,
                    locked_by=self._worker_id,
                    locked_at=datetime.now(UTC),
                    started_at=datetime.now(UTC),
                )
            )
            await session.commit()

            if result.rowcount == 0:
                # Another worker got it, or status changed
                return False

        job.mark_running()
        self._stats.pending_jobs -= 1
        self._stats.running_jobs += 1

        return True

    async def complete_job(self, job_id: str, result: Any = None) -> None:
        """Mark job as completed (persisted to DB).

        Args:
            job_id: Job ID
            result: Optional result data
        """
        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            await session.execute(
                update(BackgroundJobModel)
                .where(BackgroundJobModel.id == job_id)
                .values(
                    status=JobStatus.COMPLETED.value,
                    result=json.dumps(result) if result else None,
                    completed_at=datetime.now(UTC),
                    locked_by=None,
                    locked_at=None,
                )
            )
            await session.commit()

        # Update in-memory job
        job = self._jobs.get(job_id)
        if job:
            job.mark_completed(result)
            self._running_jobs.discard(job_id)

        self._stats.running_jobs -= 1
        self._stats.completed_jobs += 1

        logger.debug(f"Job {job_id} completed")

    async def fail_job(self, job_id: str, error: str) -> None:
        """Mark job as failed (with retry logic).

        Args:
            job_id: Job ID
            error: Error message
        """
        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            # Get current job state
            result = await session.execute(
                select(BackgroundJobModel).where(BackgroundJobModel.id == job_id)
            )
            model = result.scalar_one_or_none()

            if not model:
                logger.warning(f"Job {job_id} not found in DB for failure update")
                return

            model.retries += 1
            model.error = error
            model.locked_by = None
            model.locked_at = None

            if model.retries < model.max_retries:
                # Schedule retry with exponential backoff
                backoff_seconds = 2**model.retries  # 2, 4, 8 seconds
                model.status = JobStatus.PENDING.value
                model.next_run_at = datetime.now(UTC) + timedelta(
                    seconds=backoff_seconds
                )
                logger.info(
                    f"Job {job_id} failed (attempt {model.retries}/{model.max_retries}), "
                    f"retry in {backoff_seconds}s"
                )
                should_retry = True
            else:
                # Max retries reached - permanent failure
                model.status = JobStatus.FAILED.value
                model.completed_at = datetime.now(UTC)
                logger.warning(
                    f"Job {job_id} failed permanently after {model.retries} attempts"
                )
                should_retry = False

            await session.commit()

        # Update in-memory job
        job = self._jobs.get(job_id)
        if job:
            job.mark_failed(error)
            self._running_jobs.discard(job_id)

            if should_retry and job.should_retry():
                # Re-enqueue with lower priority
                job.status = JobStatus.PENDING
                await self._queue.put((-job.priority + 1, self._counter, job))
                self._counter += 1

        self._stats.running_jobs -= 1
        if should_retry:
            self._stats.pending_jobs += 1
        else:
            self._stats.failed_jobs += 1

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (persisted to DB).

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False if not found or already completed
        """
        # First try in-memory cancel
        success = await super().cancel_job(job_id)
        if not success:
            return False

        # Persist to DB
        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            await session.execute(
                update(BackgroundJobModel)
                .where(
                    BackgroundJobModel.id == job_id,
                    BackgroundJobModel.status.in_(
                        [
                            JobStatus.PENDING.value,
                            JobStatus.RUNNING.value,
                        ]
                    ),
                )
                .values(
                    status=JobStatus.CANCELLED.value,
                    completed_at=datetime.now(UTC),
                    locked_by=None,
                    locked_at=None,
                )
            )
            await session.commit()

        self._stats.cancelled_jobs += 1

        return True

    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """Delete old jobs from database.

        Hey future me - call this periodically to prevent DB bloat!
        Deletes:
        - Jobs in terminal states (completed, failed, cancelled) older than X days
        - PENDING jobs older than 1 day (abandoned/zombie jobs)

        Args:
            days: Delete terminal-state jobs older than this many days

        Returns:
            Number of jobs deleted
        """
        threshold = datetime.now(UTC) - timedelta(days=days)
        pending_threshold = datetime.now(UTC) - timedelta(days=1)  # 24h for pending

        async with self._session_factory() as session:
            from soulspot.infrastructure.persistence.models import BackgroundJobModel

            # Delete old completed/failed/cancelled jobs
            terminal_result = await session.execute(
                delete(BackgroundJobModel).where(
                    BackgroundJobModel.status.in_(
                        [
                            JobStatus.COMPLETED.value,
                            JobStatus.FAILED.value,
                            JobStatus.CANCELLED.value,
                        ]
                    ),
                    BackgroundJobModel.completed_at < threshold,
                )
            )
            terminal_deleted = terminal_result.rowcount or 0

            # Delete old abandoned PENDING jobs (>24h)
            # Hey future me - these are zombie jobs that never started!
            pending_result = await session.execute(
                delete(BackgroundJobModel).where(
                    BackgroundJobModel.status == JobStatus.PENDING.value,
                    BackgroundJobModel.created_at < pending_threshold,
                )
            )
            pending_deleted = pending_result.rowcount or 0
            
            await session.commit()

            total_deleted = terminal_deleted + pending_deleted
            if total_deleted > 0:
                logger.info(
                    f"Cleaned up {total_deleted} old jobs "
                    f"({terminal_deleted} terminal, {pending_deleted} pending)"
                )

            return total_deleted

    def get_stats(self) -> PersistentJobQueueStats:
        """Get queue statistics."""
        return self._stats

    def _model_to_job(self, model: "BackgroundJobModel") -> Job:
        """Convert DB model to Job dataclass."""
        from soulspot.infrastructure.persistence.models import ensure_utc_aware

        return Job(
            id=model.id,
            job_type=JobType(model.job_type),
            payload=json.loads(model.payload),
            status=JobStatus(model.status),
            priority=model.priority,
            created_at=ensure_utc_aware(model.created_at),
            started_at=ensure_utc_aware(model.started_at) if model.started_at else None,
            completed_at=ensure_utc_aware(model.completed_at)
            if model.completed_at
            else None,
            error=model.error,
            result=json.loads(model.result) if model.result else None,
            retries=model.retries,
            max_retries=model.max_retries,
        )


# Factory function for easy creation
def create_persistent_job_queue(
    session_factory: async_sessionmaker[AsyncSession],
    max_concurrent_jobs: int = 5,
    worker_id: str | None = None,
) -> PersistentJobQueue:
    """Create a PersistentJobQueue with the given configuration.

    Args:
        session_factory: Factory for creating DB sessions
        max_concurrent_jobs: Maximum concurrent jobs (default: 5)
        worker_id: Unique worker ID (auto-generated if None)

    Returns:
        Configured PersistentJobQueue instance
    """
    return PersistentJobQueue(
        session_factory=session_factory,
        max_concurrent_jobs=max_concurrent_jobs,
        worker_id=worker_id,
    )
