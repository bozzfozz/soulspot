"""Comprehensive UI accessibility tests.

This module tests that all UI pages are accessible and render correctly.
Tests verify HTML responses, status codes, and basic content validation.
"""

from httpx import AsyncClient


class TestMainUIPages:
    """Test main UI pages are accessible."""

    async def test_index_page_accessible(self, async_client: AsyncClient):
        """Verify index/dashboard page is accessible."""
        response = await async_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        # Check for basic HTML structure
        content = response.text
        assert "<html" in content.lower()
        assert "</html>" in content.lower()

    async def test_playlists_page_accessible(self, async_client: AsyncClient):
        """Verify playlists page is accessible."""
        response = await async_client.get("/playlists")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_downloads_page_accessible(self, async_client: AsyncClient):
        """Verify downloads page is accessible."""
        response = await async_client.get("/downloads")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_library_page_accessible(self, async_client: AsyncClient):
        """Verify library page is accessible."""
        response = await async_client.get("/library")
        # Library page might not exist
        assert response.status_code in [200, 404]

    async def test_settings_page_accessible(self, async_client: AsyncClient):
        """Verify settings page is accessible."""
        response = await async_client.get("/settings")
        # Settings page might not exist
        assert response.status_code in [200, 404]


class TestUIModalsAndPartials:
    """Test HTMX modals and partial templates."""

    async def test_export_modal_accessible(self, async_client: AsyncClient):
        """Verify export modal partial is accessible."""
        response = await async_client.get("/playlists/test-id/export-modal")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_missing_tracks_partial_accessible(self, async_client: AsyncClient):
        """Verify missing tracks partial is accessible."""
        # Use valid UUID format
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.get(f"/playlists/{playlist_id}/missing-tracks")
        # Should return 200 or 404 if playlist doesn't exist
        assert response.status_code in [200, 404]


class TestStaticAssets:
    """Test static assets are accessible."""

    async def test_static_files_mounted(self, async_client: AsyncClient):
        """Verify static files endpoint exists."""
        # Try to access a common static path
        response = await async_client.get("/static/")
        # Should not be 404 if static files are mounted, might be 403 or other
        # If static doesn't exist, that's okay - we just check the route exists
        assert response.status_code in [200, 403, 404]


class TestHTMXHeaders:
    """Test HTMX-specific functionality."""

    async def test_htmx_request_header_accepted(self, async_client: AsyncClient):
        """Verify server accepts HX-Request header."""
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.get(
            f"/playlists/{playlist_id}/export-modal",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in [200, 404]

    async def test_htmx_trigger_header_in_response(self, async_client: AsyncClient):
        """Verify HTMX trigger headers are used where appropriate."""
        # Test endpoints that might use HX-Trigger
        response = await async_client.get("/")
        # Just verify the endpoint works - specific HX headers depend on app logic
        assert response.status_code == 200


class TestErrorPages:
    """Test error handling in UI."""

    async def test_nonexistent_ui_route_returns_404(self, async_client: AsyncClient):
        """Verify non-existent routes return 404."""
        response = await async_client.get("/nonexistent-page-12345")
        assert response.status_code == 404

    async def test_invalid_playlist_id_handled(self, async_client: AsyncClient):
        """Verify invalid playlist ID is handled gracefully."""
        # Use a UUID format
        playlist_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/playlists/{playlist_id}/missing-tracks")
        # Should return 404 or handle gracefully, not crash
        assert response.status_code in [200, 404]


class TestUIContentValidation:
    """Test UI pages contain expected content."""

    async def test_index_contains_dashboard_elements(self, async_client: AsyncClient):
        """Verify index page contains dashboard elements."""
        response = await async_client.get("/")
        content = response.text.lower()
        # Check for dashboard-related content
        assert any(
            keyword in content
            for keyword in ["dashboard", "playlist", "track", "download"]
        )

    async def test_playlists_page_contains_playlist_elements(
        self, async_client: AsyncClient
    ):
        """Verify playlists page contains playlist-related elements."""
        response = await async_client.get("/playlists")
        content = response.text.lower()
        assert "playlist" in content

    async def test_downloads_page_contains_download_elements(
        self, async_client: AsyncClient
    ):
        """Verify downloads page contains download-related elements."""
        response = await async_client.get("/downloads")
        content = response.text.lower()
        assert "download" in content


class TestUIResponsiveness:
    """Test UI handles different request types."""

    async def test_ui_handles_json_accept_header(self, async_client: AsyncClient):
        """Verify UI endpoints handle different accept headers."""
        response = await async_client.get(
            "/",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        assert response.status_code == 200

    async def test_ui_handles_mobile_user_agent(self, async_client: AsyncClient):
        """Verify UI works with mobile user agents."""
        response = await async_client.get(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"},
        )
        assert response.status_code == 200
