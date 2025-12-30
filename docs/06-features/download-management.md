# Download Management

**Category:** Features  
**Last Updated:** 2025-11-25  
**Related Docs:** [API Reference: Downloads](../03-api-reference/downloads.md) | [Auto-Import](./auto-import.md)

---

## Overview

Download Management controls all downloads from Soulseek via slskd service. Provides complete queue management with prioritization, pause/resume functionality, and batch operations.

---

## Features

### Download Queue

- **Central Queue:** All downloads managed in single queue
- **Prioritization:** Downloads can have priority levels (higher = faster)
- **Parallel Downloads:** Configurable concurrent download count

**Endpoint:** `GET /api/downloads/status`

---

### Individual Downloads

- **Status Tracking:** Real-time progress display for each download
- **Pause/Resume:** Pause and resume individual downloads
- **Cancel:** Abort downloads
- **Retry:** Retry failed downloads

---

### Batch Operations

- **Batch Download:** Add multiple tracks to queue simultaneously
- **Batch Actions:** Pause, resume, or cancel multiple downloads at once

---

### Queue Control

- **Global Pause:** Pause all downloads
- **Global Resume:** Resume all downloads
- **Queue Status:** Overview of active, queued, and completed downloads

---

## Download Status

| Status | Description |
|--------|-------------|
| `pending` | Initial status, before queuing |
| `queued` | In queue, waiting for processing |
| `downloading` | Download currently active |
| `completed` | Successfully downloaded |
| `failed` | Failed (can be retried) |
| `cancelled` | Cancelled by user |

⚠️ **Note:** `paused` is not a separate enum value. Paused downloads reset to `queued`.

---

## Usage (Web UI)

### View Download Queue

1. Navigate to **Downloads** in main menu
2. Queue shows all active and waiting downloads
3. Progress bars show current status

---

### Prioritize Download

1. Find download in queue
2. Click priority icon
3. Set priority value

**Priority Values:**
- `0` - P0 (Highest priority)
- `1` - P1 (Medium priority)
- `2` - P2 (Lowest priority)

---

### Retry Failed Downloads

1. Filter by status "Failed"
2. Click retry icon
3. Download re-added to queue

---

## API Endpoints

### GET `/api/downloads/`

List all downloads.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by status (queued, downloading, completed, failed) |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 20 | Results per page (max 100) |

**Response:**
```json
{
  "downloads": [
    {
      "id": "download-uuid",
      "track_id": "track-uuid",
      "status": "downloading",
      "priority": 0,
      "progress_percent": 45.5,
      "source_url": "slskd://...",
      "target_path": "/music/Artist/Album/track.mp3",
      "error_message": null,
      "started_at": "2025-01-15T10:00:00Z",
      "completed_at": null,
      "created_at": "2025-01-15T09:55:00Z",
      "updated_at": "2025-01-15T10:00:30Z"
    }
  ],
  "total": 42,
  "status": null,
  "skip": 0,
  "limit": 20
}
```

---

### GET `/api/downloads/status`

Get download queue status.

**Response:**
```json
{
  "paused": false,
  "max_concurrent_downloads": 5,
  "active_downloads": 3,
  "queued_downloads": 15,
  "total_jobs": 42,
  "completed": 20,
  "failed": 2,
  "cancelled": 2
}
```

---

### GET `/api/downloads/{download_id}`

Get single download status.

---

### POST `/api/downloads/{download_id}/pause`

Pause individual download.

---

### POST `/api/downloads/{download_id}/resume`

Resume individual download.

---

### POST `/api/downloads/{download_id}/cancel`

Cancel individual download.

---

### POST `/api/downloads/{download_id}/retry`

Retry failed download.

---

### POST `/api/downloads/pause-all`

Pause all downloads.

---

### POST `/api/downloads/resume-all`

Resume all downloads.

---

## Priority System

**How Priority Works:**
- Lower number = Higher priority
- P0 (0) downloads processed before P1 (1) downloads
- Same priority → FIFO (first in, first out)

**Example:**
```
Queue:
1. Track A (P0) ← Downloads first
2. Track B (P1)
3. Track C (P0) ← Downloads second
4. Track D (P2) ← Downloads last
```

---

## Troubleshooting

### Downloads Stuck in "Queued"

**Causes:**
1. **Global pause active:** Resume queue
2. **Max concurrent reached:** Wait for active downloads to finish
3. **slskd service down:** Check slskd status

**Solution:** Check `/api/downloads/status` for `paused` flag.

---

### Download Fails Immediately

**Causes:**
1. **File not found on Soulseek:** Source user offline
2. **Network error:** Check slskd connectivity
3. **Permission error:** Check target path permissions

**Solution:** Retry later or choose different source.

---

### Progress Stuck at 0%

**Causes:**
1. **Slow source:** Large queue on source user
2. **Firewall blocking:** Check slskd network config
3. **Source cancelled:** Source user rejected transfer

**Solution:** Wait or cancel and choose different source.

---

## Related Documentation

- **[API Reference: Downloads](../03-api-reference/downloads.md)** - Full endpoint documentation
- **[Auto-Import](./auto-import.md)** - Automatic organization after download
- **[Settings](./settings.md)** - Download configuration

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
