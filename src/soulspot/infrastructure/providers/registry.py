"""Download Provider Registry implementation.

Manages all configured download providers and provides methods
to query them collectively.
"""

import logging

from soulspot.domain.entities.download_manager import DownloadProvider
from soulspot.domain.ports.download_provider import (
    IDownloadProvider,
    IDownloadProviderRegistry,
)

logger = logging.getLogger(__name__)


class DownloadProviderRegistry(IDownloadProviderRegistry):
    """Registry for managing download provider implementations.

    Providers are registered at application startup and can be
    queried individually or collectively.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._providers: dict[DownloadProvider, IDownloadProvider] = {}

    def register(self, provider: IDownloadProvider) -> None:
        """Register a download provider.

        Args:
            provider: Provider implementation to register
        """
        self._providers[provider.provider_type] = provider
        logger.info(f"Registered download provider: {provider.provider_name}")

    def unregister(self, provider_type: DownloadProvider) -> None:
        """Unregister a download provider.

        Args:
            provider_type: Type of provider to unregister
        """
        if provider_type in self._providers:
            provider = self._providers.pop(provider_type)
            logger.info(f"Unregistered download provider: {provider.provider_name}")

    def get_all_providers(self) -> list[IDownloadProvider]:
        """Get all registered providers."""
        return list(self._providers.values())

    def get_provider(self, provider_type: DownloadProvider) -> IDownloadProvider | None:
        """Get a specific provider by type."""
        return self._providers.get(provider_type)

    async def get_available_providers(self) -> list[IDownloadProvider]:
        """Get all providers that are currently available.

        Checks is_available() on each provider concurrently.
        """
        available: list[IDownloadProvider] = []

        for provider in self._providers.values():
            try:
                if await provider.is_available():
                    available.append(provider)
                else:
                    logger.debug(f"Provider {provider.provider_name} is not available")
            except Exception as e:
                logger.warning(
                    f"Error checking {provider.provider_name} availability: {e}"
                )

        return available
