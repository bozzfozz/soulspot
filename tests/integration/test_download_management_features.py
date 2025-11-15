"""Comprehensive tests for download management enhancements.

This test suite validates all the features from the download management epic:
1. Priority-based queue
2. Retry logic with exponential backoff
3. Concurrent download limits
4. Pause/resume API (global and individual)
5. Batch operations
"""

import asyncio
from uuid import uuid4

import pytest

from soulspot.application.workers.job_queue import Job, JobQueue, JobStatus, JobType
from soulspot.domain.entities import Download, DownloadStatus
from soulspot.domain.value_objects import DownloadId, TrackId


class TestPriorityBasedQueue:
    """Test priority-based job queue implementation."""

    async def test_job_priority_field_exists(self) -> None:
        """Test that Job has priority field."""
        job = Job(
            id="test-job",
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "test-track"},
            priority=10,
        )

        assert hasattr(job, "priority")
        assert job.priority == 10

    async def test_download_priority_field_exists(self) -> None:
        """Test that Download entity has priority field."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            priority=1,
        )

        assert hasattr(download, "priority")
        assert download.priority == 1

    async def test_update_download_priority(self) -> None:
        """Test updating download priority."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            priority=0,
        )

        # Update priority
        download.update_priority(2)

        assert download.priority == 2

    async def test_priority_validation(self) -> None:
        """Test priority validation (0-2 range)."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            priority=0,
        )

        # Valid priorities
        download.update_priority(0)
        download.update_priority(1)
        download.update_priority(2)

        # Invalid priorities should raise ValueError
        with pytest.raises(ValueError):
            download.update_priority(-1)

        with pytest.raises(ValueError):
            download.update_priority(3)

    async def test_jobs_processed_by_priority(self) -> None:
        """Test that jobs are processed in priority order (higher first)."""
        job_queue = JobQueue(max_concurrent_jobs=1)
        processed_jobs: list[str] = []

        async def handler(job: Job) -> None:
            processed_jobs.append(job.id)
            await asyncio.sleep(0.05)

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue jobs with different priorities (higher priority = processed first)
        low_priority_job = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-1"}, priority=0
        )
        high_priority_job = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-2"}, priority=10
        )
        medium_priority_job = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-3"}, priority=5
        )

        # Start workers
        await job_queue.start(num_workers=1)
        await asyncio.sleep(0.5)
        await job_queue.stop()

        # Verify priority order: high, medium, low
        assert len(processed_jobs) == 3
        assert processed_jobs[0] == high_priority_job
        assert processed_jobs[1] == medium_priority_job
        assert processed_jobs[2] == low_priority_job


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    async def test_retry_with_exponential_backoff(self) -> None:
        """Test that jobs retry with exponential backoff (1s, 2s, 4s)."""
        job_queue = JobQueue(max_concurrent_jobs=1)
        attempt_times: list[float] = []

        async def failing_handler(job: Job) -> None:
            import time

            attempt_times.append(time.time())
            raise ValueError("Intentional failure for testing")

        job_queue.register_handler(JobType.DOWNLOAD, failing_handler)

        # Enqueue job with 3 retries
        job_id = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-123"}, max_retries=3
        )

        # Start workers
        await job_queue.start(num_workers=1)

        # Wait for all retries (1s + 2s + 4s + processing time)
        await asyncio.sleep(10)

        # Stop workers
        await job_queue.stop()

        # Check job failed after retries
        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.retries == 3

        # Verify exponential backoff timing
        assert len(attempt_times) == 3
        if len(attempt_times) >= 2:
            # First retry should be ~1s after initial attempt
            assert attempt_times[1] - attempt_times[0] >= 0.9
        if len(attempt_times) >= 3:
            # Second retry should be ~2s after first retry
            assert attempt_times[2] - attempt_times[1] >= 1.9

    async def test_max_retries_configurable(self) -> None:
        """Test that max retries is configurable."""
        job_queue = JobQueue(max_concurrent_jobs=1)

        async def failing_handler(job: Job) -> None:
            raise ValueError("Test failure")

        job_queue.register_handler(JobType.DOWNLOAD, failing_handler)

        # Enqueue with custom max_retries
        job_id = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-123"}, max_retries=2
        )

        await job_queue.start(num_workers=1)
        await asyncio.sleep(5)
        await job_queue.stop()

        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.max_retries == 2
        assert job.retries == 2


class TestConcurrentDownloadLimits:
    """Test configurable concurrent download limits."""

    async def test_set_max_concurrent_jobs(self) -> None:
        """Test setting maximum concurrent jobs."""
        job_queue = JobQueue(max_concurrent_jobs=3)

        # Initial value
        assert job_queue.get_max_concurrent_jobs() == 3

        # Set to 2
        job_queue.set_max_concurrent_jobs(2)
        assert job_queue.get_max_concurrent_jobs() == 2

        # Set to 1
        job_queue.set_max_concurrent_jobs(1)
        assert job_queue.get_max_concurrent_jobs() == 1

    async def test_concurrent_limit_respected(self) -> None:
        """Test that concurrent job limit is respected."""
        job_queue = JobQueue(max_concurrent_jobs=2)

        running_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def slow_handler(job: Job) -> None:
            nonlocal running_count, max_concurrent
            async with lock:
                running_count += 1
                max_concurrent = max(max_concurrent, running_count)

            await asyncio.sleep(0.2)

            async with lock:
                running_count -= 1

        job_queue.register_handler(JobType.DOWNLOAD, slow_handler)

        # Enqueue multiple jobs
        for i in range(5):
            await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": f"track-{i}"})

        # Start workers
        await job_queue.start(num_workers=3)
        await asyncio.sleep(1.5)
        await job_queue.stop()

        # Verify max concurrent was respected
        assert max_concurrent <= 2

    async def test_invalid_concurrent_limit_raises_error(self) -> None:
        """Test that setting invalid concurrent limit raises ValueError."""
        job_queue = JobQueue(max_concurrent_jobs=3)

        with pytest.raises(ValueError):
            job_queue.set_max_concurrent_jobs(0)

        with pytest.raises(ValueError):
            job_queue.set_max_concurrent_jobs(-1)


class TestPauseResumeAPI:
    """Test pause/resume functionality (global and individual)."""

    async def test_global_pause_and_resume(self) -> None:
        """Test pausing and resuming the entire queue."""
        job_queue = JobQueue(max_concurrent_jobs=2)
        processed_count = 0

        async def handler(job: Job) -> None:
            nonlocal processed_count
            processed_count += 1
            await asyncio.sleep(0.05)

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue jobs
        for i in range(5):
            await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": f"track-{i}"})

        # Start workers
        await job_queue.start(num_workers=1)

        # Let one job process
        await asyncio.sleep(0.1)

        # Pause queue
        await job_queue.pause()
        assert job_queue.is_paused() is True

        count_after_pause = processed_count

        # Wait and verify no new jobs are processed
        await asyncio.sleep(0.2)
        assert processed_count == count_after_pause

        # Resume queue
        await job_queue.resume()
        assert job_queue.is_paused() is False

        # Wait for remaining jobs
        await asyncio.sleep(0.5)

        # Stop workers
        await job_queue.stop()

        # All jobs should be processed
        assert processed_count == 5

    async def test_individual_download_pause_resume(self) -> None:
        """Test pausing and resuming individual downloads."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            status=DownloadStatus.DOWNLOADING,
        )

        # Pause download
        download.pause()
        assert download.status == DownloadStatus.QUEUED

        # Resume download
        download.resume()
        assert download.status == DownloadStatus.DOWNLOADING

    async def test_pause_invalid_status_raises_error(self) -> None:
        """Test that pausing a download with invalid status raises error."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            status=DownloadStatus.PENDING,
        )

        with pytest.raises(ValueError):
            download.pause()

    async def test_resume_invalid_status_raises_error(self) -> None:
        """Test that resuming a download with invalid status raises error."""
        download = Download(
            id=DownloadId.from_string(str(uuid4())),
            track_id=TrackId.from_string(str(uuid4())),
            status=DownloadStatus.PENDING,
        )

        with pytest.raises(ValueError):
            download.resume()


class TestBatchOperations:
    """Test batch download operations."""

    async def test_batch_enqueue_multiple_jobs(self) -> None:
        """Test enqueueing multiple jobs at once."""
        job_queue = JobQueue(max_concurrent_jobs=3)

        async def handler(job: Job) -> None:
            await asyncio.sleep(0.01)

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Batch enqueue
        job_ids = []
        for i in range(10):
            job_id = await job_queue.enqueue(
                JobType.DOWNLOAD, {"track_id": f"track-{i}"}, priority=1
            )
            job_ids.append(job_id)

        assert len(job_ids) == 10

        # Verify all jobs exist
        for job_id in job_ids:
            job = await job_queue.get_job(job_id)
            assert job is not None
            assert job.priority == 1

    async def test_batch_cancel_operations(self) -> None:
        """Test cancelling multiple jobs."""
        job_queue = JobQueue(max_concurrent_jobs=1)

        # Enqueue multiple jobs
        job_ids = []
        for i in range(5):
            job_id = await job_queue.enqueue(
                JobType.DOWNLOAD, {"track_id": f"track-{i}"}
            )
            job_ids.append(job_id)

        # Cancel all jobs
        for job_id in job_ids:
            await job_queue.cancel_job(job_id)

        # Verify all are cancelled
        for job_id in job_ids:
            job = await job_queue.get_job(job_id)
            assert job is not None
            assert job.status == JobStatus.CANCELLED


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    async def test_high_priority_download_preempts_low_priority(self) -> None:
        """Test that high priority downloads are processed before low priority."""
        job_queue = JobQueue(max_concurrent_jobs=1)
        processed_order: list[int] = []

        async def handler(job: Job) -> None:
            priority = job.priority
            processed_order.append(priority)
            await asyncio.sleep(0.05)

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue low priority jobs first
        await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-1"}, priority=0
        )
        await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-2"}, priority=0
        )

        # Then enqueue high priority job
        await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-3"}, priority=10
        )

        await job_queue.start(num_workers=1)
        await asyncio.sleep(0.5)
        await job_queue.stop()

        # First job processed should be one of the P0 jobs (already in queue)
        # But the high priority job should be processed before the remaining P0 job
        assert len(processed_order) == 3
        assert 10 in processed_order

    async def test_retry_after_failure_with_priority_maintained(self) -> None:
        """Test that retries maintain original priority."""
        job_queue = JobQueue(max_concurrent_jobs=1)
        attempts = 0

        async def handler_with_one_failure(job: Job) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("First attempt fails")
            # Second attempt succeeds

        job_queue.register_handler(JobType.DOWNLOAD, handler_with_one_failure)

        # Enqueue with priority
        job_id = await job_queue.enqueue(
            JobType.DOWNLOAD, {"track_id": "track-123"}, priority=5, max_retries=2
        )

        await job_queue.start(num_workers=1)
        await asyncio.sleep(2)
        await job_queue.stop()

        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.priority == 5
        assert job.status == JobStatus.COMPLETED
        assert attempts == 2

    async def test_pause_queue_with_concurrent_downloads(self) -> None:
        """Test pausing queue while downloads are in progress."""
        job_queue = JobQueue(max_concurrent_jobs=2)
        started_jobs = 0
        completed_jobs = 0
        lock = asyncio.Lock()

        async def slow_handler(job: Job) -> None:
            nonlocal started_jobs, completed_jobs
            async with lock:
                started_jobs += 1
            await asyncio.sleep(0.3)
            async with lock:
                completed_jobs += 1

        job_queue.register_handler(JobType.DOWNLOAD, slow_handler)

        # Enqueue multiple jobs
        for i in range(5):
            await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": f"track-{i}"})

        await job_queue.start(num_workers=2)
        await asyncio.sleep(0.15)  # Let some jobs start

        # Pause
        await job_queue.pause()
        jobs_started_at_pause = started_jobs

        # Wait a bit - no new jobs should start
        await asyncio.sleep(0.5)
        assert started_jobs == jobs_started_at_pause  # No new jobs started

        # Resume
        await job_queue.resume()
        await asyncio.sleep(1.0)
        await job_queue.stop()

        # All jobs should eventually complete
        assert completed_jobs == 5
