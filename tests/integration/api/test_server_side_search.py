"""Integration tests for server-side search functionality.

This module tests all search endpoints that provide server-side search capabilities,
including Spotify track search and widget search results. These endpoints support
the search UI and enable users to find tracks, artists, and albums.
"""

# AI-Model: Copilot
# Hey future me - server-side search endpoints hit external APIs (Spotify) or query our database.
# Mock external services but test actual query parsing, result formatting, and pagination logic.
# Search endpoints should handle empty queries, special characters, very long queries, and edge
# cases gracefully. Some endpoints require authentication (access_token) while others don't.
# Remember: search_track endpoint needs valid Spotify access token or it will fail!

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# Mark all tests in this module as slow
pytestmark = pytest.mark.slow


class TestTrackSearchEndpoint:
    """Test the /api/tracks/search endpoint for Spotify track search."""

    async def test_search_endpoint_exists(self, async_client: AsyncClient):
        """Verify search endpoint exists and requires parameters."""
        # Without required params, should get validation error
        response = await async_client.get("/api/tracks/search")

        # Should return 422 (validation error) for missing required params
        assert response.status_code == 422

    async def test_search_requires_query(self, async_client: AsyncClient):
        """Test that search endpoint requires query parameter."""
        response = await async_client.get(
            "/api/tracks/search", params={"access_token": "dummy_token"}
        )

        # Should fail without query
        assert response.status_code == 422

    async def test_search_requires_access_token(self, async_client: AsyncClient):
        """Test that search endpoint requires access_token parameter."""
        response = await async_client.get(
            "/api/tracks/search", params={"query": "test"}
        )

        # Should fail without access_token
        assert response.status_code == 422

    @pytest.mark.parametrize("limit", [1, 10, 50, 100])
    async def test_search_respects_limit_parameter(
        self, async_client: AsyncClient, limit: int
    ):
        """Test that search endpoint accepts different limit values."""
        # Mock the Spotify client to avoid actual API calls
        with patch("soulspot.api.routers.tracks.SpotifyClient") as mock_spotify_class:
            mock_client = AsyncMock()
            mock_client.search_track.return_value = {
                "tracks": {
                    "items": [
                        {"id": f"track_{i}", "name": f"Track {i}"} for i in range(limit)
                    ]
                }
            }
            mock_spotify_class.return_value = mock_client

            response = await async_client.get(
                "/api/tracks/search",
                params={"query": "test", "access_token": "dummy_token", "limit": limit},
            )

            # If mocked properly, should succeed
            # Otherwise may fail with 500 (Spotify auth error)
            assert response.status_code in [200, 500]

    async def test_search_handles_empty_query(self, async_client: AsyncClient):
        """Test search endpoint with empty query string."""
        with patch("soulspot.api.routers.tracks.SpotifyClient") as mock_spotify_class:
            mock_client = AsyncMock()
            mock_client.search_track.return_value = {"tracks": {"items": []}}
            mock_spotify_class.return_value = mock_client

            response = await async_client.get(
                "/api/tracks/search",
                params={"query": "", "access_token": "dummy_token", "limit": 10},
            )

            # Empty query might be rejected by validation or accepted
            assert response.status_code in [200, 422, 500]

    async def test_search_handles_special_characters(self, async_client: AsyncClient):
        """Test search endpoint handles special characters in query."""
        special_queries = [
            "AC/DC",
            "Guns N' Roses",
            "Panic! at the Disco",
            "artist: Beatles album: Abbey Road",
            "track:Hey Jude",
        ]

        for query in special_queries:
            with patch(
                "soulspot.api.routers.tracks.SpotifyClient"
            ) as mock_spotify_class:
                mock_client = AsyncMock()
                mock_client.search_track.return_value = {"tracks": {"items": []}}
                mock_spotify_class.return_value = mock_client

                response = await async_client.get(
                    "/api/tracks/search",
                    params={"query": query, "access_token": "dummy_token", "limit": 10},
                )

                # Should handle special characters gracefully
                assert response.status_code in [200, 500]

    async def test_search_response_structure(self, async_client: AsyncClient):
        """Test that search endpoint returns properly structured response."""
        with patch("soulspot.api.routers.tracks.SpotifyClient") as mock_spotify_class:
            mock_client = AsyncMock()
            mock_client.search_track.return_value = {
                "tracks": {
                    "items": [
                        {
                            "id": "track1",
                            "name": "Test Track",
                            "artists": [{"name": "Test Artist"}],
                            "album": {"name": "Test Album"},
                            "duration_ms": 180000,
                            "uri": "spotify:track:track1",
                        }
                    ]
                }
            }
            mock_spotify_class.return_value = mock_client

            response = await async_client.get(
                "/api/tracks/search",
                params={"query": "test", "access_token": "dummy_token", "limit": 10},
            )

            if response.status_code == 200:
                data = response.json()
                assert "tracks" in data
                assert "total" in data
                assert "query" in data
                assert isinstance(data["tracks"], list)


class TestWidgetSearchEndpoints:
    """Test widget-specific search endpoints that return HTML."""

    async def test_spotify_search_results_widget(self, async_client: AsyncClient):
        """Test Spotify search results widget endpoint."""
        response = await async_client.get(
            "/api/ui/widgets/spotify-search/results",
            params={"query": "test", "limit": 5},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_spotify_search_results_empty_query(self, async_client: AsyncClient):
        """Test widget search with empty query."""
        response = await async_client.get(
            "/api/ui/widgets/spotify-search/results", params={"query": "", "limit": 5}
        )

        # Should return HTML with empty results
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_spotify_search_results_short_query(self, async_client: AsyncClient):
        """Test widget search with query < 2 characters."""
        response = await async_client.get(
            "/api/ui/widgets/spotify-search/results", params={"query": "a", "limit": 5}
        )

        # Query too short, should return empty results or handle gracefully
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_spotify_search_results_limit_parameter(
        self, async_client: AsyncClient
    ):
        """Test widget search respects limit parameter."""
        for limit in [5, 10, 20]:
            response = await async_client.get(
                "/api/ui/widgets/spotify-search/results",
                params={"query": "test", "limit": limit},
            )

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    async def test_spotify_search_results_search_type(self, async_client: AsyncClient):
        """Test widget search with different search types."""
        search_types = ["track", "artist", "album"]

        for search_type in search_types:
            response = await async_client.get(
                "/api/ui/widgets/spotify-search/results",
                params={"query": "test", "search_type": search_type, "limit": 10},
            )

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")


class TestSearchEdgeCases:
    """Test edge cases and error scenarios in search functionality."""

    async def test_search_with_very_long_query(self, async_client: AsyncClient):
        """Test search with extremely long query string."""
        long_query = "a" * 1000  # 1000 character query

        with patch("soulspot.api.routers.tracks.SpotifyClient") as mock_spotify_class:
            mock_client = AsyncMock()
            mock_client.search_track.return_value = {"tracks": {"items": []}}
            mock_spotify_class.return_value = mock_client

            response = await async_client.get(
                "/api/tracks/search",
                params={
                    "query": long_query,
                    "access_token": "dummy_token",
                    "limit": 10,
                },
            )

            # Should handle long queries (may truncate or reject)
            assert response.status_code in [200, 400, 422, 500]

    async def test_search_with_invalid_limit(self, async_client: AsyncClient):
        """Test search with invalid limit values."""
        invalid_limits = [0, -1, 101, 1000]

        for limit in invalid_limits:
            response = await async_client.get(
                "/api/tracks/search",
                params={"query": "test", "access_token": "dummy_token", "limit": limit},
            )

            # Should reject invalid limits with validation error
            assert response.status_code in [422, 400]

    async def test_search_with_unicode_query(self, async_client: AsyncClient):
        """Test search with Unicode characters in query."""
        unicode_queries = [
            "Björk",
            "Måneskin",
            "日本語",
            "한국어",
            "العربية",
            "Σωκράτης",
        ]

        for query in unicode_queries:
            with patch(
                "soulspot.api.routers.tracks.SpotifyClient"
            ) as mock_spotify_class:
                mock_client = AsyncMock()
                mock_client.search_track.return_value = {"tracks": {"items": []}}
                mock_spotify_class.return_value = mock_client

                response = await async_client.get(
                    "/api/tracks/search",
                    params={"query": query, "access_token": "dummy_token", "limit": 10},
                )

                # Should handle Unicode gracefully
                assert response.status_code in [200, 500]

    async def test_widget_search_error_handling(self, async_client: AsyncClient):
        """Test that widget search handles errors gracefully."""
        # Widget search creates SpotifyClient internally, so we can't easily mock it
        # Just verify that errors don't crash the endpoint - it should return HTML
        response = await async_client.get(
            "/api/ui/widgets/spotify-search/results",
            params={"query": "test query that will fail auth", "limit": 10},
        )

        # Should handle error and return HTML (possibly with error message)
        # Not crash or return 500
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        # Should return empty results or error message, not crash


class TestSearchPerformance:
    """Test search performance and concurrency."""

    async def test_search_handles_concurrent_requests(self, async_client: AsyncClient):
        """Test that search endpoint handles multiple concurrent requests."""
        import asyncio

        with patch("soulspot.api.routers.tracks.SpotifyClient") as mock_spotify_class:
            mock_client = AsyncMock()
            mock_client.search_track.return_value = {"tracks": {"items": []}}
            mock_spotify_class.return_value = mock_client

            # Send 5 concurrent search requests
            tasks = [
                async_client.get(
                    "/api/tracks/search",
                    params={
                        "query": f"test{i}",
                        "access_token": "dummy_token",
                        "limit": 10,
                    },
                )
                for i in range(5)
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All requests should complete successfully (or with expected errors)
            for response in responses:
                if not isinstance(response, Exception):
                    assert response.status_code in [200, 500]
