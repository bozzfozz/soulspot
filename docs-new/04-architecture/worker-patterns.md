# Worker Patterns

**Category:** Architecture  
**Last Updated:** 2024-01-XX  
**Related Docs:** [Auth Patterns](./auth-patterns.md) | [Error Handling](./error-handling.md) | [Configuration](./configuration.md)

---

## Overview

SoulSpot uses background workers for asynchronous tasks (playlist syncing, token refresh, download monitoring). Workers follow standardized lifecycle patterns for reliability and maintainability.

**Two Worker Patterns:**
1. **Standalone Loop Workers** - Periodic tasks (run every N seconds)
2. **Job-Based Workers** - Event-triggered tasks (process jobs from queue)

---

## Standalone Loop Worker Pattern

### Standard Lifecycle

All standalone loop workers **MUST** implement these methods:

```python
class ExampleWorker:
    """Standard standalone loop worker pattern.
    
    Used for periodic tasks that run every N seconds.
    Examples: TokenRefreshWorker, SpotifySyncWorker, CleanupWorker
    """
    
    def __init__(
        self,
        dependencies...,
        check_interval_seconds: int = 300,
    ) -> None:
        """Initialize worker with dependencies.
        
        ⚠️ NO async operations in __init__!
        Only dependency assignment and state setup.
        """
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self.interval = check_interval_seconds
        # Store dependencies
    
    async def start(self) -> None:
        """Start the worker background task.
        
        Creates asyncio.Task that runs _run_loop().
        Idempotent - safe to call multiple times.
        """
        if self._running:
            logger.warning(f"{self.__class__.__name__} is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"{self.__class__.__name__} started (interval: {self.interval}s)")
    
    async def stop(self) -> None:
        """Stop the worker gracefully.
        
        Cancels the task and waits for cleanup.
        Idempotent - safe to call multiple times.
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info(f"{self.__class__.__name__} stopped")
    
    async def _run_loop(self) -> None:
        """Main worker loop - runs forever until stop() called.
        
        Pattern:
        1. Initial delay (let other services start)
        2. While running: do work → sleep → repeat
        3. Catch ALL exceptions (loop must never crash!)
        """
        # Initial startup delay
        await asyncio.sleep(10)
        
        while self._running:
            try:
                await self._do_work()
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                # ⚠️ NEVER re-raise - loop must continue!
            
            # Sleep with cancellation support
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
    
    async def _do_work(self) -> None:
        """Actual work implementation.
        
        Override this method with your worker's logic.
        """
        raise NotImplementedError
    
    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.
        
        Returns standardized status dict.
        """
        return {
            "name": self.__class__.__name__,
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "interval_seconds": self.interval,
        }
```

**Source:** Pattern used in `src/soulspot/application/services/workers/`

---

### Worker Registration (Lifecycle)

Workers registered in `src/soulspot/infrastructure/lifecycle.py`:

```python
# src/soulspot/infrastructure/lifecycle.py

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # === STARTUP ===
    
    # 1. Initialize worker with dependencies
    my_worker = MyWorker(
        dependency_a=dep_a,
        dependency_b=dep_b,
        check_interval_seconds=300,
    )
    
    # 2. Start worker (creates background task)
    await my_worker.start()
    
    # 3. Store on app.state for status queries
    app.state.my_worker = my_worker
    logger.info("MyWorker started successfully")
    
    yield  # App runs here
    
    # === SHUTDOWN ===
    
    # Stop workers in REVERSE order (dependencies last)
    if hasattr(app.state, "my_worker"):
        try:
            logger.info("Stopping MyWorker...")
            await app.state.my_worker.stop()
            logger.info("MyWorker stopped successfully")
        except Exception as e:
            logger.exception(f"Error stopping MyWorker: {e}")
```

**Source:** `src/soulspot/infrastructure/lifecycle.py` (lines 150-350)

---

### Worker Startup Order

Workers **MUST** start in dependency order:

```
STARTUP ORDER (dependencies first):
1. TokenRefreshWorker      ← MUST start FIRST (others need tokens)
2. SpotifySyncWorker       ← Needs TokenRefreshWorker
3. NewReleasesSyncWorker   ← Needs TokenRefreshWorker
4. PlaylistSyncWorker      ← Needs TokenRefreshWorker
5. AutomationWorkers       ← Need TokenRefreshWorker
6. DownloadWorker          ← Independent
7. QueueDispatcherWorker   ← Needs DownloadWorker
8. StatusSyncWorker        ← Needs slskd client

SHUTDOWN ORDER (reverse!):
8. StatusSyncWorker
7. QueueDispatcherWorker
6. DownloadWorker
5. AutomationWorkers
4. PlaylistSyncWorker
3. NewReleasesSyncWorker
2. SpotifySyncWorker
1. TokenRefreshWorker      ← MUST stop LAST
```

**Why:** Dependent workers need their dependencies running. Shutdown reverses to avoid breaking dependencies.

---

### Token Manager Integration

Workers using Spotify/Deezer **MUST** handle token availability:

```python
class MySpotifyWorker:
    def __init__(
        self,
        token_manager: DatabaseTokenManager | None = None,
        spotify_plugin: SpotifyPlugin,
        ...
    ) -> None:
        self._token_manager = token_manager
        self._spotify_plugin = spotify_plugin
    
    def set_token_manager(self, token_manager: DatabaseTokenManager) -> None:
        """Set token manager post-construction.
        
        Called in lifecycle.py after DatabaseTokenManager is initialized.
        """
        self._token_manager = token_manager
    
    async def _do_work(self) -> None:
        """Check for valid token BEFORE doing work."""
        
        # 1. Check if token manager available
        if self._token_manager is None:
            logger.warning("No token manager - skipping work")
            return
        
        # 2. Get shared worker token (None if expired/invalid)
        token = await self._token_manager.get_token_for_background()
        if token is None:
            logger.debug("No valid token - skipping work")
            return
        
        # 3. Token available - do actual work
        self._spotify_plugin.set_access_token(token)
        playlists = await self._spotify_plugin.get_user_playlists()
        # ... process playlists
```

**Pattern:** Always check token availability before calling external APIs.

**Source:** `src/soulspot/application/services/workers/watchlist_worker.py`

---

### Database Session Pattern

Workers **MUST** use fresh sessions per work cycle:

```python
class MyDatabaseWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ...
    ) -> None:
        self._session_factory = session_factory
    
    async def _do_work(self) -> None:
        """Each work cycle gets fresh session."""
        async with self._session_factory() as session:
            try:
                # Do work with session
                repo = MyRepository(session)
                data = await repo.get_all()
                await self._process(data)
                
                # Commit on success
                await session.commit()
                
            except Exception as e:
                # Rollback on error
                await session.rollback()
                raise
```

**Alternative with session_scope:**

```python
class MyDatabaseWorker:
    def __init__(
        self,
        db: Database,  # Has session_scope() method
        ...
    ) -> None:
        self._db = db
    
    async def _do_work(self) -> None:
        """Use session_scope for automatic commit/rollback."""
        async with self._db.session_scope() as session:
            # Session automatically committed on exit
            # Automatically rolled back on exception
            repo = MyRepository(session)
            await repo.update(...)
```

**Source:** `src/soulspot/infrastructure/persistence/database.py`

---

### Error Handling in Workers

```python
async def _run_loop(self) -> None:
    """Main loop with robust error handling."""
    
    # Initial delay for service startup
    await asyncio.sleep(10)
    
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5
    ERROR_BACKOFF_SECONDS = 60
    
    while self._running:
        try:
            await self._do_work()
            consecutive_errors = 0  # Reset on success
            
        except asyncio.CancelledError:
            # Worker being stopped - exit cleanly
            break
            
        except ExternalServiceError as e:
            # External service (Spotify, slskd) down
            consecutive_errors += 1
            logger.warning(f"External service error: {e}")
            
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.error(
                    f"Too many consecutive errors ({consecutive_errors}) - backing off"
                )
                await asyncio.sleep(ERROR_BACKOFF_SECONDS)
                consecutive_errors = 0
            
        except Exception as e:
            # Unexpected error - log but don't crash
            logger.exception(f"Unexpected error in worker: {e}")
            consecutive_errors += 1
        
        # Normal sleep between work cycles
        try:
            await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            break
```

**Key Points:**
- ✅ Catch ALL exceptions (loop must never crash!)
- ✅ Track consecutive errors (backoff if service down)
- ✅ Handle CancelledError for graceful shutdown
- ❌ NEVER re-raise exceptions from _do_work()

---

### Circuit Breaker Pattern

For workers calling external services:

```python
class ExternalServiceWorker:
    def __init__(self, ...):
        self._circuit_open = False
        self._circuit_open_until: datetime | None = None
        self._failure_count = 0
        self.FAILURE_THRESHOLD = 3
        self.CIRCUIT_TIMEOUT_SECONDS = 60
    
    async def _do_work(self) -> None:
        """Work with circuit breaker protection."""
        
        # Check if circuit breaker is open
        if self._circuit_open:
            if datetime.now(timezone.utc) < self._circuit_open_until:
                logger.debug("Circuit breaker open - skipping work")
                return
            
            # Timeout expired - try to close circuit
            self._circuit_open = False
            self._failure_count = 0
            logger.info("Circuit breaker closed - resuming work")
        
        try:
            await self._call_external_service()
            self._failure_count = 0  # Success resets counter
            
        except ExternalServiceError:
            self._failure_count += 1
            
            if self._failure_count >= self.FAILURE_THRESHOLD:
                # Too many failures - open circuit
                self._circuit_open = True
                self._circuit_open_until = (
                    datetime.now(timezone.utc) 
                    + timedelta(seconds=self.CIRCUIT_TIMEOUT_SECONDS)
                )
                logger.warning(
                    f"Circuit breaker opened - will retry in {self.CIRCUIT_TIMEOUT_SECONDS}s"
                )
```

**Circuit Breaker States:**
- **CLOSED** (healthy) → Requests pass through
- **OPEN** (unhealthy) → Requests blocked, service given time to recover
- **HALF_OPEN** (testing) → Limited requests allowed to test recovery

**Source:** Pattern used in `src/soulspot/application/services/workers/status_sync_worker.py`

---

### Worker Status for UI

All workers **MUST** implement `get_status()`:

```python
def get_status(self) -> dict[str, Any]:
    """Get status for monitoring and UI display.
    
    Returns:
        Standardized status dict with:
        - name: Worker class name
        - running: bool (is worker running)
        - status: str ('active', 'idle', 'stopped', 'error')
        - interval_seconds: int (check interval)
        - last_run: datetime | None (when last work completed)
        - next_run: datetime | None (when next work scheduled)
        - statistics: dict (worker-specific stats)
    """
    return {
        "name": self.__class__.__name__,
        "running": self._running,
        "status": self._get_status_string(),
        "interval_seconds": self.interval,
        "last_run": self._last_run,
        "next_run": self._next_run,
        "statistics": {
            "items_processed": self._items_processed,
            "errors": self._error_count,
            "consecutive_errors": self._consecutive_errors,
        },
    }

def _get_status_string(self) -> str:
    """Determine status for UI display."""
    if not self._running:
        return "stopped"
    if self._circuit_open:
        return "error"
    if self._is_working:
        return "active"
    return "idle"
```

**Source:** `src/soulspot/api/routers/workers.py` (lines 52-100)

---

## Job-Based Worker Pattern

### When to Use

**Use Job-Based Workers when:**
- Work triggered by external events (user requests, scan completion)
- Jobs should be persisted and retried on failure
- Concurrency controlled by queue (not by worker)

**Examples:** DownloadWorker, MetadataWorker, LibraryScanWorker

---

### Standard Structure

```python
class JobBasedWorker:
    """Worker that processes jobs from JobQueue.
    
    This pattern is used when:
    - Work triggered by external events (user requests, scan completion)
    - Jobs should be persisted and retried on failure
    - Concurrency managed by JobQueue (not worker)
    """
    
    def __init__(
        self,
        job_queue: JobQueue,
        other_dependencies...,
    ) -> None:
        """Initialize with dependencies.
        
        ⚠️ NO start/stop methods - lifecycle managed by JobQueue!
        """
        self._job_queue = job_queue
        # Store other dependencies
    
    def register(self) -> None:
        """Register job handlers with queue.
        
        ⚠️ Call AFTER app fully initialized, BEFORE queue.start()!
        Tells JobQueue: "when JobType.X arrives, call my handler"
        """
        self._job_queue.register_handler(
            JobType.MY_JOB_TYPE,
            self._handle_my_job
        )
    
    async def _handle_my_job(self, job: Job) -> dict[str, Any]:
        """Handle a single job.
        
        Called by JobQueue when job ready to process.
        
        Args:
            job: Job with payload to process
            
        Returns:
            Result dict (stored in job.result)
            
        Raises:
            Exception: Triggers retry if max_retries not reached
            ValueError: Marks job as FAILED (no retry for bad data)
        """
        # Extract and validate payload
        required_param = job.payload.get("required_param")
        if not required_param:
            raise ValueError("Missing required_param in job payload")
        
        # Execute work
        result = await self._do_actual_work(required_param)
        
        # Check for errors
        if result.error_message:
            raise Exception(result.error_message)  # Triggers retry
        
        return {
            "status": "completed",
            "processed": result.count,
        }
    
    async def enqueue_job(
        self,
        param: str,
        max_retries: int = 3,
        priority: int = 0,
    ) -> str:
        """Public API to queue a job.
        
        Called by routes/services to queue work.
        
        Returns:
            job_id for tracking
        """
        return await self._job_queue.enqueue(
            job_type=JobType.MY_JOB_TYPE,
            payload={"required_param": param},
            max_retries=max_retries,
            priority=priority,
        )
```

**Source:** `src/soulspot/application/services/workers/download_worker.py`

---

### Pattern Comparison

| Aspect | Standalone Loop Worker | Job-Based Worker |
|--------|------------------------|------------------|
| **Lifecycle** | Own `start()`/`stop()` | Managed by JobQueue |
| **Trigger** | Periodic (interval) | Event-based (job enqueued) |
| **Retry** | Manual implementation | JobQueue built-in |
| **Concurrency** | Own asyncio.Task | JobQueue `max_concurrent` |
| **Status** | `get_status()` on worker | `job_queue.get_stats()` |
| **Examples** | CleanupWorker, SpotifySyncWorker | DownloadWorker, MetadataWorker |

---

### Job-Based Worker Registration

```python
# src/soulspot/infrastructure/lifecycle.py

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # === SETUP ===
    
    # 1. Create JobQueue first
    job_queue = JobQueue(max_concurrent_jobs=3)
    
    # 2. Create job-based workers
    download_worker = DownloadWorker(
        job_queue=job_queue,
        slskd_client=slskd_client,
        track_repository=track_repo,
        download_repository=download_repo,
    )
    
    # 3. Register handlers (tells queue which handler for which job type)
    download_worker.register()
    
    # 4. Start the JobQueue (starts worker loops)
    await job_queue.start(num_workers=3)
    
    # 5. Store on app.state
    app.state.job_queue = job_queue
    app.state.download_worker = download_worker
    
    yield
    
    # === SHUTDOWN ===
    
    # Stop JobQueue (all job-based workers stop automatically)
    await job_queue.stop()
```

**Source:** `src/soulspot/infrastructure/lifecycle.py`

---

## Worker Manager Pattern

For groups of related workers:

```python
class AutomationWorkerManager:
    """Manager for related workers - start/stop as group."""
    
    def __init__(
        self,
        watchlist_worker: WatchlistWorker,
        discography_worker: DiscographyWorker,
        quality_worker: QualityWorker,
    ):
        self.watchlist_worker = watchlist_worker
        self.discography_worker = discography_worker
        self.quality_worker = quality_worker
    
    def set_token_manager(self, token_manager: DatabaseTokenManager) -> None:
        """Set token manager for all workers that need it."""
        self.watchlist_worker.set_token_manager(token_manager)
        self.discography_worker.set_token_manager(token_manager)
        # quality_worker doesn't need tokens
    
    async def start_all(self) -> None:
        """Start all managed workers."""
        await self.watchlist_worker.start()
        await self.discography_worker.start()
        await self.quality_worker.start()
        logger.info("All automation workers started")
    
    async def stop_all(self) -> None:
        """Stop all managed workers gracefully (reverse order)."""
        await self.quality_worker.stop()
        await self.discography_worker.stop()
        await self.watchlist_worker.stop()
        logger.info("All automation workers stopped")
    
    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all managed workers."""
        return {
            "watchlist": self.watchlist_worker.get_status(),
            "discography": self.discography_worker.get_status(),
            "quality": self.quality_worker.get_status(),
        }
```

**Source:** Pattern used in automation worker management

---

## Worker Configuration

Workers should be configurable via app settings:

```python
class ConfigurableWorker:
    def __init__(
        self,
        db: Database,
        check_interval_seconds: int = 300,  # Sensible default
        ...
    ) -> None:
        self._db = db
        self.interval = check_interval_seconds
    
    async def _do_work(self) -> None:
        """Check if worker enabled in settings before running."""
        
        async with self._db.session_scope() as session:
            settings_service = AppSettingsService(session)
            
            # Check if worker enabled
            if not await settings_service.get_bool("my_worker.enabled"):
                logger.debug("Worker disabled in settings - skipping")
                return
            
            # Get dynamic interval from settings
            self.interval = await settings_service.get_int(
                "my_worker.interval_seconds",
                default=300
            )
            
            # Do actual work
            await self._perform_work()
```

**Source:** `src/soulspot/application/services/app_settings_service.py`

---

## Adding New Worker Checklist

### Standalone Loop Worker

- [ ] Implements: `__init__`, `start()`, `stop()`, `_run_loop()`, `_do_work()`, `get_status()`
- [ ] `start()` and `stop()` are idempotent (safe to call multiple times)
- [ ] `_run_loop()` NEVER crashes (all exceptions caught)
- [ ] Has initial startup delay (`await asyncio.sleep(10)`)
- [ ] Uses fresh session per work cycle (not reused)
- [ ] Registered in `lifecycle.py` (startup + shutdown)
- [ ] Stored on `app.state` for status queries
- [ ] Has status endpoint in `/api/workers` router
- [ ] Respects app settings for enable/disable
- [ ] Has circuit breaker if calling external services
- [ ] Token manager integration if using Spotify/Deezer

---

### Job-Based Worker

- [ ] Has: `__init__`, `register()`, `_handle_*()`, `enqueue_*()` (public API)
- [ ] Handler raises `ValueError` for bad data (no retry)
- [ ] Handler raises `Exception` for transient errors (triggers retry)
- [ ] Uses fresh session per job execution (via `db.session_scope()`)
- [ ] Registered in `lifecycle.py` via `worker.register()` BEFORE `job_queue.start()`
- [ ] JobQueue stored on `app.state` for status queries
- [ ] Uses JobQueue's built-in retry/priority/concurrency

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                  STANDALONE LOOP WORKER                          │
├─────────────────────────────────────────────────────────────────┤
│  __init__()    │ Store dependencies, init state                 │
│  start()       │ Create asyncio.Task, idempotent                │
│  _run_loop()   │ Forever loop: work → sleep → repeat            │
│  _do_work()    │ Actual work, may raise exceptions              │
│  stop()        │ Cancel task, cleanup, idempotent               │
│  get_status()  │ Return dict for monitoring/UI                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   JOB-BASED WORKER                               │
├─────────────────────────────────────────────────────────────────┤
│  __init__()    │ Store dependencies, create use_case            │
│  register()    │ Register handler with JobQueue                 │
│  _handle_*()   │ Process single job from queue                  │
│  enqueue_*()   │ Public API to queue new jobs                   │
│                │ Lifecycle managed by JobQueue.start()/stop()   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CRITICAL RULES                              │
├─────────────────────────────────────────────────────────────────┤
│  ❌ NEVER      │ Let loop crash (catch all exceptions!)         │
│  ❌ NEVER      │ Reuse sessions across work cycles              │
│  ❌ NEVER      │ Call external services without circuit breaker │
│  ✅ ALWAYS     │ Initial delay (10s) on startup                 │
│  ✅ ALWAYS     │ Check token before work (if OAuth needed)      │
│  ✅ ALWAYS     │ Respect settings (enabled/interval)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- **[Auth Patterns](./auth-patterns.md)** - TokenRefreshWorker, OAuth token management
- **[Error Handling](./error-handling.md)** - ExternalServiceError, exception patterns
- **[Configuration](./configuration.md)** - AppSettingsService for worker configuration
- **[API Reference: Workers](../01-api-reference/workers.md)** - Worker control endpoints

---

**Last Validated:** 2024-01-XX (against current source code)  
**Validation:** All patterns verified against actual worker implementations
