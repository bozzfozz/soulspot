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
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try to hit the health endpoint or base URL
            response = await client.get(f"{base_url}/health")

            if response.status_code == 200:
                return HealthCheck(
                    name="slskd",
                    status=HealthStatus.HEALTHY,
                    message="slskd service is accessible",
                    details={"url": base_url},
                )
            else:
                return HealthCheck(
                    name="slskd",
                    status=HealthStatus.DEGRADED,
                    message=f"slskd returned status {response.status_code}",
                    details={"url": base_url, "status_code": response.status_code},
                )

    except httpx.RequestError as e:
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
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Check Spotify API status
            response = await client.get("https://api.spotify.com/v1/")

            # Spotify returns 401 without auth, which is expected
            if response.status_code in (200, 401):
                return HealthCheck(
                    name="spotify",
                    status=HealthStatus.HEALTHY,
                    message="Spotify API is accessible",
                )
            else:
                return HealthCheck(
                    name="spotify",
                    status=HealthStatus.DEGRADED,
                    message=f"Spotify API returned status {response.status_code}",
                    details={"status_code": response.status_code},
                )

    except httpx.RequestError as e:
        logger.warning("Spotify health check failed", extra={"error": str(e)})
        return HealthCheck(
            name="spotify",
            status=HealthStatus.UNHEALTHY,
            message=f"Spotify API unreachable: {str(e)}",
        )
    except Exception as e:
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
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Check MusicBrainz API
            response = await client.get("https://musicbrainz.org/ws/2/")

            if response.status_code == 200:
                return HealthCheck(
                    name="musicbrainz",
                    status=HealthStatus.HEALTHY,
                    message="MusicBrainz API is accessible",
                )
            else:
                return HealthCheck(
                    name="musicbrainz",
                    status=HealthStatus.DEGRADED,
                    message=f"MusicBrainz API returned status {response.status_code}",
                    details={"status_code": response.status_code},
                )

    except httpx.RequestError as e:
        logger.warning("MusicBrainz health check failed", extra={"error": str(e)})
        return HealthCheck(
            name="musicbrainz",
            status=HealthStatus.UNHEALTHY,
            message=f"MusicBrainz API unreachable: {str(e)}",
        )
    except Exception as e:
        logger.exception("MusicBrainz health check error", extra={"error": str(e)})
        return HealthCheck(
            name="musicbrainz",
            status=HealthStatus.UNHEALTHY,
            message=f"MusicBrainz health check error: {str(e)}",
        )
