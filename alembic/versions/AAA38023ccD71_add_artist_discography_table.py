"""add artist_discography table for complete discography tracking

Revision ID: AAA38023ccD71
Revises: zz37022bbC70
Create Date: 2025-12-19 10:00:00.000000

Hey future me - DISCOGRAPHY DISCOVERY TABLE!

This table stores the COMPLETE discography of artists as discovered from
external providers (Deezer, Spotify, MusicBrainz). This is separate from
soulspot_albums which only contains albums the user OWNS (local or saved).

PURPOSE:
- LibraryDiscoveryWorker fetches all albums for watched artists
- UI can show "Missing Albums" by comparing discography vs owned
- No auto-download - user decides what to get

KEY DESIGN DECISIONS:
1. Composite unique constraint on (artist_id, title, album_type) to prevent dupes
2. is_owned is a COMPUTED field (set by comparing with soulspot_albums)
3. Multiple provider IDs can coexist (album found on both Deezer and Spotify)
4. release_date stored as string for flexibility (YYYY, YYYY-MM, YYYY-MM-DD)

WORKFLOW:
1. LibraryDiscoveryWorker calls DeezerPlugin.get_artist_albums()
2. Results stored here with source="deezer"
3. UI queries JOIN with soulspot_albums to show what's missing
4. User clicks "Download" → creates Download entry

NOTE: This is NOT for user's "saved" albums - that's still soulspot_albums.is_saved!
This is the artist's COMPLETE works as reported by streaming services.
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = "AAA38023ccD71"
down_revision = "zz37022bbC70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create artist_discography table (idempotent - skips if exists)."""
    # Hey future me - IDEMPOTENT CHECK!
    # Check if table already exists (handles retry/failed migration scenarios)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if "artist_discography" in inspector.get_table_names():
        # Table already exists - skip creation
        # This handles cases where migration was partially run before
        import logging
        logging.info("Table artist_discography already exists - skipping creation")
        return
    
    op.create_table(
        "artist_discography",
        # Primary key
        sa.Column("id", sa.String(36), primary_key=True),
        
        # Foreign key to artist
        sa.Column(
            "artist_id",
            sa.String(36),
            sa.ForeignKey("soulspot_artists.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        
        # Album identification
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("album_type", sa.String(20), nullable=False, server_default="album"),
        # album_type: "album", "single", "ep", "compilation", "live", "remix"
        
        # Provider IDs (can have multiple)
        sa.Column("deezer_id", sa.String(50), nullable=True, index=True),
        sa.Column("spotify_uri", sa.String(255), nullable=True, index=True),
        sa.Column("musicbrainz_id", sa.String(36), nullable=True, index=True),
        sa.Column("tidal_id", sa.String(50), nullable=True, index=True),
        
        # Album metadata
        sa.Column("release_date", sa.String(10), nullable=True),  # YYYY-MM-DD or YYYY-MM or YYYY
        sa.Column("release_date_precision", sa.String(10), nullable=True),  # day, month, year
        sa.Column("total_tracks", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.String(512), nullable=True),  # CDN URL for display
        
        # Discovery metadata
        sa.Column("source", sa.String(20), nullable=False, server_default="deezer"),
        # source: which provider discovered this ("deezer", "spotify", "musicbrainz")
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        # last_seen_at: updated each time we re-fetch and album still exists
        
        # Computed/cached field (updated by background job)
        sa.Column("is_owned", sa.Boolean(), nullable=False, server_default="0"),
        # is_owned: TRUE if matching album exists in soulspot_albums
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        
        # Hey future me - SQLITE UNIQUE CONSTRAINT!
        # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we must
        # define the constraint inline with create_table using UniqueConstraint
        sa.UniqueConstraint(
            "artist_id", "title", "album_type",
            name="uq_discography_artist_title_type"
        ),
    )
    
    # Index for missing albums query (is_owned = FALSE)
    op.create_index(
        "ix_discography_missing",
        "artist_discography",
        ["artist_id", "is_owned"],
    )
    
    # Index for provider lookups
    op.create_index(
        "ix_discography_deezer",
        "artist_discography",
        ["deezer_id"],
        unique=False,  # Multiple albums can have same deezer_id? No, but index doesn't need unique
    )


def downgrade() -> None:
    """Drop artist_discography table (idempotent - skips if not exists)."""
    # Hey future me - IDEMPOTENT CHECK!
    # Check if table exists before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if "artist_discography" not in inspector.get_table_names():
        # Table doesn't exist - nothing to drop
        import logging
        logging.info("Table artist_discography doesn't exist - skipping drop")
        return
    
    # Drop in reverse order of creation
    op.drop_index("ix_discography_deezer", table_name="artist_discography")
    op.drop_index("ix_discography_missing", table_name="artist_discography")
    # Unique constraint is dropped automatically with table in SQLite
    op.drop_table("artist_discography")
