"""Base cache interface and in-memory implementation."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


@dataclass
class CacheEntry(Generic[V]):
    """Cache entry with value and metadata."""

    value: V
    created_at: float
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > (self.created_at + self.ttl_seconds)


class BaseCache(ABC, Generic[K, V]):
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

    def __init__(self) -> None:
        """Initialize in-memory cache."""
        self._cache: dict[K, CacheEntry[V]] = {}
        self._lock = asyncio.Lock()

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

    async def set(self, key: K, value: V, ttl_seconds: int = 3600) -> None:
        """Set value in cache."""
        async with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl_seconds,
            )

    async def delete(self, key: K) -> bool:
        """Delete value from cache."""
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
        """Check if key exists in cache."""
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
