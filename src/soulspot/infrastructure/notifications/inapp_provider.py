"""In-app notification provider storing notifications in the database.

Hey future me - this stores notifications in a database table for the UI to display!
Unlike email/webhook which are fire-and-forget, in-app notifications persist and can be:
- Listed (paginated)
- Marked as read
- Dismissed
- Filtered by type

The UI can poll for new notifications or use WebSockets for real-time updates.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from soulspot.domain.ports.notification import (
    INotificationProvider,
    Notification,
    NotificationResult,
    NotificationType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class InAppNotificationProvider(INotificationProvider):
    """In-app notification provider storing notifications in database.
    
    Hey future me - this is for showing notifications IN THE WEB UI!
    Notifications are stored in the `notifications` table (see migration).
    
    Features:
    - Persistent storage with timestamps
    - Read/unread status tracking
    - Pagination support
    - Type-based filtering
    - Auto-cleanup of old notifications
    
    Config keys in app_settings:
        notification.inapp.enabled: bool (default True)
        notification.inapp.max_age_days: int (default 30, auto-cleanup)
        notification.inapp.max_count: int (default 100, per user)
    """

    def __init__(self, session: "AsyncSession") -> None:
        """Initialize with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self._session = session
        self._settings_cache: dict[str, Any] = {}
        self._cache_loaded = False

    @property
    def name(self) -> str:
        """Provider name."""
        return "inapp"

    @property
    def supported_types(self) -> list[NotificationType]:
        """In-app supports all notification types."""
        return []

    async def _load_settings(self) -> None:
        """Load in-app settings from database."""
        if self._cache_loaded:
            return

        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )

        settings_service = AppSettingsService(self._session)

        self._settings_cache = {
            "enabled": await settings_service.get_bool("notification.inapp.enabled", True),
            "max_age_days": await settings_service.get_int("notification.inapp.max_age_days", 30),
            "max_count": await settings_service.get_int("notification.inapp.max_count", 100),
        }
        self._cache_loaded = True

    def invalidate_cache(self) -> None:
        """Invalidate settings cache."""
        self._cache_loaded = False
        self._settings_cache.clear()

    async def is_configured(self) -> bool:
        """Check if in-app notifications are enabled.
        
        In-app notifications are always available (DB-backed),
        just need to check if enabled.
        """
        await self._load_settings()
        return bool(self._settings_cache.get("enabled", True))

    async def send(self, notification: Notification) -> NotificationResult:
        """Store notification in database.
        
        Args:
            notification: Notification to store
            
        Returns:
            NotificationResult with success status
        """
        await self._load_settings()

        if not await self.is_configured():
            return NotificationResult(
                success=False,
                provider_name=self.name,
                notification_type=notification.type,
                error="In-app notifications disabled",
            )

        try:
            # Generate unique ID
            notification_id = str(uuid4())

            # Store in database
            await self._store_notification(notification, notification_id)

            # Cleanup old notifications if needed
            await self._cleanup_old_notifications()

            logger.info(
                f"[NOTIFICATION] In-app stored: {notification.type.value} - "
                f"{notification.title[:50]}... (id={notification_id[:8]})"
            )

            return NotificationResult(
                success=True,
                provider_name=self.name,
                notification_type=notification.type,
                external_id=notification_id,
            )

        except Exception as e:
            logger.error(f"[NOTIFICATION] In-app storage failed: {e}")
            return NotificationResult(
                success=False,
                provider_name=self.name,
                notification_type=notification.type,
                error=str(e),
            )

    async def _store_notification(
        self, notification: Notification, notification_id: str
    ) -> None:
        """Store notification in database.
        
        Hey future me - this uses raw SQL insert for now. Could be refactored
        to use a NotificationModel if you prefer ORM style.
        """
        # Serialize data as JSON
        import json

        from sqlalchemy import text
        data_json = json.dumps(notification.data or {})

        query = text("""
            INSERT INTO notifications (
                id, type, title, message, priority, data,
                created_at, read, user_id
            ) VALUES (
                :id, :type, :title, :message, :priority, :data,
                :created_at, :read, :user_id
            )
        """)

        await self._session.execute(
            query,
            {
                "id": notification_id,
                "type": notification.type.value,
                "title": notification.title[:500],  # Limit title length
                "message": notification.message[:5000],  # Limit message length
                "priority": notification.priority.value,
                "data": data_json,
                "created_at": notification.timestamp or datetime.now(UTC),
                "read": notification.read,
                "user_id": notification.user_id,
            },
        )
        await self._session.commit()

    async def _cleanup_old_notifications(self) -> None:
        """Remove old notifications beyond max_age_days.
        
        Hey future me - this runs on every insert but is cheap (single DELETE).
        Consider running as a background job if notification volume is high.
        """
        from datetime import timedelta

        from sqlalchemy import text

        max_age_days = int(self._settings_cache.get("max_age_days", 30))
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        query = text("""
            DELETE FROM notifications
            WHERE created_at < :cutoff_date
        """)

        try:
            await self._session.execute(query, {"cutoff_date": cutoff_date})
            await self._session.commit()
        except Exception as e:
            logger.warning(f"[NOTIFICATION] Cleanup failed (non-critical): {e}")
            await self._session.rollback()

    # =========================================================================
    # QUERY METHODS (for API/UI use)
    # =========================================================================

    async def get_unread_count(self, user_id: str | None = None) -> int:
        """Get count of unread notifications.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Count of unread notifications
        """
        from sqlalchemy import text

        if user_id:
            query = text("""
                SELECT COUNT(*) FROM notifications
                WHERE read = FALSE AND user_id = :user_id
            """)
            result = await self._session.execute(query, {"user_id": user_id})
        else:
            query = text("""
                SELECT COUNT(*) FROM notifications
                WHERE read = FALSE
            """)
            result = await self._session.execute(query)

        row = result.scalar()
        return int(row) if row else 0

    async def get_notifications(
        self,
        user_id: str | None = None,
        unread_only: bool = False,
        notification_type: NotificationType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get notifications with filtering and pagination.
        
        Args:
            user_id: Optional user ID filter
            unread_only: If True, only return unread notifications
            notification_type: Optional type filter
            limit: Max notifications to return
            offset: Pagination offset
            
        Returns:
            List of notification dicts
        """
        from sqlalchemy import text

        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id

        if unread_only:
            conditions.append("read = FALSE")

        if notification_type:
            conditions.append("type = :type")
            params["type"] = notification_type.value

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = text(f"""
            SELECT id, type, title, message, priority, data, created_at, read, user_id
            FROM notifications
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self._session.execute(query, params)
        rows = result.fetchall()

        import json
        return [
            {
                "id": row[0],
                "type": row[1],
                "title": row[2],
                "message": row[3],
                "priority": row[4],
                "data": json.loads(row[5]) if row[5] else {},
                "created_at": row[6].isoformat() if row[6] else None,
                "read": row[7],
                "user_id": row[8],
            }
            for row in rows
        ]

    async def mark_as_read(
        self, notification_ids: list[str], user_id: str | None = None
    ) -> int:
        """Mark notifications as read.
        
        Args:
            notification_ids: List of notification IDs to mark
            user_id: Optional user ID for ownership check
            
        Returns:
            Number of notifications marked as read
        """
        from sqlalchemy import text

        if not notification_ids:
            return 0

        # Build IN clause with placeholders
        placeholders = ", ".join(f":id_{i}" for i in range(len(notification_ids)))
        params: dict[str, Any] = {f"id_{i}": nid for i, nid in enumerate(notification_ids)}

        if user_id:
            query = text(f"""
                UPDATE notifications
                SET read = TRUE
                WHERE id IN ({placeholders}) AND user_id = :user_id
            """)
            params["user_id"] = user_id
        else:
            query = text(f"""
                UPDATE notifications
                SET read = TRUE
                WHERE id IN ({placeholders})
            """)

        result = await self._session.execute(query, params)
        await self._session.commit()

        return result.rowcount

    async def mark_all_as_read(self, user_id: str | None = None) -> int:
        """Mark all notifications as read.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Number of notifications marked as read
        """
        from sqlalchemy import text

        if user_id:
            query = text("""
                UPDATE notifications
                SET read = TRUE
                WHERE read = FALSE AND user_id = :user_id
            """)
            result = await self._session.execute(query, {"user_id": user_id})
        else:
            query = text("""
                UPDATE notifications
                SET read = TRUE
                WHERE read = FALSE
            """)
            result = await self._session.execute(query)

        await self._session.commit()
        return result.rowcount

    async def delete_notification(
        self, notification_id: str, user_id: str | None = None
    ) -> bool:
        """Delete a specific notification.
        
        Args:
            notification_id: ID of notification to delete
            user_id: Optional user ID for ownership check
            
        Returns:
            True if deleted, False if not found
        """
        from sqlalchemy import text

        if user_id:
            query = text("""
                DELETE FROM notifications
                WHERE id = :id AND user_id = :user_id
            """)
            result = await self._session.execute(
                query, {"id": notification_id, "user_id": user_id}
            )
        else:
            query = text("""
                DELETE FROM notifications
                WHERE id = :id
            """)
            result = await self._session.execute(query, {"id": notification_id})

        await self._session.commit()
        return result.rowcount > 0


__all__ = ["InAppNotificationProvider"]
