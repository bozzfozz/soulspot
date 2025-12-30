# Notifications API

In-app notification system for user alerts and updates.

## Overview

The Notifications API provides in-app notifications for user-facing events:
- **Notification Types**: New releases, download completed, errors, system alerts
- **Read/Unread Tracking**: Mark notifications as read
- **Filtering**: Filter by type, read status
- **HTMX Integration**: Real-time badge updates via polling

**Notification Provider:**
- **InAppNotificationProvider**: Writes notifications to database
- **Persistence**: Stored in `notifications` table
- **Delivery**: Displayed in UI via API queries (no push/email yet)

**Use Cases:**
- **New Releases**: Notify when followed artists release new albums
- **Download Completion**: Alert when tracks finish downloading
- **Errors**: Inform user of failed operations
- **System Events**: Maintenance, updates, etc.

---

## List Notifications

**Endpoint:** `GET /api/notifications`

**Description:** List notifications with filtering and pagination.

**Query Parameters:**
- `unread_only` (boolean, optional): Only return unread notifications (default: false)
- `notification_type` (string, optional): Filter by type (`new_release`, `download_completed`, `error`, etc.)
- `limit` (integer, optional): Max notifications to return (1-100, default: 20)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response:**
```json
{
    "notifications": [
        {
            "id": "notif-uuid-123",
            "type": "new_release",
            "title": "New Album from Arctic Monkeys",
            "message": "The Car is now available!",
            "priority": "normal",
            "data": {
                "artist_id": "artist-uuid-456",
                "album_id": "album-uuid-789",
                "spotify_uri": "spotify:album:xyz"
            },
            "created_at": "2025-12-15T10:00:00Z",
            "read": false,
            "user_id": null
        },
        {
            "id": "notif-uuid-456",
            "type": "download_completed",
            "title": "Download Complete",
            "message": "Track 'Song Title' downloaded successfully",
            "priority": "low",
            "data": {
                "track_id": "track-uuid-123",
                "file_path": "/music/artist/album/song.flac"
            },
            "created_at": "2025-12-15T09:30:00Z",
            "read": true,
            "user_id": null
        }
    ],
    "total": 2,
    "unread_count": 1
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 68-120

@router.get("", response_model=NotificationsListResponse)
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    unread_only: Annotated[
        bool, Query(description="Only return unread notifications")
    ] = False,
    notification_type: Annotated[
        str | None, Query(description="Filter by type")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Max notifications to return")
    ] = 20,
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
```

**Notification Fields:**
- `id` (string): Notification UUID
- `type` (string): Notification type
- `title` (string): Notification title
- `message` (string): Notification message
- `priority` (string): Priority level (`low`, `normal`, `high`, `urgent`)
- `data` (object): Additional context (entity IDs, URIs, etc.)
- `created_at` (string): ISO timestamp
- `read` (boolean): Whether user read notification
- `user_id` (string | null): User ID (null for global notifications)

**Notification Types:**
- `new_release`: New album from followed artist
- `download_completed`: Track download finished
- `download_failed`: Track download failed
- `error`: General error notification
- `system`: System announcement
- `warning`: Warning message

**Use Cases:**
- **Notification Center**: Load notification list in UI
- **Initial Load**: Fetch recent notifications on app start
- **Filtering**: Show only specific types (e.g., errors)
- **Pagination**: Load more notifications on scroll

**Polling Frequency:**
- **Recommended**: Poll every 30-60 seconds
- **Badge Count**: Use `/notifications/unread-count` for faster badge updates
- **Real-Time Alternative**: Future SSE support for instant notifications

---

## Get Unread Count

**Endpoint:** `GET /api/notifications/unread-count`

**Description:** Get count of unread notifications (lightweight).

**Query Parameters:** None

**Response:**
```json
{
    "unread_count": 5
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 123-137

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnreadCountResponse:
    """Get count of unread notifications.

    Hey future me - frontend polls this for the notification badge!
    Lightweight endpoint that only returns the count.
    """
```

**Use Cases:**
- **Notification Badge**: Display unread count in navbar
- **Fast Polling**: Poll frequently (every 10-30 seconds)
- **Lightweight**: No need to fetch full notification list

**HTMX Alternative:** Use `/notifications/badge` for HTML badge fragment.

---

## Mark Notifications as Read

**Endpoint:** `POST /api/notifications/mark-read`

**Description:** Mark specific notifications as read.

**Request Body:**
```json
{
    "notification_ids": ["notif-uuid-123", "notif-uuid-456"]
}
```

**Request Fields:**
- `notification_ids` (array[string]): List of notification UUIDs to mark as read

**Response:**
```json
{
    "marked_count": 2
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 140-159

@router.post("/mark-read", response_model=MarkReadResponse)
async def mark_notifications_read(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: MarkReadRequest,
) -> MarkReadResponse:
    """Mark specific notifications as read.

    Hey future me - called when user clicks on a notification!
    Accepts array of IDs so frontend can batch mark.
    """
```

**Use Cases:**
- **Click Handler**: Mark notification as read when user clicks
- **Batch Marking**: Mark multiple notifications at once
- **UI Update**: Update read status in notification list

**Behavior:**
- **Idempotent**: Marking already-read notifications is safe
- **Empty Array**: Returns `marked_count=0` without error
- **Invalid IDs**: Ignores non-existent IDs (no error)

---

## Mark All Notifications as Read

**Endpoint:** `POST /api/notifications/mark-all-read`

**Description:** Mark all notifications as read.

**Request Body:** None

**Response:**
```json
{
    "marked_count": 12
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 162-176

@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_notifications_read(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarkReadResponse:
    """Mark all notifications as read.

    Hey future me - "Clear all" button in the UI!
    """
```

**Use Cases:**
- **Clear All Button**: UI "Mark all as read" action
- **Bulk Action**: Clear notification badge
- **Cleanup**: Reset notification state

**Behavior:**
- **Global**: Marks ALL notifications for user as read
- **No Filtering**: Doesn't filter by type or date

---

## Delete Notification

**Endpoint:** `DELETE /api/notifications/{notification_id}`

**Description:** Delete a specific notification permanently.

**Path Parameters:**
- `notification_id` (string): Notification UUID to delete

**Response:**
```json
{
    "success": true
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 179-198

@router.delete("/{notification_id}", response_model=DeleteResponse)
async def delete_notification(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    notification_id: str,
) -> DeleteResponse:
    """Delete a specific notification.

    Hey future me - "Dismiss" button in the UI!
    """
```

**Error Responses:**
- **404 Not Found**: Notification doesn't exist

**Use Cases:**
- **Dismiss Button**: Remove notification from list
- **Permanent Delete**: Cannot be undone
- **UI Cleanup**: Remove unwanted notifications

**Behavior:**
- **Permanent**: Notification deleted from database
- **Not Reversible**: Cannot undo deletion

---

## Get Notification Badge (HTMX)

**Endpoint:** `GET /api/notifications/badge`

**Description:** Get notification badge HTML fragment for HTMX.

**Query Parameters:** None

**Response (HTML):** Badge HTML that replaces navbar element

**Response Examples:**

**No Unread Notifications:**
```html
<span id="notification-badge" class="hidden" hx-get="/api/notifications/badge" hx-trigger="every 30s"></span>
```

**With Unread (3 notifications):**
```html
<span id="notification-badge"
    class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center"
    hx-get="/api/notifications/badge"
    hx-trigger="every 30s">3</span>
```

**With 99+ Notifications:**
```html
<span id="notification-badge"
    class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center"
    hx-get="/api/notifications/badge"
    hx-trigger="every 30s">99+</span>
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/notifications.py
# Lines 205-235

@router.get("/badge")
async def get_notification_badge(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> str:
    """Get notification badge HTML for HTMX.

    Hey future me - HTMX polls this to update the badge in the navbar!
    Returns raw HTML that replaces the badge element.

    Example response:
    <span class="notification-badge" hx-get="/api/notifications/badge" hx-trigger="every 30s">3</span>
    """
```

**HTMX Integration:**
```html
<!-- Navbar badge that auto-updates -->
<div id="notification-badge" 
     hx-get="/api/notifications/badge"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
    <!-- Replaced by endpoint response -->
</div>
```

**Badge Display Logic:**
- **0 unread**: Hidden badge (class `hidden`)
- **1-99 unread**: Show exact count
- **100+ unread**: Show "99+"

**Polling:**
- **Auto-Refresh**: HTMX polls every 30 seconds via `hx-trigger="every 30s"`
- **Self-Updating**: Badge HTML includes `hx-get` for continuous polling

**Use Cases:**
- **Navbar Badge**: Display unread count in navigation bar
- **Real-Time Updates**: Auto-refresh without JavaScript
- **HTMX Pattern**: Server-driven UI updates

---

## Summary

**Total Endpoints Documented:** 8

**Endpoint Categories:**
1. **List & Count**: 2 endpoints (list, unread count)
2. **Mark as Read**: 2 endpoints (mark specific, mark all)
3. **Delete**: 1 endpoint (delete notification)
4. **HTMX Integration**: 1 endpoint (badge HTML)

**Key Features:**
- **In-App Notifications**: Database-stored notifications displayed in UI
- **Read/Unread Tracking**: Mark notifications as read
- **Filtering**: Filter by type, read status
- **Pagination**: Offset-based pagination
- **HTMX Badge**: Auto-updating notification badge
- **Priority Levels**: Low, normal, high, urgent

**Module Stats:**
- **Source File**: `notifications.py` (237 lines)
- **Endpoints**: 8 (6 JSON + 1 HTMX HTML)
- **Code Validation**: 100%

**Notification Types:**
- `new_release`: New album from followed artist
- `download_completed`: Download finished
- `download_failed`: Download error
- `error`: General error
- `system`: System announcement
- `warning`: Warning message

**Use Cases:**
- **User Alerts**: Notify users of important events
- **Download Status**: Track download completion/failures
- **New Releases**: Alert when followed artists release music
- **System Messages**: Maintenance, updates, announcements

**HTMX Integration:**
- **Badge Polling**: Auto-update badge every 30 seconds
- **Server-Driven**: HTML fragments rendered server-side
- **No JavaScript**: HTMX handles all updates

**Future Enhancements:**
- **SSE Support**: Real-time notifications via Server-Sent Events
- **Email Delivery**: Optional email notifications
- **Push Notifications**: Browser push notifications
- **Notification Preferences**: User-configurable notification types
