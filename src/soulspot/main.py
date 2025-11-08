"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from soulspot.config import Settings, get_settings
from soulspot.infrastructure.persistence import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()

    # Ensure storage directories exist
    settings.ensure_directories()

    # Initialize database
    db = Database(settings)
    app.state.db = db

    yield

    # Shutdown
    await db.close()


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
        """Readiness check endpoint."""
        # TODO: Add database connectivity check
        return {
            "status": "ready",
            "database": "connected",
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
