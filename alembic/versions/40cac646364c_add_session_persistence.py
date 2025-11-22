"""add_session_persistence

Revision ID: 40cac646364c
Revises: 0372f0c937d1
Create Date: 2025-11-22 20:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '40cac646364c'
down_revision: str | Sequence[str] | None = '0372f0c937d1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hey future me, this migration adds database-backed session persistence to fix the
# "re-authenticate after Docker restart" bug. The sessions table stores OAuth tokens
# (access_token, refresh_token) and session metadata. When the container restarts,
# sessions survive because they're in SQLite (mounted on /config volume) instead of
# in-memory dict. The indexes on last_accessed_at and token_expires_at optimize the
# cleanup query that runs periodically to delete expired sessions. If you roll back
# this migration, users will lose all active sessions - warn them to re-authenticate!
def upgrade() -> None:
    """Upgrade schema - Add sessions table for OAuth token persistence."""
    op.create_table(
        'sessions',
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('oauth_state', sa.String(length=64), nullable=True),
        sa.Column('code_verifier', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('session_id')
    )

    # Create indexes for efficient cleanup queries
    op.create_index('ix_sessions_last_accessed', 'sessions', ['last_accessed_at'])
    op.create_index('ix_sessions_token_expires', 'sessions', ['token_expires_at'])


# Yo, rollback deletes the sessions table. This is DESTRUCTIVE - all active sessions
# are lost and users have to re-authenticate! Make sure users know this before running
# downgrade. The "if_exists" check prevents errors if table was already dropped manually.
def downgrade() -> None:
    """Downgrade schema - Remove sessions table."""
    op.drop_index('ix_sessions_token_expires', table_name='sessions', if_exists=True)
    op.drop_index('ix_sessions_last_accessed', table_name='sessions', if_exists=True)
    op.drop_table('sessions')
