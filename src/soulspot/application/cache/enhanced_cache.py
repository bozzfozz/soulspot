"""Enhanced caching utilities with warming and advanced eviction strategies.

This module provides production-ready caching improvements including:
- Cache warming for hot paths
- LRU eviction policy
- Cache hit/miss metrics
- Batch cache operations
"""

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    writes: int = 0

    # Hey future me, this calculates hit rate as a percentage (0-100). Division by zero guard is
    # CRITICAL - if cache is brand new (no hits or misses), total is 0 and we return 0.0 instead
    # of crashing! The formula is simple: hits / (hits + misses) * 100. So 80 hits and 20 misses
    # gives 80% hit rate. Use this metric to decide if cache size is adequate!
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    # Yo, reset() zeroes out ALL metrics! Use this for testing or when you want fresh stats after
    # deployment/config change. Be careful - you lose historical data. If you need trends over time,
    # export metrics before resetting!
    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.writes = 0


@dataclass
class LRUCacheEntry[V]:
    """Cache entry with value and metadata for LRU cache."""

    value: V
    created_at: float
    ttl_seconds: int
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    # Listen up, is_expired checks if entry passed its TTL. Same logic as base_cache but lives in
    # LRUCacheEntry because LRU needs metadata (access_count, last_accessed) that basic CacheEntry
    # doesn't have. Don't confuse with touch() - is_expired is about TIME expiry, touch is about
    # LRU access tracking!
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > (self.created_at + self.ttl_seconds)

    # Hey future me, touch() updates LRU metadata when entry is accessed! Increments access_count
    # and refreshes last_accessed timestamp. This is how LRU knows which items to evict - entries
    # with old last_accessed get kicked out first. Call this EVERY time you read a cached value
    # or LRU won't work correctly (it'll evict frequently-used items!). The access_count is mainly
    # for debugging/stats - the real LRU decision is based on last_accessed time.
    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()


class LRUCache[K, V]:
    """LRU (Least Recently Used) cache implementation with metrics.

    This cache automatically evicts the least recently used items when
    the maximum size is reached. It also tracks cache performance metrics
    for monitoring and optimization.

    Features:
    - Automatic LRU eviction when max_size is reached
    - TTL-based expiration
    - Hit/miss/eviction metrics
    - Thread-safe operations with async locks
    - Batch operations for efficiency
    """

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of entries before LRU eviction starts
        """
        self._cache: OrderedDict[K, LRUCacheEntry[V]] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._metrics = CacheMetrics()

    async def get(self, key: K) -> V | None:
        """Get value from cache with LRU tracking.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                self._metrics.misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._metrics.misses += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._metrics.hits += 1
            return entry.value

    async def set(self, key: K, value: V, ttl_seconds: int = 3600) -> None:
        """Set value in cache with LRU eviction if needed.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        async with self._lock:
            # If key exists, remove it first to update position
            if key in self._cache:
                del self._cache[key]

            # Evict LRU entry if at max size
            if len(self._cache) >= self._max_size:
                # Remove the first item (least recently used)
                self._cache.popitem(last=False)
                self._metrics.evictions += 1

            self._cache[key] = LRUCacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl_seconds,
            )
            self._metrics.writes += 1

    async def set_batch(self, items: dict[K, V], ttl_seconds: int = 3600) -> None:
        """Set multiple values in cache efficiently.

        Args:
            items: Dictionary of key-value pairs to cache
            ttl_seconds: Time to live in seconds for all items
        """
        async with self._lock:
            current_time = time.time()
            for key, value in items.items():
                # If key exists, remove it first
                if key in self._cache:
                    del self._cache[key]

                # Evict LRU entry if at max size
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                    self._metrics.evictions += 1

                self._cache[key] = LRUCacheEntry(
                    value=value,
                    created_at=current_time,
                    ttl_seconds=ttl_seconds,
                )
                self._metrics.writes += 1

    async def delete(self, key: K) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: K) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        value = await self.get(key)
        return value is not None

    async def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics.

        Returns:
            CacheMetrics object with current metrics
        """
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        self._metrics.reset()

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics.

        Returns:
            Dictionary with cache statistics including metrics
        """
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "max_size": self._max_size,
            "utilization_percent": (total_entries / self._max_size) * 100,
            "metrics": {
                "hits": self._metrics.hits,
                "misses": self._metrics.misses,
                "hit_rate": self._metrics.hit_rate,
                "evictions": self._metrics.evictions,
                "writes": self._metrics.writes,
            },
        }


class CacheWarmer[K, V]:
    """Utility for pre-warming caches with hot path data.

    This class helps populate caches proactively during application startup
    or periodic maintenance windows to improve cache hit rates for frequently
    accessed data.
    """

    def __init__(self, cache: LRUCache[K, V]) -> None:
        """Initialize cache warmer.

        Args:
            cache: The cache instance to warm
        """
        self._cache = cache

    async def warm_from_loader(
        self,
        keys: list[K],
        loader: Any,  # Callable[[K], Awaitable[V | None]]
        ttl_seconds: int = 3600,
    ) -> int:
        """Warm cache by loading values for given keys.

        Args:
            keys: List of cache keys to warm
            loader: Async function that loads a value for a key
            ttl_seconds: TTL for cached values

        Returns:
            Number of entries successfully warmed
        """
        warmed_count = 0
        items = {}

        for key in keys:
            value = await loader(key)
            if value is not None:
                items[key] = value
                warmed_count += 1

        if items:
            await self._cache.set_batch(items, ttl_seconds=ttl_seconds)

        return warmed_count

    async def warm_from_dict(
        self,
        items: dict[K, V],
        ttl_seconds: int = 3600,
    ) -> int:
        """Warm cache with pre-loaded data.

        Args:
            items: Dictionary of key-value pairs to cache
            ttl_seconds: TTL for cached values

        Returns:
            Number of entries warmed
        """
        await self._cache.set_batch(items, ttl_seconds=ttl_seconds)
        return len(items)
