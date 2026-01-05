"""Retry strategy for SQLite database operations with exponential backoff.

This module provides a decorator and utilities for handling SQLite "database is locked"
errors gracefully by retrying operations with exponential backoff and jitter.

Usage:
    @with_db_retry(max_retries=3, base_delay=0.1)
    async def save_data(session, data):
        session.add(data)
        await session.commit()

    # Or use execute_with_retry for one-off operations
    result = await execute_with_retry(
        lambda: session.execute(stmt),
        max_retries=3,
    )
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Any, Callable, ParamSpec, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class DatabaseBusyError(Exception):
    """SQLite database is busy/locked after max retries exhausted."""

    def __init__(self, message: str, attempts: int, total_wait_time: float) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.total_wait_time = total_wait_time


def is_lock_error(exc: BaseException) -> bool:
    """Check if an exception is a SQLite lock/busy error.

    Args:
        exc: The exception to check.

    Returns:
        True if the exception is a SQLite lock error that should trigger a retry.
    """
    if not isinstance(exc, OperationalError):
        return False

    error_msg = str(exc).lower()
    lock_indicators = [
        "database is locked",
        "database is busy",
        "sqlite_busy",
        "sqlite_locked",
        "cannot start a transaction within a transaction",
    ]

    return any(indicator in error_msg for indicator in lock_indicators)


@dataclass
class _LockMetrics:
    """Internal metrics storage for database lock errors."""

    total_lock_errors: int = 0
    total_retries: int = 0
    total_failures: int = 0
    total_successes_after_retry: int = 0
    last_lock_error: float | None = None
    error_timestamps: list[float] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)


class DatabaseLockMetrics:
    """Singleton metrics tracker for database lock errors.

    Use this to monitor lock error frequency and retry success rates.

    Example:
        metrics = DatabaseLockMetrics.get_metrics()
        print(f"Lock errors: {metrics['total_lock_errors']}")
        print(f"Error rate: {metrics['error_rate_per_minute']:.2f}/min")

        # Reset after investigation
        DatabaseLockMetrics.reset()
    """

    _instance: _LockMetrics | None = None
    _init_lock = Lock()

    @classmethod
    def _get_instance(cls) -> _LockMetrics:
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = _LockMetrics()
        return cls._instance

    @classmethod
    def record_lock_error(cls) -> None:
        """Record a lock error occurrence."""
        instance = cls._get_instance()
        with instance._lock:
            instance.total_lock_errors += 1
            now = time.time()
            instance.last_lock_error = now
            instance.error_timestamps.append(now)
            # Keep only last 5 minutes of timestamps
            cutoff = now - 300
            instance.error_timestamps = [
                ts for ts in instance.error_timestamps if ts > cutoff
            ]

    @classmethod
    def record_retry(cls) -> None:
        """Record a retry attempt."""
        instance = cls._get_instance()
        with instance._lock:
            instance.total_retries += 1

    @classmethod
    def record_failure(cls) -> None:
        """Record a final failure (all retries exhausted)."""
        instance = cls._get_instance()
        with instance._lock:
            instance.total_failures += 1

    @classmethod
    def record_success_after_retry(cls) -> None:
        """Record a successful operation after retry."""
        instance = cls._get_instance()
        with instance._lock:
            instance.total_successes_after_retry += 1

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Get current metrics as a dictionary.

        Returns:
            Dictionary with keys:
            - total_lock_errors: Total lock errors encountered
            - total_retries: Total retry attempts
            - total_failures: Operations that failed after all retries
            - total_successes_after_retry: Operations that succeeded after retry
            - last_lock_error: ISO timestamp of last error (or None)
            - error_rate_per_minute: Average errors/min over last 5 minutes
        """
        instance = cls._get_instance()
        with instance._lock:
            now = time.time()
            cutoff = now - 300  # 5 minutes
            recent_errors = len(
                [ts for ts in instance.error_timestamps if ts > cutoff]
            )
            error_rate = recent_errors / 5.0 if recent_errors > 0 else 0.0

            return {
                "total_lock_errors": instance.total_lock_errors,
                "total_retries": instance.total_retries,
                "total_failures": instance.total_failures,
                "total_successes_after_retry": instance.total_successes_after_retry,
                "last_lock_error": (
                    time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(instance.last_lock_error)
                    )
                    if instance.last_lock_error
                    else None
                ),
                "error_rate_per_minute": round(error_rate, 2),
            }

    @classmethod
    def reset(cls) -> None:
        """Reset all metrics to zero."""
        instance = cls._get_instance()
        with instance._lock:
            instance.total_lock_errors = 0
            instance.total_retries = 0
            instance.total_failures = 0
            instance.total_successes_after_retry = 0
            instance.last_lock_error = None
            instance.error_timestamps = []


def with_db_retry(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying database operations on lock errors.

    Uses exponential backoff with optional jitter to avoid thundering herd.

    Args:
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay in seconds (default: 0.1).
        max_delay: Maximum delay cap in seconds (default: 2.0).
        jitter: Add random offset to prevent synchronized retries (default: True).

    Returns:
        Decorated function that retries on SQLite lock errors.

    Example:
        @with_db_retry(max_retries=3)
        async def save_track(session, track):
            session.add(track)
            await session.commit()

    Raises:
        DatabaseBusyError: If all retries are exhausted.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: BaseException | None = None
            total_wait = 0.0

            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]

                    if attempt > 0:
                        DatabaseLockMetrics.record_success_after_retry()
                        logger.info(
                            "Operation '%s' succeeded after %d retries (%.2fs total wait)",
                            func.__name__,
                            attempt,
                            total_wait,
                        )

                    return result

                except Exception as exc:
                    if not is_lock_error(exc):
                        raise

                    last_exception = exc
                    DatabaseLockMetrics.record_lock_error()

                    if attempt >= max_retries:
                        DatabaseLockMetrics.record_failure()
                        break

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    # Add jitter (±25%)
                    if jitter:
                        delay *= 0.75 + random.random() * 0.5

                    DatabaseLockMetrics.record_retry()
                    logger.warning(
                        "SQLite lock error in '%s' (attempt %d/%d), "
                        "retrying in %.3fs: %s",
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        str(exc)[:100],
                    )

                    total_wait += delay
                    await asyncio.sleep(delay)

            # All retries exhausted
            raise DatabaseBusyError(
                f"Database busy after {max_retries + 1} attempts in '{func.__name__}': "
                f"{last_exception}",
                attempts=max_retries + 1,
                total_wait_time=total_wait,
            ) from last_exception

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: BaseException | None = None
            total_wait = 0.0

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    if attempt > 0:
                        DatabaseLockMetrics.record_success_after_retry()

                    return result

                except Exception as exc:
                    if not is_lock_error(exc):
                        raise

                    last_exception = exc
                    DatabaseLockMetrics.record_lock_error()

                    if attempt >= max_retries:
                        DatabaseLockMetrics.record_failure()
                        break

                    delay = min(base_delay * (2**attempt), max_delay)
                    if jitter:
                        delay *= 0.75 + random.random() * 0.5

                    DatabaseLockMetrics.record_retry()
                    logger.warning(
                        "SQLite lock error (attempt %d/%d), retrying in %.3fs",
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )

                    total_wait += delay
                    time.sleep(delay)

            raise DatabaseBusyError(
                f"Database busy after {max_retries + 1} attempts: {last_exception}",
                attempts=max_retries + 1,
                total_wait_time=total_wait,
            ) from last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


async def execute_with_retry(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    jitter: bool = True,
) -> T:
    """Execute a database operation with retry logic.

    Use this for one-off operations where a decorator isn't suitable.

    Args:
        operation: Callable that performs the database operation.
        max_retries: Maximum retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        jitter: Add randomization to delays.

    Returns:
        Result of the operation.

    Raises:
        DatabaseBusyError: If all retries exhausted.

    Example:
        result = await execute_with_retry(
            lambda: session.execute(select(User).where(User.id == user_id))
        )
    """
    last_exception: BaseException | None = None
    total_wait = 0.0

    for attempt in range(max_retries + 1):
        try:
            # Handle both sync and async operations
            result = operation()
            if asyncio.iscoroutine(result):
                result = await result

            if attempt > 0:
                DatabaseLockMetrics.record_success_after_retry()

            return result

        except Exception as exc:
            if not is_lock_error(exc):
                raise

            last_exception = exc
            DatabaseLockMetrics.record_lock_error()

            if attempt >= max_retries:
                DatabaseLockMetrics.record_failure()
                break

            delay = min(base_delay * (2**attempt), max_delay)
            if jitter:
                delay *= 0.75 + random.random() * 0.5

            DatabaseLockMetrics.record_retry()
            total_wait += delay
            await asyncio.sleep(delay)

    raise DatabaseBusyError(
        f"Database busy after {max_retries + 1} attempts: {last_exception}",
        attempts=max_retries + 1,
        total_wait_time=total_wait,
    ) from last_exception
