"""Integration tests for download management endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from soulspot.application.workers.job_queue import JobQueue
from soulspot.config import Settings
from soulspot.main import create_app

# Mark all tests in this module as slow
pytestmark = pytest.mark.slow


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        app_env="development",
        debug=True,
        database={"url": "sqlite+aiosqlite:///:memory:"},
        download={
            "max_concurrent_downloads": 3,
            "default_max_retries": 3,
            "enable_priority_queue": True,
        },
        observability={
            "enable_dependency_health_checks": False,
        },
    )


@pytest.fixture
def mock_job_queue():
    """Create a mock job queue."""
    job_queue = AsyncMock(spec=JobQueue)
    job_queue.is_paused.return_value = False
    job_queue.get_max_concurrent_jobs.return_value = 3
    job_queue.get_stats.return_value = {
        "total_jobs": 5,
        "pending": 2,
        "running": 1,
        "completed": 1,
        "failed": 1,
        "cancelled": 0,
        "queue_size": 2,
    }
    job_queue.pause = AsyncMock()
    job_queue.resume = AsyncMock()
    return job_queue


@pytest.fixture
def mock_download_worker():
    """Create a mock download worker."""
    worker = AsyncMock()
    worker.enqueue_download = AsyncMock(return_value="job-123")
    return worker


@pytest.fixture
def app_with_mocks(test_settings, mock_job_queue, mock_download_worker):
    """Create app with mocked dependencies."""
    from contextlib import asynccontextmanager

    app = create_app(test_settings)

    # Override the lifespan to inject mocks instead of real instances
    @asynccontextmanager
    async def mock_lifespan(app_instance):
        # Create a mock DB with async generator support
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_session = AsyncMock()

        # Make get_session return an async generator
        async def mock_get_session():
            yield mock_session

        mock_db.get_session = mock_get_session

        # Set up mocks
        app_instance.state.job_queue = mock_job_queue
        app_instance.state.download_worker = mock_download_worker
        app_instance.state.db = mock_db

        yield

        # Cleanup (mocks don't need cleanup)

    app.router.lifespan_context = mock_lifespan
    return app


@pytest.fixture
def client(app_with_mocks):
    """Create test client with mocked dependencies."""
    with TestClient(app_with_mocks) as test_client:
        yield test_client


class TestDownloadQueueManagement:
    """Test download queue management endpoints."""

    def test_pause_downloads(self, client, mock_job_queue):
        """Test pausing download queue."""
        response = client.post("/api/downloads/pause")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"
        assert "paused successfully" in data["message"].lower()
        mock_job_queue.pause.assert_called_once()

    def test_resume_downloads(self, client, mock_job_queue):
        """Test resuming download queue."""
        response = client.post("/api/downloads/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "resumed successfully" in data["message"].lower()
        mock_job_queue.resume.assert_called_once()

    def test_get_queue_status(self, client, mock_job_queue):
        """Test getting queue status."""
        response = client.get("/api/downloads/status")
        assert response.status_code == 200
        data = response.json()

        # Verify status structure
        assert "paused" in data
        assert "max_concurrent_downloads" in data
        assert "active_downloads" in data
        assert "queued_downloads" in data
        assert "total_jobs" in data
        assert "completed" in data
        assert "failed" in data
        assert "cancelled" in data

        # Verify values
        assert data["paused"] is False
        assert data["max_concurrent_downloads"] == 3
        assert data["active_downloads"] == 1
        assert data["queued_downloads"] == 2
        assert data["total_jobs"] == 5

        mock_job_queue.is_paused.assert_called_once()
        mock_job_queue.get_max_concurrent_jobs.assert_called_once()
        mock_job_queue.get_stats.assert_called_once()


class TestBatchDownloads:
    """Test batch download operations."""

    def test_batch_download_success(self, client, mock_download_worker):
        """Test batch download with valid track IDs."""
        from uuid import uuid4

        track_ids = [str(uuid4()), str(uuid4()), str(uuid4())]

        # Mock multiple job IDs
        mock_download_worker.enqueue_download = AsyncMock(
            side_effect=["job-1", "job-2", "job-3"]
        )

        response = client.post(
            "/api/downloads/batch",
            json={"track_ids": track_ids, "priority": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tracks"] == 3
        assert len(data["job_ids"]) == 3
        assert data["job_ids"] == ["job-1", "job-2", "job-3"]
        assert "batch download initiated" in data["message"].lower()

        # Verify enqueue_download was called for each track
        assert mock_download_worker.enqueue_download.call_count == 3

    def test_batch_download_empty_list(self, client):
        """Test batch download with empty track list."""
        response = client.post(
            "/api/downloads/batch",
            json={"track_ids": [], "priority": 0},
        )

        assert response.status_code == 400
        assert "at least one track" in response.json()["detail"].lower()

    def test_batch_download_invalid_track_id(self, client, mock_download_worker):
        """Test batch download with invalid track ID."""
        track_ids = ["invalid-track-id"]

        response = client.post(
            "/api/downloads/batch",
            json={"track_ids": track_ids, "priority": 0},
        )

        # Should return 400 for invalid track ID
        assert response.status_code == 400
        assert "invalid track id" in response.json()["detail"].lower()

    def test_batch_download_with_priority(self, client, mock_download_worker):
        """Test batch download with custom priority."""
        from uuid import uuid4

        track_ids = [str(uuid4())]
        mock_download_worker.enqueue_download = AsyncMock(return_value="job-1")

        response = client.post(
            "/api/downloads/batch",
            json={"track_ids": track_ids, "priority": 2},
        )

        assert response.status_code == 200

        # Verify priority was passed correctly
        mock_download_worker.enqueue_download.assert_called_once()
        call_kwargs = mock_download_worker.enqueue_download.call_args[1]
        assert call_kwargs["priority"] == 2


class TestDownloadQueueIntegration:
    """Test integration between endpoints and queue."""

    def test_queue_status_reflects_pause(self, client, mock_job_queue):
        """Test that queue status reflects paused state."""
        # Set queue to paused
        mock_job_queue.is_paused.return_value = True

        response = client.get("/api/downloads/status")
        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is True

    def test_concurrent_downloads_configuration(self, client, mock_job_queue):
        """Test that max concurrent downloads is properly configured."""
        mock_job_queue.get_max_concurrent_jobs.return_value = 2

        response = client.get("/api/downloads/status")
        assert response.status_code == 200
        data = response.json()
        assert data["max_concurrent_downloads"] == 2
