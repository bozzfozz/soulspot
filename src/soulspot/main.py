"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    try:
        # Ensure storage directories exist
        settings.ensure_directories()
        logger.info("Storage directories initialized")

        # Initialize database
        db = Database(settings)
        app.state.db = db
        logger.info("Database initialized: %s", settings.database.url)

        yield

    except Exception as e:
        logger.exception("Error during application startup: %s", e)
        raise
    finally:
        # Shutdown - always attempt cleanup
        logger.info("Shutting down application")
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
        description="Intelligente Musik-Download-Anwendung mit Spotify-Playlist-Synchronisation und Soulseek-Integration",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

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
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "profile": settings.profile.value,
        }

    # Readiness check endpoint with dependency checks
    @app.get("/ready", tags=["Health"])
    async def readiness_check() -> dict[str, Any]:
        """Readiness check endpoint with database and dependency connectivity checks."""
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

            # MusicBrainz health check
            mb_check = await check_musicbrainz_health(timeout=timeout)
            checks["musicbrainz"] = {
                "status": mb_check.status.value,
                "message": mb_check.message,
            }

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
