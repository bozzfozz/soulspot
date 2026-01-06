"""UnifiedLibraryManager - The ONE central Library Worker.

Hey future me - THIS IS IT! The single entry point for ALL library operations.

REPLACES (to be deleted after full migration):
- spotify_sync_worker.py (~1200 lines)
- deezer_sync_worker.py (~350 lines)
- library_discovery_worker.py (~800 lines)
- library_scan_worker.py (~400 lines)
- new_releases_sync_worker.py (~250 lines)
- image_queue_worker.py (~300 lines)
- duplicate_detector_worker.py (~250 lines)
- cleanup_worker.py (~200 lines)
- retry_scheduler_worker.py (~200 lines)
- automation_workers.py (partial, ~150 lines)

ARCHITECTURE:
```
UnifiedLibraryManager
├── TaskScheduler (schedules tasks based on cooldowns)
├── ProviderRouter (routes to correct plugin)
└── Tasks
    ├── ArtistSyncTask (sync followed artists from providers)
    ├── AlbumSyncTask (sync albums for artists)
    ├── TrackSyncTask (sync tracks for albums)
    ├── EnrichmentTask (MusicBrainz, CoverArt, etc.)
    ├── DownloadTask (coordinate with slskd)
    └── CleanupTask (reset failed downloads, remove orphans)
```

STATE MANAGEMENT:
- Uses OwnershipState (owned/discovered/ignored) for entities
- Uses DownloadState (not_needed/pending/downloading/downloaded/failed) for tracks
- All state persisted to DB, survives restarts

FEATURE FLAGS (in app_settings):
- library.use_unified_manager: Enable this worker (default: false)
- library.auto_queue_downloads: Auto-queue tracks on sync (default: false)
- library.sync_cooldown_minutes: Min time between syncs (default: 5)
- library.enrichment_batch_size: Entities per batch (default: 20)

USAGE:
    # In lifecycle.py when use_unified_manager=True:
    manager = UnifiedLibraryManager(
        session_factory=get_session_factory(),
        plugins=plugins,
    )
    await manager.start()

See: docs/architecture/UNIFIED_LIBRARY_WORKER.md for full documentation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from soulspot.infrastructure.observability.log_messages import LogMessages

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.infrastructure.persistence.database import Database
    from soulspot.infrastructure.persistence.write_buffer_cache import WriteBufferCache
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


# =============================================================================
# TASK TYPES
# =============================================================================


class TaskType(str, Enum):
    """Types of tasks the UnifiedLibraryManager can schedule.

    Hey future me - these are the ONLY operations the manager performs!
    Each task type has its own cooldown tracked in task_last_run.
    
    AUTOMATION TASKS (migrated from AutomationWorkerManager):
    - WATCHLIST_CHECK: Check for new releases on watched artists (hourly)
    - DISCOGRAPHY_SCAN: Check for missing albums in discographies (daily)
    - QUALITY_UPGRADE: Find tracks that can be upgraded to better quality (daily)
    
    These automation tasks use longer cooldowns and run with MAINTENANCE priority.
    """

    # === CORE SYNC TASKS ===
    ARTIST_SYNC = "artist_sync"  # Sync followed artists from providers
    ALBUM_SYNC = "album_sync"  # Sync albums for artists
    TRACK_SYNC = "track_sync"  # Sync tracks for albums
    ENRICHMENT = "enrichment"  # MusicBrainz metadata enrichment
    IMAGE_SYNC = "image_sync"  # Download/cache images
    DOWNLOAD = "download"  # Coordinate downloads with slskd
    CLEANUP = "cleanup"  # Reset failed downloads, remove orphans
    
    # === AUTOMATION TASKS (from AutomationWorkerManager) ===
    WATCHLIST_CHECK = "watchlist_check"  # Check for new releases (hourly)
    DISCOGRAPHY_SCAN = "discography_scan"  # Check for missing albums (daily)
    QUALITY_UPGRADE = "quality_upgrade"  # Find quality upgrade opportunities (daily)


class TaskPriority(int, Enum):
    """Priority levels for scheduled tasks.

    Hey future me - lower number = higher priority!
    Critical tasks run first, maintenance last.
    """

    CRITICAL = 0  # Must run immediately (error recovery)
    HIGH = 10  # User-triggered actions
    NORMAL = 50  # Regular background sync
    LOW = 80  # Enrichment, images
    MAINTENANCE = 100  # Cleanup, optimization


# =============================================================================
# TASK SCHEDULER
# =============================================================================


# Task-specific cooldowns in minutes
# Hey future me - WORKER-FIRST PATTERN (Jan 2026)!
# Routes don't fetch from API anymore - Worker is sole source of sync!
# Cooldowns are now AGGRESSIVE to keep DB always up-to-date.
#
# Core sync tasks: Very short cooldowns (1-2 min) for responsive sync
# Automation tasks: Longer cooldowns (1h-24h) to avoid API spam
TASK_COOLDOWNS: dict[TaskType, int] = {
    # === CORE SYNC (aggressive cooldowns - WORKER-FIRST!) ===
    TaskType.ARTIST_SYNC: 2,       # 2 min - quick sync for new follows
    TaskType.ALBUM_SYNC: 2,        # 2 min - follows artist sync quickly
    TaskType.TRACK_SYNC: 2,        # 2 min - follows album sync quickly
    TaskType.ENRICHMENT: 5,        # 5 min - MusicBrainz rate limiting
    TaskType.IMAGE_SYNC: 5,        # 5 min - image downloads
    TaskType.DOWNLOAD: 1,          # 1 min - responsive download queue
    TaskType.CLEANUP: 15,          # 15 min - maintenance task
    
    # === AUTOMATION (long cooldowns, Lidarr-style) ===
    TaskType.WATCHLIST_CHECK: 60,       # 1 hour - check for new releases
    TaskType.DISCOGRAPHY_SCAN: 1440,    # 24 hours - daily discography scan
    TaskType.QUALITY_UPGRADE: 1440,     # 24 hours - daily quality check
}


# Task Dependencies: Which tasks must complete before others can run
# Key = task that depends, Value = list of tasks that must complete first
TASK_DEPENDENCIES: dict[TaskType, list[TaskType]] = {
    # ARTIST_SYNC has no dependencies (runs first)
    TaskType.ARTIST_SYNC: [],
    # ALBUM_SYNC needs artists to exist
    TaskType.ALBUM_SYNC: [TaskType.ARTIST_SYNC],
    # TRACK_SYNC needs albums to exist
    TaskType.TRACK_SYNC: [TaskType.ALBUM_SYNC],
    # ENRICHMENT needs entities to exist
    TaskType.ENRICHMENT: [TaskType.ARTIST_SYNC, TaskType.ALBUM_SYNC],
    # IMAGE_SYNC can run after artists/albums exist
    TaskType.IMAGE_SYNC: [TaskType.ARTIST_SYNC, TaskType.ALBUM_SYNC],
    # DOWNLOAD can run after tracks exist
    TaskType.DOWNLOAD: [TaskType.TRACK_SYNC],
    # CLEANUP runs last (after everything)
    TaskType.CLEANUP: [TaskType.ENRICHMENT, TaskType.IMAGE_SYNC],
    
    # === AUTOMATION TASK DEPENDENCIES ===
    # WATCHLIST_CHECK needs albums synced to find new releases locally
    TaskType.WATCHLIST_CHECK: [TaskType.ALBUM_SYNC],
    # DISCOGRAPHY_SCAN needs artists to be synced
    TaskType.DISCOGRAPHY_SCAN: [TaskType.ARTIST_SYNC],
    # QUALITY_UPGRADE needs tracks to be synced
    TaskType.QUALITY_UPGRADE: [TaskType.TRACK_SYNC],
}


class TaskScheduler:
    """Schedules and tracks task execution with cooldowns AND dependencies.

    Hey future me - this is the BRAIN of the manager!
    - Tracks last run time for each task type
    - Enforces TASK-SPECIFIC cooldowns (from TASK_COOLDOWNS dict)
    - Prioritizes tasks when multiple are due
    - Respects TASK_DEPENDENCIES (topological order)

    Pattern: Simple priority queue with cooldown enforcement.
    No persistent state - all state derived from DB timestamps.
    
    NEW (Lidarr-inspired):
    - Variable cooldowns per task type (1min for downloads, 24h for discography)
    - Dependency-aware scheduling (tasks wait for dependencies)
    
    Tasks only run if their dependencies have completed in this cycle.
    """

    def __init__(self, default_cooldown_minutes: int = 5) -> None:
        """Initialize scheduler.

        Args:
            default_cooldown_minutes: Fallback cooldown if task not in TASK_COOLDOWNS.
        """
        self._default_cooldown_minutes = default_cooldown_minutes
        self._last_run: dict[TaskType, datetime] = {}
        self._running: dict[TaskType, bool] = {}
        # Track completed tasks in current cycle for dependency resolution
        self._completed_this_cycle: set[TaskType] = set()

    def _get_cooldown_minutes(self, task_type: TaskType) -> int:
        """Get cooldown for a specific task type.
        
        Hey future me - uses TASK_COOLDOWNS dict with fallback to default!
        Automation tasks have MUCH longer cooldowns than sync tasks.
        """
        return TASK_COOLDOWNS.get(task_type, self._default_cooldown_minutes)

    def start_new_cycle(self) -> None:
        """Start a new scheduling cycle.
        
        Hey future me - call this at the START of each main loop iteration!
        Clears the completed set so dependencies are checked fresh.
        """
        self._completed_this_cycle = set()

    def can_run(self, task_type: TaskType) -> bool:
        """Check if task can run based on cooldown AND dependencies.

        Args:
            task_type: The task type to check.

        Returns:
            True if cooldown has passed, task is not running, 
            AND all dependencies have completed in this cycle.
        """
        # Check if already running
        if self._running.get(task_type, False):
            return False

        # Check task-specific cooldown (Lidarr-style variable intervals)
        last_run = self._last_run.get(task_type)
        if last_run is not None:
            cooldown_minutes = self._get_cooldown_minutes(task_type)
            cooldown = timedelta(minutes=cooldown_minutes)
            time_since = datetime.now(UTC) - last_run
            if time_since < cooldown:
                return False

        # Check dependencies
        dependencies = TASK_DEPENDENCIES.get(task_type, [])
        for dep in dependencies:
            if dep not in self._completed_this_cycle:
                # Dependency hasn't completed yet this cycle
                # But if the dependency ran recently (within its cooldown), allow
                dep_last_run = self._last_run.get(dep)
                if dep_last_run is None:
                    # Dependency never ran - block this task
                    return False
                # If dependency ran recently, consider it "done enough"
                # Use 2x the dependency's cooldown as staleness threshold
                dep_cooldown = self._get_cooldown_minutes(dep)
                staleness_threshold = timedelta(minutes=dep_cooldown * 2)
                time_since_dep = datetime.now(UTC) - dep_last_run
                if time_since_dep > staleness_threshold:
                    # Dependency is stale - wait for it to run first
                    return False

        return True

    def mark_started(self, task_type: TaskType) -> None:
        """Mark task as running."""
        self._running[task_type] = True
        self._last_run[task_type] = datetime.now(UTC)

    def mark_completed(self, task_type: TaskType) -> None:
        """Mark task as completed."""
        self._running[task_type] = False
        self._completed_this_cycle.add(task_type)

    def mark_failed(self, task_type: TaskType) -> None:
        """Mark task as failed (allows immediate retry without cooldown).
        
        Hey future me - when a task FAILS, we clear the last_run timestamp!
        This allows the task to retry immediately on the next loop iteration.
        No point waiting 5 minutes if there was a bug/connection error.
        """
        self._running[task_type] = False
        # Clear last_run so task can retry immediately (no cooldown on failure!)
        if task_type in self._last_run:
            del self._last_run[task_type]

    def mark_urgent(self, task_type: TaskType) -> None:
        """Mark a task as urgent, bypassing its cooldown.

        Hey future me - THIS IS FOR OPTION D+ (Hybrid Image Sync)!
        After ARTIST_SYNC completes with new artists, we want IMAGE_SYNC
        to run IMMEDIATELY instead of waiting for the 10-minute cooldown.

        Use cases:
        - New artists added → trigger IMAGE_SYNC right away
        - User triggered action → bypass automation cooldowns
        - Error recovery → force re-run of failed task

        How it works: Clears last_run timestamp so can_run() returns True.

        Args:
            task_type: The task to mark as urgent.
        """
        if task_type in self._last_run:
            del self._last_run[task_type]
            logger.info(f"TaskScheduler: Marked {task_type.value} as URGENT (cooldown bypassed)")

    def get_next_task(self) -> TaskType | None:
        """Get next task that can run, by dependency order then priority.

        Hey future me - this uses TOPOLOGICAL ORDER for dependencies!
        
        CORE SYNC tasks run first (in order):
        1. ARTIST_SYNC (no deps)
        2. ALBUM_SYNC (depends on ARTIST_SYNC)
        3. TRACK_SYNC (depends on ALBUM_SYNC)
        4. ENRICHMENT, IMAGE_SYNC (depend on ARTIST/ALBUM)
        5. DOWNLOAD (depends on TRACK_SYNC)
        6. CLEANUP (depends on ENRICHMENT, IMAGE_SYNC)
        
        AUTOMATION tasks run last (lower priority, longer cooldowns):
        7. WATCHLIST_CHECK (depends on ALBUM_SYNC, 1h cooldown)
        8. DISCOGRAPHY_SCAN (depends on ARTIST_SYNC, 24h cooldown)
        9. QUALITY_UPGRADE (depends on TRACK_SYNC, 24h cooldown)

        Returns:
            Next runnable TaskType or None if all on cooldown.
        """
        # Topologically sorted order based on TASK_DEPENDENCIES
        # Core sync tasks first, automation tasks last (lower priority)
        topological_order = [
            # === CORE SYNC (high priority, short cooldowns) ===
            TaskType.ARTIST_SYNC,  # No deps - runs first
            TaskType.ALBUM_SYNC,  # Deps: ARTIST_SYNC
            TaskType.TRACK_SYNC,  # Deps: ALBUM_SYNC
            TaskType.ENRICHMENT,  # Deps: ARTIST_SYNC, ALBUM_SYNC
            TaskType.IMAGE_SYNC,  # Deps: ARTIST_SYNC, ALBUM_SYNC
            TaskType.DOWNLOAD,  # Deps: TRACK_SYNC
            TaskType.CLEANUP,  # Deps: ENRICHMENT, IMAGE_SYNC
            
            # === AUTOMATION (low priority, long cooldowns) ===
            TaskType.WATCHLIST_CHECK,    # Deps: ALBUM_SYNC (1h cooldown)
            TaskType.DISCOGRAPHY_SCAN,   # Deps: ARTIST_SYNC (24h cooldown)
            TaskType.QUALITY_UPGRADE,    # Deps: TRACK_SYNC (24h cooldown)
        ]

        for task_type in topological_order:
            if self.can_run(task_type):
                return task_type

        return None

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status for monitoring.

        Returns:
            Dict with task states and cooldowns (task-specific).
        """
        now = datetime.now(UTC)
        status = {}

        for task_type in TaskType:
            last_run = self._last_run.get(task_type)
            running = self._running.get(task_type, False)
            cooldown_minutes = self._get_cooldown_minutes(task_type)

            if last_run:
                elapsed = (now - last_run).total_seconds()
                next_run_in = max(0, cooldown_minutes * 60 - elapsed)
            else:
                next_run_in = 0

            status[task_type.value] = {
                "running": running,
                "last_run": last_run.isoformat() if last_run else None,
                "next_run_in_seconds": next_run_in,
                "cooldown_minutes": cooldown_minutes,  # Task-specific cooldown
                "can_run": self.can_run(task_type),
            }

        return status


# =============================================================================
# TASK DEBOUNCER (Lidarr-inspired)
# =============================================================================


class TaskDebouncer:
    """Debounces rapid task requests to prevent duplicate work.
    
    Hey future me - this is Lidarr's "debouncer" pattern!
    When multiple events trigger the same task rapidly (e.g., 10 new albums found),
    we DON'T want to run WATCHLIST_CHECK 10 times in 2 seconds.
    
    Instead: Wait for events to "settle" (no new events for X seconds),
    then run the task ONCE.
    
    Example:
        debouncer = TaskDebouncer(window_seconds=5)
        
        # Event 1 at t=0: schedule WATCHLIST_CHECK
        debouncer.request(TaskType.WATCHLIST_CHECK)  # pending, waits 5s
        
        # Event 2 at t=2: another request
        debouncer.request(TaskType.WATCHLIST_CHECK)  # extends wait to t=7
        
        # Event 3 at t=3: another request  
        debouncer.request(TaskType.WATCHLIST_CHECK)  # extends wait to t=8
        
        # No more events... at t=8 the task finally runs ONCE
    """
    
    def __init__(self, window_seconds: float = 5.0) -> None:
        """Initialize debouncer.
        
        Args:
            window_seconds: Time to wait after last request before executing.
                           Lidarr uses 5 seconds, we use the same default.
        """
        self._window_seconds = window_seconds
        # Track last request time for each task type
        self._last_request: dict[TaskType, datetime] = {}
        # Track pending executions (task requested but not yet stable)
        self._pending: set[TaskType] = set()
    
    def request(self, task_type: TaskType) -> None:
        """Request a task execution (debounced).
        
        The task won't actually run until the debounce window passes
        with no new requests for the same task type.
        
        Args:
            task_type: The task to request.
        """
        self._last_request[task_type] = datetime.now(UTC)
        self._pending.add(task_type)
        logger.debug(f"TaskDebouncer: Request for {task_type.value}, window resets")
    
    def get_ready_tasks(self) -> list[TaskType]:
        """Get tasks that are ready to execute (debounce window passed).
        
        Hey future me - call this periodically to check for settled tasks!
        Returns tasks where no new requests came in during the window.
        
        Returns:
            List of TaskTypes ready to run.
        """
        now = datetime.now(UTC)
        ready: list[TaskType] = []
        
        for task_type in list(self._pending):
            last_request = self._last_request.get(task_type)
            if last_request is None:
                continue
            
            elapsed = (now - last_request).total_seconds()
            if elapsed >= self._window_seconds:
                # Window passed - task is stable, ready to run
                ready.append(task_type)
                self._pending.discard(task_type)
                logger.debug(
                    f"TaskDebouncer: {task_type.value} ready after {elapsed:.1f}s"
                )
        
        return ready
    
    def cancel(self, task_type: TaskType) -> None:
        """Cancel a pending task request.
        
        Args:
            task_type: The task to cancel.
        """
        self._pending.discard(task_type)
        if task_type in self._last_request:
            del self._last_request[task_type]
    
    def is_pending(self, task_type: TaskType) -> bool:
        """Check if a task is pending (requested but not yet stable).
        
        Args:
            task_type: The task to check.
            
        Returns:
            True if task is in debounce window.
        """
        return task_type in self._pending
    
    def get_status(self) -> dict[str, Any]:
        """Get debouncer status for monitoring.
        
        Returns:
            Dict with pending tasks and their time until ready.
        """
        now = datetime.now(UTC)
        status: dict[str, Any] = {
            "window_seconds": self._window_seconds,
            "pending_tasks": {},
        }
        
        for task_type in self._pending:
            last_request = self._last_request.get(task_type)
            if last_request:
                elapsed = (now - last_request).total_seconds()
                remaining = max(0, self._window_seconds - elapsed)
                status["pending_tasks"][task_type.value] = {
                    "elapsed_seconds": round(elapsed, 1),
                    "remaining_seconds": round(remaining, 1),
                }
        
        return status


# =============================================================================
# UNIFIED LIBRARY MANAGER
# =============================================================================


class UnifiedLibraryManager:
    """The ONE central Library Worker.

    Hey future me - this replaces 10+ workers with ONE coordinated system!

    Features:
    - Single event loop for all library operations
    - Cooldown-based scheduling (no API spam)
    - Provider-agnostic (works with Spotify, Deezer, Tidal)
    - State-based tracking (OwnershipState, DownloadState)
    - Graceful shutdown with task completion

    Lifecycle:
    1. start() - Begin background processing
    2. _main_loop() - Continuously schedule/run tasks
    3. stop() - Graceful shutdown

    Integration:
    - Called from lifecycle.py when use_unified_manager=True
    - Registered with WorkerOrchestrator for health monitoring
    - Settings from AppSettingsService
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncGenerator[AsyncSession, None]],
        spotify_plugin: SpotifyPlugin | None = None,
        deezer_plugin: DeezerPlugin | None = None,
        *,
        database: "Database | None" = None,
        write_buffer: "WriteBufferCache | None" = None,
    ) -> None:
        """Initialize the UnifiedLibraryManager.

        Args:
            session_factory: Factory function to create DB sessions.
            spotify_plugin: Spotify plugin instance (optional).
            deezer_plugin: Deezer plugin instance (optional).
            database: Database instance for retry-enabled sessions (optional).
                     If provided, uses session_scope_with_retry() for all DB ops
                     to avoid SQLite "database is locked" errors.
            write_buffer: WriteBufferCache instance for batched DB writes (optional).
                         If provided, high-frequency writes go through the buffer
                         instead of direct session commits.

        Hey future me - ALWAYS pass database= AND write_buffer= when using SQLite!
        Without database=, we use raw session_factory which has NO retry logic.
        Without write_buffer=, all writes go directly to DB (potential lock issues).
        
        The HYBRID DB STRATEGY (Jan 2025):
        1. RetryStrategy (via database.session_scope_with_retry) - For transactional ops
        2. WriteBufferCache (via write_buffer) - For high-frequency worker writes
        Both are CRITICAL for SQLite concurrency with multiple workers!
        """
        self._session_factory = session_factory
        self._database = database
        self._write_buffer = write_buffer
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin

        # Hey future me - default cooldown only used if task not in TASK_COOLDOWNS!
        # Most tasks use TASK_COOLDOWNS dict for task-specific intervals.
        self._scheduler = TaskScheduler(default_cooldown_minutes=5)
        
        # TaskDebouncer for rapid event handling (Lidarr-style)
        self._debouncer = TaskDebouncer(window_seconds=5.0)
        
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        
        # Token manager for Spotify/Deezer access (set via set_token_manager)
        # Hey future me - this is injected after construction because
        # DatabaseTokenManager might not exist yet during app startup!
        self._token_manager: Any = None

        # Statistics for monitoring
        self._stats: dict[str, Any] = {
            "started_at": None,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_error": None,
            # Artist sync stats
            "artists_synced": 0,
            "artists_created": 0,
            "artists_owned": 0,
            # Album sync stats (Phase 3)
            "albums_synced": 0,
            "albums_created": 0,
            # Track sync stats (Phase 4)
            "tracks_synced": 0,
            "tracks_created": 0,
            # Download stats (Phase 6)
            "downloads_queued": 0,
            "downloads_completed": 0,
            "downloads_failed": 0,
            # === AUTOMATION STATS (from AutomationWorkerManager) ===
            "watchlist_checks": 0,
            "new_releases_found": 0,
            "discography_scans": 0,
            "missing_albums_found": 0,
            "quality_upgrades_found": 0,
        }
    
    def set_token_manager(self, token_manager: Any) -> None:
        """Set the token manager for background Spotify/Deezer access.
        
        Hey future me - this is called from lifecycle.py after
        DatabaseTokenManager is created. Workers need this to get
        access tokens for API calls without user interaction.
        
        Args:
            token_manager: DatabaseTokenManager instance.
        """
        self._token_manager = token_manager
        logger.debug("UnifiedLibraryManager: TokenManager set")

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the background processing loop.

        Hey future me - this is the ONLY public method to start the manager!
        Creates a background task that runs until stop() is called.
        
        WORKER-FIRST PATTERN (Jan 2026):
        On startup, immediately runs INITIAL SYNC to populate DB!
        This ensures routes have data to show even on first visit.
        """
        if self._running:
            logger.warning("UnifiedLibraryManager already running")
            return

        logger.info("Starting UnifiedLibraryManager (WORKER-FIRST mode)")
        self._running = True
        self._stop_event.clear()
        self._stats["started_at"] = datetime.now(UTC).isoformat()

        # WORKER-FIRST: Run initial sync immediately on startup!
        # This ensures DB has data before any routes are accessed.
        # Without this, users would see empty pages until first worker cycle.
        logger.info("🚀 Running INITIAL SYNC on startup...")
        try:
            await self._run_initial_sync()
        except Exception as e:
            logger.exception(f"Initial sync failed: {e}")
            # Continue anyway - main loop will retry

        self._task = asyncio.create_task(self._main_loop())

    async def _run_initial_sync(self) -> None:
        """Run initial sync on startup to populate DB immediately.
        
        Hey future me - WORKER-FIRST PATTERN (Jan 2026)!
        This runs BEFORE the main loop starts, ensuring:
        1. Artists are synced from Spotify/Deezer
        2. Albums are synced for all artists
        3. Tracks are synced for all albums
        
        After this, routes can immediately show data from DB.
        Without this, users would see empty pages on first visit.
        
        Note: This ignores cooldowns - it's an INITIAL sync!
        """
        logger.info("=" * 60)
        logger.info("INITIAL SYNC STARTING (WORKER-FIRST mode)")
        logger.info("=" * 60)
        
        # Phase 1: Sync Artists
        logger.info("[1/3] Syncing Artists...")
        try:
            await self._sync_artists()
        except Exception as e:
            logger.warning(f"[1/3] Artist sync failed: {e}")
        
        # Phase 2: Sync Albums for all artists
        logger.info("[2/3] Syncing Albums...")
        try:
            await self._sync_albums()
        except Exception as e:
            logger.warning(f"[2/3] Album sync failed: {e}")
        
        # Phase 3: Sync Tracks for all albums
        logger.info("[3/3] Syncing Tracks...")
        try:
            await self._sync_tracks()
        except Exception as e:
            logger.warning(f"[3/3] Track sync failed: {e}")
        
        logger.info("=" * 60)
        logger.info("INITIAL SYNC COMPLETE")
        logger.info("=" * 60)

    async def stop(self) -> None:
        """Stop the background processing gracefully.

        Hey future me - this ensures clean shutdown!
        Sets stop event, waits for current task, flushes buffer, then exits loop.
        
        HYBRID DB STRATEGY (Jan 2025):
        Before shutdown, we force flush the WriteBuffer to ensure all
        buffered writes are persisted. This prevents data loss on restart.
        """
        if not self._running:
            return

        logger.info("Stopping UnifiedLibraryManager")
        self._running = False
        self._stop_event.set()

        if self._task:
            try:
                # Wait up to 30 seconds for graceful shutdown
                await asyncio.wait_for(self._task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("UnifiedLibraryManager shutdown timeout, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

        # Flush any buffered writes before shutdown
        await self._flush_buffer_if_available()
        logger.info("UnifiedLibraryManager stopped")

    def get_status(self) -> dict[str, Any]:
        """Get manager status for monitoring.

        Returns:
            Dict with running state, stats, and scheduler status.
        """
        return {
            "running": self._running,
            "stats": self._stats,
            "scheduler": self._scheduler.get_status(),
        }

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    async def _main_loop(self) -> None:
        """Main processing loop - schedules and runs tasks.

        Hey future me - this is the HEART of the manager!
        Pattern: Start cycle → Run ALL tasks in dependency order → Sleep → Repeat

        WORKER-FIRST PATTERN (Jan 2026):
        Loop runs every 5 seconds (was 10) to keep DB always fresh!
        Routes don't call APIs anymore - this worker is the ONLY sync source!
        
        Each task type has its own cooldown (now 2 min for core tasks).
        Tasks respect TASK_DEPENDENCIES - e.g., ALBUM_SYNC waits for ARTIST_SYNC.
        
        CRITICAL FIX: Run ALL runnable tasks in one cycle!
        Old bug: Only ran ONE task per iteration, so fast tasks (ARTIST_SYNC)
        would always run again before slower tasks (IMAGE_SYNC) got a chance.
        
        New behavior: Run ALL tasks that can run in dependency order,
        then start fresh cycle. This ensures IMAGE_SYNC runs after ALBUM_SYNC
        in the SAME cycle.
        """
        logger.info("UnifiedLibraryManager main loop started (WORKER-FIRST mode)")
        cycle_count = 0

        try:
            while self._running:
                try:
                    # Check for stop signal with timeout
                    # WORKER-FIRST: 5 second loop (was 10) for faster responsiveness
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(), timeout=5.0
                        )
                        # Stop event was set
                        break
                    except asyncio.TimeoutError:
                        # Timeout - continue to check for work
                        pass

                    # CRITICAL FIX: Run ALL runnable tasks in this cycle!
                    # Keep getting next task until none are runnable.
                    # This ensures IMAGE_SYNC runs after ALBUM_SYNC completes
                    # in the same cycle, instead of ARTIST_SYNC running again.
                    tasks_run_this_iteration = 0
                    
                    # Get first task to check if any work to do
                    next_task = self._scheduler.get_next_task()
                    if next_task:
                        cycle_count += 1
                        # Log cycle start with box header
                        logger.info(LogMessages.task_flow_cycle_start(
                            "UnifiedLibraryManager", cycle_count
                        ))
                        
                        # Run first task
                        await self._run_task(next_task)
                        tasks_run_this_iteration += 1
                        
                        # Continue with remaining tasks
                        while not self._stop_event.is_set():
                            next_task = self._scheduler.get_next_task()
                            if next_task:
                                await self._run_task(next_task)
                                tasks_run_this_iteration += 1
                            else:
                                # No more tasks runnable
                                break
                    
                    if tasks_run_this_iteration == 0:
                        # No tasks ran - all on cooldown or waiting for deps
                        # Start a fresh cycle so dependencies can be re-evaluated
                        self._scheduler.start_new_cycle()
                        logger.debug("All tasks on cooldown, starting new cycle")
                    else:
                        logger.info(f"Cycle complete: {tasks_run_this_iteration} tasks executed")
                        # Start fresh cycle for next iteration
                        self._scheduler.start_new_cycle()

                except asyncio.CancelledError:
                    logger.info("Main loop cancelled")
                    break
                except Exception:
                    logger.exception("Error in main loop iteration")
                    self._stats["tasks_failed"] += 1
                    await asyncio.sleep(5.0)  # Brief pause on error

        finally:
            logger.info("UnifiedLibraryManager main loop exited")

    async def _run_task(self, task_type: TaskType) -> None:
        """Run a specific task type.

        Hey future me - this dispatches to the correct task handler!
        Each task type has its own implementation method.
        
        AUTOMATION TASKS (migrated from AutomationWorkerManager):
        - WATCHLIST_CHECK: Checks for new releases (from WatchlistWorker)
        - DISCOGRAPHY_SCAN: Checks for missing albums (from DiscographyWorker)
        - QUALITY_UPGRADE: Finds upgrade opportunities (from QualityUpgradeWorker)

        Args:
            task_type: The type of task to run.
        """
        # Log task start with box-drawing tree
        logger.info(LogMessages.task_flow_start(task_type.value.upper()))
        self._scheduler.mark_started(task_type)
        start_time = time.monotonic()

        try:
            # Dispatch to correct handler
            match task_type:
                # === CORE SYNC TASKS ===
                case TaskType.ARTIST_SYNC:
                    await self._sync_artists()
                case TaskType.ALBUM_SYNC:
                    await self._sync_albums()
                case TaskType.TRACK_SYNC:
                    await self._sync_tracks()
                case TaskType.ENRICHMENT:
                    await self._run_enrichment()
                case TaskType.IMAGE_SYNC:
                    await self._sync_images()
                case TaskType.DOWNLOAD:
                    await self._process_downloads()
                case TaskType.CLEANUP:
                    await self._run_cleanup()
                
                # === AUTOMATION TASKS (from AutomationWorkerManager) ===
                case TaskType.WATCHLIST_CHECK:
                    await self._check_watchlists()
                case TaskType.DISCOGRAPHY_SCAN:
                    await self._scan_discographies()
                case TaskType.QUALITY_UPGRADE:
                    await self._identify_quality_upgrades()

            self._scheduler.mark_completed(task_type)
            self._stats["tasks_completed"] += 1
            
            # Log task completion with duration
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(LogMessages.task_flow_complete(
                task_type.value.upper(), duration_ms, success=True
            ))

        except Exception as e:
            self._scheduler.mark_failed(task_type)
            self._stats["tasks_failed"] += 1
            self._stats["last_error"] = f"{task_type.value}: {e!s}"
            
            # Log task failure with error
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(LogMessages.task_flow_error(task_type.value.upper(), str(e)))
            logger.exception(f"Task failed: {task_type.value}")

    # =========================================================================
    # TASK IMPLEMENTATIONS (STUBS - To be filled in Phase 2-6)
    # =========================================================================

    async def _sync_artists(self) -> None:
        """Sync followed artists from enabled providers.

        Hey future me - THIS IS THE CORE ARTIST SYNC!
        Uses FollowedArtistsService which already handles:
        - Multi-provider sync (Spotify + Deezer)
        - Cross-provider deduplication
        - Auto-discography for new artists
        - OAuth validation via can_use()

        After sync, we update ownership_state to OWNED for all synced artists.
        This marks them as "user wants these" vs "discovered via recommendations".
        
        TOKEN HANDLING (CRITICAL FIX Jan 2026):
        Gets token from _token_manager and sets it on spotify_plugin!
        Without this, spotify_plugin.can_use() returns False and sync is skipped.
        """
        from soulspot.application.services.artist_service import ArtistService
        from soulspot.domain.entities import OwnershipState
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        # CRITICAL: Get and set Spotify token BEFORE creating service!
        # Hey future me - without this, spotify_plugin.can_use() returns False
        # and sync_followed_artists_all_providers() skips Spotify entirely!
        access_token = None
        if self._token_manager:
            access_token = await self._token_manager.get_token_for_background()
        
        if access_token and self._spotify_plugin:
            self._spotify_plugin.set_token(access_token)
            logger.debug("ARTIST_SYNC: Spotify token set from token manager")
        elif self._spotify_plugin:
            logger.warning(
                "ARTIST_SYNC: No valid Spotify token available. "
                "Spotify sync will be skipped. User needs to re-authenticate via UI."
            )

        async with self._get_session() as session:
            # Create service with available plugins
            # Hey future me - plugins might be None if not authenticated!
            artist_service = ArtistService(
                session=session,
                spotify_plugin=self._spotify_plugin,
                deezer_plugin=self._deezer_plugin,
            )

            # Log service call
            logger.info(LogMessages.task_flow_service(
                "ArtistService", "sync_followed_artists_all_providers()"
            ))

            # Sync from all providers - this returns deduplicated artists
            # and auto-syncs discography for new artists
            artists, stats = await artist_service.sync_followed_artists_all_providers()

            # Log results per provider
            provider_stats = stats.get("providers", {})
            for provider, pstats in provider_stats.items():
                if isinstance(pstats, dict):
                    if "error" in pstats:
                        logger.info(LogMessages.task_flow_provider(
                            provider.upper(), f"❌ ERROR - {pstats['error']}"
                        ))
                    elif "skipped" in pstats:
                        logger.info(LogMessages.task_flow_provider(
                            provider.upper(), f"⏭️  Skipped ({pstats['skipped']})"
                        ))
                    else:
                        logger.info(LogMessages.task_flow_provider(
                            provider.upper(), f"✓ {pstats.get('total_fetched', 0)} fetched"
                        ))

            # Update ownership_state to OWNED for all synced artists
            # This marks them as "user-selected" vs "discovered"
            artist_repo = ArtistRepository(session)
            owned_count = 0

            for idx, artist in enumerate(artists):
                if artist.ownership_state != OwnershipState.OWNED:
                    artist.ownership_state = OwnershipState.OWNED
                    # Set primary_source based on which service we got them from
                    # The source field tells us where the artist came from
                    if artist.source:
                        artist.primary_source = artist.source.value
                    await artist_repo.update(artist)
                    owned_count += 1
                
                # Hey future me - YIELD every 10 artists to keep UI responsive!
                # Without this, bulk artist updates block the event loop.
                if idx > 0 and idx % 10 == 0:
                    await asyncio.sleep(0)  # Yield without delay

            await session.commit()

            # Update worker stats
            self._stats["artists_synced"] = stats.get("total_fetched", 0)
            self._stats["artists_created"] = stats.get("total_created", 0)
            self._stats["artists_owned"] = owned_count

            # Log final result
            logger.info(LogMessages.task_flow_result(
                f"Total: {stats.get('total_fetched', 0)} fetched, "
                f"{stats.get('total_created', 0)} created, {owned_count} marked OWNED"
            ))

            # ================================================================
            # OPTION D+: Trigger IMAGE_SYNC immediately if new artists created
            # ================================================================
            # Hey future me - THIS IS THE HYBRID IMAGE SYNC!
            # When new artists are created, we want their images ASAP.
            # CDN URLs are already in DB (artist.image_url), but local files aren't.
            # By marking IMAGE_SYNC as urgent, it runs on the NEXT cycle without
            # waiting for its 10-minute cooldown.
            #
            # Why not download here? Because:
            # 1. This method should finish fast (responsive UI)
            # 2. IMAGE_SYNC has proper error handling and batching
            # 3. IMAGE_SYNC also handles albums (which sync in ALBUM_SYNC task)
            # 4. No code duplication!
            total_created = stats.get("total_created", 0)
            if total_created > 0:
                self._scheduler.mark_urgent(TaskType.IMAGE_SYNC)
                logger.info(
                    f"🖼️ {total_created} new artists created - IMAGE_SYNC marked urgent"
                )

    async def _sync_albums(self) -> None:
        """Sync albums for owned artists.

        Hey future me - THIS SYNCS ALBUMS FOR ALL OWNED ARTISTS!
        Uses FollowedArtistsService.sync_artist_discography_complete() which:
        - Fetches albums from Spotify/Deezer with pagination
        - Auto-fetches tracks if include_tracks=True
        - Handles multi-provider fallback

        We batch this to avoid overwhelming the API:
        - Process in chunks of batch_size artists
        - Brief pause between batches
        
        TOKEN HANDLING (CRITICAL FIX Jan 2026):
        Gets token from _token_manager and sets it on spotify_plugin!
        """
        from soulspot.application.services.artist_service import ArtistService
        from soulspot.domain.entities import OwnershipState
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        # CRITICAL: Get and set Spotify token BEFORE creating services!
        access_token = None
        if self._token_manager:
            access_token = await self._token_manager.get_token_for_background()
        
        if access_token and self._spotify_plugin:
            self._spotify_plugin.set_token(access_token)
            logger.debug("ALBUM_SYNC: Spotify token set from token manager")

        async with self._get_session() as session:
            artist_repo = ArtistRepository(session)

            # Get settings for batch size
            settings_service = self._app_settings_service_factory(session)
            batch_size = await settings_service.get_enrichment_batch_size()

            # Get all OWNED artists
            owned_count = await artist_repo.count_by_ownership_state(OwnershipState.OWNED)
            
            # Log service call with details
            logger.info(LogMessages.task_flow_service(
                "ProviderSyncOrchestrator", f"sync_artist_albums() for {owned_count} artists"
            ))

            # Process in batches
            offset = 0
            total_albums_added = 0
            total_tracks_added = 0
            artists_processed = 0
            errors = 0

            # Create orchestrator for multi-provider album sync with cooldown
            from soulspot.application.services.provider_sync_orchestrator import (
                ProviderSyncOrchestrator,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )

            # Hey future me - Services only created if plugins are available!
            # SpotifySyncService requires spotify_plugin (NOT optional!)
            # DeezerSyncService requires deezer_plugin (NOT optional!)
            # ProviderSyncOrchestrator accepts None for both (handles fallback)
            spotify_sync = None
            if self._spotify_plugin:
                spotify_sync = SpotifySyncService(
                    session=session,
                    spotify_plugin=self._spotify_plugin,
                )
            
            deezer_sync = None
            if self._deezer_plugin:
                deezer_sync = DeezerSyncService(
                    session=session,
                    deezer_plugin=self._deezer_plugin,
                )
            
            orchestrator = ProviderSyncOrchestrator(
                session=session,
                spotify_sync=spotify_sync,
                deezer_sync=deezer_sync,
                settings_service=settings_service,
            )

            while offset < owned_count:
                artists = await artist_repo.list_by_ownership_state(
                    ownership_state=OwnershipState.OWNED,
                    limit=batch_size,
                    offset=offset,
                )

                if not artists:
                    break

                for artist in artists:
                    try:
                        # Sync albums ONLY (not tracks!) with cooldown check
                        # Tracks will be synced separately in _sync_tracks() phase
                        # 
                        # Hey future me - WICHTIG für Artist-ID Logik:
                        # - spotify_id: Spotify artist ID (z.B. "3TV0qLgjEYM0STMlmI05U3")
                        # - deezer_id: Deezer artist ID (z.B. "27")
                        # - artist.id.value: Internes UUID (NICHT für Provider API geeignet!)
                        #
                        # Wenn Artist nur deezer_id hat (kein spotify_id), 
                        # wird Spotify übersprungen und nur Deezer verwendet.
                        # Wenn Artist keinen Provider hat, wird der Artist übersprungen.
                        
                        # Skip artists without any provider ID
                        if not artist.spotify_id and not artist.deezer_id:
                            logger.debug(
                                f"Skipping {artist.name}: No provider ID (neither Spotify nor Deezer)"
                            )
                            continue
                        
                        result = await orchestrator.sync_artist_albums(
                            artist_id=artist.spotify_id,  # Can be None - Spotify will be skipped
                            artist_name=artist.name,
                            deezer_artist_id=artist.deezer_id,
                            force=False,  # Respect cooldown!
                        )
                        
                        # Only count if actually synced (not skipped due to cooldown)
                        if result.synced and result.added > 0:
                            total_albums_added += result.added
                            artists_processed += 1
                            logger.debug(
                                f"Synced {artist.name}: {result.added} albums "
                                f"(Spotify: {result.source_counts.get('spotify', 0)}, "
                                f"Deezer: {result.source_counts.get('deezer', 0)})"
                            )
                        elif result.skipped_providers:
                            # All providers on cooldown - this is expected, not an error
                            pass  # Don't log every cooldown skip
                        
                        # Hey future me - YIELD to event loop between artists!
                        # This allows UI requests to be processed during sync.
                        # Without this, the UI becomes unresponsive during bulk syncs.
                        await asyncio.sleep(0)  # Yield without delay

                    except Exception as e:
                        errors += 1
                        logger.warning(
                            f"Failed to sync albums for {artist.name}: {e}"
                        )

                await session.commit()
                offset += batch_size

                # Brief pause between batches to avoid rate limits
                if offset < owned_count:
                    await asyncio.sleep(1.0)

            # Update stats
            self._stats["albums_synced"] = total_albums_added
            self._stats["tracks_synced"] = total_tracks_added

            # Log final result
            logger.info(LogMessages.task_flow_result(
                f"Processed: {artists_processed} artists, "
                f"{total_albums_added} albums added, {errors} errors"
            ))

            # ================================================================
            # OPTION D+: Trigger IMAGE_SYNC immediately if new albums created
            # ================================================================
            # Hey future me - same logic as _sync_artists()!
            # New albums have cover_url (CDN) but no cover_path (local).
            # IMAGE_SYNC will download them in batches with proper rate limiting.
            if total_albums_added > 0:
                self._scheduler.mark_urgent(TaskType.IMAGE_SYNC)
                logger.info(
                    f"🖼️ {total_albums_added} new albums added - IMAGE_SYNC marked urgent"
                )

    async def _sync_tracks(self) -> None:
        """Sync tracks for albums missing tracks and handle download state.

        Hey future me - THIS IS THE TRACK SYNC + DOWNLOAD QUEUE TASK!
        Two responsibilities:
        1. Backfill tracks for albums that have no tracks yet
        2. Set download_state=PENDING for new tracks if auto_queue_downloads=True

        Uses Deezer API to fetch tracks (NO AUTH NEEDED!) with rate limiting.
        
        CRITICAL FIX (Jan 2026): Use sync_album_tracks() instead of sync_artist_discography_complete()!
        Was syncing entire artist discography for EACH album → Dr. Peacock endless loop!
        
        TOKEN HANDLING (CRITICAL FIX Jan 2026):
        Gets token from _token_manager and sets it on spotify_plugin!
        """
        from soulspot.application.services.provider_sync_orchestrator import (
            ProviderSyncOrchestrator,
        )
        from soulspot.application.services.deezer_sync_service import DeezerSyncService
        from soulspot.application.services.spotify_sync_service import SpotifySyncService
        from soulspot.domain.entities import DownloadState
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            TrackRepository,
        )

        # CRITICAL: Get and set Spotify token BEFORE creating services!
        access_token = None
        if self._token_manager:
            access_token = await self._token_manager.get_token_for_background()
        
        if access_token and self._spotify_plugin:
            self._spotify_plugin.set_token(access_token)
            logger.debug("TRACK_SYNC: Spotify token set from token manager")

        async with self._get_session() as session:
            album_repo = AlbumRepository(session)
            track_repo = TrackRepository(session)

            # Get settings
            settings_service = self._app_settings_service_factory(session)
            auto_queue = await settings_service.auto_queue_downloads_enabled()
            batch_size = await settings_service.get_enrichment_batch_size()

            # Get albums needing track backfill
            albums = await album_repo.get_albums_needing_track_backfill(
                limit=batch_size
            )

            if not albums:
                logger.info(LogMessages.task_flow_skip("TRACK_SYNC", "No albums need track backfill"))
                return

            # Log service call
            logger.info(LogMessages.task_flow_service(
                "ProviderSyncOrchestrator", f"sync_album_tracks() for {len(albums)} albums"
            ))

            # Create sync services with correct parameter names!
            # Hey future me - Services only created if plugins are available!
            # SpotifySyncService requires spotify_plugin (NOT optional!)
            # DeezerSyncService requires deezer_plugin (NOT optional!)
            spotify_sync = None
            if self._spotify_plugin:
                spotify_sync = SpotifySyncService(
                    session=session, spotify_plugin=self._spotify_plugin
                )
            
            deezer_sync = None
            if self._deezer_plugin:
                deezer_sync = DeezerSyncService(
                    session=session, deezer_plugin=self._deezer_plugin
                )
            
            orchestrator = ProviderSyncOrchestrator(
                session=session,
                spotify_sync=spotify_sync,
                deezer_sync=deezer_sync,
                settings_service=settings_service,
            )

            tracks_added = 0
            albums_processed = 0
            errors = 0

            for album in albums:
                try:
                    # FIXED: Sync ONLY this album's tracks, not entire artist!
                    # Use album IDs from the album entity
                    result = await orchestrator.sync_album_tracks(
                        album_id=album.spotify_id,  # Spotify album ID
                        deezer_album_id=album.deezer_id,  # Deezer album ID (if available)
                        force=False,
                    )
                    tracks_added += result.added
                    albums_processed += 1
                    
                    if not result.synced:
                        logger.debug(
                            f"No tracks synced for album {album.title}: {result.errors}"
                        )

                except Exception as e:
                    errors += 1
                    logger.warning(
                        f"Failed to sync tracks for album {album.title}: {e}"
                    )

                # Brief pause between albums to avoid rate limits
                await asyncio.sleep(0.5)

            await session.commit()

            # If auto_queue_downloads is enabled, set PENDING for new tracks
            if auto_queue:
                await self._queue_pending_downloads(session, track_repo)

            # Update stats
            self._stats["tracks_synced"] = tracks_added
            self._stats["tracks_created"] = tracks_added

            # Log final result
            logger.info(LogMessages.task_flow_result(
                f"Processed: {albums_processed} albums, {tracks_added} tracks added, "
                f"{errors} errors"
            ))

    async def _queue_pending_downloads(
        self, session: "AsyncSession", track_repo: Any
    ) -> None:
        """Queue newly synced tracks for download.

        Hey future me - THIS SETS download_state=PENDING!
        Only for tracks that:
        - Have download_state=NOT_NEEDED (never queued)
        - Belong to OWNED artists
        - Have no local file yet

        Args:
            session: Database session
            track_repo: Track repository instance (unused but kept for API consistency)
        """
        from sqlalchemy import select, update

        from soulspot.domain.entities import DownloadState, OwnershipState
        from soulspot.infrastructure.persistence.models import ArtistModel, TrackModel

        # Update tracks to PENDING where:
        # - download_state = NOT_NEEDED
        # - artist.ownership_state = OWNED
        # - file_path is NULL
        stmt = (
            update(TrackModel)
            .where(TrackModel.download_state == DownloadState.NOT_NEEDED.value)
            .where(TrackModel.file_path.is_(None))
            .where(
                TrackModel.artist_id.in_(
                    select(ArtistModel.id).where(
                        ArtistModel.ownership_state == OwnershipState.OWNED.value
                    )
                )
            )
            .values(download_state=DownloadState.PENDING.value)
        )
        result = await session.execute(stmt)
        queued_count = result.rowcount

        if queued_count > 0:
            self._stats["downloads_queued"] = (
                self._stats.get("downloads_queued", 0) + queued_count
            )
            logger.info(f"📥 Queued {queued_count} tracks for download")

    async def _run_enrichment(self) -> None:
        """Enrich entities with MusicBrainz/external data.

        Hey future me - THIS IS THE METADATA ENRICHMENT TASK!
        Uses MusicBrainzEnrichmentService for disambiguation and metadata.
        Rate limited to 1 req/sec per MusicBrainz requirements.

        Process:
        1. Find artists/albums without disambiguation
        2. Search MusicBrainz by name
        3. Store disambiguation, musicbrainz_id, genres
        """
        from soulspot.application.services.musicbrainz_enrichment_service import (
            MusicBrainzEnrichmentService,
        )
        from soulspot.config.settings import get_settings
        from soulspot.infrastructure.integrations.musicbrainz_client import (
            MusicBrainzClient,
        )

        async with self._get_session() as session:
            settings = get_settings()
            settings_service = self._app_settings_service_factory(session)
            batch_size = await settings_service.get_enrichment_batch_size()

            # Create MusicBrainz client
            mb_client = MusicBrainzClient(settings.musicbrainz)

            # Create enrichment service
            enrichment_service = MusicBrainzEnrichmentService(
                session=session,
                musicbrainz_client=mb_client,
                settings_service=settings_service,
            )

            logger.info("Starting MusicBrainz enrichment...")

            try:
                # Run disambiguation batch (artists + albums)
                stats = await enrichment_service.enrich_disambiguation_batch(
                    limit=batch_size
                )

                await session.commit()

                logger.info(
                    f"✅ MusicBrainz enrichment complete: "
                    f"Artists: {stats.get('artists_enriched', 0)}/{stats.get('artists_processed', 0)}, "
                    f"Albums: {stats.get('albums_enriched', 0)}/{stats.get('albums_processed', 0)}"
                )

            except Exception as e:
                logger.warning(f"MusicBrainz enrichment failed: {e}")
                # Don't fail the whole task - just log and continue

            # ================================================================
            # PHASE 2: CROSS-PROVIDER ID ENRICHMENT
            # ================================================================
            # Hey future me - this adds Deezer/Spotify IDs to entities that are missing them!
            # Works incrementally: entities get provider IDs over time via name search.
            # Once an entity has both deezer_id AND spotify_uri, future lookups are FAST
            # (direct ID lookup instead of slow name search).
            #
            # Deezer: NO AUTH required! Can enrich all entities.
            # Spotify: Requires OAuth, only enriches if user authenticated.
            try:
                from soulspot.application.services.universal_id_enrichment_service import (
                    UniversalIdEnrichmentService,
                )

                id_enrichment = UniversalIdEnrichmentService(
                    session=session,
                    deezer_plugin=self._deezer_plugin,
                    spotify_plugin=self._spotify_plugin,
                )

                id_stats = await id_enrichment.enrich_entities_missing_ids(
                    batch_size=batch_size
                )

                await session.commit()

                logger.info(
                    f"🔗 Cross-Provider ID enrichment: "
                    f"Artists: {id_stats.artists_enriched}/{id_stats.artists_processed}, "
                    f"Albums: {id_stats.albums_enriched}/{id_stats.albums_processed}, "
                    f"Tracks: {id_stats.tracks_enriched}/{id_stats.tracks_processed} "
                    f"(Deezer: {id_stats.deezer_matches}, Spotify: {id_stats.spotify_matches})"
                )

            except Exception as e:
                logger.warning(f"Cross-Provider ID enrichment failed: {e}")
                # Don't fail the whole task - MusicBrainz enrichment still succeeded

    async def _sync_images(self) -> None:
        """Download/cache images for artists and albums.

        Hey future me - THIS DOES THE FULL IMAGE PIPELINE!
        1. Find entities with missing image_url → fetch from Deezer/Spotify
        2. Find entities with URL but no local file → download and cache

        Process:
        Phase 1: URL Enrichment
        - Find artists/albums with missing image_url
        - Query Deezer (no auth!) for images by ID or NAME SEARCH
        - Update image_url in DB
        
        IMPORTANT (Jan 2025): For LOCAL entities (imported from /music), we now
        also do a NAME SEARCH on Deezer to find images! Previously only entities
        with deezer_id were enriched.

        Phase 2: Local Download
        - Find artists/albums with URL but no local image_path
        - Download from CDN via ImageService
        - Convert to WebP and cache locally
        """
        from soulspot.application.services.images import ImageService
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            ArtistRepository,
        )

        async with self._get_session() as session:
            settings_service = self._app_settings_service_factory(session)
            batch_size = await settings_service.get_enrichment_batch_size()

            # Check if image download is enabled
            image_enabled = await settings_service.image_download_enabled()
            if not image_enabled:
                logger.debug("Image sync disabled in settings")
                return

            artist_repo = ArtistRepository(session)
            album_repo = AlbumRepository(session)
            image_service = ImageService(session=session)

            # Log service call
            logger.info(LogMessages.task_flow_service(
                "ImageService", "download_and_cache() + URL enrichment (incl. name search)"
            ))

            # ================================================================
            # PHASE 1: URL ENRICHMENT (fetch URLs from Deezer)
            # ================================================================
            urls_fetched = {"artists": 0, "artists_by_search": 0, "albums": 0, "albums_by_search": 0}

            # Get artists missing image URL
            try:
                artists = await artist_repo.get_missing_artwork(limit=batch_size)
                if artists and self._deezer_plugin:
                    for artist in artists:
                        try:
                            image_url = None
                            
                            # Strategy 1: Direct ID lookup (fast, accurate)
                            if artist.deezer_id:
                                artist_data = await self._deezer_plugin.get_artist(
                                    artist.deezer_id
                                )
                                if artist_data and artist_data.image_url:
                                    image_url = artist_data.image_url
                                    urls_fetched["artists"] += 1
                            
                            # Strategy 2: Name search for LOCAL artists without deezer_id
                            # Hey future me - THIS IS THE FIX for imported local artists!
                            if not image_url and artist.name:
                                search_results = await self._deezer_plugin.search_artists(
                                    artist.name, limit=1
                                )
                                if search_results and search_results.items:
                                    best_match = search_results.items[0]
                                    if best_match.image_url:
                                        image_url = best_match.image_url
                                        # Also save deezer_id for future lookups!
                                        if best_match.deezer_id:
                                            artist.deezer_id = best_match.deezer_id
                                        urls_fetched["artists_by_search"] += 1
                                        logger.debug(
                                            f"Found image for local artist '{artist.name}' via Deezer search"
                                        )
                            
                            # Update artist if we found an image URL
                            if image_url:
                                from soulspot.domain.value_objects import ImageRef
                                artist.image = ImageRef(
                                    url=image_url,
                                    path=artist.image.path if artist.image else None,
                                )
                                await artist_repo.update(artist)
                            
                            await asyncio.sleep(0.2)  # Rate limit
                        except Exception as e:
                            logger.debug(f"Failed to get URL for artist {artist.name}: {e}")
            except Exception as e:
                logger.warning(f"Artist URL enrichment failed: {e}")

            # Get albums missing cover URL
            try:
                albums = await album_repo.get_albums_without_cover_url(limit=batch_size)
                if albums and self._deezer_plugin:
                    # Pre-fetch artist names for all albums (batch lookup, more efficient)
                    # Hey future me - Album entity has artist_id: ArtistId, NOT artist_name!
                    artist_names: dict[str, str] = {}
                    unique_artist_ids = {album.artist_id for album in albums}
                    for aid in unique_artist_ids:
                        try:
                            artist = await artist_repo.get_by_id(aid)  # ArtistId object
                            if artist:
                                artist_names[str(aid)] = artist.name
                        except Exception:
                            pass  # Continue without artist name
                    
                    for album in albums:
                        try:
                            cover_url = None
                            
                            # Strategy 1: Direct ID lookup
                            if album.deezer_id:
                                album_data = await self._deezer_plugin.get_album(
                                    album.deezer_id
                                )
                                if album_data and album_data.cover_url:
                                    cover_url = album_data.cover_url
                                    urls_fetched["albums"] += 1
                            
                            # Strategy 2: Search by album title + artist name
                            # Hey future me - THIS IS THE FIX for imported local albums!
                            if not cover_url and album.title:
                                # Build search query: "Artist - Album" (better search results)
                                artist_name = artist_names.get(str(album.artist_id))
                                search_query = album.title
                                if artist_name:
                                    search_query = f"{artist_name} {album.title}"
                                
                                search_results = await self._deezer_plugin.search_albums(
                                    search_query, limit=1
                                )
                                if search_results and search_results.items:
                                    best_match = search_results.items[0]
                                    if best_match.cover_url:
                                        cover_url = best_match.cover_url
                                        # Also save deezer_id for future lookups!
                                        if best_match.deezer_id:
                                            album.deezer_id = best_match.deezer_id
                                        urls_fetched["albums_by_search"] += 1
                                        logger.debug(
                                            f"Found cover for local album '{album.title}' via Deezer search"
                                        )
                            
                            # Update album if we found a cover URL
                            if cover_url:
                                await album_repo.update_cover_url(album.id, cover_url)
                                # Also update deezer_id if found via search
                                if hasattr(album, 'deezer_id') and album.deezer_id:
                                    await album_repo.update(album)
                            
                            await asyncio.sleep(0.2)  # Rate limit
                        except Exception as e:
                            logger.debug(f"Failed to get URL for album {album.title}: {e}")
            except Exception as e:
                logger.warning(f"Album URL enrichment failed: {e}")

            await session.commit()

            logger.info(
                f"📥 Phase 1 URL enrichment: "
                f"Artists: {urls_fetched['artists']} (ID) + {urls_fetched['artists_by_search']} (search), "
                f"Albums: {urls_fetched['albums']} (ID) + {urls_fetched['albums_by_search']} (search)"
            )

            # ================================================================
            # PHASE 2: LOCAL DOWNLOAD (download and cache images locally)
            # ================================================================
            downloads = {"artists": 0, "albums": 0, "errors": 0}

            # Download artist images (have URL but no local file)
            try:
                artists_needing_download = await artist_repo.get_artists_needing_image_download(
                    limit=batch_size
                )
                for artist in artists_needing_download:
                    try:
                        if artist.image and artist.image.url:
                            result = await image_service.download_and_cache(
                                source_url=artist.image.url,
                                entity_type="artist",
                                entity_id=str(artist.id),
                            )
                            if result.success:
                                downloads["artists"] += 1
                                logger.debug(f"✅ Downloaded image for artist: {artist.name}")
                            else:
                                downloads["errors"] += 1
                                logger.debug(f"❌ Failed to download image for {artist.name}: {result.error}")
                        await asyncio.sleep(0.3)  # Rate limit downloads
                    except Exception as e:
                        downloads["errors"] += 1
                        logger.debug(f"Error downloading artist image {artist.name}: {e}")
            except Exception as e:
                logger.warning(f"Artist image download phase failed: {e}")

            # Download album covers (have URL but no local file)
            try:
                albums_needing_download = await album_repo.get_albums_needing_cover_download(
                    limit=batch_size
                )
                for album in albums_needing_download:
                    try:
                        # Album uses cover: ImageRef, not cover_url directly
                        cover_url = album.cover.url if album.cover else None
                        if cover_url:
                            result = await image_service.download_and_cache(
                                source_url=cover_url,
                                entity_type="album",
                                entity_id=str(album.id),
                            )
                            if result.success:
                                downloads["albums"] += 1
                                logger.debug(f"✅ Downloaded cover for album: {album.title}")
                            else:
                                downloads["errors"] += 1
                                logger.debug(f"❌ Failed to download cover for {album.title}: {result.error}")
                        await asyncio.sleep(0.3)  # Rate limit downloads
                    except Exception as e:
                        downloads["errors"] += 1
                        logger.debug(f"Error downloading album cover {album.title}: {e}")
            except Exception as e:
                logger.warning(f"Album cover download phase failed: {e}")

            await session.commit()

            # Log final result with Phase 1 + Phase 2 summary
            logger.info(LogMessages.task_flow_result(
                f"URLs: {urls_fetched['artists']}+{urls_fetched['albums']} | "
                f"Downloaded: {downloads['artists']} artists, {downloads['albums']} albums "
                f"({downloads['errors']} errors)"
            ))

    async def _process_downloads(self) -> None:
        """Monitor download queue and log statistics.

        Hey future me - THIS DOES NOT EXECUTE DOWNLOADS!
        The UnifiedLibraryManager only:
        1. Sets download_state=PENDING (done in _queue_pending_downloads)
        2. Monitors the queue and logs statistics

        The ACTUAL download execution is handled by:
        - QueueDispatcherWorker (dispatches to slskd)
        - DownloadManagerService (tracks progress)

        This separation allows:
        - Clear responsibility boundaries
        - Independent scaling/restart
        - Better error isolation
        """
        from sqlalchemy import func, select

        from soulspot.domain.entities import DownloadState
        from soulspot.infrastructure.persistence.models import TrackModel

        async with self._get_session() as session:
            # Log service call
            logger.info(LogMessages.task_flow_service(
                "DownloadStateMonitor", "count_by_state()"
            ))
            
            # Count tracks by download_state
            state_counts = {}
            for state in DownloadState:
                stmt = select(func.count(TrackModel.id)).where(
                    TrackModel.download_state == state.value
                )
                result = await session.execute(stmt)
                state_counts[state.value] = result.scalar() or 0

            pending = state_counts.get("pending", 0)
            downloading = state_counts.get("downloading", 0)
            downloaded = state_counts.get("downloaded", 0)
            failed = state_counts.get("failed", 0)

            # Update stats
            self._stats["downloads_pending"] = pending
            self._stats["downloads_in_progress"] = downloading
            self._stats["downloads_completed"] = downloaded
            self._stats["downloads_failed"] = failed

            # Log result with queue status
            logger.info(LogMessages.task_flow_result(
                f"Queue: {pending} pending, {downloading} downloading, "
                f"{downloaded} done, {failed} failed"
            ))

    async def _run_cleanup(self) -> None:
        """Cleanup stale data and reset failed downloads.

        Hey future me - THIS IS THE MAINTENANCE TASK!
        Runs periodically to:
        1. Reset old FAILED downloads to PENDING for retry
        2. Remove orphaned albums (no tracks)
        3. Remove orphaned artists (no albums AND no tracks)

        Uses cleanup_days from settings to determine "stale" threshold.
        """
        from datetime import timedelta

        from sqlalchemy import update

        from soulspot.application.services.library_cleanup_service import (
            LibraryCleanupService,
        )
        from soulspot.domain.entities import DownloadState
        from soulspot.infrastructure.persistence.models import TrackModel

        async with self._get_session() as session:
            settings_service = self._app_settings_service_factory(session)
            cleanup_days = await settings_service.get_download_cleanup_days()

            logger.info(f"Starting cleanup (reset FAILED older than {cleanup_days} days)...")

            # Calculate cutoff date
            cutoff = datetime.now(UTC) - timedelta(days=cleanup_days)

            # Reset FAILED downloads older than cutoff back to PENDING
            stmt = (
                update(TrackModel)
                .where(TrackModel.download_state == DownloadState.FAILED.value)
                .where(TrackModel.updated_at < cutoff)
                .values(download_state=DownloadState.PENDING.value)
            )
            result = await session.execute(stmt)
            reset_count = result.rowcount

            await session.commit()

            if reset_count > 0:
                logger.info(f"🔄 Reset {reset_count} failed downloads to PENDING for retry")
            else:
                logger.debug("No stale failed downloads to reset")

            # Clean up orphaned entities (albums without tracks, artists without albums/tracks)
            # Hey future me - this catches orphans from:
            # - Manual artist deletions
            # - Discography sync creating "discovered" entities
            # - Track deletions leaving empty albums
            cleanup_service = LibraryCleanupService(session)
            orphan_stats = await cleanup_service.cleanup_orphaned_entities()

            if orphan_stats["albums"] > 0 or orphan_stats["artists"] > 0:
                logger.info(
                    f"🧹 Orphan cleanup: {orphan_stats['albums']} albums, "
                    f"{orphan_stats['artists']} artists removed"
                )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _app_settings_service_factory(
        self, session: AsyncSession
    ) -> "AppSettingsService":
        """Create an AppSettingsService with the given session.

        Hey future me - this is used inside task handlers to get settings.
        Import is inside to avoid circular dependencies.
        """
        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )

        return AppSettingsService(session)

    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a new database session with automatic retry on SQLite locks.

        Hey future me - this now uses session_scope_with_retry() when database is available!
        This prevents "database is locked" errors during heavy concurrent writes.

        The retry mechanism:
        1. If database is available → use session_scope_with_retry (3 retries, exponential backoff)
        2. If database not available → fallback to raw session_factory (no retries)

        Dec 2025: This change fixed massive SQLite lock errors when Library Scanner,
        Artist Sync, Image Repair, and Token Refresh all wrote simultaneously.
        """
        if self._database is not None:
            # Use retry-enabled session for SQLite lock resilience
            async with self._database.session_scope_with_retry(
                max_attempts=3,
                initial_delay=0.5,
            ) as session:
                yield session
        else:
            # Fallback: raw session factory (no retries)
            async with self._session_factory() as session:
                try:
                    yield session
                finally:
                    await session.close()

    async def _buffer_entity_update(
        self,
        table: str,
        key_column: str,
        key_value: str,
        data: dict[str, Any],
    ) -> bool:
        """Buffer an entity update for batched write via WriteBufferCache.

        Hey future me - USE THIS for high-frequency entity updates!
        Instead of immediate session.commit(), updates go to the buffer.
        Buffer flushes every 5 seconds or when full.

        This is part of the HYBRID DB STRATEGY (Jan 2025):
        - Hot-path: Buffer writes → Periodic flush (no lock contention)
        - Cold-path: Direct session with retry (transactional integrity)

        Args:
            table: Database table name (e.g., "artists", "tracks")
            key_column: Primary key column (e.g., "id", "spotify_uri")
            key_value: Value of the primary key
            data: Dict of column -> value to update

        Returns:
            True if buffered successfully, False if buffer not available
            (falls back to direct write in that case)

        Example:
            # Instead of:
            #   artist.ownership_state = OwnershipState.OWNED
            #   await repo.update(artist)
            #   await session.commit()
            #
            # Use:
            #   await self._buffer_entity_update(
            #       table="artists",
            #       key_column="id",
            #       key_value=str(artist.id.value),
            #       data={"ownership_state": OwnershipState.OWNED.value}
            #   )
        """
        if self._write_buffer is None:
            logger.debug(
                "WriteBuffer not available, entity update will use direct session"
            )
            return False

        try:
            await self._write_buffer.buffer_update(
                table=table,
                key_column=key_column,
                key_value=key_value,
                data=data,
            )
            return True
        except Exception as e:
            logger.warning(
                f"Failed to buffer entity update for {table}[{key_value}]: {e}. "
                "Falling back to direct write."
            )
            return False

    async def _flush_buffer_if_available(self) -> None:
        """Force flush the write buffer if available.

        Hey future me - call this at strategic points:
        - After completing a batch of updates
        - Before task completion (ensure data is persisted)
        - On graceful shutdown

        This is a no-op if WriteBuffer is not available.
        """
        if self._write_buffer is not None:
            await self._write_buffer.force_flush()
            logger.debug("WriteBuffer force flushed")

    async def trigger_task(self, task_type: TaskType) -> bool:
        """Manually trigger a task (bypasses cooldown for user requests).

        Hey future me - this is for UI-triggered actions!
        User clicks "Sync Now" → trigger_task(ARTIST_SYNC)

        Args:
            task_type: The task to trigger.

        Returns:
            True if task was started, False if already running.
        """
        if self._scheduler._running.get(task_type, False):
            return False

        # Run immediately in background
        asyncio.create_task(self._run_task(task_type))
        return True

    # =========================================================================
    # AUTOMATION TASKS (migrated from AutomationWorkerManager)
    # =========================================================================

    async def _check_watchlists(self) -> None:
        """Check artist watchlists for new releases.
        
        Hey future me - this is the WATCHLIST_CHECK task!
        Migrated from WatchlistWorker._check_watchlists()
        
        Flow:
        1. Get all watchlists due for checking
        2. For each watchlist, check for new albums since last check
        3. If new releases found and auto_download enabled, trigger automation
        4. Update last_checked_at timestamp
        
        OPTIMIZATION: Uses pre-synced spotify_albums data (no API calls!)
        The ALBUM_SYNC task keeps albums fresh, we just query locally.
        
        TOKEN HANDLING: Gets token from _token_manager for Spotify API access.
        Graceful degradation: skips work if no valid token available.
        """
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.application.services.watchlist_service import WatchlistService
        from soulspot.domain.entities import AutomationTrigger
        from soulspot.infrastructure.persistence.repositories import (
            ArtistRepository,
            SpotifyBrowseRepository,
        )

        logger.info("🔔 Starting watchlist check for new releases...")
        
        async with self._get_session() as session:
            try:
                # Get access token from token manager
                access_token = None
                if self._token_manager:
                    access_token = await self._token_manager.get_token_for_background()
                
                if not access_token and self._spotify_plugin:
                    # Token invalid or missing - skip this cycle gracefully
                    logger.warning(
                        "No valid Spotify token - skipping watchlist check. "
                        "User needs to re-authenticate via UI."
                    )
                    return
                
                # Set token on plugin if available
                if access_token and self._spotify_plugin:
                    self._spotify_plugin.set_token(access_token)
                
                # Create services
                # MULTI-PROVIDER: Inject both Spotify AND Deezer for combined results!
                watchlist_service = WatchlistService(
                    session,
                    spotify_plugin=self._spotify_plugin,
                    deezer_plugin=self._deezer_plugin,
                )
                workflow_service = AutomationWorkflowService(session)
                artist_repo = ArtistRepository(session)
                spotify_repo = SpotifyBrowseRepository(session)
                
                # Get watchlists due for checking
                watchlists = await watchlist_service.list_due_for_check(limit=100)
                
                if not watchlists:
                    logger.debug("No watchlists due for checking")
                    return
                
                logger.info(f"Checking {len(watchlists)} watchlists for new releases")
                
                total_releases_found = 0
                total_downloads_triggered = 0
                
                for watchlist in watchlists:
                    try:
                        # Get local artist
                        local_artist = await artist_repo.get_by_id(watchlist.artist_id)
                        if not local_artist or not local_artist.spotify_uri:
                            continue
                        
                        spotify_artist_id = local_artist.spotify_id
                        
                        # Check if albums are synced
                        sync_status = await spotify_repo.get_artist_albums_sync_status(
                            spotify_artist_id
                        )
                        
                        if not sync_status["albums_synced"]:
                            # Albums not synced - will be caught by next ALBUM_SYNC
                            watchlist.update_check(releases_found=0, downloads_triggered=0)
                            await watchlist_service.repository.update(watchlist)
                            await session.commit()
                            continue
                        
                        # Get new albums since last check (LOCAL query, no API!)
                        new_album_models = await spotify_repo.get_new_albums_since(
                            artist_id=spotify_artist_id,
                            since_date=watchlist.last_checked_at,
                        )
                        
                        # Convert to dict format for automation
                        new_releases = [
                            {
                                "album_id": album.spotify_uri,
                                "album_name": album.title,
                                "album_type": album.primary_type,
                                "release_date": album.release_date,
                                "total_tracks": album.total_tracks,
                                "images": [{"url": album.cover_url}] if album.cover_url else [],
                            }
                            for album in new_album_models
                        ]
                        
                        if new_releases:
                            logger.info(
                                f"Found {len(new_releases)} new releases for {local_artist.name}"
                            )
                            total_releases_found += len(new_releases)
                        
                        # Trigger automation if enabled
                        downloads_triggered = 0
                        if new_releases and watchlist.auto_download:
                            for release in new_releases:
                                context = {
                                    "artist_id": str(watchlist.artist_id.value),
                                    "watchlist_id": str(watchlist.id.value),
                                    "release_info": release,
                                    "quality_profile": watchlist.quality_profile,
                                }
                                await workflow_service.trigger_workflow(
                                    trigger=AutomationTrigger.NEW_RELEASE,
                                    context=context,
                                )
                                downloads_triggered += 1
                                total_downloads_triggered += 1
                        
                        # Update watchlist
                        watchlist.update_check(
                            releases_found=len(new_releases),
                            downloads_triggered=downloads_triggered,
                        )
                        await watchlist_service.repository.update(watchlist)
                        await session.commit()
                        
                    except Exception as e:
                        logger.error(f"Error checking watchlist {watchlist.id}: {e}")
                        await session.rollback()
                
                # Update stats
                self._stats["watchlist_checks"] += 1
                self._stats["new_releases_found"] += total_releases_found
                
                logger.info(
                    f"✅ Watchlist check complete: "
                    f"{len(watchlists)} checked, {total_releases_found} new releases, "
                    f"{total_downloads_triggered} downloads triggered"
                )
                
            except Exception as e:
                logger.error(f"Error in watchlist check: {e}", exc_info=True)

    async def _scan_discographies(self) -> None:
        """Scan artist discographies for missing albums.
        
        Hey future me - this is the DISCOGRAPHY_SCAN task!
        Migrated from DiscographyWorker._check_discographies()
        
        Flow:
        1. Get all active watchlists with auto_download enabled
        2. For each artist, check discography completeness
        3. If missing albums found, trigger MISSING_ALBUM automation
        
        TOKEN HANDLING: Gets token from _token_manager for API access.
        Uses ArtistService.check_discography() which queries LOCAL soulspot_albums data.
        """
        from soulspot.application.services.artist_service import ArtistService
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.entities import AutomationTrigger
        from soulspot.infrastructure.persistence.repositories import (
            ArtistWatchlistRepository,
        )

        logger.info("📚 Starting discography scan for missing albums...")
        
        async with self._get_session() as session:
            try:
                # Get access token
                access_token = None
                if self._token_manager:
                    access_token = await self._token_manager.get_token_for_background()
                
                if not access_token:
                    logger.warning(
                        "No valid Spotify token - skipping discography scan. "
                        "User needs to re-authenticate via UI."
                    )
                    return
                
                # Create services
                artist_service = ArtistService(session)
                workflow_service = AutomationWorkflowService(session)
                watchlist_repo = ArtistWatchlistRepository(session)
                
                # Get active watchlists
                active_watchlists = await watchlist_repo.list_active(limit=100)
                
                if not active_watchlists:
                    logger.debug("No active watchlists to check")
                    return
                
                logger.info(f"Scanning discographies for {len(active_watchlists)} artists")
                
                total_missing_found = 0
                
                for idx, watchlist in enumerate(active_watchlists):
                    try:
                        # Skip if auto_download disabled
                        if not watchlist.auto_download:
                            continue
                        
                        # Check discography completeness
                        discography_info = await artist_service.check_discography(
                            artist_id=watchlist.artist_id,
                            access_token=access_token,
                        )
                        
                        # Trigger automation for missing albums
                        if discography_info.missing_albums:
                            missing_count = len(discography_info.missing_albums)
                            total_missing_found += missing_count
                            
                            logger.info(
                                f"Found {missing_count} missing albums "
                                f"for artist {watchlist.artist_id}"
                            )
                            
                            await workflow_service.trigger_workflow(
                                trigger=AutomationTrigger.MISSING_ALBUM,
                                context={
                                    "artist_id": str(watchlist.artist_id.value),
                                    "missing_albums": discography_info.missing_albums,
                                    "quality_profile": watchlist.quality_profile,
                                },
                            )
                        
                        # Hey future me - YIELD every 5 artists to keep UI responsive!
                        if idx > 0 and idx % 5 == 0:
                            await asyncio.sleep(0)
                        
                    except Exception as e:
                        logger.error(
                            f"Error scanning discography for artist {watchlist.artist_id}: {e}"
                        )
                        continue
                
                # Update stats
                self._stats["discography_scans"] += 1
                self._stats["missing_albums_found"] += total_missing_found
                
                logger.info(
                    f"✅ Discography scan complete: "
                    f"{len(active_watchlists)} artists, {total_missing_found} missing albums"
                )
                
            except Exception as e:
                logger.error(f"Error in discography scan: {e}", exc_info=True)

    async def _identify_quality_upgrades(self) -> None:
        """Identify tracks that can be upgraded to better quality.
        
        Hey future me - this is the QUALITY_UPGRADE task!
        Migrated from QualityUpgradeWorker._identify_upgrades()
        
        Flow:
        1. Scan library for tracks with lower quality files
        2. Calculate improvement score (bitrate/format upgrade potential)
        3. If score >= threshold (20.0), trigger QUALITY_UPGRADE automation
        
        This scans LOCAL library only - no external API calls needed.
        Improvement threshold: 20.0 = significant upgrade (MP3 → FLAC, 128 → 320)
        """
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.application.services.quality_upgrade_service import (
            QualityUpgradeService,
        )
        from soulspot.domain.entities import AutomationTrigger
        from soulspot.infrastructure.persistence.repositories import TrackRepository

        logger.info("🎵 Starting quality upgrade scan...")
        
        async with self._get_session() as session:
            try:
                # Create services
                quality_service = QualityUpgradeService(session)
                workflow_service = AutomationWorkflowService(session)
                track_repo = TrackRepository(session)
                
                # Hey future me - DON'T use list_all() without limit!
                # Default limit is 100, which would miss 99% of large libraries.
                # Use count_all() + paginated fetch instead!
                total_tracks = await track_repo.count_all()
                
                if total_tracks == 0:
                    logger.debug("No tracks in library to check for upgrades")
                    return
                
                logger.info(f"Scanning {total_tracks} tracks for quality upgrades (paginated)...")
                
                upgrade_candidates_found = 0
                improvement_threshold = 20.0  # Significant upgrade threshold
                batch_size = 500  # Process in batches to avoid memory issues
                offset = 0
                tracks_scanned = 0
                
                while offset < total_tracks:
                    # Fetch batch of tracks
                    all_tracks = await track_repo.list_all(limit=batch_size, offset=offset)
                    
                    if not all_tracks:
                        break
                
                    for track in all_tracks:
                        try:
                            tracks_scanned += 1
                            
                            # Skip tracks without audio files
                            if not track.file_path or not track.is_downloaded():
                                continue
                            
                            # Check if quality service has upgrade identification
                            if not hasattr(quality_service, "identify_upgrade_opportunities"):
                                logger.debug(
                                    "Quality upgrade identification not yet implemented - skipping"
                                )
                                break
                            
                            # Identify upgrade opportunities
                            candidates = await quality_service.identify_upgrade_opportunities(
                                track_id=track.id
                            )
                            
                            for candidate in candidates:
                                if candidate.improvement_score >= improvement_threshold:
                                    logger.info(
                                        f"Found upgrade: {track.title} - "
                                        f"{candidate.current_format}@{candidate.current_bitrate}kbps → "
                                        f"{candidate.target_format}@{candidate.target_bitrate}kbps "
                                        f"(score: {candidate.improvement_score})"
                                    )
                                    
                                    await workflow_service.trigger_workflow(
                                        trigger=AutomationTrigger.QUALITY_UPGRADE,
                                        context={
                                            "track_id": str(track.id.value),
                                            "current_quality": f"{candidate.current_format}@{candidate.current_bitrate}kbps",
                                            "target_quality": f"{candidate.target_format}@{candidate.target_bitrate}kbps",
                                            "improvement_score": candidate.improvement_score,
                                        },
                                    )
                                    upgrade_candidates_found += 1
                            
                        except Exception as e:
                            logger.error(f"Error checking upgrade for track {track.id}: {e}")
                            continue
                    
                    # Move to next batch
                    offset += batch_size
                
                # Update stats
                self._stats["quality_upgrades_found"] += upgrade_candidates_found
                
                logger.info(
                    f"✅ Quality upgrade scan complete: "
                    f"{tracks_scanned} tracks scanned, {upgrade_candidates_found} upgrades found"
                )
                
            except Exception as e:
                logger.error(f"Error in quality upgrade scan: {e}", exc_info=True)