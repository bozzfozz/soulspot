"""SQLite Hybrid Strategy - Reusable concurrency solution for async Python projects."""

from sqlite_hybrid.log_database import DatabaseLogHandler, LogDatabase, LogEntry
from sqlite_hybrid.retry import (
    DatabaseBusyError,
    DatabaseLockMetrics,
    execute_with_retry,
    is_lock_error,
    with_db_retry,
)
from sqlite_hybrid.write_buffer import (
    BufferConfig,
    PendingWrite,
    WriteBufferCache,
    WriteOperation,
)

__version__ = "1.0.0"

__all__ = [
    # Retry Strategy
    "with_db_retry",
    "execute_with_retry",
    "is_lock_error",
    "DatabaseBusyError",
    "DatabaseLockMetrics",
    # Write Buffer Cache
    "WriteBufferCache",
    "BufferConfig",
    "PendingWrite",
    "WriteOperation",
    # Log Database
    "LogDatabase",
    "LogEntry",
    "DatabaseLogHandler",
]
