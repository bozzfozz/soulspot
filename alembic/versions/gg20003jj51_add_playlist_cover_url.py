"""add_playlist_cover_url

Revision ID: gg20003jj51
Revises: ff20002ii50
Create Date: 2025-11-26 01:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "gg20003jj51"
down_revision: str | None = "ff20002ii50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add cover_url column to playlists table for Spotify playlist covers."""
    # Add cover_url column to playlists table
    op.add_column(
        "playlists", sa.Column("cover_url", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    """Remove cover_url column from playlists table."""
    # Remove cover_url column
    op.drop_column("playlists", "cover_url")
