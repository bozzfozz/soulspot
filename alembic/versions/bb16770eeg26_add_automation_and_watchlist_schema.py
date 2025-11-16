"""add_automation_and_watchlist_schema

Revision ID: bb16770eeg26
Revises: aa15670cdf15
Create Date: 2025-11-16 07:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb16770eeg26'
down_revision: Union[str, Sequence[str], None] = 'aa15670cdf15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create artist_watchlists table
    op.create_table(
        'artist_watchlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('artist_id', sa.String(36), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('check_frequency_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('auto_download', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('quality_profile', sa.String(20), nullable=False, server_default='high'),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_release_date', sa.DateTime(), nullable=True),
        sa.Column('total_releases_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_downloads_triggered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_artist_watchlists_artist_id', 'artist_watchlists', ['artist_id'])
    op.create_index('ix_artist_watchlists_status', 'artist_watchlists', ['status'])
    op.create_index('ix_artist_watchlists_last_checked', 'artist_watchlists', ['last_checked_at'])

    # Create filter_rules table
    op.create_table(
        'filter_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('filter_type', sa.String(20), nullable=False),
        sa.Column('target', sa.String(20), nullable=False),
        sa.Column('pattern', sa.Text(), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_filter_rules_name', 'filter_rules', ['name'])
    op.create_index('ix_filter_rules_type', 'filter_rules', ['filter_type'])
    op.create_index('ix_filter_rules_target', 'filter_rules', ['target'])
    op.create_index('ix_filter_rules_enabled', 'filter_rules', ['enabled'])
    op.create_index('ix_filter_rules_type_enabled', 'filter_rules', ['filter_type', 'enabled'])
    op.create_index('ix_filter_rules_priority', 'filter_rules', ['priority'])

    # Create automation_rules table
    op.create_table(
        'automation_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('trigger', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quality_profile', sa.String(20), nullable=False, server_default='high'),
        sa.Column('apply_filters', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('auto_process', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('total_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_automation_rules_name', 'automation_rules', ['name'])
    op.create_index('ix_automation_rules_trigger', 'automation_rules', ['trigger'])
    op.create_index('ix_automation_rules_enabled', 'automation_rules', ['enabled'])
    op.create_index('ix_automation_rules_trigger_enabled', 'automation_rules', ['trigger', 'enabled'])
    op.create_index('ix_automation_rules_priority', 'automation_rules', ['priority'])

    # Create quality_upgrade_candidates table
    op.create_table(
        'quality_upgrade_candidates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('track_id', sa.String(36), sa.ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_bitrate', sa.Integer(), nullable=False),
        sa.Column('current_format', sa.String(20), nullable=False),
        sa.Column('target_bitrate', sa.Integer(), nullable=False),
        sa.Column('target_format', sa.String(20), nullable=False),
        sa.Column('improvement_score', sa.Float(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('download_id', sa.String(36), sa.ForeignKey('downloads.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_quality_upgrade_candidates_track_id', 'quality_upgrade_candidates', ['track_id'])
    op.create_index('ix_quality_upgrade_candidates_processed', 'quality_upgrade_candidates', ['processed'])
    op.create_index('ix_quality_upgrade_candidates_improvement_score', 'quality_upgrade_candidates', ['improvement_score'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index('ix_quality_upgrade_candidates_improvement_score', 'quality_upgrade_candidates')
    op.drop_index('ix_quality_upgrade_candidates_processed', 'quality_upgrade_candidates')
    op.drop_index('ix_quality_upgrade_candidates_track_id', 'quality_upgrade_candidates')
    op.drop_table('quality_upgrade_candidates')

    op.drop_index('ix_automation_rules_priority', 'automation_rules')
    op.drop_index('ix_automation_rules_trigger_enabled', 'automation_rules')
    op.drop_index('ix_automation_rules_enabled', 'automation_rules')
    op.drop_index('ix_automation_rules_trigger', 'automation_rules')
    op.drop_index('ix_automation_rules_name', 'automation_rules')
    op.drop_table('automation_rules')

    op.drop_index('ix_filter_rules_priority', 'filter_rules')
    op.drop_index('ix_filter_rules_type_enabled', 'filter_rules')
    op.drop_index('ix_filter_rules_enabled', 'filter_rules')
    op.drop_index('ix_filter_rules_target', 'filter_rules')
    op.drop_index('ix_filter_rules_type', 'filter_rules')
    op.drop_index('ix_filter_rules_name', 'filter_rules')
    op.drop_table('filter_rules')

    op.drop_index('ix_artist_watchlists_last_checked', 'artist_watchlists')
    op.drop_index('ix_artist_watchlists_status', 'artist_watchlists')
    op.drop_index('ix_artist_watchlists_artist_id', 'artist_watchlists')
    op.drop_table('artist_watchlists')
