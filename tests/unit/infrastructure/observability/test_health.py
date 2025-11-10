"""Tests for health checks."""

import pytest
from pytest_httpx import HTTPXMock

from soulspot.infrastructure.observability.health import (
    HealthStatus,
    check_musicbrainz_health,
    check_slskd_health,
    check_spotify_health,
)


class TestSlskdHealthCheck:
    """Test slskd health check."""

    @pytest.mark.asyncio
    async def test_slskd_healthy(self, httpx_mock: HTTPXMock):
        """Test slskd health check when service is healthy."""
        httpx_mock.add_response(
            url="http://localhost:5030/health", status_code=200, json={"status": "ok"}
        )

        result = await check_slskd_health("http://localhost:5030", timeout=5.0)
        assert result.status == HealthStatus.HEALTHY
        assert "accessible" in result.message

    @pytest.mark.asyncio
    async def test_slskd_degraded(self, httpx_mock: HTTPXMock):
        """Test slskd health check when service returns non-200."""
        httpx_mock.add_response(
            url="http://localhost:5030/health",
            status_code=503,
            text="Service unavailable",
        )

        result = await check_slskd_health("http://localhost:5030", timeout=5.0)
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_slskd_unhealthy_connection_error(self, httpx_mock: HTTPXMock):
        """Test slskd health check when service is unreachable."""
        httpx_mock.add_exception(Exception("Connection refused"))

        result = await check_slskd_health("http://localhost:5030", timeout=5.0)
        assert result.status == HealthStatus.UNHEALTHY
        assert (
            "unreachable" in result.message.lower() or "error" in result.message.lower()
        )


class TestSpotifyHealthCheck:
    """Test Spotify health check."""

    @pytest.mark.asyncio
    async def test_spotify_healthy(self, httpx_mock: HTTPXMock):
        """Test Spotify health check when API is accessible."""
        httpx_mock.add_response(
            url="https://api.spotify.com/v1/", status_code=401
        )  # 401 is expected without auth

        result = await check_spotify_health(timeout=5.0)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_spotify_healthy_with_200(self, httpx_mock: HTTPXMock):
        """Test Spotify health check with 200 response."""
        httpx_mock.add_response(url="https://api.spotify.com/v1/", status_code=200)

        result = await check_spotify_health(timeout=5.0)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_spotify_degraded(self, httpx_mock: HTTPXMock):
        """Test Spotify health check when API returns unexpected status."""
        httpx_mock.add_response(url="https://api.spotify.com/v1/", status_code=503)

        result = await check_spotify_health(timeout=5.0)
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_spotify_unhealthy(self, httpx_mock: HTTPXMock):
        """Test Spotify health check when API is unreachable."""
        httpx_mock.add_exception(Exception("Connection error"))

        result = await check_spotify_health(timeout=5.0)
        assert result.status == HealthStatus.UNHEALTHY


class TestMusicBrainzHealthCheck:
    """Test MusicBrainz health check."""

    @pytest.mark.asyncio
    async def test_musicbrainz_healthy(self, httpx_mock: HTTPXMock):
        """Test MusicBrainz health check when API is accessible."""
        httpx_mock.add_response(
            url="https://musicbrainz.org/ws/2/", status_code=200, text="OK"
        )

        result = await check_musicbrainz_health(timeout=5.0)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_musicbrainz_degraded(self, httpx_mock: HTTPXMock):
        """Test MusicBrainz health check when API returns non-200."""
        httpx_mock.add_response(url="https://musicbrainz.org/ws/2/", status_code=503)

        result = await check_musicbrainz_health(timeout=5.0)
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_musicbrainz_unhealthy(self, httpx_mock: HTTPXMock):
        """Test MusicBrainz health check when API is unreachable."""
        httpx_mock.add_exception(Exception("Connection error"))

        result = await check_musicbrainz_health(timeout=5.0)
        assert result.status == HealthStatus.UNHEALTHY
