"""Merge library naming settings and table rename branches.

Revision ID: mm26010ppr58
Revises: ll25008oop56, ll25009ooq57
Create Date: 2025-11-29

Hey future me - this is a MERGE migration!

Problem: Two migrations were created in parallel from the same parent (kk24007nno55):
1. ll25008oop56 - Add library naming settings to app_settings
2. ll25009ooq57 - Rename local library tables to soulspot_ prefix

Both are independent changes that don't conflict, but Alembic needs a single
head to proceed. This merge migration creates that single head.

IMPORTANT: This migration does nothing - it's just a graph merge point.
The actual work is done by the two parent migrations.

Note: The order matters for downgrade - we downgrade to naming settings first,
then table rename, because naming settings might reference the old table names.
Actually both reference the original tables, so order doesn't strictly matter,
but we keep naming settings as the "main" branch for consistency.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "mm26010ppr58"
down_revision = ("ll25008oop56", "ll25009ooq57")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge point - no operations needed."""
    pass


def downgrade() -> None:
    """Merge point - no operations needed."""
    pass
