"""remove_widget_system

Revision ID: ee19001hhj49
Revises: dd18990ggh48
Create Date: 2025-11-26 00:41:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee19001hhj49"
down_revision: str | None = "dd18990ggh48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove widget system tables."""
    # Drop widget_instances first (has foreign keys to widgets and pages)
    op.drop_table("widget_instances")

    # Drop pages table
    op.drop_table("pages")

    # Drop widgets table
    op.drop_table("widgets")


def downgrade() -> None:
    """Recreate widget system tables."""
    # Recreate widgets table
    op.create_table(
        "widgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_path", sa.String(length=200), nullable=False),
        sa.Column("default_config", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type"),
    )
    op.create_index("ix_widgets_type", "widgets", ["type"])

    # Recreate pages table
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_pages_slug", "pages", ["slug"])

    # Recreate widget_instances table
    op.create_table(
        "widget_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("widget_type", sa.String(length=50), nullable=False),
        sa.Column("position_row", sa.Integer(), nullable=False),
        sa.Column("position_col", sa.Integer(), nullable=False),
        sa.Column("span_cols", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["widget_type"], ["widgets.type"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "page_id", "position_row", "position_col", name="uq_widget_position"
        ),
    )
    op.create_index("ix_widget_instances_page_id", "widget_instances", ["page_id"])
    op.create_index(
        "ix_widget_instances_widget_type", "widget_instances", ["widget_type"]
    )
