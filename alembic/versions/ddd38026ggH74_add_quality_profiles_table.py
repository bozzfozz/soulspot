"""Add quality_profiles table for download quality preferences.

Revision ID: ddd38026ggH74
Revises: ccc38025ffG73
Create Date: 2025-01-XX

Hey future me – This migration adds the quality_profiles table!
Quality profiles define download preferences: format preferences (FLAC > MP3),
bitrate constraints (min/max), file size limits, and exclude keywords.
The "is_active" column marks which profile is currently used for downloads.

Default profiles (AUDIOPHILE, BALANCED, SPACE_SAVER) are inserted by
IQualityProfileRepository.ensure_defaults_exist() on app startup, not here!
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "ddd38026ggH74"
down_revision = "ccc38025ffG73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create quality_profiles table."""
    op.create_table(
        "quality_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        # JSON array of preferred formats in priority order: ["flac", "mp3", "aac"]
        sa.Column("preferred_formats", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("min_bitrate", sa.Integer, nullable=True),  # kbps, NULL = no minimum
        sa.Column("max_bitrate", sa.Integer, nullable=True),  # kbps, NULL = no maximum
        sa.Column(
            "max_file_size_mb", sa.Integer, nullable=True
        ),  # MB, NULL = no limit
        # JSON array of keywords to exclude from results: ["live", "remix"]
        sa.Column("exclude_keywords", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Index for fast lookup of active profile
    op.create_index(
        "ix_quality_profiles_is_active",
        "quality_profiles",
        ["is_active"],
        unique=False,
    )

    # Index for name lookup (already unique constraint, but explicit index)
    op.create_index(
        "ix_quality_profiles_name",
        "quality_profiles",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    """Drop quality_profiles table."""
    op.drop_index("ix_quality_profiles_name", table_name="quality_profiles")
    op.drop_index("ix_quality_profiles_is_active", table_name="quality_profiles")
    op.drop_table("quality_profiles")
