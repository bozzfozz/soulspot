"""Application use cases - Business logic orchestration."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

# Type variables for generic use case pattern
TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class UseCase[TRequest, TResponse](ABC):
    """Base class for all use cases following command pattern."""

    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """Execute the use case with the given request.

        Orchestrates the business logic by coordinating repositories,
        domain services, and external integrations to fulfill the request.

        Args:
            request: Use case input containing all required parameters

        Returns:
            Response object containing results and status information

        Raises:
            DomainException: For business rule violations
            ValidationException: For invalid input data
        """
        pass


# Import concrete use cases (after UseCase definition to avoid circular imports)
from soulspot.application.use_cases.enrich_metadata import (  # noqa: E402
    EnrichMetadataUseCase,
)
from soulspot.application.use_cases.import_spotify_playlist import (  # noqa: E402
    ImportSpotifyPlaylistUseCase,
)
from soulspot.application.use_cases.search_and_download import (  # noqa: E402
    SearchAndDownloadTrackUseCase,
)

__all__ = [
    "UseCase",
    "ImportSpotifyPlaylistUseCase",
    "SearchAndDownloadTrackUseCase",
    "EnrichMetadataUseCase",
]
