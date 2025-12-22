"""Circuit Breaker pattern implementation for external service resilience."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from soulspot.infrastructure.observability.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


# ========================================================================
# Circuit Breaker Registry - Global tracking for monitoring
# ========================================================================
# Hey future me - this is a GLOBAL REGISTRY for all CircuitBreaker instances!
# Why? So we can expose circuit breaker stats in /metrics and /health endpoints.
# Each CircuitBreaker registers itself on creation, unregisters on __del__.
# Thread-safe (well, asyncio-safe) via dict operations being atomic.
# Use get_all_circuit_breakers() to get stats for all breakers at once!


class CircuitBreakerRegistry:
    """Global registry for circuit breaker instances.

    Hey future me - this lets us track all circuit breakers for monitoring!

    Features:
    - Auto-registration when CircuitBreaker is created
    - Get stats for all breakers at once for /metrics endpoint
    - Find specific breakers by name for debugging
    """

    _breakers: dict[str, "CircuitBreaker"] = {}

    @classmethod
    def register(cls, breaker: "CircuitBreaker") -> None:
        """Register a circuit breaker instance.

        Args:
            breaker: CircuitBreaker to register
        """
        cls._breakers[breaker.name] = breaker
        logger.debug(f"Circuit breaker '{breaker.name}' registered")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a circuit breaker by name.

        Args:
            name: Name of breaker to unregister
        """
        if name in cls._breakers:
            del cls._breakers[name]
            logger.debug(f"Circuit breaker '{name}' unregistered")

    @classmethod
    def get(cls, name: str) -> "CircuitBreaker | None":
        """Get a circuit breaker by name.

        Args:
            name: Name of breaker to find

        Returns:
            CircuitBreaker if found, None otherwise
        """
        return cls._breakers.get(name)

    @classmethod
    def get_all(cls) -> dict[str, "CircuitBreaker"]:
        """Get all registered circuit breakers.

        Returns:
            Dict of name -> CircuitBreaker
        """
        return dict(cls._breakers)

    @classmethod
    def get_all_stats(cls) -> dict[str, "CircuitBreakerStats"]:
        """Get stats for all registered circuit breakers.

        Hey future me - this is what /metrics should call!

        Returns:
            Dict of name -> CircuitBreakerStats
        """
        from soulspot.infrastructure.observability.circuit_breaker import (
            CircuitBreakerStats,
        )

        return {name: breaker.stats for name, breaker in cls._breakers.items()}

    @classmethod
    def clear(cls) -> None:
        """Clear all registered breakers (for testing)."""
        cls._breakers.clear()


def get_all_circuit_breakers() -> dict[str, "CircuitBreaker"]:
    """Convenience function to get all circuit breakers.

    Returns:
        Dict of name -> CircuitBreaker
    """
    return CircuitBreakerRegistry.get_all()


def get_circuit_breaker_stats() -> dict[str, "CircuitBreakerStats"]:
    """Convenience function to get all circuit breaker stats.

    Hey future me - use this in /metrics endpoint!

    Returns:
        Dict of name -> CircuitBreakerStats
    """
    return CircuitBreakerRegistry.get_all_stats()

T = TypeVar("T")


# Hey future me, these are the THREE STATES of the circuit breaker state machine: CLOSED means
# "all good, let traffic through", OPEN means "service is broken, fail fast", and HALF_OPEN
# means "let's TEST if the service recovered". Think of it like a real circuit breaker in your
# house - when something trips (OPEN), you have to manually test (HALF_OPEN) before it's
# back to normal (CLOSED). The transitions: CLOSED → OPEN (too many failures), OPEN → HALF_OPEN
# (timeout elapsed), HALF_OPEN → CLOSED (success threshold met) or HALF_OPEN → OPEN (any failure).
class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


# Yo future me, this config controls circuit breaker sensitivity! failure_threshold=5 means
# "5 failures in a row before opening" - lower = more sensitive but more false positives.
# success_threshold=2 means "need 2 successful requests in HALF_OPEN to close" - increase if
# you want more confidence before declaring service healthy. timeout=60s is how long to wait
# in OPEN before trying HALF_OPEN - increase if service needs recovery time (DB restart, etc).
# reset_timeout=300s is how long in CLOSED before we forget old failures - prevents "ghost"
# failures from distant past affecting current health. Tweak these via env vars, not code!
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


# Hey, these stats are GOLD for monitoring dashboards! failure_count is current streak
# (resets when circuit closes), total_failures is ALL TIME. Same for successes. Use this to
# graph circuit health over time. last_failure_time helps calculate "retry after" times.
# last_state_change tells you how long the circuit has been in current state - if it's been
# OPEN for hours, something's seriously broken! Expose this via /metrics or health check.
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


# Listen up, this exception is INTENTIONAL - it's not a bug! When the circuit is OPEN, we
# raise this to fail fast instead of waiting 30s for a timeout. The retry_after tells clients
# "come back in X seconds" - use it in HTTP 503 responses with Retry-After header! The service_name
# helps identify WHICH service is down in logs (you might have 5 different circuit breakers).
# DON'T catch this and retry immediately - respect the retry_after or you're just hammering a
# dead service. In HTTP handlers, convert this to 503 Service Unavailable with proper headers.
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
    # Also, it auto-registers itself with CircuitBreakerRegistry so metrics can find it!
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

        # Register with global registry for metrics/monitoring
        CircuitBreakerRegistry.register(self)

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

    # Yo, this calculates the "come back later" time for clients. Used in the CircuitBreakerError
    # message. If last failure was 30s ago and timeout is 60s, returns 30s. If we're past the
    # timeout, returns 0 (should be in HALF_OPEN already). The max(0.0, ...) prevents negative
    # values due to clock drift or race conditions. Use this in Retry-After headers!
    def _get_retry_after(self) -> float:
        """Calculate seconds until circuit can be tried again."""
        if self._last_failure_time is None:
            return 0.0

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return max(0.0, self.config.timeout - elapsed)

    # Hey future me, this is TIME-BASED state transition logic! Called before EVERY request.
    # If we're OPEN and timeout has passed, switch to HALF_OPEN automatically (no manual reset
    # needed). If we're CLOSED but had old failures, and reset_timeout passed, forget those
    # failures (clean slate). This prevents: 1) circuits stuck OPEN forever, 2) ancient failures
    # from 5 hours ago counting toward current failure_threshold. The "now = datetime.now()"
    # at the top is important - use same timestamp for both checks to avoid race conditions!
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

    # Listen up, success handling is STATE-DEPENDENT! In HALF_OPEN, we count successes toward
    # success_threshold to close the circuit. If we hit the threshold, circuit closes! In CLOSED,
    # a success resets the failure counter (back to "no failures"). This is important - prevents
    # a service that's MOSTLY healthy but had 4 failures in the past from opening on the 5th
    # failure if there were successes in between. The lock protects _success_count increments.
    # We log INFO in HALF_OPEN because that's important (service recovering!), but not in CLOSED
    # (that's normal operation, would flood logs).
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

    # Yo future me, failure handling is AGGRESSIVE! Every failure increments counters and updates
    # last_failure_time (used for timeouts). In HALF_OPEN, even ONE failure immediately opens the
    # circuit again - we're strict because service clearly hasn't recovered! In CLOSED, we wait
    # until failure_threshold before opening. We log WARNING (not ERROR) because failures might
    # be temporary network blips - ERROR would be too noisy. The exception type/message are logged
    # to help debug WHY it's failing (timeout vs connection refused vs 500 error, etc.). The lock
    # prevents race conditions where two failures happen simultaneously and only one gets counted.
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

    # Hey, this transition is BAD NEWS - service is down! We log ERROR (not warning) because
    # this affects availability. The success_count reset prepares for eventual HALF_OPEN state.
    # We update last_state_change for metrics tracking. The timeout value in the log message
    # tells operators "service will be tested again in X seconds". Alert on this in production!
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

    # Listen up, HALF_OPEN is the TESTING state - we cautiously try the service again. We reset
    # BOTH failure_count and success_count to zero because we're starting fresh. This state is
    # fragile - one failure snaps us back to OPEN, but success_threshold successes close the
    # circuit. We log INFO because this is hopeful (service might be recovering!). Monitor for
    # circuits that flip between HALF_OPEN and OPEN repeatedly - that means service is flaky!
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

    # Yo, we're HEALTHY again! Circuit closed means normal operation restored. Reset ALL counters
    # and timestamps to clean slate. The None assignment to last_failure_time is important - tells
    # _check_state_transition "don't apply reset_timeout logic". We log INFO (not ERROR) because
    # this is GOOD news - celebrate service recovery! If you see frequent CLOSED → OPEN → CLOSED
    # cycles, your failure_threshold might be too sensitive (increase it).
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

    # Hey future me, this is a MANUAL override - use with caution! Good for: 1) testing circuit
    # breaker behavior, 2) forcing recovery after you fix the underlying service, 3) emergency
    # "just make it work" situations. BAD for: production automation (defeats the purpose!). The
    # lock prevents race conditions. We log INFO to audit trail - track who/when/why this was
    # called. Consider adding authentication/authorization before exposing this via admin API!
    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        async with self._lock:
            await self._transition_to_closed()
            logger.info(
                "Circuit breaker %s manually reset to CLOSED state.",
                self.name,
                extra={"circuit_breaker": self.name},
            )


# Listen up, this decorator is EASIER than using CircuitBreaker directly! Just slap
# @circuit_breaker("my-service") on any function. BUT there's a caveat: the breaker is created
# PER DECORATED FUNCTION, not globally! If you have 10 functions calling same service, use 10
# decorators with SAME name to share one breaker. Or better yet, create ONE breaker instance
# and pass it as dependency. The decorator supports both sync and async functions but... most
# services are async nowadays. The wraps() preserves function metadata for introspection/docs.
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
