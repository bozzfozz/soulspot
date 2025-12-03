"""add_image_url_to_artists

Revision ID: c7da905f261a
Revises: a0fbb3aff2a8
Create Date: 2025-11-24 18:38:50.761530

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7da905f261a"
down_revision: str | Sequence[str] | None = "a0fbb3aff2a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add image_url field to artists table.

    Hey future me - adding image_url as String(512) to store artist profile pictures from Spotify CDN.
    URLs typically look like: https://i.scdn.co/image/ab6761610000e5eb... (around 100-150 chars).
    Using 512 to be safe for future URL format changes. Field is nullable because not all artists
    have images, especially indie/underground artists. No index needed - we don't query by image_url.
    Existing artists will have NULL until next Spotify sync populates the data.
    """
    # Add image_url as String column (stores Spotify CDN URL for artist profile picture)
    op.add_column(
        "artists", sa.Column("image_url", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema - remove image_url field from artists table.

    Warning: This will DELETE all artist image URLs! Run only if you're sure you want to
    revert this migration. Image URLs can be re-fetched from Spotify on next sync, but
    this requires API calls and takes time for users with many followed artists.
    """
    op.drop_column("artists", "image_url")
