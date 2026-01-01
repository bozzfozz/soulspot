"""Cleanup invalid spotify_uri values that were stored as Deezer pseudo-URIs

Revision ID: aa38023ccD73
Revises: CCC38027hhI75
Create Date: 2025-12-21 00:00:00.000000

Hey future me - we accidentally persisted Deezer pseudo-URIs ("deezer:123") into
`spotify_uri` columns.

That breaks a core invariant:
- `spotify_uri` must always be a real Spotify URI ("spotify:artist:...", "spotify:album:...")

The domain `SpotifyUri` value object validates strictly and will crash when it
sees these Deezer strings. The LibraryDiscoveryWorker hit exactly that.

Fix strategy:
- Move the Deezer ID from `spotify_uri` into the proper `deezer_id` column
  (if deezer_id is still NULL)
- NULL out the invalid `spotify_uri`

Tables:
- soulspot_artists
- soulspot_albums
- artist_discography (defensive cleanup if present)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aa38023ccD73"
down_revision = "CCC38027hhI75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Move deezer:* from spotify_uri to deezer_id and clear spotify_uri."""

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if "soulspot_artists" in tables:
        # Copy deezer id (strip prefix) if deezer_id is empty
        op.execute(
            """
            UPDATE soulspot_artists
            SET deezer_id = COALESCE(deezer_id, substr(spotify_uri, 8)),
                spotify_uri = NULL
            WHERE spotify_uri LIKE 'deezer:%'
            """
        )

    if "soulspot_albums" in tables:
        op.execute(
            """
            UPDATE soulspot_albums
            SET deezer_id = COALESCE(deezer_id, substr(spotify_uri, 8)),
                spotify_uri = NULL
            WHERE spotify_uri LIKE 'deezer:%'
            """
        )

    # Defensive: older/newer schemas may have this table.
    if "artist_discography" in tables:
        op.execute(
            """
            UPDATE artist_discography
            SET spotify_uri = NULL
            WHERE spotify_uri LIKE 'deezer:%'
            """
        )


def downgrade() -> None:
    """No safe downgrade.

    Hey future me - we can't reliably reconstruct the original spotify_uri.
    Deezer IDs belong in deezer_id, not spotify_uri.
    """
    pass
