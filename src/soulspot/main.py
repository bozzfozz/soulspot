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
from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks including:
    - Directory creation
    - Database initialization
    - Resource cleanup
    """
    settings = get_settings()
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

    # Readiness check endpoint
    @app.get("/ready", tags=["Health"])
    async def readiness_check() -> dict[str, Any]:
        """Readiness check endpoint with database connectivity check."""
        status = "ready"
        checks = {}

        # Database connectivity check
        try:
            if hasattr(app.state, "db"):
                # Perform a simple SELECT 1 query to verify database connectivity
                async with app.state.db.session() as session:
                    result = await session.execute("SELECT 1")
                    result.scalar()
                checks["database"] = "connected"
            else:
                checks["database"] = "not_initialized"
                status = "unavailable"
        except Exception as e:
            logger.exception("Database health check failed: %s", e)
            checks["database"] = f"error: {str(e)}"
            status = "unavailable"

        return {
            "status": status,
            **checks,
        }

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Root endpoint with API information."""
        return {
            "message": "Welcome to SoulSpot Bridge API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
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
