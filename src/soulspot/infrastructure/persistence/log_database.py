# Hey future me - this is a SEPARATE database just for logs!
#
# Why separate? Logs have different needs than business data:
# - Many writes (every log line)
# - Loss is acceptable (best-effort)
# - Old data gets deleted (7 days retention)
# - No complex queries needed
#
# Lidarr does the same thing (lidarr.db + logs.db).
# This keeps log writes from blocking business operations.
#
# See: docs/architecture/HYBRID_DB_STRATEGY.md for full architecture
"""
Separate SQLite database for application logs.

This module provides a dedicated database for logging that doesn't
interfere with the main application database.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A single log entry to be stored.

    Attributes:
        timestamp: When the log was created (UTC)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger_name: Name of the logger that created this
        message: The log message
        extra: Optional additional data (file, line, function, etc.)
    """

    timestamp: datetime
    level: str
    logger_name: str
    message: str
    extra: Dict[str, Any] | None = None


class LogDatabase:
    """
    Separate SQLite database for application logs.

    Features:
    - Own database file (data/logs.db)
    - Async writes with batching
    - Best-effort (errors are logged, not raised)
    - Auto-cleanup of old logs

    How it works:
    1. Logging handler calls log() → instant (adds to deque)
    2. Every 2 seconds → batch write to logs.db
    3. Daily cleanup job removes logs older than max_age_days

    Best-Effort Philosophy:
    - Losing logs is acceptable
    - Never crash the app because of log failures
    - Queue has max size (10,000) to prevent memory issues

    Example:
        log_db = LogDatabase(db_path="data/logs.db")
        await log_db.init()
        await log_db.start()

        # Attach to Python logging
        handler = DatabaseLogHandler(log_db)
        logging.getLogger("soulspot").addHandler(handler)
    """

    def __init__(
        self,
        db_path: Path | str = "data/logs.db",
        batch_size: int = 50,
        flush_interval: float = 2.0,
        max_age_days: int = 7,
    ):
        """
        Initialize the log database.

        Args:
            db_path: Path to the SQLite database file
            batch_size: Number of logs to write per batch
            flush_interval: Seconds between writes
            max_age_days: Delete logs older than this
        """
        self._db_path = Path(db_path)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_age_days = max_age_days

        # Queue with max size (prevents memory explosion)
        self._queue: Deque[LogEntry] = deque(maxlen=10000)
        self._running = False
        self._flush_task: asyncio.Task | None = None

        # Metrics
        self._logs_queued = 0
        self._logs_written = 0
        self._logs_dropped = 0
        self._write_errors = 0

    async def init(self) -> None:
        """
        Initialize the database schema.

        Creates the data directory and logs table if they don't exist.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            # WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=500")

            # Create logs table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    logger TEXT NOT NULL,
                    message TEXT NOT NULL,
                    extra TEXT
                )
                """
            )

            # Index for efficient cleanup by timestamp
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                ON logs(timestamp)
                """
            )

            # Index for filtering by level
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_logs_level
                ON logs(level)
                """
            )

            await db.commit()

        logger.info("LogDatabase initialized: %s", self._db_path)

    async def start(self) -> None:
        """Start the background writer task."""
        if self._running:
            logger.warning("LogDatabase already running")
            return

        self._running = True
        self._flush_task = asyncio.create_task(
            self._flush_loop(), name="log_db_flush"
        )
        logger.info("LogDatabase writer started")

    async def stop(self) -> None:
        """Stop the writer and flush remaining logs."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush
        await self._flush()

        logger.info(
            "LogDatabase stopped. Stats: queued=%d, written=%d, dropped=%d, errors=%d",
            self._logs_queued,
            self._logs_written,
            self._logs_dropped,
            self._write_errors,
        )

    def log(
        self,
        level: str,
        logger_name: str,
        message: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        """
        Queue a log entry (non-blocking, synchronous).

        Called by DatabaseLogHandler. If queue is full, oldest entries
        are dropped (deque maxlen behavior).

        Args:
            level: Log level string
            logger_name: Name of the logger
            message: Formatted log message
            extra: Optional additional data
        """
        queue_was_full = len(self._queue) >= 10000

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            logger_name=logger_name,
            message=message,
            extra=extra,
        )
        self._queue.append(entry)
        self._logs_queued += 1

        if queue_was_full:
            self._logs_dropped += 1

    async def _flush_loop(self) -> None:
        """Background loop that periodically writes queued logs."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Best-effort: don't crash, just log to stderr
                print(f"LogDatabase flush error: {e}")
                self._write_errors += 1

    async def _flush(self) -> None:
        """Write queued log entries to the database."""
        if not self._queue:
            return

        # Take entries from queue (up to batch_size)
        entries: List[LogEntry] = []
        while self._queue and len(entries) < self._batch_size:
            entries.append(self._queue.popleft())

        if not entries:
            return

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(
                    """
                    INSERT INTO logs 
                    (timestamp, level, logger, message, extra)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            e.timestamp.isoformat(),
                            e.level,
                            e.logger_name,
                            e.message[:10000],  # Truncate very long messages
                            json.dumps(e.extra) if e.extra else None,
                        )
                        for e in entries
                    ],
                )
                await db.commit()

            self._logs_written += len(entries)

        except Exception as e:
            # Best-effort: log error, entries are lost
            print(f"LogDatabase write error ({len(entries)} logs lost): {e}")
            self._write_errors += 1
            self._logs_dropped += len(entries)

    async def cleanup_old_logs(self) -> int:
        """
        Delete logs older than max_age_days.

        Should be called by a daily housekeeping job.

        Returns:
            Number of deleted log entries
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._max_age_days)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM logs WHERE timestamp < ?",
                    (cutoff.isoformat(),),
                )
                deleted = cursor.rowcount
                await db.commit()

            logger.info(
                "LogDatabase cleanup: deleted %d logs older than %d days",
                deleted,
                self._max_age_days,
            )
            return deleted

        except Exception as e:
            logger.error("LogDatabase cleanup failed: %s", e)
            return 0

    async def get_recent_logs(
        self,
        level: str | None = None,
        logger_name: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent log entries for the UI.

        Args:
            level: Filter by log level (e.g., "ERROR")
            logger_name: Filter by logger name prefix
            limit: Maximum entries to return

        Returns:
            List of log entry dicts, newest first
        """
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row

                # Build query with optional filters
                conditions = []
                params: List[Any] = []

                if level:
                    conditions.append("level = ?")
                    params.append(level)

                if logger_name:
                    conditions.append("logger LIKE ?")
                    params.append(f"{logger_name}%")

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                cursor = await db.execute(
                    f"""
                    SELECT id, timestamp, level, logger, message, extra
                    FROM logs
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    params + [limit],
                )

                rows = await cursor.fetchall()
                return [
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "level": row["level"],
                        "logger": row["logger"],
                        "message": row["message"],
                        "extra": (
                            json.loads(row["extra"]) if row["extra"] else None
                        ),
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error("Failed to get recent logs: %s", e)
            return []

    async def get_log_stats(self) -> Dict[str, Any]:
        """
        Get log statistics for monitoring.

        Returns:
            Dictionary with log counts by level and total
        """
        try:
            async with aiosqlite.connect(self._db_path) as db:
                # Count by level
                cursor = await db.execute(
                    """
                    SELECT level, COUNT(*) as count
                    FROM logs
                    GROUP BY level
                    """
                )
                level_counts = {row[0]: row[1] for row in await cursor.fetchall()}

                # Total count
                cursor = await db.execute("SELECT COUNT(*) FROM logs")
                total = (await cursor.fetchone())[0]

                # Database file size
                file_size = self._db_path.stat().st_size if self._db_path.exists() else 0

                return {
                    "total_logs": total,
                    "by_level": level_counts,
                    "queue_size": len(self._queue),
                    "logs_queued": self._logs_queued,
                    "logs_written": self._logs_written,
                    "logs_dropped": self._logs_dropped,
                    "write_errors": self._write_errors,
                    "db_file_size_bytes": file_size,
                    "is_running": self._running,
                }

        except Exception as e:
            logger.error("Failed to get log stats: %s", e)
            return {"error": str(e)}


class DatabaseLogHandler(logging.Handler):
    """
    Python logging handler that writes to LogDatabase.

    Integrates with Python's standard logging module.

    Example:
        log_db = LogDatabase()
        await log_db.init()
        await log_db.start()

        handler = DatabaseLogHandler(log_db)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

        logging.getLogger("soulspot").addHandler(handler)
    """

    def __init__(self, log_db: LogDatabase):
        """
        Initialize the handler.

        Args:
            log_db: LogDatabase instance to write to
        """
        super().__init__()
        self._log_db = log_db

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process a log record.

        Called synchronously by Python logging, but log() is non-blocking.
        """
        try:
            # Build extra data
            extra: Dict[str, Any] = {
                "pathname": record.pathname,
                "lineno": record.lineno,
                "funcName": record.funcName,
            }

            # Include exception info if present
            if record.exc_info:
                extra["exception"] = self.format(record)

            self._log_db.log(
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                extra=extra,
            )

        except Exception:
            # Handler should never crash
            self.handleError(record)
