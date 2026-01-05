# Hybrid Database Strategy

> **Version:** 1.1  
> **Status:** ✅ Implemented  
> **Date:** 2025-01-17 (Updated: 2025-01-17)  
> **Related:** [WRITE_BEHIND_CACHE.md](./WRITE_BEHIND_CACHE.md)

---

## ✅ Implementation Status

| Component | File | Status |
|-----------|------|--------|
| **RetryStrategy** | `src/soulspot/infrastructure/persistence/retry.py` | ✅ Already existed |
| **WriteBufferCache** | `src/soulspot/infrastructure/persistence/write_buffer_cache.py` | ✅ Implemented |
| **LogDatabase** | `src/soulspot/infrastructure/persistence/log_database.py` | ✅ Implemented |
| **BusyTimeout** | `src/soulspot/infrastructure/persistence/database.py` | ✅ Reduced to 500ms |
| **Lifecycle Integration** | `src/soulspot/infrastructure/lifecycle.py` | ✅ Integrated |
| **Debug API** | `src/soulspot/api/routers/debug_db.py` | ✅ Implemented |

### Debug API Endpoints

```bash
# Combined stats from all components
GET /api/debug/db/stats

# WriteBufferCache operations
GET  /api/debug/db/buffer       # Stats and pending writes
POST /api/debug/db/buffer/flush # Force flush

# LogDatabase operations
GET /api/debug/db/logs          # Stats
GET /api/debug/db/logs/recent   # Recent log entries

# RetryStrategy metrics
GET  /api/debug/db/retry        # Lock error stats
POST /api/debug/db/retry/reset  # Reset counters

# SQLite lock info
GET /api/debug/db/locks         # Current lock state
```

---

## Executive Summary

SoulSpot verwendet eine **Hybrid-Strategie** für SQLite-Concurrency, inspiriert von Lidarr und angepasst an unsere Anforderungen:

| Komponente | Strategie | Write-Latenz |
|------------|-----------|--------------|
| **API/User-Actions** | Retry mit Exponential Backoff | ~100-500ms |
| **Worker (Sync/Download)** | Write-Behind Cache + Batch | ~0ms (RAM) |
| **Logging** | Separate DB, async best-effort | ~0ms (Queue) |

---

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────────────┐
│                   SoulSpot Hybrid DB Strategy                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐      ┌─────────────────┐     ┌──────────────┐ │
│  │   API Routes    │      │    Workers      │     │   Logging    │ │
│  │  (User Actions) │      │ (Background)    │     │   System     │ │
│  └────────┬────────┘      └────────┬────────┘     └──────┬───────┘ │
│           │                        │                      │         │
│           ▼                        ▼                      ▼         │
│  ┌─────────────────┐      ┌─────────────────┐     ┌──────────────┐ │
│  │  RetryStrategy  │      │ WriteBufferCache│     │   logs.db    │ │
│  │  (Decorator)    │      │ (RAM → Batch)   │     │  (separate)  │ │
│  │  • 3 Retries    │      │ • 5s Flush      │     │  • Async     │ │
│  │  • Exp Backoff  │      │ • Bulk UPSERT   │     │  • Best-Eff  │ │
│  │  • Jitter       │      │ • Prioritäten   │     │  • Cleanup   │ │
│  └────────┬────────┘      └────────┬────────┘     └──────────────┘ │
│           │                        │                                │
│           └────────────┬───────────┘                                │
│                        ▼                                            │
│               ┌─────────────────┐                                   │
│               │   soulspot.db   │                                   │
│               │   (WAL Mode)    │                                   │
│               │   BusyTimeout:  │                                   │
│               │      500ms      │                                   │
│               └─────────────────┘                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Teil 1: RetryStrategy für API/User-Actions

### Warum Retry statt Buffer für APIs?

User-Aktionen (Add Track, Create Playlist, Change Settings) erwarten **direktes Feedback**. Ein Buffer würde:
- ❌ "Track added" anzeigen, obwohl noch nicht geschrieben
- ❌ Inkonsistente Reads nach Writes
- ❌ Verwirrende UX bei Fehlern

Mit Retry:
- ✅ User wartet kurz, bekommt echtes Feedback
- ✅ Konsistente Read-after-Write
- ✅ Klare Fehlermeldung wenn DB wirklich blockiert

### Implementation

```python
# src/soulspot/infrastructure/persistence/retry_strategy.py
"""
Retry-Strategie für direkte DB-Writes (API, User-Actions)
Inspiriert von Lidarr's Polly-basiertem Ansatz
"""

from __future__ import annotations

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseBusyError(Exception):
    """SQLite database is busy/locked after max retries."""
    pass


def is_sqlite_busy_error(exc: Exception) -> bool:
    """
    Prüft ob Exception ein SQLite busy/locked Error ist.
    
    Lidarr's Kommentar dazu:
    "busy/locked are benign" - sie passieren, sind aber handlebar.
    """
    if isinstance(exc, OperationalError):
        error_msg = str(exc).lower()
        return any(keyword in error_msg for keyword in [
            "database is locked",
            "database is busy", 
            "sqlite3.operationalerror",
            "locked",
            "busy"
        ])
    return False


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.1,  # 100ms wie Lidarr
    max_delay: float = 2.0,
    jitter: bool = True,
) -> Callable:
    """
    Decorator für DB-Operationen mit Exponential Backoff.
    
    Inspiriert von Lidarr's Polly-basiertem RetryStrategy:
    - ShouldHandle: SQLiteErrorCode.Busy
    - Delay: 100ms base
    - MaxRetryAttempts: 3
    - BackoffType: Exponential
    - UseJitter: True
    
    Example:
        @with_retry(max_attempts=3)
        async def add_track(self, track: Track) -> Track:
            async with self._session() as session:
                session.add(TrackModel.from_entity(track))
                await session.commit()
                return track
    
    Args:
        max_attempts: Maximale Anzahl Versuche (default: 3)
        base_delay: Basis-Wartezeit in Sekunden (default: 0.1)
        max_delay: Maximale Wartezeit in Sekunden (default: 2.0)
        jitter: Zufällige Variation hinzufügen (default: True)
    
    Returns:
        Decorated async function mit Retry-Logik
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if not is_sqlite_busy_error(exc):
                        raise  # Nicht-Busy Fehler sofort weitergeben
                    
                    last_exception = exc
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Database busy after {max_attempts} attempts: "
                            f"{func.__name__}"
                        )
                        raise DatabaseBusyError(
                            f"Database busy after {max_attempts} retries"
                        ) from exc
                    
                    # Exponential Backoff: 100ms → 200ms → 400ms
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    
                    # Jitter: 50-150% der berechneten Wartezeit
                    # Verhindert "Thundering Herd" wenn viele gleichzeitig retrien
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Database busy, retry #{attempt}/{max_attempts} "
                        f"in {delay:.3f}s: {func.__name__}"
                    )
                    await asyncio.sleep(delay)
            
            # Sollte nie erreicht werden
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        
        return wrapper
    return decorator


# Alternative: Context Manager für komplexere Transaktionen
class RetryContext:
    """
    Context Manager für Retry-Logik bei komplexen DB-Transaktionen.
    
    Für Fälle wo der Decorator nicht passt (z.B. mehrere Operationen
    in einer Transaktion).
    
    Example:
        async with RetryContext(max_attempts=3) as ctx:
            async with session.begin():
                await session.execute(stmt1)
                await session.execute(stmt2)
                # Bei Busy-Error: Session wird gerollt back, 
                # Loop startet neu
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt = 0
    
    async def __aenter__(self) -> "RetryContext":
        self.attempt += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            return False  # Keine Exception, alles gut
        
        if not is_sqlite_busy_error(exc_val):
            return False  # Nicht-Busy Fehler nicht abfangen
        
        if self.attempt >= self.max_attempts:
            logger.error(f"Database busy after {self.max_attempts} attempts")
            return False  # Max Retries erreicht, Exception weitergeben
        
        # Berechne Wartezeit
        delay = min(
            self.base_delay * (2 ** self.attempt), 
            self.max_delay
        )
        delay *= (0.5 + random.random())  # Jitter
        
        logger.warning(
            f"Database busy, retry #{self.attempt}/{self.max_attempts} "
            f"in {delay:.3f}s"
        )
        await asyncio.sleep(delay)
        
        return True  # Exception unterdrücken für Retry
```

### Verwendung in Repositories

```python
# src/soulspot/infrastructure/persistence/repositories.py

from soulspot.infrastructure.persistence.retry_strategy import with_retry


class TrackRepository:
    """Repository für Tracks mit Retry-Strategie."""
    
    @with_retry(max_attempts=3)
    async def add(self, track: Track) -> Track:
        """
        Fügt Track zur DB hinzu.
        
        Bei SQLite busy: Automatisch bis zu 3 Retries mit Backoff.
        """
        async with self._session_scope() as session:
            model = TrackModel.from_entity(track)
            session.add(model)
            await session.flush()
            track.id = model.id
            return track
    
    @with_retry(max_attempts=3)
    async def update(self, track: Track) -> Track:
        """Update Track mit Retry."""
        async with self._session_scope() as session:
            stmt = (
                update(TrackModel)
                .where(TrackModel.id == track.id)
                .values(**track.to_dict())
            )
            await session.execute(stmt)
            return track
    
    # Read-Operationen brauchen KEIN Retry
    # (SQLite WAL erlaubt concurrent reads)
    async def get_by_id(self, track_id: int) -> Track | None:
        async with self._session_scope() as session:
            result = await session.get(TrackModel, track_id)
            return result.to_entity() if result else None
```

---

## Teil 2: WriteBufferCache für Worker

### Warum Buffer für Worker?

Worker (SpotifySync, Download, LibraryScan) machen **viele schnelle Writes**:
- SpotifySync: 500+ Tracks in 30 Sekunden
- Download: Status-Updates alle 100ms
- LibraryScan: 10.000+ Files

Mit einzelnen Writes:
- ❌ 500 separate Transaktionen → UI blockiert
- ❌ Jeder Write wartet auf Lock
- ❌ Langsam (SQLite ~1ms pro Write)

Mit Buffer + Batch:
- ✅ RAM-Latenz (~0ms) für Worker
- ✅ 1 Transaktion alle 5 Sekunden
- ✅ Bulk UPSERT (100 Rows = ~5ms)

### Implementation

```python
# src/soulspot/infrastructure/persistence/write_buffer_cache.py
"""
Write-Behind Cache für Worker mit hoher Write-Frequenz.

Vollständige Dokumentation: docs/architecture/WRITE_BEHIND_CACHE.md
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WriteOperation(Enum):
    """Art der gepufferten Schreiboperation."""
    UPSERT = auto()  # INSERT or UPDATE
    UPDATE = auto()  # Nur UPDATE
    DELETE = auto()  # DELETE


@dataclass
class PendingWrite:
    """Eine gepufferte Schreiboperation."""
    table: str
    operation: WriteOperation
    key_column: str
    key_value: Any
    data: Dict[str, Any]
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class BufferConfig:
    """
    Konfiguration für den Write-Buffer.
    
    Timing:
        flush_interval: Wie oft flushen (default: 5 Sekunden)
        max_buffer_age: Force-Flush wenn Buffer älter (default: 30s)
    
    Size:
        max_pending_writes: Maximale Items im Buffer (default: 1000)
        batch_size: Items pro SQL-Statement (default: 100)
    
    Priorities:
        table_priorities: Niedrigere Zahl = wird zuerst geflusht
    """
    # Timing
    flush_interval: float = 5.0
    max_buffer_age: float = 30.0
    
    # Size Limits  
    max_pending_writes: int = 1000
    batch_size: int = 100
    
    # Table Priorities (kritische zuerst)
    table_priorities: Dict[str, int] = field(default_factory=lambda: {
        "tracks": 1,      # Höchste Priorität (Downloads brauchen diese)
        "downloads": 2,
        "artists": 3,
        "albums": 4,
        "playlists": 5,
    })


class WriteBufferCache:
    """
    Write-Behind Cache für hochfrequente DB-Operationen.
    
    Funktionsweise:
    1. Worker ruft buffer_upsert/update/delete auf
    2. Operation wird im RAM gespeichert (~0ms)
    3. Alle 5 Sekunden: Bulk-Flush zur DB
    4. Bei Shutdown: Force-Flush verbleibender Daten
    
    Thread-Safety:
    - Alle Methoden sind async-safe
    - Lock schützt Buffer-Zugriffe
    
    Fehlerbehandlung:
    - Bei Flush-Fehler: Buffer bleibt erhalten
    - Nächster Flush-Versuch in 5 Sekunden
    - Bei Shutdown: Force-Flush mit Retry
    """
    
    def __init__(
        self,
        session_factory: Any,
        config: BufferConfig | None = None,
    ):
        self._session_factory = session_factory
        self._config = config or BufferConfig()
        
        # Buffer: table -> key_value -> PendingWrite
        self._buffer: Dict[str, Dict[Any, PendingWrite]] = defaultdict(dict)
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False
        
        # Metrics
        self._writes_buffered = 0
        self._writes_flushed = 0
        self._flush_count = 0
        self._flush_errors = 0
    
    # --- Lifecycle ---
    
    async def start(self) -> None:
        """Startet den Background-Flush-Task."""
        if self._running:
            logger.warning("WriteBufferCache already running")
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name="write_buffer_flush"
        )
        logger.info(
            f"WriteBufferCache started "
            f"(flush_interval={self._config.flush_interval}s)"
        )
    
    async def stop(self, flush_remaining: bool = True) -> None:
        """
        Stoppt den Buffer sauber.
        
        Args:
            flush_remaining: Ob verbleibende Writes noch geflusht werden
        """
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        if flush_remaining:
            await self._flush_all()
        
        logger.info(
            f"WriteBufferCache stopped. "
            f"Buffered: {self._writes_buffered}, "
            f"Flushed: {self._writes_flushed}, "
            f"Errors: {self._flush_errors}"
        )
    
    # --- Public Write Methods ---
    
    async def buffer_upsert(
        self,
        table: str,
        key_column: str,
        key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """
        Buffer einen UPSERT (INSERT ON CONFLICT UPDATE).
        
        Wenn bereits ein Eintrag mit gleichem Key im Buffer ist,
        wird er überschrieben (neuere Daten gewinnen).
        
        Args:
            table: Tabellenname
            key_column: Primary Key Column (z.B. "id" oder "spotify_uri")
            key_value: Wert des Keys
            data: Alle Spalten-Werte (ohne Key, wird automatisch hinzugefügt)
        
        Example:
            await buffer.buffer_upsert(
                table="tracks",
                key_column="spotify_uri",
                key_value="spotify:track:abc123",
                data={"title": "Song", "artist": "Band", "duration_ms": 180000}
            )
        """
        async with self._lock:
            self._buffer[table][key_value] = PendingWrite(
                table=table,
                operation=WriteOperation.UPSERT,
                key_column=key_column,
                key_value=key_value,
                data=data,
            )
            self._writes_buffered += 1
            
            # Backpressure: Force-Flush wenn zu voll
            total = sum(len(t) for t in self._buffer.values())
            if total >= self._config.max_pending_writes:
                logger.warning(
                    f"Buffer full ({total} items), forcing flush"
                )
                asyncio.create_task(self._flush_all())
    
    async def buffer_update(
        self,
        table: str,
        key_column: str,
        key_value: Any,
        data: Dict[str, Any],
    ) -> None:
        """
        Buffer ein UPDATE (nur bestehende Rows).
        
        Wenn bereits ein UPSERT im Buffer ist, werden die Daten gemergt.
        
        Args:
            table: Tabellenname
            key_column: Primary Key Column
            key_value: Wert des Keys
            data: Zu aktualisierende Spalten
        """
        async with self._lock:
            existing = self._buffer[table].get(key_value)
            
            if existing and existing.operation == WriteOperation.UPSERT:
                # Merge mit existierendem UPSERT
                existing.data.update(data)
                existing.timestamp = datetime.now(timezone.utc)
            else:
                self._buffer[table][key_value] = PendingWrite(
                    table=table,
                    operation=WriteOperation.UPDATE,
                    key_column=key_column,
                    key_value=key_value,
                    data=data,
                )
            
            self._writes_buffered += 1
    
    async def buffer_delete(
        self,
        table: str,
        key_column: str,
        key_value: Any,
    ) -> None:
        """
        Buffer ein DELETE.
        
        DELETE überschreibt alle vorherigen Operationen für diesen Key.
        
        Args:
            table: Tabellenname
            key_column: Primary Key Column
            key_value: Wert des zu löschenden Keys
        """
        async with self._lock:
            self._buffer[table][key_value] = PendingWrite(
                table=table,
                operation=WriteOperation.DELETE,
                key_column=key_column,
                key_value=key_value,
                data={},
            )
            self._writes_buffered += 1
    
    # --- Flush Logic ---
    
    async def _flush_loop(self) -> None:
        """Background-Task für periodisches Flushing."""
        while self._running:
            try:
                await asyncio.sleep(self._config.flush_interval)
                await self._flush_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in flush loop: {e}")
                self._flush_errors += 1
    
    async def _flush_all(self) -> None:
        """Flusht alle gepufferten Writes zur Datenbank."""
        async with self._lock:
            if not any(self._buffer.values()):
                return  # Nichts zu flushen
            
            # Sortiere Tables nach Priorität (kritische zuerst)
            tables = sorted(
                self._buffer.keys(),
                key=lambda t: self._config.table_priorities.get(t, 99)
            )
            
            for table in tables:
                writes = list(self._buffer[table].values())
                if not writes:
                    continue
                
                # Gruppiere nach Operation
                upserts = [
                    w for w in writes 
                    if w.operation == WriteOperation.UPSERT
                ]
                updates = [
                    w for w in writes 
                    if w.operation == WriteOperation.UPDATE
                ]
                deletes = [
                    w for w in writes 
                    if w.operation == WriteOperation.DELETE
                ]
                
                try:
                    async with self._session_factory() as session:
                        # Reihenfolge: Deletes → Upserts → Updates
                        if deletes:
                            await self._bulk_delete(session, table, deletes)
                        if upserts:
                            await self._bulk_upsert(session, table, upserts)
                        if updates:
                            await self._bulk_update(session, table, updates)
                        
                        await session.commit()
                    
                    # Erfolg: Buffer leeren
                    self._writes_flushed += len(writes)
                    self._buffer[table].clear()
                    
                    logger.debug(
                        f"Flushed {len(writes)} writes to {table}"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to flush {table}: {e}")
                    self._flush_errors += 1
                    # Buffer bleibt erhalten für nächsten Versuch
        
        self._flush_count += 1
    
    async def _bulk_upsert(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """
        Bulk UPSERT via SQLite ON CONFLICT.
        
        Generiert:
            INSERT INTO "table" (col1, col2, ...)
            VALUES (:col1, :col2, ...)
            ON CONFLICT("key_col") DO UPDATE SET
                col1 = excluded.col1, col2 = excluded.col2, ...
        """
        if not writes:
            return
        
        # Sammle alle Columns aus allen Writes
        all_columns: Set[str] = set()
        for w in writes:
            all_columns.update(w.data.keys())
            all_columns.add(w.key_column)
        
        columns = sorted(all_columns)
        key_col = writes[0].key_column
        
        # Build SQL
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        update_clause = ", ".join(
            f'"{c}" = excluded."{c}"' 
            for c in columns 
            if c != key_col
        )
        
        sql = f"""
            INSERT INTO "{table}" ({col_list})
            VALUES ({placeholders})
            ON CONFLICT("{key_col}") DO UPDATE SET {update_clause}
        """
        
        # Execute in Batches
        batch_size = self._config.batch_size
        for i in range(0, len(writes), batch_size):
            batch = writes[i:i + batch_size]
            params = []
            
            for w in batch:
                row = {c: w.data.get(c) for c in columns}
                row[w.key_column] = w.key_value
                params.append(row)
            
            await session.execute(text(sql), params)
    
    async def _bulk_update(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """
        Bulk UPDATE.
        
        Für kleine Batches: Einzelne UPDATEs (einfacher).
        Für große Batches: CASE WHEN Pattern.
        """
        if not writes:
            return
        
        key_col = writes[0].key_column
        
        # Einfache Variante für kleine Batches
        for w in writes:
            for col, val in w.data.items():
                sql = f"""
                    UPDATE "{table}" 
                    SET "{col}" = :val 
                    WHERE "{key_col}" = :key
                """
                await session.execute(
                    text(sql),
                    {"val": val, "key": w.key_value}
                )
    
    async def _bulk_delete(
        self,
        session: AsyncSession,
        table: str,
        writes: List[PendingWrite],
    ) -> None:
        """
        Bulk DELETE via IN clause.
        
        Chunked in Batches von 500 (SQLite max 999 params).
        """
        if not writes:
            return
        
        key_col = writes[0].key_column
        key_values = [w.key_value for w in writes]
        
        # Chunk in Batches (SQLite Limit)
        for i in range(0, len(key_values), 500):
            batch = key_values[i:i + 500]
            placeholders = ", ".join(
                f":k{j}" for j in range(len(batch))
            )
            
            sql = f"""
                DELETE FROM "{table}" 
                WHERE "{key_col}" IN ({placeholders})
            """
            params = {f"k{j}": v for j, v in enumerate(batch)}
            
            await session.execute(text(sql), params)
    
    # --- Public Methods ---
    
    async def force_flush(self) -> None:
        """
        Erzwingt sofortigen Flush.
        
        Nützlich vor kritischen Operationen oder beim Debugging.
        """
        await self._flush_all()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Gibt Buffer-Statistiken zurück.
        
        Returns:
            Dict mit pending_writes, writes_buffered, writes_flushed, etc.
        """
        total_pending = sum(len(t) for t in self._buffer.values())
        return {
            "pending_writes": total_pending,
            "writes_buffered": self._writes_buffered,
            "writes_flushed": self._writes_flushed,
            "flush_count": self._flush_count,
            "flush_errors": self._flush_errors,
            "is_running": self._running,
            "config": {
                "flush_interval": self._config.flush_interval,
                "max_pending_writes": self._config.max_pending_writes,
                "batch_size": self._config.batch_size,
            },
            "tables": {
                table: len(items) 
                for table, items in self._buffer.items()
            }
        }
    
    async def get_buffered_keys(self, table: str) -> List[Any]:
        """
        Gibt alle gepufferten Keys für eine Tabelle zurück.
        
        Nützlich für Read-Through: Wenn ein Key im Buffer ist,
        sollte der Read die neuesten Daten aus dem Buffer nutzen.
        """
        async with self._lock:
            return list(self._buffer.get(table, {}).keys())
```

---

## Teil 3: Separate Logs-Datenbank

### Warum separate DB für Logs?

Logs haben andere Anforderungen als Business-Daten:
- ❌ Viele Writes (jede Log-Zeile)
- ❌ Verlust akzeptabel (best-effort)
- ❌ Alte Daten werden gelöscht
- ❌ Keine komplexen Queries

Lidarr macht es genauso:
```csharp
// Lidarr: ConnectionStringFactory.cs
MainDbConnection = GetDatabase("lidarr.db");
LogDbConnection = GetDatabase("logs.db");
```

### Implementation

```python
# src/soulspot/infrastructure/persistence/log_database.py
"""
Separate SQLite-Datenbank für Logs (wie Lidarr).

Features:
- Eigene DB-Datei (data/logs.db)
- Async Writes mit Batching
- Best-Effort (Fehler werden geloggt, nicht geworfen)
- Auto-Cleanup alter Logs
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Ein Log-Eintrag."""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    extra: Dict[str, Any] | None = None


class LogDatabase:
    """
    Separate, asynchrone Datenbank für Logs.
    
    Verwendet:
    - Eigene SQLite-Datei (nicht die Haupt-DB)
    - Async Writes in Background-Task
    - Batching (50 Logs pro Write)
    - Auto-Cleanup nach 7 Tagen
    
    Best-Effort:
    - Bei Fehlern: Log geht verloren (akzeptabel)
    - Keine Exceptions nach außen
    - Queue hat Max-Size (10.000)
    """
    
    def __init__(
        self,
        db_path: Path | str = "data/logs.db",
        batch_size: int = 50,
        flush_interval: float = 2.0,
        max_age_days: int = 7,
    ):
        self._db_path = Path(db_path)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_age_days = max_age_days
        
        # Queue mit Max-Size (verhindert Memory-Explosion)
        self._queue: Deque[LogEntry] = deque(maxlen=10000)
        self._running = False
        self._flush_task: asyncio.Task | None = None
    
    async def init(self) -> None:
        """
        Initialisiert die Logs-Datenbank.
        
        Erstellt:
        - data/ Directory falls nicht existiert
        - logs.db mit Schema
        - Index für schnelles Cleanup
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self._db_path) as db:
            # WAL Mode für bessere Concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=500")
            
            # Schema
            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    logger TEXT NOT NULL,
                    message TEXT NOT NULL,
                    extra TEXT
                )
            """)
            
            # Index für Cleanup (nach timestamp)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                ON logs(timestamp)
            """)
            
            await db.commit()
        
        logger.info(f"LogDatabase initialized: {self._db_path}")
    
    async def start(self) -> None:
        """Startet den Background-Writer."""
        if self._running:
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name="log_db_flush"
        )
        logger.info("LogDatabase writer started")
    
    async def stop(self) -> None:
        """Stoppt den Writer und flusht verbleibende Logs."""
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self._flush()
        logger.info("LogDatabase stopped")
    
    def log(
        self,
        level: str,
        logger_name: str,
        message: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        """
        Queued einen Log-Eintrag (non-blocking, sync).
        
        Wird von DatabaseLogHandler aufgerufen.
        Bei voller Queue: Ältester Eintrag wird verworfen (maxlen).
        
        Args:
            level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            logger_name: Name des Loggers (z.B. "soulspot.workers.sync")
            message: Die formatierte Log-Nachricht
            extra: Optionale Zusatz-Daten (pathname, lineno, etc.)
        """
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            logger_name=logger_name,
            message=message,
            extra=extra,
        )
        self._queue.append(entry)  # Thread-safe dank deque
    
    async def _flush_loop(self) -> None:
        """Background-Loop für periodisches Flushing."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Best-effort: Fehler loggen, aber nicht crashen
                print(f"LogDatabase flush error: {e}")
    
    async def _flush(self) -> None:
        """Flusht gepufferte Logs in die DB."""
        if not self._queue:
            return
        
        entries = []
        while self._queue and len(entries) < self._batch_size:
            entries.append(self._queue.popleft())
        
        if not entries:
            return
        
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(
                    """
                    INSERT INTO logs 
                    (timestamp, level, logger, message, extra)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            e.timestamp.isoformat(),
                            e.level,
                            e.logger_name,
                            e.message,
                            json.dumps(e.extra) if e.extra else None,
                        )
                        for e in entries
                    ]
                )
                await db.commit()
        except Exception as e:
            # Best-effort: Bei Fehler einfach verlieren
            # (Logs sind nicht kritisch)
            print(f"LogDatabase write error: {e}")
    
    async def cleanup_old_logs(self) -> int:
        """
        Löscht Logs älter als max_age_days.
        
        Sollte täglich via Housekeeping-Job aufgerufen werden.
        
        Returns:
            Anzahl gelöschter Log-Einträge
        """
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(
            day=cutoff.day - self._max_age_days,
            hour=0, minute=0, second=0, microsecond=0
        )
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM logs WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            deleted = cursor.rowcount
            await db.commit()
        
        logger.info(f"Cleaned up {deleted} old log entries")
        return deleted
    
    async def get_recent_logs(
        self,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Holt die letzten Logs für die UI.
        
        Args:
            level: Optional filtern nach Level (z.B. "ERROR")
            limit: Maximale Anzahl (default: 100)
        
        Returns:
            Liste von Log-Dicts, neueste zuerst
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if level:
                cursor = await db.execute(
                    """
                    SELECT * FROM logs 
                    WHERE level = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (level, limit)
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class DatabaseLogHandler(logging.Handler):
    """
    Logging Handler der in die LogDatabase schreibt.
    
    Integration mit Python's logging:
    
    Example:
        log_db = LogDatabase()
        await log_db.init()
        await log_db.start()
        
        handler = DatabaseLogHandler(log_db)
        handler.setLevel(logging.INFO)
        logging.getLogger("soulspot").addHandler(handler)
    """
    
    def __init__(self, log_db: LogDatabase):
        super().__init__()
        self._log_db = log_db
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Verarbeitet einen Log-Record.
        
        Wird synchron von logging aufgerufen, aber log() ist non-blocking.
        """
        try:
            extra = {
                "pathname": record.pathname,
                "lineno": record.lineno,
                "funcName": record.funcName,
            }
            
            if record.exc_info:
                extra["exception"] = self.format(record)
            
            self._log_db.log(
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                extra=extra,
            )
        except Exception:
            # Handler sollte nie crashen
            self.handleError(record)
```

---

## Teil 4: BusyTimeout Anpassung

### Warum reduzieren?

| Setting | Alt | Neu | Begründung |
|---------|-----|-----|------------|
| BusyTimeout | 60.000ms | 500ms | Fail fast, retry mit Backoff |

Lidarr verwendet 100ms. Wir wählen 500ms als Kompromiss:
- Lang genug für normale Operationen
- Kurz genug für schnelle Retries
- Mit Retry-Strategy: Max 3 × 500ms = 1.5s (besser als 60s Block)

### Implementation

```python
# src/soulspot/infrastructure/persistence/database.py

# ALT:
# connect_args={"timeout": 60}  # 60 Sekunden

# NEU:
connect_args={
    "timeout": 0.5,  # 500ms - fail fast
    "check_same_thread": False,
}

# Oder via URL:
DATABASE_URL = (
    f"sqlite+aiosqlite:///{db_path}"
    "?timeout=0.5"
    "&mode=wal"
)
```

---

## Teil 5: Integration in Lifecycle

```python
# src/soulspot/infrastructure/lifecycle.py

from soulspot.infrastructure.persistence.write_buffer_cache import (
    WriteBufferCache, BufferConfig
)
from soulspot.infrastructure.persistence.log_database import (
    LogDatabase, DatabaseLogHandler
)


async def init_hybrid_db_strategy(app: FastAPI) -> None:
    """
    Initialisiert die Hybrid-DB-Strategie:
    1. WriteBufferCache für Worker
    2. LogDatabase für Logs
    3. RetryStrategy wird via Decorator verwendet
    """
    config = app.state.config
    
    # 1. WriteBufferCache für Worker
    buffer_config = BufferConfig(
        flush_interval=5.0,
        max_pending_writes=2000,
        batch_size=100,
    )
    
    write_buffer = WriteBufferCache(
        session_factory=app.state.session_factory,
        config=buffer_config,
    )
    await write_buffer.start()
    app.state.write_buffer = write_buffer
    
    # 2. Separate Logs-Datenbank
    log_db = LogDatabase(
        db_path=config.data_dir / "logs.db",
        batch_size=50,
        flush_interval=2.0,
        max_age_days=7,
    )
    await log_db.init()
    await log_db.start()
    app.state.log_db = log_db
    
    # Log-Handler für soulspot.* Logger
    handler = DatabaseLogHandler(log_db)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logging.getLogger("soulspot").addHandler(handler)
    
    logger.info("Hybrid DB strategy initialized")


async def shutdown_hybrid_db_strategy(app: FastAPI) -> None:
    """Fährt die Hybrid-Komponenten sauber herunter."""
    
    # WriteBuffer stoppen (flusht verbleibende Writes)
    if hasattr(app.state, "write_buffer"):
        stats = app.state.write_buffer.get_stats()
        logger.info(f"WriteBuffer final stats: {stats}")
        await app.state.write_buffer.stop(flush_remaining=True)
    
    # LogDatabase stoppen
    if hasattr(app.state, "log_db"):
        await app.state.log_db.stop()
    
    logger.info("Hybrid DB strategy shutdown complete")


# In lifespan():
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing init ...
    await init_hybrid_db_strategy(app)
    
    yield
    
    await shutdown_hybrid_db_strategy(app)
    # ... existing shutdown ...
```

---

## Teil 6: Entscheidungsmatrix

### Wann welche Strategie verwenden?

| Komponente | Strategie | Begründung |
|------------|-----------|------------|
| **API Routes** | `@with_retry` | User erwartet direktes Feedback |
| **Settings-Änderungen** | `@with_retry` | User-initiated, muss konsistent sein |
| **TokenRefreshWorker** | `@with_retry` | Seltene, kritische Writes |
| **SpotifySyncWorker** | `WriteBufferCache` | Viele schnelle Track-Updates |
| **DeezerSyncWorker** | `WriteBufferCache` | Viele schnelle Updates |
| **DownloadWorker** | `WriteBufferCache` | Häufige Status-Updates |
| **Library Scan** | `WriteBufferCache` | Bulk-Import von Tracks |
| **Logging** | `LogDatabase` | Separate DB, best-effort |
| **Housekeeping** | `@with_retry` | Periodisch, nicht zeitkritisch |

### Entscheidungsbaum

```
Ist die Operation User-initiated?
├── JA → @with_retry (direktes Feedback wichtig)
└── NEIN
    │
    ├── Sind es viele Writes in kurzer Zeit?
    │   ├── JA → WriteBufferCache
    │   └── NEIN → @with_retry
    │
    └── Ist es Logging?
        ├── JA → LogDatabase
        └── NEIN → Siehe oben
```

---

## Teil 7: Migration Plan

### Phase 1: Infrastruktur (Woche 1)

- [ ] `retry_strategy.py` erstellen
- [ ] `write_buffer_cache.py` erstellen  
- [ ] `log_database.py` erstellen
- [ ] BusyTimeout auf 500ms reduzieren
- [ ] Tests für alle Komponenten

### Phase 2: Worker-Integration (Woche 2)

- [ ] SpotifySyncWorker auf WriteBufferCache
- [ ] DeezerSyncWorker auf WriteBufferCache
- [ ] DownloadWorker auf WriteBufferCache
- [ ] Library Scanner auf WriteBufferCache

### Phase 3: API-Integration (Woche 3)

- [ ] Alle Repositories mit `@with_retry` decorieren
- [ ] Logging auf LogDatabase umstellen
- [ ] Log-Cleanup Housekeeping-Job
- [ ] API Endpoint für Buffer-Stats

### Phase 4: Monitoring & Polish (Woche 4)

- [ ] Metriken-Dashboard (Grafana/Prometheus)
- [ ] Load-Tests mit parallelen Workern
- [ ] Performance-Vergleich vor/nach
- [ ] Dokumentation finalisieren

---

## Teil 8: Vergleich mit Lidarr

| Aspekt | Lidarr | SoulSpot Hybrid |
|--------|--------|-----------------|
| **API-Strategie** | Polly Retry | Tenacity-style Retry |
| **Worker-Strategie** | Direkte Writes | WriteBufferCache |
| **BusyTimeout** | 100ms | 500ms |
| **Retry Count** | 3 | 3 |
| **Backoff** | Exponential + Jitter | Exponential + Jitter |
| **Separate Log-DB** | ✅ Ja | ✅ Ja |
| **Async Log Writer** | SlowRunningAsyncTargetWrapper | LogDatabase |
| **Batch für Logs** | 500ms | 2000ms |

**Fazit:** Wir übernehmen Lidarrs bewährte Patterns, erweitern aber mit WriteBufferCache für unsere Worker, die mehr Writes machen als Lidarr.

---

## FAQ

### Q: Was passiert bei Stromausfall während Buffer nicht geflusht?

A: Daten im RAM gehen verloren. Bei SpotifySync: Nächster Sync holt sie wieder. Bei Downloads: Status wird beim nächsten Start aus Filesystem rekonstruiert.

### Q: Können Reads inkonsistente Daten sehen?

A: Ja, kurz nach einem Write kann ein Read noch die alten Daten sehen (bis zum Flush). Für kritische Reads: `force_flush()` aufrufen oder direkt aus Buffer lesen.

### Q: Warum nicht Postgres statt SQLite?

A: SoulSpot ist für Einzelnutzer/Home-Use designed. SQLite ist einfacher (keine separate DB), schneller für unseren Use-Case, und die Hybrid-Strategie löst das Concurrency-Problem.

### Q: Wie debugge ich Buffer-Probleme?

A: 
1. `GET /api/debug/write-buffer` zeigt Buffer-Stats
2. `await write_buffer.force_flush()` erzwingt sofortigen Flush
3. Logs zeigen Flush-Errors

---

## Changelog

- **v1.0** (2025-01-17): Initial design based on Lidarr analysis
