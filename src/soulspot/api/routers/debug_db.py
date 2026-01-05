# Hey future me - dieser Router ist für DEBUGGING der Hybrid DB Strategy!
#
# Endpoints:
# - /api/debug/db/stats           → Overview of all Hybrid DB components
# - /api/debug/db/buffer          → WriteBufferCache stats and pending writes
# - /api/debug/db/buffer/flush    → Force flush all pending writes (POST)
# - /api/debug/db/logs            → LogDatabase stats and recent logs
# - /api/debug/db/retry           → RetryStrategy metrics (lock errors, retries)
# - /api/debug/db/locks           → Current SQLite lock information
#
# USE CASE: Diagnose "database is locked" issues in production.
# SECURITY: These endpoints expose internal state - consider auth in production!
#
# See: docs/architecture/HYBRID_DB_STRATEGY.md for architecture details.
"""Debug endpoints for Hybrid DB Strategy monitoring.

These endpoints provide visibility into:
- WriteBufferCache: Pending writes, flush stats, backpressure
- LogDatabase: Log stats, recent entries, cleanup
- RetryStrategy: Lock error counts, retry attempts, timing

Use these for:
- Diagnosing "database is locked" issues
- Monitoring write batching efficiency
- Understanding lock contention patterns
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/debug/db", tags=["debug"])


class HybridDbStats(BaseModel):
    """Combined stats from all Hybrid DB Strategy components."""

    timestamp: str = Field(description="ISO timestamp of stats collection")
    write_buffer: dict[str, Any] = Field(
        default_factory=dict, description="WriteBufferCache stats"
    )
    log_database: dict[str, Any] = Field(
        default_factory=dict, description="LogDatabase stats"
    )
    retry_metrics: dict[str, Any] = Field(
        default_factory=dict, description="RetryStrategy metrics"
    )
    sqlite_info: dict[str, Any] = Field(
        default_factory=dict, description="SQLite configuration info"
    )


class BufferStats(BaseModel):
    """WriteBufferCache statistics."""

    pending_count: int = Field(description="Number of pending writes")
    total_buffered: int = Field(description="Total writes buffered since startup")
    total_flushed: int = Field(description="Total writes flushed to DB")
    flush_count: int = Field(description="Number of flush operations")
    is_running: bool = Field(description="Whether buffer is running")
    pending_by_table: dict[str, int] = Field(
        default_factory=dict, description="Pending writes by table"
    )
    config: dict[str, Any] = Field(default_factory=dict, description="Buffer config")


class LogDbStats(BaseModel):
    """LogDatabase statistics."""

    total_logged: int = Field(description="Total log entries written")
    pending_count: int = Field(description="Pending log entries in buffer")
    is_running: bool = Field(description="Whether log database is running")
    db_path: str | None = Field(description="Path to log database file")
    retention_days: int = Field(description="Days to retain logs")


class RetryMetrics(BaseModel):
    """RetryStrategy metrics from DatabaseLockMetrics."""

    total_lock_errors: int = Field(description="Total lock errors encountered")
    total_retries: int = Field(description="Total retry attempts")
    total_failures: int = Field(
        description="Total failures after all retries exhausted"
    )
    total_successes_after_retry: int = Field(
        description="Operations that succeeded after retry"
    )
    last_lock_error: str | None = Field(description="Timestamp of last lock error")
    error_rate_per_minute: float = Field(
        description="Average lock errors per minute (last 5 min)"
    )


class FlushResult(BaseModel):
    """Result of manual buffer flush."""

    flushed_count: int = Field(description="Number of writes flushed")
    duration_ms: float = Field(description="Flush duration in milliseconds")
    success: bool = Field(description="Whether flush completed successfully")
    error: str | None = Field(default=None, description="Error message if failed")


@router.get("/stats", response_model=HybridDbStats)
async def get_hybrid_db_stats(request: Request) -> HybridDbStats:
    """Get comprehensive stats from all Hybrid DB Strategy components.

    Returns:
        Combined statistics from WriteBufferCache, LogDatabase, and RetryStrategy.
    """
    from soulspot.infrastructure.persistence.retry import DatabaseLockMetrics

    timestamp = datetime.now(UTC).isoformat()

    # WriteBufferCache stats
    write_buffer_stats: dict[str, Any] = {}
    write_buffer = getattr(request.app.state, "write_buffer", None)
    if write_buffer is not None:
        write_buffer_stats = write_buffer.get_stats()

    # LogDatabase stats
    log_db_stats: dict[str, Any] = {}
    log_database = getattr(request.app.state, "log_database", None)
    if log_database is not None:
        log_db_stats = await log_database.get_log_stats()

    # RetryStrategy metrics
    retry_stats = DatabaseLockMetrics.get_metrics()

    # SQLite info
    sqlite_info = {
        "busy_timeout_ms": 500,  # From our config
        "wal_mode": True,
        "journal_mode": "WAL",
        "synchronous": "NORMAL",
        "cache_size_kb": 64000,
        "mmap_size_mb": 256,
    }

    return HybridDbStats(
        timestamp=timestamp,
        write_buffer=write_buffer_stats,
        log_database=log_db_stats,
        retry_metrics=retry_stats,
        sqlite_info=sqlite_info,
    )


@router.get("/buffer", response_model=BufferStats)
async def get_buffer_stats(request: Request) -> BufferStats:
    """Get WriteBufferCache statistics and pending write info.

    Use this to monitor:
    - How many writes are pending
    - Flush efficiency (buffered vs flushed ratio)
    - Backpressure situations (high pending count)
    """
    write_buffer = getattr(request.app.state, "write_buffer", None)
    if write_buffer is None:
        raise HTTPException(
            status_code=503,
            detail="WriteBufferCache not initialized (SQLite not in use?)",
        )

    stats = write_buffer.get_stats()
    return BufferStats(
        pending_count=stats.get("pending_count", 0),
        total_buffered=stats.get("total_buffered", 0),
        total_flushed=stats.get("total_flushed", 0),
        flush_count=stats.get("flush_count", 0),
        is_running=stats.get("is_running", False),
        pending_by_table=stats.get("pending_by_table", {}),
        config=stats.get("config", {}),
    )


@router.post("/buffer/flush", response_model=FlushResult)
async def force_flush_buffer(request: Request) -> FlushResult:
    """Force flush all pending writes immediately.

    Use this when:
    - You need writes to be visible immediately
    - Before taking a backup
    - Debugging write issues

    Returns:
        FlushResult with count of flushed writes and duration.
    """
    import time

    write_buffer = getattr(request.app.state, "write_buffer", None)
    if write_buffer is None:
        raise HTTPException(
            status_code=503,
            detail="WriteBufferCache not initialized",
        )

    start_time = time.monotonic()

    try:
        flushed = await write_buffer.force_flush()
        duration_ms = (time.monotonic() - start_time) * 1000
        return FlushResult(
            flushed_count=flushed,
            duration_ms=round(duration_ms, 2),
            success=True,
            error=None,
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        return FlushResult(
            flushed_count=0,
            duration_ms=round(duration_ms, 2),
            success=False,
            error=str(e),
        )


@router.get("/logs", response_model=LogDbStats)
async def get_log_db_stats(request: Request) -> LogDbStats:
    """Get LogDatabase statistics.

    Use this to monitor:
    - Log volume
    - Pending log entries
    - Database size/retention
    """
    log_database = getattr(request.app.state, "log_database", None)
    if log_database is None:
        raise HTTPException(
            status_code=503,
            detail="LogDatabase not initialized",
        )

    stats = await log_database.get_log_stats()
    return LogDbStats(
        total_logged=stats.get("total_logged", 0),
        pending_count=stats.get("pending_count", 0),
        is_running=stats.get("is_running", False),
        db_path=stats.get("db_path"),
        retention_days=stats.get("retention_days", 7),
    )


@router.get("/logs/recent")
async def get_recent_logs(
    request: Request,
    level: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Get recent log entries from LogDatabase.

    Args:
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        limit: Maximum number of entries to return (default 100)

    Returns:
        List of recent log entries.
    """
    log_database = getattr(request.app.state, "log_database", None)
    if log_database is None:
        raise HTTPException(
            status_code=503,
            detail="LogDatabase not initialized",
        )

    logs = await log_database.get_recent_logs(level=level, limit=limit)
    return {
        "count": len(logs),
        "logs": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "logger": log.logger_name,
                "message": log.message,
                "extra": log.extra_data,
            }
            for log in logs
        ],
    }


@router.get("/retry", response_model=RetryMetrics)
async def get_retry_metrics() -> RetryMetrics:
    """Get RetryStrategy metrics for lock error analysis.

    Use this to monitor:
    - Lock error frequency
    - Retry success rate
    - Identify if BusyTimeout needs adjustment
    """
    from soulspot.infrastructure.persistence.retry import DatabaseLockMetrics

    metrics = DatabaseLockMetrics.get_metrics()
    return RetryMetrics(
        total_lock_errors=metrics.get("total_lock_errors", 0),
        total_retries=metrics.get("total_retries", 0),
        total_failures=metrics.get("total_failures", 0),
        total_successes_after_retry=metrics.get("total_successes_after_retry", 0),
        last_lock_error=metrics.get("last_lock_error"),
        error_rate_per_minute=metrics.get("error_rate_per_minute", 0.0),
    )


@router.post("/retry/reset")
async def reset_retry_metrics() -> dict[str, str]:
    """Reset retry metrics counters.

    Use this to:
    - Start fresh measurement period
    - Clear old data after fixing issues
    """
    from soulspot.infrastructure.persistence.retry import DatabaseLockMetrics

    DatabaseLockMetrics.reset()
    return {"status": "ok", "message": "Retry metrics reset"}


@router.get("/locks")
async def get_lock_info(request: Request) -> dict[str, Any]:
    """Get current SQLite lock information.

    This queries SQLite's internal state to show:
    - Current lock mode
    - WAL checkpoint status
    - Any blocked operations

    Note: This requires a database query, so use sparingly.
    """
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not initialized",
        )

    # Check if SQLite
    if "sqlite" not in str(db.settings.database.url):
        return {
            "info": "Lock info only available for SQLite",
            "database_type": "postgresql",
        }

    lock_info: dict[str, Any] = {
        "database_type": "sqlite",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    try:
        async with db.session_scope() as session:
            # Get journal mode
            result = await session.execute("PRAGMA journal_mode")
            row = result.scalar()
            lock_info["journal_mode"] = row

            # Get WAL checkpoint info
            result = await session.execute("PRAGMA wal_checkpoint")
            row = result.fetchone()
            if row:
                lock_info["wal_checkpoint"] = {
                    "busy": row[0],
                    "log": row[1],
                    "checkpointed": row[2],
                }

            # Get busy timeout
            result = await session.execute("PRAGMA busy_timeout")
            lock_info["busy_timeout_ms"] = result.scalar()

            # Get synchronous mode
            result = await session.execute("PRAGMA synchronous")
            lock_info["synchronous"] = result.scalar()

    except Exception as e:
        lock_info["error"] = str(e)

    return lock_info
