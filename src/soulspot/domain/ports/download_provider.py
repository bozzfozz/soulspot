"""Download Provider Port (Interface) for the Download Manager.

This module defines the interface that all download providers must implement.
Following Hexagonal Architecture (Ports & Adapters), this is a PORT in the
domain layer. Implementations live in the infrastructure layer.

Each provider (slskd, SABnzbd, etc.) implements this interface, allowing
the Download Manager Service to aggregate downloads from multiple sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from soulspot.domain.entities.download_manager import (
    DownloadProgress,
    DownloadProvider,
    UnifiedDownloadStatus,
)


@dataclass
class ProviderDownload:
    """Download info as reported by a provider.

    This is the "raw" data from a provider before enrichment with
    SoulSpot metadata (track info, etc.). The DownloadManagerService
    joins this with our Download table to create UnifiedDownload.
    """

    # Provider's identifier for this download
    external_id: str

    # File information (from provider)
    filename: str  # Full path/filename
    username: str | None = None  # For P2P: source user (slskd)

    # Status
    status: UnifiedDownloadStatus = UnifiedDownloadStatus.QUEUED
    status_message: str | None = None
    error_message: str | None = None

    # Progress
    progress: DownloadProgress | None = None

    # Provider-specific extra data
    raw_data: dict[str, Any] | None = None


class IDownloadProvider(ABC):
    """Interface for download provider implementations.

    Each download backend (slskd, SABnzbd, qBittorrent) implements this
    interface. The Download Manager Service uses providers to:
    1. Check if the provider is available
    2. Get list of active downloads
    3. Get detailed progress for specific downloads

    Implementations must be stateless - they query the external service
    on each call. Caching/rate-limiting is handled by the service layer.
    """

    @property
    @abstractmethod
    def provider_type(self) -> DownloadProvider:
        """Return the provider type enum value.

        Example:
            return DownloadProvider.SOULSEEK
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return human-readable provider name.

        Example:
            return "slskd"
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider/download client is available.

        Should be a fast check (health endpoint or simple query).
        Used to determine if we can poll this provider for status.

        Returns:
            True if provider is reachable and authenticated
        """
        pass

    @abstractmethod
    async def get_active_downloads(self) -> list[ProviderDownload]:
        """Get all active (non-completed) downloads from this provider.

        Returns downloads in any non-terminal state:
        - Queued, Downloading, Paused, Stalled

        Does NOT return:
        - Completed downloads (those are in history)
        - Downloads not yet sent to provider (WAITING/PENDING in SoulSpot)

        Returns:
            List of ProviderDownload objects
        """
        pass

    @abstractmethod
    async def get_download_progress(self, external_id: str) -> ProviderDownload | None:
        """Get progress for a specific download by provider's ID.

        Args:
            external_id: Provider's identifier for the download
                        (e.g., "username/filename" for slskd)

        Returns:
            ProviderDownload if found, None if not found
        """
        pass

    @abstractmethod
    async def get_completed_downloads(
        self, since_hours: int = 24
    ) -> list[ProviderDownload]:
        """Get recently completed downloads.

        Args:
            since_hours: How far back to look (default 24h)

        Returns:
            List of completed ProviderDownload objects
        """
        pass


class IDownloadProviderRegistry(ABC):
    """Registry for managing multiple download providers.

    The Download Manager uses this to iterate over all configured
    providers and aggregate their downloads into a unified view.
    """

    @abstractmethod
    def get_all_providers(self) -> list[IDownloadProvider]:
        """Get all registered download providers.

        Returns:
            List of all provider implementations
        """
        pass

    @abstractmethod
    def get_provider(self, provider_type: DownloadProvider) -> IDownloadProvider | None:
        """Get a specific provider by type.

        Args:
            provider_type: The provider type enum value

        Returns:
            Provider implementation or None if not registered
        """
        pass

    @abstractmethod
    async def get_available_providers(self) -> list[IDownloadProvider]:
        """Get all providers that are currently available.

        Checks is_available() on each provider and returns only
        those that are reachable and authenticated.

        Returns:
            List of available provider implementations
        """
        pass
