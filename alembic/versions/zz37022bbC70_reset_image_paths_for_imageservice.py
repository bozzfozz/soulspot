"""reset image_path columns for ImageService migration

Revision ID: zz37022bbC70
Revises: yy36021aaB69
Create Date: 2025-12-18 12:00:00.000000

Hey future me - IMAGESERVICE MIGRATION CLEANUP!

This migration resets all image_path and cover_path values to NULL.
The reason is that ArtworkService → ImageService migration changed the
path structure:

OLD (ArtworkService): spotify/{type}s/{id}.webp
    Example: spotify/artists/abc123.webp

NEW (ImageService): {type}s/spotify/{id}.webp
    Example: artists/spotify/abc123.webp

By resetting to NULL:
1. ImageService.should_redownload() will return True (no existing path)
2. Images will be downloaded fresh to the new path structure
3. DB will be updated with new paths

This is a BREAKING CHANGE - all cached images need to be re-downloaded.
But since this is not production, that's acceptable.

AFFECTED TABLES:
- soulspot_artists: image_path → NULL
- soulspot_albums: cover_path → NULL
- playlists: cover_path → NULL
- spotify_artists: image_path → NULL
- spotify_albums: image_path → NULL

NOTE: image_url/cover_url are NOT reset - those are CDN URLs from providers.
Only local cache paths are reset.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "zz37022bbC70"
down_revision = "yy36021aaB69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Reset all image/cover path columns to NULL for fresh download."""
    
    # soulspot_artists - unified library artists
    op.execute("UPDATE soulspot_artists SET image_path = NULL WHERE image_path IS NOT NULL")
    
    # soulspot_albums - unified library albums  
    op.execute("UPDATE soulspot_albums SET cover_path = NULL WHERE cover_path IS NOT NULL")
    
    # playlists - user playlists
    op.execute("UPDATE playlists SET cover_path = NULL WHERE cover_path IS NOT NULL")
    
    # spotify_artists - Spotify browse/followed artists
    # Check if table exists first (might be renamed/consolidated)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if "spotify_artists" in tables:
        op.execute("UPDATE spotify_artists SET image_path = NULL WHERE image_path IS NOT NULL")
    
    if "spotify_albums" in tables:
        op.execute("UPDATE spotify_albums SET image_path = NULL WHERE image_path IS NOT NULL")


def downgrade() -> None:
    """Cannot restore old paths - they would be invalid anyway."""
    # No-op: Old paths pointed to old structure which no longer exists
    # Images will need to be re-downloaded regardless
    pass
