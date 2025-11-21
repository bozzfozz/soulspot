"""Structured logging configuration with JSON formatting and correlation IDs."""

import contextvars
import logging
import sys
import uuid
from typing import Any

from pythonjsonlogger import jsonlogger

# Hey future me, correlation IDs are CRUCIAL for distributed tracing! Every request gets a unique
# ID (UUID) that follows it through all services, logs, and async tasks. When debugging "user says
# request failed", you grep logs for their correlation_id and see EVERYTHING related to that request.
# The contextvars module is thread-safe AND asyncio-safe - each async task gets its own context!
# Don't use global variables or threading.local() - they don't work with async. The default=""
# handles cases where no correlation_id is set (startup logs, background jobs, etc.).
# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


# Yo, this getter is safe - returns "" if not set, never raises! Use this in log formatters
# and middleware. Don't call .set() directly unless you know what you're doing - use the
# set_correlation_id() function below instead (it handles None properly and returns the ID).
def get_correlation_id() -> str:
    """Get the current correlation ID from context.

    Returns:
        Current correlation ID or empty string if not set
    """
    return correlation_id_var.get()


# Listen up, this setter AUTO-GENERATES a UUID if correlation_id is None! That's the common
# case - when a request comes in without X-Correlation-ID header, we create one. The return
# value is handy for middleware to add to response headers. Call this EARLY in request lifecycle
# (middleware) so all subsequent logs inherit it. Don't call this in loops or you'll get a new
# ID every iteration! Once per request!
def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set correlation ID in context.

    Args:
        correlation_id: Correlation ID to set. If None, generates a new UUID

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


# Hey future me, this filter INJECTS correlation_id into EVERY log record! Python's logging
# framework calls filter() for each log message. We grab correlation_id from context and attach
# it to the record as an attribute. Then formatters can use %(correlation_id)s in format strings!
# The return True is important - False would BLOCK the log message. Don't do heavy work here -
# this runs for EVERY log call (could be thousands per second!).
class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to record if available."""
        record.correlation_id = get_correlation_id()
        return True


# Yo, this formatter outputs STRUCTURED JSON for production! Way better than plain text for
# log aggregation (Elasticsearch, Splunk, CloudWatch, etc). Each field (timestamp, level, message)
# is a JSON key - easy to query! We add extra fields like module/function/line for debugging.
# The getattr(record, "correlation_id", "") handles old log records before correlation_id was
# added. Stack traces and exceptions are included IF present (record.exc_info/stack_info). The
# formatTime/formatException/formatStack calls do the heavy lifting - don't reinvent those!
class CustomJsonFormatter(jsonlogger.JsonFormatter):  # type: ignore[name-defined,misc]
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to log record.

        Args:
            log_record: Dictionary to be logged as JSON
            record: Python logging record
            message_dict: Message dictionary from format string
        """
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add correlation ID if available
        correlation_id = getattr(record, "correlation_id", "")
        if correlation_id:
            log_record["correlation_id"] = correlation_id

        # Add exception info if present
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)

        # Add stack trace if present
        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)


# Listen future me, this is THE logging setup function - call it ONCE at startup! It configures
# the root logger which affects ALL modules. We remove existing handlers first (important for
# tests/reloads). Use json_format=True in production for structured logs, False in dev for
# human-readable output. The third-party logger quieting (urllib3, httpx) is CRITICAL - without
# it, you get 10x more logs from HTTP libraries than your own code! The final logger.info call
# tests that logging works - check startup logs for this message!
def configure_logging(
    log_level: str = "INFO",
    json_format: bool = False,
    app_name: str = "soulspot",
) -> None:
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format for logs (recommended for production)
        app_name: Application name to include in logs
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    handler.addFilter(correlation_filter)

    # Configure formatter
    if json_format:
        # JSON formatter for production
        formatter: logging.Formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Human-readable formatter for development
        formatter = logging.Formatter(
            fmt=(
                "%(asctime)s - %(levelname)-8s - %(name)s - "
                "[%(correlation_id)s] - %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Configure third-party loggers to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Log configuration complete
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "app_name": app_name,
            "log_level": log_level,
            "json_format": json_format,
        },
    )
