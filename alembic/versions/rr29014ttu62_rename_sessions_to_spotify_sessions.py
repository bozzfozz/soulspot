"""rename sessions to spotify_sessions for service-agnostic architecture

Revision ID: rr29014ttu62
Revises: qq28013sst61
Create Date: 2025-12-12 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "rr29014ttu62"
down_revision: Union[str, None] = "qq28013sst61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename sessions table and indexes to spotify_sessions.

    Hey future me - this enables multi-service OAuth support! Previously SessionModel was
    Spotify-specific but named generically. When we add Tidal/Deezer, each service needs
    its own session table:
    - spotify_sessions (this table, renamed from 'sessions')
    - tidal_sessions (future)
    - deezer_sessions (future)

    This migration:
    1. Renames table: sessions → spotify_sessions
    2. Renames index: ix_sessions_last_accessed → ix_spotify_sessions_last_accessed
    3. Renames index: ix_sessions_token_expires → ix_spotify_sessions_token_expires

    Data is preserved - only metadata changes. All existing Spotify OAuth sessions remain valid.
    No application downtime needed (session data is temporary anyway - users can re-auth).
    """
    # Rename table
    op.rename_table("sessions", "spotify_sessions")

    # Rename indexes (SQLite requires drop + recreate)
    with op.batch_alter_table("spotify_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_sessions_last_accessed")
        batch_op.drop_index("ix_sessions_token_expires")
        batch_op.create_index(
            "ix_spotify_sessions_last_accessed", ["last_accessed_at"], unique=False
        )
        batch_op.create_index(
            "ix_spotify_sessions_token_expires", ["token_expires_at"], unique=False
        )


def downgrade() -> None:
    """Rollback: spotify_sessions → sessions.

    If you need to rollback (e.g., deploy failed, compatibility issue), this will:
    1. Rename table: spotify_sessions → sessions
    2. Recreate original indexes with old names

    All session data is preserved. Users may need to re-authenticate if sessions expired
    during migration window (acceptable since sessions are temporary OAuth state).
    """
    # Rename indexes back
    with op.batch_alter_table("spotify_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_spotify_sessions_last_accessed")
        batch_op.drop_index("ix_spotify_sessions_token_expires")
        batch_op.create_index("ix_sessions_last_accessed", ["last_accessed_at"], unique=False)
        batch_op.create_index("ix_sessions_token_expires", ["token_expires_at"], unique=False)

    # Rename table back
    op.rename_table("spotify_sessions", "sessions")
