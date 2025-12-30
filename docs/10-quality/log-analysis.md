# Log Analysis Guide

**Category:** Troubleshooting / Operations  
**Last Updated:** 2025-12-30  
**Status:** ✅ Active

---

## Purpose

Analyze SoulSpot logs for:
- **Debugging:** Find errors and trace request flows
- **Monitoring:** Track worker health and performance  
- **Troubleshooting:** Identify slow operations and bottlenecks

---

## Accessing Logs

### Docker Logs

```bash
# View recent logs
docker logs soulspot

# Follow logs in real-time
docker logs -f soulspot

# Last 100 lines
docker logs soulspot 2>&1 | tail -100

# Logs from last hour
docker logs --since 1h soulspot

# Export to file
docker logs soulspot > soulspot.log 2>&1
```

### Log File (if configured)

```bash
# If LOG_FILE environment variable is set
tail -f /var/log/soulspot/app.log
```

---

## Log Format

SoulSpot uses structured JSON logging:

```json
{
  "timestamp": "2025-12-30T21:30:45.123Z",
  "level": "INFO",
  "module": "spotify_sync_worker",
  "message": "sync.completed",
  "correlation_id": "abc-123-def",
  "context": {
    "artist_count": 42,
    "duration_ms": 1250
  }
}
```

**Key Fields:**
- `timestamp` - ISO 8601 UTC time
- `level` - DEBUG/INFO/WARNING/ERROR/CRITICAL
- `module` - Component name (worker/service/api)
- `correlation_id` - Request tracing ID
- `context` - Structured metadata

---

## Common Log Patterns

### 1. Find Logs by Module

```bash
# All logs from Spotify Sync Worker
docker logs soulspot 2>&1 | grep "spotify_sync_worker"

# All logs from Download Service
docker logs soulspot 2>&1 | grep "download_service"

# All logs from API layer
docker logs soulspot 2>&1 | grep "api\."
```

### 2. Trace Request by Correlation ID

Track all logs for a specific HTTP request:

```bash
# Find correlation ID from first request log
docker logs soulspot 2>&1 | grep "api.request" | tail -1

# Then find ALL logs for that request
docker logs soulspot 2>&1 | grep "correlation_id.*abc-123-def"
```

**Example Output:**
```
21:30:45 │ INFO  │ middleware:45 │ api.request {"correlation_id": "abc-123-def", "path": "/library/scan"}
21:30:46 │ INFO  │ library_core:123 │ library.scan.started {"correlation_id": "abc-123-def"}
21:30:47 │ INFO  │ library_scanner:234 │ scan.complete {"correlation_id": "abc-123-def", "count": 100}
```

### 3. Find All Errors

```bash
# All ERROR level logs
docker logs soulspot 2>&1 | grep "ERROR"

# Errors with context (5 lines before/after)
docker logs soulspot 2>&1 | grep -B 5 -A 5 "ERROR"

# Errors from specific module
docker logs soulspot 2>&1 | grep "spotify_sync_worker" | grep "ERROR"
```

### 4. Find Slow Operations

```bash
# All slow query warnings
docker logs soulspot 2>&1 | grep "slow_query"

# Operations taking >100ms
docker logs soulspot 2>&1 | grep "duration_ms" | grep -E '"duration_ms": [1-9][0-9]{2,}'

# Specific slow operation type
docker logs soulspot 2>&1 | grep "library.scan" | grep "duration_ms"
```

### 5. Worker Health Check

```bash
# Token refresh worker status
docker logs soulspot 2>&1 | grep "token_refresh_worker" | tail -20

# Spotify sync worker status
docker logs soulspot 2>&1 | grep "spotify_sync_worker" | tail -20

# Download monitor status
docker logs soulspot 2>&1 | grep "download_monitor" | tail -20
```

---

## Debugging Workflows

### Scenario 1: User Reports "Artist Not Found"

```bash
# 1. Find the request
docker logs soulspot 2>&1 | grep "GET /api/artists" | tail -20

# 2. Extract correlation_id
# correlation_id: "xyz-789-abc"

# 3. Trace full request flow
docker logs soulspot 2>&1 | grep "xyz-789-abc"

# 4. Check database query logs
docker logs soulspot 2>&1 | grep "xyz-789-abc" | grep "SELECT"
```

### Scenario 2: Download Stuck in Queue

```bash
# 1. Find download logs
docker logs soulspot 2>&1 | grep "download_monitor" | tail -50

# 2. Check slskd client errors
docker logs soulspot 2>&1 | grep "slskd_client" | grep "ERROR"

# 3. Verify download service logs
docker logs soulspot 2>&1 | grep "download_service" | grep -E "(queue|failed)"
```

### Scenario 3: Slow Library Scan

```bash
# 1. Find scan start/end times
docker logs soulspot 2>&1 | grep "library.scan" | grep -E "(started|complete)"

# 2. Find slow file operations
docker logs soulspot 2>&1 | grep "library" | grep "duration_ms" | sort -t ':' -k 5 -n

# 3. Check filesystem access logs
docker logs soulspot 2>&1 | grep "filesystem" | grep "WARNING"
```

---

## Performance Analysis

### Identify Top Slow Operations

```bash
# Extract all durations >500ms
docker logs soulspot 2>&1 | \
  grep -o '"duration_ms": [0-9]*' | \
  awk -F': ' '$2 > 500 {print $2}' | \
  sort -rn | \
  head -20
```

### Track API Response Times

```bash
# Average response time by endpoint
docker logs soulspot 2>&1 | \
  grep "api.response" | \
  grep -o '"path": "[^"]*".*"duration_ms": [0-9]*' | \
  awk '{print $2, $4}' | \
  sort | \
  uniq -c
```

---

## Log Rotation

### Docker Default

Docker automatically rotates logs when they exceed 10MB:

```bash
# View Docker log size
docker inspect soulspot | grep -A 5 "LogConfig"
```

### Manual Rotation

```bash
# Truncate logs (keeps last 1000 lines)
docker logs soulspot 2>&1 | tail -1000 > soulspot.log
docker logs --tail 0 -f soulspot &  # Start fresh follow
```

---

## Troubleshooting Checklist

**When debugging issues:**

1. [ ] Check recent ERROR logs (`docker logs soulspot 2>&1 | grep ERROR`)
2. [ ] Find correlation_id from failing request
3. [ ] Trace full request flow using correlation_id
4. [ ] Check slow operations (`duration_ms > 100`)
5. [ ] Verify worker health (token_refresh, spotify_sync, download_monitor)
6. [ ] Review external API errors (Spotify, slskd, MusicBrainz)
7. [ ] Check database query logs (`SELECT ... WHERE`)

---

## Related Documentation

- [Operations Runbook](../08-guides/operations-runbook.md) - Production operations
- [Troubleshooting Guide](../08-guides/troubleshooting-guide.md) - Common issues
- [Observability Guide](../08-guides/observability-guide.md) - Monitoring setup
