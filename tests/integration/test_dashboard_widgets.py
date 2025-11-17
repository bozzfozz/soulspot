"""Integration test for dashboard widgets."""

import pytest
from httpx import AsyncClient

from soulspot.main import app


@pytest.mark.asyncio
async def test_dashboard_page_loads():
    """Test that dashboard page loads."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert b"dashboard" in response.content.lower()


@pytest.mark.asyncio
async def test_widget_catalog_endpoint():
    """Test widget catalog endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/ui/widgets/catalog")
        assert response.status_code == 200
        # Should contain widget names
        content = response.content.decode()
        assert "Active Jobs" in content or "active" in content.lower()


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
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        for widget_type in widget_types:
            response = await client.get(f"/api/ui/widgets/{widget_type}/content")
            assert response.status_code == 200, f"{widget_type} endpoint failed"
            # Should return HTML
            assert response.headers.get("content-type", "").startswith("text/html")
