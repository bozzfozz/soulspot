"""FastAPI application entry point."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from soulspot.api.routers import api_router, ui
from soulspot.config import Settings, get_settings
from soulspot.domain.exceptions import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidStateException,
    ValidationException,
)
from soulspot.infrastructure.observability import configure_logging
from soulspot.infrastructure.observability.health import (
    HealthStatus,
    check_database_health,
    check_musicbrainz_health,
    check_slskd_health,
    check_spotify_health,
)
from soulspot.infrastructure.observability.middleware import RequestLoggingMiddleware
from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


# Hey future me, this registers GLOBAL exception handlers for the entire app! FastAPI will call
# these whenever matching exceptions are raised in ANY endpoint. We convert domain exceptions
# (ValidationException, EntityNotFoundException, etc.) into proper HTTP responses with correct
# status codes. Without this, domain exceptions would leak as 500 errors with stack traces to
# clients! The @app.exception_handler decorator MUST be called during app setup BEFORE any
# requests arrive. Don't try to register handlers after app starts - won't work!
def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers for domain and validation exceptions.

    This function registers handlers for:
    - Domain exceptions (ValidationException, EntityNotFoundException, etc.)
    - Pydantic validation errors (RequestValidationError)
    - JSON decode errors
    - Standard Python ValueError
    - HTTP exceptions with proper logging

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(
        request: Request, exc: ValidationException
    ) -> JSONResponse:
        """Handle domain validation exceptions with 422 Unprocessable Entity."""
        logger.warning(
            "Validation error at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.message},
        )

    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_exception_handler(
        request: Request, exc: EntityNotFoundException
    ) -> JSONResponse:
        """Handle entity not found exceptions with 404 Not Found."""
        logger.info(
            "Entity not found at %s: %s %s",
            request.url.path,
            exc.entity_type,
            exc.entity_id,
            extra={
                "path": request.url.path,
                "entity_type": exc.entity_type,
                "entity_id": exc.entity_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )

    @app.exception_handler(DuplicateEntityException)
    async def duplicate_entity_exception_handler(
        request: Request, exc: DuplicateEntityException
    ) -> JSONResponse:
        """Handle duplicate entity exceptions with 409 Conflict."""
        logger.warning(
            "Duplicate entity at %s: %s %s",
            request.url.path,
            exc.entity_type,
            exc.entity_id,
            extra={
                "path": request.url.path,
                "entity_type": exc.entity_type,
                "entity_id": exc.entity_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message},
        )

    @app.exception_handler(InvalidStateException)
    async def invalid_state_exception_handler(
        request: Request, exc: InvalidStateException
    ) -> JSONResponse:
        """Handle invalid state exceptions with 400 Bad Request."""
        logger.warning(
            "Invalid state at %s: %s",
            request.url.path,
            exc.message,
            extra={"path": request.url.path, "error": exc.message},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic request validation errors with 422 Unprocessable Entity."""
        logger.warning(
            "Request validation error at %s: %s",
            request.url.path,
            exc.errors(),
            extra={"path": request.url.path, "errors": exc.errors()},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(json.JSONDecodeError)
    async def json_decode_error_handler(
        request: Request, exc: json.JSONDecodeError
    ) -> JSONResponse:
        """Handle malformed JSON with 400 Bad Request."""
        logger.warning(
            "Malformed JSON at %s: %s",
            request.url.path,
            str(exc),
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Malformed JSON: {exc.msg}"},
        )

    @app.exception_handler(ValueError)
    async def value_error_exception_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        """Handle ValueError with 422 Unprocessable Entity for validation-related errors."""
        logger.warning(
            "Value error at %s: %s",
            request.url.path,
            str(exc),
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions with proper logging."""
        if exc.status_code >= 500:
            logger.error(
                "HTTP error %d at %s: %s",
                exc.status_code,
                request.url.path,
                exc.detail,
                extra={
                    "path": request.url.path,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        else:
            logger.info(
                "HTTP error %d at %s: %s",
                exc.status_code,
                request.url.path,
                exc.detail,
                extra={
                    "path": request.url.path,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )


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
            logger.debug(
                "Ensured SQLite parent directory exists: %s", db_path.parent
            )
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

        # Initialize widget registry
        from soulspot.infrastructure.persistence.widget_registry import (
            initialize_widget_registry,
        )

        try:
            async for session in db.get_session():
                await initialize_widget_registry(session)
                break
            logger.info("Widget registry initialized")
        except Exception as e:
            logger.error(
                "Failed to initialize widget registry: %s. "
                "This may indicate database tables are missing. "
                "Run 'alembic upgrade head' to create database schema.",
                e,
            )
            raise

        # Initialize database-backed session store for OAuth persistence
        from soulspot.application.services.session_store import DatabaseSessionStore

        async def get_db_session_for_store() -> AsyncGenerator[Any, None]:
            """Get DB session for session store operations."""
            async for session in db.get_session():
                yield session

        session_store = DatabaseSessionStore(
            session_timeout_seconds=3600,  # 1 hour session timeout
            get_db_session=get_db_session_for_store,
        )
        app.state.session_store = session_store
        logger.info("Session store initialized with database persistence")

        # Initialize job queue with configured max concurrent downloads
        from soulspot.application.workers.download_worker import DownloadWorker
        from soulspot.application.workers.job_queue import JobQueue
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
            break

        # Start job queue workers
        await job_queue.start(num_workers=3)
        logger.info(
            "Job queue started with %d workers, max concurrent downloads: %d",
            3,
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
                poll_interval=60,
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
                        await asyncio.wait_for(auto_import_task, timeout=5)
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


# Yo, this is the APP FACTORY! Creates a new FastAPI instance with all middleware, routes, and
# exception handlers configured. Called ONCE at module load to create `app` singleton at bottom of
# file. Takes optional Settings for testing (dependency injection). Middleware order MATTERS:
# GZip first (outermost), then logging, then CORS. Exception handlers registered BEFORE routes!
# Static files mounted BEFORE routes to avoid route conflicts. Use this pattern if you ever need
# multiple app instances (like in tests). DON'T call this multiple times in production!
def create_app(settings: Settings | None = None) -> FastAPI:
    """Create FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
        ## SoulSpot API

        Intelligente Musik-Download-Anwendung mit Spotify-Playlist-Synchronisation und Soulseek-Integration.

        ### Features
        - 🎵 **Spotify Integration**: OAuth PKCE authentication and playlist management
        - ⬇️ **Automated Downloads**: Soulseek downloads via slskd
        - 📊 **Metadata Enrichment**: MusicBrainz and CoverArtArchive integration
        - 🗂️ **File Organization**: Automatic file management and tagging
        - 🔄 **Worker System**: Asynchronous job processing

        ### Authentication
        Most endpoints require Spotify OAuth authentication. Use the `/auth/spotify/login` endpoint to start the OAuth flow.

        ### Rate Limiting
        - MusicBrainz: 1 request per second (enforced by circuit breaker)
        - Spotify: API-dependent (handled with exponential backoff)

        ### Error Handling
        All errors include a `correlation_id` for debugging. Check logs with this ID for detailed information.

        ### Documentation
        - [GitHub Repository](https://github.com/bozzfozz/soulspot)
        - [Setup Guide](https://github.com/bozzfozz/soulspot/blob/main/docs/setup-guide.md)
        - [Troubleshooting](https://github.com/bozzfozz/soulspot/blob/main/docs/troubleshooting-guide.md)
        """,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        contact={
            "name": "SoulSpot",
            "url": "https://github.com/bozzfozz/soulspot",
        },
        license_info={
            "name": "TBD",
        },
    )

    # Response compression middleware (must be first)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom exception handlers
    register_exception_handlers(app)

    # Mount static files if directory exists
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static files mounted from: %s", static_dir)
    else:
        logger.warning("Static directory not found: %s", static_dir)

    # Include API routers
    app.include_router(api_router, prefix="/api")

    # Include UI router at root
    app.include_router(ui.router, tags=["UI"])

    # Hey, this is the BASIC health check - just returns "alive" without checking dependencies!
    # Kubernetes uses this for liveness probe (is process running?). FAST because no DB/API calls.
    # For detailed checks (DB connectivity, external services), use /ready endpoint instead. If this
    # returns 500, Kubernetes will restart the pod thinking process is hung. Keep it lightweight!
    # Health check endpoint
    @app.get(
        "/health",
        tags=["Health"],
        summary="Basic health check",
        description="Returns basic application health status. Use /ready for detailed dependency checks.",
        response_description="Application health status",
    )
    async def health_check() -> dict[str, Any]:
        """Health check endpoint.

        Returns:
            dict: Health status including app name and profile.

        Example response:
            {
                "status": "healthy",
                "app_name": "SoulSpot",
                "profile": "simple"
            }
        """
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "profile": settings.profile.value,
        }

    # Yo future me, this is the DETAILED readiness check - Kubernetes readiness probe! Checks DB
    # connectivity, external services (slskd, Spotify, MusicBrainz) if enabled. Takes longer than
    # /health because it makes real network calls. If this fails, Kubernetes STOPS routing traffic
    # to pod but doesn't restart it (gives time to recover). Can be slow during startup while DB
    # migrations run. The overall_status logic: UNHEALTHY if any critical service down, DEGRADED
    # if optional services down but app still works. Don't add checks for non-critical features!
    # Readiness check endpoint with dependency checks
    @app.get(
        "/ready",
        tags=["Health"],
        summary="Readiness check with dependencies",
        description="Returns detailed readiness status including database and external service health.",
        response_description="Readiness status with dependency health checks",
    )
    async def readiness_check() -> dict[str, Any]:
        """Readiness check endpoint with database and dependency connectivity checks.

        Returns:
            dict: Readiness status with detailed health checks for all dependencies.

        Example response:
            {
                "status": "ready",
                "checks": {
                    "database": {"status": "healthy", "message": "Connected"},
                    "slskd": {"status": "healthy", "message": "Connected"},
                    "spotify": {"status": "degraded", "message": "No credentials"},
                    "musicbrainz": {"status": "healthy", "message": "Available"},
                    "circuit_breakers": {
                        "spotify": "CLOSED",
                        "musicbrainz": "CLOSED",
                        "slskd": "CLOSED"
                    }
                }
            }
        """
        checks = {}
        overall_status = HealthStatus.HEALTHY

        # Database connectivity check
        if hasattr(app.state, "db"):
            db_check = await check_database_health(app.state.db)
            checks["database"] = {
                "status": db_check.status.value,
                "message": db_check.message,
            }
            if db_check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                db_check.status == HealthStatus.DEGRADED
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.DEGRADED
        else:
            checks["database"] = {
                "status": HealthStatus.UNHEALTHY.value,
                "message": "Database not initialized",
            }
            overall_status = HealthStatus.UNHEALTHY

        # External service health checks (if enabled)
        if settings.observability.enable_dependency_health_checks:
            timeout = settings.observability.health_check_timeout

            # slskd health check
            slskd_check = await check_slskd_health(settings.slskd.url, timeout=timeout)
            checks["slskd"] = {
                "status": slskd_check.status.value,
                "message": slskd_check.message,
            }
            if (
                slskd_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

            # Spotify health check
            spotify_check = await check_spotify_health(timeout=timeout)
            checks["spotify"] = {
                "status": spotify_check.status.value,
                "message": spotify_check.message,
            }
            # Update overall status based on Spotify check
            if (
                spotify_check.status == HealthStatus.UNHEALTHY
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                spotify_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

            # MusicBrainz health check
            mb_check = await check_musicbrainz_health(timeout=timeout)
            checks["musicbrainz"] = {
                "status": mb_check.status.value,
                "message": mb_check.message,
            }
            # Update overall status based on MusicBrainz check
            if (
                mb_check.status == HealthStatus.UNHEALTHY
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                mb_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "checks": checks,
        }

    # Listen, /live is the SIMPLEST liveness probe - literally just returns JSON if process is alive!
    # Kubernetes uses this to detect if app is hung/deadlocked. If this 500s or times out, pod gets
    # killed and restarted. NO database checks, NO external calls - just "can Python respond?". Even
    # simpler than /health! If this fails, something is REALLY broken (out of memory, deadlock, etc).
    # Liveness probe endpoint
    @app.get("/live", tags=["Health"])
    async def liveness_check() -> dict[str, str]:
        """Liveness check endpoint - returns OK if application is running."""
        return {"status": "alive"}

    return app


# Create application instance
app = create_app()


# Hey, this is the CLI entry point! Called when you run `python -m soulspot.main` or `soulspot` CLI
# command (defined in pyproject.toml). Starts uvicorn development server with hot-reload if debug=True.
# The string "soulspot.main:app" tells uvicorn to import app from this module (enables hot-reload).
# For production, use gunicorn/uvicorn workers instead! This is single-process, single-threaded dev mode.
# If you change settings while running with reload=True, server auto-restarts. DON'T use in production!
def main() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "soulspot.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
