"""Webhook notification provider for Discord, Slack, Gotify, and generic webhooks.

Hey future me - this sends notifications to external services via HTTP webhooks!
Supports multiple webhook formats:
- Discord: Rich embeds with colors and fields
- Slack: Block-based messages with attachments
- Gotify: Self-hosted push notification server
- Generic: Simple JSON POST

Configure via app_settings:
- notification.webhook.enabled
- notification.webhook.url
- notification.webhook.format (discord, slack, gotify, generic)
- notification.webhook.auth_header (optional, e.g., 'Bearer <token>')
"""

import logging
from typing import TYPE_CHECKING, Any

import httpx

from soulspot.domain.ports.notification import (
    INotificationProvider,
    Notification,
    NotificationPriority,
    NotificationResult,
    NotificationType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WebhookNotificationProvider(INotificationProvider):
    """Webhook notification provider for Discord/Slack/Gotify/Generic.

    Hey future me - this is VERY flexible! Supports multiple formats:

    Discord:
        - Rich embeds with colors and fields
        - URL: https://discord.com/api/webhooks/<id>/<token>

    Slack:
        - Block-based messages
        - URL: https://hooks.slack.com/services/<id>/<token>

    Gotify:
        - Self-hosted push notifications
        - URL: https://gotify.example.com/message?token=<app-token>

    Generic:
        - Simple JSON POST with notification data
        - Works with n8n, Zapier, custom endpoints

    Config keys in app_settings:
        notification.webhook.enabled: bool
        notification.webhook.url: str
        notification.webhook.format: str (discord, slack, gotify, generic)
        notification.webhook.auth_header: str (optional, e.g., 'Bearer <token>')
        notification.webhook.timeout: int (default 30)
    """

    def __init__(self, session: "AsyncSession") -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy async session for loading config
        """
        self._session = session
        self._settings_cache: dict[str, Any] = {}
        self._cache_loaded = False

    @property
    def name(self) -> str:
        """Provider name."""
        return "webhook"

    @property
    def supported_types(self) -> list[NotificationType]:
        """Webhook supports all notification types."""
        return []

    async def _load_settings(self) -> None:
        """Load webhook settings from database."""
        if self._cache_loaded:
            return

        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )

        settings_service = AppSettingsService(self._session)

        self._settings_cache = {
            "enabled": await settings_service.get_bool("notification.webhook.enabled", False),
            "url": await settings_service.get_str("notification.webhook.url", ""),
            "format": await settings_service.get_str("notification.webhook.format", "generic"),
            "auth_header": await settings_service.get_str("notification.webhook.auth_header", ""),
            "timeout": await settings_service.get_int("notification.webhook.timeout", 30),
        }
        self._cache_loaded = True

    def invalidate_cache(self) -> None:
        """Invalidate settings cache."""
        self._cache_loaded = False
        self._settings_cache.clear()

    async def is_configured(self) -> bool:
        """Check if webhook is configured."""
        await self._load_settings()

        url = self._settings_cache.get("url", "")
        enabled = self._settings_cache.get("enabled", False)

        return bool(enabled and url and isinstance(url, str) and url.strip())

    async def send(self, notification: Notification) -> NotificationResult:
        """Send notification via webhook.

        Args:
            notification: Notification to send

        Returns:
            NotificationResult with success status
        """
        await self._load_settings()

        if not await self.is_configured():
            return NotificationResult(
                success=False,
                provider_name=self.name,
                notification_type=notification.type,
                error="Webhook provider not configured",
            )

        try:
            webhook_format = str(self._settings_cache.get("format", "generic")).lower()

            # Build payload based on format
            payload = self._build_payload(notification, webhook_format)

            # Send HTTP request
            response = await self._send_request(payload)

            logger.info(
                f"[NOTIFICATION] Webhook sent ({webhook_format}): "
                f"{notification.type.value} - {notification.title[:50]}..."
            )

            return NotificationResult(
                success=True,
                provider_name=self.name,
                notification_type=notification.type,
                external_id=response,
            )

        except Exception as e:
            logger.error(f"[NOTIFICATION] Webhook failed: {e}")
            return NotificationResult(
                success=False,
                provider_name=self.name,
                notification_type=notification.type,
                error=str(e),
            )

    def _build_payload(self, notification: Notification, format_type: str) -> dict[str, Any]:
        """Build webhook payload based on format type.

        Hey future me - add new formats here! Each service has its own structure.
        """
        if format_type == "discord":
            return self._build_discord_payload(notification)
        elif format_type == "slack":
            return self._build_slack_payload(notification)
        elif format_type == "gotify":
            return self._build_gotify_payload(notification)
        else:
            return self._build_generic_payload(notification)

    def _build_discord_payload(self, notification: Notification) -> dict[str, Any]:
        """Build Discord webhook payload with rich embed.

        Hey future me - Discord embeds are pretty! Colors, fields, timestamps.
        Limit: 6000 chars total, 25 fields max, 256 chars for field name.
        """
        # Color based on priority
        priority_colors = {
            NotificationPriority.LOW: 0x6C757D,       # Gray
            NotificationPriority.NORMAL: 0x0D6EFD,    # Blue
            NotificationPriority.HIGH: 0xFD7E14,      # Orange
            NotificationPriority.CRITICAL: 0xDC3545,  # Red
        }

        # Emoji for notification type
        type_emojis = {
            NotificationType.NEW_RELEASE: "🎵",
            NotificationType.MISSING_ALBUM: "📀",
            NotificationType.QUALITY_UPGRADE: "⬆️",
            NotificationType.DOWNLOAD_STARTED: "⬇️",
            NotificationType.DOWNLOAD_COMPLETED: "✅",
            NotificationType.DOWNLOAD_FAILED: "❌",
            NotificationType.AUTOMATION_TRIGGERED: "🤖",
            NotificationType.SYNC_COMPLETED: "🔄",
            NotificationType.SYSTEM_ERROR: "⚠️",
            NotificationType.CUSTOM: "📬",
        }

        emoji = type_emojis.get(notification.type, "📬")
        color = priority_colors.get(notification.priority, 0x0D6EFD)

        # Build fields from data
        fields = []
        for key, value in (notification.data or {}).items():
            if len(fields) < 25:  # Discord limit
                fields.append({
                    "name": str(key)[:256],
                    "value": str(value)[:1024],
                    "inline": True,
                })

        embed: dict[str, Any] = {
            "title": f"{emoji} {notification.title}"[:256],
            "description": notification.message[:4096],
            "color": color,
            "timestamp": (
                notification.timestamp.isoformat()
                if notification.timestamp
                else None
            ),
            "footer": {
                "text": f"SoulSpot • {notification.type.value}",
            },
        }

        if fields:
            embed["fields"] = fields

        return {
            "embeds": [embed],
        }

    def _build_slack_payload(self, notification: Notification) -> dict[str, Any]:
        """Build Slack webhook payload with blocks.

        Hey future me - Slack uses "blocks" for rich messages.
        Keep it simple - a header, text section, and optional context.
        """
        # Priority emoji
        priority_emoji = {
            NotificationPriority.LOW: "🔵",
            NotificationPriority.NORMAL: "🟢",
            NotificationPriority.HIGH: "🟠",
            NotificationPriority.CRITICAL: "🔴",
        }

        emoji = priority_emoji.get(notification.priority, "🟢")

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {notification.title}"[:150],
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": notification.message[:3000],
                },
            },
        ]

        # Add fields if data exists
        if notification.data:
            fields = [
                {
                    "type": "mrkdwn",
                    "text": f"*{k}:* {v}",
                }
                for k, v in list(notification.data.items())[:10]
            ]
            blocks.append({
                "type": "section",
                "fields": fields,
            })

        # Add context with timestamp and type
        timestamp_str = (
            notification.timestamp.strftime("%Y-%m-%d %H:%M UTC")
            if notification.timestamp
            else "N/A"
        )
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📍 {notification.type.value} • 🕐 {timestamp_str}",
                },
            ],
        })

        return {"blocks": blocks}

    def _build_gotify_payload(self, notification: Notification) -> dict[str, Any]:
        """Build Gotify push notification payload.

        Hey future me - Gotify is a self-hosted push notification server!
        Simple structure: title, message, priority (0-10).
        Priority 4+ triggers push notifications on mobile.
        """
        # Map our priority to Gotify's 0-10 scale
        gotify_priority = {
            NotificationPriority.LOW: 2,
            NotificationPriority.NORMAL: 5,
            NotificationPriority.HIGH: 7,
            NotificationPriority.CRITICAL: 10,
        }

        # Build message with extra details
        message_parts = [notification.message]

        if notification.data:
            details = " | ".join(f"{k}: {v}" for k, v in notification.data.items())
            message_parts.append(f"\nDetails: {details}")

        return {
            "title": f"[{notification.type.value}] {notification.title}",
            "message": "\n".join(message_parts),
            "priority": gotify_priority.get(notification.priority, 5),
            "extras": {
                "client::notification": {
                    "click": {"url": "soulspot://notification"},
                },
            },
        }

    def _build_generic_payload(self, notification: Notification) -> dict[str, Any]:
        """Build generic JSON payload.

        Hey future me - this is the fallback for custom webhooks!
        Just dumps the notification as JSON. Works with n8n, Zapier, etc.
        """
        return {
            "type": notification.type.value,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value,
            "timestamp": (
                notification.timestamp.isoformat()
                if notification.timestamp
                else None
            ),
            "data": notification.data or {},
            "source": "soulspot",
        }

    async def _send_request(self, payload: dict[str, Any]) -> str | None:
        """Send HTTP POST request to webhook URL.

        Hey future me - uses httpx for async HTTP. Handles auth headers too.
        Returns response text for logging/debugging.
        """
        url = str(self._settings_cache.get("url", ""))
        auth_header = str(self._settings_cache.get("auth_header", ""))
        timeout = int(self._settings_cache.get("timeout", 30))

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SoulSpot/1.0",
        }

        if auth_header:
            headers["Authorization"] = auth_header

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            return response.text[:200] if response.text else None


__all__ = ["WebhookNotificationProvider"]
