"""Merge session_persistence and genres_tags branches

Revision ID: a0fbb3aff2a8
Revises: 40cac646364c, dd18990ggh48
Create Date: 2025-11-23 13:37:33.501242

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a0fbb3aff2a8"
down_revision: str | Sequence[str] | None = ("40cac646364c", "dd18990ggh48")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hey future me - this is a merge migration that resolves the branching issue where two
# independent migrations (40cac646364c for session persistence and dd18990ggh48 for artist
# genres/tags) both revised 0372f0c937d1. This created multiple heads in the migration
# history, causing "alembic upgrade head" to fail. This merge brings them back into a
# single linear chain. No schema changes here - just dependency resolution. Both parent
# migrations must be applied before this one can run. If you roll back past this point,
# you'll end up with the branch again - no problem, just specify which head to target.
def upgrade() -> None:
    """Merge two migration branches - no schema changes needed."""
    pass


def downgrade() -> None:
    """Downgrade from merge - no schema changes to revert."""
    pass
