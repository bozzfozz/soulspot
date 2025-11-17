"""Domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from soulspot.domain.entities.widget import Page, Widget, WidgetInstance
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    AutomationRuleId,
    DownloadId,
    FilePath,
    FilterRuleId,
    PlaylistId,
    SpotifyUri,
    TrackId,
    WatchlistId,
)


class MetadataSource(str, Enum):
    """Source of metadata."""

    MANUAL = "manual"  # User-provided overrides
    MUSICBRAINZ = "musicbrainz"
    SPOTIFY = "spotify"
    LASTFM = "lastfm"


@dataclass
class Artist:
    """Artist entity representing a music artist."""

    id: ArtistId
    name: str
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    lastfm_url: str | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate artist data."""
        if not self.name or not self.name.strip():
            raise ValueError("Artist name cannot be empty")

    def update_name(self, name: str) -> None:
        """Update artist name."""
        if not name or not name.strip():
            raise ValueError("Artist name cannot be empty")
        self.name = name
        self.updated_at = datetime.now(UTC)


@dataclass
class Album:
    """Album entity representing a music album."""

    id: AlbumId
    title: str
    artist_id: ArtistId
    release_year: int | None = None
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    artwork_path: FilePath | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate album data."""
        if not self.title or not self.title.strip():
            raise ValueError("Album title cannot be empty")
        if self.release_year is not None and (
            self.release_year < 1900 or self.release_year > 2100
        ):
            raise ValueError("Invalid release year")

    def update_artwork(self, artwork_path: FilePath) -> None:
        """Update album artwork."""
        self.artwork_path = artwork_path
        self.updated_at = datetime.now(UTC)


@dataclass
class Track:
    """Track entity representing a music track."""

    id: TrackId
    title: str
    artist_id: ArtistId
    album_id: AlbumId | None = None
    duration_ms: int = 0
    track_number: int | None = None
    disc_number: int = 1
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    isrc: str | None = None
    file_path: FilePath | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate track data."""
        if not self.title or not self.title.strip():
            raise ValueError("Track title cannot be empty")
        if self.duration_ms < 0:
            raise ValueError("Duration cannot be negative")
        if self.track_number is not None and self.track_number < 1:
            raise ValueError("Track number must be positive")
        if self.disc_number < 1:
            raise ValueError("Disc number must be positive")

    def update_file_path(self, file_path: FilePath) -> None:
        """Update track file path."""
        self.file_path = file_path
        self.updated_at = datetime.now(UTC)

    def is_downloaded(self) -> bool:
        """Check if track has been downloaded."""
        return self.file_path is not None and self.file_path.exists()


class PlaylistSource(str, Enum):
    """Source of the playlist."""

    SPOTIFY = "spotify"
    MANUAL = "manual"


@dataclass
class Playlist:
    """Playlist entity representing a collection of tracks."""

    id: PlaylistId
    name: str
    description: str | None = None
    source: PlaylistSource = PlaylistSource.MANUAL
    spotify_uri: SpotifyUri | None = None
    track_ids: list[TrackId] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate playlist data."""
        if not self.name or not self.name.strip():
            raise ValueError("Playlist name cannot be empty")

    def add_track(self, track_id: TrackId) -> None:
        """Add a track to the playlist."""
        if track_id not in self.track_ids:
            self.track_ids.append(track_id)
            self.updated_at = datetime.now(UTC)

    def remove_track(self, track_id: TrackId) -> None:
        """Remove a track from the playlist."""
        if track_id in self.track_ids:
            self.track_ids.remove(track_id)
            self.updated_at = datetime.now(UTC)

    def clear_tracks(self) -> None:
        """Remove all tracks from the playlist."""
        self.track_ids.clear()
        self.updated_at = datetime.now(UTC)

    def track_count(self) -> int:
        """Get the number of tracks in the playlist."""
        return len(self.track_ids)


class DownloadStatus(str, Enum):
    """Status of a download."""

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Download:
    """Download entity representing a track download operation."""

    id: DownloadId
    track_id: TrackId
    status: DownloadStatus = DownloadStatus.PENDING
    priority: int = 0  # Higher value = higher priority
    target_path: FilePath | None = None
    source_url: str | None = None
    progress_percent: float = 0.0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate download data."""
        if self.progress_percent < 0.0 or self.progress_percent > 100.0:
            raise ValueError("Progress must be between 0 and 100")

    def start(self) -> None:
        """Mark download as started."""
        if self.status not in (DownloadStatus.PENDING, DownloadStatus.QUEUED):
            raise ValueError(f"Cannot start download in status {self.status}")
        self.status = DownloadStatus.DOWNLOADING
        self.started_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def update_progress(self, percent: float) -> None:
        """Update download progress."""
        if percent < 0.0 or percent > 100.0:
            raise ValueError("Progress must be between 0 and 100")
        self.progress_percent = percent
        self.updated_at = datetime.now(UTC)

    def complete(self, file_path: FilePath) -> None:
        """Mark download as completed."""
        if self.status != DownloadStatus.DOWNLOADING:
            raise ValueError(f"Cannot complete download in status {self.status}")
        self.status = DownloadStatus.COMPLETED
        self.target_path = file_path
        self.progress_percent = 100.0
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def fail(self, error_message: str) -> None:
        """Mark download as failed."""
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.now(UTC)

    def cancel(self) -> None:
        """Cancel the download."""
        if self.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
            raise ValueError(f"Cannot cancel download in status {self.status}")
        self.status = DownloadStatus.CANCELLED
        self.updated_at = datetime.now(UTC)

    def update_priority(self, priority: int) -> None:
        """Update download priority.

        Args:
            priority: New priority value (0-2, where 0=P0 highest, 1=P1 medium, 2=P2 low)
        """
        if priority < 0 or priority > 2:
            raise ValueError("Priority must be between 0 (P0) and 2 (P2)")
        self.priority = priority
        self.updated_at = datetime.now(UTC)

    def pause(self) -> None:
        """Pause the download."""
        if self.status != DownloadStatus.DOWNLOADING:
            raise ValueError(f"Cannot pause download in status {self.status}")
        self.status = DownloadStatus.QUEUED
        self.updated_at = datetime.now(UTC)

    def resume(self) -> None:
        """Resume a paused download."""
        if self.status != DownloadStatus.QUEUED:
            raise ValueError(f"Cannot resume download in status {self.status}")
        self.status = DownloadStatus.DOWNLOADING
        self.updated_at = datetime.now(UTC)

    def is_finished(self) -> bool:
        """Check if download is in a terminal state."""
        return self.status in (
            DownloadStatus.COMPLETED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED,
        )


class ScanStatus(str, Enum):
    """Status of a library scan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LibraryScan:
    """Library scan entity representing a library scanning operation."""

    id: str
    status: ScanStatus
    scan_path: str
    total_files: int = 0
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    broken_files: int = 0
    duplicate_files: int = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def start(self) -> None:
        """Mark scan as started."""
        if self.status != ScanStatus.PENDING:
            raise ValueError(f"Cannot start scan in status {self.status}")
        self.status = ScanStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def update_progress(
        self,
        scanned_files: int,
        new_files: int = 0,
        updated_files: int = 0,
        broken_files: int = 0,
        duplicate_files: int = 0,
    ) -> None:
        """Update scan progress."""
        self.scanned_files = scanned_files
        self.new_files += new_files
        self.updated_files += updated_files
        self.broken_files += broken_files
        self.duplicate_files += duplicate_files
        self.updated_at = datetime.now(UTC)

    def complete(self) -> None:
        """Mark scan as completed."""
        if self.status != ScanStatus.RUNNING:
            raise ValueError(f"Cannot complete scan in status {self.status}")
        self.status = ScanStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def fail(self, error_message: str) -> None:
        """Mark scan as failed."""
        self.status = ScanStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def cancel(self) -> None:
        """Cancel the scan."""
        if self.status not in (ScanStatus.PENDING, ScanStatus.RUNNING):
            raise ValueError(f"Cannot cancel scan in status {self.status}")
        self.status = ScanStatus.CANCELLED
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def get_progress_percent(self) -> float:
        """Calculate scan progress percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.scanned_files / self.total_files) * 100.0


@dataclass
class FileDuplicate:
    """File duplicate entity representing duplicate file tracking."""

    id: str
    file_hash: str
    file_hash_algorithm: str
    primary_track_id: TrackId | None = None
    duplicate_count: int = 1
    total_size_bytes: int = 0
    resolved: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_resolved(self, primary_track_id: TrackId) -> None:
        """Mark duplicate as resolved with a primary track."""
        self.resolved = True
        self.primary_track_id = primary_track_id
        self.updated_at = datetime.now(UTC)

    def add_duplicate(self, file_size: int) -> None:
        """Add a duplicate file."""
        self.duplicate_count += 1
        self.total_size_bytes += file_size
        self.updated_at = datetime.now(UTC)


class WatchlistStatus(str, Enum):
    """Status of an artist watchlist."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class ArtistWatchlist:
    """Artist watchlist entity for monitoring new releases."""

    id: WatchlistId
    artist_id: ArtistId
    status: WatchlistStatus = WatchlistStatus.ACTIVE
    check_frequency_hours: int = 24  # How often to check for new releases
    auto_download: bool = True  # Automatically download new releases
    quality_profile: str = "high"  # Quality preference (low, medium, high, lossless)
    last_checked_at: datetime | None = None
    last_release_date: datetime | None = None
    total_releases_found: int = 0
    total_downloads_triggered: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate watchlist data."""
        if self.check_frequency_hours < 1:
            raise ValueError("Check frequency must be at least 1 hour")
        if self.quality_profile not in ("low", "medium", "high", "lossless"):
            raise ValueError(
                "Quality profile must be one of: low, medium, high, lossless"
            )

    def pause(self) -> None:
        """Pause the watchlist."""
        if self.status == WatchlistStatus.DISABLED:
            raise ValueError("Cannot pause a disabled watchlist")
        self.status = WatchlistStatus.PAUSED
        self.updated_at = datetime.now(UTC)

    def resume(self) -> None:
        """Resume the watchlist."""
        if self.status == WatchlistStatus.DISABLED:
            raise ValueError("Cannot resume a disabled watchlist")
        self.status = WatchlistStatus.ACTIVE
        self.updated_at = datetime.now(UTC)

    def disable(self) -> None:
        """Disable the watchlist."""
        self.status = WatchlistStatus.DISABLED
        self.updated_at = datetime.now(UTC)

    def update_check(
        self, releases_found: int = 0, downloads_triggered: int = 0
    ) -> None:
        """Update check statistics."""
        self.last_checked_at = datetime.now(UTC)
        self.total_releases_found += releases_found
        self.total_downloads_triggered += downloads_triggered
        self.updated_at = datetime.now(UTC)

    def should_check(self) -> bool:
        """Check if it's time to check for new releases."""
        if self.status != WatchlistStatus.ACTIVE:
            return False
        if self.last_checked_at is None:
            return True
        hours_since_check = (
            datetime.now(UTC) - self.last_checked_at
        ).total_seconds() / 3600
        return hours_since_check >= self.check_frequency_hours


class FilterType(str, Enum):
    """Type of filter rule."""

    WHITELIST = "whitelist"  # Allow only these
    BLACKLIST = "blacklist"  # Block these


class FilterTarget(str, Enum):
    """Target of filter rule."""

    KEYWORD = "keyword"  # Filter by keyword in title/artist
    USER = "user"  # Filter by slskd user
    FORMAT = "format"  # Filter by file format
    BITRATE = "bitrate"  # Filter by minimum bitrate


@dataclass
class FilterRule:
    """Filter rule entity for whitelist/blacklist filtering."""

    id: FilterRuleId
    name: str
    filter_type: FilterType
    target: FilterTarget
    pattern: str  # Regex pattern or exact match
    is_regex: bool = False
    enabled: bool = True
    priority: int = 0  # Higher priority rules evaluated first
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate filter rule data."""
        if not self.name or not self.name.strip():
            raise ValueError("Filter rule name cannot be empty")
        if not self.pattern or not self.pattern.strip():
            raise ValueError("Filter pattern cannot be empty")

    def enable(self) -> None:
        """Enable the filter rule."""
        self.enabled = True
        self.updated_at = datetime.now(UTC)

    def disable(self) -> None:
        """Disable the filter rule."""
        self.enabled = False
        self.updated_at = datetime.now(UTC)

    def update_pattern(self, pattern: str, is_regex: bool = False) -> None:
        """Update the filter pattern."""
        if not pattern or not pattern.strip():
            raise ValueError("Filter pattern cannot be empty")
        self.pattern = pattern
        self.is_regex = is_regex
        self.updated_at = datetime.now(UTC)


class AutomationTrigger(str, Enum):
    """Trigger for automation rule."""

    NEW_RELEASE = "new_release"  # Triggered when new release is detected
    MISSING_ALBUM = "missing_album"  # Triggered for missing album in discography
    QUALITY_UPGRADE = "quality_upgrade"  # Triggered for quality upgrade opportunity
    MANUAL = "manual"  # Manually triggered


class AutomationAction(str, Enum):
    """Action to perform in automation rule."""

    SEARCH_AND_DOWNLOAD = "search_and_download"
    NOTIFY_ONLY = "notify_only"
    ADD_TO_QUEUE = "add_to_queue"


@dataclass
class AutomationRule:
    """Automation rule entity for automated workflows."""

    id: AutomationRuleId
    name: str
    trigger: AutomationTrigger
    action: AutomationAction
    enabled: bool = True
    priority: int = 0
    quality_profile: str = "high"
    apply_filters: bool = True  # Apply filter rules
    auto_process: bool = True  # Run post-processing pipeline
    description: str | None = None
    last_triggered_at: datetime | None = None
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate automation rule data."""
        if not self.name or not self.name.strip():
            raise ValueError("Automation rule name cannot be empty")
        if self.quality_profile not in ("low", "medium", "high", "lossless"):
            raise ValueError(
                "Quality profile must be one of: low, medium, high, lossless"
            )

    def enable(self) -> None:
        """Enable the automation rule."""
        self.enabled = True
        self.updated_at = datetime.now(UTC)

    def disable(self) -> None:
        """Disable the automation rule."""
        self.enabled = False
        self.updated_at = datetime.now(UTC)

    def record_execution(self, success: bool) -> None:
        """Record an execution of this rule."""
        self.last_triggered_at = datetime.now(UTC)
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        self.updated_at = datetime.now(UTC)


@dataclass
class QualityUpgradeCandidate:
    """Quality upgrade candidate entity for tracking upgrade opportunities."""

    id: str
    track_id: TrackId
    current_bitrate: int
    current_format: str
    target_bitrate: int
    target_format: str
    improvement_score: float  # 0.0 to 1.0 indicating improvement potential
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed: bool = False
    download_id: DownloadId | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate quality upgrade candidate data."""
        if self.improvement_score < 0.0 or self.improvement_score > 1.0:
            raise ValueError("Improvement score must be between 0.0 and 1.0")
        if self.current_bitrate < 0 or self.target_bitrate < 0:
            raise ValueError("Bitrate cannot be negative")

    def mark_processed(self, download_id: DownloadId | None = None) -> None:
        """Mark candidate as processed."""
        self.processed = True
        self.download_id = download_id
        self.updated_at = datetime.now(UTC)


__all__ = [
    # Existing entities
    "Artist",
    "Album",
    "Track",
    "Playlist",
    "Download",
    "LibraryScan",
    "FileDuplicate",
    "ArtistWatchlist",
    "FilterRule",
    "AutomationRule",
    "QualityUpgradeCandidate",
    # Enums
    "MetadataSource",
    "PlaylistSource",
    "DownloadStatus",
    "ScanStatus",
    "WatchlistStatus",
    "FilterType",
    "FilterTarget",
    "AutomationTrigger",
    "AutomationAction",
    # Widget entities (new)
    "Widget",
    "Page",
    "WidgetInstance",
]
