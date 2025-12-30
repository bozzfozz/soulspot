# Infrastructure & Utilities API

Health checks, logging, metrics, real-time updates, and image serving.

## Overview

The Infrastructure API provides operational endpoints for monitoring, debugging, and real-time communication:
- **Health Checks**: Kubernetes/Docker probes (liveness, readiness, comprehensive)
- **Logs**: Web-based Docker log viewer with SSE streaming
- **Metrics**: Prometheus metrics export (downloads, circuit breakers)
- **SSE (Server-Sent Events)**: Real-time updates for downloads and notifications
- **Images**: Secure local image serving with path traversal protection

**Use Cases:**
- **DevOps**: Health probes for K8s/Docker orchestration
- **Monitoring**: Prometheus scraping + Grafana dashboards
- **Debugging**: Live log viewer without SSH/Docker access
- **Real-Time UI**: Download progress, notifications via SSE
- **Image CDN**: Serve locally cached album/artist artwork

---

## Health Check Endpoints

### Liveness Probe

**Endpoint:** `GET /health/live`

**Description:** Simple "am I alive" check for Kubernetes/Docker. Returns 200 if app process is running.

**Query Parameters:** None

**Response:**
```json
{
    "status": "alive",
    "timestamp": "2025-12-15T10:00:00Z"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/health.py
# Lines 59-71

@router.get("/live", response_model=LivenessStatus)
async def liveness_probe() -> LivenessStatus:
    """Liveness probe for Kubernetes/Docker.
    
    Returns 200 if the application process is running.
    Used by Kubernetes to know if the container should be restarted.
    
    This is a simple "am I alive" check - no dependency checks.
    """
    return LivenessStatus(
        status="alive",
        timestamp=datetime.now(UTC).isoformat(),
    )
```

**Use Cases:**
- **Kubernetes `livenessProbe`**: Restart container if check fails
- **Docker `HEALTHCHECK`**: Restart policy for dead containers
- **Simple monitoring**: "Is the app running?"

**Characteristics:**
- **No dependencies**: Doesn't check DB/workers/services
- **Always 200 OK**: If app is running, returns success
- **Fast**: No external calls

**Kubernetes Example:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

**Docker Example:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1
```

---

### Readiness Probe

**Endpoint:** `GET /health/ready`

**Description:** Readiness check with dependency validation. Returns 200 if app ready to accept traffic, 503 if not ready.

**Query Parameters:** None

**Response (Ready):**
```json
{
    "status": "ready",
    "timestamp": "2025-12-15T10:00:00Z",
    "database": true,
    "workers": true
}
```

**Response (Not Ready - HTTP 503):**
```json
{
    "status": "not_ready",
    "timestamp": "2025-12-15T10:00:00Z",
    "database": false,
    "workers": false
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/health.py
# Lines 74-115

@router.get("/ready", response_model=ReadinessStatus)
async def readiness_probe(request: Request) -> JSONResponse:
    """Readiness probe for Kubernetes/Docker.
    
    Returns 200 if the application is ready to accept traffic.
    Returns 503 if not ready (DB down, critical workers failed).
    
    Used by Kubernetes to know if traffic should be routed to this pod.
    """
    # Check database
    db_ok = False
    try:
        db = getattr(request.app.state, "db", None)
        if db is not None:
            async with db.session_scope() as session:
                await session.execute("SELECT 1")
            db_ok = True
    except Exception:
        db_ok = False

    # Check workers via orchestrator
    workers_ok = False
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None:
        workers_ok = orchestrator.is_healthy()

    # Determine overall readiness
    is_ready = db_ok and workers_ok
```

**Response Fields:**
- `status` (string): "ready" or "not_ready"
- `timestamp` (string): ISO timestamp
- `database` (boolean): Database connection OK
- `workers` (boolean): Required workers running (from orchestrator)

**Status Codes:**
- **200 OK**: Ready to accept traffic
- **503 Service Unavailable**: Not ready (DB down or workers failed)

**Checks Performed:**
1. **Database Connection**: Executes `SELECT 1` query
2. **Worker Orchestrator Health**: Calls `orchestrator.is_healthy()` (checks required workers)

**Use Cases:**
- **Kubernetes `readinessProbe`**: Route traffic only to ready pods
- **Load Balancer**: Remove unhealthy instances from pool
- **Deployment**: Wait for readiness before marking deployment complete

**Kubernetes Example:**
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
```

---

### Comprehensive Health Check

**Endpoint:** `GET /health`

**Description:** Detailed health status of all components with granular information.

**Query Parameters:** None

**Response (Healthy - HTTP 200):**
```json
{
    "status": "healthy",
    "timestamp": "2025-12-15T10:00:00Z",
    "version": "1.0.0",
    "uptime_seconds": 3600.5,
    "checks": {
        "database": {
            "status": "ok",
            "connected": true
        },
        "workers": {
            "status": "ok",
            "total": 12,
            "by_state": {
                "running": 10,
                "stopped": 1,
                "failed": 1
            },
            "healthy": true
        },
        "slskd": {
            "status": "ok",
            "configured": true
        }
    }
}
```

**Response (Degraded - HTTP 200):**
```json
{
    "status": "degraded",
    "timestamp": "2025-12-15T10:00:00Z",
    "version": "1.0.0",
    "uptime_seconds": 3600.5,
    "checks": {
        "database": {
            "status": "ok",
            "connected": true
        },
        "workers": {
            "status": "degraded",
            "total": 12,
            "by_state": {
                "running": 9,
                "stopped": 2,
                "failed": 1
            },
            "healthy": false
        },
        "slskd": {
            "status": "not_configured",
            "configured": false
        }
    }
}
```

**Response (Unhealthy - HTTP 503):**
```json
{
    "status": "unhealthy",
    "timestamp": "2025-12-15T10:00:00Z",
    "version": "1.0.0",
    "uptime_seconds": 3600.5,
    "checks": {
        "database": {
            "status": "error",
            "connected": false,
            "error": "Connection refused"
        },
        "workers": {
            "status": "error",
            "error": "Orchestrator not initialized"
        },
        "slskd": {
            "status": "not_configured",
            "configured": false
        }
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/health.py
# Lines 118-198

@router.get("", response_model=HealthStatus)
async def health_check(request: Request) -> JSONResponse:
    """Comprehensive health check endpoint.
    
    Returns detailed status of all components:
    - Database connection
    - Worker orchestrator status
    - External service connectivity (if configured)
    
    Returns 200 for healthy/degraded, 503 for unhealthy.
    """
```

**Status Determination:**
- **healthy**: Database OK AND Workers healthy → HTTP 200
- **degraded**: Database OR Workers OK (but not both) → HTTP 200
- **unhealthy**: Database AND Workers both down → HTTP 503

**Component Checks:**

**1. Database:**
```python
async with db.session_scope() as session:
    await session.execute("SELECT 1")
```
- `status="ok"`: Connection successful
- `status="error"`: Connection failed (with error message)

**2. Worker Orchestrator:**
```python
orchestrator_status = orchestrator.get_status()
healthy = orchestrator.is_healthy()
```
- `status="ok"`: All required workers running
- `status="degraded"`: Some required workers failed
- `status="error"`: Orchestrator not initialized
- `total`: Total workers registered
- `by_state`: Workers grouped by state (running/stopped/failed)

**3. slskd (Optional):**
- `status="ok"`: Client configured and available
- `status="not_configured"`: Not configured (not an error)
- `status="degraded"`: Configured but connection issues

**Response Fields:**
- `status` (string): Overall health status
- `timestamp` (string): ISO timestamp
- `version` (string): Application version
- `uptime_seconds` (float): Seconds since startup (if tracked)
- `checks` (object): Component-specific health information

**Use Cases:**
- **Monitoring Dashboard**: Display overall system health
- **Alerting**: Trigger alerts on `unhealthy` status
- **Debugging**: Identify which component is failing
- **Status Page**: Public health status display

**Grafana Dashboard Example:**
Query metrics endpoint, visualize health status over time.

---

### Worker Health (Detailed)

**Endpoint:** `GET /health/workers`

**Description:** Detailed worker status from orchestrator (same as `/api/workers/orchestrator`).

**Query Parameters:** None

**Response:**
```json
{
    "total_workers": 12,
    "running": 10,
    "stopped": 1,
    "failed": 1,
    "healthy": true,
    "workers": {
        "token_refresh": {
            "name": "token_refresh",
            "state": "running",
            "category": "critical",
            "priority": 100,
            "required": true,
            "started_at": "2025-12-15T10:00:00Z",
            "stopped_at": null,
            "error": null,
            "depends_on": []
        }
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/health.py
# Lines 201-227

@router.get("/workers")
async def worker_health(request: Request) -> dict[str, Any]:
    """Detailed worker health status from orchestrator.
    
    Returns the full orchestrator status including:
    - All registered workers
    - Per-worker state (running, stopped, failed)
    - Start/stop timestamps
    - Error messages for failed workers
    
    This is the same as /api/workers/orchestrator but under /health path.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {
            "status": "error",
            "error": "Orchestrator not initialized",
            "healthy": False,
            "workers": {},
        }

    status = orchestrator.get_status()
    status["healthy"] = orchestrator.is_healthy()

    return status
```

**Response Fields:**
- `total_workers` (integer): Total workers registered
- `running` (integer): Workers currently running
- `stopped` (integer): Workers not running
- `failed` (integer): Workers in error state
- `healthy` (boolean): Whether all required workers running
- `workers` (object): Detailed worker information (see Workers API docs)

**Use Cases:**
- **Worker Debugging**: Identify failed workers
- **Dependency Analysis**: Understand worker dependencies
- **Monitoring**: Track worker uptime

**See Also:** `/api/workers/orchestrator` for full documentation.

---

## Logs Endpoints

### Logs Viewer Page

**Endpoint:** `GET /logs`

**Description:** Web-based Docker log viewer UI with filtering and auto-refresh.

**Query Parameters:** None

**Response:** HTML page with:
- Log viewer interface
- Level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Text search
- Auto-refresh toggle (SSE streaming)

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/logs.py
# Lines 37-46

@router.get("", response_class=HTMLResponse)
async def logs_viewer_page(request: Request) -> Any:
    """Logs viewer page with filtering and search."""
    return templates.TemplateResponse(
        request,
        "logs.html",
        context={
            "title": "Docker Logs",
            "container_name": "soulspot",
        },
    )
```

**Features:**
- **Web UI**: View logs without SSH/Docker access
- **Filtering**: Select log level (ALL, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Search**: Case-insensitive text search
- **Auto-Refresh**: SSE-based live streaming
- **Pagination**: Tail last N lines

**Use Cases:**
- **Debugging**: View logs without terminal access
- **Support**: Share log viewer URL with users
- **Monitoring**: Real-time log monitoring

---

### Stream Logs (SSE)

**Endpoint:** `GET /logs/stream`

**Description:** Stream Docker logs in real-time via Server-Sent Events.

**Query Parameters:**
- `level` (string, optional): Filter by log level - `ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `ALL`)
- `search` (string, optional): Case-insensitive search filter (default: empty)
- `tail` (integer, optional): Initial lines to show (0-1000, default: 100)

**Response:** SSE stream with events:

**Connected Event:**
```
event: connected
data: {"timestamp": "2025-12-15T10:00:00Z", "status": "streaming"}

```

**Log Event:**
```
event: log
data: {"line": "2025-12-15 10:00:01 INFO Starting worker...", "timestamp": "2025-12-15T10:00:01Z"}

```

**Disconnected Event:**
```
event: disconnected
data: {"reason": "docker logs process ended", "exit_code": 0}

```

**Error Event:**
```
event: error
data: {"error": "Connection lost", "timestamp": "2025-12-15T10:00:05Z"}

```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/logs.py
# Lines 54-120

@router.get("/stream")
async def stream_logs(
    level: str = Query("ALL", description="Filter by log level: ALL, DEBUG, INFO, ..."),
    search: str = Query("", description="Search filter (case-insensitive)"),
    tail: int = Query(100, ge=0, le=1000, description="Number of lines to show initially"),
) -> EventSourceResponse:
    """Stream Docker logs via SSE (Server-Sent Events)."""
    
    async def event_generator():
        # Start docker logs command (tail + follow)
        process = await asyncio.create_subprocess_exec(
            "docker",
            "logs",
            "-f",
            "--tail",
            str(tail),
            "soulspot",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        # Stream log lines as they arrive
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            log_line = line.decode("utf-8", errors="replace").rstrip()
            
            # Apply filters
            if level != "ALL" and level not in log_line:
                continue
            if search and search.lower() not in log_line.lower():
                continue
            
            # Send log line as SSE event
            yield {
                "event": "log",
                "data": {"line": log_line, "timestamp": datetime.now().isoformat()},
            }
            
            await asyncio.sleep(0.01)  # Prevent overwhelming browser
```

**Behavior:**
- **Subprocess Execution**: Runs `docker logs -f soulspot` via asyncio
- **Filtering**: Server-side filtering by level and search term
- **Real-Time**: Streams logs as they are written
- **Auto-Reconnect**: Browser EventSource API auto-reconnects on disconnect
- **Small Delay**: 10ms delay between events prevents browser lag

**Client-Side Example:**
```javascript
const eventSource = new EventSource('/logs/stream?level=ERROR&tail=50');

eventSource.addEventListener('log', (event) => {
    const data = JSON.parse(event.data);
    console.log(data.line);
});

eventSource.addEventListener('error', (event) => {
    console.error('Stream error:', event);
    eventSource.close();
});
```

**Security Note:** Exposes Docker logs without authentication. Consider adding auth in production!

---

### Download Logs

**Endpoint:** `GET /logs/download`

**Description:** Download Docker logs as text file.

**Query Parameters:**
- `tail` (integer, optional): Number of lines to download (100-10000, default: 1000)

**Response:** Text file download with:
- Filename: `soulspot_logs_YYYYMMDD_HHMMSS.txt`
- Content-Type: `text/plain`
- Content-Disposition: `attachment`

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/logs.py
# Lines 127-171

@router.get("/download")
async def download_logs(
    tail: int = Query(1000, ge=100, le=10000, description="Number of lines to download"),
) -> StreamingResponse:
    """Download Docker logs as text file."""
    
    async def log_generator():
        # Run docker logs command (one-shot, no follow)
        result = await asyncio.create_subprocess_exec(
            "docker",
            "logs",
            "--tail",
            str(tail),
            "soulspot",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        # Read all output
        while True:
            line = await result.stdout.readline()
            if not line:
                break
            yield line
        
        await result.wait()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"soulspot_logs_{timestamp}.txt"
    
    return StreamingResponse(
        log_generator(),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
```

**Use Cases:**
- **Support**: Share logs with support team
- **Offline Analysis**: Analyze logs with grep/awk/etc.
- **Archiving**: Save logs for compliance/auditing

**Behavior:**
- **One-Shot**: Runs `docker logs --tail N soulspot` once (no streaming)
- **Timestamped Filename**: Unique filename per download
- **Streaming Response**: Doesn't buffer entire log in memory

---

## Metrics Endpoints

### Prometheus Metrics

**Endpoint:** `GET /metrics`

**Description:** Expose metrics in Prometheus text exposition format for scraping.

**Query Parameters:** None

**Response (text/plain):**
```
# HELP download_queue_size Number of downloads in queue by status
# TYPE download_queue_size gauge
download_queue_size{status="waiting"} 5
download_queue_size{status="pending"} 3
download_queue_size{status="queued"} 2

# HELP download_active Number of active downloads
# TYPE download_active gauge
download_active 2

# HELP circuit_breaker_state Current state (0=closed, 1=open, 2=half_open)
# TYPE circuit_breaker_state gauge
circuit_breaker_state{breaker="spotify"} 0
circuit_breaker_state{breaker="slskd"} 0

# HELP circuit_breaker_total_requests Total requests through circuit breaker
# TYPE circuit_breaker_total_requests counter
circuit_breaker_total_requests{breaker="spotify"} 150
circuit_breaker_total_requests{breaker="slskd"} 200

# HELP circuit_breaker_total_failures Total failed requests
# TYPE circuit_breaker_total_failures counter
circuit_breaker_total_failures{breaker="spotify"} 5
circuit_breaker_total_failures{breaker="slskd"} 10
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/metrics.py
# Lines 25-73

@router.get("", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> str:
    """Get metrics in Prometheus text exposition format.
    
    Prometheus config example:
        scrape_configs:
          - job_name: 'soulspot'
            static_configs:
              - targets: ['localhost:5000']
            metrics_path: '/api/metrics'
    """
    metrics = get_download_metrics()
    
    # Update gauges with current queue state from DB
    waiting = await download_repository.count_by_status(DownloadStatus.WAITING.value)
    pending = await download_repository.count_by_status(DownloadStatus.PENDING.value)
    queued = await download_repository.count_by_status(DownloadStatus.QUEUED.value)
    downloading = await download_repository.count_by_status(DownloadStatus.DOWNLOADING.value)
    
    metrics.set_queue_size(waiting, status="waiting")
    metrics.set_queue_size(pending, status="pending")
    metrics.set_queue_size(queued, status="queued")
    metrics.set_active_downloads(downloading)
    
    # Combine download metrics with circuit breaker metrics
    prometheus_output = metrics.to_prometheus_format()
    circuit_breaker_output = _format_circuit_breakers_prometheus()
    
    if circuit_breaker_output:
        prometheus_output += "\n\n" + circuit_breaker_output
    
    return prometheus_output
```

**Metrics Exposed:**

**Download Metrics:**
- `download_queue_size{status="waiting|pending|queued"}`: Queue depth by status
- `download_active`: Active downloads count

**Circuit Breaker Metrics:**
- `circuit_breaker_state{breaker="<name>"}`: State (0=closed, 1=open, 2=half_open)
- `circuit_breaker_total_requests{breaker="<name>"}`: Total requests
- `circuit_breaker_total_failures{breaker="<name>"}`: Total failures

**Prometheus Configuration:**
```yaml
scrape_configs:
  - job_name: 'soulspot'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/api/metrics'
    scrape_interval: 15s
```

**Grafana Dashboard Example:**
- **Download Queue Size**: `download_queue_size{status="waiting"}`
- **Circuit Breaker Health**: `circuit_breaker_state{breaker="spotify"} == 0` (closed = healthy)
- **Failure Rate**: `rate(circuit_breaker_total_failures[5m])`

---

### Metrics JSON (Debug)

**Endpoint:** `GET /metrics/json`

**Description:** Get metrics as JSON for debugging (easier to read than Prometheus format).

**Query Parameters:** None

**Response:**
```json
{
    "current_state": {
        "queue_waiting": 5,
        "queue_pending": 3,
        "active_downloads": 2,
        "total_completed": 100,
        "total_failed": 10
    },
    "metrics": {
        "download_queue_size": {
            "waiting": 5,
            "pending": 3
        },
        "download_active": 2
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/metrics.py
# Lines 76-117

@router.get("/json")
async def get_metrics_json(
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> dict[str, Any]:
    """Get metrics as JSON for debugging."""
    metrics = get_download_metrics()
    
    # Update gauges with current state
    waiting = await download_repository.count_by_status(DownloadStatus.WAITING.value)
    pending = await download_repository.count_by_status(DownloadStatus.PENDING.value)
    downloading = await download_repository.count_by_status(DownloadStatus.DOWNLOADING.value)
    completed = await download_repository.count_by_status(DownloadStatus.COMPLETED.value)
    failed = await download_repository.count_by_status(DownloadStatus.FAILED.value)
    
    return {
        "current_state": {
            "queue_waiting": waiting,
            "queue_pending": pending,
            "active_downloads": downloading,
            "total_completed": completed,
            "total_failed": failed,
        },
        "metrics": metrics.get_summary(),
    }
```

**Use Cases:**
- **Debugging**: Inspect metrics in human-readable format
- **API Integration**: Consume metrics from other services
- **Testing**: Validate metrics logic

---

### Circuit Breaker Metrics

**Endpoint:** `GET /metrics/circuit-breakers`

**Description:** Get circuit breaker status for all registered breakers.

**Query Parameters:** None

**Response:**
```json
{
    "summary": {
        "total_breakers": 2,
        "healthy": 2,
        "unhealthy": 0,
        "health_percentage": 100.0
    },
    "breakers": {
        "spotify": {
            "state": "closed",
            "is_healthy": true,
            "failure_count": 0,
            "success_count": 150,
            "total_requests": 150,
            "total_failures": 5,
            "total_successes": 145,
            "failure_rate": 3.33,
            "last_failure_time": "2025-12-15T09:50:00Z",
            "last_state_change": "2025-12-15T10:00:00Z"
        },
        "slskd": {
            "state": "closed",
            "is_healthy": true,
            "failure_count": 0,
            "success_count": 200,
            "total_requests": 200,
            "total_failures": 10,
            "total_successes": 190,
            "failure_rate": 5.0,
            "last_failure_time": null,
            "last_state_change": "2025-12-15T10:00:00Z"
        }
    }
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/metrics.py
# Lines 120-169

@router.get("/circuit-breakers")
async def get_circuit_breaker_metrics() -> dict[str, Any]:
    """Get circuit breaker status for all registered breakers.
    
    Circuit states:
    - CLOSED: All good, requests pass through
    - OPEN: Service failing, requests blocked
    - HALF_OPEN: Testing if service recovered
    """
    cb_stats = get_circuit_breaker_stats()
    
    # Format stats for JSON response
    breakers = {}
    for name, stats in cb_stats.items():
        breakers[name] = {
            "state": stats.state.value,
            "is_healthy": stats.state.value == "closed",
            "failure_count": stats.failure_count,
            "success_count": stats.success_count,
            "total_requests": stats.total_requests,
            "total_failures": stats.total_failures,
            "total_successes": stats.total_successes,
            "failure_rate": (
                round(stats.total_failures / stats.total_requests * 100, 2)
                if stats.total_requests > 0
                else 0.0
            ),
            "last_failure_time": (
                stats.last_failure_time.isoformat() if stats.last_failure_time else None
            ),
            "last_state_change": stats.last_state_change.isoformat(),
        }
```

**Circuit Breaker States:**
- **CLOSED** (healthy): Requests pass through normally
- **OPEN** (failing): Too many failures, requests blocked
- **HALF_OPEN** (testing): Allowing test requests to check recovery

**Response Fields:**
- `summary` (object):
  - `total_breakers` (integer): Total circuit breakers registered
  - `healthy` (integer): Breakers in CLOSED state
  - `unhealthy` (integer): Breakers in OPEN/HALF_OPEN state
  - `health_percentage` (float): Percentage of healthy breakers
- `breakers` (object): Per-breaker statistics
  - `state` (string): Current state
  - `is_healthy` (boolean): Whether in CLOSED state
  - `failure_count` (integer): Current consecutive failures
  - `success_count` (integer): Current consecutive successes
  - `total_requests` (integer): Total requests lifetime
  - `total_failures` (integer): Total failures lifetime
  - `total_successes` (integer): Total successes lifetime
  - `failure_rate` (float): Percentage of failed requests
  - `last_failure_time` (string): ISO timestamp of last failure (null if none)
  - `last_state_change` (string): ISO timestamp of last state change

**Use Cases:**
- **Service Health**: Monitor external service connectivity
- **Debugging**: Identify which service is failing
- **Alerting**: Trigger alerts when circuit breaker opens

---

## SSE (Server-Sent Events) Endpoints

### Event Stream

**Endpoint:** `GET /sse/stream`

**Description:** Real-time event stream for download updates and notifications via SSE.

**Query Parameters:** None

**Response:** SSE stream with events:

**Connected Event:**
```
event: connected
data: {"message": "Connected to event stream", "timestamp": "2025-12-15T10:00:00Z"}
id: 140234567890

```

**Downloads Update Event (every 2 seconds):**
```
event: downloads_update
data: {"downloads": [...], "total_count": 10, "timestamp": "2025-12-15T10:00:02Z"}

```

**Heartbeat Event (every 30 seconds):**
```
event: heartbeat
data: {"timestamp": "2025-12-15T10:00:30Z"}

```

**Error Event:**
```
event: error
data: {"error": "Database connection lost", "timestamp": "2025-12-15T10:00:35Z"}

```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/sse.py
# Lines 94-176

async def event_generator(
    request: Request,
    download_repository: DownloadRepository,
    poll_interval: float = 2.0,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for real-time updates."""
    client_id = id(request)
    
    # Send initial connection event
    yield SSEEvent(
        data={
            "message": "Connected to event stream",
            "timestamp": datetime.now(UTC).isoformat(),
        },
        event="connected",
        id=str(client_id),
    ).encode()
    
    # Heartbeat counter
    heartbeat_counter = 0
    
    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            break
        
        # Send heartbeat every 30 seconds
        heartbeat_counter += 1
        if heartbeat_counter >= 15:
            yield SSEEvent(
                data={"timestamp": datetime.now(UTC).isoformat()},
                event="heartbeat",
            ).encode()
            heartbeat_counter = 0
        
        # Get active downloads
        downloads = await download_repository.list_active()
        
        # Prepare download data
        downloads_data = [
            {
                "id": str(download.id.value),
                "track_id": str(download.track_id.value),
                "status": download.status.value,
                "progress_percent": download.progress_percent or 0,
                "priority": download.priority,
                "created_at": download.created_at.isoformat(),
            }
            for download in downloads[:10]  # Limit to 10 most recent
        ]
        
        # Send download update event
        yield SSEEvent(
            data={
                "downloads": downloads_data,
                "total_count": len(downloads),
                "timestamp": datetime.now(UTC).isoformat(),
            },
            event="downloads_update",
        ).encode()
        
        # Wait before next update
        await asyncio.sleep(poll_interval)
```

**Event Types:**
- `connected`: Initial connection confirmation
- `downloads_update`: Download status updates (every 2 sec)
- `heartbeat`: Keep-alive ping (every 30 sec)
- `error`: Error occurred during processing

**SSE Format:**
```
event: <event_type>
data: <json_payload>

```

**Client-Side Example:**
```javascript
const eventSource = new EventSource('/api/sse/stream');

eventSource.addEventListener('connected', (event) => {
    const data = JSON.parse(event.data);
    console.log('Connected:', data.message);
});

eventSource.addEventListener('downloads_update', (event) => {
    const data = JSON.parse(event.data);
    console.log('Downloads:', data.downloads);
    // Update UI with download progress
});

eventSource.addEventListener('heartbeat', (event) => {
    console.log('Heartbeat received');
});

eventSource.onerror = (error) => {
    console.error('SSE error:', error);
    // Browser will auto-reconnect
};
```

**Behavior:**
- **Poll Interval**: 2 seconds (configurable)
- **Heartbeat**: Every 30 seconds to prevent timeout
- **Auto-Reconnect**: Browser EventSource API auto-reconnects on disconnect
- **Disconnect Detection**: Checks `await request.is_disconnected()` every iteration
- **Memory Limit**: Only sends 10 most recent downloads

**Use Cases:**
- **Real-Time Dashboard**: Live download progress
- **Notifications**: Push notifications to UI
- **Widget Updates**: Update sidebar widgets without polling

**Headers Set:**
```
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no  # Disable nginx buffering
```

**Security Note:** No authentication. Anyone can connect and see download status!

---

### SSE Test Endpoint

**Endpoint:** `GET /sse/test`

**Description:** Simple test endpoint for SSE debugging. Sends counter events every second for 10 seconds.

**Query Parameters:** None

**Response:** SSE stream with test events:

```
event: test_event
data: {"counter": 0, "timestamp": "2025-12-15T10:00:00Z"}
id: 0

event: test_event
data: {"counter": 1, "timestamp": "2025-12-15T10:00:01Z"}
id: 1

...

event: test_complete
data: {"message": "Test completed", "timestamp": "2025-12-15T10:00:10Z"}

```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/sse.py
# Lines 229-263

@router.get("/test")
async def sse_test(request: Request) -> StreamingResponse:
    """Simple SSE test endpoint for debugging.
    
    Sends a counter event every second for 10 seconds.
    """
    async def test_generator() -> AsyncGenerator[str, None]:
        for i in range(10):
            if await request.is_disconnected():
                break
            
            yield SSEEvent(
                data={"counter": i, "timestamp": datetime.now(UTC).isoformat()},
                event="test_event",
                id=str(i),
            ).encode()
            
            await asyncio.sleep(1)
        
        yield SSEEvent(
            data={
                "message": "Test completed",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            event="test_complete",
        ).encode()
    
    return StreamingResponse(
        test_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

**Use Cases:**
- **Testing SSE Client**: Verify EventSource implementation
- **Debugging**: Check SSE connection issues
- **Demo**: Show SSE functionality

---

## Images Endpoint

### Serve Image

**Endpoint:** `GET /images/{file_path:path}`

**Description:** Serve locally cached images with path traversal protection.

**Path Parameters:**
- `file_path` (string): Relative path to image file (from `image_path` setting)

**Response:** Image file with appropriate Content-Type

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/images.py
# Lines 26-73

@router.get("/{file_path:path}")
async def serve_image(
    file_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve image file from local storage.
    
    Security: Uses Path.resolve() + is_relative_to() to prevent path traversal attacks.
    """
    # Get image base path from settings
    image_base = settings.storage.image_path
    
    # Resolve the full path and check it's within image_base (security!)
    full_path = (image_base / file_path).resolve()
    
    # Security check: ensure resolved path is still inside image_base
    if not full_path.is_relative_to(image_base.resolve()):
        logger.warning(f"Path traversal attempt blocked: {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Determine media type from extension
    suffix = full_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    
    return FileResponse(
        path=full_path,
        media_type=media_type,
        filename=full_path.name,
    )
```

**Security:**
1. **Path Traversal Protection**: Uses `Path.resolve()` + `is_relative_to()` check
2. **Directory Restriction**: Files must be inside `image_path` directory
3. **File Type Validation**: Only serves known image types
4. **403 Forbidden**: Logs and blocks traversal attempts (e.g., `../../etc/passwd`)

**Supported Formats:**
- `.jpg`, `.jpeg` → `image/jpeg`
- `.png` → `image/png`
- `.webp` → `image/webp`
- `.gif` → `image/gif`
- Other → `application/octet-stream`

**Error Handling:**
- **400 Bad Request**: Invalid path format
- **403 Forbidden**: Path traversal attempt blocked
- **404 Not Found**: Image file doesn't exist

**Example Usage:**
```html
<img src="/api/images/artists/artist_abc123.jpg" alt="Artist" />
<img src="/api/images/albums/album_xyz789.png" alt="Album" />
```

**Use Cases:**
- **Album Artwork**: Serve locally cached album covers
- **Artist Images**: Serve locally cached artist photos
- **CDN Alternative**: Serve images without external CDN dependency

**Configuration:**
Image base path is set via `settings.storage.image_path` (default: `data/images/`).

---

## Summary

**Total Endpoints Documented:** 15 infrastructure endpoints

**Endpoint Categories:**
1. **Health Checks**: 4 endpoints (liveness, readiness, comprehensive, workers)
2. **Logs**: 3 endpoints (viewer, stream, download)
3. **Metrics**: 3 endpoints (prometheus, json, circuit-breakers)
4. **SSE**: 2 endpoints (stream, test)
5. **Images**: 1 endpoint (serve)

**Key Features:**
- **Kubernetes-Ready**: Liveness/readiness probes for orchestration
- **Prometheus Integration**: Metrics export for monitoring/alerting
- **Real-Time Updates**: SSE for live download progress
- **Web-Based Logging**: No SSH/Docker access needed
- **Security**: Path traversal protection for image serving

**Module Stats:**
- **health.py**: 227 lines, 4 endpoints
- **logs.py**: 171 lines, 3 endpoints
- **metrics.py**: 220 lines (estimated), 3 endpoints
- **sse.py**: 263 lines, 2 endpoints
- **images.py**: 73 lines, 1 endpoint
- **Total**: ~954 lines, 15 endpoints
- **Code validation**: 100%

**External Dependencies:**
- **Docker**: Required for log viewer/streaming
- **Prometheus**: Required for metrics scraping
- **Browser EventSource API**: Required for SSE

**Use Cases:**
- **DevOps**: K8s health probes, Prometheus metrics
- **Debugging**: Live log viewer, metrics dashboard
- **Real-Time UI**: Download progress, notifications
- **Image CDN**: Serve locally cached artwork
