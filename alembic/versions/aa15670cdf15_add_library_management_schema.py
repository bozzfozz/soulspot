"""add_library_management_schema

Revision ID: aa15670cdf15
Revises: 46d1c2c2f85b
Create Date: 2025-11-15 20:24:33.076359

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa15670cdf15"
down_revision: str | Sequence[str] | None = "46d1c2c2f85b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add file integrity fields to tracks table
    op.add_column("tracks", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("tracks", sa.Column("file_hash", sa.String(64), nullable=True))
    op.add_column(
        "tracks", sa.Column("file_hash_algorithm", sa.String(20), nullable=True)
    )
    op.add_column("tracks", sa.Column("last_scanned_at", sa.DateTime(), nullable=True))
    op.add_column(
        "tracks",
        sa.Column("is_broken", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("tracks", sa.Column("audio_bitrate", sa.Integer(), nullable=True))
    op.add_column("tracks", sa.Column("audio_format", sa.String(20), nullable=True))
    op.add_column("tracks", sa.Column("audio_sample_rate", sa.Integer(), nullable=True))

    # Create indexes on tracks
    op.create_index("ix_tracks_file_hash", "tracks", ["file_hash"])
    op.create_index("ix_tracks_is_broken", "tracks", ["is_broken"])

    # Create library_scans table
    op.create_table(
        "library_scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("scan_path", sa.String(512), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scanned_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("broken_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Create indexes separately
    op.create_index("ix_library_scans_status", "library_scans", ["status"])
    op.create_index("ix_library_scans_started_at", "library_scans", ["started_at"])

    # Create file_duplicates table
    op.create_table(
        "file_duplicates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_hash_algorithm", sa.String(20), nullable=False),
        sa.Column(
            "primary_track_id",
            sa.String(36),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "total_size_bytes", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Create indexes separately
    op.create_index("ix_file_duplicates_hash", "file_duplicates", ["file_hash"])
    op.create_index("ix_file_duplicates_resolved", "file_duplicates", ["resolved"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes from file_duplicates
    op.drop_index("ix_file_duplicates_resolved", table_name="file_duplicates")
    op.drop_index("ix_file_duplicates_hash", table_name="file_duplicates")

    # Drop table
    op.drop_table("file_duplicates")

    # Drop indexes from library_scans
    op.drop_index("ix_library_scans_started_at", table_name="library_scans")
    op.drop_index("ix_library_scans_status", table_name="library_scans")

    # Drop table
    op.drop_table("library_scans")

    # Drop indexes from tracks
    op.drop_index("ix_tracks_is_broken", table_name="tracks")
    op.drop_index("ix_tracks_file_hash", table_name="tracks")

    # Remove columns from tracks
    op.drop_column("tracks", "audio_sample_rate")
    op.drop_column("tracks", "audio_format")
    op.drop_column("tracks", "audio_bitrate")
    op.drop_column("tracks", "is_broken")
    op.drop_column("tracks", "last_scanned_at")
    op.drop_column("tracks", "file_hash_algorithm")
    op.drop_column("tracks", "file_hash")
    op.drop_column("tracks", "file_size")
