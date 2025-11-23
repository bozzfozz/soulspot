"""SQLAlchemy ORM models for SoulSpot Bridge."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import (
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
class ArtistModel(Base):
    """SQLAlchemy model for Artist entity."""

    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    # Hey future me - genres and tags are stored as JSON text (SQLite compatible)!
    # The app layer serializes/deserializes list[str] to/from JSON string.
    # Example: '["rock", "alternative", "indie"]'. Nullable because existing artists
    # won't have this data until next Spotify sync. Migration dd18990ggh48 adds these.
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    """SQLAlchemy model for Album entity."""

    __tablename__ = "albums"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
    )
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    spotify_uri: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    musicbrainz_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    artist: Mapped["ArtistModel"] = relationship("ArtistModel", back_populates="albums")
    tracks: Mapped[list["TrackModel"]] = relationship(
        "TrackModel", back_populates="album", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_albums_title_artist", "title", "artist_id"),)


# Hey future me, TrackModel is the BUSIEST table - queries hit it constantly! The file_*
# fields (file_size, file_hash, file_hash_algorithm) are for library integrity checks - detecting
# duplicates, corruption, etc. The is_broken flag marks files that failed validation (corrupt,
# deleted, permission issues). The audio_* fields store technical metadata (bitrate, format,
# sample_rate) for quality filtering and upgrade detection. The indexes on title+artist_id and
# file_hash are CRITICAL for performance - without them, duplicate detection scans the entire
# table! The download relationship uses uselist=False because it's ONE-TO-ONE (each track has
# at most one active download). Be careful with migrations - this table can have millions of rows!
class TrackModel(Base):
    """SQLAlchemy model for Track entity."""

    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
    )
    album_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("albums.id", ondelete="SET NULL"), nullable=True
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
    """SQLAlchemy model for Playlist entity."""

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
        String(36), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
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
        ForeignKey("tracks.id", ondelete="CASCADE"),
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
        String(36), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True
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
        ForeignKey("artists.id", ondelete="CASCADE"),
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
        ForeignKey("tracks.id", ondelete="CASCADE"),
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


class WidgetModel(Base):
    """SQLAlchemy model for Widget entity (widget registry)."""

    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_path: Mapped[str] = mapped_column(String(200), nullable=False)
    default_config: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    # Relationships
    instances: Mapped[list["WidgetInstanceModel"]] = relationship(
        "WidgetInstanceModel", back_populates="widget", cascade="all, delete-orphan"
    )


class PageModel(Base):
    """SQLAlchemy model for Page entity (dashboard pages)."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    widget_instances: Mapped[list["WidgetInstanceModel"]] = relationship(
        "WidgetInstanceModel", back_populates="page", cascade="all, delete-orphan"
    )


class WidgetInstanceModel(Base):
    """SQLAlchemy model for WidgetInstance entity (placed widgets on pages)."""

    __tablename__ = "widget_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    widget_type: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("widgets.type", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position_row: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_col: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    span_cols: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    config: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    page: Mapped["PageModel"] = relationship(
        "PageModel", back_populates="widget_instances"
    )
    widget: Mapped["WidgetModel"] = relationship(
        "WidgetModel", back_populates="instances"
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "page_id", "position_row", "position_col", name="uq_widget_position"
        ),
    )


# Hey future me, SessionModel persists user sessions to survive Docker restarts!
# The access_token and refresh_token are SENSITIVE - they grant full access to user's Spotify.
# Consider encrypting these fields at rest for production (use SQLAlchemy TypeDecorator with Fernet).
# The session_id is the PRIMARY KEY - it's the random urlsafe string stored in user's cookie.
# Sessions expire based on last_accessed_at + timeout (default 1 hour) - expired ones get cleaned up.
# oauth_state and code_verifier are TEMPORARY - only needed during OAuth flow, cleared after callback.
# This model replaces the in-memory dict in SessionStore - now sessions persist across restarts!
class SessionModel(Base):
    """User session with OAuth tokens for persistence across restarts.

    Stores Spotify OAuth tokens and session state in database to survive
    container restarts. Sessions are identified by session_id (cookie value).
    """

    __tablename__ = "sessions"

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
        Index("ix_sessions_last_accessed", "last_accessed_at"),
        Index("ix_sessions_token_expires", "token_expires_at"),
    )
