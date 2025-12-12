"""add source field to artists for unified music manager view

Revision ID: qq28013sst61
Revises: pp27012rrs60
Create Date: 2025-12-11 10:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "qq28013sst61"
down_revision: Union[str, None] = "pp27012rrs60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source field to soulspot_artists table.

    Hey future me - this enables the unified Music Manager view! The source field tracks whether
    an artist comes from:
    - 'local' = Found in local library file scan (Lidarr-style folder structure)
    - 'spotify' = Followed artist synced from Spotify
    - 'hybrid' = Artist exists in BOTH local library AND Spotify followed artists

    Default is 'local' for backward compatibility with existing artists. Artists already in the
    database are assumed to be from local file scans. When Spotify followed artists are synced,
    we'll either create new artists with source='spotify' OR upgrade existing local artists to
    source='hybrid' if they match by name/spotify_uri.

    The index on source enables efficient filtering in the unified artist view:
    - Show only local artists: WHERE source IN ('local', 'hybrid')
    - Show only Spotify followed: WHERE source IN ('spotify', 'hybrid')
    - Show all artists: No filter (unified view)
    """
    # Add source column with default 'local' (nullable=False)
    op.add_column(
        "soulspot_artists",
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default="local",
        ),
    )

    # Create index on source for efficient filtering
    op.create_index(
        "ix_soulspot_artists_source",
        "soulspot_artists",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """Remove source field from soulspot_artists table.

    Hey future me - this removes the unified Music Manager feature! Artists will go back to
    being just "local library" artists with no distinction between local/Spotify/hybrid sources.
    This is safe to run - the source field doesn't affect existing functionality, it only adds
    new capabilities for displaying artist origins in the UI.
    """
    # Drop index first (can't drop column with indexes)
    op.drop_index("ix_soulspot_artists_source", table_name="soulspot_artists")

    # Drop source column
    op.drop_column("soulspot_artists", "source")
