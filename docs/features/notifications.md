# Notification System

> **Version:** 1.0  
> **Status:** 🚧 Stub Implementation (Logging Only)  
> **Last Updated:** 2025-12-12  
> **Service:** `src/soulspot/application/services/notification_service.py`

---

## Overview

Der Notification Service ist aktuell eine **Stub-Implementierung**, die nur in Logs schreibt. Er definiert die Notification-API für zukünftige Integration mit echten Notification-Providern (Email, Push, Webhooks, etc.).

**Current Status:** Logs alle Notifications mit `[NOTIFICATION]` Präfix  
**Future:** Integration mit Email (SMTP), Webhooks (Discord/Slack), Push Notifications (FCM/APNS)

---

## Supported Notification Types

### 1. New Release Notifications

```python
success = await notification_service.send_new_release_notification(
    artist_name="Radiohead",
    album_name="OK Computer (Deluxe)",
    release_date="2025-12-15"
)

# Current Output (Log):
# [NOTIFICATION] New release detected: Radiohead - OK Computer (Deluxe) (Released: 2025-12-15)
```

**Use Case:** Automation Watchlists detect new album release → Notify user

---

### 2. Missing Album Notifications

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

### 3. Quality Upgrade Notifications

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

### 4. Download Status Notifications

#### Download Started
```python
success = await notification_service.send_download_started_notification(
    item_name="Radiohead - OK Computer - 01 Airbag",
    quality_profile="FLAC Lossless"
)

# Current Output (Log):
# [NOTIFICATION] Download started: Radiohead - OK Computer - 01 Airbag (Quality: FLAC Lossless)
```

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

### 5. Generic Automation Notifications

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

### With Automation Watchlists

```python
from soulspot.application.services.automation_workflow_service import AutomationWorkflowService
from soulspot.application.services.notification_service import NotificationService

notification_service = NotificationService()
automation_service = AutomationWorkflowService(
    ...,
    notification_service=notification_service
)

# When new release detected
await automation_service.check_for_new_releases()
# → Sends notification via notification_service
```

### With Download Management

```python
from soulspot.application.services.download_service import DownloadService

notification_service = NotificationService()
download_service = DownloadService(
    ...,
    notification_service=notification_service
)

# When download starts/completes
await download_service.start_download(track_id)
# → Sends notification via notification_service
```

---

## Future Implementation Plan

### Phase 1: Email Notifications (SMTP)

```python
class EmailNotificationService(NotificationService):
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    async def send_new_release_notification(self, artist_name, album_name, release_date):
        message = MIMEText(
            f"New release: {artist_name} - {album_name}\n"
            f"Released: {release_date}"
        )
        message['Subject'] = f"New Release: {artist_name}"
        message['From'] = self.username
        message['To'] = user_email
        
        # Send via SMTP
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(message)
        
        return True
```

**Configuration:**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=soulspot@example.com
SMTP_PASSWORD=app_password
NOTIFICATION_EMAIL=user@example.com
```

---

### Phase 2: Webhook Notifications (Discord/Slack)

```python
class WebhookNotificationService(NotificationService):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_new_release_notification(self, artist_name, album_name, release_date):
        # Discord Webhook Format
        payload = {
            "embeds": [{
                "title": f"🎵 New Release: {artist_name}",
                "description": f"{album_name}",
                "fields": [
                    {"name": "Released", "value": release_date, "inline": True}
                ],
                "color": 0x8B5CF6  # Violet
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json=payload)
        
        return True
```

**Configuration:**
```bash
WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdef
# Or Slack: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX
```

---

### Phase 3: Push Notifications (FCM/APNS)

```python
class PushNotificationService(NotificationService):
    def __init__(self, fcm_credentials: dict):
        from firebase_admin import credentials, initialize_app
        cred = credentials.Certificate(fcm_credentials)
        initialize_app(cred)
    
    async def send_new_release_notification(self, artist_name, album_name, release_date):
        from firebase_admin import messaging
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"New Release: {artist_name}",
                body=f"{album_name} - Released: {release_date}"
            ),
            token=user_device_token
        )
        
        response = messaging.send(message)
        return response is not None
```

**Configuration:**
```bash
FCM_CREDENTIALS_PATH=/config/fcm-credentials.json
USER_DEVICE_TOKEN=user_fcm_token_here
```

---

### Phase 4: In-App Notifications (SSE)

```python
class InAppNotificationService(NotificationService):
    def __init__(self):
        self.notification_queue = asyncio.Queue()
    
    async def send_new_release_notification(self, artist_name, album_name, release_date):
        notification = {
            "type": "new_release",
            "title": f"New Release: {artist_name}",
            "message": f"{album_name} - Released: {release_date}",
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def stream_notifications(self):
        """SSE endpoint generator."""
        while True:
            notification = await self.notification_queue.get()
            yield f"data: {json.dumps(notification)}\n\n"
```

**Frontend Integration:**
```javascript
// JavaScript SSE client
const eventSource = new EventSource('/api/notifications/stream');
eventSource.onmessage = (event) => {
    const notification = JSON.parse(event.data);
    showNotification(notification.title, notification.message);
};
```

---

## Configuration Strategy

### Multi-Provider Support

```python
class MultiNotificationService(NotificationService):
    """Send notifications to multiple providers."""
    
    def __init__(self, providers: list[NotificationService]):
        self.providers = providers
    
    async def send_new_release_notification(self, artist_name, album_name, release_date):
        results = []
        for provider in self.providers:
            try:
                success = await provider.send_new_release_notification(
                    artist_name, album_name, release_date
                )
                results.append(success)
            except Exception as e:
                logger.error(f"Notification provider failed: {e}")
                results.append(False)
        
        # Return True if at least one provider succeeded
        return any(results)
```

**Usage:**
```python
notification_service = MultiNotificationService([
    EmailNotificationService(...),
    WebhookNotificationService(...),
    InAppNotificationService(...)
])
# → Sends to email, webhook, and in-app simultaneously
```

---

## Log Analysis (Current Implementation)

### Filtering Notifications

```bash
# All notifications
tail -f /var/log/soulspot.log | grep "\[NOTIFICATION\]"

# New releases only
tail -f /var/log/soulspot.log | grep "\[NOTIFICATION\]" | grep "New release"

# Download notifications
tail -f /var/log/soulspot.log | grep "\[NOTIFICATION\]" | grep "Download"

# Quality upgrades
tail -f /var/log/soulspot.log | grep "\[NOTIFICATION\]" | grep "Quality upgrade"
```

### Notification Metrics

```bash
# Count notifications by type
cat /var/log/soulspot.log | grep "\[NOTIFICATION\]" | cut -d' ' -f4- | sort | uniq -c

# Example Output:
#   15 New release detected: ...
#    5 Discography incomplete for ...
#   12 Quality upgrade available for ...
#   23 Download completed successfully: ...
```

---

## Testing Strategies

### Unit Tests (Current Stub)

```python
import pytest

@pytest.mark.asyncio
async def test_new_release_notification():
    service = NotificationService()
    success = await service.send_new_release_notification(
        artist_name="Test Artist",
        album_name="Test Album",
        release_date="2025-12-15"
    )
    assert success is True  # Always True for stub

@pytest.mark.asyncio
async def test_missing_album_notification():
    service = NotificationService()
    success = await service.send_missing_album_notification(
        artist_name="Test Artist",
        missing_count=3,
        total_count=10
    )
    assert success is True
```

### Integration Tests (Future)

```python
@pytest.mark.asyncio
async def test_email_notification_integration():
    # Use test SMTP server
    service = EmailNotificationService(
        smtp_host="localhost",
        smtp_port=1025,  # MailHog test server
        username="test@example.com",
        password="test"
    )
    
    success = await service.send_new_release_notification(
        artist_name="Test Artist",
        album_name="Test Album",
        release_date="2025-12-15"
    )
    
    assert success is True
    # Verify email received in MailHog
```

---

## Migration Path (Stub → Production)

### Step 1: Add Configuration

```python
# settings.py
class NotificationSettings(BaseSettings):
    enabled: bool = False
    provider: str = "logging"  # logging, email, webhook, push, multi
    
    # Email
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    
    # Webhook
    webhook_url: str | None = None
    
    # Push
    fcm_credentials_path: str | None = None
```

### Step 2: Provider Factory

```python
def create_notification_service(settings: NotificationSettings) -> NotificationService:
    """Factory for notification service based on config."""
    if not settings.enabled:
        return NotificationService()  # Stub (logging only)
    
    match settings.provider:
        case "email":
            return EmailNotificationService(
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password
            )
        case "webhook":
            return WebhookNotificationService(settings.webhook_url)
        case "push":
            return PushNotificationService(settings.fcm_credentials_path)
        case "multi":
            providers = []
            if settings.smtp_host:
                providers.append(EmailNotificationService(...))
            if settings.webhook_url:
                providers.append(WebhookNotificationService(...))
            return MultiNotificationService(providers)
        case _:
            return NotificationService()  # Default to stub
```

### Step 3: Gradual Rollout

```python
# Phase 1: Enable logging only (current)
NOTIFICATION_ENABLED=false

# Phase 2: Enable email for admins
NOTIFICATION_ENABLED=true
NOTIFICATION_PROVIDER=email
SMTP_HOST=smtp.gmail.com

# Phase 3: Add webhook for monitoring
NOTIFICATION_PROVIDER=multi
WEBHOOK_URL=https://discord.com/...

# Phase 4: Full production (email + webhook + in-app)
NOTIFICATION_PROVIDER=multi
```

---

## Related Features

- **[Automation & Watchlists](./automation-watchlists.md)** - Triggers new release notifications
- **[Download Management](./download-management.md)** - Triggers download status notifications
- **[Settings](./settings.md)** - Notification configuration UI

---

## Troubleshooting

### "Notifications not received"
**Current Behavior:** Expected - stub only logs  
**Future:** Check provider configuration (SMTP credentials, webhook URL, etc.)

### "Log file too large (notifications spam)"
**Symptom:** Logs grow quickly with many notifications  
**Solution:** Log rotation + notification filtering
```bash
# Logrotate config
/var/log/soulspot.log {
    daily
    rotate 7
    compress
    missingok
}
```

### "Need to disable notifications"
**Current:** Can't disable (always logs)  
**Future:** Set `NOTIFICATION_ENABLED=false` in config

---

**Version:** 1.0 · **Status:** Stub (Logging Only) · **Service:** `notification_service.py` · **TODO:** Implement real providers (Email, Webhook, Push)
