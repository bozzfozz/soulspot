"""Add UnifiedLibraryManager feature flags to app_settings.

Hey future me - this migration adds the feature flags for the UnifiedLibraryManager!

Feature Flags:
- library.use_unified_manager: Master switch for new UnifiedLibraryManager
- library.auto_queue_downloads: Whether to auto-queue tracks for download on sync
- library.download_cleanup_days: Days before failed downloads reset to not_needed

The flags are FALSE by default for safe rollout - enable when ready to test!
See: docs/architecture/UNIFIED_LIBRARY_WORKER.md

Revision ID: BBB38024eeE72
Revises: AAA38024ccD71
Create Date: 2025-01-24
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "BBB38024eeE72"
down_revision: Union[str, None] = "AAA38024ccD71"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add UnifiedLibraryManager feature flags to app_settings.

    Hey future me - these flags control the new UnifiedLibraryManager system!

    - library.use_unified_manager: FALSE by default (safe rollout)
    - library.auto_queue_downloads: FALSE by default (explicit download requests)
    - library.download_cleanup_days: 7 days (failed downloads reset)
    - library.sync_cooldown_minutes: 5 minutes (prevent API spam)

    Enable use_unified_manager=true when you're ready to test the new system!
    """
    # Insert feature flags with safe defaults
    # Using INSERT ... SELECT WHERE NOT EXISTS to avoid duplicates
    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.use_unified_manager', 'false', 'boolean', 'library',
               'Enable new UnifiedLibraryManager (feature flag for migration)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.use_unified_manager');
        """
    )

    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.auto_queue_downloads', 'false', 'boolean', 'library',
               'Auto-queue tracks for download when syncing (requires use_unified_manager)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.auto_queue_downloads');
        """
    )

    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.download_cleanup_days', '7', 'integer', 'library',
               'Days before failed downloads reset to not_needed (0 = never reset)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.download_cleanup_days');
        """
    )

    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.sync_cooldown_minutes', '5', 'integer', 'library',
               'Minutes between sync operations for same entity type'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.sync_cooldown_minutes');
        """
    )

    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.enrichment_batch_size', '20', 'integer', 'library',
               'Number of entities to enrich per batch (rate limit friendly)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.enrichment_batch_size');
        """
    )

    op.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category, description)
        SELECT 'library.image_download_enabled', 'true', 'boolean', 'library',
               'Download artist/album images locally (vs CDN URLs only)'
        WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'library.image_download_enabled');
        """
    )


def downgrade() -> None:
    """Remove UnifiedLibraryManager feature flags from app_settings."""
    op.execute(
        """
        DELETE FROM app_settings
        WHERE key IN (
            'library.use_unified_manager',
            'library.auto_queue_downloads',
            'library.download_cleanup_days',
            'library.sync_cooldown_minutes',
            'library.enrichment_batch_size',
            'library.image_download_enabled'
        );
        """
    )
