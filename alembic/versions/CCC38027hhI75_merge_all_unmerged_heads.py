"""Merge all unmerged heads into single head.

Hey future me - THIS CONSOLIDATES THE MIGRATION MESS!

We had 4 unmerged heads after zz37022bbC70:
1. aa38023ccD73 (cleanup_deezer_pseudo_spotify_uri) - via BBB38024ddD72
2. AAA38023DD71 (rename_spotify_download_images_setting) - ORPHAN
3. ddd38026ggH74 (add_quality_profiles_table) - via aaa38023ddE71 → bbb → ccc → ddd
4. BBB38024eeE72 (add_unified_library_feature_flags) - via AAA38024ccD71

After this merge, we have a SINGLE linear chain again!

The migration itself does nothing - it's just a merge marker.

Revision ID: CCC38027hhI75
Revises: aa38023ccD73, AAA38023DD71, ddd38026ggH74, BBB38024eeE72
Create Date: 2025-01-25

"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "CCC38027hhI75"
down_revision: Union[str, tuple[str, ...], None] = (
    "aa38023ccD73",
    "AAA38023DD71", 
    "ddd38026ggH74",
    "BBB38024eeE72",
)
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
