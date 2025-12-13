# Download Manager Implementation

> **Status:** ✅ Core Complete | Erweiterbar
> **Letzte Aktualisierung:** 2025-01-13

## Übersicht

Der SoulSpot Download Manager orchestriert Downloads über den slskd Soulseek-Client.

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                            │
│  POST /api/downloads          - Track queueen               │
│  POST /api/downloads/album    - Alle Tracks eines Albums    │
│  GET  /api/downloads/manager  - UI Page                     │
│  GET  /api/downloads/manager/events - SSE Live Updates      │
│  GET  /api/downloads/manager/health - Provider Status       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│                                                             │
│  Services:                                                  │
│    DownloadManagerService                                   │
│      - list_active_downloads()                             │
│      - get_stats()                                         │
│      - cancel_download()                                   │
│                                                             │
│  Use Cases:                                                 │
│    QueueTrackDownloadUseCase                               │
│      - Input: TrackDTO                                     │
│      - Output: Download Entity                             │
│                                                             │
│    QueueAlbumDownloadsUseCase                              │
│      - Input: album_id, source (spotify/deezer/local)      │
│      - Output: List[Download]                              │
│      - Fetches tracks from Spotify/Deezer API              │
│                                                             │
│  Workers:                                                   │
│    QueueDispatcherWorker (every 30s)                       │
│      - WAITING → search → PENDING                          │
│                                                             │
│    DownloadWorker (event-driven)                           │
│      - PENDING → slskd queue → QUEUED                      │
│                                                             │
│    DownloadStatusSyncWorker (every 5s)                     │
│      - slskd status → SoulSpot DB                          │
│      - Circuit Breaker für Offline-Recovery                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                              │
│                                                             │
│  Entities:                                                  │
│    Download                                                 │
│      - id, track_id, status, priority                      │
│      - slskd_id (provider reference)                       │
│      - created_at, updated_at, completed_at                │
│                                                             │
│  Ports:                                                     │
│    IDownloadProvider                                        │
│      - search(query) → SearchResult                        │
│      - download(file) → DownloadHandle                     │
│      - get_status(id) → DownloadProgress                   │
│      - cancel(id) → bool                                   │
│                                                             │
│    IDownloadRepository                                      │
│      - get_pending() → List[Download]                      │
│      - get_active() → List[Download]                       │
│      - update_status() → None                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│                                                             │
│  Adapters:                                                  │
│    SlskdDownloadProvider                                    │
│      - Implementiert IDownloadProvider                      │
│      - HTTP Calls zu slskd API                             │
│                                                             │
│    DownloadRepository                                       │
│      - SQLAlchemy Async                                    │
│      - Implements IDownloadRepository                       │
└─────────────────────────────────────────────────────────────┘
```

## Status Flow

```
           ┌──────────────┐
           │   WAITING    │ ← Initial Queue
           └──────┬───────┘
                  │ QueueDispatcherWorker (search)
                  ▼
           ┌──────────────┐
           │   PENDING    │ ← Search result found
           └──────┬───────┘
                  │ DownloadWorker (queue to slskd)
                  ▼
           ┌──────────────┐
           │    QUEUED    │ ← In slskd queue
           └──────┬───────┘
                  │ DownloadStatusSyncWorker (sync)
                  ▼
           ┌──────────────┐
           │ DOWNLOADING  │ ← Active transfer
           └──────┬───────┘
                  │ DownloadStatusSyncWorker (sync)
                  ▼
           ┌──────────────┐
           │  COMPLETED   │ ← File downloaded
           └──────────────┘
                  │
              ┌───┴───┐
              ▼       ▼
        ┌──────┐  ┌──────┐
        │FAILED│  │CANCEL│
        └──────┘  └──────┘
```

## Circuit Breaker (Fehlertoleranz)

Der DownloadStatusSyncWorker hat einen eingebauten Circuit Breaker:

```
           ┌──────────────┐
           │    CLOSED    │ ← Normal operation
           └──────┬───────┘
                  │ 3 consecutive failures
                  ▼
           ┌──────────────┐
           │     OPEN     │ ← Skip sync (slskd down)
           └──────┬───────┘
                  │ After 60 seconds
                  ▼
           ┌──────────────┐
           │  HALF_OPEN   │ ← Test one request
           └──────┬───────┘
                  │
        ┌─────────┴─────────┐
        │                   │
    Success              Failure
        │                   │
        ▼                   ▼
   ┌──────────┐       ┌──────────┐
   │  CLOSED  │       │   OPEN   │
   └──────────┘       └──────────┘
```

**Health Check API:**
- `GET /api/downloads/manager/health`
- Returns: state, failure_count, last_success, last_failure

## Dateien

| Datei | Zweck |
|-------|-------|
| `domain/entities/download.py` | Download Entity + Status Enum |
| `domain/ports/download_provider.py` | IDownloadProvider Interface |
| `infrastructure/download/slskd_provider.py` | slskd Adapter |
| `infrastructure/persistence/download_repository.py` | DB Repository |
| `application/services/download_manager_service.py` | Service Layer |
| `application/use_cases/queue_track_download.py` | Track Download UseCase |
| `application/use_cases/queue_album_downloads.py` | Album Download UseCase |
| `application/workers/queue_dispatcher_worker.py` | Search → Pending Worker |
| `application/workers/download_worker.py` | Pending → Queued Worker |
| `application/workers/download_status_sync_worker.py` | Status Sync + Circuit Breaker |
| `api/routers/downloads.py` | REST API Endpoints |
| `api/routers/download_manager.py` | UI + HTMX + SSE Endpoints |
| `templates/download_manager.html` | Main UI Page |
| `templates/partials/download_manager_*.html` | HTMX Partials |

## API Endpoints

### REST API
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/downloads` | Queue single track |
| `POST` | `/api/downloads/album` | Queue all album tracks |
| `DELETE` | `/api/downloads/{id}` | Cancel download |
| `GET` | `/api/downloads/{id}` | Get download status |

### Download Manager UI
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/download-manager` | Main page |
| `GET` | `/api/downloads/manager/active` | Active downloads JSON |
| `GET` | `/api/downloads/manager/stats` | Statistics JSON |
| `GET` | `/api/downloads/manager/events` | SSE stream |
| `GET` | `/api/downloads/manager/health` | Provider health status |
| `GET` | `/api/downloads/manager/htmx/list` | HTMX partial |
| `GET` | `/api/downloads/manager/htmx/stats` | HTMX partial |
| `GET` | `/api/downloads/manager/htmx/provider-health` | HTMX partial |

## Konfiguration

Settings in `app_settings` Tabelle:
- `slskd.url` - slskd Server URL (default: http://localhost:5030)
- `slskd.api_key` - API Key für slskd

Worker Konfiguration in `infrastructure/lifecycle.py`:
```python
DownloadStatusSyncWorker(
    sync_interval=5.0,          # Sync every 5 seconds
    failure_threshold=3,        # Open circuit after 3 failures
    recovery_timeout=60.0,      # Try recovery after 60s
)
```

## Tests

| Test File | Coverage |
|-----------|----------|
| `tests/unit/application/workers/test_download_status_sync_worker.py` | Circuit Breaker States |
| `tests/unit/application/use_cases/test_queue_album_downloads.py` | Album Download Logic |

## Erweiterungen (geplant)

Siehe: [DOWNLOAD_MANAGER_FEATURES.md](../features/DOWNLOAD_MANAGER_FEATURES.md)

- Auto-Retry mit Exponential Backoff
- Quality Profiles
- Metadata Tagging
- Notifications
