"""Value objects for the domain layer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from soulspot.domain.exceptions import ValidationException


@dataclass(frozen=True)
class ArtistId:
    """Unique identifier for an Artist."""

    value: UUID

    @classmethod
    def generate(cls) -> "ArtistId":
        """Generate a new ArtistId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "ArtistId":
        """Create ArtistId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid ArtistId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class AlbumId:
    """Unique identifier for an Album."""

    value: UUID

    @classmethod
    def generate(cls) -> "AlbumId":
        """Generate a new AlbumId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "AlbumId":
        """Create AlbumId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid AlbumId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class TrackId:
    """Unique identifier for a Track."""

    value: UUID

    @classmethod
    def generate(cls) -> "TrackId":
        """Generate a new TrackId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "TrackId":
        """Create TrackId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid TrackId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class PlaylistId:
    """Unique identifier for a Playlist."""

    value: UUID

    @classmethod
    def generate(cls) -> "PlaylistId":
        """Generate a new PlaylistId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "PlaylistId":
        """Create PlaylistId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid PlaylistId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class DownloadId:
    """Unique identifier for a Download."""

    value: UUID

    @classmethod
    def generate(cls) -> "DownloadId":
        """Generate a new DownloadId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "DownloadId":
        """Create DownloadId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid DownloadId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class FilePath:
    """Value object representing a file path."""

    value: Path

    def __post_init__(self) -> None:
        """Validate the file path."""
        if not isinstance(self.value, Path):
            object.__setattr__(self, "value", Path(self.value))

    @classmethod
    def from_string(cls, path: str) -> "FilePath":
        """Create FilePath from string."""
        if not path:
            raise ValidationException("File path cannot be empty")
        return cls(value=Path(path))

    def __str__(self) -> str:
        return str(self.value)

    def exists(self) -> bool:
        """Check if the path exists."""
        return self.value.exists()

    def is_file(self) -> bool:
        """Check if the path is a file."""
        return self.value.is_file()

    def is_directory(self) -> bool:
        """Check if the path is a directory."""
        return self.value.is_dir()


@dataclass(frozen=True)
class SpotifyUri:
    """Value object representing a Spotify URI."""

    value: str

    def __post_init__(self) -> None:
        """Validate the Spotify URI format."""
        if not self.value.startswith("spotify:"):
            raise ValidationException(f"Invalid Spotify URI format: {self.value}")

        parts = self.value.split(":")
        if len(parts) < 3:
            raise ValidationException(f"Invalid Spotify URI format: {self.value}")

        if parts[1] not in ("track", "album", "artist", "playlist", "user"):
            raise ValidationException(f"Unsupported Spotify URI type: {parts[1]}")

    @classmethod
    def from_string(cls, uri: str) -> "SpotifyUri":
        """Create SpotifyUri from string."""
        return cls(value=uri)

    @classmethod
    def from_url(cls, url: str) -> "SpotifyUri":
        """Create SpotifyUri from Spotify URL."""
        # Extract ID from URL like https://open.spotify.com/track/1234567890
        if "spotify.com/" not in url:
            raise ValidationException(f"Invalid Spotify URL: {url}")

        parts = url.rstrip("/").split("/")
        if len(parts) < 2:
            raise ValidationException(f"Invalid Spotify URL format: {url}")

        resource_type = parts[-2]
        resource_id = parts[-1].split("?")[0]  # Remove query params

        return cls(value=f"spotify:{resource_type}:{resource_id}")

    def __str__(self) -> str:
        return self.value

    @property
    def resource_type(self) -> str:
        """Get the resource type (track, album, artist, etc.)."""
        return self.value.split(":")[1]

    @property
    def resource_id(self) -> str:
        """Get the resource ID."""
        return self.value.split(":")[2]


@dataclass(frozen=True)
class WatchlistId:
    """Unique identifier for an Artist Watchlist."""

    value: UUID

    @classmethod
    def generate(cls) -> "WatchlistId":
        """Generate a new WatchlistId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "WatchlistId":
        """Create WatchlistId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid WatchlistId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class FilterRuleId:
    """Unique identifier for a Filter Rule."""

    value: UUID

    @classmethod
    def generate(cls) -> "FilterRuleId":
        """Generate a new FilterRuleId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "FilterRuleId":
        """Create FilterRuleId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid FilterRuleId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class AutomationRuleId:
    """Unique identifier for an Automation Rule."""

    value: UUID

    @classmethod
    def generate(cls) -> "AutomationRuleId":
        """Generate a new AutomationRuleId."""
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, value: str) -> "AutomationRuleId":
        """Create AutomationRuleId from string."""
        try:
            return cls(value=UUID(value))
        except ValueError as e:
            raise ValidationException(f"Invalid AutomationRuleId format: {value}") from e

    def __str__(self) -> str:
        return str(self.value)
