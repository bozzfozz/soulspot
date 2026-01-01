"""Worker system - Background job processing."""

from soulspot.application.workers.automation_workers import (
    AutomationWorkerManager,
    DiscographyWorker,
    QualityUpgradeWorker,
    WatchlistWorker,
)
from soulspot.application.workers.download_monitor_worker import DownloadMonitorWorker
from soulspot.application.workers.download_status_sync_worker import (
    DownloadStatusSyncWorker,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import JobQueue, JobStatus, JobType
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
from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker
from soulspot.application.workers.unified_library_worker import (
    TaskPriority,
    TaskScheduler,
    TaskType,
    UnifiedLibraryManager,
)

__all__ = [
    # Job Queue
    "JobQueue",
    "JobStatus",
    "JobType",
    # Worker Orchestrator
    "WorkerOrchestrator",
    "WorkerState",
    "get_orchestrator",
    "reset_orchestrator",
    # Persistent Job Queue
    "PersistentJobQueue",
    "PersistentJobQueueStats",
    "create_persistent_job_queue",
    # Core Workers
    "DownloadWorker",
    "DownloadMonitorWorker",
    "TokenRefreshWorker",
    "QueueDispatcherWorker",
    "create_queue_dispatcher_worker",
    "DownloadStatusSyncWorker",
    # Retry System
    "RetrySchedulerWorker",
    "create_retry_scheduler_worker",
    # Automation Workers
    "AutomationWorkerManager",
    "WatchlistWorker",
    "DiscographyWorker",
    "QualityUpgradeWorker",
    # UnifiedLibraryManager - THE central library worker
    "UnifiedLibraryManager",
    "TaskScheduler",
    "TaskType",
    "TaskPriority",
]
