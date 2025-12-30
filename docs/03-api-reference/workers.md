# Background Workers API

Monitor and control background workers for syncing, downloads, automation, and maintenance.

## Overview

The Workers API provides real-time status monitoring and control for background tasks:
- **Worker Status**: Get status of all background workers (running, idle, error, stopped)
- **Orchestrator**: Centralized worker management and health monitoring
- **Worker Control**: Start/stop individual workers (admin operations)
- **Service Health**: External service connectivity (Spotify, slskd, MusicBrainz)

**Key Features:**
- **HTMX Integration**: HTML partial for UI polling (sidebar status indicator)
- **Orchestrator Pattern**: Centralized worker lifecycle management
- **Health Monitoring**: Critical worker tracking and dependency validation
- **Real-Time Updates**: 10-second polling for live status

**Architecture:** Workers are stored on `app.state` (FastAPI lifecycle), managed by `WorkerOrchestrator`.

---

## Worker Types

SoulSpot uses 9 background workers grouped by category:

### Critical Workers
- **Token Refresh**: Keeps Spotify OAuth tokens fresh (checks every 5 min)
- **Download Monitor**: Tracks slskd download progress (polls every 10 sec)

### Sync Workers
- **Spotify Sync**: Auto-syncs Spotify data (artists, playlists, liked songs)
- **New Releases Sync**: Caches new releases from Spotify + Deezer (every 30 min)

### Download Workers
- **Queue Dispatcher**: Dispatches jobs from queue to slskd (every 5 sec)
- **Retry Scheduler**: Schedules automatic retries for failed downloads (exponential backoff)
- **Post-Processing**: Tags and organizes completed downloads

### Automation Workers
- **Watchlist Worker**: Monitors watchlists for new releases
- **Discography Worker**: Finds missing albums for followed artists
- **Quality Upgrade Worker**: Finds higher-quality versions of tracks

### Maintenance Workers
- **Cleanup Worker**: Removes orphaned files (disabled by default, destructive!)
- **Duplicate Detector**: Finds duplicate tracks via metadata hash (weekly scan)

---

## Worker Status Endpoints

### Get All Workers Status (JSON)

**Endpoint:** `GET /workers/status`

**Description:** Get comprehensive status of all background workers in JSON format.

**Query Parameters:** None

**Response:**
```json
{
    "workers": {
        "token_refresh": {
            "name": "Token Refresh",
            "icon": "bi bi-key",
            "settings_url": "/settings?tab=spotify",
            "running": true,
            "status": "idle",
            "details": {
                "check_interval_seconds": 300,
                "refresh_threshold_minutes": 10
            }
        },
        "spotify_sync": {
            "name": "Spotify Sync",
            "icon": "bi bi-spotify",
            "settings_url": "/settings?tab=spotify",
            "running": true,
            "status": "idle",
            "details": {
                "last_syncs": {
                    "artists": "vor 5 min",
                    "playlists": "vor 10 min",
                    "liked_songs": "vor 15 min"
                },
                "check_interval_seconds": 60,
                "stats": {...},
                "has_errors": false
            }
        },
        "download_monitor": {
            "name": "Download Monitor",
            "icon": "bi bi-download",
            "settings_url": "/settings?tab=downloads",
            "running": true,
            "status": "idle",
            "details": {
                "poll_interval_seconds": 10,
                "last_poll": "gerade eben",
                "downloads_completed": 50,
                "downloads_failed": 2,
                "last_error": null
            }
        },
        "automation": {
            "name": "Automation",
            "icon": "bi bi-robot",
            "settings_url": "/settings?tab=automation",
            "running": true,
            "status": "idle",
            "details": {
                "watchlist_running": true,
                "discography_running": false,
                "quality_upgrade_running": true
            }
        }
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 617-669

@router.get("/status")
async def get_all_workers_status(request: Request) -> AllWorkersStatus:
    """Get status of all background workers.
    
    Returns status information for:
    - Token Refresh Worker: Keeps Spotify OAuth tokens fresh
    - Spotify Sync Worker: Automatically syncs Spotify data
    - Download Monitor Worker: Tracks slskd download progress
    - Retry Scheduler Worker: Schedules automatic retries for failed downloads
    - Post-Processing Worker: Tags and organizes completed downloads
    - Queue Dispatcher Worker: Dispatches jobs from queue to slskd
    - Automation Workers: Watchlist, Discography, Quality Upgrade
    - Cleanup Worker: Removes orphaned files (disabled by default)
    - Duplicate Detector Worker: Finds duplicate tracks (disabled by default)
    """
    workers = {
        "token_refresh": _get_token_worker_status(request),
        "spotify_sync": _get_spotify_sync_worker_status(request),
        "download_monitor": _get_download_monitor_worker_status(request),
        "retry_scheduler": _get_retry_scheduler_worker_status(request),
        "post_processing": _get_post_processing_worker_status(request),
        "queue_dispatcher": _get_queue_dispatcher_worker_status(request),
        "automation": _get_automation_workers_status(request),
        "cleanup": _get_cleanup_worker_status(request),
        "duplicate_detector": _get_duplicate_detector_worker_status(request),
    }

    return AllWorkersStatus(workers=workers)
```

**Worker Status Fields:**
- `name` (string): Display name of the worker
- `icon` (string): Font Awesome icon class (e.g., "bi bi-spotify")
- `settings_url` (string): URL to relevant settings page
- `running` (boolean): Whether the worker is currently running
- `status` (string): Current state
  - `idle`: Running but not actively processing
  - `active`: Currently processing tasks
  - `error`: Encountered error during operation
  - `stopped`: Not running
- `details` (object): Worker-specific information (varies by worker)

**Worker-Specific Details:**

**Token Refresh Worker:**
```json
{
    "check_interval_seconds": 300,
    "refresh_threshold_minutes": 10
}
```

**Spotify Sync Worker:**
```json
{
    "last_syncs": {
        "artists": "vor 5 min",
        "playlists": "vor 10 min",
        "liked_songs": "vor 15 min",
        "saved_albums": "noch nie"
    },
    "check_interval_seconds": 60,
    "stats": {...},
    "has_errors": false
}
```

**Download Monitor Worker:**
```json
{
    "poll_interval_seconds": 10,
    "last_poll": "gerade eben",
    "downloads_completed": 50,
    "downloads_failed": 2,
    "last_error": null
}
```

**Automation Workers (Combined):**
```json
{
    "watchlist_running": true,
    "discography_running": false,
    "quality_upgrade_running": true
}
```

**Cleanup Worker:**
```json
{
    "dry_run": false,
    "last_run": "vor 3 h",
    "files_deleted": 15,
    "bytes_freed": 50000000,
    "last_error": null
}
```

**Duplicate Detector Worker:**
```json
{
    "detection_method": "metadata-hash",
    "last_scan": "vor 2 d",
    "duplicates_found": 5,
    "tracks_scanned": 5000,
    "last_error": null
}
```

---

### Get Workers Status (HTML Partial)

**Endpoint:** `GET /workers/status/html`

**Description:** Get HTML partial for HTMX polling (sidebar status indicator).

**Query Parameters:** None

**Response:** HTML fragment with:
- Worker icons with status-based animations
- Comprehensive tooltip with ALL workers + service status
- Service connectivity indicators (Spotify, slskd, MusicBrainz, CoverArt)

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 678-878

@router.get("/status/html", response_class=HTMLResponse)
async def get_workers_status_html(request: Request) -> HTMLResponse:
    """Get HTML partial for worker status indicator.
    
    Returns an HTML fragment for HTMX polling that shows:
    - Worker icons with status-based animations
    - Comprehensive tooltip with ALL workers + service status
    - Service connectivity indicators (Spotify, slskd, etc.)
    
    Used by the sidebar footer to display real-time worker status.
    """
```

**HTML Structure:**
```html
<div class="worker-indicator-single" tabindex="0">
    <a href="/settings?tab=spotify"
       class="worker-icon"
       data-status="idle"
       aria-label="Background Workers: Aktiv">
        <i class="bi bi-disc"></i>
    </a>

    <div class="worker-tooltip" role="tooltip">
        <div class="tooltip-header">
            <span>🔄 Background Workers</span>
            <span class="tooltip-badge tooltip-badge-idle">Aktiv</span>
        </div>

        <div class="tooltip-workers-section">
            <!-- Worker rows with status icons -->
        </div>

        <div class="tooltip-divider"></div>

        <div class="tooltip-services-section">
            <div class="tooltip-services-title">📡 Service Status</div>
            <div class="tooltip-services-grid">
                <!-- Service status rows -->
            </div>
        </div>
    </div>
</div>
```

**Status Icons & Colors:**
- **Idle**: `●` (green #4ade80) - Running but not active
- **Active**: `⟳` (blue #3b82f6) - Currently processing
- **Error**: `✕` (red #ef4444) - Error encountered
- **Stopped**: `○` (gray #9ca3af) - Not running

**Worker Tooltip Details:**

**Spotify Sync Worker:**
```
🎤 vor 5 min  📋 vor 10 min  ❤️ vor 15 min  💿 noch nie
```

**Download Monitor Worker:**
```
↻ alle 10s • ✓ 50 • ✕ 2
```

**Service Status Grid:**
```
✓ 🎵 Spotify
✓ ⬇️ Soulseek (slskd)
✓ 🎼 MusicBrainz
✓ 🖼️ CoverArt
```

**HTMX Integration:**
```html
<!-- Frontend polls this endpoint every 10 seconds -->
<div hx-get="/api/workers/status/html"
     hx-trigger="every 10s"
     hx-swap="outerHTML">
</div>
```

**Icon Animations (CSS):**
- **Idle**: Pulse animation (subtle glow)
- **Active**: Rotate animation (spinning icon)
- **Error**: Red color, no animation
- **Stopped**: Gray color, no animation

**Code Reference (Helper Functions):**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py

# Lines 61-81: _format_time_ago() - Formats datetime as "vor 5 min"
# Lines 84-92: _format_time_until() - Formats minutes as "in 30 min"
# Lines 95-128: _get_token_worker_status() - Token refresh status
# Lines 131-184: _get_spotify_sync_worker_status() - Spotify sync status
# Lines 187-238: _get_download_monitor_worker_status() - Download monitor status
# Lines 241-289: _get_automation_workers_status() - Combined automation status
# Lines 292-335: _get_cleanup_worker_status() - Cleanup worker status
# Lines 338-382: _get_duplicate_detector_worker_status() - Duplicate detector status
# Lines 385-438: _get_retry_scheduler_worker_status() - Retry scheduler status
# Lines 441-485: _get_post_processing_worker_status() - Post-processing status
# Lines 488-542: _get_queue_dispatcher_worker_status() - Queue dispatcher status
# Lines 545-574: _get_service_status() - External service connectivity
```

---

## Orchestrator Endpoints (New Dec 2025)

The **Worker Orchestrator** provides centralized worker lifecycle management and health monitoring.

### Get Orchestrator Status

**Endpoint:** `GET /workers/orchestrator`

**Description:** Get comprehensive status from the Worker Orchestrator including all workers tracked, grouped by state, and overall health.

**Query Parameters:** None

**Response:**
```json
{
    "total_workers": 12,
    "running": 9,
    "stopped": 2,
    "failed": 1,
    "healthy": false,
    "workers": {
        "token_refresh": {
            "name": "token_refresh",
            "state": "running",
            "category": "critical",
            "priority": 100,
            "required": true,
            "started_at": "2025-12-15T10:00:00Z",
            "stopped_at": null,
            "error": null,
            "depends_on": []
        },
        "spotify_sync": {
            "name": "spotify_sync",
            "state": "running",
            "category": "sync",
            "priority": 80,
            "required": false,
            "started_at": "2025-12-15T10:00:05Z",
            "stopped_at": null,
            "error": null,
            "depends_on": ["token_refresh"]
        },
        "cleanup": {
            "name": "cleanup",
            "state": "stopped",
            "category": "maintenance",
            "priority": 10,
            "required": false,
            "started_at": null,
            "stopped_at": null,
            "error": null,
            "depends_on": []
        }
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 895-926

@router.get("/orchestrator")
async def get_orchestrator_status(request: Request) -> dict[str, Any]:
    """Get comprehensive status from the Worker Orchestrator.
    
    Returns detailed status of all workers tracked by the orchestrator,
    including:
    - Total worker count
    - Workers grouped by state (running, stopped, failed)
    - Per-worker details (name, category, priority, started_at, etc.)
    - Overall health status
    
    This is the preferred endpoint for monitoring and debugging worker status.
    Use /api/workers/status for the UI-friendly format with icons and tooltips.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {
            "error": "Orchestrator not initialized",
            "total_workers": 0,
            "healthy": False,
            "workers": {},
        }

    status = orchestrator.get_status()
    status["healthy"] = orchestrator.is_healthy()

    return status
```

**Response Fields:**
- `total_workers` (integer): Total workers registered
- `running` (integer): Workers currently running
- `stopped` (integer): Workers not running
- `failed` (integer): Workers in error state
- `healthy` (boolean): Whether all required workers are running
- `workers` (object): Detailed worker information

**Worker Information:**
- `name` (string): Worker name
- `state` (string): Current state (`running`, `stopped`, `failed`)
- `category` (string): Worker category
  - `critical`: Must be running for app functionality
  - `sync`: Data synchronization workers
  - `download`: Download management workers
  - `automation`: Automation workers (optional)
  - `maintenance`: Maintenance workers (optional)
  - `enrichment`: Metadata enrichment workers
- `priority` (integer): Start priority (100 = highest)
- `required` (boolean): Whether worker is required for health check
- `started_at` (string): ISO timestamp of start time (null if never started)
- `stopped_at` (string): ISO timestamp of stop time (null if not stopped)
- `error` (string): Error message if `state=failed` (null otherwise)
- `depends_on` (array): Names of workers this worker depends on

**Health Check:**
- `healthy=true`: All required workers are running
- `healthy=false`: At least one required worker is not running

**Use Cases:**
- **Monitoring**: Check overall worker health
- **Debugging**: Identify failed workers
- **Dependency Tracking**: Understand worker dependencies
- **Alerting**: Trigger alerts if `healthy=false`

---

## Worker Control Endpoints (New Dec 2025)

**⚠️ Warning:** These endpoints control worker lifecycle. Only use for:
- Debugging (manual worker restart)
- Maintenance (pause workers during updates)
- Testing (isolated worker testing)

**🔒 Security:** Consider adding authentication/rate-limiting in production!

### Stop Worker

**Endpoint:** `POST /workers/orchestrator/{worker_name}/stop`

**Description:** Stop a specific worker by name.

**Path Parameters:**
- `worker_name` (string): Worker name (e.g., "token_refresh", "spotify_sync")

**Response:**
```json
{
    "success": true,
    "worker": "spotify_sync",
    "state": "stopped",
    "message": "Worker 'spotify_sync' stopped successfully"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 947-989

@router.post("/orchestrator/{worker_name}/stop")
async def stop_worker(request: Request, worker_name: str) -> dict[str, Any]:
    """Stop a specific worker by name.
    
    Warning: Stopping critical workers may affect app functionality!
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"success": False, "error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"success": False, "error": f"Worker '{worker_name}' not found"}

    try:
        # Stop the worker
        stop_result = worker_info.worker.stop()
        if asyncio.iscoroutine(stop_result):
            await stop_result

        # Update state
        from soulspot.application.workers.orchestrator import WorkerState
        worker_info.state = WorkerState.STOPPED

        return {
            "success": True,
            "worker": worker_name,
            "state": "stopped",
            "message": f"Worker '{worker_name}' stopped successfully",
        }
    except Exception as e:
        return {
            "success": False,
            "worker": worker_name,
            "error": str(e),
        }
```

**Error Response:**
```json
{
    "success": false,
    "worker": "spotify_sync",
    "error": "Worker is in critical state and cannot be stopped"
}
```

**Response Fields:**
- `success` (boolean): Whether operation succeeded
- `worker` (string): Worker name
- `state` (string): New state ("stopped")
- `message` (string): Success message
- `error` (string): Error message (if `success=false`)

**Error Handling:**
- **Worker not found**: Returns `success=false` with error
- **Stop failed**: Returns `success=false` with exception message
- **Orchestrator not initialized**: Returns `success=false`

**⚠️ Warning:** Stopping critical workers (e.g., `token_refresh`, `download_monitor`) may affect app functionality!

---

### Start Worker

**Endpoint:** `POST /workers/orchestrator/{worker_name}/start`

**Description:** Start a specific worker by name.

**Path Parameters:**
- `worker_name` (string): Worker name (e.g., "token_refresh", "spotify_sync")

**Response:**
```json
{
    "success": true,
    "worker": "spotify_sync",
    "state": "running",
    "message": "Worker 'spotify_sync' started successfully"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 992-1035

@router.post("/orchestrator/{worker_name}/start")
async def start_worker(request: Request, worker_name: str) -> dict[str, Any]:
    """Start a specific worker by name."""
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"success": False, "error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"success": False, "error": f"Worker '{worker_name}' not found"}

    try:
        # Check if already running
        from soulspot.application.workers.orchestrator import WorkerState
        if worker_info.state == WorkerState.RUNNING:
            return {
                "success": True,
                "worker": worker_name,
                "state": "running",
                "message": f"Worker '{worker_name}' is already running",
            }

        # Start the worker
        await worker_info.worker.start()
        worker_info.state = WorkerState.RUNNING

        return {
            "success": True,
            "worker": worker_name,
            "state": "running",
            "message": f"Worker '{worker_name}' started successfully",
        }
    except Exception as e:
        worker_info.state = WorkerState.FAILED
        worker_info.error = str(e)
        return {
            "success": False,
            "worker": worker_name,
            "error": str(e),
        }
```

**Already Running Response:**
```json
{
    "success": true,
    "worker": "spotify_sync",
    "state": "running",
    "message": "Worker 'spotify_sync' is already running"
}
```

**Error Response:**
```json
{
    "success": false,
    "worker": "spotify_sync",
    "error": "Worker failed to start: [exception message]"
}
```

**Response Fields:**
- `success` (boolean): Whether operation succeeded
- `worker` (string): Worker name
- `state` (string): New state ("running" or previous state if failed)
- `message` (string): Success/info message
- `error` (string): Error message (if `success=false`)

**Error Handling:**
- **Worker not found**: Returns `success=false` with error
- **Start failed**: Sets worker state to `FAILED`, returns error
- **Orchestrator not initialized**: Returns `success=false`

**Idempotent:** If worker already running, returns success without error.

---

### Get Worker Status (Single)

**Endpoint:** `GET /workers/orchestrator/{worker_name}`

**Description:** Get detailed status of a specific worker.

**Path Parameters:**
- `worker_name` (string): Worker name (e.g., "token_refresh", "spotify_sync")

**Response:**
```json
{
    "name": "spotify_sync",
    "state": "running",
    "category": "sync",
    "priority": 80,
    "required": false,
    "started_at": "2025-12-15T10:00:05Z",
    "stopped_at": null,
    "error": null,
    "depends_on": ["token_refresh"],
    "worker_details": {
        "running": true,
        "check_interval_seconds": 60,
        "last_sync": {...},
        "stats": {...}
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/workers.py
# Lines 1038-1075

@router.get("/orchestrator/{worker_name}")
async def get_worker_status(request: Request, worker_name: str) -> dict[str, Any]:
    """Get detailed status of a specific worker.
    
    Returns:
        Detailed worker status including state, category, start time, errors, etc.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"error": f"Worker '{worker_name}' not found"}

    # Get worker's own status
    try:
        worker_status = worker_info.worker.get_status()
    except Exception:
        worker_status = {}

    return {
        "name": worker_name,
        "state": worker_info.state.value,
        "category": worker_info.category,
        "priority": worker_info.priority,
        "required": worker_info.required,
        "started_at": worker_info.started_at.isoformat() if worker_info.started_at else None,
        "stopped_at": worker_info.stopped_at.isoformat() if worker_info.stopped_at else None,
        "error": worker_info.error,
        "depends_on": worker_info.depends_on,
        "worker_details": worker_status,
    }
```

**Error Response:**
```json
{
    "error": "Worker 'invalid_worker' not found"
}
```

**Response Fields:**
- `name` (string): Worker name
- `state` (string): Current state (`running`, `stopped`, `failed`)
- `category` (string): Worker category
- `priority` (integer): Start priority
- `required` (boolean): Whether required for health check
- `started_at` (string): ISO timestamp (null if never started)
- `stopped_at` (string): ISO timestamp (null if not stopped)
- `error` (string): Error message (null if no error)
- `depends_on` (array): Dependency worker names
- `worker_details` (object): Worker-specific status (from `worker.get_status()`)

**Use Cases:**
- **Debugging**: Inspect single worker in detail
- **Monitoring**: Track specific worker over time
- **Dependency Analysis**: Understand worker dependencies

---

## Helper Functions (Internal)

The workers router uses several helper functions for status formatting:

### Time Formatting

**`_format_time_ago(dt: datetime | None) -> str`**

Formats datetime as relative time string (e.g., "vor 5 min").

**Examples:**
- `< 60s` → "gerade eben"
- `< 60 min` → "vor 5 min"
- `< 24h` → "vor 3 h"
- `≥ 24h` → "vor 2 d"
- `None` → "noch nie"

**Handles both naive and aware datetimes** (different workers use different formats).

**Code Reference:** Lines 61-81

---

**`_format_time_until(minutes: int) -> str`**

Formats minutes until next action as readable string.

**Examples:**
- `≤ 0` → "jetzt"
- `< 60` → "in 30 min"
- `≥ 60` → "in 2 h"

**Code Reference:** Lines 84-92

---

### Service Connectivity Check

**`_get_service_status(request: Request) -> dict[str, Any]`**

Checks connectivity to external services:
- **Spotify**: OAuth token valid? (via Token Refresh Worker)
- **slskd**: Can connect? (via Download Monitor Worker)
- **MusicBrainz/CoverArt**: Assumed available (could add health checks)

**Returns:**
```python
{
    "spotify": True,      # Token Worker running
    "slskd": True,        # Download Monitor running
    "musicbrainz": True,  # Assumed available
    "coverart": True      # Assumed available
}
```

**Code Reference:** Lines 545-574

---

## Summary

**Total Endpoints Documented:** 6 worker control endpoints

**Endpoint Categories:**
1. **Status Monitoring**: 2 endpoints (JSON, HTML partial)
2. **Orchestrator**: 1 endpoint (comprehensive status)
3. **Worker Control**: 3 endpoints (stop, start, get single)

**Key Features:**
- **Real-Time Monitoring**: 10-second HTMX polling for live updates
- **HTMX Integration**: HTML partial for sidebar status indicator
- **Orchestrator Pattern**: Centralized worker lifecycle management
- **Health Tracking**: Critical worker validation and dependency checking
- **Admin Control**: Manual start/stop for debugging/maintenance

**Module Stats:**
- **workers.py**: 1035 lines, 6 endpoints
- **Code validation**: 100% (all endpoints verified)

**Workers Tracked:**
- **Critical**: Token Refresh, Download Monitor
- **Sync**: Spotify Sync, New Releases Sync
- **Download**: Queue Dispatcher, Retry Scheduler, Post-Processing
- **Automation**: Watchlist, Discography, Quality Upgrade
- **Maintenance**: Cleanup, Duplicate Detector

**External Service Monitoring:**
- Spotify (OAuth)
- slskd (Soulseek)
- MusicBrainz
- CoverArtArchive

**Security Notes:**
- Worker control endpoints should be protected in production
- Consider adding authentication middleware
- Rate-limiting recommended for control endpoints
