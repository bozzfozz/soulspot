"""Download worker for background download processing."""

import asyncio
import logging
from typing import Any

from soulspot.application.use_cases import SearchAndDownloadTrackUseCase
from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import IDownloadRepository, ISlskdClient, ITrackRepository
from soulspot.domain.value_objects import TrackId

logger = logging.getLogger(__name__)


class DownloadWorker:
    """Worker for processing download jobs in the background.

    This worker:
    1. Monitors download queue
    2. Searches for tracks on Soulseek
    3. Initiates downloads via slskd
    4. Updates download status in repository
    5. Handles retries for failed downloads
    """

    def __init__(
        self,
        job_queue: JobQueue,
        slskd_client: ISlskdClient,
        track_repository: ITrackRepository,
        download_repository: IDownloadRepository,
    ) -> None:
        """Initialize download worker.

        Args:
            job_queue: Job queue for background processing
            slskd_client: Client for Soulseek operations
            track_repository: Repository for track persistence
            download_repository: Repository for download persistence
        """
        self._job_queue = job_queue
        self._use_case = SearchAndDownloadTrackUseCase(
            slskd_client=slskd_client,
            track_repository=track_repository,
            download_repository=download_repository,
        )

    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(JobType.DOWNLOAD, self._handle_download_job)

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

        # Execute use case
        from soulspot.application.use_cases.search_and_download import (
            SearchAndDownloadTrackRequest,
        )

        request = SearchAndDownloadTrackRequest(
            track_id=track_id,
            search_query=search_query,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            quality_preference=quality_preference,
        )

        response = await self._use_case.execute(request)

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

    async def enqueue_download(
        self,
        track_id: TrackId,
        search_query: str | None = None,
        max_results: int = 10,
        timeout_seconds: int = 30,
        quality_preference: str = "best",
        max_retries: int = 3,
    ) -> str:
        """Enqueue a download job.

        Args:
            track_id: Track to download
            search_query: Optional custom search query
            max_results: Maximum search results
            timeout_seconds: Search timeout
            quality_preference: Quality preference (best, good, any)
            max_retries: Maximum retry attempts

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
        )

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
                        # Query slskd for status
                        # (This would be implemented in production)
                        pass

            except Exception as e:
                # Log error but continue monitoring
                logger.exception("Download monitor error: %s", e)

            await asyncio.sleep(poll_interval)
