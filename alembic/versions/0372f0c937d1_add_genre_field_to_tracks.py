"""add_genre_field_to_tracks

Revision ID: 0372f0c937d1
Revises: 0b88b6152c1d
Create Date: 2025-11-22 04:55:35.273405

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0372f0c937d1"
down_revision: str | Sequence[str] | None = "0b88b6152c1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add genre field to tracks table."""
    # Hey future me - adding genre field for primary genre classification!
    # This stores the main genre (e.g., "Rock", "Jazz") for filtering/display.
    # Index added because genre filtering is common in music apps.
    op.add_column("tracks", sa.Column("genre", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_tracks_genre"), "tracks", ["genre"], unique=False)


def downgrade() -> None:
    """Downgrade schema - remove genre field from tracks table."""
    op.drop_index(op.f("ix_tracks_genre"), table_name="tracks")
    op.drop_column("tracks", "genre")
