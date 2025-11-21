"""Track file cache for downloaded files."""

import hashlib
from pathlib import Path
from typing import Any

from soulspot.application.cache.base_cache import InMemoryCache
from soulspot.domain.value_objects import FilePath, TrackId


class TrackFileCache:
    """Cache for track file locations and metadata.

    This cache stores:
    - Track file paths
    - File checksums
    - File metadata (size, format, bitrate)

    This helps avoid redundant downloads and enables quick
    file lookup for already downloaded tracks.
    """

    # Cache TTL values (in seconds)
    # Hey future me: These TTLs are LONG because files don't move often
    # File paths cached 7 days - files sit in download folder for weeks
    # Checksums only 24h - WHY shorter? Because files can be replaced/re-downloaded
    # If checksum is stale, we just recompute (few seconds) - not a big deal
    FILE_PATH_TTL = 604800  # 7 days
    CHECKSUM_TTL = 86400  # 24 hours

    def __init__(self) -> None:
        """Initialize track file cache."""
        self._cache: InMemoryCache[str, Any] = InMemoryCache()

    # Yo, these key builders separate concerns - track location vs file integrity
    # "file_path:{track_id}" stores WHERE file is
    # "checksum:{file_path}" stores file integrity hash
    # "metadata:{track_id}" stores audio properties (bitrate, format, etc.)
    def _make_file_path_key(self, track_id: TrackId) -> str:
        """Make cache key for file path."""
        return f"file_path:{track_id}"

    def _make_checksum_key(self, file_path: str) -> str:
        """Make cache key for file checksum."""
        return f"checksum:{file_path}"

    def _make_metadata_key(self, track_id: TrackId) -> str:
        """Make cache key for file metadata."""
        return f"metadata:{track_id}"

    # Hey future me: This prevents redundant downloads!
    # Before searching Soulseek, check is_file_downloaded() - maybe you already have it
    # GOTCHA: Cache might say "yes" but file got deleted manually - always verify Path.exists()
    # That's why is_file_downloaded() does BOTH checks (cache + filesystem)
    async def get_file_path(self, track_id: TrackId) -> FilePath | None:
        """Get cached file path for track.

        Args:
            track_id: Track ID

        Returns:
            Cached file path or None
        """
        key = self._make_file_path_key(track_id)
        path_str = await self._cache.get(key)
        return FilePath(path_str) if path_str else None

    async def cache_file_path(self, track_id: TrackId, file_path: FilePath) -> None:
        """Cache file path for track.

        Args:
            track_id: Track ID
            file_path: Path to downloaded file
        """
        key = self._make_file_path_key(track_id)
        await self._cache.set(key, str(file_path), self.FILE_PATH_TTL)

    async def get_file_metadata(self, track_id: TrackId) -> dict[str, Any] | None:
        """Get cached file metadata.

        Args:
            track_id: Track ID

        Returns:
            Cached file metadata or None
        """
        key = self._make_metadata_key(track_id)
        return await self._cache.get(key)

    async def cache_file_metadata(
        self,
        track_id: TrackId,
        metadata: dict[str, Any],
    ) -> None:
        """Cache file metadata.

        Args:
            track_id: Track ID
            metadata: File metadata (size, format, bitrate, etc.)
        """
        key = self._make_metadata_key(track_id)
        await self._cache.set(key, metadata, self.FILE_PATH_TTL)

    # Listen up future me: MD5 checksums for INTEGRITY not security (that's why usedforsecurity=False)
    # We detect if download corrupted (network glitch, disk failure) - MD5 is perfect for this
    # WHY cache checksums? Computing MD5 of 50MB FLAC takes seconds - don't repeat unnecessarily
    # GOTCHA: If file modified (e.g., re-encoded), checksum changes - cache becomes stale!
    async def get_checksum(self, file_path: str) -> str | None:
        """Get cached file checksum.

        Args:
            file_path: Path to file

        Returns:
            Cached MD5 checksum or None
        """
        key = self._make_checksum_key(file_path)
        return await self._cache.get(key)

    async def cache_checksum(self, file_path: str, checksum: str) -> None:
        """Cache file checksum.

        Args:
            file_path: Path to file
            checksum: MD5 checksum of file
        """
        key = self._make_checksum_key(file_path)
        await self._cache.set(key, checksum, self.CHECKSUM_TTL)

    # Yo, this is the checksum computer - reads file in 4KB chunks to avoid memory explosion
    # WHY 4KB? Good balance - smaller = more syscalls, larger = memory pressure
    # The "nosec B324" comment tells bandit security scanner "yes we know MD5 is weak cryptographically,
    # but we're using it for file integrity not passwords!" Otherwise bandit screams every build
    # Automatically caches result so next call is instant
    async def compute_and_cache_checksum(self, file_path: str) -> str:
        """Compute and cache file checksum.

        Args:
            file_path: Path to file

        Returns:
            MD5 checksum of file
        """
        # Check cache first
        cached = await self.get_checksum(file_path)
        if cached:
            return cached

        # Compute checksum
        # MD5 is used for file integrity checking, not security
        md5 = hashlib.md5(usedforsecurity=False)  # nosec B324
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)

        checksum = md5.hexdigest()

        # Cache result
        await self.cache_checksum(file_path, checksum)

        return checksum

    # Hey future me: This is your "do we already have this track?" check
    # Prevents downloading same song twice! Check this BEFORE queuing download
    # Does TWO validations: cache says yes AND file actually exists on disk
    # WHY both? User might delete file manually, cache doesn't know - we'd return True for missing file!
    async def is_file_downloaded(self, track_id: TrackId) -> bool:
        """Check if track file is already downloaded.

        Args:
            track_id: Track ID

        Returns:
            True if file exists and is cached
        """
        file_path = await self.get_file_path(track_id)
        if not file_path:
            return False

        # Verify file actually exists
        return Path(str(file_path)).exists()

    async def invalidate_track(self, track_id: TrackId) -> bool:
        """Invalidate all cached data for a track.

        Args:
            track_id: Track ID

        Returns:
            True if any data was invalidated
        """
        path_key = self._make_file_path_key(track_id)
        meta_key = self._make_metadata_key(track_id)

        path_deleted = await self._cache.delete(path_key)
        meta_deleted = await self._cache.delete(meta_key)

        return path_deleted or meta_deleted

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
