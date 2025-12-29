# Hey future me - this is THE FIX for "database is locked" errors!
#
# SQLite locks are TEMPORARY - waiting and retrying almost always works.
# This module provides a decorator that adds automatic retry logic with
# exponential backoff to any async database operation.
#
# WHY THIS EXISTS:
# SQLite can only have ONE writer at a time (even with WAL mode).
# When multiple workers try to write simultaneously, one gets "database is locked".
# Without retry logic: immediate failure → user sees error
# With retry logic: wait a bit → try again → success!
#
# USAGE:
#   @with_db_retry(max_attempts=3)
#   async def add_track(self, track: Track) -> Track:
#       ...
#
# METRICS:
# This decorator integrates with DatabaseLockMetrics to track lock events.
# Check /api/health/db-metrics to see how often locks occur.
"""Database retry utilities for handling SQLite lock errors."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class DatabaseLockMetrics:
    """Track database lock events for monitoring.

    Hey future me - use this to DETECT problems before users complain!

    This is a singleton that collects metrics about database lock events.
    Expose via /api/health/db-metrics for Grafana/Prometheus integration.

    Metrics tracked:
    - lock_attempts: Total operations that attempted DB access
    - lock_successes: Operations that succeeded (possibly after retries)
    - lock_failures: Operations that failed after all retries exhausted
    - lock_retries: Total retry attempts made
    - total_wait_time_ms: Cumulative time spent waiting for locks
    - max_wait_time_ms: Longest single wait time recorded
    """

    _instance: DatabaseLockMetrics | None = None

    def __init__(self) -> None:
        """Initialize metrics counters."""
        self.lock_attempts: int = 0
        self.lock_successes: int = 0
        self.lock_failures: int = 0
        self.lock_retries: int = 0
        self.total_wait_time_ms: float = 0.0
        self.max_wait_time_ms: float = 0.0
        self.last_lock_event: float | None = None

    @classmethod
    def get_instance(cls) -> DatabaseLockMetrics:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_attempt(self) -> None:
        """Record a database operation attempt."""
        self.lock_attempts += 1

    def record_success(self, wait_time_ms: float = 0.0) -> None:
        """Record a successful operation.

        Args:
            wait_time_ms: Time spent waiting for lock (0 if no wait needed)
        """
        self.lock_successes += 1
        self.total_wait_time_ms += wait_time_ms
        if wait_time_ms > self.max_wait_time_ms:
            self.max_wait_time_ms = wait_time_ms
        if wait_time_ms > 0:
            self.last_lock_event = time.time()

    def record_failure(self) -> None:
        """Record a failed operation (all retries exhausted)."""
        self.lock_failures += 1
        self.last_lock_event = time.time()
        logger.warning(
            "Database lock failure recorded (total failures: %d)", self.lock_failures
        )

    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.lock_retries += 1

    def get_stats(self) -> dict[str, Any]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary with all lock metrics for monitoring/alerting.
        """
        return {
            "lock_attempts": self.lock_attempts,
            "lock_successes": self.lock_successes,
            "lock_failures": self.lock_failures,
            "lock_retries": self.lock_retries,
            "total_wait_time_ms": round(self.total_wait_time_ms, 2),
            "max_wait_time_ms": round(self.max_wait_time_ms, 2),
            "avg_wait_time_ms": round(
                self.total_wait_time_ms / self.lock_successes
                if self.lock_successes > 0
                else 0,
                2,
            ),
            "failure_rate": round(
                self.lock_failures / self.lock_attempts
                if self.lock_attempts > 0
                else 0,
                4,
            ),
            "retry_rate": round(
                self.lock_retries / self.lock_attempts if self.lock_attempts > 0 else 0,
                4,
            ),
            "last_lock_event_timestamp": self.last_lock_event,
        }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self.lock_attempts = 0
        self.lock_successes = 0
        self.lock_failures = 0
        self.lock_retries = 0
        self.total_wait_time_ms = 0.0
        self.max_wait_time_ms = 0.0
        self.last_lock_event = None


def with_db_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    track_metrics: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying database operations on lock errors.

    Hey future me - this is THE KEY decorator for SQLite resilience!

    SQLite locks are TEMPORARY. When one process holds a write lock,
    others get "database is locked" error. But if we just wait and retry,
    it almost always succeeds. This decorator automates that pattern.

    The backoff is exponential: 0.5s → 1s → 2s → 4s (capped at max_delay).
    This prevents thundering herd if multiple operations are waiting.

    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 5.0)
        backoff_factor: Multiply delay by this each retry (default: 2.0)
        track_metrics: Whether to record metrics (default: True)

    Returns:
        Decorated function with automatic retry logic.

    Example:
        @with_db_retry(max_attempts=3)
        async def add_track(self, track: Track) -> Track:
            self._session.add(TrackModel.from_entity(track))
            await self._session.flush()
            return track

        # If "database is locked" occurs:
        # - Attempt 1: fails, wait 0.5s
        # - Attempt 2: fails, wait 1.0s
        # - Attempt 3: succeeds!

    Notes:
        - Only retries on "database is locked" errors
        - Other OperationalErrors are raised immediately
        - Non-async functions are NOT supported (use async!)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            metrics = DatabaseLockMetrics.get_instance() if track_metrics else None
            last_exception: Exception | None = None
            delay = initial_delay
            start_time = time.monotonic()
            total_wait_ms = 0.0

            if metrics:
                metrics.record_attempt()

            for attempt in range(max_attempts):
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]

                    # Success! Record metrics
                    if metrics:
                        metrics.record_success(total_wait_ms)

                    return result

                except OperationalError as e:
                    error_msg = str(e).lower()

                    # Only retry on lock-related errors
                    # Other OperationalErrors (connection issues, etc.) should fail fast
                    if "locked" not in error_msg and "busy" not in error_msg:
                        if metrics:
                            metrics.record_failure()
                        raise

                    last_exception = e

                    if attempt < max_attempts - 1:
                        if metrics:
                            metrics.record_retry()

                        logger.warning(
                            "Database locked (attempt %d/%d), retrying in %.1fs: %s.%s",
                            attempt + 1,
                            max_attempts,
                            delay,
                            func.__module__,
                            func.__qualname__,
                        )

                        await asyncio.sleep(delay)
                        total_wait_ms += delay * 1000
                        delay = min(delay * backoff_factor, max_delay)

                    else:
                        # All retries exhausted
                        elapsed = (time.monotonic() - start_time) * 1000
                        logger.error(
                            "Database locked after %d attempts (%.0fms total), giving up: %s.%s",
                            max_attempts,
                            elapsed,
                            func.__module__,
                            func.__qualname__,
                        )
                        if metrics:
                            metrics.record_failure()

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry decorator")

        return wrapper  # type: ignore[return-value]

    return decorator


def is_lock_error(exception: Exception) -> bool:
    """Check if an exception is a database lock error.

    Hey future me - use this helper to check if you should retry manually!

    Args:
        exception: The exception to check

    Returns:
        True if this is a retryable lock error
    """
    if not isinstance(exception, OperationalError):
        return False

    error_msg = str(exception).lower()
    return "locked" in error_msg or "busy" in error_msg


async def execute_with_retry(
    operation: Callable[[], T],
    max_attempts: int = 3,
    initial_delay: float = 0.5,
) -> T:
    """Execute an operation with retry logic.

    Hey future me - use this for one-off operations that aren't decorated!

    This is useful for inline operations where you can't use the decorator.

    Args:
        operation: Async callable to execute
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay between retries

    Returns:
        Result of the operation

    Example:
        result = await execute_with_retry(
            lambda: session.execute(update_stmt),
            max_attempts=3,
        )
    """
    last_exception: Exception | None = None
    delay = initial_delay

    for attempt in range(max_attempts):
        try:
            return await operation()  # type: ignore[misc]
        except OperationalError as e:
            if not is_lock_error(e):
                raise

            last_exception = e

            if attempt < max_attempts - 1:
                logger.warning(
                    "Database locked (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 5.0)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in execute_with_retry")
