"""Application lifecycle management for startup and shutdown tasks.

This module handles the FastAPI lifespan context manager that orchestrates
application initialization and cleanup.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from soulspot.config import Settings, get_settings
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
        raise RuntimeError(
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
        raise RuntimeError(
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
                    logger.info(
                        "Applied log level from database: %s", db_log_level
                    )
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
        from soulspot.application.services.token_manager import DatabaseTokenManager
        from soulspot.application.workers.token_refresh_worker import TokenRefreshWorker
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

        spotify_client = SpotifyClient(settings.spotify)

        # Hey future me - same pattern as session_store: pass session_scope context manager factory!
        db_token_manager = DatabaseTokenManager(
            spotify_client=spotify_client,
            session_scope=db.session_scope,
        )
        app.state.db_token_manager = db_token_manager
        logger.info("Database token manager initialized for background workers")

        # Start token refresh worker (proactively refreshes tokens before expiry)
        token_refresh_worker = TokenRefreshWorker(
            token_manager=db_token_manager,
            check_interval_seconds=300,  # Check every 5 minutes
            refresh_threshold_minutes=10,  # Refresh if expires within 10 minutes
        )
        await token_refresh_worker.start()
        app.state.token_refresh_worker = token_refresh_worker
        logger.info("Token refresh worker started (checks every 5 min)")

        # =================================================================
        # Start Spotify Sync Worker (automatic background syncing)
        # =================================================================
        # Hey future me - this worker automatically syncs Spotify data based on settings!
        # It respects the app_settings table for enable/disable and intervals.
        # Runs after token_refresh_worker so tokens are always fresh.
        from soulspot.application.workers.spotify_sync_worker import SpotifySyncWorker

        spotify_sync_worker = SpotifySyncWorker(
            db=db,
            token_manager=db_token_manager,
            settings=settings,
            check_interval_seconds=60,  # Check every minute if syncs are due
        )
        await spotify_sync_worker.start()
        app.state.spotify_sync_worker = spotify_sync_worker
        logger.info("Spotify sync worker started (checks every 60s)")

        # Initialize job queue with configured max concurrent downloads
        from soulspot.application.workers.download_worker import DownloadWorker
        from soulspot.application.workers.job_queue import JobQueue
        from soulspot.application.workers.library_scan_worker import LibraryScanWorker
        from soulspot.infrastructure.integrations.slskd_client import SlskdClient
        from soulspot.infrastructure.persistence.repositories import (
            DownloadRepository,
            TrackRepository,
        )

        job_queue = JobQueue(
            max_concurrent_jobs=settings.download.max_concurrent_downloads
        )
        app.state.job_queue = job_queue

        # Create slskd client outside the session context (it doesn't need DB)
        slskd_client = SlskdClient(settings.slskd)
        app.state.slskd_client = slskd_client

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
            # Initialize download worker with repositories
            track_repository = TrackRepository(worker_session)
            download_repository = DownloadRepository(worker_session)

            download_worker = DownloadWorker(
                job_queue=job_queue,
                slskd_client=slskd_client,
                track_repository=track_repository,
                download_repository=download_repository,
            )
            download_worker.register()
            app.state.download_worker = download_worker

            # Initialize library scan worker
            library_scan_worker = LibraryScanWorker(
                job_queue=job_queue,
                db=db,
                settings=settings,
            )
            library_scan_worker.register()
            app.state.library_scan_worker = library_scan_worker
            logger.info("Library scan worker registered")

            # Initialize library enrichment worker
            # Hey future me - this worker enriches local library items with Spotify data!
            # It runs automatically after library scans (if auto_enrichment_enabled)
            from soulspot.application.workers.library_enrichment_worker import (
                LibraryEnrichmentWorker,
            )

            library_enrichment_worker = LibraryEnrichmentWorker(
                job_queue=job_queue,
                db=db,
                settings=settings,
            )
            library_enrichment_worker.register()
            app.state.library_enrichment_worker = library_enrichment_worker
            logger.info("Library enrichment worker registered")

            # Start job queue workers
            await job_queue.start(num_workers=settings.download.num_workers)
            logger.info(
                "Job queue started with %d workers, max concurrent downloads: %d",
                settings.download.num_workers,
                settings.download.max_concurrent_downloads,
            )

            # =================================================================
            # Start Download Monitor Worker (tracks slskd download progress)
            # =================================================================
            # Hey future me - dieser Worker ÜBERWACHT laufende Downloads!
            # Er pollt slskd alle X Sekunden und updated Job.result mit Progress.
            # Ohne ihn bleiben Jobs ewig in RUNNING Status ohne echten Progress.
            from soulspot.application.workers.download_monitor_worker import (
                DownloadMonitorWorker,
            )

            download_monitor_worker = DownloadMonitorWorker(
                job_queue=job_queue,
                slskd_client=slskd_client,
                poll_interval_seconds=10,  # Poll every 10 seconds
            )
            await download_monitor_worker.start()
            app.state.download_monitor_worker = download_monitor_worker
            logger.info("Download monitor worker started (polls every 10s)")

            # =================================================================
            # Start Automation Workers (optional, controlled by settings)
            # =================================================================
            # Hey future me - diese Worker sind OPTIONAL und default DISABLED!
            # Sie laufen im Hintergrund und checken nur, ob enabled via AppSettingsService.
            # Wenn disabled, loggen sie nur "skipping" und warten auf nächsten Interval.
            from soulspot.application.workers.automation_workers import (
                AutomationWorkerManager,
            )

            automation_manager = AutomationWorkerManager(
                session=worker_session,
                spotify_client=spotify_client,
                token_manager=db_token_manager,
                watchlist_interval=3600,  # 1 hour
                discography_interval=86400,  # 24 hours
                quality_interval=86400,  # 24 hours
            )
            await automation_manager.start_all()
            app.state.automation_manager = automation_manager
            logger.info("Automation workers started (watchlist/discography/quality)")

            # =================================================================
            # Start Cleanup Worker (optional, default disabled)
            # =================================================================
            # Hey future me - dieser Worker ist GEFÄHRLICH weil er Dateien LÖSCHT!
            # Deswegen ist er per Default disabled. User muss explizit enablen.
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
            await cleanup_worker.start()
            app.state.cleanup_worker = cleanup_worker
            logger.info("Cleanup worker started (checks daily, disabled by default)")

            # =================================================================
            # Start Duplicate Detector Worker (optional, default disabled)
            # =================================================================
            # Hey future me - dieser Worker findet Duplikate via Metadata-Hash.
            # Er ist CPU-intensiv, deswegen läuft er nur 1x pro Woche default.
            from soulspot.application.workers.duplicate_detector_worker import (
                DuplicateDetectorWorker,
            )

            # Hey future me - pass session_scope context manager for proper connection cleanup!
            duplicate_detector_worker = DuplicateDetectorWorker(
                job_queue=job_queue,
                settings_service=app_settings_service,
                session_scope=db.session_scope,
            )
            await duplicate_detector_worker.start()
            app.state.duplicate_detector_worker = duplicate_detector_worker
            logger.info(
                "Duplicate detector worker started (weekly scan, disabled by default)"
            )

            # Start auto-import service in the background
            from soulspot.application.services import AutoImportService
            from soulspot.infrastructure.persistence.repositories import (
                AlbumRepository,
                ArtistRepository,
            )

            # Create auto-import service using the worker session
            auto_import_service = AutoImportService(
                settings=settings,
                track_repository=track_repository,
                artist_repository=ArtistRepository(worker_session),
                album_repository=AlbumRepository(worker_session),
                poll_interval=settings.postprocessing.auto_import_poll_interval,
                app_settings_service=app_settings_service,  # For dynamic naming templates
            )
            app.state.auto_import = auto_import_service
            auto_import_task = asyncio.create_task(auto_import_service.start())
            logger.info("Auto-import service started")

            # Yield to keep the app running - session stays open during app lifetime
            yield

    except Exception as e:
        logger.exception("Error during application startup: %s", e)
        raise
    finally:
        # Shutdown - always attempt cleanup
        logger.info("Shutting down application")

        # Stop duplicate detector worker first (least critical)
        if hasattr(app.state, "duplicate_detector_worker"):
            try:
                logger.info("Stopping duplicate detector worker...")
                await app.state.duplicate_detector_worker.stop()
                logger.info("Duplicate detector worker stopped")
            except Exception as e:
                logger.exception("Error stopping duplicate detector worker: %s", e)

        # Stop cleanup worker
        if hasattr(app.state, "cleanup_worker"):
            try:
                logger.info("Stopping cleanup worker...")
                await app.state.cleanup_worker.stop()
                logger.info("Cleanup worker stopped")
            except Exception as e:
                logger.exception("Error stopping cleanup worker: %s", e)

        # Stop automation workers
        if hasattr(app.state, "automation_manager"):
            try:
                logger.info("Stopping automation workers...")
                await app.state.automation_manager.stop_all()
                logger.info("Automation workers stopped")
            except Exception as e:
                logger.exception("Error stopping automation workers: %s", e)

        # Stop download monitor worker
        if hasattr(app.state, "download_monitor_worker"):
            try:
                logger.info("Stopping download monitor worker...")
                await app.state.download_monitor_worker.stop()
                logger.info("Download monitor worker stopped")
            except Exception as e:
                logger.exception("Error stopping download monitor worker: %s", e)

        # Stop Spotify sync worker first (depends on token manager)
        if hasattr(app.state, "spotify_sync_worker"):
            try:
                logger.info("Stopping Spotify sync worker...")
                await app.state.spotify_sync_worker.stop()
                logger.info("Spotify sync worker stopped")
            except Exception as e:
                logger.exception("Error stopping Spotify sync worker: %s", e)

        # Stop token refresh worker
        if token_refresh_worker is not None:
            try:
                logger.info("Stopping token refresh worker...")
                await token_refresh_worker.stop()
                logger.info("Token refresh worker stopped")
            except Exception as e:
                logger.exception("Error stopping token refresh worker: %s", e)

        # Stop job queue
        if job_queue is not None:
            try:
                logger.info("Stopping job queue...")
                await job_queue.stop()
                logger.info("Job queue stopped")
            except Exception as e:
                logger.exception("Error stopping job queue: %s", e)

        # Stop auto-import service
        if auto_import_task is not None:
            try:
                if hasattr(app.state, "auto_import"):
                    await app.state.auto_import.stop()
                    # Wait for task to complete gracefully with timeout
                    try:
                        await asyncio.wait_for(
                            auto_import_task,
                            timeout=settings.observability.shutdown_timeout,
                        )
                    except TimeoutError:
                        # If timeout, cancel forcefully
                        auto_import_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await auto_import_task
                    logger.info("Auto-import service stopped")
            except Exception as e:
                logger.exception("Error stopping auto-import service: %s", e)

        # Close database
        try:
            if hasattr(app.state, "db"):
                await app.state.db.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.exception("Error closing database: %s", e)
