"""add_spotify_browse_tables

Revision ID: hh21004kkl52
Revises: gg20003jj51
Create Date: 2025-11-27 12:00:00.000000

Hey future me - these tables are for SPOTIFY DATA ONLY! They're completely separate from the
local library tables (artists, albums, tracks). The naming with "spotify_" prefix makes it clear.

The key insight: we sync followed artists from Spotify automatically, then lazily load their
albums/tracks when user navigates to detail pages. CASCADE DELETE ensures: unfollow artist →
wipe all their albums → wipe all their tracks. Clean and no orphans!

spotify_artists.last_synced_at tracks when we last checked Spotify for updates - enables cooldown
logic to avoid hammering the API on every page load.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "hh21004kkl52"
down_revision: str | None = "gg20003jj51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create spotify_artists, spotify_albums, spotify_tracks tables."""

    # Spotify Artists - followed artists from user's Spotify account
    op.create_table(
        "spotify_artists",
        sa.Column("spotify_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("genres", sa.Text(), nullable=True),  # JSON array as text
        sa.Column("popularity", sa.Integer(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("albums_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("spotify_id"),
    )
    op.create_index(
        "ix_spotify_artists_name", "spotify_artists", ["name"], unique=False
    )
    op.create_index(
        "ix_spotify_artists_last_synced",
        "spotify_artists",
        ["last_synced_at"],
        unique=False,
    )

    # Spotify Albums - albums/singles from followed artists
    op.create_table(
        "spotify_albums",
        sa.Column("spotify_id", sa.String(length=32), nullable=False),
        sa.Column("artist_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column(
            "release_date", sa.String(length=10), nullable=True
        ),  # YYYY or YYYY-MM-DD
        sa.Column(
            "release_date_precision", sa.String(length=10), nullable=True
        ),  # day, month, year
        sa.Column(
            "album_type", sa.String(length=20), nullable=False
        ),  # album, single, compilation
        sa.Column("total_tracks", sa.Integer(), nullable=False, default=0),
        sa.Column("tracks_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["artist_id"], ["spotify_artists.spotify_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("spotify_id"),
    )
    op.create_index(
        "ix_spotify_albums_artist_id", "spotify_albums", ["artist_id"], unique=False
    )
    op.create_index("ix_spotify_albums_name", "spotify_albums", ["name"], unique=False)
    op.create_index(
        "ix_spotify_albums_album_type", "spotify_albums", ["album_type"], unique=False
    )
    op.create_index(
        "ix_spotify_albums_release_date",
        "spotify_albums",
        ["release_date"],
        unique=False,
    )

    # Spotify Tracks - tracks from albums
    op.create_table(
        "spotify_tracks",
        sa.Column("spotify_id", sa.String(length=32), nullable=False),
        sa.Column("album_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("track_number", sa.Integer(), nullable=False, default=1),
        sa.Column("disc_number", sa.Integer(), nullable=False, default=1),
        sa.Column("duration_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("explicit", sa.Boolean(), nullable=False, default=False),
        sa.Column("preview_url", sa.String(length=512), nullable=True),
        sa.Column("isrc", sa.String(length=12), nullable=True),
        # Link to local library - wenn Track heruntergeladen wurde
        sa.Column("local_track_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["album_id"], ["spotify_albums.spotify_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["local_track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("spotify_id"),
    )
    op.create_index(
        "ix_spotify_tracks_album_id", "spotify_tracks", ["album_id"], unique=False
    )
    op.create_index("ix_spotify_tracks_name", "spotify_tracks", ["name"], unique=False)
    op.create_index("ix_spotify_tracks_isrc", "spotify_tracks", ["isrc"], unique=False)
    op.create_index(
        "ix_spotify_tracks_local_track_id",
        "spotify_tracks",
        ["local_track_id"],
        unique=False,
    )

    # Sync-Status-Tabelle für globalen Sync-State
    op.create_table(
        "spotify_sync_status",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "sync_type", sa.String(length=50), nullable=False
        ),  # followed_artists, artist_albums, album_tracks
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, default="idle"
        ),  # idle, running, error
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("items_synced", sa.Integer(), nullable=False, default=0),
        sa.Column("items_added", sa.Integer(), nullable=False, default=0),
        sa.Column("items_removed", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_spotify_sync_status_sync_type",
        "spotify_sync_status",
        ["sync_type"],
        unique=True,
    )


def downgrade() -> None:
    """Drop spotify_* tables."""
    op.drop_table("spotify_sync_status")
    op.drop_table("spotify_tracks")
    op.drop_table("spotify_albums")
    op.drop_table("spotify_artists")
