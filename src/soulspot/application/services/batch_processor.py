"""Batch processing utilities for external API calls.

This module provides batch processing capabilities to reduce the number of
API calls to external services like Spotify and MusicBrainz, improving
performance and respecting rate limits more effectively.

Key features:
- Batch multiple API requests into single calls
- Automatic batching with configurable size limits
- Rate limiting integration
- Error handling and partial failure support
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


# Hey future me, this is the batch result dataclass! Uses new Python 3.12+ generic syntax [R] which
# is cleaner than TypeVar. Holds successful results and failed items with their exceptions. Properties
# calculate counts on the fly instead of storing - saves memory but recomputes each access. success_rate
# as percentage is nice for UI display. Division by zero check prevents crash on empty batch. The
# failed list stores tuples of (item, exception) so you know both WHAT failed and WHY. field(default_factory=list)
# prevents mutable default argument bug (all instances would share same list!). Immutable after creation
# which is good for thread safety. This is pure data class, no behavior/methods. Consider adding
# success/failure predicates or combining multiple batch results for aggregate stats?
@dataclass
class BatchResult[R]:
    """Result of a batch operation.

    Attributes:
        successful: List of successful results
        failed: List of items that failed with their errors
        total_items: Total number of items in the batch
        success_count: Number of successful operations
        failure_count: Number of failed operations
    """

    successful: list[R] = field(default_factory=list)
    failed: list[tuple[Any, Exception]] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        """Total number of items processed."""
        return len(self.successful) + len(self.failed)

    @property
    def success_count(self) -> int:
        """Number of successful operations."""
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        """Number of failed operations."""
        return len(self.failed)

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.success_count / self.total_items) * 100


class BatchProcessor[T, R]:
    """Generic batch processor for API operations.

    This class accumulates items and processes them in batches to reduce
    the number of API calls and improve overall performance.

    Example:
        async def fetch_tracks(track_ids: list[str]) -> list[Track]:
            # API call to fetch multiple tracks
            ...

        processor = BatchProcessor(
            batch_size=50,
            processor_func=fetch_tracks,
            max_wait_time=5.0
        )

        # Add items one by one
        for track_id in track_ids:
            await processor.add(track_id)

        # Process remaining items
        result = await processor.flush()
    """

    def __init__(
        self,
        batch_size: int = 50,
        processor_func: Any = None,  # Callable[[list[T]], Awaitable[list[R]]]
        max_wait_time: float = 5.0,
        auto_flush: bool = True,
    ) -> None:
        """Initialize batch processor.

        Args:
            batch_size: Maximum number of items per batch
            processor_func: Async function that processes a batch of items
            max_wait_time: Maximum time to wait before auto-flushing (seconds)
            auto_flush: Whether to automatically flush when batch_size is reached
        """
        self._batch_size = batch_size
        self._processor_func = processor_func
        self._max_wait_time = max_wait_time
        self._auto_flush = auto_flush

        self._pending: list[T] = []
        self._lock = asyncio.Lock()
        self._last_flush_time = asyncio.get_event_loop().time()

    # Listen up! This is the core batch accumulation logic! add() appends item to pending list. If
    # auto_flush enabled and batch reaches batch_size, automatically processes and clears batch. Uses
    # asyncio.Lock to prevent race conditions (two coroutines adding simultaneously). Returns BatchResult
    # if auto-flushed, None otherwise. The lock context manager ensures only one coroutine modifies
    # _pending at a time. This is async but could block on lock acquisition if another task holds it.
    # Consider timeout on lock.acquire() to prevent deadlock? The batch_size check uses >= not == so
    # you can add multiple items and trigger flush. _flush_internal must be called within lock! No
    # validation that item is correct type T - Python generics are hints only, not enforced at runtime.
    async def add(self, item: T) -> BatchResult[R] | None:
        """Add an item to the batch.

        If auto_flush is enabled and the batch is full, it will be processed
        automatically and the result returned.

        Args:
            item: Item to add to the batch

        Returns:
            BatchResult if batch was auto-flushed, None otherwise
        """
        async with self._lock:
            self._pending.append(item)

            if self._auto_flush and len(self._pending) >= self._batch_size:
                return await self._flush_internal()

        return None

    # Yo check this - adds single item to batch and auto-flushes if batch is full
    # Returns BatchResult if we auto-flushed, None if just queued the item
    # Uses async lock to prevent race conditions - thread-safe!
    # Important: Auto-flush only happens if auto_flush=True in constructor
    async def add_batch(self, items: list[T]) -> list[BatchResult[R]]:
        """Add multiple items at once.

        This will automatically split items into multiple batches if needed.

        Args:
            items: List of items to add

        Returns:
            List of BatchResults, one for each batch processed
        """
        results = []

        async with self._lock:
            self._pending.extend(items)

            if self._auto_flush:
                while len(self._pending) >= self._batch_size:
                    result = await self._flush_internal()
                    if result:
                        results.append(result)

        return results

    # Hey, manual flush trigger - processes ALL pending items regardless of batch_size
    # WHY manual? Sometimes you want to force processing before shutdown or on timer
    # Lock ensures no other coroutine is modifying _pending during flush
    async def flush(self) -> BatchResult[R]:
        """Manually flush all pending items.

        Returns:
            BatchResult with the results of processing the batch
        """
        async with self._lock:
            return await self._flush_internal()

    # Yo the internal flush logic! Slices first batch_size items from pending, processes them, then
    # removes from _pending. Must be called within lock (caller's responsibility!). The slicing [:batch_size]
    # means if you have 150 items and batch_size=50, this processes 50 and leaves 100. Updates last_flush_time
    # for max_wait_time tracking. Returns empty BatchResult if nothing pending. Calls processor_func which
    # should return list[R] but we don't validate that! If processor fails completely (raises exception),
    # marks ALL items as failed with same error. No partial failure handling - it's all or nothing! Consider
    # processing items individually and collecting per-item results? The batch = self._pending[:batch_size]
    # creates new list (copy) so modifying batch doesn't affect _pending. Good defensive programming.
    async def _flush_internal(self) -> BatchResult[R]:
        """Internal flush implementation (must be called within lock)."""
        if not self._pending:
            return BatchResult()

        if not self._processor_func:
            raise ValueError("No processor function configured")

        batch = self._pending[: self._batch_size]
        self._pending = self._pending[self._batch_size :]
        self._last_flush_time = asyncio.get_event_loop().time()

        result = BatchResult[R]()

        try:
            # Process the batch
            results = await self._processor_func(batch)
            result.successful.extend(results)
        except Exception as e:
            # If batch processing fails completely, mark all as failed
            for item in batch:
                result.failed.append((item, e))

        return result

    # Listen, time-based flush - checks if we waited too long and forces flush
    # WHY max_wait_time? Don't want items stuck in queue forever if batch never fills
    # Example: You add 10 items but batch_size=50 - without timeout, they sit forever!
    # Returns None if didn't flush (not enough time passed yet)
    async def flush_if_needed(self) -> BatchResult[R] | None:
        """Flush pending items if max wait time has been exceeded.

        Returns:
            BatchResult if flushed, None otherwise
        """
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            if (
                self._pending
                and (current_time - self._last_flush_time) >= self._max_wait_time
            ):
                return await self._flush_internal()
        return None

    # Hey simple getter - returns count without lock (racy but fast)
    # WHY no lock? Reading int is atomic in Python, and exact count doesn't matter for monitoring
    # This is for UI display, not critical logic
    def get_pending_count(self) -> int:
        """Get the number of pending items.

        Returns:
            Number of items waiting to be processed
        """
        return len(self._pending)

    # Yo cleanup method - flushes remaining items before shutting down
    # Always call this in finally blocks or shutdown hooks to avoid data loss!
    # Alias for flush() - could be removed, but explicit names are good UX
    async def close(self) -> BatchResult[R]:
        """Close the batch processor and flush remaining items.

        Returns:
            BatchResult with the final batch results
        """
        return await self.flush()


class SpotifyBatchProcessor:
    """Specialized batch processor for Spotify API calls.

    Spotify API allows fetching multiple tracks, albums, or artists in a single
    request (up to 50 items). This processor optimizes those calls.
    """

    def __init__(self, spotify_client: Any) -> None:  # SpotifyClient
        """Initialize Spotify batch processor.

        Args:
            spotify_client: Instance of SpotifyClient
        """
        self._spotify_client = spotify_client
        self._track_processor = BatchProcessor[str, Any](
            batch_size=50,
            processor_func=self._fetch_tracks_batch,
        )
        self._album_processor = BatchProcessor[str, Any](
            batch_size=20,
            processor_func=self._fetch_albums_batch,
        )
        self._artist_processor = BatchProcessor[str, Any](
            batch_size=50,
            processor_func=self._fetch_artists_batch,
        )

    # Hey future me: Spotify batch fetcher - PLACEHOLDER implementation!
    # WHY return empty list? Real implementation would call spotify_client.get_tracks(track_ids)
    # Spotify API supports up to 50 tracks per request - that's why batch_size=50
    # TODO: Wire up actual Spotify client when implementing this
    # The _track_ids param is prefixed with _ because we're not using it yet
    async def _fetch_tracks_batch(self, _track_ids: list[str]) -> list[Any]:
        """Fetch multiple tracks from Spotify API.

        Args:
            _track_ids: List of Spotify track IDs

        Returns:
            List of track data from Spotify
        """
        # Spotify API supports fetching up to 50 tracks at once
        # This would call something like: spotify_client.get_tracks(track_ids)
        # For now, returning empty list as placeholder
        return []

    # Yo album fetcher stub - Spotify albums endpoint
    # WHY batch_size=20 not 50? Spotify album API limit is 20 per request (different from tracks!)
    # Album objects are bigger (contains track list) so Spotify caps lower
    async def _fetch_albums_batch(self, _album_ids: list[str]) -> list[Any]:
        """Fetch multiple albums from Spotify API.

        Args:
            _album_ids: List of Spotify album IDs

        Returns:
            List of album data from Spotify
        """
        # Spotify API supports fetching up to 20 albums at once
        return []

    # Listen, artist fetcher stub - back to 50 limit like tracks
    # Artists are smaller objects (just metadata, no track lists)
    async def _fetch_artists_batch(self, _artist_ids: list[str]) -> list[Any]:
        """Fetch multiple artists from Spotify API.

        Args:
            artist_ids: List of Spotify artist IDs

        Returns:
            List of artist data from Spotify
        """
        # Spotify API supports fetching up to 50 artists at once
        return []

    # Hey simple delegation - wraps underlying BatchProcessor.add()
    # Returns BatchResult if auto-flushed, otherwise None
    async def add_track(self, track_id: str) -> BatchResult[Any] | None:
        """Add a track to the batch queue.

        Args:
            track_id: Spotify track ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._track_processor.add(track_id)

    # Yo album queue delegation
    async def add_album(self, album_id: str) -> BatchResult[Any] | None:
        """Add an album to the batch queue.

        Args:
            album_id: Spotify album ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._album_processor.add(album_id)

    # Listen artist queue delegation
    async def add_artist(self, artist_id: str) -> BatchResult[Any] | None:
        """Add an artist to the batch queue.

        Args:
            artist_id: Spotify artist ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._artist_processor.add(artist_id)

    # Hey, flushes ALL three processors (tracks, albums, artists) and returns their results
    # WHY dict return? Caller can see results per entity type separately
    # Call this before shutdown or when you want to force-process everything queued
    async def flush_all(self) -> dict[str, BatchResult[Any]]:
        """Flush all pending batches.

        Returns:
            Dictionary with batch results for each entity type
        """
        return {
            "tracks": await self._track_processor.flush(),
            "albums": await self._album_processor.flush(),
            "artists": await self._artist_processor.flush(),
        }
