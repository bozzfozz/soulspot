"""SQLAlchemy ORM models for SoulSpot."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Hey future me, utc_now() ensures ALL timestamps are UTC! Never use datetime.now() without
# timezone - that's "naive" datetime and causes bugs when servers are in different timezones.
# UTC (Universal Time Coordinated) is the standard for backend systems. The datetime.now(UTC)
# syntax is Python 3.11+ - for older versions, use datetime.utcnow(). UTC is CRITICAL for
# distributed systems, log aggregation, and avoiding DST (Daylight Saving Time) headaches!
def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


# Hey future me - SQLite doesn't preserve timezone info! When we store UTC datetimes, they come
# back as "naive" (no tzinfo). This helper ensures we can safely compare with timezone-aware
# datetimes by attaching UTC if missing. ALWAYS use this when comparing datetimes from DB
# with datetime.now(UTC) to avoid "can't compare offset-naive and offset-aware" TypeError!
def ensure_utc_aware(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware, assuming naive datetimes are UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# Yo, Base is THE foundation of all ORM models! DeclarativeBase is SQLAlchemy 2.0 style
# (cleaner than old declarative_base()). ALL models inherit from this - it manages the shared
# metadata registry (table definitions, relationships, etc.). Don't create multiple Base classes
# or you'll get weird migration issues! The "pass" is intentional - Base is just a marker class.
class Base(DeclarativeBase):
    """Base class for all ORM models.

    Provides common declarative base for SQLAlchemy models.
    All models inherit from this to use the same metadata registry.
    """

    pass


# Listen up, ArtistModel is the CORE entity - everything links to artists! The id is String(36)
# for UUID storage (UUIDs are 36 chars with hyphens). The lambda: str(uuid.uuid4()) generates
# new UUIDs as default - IMPORTANT: it's a lambda, not uuid.uuid4() directly, so each row gets
# unique ID! The indexes on spotify_uri and musicbrainz_id are for lookups when syncing data.
# The func.lower(name) index enables case-insensitive artist search - "Beatles" matches "beatles".
# The cascade="all, delete-orphan" on relationships means: delete artist → delete all albums/tracks!
# This is POWERFUL but DANGEROUS - deleting "The Beatles" wipes their entire discography! Alembic
# migrations must handle this carefully to avoid data loss.
# Hey future me - source field tracks whether artist is LOCAL (file scan), SPOTIFY (followed), or
# HYBRID (both)! This enables unified Music Manager view. Defaults to LOCAL for backward compatibility
# with existing artists in DB. Use 'local', 'spotify', 'hybrid' values (not enum - SQLite compatibility).
class ArtistModel(Base):
    """SQLAlchemy model for Artist entity (Local Library)."""

    __tablename__ = "soulspot_artists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Source: 'local' (file scan), 'spotify' (followed artist), 'hybrid' (both)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    # Hey future me - image_url stores the artist's profile picture from Spotify CDN!
    # Typically 320x320 resolution. String(512) allows for long URLs. Nullable because
    # not all artists have images. This is added after genres/tags migration.
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Hey future me - genres and tags are stored as JSON text (SQLite compatible)!
    # The app layer serializes/deserializes list[str] to/from JSON string.
    # Example: '["rock", "alternative", "indie"]'. Nullable because existing artists
    # won't have this data until next Spotify sync. Migration dd18990ggh48 adds these.
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Hey future me - disambiguation is for Lidarr-style naming templates!
    # Sourced from MusicBrainz to differentiate artists with the same name.
    # Example: "Genesis" has disambiguation "English rock band" vs other Genesis artists.
    # Used in {Artist Disambiguation} naming variable. Added in migration pp27012rrs60.
    disambiguation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    albums: Mapped[list["AlbumModel"]] = relationship(
        "AlbumModel", back_populates="artist", cascade="all, delete-orphan"
    )
    tracks: Mapped[list["TrackModel"]] = relationship(
        "TrackModel", back_populates="artist", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_artists_name_lower", func.lower(name)),)


class AlbumModel(Base):
    """SQLAlchemy model for Album entity (Local Library)."""

    __tablename__ = "soulspot_albums"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Hey future me - artwork_url stores album cover from Spotify CDN! Similar to artist
    # image_url, this is the HTTP URL to the album artwork (typically 300x300 or 640x640).
    # We store BOTH artwork_path (local file) AND artwork_url (Spotify CDN) because:
    # 1) artwork_path is for downloaded/local album art, 2) artwork_url is for streaming
    # from Spotify. UI can show artwork_url immediately while downloading, then switch to
    # artwork_path once local file exists. Nullable because not all albums have covers!
    artwork_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Hey future me - Lidarr-style dual album type system! This allows proper handling of
    # compilations, soundtracks, live albums etc. An album can be "album" (primary) AND
    # "compilation" + "live" (secondary). Examples:
    # - Normal studio album: primary_type="album", secondary_types=[]
    # - Live compilation: primary_type="album", secondary_types=["live", "compilation"]
    # - Movie soundtrack: primary_type="album", secondary_types=["soundtrack"]
    # - EP with remixes: primary_type="ep", secondary_types=["remix"]
    # The album_artist field stores the album-level artist (can differ from track artists).
    # For compilations, this is typically "Various Artists" while individual tracks have
    # their own artist_id. This matches ID3v2 TPE2 (Album Artist) tag convention.
    album_artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="album", server_default="album", index=True
    )
    secondary_types: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    # Hey future me - disambiguation is for Lidarr-style naming templates!
    # Sourced from MusicBrainz to differentiate album editions/versions.
    # Example: "Thriller (25th Anniversary Edition)" has disambiguation "25th Anniversary Edition".
    # Used in {Album Disambiguation} naming variable. Added in migration pp27012rrs60.
    disambiguation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    artist: Mapped["ArtistModel"] = relationship("ArtistModel", back_populates="albums")
    tracks: Mapped[list["TrackModel"]] = relationship(
        "TrackModel", back_populates="album", cascade="all, delete-orphan"
    )

    # Hey future me - helper property to check if this is a compilation
    @property
    def is_compilation(self) -> bool:
        """Check if album is a compilation (Various Artists, etc.)."""
        return "compilation" in (self.secondary_types or [])

    __table_args__ = (
        Index("ix_albums_title_artist", "title", "artist_id"),
        Index("ix_albums_primary_type", "primary_type"),
    )


# Hey future me, TrackModel is the BUSIEST table - queries hit it constantly! The file_*
# fields (file_size, file_hash, file_hash_algorithm) are for library integrity checks - detecting
# duplicates, corruption, etc. The is_broken flag marks files that failed validation (corrupt,
# deleted, permission issues). The audio_* fields store technical metadata (bitrate, format,
# sample_rate) for quality filtering and upgrade detection. The indexes on title+artist_id and
# file_hash are CRITICAL for performance - without them, duplicate detection scans the entire
# table! The download relationship uses uselist=False because it's ONE-TO-ONE (each track has
# at most one active download). Be careful with migrations - this table can have millions of rows!
class TrackModel(Base):
    """SQLAlchemy model for Track entity (Local Library)."""

    __tablename__ = "soulspot_tracks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    album_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("soulspot_albums.id", ondelete="SET NULL"), nullable=True
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    track_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disc_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    isrc: Mapped[str | None] = mapped_column(
        String(12), nullable=True, unique=True, index=True
    )
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Hey future me - genre stores the primary genre for this track! We use JSON to store
    # list[str] in DB (SQLite doesn't have array type). Multiple genres are comma-separated
    # in the Track entity's genres list, but we store just the primary one here for filtering.
    # If you need all genres, use the full metadata from MusicBrainz/Spotify API calls.
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # File integrity and library management fields
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_hash_algorithm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_broken: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    audio_bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    audio_sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    artist: Mapped["ArtistModel"] = relationship("ArtistModel", back_populates="tracks")
    album: Mapped["AlbumModel | None"] = relationship(
        "AlbumModel", back_populates="tracks"
    )
    download: Mapped["DownloadModel | None"] = relationship(
        "DownloadModel",
        back_populates="track",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (Index("ix_tracks_title_artist", "title", "artist_id"),)


class PlaylistModel(Base):
    """SQLAlchemy model for Playlist entity.

    Hey future me - playlists can come from multiple sources:
    - MANUAL: Created in SoulSpot
    - SPOTIFY: Synced from user's Spotify playlists
    - LIKED_SONGS: Special Spotify playlist (is_liked_songs=True)

    cover_url = Spotify CDN URL (for comparison if image changed)
    cover_path = Local path to downloaded image (for offline/fast access)
    """

    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="MANUAL")
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Local path to downloaded cover image (e.g., "artwork/spotify/playlists/abc123.webp")
    cover_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # True for the special "Liked Songs" playlist - no Spotify URI for this one!
    is_liked_songs: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, server_default="0", default=False
    )
    # True if playlist is blacklisted (won't be re-synced from Spotify)
    is_blacklisted: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, server_default="0", default=False
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    playlist_tracks: Mapped[list["PlaylistTrackModel"]] = relationship(
        "PlaylistTrackModel",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistTrackModel.position",
    )


class PlaylistTrackModel(Base):
    """Association table for Playlist-Track relationship."""

    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    # Relationships
    playlist: Mapped["PlaylistModel"] = relationship(
        "PlaylistModel", back_populates="playlist_tracks"
    )
    track: Mapped["TrackModel"] = relationship("TrackModel")

    __table_args__ = (Index("ix_playlist_tracks_position", "playlist_id", "position"),)


class DownloadModel(Base):
    """SQLAlchemy model for Download entity."""

    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    track_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING", index=True
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )
    target_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    track: Mapped["TrackModel"] = relationship("TrackModel", back_populates="download")

    __table_args__ = (
        Index("ix_downloads_status_created", "status", "created_at"),
        Index("ix_downloads_priority_created", "priority", "created_at"),
    )


class LibraryScanModel(Base):
    """SQLAlchemy model for Library Scan tracking."""

    __tablename__ = "library_scans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    scan_path: Mapped[str] = mapped_column(String(512), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scanned_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    broken_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_library_scans_status", "status"),
        Index("ix_library_scans_started_at", "started_at"),
    )


class FileDuplicateModel(Base):
    """SQLAlchemy model for File Duplicate tracking."""

    __tablename__ = "file_duplicates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash_algorithm: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_track_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("soulspot_tracks.id", ondelete="CASCADE"), nullable=True
    )
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    primary_track: Mapped["TrackModel | None"] = relationship("TrackModel")

    __table_args__ = (
        Index("ix_file_duplicates_hash", "file_hash"),
        Index("ix_file_duplicates_resolved", "resolved"),
    )


class ArtistWatchlistModel(Base):
    """SQLAlchemy model for Artist Watchlist."""

    __tablename__ = "artist_watchlists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    artist_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_artists.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    check_frequency_hours: Mapped[int] = mapped_column(
        Integer, default=24, nullable=False
    )
    auto_download: Mapped[bool] = mapped_column(default=True, nullable=False)
    quality_profile: Mapped[str] = mapped_column(
        String(20), default="high", nullable=False
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_release_date: Mapped[datetime | None] = mapped_column(nullable=True)
    total_releases_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_downloads_triggered: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    artist: Mapped["ArtistModel"] = relationship("ArtistModel")

    __table_args__ = (
        Index("ix_artist_watchlists_artist_id", "artist_id"),
        Index("ix_artist_watchlists_status", "status"),
        Index("ix_artist_watchlists_last_checked", "last_checked_at"),
    )


class FilterRuleModel(Base):
    """SQLAlchemy model for Filter Rule."""

    __tablename__ = "filter_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filter_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # whitelist, blacklist
    target: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # keyword, user, format, bitrate
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    is_regex: Mapped[bool] = mapped_column(default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_filter_rules_type_enabled", "filter_type", "enabled"),
        Index("ix_filter_rules_priority", "priority"),
    )


class AutomationRuleModel(Base):
    """SQLAlchemy model for Automation Rule."""

    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # new_release, missing_album, quality_upgrade, manual
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # search_and_download, notify_only, add_to_queue
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_profile: Mapped[str] = mapped_column(
        String(20), default="high", nullable=False
    )
    apply_filters: Mapped[bool] = mapped_column(default=True, nullable=False)
    auto_process: Mapped[bool] = mapped_column(default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    total_executions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_executions: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    failed_executions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_automation_rules_trigger_enabled", "trigger", "enabled"),
        Index("ix_automation_rules_priority", "priority"),
    )


class QualityUpgradeCandidateModel(Base):
    """SQLAlchemy model for Quality Upgrade Candidate."""

    __tablename__ = "quality_upgrade_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    track_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_bitrate: Mapped[int] = mapped_column(Integer, nullable=False)
    current_format: Mapped[str] = mapped_column(String(20), nullable=False)
    target_bitrate: Mapped[int] = mapped_column(Integer, nullable=False)
    target_format: Mapped[str] = mapped_column(String(20), nullable=False)
    improvement_score: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    download_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("downloads.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    track: Mapped["TrackModel"] = relationship("TrackModel")
    download: Mapped["DownloadModel | None"] = relationship("DownloadModel")

    __table_args__ = (
        Index("ix_quality_upgrade_candidates_track_id", "track_id"),
        Index("ix_quality_upgrade_candidates_processed", "processed"),
        Index("ix_quality_upgrade_candidates_improvement_score", "improvement_score"),
    )


# Hey future me, SpotifySessionModel persists Spotify OAuth sessions to survive Docker restarts!
# The access_token and refresh_token are SENSITIVE - they grant full access to user's Spotify.
# Consider encrypting these fields at rest for production (use SQLAlchemy TypeDecorator with Fernet).
# The session_id is the PRIMARY KEY - it's the random urlsafe string stored in user's cookie.
# Sessions expire based on last_accessed_at + timeout (default 1 hour) - expired ones get cleaned up.
# oauth_state and code_verifier are TEMPORARY - only needed during OAuth flow, cleared after callback.
# This model replaces the in-memory dict in SessionStore - now sessions persist across restarts!
# RENAMED from SessionModel to SpotifySessionModel for service-agnostic architecture (2025-12-12).
class SpotifySessionModel(Base):
    """Spotify OAuth session with tokens for persistence across restarts.

    Stores Spotify OAuth tokens and session state in database to survive
    container restarts. Sessions are identified by session_id (cookie value).
    """

    __tablename__ = "spotify_sessions"

    # Primary key: session_id from cookie (urlsafe random string)
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # OAuth tokens (SENSITIVE - consider encrypting in production)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # OAuth flow state (temporary, cleared after callback)
    oauth_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Session lifecycle timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Indexes for efficient cleanup queries
    __table_args__ = (
        Index("ix_spotify_sessions_last_accessed", "last_accessed_at"),
        Index("ix_spotify_sessions_token_expires", "token_expires_at"),
    )


# =============================================================================
# SPOTIFY BROWSE MODELS (Separate from Local Library!)
# =============================================================================
# Hey future me - these models are for SYNCED SPOTIFY DATA only! They mirror what's on
# the user's Spotify account (followed artists, their albums, tracks). Completely separate
# from ArtistModel/AlbumModel/TrackModel which represent LOCAL library files.
#
# The flow is: User follows artist on Spotify → auto-sync saves to spotify_artists →
# user browses to artist detail → albums synced to spotify_albums → user clicks album →
# tracks synced to spotify_tracks → user downloads → creates entry in local TrackModel.
#
# CASCADE DELETE ensures clean removal: unfollow artist → albums gone → tracks gone.
# The local_track_id on SpotifyTrackModel links to downloaded files in local library.
# =============================================================================


class SpotifyArtistModel(Base):
    """Spotify artist from user's followed artists.

    Hey future me - this is NOT the same as ArtistModel!
    - ArtistModel = local library (tracks you downloaded)
    - SpotifyArtistModel = synced from Spotify account

    They can reference the same real-world artist but serve different purposes.
    SpotifyArtistModel persists even if you haven't downloaded any tracks yet.

    image_url = Spotify CDN URL (for comparison if image changed)
    image_path = Local path to downloaded image (for offline/fast access)
    """

    __tablename__ = "spotify_artists"

    # Spotify ID is the primary key (e.g., "0OdUWJ0sBjDrqHygGUXeCF")
    spotify_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Local path to downloaded image (e.g., "artwork/spotify/artists/0OdUWJ0sBjDrqHygGUXeCF.webp")
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Genres stored as JSON text: '["rock", "alternative"]'
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Sync timestamps for cooldown logic
    last_synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    albums_synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships - CASCADE delete albums when artist unfollowed
    albums: Mapped[list["SpotifyAlbumModel"]] = relationship(
        "SpotifyAlbumModel", back_populates="artist", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_spotify_artists_last_synced", "last_synced_at"),)


class SpotifyAlbumModel(Base):
    """Spotify album from a followed artist.

    Hey future me - albums get synced in two ways:
    1. Artist album sync: When user views artist, we sync all their albums
    2. Saved Albums: User explicitly saved this album (is_saved=True)

    is_saved=True means user has this in their "Saved Albums" collection,
    independent of whether they follow the artist. This affects sync behavior:
    - Artist albums get deleted if artist is unfollowed
    - Saved Albums persist until user removes them from saved albums

    image_url = Spotify CDN URL (for comparison if image changed)
    image_path = Local path to downloaded cover (for offline/fast access)
    """

    __tablename__ = "spotify_albums"

    spotify_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    artist_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spotify_artists.spotify_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Local path to downloaded cover (e.g., "artwork/spotify/albums/abc123.webp")
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # True if user has this album in "Saved Albums" (not just from followed artist)
    is_saved: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, server_default="0", default=False
    )
    # Release date can be "2023", "2023-05", or "2023-05-15"
    release_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True
    )
    release_date_precision: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    # album, single, compilation
    album_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_tracks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # When were tracks last synced for this album?
    tracks_synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    artist: Mapped["SpotifyArtistModel"] = relationship(
        "SpotifyArtistModel", back_populates="albums"
    )
    tracks: Mapped[list["SpotifyTrackModel"]] = relationship(
        "SpotifyTrackModel", back_populates="album", cascade="all, delete-orphan"
    )


class SpotifyTrackModel(Base):
    """Spotify track from an album.

    Synced when user opens album detail page. The local_track_id links to
    the local library entry AFTER the track has been downloaded via slskd.
    """

    __tablename__ = "spotify_tracks"

    spotify_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    album_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("spotify_albums.spotify_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    track_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    disc_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explicit: Mapped[bool] = mapped_column(default=False, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    isrc: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    # Link to local library after download
    local_track_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    album: Mapped["SpotifyAlbumModel"] = relationship(
        "SpotifyAlbumModel", back_populates="tracks"
    )
    local_track: Mapped["TrackModel | None"] = relationship("TrackModel")


class SpotifySyncStatusModel(Base):
    """Tracks sync status for different sync types.

    Enables cooldown logic - don't hammer Spotify API on every page load.
    Also provides UI feedback about last sync time and any errors.
    """

    __tablename__ = "spotify_sync_status"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # followed_artists, artist_albums, album_tracks
    sync_type: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # idle, running, error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# =============================================================================
# SPOTIFY TOKEN MODEL (Background Worker OAuth Token Storage)
# =============================================================================
# Hey future me - this is THE token store for background workers! Different from sessions table:
# - Sessions: User-facing, cookie-based, per browser session
# - Tokens: Background workers, survives logout, single active token
#
# Single-user architecture: We keep ONE row with id='default'. When user logs in via OAuth,
# we UPSERT this row. Background workers call get_active_token() and get this single token.
#
# The is_valid flag is CRITICAL for the UI warning system:
# - True = Token works, background workers operate normally
# - False = Refresh failed (user revoked access, etc.) → UI shows "re-authenticate" banner
#           → Workers skip their work (no crash loop) → User re-auths → is_valid=True again
#
# The token_refresh_worker runs every 5 min, checks token_expires_at, and proactively
# refreshes tokens before they expire. If refresh fails → is_valid=False + last_error set.
# =============================================================================


class SpotifyTokenModel(Base):
    """Spotify OAuth token for background workers.

    Single-user: exactly one row with id='default'. Background workers
    get this token for API calls. Separate from user sessions (cookie-based).

    The is_valid flag controls the UI warning banner - when False, users see
    "Spotify connection expired - please re-authenticate" message.
    """

    __tablename__ = "spotify_tokens"

    # Single-user: always 'default', could be spotify_user_id for multi-user
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # OAuth tokens (NOT encrypted - simplicity over security per user choice)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    # Scopes granted: "user-follow-read playlist-read-private ..."
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Validity flag - False when refresh fails (triggers UI warning)
    is_valid: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Error tracking for debugging and UI display
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Metadata timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_spotify_tokens_expires", "token_expires_at"),
        Index("ix_spotify_tokens_valid", "is_valid"),
    )

    # Hey future me - helper methods for cleaner code in services!
    # Use ensure_utc_aware() to handle naive datetimes from SQLite.
    def is_expired(self) -> bool:
        """Check if token is expired (past expiration time)."""
        return utc_now() >= ensure_utc_aware(self.token_expires_at)

    def expires_soon(self, minutes: int = 10) -> bool:
        """Check if token expires within given minutes (for proactive refresh)."""
        from datetime import timedelta

        threshold = utc_now() + timedelta(minutes=minutes)
        return ensure_utc_aware(self.token_expires_at) <= threshold


# =============================================================================
# APP SETTINGS MODEL (Dynamic Configuration without Restart)
# =============================================================================
# Hey future me - this is KEY-VALUE storage for runtime config!
# Unlike env-based Settings (pydantic-settings), these can be changed via UI
# without restarting the app. Used for: Spotify sync toggles, intervals, feature flags.
#
# Why not just use env vars?
# - Env vars require restart
# - Users want to toggle sync on/off from Settings page
# - Different settings per category (spotify, downloads, ui, etc.)
#
# Value types supported:
# - 'string': Plain text
# - 'boolean': 'true'/'false' (parsed in service layer)
# - 'integer': Numeric strings (parsed in service layer)
# - 'json': Complex objects/arrays (parsed via json.loads)
# =============================================================================


class AppSettingsModel(Base):
    """Dynamic application settings stored in DB.

    Key-value store for runtime configuration. Unlike env vars, these
    can be changed via Settings UI without app restart.

    Example keys:
    - 'spotify.auto_sync_enabled' (boolean)
    - 'spotify.artists_sync_interval_minutes' (integer)
    - 'spotify.download_images' (boolean)
    """

    __tablename__ = "app_settings"

    # Setting key (e.g., "spotify.auto_sync_enabled")
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    # Value as string (parsed based on value_type)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Type hint: 'string', 'boolean', 'integer', 'json'
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="string", default="string"
    )
    # Category for grouping in UI (e.g., "spotify", "downloads", "ui")
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="general", default="general"
    )
    # Human-readable description for Settings UI tooltips
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Index for fast category lookups (get all "spotify" settings)
    __table_args__ = (Index("ix_app_settings_category", "category"),)


# =============================================================================
# DUPLICATE CANDIDATES TABLE (for DuplicateDetectorWorker)
# =============================================================================
# Hey future me - this tracks POTENTIAL duplicates found by the worker!
# The worker scans the library and finds tracks that might be duplicates
# (same artist+title, similar duration). Stores them here for manual review.
# User confirms/dismisses via UI - we DON'T auto-delete anything!
# =============================================================================


class DuplicateCandidateModel(Base):
    """Potential duplicate track pairs for review.

    DuplicateDetectorWorker populates this table. Users review in UI
    and decide what to do (keep one, keep both, merge metadata, etc.).
    """

    __tablename__ = "duplicate_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # The two tracks that might be duplicates
    # Constraint ensures track_id_1 < track_id_2 to avoid (A,B) and (B,A) rows
    track_id_1: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id_2: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Confidence score 0-100 (100 = definitely same track)
    similarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # How the match was found: 'metadata' or 'fingerprint' (future)
    match_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="metadata"
    )
    # Review status: pending, confirmed, dismissed, auto_resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # JSON with match details (which fields matched, individual scores)
    match_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What user did: keep_first, keep_second, keep_both, merged
    resolution_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Relationships to get track details easily
    track_1: Mapped["TrackModel"] = relationship(
        "TrackModel", foreign_keys=[track_id_1], lazy="joined"
    )
    track_2: Mapped["TrackModel"] = relationship(
        "TrackModel", foreign_keys=[track_id_2], lazy="joined"
    )

    __table_args__ = (
        sa.CheckConstraint("track_id_1 < track_id_2", name="ck_track_order"),
        sa.UniqueConstraint("track_id_1", "track_id_2", name="uq_duplicate_pair"),
        Index("ix_duplicate_candidates_status", "status"),
    )


# =============================================================================
# ORPHANED FILES TABLE (for CleanupWorker)
# =============================================================================
# Hey future me - this tracks FILES and DB entries that are out of sync!
# Two types:
# - file_no_db: File exists on disk but no DB entry (e.g., manual file copy)
# - db_no_file: DB entry exists but file missing (e.g., file deleted externally)
# CleanupWorker detects these and stores for review. User decides action in UI.
# =============================================================================


class OrphanedFileModel(Base):
    """Files or DB entries that are orphaned (missing counterpart).

    CleanupWorker populates this. Users review in UI and decide action
    (delete file, import to library, ignore, etc.).
    """

    __tablename__ = "orphaned_files"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Path to the orphaned file (or expected path for db_no_file)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    # Size in bytes (null for db_no_file type)
    file_size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    # Last modification time
    file_modified_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Type: 'file_no_db' or 'db_no_file'
    orphan_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Related track if this is a db_no_file orphan
    related_track_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("soulspot_tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Status: pending, resolved, ignored
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Action taken: deleted, imported, linked, ignored
    resolution_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Relationship to track (if applicable)
    related_track: Mapped["TrackModel | None"] = relationship(
        "TrackModel", foreign_keys=[related_track_id], lazy="joined"
    )

    __table_args__ = (
        Index("ix_orphaned_files_status", "status"),
        Index("ix_orphaned_files_type", "orphan_type"),
    )


# =============================================================================
# ENRICHMENT CANDIDATES
# =============================================================================
# Hey future me - this stores potential Spotify matches for local library items!
# When enriching local library, if we find multiple Spotify results that could match,
# we store them here for user review. This avoids auto-matching "Pink Floyd" to
# some random tribute band. User picks the correct one in UI, we apply that match.
#
# entity_type: 'artist' or 'album'
# entity_id: FK to soulspot_artists or soulspot_albums (polymorphic reference)
# confidence_score: 0.0 - 1.0, how confident we are this is the right match
# is_selected: User chose this candidate as correct
# is_rejected: User explicitly rejected this candidate
# =============================================================================


class EnrichmentCandidateModel(Base):
    """Potential Spotify matches for local library entities.

    Stores candidates when enrichment finds multiple possible matches
    so users can review and select the correct one.
    """

    __tablename__ = "enrichment_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Entity type: 'artist' or 'album'
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Polymorphic FK - points to soulspot_artists or soulspot_albums based on entity_type
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # Spotify URI of this candidate (e.g., spotify:artist:XXXXX)
    spotify_uri: Mapped[str] = mapped_column(String(255), nullable=False)
    # Name from Spotify (for display in UI)
    spotify_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Image URL from Spotify (for preview in UI)
    spotify_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Match confidence 0.0-1.0 (higher = better match)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # User selected this candidate as correct
    is_selected: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    # User explicitly rejected this candidate
    is_rejected: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    # Additional info (genres, followers, etc.) stored as JSON
    extra_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_enrichment_entity", "entity_type", "entity_id"),
        Index("ix_enrichment_spotify_uri", "spotify_uri"),
        Index("ix_enrichment_confidence", "confidence_score"),
    )
