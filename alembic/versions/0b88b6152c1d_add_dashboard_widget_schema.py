"""add_dashboard_widget_schema

Revision ID: 0b88b6152c1d
Revises: cc17880fff37
Create Date: 2025-11-16 19:37:21.597161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b88b6152c1d'
down_revision: Union[str, Sequence[str], None] = 'cc17880fff37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add dashboard widget system tables."""
    # Create widgets table (widget registry)
    op.create_table(
        'widgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('template_path', sa.String(length=200), nullable=False),
        sa.Column('default_config', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type')
    )
    op.create_index(op.f('ix_widgets_type'), 'widgets', ['type'], unique=True)
    
    # Create pages table (dashboard pages)
    op.create_table(
        'pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_pages_slug'), 'pages', ['slug'], unique=True)
    
    # Create widget_instances table (placed widgets on pages)
    op.create_table(
        'widget_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_id', sa.Integer(), nullable=False),
        sa.Column('widget_type', sa.String(length=50), nullable=False),
        sa.Column('position_row', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('position_col', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('span_cols', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['widget_type'], ['widgets.type'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('page_id', 'position_row', 'position_col', name='uq_widget_position')
    )
    op.create_index(op.f('ix_widget_instances_page_id'), 'widget_instances', ['page_id'], unique=False)
    op.create_index(op.f('ix_widget_instances_widget_type'), 'widget_instances', ['widget_type'], unique=False)
    
    # Seed widget registry with 5 core widgets
    op.execute("""
        INSERT INTO widgets (type, name, template_path, default_config) VALUES
        ('active_jobs', 'Active Jobs', 'partials/widgets/active_jobs.html', '{"refresh_interval": 5}'),
        ('spotify_search', 'Spotify Search', 'partials/widgets/spotify_search.html', '{"max_results": 10}'),
        ('missing_tracks', 'Missing Tracks', 'partials/widgets/missing_tracks.html', '{"show_all": false}'),
        ('quick_actions', 'Quick Actions', 'partials/widgets/quick_actions.html', '{"actions": ["scan", "import", "fix"]}'),
        ('metadata_manager', 'Metadata Manager', 'partials/widgets/metadata_manager.html', '{"filter": "all"}')
    """)
    
    # Create default dashboard page
    op.execute("""
        INSERT INTO pages (name, slug, is_default, created_at, updated_at) VALUES
        ('My Dashboard', 'default', 1, datetime('now'), datetime('now'))
    """)


def downgrade() -> None:
    """Downgrade schema - Remove dashboard widget system tables."""
    op.drop_index(op.f('ix_widget_instances_widget_type'), table_name='widget_instances')
    op.drop_index(op.f('ix_widget_instances_page_id'), table_name='widget_instances')
    op.drop_table('widget_instances')
    op.drop_index(op.f('ix_pages_slug'), table_name='pages')
    op.drop_table('pages')
    op.drop_index(op.f('ix_widgets_type'), table_name='widgets')
    op.drop_table('widgets')
