"""Search Result Cache - MOVED to application/cache/search_cache.py!

⚠️ DEPRECATED LOCATION - Import from cache/ instead! ⚠️

This file is kept for backward compatibility only.
All imports should use:
    from soulspot.application.cache import SearchCache, get_search_cache

MOVED: 3. Januar 2026 as part of cache consolidation.
DELETE AFTER: All imports migrated to new location.
"""

import warnings

# Re-export from new location for backward compatibility
from soulspot.application.cache.search_cache import (
    SearchCache,
    SearchCacheEntry,
    SearchCacheStats,
    get_search_cache,
    reset_search_cache,
)

# Issue deprecation warning on import
warnings.warn(
    "Importing from soulspot.application.services.search_cache is deprecated. "
    "Use soulspot.application.cache.search_cache instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy aliases for backward compatibility
CacheEntry = SearchCacheEntry
CacheStats = SearchCacheStats

__all__ = [
    "CacheEntry",
    "CacheStats",
    "SearchCache",
    "SearchCacheEntry",
    "SearchCacheStats",
    "get_search_cache",
    "reset_search_cache",
]
