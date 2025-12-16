"""Spotify metadata cache."""

from typing import Any

from soulspot.application.cache.base_cache import InMemoryCache


class SpotifyCache:
    """Cache for Spotify API responses.

    This cache stores:
    - Track metadata
    - Album metadata
    - Artist metadata
    - Playlist metadata
    - Search results

    Cache keys are constructed from Spotify IDs to ensure
    unique caching per resource.
    """

    # Cache TTL values (in seconds)
    # Hey future me: Spotify cache TTLs reflect how often data changes
    # Tracks are stable (24h) - once published, metadata rarely changes
    # Albums are stable (24h) - album metadata rarely changes
    # Artists change occasionally (12h) - monthly listeners, images can update
    # Playlists are DYNAMIC (1h) - users add/remove tracks constantly, old cache = missing new songs
    # Search results shortest (30min) - Spotify catalog updates daily with new releases
    TRACK_TTL = 86400  # 24 hours
    ALBUM_TTL = 86400  # 24 hours (albums don't change once released)
    ARTIST_TTL = 43200  # 12 hours (artist info can get updated)
    PLAYLIST_TTL = 3600  # 1 hour (playlists change frequently)
    SEARCH_TTL = 1800  # 30 minutes

    def __init__(self) -> None:
        """Initialize Spotify cache."""
        self._cache: InMemoryCache[str, Any] = InMemoryCache()

    # Yo, these key builders use Spotify IDs which are unique and stable
    # "track:3n3Ppam7vgaVa1iaRUc9Lp" won't collide with "playlist:37i9dQZF1DXcBWIGoYBM5M"
    # WHY include limit in search key? search("beatles", 10) ≠ search("beatles", 50) results!
    def _make_track_key(self, track_id: str) -> str:
        """Make cache key for track metadata."""
        return f"spotify:track:{track_id}"

    def _make_album_key(self, album_id: str) -> str:
        """Make cache key for album metadata."""
        return f"spotify:album:{album_id}"

    def _make_artist_key(self, artist_id: str) -> str:
        """Make cache key for artist metadata."""
        return f"spotify:artist:{artist_id}"

    def _make_playlist_key(self, playlist_id: str) -> str:
        """Make cache key for playlist metadata."""
        return f"spotify:playlist:{playlist_id}"

    def _make_search_key(self, query: str, limit: int) -> str:
        """Make cache key for search results."""
        return f"spotify:search:{query}:{limit}"

    # =========================================================================
    # TRACK CACHE
    # =========================================================================

    # Hey future me: Spotify track metadata is RICH - album art, preview URLs, ISRC, etc.
    # Cache this aggressively (24h) because it saves quota and is rarely stale
    # GOTCHA: If track gets "pulled" from Spotify (rights issues), cache holds dead data
    # Consider invalidate_track() if user reports missing/wrong track
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

    async def invalidate_track(self, track_id: str) -> bool:
        """Invalidate cached track.

        Args:
            track_id: Spotify track ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_track_key(track_id)
        return await self._cache.delete(key)

    # =========================================================================
    # ALBUM CACHE
    # =========================================================================

    async def get_album(self, album_id: str) -> dict[str, Any] | None:
        """Get cached album metadata.

        Args:
            album_id: Spotify album ID

        Returns:
            Cached album data or None
        """
        key = self._make_album_key(album_id)
        return await self._cache.get(key)

    async def cache_album(self, album_id: str, album: dict[str, Any]) -> None:
        """Cache album metadata.

        Args:
            album_id: Spotify album ID
            album: Album data from Spotify
        """
        key = self._make_album_key(album_id)
        await self._cache.set(key, album, self.ALBUM_TTL)

    async def invalidate_album(self, album_id: str) -> bool:
        """Invalidate cached album.

        Args:
            album_id: Spotify album ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_album_key(album_id)
        return await self._cache.delete(key)

    # =========================================================================
    # ARTIST CACHE
    # =========================================================================

    async def get_artist(self, artist_id: str) -> dict[str, Any] | None:
        """Get cached artist metadata.

        Args:
            artist_id: Spotify artist ID

        Returns:
            Cached artist data or None
        """
        key = self._make_artist_key(artist_id)
        return await self._cache.get(key)

    async def cache_artist(self, artist_id: str, artist: dict[str, Any]) -> None:
        """Cache artist metadata.

        Args:
            artist_id: Spotify artist ID
            artist: Artist data from Spotify
        """
        key = self._make_artist_key(artist_id)
        await self._cache.set(key, artist, self.ARTIST_TTL)

    async def invalidate_artist(self, artist_id: str) -> bool:
        """Invalidate cached artist.

        Args:
            artist_id: Spotify artist ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_artist_key(artist_id)
        return await self._cache.delete(key)

    # =========================================================================
    # PLAYLIST CACHE
    # =========================================================================

    # Listen, playlists have SHORT TTL (1h) because they're living documents
    # User adds 5 tracks → sync immediately → cache still shows old version = confusion
    # WHY not 5 minutes? Balance responsiveness vs API quota (we have rate limits!)
    # For "My Discover Weekly", invalidate explicitly on Monday when Spotify refreshes it
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

    # Yo, invalidate playlist when you KNOW it changed (user just edited it)
    # Don't spam this - every invalidation = next request hits Spotify API (rate limits!)
    # Returns True if entry existed, False if wasn't cached anyway
    async def invalidate_playlist(self, playlist_id: str) -> bool:
        """Invalidate cached playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_playlist_key(playlist_id)
        return await self._cache.delete(key)

    # =========================================================================
    # SEARCH CACHE
    # =========================================================================

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

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

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
        """Get cache statistics.

        Returns:
            Dict with hits, misses, size, etc.
        """
        return self._cache.get_stats()
