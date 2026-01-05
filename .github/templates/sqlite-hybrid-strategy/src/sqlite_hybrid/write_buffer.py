"""Write buffer cache for batching database writes.

This module provides a RAM-based write buffer that collects writes and flushes
them periodically in batches. This reduces SQLite lock contention by:
1. Coalescing multiple writes to the same row
2. Executing bulk operations instead of individual inserts/updates
3. Releasing the database lock quickly between batches

Ideal for background workers that generate many writes (sync, downloads, etc.)

Usage:
    buffer = WriteBufferCache(
        session_factory=db.get_session_factory(),
        config=BufferConfig(
            flush_interval_seconds=5.0,
            flush_batch_size=100,
        ),
    )
    await buffer.start()

    # Buffer writes (returns immediately)
    await buffer.buffer_upsert("tracks", {"id": 1, "title": "Song"}, ["id"])

    # On shutdown
    await buffer.stop()  # Flushes remaining writes
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WriteOperation(Enum):
    """Type of write operation to perform."""

    UPSERT = "upsert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class BufferConfig:
    """Configuration for WriteBufferCache.

    Attributes:
        max_buffer_size: Maximum pending writes before backpressure is applied.
            When exceeded, new writes block until buffer drains.
        flush_interval_seconds: How often to flush buffered writes (seconds).
        flush_batch_size: Maximum writes per flush operation.
        table_priorities: Dict mapping table names to priority (lower = flushed first).
            Tables not in dict get priority 999.
    """

    max_buffer_size: int = 1000
    flush_interval_seconds: float = 5.0
    flush_batch_size: int = 100
    table_priorities: dict[str, int] = field(default_factory=dict)


@dataclass
class PendingWrite:
    """A single pending write operation.

    Attributes:
        operation: Type of write (UPSERT, UPDATE, DELETE).
        table: Target table name.
        data: Row data as dict (column -> value).
        key_columns: Columns that uniquely identify the row.
        timestamp: When the write was buffered.
    """

    operation: WriteOperation
    table: str
    data: dict[str, Any]
    key_columns: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class WriteBufferCache:
    """RAM-based write buffer with periodic batch flushing.

    This class buffers write operations in memory and flushes them periodically
    to the database in batches. It reduces lock contention by:
    - Coalescing multiple writes to the same row (last write wins)
    - Using bulk operations for efficiency
    - Running flushes on a schedule to batch writes together

    Thread Safety:
        This class uses asyncio locks and is safe for concurrent async access.
        It is NOT safe for multi-process use.

    Example:
        buffer = WriteBufferCache(session_factory, BufferConfig())
        await buffer.start()

        # In your worker code
        await buffer.buffer_upsert("downloads", {"id": 1, "status": "done"}, ["id"])

        # Get stats
        stats = buffer.get_stats()
        print(f"Pending: {stats['pending_count']}")

        # Clean shutdown
        await buffer.stop()
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        config: BufferConfig | None = None,
    ) -> None:
        """Initialize the write buffer.

        Args:
            session_factory: Callable that returns a new AsyncSession.
            config: Buffer configuration. Uses defaults if not provided.
        """
        self._session_factory = session_factory
        self._config = config or BufferConfig()

        # Buffer storage: table -> key -> PendingWrite
        self._buffer: dict[str, dict[str, PendingWrite]] = defaultdict(dict)
        self._lock = asyncio.Lock()

        # Metrics
        self._total_buffered = 0
        self._total_flushed = 0
        self._flush_count = 0

        # Background task
        self._flush_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background flush task.

        Must be called before buffering writes. Typically called during app startup.
        """
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "WriteBufferCache started (interval=%.1fs, batch=%d)",
            self._config.flush_interval_seconds,
            self._config.flush_batch_size,
        )

    async def stop(self) -> None:
        """Stop the flush task and flush remaining writes.

        Should be called during app shutdown to ensure no writes are lost.
        """
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.force_flush()
        logger.info("WriteBufferCache stopped")

    async def buffer_upsert(
        self,
        table: str,
        data: dict[str, Any],
        key_columns: list[str],
    ) -> None:
        """Buffer an upsert (insert or update) operation.

        If a row with the same key already exists in the buffer, it will be
        replaced (last write wins).

        Args:
            table: Target table name.
            data: Row data as dict.
            key_columns: Columns that form the unique key.

        Example:
            await buffer.buffer_upsert(
                "tracks",
                {"id": 123, "title": "Song", "artist": "Artist"},
                ["id"]
            )
        """
        await self._buffer_write(WriteOperation.UPSERT, table, data, key_columns)

    async def buffer_update(
        self,
        table: str,
        data: dict[str, Any],
        key_columns: list[str],
    ) -> None:
        """Buffer an update operation.

        Only updates existing rows. If row doesn't exist, the update is a no-op.

        Args:
            table: Target table name.
            data: Columns to update.
            key_columns: Columns that identify the row.
        """
        await self._buffer_write(WriteOperation.UPDATE, table, data, key_columns)

    async def buffer_delete(
        self,
        table: str,
        key_data: dict[str, Any],
        key_columns: list[str],
    ) -> None:
        """Buffer a delete operation.

        Args:
            table: Target table name.
            key_data: Dict with key column values.
            key_columns: Columns that identify the row.

        Example:
            await buffer.buffer_delete("tracks", {"id": 123}, ["id"])
        """
        await self._buffer_write(WriteOperation.DELETE, table, key_data, key_columns)

    async def _buffer_write(
        self,
        operation: WriteOperation,
        table: str,
        data: dict[str, Any],
        key_columns: list[str],
    ) -> None:
        """Internal method to buffer a write operation."""
        # Generate unique key from key columns
        key = self._make_key(data, key_columns)

        async with self._lock:
            # Check backpressure
            total_pending = sum(len(t) for t in self._buffer.values())
            if total_pending >= self._config.max_buffer_size:
                logger.warning(
                    "WriteBuffer backpressure: %d pending (max=%d), forcing flush",
                    total_pending,
                    self._config.max_buffer_size,
                )
                # Release lock for flush
                await self._flush_internal()

            # Add to buffer (overwrites if same key exists)
            self._buffer[table][key] = PendingWrite(
                operation=operation,
                table=table,
                data=data,
                key_columns=key_columns,
            )
            self._total_buffered += 1

    def _make_key(self, data: dict[str, Any], key_columns: list[str]) -> str:
        """Generate a unique key string from key column values."""
        return "|".join(str(data.get(col, "")) for col in sorted(key_columns))

    async def force_flush(self) -> int:
        """Force an immediate flush of all buffered writes.

        Returns:
            Number of writes flushed.
        """
        async with self._lock:
            return await self._flush_internal()

    async def _flush_internal(self) -> int:
        """Internal flush method (must hold lock)."""
        if not any(self._buffer.values()):
            return 0

        start_time = time.monotonic()
        total_flushed = 0

        # Get tables in priority order
        tables = sorted(
            self._buffer.keys(),
            key=lambda t: self._config.table_priorities.get(t, 999),
        )

        try:
            async with self._session_factory() as session:
                for table in tables:
                    writes = list(self._buffer[table].values())
                    if not writes:
                        continue

                    # Limit to batch size
                    batch = writes[: self._config.flush_batch_size]

                    try:
                        flushed = await self._execute_batch(session, table, batch)
                        total_flushed += flushed

                        # Remove flushed writes from buffer
                        for write in batch:
                            key = self._make_key(write.data, write.key_columns)
                            self._buffer[table].pop(key, None)

                    except Exception as e:
                        logger.exception(
                            "Error flushing %d writes to %s: %s",
                            len(batch),
                            table,
                            e,
                        )
                        # Keep in buffer for retry
                        continue

                await session.commit()

        except Exception as e:
            logger.exception("Error during flush commit: %s", e)

        duration = time.monotonic() - start_time
        self._total_flushed += total_flushed
        self._flush_count += 1

        if total_flushed > 0:
            logger.debug(
                "Flushed %d writes in %.3fs",
                total_flushed,
                duration,
            )

        return total_flushed

    async def _execute_batch(
        self,
        session: AsyncSession,
        table: str,
        writes: list[PendingWrite],
    ) -> int:
        """Execute a batch of writes for a single table."""
        if not writes:
            return 0

        # Group by operation type
        upserts = [w for w in writes if w.operation == WriteOperation.UPSERT]
        updates = [w for w in writes if w.operation == WriteOperation.UPDATE]
        deletes = [w for w in writes if w.operation == WriteOperation.DELETE]

        count = 0

        if upserts:
            count += await self._bulk_upsert(session, table, upserts)
        if updates:
            count += await self._bulk_update(session, table, updates)
        if deletes:
            count += await self._bulk_delete(session, table, deletes)

        return count

    async def _bulk_upsert(
        self,
        session: AsyncSession,
        table: str,
        writes: list[PendingWrite],
    ) -> int:
        """Execute bulk upsert using SQLite INSERT OR REPLACE."""
        if not writes:
            return 0

        # Get all columns from first write
        columns = list(writes[0].data.keys())
        placeholders = ", ".join([f":{col}" for col in columns])
        column_names = ", ".join(columns)

        # SQLite-specific upsert syntax
        sql = f"INSERT OR REPLACE INTO {table} ({column_names}) VALUES ({placeholders})"

        for write in writes:
            await session.execute(text(sql), write.data)

        return len(writes)

    async def _bulk_update(
        self,
        session: AsyncSession,
        table: str,
        writes: list[PendingWrite],
    ) -> int:
        """Execute bulk updates."""
        if not writes:
            return 0

        for write in writes:
            # Build SET clause (exclude key columns)
            set_cols = [
                f"{col} = :{col}"
                for col in write.data.keys()
                if col not in write.key_columns
            ]
            where_cols = [f"{col} = :{col}" for col in write.key_columns]

            sql = f"UPDATE {table} SET {', '.join(set_cols)} WHERE {' AND '.join(where_cols)}"
            await session.execute(text(sql), write.data)

        return len(writes)

    async def _bulk_delete(
        self,
        session: AsyncSession,
        table: str,
        writes: list[PendingWrite],
    ) -> int:
        """Execute bulk deletes."""
        if not writes:
            return 0

        for write in writes:
            where_cols = [f"{col} = :{col}" for col in write.key_columns]
            sql = f"DELETE FROM {table} WHERE {' AND '.join(where_cols)}"
            await session.execute(text(sql), write.data)

        return len(writes)

    async def _flush_loop(self) -> None:
        """Background task that periodically flushes the buffer."""
        while self._running:
            try:
                await asyncio.sleep(self._config.flush_interval_seconds)
                if self._running:
                    await self.force_flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in flush loop: %s", e)

    async def get_buffered_value(
        self,
        table: str,
        key_data: dict[str, Any],
        key_columns: list[str],
    ) -> dict[str, Any] | None:
        """Get a buffered value that hasn't been flushed yet.

        Use this for read-after-write consistency without waiting for flush.

        Args:
            table: Table name.
            key_data: Dict with key column values.
            key_columns: Columns that form the key.

        Returns:
            The buffered data dict, or None if not in buffer.
        """
        key = self._make_key(key_data, key_columns)
        async with self._lock:
            write = self._buffer.get(table, {}).get(key)
            if write and write.operation != WriteOperation.DELETE:
                return write.data
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics.

        Returns:
            Dict with keys:
            - pending_count: Current pending writes
            - total_buffered: Total writes buffered since start
            - total_flushed: Total writes flushed to DB
            - flush_count: Number of flush operations
            - is_running: Whether buffer is active
            - pending_by_table: Pending count per table
            - config: Current configuration
        """
        pending_by_table = {
            table: len(writes)
            for table, writes in self._buffer.items()
            if writes
        }

        return {
            "pending_count": sum(pending_by_table.values()),
            "total_buffered": self._total_buffered,
            "total_flushed": self._total_flushed,
            "flush_count": self._flush_count,
            "is_running": self._running,
            "pending_by_table": pending_by_table,
            "config": {
                "max_buffer_size": self._config.max_buffer_size,
                "flush_interval_seconds": self._config.flush_interval_seconds,
                "flush_batch_size": self._config.flush_batch_size,
                "table_priorities": self._config.table_priorities,
            },
        }
