"""Notification provider interfaces for the notification service.

Hey future me - this is the PORT (interface) for notification providers!
Each provider implements this interface. The NotificationService uses
these providers to send notifications through different channels.

Architecture:
- NotificationService (Application Layer) → INotificationProvider (Port)
- EmailNotificationProvider, WebhookProvider, etc. → Implement INotificationProvider

This follows the Hexagonal Architecture pattern for dependency inversion.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NotificationType(str, Enum):
    """Types of notifications that can be sent.

    Hey future me - add new types here when you add new notification events!
    The type is used for filtering and provider routing.
    """
    NEW_RELEASE = "new_release"
    MISSING_ALBUM = "missing_album"
    QUALITY_UPGRADE = "quality_upgrade"
    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_COMPLETED = "download_completed"
    DOWNLOAD_FAILED = "download_failed"
    AUTOMATION_TRIGGERED = "automation_triggered"
    SYNC_COMPLETED = "sync_completed"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


class NotificationPriority(str, Enum):
    """Priority levels for notifications.

    Hey future me - providers can use this to decide urgency:
    - LOW: Batch together, send daily digest
    - NORMAL: Send when convenient (within minutes)
    - HIGH: Send immediately
    - CRITICAL: Wake up the user (push with sound)
    """
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Notification:
    """Notification data object for passing to providers.

    Hey future me - this is the PAYLOAD that providers receive!
    Keep it provider-agnostic. Each provider formats it for their channel.

    Example:
        notif = Notification(
            type=NotificationType.NEW_RELEASE,
            title="New Album Released",
            message="Artist - Album (2025)",
            priority=NotificationPriority.NORMAL,
            data={"artist_id": 123, "album_id": 456}
        )
    """
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime | None = None

    # Optional: For in-app notifications (stored in DB)
    user_id: str | None = None
    read: bool = False

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if self.timestamp is None:
            from datetime import UTC
            self.timestamp = datetime.now(UTC)


@dataclass
class NotificationResult:
    """Result of sending a notification.

    Hey future me - providers return this to indicate success/failure!
    The error field contains details if success=False.
    """
    success: bool
    provider_name: str
    notification_type: NotificationType
    error: str | None = None
    external_id: str | None = None  # ID from external service (e.g., email message ID)


class INotificationProvider(ABC):
    """Interface for notification providers.

    Hey future me - this is THE CONTRACT for all notification channels!
    Implement this for Email, Webhook, Push, In-App, etc.

    Each provider must:
    1. Have a unique name (for settings/routing)
    2. Declare which notification types it supports
    3. Implement send() to actually deliver the notification
    4. Implement is_configured() to check if credentials are set

    Example implementation:
        class EmailProvider(INotificationProvider):
            @property
            def name(self) -> str:
                return "email"

            async def send(self, notification: Notification) -> NotificationResult:
                # Send email via SMTP
                ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this provider (e.g., 'email', 'webhook', 'gotify')."""
        pass

    @property
    @abstractmethod
    def supported_types(self) -> list[NotificationType]:
        """List of notification types this provider can handle.

        Return empty list to support ALL types.
        """
        pass

    @abstractmethod
    async def send(self, notification: Notification) -> NotificationResult:
        """Send a notification through this provider.

        Args:
            notification: The notification to send

        Returns:
            NotificationResult indicating success/failure
        """
        pass

    @abstractmethod
    async def is_configured(self) -> bool:
        """Check if this provider is properly configured.

        Returns:
            True if provider has all required settings (credentials, URLs, etc.)
        """
        pass

    def supports(self, notification_type: NotificationType) -> bool:
        """Check if this provider supports a notification type.

        Args:
            notification_type: Type to check

        Returns:
            True if supported (or if provider supports all types)
        """
        supported = self.supported_types
        return len(supported) == 0 or notification_type in supported


# Export all public types
__all__ = [
    "NotificationType",
    "NotificationPriority",
    "Notification",
    "NotificationResult",
    "INotificationProvider",
]
