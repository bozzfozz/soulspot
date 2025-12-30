# Notifications

**Category:** Features  
**Status:** 🚧 Stub Implementation (Logging Only)  
**Last Updated:** 2025-12-12  
**Related Docs:** [Automation Watchlists](./automation-watchlists.md) | [Download Management](./download-management.md)

---

## Overview

Notification Service is currently a **stub implementation** that only writes to logs. Defines notification API for future integration with real notification providers (Email, Push, Webhooks, etc.).

**Current Status:** Logs all notifications with `[NOTIFICATION]` prefix  
**Future:** Integration with Email (SMTP), Webhooks (Discord/Slack), Push (FCM/APNS)

---

## Supported Notification Types

### New Release Notifications

```python
success = await notification_service.send_new_release_notification(
    artist_name="Radiohead",
    album_name="OK Computer (Deluxe)",
    release_date="2025-12-15"
)

# Current Output (Log):
# [NOTIFICATION] New release detected: Radiohead - OK Computer (Deluxe) (Released: 2025-12-15)
```

**Use Case:** Automation Watchlists detect new album → Notify user

---

### Missing Album Notifications

```python
success = await notification_service.send_missing_album_notification(
    artist_name="Pink Floyd",
    missing_count=3,
    total_count=15
)

# Current Output (Log):
# [NOTIFICATION] Discography incomplete for Pink Floyd: 3 of 15 albums missing (80.0% complete)
```

**Use Case:** Discography completeness check → Notify user of gaps

---

### Quality Upgrade Notifications

```python
success = await notification_service.send_quality_upgrade_notification(
    track_title="Airbag",
    current_quality="MP3 192kbps",
    target_quality="FLAC Lossless"
)

# Current Output (Log):
# [NOTIFICATION] Quality upgrade available for Airbag: MP3 192kbps → FLAC Lossless
```

**Use Case:** Quality upgrade detection → Notify user of better version

---

### Download Status Notifications

#### Download Started

```python
success = await notification_service.send_download_started_notification(
    item_name="Radiohead - OK Computer - 01 Airbag",
    quality_profile="FLAC Lossless"
)

# Current Output (Log):
# [NOTIFICATION] Download started: Radiohead - OK Computer - 01 Airbag (Quality: FLAC Lossless)
```

---

#### Download Completed

```python
success = await notification_service.send_download_completed_notification(
    item_name="Radiohead - OK Computer - 01 Airbag",
    success=True
)

# Current Output (Log):
# [NOTIFICATION] Download completed successfully: Radiohead - OK Computer - 01 Airbag
```

---

### Generic Automation Notifications

```python
success = await notification_service.send_automation_notification(
    trigger="new_release",
    context={
        "artist_id": "abc-123",
        "album_info": {"name": "OK Computer", "release_date": "2025-12-15"},
        "track_title": "Airbag"
    }
)

# Current Output (Log):
# [NOTIFICATION] Automation triggered: new_release at 2025-12-12T10:30:00Z | Artist: abc-123 | Album: OK Computer | Track: Airbag
```

**Use Case:** Flexible notification with arbitrary context data

---

## Current Implementation (Stub)

### Service Class

```python
class NotificationService:
    """Simple logging-based notification system (stub).
    
    Production integration targets:
    - Email notifications (SMTP)
    - Webhook notifications (Discord, Slack, custom URLs)
    - Push notifications (FCM, APNS)
    - In-app notifications (SSE, WebSocket)
    """
    
    def __init__(self) -> None:
        """Initialize with logging backend only."""
        pass  # No setup required for logging
    
    async def send_*_notification(...) -> bool:
        """All methods return True (logging doesn't fail)."""
        logger.info(f"[NOTIFICATION] {message}")
        return True
```

**Key Points:**
- All methods return `True` (logging can't fail)
- `[NOTIFICATION]` prefix for easy log filtering
- No external dependencies or configuration required

---

## Integration Points

### Automation Watchlists

```python
# Watchlist detects new release
if new_album_found:
    await notification_service.send_new_release_notification(
        artist_name=watchlist.artist_name,
        album_name=new_album.name,
        release_date=new_album.release_date
    )
```

---

### Download Manager

```python
# Download started
await notification_service.send_download_started_notification(
    item_name=f"{track.artist} - {track.title}",
    quality_profile=download.quality_profile
)

# Download completed
await notification_service.send_download_completed_notification(
    item_name=f"{track.artist} - {track.title}",
    success=(download.status == "completed")
)
```

---

### Quality Profile Service

```python
# Better version available
if upgrade_available:
    await notification_service.send_quality_upgrade_notification(
        track_title=track.title,
        current_quality=track.quality,
        target_quality=upgrade.quality
    )
```

---

## Future Implementation

### Email Notifications

```python
class EmailNotificationProvider:
    def __init__(self, smtp_host, smtp_port, username, password):
        self.client = smtplib.SMTP(smtp_host, smtp_port)
        self.username = username
        self.password = password
    
    async def send(self, subject, body, to_email):
        # Send via SMTP
        pass
```

---

### Webhook Notifications

```python
class WebhookNotificationProvider:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    async def send(self, payload):
        # POST to Discord/Slack webhook
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=payload)
```

---

### Push Notifications

```python
class PushNotificationProvider:
    def __init__(self, fcm_api_key):
        self.fcm_client = FCM(api_key=fcm_api_key)
    
    async def send(self, title, body, device_token):
        # Send via Firebase Cloud Messaging
        pass
```

---

## Related Documentation

- **[Automation Watchlists](./automation-watchlists.md)** - New release notifications
- **[Download Management](./download-management.md)** - Download status notifications

---

**Last Validated:** 2025-12-12  
**Implementation Status:** 🚧 Stub (Logging Only)
