"""rename artwork columns to imageref-consistent naming

Revision ID: yy36021aaB69
Revises: xx35020zzA68
Create Date: 2025-12-28 12:00:00.000000

Hey future me - IMAGEREF CONSISTENCY REFACTOR!

This migration aligns DB column names with the new ImageRef value object pattern.
The Python code now uses:
- Artist.image.url / Artist.image.path
- Album.cover.url / Album.cover.path
- Playlist.cover.url / Playlist.cover.path

BEFORE (mixed naming):
- soulspot_artists: artwork_url, image_path
- soulspot_albums: artwork_url, artwork_path, image_path (redundant!)
- playlists: artwork_url, cover_path

AFTER (imageref-consistent):
- soulspot_artists: image_url, image_path (matches Artist.image.*)
- soulspot_albums: cover_url, cover_path (matches Album.cover.*)
- playlists: cover_url, cover_path (matches Playlist.cover.*)

CHANGES:
1. soulspot_artists.artwork_url → image_url
2. soulspot_albums.artwork_url → cover_url
3. soulspot_albums.artwork_path → cover_path
4. soulspot_albums.image_path → DROP (was redundant to artwork_path)
5. playlists.artwork_url → cover_url

WHY:
- ImageRef pattern uses semantic names (image for artists, cover for albums/playlists)
- Eliminates redundant columns (image_path vs artwork_path)
- Python-side ImageRef already uses these names, now DB matches

This migration is SAFE - column renaming with data preservation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "yy36021aaB69"
down_revision = "xx35020zzA68"
branch_labels = None
depends_on = None


def _cleanup_orphaned_tables(connection) -> None:
    """Clean up orphaned temporary tables from failed migrations.
    
    Hey future me - SQLite batch operations create temporary tables!
    If a migration fails partway through, these temp tables can be left behind.
    This causes "table already exists" errors on retry.
    """
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    
    for table_name in tables:
        if table_name.startswith("_alembic_tmp_"):
            print(f"Cleaning up orphaned table: {table_name}")
            connection.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))
            connection.commit()


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Rename artwork columns to imageref-consistent naming."""
    
    connection = op.get_bind()
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 1. ARTISTS: artwork_url → image_url
    # =========================================================================
    if _column_exists(connection, "soulspot_artists", "artwork_url"):
        print("Renaming soulspot_artists.artwork_url → image_url")
        
        # Drop indexes before batch_alter_table
        print("Dropping soulspot_artists indexes...")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name_lower"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_last_synced"))
        connection.commit()
        
        with op.batch_alter_table(
            "soulspot_artists",
            schema=None,
            recreate="always"
        ) as batch_op:
            batch_op.alter_column(
                "artwork_url",
                new_column_name="image_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
        
        # Recreate indexes
        print("Recreating soulspot_artists indexes...")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name ON soulspot_artists (name)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name_lower ON soulspot_artists (lower(name))"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_spotify_uri ON soulspot_artists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_last_synced ON soulspot_artists (last_synced_at)"
        ))
        connection.commit()
    else:
        print("Column soulspot_artists.artwork_url not found - already renamed or missing")
    
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 2. ALBUMS: artwork_url → cover_url, artwork_path → cover_path, DROP image_path
    # =========================================================================
    if _column_exists(connection, "soulspot_albums", "artwork_url"):
        print("Renaming soulspot_albums columns: artwork_url → cover_url, artwork_path → cover_path")
        print("Also dropping redundant image_path column")
        
        # Drop indexes before batch_alter_table
        print("Dropping soulspot_albums indexes...")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_title"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_release_year"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_source"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_primary_type"))
        connection.commit()
        
        with op.batch_alter_table(
            "soulspot_albums",
            schema=None,
            recreate="always"
        ) as batch_op:
            # Rename artwork_url → cover_url
            batch_op.alter_column(
                "artwork_url",
                new_column_name="cover_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
            # Rename artwork_path → cover_path
            if _column_exists(connection, "soulspot_albums", "artwork_path"):
                batch_op.alter_column(
                    "artwork_path",
                    new_column_name="cover_path",
                    existing_type=sa.String(512),
                    existing_nullable=True,
                )
            # Drop redundant image_path
            if _column_exists(connection, "soulspot_albums", "image_path"):
                batch_op.drop_column("image_path")
        
        # Recreate indexes
        print("Recreating soulspot_albums indexes...")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_title ON soulspot_albums (title)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_albums_spotify_uri ON soulspot_albums (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_release_year ON soulspot_albums (release_year)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_source ON soulspot_albums (source)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_primary_type ON soulspot_albums (primary_type)"
        ))
        connection.commit()
    else:
        print("Column soulspot_albums.artwork_url not found - already renamed or missing")
    
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 3. PLAYLISTS: artwork_url → cover_url
    # =========================================================================
    if _column_exists(connection, "playlists", "artwork_url"):
        print("Renaming playlists.artwork_url → cover_url")
        
        # Drop indexes before batch_alter_table
        print("Dropping playlists indexes...")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_is_blacklisted"))
        connection.commit()
        
        with op.batch_alter_table(
            "playlists",
            schema=None,
            recreate="always"
        ) as batch_op:
            batch_op.alter_column(
                "artwork_url",
                new_column_name="cover_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
        
        # Recreate indexes
        print("Recreating playlists indexes...")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_name ON playlists (name)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_spotify_uri ON playlists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_is_blacklisted ON playlists (is_blacklisted)"
        ))
        connection.commit()
    else:
        print("Column playlists.artwork_url not found - already renamed or missing")
    
    print("✅ ImageRef naming migration complete!")


def downgrade() -> None:
    """Revert to previous artwork_url naming."""
    
    connection = op.get_bind()
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 1. ARTISTS: image_url → artwork_url
    # =========================================================================
    if _column_exists(connection, "soulspot_artists", "image_url"):
        print("Reverting soulspot_artists.image_url → artwork_url")
        
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name_lower"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_last_synced"))
        connection.commit()
        
        with op.batch_alter_table(
            "soulspot_artists",
            schema=None,
            recreate="always"
        ) as batch_op:
            batch_op.alter_column(
                "image_url",
                new_column_name="artwork_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
        
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name ON soulspot_artists (name)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name_lower ON soulspot_artists (lower(name))"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_spotify_uri ON soulspot_artists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_last_synced ON soulspot_artists (last_synced_at)"
        ))
        connection.commit()
    
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 2. ALBUMS: cover_url → artwork_url, cover_path → artwork_path, ADD image_path
    # =========================================================================
    if _column_exists(connection, "soulspot_albums", "cover_url"):
        print("Reverting soulspot_albums columns: cover_url → artwork_url, cover_path → artwork_path")
        print("Also adding back image_path column")
        
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_title"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_release_year"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_source"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_albums_primary_type"))
        connection.commit()
        
        with op.batch_alter_table(
            "soulspot_albums",
            schema=None,
            recreate="always"
        ) as batch_op:
            batch_op.alter_column(
                "cover_url",
                new_column_name="artwork_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
            if _column_exists(connection, "soulspot_albums", "cover_path"):
                batch_op.alter_column(
                    "cover_path",
                    new_column_name="artwork_path",
                    existing_type=sa.String(512),
                    existing_nullable=True,
                )
            # Add back image_path (was redundant but existed)
            batch_op.add_column(sa.Column("image_path", sa.String(512), nullable=True))
        
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_title ON soulspot_albums (title)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_albums_spotify_uri ON soulspot_albums (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_release_year ON soulspot_albums (release_year)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_source ON soulspot_albums (source)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_primary_type ON soulspot_albums (primary_type)"
        ))
        connection.commit()
    
    _cleanup_orphaned_tables(connection)
    
    # =========================================================================
    # 3. PLAYLISTS: cover_url → artwork_url
    # =========================================================================
    if _column_exists(connection, "playlists", "cover_url"):
        print("Reverting playlists.cover_url → artwork_url")
        
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_is_blacklisted"))
        connection.commit()
        
        with op.batch_alter_table(
            "playlists",
            schema=None,
            recreate="always"
        ) as batch_op:
            batch_op.alter_column(
                "cover_url",
                new_column_name="artwork_url",
                existing_type=sa.String(512),
                existing_nullable=True,
            )
        
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_name ON playlists (name)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_spotify_uri ON playlists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_is_blacklisted ON playlists (is_blacklisted)"
        ))
        connection.commit()
    
    print("✅ ImageRef naming revert complete!")
