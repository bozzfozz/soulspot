"""FastAPI application entry point."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from soulspot.api.routers import api_router, ui
from soulspot.config import Settings, get_settings
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks including:
    - Logging configuration
    - Directory creation
    - Database initialization
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
    try:
        # Ensure storage directories exist
        settings.ensure_directories()
        logger.info("Storage directories initialized")

        # Initialize database
        db = Database(settings)
        app.state.db = db
        logger.info("Database initialized: %s", settings.database.url)

        # Start auto-import service in the background
        from soulspot.application.services import AutoImportService

        auto_import_service = AutoImportService(settings, poll_interval=60)
        app.state.auto_import = auto_import_service
        auto_import_task = asyncio.create_task(auto_import_service.start())
        logger.info("Auto-import service started")

        yield

    except Exception as e:
        logger.exception("Error during application startup: %s", e)
        raise
    finally:
        # Shutdown - always attempt cleanup
        logger.info("Shutting down application")

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


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
        ## SoulSpot Bridge API

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
        - [GitHub Repository](https://github.com/bozzfozz/soulspot-bridge)
        - [Setup Guide](https://github.com/bozzfozz/soulspot-bridge/blob/main/docs/setup-guide.md)
        - [Troubleshooting](https://github.com/bozzfozz/soulspot-bridge/blob/main/docs/troubleshooting-guide.md)
        """,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        contact={
            "name": "SoulSpot Bridge",
            "url": "https://github.com/bozzfozz/soulspot-bridge",
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

    # Mount static files if directory exists
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static files mounted from: %s", static_dir)
    else:
        logger.warning("Static directory not found: %s", static_dir)

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    # Include UI router
    app.include_router(ui.router, prefix="/ui", tags=["UI"])

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
            dict: Health status including app name, environment, and profile.

        Example response:
            {
                "status": "healthy",
                "app_name": "SoulSpot Bridge",
                "environment": "production",
                "profile": "simple"
            }
        """
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "profile": settings.profile.value,
        }

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

    # Liveness probe endpoint
    @app.get("/live", tags=["Health"])
    async def liveness_check() -> dict[str, str]:
        """Liveness check endpoint - returns OK if application is running."""
        return {"status": "alive"}

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Root endpoint with API information."""
        return {
            "message": "Welcome to SoulSpot Bridge API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
            "live": "/live",
            "api": "/api/v1",
            "ui": "/ui",
        }

    return app


# Create application instance
app = create_app()


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
