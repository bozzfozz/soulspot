"""MusicBrainz response cache."""

from typing import Any

from soulspot.application.cache.base_cache import InMemoryCache


class MusicBrainzCache:
    """Cache for MusicBrainz API responses.

    This cache stores:
    - Recording lookups by ISRC
    - Recording search results
    - Release (album) lookups
    - Artist lookups

    Cache keys are constructed from query parameters to ensure
    unique caching per request type.
    """

    # Cache TTL values (in seconds)
    RECORDING_TTL = 86400  # 24 hours
    RELEASE_TTL = 86400  # 24 hours
    ARTIST_TTL = 604800  # 7 days
    SEARCH_TTL = 3600  # 1 hour (searches may change)

    def __init__(self) -> None:
        """Initialize MusicBrainz cache."""
        self._cache: InMemoryCache[str, Any] = InMemoryCache()

    def _make_recording_key(self, isrc: str) -> str:
        """Make cache key for recording lookup by ISRC."""
        return f"recording:isrc:{isrc}"

    def _make_search_key(self, artist: str, title: str) -> str:
        """Make cache key for recording search."""
        return f"search:{artist}:{title}"

    def _make_release_key(self, mbid: str) -> str:
        """Make cache key for release lookup."""
        return f"release:{mbid}"

    def _make_artist_key(self, mbid: str) -> str:
        """Make cache key for artist lookup."""
        return f"artist:{mbid}"

    async def get_recording_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """Get cached recording by ISRC.

        Args:
            isrc: ISRC code

        Returns:
            Cached recording data or None
        """
        key = self._make_recording_key(isrc)
        return await self._cache.get(key)

    async def cache_recording_by_isrc(
        self, isrc: str, recording: dict[str, Any]
    ) -> None:
        """Cache recording lookup by ISRC.

        Args:
            isrc: ISRC code
            recording: Recording data from MusicBrainz
        """
        key = self._make_recording_key(isrc)
        await self._cache.set(key, recording, self.RECORDING_TTL)

    async def get_search_results(
        self, artist: str, title: str
    ) -> list[dict[str, Any]] | None:
        """Get cached search results.

        Args:
            artist: Artist name
            title: Track title

        Returns:
            Cached search results or None
        """
        key = self._make_search_key(artist, title)
        return await self._cache.get(key)

    async def cache_search_results(
        self,
        artist: str,
        title: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Cache search results.

        Args:
            artist: Artist name
            title: Track title
            results: Search results from MusicBrainz
        """
        key = self._make_search_key(artist, title)
        await self._cache.set(key, results, self.SEARCH_TTL)

    async def get_release(self, mbid: str) -> dict[str, Any] | None:
        """Get cached release.

        Args:
            mbid: MusicBrainz release ID

        Returns:
            Cached release data or None
        """
        key = self._make_release_key(mbid)
        return await self._cache.get(key)

    async def cache_release(self, mbid: str, release: dict[str, Any]) -> None:
        """Cache release lookup.

        Args:
            mbid: MusicBrainz release ID
            release: Release data from MusicBrainz
        """
        key = self._make_release_key(mbid)
        await self._cache.set(key, release, self.RELEASE_TTL)

    async def get_artist(self, mbid: str) -> dict[str, Any] | None:
        """Get cached artist.

        Args:
            mbid: MusicBrainz artist ID

        Returns:
            Cached artist data or None
        """
        key = self._make_artist_key(mbid)
        return await self._cache.get(key)

    async def cache_artist(self, mbid: str, artist: dict[str, Any]) -> None:
        """Cache artist lookup.

        Args:
            mbid: MusicBrainz artist ID
            artist: Artist data from MusicBrainz
        """
        key = self._make_artist_key(mbid)
        await self._cache.set(key, artist, self.ARTIST_TTL)

    async def invalidate_recording(self, isrc: str) -> bool:
        """Invalidate cached recording.

        Args:
            isrc: ISRC code

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_recording_key(isrc)
        return await self._cache.delete(key)

    async def invalidate_search(self, artist: str, title: str) -> bool:
        """Invalidate cached search results.

        Args:
            artist: Artist name
            title: Track title

        Returns:
            True if invalidated, False if not found
        """
        key = self._make_search_key(artist, title)
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
