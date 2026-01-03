"""DEPRECATED: DiscographyService has been removed.

This service was deleted on Jan 3, 2026 as part of cleanup.
Functionality has been migrated to:
- WatchlistService for discography completeness checks
- UnifiedLibraryWorker for discography scanning
- ProviderSyncOrchestrator for album sync

DO NOT USE THIS SERVICE - Refactor code to use the replacement services above.
"""


class DiscographyService:
    """DEPRECATED: Use WatchlistService + UnifiedLibraryWorker instead."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "DiscographyService has been DEPRECATED and removed. "
            "Use WatchlistService for discography checks, "
            "or UnifiedLibraryWorker for background discography scanning."
        )
