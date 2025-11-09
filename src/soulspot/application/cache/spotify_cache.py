"""Spotify metadata cache."""

from typing import Any

from soulspot.application.cache.base_cache import InMemoryCache


class SpotifyCache:
    """Cache for Spotify API responses.

    This cache stores:
    - Track metadata
    - Playlist metadata
    - Search results

    Cache keys are constructed from Spotify IDs to ensure
    unique caching per resource.
    """

    # Cache TTL values (in seconds)
    TRACK_TTL = 86400  # 24 hours
    PLAYLIST_TTL = 3600  # 1 hour (playlists change frequently)
    SEARCH_TTL = 1800  # 30 minutes

    def __init__(self) -> None:
        """Initialize Spotify cache."""
        self._cache: InMemoryCache[str, Any] = InMemoryCache()

    def _make_track_key(self, track_id: str) -> str:
        """Make cache key for track metadata."""
        return f"track:{track_id}"

    def _make_playlist_key(self, playlist_id: str) -> str:
        """Make cache key for playlist metadata."""
        return f"playlist:{playlist_id}"

    def _make_search_key(self, query: str, limit: int) -> str:
        """Make cache key for search results."""
        return f"search:{query}:{limit}"

    async def get_track(self, track_id: str) -> dict[str, Any] | None:
        """Get cached track metadata.

        Args:
            track_id: Spotify track ID

        Returns:
            Cached track data or None
        """
        key = self._make_track_key(track_id)
        return await self._cache.get(key)

    async def cache_track(self, track_id: str, track: dict[str, Any]) -> None:
        """Cache track metadata.

        Args:
            track_id: Spotify track ID
            track: Track data from Spotify
        """
        key = self._make_track_key(track_id)
        await self._cache.set(key, track, self.TRACK_TTL)

    async def get_playlist(self, playlist_id: str) -> dict[str, Any] | None:
        """Get cached playlist metadata.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Cached playlist data or None
        """
        key = self._make_playlist_key(playlist_id)
        return await self._cache.get(key)

    async def cache_playlist(self, playlist_id: str, playlist: dict[str, Any]) -> None:
        """Cache playlist metadata.

        Args:
            playlist_id: Spotify playlist ID
            playlist: Playlist data from Spotify
        """
        key = self._make_playlist_key(playlist_id)
        await self._cache.set(key, playlist, self.PLAYLIST_TTL)

    async def get_search_results(
        self, query: str, limit: int = 10
    ) -> dict[str, Any] | None:
        """Get cached search results.

        Args:
            query: Search query
            limit: Number of results

        Returns:
            Cached search results or None
        """
        key = self._make_search_key(query, limit)
        return await self._cache.get(key)

    async def cache_search_results(
        self,
        query: str,
        results: dict[str, Any],
        limit: int = 10,
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            results: Search results from Spotify
            limit: Number of results
        """
        key = self._make_search_key(query, limit)
        await self._cache.set(key, results, self.SEARCH_TTL)

    async def invalidate_track(self, track_id: str) -> bool:
        """Invalidate cached track.

        Args:
            track_id: Spotify track ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_track_key(track_id)
        return await self._cache.delete(key)

    async def invalidate_playlist(self, playlist_id: str) -> bool:
        """Invalidate cached playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_playlist_key(playlist_id)
        return await self._cache.delete(key)

    async def invalidate_search(self, query: str, limit: int = 10) -> bool:
        """Invalidate cached search results.

        Args:
            query: Search query
            limit: Number of results

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_search_key(query, limit)
        return await self._cache.delete(key)

    async def clear(self) -> None:
        """Clear all cached data."""
        await self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        return await self._cache.cleanup_expired()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()
