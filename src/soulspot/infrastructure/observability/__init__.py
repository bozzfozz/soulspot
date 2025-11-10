"""Observability infrastructure for structured logging."""

from soulspot.infrastructure.observability.logging import (
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)

__all__ = [
    "configure_logging",
    "get_correlation_id",
    "set_correlation_id",
]
