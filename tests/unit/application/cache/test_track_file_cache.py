"""Tests for TrackFileCache."""

import tempfile
from pathlib import Path

import pytest

from soulspot.application.cache.track_file_cache import TrackFileCache
from soulspot.domain.value_objects import FilePath, TrackId


@pytest.fixture
def cache():
    """Create a TrackFileCache instance."""
    return TrackFileCache()


@pytest.fixture
def track_id():
    """Create a sample track ID."""
    return TrackId.generate()


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"test content for checksum")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestTrackFileCache:
    """Tests for TrackFileCache."""

    async def test_cache_and_get_file_path(self, cache, track_id):
        """Test caching and retrieving file path."""
        file_path = FilePath("/path/to/music/song.mp3")

        await cache.cache_file_path(track_id, file_path)
        result = await cache.get_file_path(track_id)

        assert result is not None
        assert str(result) == "/path/to/music/song.mp3"

    async def test_get_nonexistent_file_path(self, cache, track_id):
        """Test getting a file path that doesn't exist in cache."""
        result = await cache.get_file_path(track_id)
        assert result is None

    async def test_cache_and_get_file_metadata(self, cache, track_id):
        """Test caching and retrieving file metadata."""
        metadata = {
            "size": 5000000,
            "format": "mp3",
            "bitrate": 320,
            "duration": 240,
        }

        await cache.cache_file_metadata(track_id, metadata)
        result = await cache.get_file_metadata(track_id)

        assert result is not None
        assert result["size"] == 5000000
        assert result["format"] == "mp3"
        assert result["bitrate"] == 320

    async def test_cache_and_get_checksum(self, cache):
        """Test caching and retrieving file checksum."""
        file_path = "/path/to/file.mp3"
        checksum = "abc123def456"

        await cache.cache_checksum(file_path, checksum)
        result = await cache.get_checksum(file_path)

        assert result is not None
        assert result == "abc123def456"

    async def test_compute_and_cache_checksum(self, cache, temp_file):
        """Test computing and caching file checksum."""
        checksum = await cache.compute_and_cache_checksum(temp_file)

        # Verify checksum is computed
        assert checksum is not None
        assert len(checksum) == 32  # MD5 hash length

        # Verify checksum is cached
        cached = await cache.get_checksum(temp_file)
        assert cached == checksum

    async def test_compute_and_cache_checksum_uses_cache(self, cache, temp_file):
        """Test that compute_and_cache_checksum uses cached value if available."""
        # Cache a specific checksum
        expected_checksum = "cached123"
        await cache.cache_checksum(temp_file, expected_checksum)

        # Compute should return cached value
        checksum = await cache.compute_and_cache_checksum(temp_file)
        assert checksum == expected_checksum

    async def test_is_file_downloaded_true(self, cache, track_id, temp_file):
        """Test checking if file is downloaded (exists and cached)."""
        file_path = FilePath(temp_file)
        await cache.cache_file_path(track_id, file_path)

        result = await cache.is_file_downloaded(track_id)
        assert result is True

    async def test_is_file_downloaded_false_not_cached(self, cache, track_id):
        """Test checking if file is downloaded when not cached."""
        result = await cache.is_file_downloaded(track_id)
        assert result is False

    async def test_is_file_downloaded_false_file_not_exists(self, cache, track_id):
        """Test checking if file is downloaded when cached but file doesn't exist."""
        file_path = FilePath("/nonexistent/path/song.mp3")
        await cache.cache_file_path(track_id, file_path)

        result = await cache.is_file_downloaded(track_id)
        assert result is False

    async def test_invalidate_track(self, cache, track_id):
        """Test invalidating all cached data for a track."""
        file_path = FilePath("/path/to/song.mp3")
        metadata = {"size": 5000000}

        await cache.cache_file_path(track_id, file_path)
        await cache.cache_file_metadata(track_id, metadata)

        result = await cache.invalidate_track(track_id)
        assert result is True

        # Verify all data is removed
        assert await cache.get_file_path(track_id) is None
        assert await cache.get_file_metadata(track_id) is None

    async def test_invalidate_nonexistent_track(self, cache, track_id):
        """Test invalidating a track that doesn't exist."""
        result = await cache.invalidate_track(track_id)
        assert result is False

    async def test_clear_all(self, cache, track_id):
        """Test clearing all cached data."""
        file_path = FilePath("/path/to/song.mp3")
        await cache.cache_file_path(track_id, file_path)
        await cache.cache_checksum("/path/to/file.mp3", "checksum123")

        await cache.clear()

        assert await cache.get_file_path(track_id) is None
        assert await cache.get_checksum("/path/to/file.mp3") is None

    async def test_ttl_expiration(self, cache, track_id, monkeypatch):
        """Test that cached entries expire after TTL."""
        import time

        # Temporarily reduce TTL for testing
        original_ttl = cache.FILE_PATH_TTL
        cache.FILE_PATH_TTL = 1  # 1 second

        # Mock time to control expiry
        current_time = time.time()

        def mock_time():
            return current_time

        monkeypatch.setattr(time, "time", mock_time)

        file_path = FilePath("/path/to/song.mp3")
        await cache.cache_file_path(track_id, file_path)

        # Should be available immediately
        assert await cache.get_file_path(track_id) is not None

        # Advance time past TTL
        current_time += 2

        # Should be expired
        assert await cache.get_file_path(track_id) is None

        # Restore original TTL
        cache.FILE_PATH_TTL = original_ttl

    async def test_cleanup_expired(self, cache, monkeypatch):
        """Test cleaning up expired entries."""
        import time

        # Temporarily reduce TTL for testing
        original_ttl = cache.FILE_PATH_TTL
        cache.FILE_PATH_TTL = 1  # 1 second

        # Mock time to control expiry
        current_time = time.time()

        def mock_time():
            return current_time

        monkeypatch.setattr(time, "time", mock_time)

        track_id1 = TrackId.generate()
        track_id2 = TrackId.generate()

        await cache.cache_file_path(track_id1, FilePath("/path/1.mp3"))
        await cache.cache_file_path(track_id2, FilePath("/path/2.mp3"))

        # Advance time past TTL
        current_time += 2

        # Cleanup should remove expired entries
        removed = await cache.cleanup_expired()
        assert removed == 2

        # Restore original TTL
        cache.FILE_PATH_TTL = original_ttl

    async def test_get_stats(self, cache, track_id):
        """Test getting cache statistics."""
        await cache.cache_file_path(track_id, FilePath("/path/to/song.mp3"))
        await cache.cache_checksum("/path/to/file.mp3", "checksum123")

        stats = cache.get_stats()
        assert "total_entries" in stats
        assert stats["total_entries"] == 2

    async def test_cache_key_format(self, cache, track_id):
        """Test that cache keys are properly formatted."""
        # Test file path key
        path_key = cache._make_file_path_key(track_id)
        assert path_key.startswith("file_path:")

        # Test checksum key
        checksum_key = cache._make_checksum_key("/path/to/file.mp3")
        assert checksum_key == "checksum:/path/to/file.mp3"

        # Test metadata key
        meta_key = cache._make_metadata_key(track_id)
        assert meta_key.startswith("metadata:")
