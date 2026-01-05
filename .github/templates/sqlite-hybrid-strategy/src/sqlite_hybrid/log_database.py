"""Separate SQLite database for application logging.

This module provides a dedicated database for storing application logs,
completely separate from the main database. This eliminates lock contention
when logging during heavy database operations.

Features:
- Async batched writes (logs are queued and written periodically)
- Best-effort (logging never crashes the application)
- Auto-cleanup of old logs
- Integration with Python's logging module

Usage:
    log_db = LogDatabase(
        db_path="/path/to/logs.db",
        retention_days=7,
    )
    await log_db.start()

    # Direct logging
    await log_db.log("INFO", "mylogger", "Something happened")

    # Or use with Python logging
    import logging
    handler = DatabaseLogHandler(log_db)
    logging.getLogger().addHandler(handler)

    # Shutdown
    await log_db.stop()
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A single log entry.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        logger_name: Name of the logger that created this entry.
        message: The log message.
        timestamp: When the log was created.
        extra_data: Additional structured data (as JSON-serializable dict).
    """

    level: str
    logger_name: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    extra_data: dict[str, Any] | None = None


class LogDatabase:
    """Separate SQLite database for application logs.

    This class manages a dedicated SQLite database for storing logs.
    It uses async batched writes to minimize lock contention and
    implements best-effort semantics (logging failures never crash the app).

    The database is completely separate from your main application database,
    ensuring that heavy logging never blocks application operations.

    Thread Safety:
        This class uses asyncio locks and is safe for concurrent async access.
        The underlying SQLite uses WAL mode for better concurrency.

    Example:
        log_db = LogDatabase("/var/log/app/logs.db")
        await log_db.start()

        await log_db.log("INFO", "myapp", "Application started")

        stats = await log_db.get_log_stats()
        print(f"Total logs: {stats['total_logged']}")

        await log_db.stop()
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        retention_days: int = 7,
        max_batch_size: int = 50,
        flush_interval_seconds: float = 2.0,
    ) -> None:
        """Initialize the log database.

        Args:
            db_path: Path to the SQLite database file.
                If None, uses in-memory database (lost on restart).
            retention_days: How many days to keep logs before auto-cleanup.
            max_batch_size: Maximum logs per write batch.
            flush_interval_seconds: How often to flush buffered logs.
        """
        self._db_path = Path(db_path) if db_path else None
        self._retention_days = retention_days
        self._max_batch_size = max_batch_size
        self._flush_interval = flush_interval_seconds

        # Connection string
        self._connection_string = (
            f"file:{self._db_path}" if self._db_path else ":memory:"
        )

        # Buffer and state
        self._buffer: list[LogEntry] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._flush_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

        # Metrics
        self._total_logged = 0

    async def start(self) -> None:
        """Start the log database and background tasks.

        Creates the database file and schema if they don't exist.
        Starts background flush and cleanup tasks.
        """
        if self._running:
            return

        try:
            await self._init_database()
            self._running = True

            # Start background tasks
            self._flush_task = asyncio.create_task(self._flush_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            logger.info(
                "LogDatabase started: %s (retention=%d days)",
                self._db_path or "in-memory",
                self._retention_days,
            )
        except Exception as e:
            logger.exception("Failed to start LogDatabase: %s", e)
            # Best effort - don't crash

    async def stop(self) -> None:
        """Stop the log database and flush remaining logs.

        Ensures all buffered logs are written before shutdown.
        """
        self._running = False

        # Cancel background tasks
        for task in [self._flush_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Final flush
        await self._flush()
        logger.info("LogDatabase stopped")

    async def log(
        self,
        level: str,
        logger_name: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Add a log entry to the buffer.

        This is a non-blocking operation - the log is buffered and will be
        written to the database during the next flush.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            logger_name: Name of the logger.
            message: The log message.
            extra: Optional additional structured data.
        """
        entry = LogEntry(
            level=level.upper(),
            logger_name=logger_name,
            message=message,
            extra_data=extra,
        )

        async with self._lock:
            self._buffer.append(entry)

            # Force flush if buffer is full
            if len(self._buffer) >= self._max_batch_size:
                await self._flush()

    async def _init_database(self) -> None:
        """Initialize the database schema."""

        def _init_sync() -> None:
            conn = sqlite3.connect(self._connection_string)
            try:
                cursor = conn.cursor()

                # Enable optimizations
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=1000")

                # Create logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        logger_name TEXT NOT NULL,
                        message TEXT NOT NULL,
                        extra_data TEXT
                    )
                """)

                # Index for timestamp-based queries and cleanup
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_timestamp
                    ON logs (timestamp)
                """)

                # Index for level filtering
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_level
                    ON logs (level)
                """)

                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_init_sync)

    async def _flush(self) -> None:
        """Flush buffered logs to database."""
        async with self._lock:
            if not self._buffer:
                return

            entries = self._buffer.copy()
            self._buffer.clear()

        # Write in thread to not block event loop
        try:
            await asyncio.to_thread(self._write_entries_sync, entries)
            self._total_logged += len(entries)
        except Exception as e:
            logger.warning("Failed to flush logs to database: %s", e)
            # Best effort - don't re-add to buffer to avoid infinite growth

    def _write_entries_sync(self, entries: list[LogEntry]) -> None:
        """Synchronously write entries to database (runs in thread)."""
        import json

        conn = sqlite3.connect(self._connection_string)
        try:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO logs (timestamp, level, logger_name, message, extra_data)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.timestamp.isoformat(),
                        entry.level,
                        entry.logger_name,
                        entry.message,
                        json.dumps(entry.extra_data) if entry.extra_data else None,
                    )
                    for entry in entries
                ],
            )
            conn.commit()
        finally:
            conn.close()

    async def _flush_loop(self) -> None:
        """Background task that periodically flushes the buffer."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._running:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Error in log flush loop: %s", e)

    async def _cleanup_loop(self) -> None:
        """Background task that periodically cleans up old logs."""
        while self._running:
            try:
                # Run cleanup once per hour
                await asyncio.sleep(3600)
                if self._running:
                    await self.cleanup_old_logs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Error in log cleanup loop: %s", e)

    async def cleanup_old_logs(self) -> int:
        """Remove logs older than retention period.

        Returns:
            Number of deleted log entries.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)

        def _cleanup_sync() -> int:
            conn = sqlite3.connect(self._connection_string)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM logs WHERE timestamp < ?",
                    (cutoff.isoformat(),),
                )
                deleted = cursor.rowcount
                conn.commit()

                # Vacuum to reclaim space
                cursor.execute("VACUUM")

                return deleted
            finally:
                conn.close()

        try:
            deleted = await asyncio.to_thread(_cleanup_sync)
            if deleted > 0:
                logger.info("Cleaned up %d old log entries", deleted)
            return deleted
        except Exception as e:
            logger.warning("Failed to cleanup old logs: %s", e)
            return 0

    async def get_recent_logs(
        self,
        level: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Get recent log entries.

        Args:
            level: Filter by log level (optional).
            limit: Maximum entries to return.

        Returns:
            List of LogEntry objects, newest first.
        """
        import json

        def _query_sync() -> list[tuple[Any, ...]]:
            conn = sqlite3.connect(self._connection_string)
            try:
                cursor = conn.cursor()

                if level:
                    cursor.execute(
                        """
                        SELECT timestamp, level, logger_name, message, extra_data
                        FROM logs WHERE level = ?
                        ORDER BY timestamp DESC LIMIT ?
                        """,
                        (level.upper(), limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT timestamp, level, logger_name, message, extra_data
                        FROM logs ORDER BY timestamp DESC LIMIT ?
                        """,
                        (limit,),
                    )

                return cursor.fetchall()
            finally:
                conn.close()

        try:
            rows = await asyncio.to_thread(_query_sync)
            return [
                LogEntry(
                    level=row[1],
                    logger_name=row[2],
                    message=row[3],
                    timestamp=datetime.fromisoformat(row[0]),
                    extra_data=json.loads(row[4]) if row[4] else None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning("Failed to query logs: %s", e)
            return []

    async def get_log_stats(self) -> dict[str, Any]:
        """Get log database statistics.

        Returns:
            Dict with keys:
            - total_logged: Total entries written since start
            - pending_count: Entries currently in buffer
            - is_running: Whether database is active
            - db_path: Path to database file
            - retention_days: Configured retention
            - db_size_mb: Database file size (if file-based)
        """
        stats: dict[str, Any] = {
            "total_logged": self._total_logged,
            "pending_count": len(self._buffer),
            "is_running": self._running,
            "db_path": str(self._db_path) if self._db_path else None,
            "retention_days": self._retention_days,
        }

        # Get file size if file-based
        if self._db_path and self._db_path.exists():
            stats["db_size_mb"] = round(self._db_path.stat().st_size / 1024 / 1024, 2)

        return stats


class DatabaseLogHandler(logging.Handler):
    """Python logging handler that writes to LogDatabase.

    This handler integrates LogDatabase with Python's standard logging module.
    All logs sent to loggers with this handler will be stored in the database.

    Example:
        log_db = LogDatabase("/path/to/logs.db")
        await log_db.start()

        handler = DatabaseLogHandler(log_db)
        handler.setLevel(logging.INFO)

        logging.getLogger().addHandler(handler)

        # Now all logs go to database
        logging.info("This goes to the database")
    """

    def __init__(self, log_database: LogDatabase) -> None:
        """Initialize the handler.

        Args:
            log_database: LogDatabase instance to write to.
        """
        super().__init__()
        self._log_database = log_database
        self._loop: asyncio.AbstractEventLoop | None = None

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record.

        This is called by Python's logging framework. The record is
        sent to the LogDatabase asynchronously.

        Args:
            record: The log record to emit.
        """
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop - skip (best effort)
                return

            # Extract extra data
            extra: dict[str, Any] | None = None
            if hasattr(record, "extra_data"):
                extra = record.extra_data  # type: ignore[attr-defined]
            elif record.exc_info:
                extra = {"exception": self.format(record)}

            # Schedule async log
            asyncio.create_task(
                self._log_database.log(
                    level=record.levelname,
                    logger_name=record.name,
                    message=record.getMessage(),
                    extra=extra,
                )
            )
        except Exception:
            # Best effort - never crash on logging
            self.handleError(record)
