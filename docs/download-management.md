# Download Management System

## Overview

The SoulSpot Bridge download management system provides a robust, priority-based queue for managing music downloads from Soulseek. It includes features for retry logic, concurrent download limits, pause/resume functionality, and batch operations.

## Features

### 1. Priority-Based Queue

Downloads can be assigned priorities to control the order of processing:

- **P0 (Priority 0)**: Highest priority - processed first
- **P1 (Priority 1)**: Medium priority
- **P2 (Priority 2)**: Low priority

**Example:**
```python
from soulspot.domain.entities import Download, DownloadStatus
from soulspot.domain.value_objects import DownloadId, TrackId

download = Download(
    id=DownloadId.from_string("some-uuid"),
    track_id=TrackId.from_string("track-uuid"),
    priority=0  # P0 - highest priority
)

# Update priority
download.update_priority(1)  # Change to P1
```

**API Endpoint:**
```bash
# Update download priority
POST /api/downloads/{download_id}/priority
Content-Type: application/json

{
  "priority": 0
}
```

### 2. Retry Logic with Exponential Backoff

Failed downloads are automatically retried with exponential backoff:

- **Retry 1**: After 1 second
- **Retry 2**: After 2 seconds
- **Retry 3**: After 4 seconds

**Configuration:**
```python
from soulspot.application.workers.job_queue import JobQueue

job_queue = JobQueue(max_concurrent_jobs=3)

# Enqueue job with custom retry settings
job_id = await job_queue.enqueue(
    job_type=JobType.DOWNLOAD,
    payload={"track_id": "track-123"},
    max_retries=3,  # Maximum 3 retry attempts
    priority=0
)
```

**Environment Variable:**
```bash
DOWNLOAD__DEFAULT_MAX_RETRIES=3
```

### 3. Concurrent Download Limits

Control how many downloads run simultaneously to manage bandwidth and system resources.

**Configuration:**
```python
from soulspot.config import Settings

settings = Settings(
    download={
        "max_concurrent_downloads": 2,  # Recommended: 1-3
    }
)
```

**Environment Variable:**
```bash
DOWNLOAD__MAX_CONCURRENT_DOWNLOADS=2
```

**Runtime Adjustment:**
```python
job_queue.set_max_concurrent_jobs(2)
```

### 4. Pause/Resume API

#### Global Pause/Resume

Pause or resume all download processing:

```bash
# Pause all downloads
POST /api/downloads/pause

# Response
{
  "message": "Download queue paused successfully",
  "status": "paused"
}

# Resume downloads
POST /api/downloads/resume

# Response
{
  "message": "Download queue resumed successfully",
  "status": "active"
}

# Get queue status
GET /api/downloads/status

# Response
{
  "paused": false,
  "max_concurrent_downloads": 3,
  "active_downloads": 2,
  "queued_downloads": 5,
  "total_jobs": 10,
  "completed": 2,
  "failed": 1,
  "cancelled": 0
}
```

#### Individual Download Pause/Resume

Pause or resume specific downloads:

```bash
# Pause a specific download
POST /api/downloads/{download_id}/pause

# Response
{
  "message": "Download paused",
  "download_id": "abc-123",
  "status": "queued"
}

# Resume a paused download
POST /api/downloads/{download_id}/resume

# Response
{
  "message": "Download resumed",
  "download_id": "abc-123",
  "status": "downloading"
}
```

**Python API:**
```python
# Pause download
download.pause()  # Changes status to QUEUED

# Resume download
download.resume()  # Changes status back to DOWNLOADING
```

### 5. Batch Operations

#### Batch Download

Enqueue multiple tracks for download at once:

```bash
POST /api/downloads/batch
Content-Type: application/json

{
  "track_ids": [
    "track-uuid-1",
    "track-uuid-2",
    "track-uuid-3"
  ],
  "priority": 1
}

# Response
{
  "message": "Batch download initiated for 3 tracks",
  "job_ids": ["job-1", "job-2", "job-3"],
  "total_tracks": 3
}
```

#### Batch Actions

Perform actions on multiple downloads:

```bash
POST /api/downloads/batch-action
Content-Type: application/json

{
  "download_ids": ["download-1", "download-2", "download-3"],
  "action": "pause",  # or "resume", "cancel", "priority"
  "priority": 0  # Required only for "priority" action
}

# Response
{
  "message": "Batch action 'pause' completed",
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {"id": "download-1", "status": "success"},
    {"id": "download-2", "status": "success"},
    {"id": "download-3", "status": "success"}
  ],
  "errors": []
}
```

## Database Schema

The download entity includes a priority field:

```sql
CREATE TABLE downloads (
    id TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,  -- 0=P0 (high), 1=P1 (medium), 2=P2 (low)
    target_path TEXT,
    source_url TEXT,
    progress_percent REAL DEFAULT 0.0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_downloads_priority_created ON downloads (priority, created_at);
```

**Migration:** `alembic/versions/46d1c2c2f85b_add_priority_field_to_downloads.py`

## API Reference

### Download Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/downloads` | GET | List all downloads (with pagination and filtering) |
| `/api/downloads/{download_id}` | GET | Get download status |
| `/api/downloads/{download_id}/cancel` | POST | Cancel a download |
| `/api/downloads/{download_id}/retry` | POST | Retry a failed download |
| `/api/downloads/{download_id}/priority` | POST | Update download priority |
| `/api/downloads/{download_id}/pause` | POST | Pause a download |
| `/api/downloads/{download_id}/resume` | POST | Resume a paused download |
| `/api/downloads/pause` | POST | Pause all downloads |
| `/api/downloads/resume` | POST | Resume all downloads |
| `/api/downloads/status` | GET | Get queue status |
| `/api/downloads/batch` | POST | Batch download multiple tracks |
| `/api/downloads/batch-action` | POST | Perform batch operations |

### Query Parameters

**List Downloads** (`GET /api/downloads`):
- `status`: Filter by status (queued, downloading, completed, failed)
- `skip`: Number of downloads to skip (pagination)
- `limit`: Number of downloads to return (max 100)

## Usage Examples

### Example 1: High-Priority Download

```python
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.domain.value_objects import TrackId

# Enqueue high-priority download
job_id = await download_worker.enqueue_download(
    track_id=TrackId.from_string("track-uuid"),
    priority=0,  # P0 - highest priority
    max_retries=3
)
```

### Example 2: Batch Download with Priority

```bash
curl -X POST http://localhost:8000/api/downloads/batch \
  -H "Content-Type: application/json" \
  -d '{
    "track_ids": [
      "550e8400-e29b-41d4-a716-446655440000",
      "550e8400-e29b-41d4-a716-446655440001",
      "550e8400-e29b-41d4-a716-446655440002"
    ],
    "priority": 0
  }'
```

### Example 3: Pause Queue During Maintenance

```bash
# Pause all downloads
curl -X POST http://localhost:8000/api/downloads/pause

# Perform maintenance...

# Resume downloads
curl -X POST http://localhost:8000/api/downloads/resume
```

### Example 4: Monitor Queue Status

```bash
curl http://localhost:8000/api/downloads/status

# Response
{
  "paused": false,
  "max_concurrent_downloads": 3,
  "active_downloads": 2,
  "queued_downloads": 5,
  "total_jobs": 10,
  "completed": 2,
  "failed": 1,
  "cancelled": 0
}
```

## Configuration Reference

### Environment Variables

```bash
# Download Queue Configuration
DOWNLOAD__MAX_CONCURRENT_DOWNLOADS=3      # Maximum concurrent downloads (1-10)
DOWNLOAD__DEFAULT_MAX_RETRIES=3           # Default retry attempts (1-10)
DOWNLOAD__ENABLE_PRIORITY_QUEUE=true     # Enable priority-based queue
```

### Settings Object

```python
from soulspot.config import Settings

settings = Settings(
    download={
        "max_concurrent_downloads": 3,
        "default_max_retries": 3,
        "enable_priority_queue": True,
    }
)
```

## Best Practices

1. **Priority Management**
   - Use P0 (priority=0) sparingly for urgent downloads
   - Most downloads should be P1 (priority=1)
   - Batch operations should use P2 (priority=2)

2. **Concurrent Downloads**
   - Recommended: 2-3 concurrent downloads
   - Higher values may impact network performance
   - Consider available bandwidth and system resources

3. **Retry Strategy**
   - Default of 3 retries is recommended
   - For flaky sources, consider increasing to 5
   - Monitor failed downloads and adjust accordingly

4. **Pause/Resume**
   - Use global pause during system maintenance
   - Use individual pause for problematic downloads
   - Monitor queue status to ensure proper operation

5. **Batch Operations**
   - Batch similar priority downloads together
   - Use lower priority for large batch imports
   - Monitor queue depth to avoid overwhelming the system

## Troubleshooting

### Downloads Not Processing

1. Check if queue is paused:
   ```bash
   curl http://localhost:8000/api/downloads/status
   ```

2. Verify concurrent download limit:
   ```python
   job_queue.get_max_concurrent_jobs()
   ```

3. Check for stuck downloads:
   ```bash
   curl 'http://localhost:8000/api/downloads?status=downloading'
   ```

### High Failure Rate

1. Check error messages:
   ```bash
   curl 'http://localhost:8000/api/downloads?status=failed'
   ```

2. Increase retry count:
   ```bash
   export DOWNLOAD__DEFAULT_MAX_RETRIES=5
   ```

3. Reduce concurrent downloads to improve stability:
   ```bash
   export DOWNLOAD__MAX_CONCURRENT_DOWNLOADS=2
   ```

### Queue Congestion

1. Check queue depth:
   ```bash
   curl http://localhost:8000/api/downloads/status
   ```

2. Increase concurrent downloads (if resources allow):
   ```python
   job_queue.set_max_concurrent_jobs(5)
   ```

3. Cancel stale downloads:
   ```bash
   # Cancel specific download
   curl -X POST http://localhost:8000/api/downloads/{download_id}/cancel
   ```

## Testing

Comprehensive test suite validates all features:

```bash
# Run download management tests
pytest tests/integration/test_download_management_features.py -v

# Run all download-related tests
pytest tests/ -k "download" -v

# Run with coverage
pytest tests/ -k "download" --cov=src/soulspot --cov-report=term
```

## Architecture

```
┌─────────────────┐
│   API Router    │
│  (downloads.py) │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Download Worker │
│  (Orchestrator) │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   Job Queue     │
│ (Priority Queue)│
│  - Retry Logic  │
│  - Concurrency  │
│  - Pause/Resume │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Use Case Layer │
│ (Business Logic)│
└────────┬────────┘
         │
         v
┌─────────────────┐
│   Repositories  │
│   (Persistence) │
└─────────────────┘
```

## Related Documentation

- [API Documentation](./api.md)
- [Database Migrations](../alembic/README.md)
- [Configuration Guide](./configuration.md)
- [Development Guide](./development.md)
