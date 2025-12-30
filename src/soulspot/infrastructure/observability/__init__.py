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
from soulspot.infrastructure.observability.logger_template import (
    end_operation,
    get_module_logger,
    log_operation,
    log_slow_operation,
    log_worker_health,
    start_operation,
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
    "end_operation",
    "get_all_circuit_breakers",
    "get_circuit_breaker_stats",
    "get_correlation_id",
    "get_module_logger",
    "log_operation",
    "log_slow_operation",
    "log_worker_health",
    "set_correlation_id",
    "start_operation",
]
