"""Observability infrastructure for structured logging."""

from soulspot.infrastructure.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitState,
    circuit_breaker,
    get_all_circuit_breakers,
    get_circuit_breaker_stats,
)
from soulspot.infrastructure.observability.logging import (
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitBreakerStats",
    "CircuitState",
    "circuit_breaker",
    "configure_logging",
    "get_all_circuit_breakers",
    "get_circuit_breaker_stats",
    "get_correlation_id",
    "set_correlation_id",
]
