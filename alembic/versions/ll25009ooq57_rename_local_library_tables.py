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
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "ll25009ooq57"
down_revision = "kk24007nno55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename local library tables from generic names to soulspot_ prefix."""
    # Rename the three core local library tables
    # SQLite handles foreign key updates automatically with RENAME TABLE
    op.rename_table("artists", "soulspot_artists")
    op.rename_table("albums", "soulspot_albums")
    op.rename_table("tracks", "soulspot_tracks")

    # Drop old indexes and recreate with new names
    # Artists indexes
    op.drop_index("ix_artists_name", table_name="soulspot_artists")
    op.drop_index("ix_artists_spotify_uri", table_name="soulspot_artists")
    op.drop_index("ix_artists_musicbrainz_id", table_name="soulspot_artists")
    op.drop_index("ix_artists_name_lower", table_name="soulspot_artists")

    op.create_index("ix_soulspot_artists_name", "soulspot_artists", ["name"])
    op.create_index(
        "ix_soulspot_artists_spotify_uri",
        "soulspot_artists",
        ["spotify_uri"],
        unique=True,
    )
    op.create_index(
        "ix_soulspot_artists_musicbrainz_id",
        "soulspot_artists",
        ["musicbrainz_id"],
        unique=True,
    )
    # Note: func.lower() index needs raw SQL in SQLite
    op.execute(
        "CREATE INDEX ix_soulspot_artists_name_lower ON soulspot_artists (lower(name))"
    )

    # Albums indexes
    op.drop_index("ix_albums_title", table_name="soulspot_albums")
    op.drop_index("ix_albums_release_year", table_name="soulspot_albums")
    op.drop_index("ix_albums_spotify_uri", table_name="soulspot_albums")
    op.drop_index("ix_albums_musicbrainz_id", table_name="soulspot_albums")
    op.drop_index("ix_albums_title_artist", table_name="soulspot_albums")

    op.create_index("ix_soulspot_albums_title", "soulspot_albums", ["title"])
    op.create_index(
        "ix_soulspot_albums_release_year", "soulspot_albums", ["release_year"]
    )
    op.create_index(
        "ix_soulspot_albums_spotify_uri",
        "soulspot_albums",
        ["spotify_uri"],
        unique=True,
    )
    op.create_index(
        "ix_soulspot_albums_musicbrainz_id",
        "soulspot_albums",
        ["musicbrainz_id"],
        unique=True,
    )
    op.create_index(
        "ix_soulspot_albums_title_artist", "soulspot_albums", ["title", "artist_id"]
    )

    # Tracks indexes
    op.drop_index("ix_tracks_title", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_spotify_uri", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_musicbrainz_id", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_isrc", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_genre", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_file_hash", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_is_broken", table_name="soulspot_tracks")
    op.drop_index("ix_tracks_title_artist", table_name="soulspot_tracks")

    op.create_index("ix_soulspot_tracks_title", "soulspot_tracks", ["title"])
    op.create_index(
        "ix_soulspot_tracks_spotify_uri",
        "soulspot_tracks",
        ["spotify_uri"],
        unique=True,
    )
    op.create_index(
        "ix_soulspot_tracks_musicbrainz_id",
        "soulspot_tracks",
        ["musicbrainz_id"],
        unique=True,
    )
    op.create_index(
        "ix_soulspot_tracks_isrc", "soulspot_tracks", ["isrc"], unique=True
    )
    op.create_index("ix_soulspot_tracks_genre", "soulspot_tracks", ["genre"])
    op.create_index("ix_soulspot_tracks_file_hash", "soulspot_tracks", ["file_hash"])
    op.create_index("ix_soulspot_tracks_is_broken", "soulspot_tracks", ["is_broken"])
    op.create_index(
        "ix_soulspot_tracks_title_artist", "soulspot_tracks", ["title", "artist_id"]
    )


def downgrade() -> None:
    """Revert table names back to generic artists/albums/tracks."""
    # Drop new indexes
    op.drop_index("ix_soulspot_artists_name", table_name="soulspot_artists")
    op.drop_index("ix_soulspot_artists_spotify_uri", table_name="soulspot_artists")
    op.drop_index("ix_soulspot_artists_musicbrainz_id", table_name="soulspot_artists")
    op.drop_index("ix_soulspot_artists_name_lower", table_name="soulspot_artists")

    op.drop_index("ix_soulspot_albums_title", table_name="soulspot_albums")
    op.drop_index("ix_soulspot_albums_release_year", table_name="soulspot_albums")
    op.drop_index("ix_soulspot_albums_spotify_uri", table_name="soulspot_albums")
    op.drop_index("ix_soulspot_albums_musicbrainz_id", table_name="soulspot_albums")
    op.drop_index("ix_soulspot_albums_title_artist", table_name="soulspot_albums")

    op.drop_index("ix_soulspot_tracks_title", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_spotify_uri", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_musicbrainz_id", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_isrc", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_genre", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_file_hash", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_is_broken", table_name="soulspot_tracks")
    op.drop_index("ix_soulspot_tracks_title_artist", table_name="soulspot_tracks")

    # Rename tables back
    op.rename_table("soulspot_tracks", "tracks")
    op.rename_table("soulspot_albums", "albums")
    op.rename_table("soulspot_artists", "artists")

    # Recreate old indexes
    op.create_index("ix_artists_name", "artists", ["name"])
    op.create_index("ix_artists_spotify_uri", "artists", ["spotify_uri"], unique=True)
    op.create_index(
        "ix_artists_musicbrainz_id", "artists", ["musicbrainz_id"], unique=True
    )
    op.execute("CREATE INDEX ix_artists_name_lower ON artists (lower(name))")

    op.create_index("ix_albums_title", "albums", ["title"])
    op.create_index("ix_albums_release_year", "albums", ["release_year"])
    op.create_index("ix_albums_spotify_uri", "albums", ["spotify_uri"], unique=True)
    op.create_index(
        "ix_albums_musicbrainz_id", "albums", ["musicbrainz_id"], unique=True
    )
    op.create_index("ix_albums_title_artist", "albums", ["title", "artist_id"])

    op.create_index("ix_tracks_title", "tracks", ["title"])
    op.create_index("ix_tracks_spotify_uri", "tracks", ["spotify_uri"], unique=True)
    op.create_index(
        "ix_tracks_musicbrainz_id", "tracks", ["musicbrainz_id"], unique=True
    )
    op.create_index("ix_tracks_isrc", "tracks", ["isrc"], unique=True)
    op.create_index("ix_tracks_genre", "tracks", ["genre"])
    op.create_index("ix_tracks_file_hash", "tracks", ["file_hash"])
    op.create_index("ix_tracks_is_broken", "tracks", ["is_broken"])
    op.create_index("ix_tracks_title_artist", "tracks", ["title", "artist_id"])
