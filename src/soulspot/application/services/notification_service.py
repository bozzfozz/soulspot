"""Notification service for sending notifications through multiple providers.

Hey future me - this is the MAIN ENTRY POINT for notifications!
It orchestrates multiple providers (Email, Webhook, In-App) and sends to all configured ones.

Architecture:
- NotificationService (this) uses INotificationProvider interface
- Providers implement the actual sending (Email, Webhook, InApp)
- Settings stored in app_settings DB table

Usage:
    notification_service = NotificationService(session)
    await notification_service.send_new_release_notification("Artist", "Album", "2025-01-01")

The service will automatically:
1. Load enabled providers from settings
2. Build Notification object
3. Send to ALL configured providers (parallel)
4. Log results and return success status
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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


class NotificationService:
    """Service for sending notifications through multiple providers.

    Hey future me - this orchestrates Email, Webhook, and In-App notifications!
    Each notification is sent to ALL enabled providers in parallel.

    Providers are initialized lazily and cached. Call invalidate_providers()
    after settings change to reload them.

    Example:
        service = NotificationService(session)

        # Send new release notification
        await service.send_new_release_notification("Radiohead", "Kid A", "2000-10-02")

        # Send custom notification
        await service.send_notification(
            notification_type=NotificationType.CUSTOM,
            title="Custom Event",
            message="Something happened!",
            data={"key": "value"},
        )
    """

    def __init__(self, session: "AsyncSession | None" = None) -> None:
        """Initialize notification service.

        Args:
            session: Optional SQLAlchemy async session. If not provided,
                    falls back to logging-only mode for backward compatibility.
        """
        self._session = session
        self._providers: list[INotificationProvider] | None = None
        self._providers_initialized = False

    async def _init_providers(self) -> list[INotificationProvider]:
        """Initialize and return enabled providers.

        Hey future me - this lazily initializes providers on first use!
        Caches the list to avoid re-initialization on every notification.
        """
        if self._providers_initialized and self._providers is not None:
            return self._providers

        self._providers = []

        if self._session is None:
            # No session = logging-only mode (backward compatibility)
            logger.debug("[NOTIFICATION] No session provided, logging-only mode")
            self._providers_initialized = True
            return self._providers

        # Import providers
        from soulspot.infrastructure.notifications import (
            InAppNotificationProvider,
            WebhookNotificationProvider,
        )

        # Initialize all providers
        all_providers: list[INotificationProvider] = [
            WebhookNotificationProvider(self._session),
            InAppNotificationProvider(self._session),
        ]

        # Filter to only configured providers
        for provider in all_providers:
            try:
                if await provider.is_configured():
                    self._providers.append(provider)
                    logger.debug(f"[NOTIFICATION] Provider enabled: {provider.name}")
            except Exception as e:
                logger.warning(f"[NOTIFICATION] Failed to check provider {provider.name}: {e}")

        self._providers_initialized = True
        return self._providers

    def invalidate_providers(self) -> None:
        """Invalidate provider cache to force reload.

        Call this after notification settings change.
        """
        self._providers = None
        self._providers_initialized = False

    async def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Send notification to all configured providers.

        Hey future me - this is the CORE method! All other send_* methods call this.

        Args:
            notification_type: Type of notification
            title: Short title
            message: Full message body
            priority: Priority level (affects delivery urgency)
            data: Optional additional data (shown in details)
            user_id: Optional user ID for in-app notifications

        Returns:
            True if at least one provider succeeded
        """
        # Build notification object
        notification = Notification(
            type=notification_type,
            title=title,
            message=message,
            priority=priority,
            data=data or {},
            user_id=user_id,
            timestamp=datetime.now(UTC),
        )

        # Always log (backward compatibility)
        logger.info(f"[NOTIFICATION] {notification_type.value}: {title} - {message[:100]}...")

        # Get enabled providers
        providers = await self._init_providers()

        if not providers:
            logger.debug("[NOTIFICATION] No providers configured, logged only")
            return True  # Logging succeeded

        # Send to all providers in parallel
        results = await self._send_to_providers(notification, providers)

        # Log results
        successes = sum(1 for r in results if r.success)
        failures = sum(1 for r in results if not r.success)

        if failures > 0:
            failed_providers = [r.provider_name for r in results if not r.success]
            logger.warning(
                f"[NOTIFICATION] {successes}/{len(results)} providers succeeded, "
                f"failed: {failed_providers}"
            )

        return successes > 0

    async def _send_to_providers(
        self, notification: Notification, providers: list[INotificationProvider]
    ) -> list[NotificationResult]:
        """Send notification to multiple providers in parallel.

        Hey future me - uses asyncio.gather for parallel sending!
        One slow provider won't block others.
        """
        tasks = []

        for provider in providers:
            if provider.supports(notification.type):
                tasks.append(self._send_to_provider(provider, notification))

        if not tasks:
            return []

        # Run all sends in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to NotificationResults
        final_results: list[NotificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                provider_name = providers[i].name if i < len(providers) else "unknown"
                final_results.append(
                    NotificationResult(
                        success=False,
                        provider_name=provider_name,
                        notification_type=notification.type,
                        error=str(result),
                    )
                )
            elif isinstance(result, NotificationResult):
                final_results.append(result)

        return final_results

    async def _send_to_provider(
        self, provider: INotificationProvider, notification: Notification
    ) -> NotificationResult:
        """Send to a single provider with error handling.

        Hey future me - wraps provider.send() with try/except!
        Individual provider failures don't crash the whole service.
        """
        try:
            return await provider.send(notification)
        except Exception as e:
            logger.error(f"[NOTIFICATION] Provider {provider.name} error: {e}")
            return NotificationResult(
                success=False,
                provider_name=provider.name,
                notification_type=notification.type,
                error=str(e),
            )

    # =========================================================================
    # CONVENIENCE METHODS (backward compatible API)
    # =========================================================================
    # Hey future me - these wrap send_notification() with pre-built messages!
    # They maintain the same API as the old logging-only version.
    # =========================================================================

    async def send_new_release_notification(
        self, artist_name: str, album_name: str, release_date: str
    ) -> bool:
        """Send notification about a new release.

        Args:
            artist_name: Name of the artist
            album_name: Name of the album
            release_date: Release date

        Returns:
            True if notification was sent successfully
        """
        return await self.send_notification(
            notification_type=NotificationType.NEW_RELEASE,
            title=f"New Release: {artist_name}",
            message=f"{artist_name} released a new album: {album_name} (Released: {release_date})",
            priority=NotificationPriority.NORMAL,
            data={
                "artist_name": artist_name,
                "album_name": album_name,
                "release_date": release_date,
            },
        )

    async def send_missing_album_notification(
        self, artist_name: str, missing_count: int, total_count: int
    ) -> bool:
        """Send notification about missing albums.

        Args:
            artist_name: Name of the artist
            missing_count: Number of missing albums
            total_count: Total number of albums

        Returns:
            True if notification was sent successfully
        """
        completeness = (
            ((total_count - missing_count) / total_count * 100)
            if total_count > 0
            else 0
        )

        return await self.send_notification(
            notification_type=NotificationType.MISSING_ALBUM,
            title=f"Incomplete Discography: {artist_name}",
            message=(
                f"Your library is missing {missing_count} of {total_count} albums "
                f"from {artist_name} ({completeness:.1f}% complete)"
            ),
            priority=NotificationPriority.LOW,
            data={
                "artist_name": artist_name,
                "missing_count": missing_count,
                "total_count": total_count,
                "completeness": f"{completeness:.1f}%",
            },
        )

    async def send_quality_upgrade_notification(
        self, track_title: str, current_quality: str, target_quality: str
    ) -> bool:
        """Send notification about quality upgrade opportunity.

        Args:
            track_title: Title of the track
            current_quality: Current quality (format and bitrate)
            target_quality: Target quality (format and bitrate)

        Returns:
            True if notification was sent successfully
        """
        return await self.send_notification(
            notification_type=NotificationType.QUALITY_UPGRADE,
            title="Quality Upgrade Available",
            message=(
                f"A higher quality version of '{track_title}' is available: "
                f"{current_quality} → {target_quality}"
            ),
            priority=NotificationPriority.LOW,
            data={
                "track_title": track_title,
                "current_quality": current_quality,
                "target_quality": target_quality,
            },
        )

    async def send_automation_notification(
        self, trigger: str, context: dict[str, Any]
    ) -> bool:
        """Send generic automation notification.

        Args:
            trigger: Trigger type (new_release, missing_album, quality_upgrade)
            context: Context information

        Returns:
            True if notification was sent successfully
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build message from context
        message_parts = [f"Automation rule '{trigger}' triggered at {timestamp}"]

        if "artist_id" in context:
            message_parts.append(f"Artist: {context['artist_id']}")
        if "album_info" in context:
            album_name = context["album_info"].get("name", "Unknown")
            message_parts.append(f"Album: {album_name}")
        if "track_title" in context:
            message_parts.append(f"Track: {context['track_title']}")

        return await self.send_notification(
            notification_type=NotificationType.AUTOMATION_TRIGGERED,
            title=f"Automation: {trigger}",
            message="\n".join(message_parts),
            priority=NotificationPriority.NORMAL,
            data=context,
        )

    async def send_download_started_notification(
        self, item_name: str, quality_profile: str
    ) -> bool:
        """Send notification about download starting.

        Args:
            item_name: Name of the item being downloaded
            quality_profile: Quality profile used

        Returns:
            True if notification was sent successfully
        """
        return await self.send_notification(
            notification_type=NotificationType.DOWNLOAD_STARTED,
            title="Download Started",
            message=f"Downloading: {item_name} (Quality: {quality_profile})",
            priority=NotificationPriority.NORMAL,
            data={
                "item_name": item_name,
                "quality_profile": quality_profile,
            },
        )

    async def send_download_completed_notification(
        self, item_name: str, success: bool
    ) -> bool:
        """Send notification about download completion.

        Args:
            item_name: Name of the item downloaded
            success: Whether download was successful

        Returns:
            True if notification was sent successfully
        """
        notification_type = (
            NotificationType.DOWNLOAD_COMPLETED if success
            else NotificationType.DOWNLOAD_FAILED
        )
        priority = (
            NotificationPriority.NORMAL if success
            else NotificationPriority.HIGH
        )
        status = "completed successfully" if success else "failed"

        return await self.send_notification(
            notification_type=notification_type,
            title=f"Download {'Complete' if success else 'Failed'}",
            message=f"Download {status}: {item_name}",
            priority=priority,
            data={
                "item_name": item_name,
                "success": success,
            },
        )

    async def send_sync_completed_notification(
        self, service_name: str, items_synced: int, errors: int = 0
    ) -> bool:
        """Send notification about sync completion.

        Args:
            service_name: Name of the service (e.g., 'Spotify', 'Deezer')
            items_synced: Number of items synced
            errors: Number of errors encountered

        Returns:
            True if notification was sent successfully
        """
        priority = NotificationPriority.NORMAL if errors == 0 else NotificationPriority.HIGH
        status = "completed" if errors == 0 else f"completed with {errors} errors"

        return await self.send_notification(
            notification_type=NotificationType.SYNC_COMPLETED,
            title=f"{service_name} Sync Complete",
            message=f"{service_name} sync {status}. {items_synced} items processed.",
            priority=priority,
            data={
                "service_name": service_name,
                "items_synced": items_synced,
                "errors": errors,
            },
        )

    async def send_system_error_notification(
        self, error_type: str, error_message: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Send notification about a system error.

        Args:
            error_type: Type of error (e.g., 'DatabaseError', 'APIError')
            error_message: Error message
            context: Optional context data

        Returns:
            True if notification was sent successfully
        """
        return await self.send_notification(
            notification_type=NotificationType.SYSTEM_ERROR,
            title=f"System Error: {error_type}",
            message=error_message,
            priority=NotificationPriority.CRITICAL,
            data=context or {},
        )


# Backward compatibility: Keep old interface working
__all__ = ["NotificationService"]
