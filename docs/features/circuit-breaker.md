# Circuit Breaker Pattern

## Overview

SoulSpot Bridge implements the Circuit Breaker pattern to protect external service integrations from cascading failures and improve system resilience. The circuit breaker monitors failures in real-time and temporarily blocks requests to failing services, allowing them time to recover.

## Architecture

### State Machine

The circuit breaker operates in three states:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLOSED (Normal)                         │
│  • All requests pass through                                │
│  • Failure count tracked                                    │
│  • Success resets failure count                             │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ failure_threshold reached
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                     OPEN (Failing)                          │
│  • All requests blocked                                     │
│  • Returns CircuitBreakerError immediately                  │
│  • Waits for timeout period                                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ timeout elapsed
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   HALF_OPEN (Testing)                       │
│  • Limited requests allowed                                 │
│  • Tests if service recovered                               │
│  • Single failure → back to OPEN                            │
│  • success_threshold reached → back to CLOSED               │
└─────────────────────────────────────────────────────────────┘
```

### Protected Services

Circuit breakers are automatically applied to:

1. **slskd API** (`slskd-api`)
   - File searches
   - Download operations
   - Download status checks

2. **Spotify API** (`spotify-api`)
   - OAuth token operations
   - Playlist fetching
   - Track metadata retrieval

3. **MusicBrainz API** (`musicbrainz-api`)
   - Recording lookups
   - Release information
   - Artist data

## Configuration

Circuit breaker behavior is configured through environment variables or settings:

### Environment Variables

```bash
# Number of failures before opening circuit
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5

# Number of successes in HALF_OPEN before closing circuit
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2

# Seconds to wait in OPEN state before trying HALF_OPEN
CIRCUIT_BREAKER_TIMEOUT=60.0

# Seconds to wait before resetting failure counter in CLOSED state
CIRCUIT_BREAKER_RESET_TIMEOUT=300.0
```

### Default Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 5 | Number of consecutive failures before opening circuit |
| `success_threshold` | 2 | Number of consecutive successes in HALF_OPEN to close circuit |
| `timeout` | 60s | Time to wait in OPEN before transitioning to HALF_OPEN |
| `reset_timeout` | 300s | Time to wait before resetting failure counter in CLOSED |

### Python Configuration

```python
from soulspot.config.settings import Settings

settings = Settings()

# Access circuit breaker configuration
cb_config = settings.observability.circuit_breaker

print(f"Failure threshold: {cb_config.failure_threshold}")
print(f"Timeout: {cb_config.timeout}s")
```

## Usage

### Automatic Protection

All external service clients are automatically wrapped with circuit breakers when instantiated through the dependency injection system:

```python
from soulspot.config.settings import Settings
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.integrations.circuit_breaker_wrapper import (
    CircuitBreakerSpotifyClient
)

settings = Settings()

# Create base client
base_client = SpotifyClient(settings.spotify)

# Wrap with circuit breaker
protected_client = CircuitBreakerSpotifyClient(base_client, settings)

# Use normally - circuit breaker is transparent
try:
    playlist = await protected_client.get_playlist(playlist_id, token)
except CircuitBreakerError as e:
    # Circuit is open - service is temporarily unavailable
    print(f"Service unavailable: {e.service_name}")
    print(f"Retry after: {e.retry_after}s")
```

### Direct Usage

For custom implementations, use the `CircuitBreaker` class directly:

```python
from soulspot.infrastructure.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
)

# Create circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout=30.0,
    reset_timeout=120.0,
)

circuit_breaker = CircuitBreaker(name="my-service", config=config)

# Protect function calls
async def call_external_api():
    # Make API call
    pass

try:
    result = await circuit_breaker.call(call_external_api)
except CircuitBreakerError as e:
    print(f"Circuit breaker is OPEN for {e.service_name}")
    print(f"Retry after {e.retry_after} seconds")
```

### Decorator Pattern

Use the `@circuit_breaker` decorator for cleaner code:

```python
from soulspot.infrastructure.observability.circuit_breaker import (
    circuit_breaker,
    CircuitBreakerConfig,
)

config = CircuitBreakerConfig(
    failure_threshold=5,
    timeout=60.0,
)

@circuit_breaker("my-service", config=config)
async def fetch_data():
    # This function is automatically protected
    pass
```

## Monitoring

### Statistics

Each circuit breaker tracks detailed statistics:

```python
stats = circuit_breaker.stats

print(f"State: {stats.state}")
print(f"Total requests: {stats.total_requests}")
print(f"Total failures: {stats.total_failures}")
print(f"Total successes: {stats.total_successes}")
print(f"Current failure count: {stats.failure_count}")
print(f"Last state change: {stats.last_state_change}")
```

### Logging

Circuit breakers emit structured logs at key events:

```json
{
  "level": "WARNING",
  "message": "Circuit breaker slskd-api is OPEN, blocking request. Retry after 45.3 seconds.",
  "circuit_breaker": "slskd-api",
  "state": "open"
}
```

```json
{
  "level": "INFO",
  "message": "Circuit breaker spotify-api transitioned to HALF_OPEN state. Testing service recovery.",
  "circuit_breaker": "spotify-api",
  "state": "half_open"
}
```

```json
{
  "level": "INFO",
  "message": "Circuit breaker musicbrainz-api transitioned to CLOSED state. Service recovered.",
  "circuit_breaker": "musicbrainz-api",
  "state": "closed"
}
```

### Manual Reset

Circuit breakers can be manually reset:

```python
# Force circuit to CLOSED state
await circuit_breaker.reset()
```

## Error Handling

### CircuitBreakerError

When a circuit is OPEN, calls are immediately rejected with `CircuitBreakerError`:

```python
from soulspot.infrastructure.observability.circuit_breaker import CircuitBreakerError

try:
    result = await protected_client.search("query")
except CircuitBreakerError as e:
    # Circuit is open
    service_name = e.service_name  # e.g., "slskd-api"
    retry_after = e.retry_after    # seconds until retry possible
    
    # Log or notify user
    logger.warning(
        f"Service {service_name} temporarily unavailable. "
        f"Retry in {retry_after:.0f} seconds"
    )
    
    # Implement backoff strategy
    await asyncio.sleep(retry_after)
```

### Best Practices

1. **Always handle CircuitBreakerError**: Implement graceful degradation when services are unavailable

2. **Use appropriate timeouts**: Set timeouts based on service SLAs and recovery times

3. **Monitor circuit state**: Track state transitions to identify problematic services

4. **Implement retry strategies**: Use exponential backoff when circuit opens

5. **Alert on prolonged OPEN state**: Set up alerts for circuits that remain open for extended periods

## Production Recommendations

### Tuning Guidelines

| Service Type | failure_threshold | timeout | reset_timeout |
|-------------|-------------------|---------|---------------|
| Critical (OAuth) | 3-5 | 30-60s | 120-300s |
| Standard (APIs) | 5-10 | 60-120s | 300-600s |
| Non-critical (Metadata) | 10-15 | 120-300s | 600-900s |

### Health Checks

Circuit breaker state should be included in health check responses:

```python
{
  "status": "degraded",
  "services": {
    "slskd": {
      "status": "unhealthy",
      "circuit_breaker": "open",
      "retry_after": 45
    },
    "spotify": {
      "status": "healthy",
      "circuit_breaker": "closed"
    }
  }
}
```

## Testing

### Unit Tests

Test circuit breaker behavior in isolation:

```python
async def test_circuit_opens_after_failures():
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
    
    async def failing_func():
        raise ValueError("error")
    
    # Trigger failures
    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(failing_func)
    
    # Circuit should be open
    assert cb.state == CircuitState.OPEN
    
    # Further calls should be blocked
    with pytest.raises(CircuitBreakerError):
        await cb.call(failing_func)
```

### Integration Tests

Test with actual services using mocks:

```python
async def test_spotify_client_with_circuit_breaker():
    mock_client = AsyncMock()
    mock_client.get_track.side_effect = Exception("API error")
    
    wrapper = CircuitBreakerSpotifyClient(mock_client, settings)
    
    # Trigger circuit opening
    for _ in range(5):
        with pytest.raises(Exception):
            await wrapper.get_track("track-123", "token")
    
    # Circuit should block further calls
    with pytest.raises(CircuitBreakerError):
        await wrapper.get_track("track-123", "token")
```

## References

- [Martin Fowler - Circuit Breaker](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Microsoft - Circuit Breaker Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [Resilience4j Documentation](https://resilience4j.readme.io/docs/circuitbreaker)

## See Also

- [Observability Guide](../observability-guide.md)
- [Architecture Documentation](../architecture.md)
- [Testing Guide](../testing-guide.md)
