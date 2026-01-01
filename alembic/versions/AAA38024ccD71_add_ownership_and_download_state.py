"""add ownership_state and download_state columns

Revision ID: AAA38024ccD71
Revises: zz37022bbC70
Create Date: 2026-01-01 10:00:00.000000

Hey future me - UNIFIED LIBRARY MANAGER FOUNDATION!

This migration adds the core columns for the ownership model:

1. ownership_state (VARCHAR 20):
   - OWNED: Entity is in user's library, actively managed
   - DISCOVERED: Known entity, but not in library (browse, search results)
   - IGNORED: Explicitly ignored by user (won't be auto-added)
   
   DEFAULT: 'discovered' (safe - explicit action required to own)

2. download_state (VARCHAR 20) - TRACKS ONLY:
   - NOT_NEEDED: No download required/wanted (DEFAULT!)
   - PENDING: In download queue
   - DOWNLOADING: Currently being downloaded
   - DOWNLOADED: Successfully downloaded (local_path should be set)
   - FAILED: Download failed (can retry)
   
   DEFAULT: 'not_needed' (important! not 'pending')

3. primary_source (VARCHAR 20):
   - Tracks where the entity came from: 'local', 'spotify', 'deezer', 'tidal'
   - NULL for entities from unknown/multiple sources
   
IMPORTANT MIGRATION STRATEGY:
- Existing local library entities → ownership_state='owned', download_state='downloaded'
- Existing Spotify-synced entities → ownership_state='owned', download_state='not_needed'
- Everything else → ownership_state='discovered'

AFFECTED TABLES:
- soulspot_artists: ownership_state, primary_source
- soulspot_albums: ownership_state, primary_source  
- soulspot_tracks: ownership_state, download_state, primary_source
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "AAA38024ccD71"
down_revision = "zz37022bbC70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ownership_state, download_state, and primary_source columns."""
    
    # Import for column check
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # === ARTISTS ===
    # Check if column already exists (idempotency for retry after partial failure)
    artist_columns = [col["name"] for col in inspector.get_columns("soulspot_artists")]
    if "ownership_state" not in artist_columns:
        with op.batch_alter_table("soulspot_artists", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "ownership_state",
                    sa.String(20),
                    nullable=False,
                    server_default="discovered",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "primary_source",
                    sa.String(20),
                    nullable=True,
                )
            )
    
    # === ALBUMS ===
    album_columns = [col["name"] for col in inspector.get_columns("soulspot_albums")]
    if "ownership_state" not in album_columns:
        with op.batch_alter_table("soulspot_albums", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "ownership_state",
                    sa.String(20),
                    nullable=False,
                    server_default="discovered",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "primary_source",
                    sa.String(20),
                    nullable=True,
                )
            )
    
    # === TRACKS ===
    track_columns = [col["name"] for col in inspector.get_columns("soulspot_tracks")]
    if "ownership_state" not in track_columns:
        with op.batch_alter_table("soulspot_tracks", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "ownership_state",
                    sa.String(20),
                    nullable=False,
                    server_default="discovered",
                )
            )
            # download_state only for tracks!
            batch_op.add_column(
                sa.Column(
                    "download_state",
                    sa.String(20),
                    nullable=False,
                    server_default="not_needed",  # IMPORTANT: not 'pending'!
                )
            )
            batch_op.add_column(
                sa.Column(
                    "primary_source",
                    sa.String(20),
                    nullable=True,
                )
            )
    
    # === DATA MIGRATION ===
    # Mark existing entities based on their source
    
    # Artists with spotify_uri are from Spotify sync → owned
    op.execute("""
        UPDATE soulspot_artists 
        SET ownership_state = 'owned', primary_source = 'spotify'
        WHERE spotify_uri IS NOT NULL
    """)
    
    # Artists with deezer_id are from Deezer sync → owned
    op.execute("""
        UPDATE soulspot_artists 
        SET ownership_state = 'owned', 
            primary_source = CASE 
                WHEN primary_source IS NULL THEN 'deezer' 
                ELSE primary_source 
            END
        WHERE deezer_id IS NOT NULL AND ownership_state != 'owned'
    """)
    
    # Albums with spotify_uri are from Spotify → owned
    op.execute("""
        UPDATE soulspot_albums 
        SET ownership_state = 'owned', primary_source = 'spotify'
        WHERE spotify_uri IS NOT NULL
    """)
    
    # Albums with deezer_id are from Deezer → owned
    op.execute("""
        UPDATE soulspot_albums 
        SET ownership_state = 'owned',
            primary_source = CASE 
                WHEN primary_source IS NULL THEN 'deezer' 
                ELSE primary_source 
            END
        WHERE deezer_id IS NOT NULL AND ownership_state != 'owned'
    """)
    
    # Tracks with local_path (if column exists) → owned + downloaded
    # Check if local_path column exists before using it
    if "local_path" in track_columns:
        op.execute("""
            UPDATE soulspot_tracks 
            SET ownership_state = 'owned', 
                download_state = 'downloaded',
                primary_source = 'local'
            WHERE local_path IS NOT NULL
        """)
    
    # Tracks with spotify_uri are from Spotify → owned + not_needed
    op.execute("""
        UPDATE soulspot_tracks 
        SET ownership_state = 'owned', primary_source = 'spotify'
        WHERE spotify_uri IS NOT NULL AND ownership_state != 'owned'
    """)
    
    # Tracks with deezer_id are from Deezer → owned + not_needed
    op.execute("""
        UPDATE soulspot_tracks 
        SET ownership_state = 'owned',
            primary_source = CASE 
                WHEN primary_source IS NULL THEN 'deezer' 
                ELSE primary_source 
            END
        WHERE deezer_id IS NOT NULL AND ownership_state != 'owned'
    """)
    
    # Create indexes for efficient filtering (idempotent - check before create)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("soulspot_artists")]
    if "ix_soulspot_artists_ownership" not in existing_indexes:
        op.create_index(
            "ix_soulspot_artists_ownership",
            "soulspot_artists",
            ["ownership_state"],
            unique=False,
        )
    
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("soulspot_albums")]
    if "ix_soulspot_albums_ownership" not in existing_indexes:
        op.create_index(
            "ix_soulspot_albums_ownership",
            "soulspot_albums",
            ["ownership_state"],
            unique=False,
        )
    
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("soulspot_tracks")]
    if "ix_soulspot_tracks_ownership" not in existing_indexes:
        op.create_index(
            "ix_soulspot_tracks_ownership",
            "soulspot_tracks",
            ["ownership_state"],
            unique=False,
        )
    if "ix_soulspot_tracks_download_state" not in existing_indexes:
        op.create_index(
            "ix_soulspot_tracks_download_state",
            "soulspot_tracks",
            ["download_state"],
            unique=False,
        )


def downgrade() -> None:
    """Remove ownership_state, download_state, and primary_source columns."""
    
    # Drop indexes first
    op.drop_index("ix_soulspot_tracks_download_state", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_ownership", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_albums_ownership", table_name="soulspot_albums")
    op.drop_index("ix_soulspot_artists_ownership", table_name="soulspot_artists")
    
    # Drop columns
    with op.batch_alter_table("soulspot_tracks", schema=None) as batch_op:
        batch_op.drop_column("primary_source")
        batch_op.drop_column("download_state")
        batch_op.drop_column("ownership_state")
    
    with op.batch_alter_table("soulspot_albums", schema=None) as batch_op:
        batch_op.drop_column("primary_source")
        batch_op.drop_column("ownership_state")
    
    with op.batch_alter_table("soulspot_artists", schema=None) as batch_op:
        batch_op.drop_column("primary_source")
        batch_op.drop_column("ownership_state")
