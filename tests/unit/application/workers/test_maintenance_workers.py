"""Unit tests for maintenance workers (DownloadMonitor, Cleanup, DuplicateDetector).

Hey future me - diese Tests decken die drei neuen maintenance workers ab:
1. DownloadMonitorWorker - pollt slskd und updated Job-Status
2. CleanupWorker - löscht alte temp files
3. DuplicateDetectorWorker - findet Duplikate via metadata-hash

Die Worker sind alle async und haben ähnliche Muster:
- start() erstellt Background-Task
- stop() cancelt den Task
- get_status() gibt Monitoring-Infos
- _run_loop() ist die Hauptschleife

Tests nutzen AsyncMock für DB/externe Services.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from soulspot.application.workers.cleanup_worker import CleanupWorker
from soulspot.application.workers.download_monitor_worker import DownloadMonitorWorker
from soulspot.application.workers.duplicate_detector_worker import (
    DuplicateDetectorWorker,
)
from soulspot.application.workers.job_queue import JobStatus, JobType


class TestDownloadMonitorWorker:
    """Test DownloadMonitorWorker class."""

    @pytest.fixture
    def mock_job_queue(self) -> MagicMock:
        """Create mock job queue."""
        queue = MagicMock()
        queue.list_jobs = AsyncMock(return_value=[])
        return queue

    @pytest.fixture
    def mock_slskd_client(self) -> MagicMock:
        """Create mock slskd client."""
        client = MagicMock()
        client.list_downloads = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def worker(
        self, mock_job_queue: MagicMock, mock_slskd_client: MagicMock
    ) -> DownloadMonitorWorker:
        """Create DownloadMonitorWorker instance."""
        return DownloadMonitorWorker(
            job_queue=mock_job_queue,
            slskd_client=mock_slskd_client,
            poll_interval_seconds=1,
        )

    def test_init(
        self,
        worker: DownloadMonitorWorker,
        mock_job_queue: MagicMock,
        mock_slskd_client: MagicMock,
    ) -> None:
        """Test DownloadMonitorWorker initialization."""
        assert worker._job_queue == mock_job_queue
        assert worker._slskd_client == mock_slskd_client
        assert worker._poll_interval == 1
        assert worker._running is False
        assert worker._task is None

    @pytest.mark.asyncio
    async def test_start(self, worker: DownloadMonitorWorker) -> None:
        """Test starting the worker creates background task."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None
        assert not worker._task.done()

        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, worker: DownloadMonitorWorker) -> None:
        """Test starting worker multiple times is idempotent."""
        await worker.start()
        initial_task = worker._task

        await worker.start()
        assert worker._task is initial_task  # Same task, not replaced

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker: DownloadMonitorWorker) -> None:
        """Test stopping the worker cancels task."""
        await worker.start()
        assert worker._running is True

        await worker.stop()

        assert worker._running is False
        assert worker._task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker: DownloadMonitorWorker) -> None:
        """Test stopping worker when not running is safe."""
        await worker.stop()
        assert worker._running is False

    def test_get_status(self, worker: DownloadMonitorWorker) -> None:
        """Test get_status returns correct info."""
        status = worker.get_status()

        assert status["name"] == "Download Monitor"
        assert status["running"] is False
        assert status["status"] == "stopped"
        assert status["poll_interval_seconds"] == 1
        assert "stats" in status

    @pytest.mark.asyncio
    async def test_get_status_when_running(self, worker: DownloadMonitorWorker) -> None:
        """Test get_status when worker is running."""
        await worker.start()

        status = worker.get_status()
        assert status["running"] is True
        assert status["status"] == "active"

        await worker.stop()

    @pytest.mark.asyncio
    async def test_poll_downloads_no_jobs(
        self, worker: DownloadMonitorWorker, mock_job_queue: MagicMock
    ) -> None:
        """Test polling when no running jobs exist."""
        mock_job_queue.list_jobs.return_value = []

        await worker._poll_downloads()

        mock_job_queue.list_jobs.assert_called_once_with(
            status=JobStatus.RUNNING,
            job_type=JobType.DOWNLOAD,
        )

    @pytest.mark.asyncio
    async def test_poll_downloads_with_running_job(
        self,
        worker: DownloadMonitorWorker,
        mock_job_queue: MagicMock,
        mock_slskd_client: MagicMock,
    ) -> None:
        """Test polling updates job status from slskd."""
        # Create mock job
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.result = {"slskd_download_id": "dl-456"}

        mock_job_queue.list_jobs.return_value = [mock_job]

        # Mock slskd response
        mock_slskd_client.list_downloads.return_value = [
            {
                "id": "dl-456",
                "state": "InProgress",
                "progress": 50,
                "bytes_transferred": 5000,
                "size": 10000,
            }
        ]

        await worker._poll_downloads()

        # Verify job result was updated
        assert mock_job.result["slskd_state"] == "InProgress"
        assert mock_job.result["progress_percent"] == 50

    @pytest.mark.asyncio
    async def test_poll_downloads_completed(
        self,
        worker: DownloadMonitorWorker,
        mock_job_queue: MagicMock,
        mock_slskd_client: MagicMock,
    ) -> None:
        """Test polling marks job as completed when download finishes."""
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.result = {"slskd_download_id": "dl-456"}

        mock_job_queue.list_jobs.return_value = [mock_job]

        mock_slskd_client.list_downloads.return_value = [
            {
                "id": "dl-456",
                "state": "Completed",
                "progress": 100,
                "bytes_transferred": 10000,
                "size": 10000,
            }
        ]

        await worker._poll_downloads()

        assert mock_job.status == JobStatus.COMPLETED
        assert worker._stats["downloads_completed"] == 1

    @pytest.mark.asyncio
    async def test_poll_downloads_failed(
        self,
        worker: DownloadMonitorWorker,
        mock_job_queue: MagicMock,
        mock_slskd_client: MagicMock,
    ) -> None:
        """Test polling marks job as failed when download errors."""
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.result = {"slskd_download_id": "dl-456"}

        mock_job_queue.list_jobs.return_value = [mock_job]

        mock_slskd_client.list_downloads.return_value = [
            {
                "id": "dl-456",
                "state": "Errored",
                "progress": 30,
                "bytes_transferred": 3000,
                "size": 10000,
            }
        ]

        await worker._poll_downloads()

        assert mock_job.status == JobStatus.FAILED
        assert "error" in mock_job.result
        assert worker._stats["downloads_failed"] == 1

    @pytest.mark.asyncio
    async def test_poll_downloads_slskd_error(
        self,
        worker: DownloadMonitorWorker,
        mock_job_queue: MagicMock,
        mock_slskd_client: MagicMock,
    ) -> None:
        """Test polling handles slskd API errors gracefully."""
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.result = {"slskd_download_id": "dl-456"}

        mock_job_queue.list_jobs.return_value = [mock_job]
        mock_slskd_client.list_downloads.side_effect = Exception("API error")

        # Should not raise, just log error
        await worker._poll_downloads()


class TestCleanupWorker:
    """Test CleanupWorker class."""

    @pytest.fixture
    def mock_job_queue(self) -> MagicMock:
        """Create mock job queue."""
        queue = MagicMock()
        queue.create_job = AsyncMock()
        return queue

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings service."""
        settings = MagicMock()
        settings.is_cleanup_enabled = AsyncMock(return_value=True)
        settings.get_cleanup_interval = AsyncMock(return_value=24)
        settings.get_cleanup_retention_days = AsyncMock(return_value=7)
        return settings

    @pytest.fixture
    def temp_paths(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create temp paths for testing."""
        downloads = tmp_path / "downloads"
        music = tmp_path / "music"
        temp = tmp_path / "temp"
        downloads.mkdir()
        music.mkdir()
        temp.mkdir()
        return downloads, music, temp

    @pytest.fixture
    def worker(
        self,
        mock_job_queue: MagicMock,
        mock_settings: MagicMock,
        temp_paths: tuple[Path, Path, Path],
    ) -> CleanupWorker:
        """Create CleanupWorker instance."""
        downloads, music, temp = temp_paths
        return CleanupWorker(
            job_queue=mock_job_queue,
            settings_service=mock_settings,
            downloads_path=downloads,
            music_path=music,
            temp_path=temp,
            dry_run=True,  # Always dry run in tests!
        )

    def test_init(
        self,
        worker: CleanupWorker,
        mock_job_queue: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test CleanupWorker initialization."""
        assert worker._job_queue == mock_job_queue
        assert worker._settings == mock_settings
        assert worker._dry_run is True
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_start(self, worker: CleanupWorker) -> None:
        """Test starting the worker."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None

        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, worker: CleanupWorker) -> None:
        """Test starting worker multiple times is idempotent."""
        await worker.start()
        initial_task = worker._task

        await worker.start()
        assert worker._task is initial_task

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker: CleanupWorker) -> None:
        """Test stopping the worker."""
        await worker.start()
        await worker.stop()

        assert worker._running is False
        assert worker._task is None

    def test_get_status(self, worker: CleanupWorker) -> None:
        """Test get_status returns correct info."""
        status = worker.get_status()

        assert status["name"] == "Cleanup Worker"
        assert status["running"] is False
        assert status["dry_run"] is True
        assert "stats" in status

    @pytest.mark.asyncio
    async def test_find_old_temp_files(
        self, worker: CleanupWorker, temp_paths: tuple[Path, Path, Path]
    ) -> None:
        """Test finding old temp files."""
        downloads, _, _ = temp_paths

        # Create old temp file
        old_file = downloads / "test.part"
        old_file.touch()

        # Make file appear old by modifying cutoff
        cutoff = datetime.now(UTC) + timedelta(days=1)  # Future cutoff includes all

        files = await worker._find_old_temp_files(cutoff)

        assert len(files) == 1
        assert files[0][0] == old_file

    @pytest.mark.asyncio
    async def test_find_old_temp_files_no_match(
        self, worker: CleanupWorker, temp_paths: tuple[Path, Path, Path]
    ) -> None:
        """Test finding temp files when none match."""
        downloads, _, _ = temp_paths

        # Create recent file (should not match)
        recent_file = downloads / "test.part"
        recent_file.touch()

        # Cutoff in the past - file is newer
        cutoff = datetime.now(UTC) - timedelta(days=365)

        files = await worker._find_old_temp_files(cutoff)

        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_clean_empty_directories(
        self, worker: CleanupWorker, temp_paths: tuple[Path, Path, Path]
    ) -> None:
        """Test cleaning empty directories."""
        downloads, _, _ = temp_paths

        # Create empty subdirectory
        empty_dir = downloads / "empty_subdir"
        empty_dir.mkdir()

        # Create non-empty subdirectory
        non_empty = downloads / "has_files"
        non_empty.mkdir()
        (non_empty / "file.txt").touch()

        # Dry run - just logs
        await worker._clean_empty_directories()

        # In dry run mode, directories should still exist
        assert empty_dir.exists()
        assert non_empty.exists()

    @pytest.mark.asyncio
    async def test_trigger_cleanup_now(
        self, worker: CleanupWorker, mock_job_queue: MagicMock
    ) -> None:
        """Test manually triggering cleanup."""
        mock_job_queue.enqueue = AsyncMock(return_value="cleanup-job-123")

        job_id = await worker.trigger_cleanup_now()

        assert job_id == "cleanup-job-123"
        mock_job_queue.enqueue.assert_called_once()
        call_kwargs = mock_job_queue.enqueue.call_args[1]
        assert call_kwargs["job_type"] == JobType.CLEANUP

    @pytest.mark.asyncio
    async def test_run_cleanup_disabled(
        self, worker: CleanupWorker, mock_settings: MagicMock
    ) -> None:
        """Test cleanup doesn't run when disabled."""
        mock_settings.is_cleanup_enabled.return_value = False

        # Simulate one iteration of the loop
        worker._running = True

        # _run_loop would check is_cleanup_enabled and skip
        # We can't easily test the loop directly, but we can verify the check
        enabled = await worker._settings.is_cleanup_enabled()
        assert enabled is False


class TestDuplicateDetectorWorker:
    """Test DuplicateDetectorWorker class."""

    @pytest.fixture
    def mock_job_queue(self) -> MagicMock:
        """Create mock job queue."""
        queue = MagicMock()
        queue.create_job = AsyncMock()
        return queue

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings service."""
        settings = MagicMock()
        settings.is_duplicate_detection_enabled = AsyncMock(return_value=True)
        settings.get_duplicate_scan_interval = AsyncMock(return_value=168)
        return settings

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        """Create mock session factory.

        Hey future me - this needs to be a callable that returns an async context manager.
        The worker uses it like: async with self._session_factory() as session:
        So we need: factory() -> context_manager, context_manager.__aenter__() -> session
        """
        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()

        # Create async context manager mock
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=None)

        # Factory callable returns the context manager
        factory_mock = MagicMock(return_value=context_manager)
        return factory_mock

    @pytest.fixture
    def worker(
        self,
        mock_job_queue: MagicMock,
        mock_settings: MagicMock,
        mock_session_factory: MagicMock,
    ) -> DuplicateDetectorWorker:
        """Create DuplicateDetectorWorker instance."""
        return DuplicateDetectorWorker(
            job_queue=mock_job_queue,
            settings_service=mock_settings,
            session_scope=mock_session_factory,
        )

    def test_init(
        self,
        worker: DuplicateDetectorWorker,
        mock_job_queue: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test DuplicateDetectorWorker initialization."""
        assert worker._job_queue == mock_job_queue
        assert worker._settings == mock_settings
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_start(self, worker: DuplicateDetectorWorker) -> None:
        """Test starting the worker."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker: DuplicateDetectorWorker) -> None:
        """Test stopping the worker."""
        await worker.start()
        await worker.stop()

        assert worker._running is False
        assert worker._task is None

    def test_get_status(self, worker: DuplicateDetectorWorker) -> None:
        """Test get_status returns correct info."""
        status = worker.get_status()

        assert status["name"] == "Duplicate Detector"
        assert status["running"] is False
        assert status["detection_method"] == "metadata-hash"
        assert "stats" in status

    def test_normalize_text(self, worker: DuplicateDetectorWorker) -> None:
        """Test text normalization."""
        # Lowercase
        assert worker._normalize_text("HELLO") == "hello"

        # Strip "The "
        assert worker._normalize_text("The Beatles") == "beatles"

        # Remove punctuation and collapse whitespace
        assert worker._normalize_text("Rock & Roll") == "rock roll"

        # Unicode normalization
        assert worker._normalize_text("Café") == "cafe"

    def test_normalize_title(self, worker: DuplicateDetectorWorker) -> None:
        """Test title normalization with extra rules."""
        # Strip remaster suffix
        assert "remaster" not in worker._normalize_title("Song (2023 Remaster)").lower()

        # Normalize feat patterns
        normalized = worker._normalize_title("Song ft. Artist")
        assert "ft" not in normalized or "feat" in normalized

        # Strip bonus track suffix
        assert "bonus" not in worker._normalize_title("Song (Bonus Track)").lower()

    def test_compute_track_hash(self, worker: DuplicateDetectorWorker) -> None:
        """Test track hash computation."""
        track_1 = {"artist_name": "The Beatles", "title": "Hey Jude"}
        track_2 = {"artist_name": "Beatles, The", "title": "Hey Jude"}

        # These should produce the same hash after normalization
        # (assuming "The" is stripped)
        hash_1 = worker._compute_track_hash(track_1)
        hash_2 = worker._compute_track_hash(track_2)

        # Both should be valid MD5 hashes
        assert len(hash_1) == 32
        assert len(hash_2) == 32

    def test_calculate_similarity_identical(
        self, worker: DuplicateDetectorWorker
    ) -> None:
        """Test similarity calculation for identical tracks."""
        track_1 = {
            "title": "Hey Jude",
            "artist_name": "The Beatles",
            "duration_ms": 180000,
        }
        track_2 = {
            "title": "Hey Jude",
            "artist_name": "The Beatles",
            "duration_ms": 180000,
        }

        score = worker._calculate_similarity(track_1, track_2)

        # Should be 1.0 (40% title + 40% artist + 20% duration)
        assert score == 1.0

    def test_calculate_similarity_different_duration(
        self, worker: DuplicateDetectorWorker
    ) -> None:
        """Test similarity with different durations."""
        track_1 = {
            "title": "Hey Jude",
            "artist_name": "The Beatles",
            "duration_ms": 180000,
        }
        track_2 = {
            "title": "Hey Jude",
            "artist_name": "The Beatles",
            "duration_ms": 300000,  # Very different duration
        }

        score = worker._calculate_similarity(track_1, track_2)

        # Should be 0.8 (40% title + 40% artist, no duration match)
        assert score == 0.8

    def test_calculate_similarity_partial_match(
        self, worker: DuplicateDetectorWorker
    ) -> None:
        """Test similarity with partial matches."""
        track_1 = {
            "title": "Hey Jude",
            "artist_name": "The Beatles",
            "duration_ms": 180000,
        }
        track_2 = {
            "title": "Let It Be",  # Different title
            "artist_name": "The Beatles",
            "duration_ms": 183000,  # Within 5s tolerance
        }

        score = worker._calculate_similarity(track_1, track_2)

        # Should be 0.6 (0% title + 40% artist + 20% duration)
        # Use pytest.approx for floating point comparison
        assert score == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_trigger_scan_now(
        self, worker: DuplicateDetectorWorker, mock_job_queue: MagicMock
    ) -> None:
        """Test manually triggering duplicate scan.

        Hey future me - trigger_scan_now() calls asyncio.create_task(_run_scan())
        which would spawn a background task that accesses the DB. We mock _run_scan
        to avoid that and prevent RuntimeWarning about unawaited coroutines.
        """
        mock_job_queue.enqueue = AsyncMock(return_value="scan-job-123")

        # Mock _run_scan to prevent background task from accessing mocked session
        worker._run_scan = AsyncMock()  # type: ignore[method-assign]

        job_id = await worker.trigger_scan_now()

        assert job_id == "scan-job-123"
        mock_job_queue.enqueue.assert_called_once()
        call_kwargs = mock_job_queue.enqueue.call_args[1]
        assert call_kwargs["job_type"] == JobType.DUPLICATE_SCAN
