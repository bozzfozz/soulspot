"""Rename local library tables to soulspot_ prefix.

Revision ID: ll25009ooq57
Revises: kk24007nno55
Create Date: 2025-11-28

Hey future me - this migration renames the core local library tables to have
a clear 'soulspot_' prefix, distinguishing them from 'spotify_' tables:

- artists → soulspot_artists
- albums → soulspot_albums
- tracks → soulspot_tracks

This makes the architecture crystal clear:
- spotify_* = data synced FROM Spotify API
- soulspot_* = LOCAL library (files in /mnt/music)

All foreign keys are automatically updated by SQLite's RENAME TABLE.
Indexes are recreated with new names to match the new table names.

IMPORTANT: This migration uses DROP INDEX IF EXISTS / CREATE INDEX IF NOT EXISTS
patterns via raw SQL to handle edge cases like:
- Index might not exist (e.g., ix_artists_name_lower was never created)
- Migration might be re-run after partial completion
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "ll25009ooq57"
down_revision = "kk24007nno55"
branch_labels = None
depends_on = None


def _drop_index_if_exists(index_name: str) -> None:
    """Drop an index if it exists (SQLite compatible).

    Note: DDL statements cannot use parameterized queries for object names.
    The index_name must be part of the SQL string itself. All callers pass
    hardcoded constant strings, not user input, so SQL injection is not possible.
    """
    # Validate index name contains only safe characters (alphanumeric + underscore)
    if not index_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid index name: {index_name}")
    op.execute(text(f"DROP INDEX IF EXISTS {index_name}"))


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in SQLite."""
    conn = op.get_bind()
    result = conn.execute(
        text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
        ).bindparams(name=table_name)
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Rename local library tables from generic names to soulspot_ prefix."""
    # Hey future me - SQLite RENAME TABLE automatically updates FK references!
    # But we need to handle the case where tables might already be renamed
    # (e.g., migration interrupted and re-run).

    # Only rename if old table exists (handles idempotent re-runs)
    if _table_exists("artists"):
        op.rename_table("artists", "soulspot_artists")
    if _table_exists("albums"):
        op.rename_table("albums", "soulspot_albums")
    if _table_exists("tracks"):
        op.rename_table("tracks", "soulspot_tracks")

    # Drop old indexes (use IF EXISTS to handle missing indexes safely)
    # Artists indexes from initial migration (259d78cbdfef)
    _drop_index_if_exists("ix_artists_name")
    _drop_index_if_exists("ix_artists_spotify_uri")
    _drop_index_if_exists("ix_artists_musicbrainz_id")
    # Note: ix_artists_name_lower was defined in model but NEVER created in migrations
    _drop_index_if_exists("ix_artists_name_lower")
    # Performance indexes from cc17880fff37
    _drop_index_if_exists("ix_artists_updated_at")

    # Albums indexes from initial migration
    _drop_index_if_exists("ix_albums_title")
    _drop_index_if_exists("ix_albums_release_year")
    _drop_index_if_exists("ix_albums_spotify_uri")
    _drop_index_if_exists("ix_albums_musicbrainz_id")
    _drop_index_if_exists("ix_albums_title_artist")
    # Performance indexes from cc17880fff37
    _drop_index_if_exists("ix_albums_artist_id")
    _drop_index_if_exists("ix_albums_updated_at")

    # Tracks indexes from initial migration
    _drop_index_if_exists("ix_tracks_title")
    _drop_index_if_exists("ix_tracks_spotify_uri")
    _drop_index_if_exists("ix_tracks_musicbrainz_id")
    _drop_index_if_exists("ix_tracks_isrc")
    _drop_index_if_exists("ix_tracks_title_artist")
    # From 0372f0c937d1
    _drop_index_if_exists("ix_tracks_genre")
    # From aa15670cdf15
    _drop_index_if_exists("ix_tracks_file_hash")
    _drop_index_if_exists("ix_tracks_is_broken")
    # Performance indexes from cc17880fff37
    _drop_index_if_exists("ix_tracks_album_track_number")
    _drop_index_if_exists("ix_tracks_album_disc_track")
    _drop_index_if_exists("ix_tracks_updated_at")
    _drop_index_if_exists("ix_tracks_file_path")
    _drop_index_if_exists("ix_tracks_last_scanned_at")
    _drop_index_if_exists("ix_tracks_broken_updated")

    # Create new indexes with soulspot_ prefix
    # Use IF NOT EXISTS to handle idempotent re-runs

    # Artists indexes
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name "
            "ON soulspot_artists (name)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_spotify_uri "
            "ON soulspot_artists (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_artists_musicbrainz_id "
            "ON soulspot_artists (musicbrainz_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_name_lower "
            "ON soulspot_artists (lower(name))"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_artists_updated_at "
            "ON soulspot_artists (updated_at)"
        )
    )

    # Albums indexes
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_title "
            "ON soulspot_albums (title)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_release_year "
            "ON soulspot_albums (release_year)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_albums_spotify_uri "
            "ON soulspot_albums (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_albums_musicbrainz_id "
            "ON soulspot_albums (musicbrainz_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_title_artist "
            "ON soulspot_albums (title, artist_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_artist_id "
            "ON soulspot_albums (artist_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_albums_updated_at "
            "ON soulspot_albums (updated_at)"
        )
    )

    # Tracks indexes
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_title "
            "ON soulspot_tracks (title)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_tracks_spotify_uri "
            "ON soulspot_tracks (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_tracks_musicbrainz_id "
            "ON soulspot_tracks (musicbrainz_id)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_soulspot_tracks_isrc "
            "ON soulspot_tracks (isrc)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_title_artist "
            "ON soulspot_tracks (title, artist_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_genre "
            "ON soulspot_tracks (genre)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_file_hash "
            "ON soulspot_tracks (file_hash)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_is_broken "
            "ON soulspot_tracks (is_broken)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_album_track_number "
            "ON soulspot_tracks (album_id, track_number)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_album_disc_track "
            "ON soulspot_tracks (album_id, disc_number, track_number)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_updated_at "
            "ON soulspot_tracks (updated_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_file_path "
            "ON soulspot_tracks (file_path)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_last_scanned_at "
            "ON soulspot_tracks (last_scanned_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_soulspot_tracks_broken_updated "
            "ON soulspot_tracks (is_broken, updated_at)"
        )
    )


def downgrade() -> None:
    """Revert table names back to generic artists/albums/tracks."""
    # Drop new indexes (using IF EXISTS for safety)
    _drop_index_if_exists("ix_soulspot_artists_name")
    _drop_index_if_exists("ix_soulspot_artists_spotify_uri")
    _drop_index_if_exists("ix_soulspot_artists_musicbrainz_id")
    _drop_index_if_exists("ix_soulspot_artists_name_lower")
    _drop_index_if_exists("ix_soulspot_artists_updated_at")

    _drop_index_if_exists("ix_soulspot_albums_title")
    _drop_index_if_exists("ix_soulspot_albums_release_year")
    _drop_index_if_exists("ix_soulspot_albums_spotify_uri")
    _drop_index_if_exists("ix_soulspot_albums_musicbrainz_id")
    _drop_index_if_exists("ix_soulspot_albums_title_artist")
    _drop_index_if_exists("ix_soulspot_albums_artist_id")
    _drop_index_if_exists("ix_soulspot_albums_updated_at")

    _drop_index_if_exists("ix_soulspot_tracks_title")
    _drop_index_if_exists("ix_soulspot_tracks_spotify_uri")
    _drop_index_if_exists("ix_soulspot_tracks_musicbrainz_id")
    _drop_index_if_exists("ix_soulspot_tracks_isrc")
    _drop_index_if_exists("ix_soulspot_tracks_title_artist")
    _drop_index_if_exists("ix_soulspot_tracks_genre")
    _drop_index_if_exists("ix_soulspot_tracks_file_hash")
    _drop_index_if_exists("ix_soulspot_tracks_is_broken")
    _drop_index_if_exists("ix_soulspot_tracks_album_track_number")
    _drop_index_if_exists("ix_soulspot_tracks_album_disc_track")
    _drop_index_if_exists("ix_soulspot_tracks_updated_at")
    _drop_index_if_exists("ix_soulspot_tracks_file_path")
    _drop_index_if_exists("ix_soulspot_tracks_last_scanned_at")
    _drop_index_if_exists("ix_soulspot_tracks_broken_updated")

    # Rename tables back (only if new names exist)
    if _table_exists("soulspot_tracks"):
        op.rename_table("soulspot_tracks", "tracks")
    if _table_exists("soulspot_albums"):
        op.rename_table("soulspot_albums", "albums")
    if _table_exists("soulspot_artists"):
        op.rename_table("soulspot_artists", "artists")

    # Recreate old indexes
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_artists_name ON artists (name)"))
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_spotify_uri "
            "ON artists (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_musicbrainz_id "
            "ON artists (musicbrainz_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_artists_name_lower ON artists (lower(name))"
        )
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_artists_updated_at ON artists (updated_at)")
    )

    op.execute(text("CREATE INDEX IF NOT EXISTS ix_albums_title ON albums (title)"))
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_albums_release_year ON albums (release_year)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_albums_spotify_uri "
            "ON albums (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_albums_musicbrainz_id "
            "ON albums (musicbrainz_id)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_albums_title_artist "
            "ON albums (title, artist_id)"
        )
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_albums_artist_id ON albums (artist_id)")
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_albums_updated_at ON albums (updated_at)")
    )

    op.execute(text("CREATE INDEX IF NOT EXISTS ix_tracks_title ON tracks (title)"))
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_tracks_spotify_uri "
            "ON tracks (spotify_uri)"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_tracks_musicbrainz_id "
            "ON tracks (musicbrainz_id)"
        )
    )
    op.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tracks_isrc ON tracks (isrc)")
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_tracks_title_artist "
            "ON tracks (title, artist_id)"
        )
    )
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_tracks_genre ON tracks (genre)"))
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_tracks_file_hash ON tracks (file_hash)")
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_tracks_is_broken ON tracks (is_broken)")
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_tracks_album_track_number "
            "ON tracks (album_id, track_number)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_tracks_album_disc_track "
            "ON tracks (album_id, disc_number, track_number)"
        )
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_tracks_updated_at ON tracks (updated_at)")
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS ix_tracks_file_path ON tracks (file_path)")
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_tracks_last_scanned_at "
            "ON tracks (last_scanned_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_tracks_broken_updated "
            "ON tracks (is_broken, updated_at)"
        )
    )
