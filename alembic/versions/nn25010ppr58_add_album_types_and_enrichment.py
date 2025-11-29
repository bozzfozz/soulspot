"""Add album types (Lidarr-style) and enrichment candidates table.

Revision ID: nn25010ppr58
Revises: ll25009ooq57
Create Date: 2025-11-29 10:00:00.000000

Hey future me - this is a BIG migration with two parts:

PART 1: Dual Album Type System (like Lidarr)
- primary_type: 'album', 'ep', 'single', 'broadcast', 'other' (default='album')
- secondary_types: JSON array like ['compilation', 'soundtrack', 'live', 'remix', ...]
- album_artist: The album-level artist (can differ from track artists!)
  For compilations, this is typically "Various Artists"

Why dual types? A live album can also be a compilation! MusicBrainz and Spotify both
use this model. primary_type is the main category, secondary_types are modifiers.

PART 2: Enrichment Candidates Table
For Spotify enrichment, when we find multiple matches for an artist/album, we store
all candidates here and let the user pick the right one. This avoids auto-matching
"The Beatles" to some random tribute band.

PART 3: Data Migration
Finds existing albums where artist.name contains "Various Artists" (or "VA", "V.A.")
and marks them as compilations. This preserves existing data!
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision = "nn25010ppr58"
down_revision = "ll25009ooq57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add album types, enrichment candidates, and migrate Various Artists."""
    
    # PART 1: Add album type columns to soulspot_albums
    # Hey - using batch_alter_table for SQLite compatibility!
    with op.batch_alter_table("soulspot_albums") as batch_op:
        # album_artist: The album-level artist (e.g., "Various Artists" for compilations)
        # This can differ from the track-level artist_id relationship
        batch_op.add_column(
            sa.Column("album_artist", sa.String(255), nullable=True)
        )
        
        # primary_type: Main album category - default is 'album'
        # Values: 'album', 'ep', 'single', 'broadcast', 'other'
        batch_op.add_column(
            sa.Column(
                "primary_type",
                sa.String(20),
                nullable=False,
                server_default="album"
            )
        )
        
        # secondary_types: JSON array of modifiers
        # Values: ['compilation', 'soundtrack', 'live', 'remix', 'dj-mix', 'mixtape', 'demo', 'spokenword']
        # An album can have MULTIPLE secondary types (e.g., live + compilation)
        batch_op.add_column(
            sa.Column(
                "secondary_types",
                sa.JSON(),
                nullable=False,
                server_default="[]"
            )
        )
        
        # Add index on primary_type for filtering
        batch_op.create_index("ix_albums_primary_type", ["primary_type"])
    
    # PART 2: Create enrichment_candidates table
    # Stores potential Spotify matches for local library items when there's ambiguity
    op.create_table(
        "enrichment_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "entity_type",
            sa.String(20),
            nullable=False,
            comment="'artist' or 'album'"
        ),
        sa.Column(
            "entity_id",
            sa.String(36),
            nullable=False,
            comment="FK to soulspot_artists or soulspot_albums"
        ),
        sa.Column(
            "spotify_uri",
            sa.String(255),
            nullable=False,
            comment="Spotify URI of this candidate"
        ),
        sa.Column(
            "spotify_name",
            sa.String(255),
            nullable=False,
            comment="Name from Spotify (for display)"
        ),
        sa.Column(
            "spotify_image_url",
            sa.String(512),
            nullable=True,
            comment="Image URL from Spotify (for preview)"
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            default=0.0,
            comment="Match confidence 0.0-1.0 (higher = better match)"
        ),
        sa.Column(
            "is_selected",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="True if user selected this candidate"
        ),
        sa.Column(
            "is_rejected",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="True if user explicitly rejected this candidate"
        ),
        sa.Column(
            "extra_info",
            sa.JSON(),
            nullable=True,
            comment="Additional info like genres, follower count, etc."
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        
        # Indexes for fast lookups
        sa.Index("ix_enrichment_entity", "entity_type", "entity_id"),
        sa.Index("ix_enrichment_spotify_uri", "spotify_uri"),
        sa.Index("ix_enrichment_confidence", "confidence_score"),
    )
    
    # PART 3: Data Migration - Mark existing "Various Artists" albums as compilations
    # This is a data migration, so we use raw SQL for performance
    # Hey - this finds albums whose artist name looks like "Various Artists" and sets
    # secondary_types = '["compilation"]' for them. Case-insensitive matching!
    
    connection = op.get_bind()
    
    # Find artist IDs that look like "Various Artists"
    # Using LOWER() for case-insensitive matching
    result = connection.execute(
        sa.text("""
            SELECT id, name FROM soulspot_artists 
            WHERE LOWER(name) LIKE '%various artist%'
               OR LOWER(name) = 'va'
               OR LOWER(name) = 'v.a.'
               OR LOWER(name) = 'v. a.'
               OR LOWER(name) LIKE '%various%artist%'
        """)
    )
    various_artist_ids = [row[0] for row in result.fetchall()]
    
    if various_artist_ids:
        # Update albums to be compilations and set album_artist
        placeholders = ",".join(["?" for _ in various_artist_ids])
        connection.execute(
            sa.text(f"""
                UPDATE soulspot_albums 
                SET secondary_types = '["compilation"]',
                    album_artist = 'Various Artists'
                WHERE artist_id IN ({placeholders})
            """),
            various_artist_ids
        )
        
        print(f"Migrated {len(various_artist_ids)} Various Artists albums to compilation type")


def downgrade() -> None:
    """Remove album types and enrichment candidates."""
    
    # Drop enrichment_candidates table
    op.drop_table("enrichment_candidates")
    
    # Remove album type columns
    with op.batch_alter_table("soulspot_albums") as batch_op:
        batch_op.drop_index("ix_albums_primary_type")
        batch_op.drop_column("secondary_types")
        batch_op.drop_column("primary_type")
        batch_op.drop_column("album_artist")
