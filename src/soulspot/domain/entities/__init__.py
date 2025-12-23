"""Domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, ClassVar, Optional

from soulspot.domain.entities.download_manager import (
    DownloadProgress,
    DownloadProvider,
    DownloadTimestamps,
    QueueStatistics,
    TrackInfo,
    UnifiedDownload,
    UnifiedDownloadStatus,
)
from soulspot.domain.entities.error_codes import (
    NON_RETRYABLE_ERRORS,
    RETRYABLE_ERRORS,
    DownloadErrorCode,
    get_error_description,
    is_non_retryable_error,
    is_retryable_error,
    normalize_error_code,
)
from soulspot.domain.entities.quality_profile import (
    QUALITY_PROFILES,
    AudioFormat,
    QualityMatcher,
    QualityProfile,
    QualityProfileId,
)
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    AutomationRuleId,
    DownloadId,
    FilePath,
    FilterRuleId,
    ImageRef,
    PlaylistId,
    SpotifyUri,
    TrackId,
    WatchlistId,
)


# Hey future me, MetadataSource tracks WHERE metadata came from! MANUAL means user edited it
# (highest priority - never overwrite). MUSICBRAINZ/SPOTIFY/LASTFM mean from API. Use this to
# decide whether to update fields when syncing - don't overwrite MANUAL with API data! The enum
# is stored as string in DB, not int. Order doesn't matter for priority - code must check explicitly.
class MetadataSource(str, Enum):
    """Source of metadata."""

    MANUAL = "manual"  # User-provided overrides
    MUSICBRAINZ = "musicbrainz"
    SPOTIFY = "spotify"
    LASTFM = "lastfm"


# Hey future me - ArtistSource tracks WHERE the artist comes from in the unified view!
# This enables SoulSpot to become a true Music Manager combining local library + streaming services.
# - LOCAL: Artist found in local file scan (Lidarr-style folder structure)
# - SPOTIFY: Followed artist from Spotify (synced from user's Spotify account)
# - HYBRID: Artist exists in BOTH local library AND Spotify followed artists
# This field drives the UI badge display (🎵 Local | 🎧 Spotify | 🎵 Deezer | 🌟 Multi) and determines
# which operations are available (e.g., can't "unfollow" a LOCAL-only artist on Spotify).
# EXPANDED (Dec 2025): Added support for Deezer, Tidal, and multi-service scenarios
class ArtistSource(str, Enum):
    """Source of the artist in the unified music manager view."""

    LOCAL = "local"  # Artist found in local library file scan
    SPOTIFY = "spotify"  # Followed artist from Spotify
    DEEZER = "deezer"  # Favorite artist from Deezer
    TIDAL = "tidal"  # Favorite artist from Tidal (future)
    HYBRID = "hybrid"  # Artist exists in multiple sources (local + streaming services)
    MULTI_SERVICE = "multi_service"  # Artist synced from multiple streaming services


# Hey future me - ProviderMode is the 3-way toggle for each external service provider!
# This controls whether a provider is used and at what level.
#
# Slider positions in UI:
#   🔴 OFF (left)   → Provider completely disabled, no API calls, not even fallback
#   🟡 BASIC (mid)  → Free features only (public API, no OAuth/account needed)
#   🟢 PRO (right)  → Full features including OAuth/Premium/paid features
#
# Provider capabilities per mode:
# | Provider    | OFF  | BASIC                              | PRO                         |
# |-------------|------|------------------------------------|-----------------------------|
# | Spotify     | -    | ❌ (requires OAuth always)         | Playlists, Browse, Follow   |
# | Deezer      | -    | Metadata, Artwork, Charts, Genres  | (same - Deezer is free!)    |
# | MusicBrainz | -    | Metadata, CoverArtArchive          | (same - MusicBrainz free!)  |
# | Last.fm     | -    | Basic scrobbling                   | Pro features                |
# | slskd       | -    | ❌ (requires setup)                | Downloads                   |
class ProviderMode(str, Enum):
    """Mode for external service providers (3-way slider)."""

    OFF = "off"  # Provider completely disabled - no API calls, no fallback
    BASIC = "basic"  # Free/public API features only (no OAuth/account needed)
    PRO = "pro"  # Full features including OAuth/Premium/paid features


# Yo, Artist is the DOMAIN ENTITY (not DB model)! It represents the business concept of an artist.
# Uses dataclass instead of Pydantic for simplicity (domain layer doesn't depend on Pydantic). The
# metadata_sources dict tracks which fields came from which APIs (e.g., {"name": "spotify", "genres":
# "musicbrainz"}). genres and tags are lists (not sets!) to preserve order. created_at/updated_at
# default to UTC now - ALWAYS use UTC in domain, convert to local time in presentation layer only!
# Hey future me - artwork_url stores the artist's profile picture from Spotify! Spotify returns an array
# of images in different sizes (640x640, 320x320, 160x160). We pick the medium-sized one (usually 320px)
# for display in the followed artists UI. This field is nullable because not all artists have images
# (especially indie/underground artists). The URL points to Spotify's CDN - it's stable and cacheable.
# Hey future me - source field tracks whether artist is from LOCAL library, SPOTIFY, or HYBRID (both)!
# This enables the unified Music Manager view where local scanned artists and Spotify followed artists
# are shown together. UI uses this to display badges and enable/disable actions (e.g., can't "unfollow"
# a LOCAL-only artist). When an artist exists in both sources, it's marked HYBRID and we merge metadata
# from both (Spotify provides artwork/genres, local files provide actual track ownership).
#
# UPDATED: image field is now ImageRef value object for consistent image handling!
# Use: artist.image.url for CDN URL, artist.image.path for local cache
@dataclass
class Artist:
    """Artist entity representing a music artist."""

    id: ArtistId
    name: str
    source: ArtistSource = ArtistSource.LOCAL  # Default to LOCAL for backward compat
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    lastfm_url: str | None = None
    # Hey future me - image is now ImageRef! Access via artist.image.url or artist.image.path
    image: ImageRef = field(default_factory=ImageRef)
    # Hey future me - multi-service IDs for cross-service artist deduplication!
    # spotify_uri is the primary Spotify ID, these are for Deezer/Tidal.
    # When syncing from multiple services, use musicbrainz_id as primary dedup key if available.
    deezer_id: str | None = None
    tidal_id: str | None = None
    # Hey future me - disambiguation is for Lidarr-style naming templates!
    # Sourced from MusicBrainz to differentiate artists with the same name.
    # Example: "Genesis" has disambiguation "English rock band" vs other Genesis artists.
    # Used in {Artist Disambiguation} naming variable.
    disambiguation: str | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Listen, __post_init__ validates artist AFTER dataclass creates object! We check name isn't empty
    # or whitespace-only. If validation fails, raise ValueError immediately (object never gets created).
    # DON'T put DB queries or API calls here - this runs on EVERY Artist object creation including
    # from DB reads! Keep it fast and pure validation only. The strip() check catches "   " strings.
    def __post_init__(self) -> None:
        """Validate artist data."""
        if not self.name or not self.name.strip():
            raise ValueError("Artist name cannot be empty")

    # Hey, update_name is a DOMAIN METHOD (business logic)! It validates the new name AND updates
    # updated_at timestamp automatically. DON'T do `artist.name = "foo"` directly - use this method
    # so validation and timestamp update happen together. This is the Command pattern - methods that
    # change state are verbs (update_name, not set_name). Always check for empty/whitespace!
    def update_name(self, name: str) -> None:
        """Update artist name."""
        if not name or not name.strip():
            raise ValueError("Artist name cannot be empty")
        self.name = name
        self.updated_at = datetime.now(UTC)


# Yo, Album entity! Similar to Artist but tied to an artist via artist_id FK. release_year is
# optional (some albums don't have clear release dates, compilations, etc). artwork_path points to
# local file (FilePath value object validates it). Genres/tags are list[str] not set[str] to preserve
# order from APIs. The metadata_sources dict is critical - don't overwrite user-edited fields!
# Hey future me - primary_type and secondary_types are Lidarr-style album typing! Used in naming
# templates via {Album Type}. Examples: "Album", "EP", "Single", "Compilation", "Live", "Soundtrack".
@dataclass
class Album:
    """Album entity representing a music album."""

    id: AlbumId
    title: str
    artist_id: ArtistId
    # Hey future me - source tracks where album came from!
    # Values: 'local' (file scan), 'spotify', 'deezer', 'tidal', 'hybrid' (multiple)
    source: str = "local"
    release_year: int | None = None
    # Hey future me - full precision release date (YYYY-MM-DD or YYYY-MM or YYYY)
    # release_date_precision tells which parts are valid: 'day', 'month', 'year'
    release_date: str | None = None
    release_date_precision: str | None = None
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    # Hey future me - multi-service IDs for cross-service album deduplication!
    # spotify_uri is the primary Spotify ID, these are for Deezer/Tidal.
    # When syncing from multiple services, use musicbrainz_id as primary dedup key if available.
    deezer_id: str | None = None
    tidal_id: str | None = None
    # Hey future me - cover is now ImageRef! Combines old artwork_path + artwork_url
    # Use: album.cover.url for Spotify CDN, album.cover.path for local cached file
    cover: ImageRef = field(default_factory=ImageRef)
    # Hey future me - Lidarr-style dual album type system for naming templates!
    # primary_type: Album, EP, Single, Broadcast, Other
    # secondary_types: Compilation, Soundtrack, Spokenword, Interview, Audiobook, Live, Remix, DJ-mix
    # Used in {Album Type} variable - combines primary + secondary for display
    primary_type: str = "Album"
    secondary_types: list[str] = field(default_factory=list)
    # Hey future me - disambiguation is for Lidarr-style naming templates!
    # Sourced from MusicBrainz to differentiate album editions/versions.
    # Example: "Thriller (25th Anniversary Edition)" has disambiguation "25th Anniversary Edition".
    # Used in {Album Disambiguation} naming variable.
    disambiguation: str | None = None
    # Hey future me - streaming metadata (from Spotify/Deezer/Tidal)
    total_tracks: int | None = None  # Number of tracks in album
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Listen, __post_init__ validates title AND release_year range! The year check is defensive -
    # prevents typos like 2202 or 195 that would break display. 1900-2100 is reasonable range for
    # music. Could argue 1800s for classical but let's not complicate it. If validation fails,
    # album object is NEVER created (ValueError raises before returning from __init__).
    def __post_init__(self) -> None:
        """Validate album data."""
        if not self.title or not self.title.strip():
            raise ValueError("Album title cannot be empty")
        if self.release_year is not None and (
            self.release_year < 1900 or self.release_year > 2100
        ):
            raise ValueError(
                f"Invalid release_year {self.release_year}: must be between 1900 and 2100"
            )

    @property
    def is_compilation(self) -> bool:
        """Check if album is a compilation (Various Artists, etc.)."""
        return "compilation" in [t.lower() for t in (self.secondary_types or [])]

    @property
    def album_type_display(self) -> str:
        """Get display string for album type (used in {Album Type} template variable).

        Hey future me - this formats the album type for Lidarr-style naming templates!
        Priority: Secondary types first (more specific), then primary type.
        Examples:
          - primary="Album", secondary=[] → "Album"
          - primary="Album", secondary=["Live"] → "Live Album"
          - primary="EP", secondary=["Remix"] → "Remix EP"
          - primary="Album", secondary=["Compilation", "Live"] → "Live Compilation"
        """
        secondary = self.secondary_types or []
        primary = self.primary_type or "Album"

        # Title-case everything for consistency
        primary = primary.title()
        secondary = [s.title() for s in secondary]

        if not secondary:
            return primary

        # Special handling: if "Compilation" is in secondary, use it as base
        if "Compilation" in secondary:
            other_secondary = [s for s in secondary if s != "Compilation"]
            if other_secondary:
                return f"{' '.join(other_secondary)} Compilation"
            return "Compilation"

        # Otherwise combine: "Live Album", "Remix EP", etc.
        return f"{' '.join(secondary)} {primary}"

    # Hey, update_cover is a domain method! Updates the cover ImageRef AND bumps updated_at. Called
    # after post-processing downloads artwork from CoverArtArchive. Use this method instead of direct
    # field assignment so updated_at changes and cache invalidates correctly.
    def update_cover(self, *, url: str | None = None, path: FilePath | str | None = None) -> None:
        """Update album cover art.

        Args:
            url: Remote CDN URL (Spotify, Deezer, etc.)
            path: Local cached file path
        """
        path_str = str(path) if path is not None else None
        self.cover = ImageRef(url=url or self.cover.url, path=path_str or self.cover.path)
        self.updated_at = datetime.now(UTC)

    # Backward compatibility alias
    def update_artwork(self, artwork_path: FilePath) -> None:
        """DEPRECATED: Use update_cover(path=...) instead."""
        self.update_cover(path=str(artwork_path))


# Hey future me - ArtistDiscography stores the COMPLETE discography from external providers!
# This is NOT what the user owns - it's what Deezer/Spotify SAYS the artist has released.
# Used by LibraryDiscoveryWorker to show "Missing Albums" in UI.
#
# Key difference:
# - Album entity = something the user HAS (in library or saved on streaming)
# - ArtistDiscography = something that EXISTS (from provider API)
#
# Workflow:
# 1. LibraryDiscoveryWorker calls DeezerPlugin.get_artist_albums()
# 2. Results stored as ArtistDiscography entries
# 3. UI shows: "You have 12/50 albums" (is_owned = True for 12)
# 4. User clicks "Download missing" → creates Download entries
@dataclass
class ArtistDiscography:
    """Discography entry - an album known to exist from external providers.

    Hey future me - this is for DISCOVERY, not ownership tracking!

    - Populated by LibraryDiscoveryWorker from Deezer/Spotify API
    - Stores ALL known albums/singles/EPs for an artist
    - is_owned field computed by comparing with user's soulspot_albums
    - UI shows missing albums with download buttons
    """

    id: AlbumId  # Reuse AlbumId value object for consistency
    artist_id: ArtistId
    title: str
    # album_type: "album", "single", "ep", "compilation", "live", "remix"
    album_type: str = "album"

    # Provider IDs - can have multiple if found on multiple services
    deezer_id: str | None = None
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    tidal_id: str | None = None

    # Album metadata
    release_date: str | None = None  # YYYY-MM-DD or YYYY-MM or YYYY
    release_date_precision: str | None = None  # "day", "month", "year"
    total_tracks: int | None = None
    cover_url: str | None = None  # CDN URL from provider (for display)

    # Discovery metadata
    source: str = "deezer"  # Which provider discovered this
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Computed field - TRUE if user owns this album (in soulspot_albums)
    is_owned: bool = False

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate discography entry data."""
        if not self.title or not self.title.strip():
            raise ValueError("Album title cannot be empty")
        valid_types = {"album", "single", "ep", "compilation", "live", "remix"}
        if self.album_type.lower() not in valid_types:
            raise ValueError(f"Invalid album_type: {self.album_type}")

    @property
    def spotify_id(self) -> str | None:
        """Extract Spotify ID from spotify_uri."""
        if not self.spotify_uri:
            return None
        return str(self.spotify_uri).split(":")[-1]

    @property
    def release_year(self) -> int | None:
        """Extract year from release_date."""
        if not self.release_date:
            return None
        try:
            return int(self.release_date[:4])
        except (ValueError, IndexError):
            return None


# Yo future me, Track entity is the CORE domain object! Every track has artist_id (required) and
# optionally album_id (singles have no album). track_number/disc_number are for multi-disc albums.
# isrc is International Standard Recording Code (globally unique, good for matching). file_path
# is None until track is downloaded. duration_ms is milliseconds (Spotify uses ms, we follow that).
# metadata_sources tracks which fields came from which API to avoid overwriting better data!
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
    # Hey future me - multi-service IDs for cross-service deduplication!
    # ISRC is the universal track identifier, these are service-specific IDs for API calls.
    # When syncing from multiple services, ISRC is primary dedup key.
    deezer_id: str | None = None
    tidal_id: str | None = None
    file_path: FilePath | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata_sources: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Listen, __post_init__ validates ALL track business rules! Title can't be empty, duration can't
    # be negative, track_number must be positive (no track 0), disc_number must be >=1. These are
    # BUSINESS RULES not DB constraints. If someone imports bad data from API, catch it here early!
    # ValueError means object creation fails immediately. Don't skip validation thinking "I'll fix
    # it later" - you won't, and corrupt data will spread through the system!
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

    # Hey, update_file_path is called after successful download! Sets file_path AND updated_at.
    # The FilePath value object validates path exists and is accessible. After calling this, you
    # should also call update_download_status() on related Download entity. DON'T set file_path
    # directly - always use this method so updated_at changes and downstream systems know to refresh!
    def update_file_path(self, file_path: FilePath) -> None:
        """Update track file path."""
        self.file_path = file_path
        self.updated_at = datetime.now(UTC)

    # Yo, is_downloaded checks if file actually exists on disk! It's not enough for file_path to be
    # set - the file must exist (user might have deleted it, disk might have failed, etc). The
    # FilePath.exists() does real filesystem check. Use this in UI to show download status. If this
    # returns False but file_path is set, something went wrong - file was downloaded but later deleted!
    def is_downloaded(self) -> bool:
        """Check if track has been downloaded."""
        return self.file_path is not None and self.file_path.exists()


# Hey future me, PlaylistSource tracks whether playlist came from Spotify sync or was manually
# created by user! SPOTIFY playlists auto-sync (we periodically fetch updates from Spotify).
# MANUAL playlists are user-created local collections that don't sync. Check this before attempting
# sync operations - don't try to sync MANUAL playlists to Spotify (they don't have spotify_uri)!
class PlaylistSource(str, Enum):
    """Source of the playlist."""

    SPOTIFY = "spotify"
    MANUAL = "manual"


# Listen, Playlist is a collection of tracks! track_ids is list[TrackId] not list[Track] (just IDs,
# not full objects - lighter weight, easier to serialize). Order matters for playlists so we use
# list not set. source=SPOTIFY means synced from Spotify (has spotify_uri). source=MANUAL means
# user-created locally. description is optional (can be empty). Use add_track/remove_track methods
# instead of manipulating track_ids directly - they update timestamps and handle duplicates correctly!
#
# UPDATED: cover field is now ImageRef for consistent image handling!
# Use: playlist.cover.url for CDN URL, playlist.cover.path for local cache
@dataclass
class Playlist:
    """Playlist entity representing a collection of tracks."""

    id: PlaylistId
    name: str
    description: str | None = None
    source: PlaylistSource = PlaylistSource.MANUAL
    spotify_uri: SpotifyUri | None = None
    # Hey future me - cover is now ImageRef! Use playlist.cover.url or playlist.cover.path
    cover: ImageRef = field(default_factory=ImageRef)
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


# Yo, DownloadStatus is the STATE MACHINE for downloads! Transitions: PENDING → QUEUED → DOWNLOADING
# → COMPLETED/FAILED/CANCELLED. You can't go from COMPLETED to DOWNLOADING (use retry to create new
# Download). The Download.start(), .complete(), .fail() methods enforce valid state transitions. If
# you try invalid transition, they raise ValueError. Don't bypass domain methods and set status
# directly - you'll create invalid states (like COMPLETED without completed_at timestamp)!
#
# Hey future me - WAITING status is for downloads queued while download manager (slskd) is unavailable!
# The flow is: WAITING → PENDING → QUEUED → DOWNLOADING → COMPLETED
# When slskd becomes available, QueueDispatcherWorker moves WAITING → PENDING one by one.
class DownloadStatus(str, Enum):
    """Status of a download."""

    WAITING = "waiting"  # Waiting for download manager to become available
    PENDING = "pending"  # Ready to be sent to download manager
    QUEUED = "queued"  # Sent to download manager, waiting in its queue
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Hey future me, Download tracks a single track download operation! It's separate from Track because
# a track can have multiple download attempts (retries). priority is 0-2 where 0=P0 (highest), 1=P1,
# 2=P2 (lowest). Job queue processes P0 before P1 before P2. progress_percent is 0-100 for UI progress
# bars. started_at and completed_at are for analytics. error_message stores exception message if FAILED.
# The is_finished() method checks if in terminal state (won't change anymore). Use domain methods
# (start, complete, fail) to change status - they enforce state machine rules and update timestamps!
#
# NEW: AUTO-RETRY FEATURE (2025-12)
# retry_count: How many times this download has been attempted
# max_retries: Maximum retry attempts (default: 3)
# next_retry_at: When the next retry is scheduled (None = not scheduled)
# last_error_code: Classified error code for intelligent retry decisions
#
# RETRY-FLOW:
# 1. Download fails → fail_with_retry() sets status=FAILED, retry_count++, calculates next_retry_at
# 2. RetrySchedulerWorker checks every 30s for: status=FAILED & next_retry_at <= now & retry_count < max_retries
# 3. If found: status → WAITING, QueueDispatcherWorker picks it up
# 4. After max_retries: Download stays FAILED (manual retry possible via schedule_retry())
#
# BACKOFF FORMULA: [1, 5, 15] minutes for retries 1, 2, 3
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
    # Retry management fields
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: datetime | None = None
    last_error_code: str | None = None

    # Backoff intervals in minutes: retry 1 → 1min, retry 2 → 5min, retry 3 → 15min
    _RETRY_BACKOFF_MINUTES: ClassVar[list[int]] = [1, 5, 15]

    # Error codes that should NOT be retried (permanent failures)
    _NON_RETRYABLE_ERRORS: ClassVar[set[str]] = {
        "file_not_found",
        "user_blocked",
        "invalid_file",
    }

    def __post_init__(self) -> None:
        """Validate download data."""
        if self.progress_percent < 0.0 or self.progress_percent > 100.0:
            raise ValueError("Progress must be between 0 and 100")

    def start(self) -> None:
        """Mark download as started."""
        if self.status not in (
            DownloadStatus.PENDING,
            DownloadStatus.QUEUED,
            DownloadStatus.WAITING,
        ):
            raise ValueError(f"Cannot start download in status {self.status}")
        self.status = DownloadStatus.DOWNLOADING
        self.started_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def dispatch(self) -> None:
        """Move from WAITING to PENDING - ready to send to download manager.

        Hey future me - this is called by QueueDispatcherWorker when slskd becomes available!
        Only WAITING downloads can be dispatched. After dispatch, the download is ready to
        be picked up by the normal download processing flow.
        """
        if self.status != DownloadStatus.WAITING:
            raise ValueError(f"Cannot dispatch download in status {self.status}")
        self.status = DownloadStatus.PENDING
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
        """Mark download as failed.

        Note: For automatic retry scheduling, use fail_with_retry() instead.
        This method just sets FAILED status without scheduling retries.
        """
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.now(UTC)

    def fail_with_retry(
        self,
        error_message: str,
        error_code: str | None = None,
    ) -> bool:
        """Mark download as failed and schedule retry if applicable.

        Hey future me - this is the SMART fail method! It:
        1. Sets FAILED status and error_message
        2. Classifies error via error_code
        3. Checks if should_retry()
        4. If yes: Calculates next_retry_at with exponential backoff
        5. Returns True if retry was scheduled, False if terminal failure

        Args:
            error_message: Human-readable error description
            error_code: Classified error code (e.g., "timeout", "source_offline", "file_not_found")
                       If None, defaults to "unknown" which is retryable.

        Returns:
            True if retry was scheduled, False if download is permanently failed
        """
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        self.last_error_code = error_code or "unknown"
        self.updated_at = datetime.now(UTC)

        if self.should_retry():
            self._schedule_next_retry()
            return True
        return False

    def should_retry(self) -> bool:
        """Check if this download should be automatically retried.

        Returns True if:
        - Status is FAILED
        - retry_count < max_retries
        - last_error_code is not in NON_RETRYABLE_ERRORS

        Hey future me - this is used by:
        1. fail_with_retry() to decide if scheduling retry
        2. RetrySchedulerWorker to filter eligible downloads
        3. UI to show "Will retry" vs "Permanently failed"
        """
        if self.status != DownloadStatus.FAILED:
            return False
        if self.retry_count >= self.max_retries:
            return False
        return self.last_error_code not in self._NON_RETRYABLE_ERRORS

    def _schedule_next_retry(self) -> None:
        """Calculate and set next_retry_at with exponential backoff.

        Backoff formula: [1, 5, 15] minutes for retries 1, 2, 3+
        Called internally by fail_with_retry() when should_retry() is True.
        """
        # Get backoff minutes based on current retry_count
        # After max backoff entries, use the last value
        backoff_idx = min(self.retry_count, len(self._RETRY_BACKOFF_MINUTES) - 1)
        delay_minutes = self._RETRY_BACKOFF_MINUTES[backoff_idx]

        self.retry_count += 1
        self.next_retry_at = datetime.now(UTC) + timedelta(minutes=delay_minutes)

    def schedule_retry(self) -> None:
        """Manually schedule a retry for a failed download.

        Hey future me - this is for MANUAL retries from UI! User clicks "Retry"
        on a permanently failed download (max_retries reached or non-retryable error).
        We reset retry_count and schedule immediately.

        Raises:
            ValueError: If download is not in FAILED status
        """
        if self.status != DownloadStatus.FAILED:
            raise ValueError(f"Cannot schedule retry for download in status {self.status}")

        # Reset retry count for manual retry
        self.retry_count = 0
        self.last_error_code = None
        self.next_retry_at = datetime.now(UTC)  # Immediate retry
        self.status = DownloadStatus.WAITING
        self.error_message = None
        self.updated_at = datetime.now(UTC)

    def activate_for_retry(self) -> None:
        """Move download from FAILED to WAITING for retry processing.

        Hey future me - this is called by RetrySchedulerWorker!
        After next_retry_at has passed and should_retry() is True.
        Moves from FAILED → WAITING so QueueDispatcherWorker picks it up.
        """
        if self.status != DownloadStatus.FAILED:
            raise ValueError(f"Cannot activate for retry from status {self.status}")
        if not self.should_retry():
            raise ValueError("Download is not eligible for retry")

        self.status = DownloadStatus.WAITING
        self.next_retry_at = None  # Clear - we're now active
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


# Hey future me - EnrichmentCandidate tracks potential Spotify matches for local library entities!
# When enriching local artists/albums, we may find multiple Spotify matches (e.g., "Queen" could be
# the legendary UK rock band OR some random tribute band). We store all candidates here for user review.
# User picks the correct one via UI, we apply that match. Never auto-match ambiguous entities!
class EnrichmentEntityType(str, Enum):
    """Type of entity being enriched."""

    ARTIST = "artist"
    ALBUM = "album"


@dataclass
class EnrichmentCandidate:
    """Potential Spotify match for a local library entity.

    Stores candidates when enrichment finds multiple possible matches
    so users can review and select the correct one.
    """

    id: str
    entity_type: EnrichmentEntityType
    entity_id: str  # FK to soulspot_artists or soulspot_albums (polymorphic)
    spotify_uri: str  # spotify:artist:XXXXX or spotify:album:XXXXX
    spotify_name: str  # Name from Spotify (for display in UI)
    spotify_image_url: str | None = None  # Image URL from Spotify (for preview)
    confidence_score: float = 0.0  # 0.0-1.0 (higher = better match)
    is_selected: bool = False  # User selected this candidate as correct
    is_rejected: bool = False  # User explicitly rejected this candidate
    extra_info: dict | None = None  # Additional info (genres, followers, etc.)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate enrichment candidate data."""
        if self.confidence_score < 0.0 or self.confidence_score > 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")

    def select(self) -> None:
        """Mark this candidate as the selected match."""
        self.is_selected = True
        self.is_rejected = False
        self.updated_at = datetime.now(UTC)

    def reject(self) -> None:
        """Mark this candidate as rejected."""
        self.is_selected = False
        self.is_rejected = True
        self.updated_at = datetime.now(UTC)


# Hey future me - DuplicateCandidateStatus tracks the review status of potential duplicates!
# The worker finds candidates, user reviews them, and decides what to do.
class DuplicateCandidateStatus(str, Enum):
    """Status of a duplicate candidate review."""

    PENDING = "pending"  # Awaiting user review
    CONFIRMED = "confirmed"  # User confirmed these are duplicates
    DISMISSED = "dismissed"  # User dismissed (not duplicates)
    AUTO_RESOLVED = "auto_resolved"  # System auto-resolved


class DuplicateMatchType(str, Enum):
    """How the duplicate was detected."""

    METADATA = "metadata"  # Same artist+title, similar duration
    FINGERPRINT = "fingerprint"  # Audio fingerprint match (future)


class DuplicateResolutionAction(str, Enum):
    """What user did to resolve the duplicate."""

    KEEP_FIRST = "keep_first"  # Keep track 1, delete track 2
    KEEP_SECOND = "keep_second"  # Keep track 2, delete track 1
    KEEP_BOTH = "keep_both"  # Keep both (not actually duplicates)
    MERGED = "merged"  # Merged metadata from both


@dataclass
class DuplicateCandidate:
    """Potential duplicate track pair for review.

    DuplicateDetectorWorker populates these. Users review in UI
    and decide what to do (keep one, keep both, merge metadata, etc.).
    """

    id: str
    track_id_1: str  # FK to soulspot_tracks
    track_id_2: str  # FK to soulspot_tracks
    similarity_score: int  # 0-100 (100 = definitely same track)
    match_type: DuplicateMatchType = DuplicateMatchType.METADATA
    status: DuplicateCandidateStatus = DuplicateCandidateStatus.PENDING
    match_details: str | None = None  # JSON with match details
    resolution_action: DuplicateResolutionAction | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate duplicate candidate data."""
        if self.similarity_score < 0 or self.similarity_score > 100:
            raise ValueError("Similarity score must be between 0 and 100")
        # Ensure track_id_1 < track_id_2 to avoid duplicate pairs (A,B) and (B,A)
        if self.track_id_1 >= self.track_id_2:
            raise ValueError("track_id_1 must be less than track_id_2")

    def confirm(self) -> None:
        """Confirm these tracks are duplicates."""
        self.status = DuplicateCandidateStatus.CONFIRMED
        self.reviewed_at = datetime.now(UTC)

    def dismiss(self) -> None:
        """Dismiss - these are not duplicates."""
        self.status = DuplicateCandidateStatus.DISMISSED
        self.reviewed_at = datetime.now(UTC)

    def resolve(self, action: DuplicateResolutionAction) -> None:
        """Resolve with a specific action."""
        self.status = DuplicateCandidateStatus.CONFIRMED
        self.resolution_action = action
        self.reviewed_at = datetime.now(UTC)


# =============================================================================
# BLOCKLIST - Auto-block failing download sources
# =============================================================================
# Hey future me - this entity tracks BLOCKED sources on Soulseek!
#
# The problem: Some sources consistently fail (offline users, blocked IPs, invalid files).
# Without a blocklist, we waste time retrying the same bad sources over and over.
#
# The solution: After 3 failures from the same username+filepath combo within 24h,
# we auto-block that source. Future searches will skip blocked sources.
#
# SCOPE OPTIONS:
# - username: Block all files from this user (for user_blocked errors)
# - filepath: Block this specific file (for file_not_found errors)
# - username+filepath: Block this file from this user only (default for most errors)
#
# EXPIRY: Blocks expire after configurable period (default 7 days).
# This handles cases where a user fixes their setup or comes back online.


class BlocklistScope(str, Enum):
    """What to block from a failing source."""

    USERNAME = "username"  # Block all files from this username
    FILEPATH = "filepath"  # Block this filepath from all users
    SPECIFIC = "specific"  # Block this filepath from this username only


@dataclass
class BlocklistEntry:
    """A blocked download source.

    Hey future me - this tracks WHY a source is blocked!

    Fields:
    - id: Unique identifier
    - username: Soulseek username (can be None for filepath-only blocks)
    - filepath: File path on the user's share (can be None for username-only blocks)
    - scope: What combination is blocked (see BlocklistScope)
    - reason: The error code that caused the block (e.g., "file_not_found", "user_blocked")
    - failure_count: How many failures led to this block
    - blocked_at: When the block was created
    - expires_at: When the block expires (None = never)
    - is_manual: True if manually blocked by user, False if auto-blocked

    Indexing strategy:
    - Unique index on (username, filepath) for fast duplicate checks
    - Index on expires_at for cleanup queries
    """

    id: str
    username: str | None = None
    filepath: str | None = None
    scope: BlocklistScope = BlocklistScope.SPECIFIC
    reason: str | None = None
    failure_count: int = 3  # Typically blocked after 3 failures
    blocked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None  # None = permanent
    is_manual: bool = False  # True if user manually blocked

    def __post_init__(self) -> None:
        """Validate blocklist entry data."""
        # Must have at least username or filepath
        if self.username is None and self.filepath is None:
            raise ValueError("BlocklistEntry must have username or filepath (or both)")

        # Scope validation
        if self.scope == BlocklistScope.USERNAME and self.username is None:
            raise ValueError("USERNAME scope requires username")
        if self.scope == BlocklistScope.FILEPATH and self.filepath is None:
            raise ValueError("FILEPATH scope requires filepath")
        if self.scope == BlocklistScope.SPECIFIC and (
            self.username is None or self.filepath is None
        ):
            raise ValueError("SPECIFIC scope requires both username and filepath")

    def is_expired(self) -> bool:
        """Check if this block has expired."""
        if self.expires_at is None:
            return False  # Permanent block
        return datetime.now(UTC) > self.expires_at

    def extend_block(self, additional_days: int = 7) -> None:
        """Extend the block duration.

        Called when the same source fails again while already blocked.
        This resets the expiry timer.
        """
        self.failure_count += 1
        if self.expires_at is not None:
            self.expires_at = datetime.now(UTC) + timedelta(days=additional_days)

    def make_permanent(self) -> None:
        """Make this block permanent (no expiry)."""
        self.expires_at = None
        self.is_manual = True  # Permanent = manual override

    @classmethod
    def create_auto_block(
        cls,
        id: str,
        username: str | None,
        filepath: str | None,
        reason: str,
        failure_count: int = 3,
        expiry_days: int = 7,
    ) -> "BlocklistEntry":
        """Factory for auto-blocking after repeated failures.

        Args:
            id: Unique identifier
            username: Soulseek username (None for filepath-only blocks)
            filepath: File path on share (None for username-only blocks)
            reason: Error code that caused the block
            failure_count: Number of failures that triggered block
            expiry_days: Days until block expires (default 7)

        Returns:
            New BlocklistEntry configured for auto-blocking
        """
        # Determine scope based on what's provided
        if username and filepath:
            scope = BlocklistScope.SPECIFIC
        elif username:
            scope = BlocklistScope.USERNAME
        else:
            scope = BlocklistScope.FILEPATH

        return cls(
            id=id,
            username=username,
            filepath=filepath,
            scope=scope,
            reason=reason,
            failure_count=failure_count,
            blocked_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=expiry_days),
            is_manual=False,
        )

    @classmethod
    def create_manual_block(
        cls,
        id: str,
        username: str | None = None,
        filepath: str | None = None,
        reason: str = "manually_blocked",
    ) -> "BlocklistEntry":
        """Factory for manual user-initiated blocks.

        Args:
            id: Unique identifier
            username: Username to block (None for filepath-only)
            filepath: Filepath to block (None for username-only)
            reason: Reason for block (default "manually_blocked")

        Returns:
            New BlocklistEntry configured as permanent manual block
        """
        if username and filepath:
            scope = BlocklistScope.SPECIFIC
        elif username:
            scope = BlocklistScope.USERNAME
        else:
            scope = BlocklistScope.FILEPATH

        return cls(
            id=id,
            username=username,
            filepath=filepath,
            scope=scope,
            reason=reason,
            failure_count=1,  # Manual = single action
            blocked_at=datetime.now(UTC),
            expires_at=None,  # Permanent
            is_manual=True,
        )


__all__ = [
    # Existing entities
    "Artist",
    "Album",
    "ArtistDiscography",  # NEW: Complete discography from providers
    "Track",
    "Playlist",
    "Download",
    "LibraryScan",
    "FileDuplicate",
    "ArtistWatchlist",
    "FilterRule",
    "AutomationRule",
    "QualityUpgradeCandidate",
    # NEW: Enrichment and Duplicate entities
    "EnrichmentCandidate",
    "EnrichmentEntityType",
    "DuplicateCandidate",
    "DuplicateCandidateStatus",
    "DuplicateMatchType",
    "DuplicateResolutionAction",
    # Download Manager entities
    "DownloadProgress",
    "DownloadProvider",
    "DownloadTimestamps",
    "QueueStatistics",
    "TrackInfo",
    "UnifiedDownload",
    "UnifiedDownloadStatus",
    # Blocklist entities (for source blocking)
    "BlocklistEntry",
    "BlocklistScope",
    # Error Codes (for download retry system)
    "DownloadErrorCode",
    "is_retryable_error",
    "is_non_retryable_error",
    "get_error_description",
    "normalize_error_code",
    "NON_RETRYABLE_ERRORS",
    "RETRYABLE_ERRORS",
    # Quality Profile (for download quality preferences)
    "AudioFormat",
    "QualityProfile",
    "QualityMatcher",
    "QUALITY_PROFILES",
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
    "ProviderMode",
    "ArtistSource",
]
