# 🔒 Database Lock Optimization Plan

## Vollständiger Plan zur Eliminierung von "database is locked" Fehlern

**Ziel:** SQLite-Lock-Probleme dauerhaft lösen durch systematische Optimierungen auf allen Ebenen.

---

## 📊 Problemanalyse

### Aktueller Stand

**Was bereits implementiert ist (✅):**
1. WAL-Modus aktiv (`PRAGMA journal_mode=WAL`)
2. Foreign Keys aktiviert (`PRAGMA foreign_keys=ON`)
3. Busy Timeout auf 60s (`PRAGMA busy_timeout=60000`)
4. Connection timeout auf 60s (`timeout: 60`)
5. Job Queue Worker auf 1 reduziert für SQLite
6. `check_same_thread=False` für async-Kompatibilität

**Was noch fehlt (❌):**
1. Keine Retry-Logik für OperationalError auf Application Layer
2. Keine Connection-Pool-Limits für SQLite (obwohl SQLite keinen echten Pool braucht)
3. Keine Transaktions-Timeouts
4. Keine Metriken/Logging für Lock-Ereignisse
5. Keine Priorisierung von kurzen vs. langen Transaktionen
6. Workers haben unterschiedliche Session-Patterns (manche teilen Session, manche nicht)

### Root Causes der Locks

| Problem | Beschreibung | Impact |
|---------|-------------|--------|
| **Lange Transaktionen** | Library Scan kann Minuten dauern | Blockiert alle anderen Writes |
| **Concurrent Workers** | 8+ Workers schreiben gleichzeitig | Lock-Contention |
| **Shared Sessions** | worker_session wird für mehrere Worker geteilt | Serialisiert unnötig |
| **Fehlende Retries** | Kein Retry bei temporärem Lock | Sofortiger Fehler |
| **Bulk Operations** | Große INSERT/UPDATE ohne Batching | Hält Lock lange |

---

## 🎯 Optimierungsplan (5 Phasen)

### Phase 1: Immediate Fixes (Priority: CRITICAL)
**Zeitrahmen: 1-2 Stunden**

#### 1.1 Retry-Decorator für DB-Operations

```python
# src/soulspot/infrastructure/persistence/retry.py

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_db_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying database operations on lock errors.
    
    Hey future me - this is THE FIX for "database is locked" errors!
    
    SQLite locks are TEMPORARY - waiting and retrying almost always works.
    This decorator adds exponential backoff retry logic to any async function.
    
    Usage:
        @with_db_retry(max_attempts=3)
        async def my_db_operation(session):
            ...
    
    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 5.0)
        backoff_factor: Multiply delay by this factor each retry (default: 2.0)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            delay = initial_delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    error_msg = str(e).lower()
                    
                    # Only retry on lock-related errors
                    if "database is locked" not in error_msg and "locked" not in error_msg:
                        raise
                    
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "Database locked (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1,
                            max_attempts,
                            delay,
                            func.__name__,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            "Database locked after %d attempts, giving up: %s",
                            max_attempts,
                            func.__name__,
                        )
            
            raise last_exception  # type: ignore[misc]
        
        return wrapper  # type: ignore[return-value]
    
    return decorator
```

#### 1.2 Anwenden auf kritische Repositories

```python
# In repositories.py - Beispiel für TrackRepository

from soulspot.infrastructure.persistence.retry import with_db_retry

class TrackRepository:
    
    @with_db_retry(max_attempts=3)
    async def add(self, track: Track) -> Track:
        """Add track with retry on lock."""
        # ... existing implementation
    
    @with_db_retry(max_attempts=3)
    async def update(self, track: Track) -> Track:
        """Update track with retry on lock."""
        # ... existing implementation
```

---

### Phase 2: Session Management Optimization
**Zeitrahmen: 2-3 Stunden**

#### 2.1 Short-Lived Sessions für alle Workers

**Problem:** `worker_session` in lifecycle.py wird für mehrere Worker geteilt.

**Lösung:** Jeder Worker bekommt `session_factory`, nicht eine geteilte Session.

```python
# VORHER (lifecycle.py):
async with db.session_scope() as worker_session:
    track_repository = TrackRepository(worker_session)
    # ... alle Worker teilen worker_session

# NACHHER:
# Übergebe session_factory an Worker, jeder erstellt eigene kurzlebige Sessions
download_worker = DownloadWorker(
    job_queue=job_queue,
    slskd_client=slskd_client,
    session_factory=db.get_session_factory(),  # NEW!
)
```

#### 2.2 Worker-Session-Pattern

```python
# src/soulspot/application/workers/base_worker.py

class BaseWorker:
    """Base class for workers with proper session management.
    
    Hey future me - JEDER Worker sollte von dieser Klasse erben!
    
    Pattern:
    - Worker bekommt session_factory (nicht Session!)
    - Jede Operation bekommt eigene kurzlebige Session
    - Sessions werden SOFORT nach Operation geschlossen
    - Keine langen offenen Transaktionen
    """
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
    
    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a short-lived session for a single operation.
        
        Usage:
            async with self._get_session() as session:
                repo = TrackRepository(session)
                await repo.add(track)
                # Session auto-commits on exit, auto-rollbacks on exception
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
```

---

### Phase 3: Transaction Batching & Chunking
**Zeitrahmen: 3-4 Stunden**

#### 3.1 Batch-Processor für Bulk Operations

```python
# src/soulspot/infrastructure/persistence/batch_utils.py

from typing import TypeVar, Sequence, Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def batch_insert(
    session: AsyncSession,
    items: Sequence[T],
    batch_size: int = 100,
    commit_after_each: bool = True,
) -> int:
    """Insert items in batches to minimize lock time.
    
    Hey future me - USE THIS for any operation with >50 items!
    
    SQLite locks on EVERY write. By batching and committing frequently,
    we release the lock between batches, allowing other operations to proceed.
    
    Args:
        session: Database session
        items: Items to insert
        batch_size: Items per batch (default: 100)
        commit_after_each: Commit after each batch (default: True)
    
    Returns:
        Number of items inserted
    """
    total_inserted = 0
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        session.add_all(batch)
        
        if commit_after_each:
            await session.commit()
        
        total_inserted += len(batch)
        
        # Brief pause between batches to allow other operations
        if i + batch_size < len(items):
            await asyncio.sleep(0.01)  # 10ms breather
    
    if not commit_after_each:
        await session.commit()
    
    return total_inserted


async def batch_update(
    session: AsyncSession,
    update_func: Callable[[AsyncSession, Sequence[T]], Any],
    items: Sequence[T],
    batch_size: int = 50,
) -> int:
    """Update items in batches.
    
    Usage:
        async def update_tracks(session, tracks):
            for track in tracks:
                track.status = "processed"
        
        await batch_update(session, update_tracks, tracks, batch_size=50)
    """
    total_updated = 0
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        await update_func(session, batch)
        await session.commit()
        total_updated += len(batch)
        await asyncio.sleep(0.01)
    
    return total_updated
```

#### 3.2 Library Scanner Optimization

```python
# In LibraryScannerService - Commit nach jedem Track/Album statt am Ende

async def _scan_directory(self, path: Path) -> ScanResult:
    """Scan with incremental commits to reduce lock time."""
    
    for file in files:
        track = await self._process_file(file)
        
        if track:
            await self._track_repo.add(track)
            # WICHTIG: Commit nach jedem Track!
            await self._session.commit()
            
            # Brief pause for other operations
            if processed_count % 10 == 0:
                await asyncio.sleep(0.01)
```

---

### Phase 4: Connection Pool & PRAGMA Optimization
**Zeitrahmen: 1-2 Stunden**

#### 4.1 Optimierte Database-Konfiguration

```python
# src/soulspot/infrastructure/persistence/database.py - Updates

def __init__(self, settings: Settings) -> None:
    """Initialize database with optimized SQLite settings."""
    
    if "sqlite" in settings.database.url:
        engine_kwargs.update({
            "connect_args": {
                "check_same_thread": False,
                "timeout": 60,
                # NEU: Isolation level für bessere Concurrency
                "isolation_level": None,  # Autocommit-Modus
            },
            # NEU: Pool-Limits für SQLite
            "poolclass": StaticPool,  # Single connection für SQLite
            # ODER: NullPool für keine Pooling (jede Operation eigene Connection)
        })
```

#### 4.2 Erweiterte SQLite PRAGMAs

```python
def _enable_sqlite_optimizations(self) -> None:
    """Enable all SQLite optimizations for better concurrency."""
    
    @event.listens_for(self._engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
        cursor = dbapi_conn.cursor()
        
        # Bestehende PRAGMAs
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        
        # NEUE Optimierungen:
        
        # 1. Synchronous: NORMAL ist sicher genug, schneller als FULL
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # 2. Cache size: Mehr Cache = weniger Disk I/O = schnellere Ops
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        
        # 3. Temp store: RAM ist schneller als Disk
        cursor.execute("PRAGMA temp_store=MEMORY")
        
        # 4. Memory-mapped I/O: Schnellere Reads
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        # 5. Page size: Größere Pages = weniger I/O (nur bei neuer DB!)
        # cursor.execute("PRAGMA page_size=4096")  # Nur bei leerer DB!
        
        cursor.close()
        logger.debug("Applied SQLite optimizations: WAL, cache, mmap, synchronous")
```

---

### Phase 5: Monitoring & Alerting
**Zeitrahmen: 1-2 Stunden**

#### 5.1 Lock-Metriken-Collector

```python
# src/soulspot/infrastructure/observability/db_metrics.py

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass
class DatabaseLockMetrics:
    """Track database lock events for monitoring.
    
    Hey future me - use this to DETECT problems before users complain!
    
    Expose via /api/health/db-metrics for Grafana/Prometheus.
    """
    
    lock_attempts: int = 0
    lock_successes: int = 0
    lock_failures: int = 0
    lock_retries: int = 0
    total_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0
    last_lock_event: datetime | None = None
    
    _instance: ClassVar["DatabaseLockMetrics | None"] = None
    
    @classmethod
    def get_instance(cls) -> "DatabaseLockMetrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def record_lock_attempt(self) -> None:
        self.lock_attempts += 1
    
    def record_lock_success(self, wait_time_ms: float = 0.0) -> None:
        self.lock_successes += 1
        self.total_wait_time_ms += wait_time_ms
        if wait_time_ms > self.max_wait_time_ms:
            self.max_wait_time_ms = wait_time_ms
        self.last_lock_event = datetime.now(UTC)
    
    def record_lock_failure(self) -> None:
        self.lock_failures += 1
        self.last_lock_event = datetime.now(UTC)
        logger.warning("Database lock failure recorded (total: %d)", self.lock_failures)
    
    def record_retry(self) -> None:
        self.lock_retries += 1
    
    def get_stats(self) -> dict:
        return {
            "lock_attempts": self.lock_attempts,
            "lock_successes": self.lock_successes,
            "lock_failures": self.lock_failures,
            "lock_retries": self.lock_retries,
            "total_wait_time_ms": self.total_wait_time_ms,
            "max_wait_time_ms": self.max_wait_time_ms,
            "avg_wait_time_ms": (
                self.total_wait_time_ms / self.lock_successes
                if self.lock_successes > 0 else 0
            ),
            "failure_rate": (
                self.lock_failures / self.lock_attempts
                if self.lock_attempts > 0 else 0
            ),
            "last_event": self.last_lock_event.isoformat() if self.last_lock_event else None,
        }
    
    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self.lock_attempts = 0
        self.lock_successes = 0
        self.lock_failures = 0
        self.lock_retries = 0
        self.total_wait_time_ms = 0.0
        self.max_wait_time_ms = 0.0
        self.last_lock_event = None
```

#### 5.2 Health-Endpoint für DB-Status

```python
# In api/routers/health.py

@router.get("/db-metrics")
async def get_db_metrics() -> dict:
    """Get database lock metrics for monitoring."""
    from soulspot.infrastructure.observability.db_metrics import DatabaseLockMetrics
    
    metrics = DatabaseLockMetrics.get_instance()
    return metrics.get_stats()
```

---

## 📋 Implementierungs-Checkliste

### Phase 1: Immediate Fixes ⏰ 1-2h
- [ ] `retry.py` erstellen mit `@with_db_retry` Decorator
- [ ] Decorator auf kritische Repository-Methoden anwenden:
  - [ ] `TrackRepository.add()`, `.update()`
  - [ ] `AlbumRepository.add()`, `.update()`
  - [ ] `ArtistRepository.add()`, `.update()`
  - [ ] `DownloadRepository.add()`, `.update_status()`
- [x] Logging für Lock-Events hinzufügen (via `DatabaseLockMetrics`)

### Phase 2: Session Management ⏰ 2-3h (ERLEDIGT ✅)
- [ ] `BaseWorker` Klasse mit `session_factory` Pattern erstellen (optional)
- [x] Workers refactoren:
  - [x] `DownloadWorker` - REFACTORED! Nutzt jetzt session_factory, erstellt Session pro Job
  - [x] `LibraryScanWorker` - bereits OK (nutzt db.session_scope_with_retry)
  - [x] `LibraryDiscoveryWorker` - bereits OK (nutzt db.session_scope_with_retry)
  - [x] `QueueDispatcherWorker` - bereits OK (nutzt session_factory)
  - [x] `DownloadStatusSyncWorker` - bereits OK (nutzt session_factory)
  - [x] `RetrySchedulerWorker` - bereits OK (nutzt session_factory)
  - [x] `AutomationWorkerManager` - bereits OK (nutzt session_factory)
- [x] `lifecycle.py` anpassen - DownloadWorker nutzt jetzt session_factory
- [ ] `AutoImportService` - auf session_factory umstellen (niedrige Priorität, macht meist Reads)
- [ ] `CleanupWorker` - macht nur Settings-Reads, weniger kritisch

### Phase 3: Transaction Batching ⏰ 3-4h (TEILWEISE ERLEDIGT ✅)
- [x] `batch_utils.py` mit `batch_insert()` / `batch_update()` erstellt
- [x] `LibraryScannerService` optimiert:
  - [x] BATCH_SIZE von 250 auf 10 reduziert
  - [x] Commit nach jedem Album (natürliche Transaktionsgrenze)
  - [x] `_cleanup_missing_files()` mit Commits nach jedem Batch
- [x] `LibraryDiscoveryWorker` - nutzt session_scope_with_retry

### Phase 4: Connection & PRAGMA Optimization ⏰ 1-2h (ERLEDIGT ✅)
- [x] `_enable_sqlite_optimizations()` mit erweiterten PRAGMAs:
  - [x] `synchronous=NORMAL` (statt FULL)
  - [x] `cache_size=-64000` (64MB cache)
  - [x] `temp_store=MEMORY`
  - [x] `mmap_size=268435456` (256MB memory-mapped I/O)
- [x] `NullPool` für SQLite implementiert:
  - Jede Session bekommt eigene Verbindung (keine Connection-Sharing)
  - Verbindung wird sofort nach Gebrauch geschlossen
  - Eliminiert Lock-Konflikte durch Connection-Reuse
- [ ] Benchmark vorher/nachher (manueller Test empfohlen)

### Phase 5: Monitoring ⏰ 1-2h (ERLEDIGT ✅)
- [x] `DatabaseLockMetrics` Klasse erstellt (`retry.py`)
- [x] In Retry-Decorator integriert (`@with_db_retry`)
- [x] Health-Endpoint `/api/health/db-metrics` hinzugefügt
- [ ] Dashboard/Alerts konfigurieren (optional)

---

## 🧪 Test-Strategie

### Manuelle Tests (Live in Docker)

```bash
# 1. Library Scan während UI-Nutzung
# Terminal 1: Starte Library Scan
curl -X POST http://localhost:8000/api/library/scan

# Terminal 2: Lade gleichzeitig Artists
curl http://localhost:8000/api/library/artists?page=1&size=50

# Erwartung: Keine "database is locked" Fehler

# 2. Concurrent Downloads
# Queue 10 Downloads gleichzeitig und prüfe Logs

# 3. Discovery Worker während UI-Browsing
# Trigger Discovery manuell und browse gleichzeitig
```

### Metriken-Validation

```bash
# Nach Optimierung prüfen:
curl http://localhost:8000/api/health/db-metrics

# Erwartete Verbesserung:
# - failure_rate: < 0.01 (weniger als 1%)
# - avg_wait_time_ms: < 100ms
# - max_wait_time_ms: < 5000ms
```

---

## 🚨 Fallback: PostgreSQL Migration

Falls SQLite-Optimierungen nicht ausreichen:

### Wann migrieren?
- Lock-Fehler bleiben bei > 5% aller Writes
- Mehr als 10 gleichzeitige aktive User
- Datenbank > 500MB
- Geografisch verteilte Nutzung

### Migrations-Schritte
1. PostgreSQL Container hinzufügen (`docker-compose.yml`)
2. `DATABASE_URL` auf PostgreSQL ändern
3. Alembic-Migrations auf PostgreSQL testen
4. Daten-Migration mit `pgloader` oder Custom-Script
5. Pool-Settings aktivieren (pool_size=10, max_overflow=20)

---

## 📊 Erwartete Ergebnisse

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Lock-Fehler | ~5-10% | < 1% |
| Avg Wait Time | ~200ms | < 50ms |
| Max Wait Time | ~60s | < 5s |
| Retry-Rate | 0% (keine Retries) | ~2% (mit Recovery) |
| Library Scan Blocking | Komplett | Minimal |

---

## ✅ Implementierungs-Zusammenfassung (Dez 2025)

### Phase 1: Retry Logic & SQLite PRAGMAs ✅
**Dateien:**
- `src/soulspot/infrastructure/persistence/retry.py` (NEU)
- `src/soulspot/infrastructure/persistence/database.py` (GEÄNDERT)
- `src/soulspot/api/health_checks.py` (GEÄNDERT)

**Änderungen:**
- `@with_db_retry` Decorator für automatische Retries bei "database is locked"
- `DatabaseLockMetrics` Singleton für Monitoring
- `session_scope_with_retry()` Context Manager
- Erweiterte SQLite PRAGMAs (cache, mmap, synchronous)
- `/health/db-metrics` Endpoint

### Phase 2: Session Management ✅
**Dateien:**
- `src/soulspot/application/workers/download_worker.py` (REFACTORED)
- `src/soulspot/infrastructure/lifecycle.py` (GEÄNDERT)

**Änderungen:**
- `DownloadWorker` nutzt jetzt `session_factory` statt shared repositories
- Jeder Download-Job bekommt eigene kurzlebige Session
- Eliminiert Lock-Konflikte zwischen concurrent Jobs

### Phase 3: Transaction Batching ✅
**Dateien:**
- `src/soulspot/infrastructure/persistence/batch_utils.py` (NEU)
- `src/soulspot/application/services/library_scanner_service.py` (GEÄNDERT)

**Änderungen:**
- `batch_insert()`, `batch_update()`, `IncrementalCommitter` Utilities
- LibraryScannerService: BATCH_SIZE 250→10, Commit nach jedem Album
- Cleanup: Commits nach jedem Batch statt am Ende

### Phase 4: Connection Pool ✅
**Dateien:**
- `src/soulspot/infrastructure/persistence/database.py` (GEÄNDERT)

**Änderungen:**
- `NullPool` für SQLite (keine Connection-Sharing)
- Jede Session bekommt eigene frische Verbindung
- Verbindung wird sofort nach Gebrauch geschlossen

### Phase 5: Monitoring ✅
**Dateien:**
- `src/soulspot/infrastructure/persistence/retry.py`
- `src/soulspot/api/health_checks.py`

**Änderungen:**
- Lock-Metriken werden automatisch gesammelt
- `/health/db-metrics` zeigt failure_rate, retry_rate, avg_wait_time

---

## 🔗 Verwandte Dokumente

- `docs/development/SQLITE_BEST_PRACTICES.md` - Bestehende SQLite-Doku
- `docs/development/sqlite-operations.md` - Operations Guide
- `docs/guides/user/troubleshooting-guide.md` - User-Facing Troubleshooting
- `src/soulspot/infrastructure/persistence/database.py` - Current Implementation

---

**Erstellt:** 2025-12-25  
**Status:** Plan - Bereit zur Implementierung  
**Priorität:** HIGH - Beeinträchtigt User Experience
