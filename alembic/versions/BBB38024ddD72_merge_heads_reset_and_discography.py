"""merge heads: full_database_reset and add_artist_discography_table

Revision ID: BBB38024ddD72
Revises: AA38023ccD71, AAA38023ccD71
Create Date: 2025-12-19 12:00:00.000000

Hey future me - MERGE MIGRATION!

This migration merges two parallel heads:
1. AA38023ccD71 - full_database_reset (truncates all tables)
2. AAA38023ccD71 - add_artist_discography_table (adds discography tracking)

Both were branched from zz37022bbC70, creating two heads in the migration tree.
This merge brings them back together into a single linear history.

This is a NO-OP migration - all actual schema changes are in the parent migrations.
We just merge the branches so alembic can continue.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "BBB38024ddD72"
down_revision = ("AA38023ccD71", "AAA38023ccD71")
branch_labels = None
depends_on = None


def upgrade():
    """Merge migration - no schema changes."""
    pass


def downgrade():
    """Merge migration - no schema changes."""
    pass
