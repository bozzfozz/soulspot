"""FastAPI application entry point.

This module provides the main FastAPI application factory and CLI entry point.
The application logic is organized into separate modules:
- api.exception_handlers: Custom exception handlers
- api.health_checks: Health check endpoints
- infrastructure.lifecycle: Application startup/shutdown logic
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from soulspot.api.exception_handlers import register_exception_handlers
from soulspot.api.health_checks import register_health_endpoints
from soulspot.api.routers import api_router, ui
from soulspot.config import Settings, get_settings
from soulspot.infrastructure.lifecycle import lifespan
from soulspot.infrastructure.observability.middleware import RequestLoggingMiddleware

logger = logging.getLogger(__name__)


# Yo, this is the APP FACTORY! Creates a new FastAPI instance with all middleware, routes, and
# exception handlers configured. Called ONCE at module load to create `app` singleton at bottom of
# file. Takes optional Settings for testing (dependency injection). Middleware order MATTERS:
# GZip first (outermost), then logging, then CORS. Exception handlers registered BEFORE routes!
# Static files mounted BEFORE routes to avoid route conflicts. Use this pattern if you ever need
# multiple app instances (like in tests). DON'T call this multiple times in production!
def create_app(settings: Settings | None = None) -> FastAPI:
    """Create FastAPI application instance.

    Args:
        settings: Optional settings override for testing

    Returns:
        Configured FastAPI application instance
    """
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
    app.add_middleware(GZipMiddleware, minimum_size=settings.api.gzip_minimum_size)

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

    # Register health check endpoints
    register_health_endpoints(app, settings)

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

