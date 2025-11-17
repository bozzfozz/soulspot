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

    async def flush(self) -> BatchResult[R]:
        """Manually flush all pending items.

        Returns:
            BatchResult with the results of processing the batch
        """
        async with self._lock:
            return await self._flush_internal()

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

    def get_pending_count(self) -> int:
        """Get the number of pending items.

        Returns:
            Number of items waiting to be processed
        """
        return len(self._pending)

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

    async def _fetch_albums_batch(self, _album_ids: list[str]) -> list[Any]:
        """Fetch multiple albums from Spotify API.

        Args:
            _album_ids: List of Spotify album IDs

        Returns:
            List of album data from Spotify
        """
        # Spotify API supports fetching up to 20 albums at once
        return []

    async def _fetch_artists_batch(self, _artist_ids: list[str]) -> list[Any]:
        """Fetch multiple artists from Spotify API.

        Args:
            artist_ids: List of Spotify artist IDs

        Returns:
            List of artist data from Spotify
        """
        # Spotify API supports fetching up to 50 artists at once
        return []

    async def add_track(self, track_id: str) -> BatchResult[Any] | None:
        """Add a track to the batch queue.

        Args:
            track_id: Spotify track ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._track_processor.add(track_id)

    async def add_album(self, album_id: str) -> BatchResult[Any] | None:
        """Add an album to the batch queue.

        Args:
            album_id: Spotify album ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._album_processor.add(album_id)

    async def add_artist(self, artist_id: str) -> BatchResult[Any] | None:
        """Add an artist to the batch queue.

        Args:
            artist_id: Spotify artist ID

        Returns:
            BatchResult if batch was processed, None otherwise
        """
        return await self._artist_processor.add(artist_id)

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
