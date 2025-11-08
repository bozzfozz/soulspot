"""Tests for Job Queue system."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from soulspot.application.workers.job_queue import Job, JobQueue, JobStatus, JobType


class TestJob:
    """Test Job dataclass."""

    def test_create_job(self) -> None:
        """Test creating a job."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
        )

        assert job.id == "job-123"
        assert job.job_type == JobType.DOWNLOAD
        assert job.payload == {"track_id": "track-123"}
        assert job.status == JobStatus.PENDING
        assert job.retries == 0
        assert job.max_retries == 3

    def test_mark_running(self) -> None:
        """Test marking job as running."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
        )

        job.mark_running()

        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    def test_mark_completed(self) -> None:
        """Test marking job as completed."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
        )

        job.mark_completed(result={"status": "success"})

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.result == {"status": "success"}

    def test_mark_failed(self) -> None:
        """Test marking job as failed."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
        )

        job.mark_failed(error="Test error")

        assert job.status == JobStatus.FAILED
        assert job.completed_at is not None
        assert job.error == "Test error"
        assert job.retries == 1

    def test_mark_cancelled(self) -> None:
        """Test marking job as cancelled."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
        )

        job.mark_cancelled()

        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None

    def test_should_retry_when_failed_with_retries_left(self) -> None:
        """Test should retry when job failed with retries left."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
            max_retries=3,
        )

        job.mark_failed("Test error")

        assert job.should_retry() is True

    def test_should_not_retry_when_max_retries_reached(self) -> None:
        """Test should not retry when max retries reached."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
            max_retries=2,
        )

        # Fail twice
        job.mark_failed("Test error 1")
        job.mark_failed("Test error 2")

        assert job.should_retry() is False

    def test_should_not_retry_when_not_failed(self) -> None:
        """Test should not retry when job not failed."""
        job = Job(
            id="job-123",
            job_type=JobType.DOWNLOAD,
            payload={},
        )

        assert job.should_retry() is False


class TestJobQueue:
    """Test JobQueue."""

    @pytest.fixture
    def job_queue(self) -> JobQueue:
        """Create job queue instance."""
        return JobQueue(max_concurrent_jobs=3)

    async def test_enqueue_job(self, job_queue: JobQueue) -> None:
        """Test enqueueing a job."""
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
        )

        assert job_id is not None
        assert len(job_id) > 0

        # Check job was added
        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.job_type == JobType.DOWNLOAD
        assert job.status == JobStatus.PENDING

    async def test_get_job(self, job_queue: JobQueue) -> None:
        """Test getting a job by ID."""
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
        )

        job = await job_queue.get_job(job_id)

        assert job is not None
        assert job.id == job_id

    async def test_get_nonexistent_job(self, job_queue: JobQueue) -> None:
        """Test getting a non-existent job returns None."""
        job = await job_queue.get_job("nonexistent-job-id")
        assert job is None

    async def test_cancel_job(self, job_queue: JobQueue) -> None:
        """Test cancelling a job."""
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
        )

        success = await job_queue.cancel_job(job_id)

        assert success is True

        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.CANCELLED

    async def test_cancel_nonexistent_job(self, job_queue: JobQueue) -> None:
        """Test cancelling non-existent job returns False."""
        success = await job_queue.cancel_job("nonexistent-job-id")
        assert success is False

    async def test_register_handler(self, job_queue: JobQueue) -> None:
        """Test registering a job handler."""
        handler = AsyncMock()

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Verify handler was registered
        assert JobType.DOWNLOAD in job_queue._handlers
        assert job_queue._handlers[JobType.DOWNLOAD] == handler

    async def test_process_job_success(self, job_queue: JobQueue) -> None:
        """Test successful job processing."""
        # Register handler
        async def handler(job: Job) -> str:
            return "success"

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue job
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
        )

        # Start workers
        await job_queue.start(num_workers=1)

        # Wait for job to complete
        await asyncio.sleep(0.2)

        # Stop workers
        await job_queue.stop()

        # Check job status
        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.result == "success"

    async def test_process_job_failure(self, job_queue: JobQueue) -> None:
        """Test job processing failure."""
        # Register handler that raises exception
        async def handler(job: Job) -> None:
            raise ValueError("Test error")

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue job with max_retries=1
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": "track-123"},
            max_retries=1,
        )

        # Start workers
        await job_queue.start(num_workers=1)

        # Wait for job to fail and retries to complete
        await asyncio.sleep(0.2)

        # Stop workers
        await job_queue.stop()

        # Check job status
        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert "Test error" in str(job.error)
        assert job.retries >= 1

    async def test_start_and_stop_workers(self, job_queue: JobQueue) -> None:
        """Test starting and stopping workers."""
        # Register a simple handler
        async def handler(job: Job) -> None:
            await asyncio.sleep(0.01)
            return None

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Start workers
        await job_queue.start(num_workers=2)

        # Verify workers are running
        assert len(job_queue._workers) == 2
        assert not job_queue._shutdown

        # Stop workers
        await job_queue.stop()

        # Verify workers are stopped
        assert job_queue._shutdown

    async def test_queue_size(self, job_queue: JobQueue) -> None:
        """Test getting queue size."""
        # Enqueue several jobs
        await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": "1"})
        await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": "2"})
        await job_queue.enqueue(JobType.METADATA_ENRICHMENT, {"track_id": "3"})

        # Check total jobs
        assert len(job_queue._jobs) == 3

    async def test_concurrent_job_processing(self, job_queue: JobQueue) -> None:
        """Test that jobs are processed concurrently."""
        completed_count = 0
        lock = asyncio.Lock()

        async def simple_handler(job: Job) -> None:
            nonlocal completed_count
            await asyncio.sleep(0.1)
            async with lock:
                completed_count += 1
            return None

        job_queue.register_handler(JobType.DOWNLOAD, simple_handler)

        # Enqueue jobs
        for i in range(5):
            await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": f"track-{i}"})

        # Start workers
        await job_queue.start(num_workers=3)

        # Wait for all jobs to complete
        await asyncio.sleep(0.8)

        # Stop workers
        await job_queue.stop()

        # Verify jobs were completed
        assert completed_count == 5

    async def test_wait_for_job(self, job_queue: JobQueue) -> None:
        """Test waiting for job completion."""
        # Register handler
        async def handler(job: Job) -> str:
            await asyncio.sleep(0.1)
            return "done"

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue job
        job_id = await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": "track-123"})

        # Start workers
        await job_queue.start(num_workers=1)

        # Wait for job
        try:
            job = await job_queue.wait_for_job(job_id, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # Stop workers
        await job_queue.stop()

        # Check job completed
        job = await job_queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.result == "done"

    async def test_wait_for_job_timeout(self, job_queue: JobQueue) -> None:
        """Test waiting for job with timeout."""
        # Register slow handler
        async def handler(job: Job) -> None:
            await asyncio.sleep(2.0)
            return None

        job_queue.register_handler(JobType.DOWNLOAD, handler)

        # Enqueue job
        job_id = await job_queue.enqueue(JobType.DOWNLOAD, {"track_id": "track-123"})

        # Start workers
        await job_queue.start(num_workers=1)

        # Wait for job with short timeout
        try:
            job = await job_queue.wait_for_job(job_id, timeout=0.1)
        except asyncio.TimeoutError:
            job = await job_queue.get_job(job_id)

        # Stop workers
        await job_queue.stop()

        # Job should still be running or pending
        assert job is not None
        assert job.status in [JobStatus.RUNNING, JobStatus.PENDING]
