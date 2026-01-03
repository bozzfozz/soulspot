"""Value objects for the domain layer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from soulspot.domain.exceptions import ValidationException

# Album type exports
from soulspot.domain.value_objects.album_types import (
    DIVERSITY_THRESHOLD,
    DOMINANT_ARTIST_THRESHOLD,
    MIN_TRACKS_FOR_DIVERSITY,
    VARIOUS_ARTISTS_PATTERNS,
    CompilationDetectionResult,
    PrimaryAlbumType,
    SecondaryAlbumType,
    calculate_track_diversity,
    detect_compilation,
    detect_compilation_from_track_artists,
    is_various_artists,
)

# Artist normalization exports (for matching and deduplication)
from soulspot.domain.value_objects.artist_normalization import (
    ARTIST_PREFIXES,
    ARTIST_SUFFIXES,
    extract_sort_name,
    normalize_artist_name,
    normalize_for_fuzzy_match,
)

# Folder parsing exports (Lidarr library structure parsing)
from soulspot.domain.value_objects.folder_parsing import (
    LibraryFolderParser,
    LibraryScanResult,
    ParsedAlbumFolder,
    ParsedTrackFilename,
    ScannedAlbum,
    ScannedArtist,
    ScannedTrack,
    is_audio_file,
    is_disc_folder,
    parse_album_folder,
    parse_track_filename,
)

# ImageRef - Standard-Struktur für alle Bilder (artist.image, album.cover, etc.)
from soulspot.domain.value_objects.image_ref import ImageRef

# Naming exports (Lidarr-style file/folder naming)
from soulspot.domain.value_objects.naming import (
    ColonReplacement,
    MultiDiscStyle,
    NamingConfig,
    NamingService,
    clean_name,
    sort_name,
)

# Quality profile exports (single source of truth for audio quality standards)
# Hey future me - use QualityProfile enum instead of string "high"/"low"/etc!
from soulspot.domain.value_objects.quality_profile import (
    QualityConfig,
    QualityProfile,
    QUALITY_PROFILES_DICT,  # Legacy compatibility only
)


# Hey future me, ArtistId is a VALUE OBJECT (Domain-Driven Design)! It's NOT just a UUID - it's a
# type-safe wrapper that ensures IDs are always valid UUIDs. The @dataclass(frozen=True) makes it
# IMMUTABLE - once created, can't change. This prevents bugs like accidentally swapping artist_id and
# track_id (they're different types now). Use .generate() for new IDs, .from_string() to parse from
# DB/API. The __str__ returns UUID string for serialization. Value objects are compared by VALUE not
# identity (two ArtistId with same UUID are equal even if different Python objects).
@dataclass(frozen=True)
class ArtistId:
    """Unique identifier for an Artist."""

    value: UUID

    # Yo, generate() creates a NEW random UUID! Use this when creating new artists: `artist_id =
    # ArtistId.generate()`. It's a class method (not instance method) because you call it BEFORE you
    # have an instance. The uuid4() generates cryptographically random UUID (version 4). Don't use
    # sequential IDs or you leak how many artists you have! UUID collision is astronomically unlikely.
    @classmethod
    def generate(cls) -> "ArtistId":
        """Generate a new ArtistId."""
        return cls(value=uuid4())

    # Listen, from_string() parses UUID string from DB/API/URL! The try/except catches invalid UUID
    # format and raises domain exception (ValidationException) instead of stdlib ValueError. This keeps
    # exception handling at domain layer - callers catch ValidationException, not ValueError. The error
    # message includes the invalid value for debugging. Use when loading from external sources!
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


# Yo future me, FilePath is a VALUE OBJECT for file paths! It wraps pathlib.Path with validation.
# The __post_init__ converts string to Path if needed (handles both Path and str inputs). Unlike
# plain Path, FilePath is FROZEN (immutable) - can't change after creation. It provides helper methods
# exists(), is_file(), is_directory() that delegate to Path. Use this instead of bare Path or str in
# domain entities - it's type-safe and self-documenting. from_string() factory validates path is not empty!
@dataclass(frozen=True)
class FilePath:
    """Value object representing a file path."""

    value: Path

    # Listen, __post_init__ runs AFTER dataclass freezes the object! Normally frozen dataclasses can't
    # be modified, but __post_init__ can use object.__setattr__ to modify frozen fields during construction.
    # We check if value is already Path, if not convert string to Path. This allows FilePath(Path("/foo"))
    # AND FilePath("/foo") to both work. The object.__setattr__ is special - DON'T use it elsewhere,
    # it bypasses frozen protection! Only safe here because we're still in __init__ phase.
    def __post_init__(self) -> None:
        """Validate the file path."""
        if not isinstance(self.value, Path):
            object.__setattr__(self, "value", Path(self.value))

    # Hey, from_string validates path is not empty! It raises ValidationException (domain exception)
    # instead of ValueError. Use this when loading paths from external sources (DB, API, config files).
    # Empty string check prevents creating FilePath("") which would be invalid but Path("") is technically
    # valid (current directory). We enforce stricter business rule: paths must be explicit, not empty!
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


# Yo, SpotifyUri is a VALUE OBJECT for Spotify URIs! Format is "spotify:type:id" like
# "spotify:track:3n3Ppam7vgaVa1iaRUc9Lp". The __post_init__ VALIDATES format on creation - invalid URIs
# can't exist! We check starts with "spotify:", has at least 3 parts (spotify:type:id), and type is
# one of (track, album, artist, playlist, user). from_url() converts URLs like
# "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp" to URIs. Properties resource_type and
# resource_id parse the URI parts. This prevents bugs from malformed Spotify IDs!
@dataclass(frozen=True)
class SpotifyUri:
    """Value object representing a Spotify URI."""

    value: str

    # Listen, __post_init__ STRICTLY validates Spotify URI format! We check: 1) starts with "spotify:",
    # 2) has at least 3 colon-separated parts (spotify:type:id), 3) type is valid (track/album/artist/
    # playlist/user). If ANY validation fails, raises ValidationException - invalid URIs CAN'T be created!
    # This is fail-fast design. The validation is defensive - better to reject invalid URI early than
    # let it propagate and cause obscure Spotify API errors later. Frozen dataclass ensures immutability!
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

    # Hey, from_url parses Spotify HTTPS URLs to URIs! Users often paste URLs from browser:
    # "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp?si=xyz". We extract type (track) and
    # id (3n3Ppam7vgaVa1iaRUc9Lp) and construct URI "spotify:track:3n3Ppam7vgaVa1iaRUc9Lp". The
    # .split("?")[0] removes query params (si= sharing token). This makes API more user-friendly -
    # accept both URIs and URLs! The validation in __post_init__ ensures result is valid URI.
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

    # Yo, resource_type property extracts type from URI! "spotify:track:123" → "track". It's a @property
    # not a method so you use it like `uri.resource_type` not `uri.resource_type()`. The split(":")[1]
    # gets second part (index 1). Safe because __post_init__ already validated format (at least 3 parts).
    # Use this to route API calls - track URIs go to tracks endpoint, playlist URIs to playlists endpoint!
    @property
    def resource_type(self) -> str:
        """Get the resource type (track, album, artist, etc.)."""
        return self.value.split(":")[1]

    # Listen, resource_id property extracts ID from URI! "spotify:track:123abc" → "123abc". It's what
    # you pass to Spotify API endpoints. The split(":")[2] gets third part (index 2). @property means
    # access like attribute: `uri.resource_id`. Already validated by __post_init__ so safe to access.
    # This is the actual Spotify object ID - use it in API calls like GET /tracks/{resource_id}!
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
            raise ValidationException(
                f"Invalid AutomationRuleId format: {value}"
            ) from e

    def __str__(self) -> str:
        return str(self.value)
