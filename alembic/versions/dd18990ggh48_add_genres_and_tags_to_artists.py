"""add_genres_and_tags_to_artists

Revision ID: dd18990ggh48
Revises: 0372f0c937d1
Create Date: 2025-11-23 07:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd18990ggh48"
down_revision: str | Sequence[str] | None = "0372f0c937d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add genres and tags fields to artists table.

    Hey future me - adding genres and tags as JSON text fields to store multiple genres/tags
    per artist fetched from Spotify API. We use TEXT instead of JSON type for SQLite compatibility
    (SQLite doesn't have native JSON type). The application layer handles JSON serialization/
    deserialization. No index needed initially - can add later if genre filtering becomes common.
    These fields are nullable because existing artists won't have this data until next Spotify sync.
    """
    # Add genres as TEXT column (stores JSON array like '["rock", "alternative", "indie"]')
    op.add_column("artists", sa.Column("genres", sa.Text(), nullable=True))

    # Add tags as TEXT column (stores JSON array for additional metadata tags)
    op.add_column("artists", sa.Column("tags", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema - remove genres and tags fields from artists table.

    Warning: This will DELETE all genre and tag data! Run only if you're sure you want to
    revert this migration. Data cannot be recovered after downgrade without a backup.
    """
    op.drop_column("artists", "tags")
    op.drop_column("artists", "genres")
