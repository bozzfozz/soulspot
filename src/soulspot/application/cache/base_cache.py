"""Base cache interface and in-memory implementation."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


@dataclass
class CacheEntry[V]:
    """Cache entry with value and metadata."""

    value: V
    created_at: float
    ttl_seconds: int

    # Hey future me, simple time-based expiry check here. We compare CURRENT time.time() against
    # created_at + ttl. If NOW is GREATER, it's expired. Uses Unix timestamps (floats) so no
    # timezone drama. One gotcha: if system clock jumps backwards (NTP sync, manual change),
    # unexpired entries might suddenly appear expired! Hasn't been a problem yet but watch out
    # in containerized environments with dodgy time sync.
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > (self.created_at + self.ttl_seconds)


class BaseCache[K, V](ABC):
    """Base cache interface for all cache implementations."""

    @abstractmethod
    async def get(self, key: K) -> V | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    async def set(self, key: K, value: V, ttl_seconds: int = 3600) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        pass

    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from cache."""
        pass

    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        pass


class InMemoryCache(BaseCache[K, V]):
    """In-memory cache implementation using dictionary.

    This is a simple implementation for development and testing.
    For production use, consider using Redis or Memcached.
    """

    # Listen up future me, this is IN-MEMORY ONLY! Server restart = all cache lost. No persistence,
    # no sharing across processes/servers. The _lock is CRITICAL for async safety - without it,
    # two coroutines could read-modify-write the dict simultaneously and corrupt state. I learned
    # this the hard way when cache.get() returned half-written CacheEntry objects. Always use
    # "async with self._lock" before touching self._cache! For production, move to Redis.
    def __init__(self) -> None:
        """Initialize in-memory cache."""
        self._cache: dict[K, CacheEntry[V]] = {}
        self._lock = asyncio.Lock()

    # Yo, get() does TWO checks: exists AND not expired. If entry is expired, we DELETE it immediately
    # (cache eviction on read). This means get() has side effects! It modifies the cache even though
    # it's named like a pure getter. Returns None for both "not found" and "found but expired" - caller
    # can't tell the difference. The lock ensures no race where another task reads the entry between
    # our expiry check and deletion.
    async def get(self, key: K) -> V | None:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            if entry.is_expired():
                del self._cache[key]
                return None

            return entry.value

    # Hey, set() ALWAYS overwrites existing key without warning! No "insert only if missing" mode.
    # Default TTL is 3600 seconds (1 hour) - don't forget to pass custom ttl_seconds for data that
    # expires faster/slower! created_at is set to NOW (time.time()) so clock changes affect all
    # entries equally. The lock prevents concurrent sets from creating partial CacheEntry objects.
    async def set(self, key: K, value: V, ttl_seconds: int = 3600) -> None:
        """Set value in cache."""
        async with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl_seconds,
            )

    # Yo, delete returns bool so caller knows if key existed. Idempotent - calling twice returns
    # False second time. Unlike get(), this doesn't check expiry - it deletes even if expired.
    # Useful for explicit invalidation when you KNOW data is stale.
    async def delete(self, key: K) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    # Listen, clear() nukes EVERYTHING including non-expired entries! Use carefully - this is for
    # emergency cache invalidation or test cleanup. After clear(), get_stats() will show 0 entries.
    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()

    # Hey future me, exists() just calls get() and checks if result is None. This means it has the
    # SAME side effect - expired entries get deleted! So exists() can modify cache state. Could
    # optimize by checking dict key + expiry without deleting, but consistency with get() is more
    # important. If get() returns something, exists() should return True.
    async def exists(self, key: K) -> bool:
        """Check if key exists in cache."""
        value = await self.get(key)
        return value is not None

    # Yo, cleanup_expired is for MANUAL garbage collection! Unlike get() which deletes on-demand,
    # this scans ALL entries and removes expired ones in bulk. Good for background tasks or before
    # get_stats(). Returns count so you can monitor "how much junk accumulated". The comprehension
    # creates list of keys FIRST, then deletes - don't delete while iterating dict or it'll crash!
    # Lock prevents cleanup from interfering with concurrent get/set operations.
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

    # Listen up, get_stats() is NOT locked! It reads self._cache.values() without acquiring lock,
    # so it might see inconsistent state if concurrent operations are running. We accept this for
    # performance - stats are for monitoring/debugging, not critical data. The "expired_entries"
    # count includes entries that WOULD be deleted by cleanup but haven't been yet. This is a
    # SYNCHRONOUS method (not async) because it's meant for quick health checks - no blocking I/O.
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
        }
