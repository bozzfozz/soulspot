# Hey future me - dieser Router ist für Kubernetes/Docker Health Checks!
#
# Endpoints:
# - /health          → Comprehensive health check (workers + DB + services)
# - /health/live     → Liveness probe (app is running)
# - /health/ready    → Readiness probe (app can accept requests)
# - /health/workers  → Detailed worker status from orchestrator
#
# Use cases:
# - Docker HEALTHCHECK: curl -f http://localhost:8000/health/live || exit 1
# - K8s livenessProbe: /health/live
# - K8s readinessProbe: /health/ready
# - Monitoring dashboard: /health (full status)
#
# The orchestrator provides worker health info via is_healthy() and get_status().
"""Health check endpoints for Docker/Kubernetes probes."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()


class HealthStatus(BaseModel):
    """Overall health status response."""

    status: str = Field(description="Overall status: healthy, degraded, unhealthy")
    timestamp: str = Field(description="ISO timestamp of health check")
    version: str = Field(default="1.0.0", description="Application version")
    uptime_seconds: float | None = Field(
        default=None, description="Seconds since app started"
    )
    checks: dict[str, Any] = Field(
        default_factory=dict, description="Individual component checks"
    )


class LivenessStatus(BaseModel):
    """Simple liveness probe response."""

    status: str = Field(description="alive or dead")
    timestamp: str = Field(description="ISO timestamp")


class ReadinessStatus(BaseModel):
    """Readiness probe response."""

    status: str = Field(description="ready or not_ready")
    timestamp: str = Field(description="ISO timestamp")
    database: bool = Field(description="Database connection OK")
    workers: bool = Field(description="Required workers running")


@router.get("/live", response_model=LivenessStatus)
async def liveness_probe() -> LivenessStatus:
    """Liveness probe for Kubernetes/Docker.

    Returns 200 if the application process is running.
    Used by Kubernetes to know if the container should be restarted.

    This is a simple "am I alive" check - no dependency checks.
    """
    return LivenessStatus(
        status="alive",
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/ready", response_model=ReadinessStatus)
async def readiness_probe(request: Request) -> JSONResponse:
    """Readiness probe for Kubernetes/Docker.

    Returns 200 if the application is ready to accept traffic.
    Returns 503 if not ready (DB down, critical workers failed).

    Used by Kubernetes to know if traffic should be routed to this pod.
    """
    timestamp = datetime.now(UTC).isoformat()

    # Check database
    db_ok = False
    try:
        db = getattr(request.app.state, "db", None)
        if db is not None:
            # Quick ping - just check if we can get a session
            async with db.session_scope() as session:
                await session.execute("SELECT 1")  # type: ignore
            db_ok = True
    except Exception:
        db_ok = False

    # Check workers via orchestrator
    workers_ok = False
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None:
        workers_ok = orchestrator.is_healthy()

    # Determine overall readiness
    is_ready = db_ok and workers_ok

    response = ReadinessStatus(
        status="ready" if is_ready else "not_ready",
        timestamp=timestamp,
        database=db_ok,
        workers=workers_ok,
    )

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=response.model_dump(), status_code=status_code)


@router.get("", response_model=HealthStatus)
async def health_check(request: Request) -> JSONResponse:
    """Comprehensive health check endpoint.

    Returns detailed status of all components:
    - Database connection
    - Worker orchestrator status
    - External service connectivity (if configured)

    Returns 200 for healthy/degraded, 503 for unhealthy.
    """
    timestamp = datetime.now(UTC).isoformat()
    checks: dict[str, Any] = {}

    # Check database
    try:
        db = getattr(request.app.state, "db", None)
        if db is not None:
            async with db.session_scope() as session:
                await session.execute("SELECT 1")  # type: ignore
            checks["database"] = {"status": "ok", "connected": True}
        else:
            checks["database"] = {"status": "error", "connected": False, "error": "Not initialized"}
    except Exception as e:
        checks["database"] = {"status": "error", "connected": False, "error": str(e)}

    # Check worker orchestrator
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None:
        orchestrator_status = orchestrator.get_status()
        checks["workers"] = {
            "status": "ok" if orchestrator.is_healthy() else "degraded",
            "total": orchestrator_status.get("total_workers", 0),
            "by_state": orchestrator_status.get("by_state", {}),
            "healthy": orchestrator.is_healthy(),
        }
    else:
        checks["workers"] = {"status": "error", "error": "Orchestrator not initialized"}

    # Check slskd connectivity (optional - don't fail health check if not configured)
    slskd_client = getattr(request.app.state, "slskd_client", None)
    if slskd_client is not None:
        try:
            # Quick health check - just see if client exists
            checks["slskd"] = {"status": "ok", "configured": True}
        except Exception as e:
            checks["slskd"] = {"status": "degraded", "error": str(e)}
    else:
        checks["slskd"] = {"status": "not_configured", "configured": False}

    # Calculate uptime if startup time is tracked
    uptime = None
    startup_time = getattr(request.app.state, "startup_time", None)
    if startup_time is not None:
        uptime = (datetime.now(UTC) - startup_time).total_seconds()

    # Determine overall status
    db_ok = checks.get("database", {}).get("status") == "ok"
    workers_ok = checks.get("workers", {}).get("healthy", False)

    if db_ok and workers_ok:
        overall_status = "healthy"
        status_code = status.HTTP_200_OK
    elif db_ok or workers_ok:
        overall_status = "degraded"
        status_code = status.HTTP_200_OK  # Degraded is still 200
    else:
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    response = HealthStatus(
        status=overall_status,
        timestamp=timestamp,
        uptime_seconds=uptime,
        checks=checks,
    )

    return JSONResponse(content=response.model_dump(), status_code=status_code)


@router.get("/workers")
async def worker_health(request: Request) -> dict[str, Any]:
    """Detailed worker health status from orchestrator.

    Returns the full orchestrator status including:
    - All registered workers
    - Per-worker state (running, stopped, failed)
    - Start/stop timestamps
    - Error messages for failed workers

    This is the same as /api/workers/orchestrator but under /health path.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {
            "status": "error",
            "error": "Orchestrator not initialized",
            "healthy": False,
            "workers": {},
        }

    status = orchestrator.get_status()
    status["healthy"] = orchestrator.is_healthy()

    return status
