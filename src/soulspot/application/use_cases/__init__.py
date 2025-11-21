"""Application use cases - Business logic orchestration."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

# Hey future me: This is the base command pattern for all use cases!
# WHY TypeVars? Type-safe request/response pairs - execute() input/output are strongly typed
# WHY generic syntax [TRequest, TResponse]? Python 3.12+ allows inline type parameters
# All use cases follow this pattern: take a Request object, return a Response object
# No side effects in constructors - all work happens in execute()
TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


# Listen up - this is the abstract base ALL use cases inherit from!
# WHY ABC? Enforces that subclasses implement execute() - catches missing methods at import time
# WHY async execute? All use cases involve I/O (DB, API calls, file ops) - must be async
# Request/Response pattern keeps interfaces clean - no function with 10 parameters
class UseCase[TRequest, TResponse](ABC):
    """Base class for all use cases following command pattern."""

    # Yo future me: execute() is the ONLY public method on use cases - single responsibility!
    # WHY abstractmethod? Forces every use case to implement this - no accidental empty use cases
    # Orchestration layer - coordinates repositories, services, domain logic
    # Should NOT contain business rules - those belong in domain entities/services
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


# Hey, imports are AFTER UseCase definition to prevent circular import hell!
# WHY noqa: E402? Ruff complains about imports not at top of file, but we need UseCase defined first
# These are the "main" use cases - others exist but aren't exported in __all__ (internal only)
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
