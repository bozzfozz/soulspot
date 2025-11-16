"""Infrastructure persistence layer."""

from .database import Database
from .models import (
    AlbumModel,
    ArtistModel,
    ArtistWatchlistModel,
    AutomationRuleModel,
    Base,
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
    DownloadRepository,
    FilterRuleRepository,
    PlaylistRepository,
    QualityUpgradeCandidateRepository,
    TrackRepository,
)

__all__ = [
    "Database",
    "Base",
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
    "ArtistRepository",
    "AlbumRepository",
    "TrackRepository",
    "PlaylistRepository",
    "DownloadRepository",
    "ArtistWatchlistRepository",
    "FilterRuleRepository",
    "AutomationRuleRepository",
    "QualityUpgradeCandidateRepository",
]
