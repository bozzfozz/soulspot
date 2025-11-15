"""SQLAlchemy ORM models for SoulSpot Bridge."""

import uuid
from datetime import UTC, datetime

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


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


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
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
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
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_hash_algorithm: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_track_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True
    )
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
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
