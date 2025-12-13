"""Download Manager Service.

The central service that aggregates download status from multiple providers
and enriches it with SoulSpot metadata (track info, etc.).

This is the APPLICATION LAYER service that orchestrates:
1. Querying all download providers for active downloads
2. Joining provider data with SoulSpot's Download table
3. Enriching with track metadata for display
4. Computing queue statistics
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Download, DownloadStatus, Track
from soulspot.domain.entities.download_manager import (
    DownloadProgress,
    DownloadProvider,
    DownloadTimestamps,
    QueueStatistics,
    TrackInfo,
    UnifiedDownload,
    UnifiedDownloadStatus,
)
from soulspot.domain.ports.download_provider import (
    IDownloadProviderRegistry,
    ProviderDownload,
)
from soulspot.domain.value_objects import DownloadId, TrackId
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel

logger = logging.getLogger(__name__)


# Hey future me - mapping SoulSpot's internal DownloadStatus to UnifiedDownloadStatus
# Our Download entity uses DownloadStatus enum (defined in domain/entities/__init__.py)
# The UnifiedDownloadStatus is the new unified enum for the Download Manager
SOULSPOT_STATUS_MAPPING: dict[DownloadStatus, UnifiedDownloadStatus] = {
    DownloadStatus.WAITING: UnifiedDownloadStatus.WAITING,
    DownloadStatus.PENDING: UnifiedDownloadStatus.PENDING,
    DownloadStatus.QUEUED: UnifiedDownloadStatus.QUEUED,
    DownloadStatus.DOWNLOADING: UnifiedDownloadStatus.DOWNLOADING,
    DownloadStatus.COMPLETED: UnifiedDownloadStatus.COMPLETED,
    DownloadStatus.FAILED: UnifiedDownloadStatus.FAILED,
    DownloadStatus.CANCELLED: UnifiedDownloadStatus.CANCELLED,
}


@dataclass
class DownloadManagerConfig:
    """Configuration for the Download Manager Service."""

    # How old downloads to include in stats
    stats_history_hours: int = 24

    # Whether to show completed downloads in active list
    show_completed_in_active: bool = False

    # Maximum downloads to return per page
    max_active_downloads: int = 100


class DownloadManagerService:
    """Service for aggregating and managing downloads across all providers.

    This service is the single source of truth for download status in the UI.
    It combines data from:
    1. SoulSpot's Download table (internal queue: WAITING, PENDING)
    2. Download providers (external status: QUEUED, DOWNLOADING, etc.)
    3. Track table (metadata for display)
    """

    def __init__(
        self,
        session: AsyncSession,
        provider_registry: IDownloadProviderRegistry,
        config: DownloadManagerConfig | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            session: Database session for queries
            provider_registry: Registry of download providers
            config: Optional configuration
        """
        self._session = session
        self._registry = provider_registry
        self._config = config or DownloadManagerConfig()

    # Hey future me - this is THE MAIN METHOD that the API calls!
    # It returns a unified list of all active downloads from all sources.
    async def get_active_downloads(self) -> list[UnifiedDownload]:
        """Get all active downloads from all sources.

        Returns downloads in these states:
        - WAITING, PENDING (from SoulSpot's queue, not yet in provider)
        - QUEUED, DOWNLOADING, PAUSED, STALLED (from providers)

        Does NOT return:
        - COMPLETED, FAILED, CANCELLED (terminal states)

        Returns:
            List of UnifiedDownload objects sorted by created_at desc
        """
        active_downloads: list[UnifiedDownload] = []

        # 1. Get SoulSpot's internal queue (WAITING, PENDING downloads)
        internal_downloads = await self._get_internal_queue_downloads()
        active_downloads.extend(internal_downloads)

        # 2. Get downloads from all available providers
        provider_downloads = await self._get_provider_downloads()
        active_downloads.extend(provider_downloads)

        # 3. Sort by created_at (newest first)
        active_downloads.sort(key=lambda d: d.timestamps.created_at, reverse=True)

        # 4. Limit results
        return active_downloads[: self._config.max_active_downloads]

    async def get_queue_statistics(self) -> QueueStatistics:
        """Get statistics about the download queue.

        Returns counts of downloads in each state, plus recent
        completed/failed counts.
        """
        # Count by status in SoulSpot's Download table
        status_counts = await self._count_downloads_by_status()

        # Count completed/failed in last N hours
        since = datetime.now(UTC) - timedelta(hours=self._config.stats_history_hours)
        completed_today = await self._count_downloads_since(
            DownloadStatus.COMPLETED, since
        )
        failed_today = await self._count_downloads_since(DownloadStatus.FAILED, since)

        return QueueStatistics(
            waiting=status_counts.get(DownloadStatus.WAITING, 0),
            pending=status_counts.get(DownloadStatus.PENDING, 0),
            queued=status_counts.get(DownloadStatus.QUEUED, 0),
            downloading=status_counts.get(DownloadStatus.DOWNLOADING, 0),
            paused=0,  # Not tracked in our DB yet
            stalled=0,  # Not tracked in our DB yet
            completed_today=completed_today,
            failed_today=failed_today,
        )

    async def get_download_by_id(self, download_id: DownloadId) -> UnifiedDownload | None:
        """Get a specific download by its SoulSpot ID.

        Args:
            download_id: SoulSpot's download ID

        Returns:
            UnifiedDownload or None if not found
        """
        # Query our DB for the download
        result = await self._session.execute(
            select(DownloadModel).where(DownloadModel.id == str(download_id))
        )
        download_model = result.scalar_one_or_none()

        if not download_model:
            return None

        # Get track info
        track_info = await self._get_track_info(TrackId(download_model.track_id))

        # If download is in provider, get live status
        provider_status = None
        if download_model.source_url and download_model.status in (
            DownloadStatus.QUEUED.value,
            DownloadStatus.DOWNLOADING.value,
        ):
            provider_status = await self._get_provider_status_for_download(
                download_model.source_url
            )

        return self._create_unified_download(download_model, track_info, provider_status)

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    async def _get_internal_queue_downloads(self) -> list[UnifiedDownload]:
        """Get downloads from SoulSpot's internal queue (WAITING, PENDING).

        These are downloads that haven't been sent to a provider yet.
        """
        result = await self._session.execute(
            select(DownloadModel)
            .where(
                DownloadModel.status.in_([
                    DownloadStatus.WAITING.value,
                    DownloadStatus.PENDING.value,
                ])
            )
            .order_by(DownloadModel.created_at.desc())
            .limit(self._config.max_active_downloads)
        )
        download_models = result.scalars().all()

        unified: list[UnifiedDownload] = []
        for dm in download_models:
            track_info = await self._get_track_info(TrackId(dm.track_id))
            unified.append(self._create_unified_download(dm, track_info, None))

        return unified

    async def _get_provider_downloads(self) -> list[UnifiedDownload]:
        """Get active downloads from all available providers.

        Queries each provider, then joins with our Download table
        to enrich with SoulSpot metadata.
        """
        unified: list[UnifiedDownload] = []

        # Get available providers
        providers = await self._registry.get_available_providers()
        if not providers:
            logger.debug("No download providers available")
            return unified

        for provider in providers:
            try:
                provider_downloads = await provider.get_active_downloads()

                for pd in provider_downloads:
                    # Try to find matching download in our DB
                    download_model = await self._find_download_by_external_id(
                        pd.external_id
                    )

                    if download_model:
                        # Found in our DB - enrich with track info
                        track_info = await self._get_track_info(
                            TrackId(download_model.track_id)
                        )
                        unified.append(
                            self._create_unified_download(
                                download_model, track_info, pd
                            )
                        )
                    else:
                        # Not in our DB (orphan download in provider)
                        # Create a minimal UnifiedDownload from provider data
                        unified.append(
                            self._create_orphan_unified_download(provider, pd)
                        )

            except Exception as e:
                logger.error(
                    f"Failed to get downloads from {provider.provider_name}: {e}"
                )

        return unified

    async def _find_download_by_external_id(
        self, external_id: str
    ) -> DownloadModel | None:
        """Find a download in our DB by the provider's external ID.

        The external_id is stored in source_url field.
        """
        # external_id might be "username/filename" for slskd
        # We store it as "slskd://username/filename" in source_url
        possible_urls = [
            external_id,
            f"slskd://{external_id}",
            f"soulseek://{external_id}",
        ]

        for url in possible_urls:
            result = await self._session.execute(
                select(DownloadModel).where(DownloadModel.source_url == url)
            )
            model = result.scalar_one_or_none()
            if model:
                return model

        return None

    async def _get_track_info(self, track_id: TrackId) -> TrackInfo:
        """Load track info for display."""
        result = await self._session.execute(
            select(TrackModel).where(TrackModel.id == str(track_id))
        )
        track_model = result.scalar_one_or_none()

        if not track_model:
            return TrackInfo.unknown()

        return TrackInfo(
            title=track_model.title,
            artist=track_model.artist_name or "Unknown Artist",
            album=track_model.album,
            duration_ms=track_model.duration_ms,
            artwork_url=None,  # Could load from album if needed
        )

    async def _get_provider_status_for_download(
        self, source_url: str
    ) -> ProviderDownload | None:
        """Get live provider status for a download.

        Args:
            source_url: Our source_url field (e.g., "slskd://user/file")
        """
        # Determine provider from URL scheme
        if source_url.startswith("slskd://"):
            external_id = source_url[8:]  # Remove "slskd://"
            provider = self._registry.get_provider(DownloadProvider.SOULSEEK)
            if provider:
                return await provider.get_download_progress(external_id)

        return None

    async def _count_downloads_by_status(self) -> dict[DownloadStatus, int]:
        """Count downloads by status."""
        result = await self._session.execute(
            select(DownloadModel.status, func.count(DownloadModel.id))
            .group_by(DownloadModel.status)
        )
        rows = result.all()

        counts: dict[DownloadStatus, int] = {}
        for status_str, count in rows:
            try:
                status = DownloadStatus(status_str)
                counts[status] = count
            except ValueError:
                pass  # Unknown status, skip

        return counts

    async def _count_downloads_since(
        self, status: DownloadStatus, since: datetime
    ) -> int:
        """Count downloads with given status since timestamp."""
        result = await self._session.execute(
            select(func.count(DownloadModel.id))
            .where(DownloadModel.status == status.value)
            .where(DownloadModel.updated_at >= since)
        )
        return result.scalar() or 0

    def _create_unified_download(
        self,
        model: DownloadModel,
        track_info: TrackInfo,
        provider_status: ProviderDownload | None,
    ) -> UnifiedDownload:
        """Create UnifiedDownload from DB model and optional provider status.

        If provider_status is provided, it takes precedence for progress info.
        """
        # Determine status - prefer provider status if available
        if provider_status:
            status = provider_status.status
            progress = provider_status.progress or DownloadProgress.zero()
            status_message = provider_status.status_message
            error_message = provider_status.error_message
        else:
            status = SOULSPOT_STATUS_MAPPING.get(
                DownloadStatus(model.status), UnifiedDownloadStatus.QUEUED
            )
            progress = DownloadProgress(
                percent=model.progress_percent or 0.0,
                bytes_downloaded=0,
                total_bytes=0,
                speed_bytes_per_sec=0.0,
                eta_seconds=None,
            )
            status_message = None
            error_message = model.error_message

        # Build timestamps
        timestamps = DownloadTimestamps(
            created_at=model.created_at or datetime.now(UTC),
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

        # Determine provider from source_url
        provider = DownloadProvider.UNKNOWN
        provider_name = "Unknown"
        if model.source_url:
            if model.source_url.startswith("slskd://"):
                provider = DownloadProvider.SOULSEEK
                provider_name = "slskd"

        return UnifiedDownload(
            id=DownloadId(model.id),
            track_id=TrackId(model.track_id),
            track_info=track_info,
            provider=provider,
            provider_name=provider_name,
            external_id=model.source_url,
            status=status,
            status_message=status_message,
            error_message=error_message,
            progress=progress,
            timestamps=timestamps,
        )

    def _create_orphan_unified_download(
        self,
        provider: "IDownloadProvider",
        pd: ProviderDownload,
    ) -> UnifiedDownload:
        """Create UnifiedDownload for a download not in our DB.

        This happens when a download exists in the provider but we don't
        have a matching record. We show it anyway with limited info.
        """
        # Try to extract track info from filename
        filename = pd.filename
        title = filename.rsplit("/", 1)[-1] if "/" in filename else filename
        # Remove extension
        if "." in title:
            title = title.rsplit(".", 1)[0]

        track_info = TrackInfo(
            title=title,
            artist=pd.username or "Unknown",
        )

        return UnifiedDownload(
            id=DownloadId.generate(),  # Fake ID
            track_id=TrackId.generate(),  # Fake track ID
            track_info=track_info,
            provider=provider.provider_type,
            provider_name=provider.provider_name,
            external_id=pd.external_id,
            status=pd.status,
            status_message=pd.status_message,
            error_message=pd.error_message,
            progress=pd.progress or DownloadProgress.zero(),
            timestamps=DownloadTimestamps(created_at=datetime.now(UTC)),
            provider_metadata={"orphan": True},
        )
