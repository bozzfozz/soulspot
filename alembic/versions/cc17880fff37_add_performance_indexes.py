"""Add performance indexes for query optimization.

Revision ID: cc17880fff37
Revises: bb16770eeg26
Create Date: 2025-11-16 11:30:00.000000

This migration adds composite and single-column indexes to improve query performance
for common access patterns identified in the Performance & Scalability epic.

Key optimizations:
1. Composite indexes for frequently joined queries (album_id + track_number)
2. Index on artist_id in albums for artist->albums queries
3. Index on updated_at for filtering recently modified entities
4. Index on completed_at in downloads for reporting
5. Index on file_path in tracks for file system operations
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "cc17880fff37"
down_revision = "bb16770eeg26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance-enhancing indexes."""
    # Composite index for tracks by album with ordering by track number
    # Optimizes queries like: SELECT * FROM tracks WHERE album_id = ? ORDER BY track_number
    op.create_index(
        "ix_tracks_album_track_number",
        "tracks",
        ["album_id", "track_number"],
        unique=False,
    )

    # Composite index for tracks by album and disc
    # Optimizes queries with both album_id and disc_number filters
    op.create_index(
        "ix_tracks_album_disc_track",
        "tracks",
        ["album_id", "disc_number", "track_number"],
        unique=False,
    )

    # Index on artist_id in albums for artist->albums relationship queries
    # Optimizes queries like: SELECT * FROM albums WHERE artist_id = ?
    op.create_index("ix_albums_artist_id", "albums", ["artist_id"], unique=False)

    # Index on updated_at for filtering recently modified entities
    # Useful for sync operations and change tracking
    op.create_index("ix_tracks_updated_at", "tracks", ["updated_at"], unique=False)

    op.create_index("ix_albums_updated_at", "albums", ["updated_at"], unique=False)

    op.create_index("ix_artists_updated_at", "artists", ["updated_at"], unique=False)

    # Index on completed_at in downloads for completed download queries
    # Optimizes queries filtering by completion status with time ranges
    op.create_index(
        "ix_downloads_completed_at", "downloads", ["completed_at"], unique=False
    )

    # Index on file_path for file system lookup operations
    # Optimizes queries like: SELECT * FROM tracks WHERE file_path = ?
    op.create_index("ix_tracks_file_path", "tracks", ["file_path"], unique=False)

    # Composite index for downloads by status and priority
    # Optimizes queue processing queries: SELECT * FROM downloads WHERE status = ? ORDER BY priority DESC
    op.create_index(
        "ix_downloads_status_priority",
        "downloads",
        ["status", "priority"],
        unique=False,
    )

    # Index on last_scanned_at for library management queries
    # Optimizes queries filtering by scan date
    op.create_index(
        "ix_tracks_last_scanned_at", "tracks", ["last_scanned_at"], unique=False
    )

    # Composite index on is_broken and updated_at for broken file monitoring
    # Optimizes queries: SELECT * FROM tracks WHERE is_broken = true ORDER BY updated_at DESC
    op.create_index(
        "ix_tracks_broken_updated", "tracks", ["is_broken", "updated_at"], unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index("ix_tracks_broken_updated", table_name="tracks")
    op.drop_index("ix_tracks_last_scanned_at", table_name="tracks")
    op.drop_index("ix_downloads_status_priority", table_name="downloads")
    op.drop_index("ix_tracks_file_path", table_name="tracks")
    op.drop_index("ix_downloads_completed_at", table_name="downloads")
    op.drop_index("ix_artists_updated_at", table_name="artists")
    op.drop_index("ix_albums_updated_at", table_name="albums")
    op.drop_index("ix_tracks_updated_at", table_name="tracks")
    op.drop_index("ix_albums_artist_id", table_name="albums")
    op.drop_index("ix_tracks_album_disc_track", table_name="tracks")
    op.drop_index("ix_tracks_album_track_number", table_name="tracks")
