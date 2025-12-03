"""add_spotify_tokens_table

Revision ID: ii22005llm53
Revises: hh21004kkl52
Create Date: 2025-11-27 14:00:00.000000

Hey future me - this table stores Spotify OAuth tokens for BACKGROUND WORKERS!
The key difference from sessions table: sessions are for user requests (cookie-based),
tokens table is for automated background jobs (watchlist checks, discography sync, etc.)
that need Spotify API access even when no user is logged in.

Single-user architecture: We store ONE active token. When user authenticates, we UPSERT
to keep exactly one row. Background workers call get_active_token() and get this row.

The is_valid flag is CRITICAL: When Spotify refresh fails (user revoked access, token
corrupted, etc.), we set is_valid=False. This triggers UI warning banner telling user
to re-authenticate. Workers check this flag and skip work if False (no crash/retry loop).

The token_refresh_worker runs every 5 min and proactively refreshes tokens expiring in <10 min.
This prevents 401 errors during long-running background jobs mid-operation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ii22005llm53"
down_revision: str | Sequence[str] | None = "hh21004kkl52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create spotify_tokens table for background worker OAuth token storage."""
    op.create_table(
        "spotify_tokens",
        # Single-user: just use 'default' as id, or could be spotify_user_id for future multi-user
        sa.Column("id", sa.String(length=64), nullable=False),
        # OAuth tokens (NOT encrypted - per user request for simplicity)
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        # Scopes the token was granted (for validation)
        sa.Column(
            "scopes", sa.Text(), nullable=True
        ),  # Space-separated: "user-follow-read playlist-read-private"
        # Validity flag - False when refresh fails (user revoked access)
        sa.Column(
            "is_valid", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        # Error tracking for UI display
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        # Metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index for finding tokens expiring soon (background refresh worker)
    op.create_index("ix_spotify_tokens_expires", "spotify_tokens", ["token_expires_at"])
    # Index for finding valid tokens (background workers)
    op.create_index("ix_spotify_tokens_valid", "spotify_tokens", ["is_valid"])


def downgrade() -> None:
    """Drop spotify_tokens table."""
    op.drop_index("ix_spotify_tokens_valid", table_name="spotify_tokens")
    op.drop_index("ix_spotify_tokens_expires", table_name="spotify_tokens")
    op.drop_table("spotify_tokens")
