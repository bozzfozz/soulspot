"""add spotify and slskd credentials to app_settings

Revision ID: uu32017wwy65
Revises: tt31016vvw64
Create Date: 2025-12-15 11:00:00.000000

Hey future me - this migration moves Spotify and slskd credentials to DB!

IMPORTANT: This is a BACKWARD COMPATIBLE change. The app will:
1. First check app_settings (DB) for credentials
2. Fall back to environment variables if DB is empty
3. Settings UI saves to DB, which becomes the primary source

This allows gradual migration without breaking existing setups.
Users with .env files will continue to work until they configure via Settings UI.

Credentials stored in app_settings:
- spotify.client_id
- spotify.client_secret  
- spotify.redirect_uri
- slskd.url
- slskd.api_key
- slskd.username
- slskd.password
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "uu32017wwy65"
down_revision: Union[str, None] = "tt31016vvw64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Spotify and slskd credentials to app_settings table."""
    # Spotify credentials
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'spotify.client_id', '', 'string', 'spotify', 'Spotify OAuth Client ID from developer.spotify.com'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'spotify.client_id');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'spotify.client_secret', '', 'string', 'spotify', 'Spotify OAuth Client Secret'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'spotify.client_secret');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'spotify.redirect_uri', 'http://localhost:8000/api/auth/callback', 'string', 'spotify', 'Spotify OAuth redirect URI (must match Spotify App settings)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'spotify.redirect_uri');
        """
    )
    
    # slskd credentials
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'slskd.url', 'http://localhost:5030', 'string', 'slskd', 'slskd service URL'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'slskd.url');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'slskd.api_key', '', 'string', 'slskd', 'slskd API key (preferred authentication)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'slskd.api_key');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'slskd.username', '', 'string', 'slskd', 'slskd username (fallback if no API key)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'slskd.username');
        """
    )
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'slskd.password', '', 'string', 'slskd', 'slskd password (fallback if no API key)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'slskd.password');
        """
    )


def downgrade() -> None:
    """Remove Spotify and slskd credentials from app_settings table."""
    op.execute(
        """
        DELETE FROM app_settings WHERE key IN (
            'spotify.client_id',
            'spotify.client_secret',
            'spotify.redirect_uri',
            'slskd.url',
            'slskd.api_key',
            'slskd.username',
            'slskd.password'
        );
        """
    )
