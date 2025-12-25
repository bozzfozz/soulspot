"""Download worker for background download processing."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

# Hey future me - TYPE_CHECKING is a CRITICAL circular import fix! This block is:
# - TRUE during mypy/pylance type checking (so types resolve correctly)
# - FALSE at runtime (so import doesn't execute, breaking the cycle)
# The actual import happens LAZILY in __init__ where we instantiate the use case.
# SearchAndDownloadTrackUseCase needs to be imported there, not at module level!
if TYPE_CHECKING:
    pass

from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import ISlskdClient
from soulspot.domain.value_objects import TrackId

logger = logging.getLogger(__name__)


# Type alias for session factory - returns an async context manager yielding AsyncSession
# Hey future me - we use Callable returning AsyncGenerator because that's what
# @asynccontextmanager decorated functions return. Can't use AsyncContextManager
# directly because db.session_scope is a method, not a class.
SessionFactory = Callable[[], AsyncGenerator[AsyncSession, None]]


class DownloadWorker:
    """Worker for processing download jobs in the background.

    REFACTORED (Dec 2025) - Session Factory Pattern for SQLite Lock Optimization!
    
    Previously: Received pre-instantiated repositories with a shared session.
    Problem: Shared session caused "database is locked" errors when concurrent
    jobs tried to write to SQLite.
    
    Now: Receives a session_factory and creates fresh session + repositories
    for each job. This ensures each job has its own transaction scope and
    releases locks quickly after completion.

    This worker:
    1. Monitors download queue
    2. Creates fresh DB session per job (lock optimization!)
    3. Searches for tracks on Soulseek
    4. Initiates downloads via slskd
    5. Updates download status in repository
    6. Handles retries for failed downloads
    """

    # Hey future me - REFACTORED to use session_factory instead of shared repositories!
    # This prevents SQLite "database is locked" errors by giving each job its own session.
    # The session is created fresh for each job and committed/rolled back immediately.
    def __init__(
        self,
        job_queue: JobQueue,
        slskd_client: ISlskdClient,
        session_factory: SessionFactory,
    ) -> None:
        """Initialize download worker.

        Args:
            job_queue: Job queue for background processing
            slskd_client: Client for Soulseek operations
            session_factory: Factory to create new DB sessions (e.g., db.session_scope)
        """
        self._job_queue = job_queue
        self._slskd_client = slskd_client
        self._session_factory = session_factory

    # Yo, this is the registration step - tells the job queue "when you see a DOWNLOAD job, call my
    # _handle_download_job method". This is separate from __init__ so you can create the worker without
    # it immediately consuming jobs (important for startup sequencing!). Call this AFTER the app is fully
    # initialized and DB is ready. If you call this too early, jobs might fail because dependencies aren't ready.
    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(JobType.DOWNLOAD, self._handle_download_job)

    # Listen up future me, this is the actual job handler that processes each download job.
    # 
    # REFACTORED (Dec 2025) - Session-per-Job Pattern!
    # Each job now gets its OWN database session, created fresh and committed/rolled back
    # immediately after the operation. This prevents SQLite lock contention when multiple
    # download jobs run concurrently.
    #
    # The flow is:
    # 1. Create fresh session via session_factory
    # 2. Create fresh repositories with that session
    # 3. Create use case with those repositories
    # 4. Execute download
    # 5. Session auto-commits on success / rollback on error (via context manager)
    #
    # This is called by the job queue worker pool, NOT directly by your code!
    async def _handle_download_job(self, job: Job) -> Any:
        """Handle a download job.

        Args:
            job: Job to process

        Returns:
            Download result
        """
        # Extract payload
        track_id_str = job.payload.get("track_id")
        if not track_id_str:
            raise ValueError("Missing track_id in job payload")

        track_id = TrackId.from_string(track_id_str)
        search_query = job.payload.get("search_query")
        max_results = job.payload.get("max_results", 10)
        timeout_seconds = job.payload.get("timeout_seconds", 30)
        quality_preference = job.payload.get("quality_preference", "best")

        # LOCK OPTIMIZATION: Create fresh session and repositories for THIS job only!
        # This ensures short-lived transactions that release SQLite locks quickly.
        async with self._session_factory() as session:
            # Lazy imports to avoid circular dependencies
            from soulspot.application.use_cases.search_and_download import (
                SearchAndDownloadTrackRequest,
                SearchAndDownloadTrackUseCase,
            )
            from soulspot.infrastructure.persistence.repositories import (
                DownloadRepository,
                TrackRepository,
            )

            # Create fresh repositories with this job's session
            track_repository = TrackRepository(session)
            download_repository = DownloadRepository(session)

            # Create use case with fresh repositories
            use_case = SearchAndDownloadTrackUseCase(
                slskd_client=self._slskd_client,
                track_repository=track_repository,
                download_repository=download_repository,
            )

            # Execute use case
            request = SearchAndDownloadTrackRequest(
                track_id=track_id,
                search_query=search_query,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
                quality_preference=quality_preference,
            )

            response = await use_case.execute(request)

            # Check if download was successful
            if response.error_message:
                raise Exception(response.error_message)

            return {
                "download_id": str(response.download.id.value)
                if response.download
                else None,
                "slskd_download_id": response.slskd_download_id,
                "search_results_count": response.search_results_count,
                "status": response.status.value,
            }

    # Hey, this is the PUBLIC API for queueing downloads - controllers call this, not _handle_download_job!
    # It packages up all the download params into a job payload and enqueues it. The job gets picked up
    # later by _handle_download_job running in the worker pool. The quality_preference ("best", "good", "any")
    # affects which Soulseek results we pick - "best" = highest bitrate/FLAC, "any" = first result. max_retries
    # defaults to 3 - if download fails 3 times, job goes to FAILED (no more retries). Priority lets urgent
    # downloads jump the queue (higher number = higher priority). Returns job_id for tracking.
    async def enqueue_download(
        self,
        track_id: TrackId,
        search_query: str | None = None,
        max_results: int = 10,
        timeout_seconds: int = 30,
        quality_preference: str = "best",
        max_retries: int = 3,
        priority: int = 0,
    ) -> str:
        """Enqueue a download job.

        Args:
            track_id: Track to download
            search_query: Optional custom search query
            max_results: Maximum search results
            timeout_seconds: Search timeout
            quality_preference: Quality preference (best, good, any)
            max_retries: Maximum retry attempts
            priority: Job priority (higher value = higher priority)

        Returns:
            Job ID
        """
        return await self._job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={
                "track_id": str(track_id.value),
                "search_query": search_query,
                "max_results": max_results,
                "timeout_seconds": timeout_seconds,
                "quality_preference": quality_preference,
            },
            max_retries=max_retries,
            priority=priority,
        )

    # Yo future me, this monitor is a BACKGROUND LOOP that polls slskd for download progress! It runs FOREVER
    # in an asyncio task, checking every poll_interval seconds (default 10s). It finds RUNNING download jobs,
    # extracts their slskd_download_id, and queries slskd for status (bytes downloaded, state, errors). The
    # implementation is STUBBED OUT (pass) - you need to add actual slskd API calls! This is where you'd
    # update progress bars, detect completed/failed downloads, and trigger post-processing. IMPORTANT: This
    # is CPU/network intensive if you have hundreds of downloads - consider batching slskd status calls!
    # If this crashes, downloads become "zombie" jobs - stuck in RUNNING forever. Add health checks!
    async def monitor_downloads(self, poll_interval: int = 10) -> None:
        """Monitor active downloads and update status.

        This should be run as a background task to periodically
        check download progress and update the database.

        Args:
            poll_interval: Seconds between status checks
        """

        while True:
            try:
                # Get all downloads in progress
                from soulspot.application.workers.job_queue import JobStatus

                running_jobs = await self._job_queue.list_jobs(
                    status=JobStatus.RUNNING,
                    job_type=JobType.DOWNLOAD,
                )

                # Check each download status
                for job in running_jobs:
                    slskd_download_id = (
                        job.result.get("slskd_download_id") if job.result else None
                    )
                    if slskd_download_id:
                        # Query slskd for download status and update job accordingly
                        # Implementation needed:
                        # 1. status = await slskd_client.get_download_status(slskd_download_id)
                        # 2. if status['state'] == 'completed': mark job as completed
                        # 3. if status['state'] == 'failed': mark job as failed and retry
                        # 4. Update job progress with bytes_downloaded / total_bytes
                        pass

            except Exception as e:
                # Log error but continue monitoring
                logger.exception("Download monitor error: %s", e)

            await asyncio.sleep(poll_interval)
