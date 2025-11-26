"""add_album_artwork_url

Revision ID: ff20002ii50
Revises: ee19001hhj49
Create Date: 2025-11-26 01:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff20002ii50'
down_revision: Union[str, None] = 'ee19001hhj49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add artwork_url column to albums table for Spotify album covers."""
    # Add artwork_url column to albums table
    op.add_column('albums', sa.Column('artwork_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Remove artwork_url column from albums table."""
    # Remove artwork_url column
    op.drop_column('albums', 'artwork_url')
