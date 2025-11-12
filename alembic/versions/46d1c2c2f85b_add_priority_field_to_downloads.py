"""add_priority_field_to_downloads

Revision ID: 46d1c2c2f85b
Revises: 259d78cbdfef
Create Date: 2025-11-12 17:05:33.059354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46d1c2c2f85b'
down_revision: Union[str, Sequence[str], None] = '259d78cbdfef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add priority column to downloads table
    op.add_column('downloads', sa.Column('priority', sa.Integer(), nullable=False, server_default='0'))
    
    # Create index on priority and created_at for efficient priority-based queries
    op.create_index('ix_downloads_priority_created', 'downloads', ['priority', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index first
    op.drop_index('ix_downloads_priority_created', table_name='downloads')
    
    # Remove priority column
    op.drop_column('downloads', 'priority')
