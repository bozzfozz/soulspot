"""API routes for in-app notifications.

Hey future me - this exposes the notifications to the frontend!
The InAppNotificationProvider writes notifications to the DB, and these
endpoints let the UI:
- List notifications (paginated)
- Get unread count
- Mark as read
- Delete notifications

All endpoints use HTMX-compatible responses where appropriate.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.ports.notification import NotificationType
from soulspot.infrastructure.notifications.inapp_provider import InAppNotificationProvider
from soulspot.infrastructure.persistence.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============================================================================
# Pydantic Models
# ============================================================================


class NotificationResponse(BaseModel):
    """Single notification response."""
    id: str
    type: str
    title: str
    message: str
    priority: str
    data: dict
    created_at: str | None
    read: bool
    user_id: str | None


class NotificationsListResponse(BaseModel):
    """List of notifications response."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread count response."""
    unread_count: int


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: list[str]


class MarkReadResponse(BaseModel):
    """Response after marking notifications as read."""
    marked_count: int


class DeleteResponse(BaseModel):
    """Response after deleting a notification."""
    success: bool


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=NotificationsListResponse)
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_session)],
    unread_only: Annotated[bool, Query(description="Only return unread notifications")] = False,
    notification_type: Annotated[str | None, Query(description="Filter by type")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max notifications to return")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> NotificationsListResponse:
    """List notifications with filtering and pagination.
    
    Hey future me - this is the main endpoint for loading the notification list!
    Frontend polls this or uses it for initial load.
    
    Query params:
    - unread_only: If true, only return unread notifications
    - notification_type: Filter by type (new_release, download_completed, etc.)
    - limit: Max results (default 20, max 100)
    - offset: For pagination
    
    Returns list of notifications plus counts for UI badges.
    """
    provider = InAppNotificationProvider(session)
    
    # Parse notification type if provided
    type_filter = None
    if notification_type:
        try:
            type_filter = NotificationType(notification_type)
        except ValueError:
            pass  # Invalid type, ignore filter
    
    # Get notifications
    notifications = await provider.get_notifications(
        unread_only=unread_only,
        notification_type=type_filter,
        limit=limit,
        offset=offset,
    )
    
    # Get unread count for badge
    unread_count = await provider.get_unread_count()
    
    return NotificationsListResponse(
        notifications=[
            NotificationResponse(
                id=n["id"],
                type=n["type"],
                title=n["title"],
                message=n["message"],
                priority=n["priority"],
                data=n["data"],
                created_at=n["created_at"],
                read=n["read"],
                user_id=n["user_id"],
            )
            for n in notifications
        ],
        total=len(notifications),  # TODO: Add total count query
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnreadCountResponse:
    """Get count of unread notifications.
    
    Hey future me - frontend polls this for the notification badge!
    Lightweight endpoint that only returns the count.
    """
    provider = InAppNotificationProvider(session)
    count = await provider.get_unread_count()
    
    return UnreadCountResponse(unread_count=count)


@router.post("/mark-read", response_model=MarkReadResponse)
async def mark_notifications_read(
    session: Annotated[AsyncSession, Depends(get_session)],
    request: MarkReadRequest,
) -> MarkReadResponse:
    """Mark specific notifications as read.
    
    Hey future me - called when user clicks on a notification!
    Accepts array of IDs so frontend can batch mark.
    """
    if not request.notification_ids:
        return MarkReadResponse(marked_count=0)
    
    provider = InAppNotificationProvider(session)
    count = await provider.mark_as_read(request.notification_ids)
    
    logger.info(f"[NOTIFICATION] Marked {count} notifications as read")
    return MarkReadResponse(marked_count=count)


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_notifications_read(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MarkReadResponse:
    """Mark all notifications as read.
    
    Hey future me - "Clear all" button in the UI!
    """
    provider = InAppNotificationProvider(session)
    count = await provider.mark_all_as_read()
    
    logger.info(f"[NOTIFICATION] Marked all ({count}) notifications as read")
    return MarkReadResponse(marked_count=count)


@router.delete("/{notification_id}", response_model=DeleteResponse)
async def delete_notification(
    session: Annotated[AsyncSession, Depends(get_session)],
    notification_id: str,
) -> DeleteResponse:
    """Delete a specific notification.
    
    Hey future me - "Dismiss" button in the UI!
    """
    provider = InAppNotificationProvider(session)
    success = await provider.delete_notification(notification_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    logger.info(f"[NOTIFICATION] Deleted notification {notification_id[:8]}...")
    return DeleteResponse(success=True)


# ============================================================================
# HTMX Endpoints (HTML fragments)
# ============================================================================


@router.get("/badge")
async def get_notification_badge(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> str:
    """Get notification badge HTML for HTMX.
    
    Hey future me - HTMX polls this to update the badge in the navbar!
    Returns raw HTML that replaces the badge element.
    
    Example response:
    <span class="notification-badge" hx-get="/api/notifications/badge" hx-trigger="every 30s">3</span>
    """
    from fastapi.responses import HTMLResponse
    
    provider = InAppNotificationProvider(session)
    count = await provider.get_unread_count()
    
    if count == 0:
        # Empty badge (hidden)
        html = '<span id="notification-badge" class="hidden" hx-get="/api/notifications/badge" hx-trigger="every 30s"></span>'
    else:
        # Visible badge with count
        badge_text = "99+" if count > 99 else str(count)
        html = f'''<span id="notification-badge" 
            class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center"
            hx-get="/api/notifications/badge" 
            hx-trigger="every 30s">{badge_text}</span>'''
    
    return HTMLResponse(content=html)


__all__ = ["router"]
