"""Add is_blacklisted field to playlists table.

Revision ID: oo26011qqr59
Revises: nn25010ppr58
Create Date: 2025-11-30 12:00:00.000000

Hey future me - this adds the ability to blacklist playlists!

When a playlist is blacklisted:
- It won't be re-imported during Spotify sync
- It's hidden from the UI by default (can be shown with filter)
- Useful for excluding shared/followed playlists you don't want

The sync worker checks is_blacklisted before re-syncing playlists.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "oo26011qqr59"
down_revision: str | None = "nn25010ppr58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_blacklisted column to playlists table."""
    # Add is_blacklisted field - defaults to False
    op.add_column(
        "playlists",
        sa.Column(
            "is_blacklisted",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )

    # Add index for filtering blacklisted playlists
    op.create_index(
        "ix_playlists_is_blacklisted",
        "playlists",
        ["is_blacklisted"],
    )


def downgrade() -> None:
    """Remove is_blacklisted column."""
    op.drop_index("ix_playlists_is_blacklisted", table_name="playlists")
    op.drop_column("playlists", "is_blacklisted")
