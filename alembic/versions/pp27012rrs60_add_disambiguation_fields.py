"""Add disambiguation fields to artists and albums for Lidarr-compatible naming.

Revision ID: pp27012rrs60
Revises: oo26011qqr59
Create Date: 2025-12-02 10:00:00.000000

Hey future me - this adds disambiguation fields for Lidarr-style naming templates!

Disambiguation is used to differentiate:
- Artists: "Genesis (UK band)" vs "Genesis (US band)"
- Albums: "Bad (Deluxe Edition)" vs "Bad (Original)"

These are sourced from MusicBrainz during enrichment and used in naming templates:
- {Artist Disambiguation} - empty if not needed, e.g., "(UK band)" when needed
- {Album Disambiguation} - e.g., "(Deluxe Edition)", "(Remastered 2023)"

The disambiguation is stored as a simple string (not including parentheses).
The naming templates handle the formatting (with parentheses if non-empty).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "pp27012rrs60"
down_revision: str | None = "oo26011qqr59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add disambiguation columns to artists and albums tables."""
    # Add disambiguation to soulspot_artists
    # Hey future me - this is optional metadata from MusicBrainz!
    # Most artists don't need disambiguation (only when there are multiple with same name).
    # Example: "Genesis" has disambiguation "English rock band" to differentiate from others.
    op.add_column(
        "soulspot_artists",
        sa.Column(
            "disambiguation",
            sa.String(255),
            nullable=True,
            comment="MusicBrainz disambiguation for artists with same name",
        ),
    )

    # Add disambiguation to soulspot_albums
    # Hey future me - this is used for release editions/versions!
    # Example: "Thriller" has releases like "Thriller (25th Anniversary Edition)".
    # The disambiguation helps differentiate releases of the same album.
    op.add_column(
        "soulspot_albums",
        sa.Column(
            "disambiguation",
            sa.String(255),
            nullable=True,
            comment="MusicBrainz disambiguation for album editions/versions",
        ),
    )


def downgrade() -> None:
    """Remove disambiguation columns from artists and albums tables."""
    op.drop_column("soulspot_albums", "disambiguation")
    op.drop_column("soulspot_artists", "disambiguation")
