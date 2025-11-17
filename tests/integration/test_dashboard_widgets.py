"""Integration test for dashboard widgets."""

import pytest
from httpx import ASGITransport, AsyncClient

from soulspot.main import app


@pytest.mark.asyncio
async def test_dashboard_page_loads():
    """Test that dashboard page loads."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert b"dashboard" in response.content.lower()


@pytest.mark.asyncio
async def test_dashboard_page_contains_required_elements():
    """Test that dashboard page has all required UI elements."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
        content = response.content.decode()

        # Check for key elements
        assert "Edit Dashboard" in content or "Done Editing" in content
        assert "Add Widget" in content or "edit" in content.lower()
        assert "widget-canvas" in content
        assert "modal-container" in content
        assert "keyboard-shortcuts-modal" in content


@pytest.mark.asyncio
async def test_widget_catalog_endpoint():
    """Test widget catalog endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ui/widgets/catalog")
        assert response.status_code == 200
        content = response.content.decode()

        # Should contain widget names
        assert "Active Jobs" in content
        assert "Spotify Search" in content
        assert "Missing Tracks" in content
        assert "Quick Actions" in content
        assert "Metadata Manager" in content

        # Should have ARIA attributes
        assert 'role="dialog"' in content
        assert 'aria-modal="true"' in content


@pytest.mark.asyncio
async def test_widget_content_endpoints():
    """Test widget content endpoints."""
    widget_types = [
        "active-jobs",
        "spotify-search",
        "missing-tracks",
        "quick-actions",
        "metadata-manager",
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for widget_type in widget_types:
            response = await client.get(f"/api/ui/widgets/{widget_type}/content")
            assert response.status_code == 200, f"{widget_type} endpoint failed"
            # Should return HTML
            assert response.headers.get("content-type", "").startswith("text/html")
            content = response.content.decode()
            # Should have widget structure
            assert "widget-content" in content or "widget-header" in content


@pytest.mark.asyncio
async def test_dashboard_canvas_endpoint():
    """Test widget canvas endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ui/pages/default/canvas")
        assert response.status_code == 200
        content = response.content.decode()

        # Should have canvas structure or empty state
        assert ("widget-card" in content or
                "No widgets yet" in content or
                "widget-col-" in content)


@pytest.mark.asyncio
async def test_widget_instance_crud():
    """Test creating and deleting widget instances."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a widget instance
        response = await client.post(
            "/api/ui/widgets/instances",
            data={
                "page_id": "1",
                "widget_type": "active_jobs"
            }
        )
        # Should succeed or return appropriate response
        assert response.status_code in [200, 201, 302]

        # Get canvas to verify (this also tests that the page exists)
        canvas_response = await client.get("/api/ui/pages/1/canvas?edit_mode=true")
        assert canvas_response.status_code == 200


@pytest.mark.asyncio
async def test_page_list_endpoint():
    """Test page list endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ui/pages/list")
        assert response.status_code == 200
        content = response.content.decode()
        # Should have page list structure
        assert "page-list" in content or "My Dashboard" in content


@pytest.mark.asyncio
async def test_widget_config_endpoint():
    """Test widget configuration endpoint requires valid instance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Try to get config for non-existent widget
        response = await client.get("/api/ui/widgets/instances/99999/config")
        # Should return 404 or error
        assert response.status_code in [404, 500]


@pytest.mark.asyncio
async def test_dashboard_accessibility_features():
    """Test that accessibility features are present."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
        content = response.content.decode()

        # Check for ARIA attributes
        assert 'role="region"' in content or 'role="dialog"' in content or 'aria-label' in content

        # Check for keyboard shortcuts
        assert 'sr-announcer' in content or 'sr-only' in content

        # Check for keyboard shortcuts modal
        assert 'keyboard-shortcuts-modal' in content
        assert 'Keyboard Shortcuts' in content


@pytest.mark.asyncio
async def test_spotify_search_widget_with_query():
    """Test Spotify search widget with search query."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/ui/widgets/spotify-search/results",
            params={"query": "test", "search_type": "track", "limit": "5"}
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Should return search results or empty state
        assert "spotify" in content.lower() or "search" in content.lower() or "results" in content.lower()


@pytest.mark.asyncio
async def test_metadata_manager_with_filter():
    """Test metadata manager widget with different filters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for filter_type in ["all", "missing", "incorrect"]:
            response = await client.get(
                "/api/ui/widgets/metadata-manager/content",
                params={"filter": filter_type}
            )
            assert response.status_code == 200
            content = response.content.decode()
            # Should have filter buttons
            assert "filter-btn" in content or "All" in content


@pytest.mark.asyncio
async def test_htmx_headers_present():
    """Test that pages include HTMX headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard")
        content = response.content.decode()

        # Check for HTMX attributes
        assert "hx-get" in content or "hx-post" in content
        assert "hx-target" in content
        assert "hx-swap" in content

        # Check HTMX is loaded
        assert "htmx.org" in content or "htmx" in content.lower()
