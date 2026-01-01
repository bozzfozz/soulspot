"""Continue after BBB38024eeE72 (Unified Library feature flags).

Hey future me - THIS IS NOT A MERGE!

The previous attempt tried to merge 4 heads, but 3 of those heads
(aa38023ccD73, AAA38023DD71, ddd38026ggH74) were never executed in this DB.

The DB's actual migration path was:
  zz37022bbC70 → AAA38024ccD71 → BBB38024eeE72

This migration simply continues from BBB38024eeE72 (the real HEAD).

No schema changes - just a placeholder for future migrations.

Revision ID: CCC38027hhI75
Revises: BBB38024eeE72
Create Date: 2025-01-25

"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "CCC38027hhI75"
down_revision: Union[str, None] = "BBB38024eeE72"  # SINGLE parent, not a merge!
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes.
    
    This migration consolidates 4 unmerged heads into a single chain.
    No actual database changes are made.
    """
    pass  # Merge migrations don't modify the database


def downgrade() -> None:
    """Merge downgrade - no schema changes."""
    pass  # Merge migrations don't modify the database
