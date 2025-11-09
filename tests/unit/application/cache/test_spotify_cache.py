"""Tests for SpotifyCache."""

import asyncio

import pytest

from soulspot.application.cache.spotify_cache import SpotifyCache


@pytest.fixture
def cache():
    """Create a SpotifyCache instance."""
    return SpotifyCache()


class TestSpotifyCache:
    """Tests for SpotifyCache."""

    async def test_cache_and_get_track(self, cache):
        """Test caching and retrieving track metadata."""
        track_data = {"id": "track123", "name": "Test Song", "artists": [{"name": "Test Artist"}]}

        await cache.cache_track("track123", track_data)
        result = await cache.get_track("track123")

        assert result is not None
        assert result["id"] == "track123"
        assert result["name"] == "Test Song"

    async def test_get_nonexistent_track(self, cache):
        """Test getting a track that doesn't exist in cache."""
        result = await cache.get_track("nonexistent")
        assert result is None

    async def test_cache_and_get_playlist(self, cache):
        """Test caching and retrieving playlist metadata."""
        playlist_data = {
            "id": "playlist123",
            "name": "My Playlist",
            "tracks": {"total": 10},
        }

        await cache.cache_playlist("playlist123", playlist_data)
        result = await cache.get_playlist("playlist123")

        assert result is not None
        assert result["id"] == "playlist123"
        assert result["name"] == "My Playlist"

    async def test_cache_and_get_search_results(self, cache):
        """Test caching and retrieving search results."""
        search_results = {
            "tracks": {
                "items": [{"id": "track1", "name": "Song 1"}],
                "total": 1,
            }
        }

        await cache.cache_search_results("test query", search_results, limit=10)
        result = await cache.get_search_results("test query", limit=10)

        assert result is not None
        assert result["tracks"]["total"] == 1

    async def test_search_results_different_limits(self, cache):
        """Test that search results with different limits are cached separately."""
        results_10 = {"tracks": {"items": ["item1"] * 10}}
        results_20 = {"tracks": {"items": ["item1"] * 20}}

        await cache.cache_search_results("query", results_10, limit=10)
        await cache.cache_search_results("query", results_20, limit=20)

        result_10 = await cache.get_search_results("query", limit=10)
        result_20 = await cache.get_search_results("query", limit=20)

        assert len(result_10["tracks"]["items"]) == 10
        assert len(result_20["tracks"]["items"]) == 20

    async def test_invalidate_track(self, cache):
        """Test invalidating cached track."""
        track_data = {"id": "track123", "name": "Test Song"}

        await cache.cache_track("track123", track_data)
        assert await cache.get_track("track123") is not None

        result = await cache.invalidate_track("track123")
        assert result is True
        assert await cache.get_track("track123") is None

    async def test_invalidate_nonexistent_track(self, cache):
        """Test invalidating a track that doesn't exist."""
        result = await cache.invalidate_track("nonexistent")
        assert result is False

    async def test_invalidate_playlist(self, cache):
        """Test invalidating cached playlist."""
        playlist_data = {"id": "playlist123", "name": "My Playlist"}

        await cache.cache_playlist("playlist123", playlist_data)
        assert await cache.get_playlist("playlist123") is not None

        result = await cache.invalidate_playlist("playlist123")
        assert result is True
        assert await cache.get_playlist("playlist123") is None

    async def test_invalidate_search_results(self, cache):
        """Test invalidating cached search results."""
        search_results = {"tracks": {"items": []}}

        await cache.cache_search_results("query", search_results)
        assert await cache.get_search_results("query") is not None

        result = await cache.invalidate_search("query")
        assert result is True
        assert await cache.get_search_results("query") is None

    async def test_clear_all(self, cache):
        """Test clearing all cached data."""
        await cache.cache_track("track1", {"id": "track1"})
        await cache.cache_playlist("playlist1", {"id": "playlist1"})
        await cache.cache_search_results("query", {"tracks": {}})

        await cache.clear()

        assert await cache.get_track("track1") is None
        assert await cache.get_playlist("playlist1") is None
        assert await cache.get_search_results("query") is None

    async def test_ttl_expiration(self, cache):
        """Test that cached entries expire after TTL."""
        # Temporarily reduce TTL for testing
        original_ttl = cache.TRACK_TTL
        cache.TRACK_TTL = 1  # 1 second

        track_data = {"id": "track123", "name": "Test Song"}
        await cache.cache_track("track123", track_data)

        # Should be available immediately
        assert await cache.get_track("track123") is not None

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired
        assert await cache.get_track("track123") is None

        # Restore original TTL
        cache.TRACK_TTL = original_ttl

    async def test_cleanup_expired(self, cache):
        """Test cleaning up expired entries."""
        # Temporarily reduce TTL for testing
        original_ttl = cache.TRACK_TTL
        cache.TRACK_TTL = 1  # 1 second

        await cache.cache_track("track1", {"id": "track1"})
        await cache.cache_track("track2", {"id": "track2"})

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup should remove expired entries
        removed = await cache.cleanup_expired()
        assert removed == 2

        # Restore original TTL
        cache.TRACK_TTL = original_ttl

    async def test_get_stats(self, cache):
        """Test getting cache statistics."""
        await cache.cache_track("track1", {"id": "track1"})
        await cache.cache_playlist("playlist1", {"id": "playlist1"})

        stats = cache.get_stats()
        assert "total_entries" in stats
        assert stats["total_entries"] == 2

    async def test_cache_key_format(self, cache):
        """Test that cache keys are properly formatted."""
        # Test track key
        track_key = cache._make_track_key("abc123")
        assert track_key == "track:abc123"

        # Test playlist key
        playlist_key = cache._make_playlist_key("def456")
        assert playlist_key == "playlist:def456"

        # Test search key
        search_key = cache._make_search_key("test query", 10)
        assert search_key == "search:test query:10"
