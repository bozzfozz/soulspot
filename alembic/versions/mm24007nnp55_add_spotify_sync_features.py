"""Add Spotify sync features: image paths, liked songs, saved albums.

Revision ID: mm24007nnp55
Revises: jj23006mmn54
Create Date: 2025-11-27 16:00:00.000000

Hey future me - this migration adds LOCAL IMAGE STORAGE for Spotify data!

Problem: We stored Spotify CDN URLs (image_url, cover_url). If Spotify changes URLs
or user is offline, images break. Also no way to know when image changed on Spotify.

Solution: Download images locally, store path in image_path/cover_path column.
Keep original URL in image_url for comparison (detect when Spotify updated the image).

New columns:
- spotify_artists.image_path: Local path to artist profile image
- spotify_albums.image_path: Local path to album cover
- spotify_albums.is_saved: True if user has this album in "Saved Albums" (not just from followed artist)
- playlists.cover_path: Local path to playlist cover
- playlists.is_liked_songs: True if this is the special "Liked Songs" playlist

Also adds app_settings table for dynamic Spotify sync configuration (no app restart needed).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "mm24007nnp55"
down_revision = "jj23006mmn54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add image_path columns and sync-related fields."""

    # Add image_path to spotify_artists (local path for downloaded image)
    op.add_column(
        "spotify_artists",
        sa.Column("image_path", sa.String(512), nullable=True),
    )

    # Add image_path to spotify_albums (local path for downloaded cover)
    op.add_column(
        "spotify_albums",
        sa.Column("image_path", sa.String(512), nullable=True),
    )

    # Add is_saved flag to spotify_albums (True if in user's "Saved Albums")
    # This differentiates "saved by user" from "synced because of followed artist"
    op.add_column(
        "spotify_albums",
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Add cover_path to playlists (local path for downloaded cover)
    op.add_column(
        "playlists",
        sa.Column("cover_path", sa.String(512), nullable=True),
    )

    # Add is_liked_songs flag to playlists (True for special "Liked Songs" playlist)
    op.add_column(
        "playlists",
        sa.Column("is_liked_songs", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Create app_settings table for dynamic configuration
    # Hey future me - this is KEY-VALUE storage for runtime settings!
    # Unlike env-based Settings, these can be changed via UI without restart.
    # Used for: Spotify sync toggles, intervals, feature flags, etc.
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        # JSON type hint for complex values (object, array, etc.)
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("description", sa.String(500), nullable=True),
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
    )

    # Index for fast category lookups (get all "spotify" settings)
    op.create_index(
        "ix_app_settings_category",
        "app_settings",
        ["category"],
        unique=False,
    )

    # Insert default Spotify sync settings
    # Hey - these are the DEFAULT values, user can change via Settings UI
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, category, description) VALUES
        ('spotify.auto_sync_enabled', 'true', 'boolean', 'spotify', 'Master switch for all Spotify auto-sync'),
        ('spotify.auto_sync_artists', 'true', 'boolean', 'spotify', 'Auto-sync followed artists'),
        ('spotify.auto_sync_playlists', 'true', 'boolean', 'spotify', 'Auto-sync user playlists'),
        ('spotify.auto_sync_liked_songs', 'true', 'boolean', 'spotify', 'Auto-sync Liked Songs'),
        ('spotify.auto_sync_saved_albums', 'true', 'boolean', 'spotify', 'Auto-sync Saved Albums'),
        ('spotify.artists_sync_interval_minutes', '5', 'integer', 'spotify', 'Cooldown between artist syncs'),
        ('spotify.playlists_sync_interval_minutes', '10', 'integer', 'spotify', 'Cooldown between playlist syncs'),
        ('spotify.download_images', 'true', 'boolean', 'spotify', 'Download images locally for offline use'),
        ('spotify.remove_unfollowed_artists', 'true', 'boolean', 'spotify', 'Remove artists when unfollowed on Spotify'),
        ('spotify.remove_unfollowed_playlists', 'false', 'boolean', 'spotify', 'Remove playlists deleted on Spotify')
    """)


def downgrade() -> None:
    """Remove image_path columns and sync-related fields."""

    # Drop app_settings table
    op.drop_index("ix_app_settings_category", table_name="app_settings")
    op.drop_table("app_settings")

    # Remove columns from playlists
    op.drop_column("playlists", "is_liked_songs")
    op.drop_column("playlists", "cover_path")

    # Remove columns from spotify_albums
    op.drop_column("spotify_albums", "is_saved")
    op.drop_column("spotify_albums", "image_path")

    # Remove column from spotify_artists
    op.drop_column("spotify_artists", "image_path")
