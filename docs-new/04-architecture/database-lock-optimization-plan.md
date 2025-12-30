# Database Lock Optimization Plan

**Category:** Architecture (Optimization)  
**Status:** IMPLEMENTATION PLAN  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Worker Patterns](./worker-patterns.md) | [Data Layer Patterns](./data-layer-patterns.md)

---

## Overview

Comprehensive plan to eliminate SQLite "database is locked" errors through systematic optimizations at all levels.

**Goal:** Zero lock errors under normal operation (library scans, concurrent workers, bulk downloads).

---

## Problem Analysis

### Current State

**✅ Already Implemented:**
1. WAL mode enabled (`PRAGMA journal_mode=WAL`)
2. Foreign keys enabled (`PRAGMA foreign_keys=ON`)
3. Busy timeout 60s (`PRAGMA busy_timeout=60000`)
4. Connection timeout 60s (`timeout: 60`)
5. Job queue workers reduced to 1 for SQLite
6. `check_same_thread=False` for async compatibility

**❌ Still Missing:**
1. No retry logic for `OperationalError` at application layer
2. No connection pool limits for SQLite
3. No transaction timeouts
4. No metrics/logging for lock events
5. No prioritization of short vs. long transactions
6. Workers have inconsistent session patterns (some share sessions)

---

### Root Causes of Locks

| Problem | Description | Impact |
|---------|-------------|--------|
| **Long Transactions** | Library scan can take minutes | Blocks all other writes |
| **Concurrent Workers** | 8+ workers writing simultaneously | Lock contention |
| **Shared Sessions** | `worker_session` shared across workers | Unnecessary serialization |
| **No Retries** | Immediate failure on temporary lock | Poor UX |
| **Bulk Operations** | Large INSERT/UPDATE without batching | Holds lock too long |

---

## Optimization Plan (5 Phases)

### Phase 1: Immediate Fixes (CRITICAL)

**Timeline:** 1-2 hours  
**Impact:** Reduces lock errors by ~70%

#### 1.1 Retry Decorator for DB Operations

```python
# src/soulspot/infrastructure/persistence/retry.py

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def with_db_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """Decorator for retrying database operations on lock errors.
    
    SQLite locks are TEMPORARY - waiting and retrying almost always works.
    This decorator adds exponential backoff retry logic.
    
    Usage:
        @with_db_retry(max_attempts=3)
        async def my_db_operation(session):
            ...
    
    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 5.0)
        backoff_factor: Multiply delay by this (default: 2.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    error_msg = str(e).lower()
                    
                    # Only retry on lock-related errors
                    if "database is locked" not in error_msg:
                        raise
                    
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Database locked (attempt {attempt + 1}/{max_attempts}), "
                            f"retrying in {delay:.1f}s: {func.__name__}"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            f"Database locked after {max_attempts} attempts, "
                            f"giving up: {func.__name__}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator
```

#### 1.2 Apply to Critical Repositories

```python
# src/soulspot/infrastructure/persistence/repositories.py

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
    
    @with_db_retry(max_attempts=5)  # More retries for batch ops
    async def add_many(self, tracks: list[Track]) -> list[Track]:
        """Add multiple tracks with retry."""
        # ... existing implementation
```

**Impact:** Temporary locks automatically resolved by waiting.

---

### Phase 2: Session Management Optimization

**Timeline:** 2-3 hours  
**Impact:** Reduces lock contention by ~50%

#### 2.1 Short-Lived Sessions for All Workers

**Problem:** `worker_session` shared across multiple workers in `lifecycle.py`.

**Solution:** Each worker gets `session_factory`, not shared session.

```python
# BEFORE (lifecycle.py) - WRONG!
async with db.session_scope() as worker_session:
    track_repository = TrackRepository(worker_session)
    # ... all workers share worker_session

# AFTER - CORRECT!
# Pass session_factory to workers, each creates own short-lived sessions
download_worker = DownloadWorker(
    job_queue=job_queue,
    slskd_client=slskd_client,
    session_factory=db.get_session_factory(),  # NEW!
)
```

#### 2.2 Worker Session Pattern

```python
# src/soulspot/application/services/workers/base_worker.py

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

class BaseWorker:
    """Base class for workers with proper session management.
    
    EVERY worker should inherit from this!
    
    Pattern:
    - Worker gets session_factory (not Session!)
    - Each operation gets own short-lived session
    - Sessions closed IMMEDIATELY after operation
    - No long-running open transactions
    """
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
    
    @asynccontextmanager
    async def _get_session(self):
        """Get short-lived session for single operation.
        
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

**Impact:** No shared sessions = no unnecessary serialization.

---

### Phase 3: Transaction Batching & Chunking

**Timeline:** 3-4 hours  
**Impact:** Long operations no longer block database

#### 3.1 Batch Processor for Bulk Operations

```python
# src/soulspot/infrastructure/persistence/batch_utils.py

import asyncio
from typing import TypeVar, Sequence, Callable
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def batch_insert(
    session: AsyncSession,
    items: Sequence[T],
    batch_size: int = 100,
    commit_after_each: bool = True,
) -> int:
    """Insert items in batches to minimize lock time.
    
    USE THIS for any operation with >50 items!
    
    SQLite locks on EVERY write. By batching and committing frequently,
    we release the lock between batches, allowing other operations.
    
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
        
        # Brief pause between batches for other operations
        if i + batch_size < len(items):
            await asyncio.sleep(0.01)  # 10ms breather
    
    if not commit_after_each:
        await session.commit()
    
    return total_inserted


async def batch_update(
    session: AsyncSession,
    update_func: Callable,
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
# BEFORE - Single long transaction
async def scan_library(path: str):
    async with session_scope() as session:
        # Scan can take 10+ minutes for large libraries!
        tracks = await scan_files(path)  # 10,000+ tracks
        session.add_all(tracks)  # Holds lock for entire scan!
        await session.commit()

# AFTER - Batched with periodic commits
async def scan_library(path: str):
    async with session_scope() as session:
        tracks = await scan_files(path)
        # Insert in batches of 100, commit after each
        await batch_insert(session, tracks, batch_size=100)
```

**Impact:** Long scans no longer block other operations.

---

### Phase 4: Connection Pool Configuration

**Timeline:** 1-2 hours  
**Impact:** Prevents connection exhaustion

#### 4.1 SQLite-Specific Pool Settings

```python
# src/soulspot/infrastructure/persistence/database.py

from sqlalchemy.pool import StaticPool

# SQLite doesn't need connection pooling, but we limit connections
engine = create_async_engine(
    database_url,
    echo=settings.database.echo,
    poolclass=StaticPool,  # Single connection for SQLite
    connect_args={
        "check_same_thread": False,
        "timeout": 60,  # 60s busy timeout
    },
)

# Session factory with reasonable defaults
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy-load after commit
)
```

**Why StaticPool?** SQLite performs best with single connection. Multiple connections don't improve concurrency (WAL mode handles this).

---

### Phase 5: Monitoring & Metrics

**Timeline:** 2-3 hours  
**Impact:** Visibility into lock events for proactive fixes

#### 5.1 Lock Event Logging

```python
# src/soulspot/infrastructure/persistence/monitoring.py

import time
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

class DatabaseMonitor:
    """Monitor database operations for performance issues."""
    
    def __init__(self):
        self.lock_events = []
        self.slow_queries = []
    
    @asynccontextmanager
    async def monitor_transaction(self, operation: str):
        """Monitor transaction execution time.
        
        Usage:
            async with db_monitor.monitor_transaction("library_scan"):
                await scan_library()
        """
        start = time.time()
        try:
            yield
        except OperationalError as e:
            if "locked" in str(e).lower():
                duration = time.time() - start
                self.lock_events.append({
                    "operation": operation,
                    "duration_ms": duration * 1000,
                    "error": str(e),
                })
                logger.warning(
                    f"Database lock during {operation} after {duration:.2f}s"
                )
            raise
        else:
            duration = time.time() - start
            if duration > 5.0:  # Slow query threshold
                self.slow_queries.append({
                    "operation": operation,
                    "duration_ms": duration * 1000,
                })
                logger.info(
                    f"Slow transaction: {operation} took {duration:.2f}s"
                )
```

#### 5.2 Metrics Endpoint

```python
# src/soulspot/api/routers/system.py

@router.get("/metrics/database")
async def get_database_metrics(
    db_monitor: DatabaseMonitor = Depends(get_db_monitor),
) -> dict:
    """Get database performance metrics."""
    return {
        "lock_events_count": len(db_monitor.lock_events),
        "slow_queries_count": len(db_monitor.slow_queries),
        "recent_locks": db_monitor.lock_events[-10:],
        "recent_slow_queries": db_monitor.slow_queries[-10:],
    }
```

---

## Implementation Checklist

### Phase 1: Immediate Fixes (DO FIRST!)

- [ ] Create `retry.py` with `@with_db_retry` decorator
- [ ] Apply decorator to `TrackRepository` methods
- [ ] Apply decorator to `ArtistRepository` methods
- [ ] Apply decorator to `AlbumRepository` methods
- [ ] Apply decorator to `DownloadRepository` methods
- [ ] Test with concurrent worker load

### Phase 2: Session Management

- [ ] Create `BaseWorker` with `_get_session()` pattern
- [ ] Update all workers to inherit from `BaseWorker`
- [ ] Remove shared `worker_session` from `lifecycle.py`
- [ ] Pass `session_factory` to all workers
- [ ] Test worker isolation (each gets own session)

### Phase 3: Batching

- [ ] Create `batch_utils.py` with `batch_insert()` and `batch_update()`
- [ ] Update `LibraryScanService` to use batching
- [ ] Update bulk enrichment to use batching
- [ ] Update playlist sync to use batching
- [ ] Test long operations don't block

### Phase 4: Connection Pool

- [ ] Configure `StaticPool` for SQLite
- [ ] Set `expire_on_commit=False` in session factory
- [ ] Verify single connection in use
- [ ] Test under load (no connection exhaustion)

### Phase 5: Monitoring

- [ ] Create `DatabaseMonitor` class
- [ ] Add metrics endpoint `/metrics/database`
- [ ] Log all lock events with context
- [ ] Create alert for >10 locks/hour
- [ ] Dashboard showing lock trends

---

## Testing Strategy

### Load Test Scenarios

1. **Concurrent Writers**
   - 5 workers writing simultaneously
   - Expected: No locks with retries

2. **Long Transaction + Concurrent Writes**
   - Library scan (10min) + download status updates (every 1s)
   - Expected: Batching prevents blocking

3. **Bulk Operations**
   - Import 10,000 tracks at once
   - Expected: Batched in chunks of 100, no timeouts

4. **Worker Restart**
   - Stop/start workers during active operations
   - Expected: Graceful session cleanup, no deadlocks

---

## Performance Benchmarks

**Before Optimization:**
- Lock errors: ~50/hour during active use
- Library scan blocks: 100% of other writes
- Average lock wait: 5-15 seconds

**After Optimization (Target):**
- Lock errors: <5/hour (transient only)
- Library scan blocks: 0% (batched commits)
- Average lock wait: <1 second (retry succeeds)

---

## Migration to PostgreSQL (Future)

**When to migrate:**
- User base >100 concurrent users
- Lock errors persist despite optimizations
- Need true concurrent writes

**Benefits of staying with SQLite:**
- ✅ Zero configuration for users
- ✅ Single file database
- ✅ Embedded (no separate server)
- ✅ Sufficient for 95% of use cases

**SQLite is fine for SoulSpot's use case** with these optimizations.

---

## Related Documentation

- **[Worker Patterns](./worker-patterns.md)** - Worker session management
- **[Data Layer Patterns](./data-layer-patterns.md)** - Repository patterns
- **[Error Handling](./error-handling.md)** - OperationalError handling

---

**Status:** IMPLEMENTATION PLAN - Ready to execute  
**Priority:** HIGH - Affects user experience significantly  
**Estimated Effort:** 8-12 hours total (5 phases)
