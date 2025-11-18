"""Tests for base cache implementation."""

import asyncio
from typing import Any

import pytest

from soulspot.application.cache.base_cache import InMemoryCache


class TestInMemoryCache:
    """Test InMemoryCache implementation."""

    @pytest.fixture
    def cache(self) -> InMemoryCache[str, str]:
        """Create cache instance."""
        return InMemoryCache[str, str]()

    async def test_set_and_get(self, cache: InMemoryCache[str, str]) -> None:
        """Test setting and getting cache entries."""
        # Set a value with ttl
        await cache.set("key1", "value1", ttl_seconds=3600)

        # Get the value
        result = await cache.get("key1")
        assert result == "value1"

    async def test_get_nonexistent_key(self, cache: InMemoryCache[str, str]) -> None:
        """Test getting a non-existent key returns None."""
        result = await cache.get("nonexistent")
        assert result is None

    async def test_delete(self, cache: InMemoryCache[str, str]) -> None:
        """Test deleting cache entries."""
        # Set a value
        await cache.set("key1", "value1", ttl_seconds=3600)

        # Delete it
        await cache.delete("key1")

        # Verify it's gone
        result = await cache.get("key1")
        assert result is None

    async def test_clear(self, cache: InMemoryCache[str, str]) -> None:
        """Test clearing all cache entries."""
        # Set multiple values
        await cache.set("key1", "value1", ttl_seconds=3600)
        await cache.set("key2", "value2", ttl_seconds=3600)
        await cache.set("key3", "value3", ttl_seconds=3600)

        # Clear the cache
        await cache.clear()

        # Verify all entries are gone
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None

    async def test_has(self, cache: InMemoryCache[str, str]) -> None:
        """Test checking if key exists."""
        # Set a value
        await cache.set("key1", "value1", ttl_seconds=3600)

        # Check if it exists
        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

    async def test_ttl_expiration(self) -> None:
        """Test that entries expire after TTL."""
        # Create cache
        cache = InMemoryCache[str, str]()

        # Set a value with 0.1 second TTL
        await cache.set("key1", "value1", ttl_seconds=0.05)

        # Value should exist immediately
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(0.06)

        # Value should be gone
        assert await cache.get("key1") is None

    async def test_custom_ttl(self) -> None:
        """Test setting custom TTL per entry."""
        # Create cache
        cache = InMemoryCache[str, str]()

        # Set value with custom 0.05 second TTL
        await cache.set("key1", "value1", ttl_seconds=0.05)

        # Value should exist immediately
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(0.06)

        # Value should be gone
        assert await cache.get("key1") is None

    async def test_cleanup_expired_entries(self) -> None:
        """Test cleanup of expired entries."""
        # Create cache
        cache = InMemoryCache[str, str]()

        # Set multiple values with 0.05 second TTL
        await cache.set("key1", "value1", ttl_seconds=0.05)
        await cache.set("key2", "value2", ttl_seconds=0.05)

        # Wait for expiration
        await asyncio.sleep(0.06)

        # Cleanup expired entries
        count = await cache.cleanup_expired()

        # Both should be gone
        assert count == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    async def test_size(self, cache: InMemoryCache[str, str]) -> None:
        """Test getting cache size."""
        # Get stats
        stats = cache.get_stats()
        assert stats["total_entries"] == 0

        # Add entries
        await cache.set("key1", "value1", ttl_seconds=3600)
        await cache.set("key2", "value2", ttl_seconds=3600)

        # Size should be 2
        stats = cache.get_stats()
        assert stats["total_entries"] == 2

        # Delete one
        await cache.delete("key1")

        # Size should be 1
        stats = cache.get_stats()
        assert stats["total_entries"] == 1

    async def test_stats(self, cache: InMemoryCache[str, str]) -> None:
        """Test getting cache statistics."""
        # Add entries
        await cache.set("key1", "value1", ttl_seconds=3600)
        await cache.set("key2", "value2", ttl_seconds=3600)
        await cache.set("key3", "value3", ttl_seconds=3600)

        # Get stats
        stats = cache.get_stats()

        # Should have all 3 entries
        assert stats["total_entries"] == 3
        assert stats["active_entries"] == 3
        assert stats["expired_entries"] == 0

    async def test_concurrent_access(self) -> None:
        """Test concurrent access to cache."""
        cache = InMemoryCache[str, int]()

        # Set initial value
        await cache.set("counter", 0, ttl_seconds=3600)

        # Concurrent get operations
        async def get_value() -> int | None:
            return await cache.get("counter")

        results = await asyncio.gather(*[get_value() for _ in range(10)])

        # All should get the same value
        assert all(r == 0 for r in results)

    async def test_different_types(self) -> None:
        """Test cache with different value types."""
        # Integer cache
        int_cache = InMemoryCache[str, int]()
        await int_cache.set("count", 42, ttl_seconds=3600)
        assert await int_cache.get("count") == 42

        # Dict cache
        dict_cache = InMemoryCache[str, dict[str, Any]]()
        await dict_cache.set("data", {"name": "test", "value": 123}, ttl_seconds=3600)
        result = await dict_cache.get("data")
        assert result is not None
        assert result["name"] == "test"
        assert result["value"] == 123

        # List cache
        list_cache = InMemoryCache[str, list[str]]()
        await list_cache.set("items", ["a", "b", "c"], ttl_seconds=3600)
        assert await list_cache.get("items") == ["a", "b", "c"]

    async def test_update_existing_key(self, cache: InMemoryCache[str, str]) -> None:
        """Test updating an existing key."""
        # Set initial value
        await cache.set("key1", "value1", ttl_seconds=3600)
        assert await cache.get("key1") == "value1"

        # Update value
        await cache.set("key1", "value2", ttl_seconds=3600)
        assert await cache.get("key1") == "value2"

    async def test_delete_nonexistent_key(self, cache: InMemoryCache[str, str]) -> None:
        """Test deleting a non-existent key doesn't raise error."""
        # Should not raise exception
        await cache.delete("nonexistent")
