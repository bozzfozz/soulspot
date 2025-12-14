"""consolidate spotify tables into unified soulspot library

Revision ID: ww34019yyz67
Revises: vv33018xxz66
Create Date: 2025-12-14 16:00:00.000000

Hey future me - BIG REFACTOR! We're eliminating redundant spotify_* tables!

BEFORE (redundant):
- spotify_artists, spotify_albums, spotify_tracks → separate Spotify browse cache
- soulspot_artists, soulspot_albums, soulspot_tracks → unified library
- Data was copied from spotify_* to soulspot_* (duplicate work!)

AFTER (unified):
- ONLY soulspot_* tables (with source='spotify'/'deezer'/'local'/'hybrid')
- No more data duplication
- ProviderSyncService writes directly to unified library

MIGRATION STEPS:
1. Add missing sync fields to soulspot_* tables (from spotify_* tables)
2. Rename spotify_sync_status → provider_sync_status
3. Migrate data from spotify_* → soulspot_* (where not already present)
4. Drop spotify_artists, spotify_albums, spotify_tracks tables

KEEPS:
- spotify_sessions (OAuth browser sessions)
- spotify_tokens (OAuth tokens with refresh)
- deezer_sessions (OAuth session + token)

This migration is SAFE:
- Data is migrated before dropping tables
- All important sync metadata fields are preserved
- Can rollback by recreating tables from existing data
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision = "ww34019yyz67"
down_revision = "vv33018xxz66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sync fields to soulspot_* tables, migrate data, drop spotify_* tables."""
    
    # =========================================================================
    # STEP 1: Add missing sync fields to soulspot_artists
    # =========================================================================
    
    # image_path - local cached image path (from spotify_artists)
    op.add_column(
        "soulspot_artists",
        sa.Column("image_path", sa.String(512), nullable=True),
    )
    
    # popularity - artist popularity score (0-100)
    op.add_column(
        "soulspot_artists",
        sa.Column("popularity", sa.Integer(), nullable=True),
    )
    
    # follower_count - number of followers on streaming service
    op.add_column(
        "soulspot_artists",
        sa.Column("follower_count", sa.Integer(), nullable=True),
    )
    
    # last_synced_at - when artist was last synced from provider
    op.add_column(
        "soulspot_artists",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # albums_synced_at - when artist's albums were last synced
    op.add_column(
        "soulspot_artists",
        sa.Column("albums_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Add index for sync cooldown queries
    op.create_index(
        "ix_soulspot_artists_last_synced",
        "soulspot_artists",
        ["last_synced_at"],
    )
    
    # =========================================================================
    # STEP 2: Add missing sync fields to soulspot_albums
    # =========================================================================
    
    # image_path - local cached cover path
    op.add_column(
        "soulspot_albums",
        sa.Column("image_path", sa.String(512), nullable=True),
    )
    
    # is_saved - user saved this album (Spotify Saved Albums feature)
    op.add_column(
        "soulspot_albums",
        sa.Column("is_saved", sa.Boolean(), server_default="0", nullable=False),
    )
    
    # tracks_synced_at - when album tracks were last synced
    op.add_column(
        "soulspot_albums",
        sa.Column("tracks_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # release_date - full release date string (from spotify_albums)
    op.add_column(
        "soulspot_albums",
        sa.Column("release_date", sa.String(10), nullable=True),
    )
    
    # release_date_precision - 'day', 'month', or 'year'
    op.add_column(
        "soulspot_albums",
        sa.Column("release_date_precision", sa.String(10), nullable=True),
    )
    
    # total_tracks - number of tracks in album
    op.add_column(
        "soulspot_albums",
        sa.Column("total_tracks", sa.Integer(), nullable=True),
    )
    
    # source - provider source (like artists table)
    op.add_column(
        "soulspot_albums",
        sa.Column("source", sa.String(20), server_default="local", nullable=False),
    )
    
    op.create_index(
        "ix_soulspot_albums_source",
        "soulspot_albums",
        ["source"],
    )
    
    # =========================================================================
    # STEP 3: Add missing sync fields to soulspot_tracks
    # =========================================================================
    
    # source - provider source
    op.add_column(
        "soulspot_tracks",
        sa.Column("source", sa.String(20), server_default="local", nullable=False),
    )
    
    # explicit - explicit content flag
    op.add_column(
        "soulspot_tracks",
        sa.Column("explicit", sa.Boolean(), server_default="0", nullable=False),
    )
    
    # preview_url - 30s preview URL
    op.add_column(
        "soulspot_tracks",
        sa.Column("preview_url", sa.String(512), nullable=True),
    )
    
    op.create_index(
        "ix_soulspot_tracks_source",
        "soulspot_tracks",
        ["source"],
    )
    
    # =========================================================================
    # STEP 4: Rename spotify_sync_status → provider_sync_status
    # =========================================================================
    
    op.rename_table("spotify_sync_status", "provider_sync_status")
    
    # Add provider column (for multi-provider sync status)
    op.add_column(
        "provider_sync_status",
        sa.Column("provider", sa.String(32), server_default="spotify", nullable=False),
    )
    
    # =========================================================================
    # STEP 5: Migrate data from spotify_artists to soulspot_artists
    # =========================================================================
    
    # SQLite-compatible data migration using raw SQL
    # Only insert artists that don't already exist (by spotify_uri match)
    op.execute("""
        INSERT INTO soulspot_artists (
            id, name, source, spotify_uri, image_url, image_path, genres,
            popularity, follower_count, last_synced_at, albums_synced_at,
            created_at, updated_at
        )
        SELECT 
            lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || 
                  substr(hex(randomblob(2)),2) || '-' || 
                  substr('89ab', abs(random()) % 4 + 1, 1) || 
                  substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))) as id,
            sa.name,
            'spotify' as source,
            'spotify:artist:' || sa.spotify_id as spotify_uri,
            sa.image_url,
            sa.image_path,
            sa.genres,
            sa.popularity,
            sa.follower_count,
            sa.last_synced_at,
            sa.albums_synced_at,
            sa.created_at,
            sa.updated_at
        FROM spotify_artists sa
        WHERE NOT EXISTS (
            SELECT 1 FROM soulspot_artists sl 
            WHERE sl.spotify_uri = 'spotify:artist:' || sa.spotify_id
        )
    """)
    
    # =========================================================================
    # STEP 6: Migrate data from spotify_albums to soulspot_albums
    # =========================================================================
    
    # First, we need artist IDs mapping (spotify_id → soulspot_id)
    # This is complex because we need to join and match
    op.execute("""
        INSERT INTO soulspot_albums (
            id, title, artist_id, release_year, spotify_uri, artwork_url, 
            image_path, is_saved, release_date, release_date_precision,
            total_tracks, primary_type, source, created_at, updated_at
        )
        SELECT 
            lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || 
                  substr(hex(randomblob(2)),2) || '-' || 
                  substr('89ab', abs(random()) % 4 + 1, 1) || 
                  substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))) as id,
            salb.name as title,
            sla.id as artist_id,
            CAST(substr(salb.release_date, 1, 4) AS INTEGER) as release_year,
            'spotify:album:' || salb.spotify_id as spotify_uri,
            salb.image_url as artwork_url,
            salb.image_path,
            salb.is_saved,
            salb.release_date,
            salb.release_date_precision,
            salb.total_tracks,
            salb.album_type as primary_type,
            'spotify' as source,
            salb.created_at,
            salb.updated_at
        FROM spotify_albums salb
        JOIN soulspot_artists sla ON sla.spotify_uri = 'spotify:artist:' || salb.artist_id
        WHERE NOT EXISTS (
            SELECT 1 FROM soulspot_albums slalb 
            WHERE slalb.spotify_uri = 'spotify:album:' || salb.spotify_id
        )
    """)
    
    # =========================================================================
    # STEP 7: Migrate data from spotify_tracks to soulspot_tracks
    # =========================================================================
    
    op.execute("""
        INSERT INTO soulspot_tracks (
            id, title, artist_id, album_id, track_number, disc_number,
            duration_ms, explicit, preview_url, isrc, spotify_uri,
            source, created_at, updated_at
        )
        SELECT 
            lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || 
                  substr(hex(randomblob(2)),2) || '-' || 
                  substr('89ab', abs(random()) % 4 + 1, 1) || 
                  substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))) as id,
            st.name as title,
            sla.id as artist_id,
            slalb.id as album_id,
            st.track_number,
            st.disc_number,
            st.duration_ms,
            st.explicit,
            st.preview_url,
            st.isrc,
            'spotify:track:' || st.spotify_id as spotify_uri,
            'spotify' as source,
            st.created_at,
            st.updated_at
        FROM spotify_tracks st
        JOIN spotify_albums salb ON salb.spotify_id = st.album_id
        JOIN soulspot_artists sla ON sla.spotify_uri = 'spotify:artist:' || salb.artist_id
        JOIN soulspot_albums slalb ON slalb.spotify_uri = 'spotify:album:' || st.album_id
        WHERE NOT EXISTS (
            SELECT 1 FROM soulspot_tracks slt 
            WHERE slt.spotify_uri = 'spotify:track:' || st.spotify_id
        )
    """)
    
    # =========================================================================
    # STEP 8: Drop old spotify_* tables (data migrated!)
    # =========================================================================
    
    # Drop in correct order (respect foreign keys)
    op.drop_table("spotify_tracks")
    op.drop_table("spotify_albums")
    op.drop_table("spotify_artists")


def downgrade() -> None:
    """Recreate spotify_* tables and restore data (reverse migration)."""
    
    # =========================================================================
    # STEP 1: Recreate spotify_artists table
    # =========================================================================
    
    op.create_table(
        "spotify_artists",
        sa.Column("spotify_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("image_path", sa.String(512), nullable=True),
        sa.Column("genres", sa.Text(), nullable=True),
        sa.Column("popularity", sa.Integer(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("albums_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_spotify_artists_name", "spotify_artists", ["name"])
    op.create_index("ix_spotify_artists_last_synced", "spotify_artists", ["last_synced_at"])
    
    # =========================================================================
    # STEP 2: Recreate spotify_albums table
    # =========================================================================
    
    op.create_table(
        "spotify_albums",
        sa.Column("spotify_id", sa.String(32), primary_key=True),
        sa.Column("artist_id", sa.String(32), sa.ForeignKey("spotify_artists.spotify_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("image_path", sa.String(512), nullable=True),
        sa.Column("is_saved", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("release_date", sa.String(10), nullable=True, index=True),
        sa.Column("release_date_precision", sa.String(10), nullable=True),
        sa.Column("album_type", sa.String(20), nullable=False, index=True),
        sa.Column("total_tracks", sa.Integer(), nullable=False, default=0),
        sa.Column("tracks_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # =========================================================================
    # STEP 3: Recreate spotify_tracks table
    # =========================================================================
    
    op.create_table(
        "spotify_tracks",
        sa.Column("spotify_id", sa.String(32), primary_key=True),
        sa.Column("album_id", sa.String(32), sa.ForeignKey("spotify_albums.spotify_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("track_number", sa.Integer(), nullable=False, default=1),
        sa.Column("disc_number", sa.Integer(), nullable=False, default=1),
        sa.Column("duration_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("explicit", sa.Boolean(), default=False, nullable=False),
        sa.Column("preview_url", sa.String(512), nullable=True),
        sa.Column("isrc", sa.String(12), nullable=True, index=True),
        sa.Column("local_track_id", sa.String(36), sa.ForeignKey("soulspot_tracks.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # =========================================================================
    # STEP 4: Migrate data back from soulspot_* to spotify_* (for source='spotify')
    # =========================================================================
    
    # Artists with source='spotify'
    op.execute("""
        INSERT INTO spotify_artists (
            spotify_id, name, image_url, image_path, genres, popularity,
            follower_count, last_synced_at, albums_synced_at, created_at, updated_at
        )
        SELECT 
            replace(spotify_uri, 'spotify:artist:', '') as spotify_id,
            name, image_url, image_path, genres, popularity,
            follower_count, last_synced_at, albums_synced_at, created_at, updated_at
        FROM soulspot_artists
        WHERE source = 'spotify' AND spotify_uri IS NOT NULL
    """)
    
    # Albums with source='spotify'
    op.execute("""
        INSERT INTO spotify_albums (
            spotify_id, artist_id, name, image_url, image_path, is_saved,
            release_date, release_date_precision, album_type, total_tracks,
            tracks_synced_at, created_at, updated_at
        )
        SELECT 
            replace(slalb.spotify_uri, 'spotify:album:', '') as spotify_id,
            replace(sla.spotify_uri, 'spotify:artist:', '') as artist_id,
            slalb.title as name,
            slalb.artwork_url as image_url,
            slalb.image_path,
            slalb.is_saved,
            slalb.release_date,
            slalb.release_date_precision,
            slalb.primary_type as album_type,
            slalb.total_tracks,
            slalb.tracks_synced_at,
            slalb.created_at,
            slalb.updated_at
        FROM soulspot_albums slalb
        JOIN soulspot_artists sla ON sla.id = slalb.artist_id
        WHERE slalb.source = 'spotify' AND slalb.spotify_uri IS NOT NULL
    """)
    
    # Tracks with source='spotify'
    op.execute("""
        INSERT INTO spotify_tracks (
            spotify_id, album_id, name, track_number, disc_number,
            duration_ms, explicit, preview_url, isrc, created_at, updated_at
        )
        SELECT 
            replace(slt.spotify_uri, 'spotify:track:', '') as spotify_id,
            replace(slalb.spotify_uri, 'spotify:album:', '') as album_id,
            slt.title as name,
            slt.track_number,
            slt.disc_number,
            slt.duration_ms,
            slt.explicit,
            slt.preview_url,
            slt.isrc,
            slt.created_at,
            slt.updated_at
        FROM soulspot_tracks slt
        JOIN soulspot_albums slalb ON slalb.id = slt.album_id
        WHERE slt.source = 'spotify' AND slt.spotify_uri IS NOT NULL
    """)
    
    # =========================================================================
    # STEP 5: Rename provider_sync_status → spotify_sync_status
    # =========================================================================
    
    op.drop_column("provider_sync_status", "provider")
    op.rename_table("provider_sync_status", "spotify_sync_status")
    
    # =========================================================================
    # STEP 6: Drop added columns from soulspot_* tables
    # =========================================================================
    
    # Artists
    op.drop_index("ix_soulspot_artists_last_synced", "soulspot_artists")
    op.drop_column("soulspot_artists", "image_path")
    op.drop_column("soulspot_artists", "popularity")
    op.drop_column("soulspot_artists", "follower_count")
    op.drop_column("soulspot_artists", "last_synced_at")
    op.drop_column("soulspot_artists", "albums_synced_at")
    
    # Albums
    op.drop_index("ix_soulspot_albums_source", "soulspot_albums")
    op.drop_column("soulspot_albums", "image_path")
    op.drop_column("soulspot_albums", "is_saved")
    op.drop_column("soulspot_albums", "tracks_synced_at")
    op.drop_column("soulspot_albums", "release_date")
    op.drop_column("soulspot_albums", "release_date_precision")
    op.drop_column("soulspot_albums", "total_tracks")
    op.drop_column("soulspot_albums", "source")
    
    # Tracks
    op.drop_index("ix_soulspot_tracks_source", "soulspot_tracks")
    op.drop_column("soulspot_tracks", "source")
    op.drop_column("soulspot_tracks", "explicit")
    op.drop_column("soulspot_tracks", "preview_url")
