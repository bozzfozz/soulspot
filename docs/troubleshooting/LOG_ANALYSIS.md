# Log Analysis Guide

**Version:** 1.0  
**Last Updated:** 2025-12-30

---

## Purpose

This guide shows how to analyze SoulSpot logs for:
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
```

### Log File (if configured)

```bash
# If logs are written to file (not default)
tail -f /path/to/soulspot.log
```

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

### 2. Find Logs by Correlation ID

Track all logs for a specific request:

```bash
# Find correlation ID from first request log
docker logs soulspot 2>&1 | grep "api.request"

# Then find ALL logs for that request
docker logs soulspot 2>&1 | grep "correlation_id.*abc-123-def"
```

**Example Output:**
```
21:30:45 │ INFO    │ middleware:45 │ api.request {"correlation_id": "abc-123-def", "path": "/library/scan"}
21:30:46 │ INFO    │ library_core:123 │ library.scan.started {"correlation_id": "abc-123-def"}
21:30:47 │ INFO    │ library_scanner:234 │ scan.complete {"correlation_id": "abc-123-def", "count": 100}
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
docker logs soulspot 2>&1 | grep "duration_ms" | grep -E "duration_ms\": [1-9][0-9]{2,}"

# Specific slow operation type
docker logs soulspot 2>&1 | grep "operation.slow" | grep "spotify_sync"
```

### 5. Find Worker Health Status

```bash
# All worker health logs
docker logs soulspot 2>&1 | grep "worker.health"

# Health for specific worker
docker logs soulspot 2>&1 | grep "worker.health" | grep "spotify_sync"

# Extract structured data (requires jq if JSON logging enabled)
docker logs soulspot 2>&1 | grep "worker.health" | grep -o '{.*}' | jq .
```

### 6. Find Exceptions

```bash
# All exception tracebacks
docker logs soulspot 2>&1 | grep "╰─►"

# Specific exception type
docker logs soulspot 2>&1 | grep "ConnectError"

# Full exception chain (with context)
docker logs soulspot 2>&1 | grep -A 20 "╰─► httpx.ConnectError"
```

---

## Analysis Workflows

### Workflow 1: Debug Failed Request

**Problem:** User reports "Library scan failed" in UI

**Steps:**

1. **Find the request:**
   ```bash
   docker logs soulspot 2>&1 | grep "library.scan" | grep "ERROR"
   ```

2. **Get correlation ID:**
   ```
   21:30:45 │ ERROR   │ library_core:123 │ library.scan.failed {"correlation_id": "xyz-789"}
   ```

3. **Trace full request flow:**
   ```bash
   docker logs soulspot 2>&1 | grep "xyz-789"
   ```

4. **Analyze exception:**
   Look for `╰─►` markers showing exception chain

5. **Check related logs:**
   ```bash
   # Were there any warnings before the error?
   docker logs soulspot 2>&1 | grep "xyz-789" | grep "WARNING"
   ```

---

### Workflow 2: Monitor Worker Health

**Goal:** Check if workers are running properly

**Steps:**

1. **Check worker startup:**
   ```bash
   docker logs soulspot 2>&1 | grep "worker.started"
   ```

   **Expected:**
   ```
   21:21:07 │ INFO │ spotify_sync_worker:74 │ worker.started {"worker": "spotify_sync"}
   21:21:07 │ INFO │ deezer_sync_worker:163 │ worker.started {"worker": "deezer_sync"}
   ```

2. **Check recent health reports:**
   ```bash
   docker logs soulspot 2>&1 | grep "worker.health" | tail -20
   ```

   **Look for:**
   - `cycles_completed` increasing
   - `errors_total` should be low
   - `uptime_seconds` shows worker hasn't restarted

3. **Check for errors:**
   ```bash
   docker logs soulspot 2>&1 | grep "worker.*ERROR"
   ```

4. **Identify problematic workers:**
   ```bash
   # High error count?
   docker logs soulspot 2>&1 | grep "worker.health" | grep "errors_total.*[5-9]"
   ```

---

### Workflow 3: Investigate Performance Issue

**Problem:** Slow response times

**Steps:**

1. **Find slow operations:**
   ```bash
   docker logs soulspot 2>&1 | grep "operation.slow"
   ```

2. **Check slow queries:**
   ```bash
   docker logs soulspot 2>&1 | grep "repository.slow_query"
   ```

   **Example:**
   ```
   21:30:45 │ WARNING │ track_repository:234 │ repository.slow_query {
       "repository": "TrackRepository",
       "operation": "get_by_album",
       "duration_ms": 234
   }
   ```

3. **Analyze operation durations:**
   ```bash
   # Extract duration_ms values
   docker logs soulspot 2>&1 | grep "sync.playlists.completed" | grep -o "duration_ms\": [0-9]*"
   ```

4. **Check for patterns:**
   - Which operations are consistently slow?
   - Are there spikes at specific times?
   - Is it all operations or specific ones?

---

### Workflow 4: Debug Worker Not Syncing

**Problem:** Spotify sync not working

**Steps:**

1. **Check if worker is running:**
   ```bash
   docker logs soulspot 2>&1 | grep "spotify_sync_worker" | grep "worker.started"
   ```

2. **Check for token issues:**
   ```bash
   docker logs soulspot 2>&1 | grep "spotify_sync" | grep -E "token|auth"
   ```

   **Look for:**
   ```
   WARNING: No valid Spotify token available - skipping sync cycle
   ```

3. **Check sync attempts:**
   ```bash
   docker logs soulspot 2>&1 | grep "sync.*.started"
   ```

4. **Check for errors during sync:**
   ```bash
   docker logs soulspot 2>&1 | grep "spotify_sync" | grep "ERROR"
   ```

---

## Filtering Techniques

### By Time Range

```bash
# Last hour
docker logs --since 1h soulspot

# Specific time range
docker logs --since "2025-12-30T10:00:00" --until "2025-12-30T11:00:00" soulspot

# Last 5 minutes
docker logs --since 5m soulspot
```

### By Log Level

```bash
# Only errors
docker logs soulspot 2>&1 | grep "ERROR"

# Errors and warnings
docker logs soulspot 2>&1 | grep -E "ERROR|WARNING"

# Debug logs only
docker logs soulspot 2>&1 | grep "DEBUG"
```

### By Structured Fields

```bash
# All logs with track_id
docker logs soulspot 2>&1 | grep "track_id"

# Specific track
docker logs soulspot 2>&1 | grep "track_id.*abc123"

# All downloads
docker logs soulspot 2>&1 | grep "download\."
```

### Complex Filters (Combine with grep)

```bash
# Errors from spotify_sync in last hour
docker logs --since 1h soulspot 2>&1 | grep "spotify_sync" | grep "ERROR"

# Slow operations >500ms
docker logs soulspot 2>&1 | grep "duration_ms" | grep -E "duration_ms\": [5-9][0-9]{2,}"

# All sync operations (started + completed)
docker logs soulspot 2>&1 | grep -E "sync\..*\.(started|completed)"
```

---

## JSON Log Analysis (if enabled)

If `LOG_FORMAT=json` is set, use `jq` for structured analysis:

```bash
# Pretty print JSON logs
docker logs soulspot 2>&1 | grep "^{" | jq .

# Extract specific fields
docker logs soulspot 2>&1 | grep "^{" | jq -r '.message, .correlation_id'

# Filter by field value
docker logs soulspot 2>&1 | grep "^{" | jq 'select(.level == "ERROR")'

# Group errors by type
docker logs soulspot 2>&1 | grep "^{" | jq -r 'select(.level == "ERROR") | .error_type' | sort | uniq -c
```

---

## Performance Metrics from Logs

### Calculate Average Duration

```bash
# Extract all duration_ms values
docker logs soulspot 2>&1 | grep "sync.playlists.completed" | grep -o "duration_ms\": [0-9]*" | cut -d' ' -f2

# Calculate average (requires bc)
docker logs soulspot 2>&1 | grep "sync.playlists.completed" | grep -o "duration_ms\": [0-9]*" | cut -d' ' -f2 | awk '{sum+=$1; count++} END {print sum/count}'
```

### Count Operations

```bash
# How many syncs completed?
docker logs soulspot 2>&1 | grep "sync.*.completed" | wc -l

# How many errors?
docker logs soulspot 2>&1 | grep "ERROR" | wc -l

# Operations by type
docker logs soulspot 2>&1 | grep -o "sync\.[a-z_]*\.completed" | sort | uniq -c
```

### Error Rate

```bash
# Total operations
total=$(docker logs soulspot 2>&1 | grep "download.*.completed" | wc -l)

# Failed operations
failed=$(docker logs soulspot 2>&1 | grep "download.*.failed" | wc -l)

# Calculate percentage
echo "scale=2; ($failed / $total) * 100" | bc
```

---

## Alert Patterns

### High Error Rate

```bash
# Alert if >10 errors in last 5 minutes
errors=$(docker logs --since 5m soulspot 2>&1 | grep "ERROR" | wc -l)
if [ "$errors" -gt 10 ]; then
    echo "ALERT: High error rate ($errors errors in 5 min)"
fi
```

### Worker Not Healthy

```bash
# Check if worker has reported health in last 10 minutes
last_health=$(docker logs --since 10m soulspot 2>&1 | grep "worker.health" | grep "spotify_sync" | wc -l)
if [ "$last_health" -eq 0 ]; then
    echo "ALERT: spotify_sync worker not reporting health"
fi
```

### Slow Operations

```bash
# Alert if any operation >5 seconds
docker logs --since 1h soulspot 2>&1 | grep "duration_ms" | grep -E "duration_ms\": [5-9][0-9]{3,}"
if [ $? -eq 0 ]; then
    echo "ALERT: Slow operations detected (>5s)"
fi
```

---

## Troubleshooting Checklist

### When debugging issues, check:

- [ ] **Worker Status:** Are all workers started? (`grep "worker.started"`)
- [ ] **Recent Errors:** Any errors in last hour? (`docker logs --since 1h | grep ERROR`)
- [ ] **Token Status:** Valid auth tokens? (`grep "token.*expired"`)
- [ ] **Slow Operations:** Any performance issues? (`grep "operation.slow"`)
- [ ] **Worker Health:** Recent health reports? (`grep "worker.health"`)
- [ ] **Exception Types:** What exceptions are occurring? (`grep "╰─►"`)
- [ ] **Correlation IDs:** Can you trace full request flow?

---

## Common Issues & Solutions

### Issue: No logs appearing

**Check:**
```bash
# Is container running?
docker ps | grep soulspot

# Are logs being written to stdout?
docker exec soulspot cat /proc/1/fd/1
```

### Issue: Logs too verbose

**Solution:**
```bash
# Adjust log level
# In docker-compose.yml or .env:
LOG_LEVEL=WARNING  # Instead of DEBUG
```

### Issue: Can't find specific operation

**Solution:**
```bash
# Use broader pattern first
docker logs soulspot 2>&1 | grep "spotify"

# Then narrow down
docker logs soulspot 2>&1 | grep "spotify.*sync.*completed"
```

### Issue: Correlation ID not helping

**Check:**
- Is middleware enabled? (`grep RequestLoggingMiddleware`)
- Are you looking at API routes? (correlation ID only set for HTTP requests)
- Background workers don't have correlation IDs

---

## Related Documentation

- [Logging Standards](../development/LOGGING_STANDARDS.md)
- [Troubleshooting Guide](../guides/user/troubleshooting-guide.md)
- [Monitoring Guide](../operations/MONITORING.md)

---

## Changelog

### 2025-12-30 - Version 1.0
- Initial log analysis guide
- Added common patterns and workflows
- Added filtering techniques and examples
