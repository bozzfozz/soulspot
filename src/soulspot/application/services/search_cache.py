"""Search Result Cache - caches slskd search results to avoid re-searches.

Hey future me - this service CACHES search results from slskd!

The problem: Each slskd search takes 10-60 seconds (Soulseek P2P network delay).
Users searching the same track multiple times waste time and network resources.
If download fails, user has to wait for another search.

The solution: SearchCache stores results keyed by query:
- TTL-based expiration (default: 15 minutes)
- Query normalization (lowercase, trim, remove extra spaces)
- Memory-bounded (max entries, LRU eviction)
- Hit/miss stats for monitoring

USE CASES:
1. User searches "Pink Floyd - Comfortably Numb", views results, doesn't download
2. User comes back 5 minutes later, same search → INSTANT results from cache
3. Download fails, user retries → cached results still available
4. Different query variations normalized: "pink floyd comfortably numb" == previous

CACHE KEY STRATEGY:
- Normalize query: lowercase, collapse whitespace, trim
- Include search options: format filter, min bitrate
- Hash for compact storage

EVICTION:
- TTL expiration (stale results become irrelevant)
- LRU for memory management
- Manual clear on demand

THREAD SAFETY:
- Uses asyncio.Lock for concurrent access
- Safe for multiple workers accessing same cache
"""

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with metadata.

    Hey future me - tracks when entry was created and last accessed!
    """

    query: str
    results: list[dict[str, Any]]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    hit_count: int = 0

    @property
    def age_seconds(self) -> float:
        """How old is this entry in seconds."""
        return (datetime.now(UTC) - self.created_at).total_seconds()

    def touch(self) -> None:
        """Update last accessed time and increment hit count."""
        self.last_accessed = datetime.now(UTC)
        self.hit_count += 1


@dataclass
class CacheStats:
    """Statistics for the search cache.

    Hey future me - track hit rate for optimization!
    """

    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_entries: int = 0
    total_results_cached: int = 0
    oldest_entry_age_seconds: float = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        if self.total_queries == 0:
            return 0.0
        return (self.cache_hits / self.total_queries) * 100


class SearchCache:
    """In-memory cache for slskd search results.

    Hey future me - this is the CENTRAL search cache!

    Usage:
        cache = SearchCache(ttl_seconds=900, max_entries=100)

        # Check cache before searching
        results = await cache.get("pink floyd comfortably numb")
        if results is None:
            results = await slskd_client.search(query)
            await cache.put(query, results)

        # Get stats
        stats = cache.get_stats()
        print(f"Hit rate: {stats.hit_rate}%")

    Configuration:
        ttl_seconds: How long entries live (default: 900 = 15 min)
        max_entries: Max cache size (default: 100)
        normalize_queries: Whether to normalize queries (default: True)
    """

    def __init__(
        self,
        ttl_seconds: int = 900,
        max_entries: int = 100,
        normalize_queries: bool = True,
    ) -> None:
        """Initialize the search cache.

        Args:
            ttl_seconds: Entry TTL in seconds (default: 15 minutes)
            max_entries: Maximum number of cached searches (default: 100)
            normalize_queries: Normalize queries before caching (default: True)
        """
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._normalize = normalize_queries
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()

    def _normalize_query(self, query: str) -> str:
        """Normalize a search query for consistent caching.

        Hey future me - makes different query variations hit same cache!
        "Pink Floyd - Comfortably Numb" → "pink floyd comfortably numb"
        """
        if not self._normalize:
            return query

        # Lowercase
        normalized = query.lower()
        # Remove common separators (treat as spaces)
        for sep in ["-", "–", "—", "_", ":"]:
            normalized = normalized.replace(sep, " ")
        # Collapse multiple spaces
        normalized = " ".join(normalized.split())
        # Trim
        normalized = normalized.strip()

        return normalized

    def _make_cache_key(self, query: str, **options: Any) -> str:
        """Create cache key from query and options.

        Hey future me - includes options so different filters = different cache entries!
        """
        normalized = self._normalize_query(query)

        # Sort options for consistent key
        opts_str = "|".join(
            f"{k}={v}" for k, v in sorted(options.items()) if v is not None
        )

        # Combine and hash for compact key
        key_input = f"{normalized}|{opts_str}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]

    async def get(self, query: str, **options: Any) -> list[dict[str, Any]] | None:
        """Get cached search results.

        Hey future me - returns None if not cached or expired!

        Args:
            query: Search query
            **options: Search options (format filter, etc.)

        Returns:
            Cached results or None if not found/expired
        """
        key = self._make_cache_key(query, **options)

        async with self._lock:
            self._stats.total_queries += 1

            entry = self._cache.get(key)
            if entry is None:
                self._stats.cache_misses += 1
                logger.debug(f"Cache MISS for query: {query[:50]}...")
                return None

            # Check TTL
            if datetime.now(UTC) - entry.created_at > self._ttl:
                # Expired - remove and return miss
                del self._cache[key]
                self._stats.cache_misses += 1
                logger.debug(f"Cache EXPIRED for query: {query[:50]}...")
                return None

            # Cache hit!
            entry.touch()
            self._cache.move_to_end(key)  # LRU: move to end
            self._stats.cache_hits += 1

            logger.debug(
                f"Cache HIT for query: {query[:50]}... "
                f"({len(entry.results)} results, age={entry.age_seconds:.0f}s)"
            )
            return entry.results

    async def put(
        self, query: str, results: list[dict[str, Any]], **options: Any
    ) -> None:
        """Store search results in cache.

        Hey future me - handles eviction if cache is full!

        Args:
            query: Search query
            results: Search results to cache
            **options: Search options
        """
        key = self._make_cache_key(query, **options)

        async with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self._max_entries:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1
                logger.debug(
                    f"Evicted oldest cache entry (total: {self._stats.evictions})"
                )

            # Store new entry
            self._cache[key] = CacheEntry(
                query=query,
                results=results,
            )

            logger.debug(
                f"Cached {len(results)} results for query: {query[:50]}... "
                f"(cache size: {len(self._cache)})"
            )

    async def invalidate(self, query: str, **options: Any) -> bool:
        """Invalidate a specific cache entry.

        Hey future me - use when results might be stale!

        Returns:
            True if entry was removed, False if not found
        """
        key = self._make_cache_key(query, **options)

        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Invalidated cache for query: {query[:50]}...")
                return True
            return False

    async def clear(self) -> int:
        """Clear all cache entries.

        Hey future me - use for cache reset!

        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cache entries")
            return count

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Hey future me - call periodically to free memory!

        Returns:
            Number of entries removed
        """
        now = datetime.now(UTC)
        removed = 0

        async with self._lock:
            keys_to_remove = [
                key
                for key, entry in self._cache.items()
                if now - entry.created_at > self._ttl
            ]
            for key in keys_to_remove:
                del self._cache[key]
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} expired cache entries")

        return removed

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Hey future me - useful for monitoring!
        """
        stats = CacheStats(
            total_queries=self._stats.total_queries,
            cache_hits=self._stats.cache_hits,
            cache_misses=self._stats.cache_misses,
            total_entries=len(self._cache),
            evictions=self._stats.evictions,
        )

        # Calculate total results and oldest entry
        if self._cache:
            stats.total_results_cached = sum(
                len(e.results) for e in self._cache.values()
            )
            oldest = min(e.created_at for e in self._cache.values())
            stats.oldest_entry_age_seconds = (
                datetime.now(UTC) - oldest
            ).total_seconds()

        return stats


# =============================================================================
# GLOBAL SEARCH CACHE INSTANCE
# =============================================================================
# Hey future me - single cache instance shared across all workers!
# Initialize in lifecycle.py or get via dependency injection.
# Default config: 15 min TTL, 100 max entries.

_search_cache: SearchCache | None = None


def get_search_cache() -> SearchCache:
    """Get the global search cache instance.

    Hey future me - creates cache on first call (lazy init)!
    """
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache(ttl_seconds=900, max_entries=100)
    return _search_cache


def reset_search_cache() -> None:
    """Reset the global search cache (for testing).

    Hey future me - use in tests to get fresh cache!
    """
    global _search_cache
    _search_cache = None
