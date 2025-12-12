"""add deezer_sessions table for OAuth

Revision ID: tt31016vvw64
Revises: ss30015uuv63
Create Date: 2025-12-15 10:00:00.000000

Hey future me - this migration adds Deezer OAuth session storage!

Unlike Spotify, Deezer OAuth is SIMPLER:
- No PKCE (no code_verifier needed)
- No refresh_token (access_token is long-lived, typically months)
- Different OAuth flow (connect.deezer.com vs accounts.spotify.com)

The deezer_sessions table mirrors spotify_sessions but with Deezer-specific fields:
- session_id: Links to browser session (same cookie as Spotify)
- access_token: Long-lived OAuth token (no expiry tracking needed)
- deezer_user_id: Deezer user ID for identity
- deezer_username: Display name for UI
- oauth_state: CSRF protection during OAuth flow

Also adds app_settings entries for Deezer OAuth credentials (app_id, secret, redirect_uri).
These are stored in DB instead of .env, so users can configure via Settings UI.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "tt31016vvw64"
down_revision: Union[str, None] = "ss30015uuv63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create deezer_sessions table and add Deezer settings to app_settings."""
    # Create deezer_sessions table
    op.create_table(
        "deezer_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("deezer_user_id", sa.String(50), nullable=True),
        sa.Column("deezer_username", sa.String(100), nullable=True),
        sa.Column("oauth_state", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Index for session cleanup queries
    op.create_index(
        "ix_deezer_sessions_last_accessed",
        "deezer_sessions",
        ["last_accessed_at"],
    )

    # Add Deezer OAuth settings to app_settings table
    # These are stored in DB so users can configure via Settings UI
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'deezer.app_id', '', 'string', 'deezer', 'Deezer OAuth App ID from developers.deezer.com'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'deezer.app_id');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'deezer.secret', '', 'string', 'deezer', 'Deezer OAuth Secret Key'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'deezer.secret');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'deezer.redirect_uri', 'http://localhost:8000/api/auth/deezer/callback', 'string', 'deezer', 'Deezer OAuth redirect URI (must match Deezer App settings)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'deezer.redirect_uri');
        """
    )


def downgrade() -> None:
    """Remove deezer_sessions table and Deezer settings from app_settings."""
    # Remove Deezer settings from app_settings
    op.execute(
        """
        DELETE FROM app_settings WHERE key IN (
            'deezer.app_id',
            'deezer.secret',
            'deezer.redirect_uri'
        );
        """
    )

    # Drop deezer_sessions table
    op.drop_index("ix_deezer_sessions_last_accessed", table_name="deezer_sessions")
    op.drop_table("deezer_sessions")
