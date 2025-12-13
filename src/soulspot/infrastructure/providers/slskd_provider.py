"""Slskd Download Provider implementation.

This adapter implements IDownloadProvider for the slskd daemon.
It translates slskd's API responses into our unified DownloadProvider model.

slskd States Mapping:
- Queued → QUEUED
- InProgress → DOWNLOADING
- Completed → COMPLETED
- Cancelled, Aborted → CANCELLED
- Errored, TimedOut → FAILED
- Unknown/Connecting → STALLED
"""

import logging
from datetime import datetime
from typing import Any

from soulspot.domain.entities.download_manager import (
    DownloadProgress,
    DownloadProvider,
    UnifiedDownloadStatus,
)
from soulspot.domain.ports import ISlskdClient
from soulspot.domain.ports.download_provider import (
    IDownloadProvider,
    ProviderDownload,
)

logger = logging.getLogger(__name__)


# Hey future me - slskd download states are NOT documented well!
# I figured these out by testing and reading slskd source code.
# The API returns camelCase fields like "state", "percentComplete", etc.
# States come as lowercase strings from the API.
SLSKD_STATE_MAPPING: dict[str, UnifiedDownloadStatus] = {
    # Pre-transfer states
    "none": UnifiedDownloadStatus.QUEUED,
    "queued": UnifiedDownloadStatus.QUEUED,
    "requested": UnifiedDownloadStatus.QUEUED,  # Waiting for user to accept
    # Active states
    "initializing": UnifiedDownloadStatus.DOWNLOADING,
    "inprogress": UnifiedDownloadStatus.DOWNLOADING,
    "downloading": UnifiedDownloadStatus.DOWNLOADING,  # Alias
    # Terminal - Success
    "completed": UnifiedDownloadStatus.COMPLETED,
    "succeeded": UnifiedDownloadStatus.COMPLETED,  # Alias
    # Terminal - Failure
    "errored": UnifiedDownloadStatus.FAILED,
    "timedout": UnifiedDownloadStatus.FAILED,
    "rejected": UnifiedDownloadStatus.FAILED,  # User rejected our request
    "forbidden": UnifiedDownloadStatus.FAILED,  # User blocked us
    # Terminal - Cancelled
    "cancelled": UnifiedDownloadStatus.CANCELLED,
    "aborted": UnifiedDownloadStatus.CANCELLED,
    "removed": UnifiedDownloadStatus.CANCELLED,
}


class SlskdDownloadProvider(IDownloadProvider):
    """Download provider implementation for slskd (Soulseek).

    Uses the ISlskdClient port to communicate with slskd API.
    Converts slskd's response format to our unified DownloadProvider model.
    """

    # Hey future me - we track last_bytes per download to calculate speed!
    # slskd doesn't provide speed directly, so we calculate it from
    # bytes_transferred delta / time delta between polls.
    def __init__(self, slskd_client: ISlskdClient) -> None:
        """Initialize with slskd client.

        Args:
            slskd_client: ISlskdClient implementation for API calls
        """
        self._client = slskd_client
        self._last_poll_time: datetime | None = None
        self._last_bytes: dict[str, int] = {}  # external_id → bytes at last poll

    @property
    def provider_type(self) -> DownloadProvider:
        """Return SOULSEEK provider type."""
        return DownloadProvider.SOULSEEK

    @property
    def provider_name(self) -> str:
        """Return slskd as the provider name."""
        return "slskd"

    async def is_available(self) -> bool:
        """Check if slskd is reachable and authenticated.

        Uses the test_connection method which hits /api/v0/application.
        """
        try:
            result = await self._client.test_connection()
            return result.get("success", False)
        except Exception as e:
            logger.debug(f"slskd availability check failed: {e}")
            return False

    async def get_active_downloads(self) -> list[ProviderDownload]:
        """Get all active downloads from slskd.

        Returns downloads that are NOT in terminal states
        (completed, failed, cancelled).
        """
        try:
            raw_downloads = await self._client.list_downloads()
        except Exception as e:
            logger.error(f"Failed to get slskd downloads: {e}")
            return []

        # Calculate time delta for speed calculation
        now = datetime.now()
        time_delta_secs = 0.0
        if self._last_poll_time:
            time_delta_secs = (now - self._last_poll_time).total_seconds()
        self._last_poll_time = now

        active_downloads: list[ProviderDownload] = []

        for raw in raw_downloads:
            download = self._convert_to_provider_download(raw, time_delta_secs)
            if download and download.status.is_active:
                active_downloads.append(download)

        return active_downloads

    async def get_download_progress(
        self, external_id: str
    ) -> ProviderDownload | None:
        """Get progress for a specific download.

        Args:
            external_id: slskd download ID (format: "username/filename")
        """
        try:
            raw = await self._client.get_download_status(external_id)
            if raw.get("state") == "not_found":
                return None
            return self._convert_to_provider_download(raw, 0.0)
        except Exception as e:
            logger.error(f"Failed to get slskd download status for {external_id}: {e}")
            return None

    async def get_completed_downloads(
        self, since_hours: int = 24
    ) -> list[ProviderDownload]:
        """Get recently completed downloads from slskd.

        Note: slskd doesn't have a timestamp filter, so we get all
        and filter. This might be slow if there's a lot of history.
        """
        try:
            raw_downloads = await self._client.list_downloads()
        except Exception as e:
            logger.error(f"Failed to get slskd downloads: {e}")
            return []

        completed: list[ProviderDownload] = []

        for raw in raw_downloads:
            download = self._convert_to_provider_download(raw, 0.0)
            if download and download.status == UnifiedDownloadStatus.COMPLETED:
                completed.append(download)

        # Note: We can't filter by time because slskd doesn't give us completion timestamps
        # The since_hours parameter is ignored for slskd
        return completed

    # Hey future me - this is where the magic happens!
    # We convert slskd's raw JSON response to our ProviderDownload model.
    # Speed calculation: (current_bytes - last_bytes) / time_delta
    def _convert_to_provider_download(
        self,
        raw: dict[str, Any],
        time_delta_secs: float,
    ) -> ProviderDownload | None:
        """Convert slskd API response to ProviderDownload.

        Args:
            raw: Raw JSON dict from slskd API
            time_delta_secs: Seconds since last poll (for speed calc)

        Returns:
            ProviderDownload or None if conversion fails
        """
        try:
            external_id = raw.get("id", "")
            if not external_id:
                # Construct ID from username/filename
                username = raw.get("username", "")
                filename = raw.get("filename", "")
                if username and filename:
                    external_id = f"{username}/{filename}"
                else:
                    return None

            # Map state to unified status
            state_str = raw.get("state", "unknown").lower()
            status = SLSKD_STATE_MAPPING.get(state_str, UnifiedDownloadStatus.QUEUED)

            # Extract progress info
            percent = raw.get("progress", raw.get("percentComplete", 0)) or 0
            bytes_transferred = raw.get("bytes_transferred", raw.get("bytesTransferred", 0)) or 0
            total_bytes = raw.get("size", 0) or 0

            # Calculate speed from bytes delta
            speed = 0.0
            if time_delta_secs > 0 and external_id in self._last_bytes:
                bytes_delta = bytes_transferred - self._last_bytes[external_id]
                if bytes_delta > 0:
                    speed = bytes_delta / time_delta_secs

            # Update last bytes for next calculation
            self._last_bytes[external_id] = bytes_transferred

            # Calculate ETA
            eta_seconds: int | None = None
            if speed > 0 and total_bytes > 0:
                remaining_bytes = total_bytes - bytes_transferred
                if remaining_bytes > 0:
                    eta_seconds = int(remaining_bytes / speed)

            progress = DownloadProgress(
                percent=float(percent),
                bytes_downloaded=bytes_transferred,
                total_bytes=total_bytes,
                speed_bytes_per_sec=speed,
                eta_seconds=eta_seconds,
            )

            # Build ProviderDownload
            return ProviderDownload(
                external_id=external_id,
                filename=raw.get("filename", "Unknown"),
                username=raw.get("username"),
                status=status,
                status_message=raw.get("message"),
                error_message=raw.get("error") if status == UnifiedDownloadStatus.FAILED else None,
                progress=progress,
                raw_data=raw,
            )

        except Exception as e:
            logger.warning(f"Failed to convert slskd download: {e}")
            return None
