"""Application lifecycle management for startup and shutdown tasks.

This module handles the FastAPI lifespan context manager that orchestrates
application initialization and cleanup.

REFACTORED (Dec 2025): Now uses WorkerOrchestrator for centralized worker management!
- All workers are registered with the orchestrator
- Priority-based startup (lower number = starts first)
- Dependency tracking (worker A needs worker B)
- Graceful shutdown with timeouts
- Health status API via orchestrator.get_status()

Worker Categories:
- critical (1-9): Token refresh, session store - must succeed
- sync (10-19): Spotify/Deezer/NewReleases sync
- download (20-29): Download worker, monitor, dispatcher
- enrichment (30-39): Library discovery, image backfill
- maintenance (40-49): Cleanup, duplicate detection
- automation (50-59): Watchlist, discography, quality
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from soulspot.config import Settings, get_settings
from soulspot.domain.exceptions import ConfigurationError
from soulspot.infrastructure.observability import configure_logging
from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


# Hey future me, this validates SQLite paths BEFORE we try creating DB engine! It ensures parent
# directories exist and are writable for both the database file and temporary files. SQLite needs
# to create temp files (-journal, -wal, -shm) in the same directory as the .db file, so we validate
# directory write permissions thoroughly. We DON'T pre-create the .db file here - let SQLite handle
# that to avoid corrupting an empty file! Call this during startup, NOT during request handling
# (too slow). If validation fails, app won't start - better than cryptic SQLAlchemy errors later.
# Only runs for SQLite URLs (returns early for PostgreSQL). The try/except blocks catch filesystem
# permission errors and convert them to clear RuntimeError messages!
def _validate_sqlite_path(settings: Settings) -> None:
    """Validate SQLite database path accessibility before engine creation.

    This function ensures:
    1. Parent directory exists and is writable
    2. Directory allows creating database and temporary files (journal, WAL, etc.)

    Note: We don't pre-create the database file to avoid initialization issues.
    SQLite will create and initialize the file properly on first connection.
    """

    db_path = settings._get_sqlite_db_path()
    if db_path is None:
        return

    # Ensure parent directory exists
    try:
        if db_path.parent and str(db_path.parent) != ".":
            db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured SQLite parent directory exists: %s", db_path.parent)
    except Exception as exc:  # pragma: no cover - safety log
        raise ConfigurationError(
            f"Unable to create SQLite database directory '{db_path.parent}': {exc}. "
            "Ensure the directory path is valid and has write permissions. "
            "Update DATABASE_URL or adjust directory permissions."
        ) from exc

    # Verify directory write permissions by creating a test file
    # This ensures both the database file and temporary files can be created
    try:
        test_file = db_path.parent / f".{db_path.stem}_write_test"
        test_file.write_bytes(b"test")
        test_file.unlink()
        logger.debug(
            "Verified directory write permissions for SQLite files: %s",
            db_path.parent,
        )
    except Exception as exc:  # pragma: no cover - safety log
        raise ConfigurationError(
            f"Unable to write files in database directory '{db_path.parent}': {exc}. "
            "SQLite requires write permissions to create database and journal files. "
            "Ensure the directory is fully writable. "
            "Update DATABASE_URL or adjust directory permissions."
        ) from exc


# Listen future me, @asynccontextmanager makes this a CONTEXT MANAGER for FastAPI lifespan!
# Everything before `yield` runs at STARTUP, everything after runs at SHUTDOWN. FastAPI calls
# this ONCE when server starts and cleans up when server stops. The try/finally ensures cleanup
# ALWAYS runs even if startup fails! If startup crashes, app won't start. Resources like DB
# connections, job queue workers, and auto-import tasks are stored on app.state so routes can
# access them. DON'T put long-running code here without timeouts - blocks server startup!
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks including:
    - Logging configuration
    - Directory creation
    - Database initialization
    - Job queue and download worker startup
    - Token refresh worker startup (background Spotify token management)
    - Auto-import service startup
    - Resource cleanup
    """
    settings = get_settings()

    # Configure structured logging
    configure_logging(
        log_level=settings.log_level,
        json_format=settings.observability.log_json_format,
        app_name=settings.app_name,
    )
    logger.info("Starting application: %s", settings.app_name)

    # Startup
    auto_import_task = None
    job_queue = None
    token_refresh_worker = None
    try:
        # Ensure storage directories exist
        settings.ensure_directories()
        logger.info("Storage directories initialized")

        # Validate SQLite path before initializing database engine
        try:
            _validate_sqlite_path(settings)
            logger.info("SQLite path validation completed successfully")
        except RuntimeError as e:
            logger.error("SQLite path validation failed: %s", e)
            raise

        # Initialize database
        db = Database(settings)
        app.state.db = db
        logger.info("Database initialized: %s", settings.database.url)

        # =================================================================
        # Load runtime settings from DB (log level, etc.)
        # =================================================================
        # Hey future me - this is the STARTUP HOOK for dynamic settings!
        # It reads log_level from DB and applies it before other components start.
        # If no DB value exists, env default is kept. This ensures user's log_level
        # choice persists across container restarts!
        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )

        async with db.session_scope() as startup_session:
            startup_settings_service = AppSettingsService(startup_session)
            try:
                # Load log level from DB (if set), otherwise keep env default
                db_log_level = await startup_settings_service.get_string(
                    "general.log_level", default=None
                )
                if db_log_level:
                    # Apply the DB-stored log level
                    await startup_settings_service.set_log_level(db_log_level)
                    logger.info("Applied log level from database: %s", db_log_level)
                else:
                    logger.debug(
                        "No log level in database, using env default: %s",
                        settings.log_level,
                    )
            except Exception as e:
                # Don't fail startup if settings load fails - just log and continue
                logger.warning(
                    "Failed to load runtime settings from DB: %s (using env defaults)",
                    e,
                )

        # Initialize database-backed session store for OAuth persistence
        from soulspot.application.services.session_store import DatabaseSessionStore

        # Hey future me - we pass the session_scope context manager factory directly!
        # This ensures proper connection cleanup (no more "GC cleaning up non-checked-in connection" errors).
        # The old get_session() generator pattern leaked connections when used with "async for ... break".
        session_store = DatabaseSessionStore(
            session_timeout_seconds=settings.api.session_max_age,
            session_scope=db.session_scope,
        )
        app.state.session_store = session_store
        logger.info("Session store initialized with database persistence")

        # =================================================================
        # Initialize DatabaseTokenManager for background workers
        # =================================================================
        # Hey future me - this is THE central token store for background workers!
        # It's separate from session_store (which is for user requests).
        # Workers like WatchlistWorker, DiscographyWorker use this to get tokens.
        # =================================================================
        # Track startup time for uptime monitoring
        # =================================================================
        from datetime import UTC, datetime

        from soulspot.application.services.token_manager import DatabaseTokenManager
        from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

        app.state.startup_time = datetime.now(UTC)

        # =================================================================
        # Initialize Worker Orchestrator (for tracking & status API)
        # =================================================================
        # Hey future me - the orchestrator tracks all workers for status monitoring!
        # Workers still start/stop via their own code, but orchestrator provides:
        # - Central status API (get_orchestrator().get_status())
        # - Health checks (is_healthy())
        # - Worker discovery (get_worker(name))
        # Full migration to orchestrator-managed start/stop is planned for v2.
        from soulspot.application.workers.orchestrator import (
            get_orchestrator,
        )

        orchestrator = get_orchestrator()
        app.state.orchestrator = orchestrator
        logger.info("Worker orchestrator initialized (tracking mode)")

        # =================================================================
        # Image Download Queue (used by sync services for async downloads)
        # =================================================================
        # Hey future me - Queue wird FRÜH erstellt weil SyncWorker sie brauchen!
        # ImageDownloadQueue ist stateless und hat keine Dependencies.
        # Worker wird später gestartet nachdem alle anderen Workers registriert sind.
        from soulspot.application.services.images import ImageDownloadQueue

        image_download_queue = ImageDownloadQueue()
        app.state.image_download_queue = image_download_queue
        logger.info("Image download queue created (worker starts later)")

        spotify_client = SpotifyClient(settings.spotify)

        # Hey future me - same pattern as session_store: pass session_scope context manager factory!
        db_token_manager = DatabaseTokenManager(
            spotify_client=spotify_client,
            session_scope=db.session_scope,
        )
        app.state.db_token_manager = db_token_manager
        logger.info("Database token manager initialized for background workers")

        # =================================================================
        # CREATE ALL WORKERS (Orchestrator will start them in correct order)
        # =================================================================
        # Hey future me - REFACTORED Dec 2025!
        # Workers are now CREATED but NOT STARTED here.
        # Instead, we register them with the orchestrator which will:
        # 1. Start them in priority order (lower priority = starts first)
        # 2. Check dependencies (e.g., token_refresh before spotify_sync)
        # 3. Handle errors gracefully (required vs optional workers)
        # At the end: await orchestrator.start_all() starts everything!

        # Token refresh worker (proactively refreshes tokens before expiry)
        token_refresh_worker = TokenRefreshWorker(
            token_manager=db_token_manager,
            check_interval_seconds=300,  # Check every 5 minutes
            refresh_threshold_minutes=10,  # Refresh if expires within 10 minutes
        )
        orchestrator.register(
            name="token_refresh",
            worker=token_refresh_worker,
            category="critical",
            priority=1,
            required=True,
        )
        app.state.token_refresh_worker = token_refresh_worker

        # =================================================================
        # UnifiedLibraryManager (THE central library worker)
        # =================================================================
        # Hey future me - THIS IS IT! The ONE worker that replaces:
        # - SpotifySyncWorker (DELETED)
        # - DeezerSyncWorker (DELETED)
        # - NewReleasesSyncWorker (DELETED)
        # - LibraryDiscoveryWorker (DELETED)
        # - ImageBackfillWorker (DELETED)
        # - ImageQueueWorker (DELETED)
        # - AutomationWorkerManager (CONSOLIDATED - watchlist/discography/quality)
        #
        # Architecture: See docs/architecture/UNIFIED_LIBRARY_WORKER.md
        # - Core tasks: ARTIST_SYNC → ALBUM_SYNC → TRACK_SYNC → ENRICHMENT → etc.
        # - Automation tasks: WATCHLIST_CHECK, DISCOGRAPHY_SCAN, QUALITY_UPGRADE
        # - Dependency-based task scheduling (topological order)
        # - Task-specific cooldowns (TASK_COOLDOWNS dict)
        # - Single DB session per task (no SQLite locking issues!)
        from soulspot.application.workers.unified_library_worker import (
            UnifiedLibraryManager,
        )
        from soulspot.infrastructure.plugins import DeezerPlugin, SpotifyPlugin

        # Create plugins for the UnifiedLibraryManager
        # Hey future me - SpotifyPlugin needs token from db_token_manager!
        # DeezerPlugin doesn't need auth for most operations (charts, search, etc.)
        spotify_plugin = SpotifyPlugin(
            client=spotify_client,
            access_token=None,  # Token set dynamically from db_token_manager
        )
        deezer_plugin = DeezerPlugin()

        unified_library_manager = UnifiedLibraryManager(
            session_factory=db.get_session_factory(),
            spotify_plugin=spotify_plugin,
            deezer_plugin=deezer_plugin,
        )
        # Hey future me - set token_manager for automation tasks!
        # WATCHLIST_CHECK, DISCOGRAPHY_SCAN need Spotify API access.
        unified_library_manager.set_token_manager(db_token_manager)
        
        orchestrator.register(
            name="unified_library",
            worker=unified_library_manager,
            category="sync",
            priority=10,  # High priority - main sync worker
            depends_on=["token_refresh"],
            required=True,  # This is now THE sync worker
        )
        app.state.unified_library_manager = unified_library_manager
        logger.info(
            "UnifiedLibraryManager registered "
            "(replaces 6 deprecated workers + AutomationWorkerManager)"
        )

        # Initialize PERSISTENT job queue (survives restarts!)
        # Hey future me - PersistentJobQueue wraps JobQueue with DB persistence.
        # Jobs are stored in background_jobs table and recovered on startup.
        # This prevents losing queued downloads when container restarts!
        from soulspot.application.workers.download_worker import DownloadWorker
        from soulspot.application.workers.persistent_job_queue import (
            PersistentJobQueue,
        )
        from soulspot.infrastructure.integrations.slskd_client import SlskdClient
        from soulspot.infrastructure.persistence.repositories import (
            DownloadRepository,
            TrackRepository,
        )

        # Create persistent job queue with DB session factory
        job_queue = PersistentJobQueue(
            session_factory=db.get_session_factory(),
            max_concurrent_jobs=settings.download.max_concurrent_downloads,
        )

        # Recover pending jobs from database (crashed workers, etc.)
        recovered_count = await job_queue.recover_jobs()
        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} pending jobs from database")

        app.state.job_queue = job_queue

        # =================================================================
        # Create slskd client with DB-first credentials (with env fallback)
        # =================================================================
        # Hey future me - we load slskd credentials from DB first, fall back to env!
        # This matches the pattern used in API dependencies (get_slskd_client).
        # If slskd is not configured, we create a dummy client with default URL -
        # workers will gracefully handle connection failures via circuit breaker.
        from soulspot.application.services.credentials_service import (
            CredentialsService,
        )
        from soulspot.config.settings import SlskdSettings

        # Load credentials from DB with env fallback
        async with db.session_scope() as creds_session:
            creds_service = CredentialsService(
                session=creds_session,
                fallback_settings=settings,  # Enable env fallback for migration
            )
            slskd_creds = await creds_service.get_slskd_credentials()

        # Create SlskdSettings from credentials
        slskd_settings = SlskdSettings(
            url=slskd_creds.url,
            username=slskd_creds.username or "admin",
            password=slskd_creds.password or "changeme",
            api_key=slskd_creds.api_key,
        )

        # Try to create slskd client - may fail if URL is invalid
        try:
            slskd_client = SlskdClient(slskd_settings)
            app.state.slskd_client = slskd_client

            # Log configuration status
            if slskd_creds.is_configured():
                logger.info("slskd client initialized: %s", slskd_creds.url)
            else:
                logger.warning(
                    "slskd credentials not fully configured - download features will be disabled"
                )
        except ValueError as e:
            # slskd URL validation failed - this is non-fatal for app startup
            # Workers will handle missing client gracefully via circuit breaker
            logger.warning(
                "slskd client initialization failed: %s - download features will be disabled",
                e,
            )
            # Create a placeholder client with None to signal it's not available
            app.state.slskd_client = None

        # =================================================================
        # Create a single long-lived session for background workers
        # =================================================================
        # Hey future me - some workers (AutomationWorkerManager, CleanupWorker) need
        # a long-lived session that stays open for the app's lifetime. We use a
        # session_scope context manager that spans the entire app lifecycle.
        # The session is committed/rolled back within each worker operation.
        # This is different from request-scoped sessions which are short-lived.
        #
        # IMPORTANT: Transaction isolation and error handling:
        # - Each worker method is responsible for committing or rolling back its own transactions
        # - If one worker's transaction fails, it should rollback and NOT affect other workers
        # - The shared session means workers should NOT hold transactions open for long periods
        # - Use explicit commit() after each logical operation, not at the end of a loop
        # - On exception, always rollback() before re-raising to clean up the transaction
        #
        # Example pattern for workers:
        #   try:
        #       result = await repo.do_something()
        #       await session.commit()  # Commit immediately after successful operation
        #   except Exception as e:
        #       await session.rollback()  # Always rollback on error
        #       raise
        #
        # The context manager ensures the session is properly closed on app shutdown.
        async with db.session_scope() as worker_session:
            # =================================================================
            # Initialize SLSKD-dependent workers (conditional on slskd_client)
            # =================================================================
            # Hey future me - these workers REQUIRE slskd to be configured!
            # If slskd_client is None (failed validation), we skip them.
            # The app will still start but download features will be disabled.
            #
            # REFACTORED (Dec 2025) - Lock Optimization!
            # DownloadWorker now uses session_factory instead of shared repositories.
            # This prevents SQLite "database is locked" errors by giving each job
            # its own short-lived session.
            if slskd_client is not None:
                download_worker = DownloadWorker(
                    job_queue=job_queue,
                    slskd_client=slskd_client,
                    session_factory=db.session_scope,  # Session-per-job for lock optimization!
                )
                download_worker.register()
                app.state.download_worker = download_worker
                logger.info("Download worker registered (session-per-job mode)")
            else:
                logger.warning("Download worker skipped - slskd client not available")
                app.state.download_worker = None

            # =================================================================
            # REMOVED: LibraryScanWorker - Replaced by UnifiedLibraryManager
            # =================================================================
            # Hey future me - LibraryScanWorker was DELETED!
            # Its functionality is now in UnifiedLibraryManager:
            # - Phase 1: DISCOVER (scan local library for files)
            # See docs/architecture/UNIFIED_LIBRARY_WORKER.md for details.
            # =================================================================

            # =================================================================
            # REMOVED: LibraryDiscoveryWorker - Replaced by UnifiedLibraryManager
            # =================================================================
            # Hey future me - LibraryDiscoveryWorker was DELETED!
            # Its functionality is now in UnifiedLibraryManager:
            # - Phase 2: IDENTIFY (MusicBrainz IDs for artists/albums)
            # - Phase 3: ENRICH (metadata from providers)
            # - Phase 4: EXPAND (discography sync)
            # See docs/architecture/UNIFIED_LIBRARY_WORKER.md for details.
            # =================================================================

            # Start job queue workers
            # Hey future me - SQLite needs fewer workers to avoid "database is locked" errors!
            # Multiple concurrent workers all trying to write to SQLite causes lock contention.
            # For SQLite: use max 1 worker to serialize DB writes.
            # For PostgreSQL: use configured num_workers (default 3).
            is_sqlite = "sqlite" in settings.database.url
            effective_workers = 1 if is_sqlite else settings.download.num_workers
            await job_queue.start(num_workers=effective_workers)
            logger.info(
                "Job queue started with %d workers%s, max concurrent downloads: %d",
                effective_workers,
                " (SQLite mode - serialized)" if is_sqlite else "",
                settings.download.max_concurrent_downloads,
            )

            # =================================================================
            # DownloadStatusWorker (CONSOLIDATED - replaces MonitorWorker + StatusSyncWorker)
            # =================================================================
            # Hey future me - THIS IS THE LIDARR-INSPIRED CONSOLIDATED WORKER!
            # Single slskd poll fetches ALL download state at once:
            # - Active downloads (progress, speed, ETA)
            # - Completed downloads (ready for import)
            # - Failed downloads (error detection)
            # - Stale downloads (stuck > 1 hour)
            #
            # Replaces 2 separate workers with overlapping functionality:
            # - download_monitor_worker.py (506 lines) - DEPRECATED
            # - download_status_sync_worker.py (665 lines) - DEPRECATED
            #
            # See: docs/architecture/DOWNLOAD_WORKER_CONSOLIDATION_PLAN.md
            if slskd_client is not None:
                from soulspot.application.workers.download_status_worker import (
                    DownloadStatusWorker,
                )

                download_status_worker = DownloadStatusWorker(
                    session_factory=db.get_session_factory(),
                    slskd_client=slskd_client,
                    job_queue=job_queue,
                    poll_interval=5,  # Poll slskd every 5 seconds for responsive UI
                    completed_history_hours=24,  # Track completed downloads for 24h
                    max_consecutive_failures=3,  # Open circuit after 3 failures
                    circuit_breaker_timeout=60,  # Wait 60s before retry when circuit open
                )
                download_status_task = asyncio.create_task(
                    download_status_worker.start()
                )
                orchestrator.register_running_task(
                    name="download_status",
                    task=download_status_task,
                    worker=download_status_worker,
                    priority=31,
                    category="download",
                    required=False,
                )
                app.state.download_status_worker = download_status_worker
                app.state.download_status_task = download_status_task
                logger.info("DownloadStatusWorker started (consolidated slskd monitor)")
            else:
                logger.warning(
                    "DownloadStatusWorker skipped - slskd client not available"
                )
                app.state.download_status_worker = None
                app.state.download_status_task = None

            # =================================================================
            # DownloadQueueWorker (CONSOLIDATED - replaces DispatcherWorker + RetryWorker)
            # =================================================================
            # Hey future me - THIS IS THE LIDARR-INSPIRED QUEUE MANAGER!
            # Single poll cycle handles BOTH dispatch AND retry:
            # - Phase 1: Check slskd health (skip if circuit breaker open)
            # - Phase 2: Dispatch WAITING → PENDING downloads to slskd
            # - Phase 3: Schedule FAILED → WAITING retries (with exponential backoff)
            #
            # Replaces 2 separate workers:
            # - queue_dispatcher_worker.py (352 lines) - DEPRECATED
            # - retry_scheduler_worker.py (214 lines) - DEPRECATED
            #
            # BLOCKLIST_ERRORS: Permanent failures that are NOT retried:
            # - file_not_found, user_blocked, corrupted_file, invalid_format
            #
            # See: docs/architecture/DOWNLOAD_WORKER_CONSOLIDATION_PLAN.md
            if slskd_client is not None:
                from soulspot.application.workers.download_queue_worker import (
                    DownloadQueueWorker,
                )

                download_queue_worker = DownloadQueueWorker(
                    session_factory=db.get_session_factory(),
                    slskd_client=slskd_client,
                    job_queue=job_queue,
                    poll_interval=30,  # Check queue every 30 seconds
                    dispatch_delay=2.0,  # 2s between dispatches (rate limiting)
                    max_dispatch_per_cycle=5,  # Max 5 new downloads per cycle
                    max_retries_per_cycle=10,  # Max 10 retries per cycle
                )
                download_queue_task = asyncio.create_task(
                    download_queue_worker.start()
                )
                orchestrator.register_running_task(
                    name="download_queue",
                    task=download_queue_task,
                    worker=download_queue_worker,
                    priority=32,
                    category="download",
                    required=False,
                )
                app.state.download_queue_worker = download_queue_worker
                app.state.download_queue_task = download_queue_task
                logger.info("DownloadQueueWorker started (consolidated dispatch+retry)")
            else:
                logger.warning(
                    "DownloadQueueWorker skipped - slskd client not available"
                )
                app.state.download_queue_worker = None
                app.state.download_queue_task = None

            # =================================================================
            # REMOVED: Download Status Sync Worker - CONSOLIDATED
            # =================================================================
            # Hey future me - this worker was CONSOLIDATED into DownloadStatusWorker!
            # The new worker handles both progress monitoring AND status sync in one
            # poll cycle (Lidarr-inspired pattern). See lines above for the new worker.
            # Old file: download_status_sync_worker.py (665 lines) - DEPRECATED
            # =================================================================

            # =================================================================
            # REMOVED: Retry Scheduler Worker - CONSOLIDATED
            # =================================================================
            # Hey future me - this worker was CONSOLIDATED into DownloadQueueWorker!
            # The new worker handles both dispatch AND retry in one poll cycle.
            # Old file: retry_scheduler_worker.py (214 lines) - DEPRECATED
            # =================================================================

            # =================================================================
            # REMOVED: AutomationWorkerManager - CONSOLIDATED into UnifiedLibraryManager
            # =================================================================
            # Hey future me - AutomationWorkerManager was CONSOLIDATED!
            # Its 3 sub-workers are now TASKS in UnifiedLibraryManager:
            # - WatchlistWorker → TaskType.WATCHLIST_CHECK (1h cooldown)
            # - DiscographyWorker → TaskType.DISCOGRAPHY_SCAN (24h cooldown)
            # - QualityUpgradeWorker → TaskType.QUALITY_UPGRADE (24h cooldown)
            #
            # Benefits of consolidation:
            # - Single DB session shared across all automation tasks
            # - Task dependency management (WATCHLIST_CHECK depends on ALBUM_SYNC)
            # - Unified status API via UnifiedLibraryManager.get_status()
            # - ~835 lines → ~200 lines (76% code reduction)
            #
            # Old file: automation_workers.py - DEPRECATED, do not delete yet
            # See: docs/architecture/AUTOMATION_WORKER_CONSOLIDATION_PLAN.md
            # =================================================================
            app.state.automation_manager = None  # Legacy compat - use unified_library_manager

            # =================================================================
            # Cleanup Worker (optional, default disabled)
            # =================================================================
            # Hey future me - dieser Worker ist GEFÄHRLICH weil er Dateien LÖSCHT!
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.workers.cleanup_worker import CleanupWorker

            app_settings_service = AppSettingsService(worker_session)
            cleanup_worker = CleanupWorker(
                job_queue=job_queue,
                settings_service=app_settings_service,
                downloads_path=settings.storage.download_path,
                music_path=settings.storage.music_path,
                dry_run=False,  # Set to True for testing
            )
            orchestrator.register(
                name="cleanup",
                worker=cleanup_worker,
                category="maintenance",
                priority=70,
                required=False,
            )
            app.state.cleanup_worker = cleanup_worker

            # =================================================================
            # Duplicate Detector Worker (optional, default disabled)
            # =================================================================
            # Hey future me - dieser Worker findet Duplikate via Metadata-Hash.
            from soulspot.application.workers.duplicate_detector_worker import (
                DuplicateDetectorWorker,
            )

            # Hey future me - pass session_scope context manager for proper connection cleanup!
            duplicate_detector_worker = DuplicateDetectorWorker(
                job_queue=job_queue,
                settings_service=app_settings_service,
                session_scope=db.session_scope,
            )
            orchestrator.register(
                name="duplicate_detector",
                worker=duplicate_detector_worker,
                category="maintenance",
                priority=71,
                required=False,
            )
            app.state.duplicate_detector_worker = duplicate_detector_worker

            # =================================================================
            # REMOVED: ImageBackfillWorker + ImageQueueWorker
            # =================================================================
            # Hey future me - These workers were DELETED!
            # Image handling is now in UnifiedLibraryManager:
            # - Phase 5: IMAGERY (Cover URLs + Queue Download Jobs)
            # The ImageDownloadQueue is still used but processed differently.
            # See docs/architecture/UNIFIED_LIBRARY_WORKER.md for details.
            # =================================================================

            # Auto-import service
            from soulspot.application.services import AutoImportService
            from soulspot.infrastructure.persistence.repositories import (
                AlbumRepository,
                ArtistRepository,
                DownloadRepository,
                TrackRepository,
            )

            auto_import_service = AutoImportService(
                settings=settings,
                track_repository=TrackRepository(worker_session),
                artist_repository=ArtistRepository(worker_session),
                album_repository=AlbumRepository(worker_session),
                download_repository=DownloadRepository(worker_session),
                poll_interval=settings.postprocessing.auto_import_poll_interval,
                spotify_plugin=automation_spotify_plugin,
                app_settings_service=app_settings_service,
            )
            app.state.auto_import = auto_import_service
            # AutoImportService runs as blocking coroutine
            auto_import_task = asyncio.create_task(auto_import_service.start())
            orchestrator.register_running_task(
                name="auto_import",
                task=auto_import_task,
                worker=auto_import_service,
                priority=90,
                category="automation",
                required=False,
            )
            logger.info("Auto-import service started")

            # =================================================================
            # START ALL ORCHESTRATOR-MANAGED WORKERS
            # =================================================================
            # Hey future me - THIS IS WHERE THE MAGIC HAPPENS!
            # All workers registered with orchestrator.register() (not register_running_task)
            # will be started here in priority order!
            logger.info("Starting all orchestrator-managed workers...")
            start_success = await orchestrator.start_all()
            if not start_success:
                logger.error("Some required workers failed to start!")
                # Don't raise - let app continue with degraded functionality
            else:
                logger.info("All orchestrator-managed workers started successfully")

            # Log orchestrator summary
            status = orchestrator.get_status()
            logger.info(
                "Worker orchestrator tracking %d workers: %s",
                status["total_workers"],
                ", ".join(status["workers"].keys()),
            )

            # Yield to keep the app running - session stays open during app lifetime
            yield

    except Exception as e:
        logger.exception("Error during application startup: %s", e)
        raise
    finally:
        # =================================================================
        # SHUTDOWN via Worker Orchestrator (Refactored Dec 2025)
        # =================================================================
        # Hey future me - der Orchestrator stoppt ALLE Worker in einer Zeile!
        # Früher waren das 160+ Zeilen mit try/except für jeden Worker.
        # Der Orchestrator:
        # - Stoppt Worker in umgekehrter Priority-Reihenfolge
        # - Hat Timeout per Worker (default 10s)
        # - Loggt jeden Stop-Vorgang
        # - Fängt Exceptions pro Worker, bricht nicht ab
        #
        # Worker die NICHT beim Orchestrator registriert sind:
        # - job_queue: Wird separat gestoppt (ist kein "Worker")
        # - auto_import: Wird separat gestoppt (task-basiert)
        # - database: Wird separat geschlossen
        # - http_pool: Wird separat geschlossen

        logger.info("Shutting down application")

        # 1. Stop ALL workers via orchestrator (replaces 160+ lines of try/except!)
        orchestrator = getattr(app.state, "orchestrator", None)
        if orchestrator is not None:
            await orchestrator.stop_all()
        else:
            logger.warning(
                "Orchestrator not found - workers may not be stopped properly"
            )
            # Fallback: Stop critical workers manually if orchestrator missing
            for worker_name in [
                "token_refresh_worker",
                "unified_library_manager",  # THE central worker now
            ]:
                worker = getattr(app.state, worker_name, None)
                if worker is not None:
                    try:
                        await worker.stop()
                        logger.info(f"{worker_name} stopped (fallback)")
                    except Exception as e:
                        logger.exception(f"Error stopping {worker_name}: {e}")

        # 2. Stop job queue (not a worker, manages download jobs)
        if job_queue is not None:
            try:
                logger.info("Stopping job queue...")
                await job_queue.stop()
                logger.info("Job queue stopped")
            except Exception as e:
                logger.exception("Error stopping job queue: %s", e)

        # 3. Stop auto-import service (task-based, special handling)
        if auto_import_task is not None:
            try:
                if hasattr(app.state, "auto_import"):
                    await app.state.auto_import.stop()
                    try:
                        await asyncio.wait_for(
                            auto_import_task,
                            timeout=settings.observability.shutdown_timeout,
                        )
                    except TimeoutError:
                        auto_import_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await auto_import_task
                    logger.info("Auto-import service stopped")
            except Exception as e:
                logger.exception("Error stopping auto-import service: %s", e)

        # 4. Close database connection
        try:
            if hasattr(app.state, "db"):
                await app.state.db.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.exception("Error closing database: %s", e)

        # 5. Close HTTP client pool (release all TCP connections)
        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            await HttpClientPool.close()
            logger.info("HTTP client pool closed")
        except Exception as e:
            logger.exception("Error closing HTTP client pool: %s", e)
