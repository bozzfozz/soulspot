# Hey future me - this is THE SOLUTION for "multiple workers blocking UI"!
#
# Problem: SQLite allows only ONE writer at a time. When SpotifySync, Download,
# and Deezer workers all try to write, they block each other AND the UI.
#
# Solution: Buffer all writes in RAM, flush periodically in batches.
# - Worker calls buffer_upsert() → instant (0ms, RAM)
# - Every 5 seconds → flush to DB in ONE transaction
# - UI never sees the locks, workers never block each other
#
# IMPORTANT: Read cache.get_buffered_value() for Read-Through when needed!
#
# Inspired by: Lidarr's approach (they use Polly retry, we add batching on top)
# See: docs/architecture/HYBRID_DB_STRATEGY.md for full architecture
"""
Write-Behind Cache for high-frequency database writes.

This module buffers write operations in RAM and flushes them periodically
to SQLite in batches. This prevents multiple workers from blocking each other
and keeps the UI responsive.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WriteOperation(Enum):
    """Type of buffered write operation."""

    UPSERT = auto()  # INSERT ON CONFLICT UPDATE
    UPDATE = auto()  # UPDATE existing row
    DELETE = auto()  # DELETE row


@dataclass
class PendingWrite:
    """A buffered write operation waiting to be flushed.

    Attributes:
        table: Database table name
        operation: Type of operation (UPSERT/UPDATE/DELETE)
        key_column: Primary key column name (e.g., "id", "spotify_uri")
        key_value: Value of the primary key
        data: Column values to write (empty for DELETE)
        timestamp: When this write was buffered
    """

    table: str
    operation: WriteOperation
    key_column: str
    key_value: Any
    data: Dict[str, Any]
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class BufferConfig:
    """Configuration for the write buffer.

    Timing:
        flush_interval: Seconds between automatic flushes (default: 5.0)
        max_buffer_age: Force flush if oldest item exceeds this (default: 30.0)

    Size Limits:
        max_pending_writes: Maximum items before force flush (default: 1000)
        batch_size: Items per SQL statement (default: 100)

    Priorities:
        table_priorities: Lower number = flushed first
    """

    flush_interval: float = 5.0
    max_buffer_age: float = 30.0
    max_pending_writes: int = 1000
    batch_size: int = 100

    # Critical tables flushed first (downloads need tracks)
    table_priorities: Dict[str, int] = field(
        default_factory=lambda: {
            "tracks": 1,
            "downloads": 2,
            "artists": 3,
            "albums": 4,
            "playlists": 5,
        }
    )


class WriteBufferCache:
    """
    Write-Behind Cache for high-frequency database writes.

    How it works:
    1. Worker calls buffer_upsert/update/delete() → instant (0ms, RAM)
    2. Every flush_interval seconds → bulk flush to DB
    3. On shutdown → force flush remaining data

    Thread Safety:
    - All methods are async-safe via asyncio.Lock
    - Multiple coroutines can buffer writes concurrently

    Error Handling:
    - Failed flushes: buffer is preserved, retry on next interval
    - On shutdown: force flush with error logging

    Example:
        cache = WriteBufferCache(session_factory)
        await cache.start()

        # In SpotifySyncWorker:
        await cache.buffer_upsert(
            table="tracks",
            key_column="spotify_uri",
            key_value="spotify:track:abc",
            data={"title": "Song", "duration_ms": 180000}
        )

        # Later, on shutdown:
        await cache.stop(flush_remaining=True)
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        config: BufferConfig | None = None,
    ):
        """
        Initialize the write buffer.

        Args:
            session_factory: Async context manager that yields AsyncSession
            config: Buffer configuration (uses defaults if None)
        """
        self._session_factory = session_factory
        self._config = config or BufferConfig()

        # Buffer structure: table -> key_value -> PendingWrite
        self._buffer: Dict[str, Dict[Any, PendingWrite]] = defaultdict(dict)
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

        # Metrics for monitoring
        self._writes_buffered = 0
        self._writes_flushed = 0
        self._flush_count = 0
        self._flush_errors = 0

    # ==================== Lifecycle ====================

    async def start(self) -> None:
        """Start the background flush task."""
        if self._running:
            logger.warning("WriteBufferCache already running")
            return

        self._running = True
        self._flush_task = asyncio.create_task(
            self._flush_loop(), name="write_buffer_flush"
        )
        logger.info(
            "WriteBufferCache started (flush_interval=%.1fs, batch_size=%d)",
            self._config.flush_interval,
            self._config.batch_size,
        )

    async def stop(self, flush_remaining: bool = True) -> None:
        """
        Stop the buffer and optionally flush remaining data.

        Args:
            flush_remaining: If True, flush all buffered data before stopping
        """
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        if flush_remaining:
            logger.info("WriteBufferCache stopping, flushing remaining data...")
            await self._flush_all()

        logger.info(
            "WriteBufferCache stopped. Stats: buffered=%d, flushed=%d, errors=%d",
            self._writes_buffered,
            self._writes_flushed,
            self._flush_errors,
        )

    # ==================== Public Write Methods ====================

    async def buffer_upsert(
        self,
        table: str,
        key_column: str,
        key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """
        Buffer an UPSERT operation (INSERT ON CONFLICT UPDATE).

        If a write for the same key already exists in buffer, it's replaced.
        The newest data wins.

        Args:
            table: Database table name
            key_column: Primary key column (e.g., "id", "spotify_uri")
            key_value: Primary key value
            data: Column values (key column is added automatically)

        Example:
            await cache.buffer_upsert(
                table="tracks",
                key_column="spotify_uri",
                key_value="spotify:track:abc123",
                data={"title": "Song", "artist": "Band", "duration_ms": 180000}
            )
        """
        async with self._lock:
            self._buffer[table][key_value] = PendingWrite(
                table=table,
                operation=WriteOperation.UPSERT,
                key_column=key_column,
                key_value=key_value,
                data=data,
            )
            self._writes_buffered += 1

            # Backpressure: force flush if buffer is full
            total = sum(len(t) for t in self._buffer.values())
            if total >= self._config.max_pending_writes:
                logger.warning(
                    "WriteBufferCache full (%d items), forcing flush", total
                )
                # Don't await here to avoid blocking the caller
                asyncio.create_task(self._flush_all())

    async def buffer_update(
        self,
        table: str,
        key_column: str,
        key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """
        Buffer an UPDATE operation (only updates existing rows).

        If an UPSERT is already buffered for this key, the data is merged.

        Args:
            table: Database table name
            key_column: Primary key column
            key_value: Primary key value
            data: Column values to update
        """
        async with self._lock:
            existing = self._buffer[table].get(key_value)

            if existing and existing.operation == WriteOperation.UPSERT:
                # Merge with existing UPSERT
                existing.data.update(data)
                existing.timestamp = datetime.now(timezone.utc)
            else:
                self._buffer[table][key_value] = PendingWrite(
                    table=table,
                    operation=WriteOperation.UPDATE,
                    key_column=key_column,
                    key_value=key_value,
                    data=data,
                )

            self._writes_buffered += 1

    async def buffer_delete(
        self,
        table: str,
        key_column: str,
        key_value: Any,
    ) -> None:
        """
        Buffer a DELETE operation.

        DELETE overwrites any previous operation for this key.

        Args:
            table: Database table name
            key_column: Primary key column
            key_value: Primary key value to delete
        """
        async with self._lock:
            # DELETE overwrites everything
            self._buffer[table][key_value] = PendingWrite(
                table=table,
                operation=WriteOperation.DELETE,
                key_column=key_column,
                key_value=key_value,
                data={},
            )
            self._writes_buffered += 1

    # ==================== Read-Through Support ====================

    async def get_buffered_value(
        self,
        table: str,
        key_value: Any,
    ) -> Dict[str, Any] | None:
        """
        Get buffered data for a key (for read-through cache).

        Use this when reading data that might be in the buffer but not
        yet flushed to the database.

        Args:
            table: Database table name
            key_value: Primary key value to look up

        Returns:
            Buffered data dict, or None if not in buffer

        Example:
            # Check buffer first, then DB
            buffered = await cache.get_buffered_value("tracks", "spotify:track:abc")
            if buffered:
                return Track.from_dict(buffered)
            return await repo.get_by_spotify_uri("spotify:track:abc")
        """
        async with self._lock:
            pending = self._buffer.get(table, {}).get(key_value)
            if pending and pending.operation != WriteOperation.DELETE:
                # Return copy to prevent external modification
                result = dict(pending.data)
                result[pending.key_column] = pending.key_value
                return result
            return None

    async def is_key_buffered(self, table: str, key_value: Any) -> bool:
        """Check if a key is in the buffer."""
        async with self._lock:
            return key_value in self._buffer.get(table, {})

    # ==================== Flush Logic ====================

    async def _flush_loop(self) -> None:
        """Background task that periodically flushes the buffer."""
        while self._running:
            try:
                await asyncio.sleep(self._config.flush_interval)
                await self._flush_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in write buffer flush loop: %s", e)
                self._flush_errors += 1

    async def _flush_all(self) -> None:
        """Flush all buffered writes to the database."""
        async with self._lock:
            if not any(self._buffer.values()):
                return  # Nothing to flush

            # Sort tables by priority (critical tables first)
            tables = sorted(
                self._buffer.keys(),
                key=lambda t: self._config.table_priorities.get(t, 99),
            )

            for table in tables:
                writes = list(self._buffer[table].values())
                if not writes:
                    continue

                # Group by operation type
                upserts = [
                    w for w in writes if w.operation == WriteOperation.UPSERT
                ]
                updates = [
                    w for w in writes if w.operation == WriteOperation.UPDATE
                ]
                deletes = [
                    w for w in writes if w.operation == WriteOperation.DELETE
                ]

                try:
                    async with self._session_factory() as session:
                        # Order: DELETEs first (referential integrity),
                        # then UPSERTs, then UPDATEs
                        if deletes:
                            await self._bulk_delete(session, table, deletes)
                        if upserts:
                            await self._bulk_upsert(session, table, upserts)
                        if updates:
                            await self._bulk_update(session, table, updates)

                        await session.commit()

                    # Success: clear buffer for this table
                    self._writes_flushed += len(writes)
                    self._buffer[table].clear()

                    if len(writes) > 10:
                        logger.debug(
                            "Flushed %d writes to %s", len(writes), table
                        )

                except Exception as e:
                    logger.error(
                        "Failed to flush %d writes to %s: %s",
                        len(writes),
                        table,
                        e,
                    )
                    self._flush_errors += 1
                    # Buffer is preserved for next flush attempt

        self._flush_count += 1

    async def _bulk_upsert(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """Execute bulk UPSERT via SQLite ON CONFLICT."""
        if not writes:
            return

        # Collect all columns from all writes
        all_columns: Set[str] = set()
        for w in writes:
            all_columns.update(w.data.keys())
            all_columns.add(w.key_column)

        columns = sorted(all_columns)
        key_col = writes[0].key_column

        # Build SQL
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        update_clause = ", ".join(
            f'"{c}" = excluded."{c}"' for c in columns if c != key_col
        )

        sql = f"""
            INSERT INTO "{table}" ({col_list})
            VALUES ({placeholders})
            ON CONFLICT("{key_col}") DO UPDATE SET {update_clause}
        """

        # Execute in batches
        batch_size = self._config.batch_size
        for i in range(0, len(writes), batch_size):
            batch = writes[i : i + batch_size]
            params = []

            for w in batch:
                row = {c: w.data.get(c) for c in columns}
                row[w.key_column] = w.key_value
                params.append(row)

            await session.execute(text(sql), params)

    async def _bulk_update(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """Execute bulk UPDATE operations."""
        if not writes:
            return

        key_col = writes[0].key_column

        # Simple approach: individual UPDATEs (SQLite is fast for this)
        # For large batches, consider CASE WHEN pattern
        for w in writes:
            for col, val in w.data.items():
                sql = f"""
                    UPDATE "{table}" 
                    SET "{col}" = :val 
                    WHERE "{key_col}" = :key
                """
                await session.execute(
                    text(sql), {"val": val, "key": w.key_value}
                )

    async def _bulk_delete(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """Execute bulk DELETE via IN clause."""
        if not writes:
            return

        key_col = writes[0].key_column
        key_values = [w.key_value for w in writes]

        # Chunk to stay under SQLite's 999 parameter limit
        chunk_size = 500
        for i in range(0, len(key_values), chunk_size):
            batch = key_values[i : i + chunk_size]
            placeholders = ", ".join(f":k{j}" for j in range(len(batch)))

            sql = f"""
                DELETE FROM "{table}" 
                WHERE "{key_col}" IN ({placeholders})
            """
            params = {f"k{j}": v for j, v in enumerate(batch)}

            await session.execute(text(sql), params)

    # ==================== Public Methods ====================

    async def force_flush(self) -> None:
        """
        Force an immediate flush of all buffered data.

        Useful before critical operations or for debugging.
        """
        await self._flush_all()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get buffer statistics for monitoring.

        Returns:
            Dictionary with buffer metrics
        """
        total_pending = sum(len(t) for t in self._buffer.values())
        return {
            "pending_writes": total_pending,
            "writes_buffered": self._writes_buffered,
            "writes_flushed": self._writes_flushed,
            "flush_count": self._flush_count,
            "flush_errors": self._flush_errors,
            "is_running": self._running,
            "config": {
                "flush_interval": self._config.flush_interval,
                "max_pending_writes": self._config.max_pending_writes,
                "batch_size": self._config.batch_size,
            },
            "tables": {
                table: len(items) for table, items in self._buffer.items()
            },
        }

    async def get_pending_count(self, table: str | None = None) -> int:
        """Get count of pending writes, optionally filtered by table."""
        async with self._lock:
            if table:
                return len(self._buffer.get(table, {}))
            return sum(len(t) for t in self._buffer.values())
