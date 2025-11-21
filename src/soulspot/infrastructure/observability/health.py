"""Health check functionality with dependency monitoring."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)


# Hey future me, HEALTHY means "all good", DEGRADED means "works but something's off" (like
# a cache miss or slow response), UNHEALTHY means "broken, don't use this". For overall health
# checks: all HEALTHY = 200 OK, any DEGRADED = 200 OK but warn operators, any UNHEALTHY = 503
# Service Unavailable. Use DEGRADED wisely - don't mark the whole app unhealthy just because
# Last.fm is down if that's not critical! Reserve UNHEALTHY for show-stoppers like DB failures.
class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# Listen up, this is the health check RESULT object! name identifies which check (database,
# slskd, spotify, etc). status is the verdict. message is human-readable (show in dashboards).
# details is optional structured data (response times, version info, etc) - useful for debugging
# but don't put sensitive data here! This gets exposed via /health endpoint. Keep checks FAST
# (<1s) or health endpoint becomes slow and defeats the purpose!
@dataclass
class HealthCheck:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str | None = None
    details: dict[str, Any] | None = None


# Hey future me, this health check does a simple SELECT 1 query to verify DB is alive and responsive.
# We use text("SELECT 1") which is DB-agnostic (works on Postgres, MySQL, SQLite). The scalar() call
# actually fetches the result (otherwise query might not execute!). We wrap in session_scope() so
# session is properly closed even if query fails. This runs on /health endpoint - keep it FAST
# (no complex queries, no table scans!). If this fails, app is basically dead - DB is critical.
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


# Yo, this checks if slskd (Soulseek daemon) is reachable by HTTP GET to /health endpoint. The
# 5s timeout is critical - without it, hung slskd service could block health checks for minutes!
# If slskd is down, downloads won't work but the rest of the app still functions (degraded mode).
# We return DEGRADED not UNHEALTHY because it's not a critical dependency - users can still browse
# their library, edit playlists, etc. The try/except catches network errors, timeouts, DNS failures.
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


# Yo future me, Spotify health check is interesting - we expect 401 Unauthorized! That's because
# their API requires auth tokens, but a 401 means the API is UP and responding. We'd only get
# timeouts/connection errors if it's actually down. The 5s timeout is generous for a health check
# but Spotify can be slow sometimes. We return DEGRADED (not UNHEALTHY) on errors because Spotify
# being down doesn't break the ENTIRE app - users can still manage their library, downloads, etc.
# Only new playlist imports are affected. The httpx.RequestError catches network/DNS/timeout issues.
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


# Hey, MusicBrainz is similar to Spotify health check - just hit the base URL and see if it
# responds. 200 OK means healthy. They have strict rate limiting (1 req/sec) but ONE health check
# request won't violate that. Unlike Spotify, MusicBrainz doesn't require auth for basic endpoints,
# so we expect 200, not 401. We return DEGRADED on errors because MB is for metadata enrichment -
# app still works without it, just less pretty track info. The 5s timeout is fine - MB is usually
# fast. If this times out frequently, their servers might be overloaded (check status.musicbrainz.org).
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
