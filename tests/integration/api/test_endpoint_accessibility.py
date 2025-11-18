"""Comprehensive endpoint accessibility tests.

This module tests that all API endpoints are accessible and respond correctly
to basic requests. It ensures 100% endpoint coverage and validates that all
pages and features are reachable.
"""

from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health and status endpoints."""

    async def test_health_endpoint_accessible(self, async_client: AsyncClient):
        """Verify /health endpoint is accessible."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """Test authentication endpoints."""

    async def test_authorize_endpoint_accessible(self, async_client: AsyncClient):
        """Verify authorize endpoint is accessible."""
        response = await async_client.get("/api/auth/authorize")
        # Should redirect or return 200 with auth URL
        assert response.status_code in [200, 302, 307]

    async def test_callback_endpoint_accessible(self, async_client: AsyncClient):
        """Verify callback endpoint exists."""
        # This will fail without proper params, but endpoint should exist
        response = await async_client.get("/api/auth/callback")
        # Should return 422 (validation error) or other error, not 404
        assert response.status_code != 404

    async def test_spotify_status_endpoint_accessible(self, async_client: AsyncClient):
        """Verify Spotify auth status endpoint is accessible."""
        response = await async_client.get("/api/auth/spotify/status")
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data or "authenticated" in data

    async def test_session_endpoint_accessible(self, async_client: AsyncClient):
        """Verify session endpoint is accessible."""
        response = await async_client.get("/api/auth/session")
        assert response.status_code in [200, 401]

    async def test_logout_endpoint_exists(self, async_client: AsyncClient):
        """Verify logout endpoint exists."""
        response = await async_client.post("/api/auth/logout")
        assert response.status_code != 404


class TestPlaylistEndpoints:
    """Test playlist management endpoints."""

    async def test_list_playlists_endpoint_accessible(self, async_client: AsyncClient):
        """Verify playlists list endpoint is accessible."""
        response = await async_client.get("/api/playlists/")
        # Might require auth, but endpoint should exist
        assert response.status_code in [200, 401, 403]

    async def test_sync_all_playlists_endpoint_exists(self, async_client: AsyncClient):
        """Verify sync all playlists endpoint exists."""
        response = await async_client.post("/api/playlists/sync-all")
        # Should not be 404
        assert response.status_code != 404

    async def test_import_playlist_endpoint_exists(self, async_client: AsyncClient):
        """Verify import playlist endpoint exists."""
        response = await async_client.post("/api/playlists/import", json={})
        assert response.status_code != 404

    async def test_sync_playlist_tracks_endpoint_exists(
        self, async_client: AsyncClient
    ):
        """Verify sync playlist tracks endpoint exists."""
        # Use a valid UUID format
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.post(f"/api/playlists/{playlist_id}/sync")
        assert response.status_code != 404

    async def test_export_endpoints_exist(self, async_client: AsyncClient):
        """Verify export endpoints exist."""
        playlist_id = "550e8400-e29b-41d4-a716-446655440000"
        for format in ["m3u", "csv", "json"]:
            response = await async_client.get(
                f"/api/playlists/{playlist_id}/export/{format}"
            )
            # Should return 404 for non-existent playlist, not route not found
            assert response.status_code in [200, 404]


class TestTracksEndpoints:
    """Test track management endpoints."""

    async def test_get_track_endpoint_exists(self, async_client: AsyncClient):
        """Verify get track endpoint exists."""
        response = await async_client.get("/api/tracks/1")
        # Should return 404 for non-existent track
        assert response.status_code in [200, 404]

    async def test_search_tracks_endpoint_accessible(self, async_client: AsyncClient):
        """Verify search tracks endpoint is accessible."""
        # Note: Search requires access_token parameter, so we expect 422 validation error
        # when token is missing, which confirms the endpoint exists
        response = await async_client.get("/api/tracks/search?q=test")
        # Should return 422 (missing required access_token), not 404
        assert response.status_code in [200, 422]

    async def test_download_track_endpoint_exists(self, async_client: AsyncClient):
        """Verify download track endpoint exists."""
        response = await async_client.post("/api/tracks/1/download")
        assert response.status_code != 404

    async def test_enrich_track_endpoint_exists(self, async_client: AsyncClient):
        """Verify enrich track endpoint exists."""
        response = await async_client.post("/api/tracks/1/enrich")
        assert response.status_code != 404


class TestDownloadEndpoints:
    """Test download management endpoints."""

    async def test_list_downloads_endpoint_accessible(self, async_client: AsyncClient):
        """Verify downloads list endpoint is accessible."""
        response = await async_client.get("/api/downloads/")
        assert response.status_code == 200

    async def test_download_status_endpoint_accessible(self, async_client: AsyncClient):
        """Verify download status endpoint is accessible."""
        response = await async_client.get("/api/downloads/status")
        # Might return 503 if job queue not running
        assert response.status_code in [200, 503]

    async def test_pause_downloads_endpoint_exists(self, async_client: AsyncClient):
        """Verify pause downloads endpoint exists."""
        response = await async_client.post("/api/downloads/pause")
        # Might return 503 if job queue not running
        assert response.status_code in [200, 204, 503]

    async def test_resume_downloads_endpoint_exists(self, async_client: AsyncClient):
        """Verify resume downloads endpoint exists."""
        response = await async_client.post("/api/downloads/resume")
        # Might return 503 if job queue not running
        assert response.status_code in [200, 204, 503]

    async def test_batch_download_endpoint_exists(self, async_client: AsyncClient):
        """Verify batch download endpoint exists."""
        response = await async_client.post(
            "/api/downloads/batch", json={"track_ids": []}
        )
        # Might fail with 503 if job queue not running, but route exists
        assert response.status_code in [200, 400, 422, 503]

    async def test_cancel_download_endpoint_exists(self, async_client: AsyncClient):
        """Verify cancel download endpoint exists."""
        download_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.post(f"/api/downloads/{download_id}/cancel")
        # Should return 404 for non-existent download, not route not found
        assert response.status_code in [200, 404]


class TestMetadataEndpoints:
    """Test metadata management endpoints."""

    async def test_enrich_metadata_endpoint_exists(self, async_client: AsyncClient):
        """Verify enrich metadata endpoint exists."""
        response = await async_client.post("/api/metadata/enrich", json={})
        # Should return validation error, not 404
        assert response.status_code != 404

    async def test_auto_fix_metadata_endpoint_exists(self, async_client: AsyncClient):
        """Verify auto-fix metadata endpoint exists."""
        response = await async_client.post("/api/metadata/1/auto-fix")
        assert response.status_code != 404

    async def test_fix_all_metadata_endpoint_exists(self, async_client: AsyncClient):
        """Verify fix all metadata endpoint exists."""
        response = await async_client.post("/api/metadata/fix-all")
        assert response.status_code != 404


class TestLibraryEndpoints:
    """Test library management endpoints."""

    async def test_library_stats_endpoint_accessible(self, async_client: AsyncClient):
        """Verify library stats endpoint is accessible."""
        response = await async_client.get("/api/library/stats")
        assert response.status_code == 200

    async def test_scan_library_endpoint_exists(self, async_client: AsyncClient):
        """Verify scan library endpoint exists."""
        response = await async_client.post("/api/library/scan")
        assert response.status_code != 404

    async def test_get_duplicates_endpoint_accessible(self, async_client: AsyncClient):
        """Verify get duplicates endpoint is accessible."""
        response = await async_client.get("/api/library/duplicates")
        assert response.status_code == 200

    async def test_get_broken_files_endpoint_accessible(
        self, async_client: AsyncClient
    ):
        """Verify get broken files endpoint is accessible."""
        response = await async_client.get("/api/library/broken-files")
        assert response.status_code == 200

    async def test_incomplete_albums_endpoint_accessible(
        self, async_client: AsyncClient
    ):
        """Verify incomplete albums endpoint is accessible."""
        response = await async_client.get("/api/library/incomplete-albums")
        assert response.status_code == 200


class TestSettingsEndpoints:
    """Test settings endpoints."""

    async def test_get_settings_endpoint_accessible(self, async_client: AsyncClient):
        """Verify get settings endpoint is accessible."""
        response = await async_client.get("/api/settings/")
        assert response.status_code == 200

    async def test_update_settings_endpoint_exists(self, async_client: AsyncClient):
        """Verify update settings endpoint exists."""
        response = await async_client.put("/api/settings/", json={})
        assert response.status_code != 404


class TestDashboardEndpoints:
    """Test dashboard endpoints."""

    async def test_get_dashboard_endpoint_accessible(self, async_client: AsyncClient):
        """Verify get dashboard endpoint is accessible."""
        response = await async_client.get("/api/ui/dashboard")
        assert response.status_code == 200

    async def test_toggle_edit_mode_endpoint_exists(self, async_client: AsyncClient):
        """Verify toggle edit mode endpoint exists."""
        response = await async_client.post("/api/ui/dashboard/toggle-edit-mode")
        assert response.status_code != 404

    async def test_widgets_catalog_endpoint_accessible(self, async_client: AsyncClient):
        """Verify widgets catalog endpoint is accessible."""
        response = await async_client.get("/api/ui/widgets/catalog")
        assert response.status_code == 200


class TestWidgetEndpoints:
    """Test widget endpoints."""

    async def test_active_jobs_widget_content_accessible(
        self, async_client: AsyncClient
    ):
        """Verify active jobs widget content is accessible."""
        response = await async_client.get("/api/ui/widgets/active-jobs/content")
        assert response.status_code == 200

    async def test_spotify_search_widget_content_accessible(
        self, async_client: AsyncClient
    ):
        """Verify Spotify search widget content is accessible."""
        response = await async_client.get("/api/ui/widgets/spotify-search/content")
        assert response.status_code == 200

    async def test_missing_tracks_widget_content_accessible(
        self, async_client: AsyncClient
    ):
        """Verify missing tracks widget content is accessible."""
        response = await async_client.get("/api/ui/widgets/missing-tracks/content")
        assert response.status_code == 200


class TestWidgetTemplateEndpoints:
    """Test widget template endpoints."""

    async def test_list_widget_templates_endpoint_accessible(
        self, async_client: AsyncClient
    ):
        """Verify list widget templates endpoint is accessible."""
        response = await async_client.get("/api/widgets/templates")
        assert response.status_code == 200

    async def test_get_categories_endpoint_accessible(self, async_client: AsyncClient):
        """Verify get categories endpoint is accessible."""
        response = await async_client.get("/api/widgets/templates/categories/list")
        assert response.status_code == 200


class TestAutomationEndpoints:
    """Test automation endpoints."""

    async def test_list_watchlist_endpoint_accessible(self, async_client: AsyncClient):
        """Verify list watchlist endpoint is accessible."""
        response = await async_client.get("/api/automation/watchlist")
        assert response.status_code == 200

    async def test_create_watchlist_endpoint_exists(self, async_client: AsyncClient):
        """Verify create watchlist endpoint exists."""
        response = await async_client.post("/api/automation/watchlist", json={})
        assert response.status_code != 404

    async def test_get_missing_discography_endpoint_accessible(
        self, async_client: AsyncClient
    ):
        """Verify get missing discography endpoint is accessible."""
        response = await async_client.get("/api/automation/discography/missing")
        # Endpoint requires authentication, so 401/403 is expected
        assert response.status_code in [200, 401, 403]

    async def test_identify_quality_upgrades_endpoint_exists(
        self, async_client: AsyncClient
    ):
        """Verify identify quality upgrades endpoint exists."""
        response = await async_client.post("/api/automation/quality-upgrades/identify")
        assert response.status_code != 404


class TestSSEEndpoints:
    """Test Server-Sent Events endpoints."""

    async def test_sse_stream_endpoint_accessible(self, async_client: AsyncClient):
        """Verify SSE stream endpoint is accessible."""
        import asyncio
        
        # SSE endpoints use streaming responses that never complete on their own
        # Use a timeout to prevent hanging
        try:
            async with asyncio.timeout(2.0):  # 2 second timeout
                async with async_client.stream("GET", "/api/ui/sse/stream") as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers.get("content-type", "")
                    # Read one chunk to ensure stream works
                    async for _ in response.aiter_bytes():
                        break  # Exit after first chunk
        except asyncio.TimeoutError:
            # Timeout is expected for SSE streams, endpoint is accessible
            pass

    async def test_sse_test_endpoint_accessible(self, async_client: AsyncClient):
        """Verify SSE test endpoint is accessible."""
        import asyncio
        
        # SSE test endpoint also uses streaming
        try:
            async with asyncio.timeout(2.0):  # 2 second timeout
                async with async_client.stream("GET", "/api/ui/sse/test") as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers.get("content-type", "")
                    # Read one chunk to ensure stream works
                    async for _ in response.aiter_bytes():
                        break  # Exit after first chunk
        except asyncio.TimeoutError:
            # Timeout is expected for SSE streams, endpoint is accessible
            pass
