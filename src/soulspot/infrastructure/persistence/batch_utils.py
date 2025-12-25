# Hey future me - these are THE TOOLS for reducing SQLite lock contention!
#
# SQLite locks on EVERY write. If you do 1000 INSERTs in one transaction,
# the database is locked for the ENTIRE duration. Other operations time out.
#
# SOLUTION: Commit frequently! These utilities make that easy.
#
# GOLDEN RULE: Commit after EACH logical operation, not at the end of a loop.
#
# EXAMPLE:
#   WRONG:
#     for track in tracks:
#         session.add(track)
#     await session.commit()  # Lock held for entire loop!
#
#   RIGHT:
#     for track in tracks:
#         session.add(track)
#         await session.commit()  # Lock released between items!
#
# Or use batch_process() which handles this automatically.
"""Batch processing utilities for reducing SQLite lock contention."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


async def batch_process(
    session: AsyncSession,
    items: Sequence[T],
    processor: Callable[[AsyncSession, T], Any],
    batch_size: int = 1,
    commit_after_each: bool = True,
    breather_interval: int = 10,
    breather_delay: float = 0.01,
) -> dict[str, Any]:
    """Process items in batches with commits to reduce lock time.

    Hey future me - USE THIS for any operation processing >10 items!

    SQLite locks the entire database during writes. By committing after each item
    (or small batch), we release the lock frequently, allowing other operations
    to proceed.

    Args:
        session: Database session
        items: Items to process
        processor: Async function to process each item. Called with (session, item).
                   Should NOT commit - this function handles commits.
        batch_size: Items per commit batch (default: 1 = commit after each item)
        commit_after_each: Whether to commit after each batch (default: True)
        breather_interval: Commit count interval for brief pause (default: 10)
        breather_delay: Seconds to sleep between breather intervals (default: 0.01)

    Returns:
        Dict with processing stats:
        - total: Total items processed
        - success: Successful items
        - errors: Failed items
        - error_details: List of error messages

    Example:
        async def add_track(session, track):
            session.add(TrackModel.from_entity(track))

        stats = await batch_process(session, tracks, add_track, batch_size=1)
        print(f"Added {stats['success']} tracks, {stats['errors']} errors")
    """
    stats = {
        "total": len(items),
        "success": 0,
        "errors": 0,
        "error_details": [],
    }

    current_batch = 0
    commit_count = 0

    for i, item in enumerate(items):
        try:
            await processor(session, item)
            current_batch += 1
            stats["success"] += 1

            # Commit when batch is full
            if commit_after_each and current_batch >= batch_size:
                await session.commit()
                current_batch = 0
                commit_count += 1

                # Brief pause every N commits to let other operations proceed
                if commit_count % breather_interval == 0:
                    await asyncio.sleep(breather_delay)

        except Exception as e:
            stats["errors"] += 1
            stats["error_details"].append(f"Item {i}: {e!s}")
            logger.warning("Error processing item %d: %s", i, e)

            # Rollback failed item and continue
            try:
                await session.rollback()
                current_batch = 0
            except Exception:
                pass

    # Final commit for any remaining items
    if commit_after_each and current_batch > 0:
        try:
            await session.commit()
        except Exception as e:
            stats["errors"] += current_batch
            stats["success"] -= current_batch
            logger.error("Final commit failed: %s", e)

    return stats


async def batch_insert(
    session: AsyncSession,
    models: Sequence[Any],
    batch_size: int = 50,
    breather_interval: int = 5,
) -> dict[str, Any]:
    """Insert models in batches with commits.

    Simplified version of batch_process for bulk inserts.

    Args:
        session: Database session
        models: SQLAlchemy model instances to insert
        batch_size: Models per commit (default: 50)
        breather_interval: Batches between brief pauses (default: 5)

    Returns:
        Stats dict with total, success, errors counts

    Example:
        models = [TrackModel(...) for track in tracks]
        stats = await batch_insert(session, models, batch_size=50)
    """
    stats = {"total": len(models), "success": 0, "errors": 0}

    for i in range(0, len(models), batch_size):
        batch = models[i : i + batch_size]

        try:
            session.add_all(batch)
            await session.commit()
            stats["success"] += len(batch)

            # Brief pause between batches
            if (i // batch_size + 1) % breather_interval == 0:
                await asyncio.sleep(0.01)

        except Exception as e:
            stats["errors"] += len(batch)
            logger.error("Batch insert failed at index %d: %s", i, e)

            try:
                await session.rollback()
            except Exception:
                pass

    return stats


async def batch_update(
    session: AsyncSession,
    items: Sequence[T],
    updater: Callable[[T], None],
    batch_size: int = 50,
) -> dict[str, Any]:
    """Update items in batches with commits.

    The updater function should modify the item in place.
    Items must already be attached to the session.

    Args:
        session: Database session
        items: Items to update (must be session-attached models)
        updater: Function to modify each item. Called with (item).
        batch_size: Items per commit (default: 50)

    Returns:
        Stats dict with total, success, errors counts

    Example:
        tracks = await repo.get_all()
        def update_status(track):
            track.status = "processed"
        stats = await batch_update(session, tracks, update_status)
    """
    stats = {"total": len(items), "success": 0, "errors": 0}

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        try:
            for item in batch:
                updater(item)

            await session.commit()
            stats["success"] += len(batch)

        except Exception as e:
            stats["errors"] += len(batch)
            logger.error("Batch update failed at index %d: %s", i, e)

            try:
                await session.rollback()
            except Exception:
                pass

    return stats


class IncrementalCommitter:
    """Context manager for incremental commits during long operations.

    Hey future me - use this when you can't easily restructure a loop!

    Instead of refactoring code to use batch_process, wrap your existing
    loop with this context manager.

    Example:
        async with IncrementalCommitter(session, commit_every=10) as committer:
            for track in tracks:
                session.add(track)
                await committer.mark_progress()  # Commits every 10 items
    """

    def __init__(
        self,
        session: AsyncSession,
        commit_every: int = 10,
        breather_delay: float = 0.01,
    ) -> None:
        """Initialize the committer.

        Args:
            session: Database session
            commit_every: Commit after this many mark_progress() calls
            breather_delay: Sleep duration after each commit
        """
        self._session = session
        self._commit_every = commit_every
        self._breather_delay = breather_delay
        self._count = 0
        self._commit_count = 0

    async def __aenter__(self) -> IncrementalCommitter:
        """Enter context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context - commit any remaining changes."""
        if exc_type is None and self._count > 0:
            try:
                await self._session.commit()
                self._commit_count += 1
            except Exception as e:
                logger.error("Final commit failed: %s", e)
                await self._session.rollback()
                raise

    async def mark_progress(self) -> None:
        """Mark progress and possibly commit.

        Call this after each item in your loop. Commits will happen
        automatically every `commit_every` calls.
        """
        self._count += 1

        if self._count >= self._commit_every:
            await self._session.commit()
            self._commit_count += 1
            self._count = 0

            # Brief pause to let other operations proceed
            await asyncio.sleep(self._breather_delay)

    @property
    def commits_made(self) -> int:
        """Get total commits made so far."""
        return self._commit_count
