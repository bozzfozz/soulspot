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
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.application.services.app_settings_service import AppSettingsService
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
    """

    ARTIST_SYNC = "artist_sync"  # Sync followed artists from providers
    ALBUM_SYNC = "album_sync"  # Sync albums for artists
    TRACK_SYNC = "track_sync"  # Sync tracks for albums
    ENRICHMENT = "enrichment"  # MusicBrainz metadata enrichment
    IMAGE_SYNC = "image_sync"  # Download/cache images
    DOWNLOAD = "download"  # Coordinate downloads with slskd
    CLEANUP = "cleanup"  # Reset failed downloads, remove orphans


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
}


class TaskScheduler:
    """Schedules and tracks task execution with cooldowns AND dependencies.

    Hey future me - this is the BRAIN of the manager!
    - Tracks last run time for each task type
    - Enforces cooldowns to prevent API spam
    - Prioritizes tasks when multiple are due
    - Respects TASK_DEPENDENCIES (topological order)

    Pattern: Simple priority queue with cooldown enforcement.
    No persistent state - all state derived from DB timestamps.
    
    NEW: Dependency-aware scheduling!
    Tasks only run if their dependencies have completed in this cycle.
    """

    def __init__(self, cooldown_minutes: int = 5) -> None:
        """Initialize scheduler.

        Args:
            cooldown_minutes: Default cooldown between same task types.
        """
        self._cooldown_minutes = cooldown_minutes
        self._last_run: dict[TaskType, datetime] = {}
        self._running: dict[TaskType, bool] = {}
        # Track completed tasks in current cycle for dependency resolution
        self._completed_this_cycle: set[TaskType] = set()

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
        # DEBUG: Log checks for IMAGE_SYNC
        is_image_sync = task_type == TaskType.IMAGE_SYNC
        
        # Check if already running
        if self._running.get(task_type, False):
            if is_image_sync:
                logger.debug(f"[IMAGE_SYNC] Already running - skipping")
            return False

        # Check cooldown
        last_run = self._last_run.get(task_type)
        if last_run is not None:
            cooldown = timedelta(minutes=self._cooldown_minutes)
            time_since = datetime.now(UTC) - last_run
            if time_since < cooldown:
                if is_image_sync:
                    logger.debug(f"[IMAGE_SYNC] On cooldown - {time_since.total_seconds():.0f}s elapsed, need {cooldown.total_seconds():.0f}s")
                return False

        # Check dependencies
        dependencies = TASK_DEPENDENCIES.get(task_type, [])
        if is_image_sync:
            logger.info(f"[IMAGE_SYNC] Checking dependencies: {[d.value for d in dependencies]}")
            logger.info(f"[IMAGE_SYNC] Completed this cycle: {[d.value for d in self._completed_this_cycle]}")
        
        for dep in dependencies:
            if dep not in self._completed_this_cycle:
                # Dependency hasn't completed yet this cycle
                # But if the dependency ran recently (within cooldown), allow
                dep_last_run = self._last_run.get(dep)
                if is_image_sync:
                    logger.debug(f"[IMAGE_SYNC] Dependency {dep.value} not in completed_this_cycle")
                    logger.debug(f"[IMAGE_SYNC] Dependency {dep.value} last_run: {dep_last_run}")
                
                if dep_last_run is None:
                    # Dependency never ran - block this task
                    if is_image_sync:
                        logger.warning(f"[IMAGE_SYNC] BLOCKED: Dependency {dep.value} never ran!")
                    return False
                # If dependency ran recently, consider it "done enough"
                # This handles the case where deps are on different cooldowns
                cooldown = timedelta(minutes=self._cooldown_minutes * 2)
                time_since_dep = datetime.now(UTC) - dep_last_run
                if time_since_dep > cooldown:
                    # Dependency is stale - wait for it to run first
                    if is_image_sync:
                        logger.warning(f"[IMAGE_SYNC] BLOCKED: Dependency {dep.value} is stale ({time_since_dep.total_seconds():.0f}s > {cooldown.total_seconds():.0f}s)")
                    return False
                else:
                    if is_image_sync:
                        logger.debug(f"[IMAGE_SYNC] Dependency {dep.value} ran recently enough ({time_since_dep.total_seconds():.0f}s ago)")

        if is_image_sync:
            logger.info(f"[IMAGE_SYNC] ✅ CAN RUN - all checks passed!")
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

    def get_next_task(self) -> TaskType | None:
        """Get next task that can run, by dependency order then priority.

        Hey future me - this uses TOPOLOGICAL ORDER for dependencies!
        Tasks run in correct dependency order:
        1. ARTIST_SYNC (no deps)
        2. ALBUM_SYNC (depends on ARTIST_SYNC)
        3. TRACK_SYNC (depends on ALBUM_SYNC)
        4. ENRICHMENT, IMAGE_SYNC (depend on ARTIST/ALBUM)
        5. DOWNLOAD (depends on TRACK_SYNC)
        6. CLEANUP (depends on ENRICHMENT, IMAGE_SYNC)

        Returns:
            Next runnable TaskType or None if all on cooldown.
        """
        # Topologically sorted order based on TASK_DEPENDENCIES
        # Tasks with fewer dependencies come first
        topological_order = [
            TaskType.ARTIST_SYNC,  # No deps - runs first
            TaskType.ALBUM_SYNC,  # Deps: ARTIST_SYNC
            TaskType.TRACK_SYNC,  # Deps: ALBUM_SYNC
            TaskType.ENRICHMENT,  # Deps: ARTIST_SYNC, ALBUM_SYNC
            TaskType.IMAGE_SYNC,  # Deps: ARTIST_SYNC, ALBUM_SYNC
            TaskType.DOWNLOAD,  # Deps: TRACK_SYNC
            TaskType.CLEANUP,  # Deps: ENRICHMENT, IMAGE_SYNC - runs last
        ]

        # DEBUG: Log when IMAGE_SYNC is checked
        checking_image = False
        for task_type in topological_order:
            if task_type == TaskType.IMAGE_SYNC:
                checking_image = True
                logger.debug(f"[IMAGE_SYNC] Checking if can run...")
            
            if self.can_run(task_type):
                if task_type == TaskType.IMAGE_SYNC:
                    logger.info(f"[IMAGE_SYNC] ✅ SELECTED as next task!")
                return task_type
            elif checking_image:
                logger.debug(f"[IMAGE_SYNC] ❌ Cannot run (see can_run logs above)")
                checking_image = False

        return None

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status for monitoring.

        Returns:
            Dict with task states and cooldowns.
        """
        now = datetime.now(UTC)
        status = {}

        for task_type in TaskType:
            last_run = self._last_run.get(task_type)
            running = self._running.get(task_type, False)

            if last_run:
                elapsed = (now - last_run).total_seconds()
                next_run_in = max(0, self._cooldown_minutes * 60 - elapsed)
            else:
                next_run_in = 0

            status[task_type.value] = {
                "running": running,
                "last_run": last_run.isoformat() if last_run else None,
                "next_run_in_seconds": next_run_in,
                "can_run": self.can_run(task_type),
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
    ) -> None:
        """Initialize the UnifiedLibraryManager.

        Args:
            session_factory: Factory function to create DB sessions.
            spotify_plugin: Spotify plugin instance (optional).
            deezer_plugin: Deezer plugin instance (optional).
        """
        self._session_factory = session_factory
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin

        # Hey future me - 1 minute cooldown for responsive initial sync!
        # Prevents API spam but allows tasks to complete in reasonable time.
        # Old default was 5 minutes which made users think nothing was happening.
        self._scheduler = TaskScheduler(cooldown_minutes=1)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

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
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the background processing loop.

        Hey future me - this is the ONLY public method to start the manager!
        Creates a background task that runs until stop() is called.
        """
        if self._running:
            logger.warning("UnifiedLibraryManager already running")
            return

        logger.info("Starting UnifiedLibraryManager")
        self._running = True
        self._stop_event.clear()
        self._stats["started_at"] = datetime.now(UTC).isoformat()

        self._task = asyncio.create_task(self._main_loop())

    async def stop(self) -> None:
        """Stop the background processing gracefully.

        Hey future me - this ensures clean shutdown!
        Sets stop event, waits for current task, then exits loop.
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
        Pattern: Start cycle → Run tasks in dependency order → Sleep → Repeat

        The loop runs every 10 seconds to check for work.
        Each task type has its own cooldown (default 5 minutes).
        Tasks respect TASK_DEPENDENCIES - e.g., ALBUM_SYNC waits for ARTIST_SYNC.
        
        NEW: Cycle-based dependency tracking!
        - start_new_cycle() clears completed tasks set
        - Tasks only run when dependencies completed THIS cycle
        - When no tasks are runnable, we start a fresh cycle
        """
        logger.info("UnifiedLibraryManager main loop started")

        try:
            while self._running:
                try:
                    # Check for stop signal with timeout
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(), timeout=10.0
                        )
                        # Stop event was set
                        break
                    except asyncio.TimeoutError:
                        # Timeout - continue to check for work
                        pass

                    # Get next runnable task (respects dependencies)
                    next_task = self._scheduler.get_next_task()
                    
                    if next_task:
                        await self._run_task(next_task)
                    else:
                        # No tasks runnable - all on cooldown or waiting for deps
                        # Start a fresh cycle so dependencies can be re-evaluated
                        # when cooldowns expire
                        self._scheduler.start_new_cycle()
                        logger.debug("All tasks on cooldown, starting new cycle")

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

        Args:
            task_type: The type of task to run.
        """
        logger.debug(f"Running task: {task_type.value}")
        self._scheduler.mark_started(task_type)

        try:
            # Dispatch to correct handler
            match task_type:
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

            self._scheduler.mark_completed(task_type)
            self._stats["tasks_completed"] += 1
            logger.debug(f"Task completed: {task_type.value}")

        except Exception as e:
            self._scheduler.mark_failed(task_type)
            self._stats["tasks_failed"] += 1
            self._stats["last_error"] = f"{task_type.value}: {e!s}"
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
        """
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )
        from soulspot.domain.entities import OwnershipState
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        async with self._get_session() as session:
            # Create service with available plugins
            # Hey future me - plugins might be None if not authenticated!
            followed_service = FollowedArtistsService(
                session=session,
                spotify_plugin=self._spotify_plugin,
                deezer_plugin=self._deezer_plugin,
            )

            logger.info("Starting multi-provider artist sync...")

            # Sync from all providers - this returns deduplicated artists
            # and auto-syncs discography for new artists
            artists, stats = await followed_service.sync_followed_artists_all_providers()

            # Update ownership_state to OWNED for all synced artists
            # This marks them as "user-selected" vs "discovered"
            artist_repo = ArtistRepository(session)
            owned_count = 0

            for artist in artists:
                if artist.ownership_state != OwnershipState.OWNED:
                    artist.ownership_state = OwnershipState.OWNED
                    # Set primary_source based on which service we got them from
                    # The source field tells us where the artist came from
                    if artist.source:
                        artist.primary_source = artist.source.value
                    await artist_repo.update(artist)
                    owned_count += 1

            await session.commit()

            # Update worker stats
            self._stats["artists_synced"] = stats.get("total_fetched", 0)
            self._stats["artists_created"] = stats.get("total_created", 0)
            self._stats["artists_owned"] = owned_count

            logger.info(
                f"✅ Artist sync complete: {stats.get('total_fetched', 0)} fetched, "
                f"{stats.get('total_created', 0)} created, {owned_count} marked OWNED"
            )

            # Log per-provider stats
            provider_stats = stats.get("providers", {})
            for provider, pstats in provider_stats.items():
                if isinstance(pstats, dict):
                    if "error" in pstats:
                        logger.warning(f"  {provider}: ERROR - {pstats['error']}")
                    elif "skipped" in pstats:
                        logger.debug(f"  {provider}: Skipped ({pstats['skipped']})")
                    else:
                        logger.info(
                            f"  {provider}: {pstats.get('total_fetched', 0)} fetched"
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
        """
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )
        from soulspot.domain.entities import OwnershipState
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        async with self._get_session() as session:
            artist_repo = ArtistRepository(session)

            # Get settings for batch size
            settings_service = self._app_settings_service_factory(session)
            batch_size = await settings_service.get_enrichment_batch_size()

            # Get all OWNED artists
            owned_count = await artist_repo.count_by_ownership_state(OwnershipState.OWNED)
            logger.info(f"Starting album sync for {owned_count} OWNED artists...")

            # Process in batches
            offset = 0
            total_albums_added = 0
            total_tracks_added = 0
            artists_processed = 0
            errors = 0

            # Create service once per session
            followed_service = FollowedArtistsService(
                session=session,
                spotify_plugin=self._spotify_plugin,
                deezer_plugin=self._deezer_plugin,
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
                        # Sync discography (albums + tracks)
                        stats = await followed_service.sync_artist_discography_complete(
                            artist_id=str(artist.id.value),
                            include_tracks=True,  # Sync tracks too!
                        )
                        total_albums_added += stats.get("albums_added", 0)
                        total_tracks_added += stats.get("tracks_added", 0)
                        artists_processed += 1

                        logger.debug(
                            f"Synced {artist.name}: {stats.get('albums_added', 0)} albums, "
                            f"{stats.get('tracks_added', 0)} tracks"
                        )

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

            logger.info(
                f"✅ Album sync complete: {artists_processed} artists processed, "
                f"{total_albums_added} albums added, {total_tracks_added} tracks added, "
                f"{errors} errors"
            )

    async def _sync_tracks(self) -> None:
        """Sync tracks for albums missing tracks and handle download state.

        Hey future me - THIS IS THE TRACK SYNC + DOWNLOAD QUEUE TASK!
        Two responsibilities:
        1. Backfill tracks for albums that have no tracks yet
        2. Set download_state=PENDING for new tracks if auto_queue_downloads=True

        Uses Deezer API to fetch tracks (NO AUTH NEEDED!) with rate limiting.
        """
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )
        from soulspot.domain.entities import DownloadState
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            TrackRepository,
        )

        async with self._get_session() as session:
            album_repo = AlbumRepository(session)
            track_repo = TrackRepository(session)

            # Get settings
            settings_service = self._app_settings_service_factory(session)
            auto_queue = await settings_service.auto_queue_downloads_enabled()
            batch_size = await settings_service.get_enrichment_batch_size()

            logger.info(
                f"Starting track sync (auto_queue_downloads={auto_queue})..."
            )

            # Get albums needing track backfill
            albums = await album_repo.get_albums_needing_track_backfill(
                limit=batch_size
            )

            if not albums:
                logger.debug("No albums need track backfill")
                return

            logger.info(f"Found {len(albums)} albums needing track backfill")

            # Create service for track fetching
            followed_service = FollowedArtistsService(
                session=session,
                spotify_plugin=self._spotify_plugin,
                deezer_plugin=self._deezer_plugin,
            )

            tracks_added = 0
            albums_processed = 0
            errors = 0

            for album in albums:
                try:
                    # sync_artist_discography_complete fetches tracks too
                    # But we already have the album, just need tracks
                    # Use _fetch_album_tracks_from_deezer if available
                    # For now, re-sync entire artist discography which handles it
                    stats = await followed_service.sync_artist_discography_complete(
                        artist_id=str(album.artist_id.value),
                        include_tracks=True,
                    )
                    tracks_added += stats.get("tracks_added", 0)
                    albums_processed += 1

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

            logger.info(
                f"✅ Track sync complete: {albums_processed} albums processed, "
                f"{tracks_added} tracks added, {errors} errors"
            )

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
                    f"✅ Enrichment complete: "
                    f"Artists: {stats.get('artists_enriched', 0)}/{stats.get('artists_processed', 0)}, "
                    f"Albums: {stats.get('albums_enriched', 0)}/{stats.get('albums_processed', 0)}"
                )

            except Exception as e:
                logger.warning(f"MusicBrainz enrichment failed: {e}")
                # Don't fail the whole task - just log and continue

    async def _sync_images(self) -> None:
        """Download/cache images for artists and albums.

        Hey future me - THIS SYNCS IMAGE URLS FROM PROVIDERS!
        Finds entities with missing image URLs and fetches from Deezer/Spotify.
        Actual file download is handled separately by ImageService.

        Process:
        1. Find artists/albums with missing image_url
        2. Query Deezer (no auth!) for images
        3. Update image_url in DB
        """
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            ArtistRepository,
        )

        logger.info("[IMAGE_SYNC] ========== _sync_images() CALLED ==========")
        
        async with self._get_session() as session:
            settings_service = self._app_settings_service_factory(session)
            batch_size = await settings_service.get_enrichment_batch_size()
            logger.info(f"[IMAGE_SYNC] Batch size: {batch_size}")

            # Check if image download is enabled
            image_enabled = await settings_service.image_download_enabled()
            logger.info(f"[IMAGE_SYNC] Image download enabled setting: {image_enabled}")
            
            if not image_enabled:
                logger.warning("[IMAGE_SYNC] ⚠️ Image sync DISABLED in settings - early return")
                return

            artist_repo = ArtistRepository(session)
            album_repo = AlbumRepository(session)

            logger.info("[IMAGE_SYNC] Starting image URL sync...")

            # Get artists missing artwork
            artists_updated = 0
            try:
                artists = await artist_repo.get_missing_artwork(limit=batch_size)
                if artists and self._deezer_plugin:
                    for artist in artists:
                        try:
                            # Try to find artist on Deezer and get image
                            if artist.deezer_id:
                                artist_data = await self._deezer_plugin.get_artist(
                                    artist.deezer_id
                                )
                                if artist_data and artist_data.image_url:
                                    from soulspot.domain.value_objects import ImageRef

                                    artist.image = ImageRef(
                                        url=artist_data.image_url,
                                        path=artist.image.path,
                                    )
                                    await artist_repo.update(artist)
                                    artists_updated += 1
                            await asyncio.sleep(0.2)  # Brief pause
                        except Exception as e:
                            logger.debug(f"Failed to get image for {artist.name}: {e}")
            except Exception as e:
                logger.warning(f"Artist image sync failed: {e}")

            # Get albums missing cover
            albums_updated = 0
            try:
                albums = await album_repo.get_albums_without_cover_url(limit=batch_size)
                if albums and self._deezer_plugin:
                    for album in albums:
                        try:
                            if album.deezer_id:
                                album_data = await self._deezer_plugin.get_album(
                                    album.deezer_id
                                )
                                if album_data and album_data.cover_url:
                                    await album_repo.update_cover_url(
                                        album.id, album_data.cover_url
                                    )
                                    albums_updated += 1
                            await asyncio.sleep(0.2)  # Brief pause
                        except Exception as e:
                            logger.debug(f"Failed to get cover for {album.title}: {e}")
            except Exception as e:
                logger.warning(f"Album cover sync failed: {e}")

            await session.commit()

            logger.info(
                f"✅ Image sync complete: {artists_updated} artists, {albums_updated} albums"
            )

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

            logger.info(
                f"📊 Download queue status: "
                f"{pending} pending, {downloading} in progress, "
                f"{downloaded} completed, {failed} failed"
            )

            # If there are pending downloads and QueueDispatcher isn't active,
            # we could trigger it here. But for now, just log.
            if pending > 0:
                logger.info(
                    f"📥 {pending} tracks waiting for download. "
                    "QueueDispatcherWorker should pick them up."
                )

    async def _run_cleanup(self) -> None:
        """Cleanup stale data and reset failed downloads.

        Hey future me - THIS IS THE MAINTENANCE TASK!
        Runs periodically to:
        1. Reset old FAILED downloads to PENDING for retry
        2. Validate file paths still exist
        3. Remove orphaned entities

        Uses cleanup_days from settings to determine "stale" threshold.
        """
        from datetime import timedelta

        from sqlalchemy import update

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

            # Future: Add orphan detection and file validation here

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
        """Get a new database session.

        Hey future me - use this with `async with self._get_session() as session:`
        The session is automatically committed and closed when exiting the context.
        
        session_factory() is an async generator that yields sessions, so we use
        `async with` to consume it as a context manager, not `async for`.
        """
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

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
