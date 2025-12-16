# Workers API

> **Version:** 2.0  
> **Last Updated:** 2025-01-06  
> **Base Path:** `/api/workers`

---

## Overview

The Workers API provides endpoints for monitoring and controlling background workers. These workers handle automated tasks like OAuth token refresh, Spotify synchronization, download monitoring, and automation.

The primary use case is the **Sidebar Status Indicator** which polls `/api/workers/status/html` every 10 seconds to show real-time worker status with animated icons.

---

## Workers Overview

| Worker | Purpose | Default State |
|--------|---------|---------------|
| **Token Refresh** | Keeps Spotify OAuth tokens fresh | Running |
| **Spotify Sync** | Auto-syncs artists, playlists, albums | Running |
| **Download Monitor** | Tracks slskd download progress | Running |
| **Automation** | Watchlist, Discography, Quality Upgrade | Disabled |
| **Cleanup** | Removes orphaned temp files | Disabled |
| **Duplicate Detector** | Finds duplicate tracks | Disabled |

---

## Endpoints

### Get All Workers Status (JSON)

```http
GET /api/workers/status
```

Returns JSON with status information for all workers. Useful for debugging or custom integrations.

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
          "playlists": "vor 12 min",
          "albums": "vor 1 h"
        },
        "check_interval_seconds": 60,
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
        "downloads_completed": 42,
        "downloads_failed": 2
      }
    },
    "automation": {
      "name": "Automation",
      "icon": "bi bi-robot",
      "settings_url": "/settings?tab=automation",
      "running": false,
      "status": "stopped",
      "details": {
        "watchlist_running": false,
        "discography_running": false,
        "quality_upgrade_running": false
      }
    },
    "cleanup": {
      "name": "Cleanup",
      "icon": "bi bi-trash3",
      "settings_url": "/settings?tab=automation",
      "running": false,
      "status": "stopped",
      "details": {
        "dry_run": false,
        "last_run": "noch nie",
        "files_deleted": 0,
        "bytes_freed": 0
      }
    },
    "duplicate_detector": {
      "name": "Duplicate Detector",
      "icon": "bi bi-copy",
      "settings_url": "/settings?tab=automation",
      "running": false,
      "status": "stopped",
      "details": {
        "detection_method": "metadata-hash",
        "last_scan": "noch nie",
        "duplicates_found": 0,
        "tracks_scanned": 0
      }
    }
  }
}
```

### Get All Workers Status (HTML)

```http
GET /api/workers/status/html
```

Returns an HTML partial for HTMX integration. Used by the sidebar footer to display worker status icons.

**Usage in Templates:**
```html
<div hx-get="/api/workers/status/html" 
     hx-trigger="load, every 10s" 
     hx-swap="innerHTML">
</div>
```

**Response:**
Returns Bootstrap Icons with tooltips showing:
- **Idle (Green)**: Worker running, waiting for next task
- **Active (Spinning)**: Worker currently processing
- **Error (Red)**: Worker encountered an error
- **Stopped (Gray)**: Worker not running

### Get Service Connectivity Status

```http
GET /api/workers/services
```

Returns connectivity status for external services.

**Response:**
```json
{
  "spotify": true,
  "slskd": true,
  "musicbrainz": true,
  "coverart": true
}
```

---

## Worker Status Schema

Each worker returns a `WorkerStatusInfo` object:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name |
| `icon` | string | Bootstrap Icon class |
| `settings_url` | string | URL to settings page |
| `running` | bool | Whether the worker task is running |
| `status` | string | Current status: `idle`, `active`, `error`, `stopped` |
| `details` | object | Worker-specific details |

---

## Status Values

| Status | Icon State | Description |
|--------|------------|-------------|
| `idle` | Green, pulsing gently | Running, waiting for next task |
| `active` | Spinning | Currently processing |
| `error` | Red | Encountered an error (see details.last_error) |
| `stopped` | Gray | Not running (disabled or not initialized) |

---

## Worker Details

### Token Refresh Worker

| Detail | Type | Description |
|--------|------|-------------|
| `check_interval_seconds` | int | How often to check token validity |
| `refresh_threshold_minutes` | int | Refresh if token expires within this many minutes |

### Spotify Sync Worker

| Detail | Type | Description |
|--------|------|-------------|
| `last_syncs` | object | Last sync times per sync type (artists, playlists, albums) |
| `check_interval_seconds` | int | How often to check for sync needs |
| `has_errors` | bool | Whether any sync operation has errors |
| `stats` | object | Cumulative sync statistics |

### Download Monitor Worker

| Detail | Type | Description |
|--------|------|-------------|
| `poll_interval_seconds` | int | How often to poll slskd |
| `last_poll` | string | Human-readable time since last poll |
| `downloads_completed` | int | Cumulative completed downloads |
| `downloads_failed` | int | Cumulative failed downloads |

### Automation Workers

| Detail | Type | Description |
|--------|------|-------------|
| `watchlist_running` | bool | Watchlist worker running |
| `discography_running` | bool | Discography worker running |
| `quality_upgrade_running` | bool | Quality upgrade worker running |

### Cleanup Worker

| Detail | Type | Description |
|--------|------|-------------|
| `dry_run` | bool | Running in dry-run mode (no actual deletions) |
| `last_run` | string | Human-readable time since last run |
| `files_deleted` | int | Cumulative files deleted |
| `bytes_freed` | int | Cumulative bytes freed |

### Duplicate Detector Worker

| Detail | Type | Description |
|--------|------|-------------|
| `detection_method` | string | Method used (e.g., "metadata-hash") |
| `last_scan` | string | Human-readable time since last scan |
| `duplicates_found` | int | Cumulative duplicates found |
| `tracks_scanned` | int | Cumulative tracks scanned |

---

## Time Formatting

The API formats times as German human-readable strings:

| Time Ago | Format |
|----------|--------|
| < 60 seconds | "gerade eben" |
| < 60 minutes | "vor X min" |
| < 24 hours | "vor X h" |
| ≥ 24 hours | "vor X d" |
| Never run | "noch nie" |

---

## Controlling Workers

Workers are controlled via the Settings UI, not via API endpoints. To enable/disable workers:

1. Navigate to `/settings?tab=automation`
2. Toggle the relevant worker setting
3. Changes take effect immediately

---

## Related Documentation

- [Settings API](settings-api.md)
- [Infrastructure API](infrastructure-api.md)
- [Architecture: Worker Patterns](../architecture/WORKER_PATTERNS.md)
