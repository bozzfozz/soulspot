# Logging Standards

**Version:** 1.0  
**Last Updated:** 2025-12-30  
**Applies To:** All SoulSpot modules (Workers, Services, API, Infrastructure)

---

## Purpose

This document defines logging standards for SoulSpot to ensure:
- **Consistency:** All modules log in the same format
- **Debuggability:** Logs contain enough context for troubleshooting
- **Performance:** Structured logging for efficient filtering
- **Maintainability:** Clear patterns for future developers

---

## Quick Reference

```python
# 1. Import logger
import logging
logger = logging.getLogger(__name__)  # ALWAYS use __name__!

# 2. Log with structured fields
logger.info("operation.complete", extra={
    "operation": "spotify_sync",
    "duration_ms": 1234,
    "items_processed": 50
})

# 3. Exception logging
try:
    await risky_operation()
except Exception as e:
    logger.error(
        "operation.failed",
        extra={"operation": "download", "track_id": track.id},
        exc_info=True  # CRITICAL: Auto-includes traceback!
    )
    raise  # Re-raise if needed
```

---

## Logger Initialization

### Rule: Always Use `__name__`

```python
import logging
logger = logging.getLogger(__name__)  # ✅ CORRECT
```

**Why `__name__`?**
- Automatically uses module path (e.g., `soulspot.application.workers.spotify_sync_worker`)
- Enables hierarchical filtering (can silence `soulspot.infrastructure.*` but keep `soulspot.application.*`)
- Makes logs searchable by module

**Anti-patterns:**
```python
logger = logging.getLogger("my_logger")  # ❌ WRONG: Not searchable
logger = logging.getLogger()            # ❌ WRONG: Uses root logger
```

---

## Log Levels

Use log levels consistently across all modules:

| Level | When to Use | Examples |
|-------|-------------|----------|
| **DEBUG** | Detailed diagnostic info (Dev only) | Variable values, loop iterations, function entry/exit |
| **INFO** | Normal operations | Worker start, sync complete, API request success |
| **WARNING** | Unexpected but recoverable | Token expired (will retry), rate limit hit, slow query |
| **ERROR** | Operation failed | Download failed, sync error, database connection lost |

### Examples

```python
# DEBUG - Detailed diagnostics
logger.debug("spotify_sync.fetching_artists", extra={"offset": 0, "limit": 50})

# INFO - Normal operation
logger.info("worker.started", extra={"worker": "spotify_sync", "interval": 60})

# WARNING - Recoverable issue
logger.warning(
    "token.expired",
    extra={"provider": "spotify", "action": "refresh_attempted"}
)

# ERROR - Operation failed
logger.error(
    "download.failed",
    extra={"track_id": track.id, "reason": "timeout"},
    exc_info=True
)
```

---

## Structured Logging Format

### Rule: Use `extra={}` for Context

All logs should include structured fields via `extra` parameter:

```python
# ✅ CORRECT: Structured logging
logger.info("sync.complete", extra={
    "operation": "spotify_sync",
    "duration_ms": 1234,
    "items_processed": 50,
    "errors": 2
})

# ❌ WRONG: String interpolation (not machine-parseable)
logger.info(f"Spotify sync complete: {count} items in {duration}ms, {errors} errors")
```

### Field Naming Convention

- **snake_case:** All field names use snake_case
- **Units in name:** Include units in field name (e.g., `duration_ms`, `size_bytes`)
- **Consistent names:** Use same field names across modules

**Common Fields:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `operation` | str | Operation name | "spotify_sync", "download" |
| `duration_ms` | int | Operation duration in milliseconds | 1234 |
| `count` | int | Number of items processed | 50 |
| `error_type` | str | Exception class name | "ConnectError" |
| `track_id` | str | Track identifier | "abc123" |
| `worker` | str | Worker name | "spotify_sync" |

---

## Exception Logging

### Rule: Always Use `exc_info=True`

When logging exceptions, **ALWAYS** include `exc_info=True` to capture the full traceback:

```python
try:
    await download_track(track_id)
except Exception as e:
    logger.error(
        "download.failed",
        extra={
            "track_id": track_id,
            "error_type": type(e).__name__,
            "error_message": str(e)
        },
        exc_info=True  # CRITICAL: Includes full traceback!
    )
    raise  # Re-raise if you want caller to handle it
```

**What `exc_info=True` does:**
- Automatically captures exception type, message, and full stack trace
- Uses our `CompactExceptionFormatter` for readable output
- No need to manually format tracebacks

**Output Example:**
```
21:30:45 │ ERROR   │ download_worker:123 │ download.failed {"track_id": "abc", "error_type": "ConnectError"}
╰─► httpx.ConnectError: All connection attempts failed
    File "download_worker.py", line 123, in _download
      response = await client.get("/api/download")
    File "httpx/_client.py", line 456, in get
      return await self.request("GET", url)
```

### Exception Context Fields

Include these fields when logging exceptions:

```python
extra={
    "operation": "download",           # What was being attempted
    "track_id": track.id,              # Entity involved
    "error_type": type(e).__name__,    # Exception class
    "retry_count": retry_count,        # How many retries attempted
    "will_retry": will_retry           # Whether retry will happen
}
```

---

## Logging Patterns

### Pattern 1: Worker Lifecycle

```python
class SpotifySyncWorker:
    async def start(self):
        logger.info(
            "worker.started",
            extra={
                "worker": "spotify_sync",
                "check_interval_seconds": self.check_interval_seconds
            }
        )
        # ... work ...
    
    async def stop(self):
        logger.info(
            "worker.stopped",
            extra={
                "worker": "spotify_sync",
                "cycles_completed": self._cycles,
                "errors_total": self._errors
            }
        )
```

### Pattern 2: Operation Timing

```python
import time

async def sync_playlists(self):
    start = time.time()
    logger.info("sync.playlists.started")
    
    try:
        # ... do work ...
        playlists = await self._fetch_playlists()
        
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "sync.playlists.completed",
            extra={
                "count": len(playlists),
                "duration_ms": duration_ms
            }
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(
            "sync.playlists.failed",
            extra={
                "duration_ms": duration_ms,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
```

### Pattern 3: Worker Health Reporting

```python
class Worker:
    def __init__(self):
        self._cycles_completed = 0
        self._errors_total = 0
        self._start_time = time.time()
    
    async def _main_loop(self):
        while self._running:
            try:
                await self._do_work()
                self._cycles_completed += 1
                
                # Log health every 10 cycles
                if self._cycles_completed % 10 == 0:
                    logger.info(
                        "worker.health",
                        extra={
                            "worker": self.__class__.__name__,
                            "cycles_completed": self._cycles_completed,
                            "errors_total": self._errors_total,
                            "uptime_seconds": int(time.time() - self._start_time)
                        }
                    )
            except Exception as e:
                self._errors_total += 1
                logger.error("worker.error", exc_info=True)
```

### Pattern 4: Slow Query Logging

```python
async def _execute_query(self, stmt, operation: str):
    start = time.time()
    result = await self.session.execute(stmt)
    duration_ms = int((time.time() - start) * 1000)
    
    # Warn if query takes >100ms
    if duration_ms > 100:
        logger.warning(
            "repository.slow_query",
            extra={
                "repository": self.__class__.__name__,
                "operation": operation,
                "duration_ms": duration_ms
            }
        )
    
    return result
```

### Pattern 5: API Request Logging

```python
@router.post("/library/scan")
async def trigger_library_scan(background_tasks: BackgroundTasks):
    logger.info(
        "api.request",
        extra={
            "endpoint": "/library/scan",
            "method": "POST"
        }
    )
    
    try:
        # ... do work ...
        return {"status": "ok"}
    except Exception as e:
        logger.error(
            "api.error",
            extra={
                "endpoint": "/library/scan",
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
```

---

## Message Naming Convention

### Format: `{module}.{action}`

Use dot-separated hierarchical names:

```python
# ✅ CORRECT
"worker.started"
"sync.playlists.completed"
"download.track.failed"
"api.library_scan.triggered"

# ❌ WRONG
"Worker started"
"Sync complete"
"Error downloading track"
```

### Common Prefixes

| Prefix | Use For | Examples |
|--------|---------|----------|
| `worker.*` | Worker lifecycle | `worker.started`, `worker.health`, `worker.stopped` |
| `sync.*` | Sync operations | `sync.playlists.started`, `sync.artists.completed` |
| `download.*` | Download operations | `download.track.queued`, `download.track.completed` |
| `api.*` | API endpoints | `api.request`, `api.error` |
| `repository.*` | Database operations | `repository.slow_query`, `repository.error` |

---

## Log Message Length

**Rule:** Keep messages concise (<80 chars)

```python
# ✅ CORRECT: Short message, context in extra
logger.info("sync.complete", extra={"count": 50, "duration_ms": 1234})

# ❌ WRONG: Long message with all details
logger.info("Spotify sync completed successfully: 50 playlists synced in 1234ms with 2 errors")
```

**Why?**
- Easier to grep/filter
- Structured fields are machine-parseable
- Consistent log format

---

## Anti-Patterns to Avoid

### ❌ Don't Use String Interpolation

```python
# ❌ WRONG
logger.info(f"Downloaded {count} tracks in {duration}ms")

# ✅ CORRECT
logger.info("download.complete", extra={"count": count, "duration_ms": duration})
```

### ❌ Don't Log Sensitive Data

```python
# ❌ WRONG: Logs password!
logger.info("login.success", extra={"username": user, "password": pwd})

# ✅ CORRECT: Only non-sensitive data
logger.info("login.success", extra={"username": user})
```

### ❌ Don't Swallow Exceptions Without Logging

```python
# ❌ WRONG: Silent failure
try:
    await risky_operation()
except Exception:
    pass  # NO! Log the error!

# ✅ CORRECT: Log then handle
try:
    await risky_operation()
except Exception as e:
    logger.error("operation.failed", exc_info=True)
    # Handle or re-raise
```

### ❌ Don't Use print()

```python
# ❌ WRONG
print(f"Downloading track {track_id}")

# ✅ CORRECT
logger.info("download.started", extra={"track_id": track_id})
```

**Why logger over print?**
- Logger respects log levels (can filter DEBUG in production)
- Includes timestamps, module name, line number automatically
- Structured logging with `extra` fields
- Correlation ID support

---

## Helper Functions

Use shared utilities from `infrastructure/observability/logger_template.py`:

```python
from soulspot.infrastructure.observability.logger_template import (
    get_module_logger,
    log_operation,
    log_worker_health
)

# Get logger
logger = get_module_logger(__name__)

# Log operation with automatic timing
async with log_operation(logger, "sync_playlists", user_id="123"):
    await sync_playlists()

# Log worker health
log_worker_health(logger, "spotify_sync", cycles=10, errors=2, uptime=3600)
```

---

## Troubleshooting with Logs

### Find All Logs for a Module

```bash
docker logs soulspot 2>&1 | grep "spotify_sync_worker"
```

### Find Logs by Correlation ID

```bash
# Find all logs for specific request
docker logs soulspot 2>&1 | grep "correlation_id.*abc-123"
```

### Find All Errors

```bash
docker logs soulspot 2>&1 | grep "ERROR"
```

### Find Slow Queries

```bash
docker logs soulspot 2>&1 | grep "slow_query"
```

### Find Worker Health Status

```bash
docker logs soulspot 2>&1 | grep "worker.health"
```

---

## Configuration

Logging is configured in `infrastructure/observability/logging.py`.

**Environment Variables:**
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `LOG_FORMAT`: json, text (default: text for Docker)

**Development:**
```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=text
```

**Production:**
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## Related Documentation

- [Log Analysis Guide](../troubleshooting/LOG_ANALYSIS.md)
- [Observability Overview](../architecture/OBSERVABILITY.md)
- [Monitoring Guide](../operations/MONITORING.md)

---

## Changelog

### 2025-12-30 - Version 1.0
- Initial logging standards documentation
- Added patterns for workers, services, API
- Defined structured logging format
- Added anti-patterns section
