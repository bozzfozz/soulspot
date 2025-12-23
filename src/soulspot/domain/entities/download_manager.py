"""Download Manager domain entities and value objects.

This module contains the core domain model for the unified download manager.
It provides abstractions to display download status from ANY download provider
(slskd, SABnzbd, etc.) in a unified way.

Key Design Principles:
1. Provider-agnostic: Works with any download backend
2. Rich progress info: Speed, ETA, bytes, not just percentage
3. Track linking: Downloads are associated with SoulSpot tracks
4. Immutable value objects: DownloadProgress, TrackInfo
5. Status unification: All provider states map to UnifiedDownloadStatus
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from soulspot.domain.value_objects import DownloadId, TrackId


# Hey future me - this enum unifies ALL provider states into one vocabulary!
# Each provider has its own states (slskd: Queued/InProgress/Completed, SABnzbd: Downloading/Paused/etc)
# but the UI only needs to know these unified states. Makes the frontend SO much simpler.
# The mapping happens in each provider's implementation.
class UnifiedDownloadStatus(str, Enum):
    """Unified download status across all providers.

    Maps provider-specific states to these unified states:
    - slskd: Queued→QUEUED, InProgress→DOWNLOADING, Completed→COMPLETED, etc.
    - SABnzbd: Queued→QUEUED, Downloading→DOWNLOADING, Paused→PAUSED, etc.
    """

    # Pre-download states (SoulSpot internal)
    WAITING = "waiting"  # Waiting for provider to become available
    PENDING = "pending"  # Ready to send to provider

    # Provider states (actively managed by download client)
    QUEUED = "queued"  # In provider's queue, waiting to start
    DOWNLOADING = "downloading"  # Actively transferring data
    PAUSED = "paused"  # User paused or provider paused
    STALLED = "stalled"  # No progress for extended time (P2P connection issues)

    # Terminal states
    COMPLETED = "completed"  # Successfully downloaded
    FAILED = "failed"  # Download failed (see error_message)
    CANCELLED = "cancelled"  # User cancelled

    @property
    def is_active(self) -> bool:
        """Check if this is an active (non-terminal) state."""
        return self in {
            UnifiedDownloadStatus.WAITING,
            UnifiedDownloadStatus.PENDING,
            UnifiedDownloadStatus.QUEUED,
            UnifiedDownloadStatus.DOWNLOADING,
            UnifiedDownloadStatus.PAUSED,
            UnifiedDownloadStatus.STALLED,
        }

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal (final) state."""
        return self in {
            UnifiedDownloadStatus.COMPLETED,
            UnifiedDownloadStatus.FAILED,
            UnifiedDownloadStatus.CANCELLED,
        }


# Hey future me - this identifies which download backend is handling the download.
# Used for display ("Downloaded via slskd") and for routing operations.
# When you add a new provider, add it here FIRST.
class DownloadProvider(str, Enum):
    """Download provider/backend identifier."""

    SOULSEEK = "soulseek"  # Via slskd daemon
    USENET = "usenet"  # Via SABnzbd/NZBGet (future)
    TORRENT = "torrent"  # Via qBittorrent/Transmission (future)
    DIRECT = "direct"  # Direct HTTP download (future)
    UNKNOWN = "unknown"  # Fallback for legacy downloads


@dataclass(frozen=True)
class DownloadProgress:
    """Immutable value object representing download progress.

    Contains all metrics needed to display a progress bar with speed and ETA.
    Frozen=True makes this immutable and hashable.
    """

    percent: float  # 0.0 to 100.0
    bytes_downloaded: int  # Bytes transferred so far
    total_bytes: int  # Total file size in bytes (0 if unknown)
    speed_bytes_per_sec: float  # Current download speed (0 if not downloading)
    eta_seconds: int | None  # Estimated time remaining (None if unknown)

    def __post_init__(self) -> None:
        """Validate progress values."""
        # Use object.__setattr__ because frozen=True
        if self.percent < 0.0:
            object.__setattr__(self, "percent", 0.0)
        if self.percent > 100.0:
            object.__setattr__(self, "percent", 100.0)

    @property
    def speed_formatted(self) -> str:
        """Human-readable speed string."""
        if self.speed_bytes_per_sec < 1024:
            return f"{self.speed_bytes_per_sec:.0f} B/s"
        elif self.speed_bytes_per_sec < 1024 * 1024:
            return f"{self.speed_bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{self.speed_bytes_per_sec / (1024 * 1024):.2f} MB/s"

    @property
    def eta_formatted(self) -> str:
        """Human-readable ETA string."""
        if self.eta_seconds is None:
            return "Unknown"
        if self.eta_seconds < 60:
            return f"{self.eta_seconds}s"
        elif self.eta_seconds < 3600:
            mins = self.eta_seconds // 60
            secs = self.eta_seconds % 60
            return f"{mins}m {secs}s"
        else:
            hours = self.eta_seconds // 3600
            mins = (self.eta_seconds % 3600) // 60
            return f"{hours}h {mins}m"

    @property
    def size_formatted(self) -> str:
        """Human-readable size string (downloaded / total)."""

        def fmt(b: int) -> str:
            if b < 1024:
                return f"{b} B"
            elif b < 1024 * 1024:
                return f"{b / 1024:.1f} KB"
            elif b < 1024 * 1024 * 1024:
                return f"{b / (1024 * 1024):.1f} MB"
            else:
                return f"{b / (1024 * 1024 * 1024):.2f} GB"

        if self.total_bytes > 0:
            return f"{fmt(self.bytes_downloaded)} / {fmt(self.total_bytes)}"
        return fmt(self.bytes_downloaded)

    @classmethod
    def zero(cls) -> "DownloadProgress":
        """Create a zero-progress instance."""
        return cls(
            percent=0.0,
            bytes_downloaded=0,
            total_bytes=0,
            speed_bytes_per_sec=0.0,
            eta_seconds=None,
        )

    @classmethod
    def completed(cls, total_bytes: int) -> "DownloadProgress":
        """Create a completed-progress instance."""
        return cls(
            percent=100.0,
            bytes_downloaded=total_bytes,
            total_bytes=total_bytes,
            speed_bytes_per_sec=0.0,
            eta_seconds=0,
        )


@dataclass(frozen=True)
class TrackInfo:
    """Immutable value object with track metadata for display.

    This is a lightweight DTO - not the full Track entity!
    Used when we just need display info without loading the whole track.
    """

    title: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    artwork_url: str | None = None

    @property
    def display_name(self) -> str:
        """Formatted display string: Artist - Title."""
        return f"{self.artist} - {self.title}"

    @classmethod
    def unknown(cls) -> "TrackInfo":
        """Create an unknown track info instance."""
        return cls(title="Unknown Track", artist="Unknown Artist")


@dataclass(frozen=True)
class DownloadTimestamps:
    """Immutable value object for download timing information."""

    created_at: datetime  # When SoulSpot created the download entry
    queued_at: datetime | None = None  # When sent to provider queue
    started_at: datetime | None = None  # When transfer actually started
    completed_at: datetime | None = None  # When transfer finished


# Hey future me - this is THE main entity for the download manager!
# It unifies data from: SoulSpot's Download table + Provider's live status + Track metadata.
# The UI renders THIS, not raw provider responses. Notice it's a dataclass, not frozen,
# because we update it during polling cycles.
@dataclass
class UnifiedDownload:
    """Unified download entity combining SoulSpot metadata with provider status.

    This is the primary entity for the Download Manager UI. It combines:
    1. SoulSpot's internal download record (id, track_id)
    2. Provider's live status (progress, speed, ETA)
    3. Track metadata for display (title, artist)

    The Download Manager Service creates these by joining data from multiple sources.
    """

    # SoulSpot identifiers
    id: DownloadId  # SoulSpot's download ID
    track_id: TrackId  # Link to track in library

    # Track info for display (loaded from Track entity or provider filename)
    track_info: TrackInfo

    # Provider information
    provider: DownloadProvider  # Which backend (slskd, usenet, etc.)
    provider_name: str  # Display name ("slskd", "SABnzbd")
    external_id: str | None  # Provider's download ID (slskd: "user/filename")

    # Current status
    status: UnifiedDownloadStatus
    status_message: str | None = None  # Additional context (e.g., "Waiting for slots")
    error_message: str | None = None  # Error details if failed

    # Progress metrics
    progress: DownloadProgress = field(default_factory=DownloadProgress.zero)

    # Timing
    timestamps: DownloadTimestamps = field(
        default_factory=lambda: DownloadTimestamps(created_at=datetime.now())
    )

    # Provider-specific metadata (for advanced UI)
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if download is in an active (non-terminal) state."""
        return self.status.is_active

    @property
    def can_cancel(self) -> bool:
        """Check if download can be cancelled."""
        return self.status in {
            UnifiedDownloadStatus.WAITING,
            UnifiedDownloadStatus.PENDING,
            UnifiedDownloadStatus.QUEUED,
            UnifiedDownloadStatus.DOWNLOADING,
            UnifiedDownloadStatus.PAUSED,
            UnifiedDownloadStatus.STALLED,
        }

    @property
    def can_retry(self) -> bool:
        """Check if download can be retried."""
        return self.status in {
            UnifiedDownloadStatus.FAILED,
            UnifiedDownloadStatus.CANCELLED,
        }


@dataclass(frozen=True)
class QueueStatistics:
    """Statistics about the download queue.

    Used for the summary bar: "15 waiting | 3 pending | 2 downloading | 156 completed today"
    """

    waiting: int = 0  # Waiting for provider availability
    pending: int = 0  # Ready to send to provider
    queued: int = 0  # In provider's queue
    downloading: int = 0  # Actively downloading
    paused: int = 0  # Paused
    stalled: int = 0  # Stalled (no progress)
    completed_today: int = 0  # Completed in last 24h
    failed_today: int = 0  # Failed in last 24h

    @property
    def total_active(self) -> int:
        """Total active (non-terminal) downloads."""
        return (
            self.waiting
            + self.pending
            + self.queued
            + self.downloading
            + self.paused
            + self.stalled
        )

    @property
    def total_in_progress(self) -> int:
        """Downloads actually transferring or queued in provider."""
        return self.queued + self.downloading + self.stalled

    @property
    def summary_text(self) -> str:
        """Human-readable summary for UI."""
        parts = []
        if self.waiting > 0:
            parts.append(f"{self.waiting} waiting")
        if self.pending > 0:
            parts.append(f"{self.pending} pending")
        if self.queued > 0:
            parts.append(f"{self.queued} queued")
        if self.downloading > 0:
            parts.append(f"{self.downloading} downloading")
        if self.paused > 0:
            parts.append(f"{self.paused} paused")
        if self.completed_today > 0:
            parts.append(f"{self.completed_today} completed today")
        if self.failed_today > 0:
            parts.append(f"{self.failed_today} failed")

        return " │ ".join(parts) if parts else "No downloads"
