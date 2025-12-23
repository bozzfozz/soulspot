"""Metrics API endpoint for Prometheus scraping.

Hey future me - this router exposes metrics for monitoring!

Endpoints:
- GET /api/metrics         → Prometheus text format
- GET /api/metrics/json    → JSON format for debugging
- GET /api/metrics/circuit-breakers → Circuit breaker status

The metrics endpoint is scraped by Prometheus at regular intervals.
Grafana can visualize these metrics in dashboards.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from soulspot.api.dependencies import get_download_repository
from soulspot.infrastructure.observability.circuit_breaker import (
    get_circuit_breaker_stats,
)
from soulspot.infrastructure.observability.metrics import get_download_metrics
from soulspot.infrastructure.persistence.repositories import DownloadRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> str:
    """Get metrics in Prometheus text exposition format.

    Hey future me - this is what Prometheus scrapes!

    Prometheus config example:
        scrape_configs:
          - job_name: 'soulspot'
            static_configs:
              - targets: ['localhost:5000']
            metrics_path: '/api/metrics'

    Returns:
        Prometheus-formatted metrics text including circuit breaker metrics
    """
    from soulspot.domain.entities import DownloadStatus

    metrics = get_download_metrics()

    # Update gauges with current queue state from DB
    try:
        waiting = await download_repository.count_by_status(
            DownloadStatus.WAITING.value
        )
        pending = await download_repository.count_by_status(
            DownloadStatus.PENDING.value
        )
        queued = await download_repository.count_by_status(DownloadStatus.QUEUED.value)
        downloading = await download_repository.count_by_status(
            DownloadStatus.DOWNLOADING.value
        )

        metrics.set_queue_size(waiting, status="waiting")
        metrics.set_queue_size(pending, status="pending")
        metrics.set_queue_size(queued, status="queued")
        metrics.set_active_downloads(downloading)

    except Exception as e:
        logger.warning(f"Failed to update queue metrics: {e}")

    # Combine download metrics with circuit breaker metrics
    prometheus_output = metrics.to_prometheus_format()
    circuit_breaker_output = _format_circuit_breakers_prometheus()

    if circuit_breaker_output:
        prometheus_output += "\n\n" + circuit_breaker_output

    return prometheus_output


@router.get("/json")
async def get_metrics_json(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get metrics as JSON for debugging.

    Hey future me - easier to read than Prometheus format!

    Returns:
        Metrics summary as JSON
    """
    from soulspot.domain.entities import DownloadStatus

    metrics = get_download_metrics()

    # Update gauges with current state
    try:
        waiting = await download_repository.count_by_status(
            DownloadStatus.WAITING.value
        )
        pending = await download_repository.count_by_status(
            DownloadStatus.PENDING.value
        )
        downloading = await download_repository.count_by_status(
            DownloadStatus.DOWNLOADING.value
        )
        completed = await download_repository.count_by_status(
            DownloadStatus.COMPLETED.value
        )
        failed = await download_repository.count_by_status(DownloadStatus.FAILED.value)

        metrics.set_queue_size(waiting, status="waiting")
        metrics.set_queue_size(pending, status="pending")
        metrics.set_active_downloads(downloading)

        return {
            "current_state": {
                "queue_waiting": waiting,
                "queue_pending": pending,
                "active_downloads": downloading,
                "total_completed": completed,
                "total_failed": failed,
            },
            "metrics": metrics.get_summary(),
        }

    except Exception as e:
        logger.warning(f"Failed to get metrics: {e}")
        return {"error": str(e), "metrics": metrics.get_summary()}


@router.get("/circuit-breakers")
async def get_circuit_breaker_metrics() -> dict[str, Any]:
    """Get circuit breaker status for all registered breakers.

    Hey future me - this shows health of external service connections!

    Circuit states:
    - CLOSED: All good, requests pass through
    - OPEN: Service failing, requests blocked
    - HALF_OPEN: Testing if service recovered

    Returns:
        Circuit breaker stats for each registered breaker
    """
    cb_stats = get_circuit_breaker_stats()

    # Format stats for JSON response
    breakers = {}
    for name, stats in cb_stats.items():
        breakers[name] = {
            "state": stats.state.value,
            "is_healthy": stats.state.value == "closed",
            "failure_count": stats.failure_count,
            "success_count": stats.success_count,
            "total_requests": stats.total_requests,
            "total_failures": stats.total_failures,
            "total_successes": stats.total_successes,
            "failure_rate": (
                round(stats.total_failures / stats.total_requests * 100, 2)
                if stats.total_requests > 0
                else 0.0
            ),
            "last_failure_time": (
                stats.last_failure_time.isoformat() if stats.last_failure_time else None
            ),
            "last_state_change": stats.last_state_change.isoformat(),
        }

    # Summary stats
    total_breakers = len(breakers)
    healthy_breakers = sum(1 for b in breakers.values() if b["is_healthy"])
    unhealthy_breakers = total_breakers - healthy_breakers

    return {
        "summary": {
            "total_breakers": total_breakers,
            "healthy": healthy_breakers,
            "unhealthy": unhealthy_breakers,
            "health_percentage": (
                round(healthy_breakers / total_breakers * 100, 2)
                if total_breakers > 0
                else 100.0
            ),
        },
        "breakers": breakers,
    }


def _format_circuit_breakers_prometheus() -> str:
    """Format circuit breaker stats as Prometheus metrics.

    Hey future me - this is included in the main /metrics endpoint!

    Metrics:
    - circuit_breaker_state: Current state (0=closed, 1=open, 2=half_open)
    - circuit_breaker_total_requests: Total requests through breaker
    - circuit_breaker_total_failures: Total failed requests
    - circuit_breaker_failure_rate: Failure percentage
    """
    lines = [
        "# HELP circuit_breaker_state Current state (0=closed, 1=open, 2=half_open)",
        "# TYPE circuit_breaker_state gauge",
        "# HELP circuit_breaker_total_requests Total requests through circuit breaker",
        "# TYPE circuit_breaker_total_requests counter",
        "# HELP circuit_breaker_total_failures Total failed requests",
        "# TYPE circuit_breaker_total_failures counter",
    ]

    state_values = {"closed": 0, "open": 1, "half_open": 2}

    cb_stats = get_circuit_breaker_stats()
    for name, stats in cb_stats.items():
        state_num = state_values.get(stats.state.value, -1)
        lines.append(f'circuit_breaker_state{{breaker="{name}"}} {state_num}')
        lines.append(
            f'circuit_breaker_total_requests{{breaker="{name}"}} {stats.total_requests}'
        )
        lines.append(
            f'circuit_breaker_total_failures{{breaker="{name}"}} {stats.total_failures}'
        )

    return "\n".join(lines)
