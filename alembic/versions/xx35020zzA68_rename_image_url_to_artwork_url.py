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
- Rename playlists.cover_url → artwork_url
- (Album already uses artwork_url - no change needed)

This migration is SAFE - just column renaming, no data loss.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "xx35020zzA68"
down_revision = "ww34019yyz67"
branch_labels = None
depends_on = None


def _cleanup_orphaned_tables(connection) -> None:
    """Clean up orphaned temporary tables from failed migrations.
    
    Hey future me - SQLite batch operations create temporary tables!
    If a migration fails partway through, these temp tables can be left behind.
    This causes "table already exists" errors on retry.
    
    This function drops any orphaned _alembic_tmp_* tables before running the migration.
    """
    # Get list of all tables
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    
    # Drop any orphaned temporary tables
    for table_name in tables:
        if table_name.startswith("_alembic_tmp_"):
            print(f"Cleaning up orphaned table: {table_name}")
            connection.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))
            connection.commit()


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table.
    
    Hey future me - this makes migrations idempotent!
    If the migration was already partially applied, we can detect it and skip.
    """
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Rename image_url/cover_url to artwork_url for consistency."""
    
    # Get connection for cleanup and checks
    connection = op.get_bind()
    
    # Clean up any orphaned temporary tables from previous failed migrations
    _cleanup_orphaned_tables(connection)
    
    # Rename soulspot_artists.image_url → artwork_url (if needed)
    if _column_exists(connection, "soulspot_artists", "image_url"):
        print("Renaming soulspot_artists.image_url → artwork_url")
        
        # CRITICAL: Drop ALL indexes BEFORE batch_alter_table
        # SQLite batch_alter_table(recreate="always") drops ALL indexes during table recreation
        # We must manually drop/recreate them, especially expression-based indexes
        print("Dropping all soulspot_artists indexes (will recreate after)")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name_lower"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_spotify_uri"))
        connection.commit()
        
        # For SQLite, we need to use batch mode with recreate strategy
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
        
        # CRITICAL: Recreate ALL indexes AFTER batch_alter_table
        print("Recreating all soulspot_artists indexes")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name "
            "ON soulspot_artists (name)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name_lower "
            "ON soulspot_artists (lower(name))"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_spotify_uri "
            "ON soulspot_artists (spotify_uri)"
        ))
        connection.commit()
        
    elif _column_exists(connection, "soulspot_artists", "artwork_url"):
        print("Column soulspot_artists.artwork_url already exists - skipping rename")
    else:
        # If neither exists, create artwork_url column
        print("WARNING: Neither image_url nor artwork_url found - creating artwork_url")
        op.add_column(
            "soulspot_artists",
            sa.Column("artwork_url", sa.String(512), nullable=True),
        )
    
    # Clean up again before second table (in case first batch left temps)
    _cleanup_orphaned_tables(connection)
    
    # Rename playlists.cover_url → artwork_url (if needed)
    if _column_exists(connection, "playlists", "cover_url"):
        print("Renaming playlists.cover_url → artwork_url")
        
        # CRITICAL: Drop ALL indexes BEFORE batch_alter_table
        # SQLite batch_alter_table(recreate="always") drops ALL indexes during table recreation
        print("Dropping all playlists indexes (will recreate after)")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_spotify_uri"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_playlists_is_blacklisted"))
        connection.commit()
        
        # For SQLite, we need to use batch mode with recreate strategy
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
        
        # CRITICAL: Recreate ALL indexes AFTER batch_alter_table
        print("Recreating all playlists indexes")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_name "
            "ON playlists (name)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_spotify_uri "
            "ON playlists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_is_blacklisted "
            "ON playlists (is_blacklisted)"
        ))
        connection.commit()
    elif _column_exists(connection, "playlists", "artwork_url"):
        print("Column playlists.artwork_url already exists - skipping rename")
    else:
        # If neither exists, create artwork_url column
        print("WARNING: Neither cover_url nor artwork_url found - creating artwork_url")
        op.add_column(
            "playlists",
            sa.Column("artwork_url", sa.String(512), nullable=True),
        )


def downgrade() -> None:
    """Revert artwork_url back to image_url/cover_url."""
    
    # Get connection for cleanup and checks
    connection = op.get_bind()
    
    # Clean up any orphaned temporary tables from previous failed migrations
    _cleanup_orphaned_tables(connection)
    
    # Revert soulspot_artists.artwork_url → image_url (if needed)
    if _column_exists(connection, "soulspot_artists", "artwork_url"):
        print("Reverting soulspot_artists.artwork_url → image_url")
        
        # CRITICAL: Drop ALL indexes BEFORE batch_alter_table
        print("Dropping all soulspot_artists indexes (will recreate after)")
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_name_lower"))
        connection.execute(sa.text("DROP INDEX IF EXISTS ix_soulspot_artists_spotify_uri"))
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
        
        # CRITICAL: Recreate ALL indexes AFTER batch_alter_table
        print("Recreating all soulspot_artists indexes")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name "
            "ON soulspot_artists (name)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name_lower "
            "ON soulspot_artists (lower(name))"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_spotify_uri "
            "ON soulspot_artists (spotify_uri)"
        ))
        connection.commit()
        
    elif _column_exists(connection, "soulspot_artists", "image_url"):
        print("Column soulspot_artists.image_url already exists - skipping revert")
    else:
        print("WARNING: Neither artwork_url nor image_url found in soulspot_artists")
    
    # Clean up again before second table
    _cleanup_orphaned_tables(connection)
    
    # Revert playlists.artwork_url → cover_url (if needed)
    if _column_exists(connection, "playlists", "artwork_url"):
        print("Reverting playlists.artwork_url → cover_url")
        
        # CRITICAL: Drop ALL indexes BEFORE batch_alter_table
        print("Dropping all playlists indexes (will recreate after)")
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
        
        # CRITICAL: Recreate ALL indexes AFTER batch_alter_table
        print("Recreating all playlists indexes")
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_name "
            "ON playlists (name)"
        ))
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_spotify_uri "
            "ON playlists (spotify_uri)"
        ))
        connection.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_playlists_is_blacklisted "
            "ON playlists (is_blacklisted)"
        ))
        connection.commit()
    elif _column_exists(connection, "playlists", "cover_url"):
        print("Column playlists.cover_url already exists - skipping revert")
    else:
        print("WARNING: Neither artwork_url nor cover_url found in playlists")

