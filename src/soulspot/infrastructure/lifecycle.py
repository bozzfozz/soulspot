"""Application lifecycle management for startup and shutdown tasks.

This module handles the FastAPI lifespan context manager that orchestrates
application initialization and cleanup.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any

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

        # Initialize database-backed session store for OAuth persistence
        from soulspot.application.services.session_store import DatabaseSessionStore

        async def get_db_session_for_store() -> AsyncGenerator[Any, None]:
            """Get DB session for session store operations."""
            async for session in db.get_session():
                yield session

        session_store = DatabaseSessionStore(
            session_timeout_seconds=settings.api.session_max_age,
            get_db_session=get_db_session_for_store,
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

        db_token_manager = DatabaseTokenManager(
            spotify_client=spotify_client,
            get_db_session=get_db_session_for_store,
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

        # Initialize download worker with repositories
        # Note: These will be created per-request in real usage, but we need instances for worker
        async for session in db.get_session():
            slskd_client = SlskdClient(settings.slskd)
            track_repository = TrackRepository(session)
            download_repository = DownloadRepository(session)

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

            break

        # Start job queue workers
        await job_queue.start(num_workers=settings.download.num_workers)
        logger.info(
            "Job queue started with %d workers, max concurrent downloads: %d",
            settings.download.num_workers,
            settings.download.max_concurrent_downloads,
        )

        # Start auto-import service in the background
        from soulspot.application.services import AutoImportService
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            ArtistRepository,
        )

        # Create repositories for auto-import service
        async for session in db.get_session():
            auto_import_service = AutoImportService(
                settings=settings,
                track_repository=track_repository,
                artist_repository=ArtistRepository(session),
                album_repository=AlbumRepository(session),
                poll_interval=settings.postprocessing.auto_import_poll_interval,
            )
            app.state.auto_import = auto_import_service
            auto_import_task = asyncio.create_task(auto_import_service.start())
            logger.info("Auto-import service started")
            break

        yield

    except Exception as e:
        logger.exception("Error during application startup: %s", e)
        raise
    finally:
        # Shutdown - always attempt cleanup
        logger.info("Shutting down application")

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
