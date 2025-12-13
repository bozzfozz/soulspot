"""Notification providers package.

Hey future me - this package contains all notification provider implementations!
Each provider sends notifications through a different channel:
- webhook_provider: Discord/Slack/Gotify/Generic webhooks
- inapp_provider: Database-backed in-app notifications

Add new providers here and register them in NotificationService.
"""

from soulspot.infrastructure.notifications.inapp_provider import (
    InAppNotificationProvider,
)
from soulspot.infrastructure.notifications.webhook_provider import (
    WebhookNotificationProvider,
)

__all__ = [
    "WebhookNotificationProvider",
    "InAppNotificationProvider",
]
