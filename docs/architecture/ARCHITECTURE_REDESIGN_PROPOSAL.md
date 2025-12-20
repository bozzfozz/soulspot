# 🏗️ SoulSpot Architektur-Redesign Proposal

**Status:** PROPOSAL  
**Erstellt:** Januar 2025  
**Autor:** AI Architecture Analysis  

---

## 📋 Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Problem-Analyse](#2-problem-analyse)
3. [Neue Architektur](#3-neue-architektur)
4. [Verzeichnisstruktur](#4-verzeichnisstruktur)
5. [Komponenten-Design](#5-komponenten-design)
6. [Funktions-Mapping](#6-funktions-mapping)
7. [Migrations-Plan](#7-migrations-plan)
8. [Risiken & Mitigations](#8-risiken--mitigations)
9. [Akzeptanzkriterien](#9-akzeptanzkriterien)

---

## 1. Executive Summary

### Das Problem

SoulSpot implementiert **Clean Architecture** mit 4 Layern, aber:
- **100+ Dateien** für ~10 Kern-Features
- **God Files** mit 1000-6000+ LOC trotz Architektur
- **40+ Services** statt fokussierter Use Cases
- **18 Worker** mit überlappenden Verantwortlichkeiten
- **Keine Tests** trotz Architektur für Testbarkeit

### Die Lösung

**Pragmatic Clean Architecture:**
- 3 Layer statt 4 (Core, Providers/Storage, API)
- **~40 Dateien** statt 100+
- **8-10 Services** statt 40+
- **1 JobScheduler** statt 18 Worker
- **60% weniger Code** bei **100% Funktionalität**

### Vorteile

| Metrik | VORHER | NACHHER | Verbesserung |
|--------|--------|---------|--------------|
| Dateien | 100+ | ~40 | -60% |
| Services | 40+ | 8-10 | -75% |
| Workers | 18 | 1+Handlers | -90% |
| LOC | ~20,000 | ~8,000 | -60% |
| Funktionen | 100% | 100% | ±0% |

---

## 2. Problem-Analyse

### 2.1 Aktuelle Architektur-Probleme

#### God Files (trotz Clean Architecture!)

| Datei | LOC | Problem |
|-------|-----|---------|
| `repositories.py` | 6418 | Alle 15+ Repos in einer Datei |
| `local_library_enrichment_service.py` | 3100 | God Service mit 20+ Methoden |
| `ports/__init__.py` | 1678 | Alle Interfaces zusammen |
| `dependencies.py` | 1244 | DI Monster |
| `entities/__init__.py` | 1125 | Alle Entities zusammen |

#### Layer-Verletzungen (~40 Stellen!)

```python
# ❌ Application Layer importiert Infrastructure direkt
from soulspot.infrastructure.persistence.models import AlbumModel
from soulspot.infrastructure.persistence.repositories import ArtistRepository

# ❌ API Layer importiert Infrastructure direkt  
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
```

#### Service-Proliferation

```
application/services/
├── 40+ Service-Dateien
├── Viele mit <200 LOC
├── Überlappende Verantwortlichkeiten
└── Keine klare Trennung Service vs Use Case
```

#### Worker-Chaos

```
application/workers/
├── 18 Worker-Dateien
├── download_worker.py
├── download_monitor_worker.py      # Überlappend!
├── download_status_sync_worker.py  # Überlappend!
├── queue_dispatcher_worker.py      # Überlappend!
├── library_enrichment_worker.py    # DEPRECATED
├── library_discovery_worker.py     # Ersetzt Enrichment
└── ... 12 weitere
```

### 2.2 Was GUT funktioniert (behalten!)

1. **Plugin-System** - Elegant und erweiterbar
2. **Domain-Isolation** - Entities sind "pure"
3. **Error-Handling** - Professionell mit Correlation IDs
4. **Structured Logging** - JSON-basiert mit Context

---

## 3. Neue Architektur

### 3.1 Design-Prinzipien

1. **YAGNI (You Ain't Gonna Need It)**
   - Nur Abstraktionen wo wirklich nötig
   - Keine "Future-Proofing" auf Vorrat

2. **Single Responsibility - aber pragmatisch**
   - Eine Service-Datei pro Feature-Bereich
   - Nicht eine Datei pro Methode

3. **Dateigröße-Limit: ~500 LOC**
   - Jede Datei unter 500 Zeilen
   - Wenn größer → Aufteilen nach Verantwortung

4. **Ports nur für Externe**
   - Interfaces nur für externe Services (Spotify, Deezer, slskd)
   - Keine internen Interfaces ohne Grund

### 3.2 Layer-Struktur

```
┌─────────────────────────────────────────────────────┐
│                    API Layer                         │
│  FastAPI Routes, Dependencies, Request/Response     │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                   Core Layer                         │
│  Services, Jobs, Models, Ports (für externe)        │
│  = Was war: Domain + Application                    │
└─────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Providers  │  │   Storage   │  │    UI       │
│  Spotify    │  │  Database   │  │  Templates  │
│  Deezer     │  │  Repos      │  │  Static     │
│  slskd      │  │  Models     │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## 4. Verzeichnisstruktur

### 4.1 Neue Struktur

```
src/soulspot/
│
├── 📁 core/                          # Business Logic
│   │
│   ├── 📄 models.py                  # ~500 LOC
│   │   ├── Entities (Artist, Album, Track, Playlist, Download)
│   │   ├── DTOs (ArtistDTO, AlbumDTO, TrackDTO)
│   │   ├── Value Objects (SpotifyURI, ISRC, UUID)
│   │   └── Enums (JobType, DownloadStatus, etc.)
│   │
│   ├── 📄 exceptions.py              # ~200 LOC
│   │   ├── EntityNotFoundError
│   │   ├── ValidationError
│   │   ├── BusinessRuleViolation
│   │   └── AuthenticationError
│   │
│   ├── 📁 ports/                     # Interfaces für externe Services
│   │   ├── 📄 music_provider.py      # ~150 LOC - IMusicProvider
│   │   └── 📄 download_provider.py   # ~100 LOC - IDownloadProvider
│   │
│   ├── 📁 services/                  # Business Services
│   │   ├── 📄 library.py             # ~500 LOC
│   │   │   ├── scan_library()
│   │   │   ├── get_library_stats()
│   │   │   ├── find_duplicates()
│   │   │   ├── cleanup_library()
│   │   │   └── get_library_view()
│   │   │
│   │   ├── 📄 enrichment.py          # ~600 LOC
│   │   │   ├── enrich_artists()
│   │   │   ├── enrich_albums()
│   │   │   ├── enrich_tracks_by_isrc()
│   │   │   ├── merge_artists()
│   │   │   ├── merge_albums()
│   │   │   ├── repair_artwork()
│   │   │   └── enrich_disambiguation()
│   │   │
│   │   ├── 📄 download.py            # ~400 LOC
│   │   │   ├── enqueue_download()
│   │   │   ├── get_download_queue()
│   │   │   ├── process_download()
│   │   │   ├── auto_import()
│   │   │   └── check_quality_upgrade()
│   │   │
│   │   ├── 📄 playlist.py            # ~300 LOC
│   │   │   ├── sync_spotify_playlists()
│   │   │   ├── sync_deezer_playlists()
│   │   │   ├── get_playlist_tracks()
│   │   │   └── create_local_playlist()
│   │   │
│   │   ├── 📄 discovery.py           # ~400 LOC
│   │   │   ├── get_new_releases()
│   │   │   ├── browse_categories()
│   │   │   ├── get_recommendations()
│   │   │   └── search_all_providers()
│   │   │
│   │   ├── 📄 sync.py                # ~400 LOC
│   │   │   ├── sync_spotify_data()
│   │   │   ├── sync_deezer_data()
│   │   │   ├── sync_followed_artists()
│   │   │   └── sync_saved_albums()
│   │   │
│   │   ├── 📄 auth.py                # ~300 LOC
│   │   │   ├── start_spotify_oauth()
│   │   │   ├── complete_spotify_oauth()
│   │   │   ├── start_deezer_oauth()
│   │   │   ├── complete_deezer_oauth()
│   │   │   └── refresh_tokens()
│   │   │
│   │   ├── 📄 settings.py            # ~200 LOC
│   │   │   ├── get_setting()
│   │   │   ├── set_setting()
│   │   │   └── get_all_settings()
│   │   │
│   │   └── 📄 images.py              # ~400 LOC (existiert bereits!)
│   │       ├── get_display_url()
│   │       ├── download_and_cache()
│   │       └── get_best_image()
│   │
│   └── 📁 jobs/                      # Background Job System
│       ├── 📄 scheduler.py           # ~200 LOC
│       │   └── class JobScheduler
│       │
│       └── 📄 handlers.py            # ~400 LOC
│           ├── handle_library_scan()
│           ├── handle_enrichment()
│           ├── handle_download()
│           ├── handle_sync()
│           └── handle_cleanup()
│
├── 📁 providers/                     # Provider Implementations
│   │
│   ├── 📁 spotify/
│   │   ├── 📄 client.py              # ~400 LOC - API Client
│   │   └── 📄 plugin.py              # ~300 LOC - IMusicProvider
│   │
│   ├── 📁 deezer/
│   │   ├── 📄 client.py              # ~300 LOC
│   │   └── 📄 plugin.py              # ~250 LOC
│   │
│   ├── 📁 musicbrainz/
│   │   └── 📄 client.py              # ~200 LOC
│   │
│   └── 📁 slskd/
│       ├── 📄 client.py              # ~300 LOC
│       └── 📄 plugin.py              # ~150 LOC - IDownloadProvider
│
├── 📁 storage/                       # Persistence Layer
│   │
│   ├── 📄 database.py                # ~100 LOC - Engine + Session
│   │
│   ├── 📄 models.py                  # ~500 LOC - SQLAlchemy Models
│   │
│   └── 📁 repositories/
│       ├── 📄 artist.py              # ~150 LOC
│       ├── 📄 album.py               # ~150 LOC
│       ├── 📄 track.py               # ~150 LOC
│       ├── 📄 playlist.py            # ~150 LOC
│       ├── 📄 download.py            # ~150 LOC
│       └── 📄 settings.py            # ~100 LOC
│
├── 📁 api/                           # FastAPI Layer
│   │
│   ├── 📄 main.py                    # ~100 LOC - App Factory
│   │
│   ├── 📄 dependencies.py            # ~200 LOC (statt 1244!)
│   │
│   └── 📁 routes/
│       ├── 📄 library.py             # ~300 LOC
│       │   ├── GET /api/library/artists
│       │   ├── GET /api/library/albums
│       │   ├── GET /api/library/tracks
│       │   ├── POST /api/library/scan
│       │   ├── GET /api/library/stats
│       │   └── GET /api/library/duplicates
│       │
│       ├── 📄 enrichment.py          # ~200 LOC
│       │   ├── POST /api/enrichment/trigger
│       │   ├── GET /api/enrichment/status
│       │   └── POST /api/enrichment/repair-artwork
│       │
│       ├── 📄 downloads.py           # ~200 LOC
│       │   ├── GET /api/downloads/queue
│       │   ├── POST /api/downloads/enqueue
│       │   └── DELETE /api/downloads/{id}
│       │
│       ├── 📄 playlists.py           # ~150 LOC
│       │   ├── GET /api/playlists
│       │   ├── POST /api/playlists/sync
│       │   └── GET /api/playlists/{id}/tracks
│       │
│       ├── 📄 discovery.py           # ~200 LOC
│       │   ├── GET /api/discovery/new-releases
│       │   ├── GET /api/discovery/browse
│       │   └── GET /api/discovery/search
│       │
│       ├── 📄 settings.py            # ~100 LOC
│       │   ├── GET /api/settings
│       │   └── PUT /api/settings/{key}
│       │
│       └── 📄 auth.py                # ~200 LOC
│           ├── GET /api/auth/spotify/login
│           ├── GET /api/auth/spotify/callback
│           ├── GET /api/auth/deezer/login
│           └── GET /api/auth/deezer/callback
│
├── 📁 ui/                            # Frontend
│   ├── 📁 templates/
│   └── 📁 static/
│
└── 📁 config/
    └── 📄 settings.py                # Pydantic Settings
```

### 4.2 Datei-Statistik

| Bereich | Dateien | LOC (geschätzt) |
|---------|---------|-----------------|
| core/models + exceptions | 2 | ~700 |
| core/ports | 2 | ~250 |
| core/services | 9 | ~3,500 |
| core/jobs | 2 | ~600 |
| providers | 8 | ~1,900 |
| storage | 8 | ~1,350 |
| api | 9 | ~1,450 |
| **TOTAL** | **~40** | **~9,750** |

Vergleich: Aktuell ~100+ Dateien mit ~20,000+ LOC

---

## 5. Komponenten-Design

### 5.1 Core Services

#### LibraryService

```python
# core/services/library.py

class LibraryService:
    """Unified library management - was: 4 separate files."""
    
    def __init__(
        self,
        session: AsyncSession,
        settings: AppSettings,
    ):
        self._session = session
        self._settings = settings
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)
    
    # === Library Scan ===
    async def scan_library(self, paths: list[Path]) -> ScanResult:
        """Scan filesystem for music files and import to library."""
        ...
    
    async def get_scan_status(self) -> ScanStatus:
        """Get current/last scan status."""
        ...
    
    # === Library Stats ===
    async def get_library_stats(self) -> LibraryStats:
        """Get aggregated library statistics."""
        return LibraryStats(
            total_artists=await self._artist_repo.count(),
            total_albums=await self._album_repo.count(),
            total_tracks=await self._track_repo.count(),
            total_duration_seconds=await self._track_repo.total_duration(),
            storage_bytes=await self._calculate_storage(),
        )
    
    # === Library Views ===
    async def get_artists(self, page: int, limit: int) -> Page[Artist]:
        """Get paginated artist list."""
        ...
    
    async def get_albums(self, artist_id: UUID | None = None) -> list[Album]:
        """Get albums, optionally filtered by artist."""
        ...
    
    # === Duplicates ===
    async def find_duplicate_tracks(self) -> list[DuplicateGroup]:
        """Find duplicate tracks by SHA256 or metadata hash."""
        ...
    
    # === Cleanup ===
    async def cleanup_orphaned(self) -> CleanupResult:
        """Remove orphaned database entries."""
        ...
```

#### EnrichmentService

```python
# core/services/enrichment.py

class EnrichmentService:
    """Unified enrichment - was: 3100 LOC in one file!"""
    
    def __init__(
        self,
        session: AsyncSession,
        providers: dict[str, IMusicProvider],
        image_service: ImageService,
    ):
        self._session = session
        self._providers = providers
        self._images = image_service
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)
    
    # === Batch Enrichment ===
    async def enrich_artists(self, limit: int = 50) -> EnrichmentStats:
        """Enrich unenriched artists via all providers."""
        artists = await self._artist_repo.get_unenriched(limit)
        stats = EnrichmentStats()
        
        for artist in artists:
            result = await self._enrich_single_artist(artist)
            if result.success:
                stats.enriched += 1
            else:
                stats.failed += 1
        
        await self._session.commit()
        return stats
    
    async def enrich_albums(self, limit: int = 50) -> EnrichmentStats:
        """Enrich unenriched albums via all providers."""
        ...
    
    async def enrich_tracks_by_isrc(self, limit: int = 50) -> EnrichmentStats:
        """Enrich tracks using ISRC lookup."""
        ...
    
    # === Duplicate Management ===
    async def find_duplicate_artists(self) -> list[DuplicateGroup]:
        """Find potential duplicate artists by normalized name."""
        ...
    
    async def merge_artists(
        self, 
        keep_id: UUID, 
        merge_ids: list[UUID],
    ) -> MergeResult:
        """Merge multiple artists into one."""
        ...
    
    async def find_duplicate_albums(self) -> list[DuplicateGroup]:
        ...
    
    async def merge_albums(
        self,
        keep_id: UUID,
        merge_ids: list[UUID],
    ) -> MergeResult:
        ...
    
    # === Artwork Repair ===
    async def repair_missing_artwork(self, limit: int = 50) -> RepairStats:
        """Re-download artwork for entities with missing images."""
        ...
    
    # === MusicBrainz Disambiguation ===
    async def enrich_disambiguation(self, limit: int = 50) -> EnrichmentStats:
        """Enrich artists with MusicBrainz disambiguation data."""
        ...
    
    # === Status ===
    async def get_enrichment_status(self) -> EnrichmentStatus:
        """Get current enrichment status."""
        return EnrichmentStatus(
            artists_enriched=await self._artist_repo.count_enriched(),
            artists_pending=await self._artist_repo.count_unenriched(),
            albums_enriched=await self._album_repo.count_enriched(),
            albums_pending=await self._album_repo.count_unenriched(),
        )
    
    # === Private Helpers ===
    async def _enrich_single_artist(self, artist: Artist) -> EnrichmentResult:
        """Try to enrich artist via all providers."""
        for name, provider in self._providers.items():
            try:
                results = await provider.search_artist(artist.name)
                if results:
                    await self._apply_enrichment(artist, results[0], name)
                    return EnrichmentResult(success=True, source=name)
            except Exception as e:
                logger.warning(f"{name} enrichment failed for {artist.name}: {e}")
        
        return EnrichmentResult(success=False)
```

### 5.2 Job System

```python
# core/jobs/scheduler.py

class JobScheduler:
    """Central job orchestration - replaces 18 workers!"""
    
    def __init__(
        self,
        db: Database,
        providers: dict[str, IMusicProvider],
        services: dict[str, Any],
    ):
        self._db = db
        self._queue = asyncio.Queue()
        self._handlers: dict[str, Callable] = {}
        self._running = False
        
        # Register all handlers
        from core.jobs.handlers import (
            handle_library_scan,
            handle_enrichment,
            handle_download,
            handle_sync,
            handle_cleanup,
        )
        
        self._handlers = {
            JobType.LIBRARY_SCAN: handle_library_scan,
            JobType.ENRICHMENT: handle_enrichment,
            JobType.DOWNLOAD: handle_download,
            JobType.SYNC: handle_sync,
            JobType.CLEANUP: handle_cleanup,
        }
    
    async def schedule(self, job_type: JobType, payload: dict) -> UUID:
        """Schedule a job for background processing."""
        job = Job(id=uuid4(), type=job_type, payload=payload)
        await self._queue.put(job)
        return job.id
    
    async def start(self) -> None:
        """Start the job processor loop."""
        self._running = True
        asyncio.create_task(self._process_loop())
        asyncio.create_task(self._periodic_jobs())
    
    async def stop(self) -> None:
        """Stop the job processor."""
        self._running = False
    
    async def _process_loop(self) -> None:
        """Main job processing loop."""
        while self._running:
            try:
                job = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                handler = self._handlers.get(job.type)
                if handler:
                    async with self._db.session_scope() as session:
                        await handler(session, job.payload)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Job processing error: {e}")
    
    async def _periodic_jobs(self) -> None:
        """Schedule periodic jobs based on settings."""
        while self._running:
            await asyncio.sleep(1800)  # 30 minutes
            
            # Sync if enabled
            await self.schedule(JobType.SYNC, {"providers": ["spotify", "deezer"]})
            
            # Daily cleanup
            if self._is_daily_time():
                await self.schedule(JobType.CLEANUP, {})
```

```python
# core/jobs/handlers.py

async def handle_library_scan(session: AsyncSession, payload: dict) -> ScanResult:
    """Handle library scan job."""
    library_service = LibraryService(session)
    paths = [Path(p) for p in payload.get("paths", [])]
    return await library_service.scan_library(paths)


async def handle_enrichment(session: AsyncSession, payload: dict) -> EnrichmentStats:
    """Handle enrichment job."""
    providers = get_all_providers()
    service = EnrichmentService(session, providers, ImageService())
    
    stats = EnrichmentStats()
    
    if payload.get("artists", True):
        artist_stats = await service.enrich_artists(limit=50)
        stats += artist_stats
    
    if payload.get("albums", True):
        album_stats = await service.enrich_albums(limit=50)
        stats += album_stats
    
    return stats


async def handle_download(session: AsyncSession, payload: dict) -> DownloadResult:
    """Handle download job."""
    download_service = DownloadService(session, get_slskd_provider())
    return await download_service.process_download(
        track_id=payload["track_id"],
        quality=payload.get("quality", "flac"),
    )


async def handle_sync(session: AsyncSession, payload: dict) -> SyncStats:
    """Handle provider sync job."""
    providers = get_all_providers()
    sync_service = SyncService(session, providers)
    
    stats = SyncStats()
    for provider_name in payload.get("providers", []):
        if provider_name in providers:
            provider_stats = await sync_service.sync_provider(provider_name)
            stats += provider_stats
    
    return stats


async def handle_cleanup(session: AsyncSession, payload: dict) -> CleanupResult:
    """Handle cleanup job."""
    library_service = LibraryService(session)
    return await library_service.cleanup_orphaned()
```

### 5.3 Provider Interface

```python
# core/ports/music_provider.py

from typing import Protocol

class IMusicProvider(Protocol):
    """Unified interface for all music services."""
    
    @property
    def provider_name(self) -> str:
        """Provider identifier (spotify, deezer, etc.)."""
        ...
    
    @property
    def requires_auth(self) -> bool:
        """Whether this provider requires OAuth."""
        ...
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        ...
    
    # === Search ===
    async def search_artist(
        self, 
        name: str, 
        limit: int = 10,
    ) -> list[ArtistDTO]:
        """Search for artists by name."""
        ...
    
    async def search_album(
        self,
        title: str,
        artist: str | None = None,
        limit: int = 10,
    ) -> list[AlbumDTO]:
        """Search for albums by title."""
        ...
    
    async def search_track(
        self,
        title: str,
        artist: str | None = None,
        limit: int = 10,
    ) -> list[TrackDTO]:
        """Search for tracks."""
        ...
    
    # === Get by ID ===
    async def get_artist(self, id: str) -> ArtistDTO | None:
        """Get artist by provider ID."""
        ...
    
    async def get_album(self, id: str) -> AlbumDTO | None:
        """Get album by provider ID."""
        ...
    
    async def get_track(self, id: str) -> TrackDTO | None:
        """Get track by provider ID."""
        ...
    
    # === Images ===
    async def get_artist_image(
        self, 
        id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> str | None:
        """Get artist image URL."""
        ...
    
    async def get_album_image(
        self,
        id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> str | None:
        """Get album cover URL."""
        ...
    
    # === User Data (optional) ===
    async def get_followed_artists(self) -> list[ArtistDTO]:
        """Get user's followed artists."""
        ...
    
    async def get_saved_albums(self) -> list[AlbumDTO]:
        """Get user's saved albums."""
        ...
    
    async def get_playlists(self) -> list[PlaylistDTO]:
        """Get user's playlists."""
        ...
```

### 5.4 Simplified Dependencies

```python
# api/dependencies.py (~200 LOC statt 1244!)

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.services import (
    LibraryService,
    EnrichmentService,
    DownloadService,
    PlaylistService,
    DiscoveryService,
    SyncService,
    AuthService,
    SettingsService,
    ImageService,
)
from core.jobs.scheduler import JobScheduler
from providers.spotify.plugin import SpotifyPlugin
from providers.deezer.plugin import DeezerPlugin
from providers.slskd.plugin import SlskdPlugin
from storage.database import async_session, Database
from config.settings import get_settings


# === Database ===

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        yield session


def get_database() -> Database:
    """Get database instance."""
    return Database()


# === Providers ===

@lru_cache
def get_spotify_plugin() -> SpotifyPlugin:
    """Get Spotify plugin (cached)."""
    settings = get_settings()
    return SpotifyPlugin(settings.spotify)


@lru_cache
def get_deezer_plugin() -> DeezerPlugin:
    """Get Deezer plugin (cached)."""
    return DeezerPlugin()


@lru_cache
def get_slskd_plugin() -> SlskdPlugin:
    """Get slskd plugin (cached)."""
    settings = get_settings()
    return SlskdPlugin(settings.slskd)


def get_all_providers() -> dict[str, IMusicProvider]:
    """Get all music providers."""
    return {
        "spotify": get_spotify_plugin(),
        "deezer": get_deezer_plugin(),
    }


# === Services ===

async def get_library_service(
    session: AsyncSession = Depends(get_db_session),
) -> LibraryService:
    return LibraryService(session, get_settings())


async def get_enrichment_service(
    session: AsyncSession = Depends(get_db_session),
) -> EnrichmentService:
    return EnrichmentService(
        session=session,
        providers=get_all_providers(),
        image_service=ImageService(),
    )


async def get_download_service(
    session: AsyncSession = Depends(get_db_session),
) -> DownloadService:
    return DownloadService(session, get_slskd_plugin())


async def get_playlist_service(
    session: AsyncSession = Depends(get_db_session),
) -> PlaylistService:
    return PlaylistService(session, get_all_providers())


async def get_discovery_service(
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryService:
    return DiscoveryService(session, get_all_providers())


async def get_sync_service(
    session: AsyncSession = Depends(get_db_session),
) -> SyncService:
    return SyncService(session, get_all_providers())


async def get_settings_service(
    session: AsyncSession = Depends(get_db_session),
) -> SettingsService:
    return SettingsService(session)


# === Job Scheduler ===

@lru_cache
def get_job_scheduler() -> JobScheduler:
    """Get job scheduler (singleton)."""
    return JobScheduler(
        db=get_database(),
        providers=get_all_providers(),
        services={},  # Services created per-job
    )
```

---

## 6. Funktions-Mapping

### 6.1 Vollständiges Mapping: Alt → Neu

#### Library Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `library_scanner_service.py` | `scan_directory()` | `core/services/library.py` | `scan_library()` |
| `library_scanner_service.py` | `get_scan_status()` | `core/services/library.py` | `get_scan_status()` |
| `library_view_service.py` | `get_artists()` | `core/services/library.py` | `get_artists()` |
| `library_view_service.py` | `get_albums()` | `core/services/library.py` | `get_albums()` |
| `stats_service.py` | `get_library_stats()` | `core/services/library.py` | `get_library_stats()` |
| `duplicate_service.py` | `find_duplicates()` | `core/services/library.py` | `find_duplicate_tracks()` |
| `library_cleanup_service.py` | `cleanup()` | `core/services/library.py` | `cleanup_orphaned()` |
| `library_scan_worker.py` | `_handle_scan_job()` | `core/jobs/handlers.py` | `handle_library_scan()` |

#### Enrichment Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `local_library_enrichment_service.py` | `enrich_batch()` | `core/services/enrichment.py` | `enrich_artists()` + `enrich_albums()` |
| `local_library_enrichment_service.py` | `enrich_tracks_by_isrc()` | `core/services/enrichment.py` | `enrich_tracks_by_isrc()` |
| `local_library_enrichment_service.py` | `find_duplicate_artists()` | `core/services/enrichment.py` | `find_duplicate_artists()` |
| `local_library_enrichment_service.py` | `merge_artists()` | `core/services/enrichment.py` | `merge_artists()` |
| `local_library_enrichment_service.py` | `find_duplicate_albums()` | `core/services/enrichment.py` | `find_duplicate_albums()` |
| `local_library_enrichment_service.py` | `merge_albums()` | `core/services/enrichment.py` | `merge_albums()` |
| `local_library_enrichment_service.py` | `repair_missing_artwork()` | `core/services/enrichment.py` | `repair_missing_artwork()` |
| `local_library_enrichment_service.py` | `enrich_disambiguation_batch()` | `core/services/enrichment.py` | `enrich_disambiguation()` |
| `local_library_enrichment_service.py` | `get_enrichment_status()` | `core/services/enrichment.py` | `get_enrichment_status()` |
| `library_enrichment_worker.py` | `_handle_enrichment_job()` | `core/jobs/handlers.py` | `handle_enrichment()` |
| `library_discovery_worker.py` | `_run_discovery_cycle()` | `core/jobs/handlers.py` | `handle_enrichment()` |

#### Download Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `download_manager_service.py` | `enqueue_track()` | `core/services/download.py` | `enqueue_download()` |
| `download_manager_service.py` | `get_queue()` | `core/services/download.py` | `get_download_queue()` |
| `download_worker.py` | `_handle_download_job()` | `core/jobs/handlers.py` | `handle_download()` |
| `download_monitor_worker.py` | `_check_downloads()` | `core/jobs/handlers.py` | (Teil von `handle_download()`) |
| `download_status_sync_worker.py` | `_sync_status()` | `core/jobs/handlers.py` | (Teil von `handle_download()`) |
| `queue_dispatcher_worker.py` | `_dispatch_queue()` | `core/jobs/handlers.py` | (Teil von `handle_download()`) |
| `auto_import.py` | `auto_import_downloads()` | `core/services/download.py` | `auto_import()` |
| `quality_upgrade_service.py` | `check_upgrades()` | `core/services/download.py` | `check_quality_upgrade()` |

#### Sync Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `spotify_sync_service.py` | `sync_all()` | `core/services/sync.py` | `sync_spotify_data()` |
| `spotify_sync_worker.py` | `_run_sync()` | `core/jobs/handlers.py` | `handle_sync()` |
| `deezer_sync_service.py` | `sync_all()` | `core/services/sync.py` | `sync_deezer_data()` |
| `deezer_sync_worker.py` | `_run_sync()` | `core/jobs/handlers.py` | `handle_sync()` |
| `followed_artists_service.py` | `sync_followed()` | `core/services/sync.py` | `sync_followed_artists()` |
| `playlist_sync_worker.py` | `_sync_playlists()` | `core/services/playlist.py` | `sync_spotify_playlists()` |
| `token_refresh_worker.py` | `_refresh_tokens()` | `core/services/auth.py` | `refresh_tokens()` |

#### Discovery Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `new_releases_service.py` | `get_new_releases()` | `core/services/discovery.py` | `get_new_releases()` |
| `discover_service.py` | `browse_categories()` | `core/services/discovery.py` | `browse_categories()` |
| `discover_service.py` | `get_recommendations()` | `core/services/discovery.py` | `get_recommendations()` |
| `advanced_search.py` | `search()` | `core/services/discovery.py` | `search_all_providers()` |
| `new_releases_sync_worker.py` | `_sync_releases()` | `core/jobs/handlers.py` | (Teil von `handle_sync()`) |

#### Auth Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `spotify_auth_service.py` | `start_oauth()` | `core/services/auth.py` | `start_spotify_oauth()` |
| `spotify_auth_service.py` | `handle_callback()` | `core/services/auth.py` | `complete_spotify_oauth()` |
| `deezer_auth_service.py` | `start_oauth()` | `core/services/auth.py` | `start_deezer_oauth()` |
| `deezer_auth_service.py` | `handle_callback()` | `core/services/auth.py` | `complete_deezer_oauth()` |
| `token_manager.py` | `refresh_all()` | `core/services/auth.py` | `refresh_tokens()` |

#### Settings Features

| Alte Datei | Alte Methode | Neue Datei | Neue Methode |
|------------|--------------|------------|--------------|
| `app_settings_service.py` | `get_setting()` | `core/services/settings.py` | `get_setting()` |
| `app_settings_service.py` | `set_setting()` | `core/services/settings.py` | `set_setting()` |
| `app_settings_service.py` | `get_all()` | `core/services/settings.py` | `get_all_settings()` |

### 6.2 Worker → Job Handler Mapping

| Alter Worker | Neuer Handler |
|--------------|---------------|
| `library_scan_worker.py` | `handle_library_scan()` |
| `library_enrichment_worker.py` | `handle_enrichment()` |
| `library_discovery_worker.py` | `handle_enrichment()` |
| `download_worker.py` | `handle_download()` |
| `download_monitor_worker.py` | (in `handle_download()`) |
| `download_status_sync_worker.py` | (in `handle_download()`) |
| `queue_dispatcher_worker.py` | (in `handle_download()`) |
| `spotify_sync_worker.py` | `handle_sync()` |
| `deezer_sync_worker.py` | `handle_sync()` |
| `playlist_sync_worker.py` | `handle_sync()` |
| `new_releases_sync_worker.py` | `handle_sync()` |
| `token_refresh_worker.py` | (in `handle_sync()`) |
| `cleanup_worker.py` | `handle_cleanup()` |
| `duplicate_detector_worker.py` | (in `handle_library_scan()`) |
| `metadata_worker.py` | (in `handle_enrichment()`) |
| `automation_workers.py` | (separater Handler wenn nötig) |

---

## 7. Migrations-Plan

### 7.1 Phasen-Übersicht

| Phase | Dauer | Fokus | Risiko |
|-------|-------|-------|--------|
| **Phase 0** | 1 Tag | Inventur + Vorbereitung | Niedrig |
| **Phase 1** | 1 Woche | Parallele Struktur aufbauen | Niedrig |
| **Phase 2** | 2 Wochen | Feature-Migration | Mittel |
| **Phase 3** | 1 Woche | Aufräumen + Testen | Niedrig |

**Gesamt: ~4 Wochen**

### 7.2 Phase 0: Inventur (1 Tag)

**Ziele:**
- Vollständige Funktionsliste erstellen
- API-Route-Inventar
- Tests vorbereiten

**Aktionen:**

```bash
# 1. API Routes extrahieren
grep -rn "@router\." src/soulspot/api/routers/ > MIGRATION_ROUTES.txt

# 2. Service-Methoden extrahieren
grep -rn "async def [a-z_]*\(self" src/soulspot/application/services/ > MIGRATION_SERVICES.txt

# 3. Worker-Handler extrahieren
grep -rn "async def _handle\|async def run" src/soulspot/application/workers/ > MIGRATION_WORKERS.txt
```

**Deliverables:**
- `docs/migration/ROUTE_INVENTORY.md`
- `docs/migration/SERVICE_INVENTORY.md`
- `docs/migration/WORKER_INVENTORY.md`

### 7.3 Phase 1: Parallele Struktur (1 Woche)

**Ziele:**
- Neue Verzeichnisstruktur erstellen
- Neue Services als Wrapper der alten
- Keine Funktionalität ändern

**Woche 1 Tasks:**

| Tag | Task |
|-----|------|
| Mo | `core/` Verzeichnis + `models.py` erstellen |
| Di | `core/ports/` + `core/services/` Struktur |
| Mi | `core/jobs/scheduler.py` + `handlers.py` Grundgerüst |
| Do | `storage/repositories/` aufteilen (aus God File) |
| Fr | `api/dependencies.py` vereinfachen |

**Beispiel: Delegation Pattern**

```python
# core/services/library.py (Phase 1 Version)

class LibraryService:
    """Wrapper - delegiert an alte Services."""
    
    def __init__(self, session: AsyncSession):
        # Alte Services als Dependencies
        from soulspot.application.services.library_scanner_service import (
            LibraryScannerService,
        )
        from soulspot.application.services.stats_service import StatsService
        
        self._scanner = LibraryScannerService(session)
        self._stats = StatsService(session)
    
    async def scan_library(self, paths: list[Path]) -> ScanResult:
        # Delegiere an alte Implementation
        return await self._scanner.scan_directory(paths[0])
    
    async def get_library_stats(self) -> LibraryStats:
        # Delegiere an alte Implementation
        return await self._stats.get_library_stats()
```

### 7.4 Phase 2: Feature-Migration (2 Wochen)

**Ziele:**
- Feature für Feature die echte Logik migrieren
- Tests nach jeder Migration
- Alte Wrapper durch echten Code ersetzen

**Woche 2: Core Features**

| Tag | Feature | Von | Nach |
|-----|---------|-----|------|
| Mo | Library Scan | `library_scanner_service.py` | `library.py` |
| Di | Library Stats | `stats_service.py` | `library.py` |
| Mi | Library Duplicates | `duplicate_service.py` | `library.py` |
| Do | Library Cleanup | `library_cleanup_service.py` | `library.py` |
| Fr | Testen + Bugfixes | | |

**Woche 3: Enrichment + Downloads**

| Tag | Feature | Von | Nach |
|-----|---------|-----|------|
| Mo | Artist Enrichment | `local_library_enrichment_service.py` | `enrichment.py` |
| Di | Album Enrichment | `local_library_enrichment_service.py` | `enrichment.py` |
| Mi | Artwork Repair | `local_library_enrichment_service.py` | `enrichment.py` |
| Do | Download Queue | `download_manager_service.py` | `download.py` |
| Fr | Testen + Bugfixes | | |

**Migration-Checkliste pro Feature:**

```markdown
## Feature: Library Scan

### Pre-Migration
- [ ] Alte Implementation verstanden
- [ ] Tests für alte Implementation existieren/erstellt
- [ ] Neue Service-Datei vorbereitet

### Migration
- [ ] Logik in neue Datei kopiert
- [ ] Imports angepasst
- [ ] Repository-Calls aktualisiert
- [ ] Session-Handling korrekt

### Post-Migration  
- [ ] Alte Wrapper entfernt
- [ ] Alle Tests grün
- [ ] API Routes funktionieren
- [ ] Alte Datei als DEPRECATED markiert
```

### 7.5 Phase 3: Aufräumen (1 Woche)

**Ziele:**
- Alle deprecaten Dateien entfernen
- Imports aufräumen
- Dokumentation aktualisieren
- Finale Tests

**Woche 4 Tasks:**

| Tag | Task |
|-----|------|
| Mo | Deprecated Services löschen |
| Di | Deprecated Workers löschen |
| Mi | Import-Cleanup (grep + fix) |
| Do | Dokumentation aktualisieren |
| Fr | Finaler Test-Durchlauf |

**Cleanup-Script:**

```bash
#!/bin/bash
# scripts/cleanup_migration.sh

# 1. Finde alle Imports der alten Dateien
echo "Checking for remaining old imports..."
grep -rn "from soulspot.application.services.library_scanner_service" src/

# 2. Wenn keine Imports mehr → Löschen
if [ $? -ne 0 ]; then
    echo "Deleting old file..."
    rm src/soulspot/application/services/library_scanner_service.py
fi
```

---

## 8. Risiken & Mitigations

### 8.1 Risiko-Matrix

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Funktion vergessen | Mittel | Hoch | Inventur + Mapping-Tabelle |
| Breaking Changes | Mittel | Hoch | Inkrementelle Migration |
| Regression Bugs | Mittel | Mittel | Tests nach jeder Migration |
| Circular Imports | Niedrig | Mittel | Klare Layer-Grenzen |
| Performance-Probleme | Niedrig | Niedrig | Monitoring |

### 8.2 Rollback-Plan

Falls kritische Probleme auftreten:

1. **Git Branch-Strategie:**
   ```bash
   # Jede Phase in eigenem Branch
   git checkout -b migration/phase-1
   git checkout -b migration/phase-2
   
   # Bei Problemen: Revert
   git revert --no-commit HEAD~5..HEAD
   ```

2. **Feature Flags:**
   ```python
   # Beide Implementierungen parallel
   if settings.use_new_library_service:
       service = LibraryService(session)
   else:
       service = LibraryScannerService(session)  # Fallback
   ```

3. **Monitoring:**
   - Error Rates tracken
   - Response Times vergleichen
   - User Feedback sammeln

---

## 9. Akzeptanzkriterien

### 9.1 Technische Kriterien

- [ ] Alle 142 API-Routes funktionieren identisch
- [ ] Alle Background-Jobs laufen korrekt
- [ ] Keine Regressions in bestehenden Features
- [ ] Dateigröße-Limit (~500 LOC) eingehalten
- [ ] Layer-Grenzen respektiert (keine Cross-Imports)

### 9.2 Code-Qualität

- [ ] `ruff check .` ohne Fehler
- [ ] `mypy` ohne Type-Errors
- [ ] Alle Services haben Docstrings
- [ ] "Future me" Kommentare für komplexe Logik

### 9.3 Dokumentation

- [ ] README aktualisiert
- [ ] API-Docs aktuell
- [ ] Migration abgeschlossen dokumentiert
- [ ] Architektur-Diagramm aktualisiert

### 9.4 Performance

- [ ] API Response Times <= vorher
- [ ] Memory Usage <= vorher
- [ ] Background Job Durchsatz >= vorher

---

## Anhang A: Quick Reference

### Alte → Neue Pfade

```
application/services/library_scanner_service.py → core/services/library.py
application/services/local_library_enrichment_service.py → core/services/enrichment.py
application/services/download_manager_service.py → core/services/download.py
application/services/spotify_sync_service.py → core/services/sync.py
application/services/deezer_sync_service.py → core/services/sync.py
application/services/new_releases_service.py → core/services/discovery.py
application/services/spotify_auth_service.py → core/services/auth.py
application/services/app_settings_service.py → core/services/settings.py

application/workers/* → core/jobs/handlers.py

infrastructure/persistence/repositories.py → storage/repositories/*.py
infrastructure/plugins/spotify_plugin.py → providers/spotify/plugin.py
infrastructure/plugins/deezer_plugin.py → providers/deezer/plugin.py
infrastructure/integrations/slskd_client.py → providers/slskd/client.py

domain/entities/__init__.py → core/models.py
domain/ports/__init__.py → core/ports/*.py
```

### Commit-Message Convention

```
migration(phase-1): Setup core/services structure
migration(library): Migrate scan_library to new service
migration(cleanup): Remove deprecated library_scanner_service.py
```

---

**Dokument Ende**
