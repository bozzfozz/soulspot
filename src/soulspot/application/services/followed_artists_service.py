"""DEPRECATED: FollowedArtistsService has been removed.

This service was deleted on Jan 3, 2026 as part of cleanup.
Functionality has been migrated to:
- WatchlistService for managing artist watchlists
- ProviderSyncOrchestrator for multi-provider sync
- UnifiedLibraryWorker for background sync operations

DO NOT USE THIS SERVICE - Refactor code to use the replacement services above.
"""


class FollowedArtistsService:
    """DEPRECATED: Use WatchlistService + ProviderSyncOrchestrator instead."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "FollowedArtistsService has been DEPRECATED and removed. "
            "Use WatchlistService for artist management, "
            "ProviderSyncOrchestrator for multi-provider sync, "
            "or UnifiedLibraryWorker for background operations."
        )
