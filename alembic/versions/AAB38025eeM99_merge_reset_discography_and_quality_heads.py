"""merge_reset_discography_and_quality_heads

Revision ID: AAB38025eeM99
Revises: BBB38024ddD72, ddd38026ggH74
Create Date: 2026-01-01 18:30:00.000000

Hey future me - CRITICAL MERGE MIGRATION!

This migration resolves the "Multiple head revisions" error that was
blocking Docker container startup and alembic upgrade head commands.

The problem: Two independent branches were left unmerged:

Branch 1 - Reset/Discography Path:
  zz37022bbC70 -> AA38023ccD71 (full_database_reset)
               -> AAA38023ccD71 (add_artist_discography)
               -> BBB38024ddD72 (merge) <-- HEAD 1

Branch 2 - Quality Profiles Path:
  zz37022bbC70 -> AAA38024ccD71 -> BBB38024eeE72 -> CCC38027hhI75
               -> aa38023ccD73 -> AAA38023DD71 -> aaa38023ddE71
               -> bbb38024eeF72 -> ccc38025ffG73 -> ddd38026ggH74 <-- HEAD 2

Both branches diverged from zz37022bbC70 but were never merged back together.

This is a NO-OP migration - all actual schema changes are in the parent migrations.
We just merge the branches so alembic can continue with a single linear history.

After this migration:
  alembic heads -> AAB38025eeM99 (head) [SINGLE HEAD!]
  alembic upgrade head -> Works correctly!
"""

from typing import Union

# revision identifiers, used by Alembic.
revision: str = "AAB38025eeM99"
down_revision: Union[str, tuple[str, ...], None] = ("BBB38024ddD72", "ddd38026ggH74")
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes.

    This brings together the two parallel migration branches into
    a single linear history, resolving the multiple heads issue.
    """
    pass


def downgrade() -> None:
    """Merge migration - no schema changes.

    Rolling back past this point will re-create the branch split.
    Use `alembic downgrade <specific_revision>` if needed.
    """
    pass
