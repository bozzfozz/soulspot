"""Caching layer - Cache implementations for reducing API calls."""

from soulspot.application.cache.base_cache import BaseCache
from soulspot.application.cache.deezer_cache import DeezerCache

# NOTE: DeezerChartsCache and DeezerNewReleasesCache removed
# - Charts: showed generic browse content, feature removed
# - New Releases: now handled by NewReleasesSyncWorker
from soulspot.application.cache.musicbrainz_cache import MusicBrainzCache
from soulspot.application.cache.search_cache import (
    SearchCache,
    SearchCacheEntry,
    SearchCacheStats,
    get_search_cache,
    reset_search_cache,
)
from soulspot.application.cache.spotify_cache import SpotifyCache
from soulspot.application.cache.track_file_cache import TrackFileCache

__all__ = [
    "BaseCache",
    "DeezerCache",
    # "DeezerChartsCache" removed - Charts feature removed
    # "DeezerNewReleasesCache" removed - use NewReleasesCache in workers/
    "MusicBrainzCache",
    "SearchCache",
    "SearchCacheEntry",
    "SearchCacheStats",
    "SpotifyCache",
    "TrackFileCache",
    "get_search_cache",
    "reset_search_cache",
]
