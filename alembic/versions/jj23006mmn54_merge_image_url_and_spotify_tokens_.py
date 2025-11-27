"""Merge image_url and spotify_tokens branches

Revision ID: jj23006mmn54
Revises: c7da905f261a, ii22005llm53
Create Date: 2025-11-27 06:30:00.000000

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'jj23006mmn54'
down_revision: str | Sequence[str] | None = ('c7da905f261a', 'ii22005llm53')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Hey future me - this is a merge migration that resolves the branching issue where two
# independent branches diverged from dd18990ggh48:
# - Branch 1: dd18990ggh48 -> a0fbb3aff2a8 (merge) -> c7da905f261a (add_image_url_to_artists)
# - Branch 2: dd18990ggh48 -> ee19001hhj49 -> ff20002ii50 -> gg20003jj51 -> hh21004kkl52 -> ii22005llm53
# This created multiple heads in the migration history, causing "alembic upgrade head" to fail.
# This merge brings them back into a single linear chain. No schema changes here - just
# dependency resolution. Both parent migrations must be applied before this one can run.
def upgrade() -> None:
    """Merge two migration branches - no schema changes needed."""
    pass


def downgrade() -> None:
    """Downgrade from merge - no schema changes to revert."""
    pass
