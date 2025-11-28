"""Worker system - Background job processing."""

from soulspot.application.workers.automation_workers import (
    AutomationWorkerManager,
    DiscographyWorker,
    QualityUpgradeWorker,
    WatchlistWorker,
)
from soulspot.application.workers.cleanup_worker import CleanupWorker
from soulspot.application.workers.download_monitor_worker import DownloadMonitorWorker
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.duplicate_detector_worker import (
    DuplicateDetectorWorker,
)
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.application.workers.metadata_worker import MetadataWorker
from soulspot.application.workers.playlist_sync_worker import PlaylistSyncWorker
from soulspot.application.workers.spotify_sync_worker import SpotifySyncWorker
from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker

__all__ = [
    # Job Queue
    "JobQueue",
    "JobStatus",
    "JobType",
    # Core Workers
    "DownloadWorker",
    "DownloadMonitorWorker",
    "MetadataWorker",
    "PlaylistSyncWorker",
    "SpotifySyncWorker",
    "TokenRefreshWorker",
    # Automation Workers
    "AutomationWorkerManager",
    "WatchlistWorker",
    "DiscographyWorker",
    "QualityUpgradeWorker",
    # Maintenance Workers
    "CleanupWorker",
    "DuplicateDetectorWorker",
]
