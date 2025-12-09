# Infrastructure APIs Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Routers:** `stats.py`, `artwork.py`, `sse.py`, `workers.py`

---

## Overview

This document covers **4 infrastructure APIs** that provide system-level functionality:

1. **Stats API** - Dashboard statistics & trends
2. **Artwork API** - Local artwork file serving
3. **SSE API** - Server-Sent Events (real-time updates)
4. **Workers API** - Background worker status

---

## 1. Stats API (`/api/stats`)

### GET `/api/stats/trends`

**Purpose:** Get dashboard statistics with trend indicators.

**Response:**
```json
{
  "playlists": 42,
  "tracks": 1234,
  "tracks_downloaded": 800,
  "downloads_completed": 450,
  "downloads_failed": 3,
  "queue_size": 12,
  "active_downloads": 2,
  "spotify_artists": 89,
  "spotify_albums": 203,
  "spotify_tracks": 1150,
  "trends": {
    "downloads_completed": {
      "current": 450,
      "previous": 438,
      "change": 12,
      "change_percent": 2.74,
      "direction": "up",
      "period": "today"
    }
  },
  "last_updated": "2025-12-09T15:30:00Z"
}
```

**Trends:**
- `downloads_completed` - Today vs. yesterday
- `playlists` - This week vs. last week
- `tracks_downloaded` - This week vs. last week

**Use Cases:**
- Dashboard stat cards with trend arrows (↑/↓)
- Weekly progress tracking
- Download activity monitoring

**Code Reference:**
```python
# src/soulspot/api/routers/stats.py (lines 67-150)
@router.get("/trends")
async def get_stats_with_trends(...) -> StatsWithTrends:
    """Get dashboard statistics with trend indicators."""
    ...
```

---

## 2. Artwork API (`/api/artwork`)

### GET `/api/artwork/{file_path:path}`

**Purpose:** Serve locally stored album/artist artwork files.

**Parameters:**
- `file_path` (path) - Relative path from `ARTWORK_PATH` setting

**Example Request:**
```bash
GET /api/artwork/artists/abc123/cover.jpg
GET /api/artwork/albums/xyz789/folder.png
```

**Response:**
- **200 OK** - Image file (JPEG/PNG/WebP/GIF)
- **404 Not Found** - File doesn't exist
- **403 Forbidden** - Path traversal attempt blocked

**Security:**
- Uses `Path.resolve() + is_relative_to()` to prevent path traversal attacks
- Blocks requests like `../../../etc/passwd`

**Supported Formats:**
- `.jpg`, `.jpeg` → `image/jpeg`
- `.png` → `image/png`
- `.webp` → `image/webp`
- `.gif` → `image/gif`

**Code Reference:**
```python
# src/soulspot/api/routers/artwork.py (lines 23-76)
@router.get("/{file_path:path}")
async def serve_artwork(file_path: str, ...) -> FileResponse:
    """Serve artwork file from local storage."""
    ...
```

---

## 3. SSE API (`/api/sse`)

### GET `/api/sse/stream`

**Purpose:** Server-Sent Events stream for real-time UI updates.

**Query Parameters:**
- `poll_interval` (int, default: `2`) - Polling interval in seconds

**Response:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: download_update
data: {"id": "abc123", "progress": 50}

event: heartbeat
data: {"timestamp": "2025-12-09T15:30:00Z"}
```

**Event Types:**
- `download_update` - Download progress changed
- `queue_update` - Download queue changed
- `heartbeat` - Keep-alive ping (every 30s)

**Use Cases:**
- Live download progress bars
- Real-time queue updates
- Dashboard activity feed

**Client Example (JavaScript):**
```javascript
const eventSource = new EventSource('/api/sse/stream');

eventSource.addEventListener('download_update', (e) => {
    const data = JSON.parse(e.data);
    console.log(`Download ${data.id}: ${data.progress}%`);
});

eventSource.addEventListener('heartbeat', (e) => {
    console.log('Connection alive');
});
```

**Code Reference:**
```python
# src/soulspot/api/routers/sse.py (lines 100-250)
@router.get("/stream")
async def sse_stream(poll_interval: int = 2, ...) -> StreamingResponse:
    """Server-Sent Events stream for real-time updates."""
    ...
```

---

## 4. Workers API (`/api/workers`)

### GET `/api/workers/status`

**Purpose:** Get JSON status of all background workers.

**Response:**
```json
{
  "workers": {
    "token_refresh": {
      "name": "Token Refresh Worker",
      "icon": "fa-key",
      "settings_url": "/settings#spotify-sync",
      "running": true,
      "status": "idle",
      "details": {
        "last_refresh": "2025-12-09T15:25:00Z",
        "next_refresh_in_minutes": 55,
        "token_expires_at": "2025-12-09T16:20:00Z"
      }
    },
    "spotify_sync": {
      "name": "Spotify Sync Worker",
      "icon": "fa-spotify",
      "settings_url": "/settings#spotify-sync",
      "running": true,
      "status": "active",
      "details": {
        "last_sync": "2025-12-09T15:10:00Z",
        "next_sync_in_minutes": 20,
        "sync_interval_minutes": 30
      }
    }
  }
}
```

**Worker Statuses:**
- `idle` - Running, waiting for next action
- `active` - Currently processing
- `error` - Failed, needs attention
- `stopped` - Not running

**Code Reference:**
```python
# src/soulspot/api/routers/workers.py (lines 100-200)
@router.get("/status")
async def get_all_workers_status(...) -> AllWorkersStatus:
    """Get status of all background workers."""
    ...
```

### GET `/api/workers/status/html`

**Purpose:** Get HTML fragment for sidebar worker status indicator.

**Response:**
```html
<div class="worker-status-container">
  <div class="worker-icon" data-worker="token_refresh" data-status="idle">
    <i class="fa-solid fa-key pulse"></i>
  </div>
  <div class="worker-icon" data-worker="spotify_sync" data-status="active">
    <i class="fa-brands fa-spotify spin"></i>
  </div>
</div>
```

**Use Cases:**
- Sidebar worker status indicator (HTMX polling)
- Animated icons (idle = pulse, active = spin, error = red)
- Tooltips with worker details

**Code Reference:**
```python
# src/soulspot/api/routers/workers.py (lines 300-400)
@router.get("/status/html")
async def get_workers_status_html(...) -> HTMLResponse:
    """Get HTML fragment for worker status indicator."""
    ...
```

---

## Summary

**7 Endpoints** across 4 infrastructure routers:

| Endpoint | Method | Purpose | Complexity |
|----------|--------|---------|------------|
| `/stats/trends` | GET | Dashboard statistics + trends | Medium |
| `/artwork/{path}` | GET | Serve local artwork files | Low |
| `/sse/stream` | GET | Server-Sent Events stream | High |
| `/workers/status` | GET | Worker status (JSON) | Medium |
| `/workers/status/html` | GET | Worker status (HTML) | Medium |

**Key Features:**
- 📊 **Stats API** - Trend calculations (today vs. yesterday, week vs. last week)
- 🖼️ **Artwork API** - Secure file serving (path traversal protection)
- 📡 **SSE API** - Real-time updates (long-lived HTTP connection)
- ⚙️ **Workers API** - Background worker monitoring (Token Refresh, Spotify Sync)

**Performance Notes:**
- `/stats/trends` - Fast (< 200ms, database aggregations)
- `/artwork/{path}` - Fast (< 50ms, direct file serving)
- `/sse/stream` - Long-lived (infinite stream until disconnect)
- `/workers/status` - Fast (< 100ms, in-memory state check)
