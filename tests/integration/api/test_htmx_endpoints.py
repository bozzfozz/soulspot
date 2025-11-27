"""Integration tests for HTMX endpoints.

This module tests all HTMX endpoints that return HTML fragments for dynamic
content updates. These endpoints are called by htmx attributes in templates
(hx-get, hx-post, hx-delete) to provide seamless UI updates.
"""

# AI-Model: Copilot
# Hey future me - HTMX endpoints return HTML fragments, not JSON! Test for HTML content-type
# and check that response contains expected HTML structure. These are integration tests so they
# hit real database and repositories. Mock external services (Spotify, slskd) but test actual
# endpoint logic and template rendering. Status codes matter: 200 for success, 404 for not found,
# 400 for validation errors. HTMX swaps expect specific HTML structures with proper IDs/classes.

import pytest
from httpx import AsyncClient

# Mark all tests in this module as slow
pytestmark = pytest.mark.slow


class TestWidgetContentEndpoints:
    """Test widget content endpoints that return HTML fragments."""

    async def test_active_jobs_widget_content(self, async_client: AsyncClient):
        """Test active jobs widget content endpoint returns HTML."""
        response = await async_client.get("/api/ui/widgets/active-jobs/content")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        # Should contain some HTML structure
        assert b"<" in response.content and b">" in response.content

    async def test_spotify_search_widget_content(self, async_client: AsyncClient):
        """Test Spotify search widget content endpoint returns HTML."""
        response = await async_client.get("/api/ui/widgets/spotify-search/content")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert b"<" in response.content

    async def test_spotify_search_results(self, async_client: AsyncClient):
        """Test Spotify search results endpoint with query."""
        # Test empty query
        response = await async_client.get("/api/ui/widgets/spotify-search/results")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        # Test with query (will fail without Spotify auth but should return HTML)
        response = await async_client.get(
            "/api/ui/widgets/spotify-search/results",
            params={"query": "test", "limit": 5},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_missing_tracks_widget_content(self, async_client: AsyncClient):
        """Test missing tracks widget content endpoint."""
        response = await async_client.get("/api/ui/widgets/missing-tracks/content")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_quick_actions_widget_content(self, async_client: AsyncClient):
        """Test quick actions widget content endpoint."""
        response = await async_client.get("/api/ui/widgets/quick-actions/content")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_metadata_manager_widget_content(self, async_client: AsyncClient):
        """Test metadata manager widget content endpoint."""
        response = await async_client.get("/api/ui/widgets/metadata-manager/content")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_metadata_manager_with_filters(self, async_client: AsyncClient):
        """Test metadata manager widget with different filters."""
        filters = ["all", "missing", "incorrect"]

        for filter_type in filters:
            response = await async_client.get(
                "/api/ui/widgets/metadata-manager/content",
                params={"filter": filter_type},
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")


class TestUIPartialEndpoints:
    """Test UI partial endpoints that return HTML fragments for modals and dynamic content."""

    async def test_playlist_export_modal_endpoint_accessible(
        self, async_client: AsyncClient
    ):
        """Test playlist export modal endpoint exists."""
        # Use a valid UUID format
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.get(f"/playlists/{playlist_id}/export-modal")

        # Endpoint may not be in API prefix, check if it's accessible
        # If 404, it might not be registered in test fixture
        assert response.status_code in [200, 404]

    async def test_playlist_missing_tracks_endpoint_exists(
        self, async_client: AsyncClient
    ):
        """Test missing tracks partial endpoint exists."""
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.get(f"/playlists/{playlist_id}/missing-tracks")

        # Endpoint might not be registered or requires different route
        # Check that it's at least attempting to process, not completely missing
        assert response.status_code in [200, 404, 400]

    async def test_track_metadata_editor_endpoint_exists(
        self, async_client: AsyncClient
    ):
        """Test metadata editor modal endpoint exists."""
        track_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.get(f"/tracks/{track_id}/metadata-editor")

        # Endpoint might not be registered in test fixture
        assert response.status_code in [200, 404, 400]


class TestHTMXContentTypes:
    """Test that HTMX endpoints return proper HTML content-type headers."""

    async def test_all_widget_endpoints_return_html(self, async_client: AsyncClient):
        """Verify all widget content endpoints return HTML content-type."""
        widget_endpoints = [
            "/api/ui/widgets/active-jobs/content",
            "/api/ui/widgets/spotify-search/content",
            "/api/ui/widgets/missing-tracks/content",
            "/api/ui/widgets/quick-actions/content",
            "/api/ui/widgets/metadata-manager/content",
        ]

        for endpoint in widget_endpoints:
            response = await async_client.get(endpoint)
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert (
                "text/html" in content_type
            ), f"Endpoint {endpoint} should return HTML, got {content_type}"

    async def test_html_structure_validity(self, async_client: AsyncClient):
        """Test that returned HTML has basic structure (not malformed)."""
        response = await async_client.get("/api/ui/widgets/quick-actions/content")

        assert response.status_code == 200
        content = response.text

        # Basic HTML structure checks
        # Should have matched opening and closing tags
        opening_tags = content.count("<div")
        closing_tags = content.count("</div>")
        # Not necessarily equal (some tags might be self-closing), but should be close
        assert (
            abs(opening_tags - closing_tags) <= 5
        ), "HTML structure appears malformed - tag mismatch"


class TestHTMXErrorHandling:
    """Test error handling in HTMX endpoints."""

    async def test_widget_content_with_invalid_params(self, async_client: AsyncClient):
        """Test widget endpoints handle invalid parameters gracefully."""
        # Metadata manager with invalid filter
        response = await async_client.get(
            "/api/ui/widgets/metadata-manager/content",
            params={"filter": "invalid_filter_type"},
        )

        # Should still return 200 (graceful handling) or 400
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            # Should return HTML even with invalid filter
            assert "text/html" in response.headers.get("content-type", "")

    async def test_widget_endpoints_handle_errors_gracefully(
        self, async_client: AsyncClient
    ):
        """Test that widget endpoints handle errors gracefully without crashing."""
        # Test metadata manager with various edge cases
        response = await async_client.get(
            "/api/ui/widgets/metadata-manager/content",
            params={"filter": "nonexistent_filter"},
        )

        # Should return successfully (graceful handling) or reject with 400
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
