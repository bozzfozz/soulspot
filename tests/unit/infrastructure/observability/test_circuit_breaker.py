"""Tests for circuit breaker implementation."""

import asyncio
from datetime import datetime, timedelta

import pytest

from soulspot.infrastructure.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)


@pytest.fixture
def config() -> CircuitBreakerConfig:
    """Create circuit breaker config for testing."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=1.0,  # Short timeout for tests
        reset_timeout=5.0,
    )


@pytest.fixture
def circuit_breaker(config: CircuitBreakerConfig) -> CircuitBreaker:
    """Create circuit breaker for testing."""
    return CircuitBreaker(name="test-service", config=config)


class TestCircuitBreakerInit:
    """Test circuit breaker initialization."""

    def test_init_with_config(self, config: CircuitBreakerConfig) -> None:
        """Test circuit breaker initialization with config."""
        cb = CircuitBreaker(name="test", config=config)
        assert cb.name == "test"
        assert cb.config == config
        assert cb.state == CircuitState.CLOSED

    def test_init_with_default_config(self) -> None:
        """Test circuit breaker initialization with default config."""
        cb = CircuitBreaker(name="test")
        assert cb.name == "test"
        assert cb.config.failure_threshold == 5
        assert cb.state == CircuitState.CLOSED

    def test_initial_stats(self, circuit_breaker: CircuitBreaker) -> None:
        """Test initial statistics."""
        stats = circuit_breaker.stats
        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_requests == 0
        assert stats.total_failures == 0
        assert stats.total_successes == 0


class TestCircuitBreakerClosed:
    """Test circuit breaker in CLOSED state."""

    async def test_call_success_in_closed_state(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test successful call in CLOSED state."""

        async def success_func() -> str:
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.stats.total_successes == 1
        assert circuit_breaker.stats.total_failures == 0

    async def test_call_failure_in_closed_state(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test failed call in CLOSED state."""

        async def failure_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.stats.failure_count == 1
        assert circuit_breaker.stats.total_failures == 1

    async def test_transition_to_open_after_threshold(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test transition to OPEN after failure threshold."""

        async def failure_func() -> None:
            raise ValueError("test error")

        # Trigger failures up to threshold (3)
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.stats.failure_count == 3

    async def test_reset_failure_count_on_success(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that failure count is reset on success."""

        async def failure_func() -> None:
            raise ValueError("test error")

        async def success_func() -> str:
            return "success"

        # Accumulate some failures
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.stats.failure_count == 2

        # Success should reset failure count
        await circuit_breaker.call(success_func)
        assert circuit_breaker.stats.failure_count == 0


class TestCircuitBreakerOpen:
    """Test circuit breaker in OPEN state."""

    async def test_calls_blocked_in_open_state(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that calls are blocked in OPEN state."""

        # Force transition to OPEN
        async def failure_func() -> None:
            raise ValueError("test error")

        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN

        # Now calls should be blocked
        async def any_func() -> str:
            return "should not execute"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(any_func)

        assert exc_info.value.service_name == "test-service"
        assert "OPEN" in str(exc_info.value)

    async def test_transition_to_half_open_after_timeout(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test transition to HALF_OPEN after timeout."""

        # Force transition to OPEN
        async def failure_func() -> None:
            raise ValueError("test error")

        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)  # Slightly more than config timeout

        # Next call should transition to HALF_OPEN
        async def success_func() -> str:
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.HALF_OPEN


class TestCircuitBreakerHalfOpen:
    """Test circuit breaker in HALF_OPEN state."""

    async def _transition_to_half_open(self, circuit_breaker: CircuitBreaker) -> None:
        """Helper to transition circuit to HALF_OPEN state."""

        async def failure_func() -> None:
            raise ValueError("test error")

        # Trigger failures to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        # Wait for timeout
        await asyncio.sleep(1.1)

        # First success after timeout transitions to HALF_OPEN
        async def success_func() -> str:
            return "success"

        await circuit_breaker.call(success_func)
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    async def test_transition_to_closed_after_success_threshold(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test transition to CLOSED after success threshold in HALF_OPEN."""
        await self._transition_to_half_open(circuit_breaker)

        async def success_func() -> str:
            return "success"

        # One more success to reach threshold (2 total)
        await circuit_breaker.call(success_func)

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.stats.failure_count == 0

    async def test_transition_to_open_on_failure(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test transition back to OPEN on failure in HALF_OPEN."""
        await self._transition_to_half_open(circuit_breaker)

        async def failure_func() -> None:
            raise ValueError("test error")

        # Any failure in HALF_OPEN should immediately open circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN


class TestCircuitBreakerStats:
    """Test circuit breaker statistics tracking."""

    async def test_stats_track_requests(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that statistics track all requests."""

        async def success_func() -> str:
            return "success"

        async def failure_func() -> None:
            raise ValueError("test error")

        # Execute mix of successes and failures
        await circuit_breaker.call(success_func)
        await circuit_breaker.call(success_func)

        with pytest.raises(ValueError):
            await circuit_breaker.call(failure_func)

        stats = circuit_breaker.stats
        assert stats.total_requests == 3
        assert stats.total_successes == 2
        assert stats.total_failures == 1

    async def test_stats_track_state_changes(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that statistics track state changes."""
        initial_time = circuit_breaker.stats.last_state_change

        async def failure_func() -> None:
            raise ValueError("test error")

        # Trigger state change
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        stats = circuit_breaker.stats
        assert stats.state == CircuitState.OPEN
        assert stats.last_state_change > initial_time


class TestCircuitBreakerReset:
    """Test manual circuit breaker reset."""

    async def test_manual_reset(self, circuit_breaker: CircuitBreaker) -> None:
        """Test manual reset of circuit breaker."""

        async def failure_func() -> None:
            raise ValueError("test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN

        # Manually reset
        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.stats.failure_count == 0


class TestCircuitBreakerConcurrency:
    """Test circuit breaker concurrent access."""

    async def test_concurrent_calls(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit breaker handles concurrent calls correctly."""
        call_count = 0

        async def counting_func() -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate some work
            return call_count

        # Execute multiple concurrent calls
        tasks = [circuit_breaker.call(counting_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert circuit_breaker.stats.total_requests == 10
        assert circuit_breaker.stats.total_successes == 10


class TestCircuitBreakerWithSyncFunctions:
    """Test circuit breaker with synchronous functions."""

    async def test_sync_function_success(self, circuit_breaker: CircuitBreaker) -> None:
        """Test circuit breaker with synchronous function."""

        def sync_func() -> str:
            return "sync success"

        result = await circuit_breaker.call(sync_func)
        assert result == "sync success"
        assert circuit_breaker.stats.total_successes == 1

    async def test_sync_function_failure(self, circuit_breaker: CircuitBreaker) -> None:
        """Test circuit breaker with failing synchronous function."""

        def sync_failure() -> None:
            raise ValueError("sync error")

        with pytest.raises(ValueError, match="sync error"):
            await circuit_breaker.call(sync_failure)

        assert circuit_breaker.stats.total_failures == 1


class TestCircuitBreakerResetTimeout:
    """Test circuit breaker reset timeout behavior."""

    async def test_failure_count_reset_after_reset_timeout(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that failure count is reset after reset_timeout in CLOSED state."""

        async def failure_func() -> None:
            raise ValueError("test error")

        # Accumulate some failures (but not enough to open)
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.stats.failure_count == 2

        # Manually set last_failure_time to past
        circuit_breaker._last_failure_time = datetime.now() - timedelta(
            seconds=circuit_breaker.config.reset_timeout + 1
        )

        # Next call should reset failure count
        async def success_func() -> str:
            return "success"

        await circuit_breaker.call(success_func)
        # The failure count should have been reset during state check
        assert circuit_breaker.stats.failure_count == 0
