"""Unit tests for NotificationService.

Hey future me - these tests verify the notification service works correctly!
Tests are split into:
1. Backward compatibility tests (logging-only mode without session)
2. Provider integration tests (with mock providers)
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from soulspot.application.services.notification_service import NotificationService
from soulspot.domain.ports.notification import (
    Notification,
    NotificationPriority,
    NotificationResult,
    NotificationType,
)


class TestNotificationService:
    """Test suite for NotificationService."""

    @pytest.fixture
    def service(self) -> NotificationService:
        """Create a NotificationService instance for testing."""
        return NotificationService()

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create a mock logger for testing."""
        return MagicMock(spec=logging.Logger)

    async def test_send_new_release_notification_success(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending new release notification."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_new_release_notification(
                artist_name="The Beatles",
                album_name="Abbey Road",
                release_date="1969-09-26",
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "The Beatles" in call_args
            assert "Abbey Road" in call_args
            assert "1969-09-26" in call_args

    async def test_send_missing_album_notification_success(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending missing album notification."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_missing_album_notification(
                artist_name="Pink Floyd", missing_count=3, total_count=15
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "Pink Floyd" in call_args
            assert "3 of 15 albums missing" in call_args
            assert "80.0% complete" in call_args

    async def test_send_missing_album_notification_zero_total(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test missing album notification with zero total count."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_missing_album_notification(
                artist_name="New Artist", missing_count=0, total_count=0
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "0.0% complete" in call_args

    async def test_send_quality_upgrade_notification_success(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending quality upgrade notification."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_quality_upgrade_notification(
                track_title="Bohemian Rhapsody",
                current_quality="MP3 320kbps",
                target_quality="FLAC Lossless",
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "Bohemian Rhapsody" in call_args
            assert "MP3 320kbps → FLAC Lossless" in call_args

    async def test_send_automation_notification_minimal_context(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with minimal context."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="new_release", context={}
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "new_release" in call_args

    async def test_send_automation_notification_with_artist_id(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with artist ID in context."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="new_release", context={"artist_id": "spotify:artist:123"}
            )

            assert result is True
            call_args = mock_logger.info.call_args[0][0]
            assert "Artist: spotify:artist:123" in call_args

    async def test_send_automation_notification_with_album_info(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with album info in context."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="missing_album",
                context={"album_info": {"name": "Dark Side of the Moon"}},
            )

            assert result is True
            call_args = mock_logger.info.call_args[0][0]
            assert "Album: Dark Side of the Moon" in call_args

    async def test_send_automation_notification_with_album_info_no_name(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with album info but no name."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="missing_album", context={"album_info": {}}
            )

            assert result is True
            call_args = mock_logger.info.call_args[0][0]
            assert "Album: Unknown" in call_args

    async def test_send_automation_notification_with_track_title(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with track title in context."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="quality_upgrade", context={"track_title": "Stairway to Heaven"}
            )

            assert result is True
            call_args = mock_logger.info.call_args[0][0]
            assert "Track: Stairway to Heaven" in call_args

    async def test_send_automation_notification_with_all_context(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test automation notification with all context fields."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_automation_notification(
                trigger="new_release",
                context={
                    "artist_id": "spotify:artist:456",
                    "album_info": {"name": "Led Zeppelin IV"},
                    "track_title": "Black Dog",
                },
            )

            assert result is True
            call_args = mock_logger.info.call_args[0][0]
            assert "Artist: spotify:artist:456" in call_args
            assert "Album: Led Zeppelin IV" in call_args
            assert "Track: Black Dog" in call_args

    async def test_send_download_started_notification_success(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending download started notification."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_download_started_notification(
                item_name="Hotel California - Eagles", quality_profile="FLAC Lossless"
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "Download started" in call_args
            assert "Hotel California - Eagles" in call_args
            assert "FLAC Lossless" in call_args

    async def test_send_download_completed_notification_success(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending download completed notification with success."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_download_completed_notification(
                item_name="Comfortably Numb - Pink Floyd", success=True
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "completed successfully" in call_args
            assert "Comfortably Numb - Pink Floyd" in call_args

    async def test_send_download_completed_notification_failure(
        self, service: NotificationService, mock_logger: MagicMock
    ):
        """Test sending download completed notification with failure."""
        with patch(
            "soulspot.application.services.notification_service.logger", mock_logger
        ):
            result = await service.send_download_completed_notification(
                item_name="Wish You Were Here - Pink Floyd", success=False
            )

            assert result is True
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[NOTIFICATION]" in call_args
            assert "failed" in call_args
            assert "Wish You Were Here - Pink Floyd" in call_args

    async def test_notification_service_initialization(self):
        """Test NotificationService initialization."""
        service = NotificationService()
        assert service is not None
        assert isinstance(service, NotificationService)


class TestNotificationServiceWithProviders:
    """Test NotificationService with mock providers.
    
    Hey future me - these tests verify the provider orchestration works!
    """

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def service_with_session(self, mock_session: MagicMock) -> NotificationService:
        """Create NotificationService with mock session."""
        return NotificationService(mock_session)

    def test_init_with_session(
        self, service_with_session: NotificationService, mock_session: MagicMock
    ) -> None:
        """Test initialization with database session."""
        assert service_with_session._session == mock_session
        assert service_with_session._providers is None
        assert service_with_session._providers_initialized is False

    def test_invalidate_providers(
        self, service_with_session: NotificationService
    ) -> None:
        """Test that invalidate_providers resets the cache."""
        service_with_session._providers = []
        service_with_session._providers_initialized = True

        service_with_session.invalidate_providers()

        assert service_with_session._providers is None
        assert service_with_session._providers_initialized is False

    async def test_init_providers_no_session(self) -> None:
        """Test provider init returns empty list when no session."""
        service = NotificationService()  # No session
        providers = await service._init_providers()

        assert providers == []
        assert service._providers_initialized is True

    async def test_send_notification_with_provider(
        self, service_with_session: NotificationService
    ) -> None:
        """Test sending notification to a provider."""
        # Create mock provider
        mock_provider = MagicMock()
        mock_provider.name = "test_provider"
        mock_provider.supports.return_value = True
        mock_provider.send = AsyncMock(
            return_value=NotificationResult(
                success=True,
                provider_name="test_provider",
                notification_type=NotificationType.NEW_RELEASE,
            )
        )

        # Inject mock provider
        service_with_session._providers = [mock_provider]
        service_with_session._providers_initialized = True

        result = await service_with_session.send_notification(
            notification_type=NotificationType.NEW_RELEASE,
            title="Test Title",
            message="Test Message",
            priority=NotificationPriority.HIGH,
            data={"key": "value"},
        )

        assert result is True
        mock_provider.send.assert_called_once()

        # Verify notification was built correctly
        call_args = mock_provider.send.call_args[0][0]
        assert isinstance(call_args, Notification)
        assert call_args.type == NotificationType.NEW_RELEASE
        assert call_args.title == "Test Title"
        assert call_args.priority == NotificationPriority.HIGH

    async def test_send_notification_provider_failure(
        self, service_with_session: NotificationService
    ) -> None:
        """Test handling of provider failure."""
        mock_provider = MagicMock()
        mock_provider.name = "failing_provider"
        mock_provider.supports.return_value = True
        mock_provider.send = AsyncMock(
            return_value=NotificationResult(
                success=False,
                provider_name="failing_provider",
                notification_type=NotificationType.NEW_RELEASE,
                error="Connection failed",
            )
        )

        service_with_session._providers = [mock_provider]
        service_with_session._providers_initialized = True

        result = await service_with_session.send_notification(
            notification_type=NotificationType.NEW_RELEASE,
            title="Test",
            message="Test",
        )

        # Returns False when all providers fail
        assert result is False

    async def test_send_notification_partial_success(
        self, service_with_session: NotificationService
    ) -> None:
        """Test partial success with multiple providers."""
        success_provider = MagicMock()
        success_provider.name = "success"
        success_provider.supports.return_value = True
        success_provider.send = AsyncMock(
            return_value=NotificationResult(
                success=True,
                provider_name="success",
                notification_type=NotificationType.NEW_RELEASE,
            )
        )

        fail_provider = MagicMock()
        fail_provider.name = "fail"
        fail_provider.supports.return_value = True
        fail_provider.send = AsyncMock(
            return_value=NotificationResult(
                success=False,
                provider_name="fail",
                notification_type=NotificationType.NEW_RELEASE,
                error="Failed",
            )
        )

        service_with_session._providers = [success_provider, fail_provider]
        service_with_session._providers_initialized = True

        result = await service_with_session.send_notification(
            notification_type=NotificationType.NEW_RELEASE,
            title="Test",
            message="Test",
        )

        # Returns True if at least one provider succeeds
        assert result is True

    async def test_provider_exception_handling(
        self, service_with_session: NotificationService
    ) -> None:
        """Test that provider exceptions don't crash the service."""
        mock_provider = MagicMock()
        mock_provider.name = "crashing"
        mock_provider.supports.return_value = True
        mock_provider.send = AsyncMock(side_effect=Exception("Provider crashed"))

        service_with_session._providers = [mock_provider]
        service_with_session._providers_initialized = True

        # Should not raise, should return False
        result = await service_with_session.send_notification(
            notification_type=NotificationType.NEW_RELEASE,
            title="Test",
            message="Test",
        )

        assert result is False

    async def test_send_sync_completed_notification(self) -> None:
        """Test send_sync_completed_notification method."""
        service = NotificationService()

        result = await service.send_sync_completed_notification(
            service_name="Spotify",
            items_synced=100,
            errors=5,
        )

        assert result is True

    async def test_send_system_error_notification(self) -> None:
        """Test send_system_error_notification method."""
        service = NotificationService()

        result = await service.send_system_error_notification(
            error_type="DatabaseError",
            error_message="Connection lost",
            context={"db_host": "localhost"},
        )

        assert result is True


class TestNotificationTypes:
    """Tests for Notification and NotificationResult dataclasses."""

    def test_notification_creation(self) -> None:
        """Test creating a Notification object."""
        notif = Notification(
            type=NotificationType.NEW_RELEASE,
            title="Test",
            message="Test message",
        )

        assert notif.type == NotificationType.NEW_RELEASE
        assert notif.title == "Test"
        assert notif.message == "Test message"
        assert notif.priority == NotificationPriority.NORMAL
        assert notif.data == {}
        assert notif.timestamp is not None

    def test_notification_result_success(self) -> None:
        """Test creating successful NotificationResult."""
        result = NotificationResult(
            success=True,
            provider_name="email",
            notification_type=NotificationType.NEW_RELEASE,
        )

        assert result.success is True
        assert result.provider_name == "email"
        assert result.error is None

    def test_notification_result_failure(self) -> None:
        """Test creating failure NotificationResult."""
        result = NotificationResult(
            success=False,
            provider_name="webhook",
            notification_type=NotificationType.DOWNLOAD_FAILED,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"
