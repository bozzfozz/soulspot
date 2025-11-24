# Observability Guide

This guide explains how to use the observability features in SoulSpot.

## Table of Contents

- [Overview](#overview)
- [Structured Logging](#structured-logging)
- [Circuit Breaker](#circuit-breaker)
- [Health Checks](#health-checks)
- [Configuration](#configuration)
- [Best Practices](#best-practices)

## Overview

SoulSpot includes observability features to help you monitor and debug your application:

- **Structured Logging**: JSON-formatted logs with correlation IDs for request tracking
- **Circuit Breaker**: Resilience pattern to protect external service integrations
- **Health Checks**: Liveness and readiness probes with dependency monitoring

## Structured Logging

### Features

- **Correlation IDs**: Automatic request tracking across logs
- **JSON Format**: Machine-readable logs for production (optional)
- **Contextual Information**: Automatic inclusion of metadata (timestamp, level, module)
- **Request/Response Logging**: Automatic logging of all HTTP requests

### Configuration

Configure logging in your `.env` file:

```env
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Enable JSON format for production
OBSERVABILITY__LOG_JSON_FORMAT=true
```

### Correlation IDs

Every request gets a unique correlation ID that's included in all logs. The ID is:
- Generated automatically if not provided
- Can be provided via `X-Correlation-ID` header
- Returned in the response `X-Correlation-ID` header
- Included in all logs during request processing

Example log output (text format):
```
2025-11-10 14:00:00 - INFO - soulspot.api.routers.tracks - [abc-123-def] - Fetching track details
```

Example log output (JSON format):
```json
{
  "timestamp": "2025-11-10 14:00:00",
  "level": "INFO",
  "logger": "soulspot.api.routers.tracks",
  "correlation_id": "abc-123-def",
  "message": "Fetching track details"
}
```

### Usage in Code

```python
import logging
from soulspot.infrastructure.observability.logging import get_correlation_id

logger = logging.getLogger(__name__)

# Logs automatically include correlation ID
logger.info("Processing request", extra={"user_id": 123})

# Get current correlation ID
correlation_id = get_correlation_id()
```

## Circuit Breaker

The circuit breaker pattern protects external service integrations from cascading failures by temporarily blocking requests to failing services.

### Quick Start

Circuit breakers are automatically applied to all external service clients (Spotify, MusicBrainz, slskd). No code changes required!

### Configuration

```env
# Number of failures before opening circuit (default: 5)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5

# Seconds to wait in OPEN state before testing recovery (default: 60)
CIRCUIT_BREAKER_TIMEOUT=60.0

# Number of successes needed to close circuit (default: 2)
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2

# Seconds before resetting failure counter (default: 300)
CIRCUIT_BREAKER_RESET_TIMEOUT=300.0
```

### States

- **CLOSED**: Normal operation, all requests pass through
- **OPEN**: Service failing, requests are blocked immediately
- **HALF_OPEN**: Testing recovery, limited requests allowed

### Error Handling

When a circuit is open, clients raise `CircuitBreakerError`:

```python
from soulspot.infrastructure.observability.circuit_breaker import CircuitBreakerError

try:
    playlist = await spotify_client.get_playlist(playlist_id, token)
except CircuitBreakerError as e:
    logger.warning(f"Service {e.service_name} unavailable, retry after {e.retry_after}s")
```

### Monitoring

Circuit breakers emit structured logs with state transitions:

```json
{
  "level": "WARNING",
  "message": "Circuit breaker spotify-api is OPEN, blocking request.",
  "circuit_breaker": "spotify-api",
  "state": "open"
}
```

**📖 For detailed information, see [Circuit Breaker Documentation](../features/circuit-breaker.md)**

## Health Checks

### Endpoints

#### Liveness Probe (`/live`)
Checks if the application is running:

```bash
curl http://localhost:8000/live
# {"status": "alive"}
```

#### Health Check (`/health`)
Basic health check endpoint:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "app_name": "SoulSpot",
  "environment": "development",
  "profile": "simple"
}
```

#### Readiness Probe (`/ready`)
Checks if the application is ready to serve traffic with dependency checks:

```bash
curl http://localhost:8000/ready
```

Response:
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "slskd": {
      "status": "healthy",
      "message": "slskd service is accessible"
    },
    "spotify": {
      "status": "healthy",
      "message": "Spotify API is accessible"
    },
    "musicbrainz": {
      "status": "healthy",
      "message": "MusicBrainz API is accessible"
    }
  }
}
```

Status values:
- `healthy`: All checks passed
- `degraded`: Some checks failed but service is operational
- `unhealthy`: Critical checks failed

### Configuration

```env
# Enable dependency health checks (default: true)
OBSERVABILITY__ENABLE_DEPENDENCY_HEALTH_CHECKS=true

# Health check timeout in seconds (default: 5.0)
OBSERVABILITY__HEALTH_CHECK_TIMEOUT=5.0
```

### Kubernetes Integration

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: soulspot
spec:
  containers:
  - name: app
    image: soulspot:latest
    livenessProbe:
      httpGet:
        path: /live
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
```

## Configuration

### Complete Environment Variables

```env
# Application
APP_ENV=production
LOG_LEVEL=INFO

# Observability - Logging
OBSERVABILITY__LOG_JSON_FORMAT=true

# Observability - Health Checks
OBSERVABILITY__ENABLE_DEPENDENCY_HEALTH_CHECKS=true
OBSERVABILITY__HEALTH_CHECK_TIMEOUT=5.0

# Observability - Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2
CIRCUIT_BREAKER_TIMEOUT=60.0
CIRCUIT_BREAKER_RESET_TIMEOUT=300.0
```

## Best Practices

### Logging

1. **Use appropriate log levels**:
   - DEBUG: Detailed diagnostic information
   - INFO: General informational messages
   - WARNING: Warning messages for potential issues
   - ERROR: Error messages for failures
   - CRITICAL: Critical issues requiring immediate attention

2. **Include context**: Use `extra` parameter to add structured data:
   ```python
   logger.info("User action completed", extra={
       "user_id": user.id,
       "action": "download",
       "duration_ms": duration
   })
   ```

3. **Avoid logging sensitive data**: Never log passwords, tokens, or personal information

4. **Use JSON format in production**: Makes logs easier to parse and analyze with log aggregation tools

### Health Checks

1. **Set appropriate timeouts**: Balance responsiveness with false positives
2. **Monitor health check latency**: Slow health checks indicate problems
3. **Use readiness for dependencies**: Liveness for application health only
4. **Test health checks regularly**: Ensure they accurately reflect system state

### Circuit Breaker

1. **Tune thresholds for service type**: Critical services should open faster
2. **Monitor state transitions**: Track patterns in circuit opening/closing
3. **Implement graceful degradation**: Handle `CircuitBreakerError` appropriately
4. **Alert on prolonged OPEN state**: Indicates ongoing service issues
5. **Test circuit behavior**: Verify circuit opens under failure conditions

---

For more information about the application architecture and deployment, see:
- [Architecture Guide](../architecture.md)
- [Circuit Breaker Pattern](../features/circuit-breaker.md)
- [Setup Guide](setup-guide.md)
- [Backend Development Roadmap](../../development/backend-roadmap.md)
