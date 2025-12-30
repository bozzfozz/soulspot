# Download Manager API

Unified download management across multiple providers (Soulseek, future: Spotify Direct, etc.).

## Overview

The Download Manager API provides a unified interface for managing downloads from multiple providers:
- **Unified Downloads**: Single view of downloads across all providers
- **Queue Statistics**: Download counts by status (waiting, pending, downloading, etc.)
- **Real-Time Updates**: SSE endpoint for live progress
- **Provider Health**: Circuit breaker status for each provider
- **HTMX Integration**: Server-rendered HTML partials for UI

**Providers:**
- **slskd**: Soulseek downloads (current)
- **Future**: Spotify Direct Download, Deezer, etc.

**Download States:**
- `WAITING`: In SoulSpot's queue, not sent to provider yet
- `PENDING`: Sent to provider, waiting for slot
- `QUEUED`: In provider's queue
- `DOWNLOADING`: Actively downloading
- `PAUSED`: Download paused by user/provider
- `STALLED`: Download stalled (no progress)
- `COMPLETED`: Download finished successfully
- `FAILED`: Download failed with error

---

## Get Active Downloads

**Endpoint:** `GET /api/downloads/manager/active`

**Description:** Get all active downloads from all providers (unified view).

**Query Parameters:** None

**Response:**
```json
{
    "downloads": [
        {
            "id": "unified-download-uuid-123",
            "track_id": "track-uuid-456",
            "track_info": {
                "title": "Song Title",
                "artist": "Artist Name",
                "album": "Album Name",
                "display_name": "Artist Name - Song Title"
            },
            "provider": "soulseek",
            "provider_name": "slskd",
            "external_id": "slskd-download-789",
            "status": "downloading",
            "status_message": null,
            "error_message": null,
            "progress": {
                "percent": 45.5,
                "bytes_downloaded": 15728640,
                "total_bytes": 34603008,
                "speed_bytes_per_sec": 524288,
                "eta_seconds": 36,
                "speed_formatted": "512 KB/s",
                "eta_formatted": "36s",
                "size_formatted": "33 MB"
            },
            "created_at": "2025-12-15T10:00:00Z",
            "started_at": "2025-12-15T10:01:00Z",
            "is_active": true,
            "can_cancel": true
        }
    ],
    "stats": {
        "waiting": 5,
        "pending": 3,
        "queued": 2,
        "downloading": 2,
        "paused": 0,
        "stalled": 1,
        "completed_today": 15,
        "failed_today": 2,
        "total_active": 13,
        "total_in_progress": 7,
        "summary_text": "13 active · 2 downloading"
    },
    "providers_available": ["slskd"]
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 176-208

@router.get("/active", response_model=ActiveDownloadsResponse)
async def get_active_downloads(
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> ActiveDownloadsResponse:
    """Get all active downloads from all providers.

    Returns a unified view of:
    - Downloads waiting in SoulSpot's queue (WAITING, PENDING)
    - Downloads active in providers (QUEUED, DOWNLOADING, PAUSED, STALLED)

    Plus queue statistics and available providers.
    """
```

**UnifiedDownload Fields:**
- `id` (string): Unified download UUID
- `track_id` (string): Track UUID
- `track_info` (object): Track metadata
  - `title` (string): Track title
  - `artist` (string): Artist name
  - `album` (string | null): Album name
  - `display_name` (string): Formatted display name
- `provider` (string): Provider ID (`soulseek`, `spotify`, etc.)
- `provider_name` (string): Provider display name
- `external_id` (string | null): Provider-specific download ID
- `status` (string): Current status
- `status_message` (string | null): Provider status message
- `error_message` (string | null): Error details if failed
- `progress` (object): Progress information
  - `percent` (float): Progress percentage (0-100)
  - `bytes_downloaded` (integer): Bytes downloaded
  - `total_bytes` (integer): Total file size
  - `speed_bytes_per_sec` (float): Current download speed
  - `eta_seconds` (integer | null): Estimated seconds remaining
  - `speed_formatted` (string): Human-readable speed (e.g., "512 KB/s")
  - `eta_formatted` (string): Human-readable ETA (e.g., "2m 15s")
  - `size_formatted` (string): Human-readable size (e.g., "33 MB")
- `created_at` (datetime): When download was created
- `started_at` (datetime | null): When download started
- `is_active` (boolean): Whether download is currently active
- `can_cancel` (boolean): Whether download can be cancelled

**Queue Statistics Fields:**
- `waiting` (integer): Downloads in SoulSpot queue
- `pending` (integer): Sent to provider, waiting for slot
- `queued` (integer): In provider's queue
- `downloading` (integer): Actively downloading
- `paused` (integer): Paused downloads
- `stalled` (integer): Stalled downloads
- `completed_today` (integer): Completed in last 24h
- `failed_today` (integer): Failed in last 24h
- `total_active` (integer): Total active downloads
- `total_in_progress` (integer): Downloads that are progressing (queued + downloading)
- `summary_text` (string): Human-readable summary

**Use Cases:**
- **Download Manager UI**: Display all active downloads
- **Queue Monitoring**: Track download progress
- **Provider Status**: See which providers are active

**Performance:**
- **Aggregation**: Combines SoulSpot DB + provider API calls
- **Caching**: Provider responses cached for 2-5 seconds
- **Pagination**: All active downloads returned (no pagination yet)

---

## Get Queue Statistics

**Endpoint:** `GET /api/downloads/manager/stats`

**Description:** Get download queue statistics only (lightweight).

**Query Parameters:** None

**Response:**
```json
{
    "waiting": 5,
    "pending": 3,
    "queued": 2,
    "downloading": 2,
    "paused": 0,
    "stalled": 1,
    "completed_today": 15,
    "failed_today": 2,
    "total_active": 13,
    "total_in_progress": 7,
    "summary_text": "13 active · 2 downloading"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 211-226

@router.get("/stats", response_model=QueueStatsDTO)
async def get_queue_stats(
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> QueueStatsDTO:
    """Get download queue statistics.

    Returns counts of downloads in each state, plus recent
    completed/failed counts for the summary bar.
    """
```

**Use Cases:**
- **Dashboard Widget**: Show queue stats without full download list
- **Monitoring**: Track queue health
- **Fast Polling**: Lightweight endpoint for frequent updates

**Performance:**
- **Fast**: DB queries only, no provider API calls
- **Cacheable**: Results can be cached for 1-2 seconds

---

## Download Events (SSE)

**Endpoint:** `GET /api/downloads/manager/events`

**Description:** Server-Sent Events endpoint for real-time download progress.

**Query Parameters:** None

**Response:** SSE stream with events

**Event Format:**
```
event: update
data: {"downloads": [...], "stats": {...}, "timestamp": "2025-12-15T10:00:00Z"}

event: update
data: {"downloads": [...], "stats": {...}, "timestamp": "2025-12-15T10:00:02Z"}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 229-305

@router.get("/events")
async def download_events(
    request: Request,
) -> EventSourceResponse:
    """Server-Sent Events endpoint for real-time download progress.

    Sends updates every 2 seconds with current download status.
    Use this for live progress bars without polling.

    Note: We create fresh sessions per update to avoid stale connections.

    Example JS client:
    ```javascript
    const evtSource = new EventSource('/api/downloads/manager/events');
    evtSource.addEventListener('update', (event) => {
        const data = JSON.parse(event.data);
        updateProgressBars(data.downloads);
    });
    ```
    """
```

**Event Data:**
```json
{
    "downloads": [
        {
            "id": "...",
            "track_info": {...},
            "status": "downloading",
            "progress": {...}
        }
    ],
    "stats": {
        "waiting": 5,
        "downloading": 2,
        "total_active": 13
    },
    "timestamp": "2025-12-15T10:00:02Z"
}
```

**SSE Behavior:**
- **Update Interval**: 2 seconds
- **Fresh Sessions**: Creates new DB session per update (prevents stale data)
- **Auto-Reconnect**: Browser reconnects automatically on disconnect
- **Disconnect Detection**: Stops streaming if client disconnects

**Client-Side Example:**
```javascript
const eventSource = new EventSource('/api/downloads/manager/events');

eventSource.addEventListener('update', (event) => {
    const data = JSON.parse(event.data);
    console.log(`${data.downloads.length} active downloads`);
    data.downloads.forEach(d => {
        updateProgressBar(d.id, d.progress.percent);
    });
});

eventSource.onerror = (error) => {
    console.error('SSE error:', error);
    // Browser will auto-reconnect
};
```

**Use Cases:**
- **Real-Time Progress**: Live progress bars without polling
- **Download Manager UI**: Auto-updating download list
- **Status Dashboard**: Monitor downloads without manual refresh

**Performance:**
- **Efficient**: Only sends updates for active downloads
- **Lightweight**: 2-second interval prevents overwhelming browser
- **Disconnect Handling**: Stops streaming to save resources

---

## Get Providers Health

**Endpoint:** `GET /api/downloads/manager/health`

**Description:** Get health status of all download providers.

**Query Parameters:** None

**Response:**
```json
{
    "providers": [
        {
            "provider": "soulseek",
            "provider_name": "slskd",
            "is_healthy": true,
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "last_successful_sync": "2025-12-15T10:00:00Z",
            "seconds_since_last_sync": 15,
            "seconds_until_recovery_attempt": null,
            "error_message": null,
            "has_successful_connection": true
        }
    ],
    "overall_healthy": true
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 328-410

@router.get("/health", response_model=ProvidersHealthResponse)
async def get_providers_health(
    request: Request,
) -> ProvidersHealthResponse:
    """Get health status of all download providers.

    Returns circuit breaker status for each provider, which indicates
    if the provider is reachable and functioning properly.

    Hey future me – this endpoint reads health from app.state where
    the StatusSyncWorker stores its circuit breaker state. If no
    worker is running, we try a direct ping to slskd.
    """
```

**Provider Health Fields:**
- `provider` (string): Provider ID (`soulseek`)
- `provider_name` (string): Display name (`slskd`)
- `is_healthy` (boolean): Whether provider is operational
- `circuit_state` (string | null): Circuit breaker state (`closed`, `open`, `half_open`)
- `consecutive_failures` (integer): Recent failure count
- `last_successful_sync` (string | null): ISO timestamp of last successful sync
- `seconds_since_last_sync` (integer | null): Seconds since last sync
- `seconds_until_recovery_attempt` (integer | null): Seconds until retry (if circuit open)
- `error_message` (string | null): Error details if unhealthy
- `has_successful_connection` (boolean): Whether provider ever connected successfully

**Circuit Breaker States:**
- **CLOSED** (healthy): Provider operational, requests pass through
- **OPEN** (failing): Too many failures, requests blocked
- **HALF_OPEN** (testing): Allowing test requests to check recovery

**Health Check Sources:**
1. **StatusSyncWorker** (preferred): Reads circuit breaker state from `app.state`
2. **Direct Ping** (fallback): If worker not running, directly pings slskd

**Use Cases:**
- **Provider Status UI**: Show which providers are operational
- **Debugging**: Identify provider connection issues
- **Circuit Breaker Monitoring**: Track provider reliability

**Response Fields:**
- `providers` (array): Health status for each provider
- `overall_healthy` (boolean): True if ALL providers healthy

---

## Active Downloads List (HTMX)

**Endpoint:** `GET /api/downloads/manager/htmx/active-list`

**Description:** HTMX endpoint for server-rendered active downloads list.

**Query Parameters:** None

**Response:** HTML partial

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 418-438

@router.get("/htmx/active-list", response_class=HTMLResponse)
async def htmx_active_downloads_list(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render active downloads list partial.

    Use with hx-get for auto-refreshing download list:
    ```html
    <div hx-get="/api/downloads/manager/htmx/active-list"
         hx-trigger="every 3s"
         hx-swap="innerHTML">
    </div>
    ```
    """
```

**HTMX Integration:**
```html
<div hx-get="/api/downloads/manager/htmx/active-list"
     hx-trigger="every 3s"
     hx-swap="innerHTML">
    <!-- Server-rendered download list updated every 3 seconds -->
</div>
```

**Use Cases:**
- **Download Manager UI**: Auto-refreshing download list
- **Server-Rendered**: No JavaScript needed for updates
- **HTMX Pattern**: Server-driven progressive enhancement

---

## Stats Bar (HTMX)

**Endpoint:** `GET /api/downloads/manager/htmx/stats-bar`

**Description:** HTMX endpoint for queue statistics bar.

**Query Parameters:** None

**Response:** HTML partial with stats summary

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 441-457

@router.get("/htmx/stats-bar", response_class=HTMLResponse)
async def htmx_stats_bar(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render queue stats bar partial.

    Displays summary like: "15 waiting │ 3 pending │ 2 downloading"
    """
```

**Example Output:**
```
15 waiting │ 3 pending │ 2 downloading │ 1 stalled
```

**HTMX Integration:**
```html
<div hx-get="/api/downloads/manager/htmx/stats-bar"
     hx-trigger="every 5s"
     hx-swap="innerHTML">
    <!-- Auto-updating stats bar -->
</div>
```

---

## Provider Health Widget (HTMX)

**Endpoint:** `GET /api/downloads/manager/htmx/provider-health`

**Description:** HTMX endpoint for provider health widget.

**Query Parameters:** None

**Response:** HTML partial with provider status indicators

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 460-482

@router.get("/htmx/provider-health", response_class=HTMLResponse)
async def htmx_provider_health(
    request: Request,
) -> HTMLResponse:
    """HTMX endpoint: Render provider health widget partial.

    Shows connection status for slskd and other download providers.
    Updates every 10 seconds via hx-trigger.
    """
```

**HTMX Integration:**
```html
<div hx-get="/api/downloads/manager/htmx/provider-health"
     hx-trigger="every 10s"
     hx-swap="innerHTML">
    <!-- Provider health indicators -->
</div>
```

---

## Download Center Page

**Endpoint:** `GET /api/downloads/manager/center`

**Description:** Render the unified Download Center page.

**Query Parameters:** None

**Response:** Full HTML page

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 540-566

@router.get("/center", response_class=HTMLResponse)
async def download_center_page(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """Render the new unified Download Center page.

    This is the main page for managing downloads with a professional UI.
    Combines queue, history, and failed downloads in one view.
    """
```

**Page Sections:**
- **Queue Tab**: Active downloads (waiting, pending, downloading)
- **History Tab**: Completed downloads (last 7/30 days)
- **Failed Tab**: Failed downloads with retry option

**Use Cases:**
- **Download Manager**: Main download management UI
- **Unified View**: Single page for all download statuses

---

## Download Center Queue (HTMX)

**Endpoint:** `GET /api/downloads/manager/center/htmx/queue`

**Description:** HTMX endpoint for Download Center queue tab.

**Query Parameters:**
- `status` (string, optional): Filter by status
- `provider` (string, optional): Filter by provider

**Response:** HTML partial

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 569-590

@router.get("/center/htmx/queue", response_class=HTMLResponse)
async def htmx_download_center_queue(
    request: Request,
    status: str | None = None,
    provider: str | None = None,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render queue list for Download Center.

    Supports filtering by status and provider.
    """
```

**Filtering:**
- **Status**: `waiting`, `pending`, `downloading`, etc.
- **Provider**: `soulseek`, `spotify`, etc.

---

## Download Center History (HTMX)

**Endpoint:** `GET /api/downloads/manager/center/htmx/history`

**Description:** HTMX endpoint for Download Center history tab.

**Query Parameters:**
- `days` (integer, optional): Days of history to show (default: 7)

**Response:** HTML partial

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 593-612

@router.get("/center/htmx/history", response_class=HTMLResponse)
async def htmx_download_center_history(
    request: Request,
    days: int = 7,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render history list for Download Center.

    Shows completed downloads from the last N days (default: 7).
    """
```

**History Ranges:**
- **7 days** (default)
- **30 days**
- **90 days** (custom)

---

## Download Center Failed (HTMX)

**Endpoint:** `GET /api/downloads/manager/center/htmx/failed`

**Description:** HTMX endpoint for Download Center failed tab.

**Query Parameters:** None

**Response:** HTML partial with failed downloads and retry buttons

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 615-631

@router.get("/center/htmx/failed", response_class=HTMLResponse)
async def htmx_download_center_failed(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render failed downloads for Download Center.

    Shows downloads that failed with retry info and retry option.
    """
```

---

## Retry All Failed Downloads

**Endpoint:** `POST /api/downloads/manager/retry-all-failed`

**Description:** Retry all failed downloads.

**Request Body:** None

**Response:**
```json
{
    "retried": 5,
    "message": "Queued 5 downloads for retry"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 645-668

@router.post("/retry-all-failed", response_model=RetryAllResponse)
async def retry_all_failed_downloads(
    session: AsyncSession = Depends(get_db_session),
) -> RetryAllResponse:
    """Retry all failed downloads.

    Moves all failed downloads back to WAITING status for re-processing.
    """
```

**Behavior:**
- **Status Change**: FAILED → WAITING
- **Error Cleared**: Removes error messages
- **Re-Queued**: Downloads will be processed again

**Use Cases:**
- **Bulk Retry**: Retry all failures after fixing issue
- **Network Recovery**: Retry after network restored

---

## Clear Failed Downloads

**Endpoint:** `DELETE /api/downloads/manager/clear-failed`

**Description:** Delete all failed downloads permanently.

**Request Body:** None

**Response:**
```json
{
    "deleted": 5,
    "message": "Removed 5 failed downloads"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 671-688

@router.delete("/clear-failed")
async def clear_all_failed_downloads(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete all failed downloads permanently."""
```

**Behavior:**
- **Permanent Deletion**: Removes from database
- **Not Reversible**: Cannot recover deleted downloads

---

## Clear Old History

**Endpoint:** `DELETE /api/downloads/manager/history/clear`

**Description:** Clear completed downloads older than N days.

**Query Parameters:**
- `days` (integer, optional): Age threshold in days (default: 7)

**Request Body:** None

**Response:**
```json
{
    "deleted": 120,
    "message": "Removed 120 old downloads"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 691-717

@router.delete("/history/clear")
async def clear_old_history(
    days: int = 7,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Clear completed downloads older than N days."""
```

**Use Cases:**
- **Database Cleanup**: Remove old completed downloads
- **Storage Management**: Free database space

---

## Export Downloads

**Endpoint:** `GET /api/downloads/manager/export`

**Description:** Export downloads to JSON or CSV format.

**Query Parameters:**
- `format` (string, optional): Export format (`json` or `csv`, default: `json`)
- `status` (string, optional): Filter by status

**Response (JSON):**
```json
{
    "count": 150,
    "exported_at": "2025-12-15T10:00:00Z",
    "downloads": [...]
}
```

**Response (CSV):** CSV file download

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/download_manager.py
# Lines 725-861

@router.get("/export")
async def export_downloads(
    format: str = "json",
    status: str | None = None,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> dict:
    """Export downloads to JSON or CSV format.

    Args:
        format: Export format ('json' or 'csv')
        status: Filter by status (optional)
    """
```

**CSV Columns:**
- ID, Title, Artist, Album, Status, Provider, Progress %, Size, Created At, Error

**Use Cases:**
- **Reporting**: Generate download reports
- **Backup**: Export download history
- **Analysis**: Analyze download patterns

---

## Summary

**Total Endpoints Documented:** 18

**Endpoint Categories:**
1. **Core API**: 3 endpoints (active downloads, stats, events)
2. **Health**: 1 endpoint (provider health)
3. **HTMX Partials**: 7 endpoints (list, stats bar, health widget, queue, history, failed, mini health)
4. **Pages**: 1 endpoint (download center)
5. **Actions**: 3 endpoints (retry failed, clear failed, clear history)
6. **Export**: 1 endpoint (export downloads)

**Key Features:**
- **Unified Interface**: Single API for all download providers
- **Real-Time Updates**: SSE for live progress
- **Circuit Breaker**: Provider health monitoring
- **HTMX Integration**: Server-rendered UI components
- **Queue Management**: Filter, retry, clear operations
- **Export**: JSON/CSV download history

**Module Stats:**
- **Source File**: `download_manager.py` (861 lines)
- **Endpoints**: 18
- **Code Validation**: 100%

**Providers:**
- **slskd** (Soulseek): Current provider
- **Future**: Spotify Direct Download, Deezer, etc.

**Download States:**
- WAITING, PENDING, QUEUED, DOWNLOADING, PAUSED, STALLED, COMPLETED, FAILED

**Use Cases:**
- **Download Management**: Track downloads across providers
- **Progress Monitoring**: Real-time progress bars
- **Provider Health**: Monitor service connectivity
- **History Management**: View/export download history
- **Bulk Operations**: Retry/clear multiple downloads
