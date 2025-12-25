"""Infrastructure persistence layer."""

from .batch_utils import (
    IncrementalCommitter,
    batch_insert,
    batch_process,
    batch_update,
)
from .database import Database
from .models import (
    AlbumModel,
    ArtistModel,
    ArtistWatchlistModel,
    AutomationRuleModel,
    Base,
    DeezerSessionModel,
    DownloadModel,
    FilterRuleModel,
    PlaylistModel,
    PlaylistTrackModel,
    QualityUpgradeCandidateModel,
    TrackModel,
)
from .repositories import (
    AlbumRepository,
    ArtistRepository,
    ArtistWatchlistRepository,
    AutomationRuleRepository,
    DeezerSessionRepository,
    DownloadRepository,
    FilterRuleRepository,
    PlaylistRepository,
    QualityUpgradeCandidateRepository,
    TrackRepository,
)
from .retry import (
    DatabaseLockMetrics,
    execute_with_retry,
    is_lock_error,
    with_db_retry,
)

__all__ = [
    # Database
    "Database",
    "Base",
    # Models
    "ArtistModel",
    "AlbumModel",
    "TrackModel",
    "PlaylistModel",
    "PlaylistTrackModel",
    "DownloadModel",
    "ArtistWatchlistModel",
    "FilterRuleModel",
    "AutomationRuleModel",
    "QualityUpgradeCandidateModel",
    "DeezerSessionModel",
    # Repositories
    "ArtistRepository",
    "AlbumRepository",
    "TrackRepository",
    "PlaylistRepository",
    "DownloadRepository",
    "DeezerSessionRepository",
    "ArtistWatchlistRepository",
    "FilterRuleRepository",
    "AutomationRuleRepository",
    "QualityUpgradeCandidateRepository",
    # Retry utilities
    "with_db_retry",
    "execute_with_retry",
    "is_lock_error",
    "DatabaseLockMetrics",
    # Batch utilities
    "batch_process",
    "batch_insert",
    "batch_update",
    "IncrementalCommitter",
]
