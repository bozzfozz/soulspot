"""Health check functionality with dependency monitoring."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str | None = None
    details: dict[str, Any] | None = None


class CircuitBreaker:
    """Simple circuit breaker for external service calls."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds to wait before trying again
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time: float | None = None
        self.is_open = False

    def record_success(self) -> None:
        """Record a successful call."""
        self.failures = 0
        self.is_open = False
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Record a failed call."""
        import time

        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker opened after {self.failures} failures",
                extra={"failures": self.failures, "threshold": self.failure_threshold},
            )

    def can_attempt(self) -> bool:
        """Check if a call can be attempted.

        Returns:
            True if circuit is closed or timeout has passed
        """
        import time

        if not self.is_open:
            return True

        if self.last_failure_time is None:
            return True

        # Check if timeout has passed
        elapsed = time.time() - self.last_failure_time
        if elapsed > self.timeout_seconds:
            logger.info(
                "Circuit breaker timeout passed, attempting call",
                extra={"elapsed_seconds": elapsed},
            )
            self.is_open = False
            self.failures = 0
            return True

        return False


# Global circuit breakers for external services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service.

    Args:
        service_name: Name of the external service

    Returns:
        Circuit breaker instance
    """
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker()
    return _circuit_breakers[service_name]


async def check_database_health(db: Any) -> HealthCheck:
    """Check database connectivity.

    Args:
        db: Database instance

    Returns:
        Health check result
    """
    try:
        async with db.session_scope() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()

        return HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection successful",
        )

    except Exception as e:
        logger.exception("Database health check failed", extra={"error": str(e)})
        return HealthCheck(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database connection failed: {str(e)}",
        )


async def check_slskd_health(base_url: str, timeout: float = 5.0) -> HealthCheck:
    """Check slskd service health.

    Args:
        base_url: slskd base URL
        timeout: Request timeout in seconds

    Returns:
        Health check result
    """
    circuit_breaker = get_circuit_breaker("slskd")

    if not circuit_breaker.can_attempt():
        return HealthCheck(
            name="slskd",
            status=HealthStatus.DEGRADED,
            message="Circuit breaker open, service temporarily unavailable",
            details={"failures": circuit_breaker.failures},
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try to hit the health endpoint or base URL
            response = await client.get(f"{base_url}/health")

            if response.status_code == 200:
                circuit_breaker.record_success()
                return HealthCheck(
                    name="slskd",
                    status=HealthStatus.HEALTHY,
                    message="slskd service is accessible",
                    details={"url": base_url},
                )
            else:
                circuit_breaker.record_failure()
                return HealthCheck(
                    name="slskd",
                    status=HealthStatus.DEGRADED,
                    message=f"slskd returned status {response.status_code}",
                    details={"url": base_url, "status_code": response.status_code},
                )

    except httpx.RequestError as e:
        circuit_breaker.record_failure()
        logger.warning(
            "slskd health check failed",
            extra={"error": str(e), "url": base_url},
        )
        return HealthCheck(
            name="slskd",
            status=HealthStatus.UNHEALTHY,
            message=f"slskd service unreachable: {str(e)}",
            details={"url": base_url},
        )
    except Exception as e:
        circuit_breaker.record_failure()
        logger.exception("slskd health check error", extra={"error": str(e)})
        return HealthCheck(
            name="slskd",
            status=HealthStatus.UNHEALTHY,
            message=f"slskd health check error: {str(e)}",
        )


async def check_spotify_health(timeout: float = 5.0) -> HealthCheck:
    """Check Spotify API health.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Health check result
    """
    circuit_breaker = get_circuit_breaker("spotify")

    if not circuit_breaker.can_attempt():
        return HealthCheck(
            name="spotify",
            status=HealthStatus.DEGRADED,
            message="Circuit breaker open, service temporarily unavailable",
            details={"failures": circuit_breaker.failures},
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Check Spotify API status
            response = await client.get("https://api.spotify.com/v1/")

            # Spotify returns 401 without auth, which is expected
            if response.status_code in (200, 401):
                circuit_breaker.record_success()
                return HealthCheck(
                    name="spotify",
                    status=HealthStatus.HEALTHY,
                    message="Spotify API is accessible",
                )
            else:
                circuit_breaker.record_failure()
                return HealthCheck(
                    name="spotify",
                    status=HealthStatus.DEGRADED,
                    message=f"Spotify API returned status {response.status_code}",
                    details={"status_code": response.status_code},
                )

    except httpx.RequestError as e:
        circuit_breaker.record_failure()
        logger.warning("Spotify health check failed", extra={"error": str(e)})
        return HealthCheck(
            name="spotify",
            status=HealthStatus.UNHEALTHY,
            message=f"Spotify API unreachable: {str(e)}",
        )
    except Exception as e:
        circuit_breaker.record_failure()
        logger.exception("Spotify health check error", extra={"error": str(e)})
        return HealthCheck(
            name="spotify",
            status=HealthStatus.UNHEALTHY,
            message=f"Spotify health check error: {str(e)}",
        )


async def check_musicbrainz_health(timeout: float = 5.0) -> HealthCheck:
    """Check MusicBrainz API health.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Health check result
    """
    circuit_breaker = get_circuit_breaker("musicbrainz")

    if not circuit_breaker.can_attempt():
        return HealthCheck(
            name="musicbrainz",
            status=HealthStatus.DEGRADED,
            message="Circuit breaker open, service temporarily unavailable",
            details={"failures": circuit_breaker.failures},
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Check MusicBrainz API
            response = await client.get("https://musicbrainz.org/ws/2/")

            if response.status_code == 200:
                circuit_breaker.record_success()
                return HealthCheck(
                    name="musicbrainz",
                    status=HealthStatus.HEALTHY,
                    message="MusicBrainz API is accessible",
                )
            else:
                circuit_breaker.record_failure()
                return HealthCheck(
                    name="musicbrainz",
                    status=HealthStatus.DEGRADED,
                    message=f"MusicBrainz API returned status {response.status_code}",
                    details={"status_code": response.status_code},
                )

    except httpx.RequestError as e:
        circuit_breaker.record_failure()
        logger.warning("MusicBrainz health check failed", extra={"error": str(e)})
        return HealthCheck(
            name="musicbrainz",
            status=HealthStatus.UNHEALTHY,
            message=f"MusicBrainz API unreachable: {str(e)}",
        )
    except Exception as e:
        circuit_breaker.record_failure()
        logger.exception("MusicBrainz health check error", extra={"error": str(e)})
        return HealthCheck(
            name="musicbrainz",
            status=HealthStatus.UNHEALTHY,
            message=f"MusicBrainz health check error: {str(e)}",
        )
