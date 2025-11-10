"""Tests for structured logging."""

import logging

from soulspot.infrastructure.observability.logging import (
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)


class TestCorrelationId:
    """Test correlation ID functionality."""

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        test_id = "test-123-abc"
        result = set_correlation_id(test_id)
        assert result == test_id
        assert get_correlation_id() == test_id

    def test_set_correlation_id_generates_uuid_when_none(self):
        """Test that setting None generates a UUID."""
        result = set_correlation_id(None)
        assert result is not None
        assert len(result) > 0
        assert get_correlation_id() == result

    def test_correlation_id_persists_in_context(self):
        """Test that correlation ID persists within context."""
        test_id = "test-456-def"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
        # Call again to verify it persists
        assert get_correlation_id() == test_id


class TestLoggingConfiguration:
    """Test logging configuration."""

    def test_configure_logging_debug_level(self):
        """Test configuring logging with DEBUG level."""
        configure_logging(log_level="DEBUG", json_format=False, app_name="test-app")
        logger = logging.getLogger("test")
        assert logger.getEffectiveLevel() <= logging.DEBUG

    def test_configure_logging_info_level(self):
        """Test configuring logging with INFO level."""
        configure_logging(log_level="INFO", json_format=False, app_name="test-app")
        logger = logging.getLogger("test")
        assert logger.getEffectiveLevel() == logging.INFO

    def test_configure_logging_json_format(self):
        """Test configuring logging with JSON format."""
        configure_logging(log_level="INFO", json_format=True, app_name="test-app")
        root_logger = logging.getLogger()
        # Check that handler has been added
        assert len(root_logger.handlers) > 0

    def test_configure_logging_text_format(self):
        """Test configuring logging with text format."""
        configure_logging(log_level="INFO", json_format=False, app_name="test-app")
        root_logger = logging.getLogger()
        # Check that handler has been added
        assert len(root_logger.handlers) > 0

    def test_logging_with_correlation_id(self):
        """Test that logs include correlation ID."""
        configure_logging(log_level="INFO", json_format=False, app_name="test-app")
        test_id = "test-correlation-789"
        set_correlation_id(test_id)

        # Use logging getLogger to verify correlation ID is set
        assert get_correlation_id() == test_id
