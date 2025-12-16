# SoulSpot Worker Patterns

> **PFLICHTLEKTÜRE** für alle, die Background Worker schreiben oder ändern.

---

## 1. Worker Lifecycle Standard

Alle Worker MÜSSEN diese Methoden implementieren:

```python
class ExampleWorker:
    """Standard worker pattern."""
    
    def __init__(self, dependencies...) -> None:
        """Initialize worker with dependencies.
        
        Keine async Operationen hier!
        Nur Dependency Assignment und State Setup.
        """
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # ... store dependencies
    
    async def start(self) -> None:
        """Start the worker background task.
        
        Creates asyncio.Task that runs _run_loop().
        Idempotent - safe to call multiple times.
        """
        if self._running:
            logger.warning("Worker is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Worker started (interval: {self.interval}s)")
    
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
        logger.info("Worker stopped")
    
    async def _run_loop(self) -> None:
        """Main worker loop - runs forever until stop().
        
        Pattern:
        1. Optional: Initial delay for startup
        2. While running: do work → sleep → repeat
        3. Handle errors without crashing the loop
        """
        await asyncio.sleep(10)  # Let other services start
        
        while self._running:
            try:
                await self._do_work()
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                # NIEMALS re-raise - Loop muss weiterlaufen!
            
            # Sleep with cancellation support
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
    
    async def _do_work(self) -> None:
        """Actual work implementation."""
        raise NotImplementedError
    
    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI."""
        return {
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "interval_seconds": self.interval,
        }
```

---

## 2. Worker Registration in Lifecycle

Worker werden in `src/soulspot/infrastructure/lifecycle.py` registriert:

```python
# lifecycle.py - App Startup

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ... database setup ...
    
    # === STARTUP ===
    
    # 1. Initialize worker
    my_worker = MyWorker(
        dependency_a=dep_a,
        dependency_b=dep_b,
        check_interval_seconds=300,
    )
    
    # 2. Start worker
    await my_worker.start()
    
    # 3. Store on app.state for access
    app.state.my_worker = my_worker
    logger.info("MyWorker started")
    
    yield
    
    # === SHUTDOWN ===
    
    # Stop in reverse order (dependencies last)
    if hasattr(app.state, "my_worker"):
        try:
            logger.info("Stopping MyWorker...")
            await app.state.my_worker.stop()
            logger.info("MyWorker stopped")
        except Exception as e:
            logger.exception(f"Error stopping MyWorker: {e}")
```

---

## 3. Worker Startup Order

Worker müssen in Abhängigkeitsreihenfolge gestartet werden:

```
1. TokenRefreshWorker      ← Muss ZUERST starten (andere brauchen Token)
2. SpotifySyncWorker       ← Braucht TokenRefreshWorker
3. NewReleasesSyncWorker   ← Braucht TokenRefreshWorker
4. PlaylistSyncWorker      ← Braucht TokenRefreshWorker
5. AutomationWorkers       ← Brauchen TokenRefreshWorker
6. DownloadWorker          ← Unabhängig
7. QueueDispatcherWorker   ← Braucht DownloadWorker
8. DownloadStatusSyncWorker ← Braucht slskd Client
```

**Shutdown: Umgekehrte Reihenfolge!**

---

## 4. Token Manager Integration

Worker die Spotify/Deezer brauchen MÜSSEN Token-Handling haben:

```python
class MySpotifyWorker:
    def __init__(
        self,
        token_manager: "DatabaseTokenManager | None" = None,
        ...
    ) -> None:
        self._token_manager = token_manager
    
    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
        """Set token manager post-construction.
        
        Called in lifecycle.py after DatabaseTokenManager is ready.
        """
        self._token_manager = token_manager
    
    async def _do_work(self) -> None:
        # Check for valid token FIRST
        if self._token_manager is None:
            logger.warning("No token manager - skipping work")
            return
        
        token = await self._token_manager.get_token_for_background()
        if token is None:
            logger.debug("No valid token - skipping work")
            return
        
        # Token available - do actual work
        plugin = SpotifyPlugin(token=token, ...)
        await plugin.get_user_playlists()
```

---

## 5. Database Session Pattern

Worker MÜSSEN eigene Sessions pro Durchlauf verwenden:

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
                # Do work
                repo = MyRepository(session)
                data = await repo.get_all()
                await self._process(data)
                
                # Commit
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                raise
```

**Alternative mit session_scope:**

```python
class MyDatabaseWorker:
    def __init__(
        self,
        db: Database,  # Has session_scope method
        ...
    ) -> None:
        self._db = db
    
    async def _do_work(self) -> None:
        async with self._db.session_scope() as session:
            # Session automatically committed on exit
            # Rolled back on exception
            repo = MyRepository(session)
            await repo.update(...)
```

---

## 6. Error Handling in Workers

```python
async def _run_loop(self) -> None:
    """Main loop with robust error handling."""
    
    # Initial delay
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
                    f"Too many errors ({consecutive_errors}) - backing off"
                )
                await asyncio.sleep(ERROR_BACKOFF_SECONDS)
                consecutive_errors = 0
            
        except Exception as e:
            # Unexpected error - log but don't crash
            logger.exception(f"Unexpected error in worker: {e}")
            consecutive_errors += 1
        
        # Normal sleep
        try:
            await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            break
```

---

## 7. Circuit Breaker Pattern

Für Worker die externe Services aufrufen:

```python
class ExternalServiceWorker:
    def __init__(self, ...):
        self._circuit_open = False
        self._circuit_open_until: datetime | None = None
        self._failure_count = 0
        self.FAILURE_THRESHOLD = 3
        self.CIRCUIT_TIMEOUT_SECONDS = 60
    
    async def _do_work(self) -> None:
        # Check circuit breaker
        if self._circuit_open:
            if datetime.now(timezone.utc) < self._circuit_open_until:
                logger.debug("Circuit breaker open - skipping")
                return
            # Try to close circuit
            self._circuit_open = False
            self._failure_count = 0
            logger.info("Circuit breaker closed - resuming")
        
        try:
            await self._call_external_service()
            self._failure_count = 0  # Success resets counter
            
        except ExternalServiceError:
            self._failure_count += 1
            if self._failure_count >= self.FAILURE_THRESHOLD:
                self._circuit_open = True
                self._circuit_open_until = (
                    datetime.now(timezone.utc) 
                    + timedelta(seconds=self.CIRCUIT_TIMEOUT_SECONDS)
                )
                logger.warning(
                    f"Circuit breaker opened - will retry in {self.CIRCUIT_TIMEOUT_SECONDS}s"
                )
```

---

## 8. Worker Status for UI

Alle Worker MÜSSEN `get_status()` implementieren:

```python
def get_status(self) -> dict[str, Any]:
    """Get status for monitoring and UI display.
    
    Returns dict with standardized fields:
    - running: bool - is worker running
    - status: str - 'active', 'idle', 'stopped', 'error'
    - interval_seconds: int - check interval
    - last_run: datetime | None - when last work completed
    - next_run: datetime | None - when next work scheduled
    - statistics: dict - worker-specific stats
    """
    return {
        "name": "My Worker",
        "running": self._running,
        "status": self._get_status_string(),
        "interval_seconds": self.interval,
        "last_run": self._last_run,
        "next_run": self._next_run,
        "statistics": {
            "items_processed": self._items_processed,
            "errors": self._error_count,
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

---

## 9. Worker Manager Pattern

Für Gruppen von zusammengehörigen Workern:

```python
class AutomationWorkerManager:
    """Manager for related workers - start/stop as group."""
    
    def __init__(self, ...):
        self.watchlist_worker = WatchlistWorker(...)
        self.discography_worker = DiscographyWorker(...)
        self.quality_worker = QualityWorker(...)
    
    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
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
        """Stop all managed workers gracefully."""
        await self.watchlist_worker.stop()
        await self.discography_worker.stop()
        await self.quality_worker.stop()
        logger.info("All automation workers stopped")
    
    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all managed workers."""
        return {
            "watchlist": self.watchlist_worker.get_status(),
            "discography": self.discography_worker.get_status(),
            "quality": self.quality_worker.get_status(),
        }
```

---

## 10. Worker Configuration

Worker sollten konfigurierbar sein:

```python
class ConfigurableWorker:
    def __init__(
        self,
        settings: "Settings",
        check_interval_seconds: int = 300,  # Sensible default
        ...
    ) -> None:
        self._settings = settings
        self.interval = check_interval_seconds
    
    async def _do_work(self) -> None:
        # Check if worker is enabled in settings
        async with self._db.session_scope() as session:
            settings_service = AppSettingsService(session)
            
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

---

## 11. Logging Standards for Workers

```python
from soulspot.infrastructure.observability.log_messages import LogMessages

class MyWorker:
    async def start(self) -> None:
        # ... start logic ...
        logger.info(
            LogMessages.worker_started(
                worker="My Worker",
                interval=self.interval,
                config={"threshold": self.threshold}
            )
        )
    
    async def _do_work(self) -> None:
        logger.debug(f"Worker cycle started")
        
        try:
            result = await self._perform_work()
            logger.info(f"Worker processed {result.count} items")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
    
    async def stop(self) -> None:
        # ... stop logic ...
        logger.info("Worker stopped")
```

---

## 12. Checkliste für neue Worker

### Standalone Loop Worker (Periodic Tasks)

- [ ] Erbt von keiner Base-Klasse (Composition over Inheritance)
- [ ] Hat `__init__`, `start()`, `stop()`, `_run_loop()`, `_do_work()`, `get_status()`
- [ ] `start()` und `stop()` sind idempotent
- [ ] `_run_loop()` crasht NIEMALS (alle Exceptions gefangen)
- [ ] Hat initiale Startup-Delay (`await asyncio.sleep(10)`)
- [ ] Session per work cycle (nicht wiederverwendet)
- [ ] Registered in `lifecycle.py` (start + shutdown)
- [ ] Stored on `app.state` für Status-Abfrage
- [ ] Hat Status-Endpoint in `/api/workers` Router
- [ ] Respektiert App Settings für enable/disable
- [ ] Hat Circuit Breaker wenn externe Services aufgerufen werden

### Job-Based Worker (Event-Triggered Tasks)

- [ ] Erbt von keiner Base-Klasse
- [ ] Hat `__init__`, `register()`, `_handle_*()`, `enqueue_*()` (public API)
- [ ] Handler wirft ValueError für bad data (no retry)
- [ ] Handler wirft Exception für transient errors (triggers retry)
- [ ] Session per job execution (via `db.session_scope()`)
- [ ] Registered in `lifecycle.py` via `worker.register()` BEFORE `job_queue.start()`
- [ ] JobQueue stored on `app.state` für Status-Abfrage
- [ ] Uses JobQueue's built-in retry/priority/concurrency

### Wann welches Pattern wählen?

| Situation | Pattern |
|-----------|---------|
| Alle X Minuten prüfen (sync, cleanup) | Standalone Loop |
| User-Aktion verarbeiten (download, scan) | Job-Based |
| Retry/Persistence wichtig | Job-Based |
| Unabhängige Arbeit | Standalone Loop |

---

## 13. Job-Based Worker Pattern (Alternative)

Für Worker die **Jobs aus einer Queue verarbeiten** statt periodisch zu laufen:

```python
class JobBasedWorker:
    """Worker that processes jobs from JobQueue.
    
    This pattern is used when:
    - Work is triggered by external events (user requests, scan completion)
    - Jobs should be persisted and retried on failure
    - Concurrency is managed by the JobQueue, not the worker
    
    Examples: DownloadWorker, MetadataWorker, LibraryScanWorker
    """
    
    def __init__(
        self,
        job_queue: JobQueue,
        other_deps...,
    ) -> None:
        """Initialize with dependencies.
        
        NOTE: No start/stop methods - lifecycle is managed by JobQueue!
        """
        self._job_queue = job_queue
        # Store other dependencies
        # Optionally create use_case instance
    
    def register(self) -> None:
        """Register job handlers with queue.
        
        Call AFTER app is fully initialized!
        This tells JobQueue: "when JobType.X arrives, call my handler"
        """
        self._job_queue.register_handler(
            JobType.MY_JOB_TYPE,
            self._handle_my_job
        )
    
    async def _handle_my_job(self, job: Job) -> dict[str, Any]:
        """Handle a single job.
        
        Called by JobQueue when job is ready to process.
        
        Args:
            job: The job with payload to process
            
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
        
        # Execute work (usually via use case)
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
        Returns job_id for tracking.
        """
        return await self._job_queue.enqueue(
            job_type=JobType.MY_JOB_TYPE,
            payload={"required_param": param},
            max_retries=max_retries,
            priority=priority,
        )
```

### Unterschiede zwischen Patterns

| Aspekt | Standalone Loop Worker | Job-Based Worker |
|--------|------------------------|------------------|
| Lifecycle | Eigene `start()`/`stop()` | Von JobQueue verwaltet |
| Trigger | Periodisch (Intervall) | Event-basiert (Job enqueued) |
| Retry | Manuell implementiert | JobQueue built-in |
| Concurrency | Eigener Task | JobQueue `max_concurrent` |
| Status | `get_status()` auf Worker | `job_queue.get_stats()` |
| Beispiele | CleanupWorker, SpotifySyncWorker | DownloadWorker, MetadataWorker |

### Wann welches Pattern?

**Standalone Loop Worker verwenden wenn:**
- Arbeit periodisch passieren muss (alle X Minuten)
- Keine externe Queue/Persistence nötig
- Worker unabhängig von anderen Components

**Job-Based Worker verwenden wenn:**
- Arbeit durch User-Aktionen getriggert wird
- Jobs retried/tracked werden sollen
- Mehrere Worker-Types dieselbe Queue teilen

### Job-Based Worker Registration in Lifecycle

```python
# lifecycle.py - Job-based worker registration

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

---

## 14. Zusammenfassung

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
│  ❌ NIEMALS      │ Loop crashen lassen (Exceptions fangen!)     │
│  ❌ NIEMALS      │ Sessions über Work Cycles wiederverwenden    │
│  ❌ NIEMALS      │ Externe Services ohne Circuit Breaker        │
│  ✅ IMMER        │ Initial delay (10s) beim Start               │
│  ✅ IMMER        │ Token vor Work prüfen (wenn OAuth nötig)     │
│  ✅ IMMER        │ Settings respektieren (enabled/interval)     │
└─────────────────────────────────────────────────────────────────┘
```
