"""Add duplicate_candidates table for duplicate track detection.

Revision ID: kk24007nno55
Revises: mm24007nnp55
Create Date: 2025-11-28 10:00:00.000000

Hey future me - this migration adds the DUPLICATE DETECTION infrastructure!

Problem: Music libraries often have duplicate tracks - same song downloaded multiple times,
different versions of same track, re-releases, etc. These waste disk space and clutter the UI.

Solution: DuplicateDetectorWorker scans library and finds potential duplicates using metadata
matching (artist + title + duration). Stores candidates in this table for manual review.

The duplicate_candidates table stores:
- track_id_1, track_id_2: The two tracks that might be duplicates
- similarity_score: 0-100, how confident we are they're duplicates
- match_type: 'metadata' (name+artist+duration) or 'fingerprint' (audio analysis, future)
- status: 'pending' (needs review), 'confirmed' (user said yes), 'dismissed' (user said no)
- created_at, reviewed_at: Timestamps for tracking

IMPORTANT: We use CHECK constraint to ensure track_id_1 < track_id_2 to avoid storing
(A,B) and (B,A) as separate rows. Unique constraint enforces one entry per pair.

Also adds orphaned_files table for CleanupWorker to track files that exist on disk
but have no corresponding DB entry (or vice versa).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "kk24007nno55"
down_revision = "mm24007nnp55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create duplicate_candidates and orphaned_files tables."""

    # =========================================================================
    # DUPLICATE CANDIDATES TABLE
    # =========================================================================
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "track_id_1",
            sa.String(36),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "track_id_2",
            sa.String(36),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "similarity_score",
            sa.Integer,
            nullable=False,
            comment="0-100 confidence score",
        ),
        sa.Column(
            "match_type",
            sa.String(20),
            nullable=False,
            default="metadata",
            comment="metadata or fingerprint",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="pending",
            comment="pending, confirmed, dismissed, auto_resolved",
        ),
        sa.Column(
            "match_details",
            sa.Text,
            nullable=True,
            comment="JSON with match details (which fields matched, scores)",
        ),
        sa.Column(
            "resolution_action",
            sa.String(50),
            nullable=True,
            comment="Action taken: keep_first, keep_second, keep_both, merged",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Ensure track_id_1 < track_id_2 to avoid duplicate pairs (A,B) and (B,A)
        sa.CheckConstraint("track_id_1 < track_id_2", name="ck_track_order"),
        # Unique constraint on the pair
        sa.UniqueConstraint("track_id_1", "track_id_2", name="uq_duplicate_pair"),
    )

    # Index for finding all duplicates of a specific track
    op.create_index(
        "ix_duplicate_candidates_tracks",
        "duplicate_candidates",
        ["track_id_1", "track_id_2"],
    )

    # Index for filtering by status (most common query)
    op.create_index(
        "ix_duplicate_candidates_status",
        "duplicate_candidates",
        ["status"],
    )

    # =========================================================================
    # ORPHANED FILES TABLE (for CleanupWorker)
    # =========================================================================
    op.create_table(
        "orphaned_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "file_path",
            sa.String(1024),
            nullable=False,
            unique=True,
            comment="Absolute path to the orphaned file",
        ),
        sa.Column(
            "file_size_bytes",
            sa.BigInteger,
            nullable=True,
            comment="Size of the file in bytes",
        ),
        sa.Column(
            "file_modified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last modification time of the file",
        ),
        sa.Column(
            "orphan_type",
            sa.String(30),
            nullable=False,
            comment="file_no_db (file exists, no DB entry) or db_no_file (DB entry, file missing)",
        ),
        sa.Column(
            "related_track_id",
            sa.String(36),
            sa.ForeignKey("tracks.id", ondelete="SET NULL"),
            nullable=True,
            comment="Track ID if this is a db_no_file orphan",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="pending",
            comment="pending, resolved, ignored",
        ),
        sa.Column(
            "resolution_action",
            sa.String(50),
            nullable=True,
            comment="Action taken: deleted, imported, linked, ignored",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Index for finding orphans by status
    op.create_index(
        "ix_orphaned_files_status",
        "orphaned_files",
        ["status"],
    )

    # Index for finding orphans by type
    op.create_index(
        "ix_orphaned_files_type",
        "orphaned_files",
        ["orphan_type"],
    )


def downgrade() -> None:
    """Drop duplicate_candidates and orphaned_files tables."""
    op.drop_index("ix_orphaned_files_type", table_name="orphaned_files")
    op.drop_index("ix_orphaned_files_status", table_name="orphaned_files")
    op.drop_table("orphaned_files")

    op.drop_index("ix_duplicate_candidates_status", table_name="duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_tracks", table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")
