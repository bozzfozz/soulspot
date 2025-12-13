"""add notifications table for in-app notifications

Revision ID: vv33018xxz66
Revises: uu32017wwy65
Create Date: 2025-12-15 14:00:00.000000

Hey future me - this creates the notifications table for in-app notifications!

This table stores notifications that are displayed in the SoulSpot web UI.
Unlike email/webhook notifications which are fire-and-forget, these persist
and can be:
- Listed (paginated)
- Marked as read
- Dismissed
- Filtered by type

The InAppNotificationProvider writes to this table, and the API exposes
endpoints for the frontend to consume.

Columns:
- id: UUID primary key
- type: Notification type (new_release, download_completed, etc.)
- title: Short title for display
- message: Full message content
- priority: low/normal/high/critical
- data: JSON blob for extra context
- created_at: When notification was created
- read: Whether user has seen it
- user_id: Optional user ID (for multi-user support later)

Indexes:
- idx_notifications_read_created: For efficient unread queries
- idx_notifications_type: For type-based filtering
- idx_notifications_user_id: For user-specific queries
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "vv33018xxz66"
down_revision: Union[str, None] = "uu32017wwy65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notifications table and indexes."""
    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("data", sa.Text, nullable=True),  # JSON string
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("user_id", sa.String(100), nullable=True),
    )
    
    # Index for efficient "unread notifications" queries (most common)
    op.create_index(
        "idx_notifications_read_created",
        "notifications",
        ["read", "created_at"],
    )
    
    # Index for type-based filtering
    op.create_index(
        "idx_notifications_type",
        "notifications",
        ["type"],
    )
    
    # Index for user-specific queries (future multi-user support)
    op.create_index(
        "idx_notifications_user_id",
        "notifications",
        ["user_id"],
    )
    
    # Hey future me - add default notification settings to app_settings!
    # InApp notifications are enabled by default, others require configuration.
    from datetime import datetime, UTC
    
    notifications_table = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    
    now = datetime.now(UTC)
    default_settings = [
        # In-app notifications (enabled by default)
        ("notification.inapp.enabled", "true"),
        ("notification.inapp.max_age_days", "30"),
        ("notification.inapp.max_count", "100"),
        # Webhook notifications (disabled by default, requires config)
        ("notification.webhook.enabled", "false"),
        ("notification.webhook.url", ""),
        ("notification.webhook.format", "generic"),
        ("notification.webhook.auth_header", ""),
        ("notification.webhook.timeout", "30"),
    ]
    
    for key, value in default_settings:
        op.execute(
            notifications_table.insert().values(
                key=key,
                value=value,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    """Drop notifications table and remove settings."""
    # Drop indexes first
    op.drop_index("idx_notifications_user_id", table_name="notifications")
    op.drop_index("idx_notifications_type", table_name="notifications")
    op.drop_index("idx_notifications_read_created", table_name="notifications")
    
    # Drop table
    op.drop_table("notifications")
    
    # Remove notification settings from app_settings
    op.execute(
        "DELETE FROM app_settings WHERE key LIKE 'notification.%'"
    )
