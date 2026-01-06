"""Shared logger utilities and templates.

Hey future me - this makes logging consistent across all modules!
Use these helper functions instead of raw logger.info() calls.

USAGE:
    from soulspot.infrastructure.observability.logger_template import (
        get_module_logger,
        log_operation,
        log_worker_health
    )
    
    logger = get_module_logger(__name__)
    
    async with log_operation(logger, "spotify_sync", playlist_id="xyz"):
        await sync_playlist()
    
    log_worker_health(logger, "spotify_sync", cycles=10, errors=2, uptime=3600)
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any


# Hey future me, this is just a wrapper around logging.getLogger() but ensures consistent
# usage across all modules. Always use __name__ for the logger name so it matches the module
# path (e.g., "soulspot.application.workers.spotify_sync_worker"). This enables hierarchical
# filtering in production (can silence debug logs from infrastructure but keep application logs).
def get_module_logger(name: str) -> logging.Logger:
    """Get logger for module with standard config.
    
    Args:
        name: Module name (use __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_module_logger(__name__)
        >>> logger.info("worker.started")
    """
    return logging.getLogger(name)


# Yo, this context manager is GOLD for operation timing! It logs start/end with automatic
# duration tracking. Put your operation inside the context and it handles success/failure
# logging automatically. The **context args become extra fields in both start and end logs!
# On exception, it logs the failure with exc_info=True (full traceback) and re-raises so
# caller can handle it. Use this for ANY operation you want to time (sync cycles, API calls,
# database queries). The duration_ms field is added automatically to the completion log!
@asynccontextmanager
async def log_operation(
    logger: logging.Logger,
    operation: str,
    **context: Any,
):
    """Context manager for logging operation start/end with automatic timing.
    
    Logs:
    - {operation}.started with context fields
    - {operation}.completed with context + duration_ms
    - {operation}.failed with context + duration_ms + error details (if exception)
    
    Args:
        logger: Logger instance from get_module_logger()
        operation: Operation name (e.g., "spotify_sync", "download_track")
        **context: Additional fields to include in logs (e.g., track_id="abc")
        
    Example:
        >>> async with log_operation(logger, "download_track", track_id="abc123"):
        ...     await download_track()
        
        # Logs:
        # INFO: download_track.started {"track_id": "abc123"}
        # INFO: download_track.completed {"track_id": "abc123", "duration_ms": 1234}
    """
    start = time.time()
    logger.info(f"{operation}.started", extra=context)
    
    try:
        yield
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            f"{operation}.completed",
            extra={**context, "duration_ms": duration_ms},
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(
            f"{operation}.failed",
            extra={
                **context,
                "duration_ms": duration_ms,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,  # CRITICAL: Includes full traceback
        )
        raise  # Re-raise so caller can handle


# Listen future me, this logs worker health status in a CONSISTENT format across all workers!
# Call this periodically (every 10 cycles or every 10 minutes) to monitor worker health.
# The uptime_seconds helps track when workers were last restarted. The errors_total counter
# helps identify problematic workers. If a worker has high errors, you can grep logs for
# that worker name to debug. Use this instead of ad-hoc health logging!
def log_worker_health(
    logger: logging.Logger,
    worker_name: str,
    cycles_completed: int,
    errors_total: int,
    uptime_seconds: float,
    extra_stats: dict[str, Any] | None = None,
) -> None:
    """Log worker health status in consistent format.
    
    Call this every N cycles (e.g., every 10) for monitoring.
    
    Args:
        logger: Logger instance
        worker_name: Worker identifier (e.g., "spotify_sync", "download_monitor")
        cycles_completed: Total cycles completed since start
        errors_total: Total errors encountered since start
        uptime_seconds: Seconds since worker started
        extra_stats: Optional dict of additional stats to include in log
        
    Example:
        >>> log_worker_health(
        ...     logger,
        ...     "spotify_sync",
        ...     cycles_completed=100,
        ...     errors_total=3,
        ...     uptime_seconds=3600,
        ...     extra_stats={"synced_playlists": 5}
        ... )
        
        # Logs:
        # INFO: worker.health {
        #     "worker": "spotify_sync",
        #     "cycles_completed": 100,
        #     "errors_total": 3,
        #     "uptime_seconds": 3600,
        #     "synced_playlists": 5
        # }
    """
    log_data = {
        "worker": worker_name,
        "cycles_completed": cycles_completed,
        "errors_total": errors_total,
        "uptime_seconds": int(uptime_seconds),
    }
    if extra_stats:
        log_data.update(extra_stats)
    
    logger.info("worker.health", extra=log_data)


# Hey future me, this logs operation timing WITHOUT the context manager! Use this when you
# can't use async context managers (sync code, or when you need more control). It does the
# same duration tracking but you call start_operation() and end_operation() manually. The
# operation_id is important - it ties start/end logs together. Generate it with str(uuid.uuid4())
# or use a unique identifier like track_id. Don't forget to call end_operation even on errors!
#
# NEW: log_level parameter! For batch operations (per-item in a loop), use logging.DEBUG
# to avoid flooding logs. The batch summary should be INFO, not each individual item.
def start_operation(
    logger: logging.Logger,
    operation: str,
    operation_id: str | None = None,
    log_level: int = logging.INFO,
    **context: Any,
) -> tuple[float, str]:
    """Log operation start and return timing info.
    
    Use this with end_operation() for manual timing control.
    
    Args:
        logger: Logger instance
        operation: Operation name
        operation_id: Optional unique ID for this operation instance
        log_level: Logging level (default INFO, use DEBUG for batch item operations)
        **context: Additional fields
        
    Returns:
        (start_time, operation_id) - Pass to end_operation()
        
    Example:
        >>> start_time, op_id = start_operation(logger, "sync_playlists", user_id="123")
        >>> # ... do work ...
        >>> end_operation(logger, "sync_playlists", start_time, op_id, user_id="123")
        
        # For batch operations (per-item logging):
        >>> for item in items:
        ...     start_time, op_id = start_operation(
        ...         logger, "process_item", log_level=logging.DEBUG, item_id=item.id
        ...     )
        ...     # process item
        ...     end_operation(logger, "process_item", start_time, op_id, log_level=logging.DEBUG)
    """
    import uuid

    if operation_id is None:
        operation_id = str(uuid.uuid4())

    start_time = time.time()
    logger.log(
        log_level,
        f"{operation}.started",
        extra={**context, "operation_id": operation_id},
    )
    return start_time, operation_id


def end_operation(
    logger: logging.Logger,
    operation: str,
    start_time: float,
    operation_id: str,
    success: bool = True,
    error: Exception | None = None,
    log_level: int = logging.INFO,
    **context: Any,
) -> None:
    """Log operation end with duration.
    
    Args:
        logger: Logger instance
        operation: Operation name (must match start_operation)
        start_time: Start time from start_operation()
        operation_id: Operation ID from start_operation()
        success: Whether operation succeeded
        error: Exception if failed (will log with exc_info=True)
        log_level: Logging level for success (default INFO, use DEBUG for batch items)
                   Error level is always ERROR regardless of this setting.
        **context: Additional fields (should match start_operation)
        
    Example:
        >>> start_time, op_id = start_operation(logger, "download", track_id="abc")
        >>> try:
        ...     # ... do work ...
        ...     end_operation(logger, "download", start_time, op_id, track_id="abc")
        ... except Exception as e:
        ...     end_operation(
        ...         logger, "download", start_time, op_id,
        ...         success=False, error=e, track_id="abc"
        ...     )
    """
    duration_ms = int((time.time() - start_time) * 1000)
    
    if success:
        logger.log(
            log_level,
            f"{operation}.completed",
            extra={
                **context,
                "operation_id": operation_id,
                "duration_ms": duration_ms,
            },
        )
    else:
        # Errors always log at ERROR level regardless of log_level parameter
        logger.error(
            f"{operation}.failed",
            extra={
                **context,
                "operation_id": operation_id,
                "duration_ms": duration_ms,
                "error": str(error) if error else "Unknown error",
                "error_type": type(error).__name__ if error else "Unknown",
            },
            exc_info=error is not None,  # Include traceback if exception provided
        )


# Yo, this is a simple wrapper for slow operation detection! Use it to log warnings when
# operations take longer than expected. The threshold_ms is configurable per operation
# (100ms for DB queries, 5000ms for API calls, etc.). It logs the actual duration so you
# can see how slow it was. Use this in repositories, API clients, and anywhere performance
# matters. If you see lots of slow_operation logs, investigate what's blocking!
def log_slow_operation(
    logger: logging.Logger,
    operation: str,
    duration_ms: int,
    threshold_ms: int = 100,
    **context: Any,
) -> None:
    """Log warning if operation exceeded threshold.
    
    Args:
        logger: Logger instance
        operation: Operation name
        duration_ms: Actual operation duration
        threshold_ms: Threshold for "slow" (default: 100ms)
        **context: Additional fields (e.g., query, endpoint)
        
    Example:
        >>> start = time.time()
        >>> await execute_query(...)
        >>> duration_ms = int((time.time() - start) * 1000)
        >>> log_slow_operation(
        ...     logger, "database_query",
        ...     duration_ms, threshold_ms=100,
        ...     query="SELECT * FROM tracks"
        ... )
        
        # Only logs if duration_ms > 100:
        # WARNING: operation.slow {
        #     "operation": "database_query",
        #     "duration_ms": 234,
        #     "threshold_ms": 100,
        #     "query": "SELECT * FROM tracks"
        # }
    """
    if duration_ms > threshold_ms:
        logger.warning(
            "operation.slow",
            extra={
                **context,
                "operation": operation,
                "duration_ms": duration_ms,
                "threshold_ms": threshold_ms,
            },
        )
