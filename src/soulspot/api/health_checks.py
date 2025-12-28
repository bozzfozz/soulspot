"""Health check endpoints for application monitoring.

This module provides health and readiness endpoints for Kubernetes-style
health monitoring with dependency checks.
"""

import logging
from typing import Any

from fastapi import FastAPI

from soulspot.application.services.credentials_service import CredentialsService
from soulspot.config import Settings
from soulspot.infrastructure.observability.health import (
    HealthStatus,
    check_database_health,
    check_musicbrainz_health,
    check_slskd_health,
    check_spotify_health,
)

logger = logging.getLogger(__name__)


def register_health_endpoints(app: FastAPI, settings: Settings) -> None:
    """Register health check endpoints on the FastAPI application.

    This function registers three health endpoints:
    - /health: Basic health check (liveness)
    - /ready: Detailed readiness check with dependencies
    - /live: Simple liveness probe

    Args:
        app: FastAPI application instance
        settings: Application settings
    """

    # Hey, this is the BASIC health check - just returns "alive" without checking dependencies!
    # Kubernetes uses this for liveness probe (is process running?). FAST because no DB/API calls.
    # For detailed checks (DB connectivity, external services), use /ready endpoint instead. If this
    # returns 500, Kubernetes will restart the pod thinking process is hung. Keep it lightweight!
    @app.get(
        "/health",
        tags=["Health"],
        summary="Basic health check",
        description="Returns basic application health status. Use /ready for detailed dependency checks.",
        response_description="Application health status",
    )
    async def health_check() -> dict[str, Any]:
        """Health check endpoint.

        Returns:
            dict: Health status including app name and profile.

        Example response:
            {
                "status": "healthy",
                "app_name": "SoulSpot",
                "profile": "simple"
            }
        """
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "profile": settings.profile.value,
        }

    # Yo future me, this is the DETAILED readiness check - Kubernetes readiness probe! Checks DB
    # connectivity, external services (slskd, Spotify, MusicBrainz) if enabled. Takes longer than
    # /health because it makes real network calls. If this fails, Kubernetes STOPS routing traffic
    # to pod but doesn't restart it (gives time to recover). Can be slow during startup while DB
    # migrations run. The overall_status logic: UNHEALTHY if any critical service down, DEGRADED
    # if optional services down but app still works. Don't add checks for non-critical features!
    @app.get(
        "/ready",
        tags=["Health"],
        summary="Readiness check with dependencies",
        description="Returns detailed readiness status including database and external service health.",
        response_description="Readiness status with dependency health checks",
    )
    async def readiness_check() -> dict[str, Any]:
        """Readiness check endpoint with database and dependency connectivity checks.

        Returns:
            dict: Readiness status with detailed health checks for all dependencies.

        Example response:
            {
                "status": "ready",
                "checks": {
                    "database": {"status": "healthy", "message": "Connected"},
                    "slskd": {"status": "healthy", "message": "Connected"},
                    "spotify": {"status": "degraded", "message": "No credentials"},
                    "musicbrainz": {"status": "healthy", "message": "Available"},
                    "circuit_breakers": {
                        "spotify": "CLOSED",
                        "musicbrainz": "CLOSED",
                        "slskd": "CLOSED"
                    }
                }
            }
        """
        checks = {}
        overall_status = HealthStatus.HEALTHY

        # Database connectivity check
        if hasattr(app.state, "db"):
            db_check = await check_database_health(app.state.db)
            checks["database"] = {
                "status": db_check.status.value,
                "message": db_check.message,
            }
            if db_check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                db_check.status == HealthStatus.DEGRADED
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.DEGRADED
        else:
            checks["database"] = {
                "status": HealthStatus.UNHEALTHY.value,
                "message": "Database not initialized",
            }
            overall_status = HealthStatus.UNHEALTHY

        # External service health checks (if enabled)
        if settings.observability.enable_dependency_health_checks:
            timeout = settings.observability.health_check_timeout

            # slskd health check - get URL from DB via CredentialsService (with env fallback)
            # Hey future me - we need to get slskd URL from DB-first config now!
            slskd_url = settings.slskd.url  # Default fallback
            if hasattr(app.state, "db"):
                try:
                    async with app.state.db.session_scope() as session:
                        creds_service = CredentialsService(session)
                        slskd_creds = await creds_service.get_slskd_credentials()
                        slskd_url = slskd_creds.url
                except Exception as e:
                    logger.warning(f"Failed to get slskd credentials from DB: {e}")
                    # Fall through to env-based settings.slskd.url

            slskd_check = await check_slskd_health(slskd_url, timeout=timeout)
            checks["slskd"] = {
                "status": slskd_check.status.value,
                "message": slskd_check.message,
            }
            if (
                slskd_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

            # Spotify health check
            spotify_check = await check_spotify_health(timeout=timeout)
            checks["spotify"] = {
                "status": spotify_check.status.value,
                "message": spotify_check.message,
            }
            # Update overall status based on Spotify check
            if (
                spotify_check.status == HealthStatus.UNHEALTHY
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                spotify_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

            # MusicBrainz health check
            mb_check = await check_musicbrainz_health(timeout=timeout)
            checks["musicbrainz"] = {
                "status": mb_check.status.value,
                "message": mb_check.message,
            }
            # Update overall status based on MusicBrainz check
            if (
                mb_check.status == HealthStatus.UNHEALTHY
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                mb_check.status == HealthStatus.DEGRADED
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        # Worker health checks via Orchestrator (refactored Dec 2025)
        # Hey future me - we now use the centralized orchestrator for worker health!
        # This replaces 50+ lines of individual worker checks with one orchestrator call.
        # The orchestrator tracks all workers and knows if required workers are healthy.
        orchestrator = getattr(app.state, "orchestrator", None)
        if orchestrator is not None:
            orchestrator_status = orchestrator.get_status()
            workers_healthy = orchestrator.is_healthy()
            
            # Simplified worker status for health endpoint
            workers_summary = {
                "total": orchestrator_status.get("total_workers", 0),
                "by_state": orchestrator_status.get("by_state", {}),
                "healthy": workers_healthy,
            }
            
            # Add individual worker states for debugging
            workers_detail = {}
            for name, info in orchestrator_status.get("workers", {}).items():
                workers_detail[name] = {
                    "state": info.get("state", "unknown"),
                    "category": info.get("category", "general"),
                }
            
            checks["workers"] = {
                "summary": workers_summary,
                "workers": workers_detail,
            }
        else:
            # Fallback: check workers manually if orchestrator not available
            workers_healthy = True
            workers_status = {}
            
            # Download Worker
            download_worker = getattr(app.state, "download_worker", None)
            if download_worker:
                worker_status = download_worker.get_status()
                workers_status["download_worker"] = {
                    "running": worker_status.get("running", False),
                }
                if not worker_status.get("running"):
                    workers_healthy = False
    
            # Token Refresh Worker
            token_worker = getattr(app.state, "token_refresh_worker", None)
            if token_worker:
                worker_status = token_worker.get_status()
                workers_status["token_refresh"] = {
                    "running": worker_status.get("running", False),
                }
            
            checks["workers"] = workers_status

        if not workers_healthy and overall_status == HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "checks": checks,
        }

    # Listen, /live is the SIMPLEST liveness probe - literally just returns JSON if process is alive!
    # Kubernetes uses this to detect if app is hung/deadlocked. If this 500s or times out, pod gets
    # killed and restarted. NO database checks, NO external calls - just "can Python respond?". Even
    # simpler than /health! If this fails, something is REALLY broken (out of memory, deadlock, etc).
    @app.get("/live", tags=["Health"])
    async def liveness_check() -> dict[str, str]:
        """Liveness check endpoint - returns OK if application is running."""
        return {"status": "alive"}

    # Hey future me - this is THE endpoint for monitoring SQLite lock health!
    # Shows how often "database is locked" errors occur and how the retry logic performs.
    # Use this to:
    # 1. Detect if lock contention is increasing (failure_rate going up)
    # 2. See if retry logic is working (retry_rate > 0 but failure_rate low = good!)
    # 3. Identify slow operations (max_wait_time_ms high = something holds lock too long)
    #
    # Ideal metrics:
    # - failure_rate: < 0.01 (less than 1% failures after retries)
    # - avg_wait_time_ms: < 100ms (retries complete quickly)
    # - retry_rate: < 0.05 (less than 5% operations need retries)
    #
    # If metrics are bad, investigate:
    # - Which workers are running? (check /ready)
    # - Is Library Scan active? (long transactions)
    # - Are many downloads queued? (concurrent writes)
    @app.get(
        "/health/db-metrics",
        tags=["Health"],
        summary="Database lock metrics",
        description="Returns metrics about database lock events and retry performance. "
        "Useful for monitoring SQLite concurrency health.",
    )
    async def db_metrics() -> dict[str, Any]:
        """Get database lock metrics for monitoring.

        Returns:
            dict: Lock metrics including attempt/success/failure counts,
                  wait times, and retry statistics.

        Example response:
            {
                "lock_attempts": 1000,
                "lock_successes": 998,
                "lock_failures": 2,
                "lock_retries": 15,
                "total_wait_time_ms": 450.5,
                "max_wait_time_ms": 125.3,
                "avg_wait_time_ms": 30.0,
                "failure_rate": 0.002,
                "retry_rate": 0.015,
                "last_lock_event_timestamp": 1735120000.0
            }
        """
        from soulspot.infrastructure.persistence.retry import DatabaseLockMetrics

        metrics = DatabaseLockMetrics.get_instance()
        stats = metrics.get_stats()

        # Add DB pool stats if available
        if hasattr(app.state, "db"):
            pool_stats = app.state.db.get_pool_stats()
            stats["connection_pool"] = pool_stats

        return stats

