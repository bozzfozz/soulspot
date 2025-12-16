"""Deezer metadata cache.

Hey future me - this is the Deezer-equivalent of SpotifyCache!
Caches API responses to reduce API calls and improve performance.

Deezer is more lenient with rate limits (50 req/5 sec) but caching
still helps with responsiveness and reduces unnecessary network calls.
"""

from typing import Any

from soulspot.application.cache.base_cache import InMemoryCache


class DeezerCache:
    """Cache for Deezer API responses.

    This cache stores:
    - Track metadata
    - Album metadata
    - Artist metadata
    - Playlist metadata
    - Search results
    - Chart results

    Cache keys are constructed from Deezer IDs to ensure
    unique caching per resource.
    
    Hey future me - Deezer IDs are integers (unlike Spotify's alphanumeric).
    We convert to string for cache key consistency.
    """

    # Cache TTL values (in seconds)
    # Hey future me - Deezer data is more stable than Spotify
    # Charts change daily, everything else is pretty static
    TRACK_TTL = 86400  # 24 hours
    ALBUM_TTL = 86400  # 24 hours (albums don't change once released)
    ARTIST_TTL = 43200  # 12 hours (artist info can get updated)
    PLAYLIST_TTL = 3600  # 1 hour (user playlists change frequently)
    SEARCH_TTL = 1800  # 30 minutes (catalog updates)
    CHART_TTL = 3600  # 1 hour (charts update throughout day)
    USER_TTL = 300  # 5 minutes (user data changes frequently)

    def __init__(self) -> None:
        """Initialize Deezer cache."""
        self._cache: InMemoryCache[str, Any] = InMemoryCache()

    # Hey future me - we use "deezer:" prefix to avoid collision with other caches
    # if they share the same InMemoryCache instance in the future.
    def _make_track_key(self, track_id: int | str) -> str:
        """Make cache key for track metadata."""
        return f"deezer:track:{track_id}"

    def _make_album_key(self, album_id: int | str) -> str:
        """Make cache key for album metadata."""
        return f"deezer:album:{album_id}"

    def _make_artist_key(self, artist_id: int | str) -> str:
        """Make cache key for artist metadata."""
        return f"deezer:artist:{artist_id}"

    def _make_playlist_key(self, playlist_id: int | str) -> str:
        """Make cache key for playlist metadata."""
        return f"deezer:playlist:{playlist_id}"

    def _make_search_key(self, entity_type: str, query: str, limit: int) -> str:
        """Make cache key for search results."""
        return f"deezer:search:{entity_type}:{query}:{limit}"

    def _make_chart_key(self, chart_type: str) -> str:
        """Make cache key for chart results."""
        return f"deezer:chart:{chart_type}"

    # =========================================================================
    # TRACK CACHE
    # =========================================================================

    async def get_track(self, track_id: int | str) -> dict[str, Any] | None:
        """Get cached track metadata."""
        key = self._make_track_key(track_id)
        return await self._cache.get(key)

    async def cache_track(self, track_id: int | str, track: dict[str, Any]) -> None:
        """Cache track metadata."""
        key = self._make_track_key(track_id)
        await self._cache.set(key, track, self.TRACK_TTL)

    async def invalidate_track(self, track_id: int | str) -> bool:
        """Invalidate cached track data.

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_track_key(track_id)
        return await self._cache.delete(key)

    # =========================================================================
    # ALBUM CACHE
    # =========================================================================

    async def get_album(self, album_id: int | str) -> dict[str, Any] | None:
        """Get cached album metadata."""
        key = self._make_album_key(album_id)
        return await self._cache.get(key)

    async def cache_album(self, album_id: int | str, album: dict[str, Any]) -> None:
        """Cache album metadata."""
        key = self._make_album_key(album_id)
        await self._cache.set(key, album, self.ALBUM_TTL)

    async def invalidate_album(self, album_id: int | str) -> bool:
        """Invalidate cached album data.

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_album_key(album_id)
        return await self._cache.delete(key)

    # =========================================================================
    # ARTIST CACHE
    # =========================================================================

    async def get_artist(self, artist_id: int | str) -> dict[str, Any] | None:
        """Get cached artist metadata."""
        key = self._make_artist_key(artist_id)
        return await self._cache.get(key)

    async def cache_artist(
        self, artist_id: int | str, artist: dict[str, Any]
    ) -> None:
        """Cache artist metadata."""
        key = self._make_artist_key(artist_id)
        await self._cache.set(key, artist, self.ARTIST_TTL)

    async def invalidate_artist(self, artist_id: int | str) -> bool:
        """Invalidate cached artist data.

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_artist_key(artist_id)
        return await self._cache.delete(key)

    # =========================================================================
    # PLAYLIST CACHE
    # =========================================================================

    async def get_playlist(self, playlist_id: int | str) -> dict[str, Any] | None:
        """Get cached playlist metadata.

        Args:
            playlist_id: Deezer playlist ID

        Returns:
            Cached playlist data or None
        """
        key = self._make_playlist_key(playlist_id)
        return await self._cache.get(key)

    async def cache_playlist(
        self, playlist_id: int | str, playlist: dict[str, Any]
    ) -> None:
        """Cache playlist metadata.

        Args:
            playlist_id: Deezer playlist ID
            playlist: Playlist data from Deezer
        """
        key = self._make_playlist_key(playlist_id)
        await self._cache.set(key, playlist, self.PLAYLIST_TTL)

    async def invalidate_playlist(self, playlist_id: int | str) -> bool:
        """Invalidate cached playlist.

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_playlist_key(playlist_id)
        return await self._cache.delete(key)

    # =========================================================================
    # SEARCH CACHE
    # =========================================================================

    async def get_search_results(
        self, entity_type: str, query: str, limit: int
    ) -> list[dict[str, Any]] | None:
        """Get cached search results.

        Args:
            entity_type: "track", "album", or "artist"
            query: Search query string
            limit: Result limit (part of cache key!)

        Returns:
            Cached results or None
        """
        key = self._make_search_key(entity_type, query, limit)
        return await self._cache.get(key)

    async def cache_search_results(
        self,
        entity_type: str,
        query: str,
        limit: int,
        results: list[dict[str, Any]],
    ) -> None:
        """Cache search results.

        Args:
            entity_type: "track", "album", or "artist"
            query: Search query string
            limit: Result limit
            results: Search results to cache
        """
        key = self._make_search_key(entity_type, query, limit)
        await self._cache.set(key, results, self.SEARCH_TTL)

    async def invalidate_search(
        self, entity_type: str, query: str, limit: int
    ) -> bool:
        """Invalidate cached search results.

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_search_key(entity_type, query, limit)
        return await self._cache.delete(key)

    # =========================================================================
    # CHART CACHE
    # =========================================================================

    async def get_chart(self, chart_type: str) -> dict[str, Any] | None:
        """Get cached chart data.

        Args:
            chart_type: "tracks", "albums", or "artists"

        Returns:
            Cached chart data or None
        """
        key = self._make_chart_key(chart_type)
        return await self._cache.get(key)

    async def cache_chart(
        self, chart_type: str, chart_data: dict[str, Any]
    ) -> None:
        """Cache chart data.

        Args:
            chart_type: "tracks", "albums", or "artists"
            chart_data: Chart data to cache
        """
        key = self._make_chart_key(chart_type)
        await self._cache.set(key, chart_data, self.CHART_TTL)

    async def invalidate_all_charts(self) -> None:
        """Invalidate all cached chart data.

        Hey future me - call this when force-refreshing charts!
        """
        for chart_type in ["tracks", "albums", "artists"]:
            key = self._make_chart_key(chart_type)
            await self._cache.delete(key)

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    async def clear(self) -> None:
        """Clear entire cache.

        Hey future me - use sparingly! Clears ALL cached Deezer data.
        """
        await self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        return await self._cache.cleanup_expired()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, size, etc.
        """
        return self._cache.get_stats()
