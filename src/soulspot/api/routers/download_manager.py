"""Download Manager API Routes.

Provides endpoints for the Download Manager UI to query active downloads,
queue statistics, and receive real-time progress updates via SSE.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.download_manager_service import (
    DownloadManagerConfig,
    DownloadManagerService,
)
from soulspot.config.settings import get_settings
from soulspot.domain.entities.download_manager import (
    DownloadProvider,
    QueueStatistics,
    UnifiedDownload,
)
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.providers import (
    DownloadProviderRegistry,
    SlskdDownloadProvider,
)

logger = logging.getLogger(__name__)

# Initialize templates (same pattern as library.py)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/downloads/manager", tags=["download-manager"])


# -------------------------------------------------------------------------
# Response Models (Pydantic DTOs)
# -------------------------------------------------------------------------


class ProgressDTO(BaseModel):
    """Progress information for a download."""

    percent: float
    bytes_downloaded: int
    total_bytes: int
    speed_bytes_per_sec: float
    eta_seconds: int | None
    speed_formatted: str
    eta_formatted: str
    size_formatted: str


class TrackInfoDTO(BaseModel):
    """Track metadata for display."""

    title: str
    artist: str
    album: str | None
    display_name: str


class UnifiedDownloadDTO(BaseModel):
    """API response model for a unified download."""

    id: str
    track_id: str
    track_info: TrackInfoDTO
    provider: str
    provider_name: str
    external_id: str | None
    status: str
    status_message: str | None
    error_message: str | None
    progress: ProgressDTO
    created_at: datetime
    started_at: datetime | None
    is_active: bool
    can_cancel: bool

    @classmethod
    def from_entity(cls, entity: UnifiedDownload) -> "UnifiedDownloadDTO":
        """Convert domain entity to DTO."""
        return cls(
            id=str(entity.id),
            track_id=str(entity.track_id),
            track_info=TrackInfoDTO(
                title=entity.track_info.title,
                artist=entity.track_info.artist,
                album=entity.track_info.album,
                display_name=entity.track_info.display_name,
            ),
            provider=entity.provider.value,
            provider_name=entity.provider_name,
            external_id=entity.external_id,
            status=entity.status.value,
            status_message=entity.status_message,
            error_message=entity.error_message,
            progress=ProgressDTO(
                percent=entity.progress.percent,
                bytes_downloaded=entity.progress.bytes_downloaded,
                total_bytes=entity.progress.total_bytes,
                speed_bytes_per_sec=entity.progress.speed_bytes_per_sec,
                eta_seconds=entity.progress.eta_seconds,
                speed_formatted=entity.progress.speed_formatted,
                eta_formatted=entity.progress.eta_formatted,
                size_formatted=entity.progress.size_formatted,
            ),
            created_at=entity.timestamps.created_at,
            started_at=entity.timestamps.started_at,
            is_active=entity.is_active,
            can_cancel=entity.can_cancel,
        )


class QueueStatsDTO(BaseModel):
    """Queue statistics response model."""

    waiting: int
    pending: int
    queued: int
    downloading: int
    paused: int
    stalled: int
    completed_today: int
    failed_today: int
    total_active: int
    total_in_progress: int
    summary_text: str

    @classmethod
    def from_entity(cls, stats: QueueStatistics) -> "QueueStatsDTO":
        """Convert domain entity to DTO."""
        return cls(
            waiting=stats.waiting,
            pending=stats.pending,
            queued=stats.queued,
            downloading=stats.downloading,
            paused=stats.paused,
            stalled=stats.stalled,
            completed_today=stats.completed_today,
            failed_today=stats.failed_today,
            total_active=stats.total_active,
            total_in_progress=stats.total_in_progress,
            summary_text=stats.summary_text,
        )


class ActiveDownloadsResponse(BaseModel):
    """Response for active downloads endpoint."""

    downloads: list[UnifiedDownloadDTO]
    stats: QueueStatsDTO
    providers_available: list[str]


# -------------------------------------------------------------------------
# Dependency Injection Helpers
# -------------------------------------------------------------------------


async def get_download_manager_service(
    session: AsyncSession = Depends(get_db_session),
) -> DownloadManagerService:
    """Create DownloadManagerService with all providers."""
    # Get slskd settings from app settings
    settings = get_settings()

    # Create provider registry
    registry = DownloadProviderRegistry()

    # Register slskd provider if configured
    if settings.slskd.url:
        try:
            slskd_client = SlskdClient(settings.slskd)
            slskd_provider = SlskdDownloadProvider(slskd_client)
            registry.register(slskd_provider)
        except Exception as e:
            logger.warning(f"Failed to initialize slskd provider: {e}")

    # Create and return service
    return DownloadManagerService(
        session=session,
        provider_registry=registry,
        config=DownloadManagerConfig(),
    )


# -------------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------------


@router.get("/active", response_model=ActiveDownloadsResponse)
async def get_active_downloads(
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> ActiveDownloadsResponse:
    """Get all active downloads from all providers.

    Returns a unified view of:
    - Downloads waiting in SoulSpot's queue (WAITING, PENDING)
    - Downloads active in providers (QUEUED, DOWNLOADING, PAUSED, STALLED)

    Plus queue statistics and available providers.
    """
    # Get active downloads
    downloads = await service.get_active_downloads()

    # Get queue statistics
    stats = await service.get_queue_statistics()

    # Get available providers
    available_providers = await service._registry.get_available_providers()
    provider_names = [p.provider_name for p in available_providers]

    return ActiveDownloadsResponse(
        downloads=[UnifiedDownloadDTO.from_entity(d) for d in downloads],
        stats=QueueStatsDTO.from_entity(stats),
        providers_available=provider_names,
    )


@router.get("/stats", response_model=QueueStatsDTO)
async def get_queue_stats(
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> QueueStatsDTO:
    """Get download queue statistics.

    Returns counts of downloads in each state, plus recent
    completed/failed counts for the summary bar.
    """
    stats = await service.get_queue_statistics()
    return QueueStatsDTO.from_entity(stats)


@router.get("/events")
async def download_events(
    request: Request,
) -> EventSourceResponse:
    """Server-Sent Events endpoint for real-time download progress.

    Sends updates every 2 seconds with current download status.
    Use this for live progress bars without polling.

    Note: We create fresh sessions per update to avoid stale connections.

    Example JS client:
    ```javascript
    const evtSource = new EventSource('/api/downloads/manager/events');
    evtSource.addEventListener('update', (event) => {
        const data = JSON.parse(event.data);
        updateProgressBars(data.downloads);
    });
    ```
    """
    # Get settings and create registry once
    settings = get_settings()
    registry = DownloadProviderRegistry()

    if settings.slskd.url:
        try:
            slskd_client = SlskdClient(settings.slskd)
            slskd_provider = SlskdDownloadProvider(slskd_client)
            registry.register(slskd_provider)
        except Exception as e:
            logger.warning(f"Failed to initialize slskd provider for SSE: {e}")

    async def event_generator():
        """Generate SSE events with download updates."""
        # Get database from app state
        from soulspot.infrastructure.persistence.database import Database

        db: Database = request.app.state.db

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Create fresh session for each update (avoids stale session issues)
                async with db.session_scope() as session:
                    service = DownloadManagerService(
                        session=session,
                        provider_registry=registry,
                        config=DownloadManagerConfig(),
                    )

                    # Get current state
                    downloads = await service.get_active_downloads()
                    stats = await service.get_queue_statistics()

                    # Build event data
                    data = {
                        "downloads": [
                            UnifiedDownloadDTO.from_entity(d).model_dump(mode="json")
                            for d in downloads
                        ],
                        "stats": QueueStatsDTO.from_entity(stats).model_dump(mode="json"),
                        "timestamp": datetime.now().isoformat(),
                    }

                yield {
                    "event": "update",
                    "data": json.dumps(data),
                }

                # Wait before next update
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            logger.debug("SSE connection cancelled")
        except Exception as e:
            logger.error(f"SSE error: {e}")

    return EventSourceResponse(event_generator())


# -------------------------------------------------------------------------
# Provider Health Endpoint
# -------------------------------------------------------------------------


class ProviderHealthDTO(BaseModel):
    """Health status for a download provider."""

    provider: str
    provider_name: str
    is_healthy: bool
    circuit_state: str | None  # closed, open, half_open
    consecutive_failures: int
    last_successful_sync: str | None
    seconds_since_last_sync: int | None
    seconds_until_recovery_attempt: int | None
    error_message: str | None


class ProvidersHealthResponse(BaseModel):
    """Response for provider health check."""

    providers: list[ProviderHealthDTO]
    overall_healthy: bool


@router.get("/health", response_model=ProvidersHealthResponse)
async def get_providers_health(
    request: Request,
) -> ProvidersHealthResponse:
    """Get health status of all download providers.

    Returns circuit breaker status for each provider, which indicates
    if the provider is reachable and functioning properly.

    Hey future me – this endpoint reads health from app.state where
    the StatusSyncWorker stores its circuit breaker state. If no
    worker is running, we show a degraded status.
    """
    providers: list[ProviderHealthDTO] = []

    # Get status sync worker from app state (if running)
    app = request.app
    sync_worker = getattr(app.state, "download_status_sync_worker", None)

    # slskd provider health
    if sync_worker:
        health = sync_worker.get_health_status()
        providers.append(
            ProviderHealthDTO(
                provider="soulseek",
                provider_name="slskd",
                is_healthy=health.get("is_healthy", False),
                circuit_state=health.get("circuit_state"),
                consecutive_failures=health.get("consecutive_failures", 0),
                last_successful_sync=health.get("last_successful_sync"),
                seconds_since_last_sync=health.get("seconds_since_last_sync"),
                seconds_until_recovery_attempt=health.get(
                    "seconds_until_recovery_attempt"
                ),
                error_message=None,
            )
        )
    else:
        # No worker running - show as unknown
        providers.append(
            ProviderHealthDTO(
                provider="soulseek",
                provider_name="slskd",
                is_healthy=False,
                circuit_state=None,
                consecutive_failures=0,
                last_successful_sync=None,
                seconds_since_last_sync=None,
                seconds_until_recovery_attempt=None,
                error_message="Status sync worker not running",
            )
        )

    overall_healthy = all(p.is_healthy for p in providers)

    return ProvidersHealthResponse(
        providers=providers,
        overall_healthy=overall_healthy,
    )


# -------------------------------------------------------------------------
# HTMX Endpoints for UI Components
# -------------------------------------------------------------------------


@router.get("/htmx/active-list", response_class=HTMLResponse)
async def htmx_active_downloads_list(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render active downloads list partial.

    Use with hx-get for auto-refreshing download list:
    ```html
    <div hx-get="/api/downloads/manager/htmx/active-list"
         hx-trigger="every 3s"
         hx-swap="innerHTML">
    </div>
    ```
    """
    downloads = await service.get_active_downloads()
    stats = await service.get_queue_statistics()

    return templates.TemplateResponse(
        "partials/download_manager_list.html",
        {
            "request": request,
            "downloads": [UnifiedDownloadDTO.from_entity(d) for d in downloads],
            "stats": QueueStatsDTO.from_entity(stats),
        },
    )


@router.get("/htmx/stats-bar", response_class=HTMLResponse)
async def htmx_stats_bar(
    request: Request,
    service: DownloadManagerService = Depends(get_download_manager_service),
) -> HTMLResponse:
    """HTMX endpoint: Render queue stats bar partial.

    Displays summary like: "15 waiting │ 3 pending │ 2 downloading"
    """
    stats = await service.get_queue_statistics()

    return templates.TemplateResponse(
        "partials/download_manager_stats.html",
        {
            "request": request,
            "stats": QueueStatsDTO.from_entity(stats),
        },
    )


@router.get("/htmx/provider-health", response_class=HTMLResponse)
async def htmx_provider_health(
    request: Request,
) -> HTMLResponse:
    """HTMX endpoint: Render provider health widget partial.

    Shows connection status for slskd and other download providers.
    Updates every 10 seconds via hx-trigger.
    """
    # Get health data using same logic as /health endpoint
    health_response = await get_providers_health(request)

    return templates.TemplateResponse(
        "partials/download_manager_provider_health.html",
        {
            "request": request,
            "providers": health_response.providers,
            "overall_healthy": health_response.overall_healthy,
        },
    )
