"""Worker system - Background work item processing.

NAMING CONVENTION:
- "WorkItem" is the preferred user-facing term (clearer, more intuitive)
- "Job" is the internal implementation term (historical, widely used)
- Both refer to the same concept: a unit of work to be processed
- Use WorkItem in UI, docs, and new code; Job in internal implementation
"""

from soulspot.application.workers.automation_workers import (
    AutomationWorkerManager,
    DiscographyWorker,
    QualityUpgradeWorker,
    WatchlistWorker,
)
from soulspot.application.workers.download_queue_worker import DownloadQueueWorker
from soulspot.application.workers.download_status_worker import DownloadStatusWorker
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import (
    Job,
    JobQueue,
    JobStatus,
    JobType,
    # WorkItem aliases
    WorkItem,
    WorkItemQueue,
    WorkItemStatus,
    WorkItemType,
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
    PersistentWorkItemQueue,
    create_persistent_job_queue,
)
from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker
from soulspot.application.workers.unified_library_worker import (
    TaskPriority,
    TaskScheduler,
    TaskType,
    UnifiedLibraryManager,
)

__all__ = [
    # Job Queue (internal names)
    "Job",
    "JobQueue",
    "JobStatus",
    "JobType",
    # WorkItem Queue (user-friendly aliases)
    "WorkItem",
    "WorkItemQueue",
    "WorkItemStatus",
    "WorkItemType",
    # Worker Orchestrator
    "WorkerOrchestrator",
    "WorkerState",
    "get_orchestrator",
    "reset_orchestrator",
    # Persistent Job Queue
    "PersistentJobQueue",
    "PersistentJobQueueStats",
    "PersistentWorkItemQueue",  # Alias
    "create_persistent_job_queue",
    # Core Workers
    "DownloadWorker",
    "TokenRefreshWorker",
    # Consolidated Download Workers (Jan 2026)
    # Replaces: DownloadMonitorWorker, DownloadStatusSyncWorker,
    #           QueueDispatcherWorker, RetrySchedulerWorker
    "DownloadStatusWorker",  # slskd status → JobQueue + DB
    "DownloadQueueWorker",  # WAITING↔FAILED↔PENDING queue management
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
