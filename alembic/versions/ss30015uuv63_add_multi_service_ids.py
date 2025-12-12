"""add deezer_id and tidal_id to artists, albums, tracks

Revision ID: ss30015uuv63
Revises: rr29014ttu62
Create Date: 2025-12-12 15:00:00.000000

Hey future me - this is THE key migration for multi-service support!
Adds service-specific IDs (deezer_id, tidal_id) to Artist, Album, and Track models.

WHY: When user syncs from multiple services (Spotify + Deezer + Tidal), we need to:
1. Avoid duplicates - same artist/album/track from different services
2. Link entities across services - "This Spotify artist = That Deezer artist"
3. Query back to original service for metadata refresh

DEDUPLICATION STRATEGY:
- Tracks: ISRC is primary key (already exists), service IDs are secondary
- Artists: MusicBrainz ID is universal key, service IDs for API calls
- Albums: MusicBrainz ID is universal key, service IDs for API calls

Example: User follows "Daft Punk" on Spotify AND Deezer
- First sync (Spotify): Creates artist with spotify_uri='spotify:artist:xxx'
- Second sync (Deezer): Finds artist by name, adds deezer_id='123456'
- Result: ONE artist with both IDs, not two duplicates!
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ss30015uuv63"
down_revision: Union[str, None] = "rr29014ttu62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deezer_id and tidal_id columns to soulspot_artists, soulspot_albums, soulspot_tracks.
    
    All new columns are:
    - nullable (existing data doesn't have them)
    - unique (prevent duplicates within same service)
    - indexed (fast lookups by service ID)
    """
    # === ARTISTS ===
    with op.batch_alter_table("soulspot_artists", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deezer_id", sa.String(50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tidal_id", sa.String(50), nullable=True)
        )
        batch_op.create_index("ix_soulspot_artists_deezer_id", ["deezer_id"], unique=True)
        batch_op.create_index("ix_soulspot_artists_tidal_id", ["tidal_id"], unique=True)

    # === ALBUMS ===
    with op.batch_alter_table("soulspot_albums", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deezer_id", sa.String(50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tidal_id", sa.String(50), nullable=True)
        )
        batch_op.create_index("ix_soulspot_albums_deezer_id", ["deezer_id"], unique=True)
        batch_op.create_index("ix_soulspot_albums_tidal_id", ["tidal_id"], unique=True)

    # === TRACKS ===
    with op.batch_alter_table("soulspot_tracks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deezer_id", sa.String(50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tidal_id", sa.String(50), nullable=True)
        )
        batch_op.create_index("ix_soulspot_tracks_deezer_id", ["deezer_id"], unique=True)
        batch_op.create_index("ix_soulspot_tracks_tidal_id", ["tidal_id"], unique=True)


def downgrade() -> None:
    """Remove deezer_id and tidal_id columns and indexes."""
    # === TRACKS ===
    with op.batch_alter_table("soulspot_tracks", schema=None) as batch_op:
        batch_op.drop_index("ix_soulspot_tracks_tidal_id")
        batch_op.drop_index("ix_soulspot_tracks_deezer_id")
        batch_op.drop_column("tidal_id")
        batch_op.drop_column("deezer_id")

    # === ALBUMS ===
    with op.batch_alter_table("soulspot_albums", schema=None) as batch_op:
        batch_op.drop_index("ix_soulspot_albums_tidal_id")
        batch_op.drop_index("ix_soulspot_albums_deezer_id")
        batch_op.drop_column("tidal_id")
        batch_op.drop_column("deezer_id")

    # === ARTISTS ===
    with op.batch_alter_table("soulspot_artists", schema=None) as batch_op:
        batch_op.drop_index("ix_soulspot_artists_tidal_id")
        batch_op.drop_index("ix_soulspot_artists_deezer_id")
        batch_op.drop_column("tidal_id")
        batch_op.drop_column("deezer_id")
