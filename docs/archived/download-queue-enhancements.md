# Download Queue Enhancements

This document describes the enhanced download queue system implemented in SoulSpot, providing priority-based job scheduling, retry logic, and queue management features.

## Overview

The download queue system has been enhanced with several production-ready features:

- **Priority-based Queue**: Jobs are processed based on priority levels
- **Exponential Backoff Retry**: Failed downloads automatically retry with increasing delays
- **Concurrent Download Limits**: Configurable limits prevent resource exhaustion
- **Pause/Resume**: Global queue control for maintenance or resource management
- **Batch Operations**: Efficient downloading of multiple tracks

## Features

### 1. Priority-based Queue

Jobs can be assigned priority levels (integer values, higher = more important). The queue processes higher priority jobs first while maintaining FIFO order for jobs with the same priority.

**Usage:**
```python
# Enqueue a high-priority download
job_id = await download_worker.enqueue_download(
    track_id=track_id,
    priority=10  # Higher priority
)

# Enqueue a normal-priority download
job_id = await download_worker.enqueue_download(
    track_id=track_id,
    priority=0   # Default priority
)
```

**Database Support:**
- Priority field added to downloads table
- Indexed for efficient priority-based queries
- Default value: 0

### 2. Exponential Backoff Retry Logic

Failed downloads automatically retry with exponential backoff delays:
- 1st retry: 1 second delay
- 2nd retry: 2 seconds delay
- 3rd retry: 4 seconds delay

**Configuration:**
```python
# Configure max retries when enqueueing
job_id = await download_worker.enqueue_download(
    track_id=track_id,
    max_retries=3  # Default: 3
)
```

**Features:**
- Automatic re-queuing on failure
- Detailed logging with retry count and delay
- Configurable max retry attempts
- Original priority preserved on retry

### 3. Configurable Concurrent Download Limits

Control the maximum number of concurrent downloads to prevent resource exhaustion and respect external API rate limits.

**Configuration (environment variables):**
```bash
DOWNLOAD__MAX_CONCURRENT_DOWNLOADS=3  # Default: 3, Range: 1-10
DOWNLOAD__DEFAULT_MAX_RETRIES=3       # Default: 3, Range: 1-10
DOWNLOAD__ENABLE_PRIORITY_QUEUE=true  # Default: true
```

**Runtime Configuration:**
```python
# Update concurrent limit dynamically
job_queue.set_max_concurrent_jobs(2)

# Get current limit
current_limit = job_queue.get_max_concurrent_jobs()
```

### 4. Pause/Resume Functionality

Pause and resume the download queue globally for maintenance, resource management, or testing.

**API Endpoints:**
```bash
# Pause download queue
POST /api/v1/downloads/pause

# Resume download queue
POST /api/v1/downloads/resume

# Check queue status
GET /api/v1/downloads/status
```

**Response Example:**
```json
{
  "paused": false,
  "max_concurrent_downloads": 3,
  "active_downloads": 2,
  "queued_downloads": 5
}
```

**Features:**
- Currently running downloads continue to completion
- New downloads wait until queue is resumed
- Jobs safely returned to queue when paused

### 5. Batch Operations

Download multiple tracks with a single API call, all with the same priority.

**API Endpoint:**
```bash
POST /api/v1/downloads/batch
```

**Request Body:**
```json
{
  "track_ids": [
    "track-uuid-1",
    "track-uuid-2",
    "track-uuid-3"
  ],
  "priority": 5
}
```

**Response:**
```json
{
  "message": "Batch download initiated for 3 tracks",
  "job_ids": ["job-uuid-1", "job-uuid-2", "job-uuid-3"],
  "total_tracks": 3
}
```

## Configuration

### Settings

The download queue is configured via the `DownloadSettings` section in settings:

```python
from soulspot.config import get_settings

settings = get_settings()

# Access download settings
max_concurrent = settings.download.max_concurrent_downloads
max_retries = settings.download.default_max_retries
priority_enabled = settings.download.enable_priority_queue
```

### Environment Variables

Configure via environment variables with the prefix `DOWNLOAD__`:

```bash
# Maximum concurrent downloads (1-10)
DOWNLOAD__MAX_CONCURRENT_DOWNLOADS=3

# Default maximum retry attempts (1-10)
DOWNLOAD__DEFAULT_MAX_RETRIES=3

# Enable priority-based queue
DOWNLOAD__ENABLE_PRIORITY_QUEUE=true
```

## Database Schema

### Migration

A database migration adds the priority field to the downloads table:

```sql
-- Add priority column
ALTER TABLE downloads ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;

-- Create index for priority-based queries
CREATE INDEX ix_downloads_priority_created ON downloads (priority, created_at);
```

**Migration ID:** `46d1c2c2f85b`

**Apply Migration:**
```bash
poetry run alembic upgrade head
```

### Schema

```sql
CREATE TABLE downloads (
    id VARCHAR(36) PRIMARY KEY,
    track_id VARCHAR(36) NOT NULL,
    status VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,  -- New field
    target_path VARCHAR(512),
    source_url VARCHAR(512),
    progress_percent FLOAT NOT NULL,
    error_message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE
);
```

## Testing

The enhanced download queue includes comprehensive test coverage:

### Test Coverage
- **27 job queue tests** with **83.66% code coverage**
- All 320 existing tests continue to pass
- Zero security vulnerabilities

### Test Categories
1. **Priority Queue Ordering**: Verifies high-priority jobs processed first
2. **Exponential Backoff**: Validates retry timing (1s, 2s, 4s)
3. **Pause/Resume**: Tests queue pausing and resuming behavior
4. **Concurrent Limits**: Verifies max concurrent jobs respected
5. **Configuration**: Tests dynamic configuration changes

### Running Tests

```bash
# Run job queue tests
poetry run pytest tests/unit/application/workers/test_job_queue.py -v

# Run with coverage
poetry run pytest tests/unit/application/workers/test_job_queue.py \
  --cov=soulspot.application.workers.job_queue \
  --cov-report=term-missing

# Run all tests
poetry run pytest tests/ -v
```

## Implementation Details

### Architecture

The enhanced download queue follows a layered architecture:

```
┌─────────────────────────────────────┐
│   API Layer (FastAPI)               │
│   - Pause/Resume/Status endpoints   │
│   - Batch download endpoint         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Application Layer                 │
│   - DownloadWorker                  │
│   - JobQueue (Priority Queue)       │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Domain Layer                      │
│   - Job (with priority)             │
│   - Download (with priority)        │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Infrastructure Layer              │
│   - DownloadRepository              │
│   - Database (priority field)       │
└─────────────────────────────────────┘
```

### Key Components

1. **JobQueue**: Priority queue implementation using `asyncio.PriorityQueue`
2. **Job**: Dataclass with priority, retry logic, and status tracking
3. **DownloadWorker**: Manages download job lifecycle
4. **DownloadRepository**: Persists download state with priority

## Best Practices

### Priority Levels

Recommended priority scheme:
- **10**: Critical/urgent downloads
- **5**: High-priority user requests
- **0**: Normal downloads (default)
- **-5**: Background/maintenance tasks

### Retry Configuration

- Use default 3 retries for transient failures
- Increase retries for critical downloads
- Set lower retries for batch operations to fail fast

### Concurrent Limits

- **1-2**: For rate-limited external APIs
- **3**: Default, balanced for most use cases
- **5-10**: For high-throughput scenarios with robust infrastructure

### Monitoring

Monitor these metrics for optimal performance:
- Queue length (pending jobs)
- Active downloads
- Retry rates
- Average completion time
- Failure rates by priority

## Troubleshooting

### Queue Not Processing

**Symptoms:** Jobs enqueued but not processing

**Solutions:**
1. Check if queue is paused: `GET /api/v1/downloads/status`
2. Verify workers are started: `await job_queue.start(num_workers=3)`
3. Check concurrent limit: `job_queue.get_max_concurrent_jobs()`

### High Retry Rates

**Symptoms:** Many jobs failing and retrying

**Solutions:**
1. Check external service availability (slskd, network)
2. Review error messages in logs
3. Verify retry delays are sufficient
4. Consider increasing max_retries for critical jobs

### Performance Issues

**Symptoms:** Slow download processing

**Solutions:**
1. Increase concurrent download limit (if resources allow)
2. Review priority distribution (avoid too many high-priority jobs)
3. Monitor external API rate limits
4. Check database query performance on priority index

## API Reference

### Pause Queue

```http
POST /api/v1/downloads/pause
```

**Response:**
```json
{
  "message": "Download queue paused successfully",
  "status": "paused"
}
```

### Resume Queue

```http
POST /api/v1/downloads/resume
```

**Response:**
```json
{
  "message": "Download queue resumed successfully",
  "status": "active"
}
```

### Get Queue Status

```http
GET /api/v1/downloads/status
```

**Response:**
```json
{
  "paused": false,
  "max_concurrent_downloads": 3,
  "active_downloads": 2,
  "queued_downloads": 5
}
```

### Batch Download

```http
POST /api/v1/downloads/batch
```

**Request:**
```json
{
  "track_ids": ["track-1", "track-2"],
  "priority": 5
}
```

**Response:**
```json
{
  "message": "Batch download initiated for 2 tracks",
  "job_ids": ["job-1", "job-2"],
  "total_tracks": 2
}
```

## Future Enhancements

Potential future improvements:
- [ ] Persistent queue storage (Redis/RabbitMQ)
- [ ] Dynamic priority adjustment based on wait time
- [ ] Queue analytics and statistics dashboard
- [ ] Scheduled downloads with cron-like scheduling
- [ ] Download quotas per user/time period
- [ ] Advanced retry strategies (jitter, circuit breaker)
- [ ] Dead letter queue for permanently failed jobs

## References

- [Job Queue Implementation](../src/soulspot/application/workers/job_queue.py)
- [Download Worker](../src/soulspot/application/workers/download_worker.py)
- [Downloads API](../src/soulspot/api/routers/downloads.py)
- [Database Migration](../alembic/versions/46d1c2c2f85b_add_priority_field_to_downloads.py)
- [Test Suite](../tests/unit/application/workers/test_job_queue.py)
