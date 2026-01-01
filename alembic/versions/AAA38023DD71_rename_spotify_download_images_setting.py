"""rename spotify.download_images to library.download_images

Revision ID: AAA38023DD71
Revises: aa38023ccD73
Create Date: 2025-12-18 14:00:00.000000

Hey future me - MULTI-PROVIDER SETTING KEY MIGRATION!

Problem: Setting key was 'spotify.download_images' despite SoulSpot supporting
multiple providers (Spotify + Deezer + Tidal). This was misleading and architecturally
inconsistent with the multi-provider vision.

Solution: Rename to 'library.download_images' to reflect that this setting applies
to ALL providers' image downloading (Spotify, Deezer, Tidal).

Why this is correct:
- Images from ALL providers get stored in /config/images/
- ImageService is provider-agnostic (downloads from any CDN URL)
- Path structure: {type}s/{provider}/{id}.webp (artists/spotify/..., albums/deezer/...)
- Setting should reflect scope: library-wide, not Spotify-specific

What this migration does:
1. UPDATE existing app_settings row:
   - 'spotify.download_images' → 'library.download_images'
2. Keep same category ('spotify' → 'library' for consistency)
3. Update description to mention multi-provider

Backwards compatibility:
- Old code checking 'spotify.download_images' will get None (default to True)
- New code checks 'library.download_images' (migrated value)
- AppSettingsService.should_download_images() uses new key

This is a SAFE migration:
- No data loss (same boolean value transferred)
- Default is True (images download even if key missing)
- User preference is preserved

AFFECTED CODE:
- src/soulspot/application/services/app_settings_service.py
- src/soulspot/infrastructure/lifecycle.py
- src/soulspot/api/routers/settings.py
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "AAA38023DD71"
down_revision = "aa38023ccD73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename spotify.download_images to library.download_images."""
    
    # Hey future me - this UPDATE is idempotent (safe to run multiple times)
    # If key already renamed or doesn't exist, no error!
    op.execute("""
        UPDATE app_settings
        SET 
            key = 'library.download_images',
            category = 'library',
            description = 'Download images locally from all providers (Spotify, Deezer, Tidal) for offline use'
        WHERE key = 'spotify.download_images'
    """)


def downgrade() -> None:
    """Revert library.download_images back to spotify.download_images."""
    
    # Hey - downgrade is NOT recommended because it breaks multi-provider intent!
    # But provided for migration rollback if needed (e.g., critical bug discovered)
    op.execute("""
        UPDATE app_settings
        SET 
            key = 'spotify.download_images',
            category = 'spotify',
            description = 'Download images locally for offline use'
        WHERE key = 'library.download_images'
    """)
