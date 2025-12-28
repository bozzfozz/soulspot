"""Worker system - Background job processing."""

from soulspot.application.workers.automation_workers import (
    AutomationWorkerManager,
    DiscographyWorker,
    QualityUpgradeWorker,
    WatchlistWorker,
)
from soulspot.application.workers.cleanup_worker import CleanupWorker
from soulspot.application.workers.deezer_sync_worker import DeezerSyncWorker
from soulspot.application.workers.download_monitor_worker import DownloadMonitorWorker
from soulspot.application.workers.download_status_sync_worker import (
    DownloadStatusSyncWorker,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.duplicate_detector_worker import (
    DuplicateDetectorWorker,
)
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
from soulspot.application.workers.library_discovery_worker import LibraryDiscoveryWorker
from soulspot.application.workers.new_releases_sync_worker import (
    NewReleasesCache,
    NewReleasesSyncWorker,
)
from soulspot.application.workers.orchestrator import (
    WorkerOrchestrator,
    WorkerState,
    get_orchestrator,
    reset_orchestrator,
)
from soulspot.application.workers.persistent_job_queue import (
    PersistentJobQueue,
    PersistentJobQueueStats,
    create_persistent_job_queue,
)
from soulspot.application.workers.queue_dispatcher_worker import (
    QueueDispatcherWorker,
    create_queue_dispatcher_worker,
)
from soulspot.application.workers.retry_scheduler_worker import (
    RetrySchedulerWorker,
    create_retry_scheduler_worker,
)
from soulspot.application.workers.spotify_sync_worker import SpotifySyncWorker
from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker
from soulspot.application.workers.ImageWorker import ImageWorker

# ⚠️ DEPRECATED Workers - Import triggers deprecation warning
# These are kept for backwards compatibility only and will be removed
# from soulspot.application.workers.metadata_worker import MetadataWorker
# from soulspot.application.workers.playlist_sync_worker import PlaylistSyncWorker
# from soulspot.application.workers.post_processing_worker import PostProcessingWorker

__all__ = [
    # Job Queue
    "JobQueue",
    "JobStatus",
    "JobType",
    # Worker Orchestrator (NEW!)
    "WorkerOrchestrator",
    "WorkerState",
    "get_orchestrator",
    "reset_orchestrator",
    # Persistent Job Queue (survives restarts!)
    "PersistentJobQueue",
    "PersistentJobQueueStats",
    "create_persistent_job_queue",
    # Core Workers
    "DeezerSyncWorker",
    "DownloadWorker",
    "DownloadMonitorWorker",
    "SpotifySyncWorker",
    "TokenRefreshWorker",
    "QueueDispatcherWorker",
    "create_queue_dispatcher_worker",
    "DownloadStatusSyncWorker",
    # Retry System
    "RetrySchedulerWorker",
    "create_retry_scheduler_worker",
    # New Releases
    "NewReleasesSyncWorker",
    "NewReleasesCache",
    # Automation Workers
    "AutomationWorkerManager",
    "WatchlistWorker",
    "DiscographyWorker",
    "QualityUpgradeWorker",
    # Maintenance Workers
    "CleanupWorker",
    "DuplicateDetectorWorker",
    "LibraryDiscoveryWorker",  # NEW: Unified enrichment + discography discovery
    "ImageWorker",  # Image repair/backfill worker
    # ⚠️ DEPRECATED - these exports are removed, use replacements:
    # "MetadataWorker" → Use LibraryDiscoveryWorker
    # "PlaylistSyncWorker" → Use SpotifySyncWorker or API endpoints
    # "PostProcessingWorker" → Use AutoImportService
]
