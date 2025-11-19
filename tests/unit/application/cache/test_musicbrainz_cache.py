"""Tests for MusicBrainzCache."""

import pytest

from soulspot.application.cache.musicbrainz_cache import MusicBrainzCache


@pytest.fixture
def cache():
    """Create a MusicBrainzCache instance."""
    return MusicBrainzCache()


class TestMusicBrainzCache:
    """Tests for MusicBrainzCache."""

    async def test_cache_and_get_recording_by_isrc(self, cache):
        """Test caching and retrieving recording by ISRC."""
        recording_data = {
            "id": "mb-recording-123",
            "title": "Test Song",
            "isrc-list": ["USRC12345678"],
        }

        await cache.cache_recording_by_isrc("USRC12345678", recording_data)
        result = await cache.get_recording_by_isrc("USRC12345678")

        assert result is not None
        assert result["id"] == "mb-recording-123"
        assert result["title"] == "Test Song"

    async def test_get_nonexistent_recording(self, cache):
        """Test getting a recording that doesn't exist in cache."""
        result = await cache.get_recording_by_isrc("NONEXISTENT")
        assert result is None

    async def test_cache_and_get_search_results(self, cache):
        """Test caching and retrieving search results."""
        search_results = [
            {"id": "rec1", "title": "Song 1"},
            {"id": "rec2", "title": "Song 2"},
        ]

        await cache.cache_search_results("Test Artist", "Test Song", search_results)
        result = await cache.get_search_results("Test Artist", "Test Song")

        assert result is not None
        assert len(result) == 2
        assert result[0]["id"] == "rec1"

    async def test_cache_and_get_release(self, cache):
        """Test caching and retrieving release."""
        release_data = {
            "id": "mb-release-123",
            "title": "Test Album",
            "date": "2023-01-15",
        }

        await cache.cache_release("mb-release-123", release_data)
        result = await cache.get_release("mb-release-123")

        assert result is not None
        assert result["id"] == "mb-release-123"
        assert result["title"] == "Test Album"

    async def test_cache_and_get_artist(self, cache):
        """Test caching and retrieving artist."""
        artist_data = {
            "id": "mb-artist-123",
            "name": "Test Artist",
        }

        await cache.cache_artist("mb-artist-123", artist_data)
        result = await cache.get_artist("mb-artist-123")

        assert result is not None
        assert result["id"] == "mb-artist-123"
        assert result["name"] == "Test Artist"

    async def test_invalidate_recording(self, cache):
        """Test invalidating cached recording."""
        recording_data = {"id": "rec123", "title": "Test"}

        await cache.cache_recording_by_isrc("ISRC123", recording_data)
        assert await cache.get_recording_by_isrc("ISRC123") is not None

        result = await cache.invalidate_recording("ISRC123")
        assert result is True
        assert await cache.get_recording_by_isrc("ISRC123") is None

    async def test_invalidate_nonexistent_recording(self, cache):
        """Test invalidating a recording that doesn't exist."""
        result = await cache.invalidate_recording("NONEXISTENT")
        assert result is False

    async def test_invalidate_search(self, cache):
        """Test invalidating cached search results."""
        search_results = [{"id": "rec1"}]

        await cache.cache_search_results("Artist", "Title", search_results)
        assert await cache.get_search_results("Artist", "Title") is not None

        result = await cache.invalidate_search("Artist", "Title")
        assert result is True
        assert await cache.get_search_results("Artist", "Title") is None

    async def test_clear_all(self, cache):
        """Test clearing all cached data."""
        await cache.cache_recording_by_isrc("ISRC1", {"id": "rec1"})
        await cache.cache_release("rel1", {"id": "rel1"})
        await cache.cache_artist("art1", {"id": "art1"})

        await cache.clear()

        assert await cache.get_recording_by_isrc("ISRC1") is None
        assert await cache.get_release("rel1") is None
        assert await cache.get_artist("art1") is None

    async def test_ttl_expiration_recording(self, cache, monkeypatch):
        """Test that cached recordings expire after TTL."""
        import time

        # Temporarily reduce TTL for testing
        original_ttl = cache.RECORDING_TTL
        cache.RECORDING_TTL = 1  # 1 second

        # Mock time to control expiry
        current_time = time.time()

        def mock_time():
            return current_time

        monkeypatch.setattr(time, "time", mock_time)

        recording_data = {"id": "rec123", "title": "Test"}
        await cache.cache_recording_by_isrc("ISRC123", recording_data)

        # Should be available immediately
        assert await cache.get_recording_by_isrc("ISRC123") is not None

        # Advance time past TTL
        current_time += 2

        # Should be expired
        assert await cache.get_recording_by_isrc("ISRC123") is None

        # Restore original TTL
        cache.RECORDING_TTL = original_ttl

    async def test_cleanup_expired(self, cache, monkeypatch):
        """Test cleaning up expired entries."""
        import time

        # Temporarily reduce TTL for testing
        original_ttl = cache.RECORDING_TTL
        cache.RECORDING_TTL = 1  # 1 second

        # Mock time to control expiry
        current_time = time.time()

        def mock_time():
            return current_time

        monkeypatch.setattr(time, "time", mock_time)

        await cache.cache_recording_by_isrc("ISRC1", {"id": "rec1"})
        await cache.cache_recording_by_isrc("ISRC2", {"id": "rec2"})

        # Advance time past TTL
        current_time += 2

        # Cleanup should remove expired entries
        removed = await cache.cleanup_expired()
        assert removed == 2

        # Restore original TTL
        cache.RECORDING_TTL = original_ttl

    async def test_get_stats(self, cache):
        """Test getting cache statistics."""
        await cache.cache_recording_by_isrc("ISRC1", {"id": "rec1"})
        await cache.cache_release("rel1", {"id": "rel1"})

        stats = cache.get_stats()
        assert "total_entries" in stats
        assert stats["total_entries"] == 2

    async def test_cache_key_format(self, cache):
        """Test that cache keys are properly formatted."""
        # Test recording key
        rec_key = cache._make_recording_key("ISRC123")
        assert rec_key == "recording:isrc:ISRC123"

        # Test search key
        search_key = cache._make_search_key("Artist", "Title")
        assert search_key == "search:Artist:Title"

        # Test release key
        release_key = cache._make_release_key("mbid123")
        assert release_key == "release:mbid123"

        # Test artist key
        artist_key = cache._make_artist_key("mbid456")
        assert artist_key == "artist:mbid456"
