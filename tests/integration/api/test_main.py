"""Tests for FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from soulspot.config import Settings
from soulspot.main import create_app


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        app_env="development",
        debug=True,
        database={"url": "sqlite+aiosqlite:///:memory:"},
        observability={
            "enable_dependency_health_checks": False,
        },
    )


@pytest.fixture
def client(test_settings):
    """Create test client."""
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
        assert "environment" in data
        assert "profile" in data

    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "checks" in data
        assert "database" in data["checks"]

    @pytest.mark.skip(
        reason="Root endpoint requires database initialization - tested in UI tests"
    )
    def test_root_endpoint(self, client):
        """Test root endpoint returns HTML dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_schema(self, client):
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_swagger_ui(self, client):
        """Test Swagger UI endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_allowed_origin(self, client):
        """Test CORS with allowed origin."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:8000"},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:8000"
        )
