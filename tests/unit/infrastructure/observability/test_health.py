"""Tests for health checks and circuit breakers."""

import pytest
from pytest_httpx import HTTPXMock

from soulspot.infrastructure.observability.health import (
    CircuitBreaker,
    HealthStatus,
    check_musicbrainz_health,
    check_slskd_health,
    check_spotify_health,
    get_circuit_breaker,
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_allows_attempts(self):
        """Test that circuit breaker initially allows attempts."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.can_attempt() is True
        assert cb.is_open is False

    def test_records_failures(self):
        """Test recording failures."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.failures == 1
        assert cb.is_open is False

    def test_opens_after_threshold(self):
        """Test that circuit opens after threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_attempt() is False

    def test_records_success_resets_failures(self):
        """Test that success resets failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.failures == 2
        cb.record_success()
        assert cb.failures == 0
        assert cb.is_open is False

    def test_timeout_allows_retry(self):
        """Test that timeout allows retry after circuit opens."""
        import time

        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_attempt() is False

        # Wait for timeout
        time.sleep(0.2)
        assert cb.can_attempt() is True

    def test_get_circuit_breaker_creates_instance(self):
        """Test that get_circuit_breaker creates and caches instances."""
        cb1 = get_circuit_breaker("test-service")
        cb2 = get_circuit_breaker("test-service")
        assert cb1 is cb2

    def test_get_circuit_breaker_separate_instances(self):
        """Test that different services get different circuit breakers."""
        cb1 = get_circuit_breaker("service-1")
        cb2 = get_circuit_breaker("service-2")
        assert cb1 is not cb2


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
            url="http://localhost:5030/health", status_code=503, text="Service unavailable"
        )

        result = await check_slskd_health("http://localhost:5030", timeout=5.0)
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_slskd_unhealthy_connection_error(self, httpx_mock: HTTPXMock):
        """Test slskd health check when service is unreachable."""
        httpx_mock.add_exception(Exception("Connection refused"))

        result = await check_slskd_health("http://localhost:5030", timeout=5.0)
        assert result.status == HealthStatus.UNHEALTHY
        assert "unreachable" in result.message.lower() or "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_slskd_circuit_breaker_opens(self, httpx_mock: HTTPXMock):
        """Test that circuit breaker opens after failures."""
        # Reset the circuit breaker for this test
        from soulspot.infrastructure.observability.health import _circuit_breakers
        test_url = "http://localhost-circuit-test:5031"
        circuit_key = "slskd"
        if circuit_key in _circuit_breakers:
            del _circuit_breakers[circuit_key]

        # Add exception responses for failures (5 is the threshold)
        for _ in range(5):
            httpx_mock.add_exception(Exception("Connection refused"))

        # Make 5 failed requests to open circuit (threshold is 5 by default)
        for i in range(5):
            result = await check_slskd_health(test_url, timeout=5.0)
            # Should be UNHEALTHY for failures
            if i < 4:
                assert result.status == HealthStatus.UNHEALTHY
            else:
                # After 5th failure, circuit opens so status could be UNHEALTHY or DEGRADED
                assert result.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]

        # Now circuit should be open - next request should be blocked without making HTTP call
        result = await check_slskd_health(test_url, timeout=5.0)
        assert result.status == HealthStatus.DEGRADED
        assert "circuit breaker" in result.message.lower()


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
