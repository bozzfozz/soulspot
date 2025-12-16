"""rename image_url and cover_url to artwork_url for consistency

Revision ID: xx35020zzA68
Revises: ww34019yyz67
Create Date: 2025-12-16 12:00:00.000000

Hey future me - CONSISTENCY REFACTOR! Standardizing all artwork field names!

BEFORE (inconsistent):
- Artist: image_url
- Album: artwork_url ✓ (already consistent!)
- Track: (no artwork field - singles need this!)
- Playlist: cover_url
- UserProfile: image_url

AFTER (all use artwork_url):
- Artist: artwork_url
- Album: artwork_url (unchanged)
- Track: artwork_url (NEW - for singles)
- Playlist: artwork_url
- UserProfile: artwork_url

WHY:
- Singles are tracks with their own artwork
- "artwork_url" is more descriptive than generic "image_url"
- Consistent naming = less confusion in code

DATABASE CHANGES:
- Rename soulspot_artists.image_url → artwork_url
- Rename soulspot_playlists.cover_url → artwork_url
- (Album already uses artwork_url - no change needed)

This migration is SAFE - just column renaming, no data loss.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "xx35020zzA68"
down_revision = "ww34019yyz67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename image_url/cover_url to artwork_url for consistency."""
    
    # Rename soulspot_artists.image_url → artwork_url
    with op.batch_alter_table("soulspot_artists") as batch_op:
        batch_op.alter_column(
            "image_url",
            new_column_name="artwork_url",
            existing_type=sa.String(512),
            existing_nullable=True,
        )
    
    # Rename soulspot_playlists.cover_url → artwork_url
    with op.batch_alter_table("soulspot_playlists") as batch_op:
        batch_op.alter_column(
            "cover_url",
            new_column_name="artwork_url",
            existing_type=sa.String(512),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Revert artwork_url back to image_url/cover_url."""
    
    # Revert soulspot_artists.artwork_url → image_url
    with op.batch_alter_table("soulspot_artists") as batch_op:
        batch_op.alter_column(
            "artwork_url",
            new_column_name="image_url",
            existing_type=sa.String(512),
            existing_nullable=True,
        )
    
    # Revert soulspot_playlists.artwork_url → cover_url
    with op.batch_alter_table("soulspot_playlists") as batch_op:
        batch_op.alter_column(
            "artwork_url",
            new_column_name="cover_url",
            existing_type=sa.String(512),
            existing_nullable=True,
        )
