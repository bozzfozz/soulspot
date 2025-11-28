"""API module for SoulSpot.

Hey future me - dieses Modul exportiert alle API-Komponenten!
Der Haupteinstiegspunkt ist `api_router` aus routers/, der alle
Sub-Router aggregiert und in main.py unter /api gemountet wird.

Struktur:
- routers/: Alle API-Endpunkte (auth, playlists, tracks, etc.)
- schemas/: Pydantic-Modelle für Request/Response
- dependencies.py: Dependency Injection (Repositories, Services, etc.)
- exception_handlers.py: Globale Error-Handler
- health_checks.py: Health/Readiness Endpoints
"""

from soulspot.api.routers import (
    api_router,
    artist_songs,
    artists,
    auth,
    automation,
    downloads,
    library,
    metadata,
    playlists,
    settings,
    sse,
    tracks,
    workers,
)

__all__ = [
    "api_router",
    "artist_songs",
    "artists",
    "auth",
    "automation",
    "downloads",
    "library",
    "metadata",
    "playlists",
    "settings",
    "sse",
    "tracks",
    "workers",
]
