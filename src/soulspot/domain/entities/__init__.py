"""Domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    DownloadId,
    FilePath,
    PlaylistId,
    SpotifyUri,
    TrackId,
)


@dataclass
class Artist:
    """Artist entity representing a music artist."""

    id: ArtistId
    name: str
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate artist data."""
        if not self.name or not self.name.strip():
            raise ValueError("Artist name cannot be empty")

    def update_name(self, name: str) -> None:
        """Update artist name."""
        if not name or not name.strip():
            raise ValueError("Artist name cannot be empty")
        self.name = name
        self.updated_at = datetime.utcnow()


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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate album data."""
        if not self.title or not self.title.strip():
            raise ValueError("Album title cannot be empty")
        if self.release_year is not None and (self.release_year < 1900 or self.release_year > 2100):
            raise ValueError("Invalid release year")

    def update_artwork(self, artwork_path: FilePath) -> None:
        """Update album artwork."""
        self.artwork_path = artwork_path
        self.updated_at = datetime.utcnow()


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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

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
        self.updated_at = datetime.utcnow()

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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate playlist data."""
        if not self.name or not self.name.strip():
            raise ValueError("Playlist name cannot be empty")

    def add_track(self, track_id: TrackId) -> None:
        """Add a track to the playlist."""
        if track_id not in self.track_ids:
            self.track_ids.append(track_id)
            self.updated_at = datetime.utcnow()

    def remove_track(self, track_id: TrackId) -> None:
        """Remove a track from the playlist."""
        if track_id in self.track_ids:
            self.track_ids.remove(track_id)
            self.updated_at = datetime.utcnow()

    def clear_tracks(self) -> None:
        """Remove all tracks from the playlist."""
        self.track_ids.clear()
        self.updated_at = datetime.utcnow()

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
    target_path: FilePath | None = None
    source_url: str | None = None
    progress_percent: float = 0.0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate download data."""
        if self.progress_percent < 0.0 or self.progress_percent > 100.0:
            raise ValueError("Progress must be between 0 and 100")

    def start(self) -> None:
        """Mark download as started."""
        if self.status not in (DownloadStatus.PENDING, DownloadStatus.QUEUED):
            raise ValueError(f"Cannot start download in status {self.status}")
        self.status = DownloadStatus.DOWNLOADING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def update_progress(self, percent: float) -> None:
        """Update download progress."""
        if percent < 0.0 or percent > 100.0:
            raise ValueError("Progress must be between 0 and 100")
        self.progress_percent = percent
        self.updated_at = datetime.utcnow()

    def complete(self, file_path: FilePath) -> None:
        """Mark download as completed."""
        if self.status != DownloadStatus.DOWNLOADING:
            raise ValueError(f"Cannot complete download in status {self.status}")
        self.status = DownloadStatus.COMPLETED
        self.target_path = file_path
        self.progress_percent = 100.0
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """Mark download as failed."""
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        """Cancel the download."""
        if self.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
            raise ValueError(f"Cannot cancel download in status {self.status}")
        self.status = DownloadStatus.CANCELLED
        self.updated_at = datetime.utcnow()

    def is_finished(self) -> bool:
        """Check if download is in a terminal state."""
        return self.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)
