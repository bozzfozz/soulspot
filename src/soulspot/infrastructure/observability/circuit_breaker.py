"""Circuit Breaker pattern implementation for external service resilience."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    """Number of failures before opening circuit"""

    success_threshold: int = 2
    """Number of successes in HALF_OPEN before closing circuit"""

    timeout: float = 60.0
    """Seconds to wait in OPEN state before trying HALF_OPEN"""

    reset_timeout: float = 300.0
    """Seconds to wait before resetting failure counter in CLOSED state"""


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: datetime | None = None
    last_state_change: datetime = field(default_factory=datetime.now)
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and requests are blocked."""

    def __init__(self, service_name: str, retry_after: float) -> None:
        super().__init__(
            f"Circuit breaker is OPEN for {service_name}. "
            f"Retry after {retry_after:.1f} seconds."
        )
        self.service_name = service_name
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.

    Protects external services from cascading failures by tracking failures
    and temporarily blocking requests when a threshold is reached.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Service is failing, requests are blocked
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Args:
        name: Unique name for this circuit breaker (e.g., "spotify-api")
        config: Circuit breaker configuration
    """

    # Hey future me, CircuitBreaker is STATEFUL - it tracks failures/successes across ALL calls!
    # Starts in CLOSED (normal), moves to OPEN (broken) after threshold failures, then HALF_OPEN
    # (testing recovery). The _lock is CRITICAL - without it, concurrent requests can corrupt state
    # (imagine two failures incrementing _failure_count at same time, count goes up by 1 not 2!).
    # Each instance is for ONE service - don't share across different APIs or you'll get weird
    # behavior (Spotify fails but MusicBrainz gets blocked too!). Use globals/singletons per service.
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize circuit breaker."""
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._last_state_change = datetime.now()
        self._total_requests = 0
        self._total_failures = 0
        self._total_successes = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get current circuit breaker statistics."""
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_state_change=self._last_state_change,
            total_requests=self._total_requests,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
        )

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception from the wrapped function
        """
        async with self._lock:
            self._total_requests += 1

            # Check if we should transition states
            await self._check_state_transition()

            # If circuit is open, reject the request
            if self._state == CircuitState.OPEN:
                retry_after = self._get_retry_after()
                logger.warning(
                    "Circuit breaker %s is OPEN, blocking request. "
                    "Retry after %.1f seconds.",
                    self.name,
                    retry_after,
                    extra={"circuit_breaker": self.name, "state": self._state.value},
                )
                raise CircuitBreakerError(self.name, retry_after)

        # Execute the function
        try:
            result = func(*args, **kwargs)
            # Handle async functions
            if asyncio.iscoroutine(result):
                result = await result

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure(e)
            raise

    def _get_retry_after(self) -> float:
        """Calculate seconds until circuit can be tried again."""
        if self._last_failure_time is None:
            return 0.0

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return max(0.0, self.config.timeout - elapsed)

    async def _check_state_transition(self) -> None:
        """Check if state should transition based on time elapsed."""
        now = datetime.now()

        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed to move to HALF_OPEN
            if self._last_failure_time:
                elapsed = (now - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    await self._transition_to_half_open()

        elif self._state == CircuitState.CLOSED and self._last_failure_time:
            # Reset failure counter if reset timeout has elapsed
            elapsed = (now - self._last_failure_time).total_seconds()
            if elapsed >= self.config.reset_timeout:
                self._failure_count = 0
                self._last_failure_time = None

    async def _on_success(self) -> None:
        """Handle successful request."""
        async with self._lock:
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    "Circuit breaker %s: Success in HALF_OPEN state (%d/%d)",
                    self.name,
                    self._success_count,
                    self.config.success_threshold,
                    extra={
                        "circuit_breaker": self.name,
                        "state": self._state.value,
                        "success_count": self._success_count,
                    },
                )

                if self._success_count >= self.config.success_threshold:
                    await self._transition_to_closed()

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    self._failure_count = 0
                    self._last_failure_time = None

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed request."""
        async with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            logger.warning(
                "Circuit breaker %s: Failure recorded (%d/%d) - %s: %s",
                self.name,
                self._failure_count,
                self.config.failure_threshold,
                type(exception).__name__,
                str(exception),
                extra={
                    "circuit_breaker": self.name,
                    "state": self._state.value,
                    "failure_count": self._failure_count,
                    "exception_type": type(exception).__name__,
                },
            )

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately opens circuit
                await self._transition_to_open()

            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.config.failure_threshold
            ):
                # Check if we've hit the failure threshold
                await self._transition_to_open()

    async def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._success_count = 0
        self._last_state_change = datetime.now()

        logger.error(
            "Circuit breaker %s transitioned to OPEN state. "
            "Service calls will be blocked for %.1f seconds.",
            self.name,
            self.config.timeout,
            extra={
                "circuit_breaker": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
            },
        )

    async def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = datetime.now()

        logger.info(
            "Circuit breaker %s transitioned to HALF_OPEN state. Testing service recovery.",
            self.name,
            extra={"circuit_breaker": self.name, "state": self._state.value},
        )

    async def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_state_change = datetime.now()

        logger.info(
            "Circuit breaker %s transitioned to CLOSED state. Service recovered.",
            self.name,
            extra={"circuit_breaker": self.name, "state": self._state.value},
        )

    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        async with self._lock:
            await self._transition_to_closed()
            logger.info(
                "Circuit breaker %s manually reset to CLOSED state.",
                self.name,
                extra={"circuit_breaker": self.name},
            )


def circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to wrap functions with circuit breaker protection.

    Usage:
        @circuit_breaker("my-service")
        async def call_external_service():
            ...

    Args:
        name: Unique name for this circuit breaker
        config: Optional circuit breaker configuration

    Returns:
        Decorated function
    """
    breaker = CircuitBreaker(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Decorator function that wraps the target function with circuit breaker logic.

        Args:
            func: Function to wrap with circuit breaker

        Returns:
            Wrapped function with circuit breaker protection
        """

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            """Async wrapper for circuit breaker call."""
            return cast(T, await breaker.call(func, *args, **kwargs))

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            """Sync wrapper for circuit breaker call.

            Runs the circuit breaker in an event loop for synchronous functions.
            """
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return cast(T, loop.run_until_complete(breaker.call(func, *args, **kwargs)))

        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)

    return decorator
