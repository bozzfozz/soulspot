"""DEPRECATED: ArtistSongsService has been removed.

This service was deleted on Jan 3, 2026 as part of cleanup.
Functionality has been migrated to:
- ProviderSyncOrchestrator for track syncing
- UnifiedLibraryWorker for background track operations

DO NOT USE THIS SERVICE - Refactor code to use the replacement services above.
"""


class ArtistSongsService:
    """DEPRECATED: Use ProviderSyncOrchestrator + UnifiedLibraryWorker instead."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "ArtistSongsService has been DEPRECATED and removed. "
            "Use ProviderSyncOrchestrator for track sync operations, "
            "or UnifiedLibraryWorker for background processing."
        )
