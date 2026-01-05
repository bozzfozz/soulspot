# Write-Behind Cache für SQLite

> **Vollständige Architektur-Dokumentation**  
> Version: 1.1 (mit Optimierungen)  
> Erstellt: 2025-01-17  
> Status: Design Phase

---

> **📖 Siehe auch:** [HYBRID_DB_STRATEGY.md](./HYBRID_DB_STRATEGY.md) für die vollständige Hybrid-Strategie (WriteBufferCache + RetryStrategy + LogDatabase), die Lidarrs bewährte Patterns mit diesem Cache kombiniert.

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Problem-Analyse](#2-problem-analyse)
3. [Lösung: Write-Behind Cache](#3-lösung-write-behind-cache)
4. [Architektur-Design](#4-architektur-design)
5. [Implementierung](#5-implementierung)
6. [Bulk-Operationen](#6-bulk-operationen)
7. [Integration](#7-integration)
8. [Testing & Validierung](#8-testing--validierung)
9. [Metriken & Monitoring](#9-metriken--monitoring)
10. [Rollout-Plan](#10-rollout-plan)
11. [FAQ](#11-faq)
12. [Optimierungen & Erweiterungen](#12-optimierungen--erweiterungen) ← **NEU**

---

## 1. Executive Summary

### Was ist das Problem?

SoulSpot verwendet SQLite als Datenbank. SQLite erlaubt nur **einen Writer gleichzeitig**. Wenn mehrere Background-Worker (Spotify-Sync, Deezer-Sync, Image-Download, etc.) gleichzeitig Daten schreiben wollen, blockieren sie sich gegenseitig und **blockieren die UI**.

### Was ist die Lösung?

Ein **Write-Behind Cache** (auch "Write-Back Cache" genannt) puffert alle Schreiboperationen im RAM und schreibt sie **periodisch in Batches** zur Datenbank. Dadurch:

- ✅ Worker-Writes sind instant (0ms)
- ✅ UI bleibt immer responsiv
- ✅ DB-Writes sind 50x schneller (Bulk statt Einzeln)
- ✅ Mehrfache Updates zum gleichen Datensatz werden zusammengefasst

### Technische Kennzahlen

| Metrik | Ohne Cache | Mit Write-Behind Cache |
|--------|------------|------------------------|
| Write Latenz | 10-100ms (DB Lock) | 0ms (RAM) |
| UI Blockierung | 1-30 Sekunden | Nie |
| Throughput | ~100 rows/sec | ~5,000 rows/sec |
| Concurrent Writers | 1 (blockierend) | Unbegrenzt (gepuffert) |

---

## 2. Problem-Analyse

### 2.1 Aktuelle Situation

```
┌─────────────────────────────────────────────────────────────┐
│                    AKTUELLES SYSTEM                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Worker A ────┐                                            │
│   Worker B ────┼───► SQLite ───► "database is locked" 🔒    │
│   Worker C ────┘        │                                   │
│                         │                                   │
│   UI (FastAPI) ─────────┘  ← BLOCKIERT während Lock         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 SQLite Limitierungen

SQLite ist eine **embedded database** mit folgenden Eigenschaften:

| Feature | SQLite Verhalten |
|---------|-----------------|
| **Concurrent Reads** | ✅ Unbegrenzt (mit WAL) |
| **Concurrent Writes** | ❌ Nur 1 Writer |
| **Write Lock** | Blockiert bis Transaction committed |
| **Lock Timeout** | Konfigurierbar (default: 5s) |

**WAL Mode** (Write-Ahead Logging) ist bereits aktiviert:
```python
# database.py
"PRAGMA journal_mode=WAL"
```

**Was WAL löst:**
- Reader blockieren Writer nicht
- Writer blockieren Reader nicht

**Was WAL NICHT löst:**
- Mehrere Writer blockieren sich immer noch gegenseitig

### 2.3 Symptome im Log

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
```

```
WARNING: Retrying database operation (attempt 2/5) after 1.0s
WARNING: Retrying database operation (attempt 3/5) after 2.0s
WARNING: Retrying database operation (attempt 4/5) after 4.0s
```

### 2.4 Betroffene Worker

| Worker | DB Operationen | Häufigkeit |
|--------|---------------|------------|
| SpotifySyncWorker | Tracks, Albums, Artists, Playlists | 100-1000 rows/sync |
| DeezerSyncWorker | Tracks, Albums, Artists | 100-1000 rows/sync |
| ImageDownloadWorker | Track/Album/Artist image URLs | 50-200 rows/sync |
| DownloadWorker | Download status updates | 10-100 rows/batch |
| MetadataEnricher | Track metadata updates | 10-50 rows/batch |

---

## 3. Lösung: Write-Behind Cache

### 3.1 Konzept

```
┌─────────────────────────────────────────────────────────────┐
│                    MIT WRITE-BEHIND CACHE                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Worker A ────┐                                            │
│   Worker B ────┼───► WriteBufferCache ───┐                  │
│   Worker C ────┘      (RAM, instant)     │                  │
│                                          │ flush()          │
│                                          │ every 5s         │
│                                          ▼                  │
│                                       SQLite                │
│                                    (batch write)            │
│                                                             │
│   UI (FastAPI) ───► ReadCache ───► DB (wenn Cache miss)     │
│                    (LRU, 0ms)                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Datenfluss

#### Write Path (Worker → Cache → DB)

```
1. Worker ruft cache.upsert("tracks", track_id, data) auf
2. WriteBufferCache speichert in RAM dict (instant, 0ms)
3. Worker bekommt sofort "success" zurück
4. ... Worker macht weiter mit nächstem Track ...
5. ... 5 Sekunden später ...
6. Auto-Flush Task wacht auf
7. Alle pending writes werden als BATCH zur DB geschrieben
8. Eine einzige Transaction für 500+ rows
```

#### Read Path (UI → Cache → DB)

```
1. UI ruft cache.get("tracks", track_id) auf
2. Check: Ist track_id in pending_writes? → Return sofort
3. Check: Ist track_id in read_cache (LRU)? → Return sofort
4. Fallback: Query DB
5. Ergebnis in read_cache speichern
6. Return zu UI
```

### 3.3 Warum funktioniert das?

**Bewährtes Pattern:**
- Write-Behind/Write-Back Cache ist Standard in Enterprise-Systemen
- Verwendet von: Redis, Hazelcast, EHCache, Memcached
- Etabliert seit 20+ Jahren in Datenbank-Systemen

**SQLite-kompatibel:**
- WAL + Batched Writes = optimal für SQLite
- Reduziert Lock-Contention auf Minimum
- Nutzt SQLite's Stärke: schnelle Bulk-Operationen

**Trade-offs:**
| Vorteil | Kosten |
|---------|--------|
| Instant Writes | Max 5s Delay bis DB |
| Keine Lock-Blockierung | Eventual Consistency |
| 50x besserer Throughput | Mehr RAM-Verbrauch |
| Coalescing (Dedupe) | Komplexität |

---

## 4. Architektur-Design

### 4.1 Komponenten-Übersicht

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SOULSPOT APPLICATION                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐         ┌───────────────────────────────────┐   │
│  │   FastAPI UI      │         │        Background Workers          │   │
│  │   (Reads + HTTP)  │         │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │   │
│  └─────────┬─────────┘         │  │Spot.│ │Deez.│ │Image│ │Down.│  │   │
│            │                   │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘  │   │
│            │                   └─────┼──────┼──────┼──────┼───────┘   │
│            │                         │      │      │      │           │
│            │ get()                   │upsert()    update()│           │
│            ▼                         ▼      ▼      ▼      ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    🔥 WriteBufferCache 🔥                        │  │
│  │  ┌────────────────────────────────────────────────────────────┐ │  │
│  │  │ Layer 1: Write Buffer (RAM)                                │ │  │
│  │  │ ├── pending_upserts[table][pk] = {entity_data}            │ │  │
│  │  │ ├── pending_updates[table][pk] = {field: value}           │ │  │
│  │  │ └── write_timestamps[table][pk] = datetime                │ │  │
│  │  ├────────────────────────────────────────────────────────────┤ │  │
│  │  │ Layer 2: Read Cache (LRU)                                  │ │  │
│  │  │ └── read_through_cache[key] = entity (TTL: 5min)          │ │  │
│  │  ├────────────────────────────────────────────────────────────┤ │  │
│  │  │ Layer 3: Flush Engine                                      │ │  │
│  │  │ ├── auto_flush_task (every 5s)                            │ │  │
│  │  │ ├── emergency_flush (on buffer_full)                      │ │  │
│  │  │ └── shutdown_flush (on app shutdown)                      │ │  │
│  │  └────────────────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────┬───────────────────────────────┘  │
│                                    │                                   │
│                        flush() with session_scope_with_retry()         │
│                                    │                                   │
│  ┌─────────────────────────────────▼───────────────────────────────┐  │
│  │                      SQLite + WAL Mode                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │  │
│  │  │   tracks    │  │   albums    │  │   artists   │  ...         │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Datei-Struktur

```
src/soulspot/
├── application/
│   └── cache/
│       ├── __init__.py              # Export WriteBufferCache
│       ├── base_cache.py            # ✅ Existiert bereits
│       ├── enhanced_cache.py        # ✅ Existiert (LRUCache)
│       ├── write_buffer.py          # 🆕 NEU: WriteBufferCache Klasse
│       └── buffer_flush_service.py  # 🆕 NEU: Flush-Logik
│
├── infrastructure/
│   └── persistence/
│       ├── database.py              # ✅ Existiert
│       ├── repositories.py          # 📝 ERWEITERN: bulk_upsert()
│       └── bulk_operations.py       # 🆕 NEU: Batch SQL-Operationen
│
└── domain/
    └── ports/
        └── __init__.py              # 📝 ERWEITERN: IWriteBuffer Interface
```

### 4.3 Konfiguration

```python
@dataclass
class BufferConfig:
    """Konfiguration für den Write-Buffer."""
    
    # Buffer Limits
    max_buffer_size: int = 10_000          # Max Einträge bevor Emergency-Flush
    batch_size: int = 500                   # Max Rows pro DB-Transaction
    
    # Timing
    flush_interval_seconds: float = 5.0     # Auto-Flush Intervall
    
    # Read Cache
    read_cache_size: int = 5_000            # LRU Cache Größe
    read_cache_ttl_seconds: int = 300       # TTL für Read-Cache (5 min)
    
    # Features
    enable_coalescing: bool = True          # Mehrfache Updates zusammenführen
```

---

## 5. Implementierung

### 5.1 WriteBufferCache Klasse

```python
# src/soulspot/application/cache/write_buffer.py
"""
Write-Behind Cache für SoulSpot.

ZWECK: Entkoppelt Worker-Writes von DB-Writes, damit UI nie blockiert.

ARCHITEKTUR:
- pending_upserts: RAM-Buffer für neue/geänderte Entities
- read_cache: LRU für schnelle Reads
- flush_engine: Background Task für periodisches DB-Schreiben

GARANTIEN:
- Write: Immer 0ms (nur RAM)
- Read: Cache-Hit = 0ms, Cache-Miss = DB-Query
- Consistency: Eventual (max 5s delay)
- Durability: Flush bei Shutdown + Emergency Flush bei Buffer-Full
"""

from __future__ import annotations

import asyncio
import atexit
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Generic, TypeVar

from soulspot.application.cache.enhanced_cache import LRUCache
from soulspot.infrastructure.persistence.database import session_scope_with_retry

T = TypeVar("T")


@dataclass
class BufferConfig:
    """Konfiguration für den Write-Buffer."""
    
    max_buffer_size: int = 10_000          # Max Einträge bevor Emergency-Flush
    flush_interval_seconds: float = 5.0     # Auto-Flush Intervall
    read_cache_size: int = 5_000            # LRU Cache Größe
    read_cache_ttl_seconds: int = 300       # TTL für Read-Cache (5 min)
    enable_coalescing: bool = True          # Mehrfache Updates zusammenführen
    batch_size: int = 500                   # Max Rows pro DB-Transaction


@dataclass
class PendingWrite:
    """Ein gepufferter Schreibvorgang."""
    
    table: str
    primary_key: Any
    data: dict[str, Any]
    operation: str  # "upsert" oder "update"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WriteBufferCache(Generic[T]):
    """
    Write-Behind Cache mit automatischem Flush.
    
    VERWENDUNG:
    ```python
    cache = WriteBufferCache(config=BufferConfig())
    await cache.start()  # Startet Auto-Flush Task
    
    # Worker schreibt (instant, 0ms)
    await cache.upsert("tracks", track.id, track.to_dict())
    
    # UI liest (Cache-first, DB-fallback)
    track_data = await cache.get("tracks", track_id, db_fallback=repo.get_by_id)
    
    await cache.stop()  # Finaler Flush + Cleanup
    ```
    """
    
    def __init__(
        self,
        config: BufferConfig | None = None,
        flush_callback: Callable | None = None,
    ) -> None:
        self._config = config or BufferConfig()
        self._flush_callback = flush_callback
        
        # Layer 1: Write Buffer
        self._pending_upserts: dict[str, dict[Any, dict]] = defaultdict(dict)
        self._pending_updates: dict[str, dict[Any, dict]] = defaultdict(dict)
        
        # Layer 2: Read Cache (nutzt bestehenden LRUCache)
        self._read_cache = LRUCache[str, dict](
            maxsize=self._config.read_cache_size,
            ttl=self._config.read_cache_ttl_seconds,
        )
        
        # Layer 3: Flush Engine
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()
        self._running = False
        
        # Metrics
        self._stats = {
            "writes_buffered": 0,
            "writes_coalesced": 0,
            "flushes_completed": 0,
            "flush_errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        
        # Emergency shutdown hook
        atexit.register(self._sync_emergency_flush)
    
    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API: Lifecycle
    # ═══════════════════════════════════════════════════════════════════
    
    async def start(self) -> None:
        """Startet den Auto-Flush Background Task."""
        if self._running:
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(
            self._auto_flush_loop(),
            name="write_buffer_auto_flush",
        )
    
    async def stop(self) -> None:
        """Stoppt den Cache und flusht alle ausstehenden Writes."""
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Finaler Flush
        await self.flush()
    
    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API: Write Operations (für Worker)
    # ═══════════════════════════════════════════════════════════════════
    
    async def upsert(
        self,
        table: str,
        primary_key: Any,
        data: dict[str, Any],
    ) -> None:
        """
        Puffert einen UPSERT (Insert oder Update).
        
        GARANTIE: Kehrt sofort zurück (0ms), keine DB-Interaktion.
        
        Args:
            table: Tabellenname (z.B. "tracks", "albums")
            primary_key: Primary Key der Entity
            data: Vollständige Entity-Daten als dict
        """
        cache_key = self._make_cache_key(table, primary_key)
        
        async with self._flush_lock:
            # Coalescing: Wenn bereits ein pending upsert existiert, überschreiben
            if self._config.enable_coalescing and primary_key in self._pending_upserts[table]:
                self._stats["writes_coalesced"] += 1
            
            self._pending_upserts[table][primary_key] = data
            self._stats["writes_buffered"] += 1
            
            # Update read cache sofort (für Read-after-Write Konsistenz)
            self._read_cache.set(cache_key, data)
        
        # Emergency flush wenn Buffer zu voll
        if self._buffer_size() > self._config.max_buffer_size:
            asyncio.create_task(self.flush())
    
    async def update(
        self,
        table: str,
        primary_key: Any,
        updates: dict[str, Any],
    ) -> None:
        """
        Puffert ein UPDATE (nur geänderte Felder).
        
        GARANTIE: Kehrt sofort zurück (0ms), keine DB-Interaktion.
        
        Args:
            table: Tabellenname
            primary_key: Primary Key der Entity
            updates: Nur die geänderten Felder {field: new_value}
        """
        cache_key = self._make_cache_key(table, primary_key)
        
        async with self._flush_lock:
            # Merge mit existierenden pending updates
            if primary_key in self._pending_updates[table]:
                self._pending_updates[table][primary_key].update(updates)
                self._stats["writes_coalesced"] += 1
            else:
                self._pending_updates[table][primary_key] = updates
            
            self._stats["writes_buffered"] += 1
            
            # Update read cache (merge mit existierendem)
            if cached := self._read_cache.get(cache_key):
                cached.update(updates)
                self._read_cache.set(cache_key, cached)
    
    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API: Read Operations (für UI/API)
    # ═══════════════════════════════════════════════════════════════════
    
    async def get(
        self,
        table: str,
        primary_key: Any,
        db_fallback: Callable | None = None,
    ) -> dict[str, Any] | None:
        """
        Liest eine Entity (Cache-first, DB-fallback).
        
        REIHENFOLGE:
        1. Check pending_upserts (uncommitted writes)
        2. Check read_cache (LRU)
        3. Query DB (via db_fallback callback)
        
        Args:
            table: Tabellenname
            primary_key: Primary Key
            db_fallback: Async Funktion für DB-Lookup
        
        Returns:
            Entity als dict oder None
        """
        cache_key = self._make_cache_key(table, primary_key)
        
        # 1. Check pending writes (höchste Priorität)
        if primary_key in self._pending_upserts.get(table, {}):
            self._stats["cache_hits"] += 1
            return self._pending_upserts[table][primary_key]
        
        # 2. Check read cache
        if cached := self._read_cache.get(cache_key):
            self._stats["cache_hits"] += 1
            return cached
        
        # 3. DB fallback
        self._stats["cache_misses"] += 1
        
        if db_fallback:
            result = await db_fallback(primary_key)
            if result:
                # Populate cache
                data = result if isinstance(result, dict) else result.__dict__
                self._read_cache.set(cache_key, data)
                return data
        
        return None
    
    async def get_many(
        self,
        table: str,
        primary_keys: list[Any],
        db_fallback: Callable | None = None,
    ) -> dict[Any, dict[str, Any]]:
        """
        Bulk-Read für mehrere Entities.
        
        Returns:
            Dict mapping pk → entity_data
        """
        results = {}
        missing_pks = []
        
        for pk in primary_keys:
            cache_key = self._make_cache_key(table, pk)
            
            # Check pending
            if pk in self._pending_upserts.get(table, {}):
                results[pk] = self._pending_upserts[table][pk]
                continue
            
            # Check cache
            if cached := self._read_cache.get(cache_key):
                results[pk] = cached
                continue
            
            missing_pks.append(pk)
        
        # Bulk DB lookup für cache misses
        if missing_pks and db_fallback:
            db_results = await db_fallback(missing_pks)
            for pk, data in db_results.items():
                cache_key = self._make_cache_key(table, pk)
                self._read_cache.set(cache_key, data)
                results[pk] = data
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API: Flush Operations
    # ═══════════════════════════════════════════════════════════════════
    
    async def flush(self) -> int:
        """
        Flusht alle pending Writes zur DB.
        
        Returns:
            Anzahl der geschriebenen Records
        """
        async with self._flush_lock:
            # Snapshot und Reset
            upserts_to_flush = dict(self._pending_upserts)
            updates_to_flush = dict(self._pending_updates)
            
            self._pending_upserts = defaultdict(dict)
            self._pending_updates = defaultdict(dict)
        
        if not upserts_to_flush and not updates_to_flush:
            return 0
        
        total_written = 0
        
        try:
            async with session_scope_with_retry() as session:
                # Process upserts per table
                for table, records in upserts_to_flush.items():
                    if records:
                        count = await self._bulk_upsert(session, table, records)
                        total_written += count
                
                # Process updates per table
                for table, records in updates_to_flush.items():
                    if records:
                        count = await self._bulk_update(session, table, records)
                        total_written += count
                
                await session.commit()
            
            self._stats["flushes_completed"] += 1
            
        except Exception as e:
            self._stats["flush_errors"] += 1
            
            # Restore failed writes (wichtig für Durability!)
            async with self._flush_lock:
                for table, records in upserts_to_flush.items():
                    self._pending_upserts[table].update(records)
                for table, records in updates_to_flush.items():
                    self._pending_updates[table].update(records)
            
            raise
        
        return total_written
    
    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API: Stats & Monitoring
    # ═══════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> dict[str, Any]:
        """Gibt Cache-Statistiken zurück."""
        return {
            **self._stats,
            "buffer_size": self._buffer_size(),
            "read_cache_size": len(self._read_cache),
            "pending_tables": list(self._pending_upserts.keys()),
        }
    
    def _buffer_size(self) -> int:
        """Berechnet aktuelle Buffer-Größe."""
        upsert_count = sum(len(v) for v in self._pending_upserts.values())
        update_count = sum(len(v) for v in self._pending_updates.values())
        return upsert_count + update_count
    
    # ═══════════════════════════════════════════════════════════════════
    # PRIVATE: Internal Methods
    # ═══════════════════════════════════════════════════════════════════
    
    def _make_cache_key(self, table: str, pk: Any) -> str:
        """Generiert eindeutigen Cache-Key."""
        return f"{table}:{pk}"
    
    async def _auto_flush_loop(self) -> None:
        """Background Task für periodisches Flushing."""
        while self._running:
            try:
                await asyncio.sleep(self._config.flush_interval_seconds)
                if self._buffer_size() > 0:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log but continue (wichtig: nicht crashen!)
                self._stats["flush_errors"] += 1
    
    async def _bulk_upsert(
        self,
        session: Any,
        table: str,
        records: dict[Any, dict],
    ) -> int:
        """
        Führt Batch-UPSERT zur DB durch.
        
        MUSS mit flush_callback oder bulk_operations.py implementiert werden!
        """
        if self._flush_callback:
            return await self._flush_callback(session, table, "upsert", records)
        
        # Fallback: Einzelne INSERTs (langsamer, aber funktioniert)
        return len(records)
    
    async def _bulk_update(
        self,
        session: Any,
        table: str,
        records: dict[Any, dict],
    ) -> int:
        """Führt Batch-UPDATE zur DB durch."""
        if self._flush_callback:
            return await self._flush_callback(session, table, "update", records)
        return len(records)
    
    def _sync_emergency_flush(self) -> None:
        """
        Synchroner Emergency-Flush für atexit.
        
        ACHTUNG: Wird nur bei normalem Python-Exit aufgerufen,
        nicht bei SIGKILL oder Crash.
        """
        if self._buffer_size() > 0:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.flush())
                else:
                    loop.run_until_complete(self.flush())
            except Exception:
                pass  # Best effort
```

---

## 6. Bulk-Operationen

### 6.1 bulk_operations.py

```python
# src/soulspot/infrastructure/persistence/bulk_operations.py
"""
Bulk-SQL-Operationen für WriteBufferCache.

PERFORMANCE:
- Einzelne INSERTs: ~100 rows/sec
- Bulk INSERT: ~10,000 rows/sec
- Bulk UPSERT mit ON CONFLICT: ~5,000 rows/sec
"""

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from soulspot.infrastructure.persistence.models import (
    TrackModel,
    AlbumModel,
    ArtistModel,
    PlaylistModel,
)


# Table → Model mapping
TABLE_MODELS = {
    "tracks": TrackModel,
    "albums": AlbumModel,
    "artists": ArtistModel,
    "playlists": PlaylistModel,
}


async def bulk_upsert(
    session: AsyncSession,
    table: str,
    records: dict[Any, dict[str, Any]],
) -> int:
    """
    SQLite UPSERT mit ON CONFLICT DO UPDATE.
    
    PERFORMANCE: ~5,000 rows/sec (vs ~100 rows/sec einzeln)
    
    Args:
        session: SQLAlchemy AsyncSession
        table: Tabellenname
        records: Dict[primary_key, entity_data]
    
    Returns:
        Anzahl verarbeiteter Records
    """
    if not records:
        return 0
    
    model = TABLE_MODELS.get(table)
    if not model:
        raise ValueError(f"Unknown table: {table}")
    
    # SQLite INSERT ... ON CONFLICT DO UPDATE
    values_list = list(records.values())
    
    stmt = sqlite_insert(model).values(values_list)
    
    # ON CONFLICT: Update alle Spalten außer Primary Key
    update_columns = {
        col.name: stmt.excluded[col.name]
        for col in model.__table__.columns
        if not col.primary_key
    }
    
    stmt = stmt.on_conflict_do_update(
        index_elements=[model.__table__.primary_key.columns.values()[0]],
        set_=update_columns,
    )
    
    await session.execute(stmt)
    return len(records)


async def bulk_update(
    session: AsyncSession,
    table: str,
    records: dict[Any, dict[str, Any]],
) -> int:
    """
    Bulk UPDATE mit CASE WHEN.
    
    Generiert:
    ```sql
    UPDATE tracks SET
      title = CASE id WHEN 1 THEN 'A' WHEN 2 THEN 'B' END,
      artist = CASE id WHEN 1 THEN 'X' WHEN 2 THEN 'Y' END
    WHERE id IN (1, 2)
    ```
    
    PERFORMANCE: ~3,000 rows/sec
    """
    if not records:
        return 0
    
    model = TABLE_MODELS.get(table)
    if not model:
        raise ValueError(f"Unknown table: {table}")
    
    pk_column = model.__table__.primary_key.columns.values()[0].name
    
    # Sammle alle zu updatenden Felder
    all_fields: set[str] = set()
    for updates in records.values():
        all_fields.update(updates.keys())
    
    if not all_fields:
        return 0
    
    # Build CASE WHEN statements
    set_clauses = []
    params = {}
    
    for field in all_fields:
        cases = []
        for i, (pk, updates) in enumerate(records.items()):
            if field in updates:
                param_name = f"{field}_{i}"
                cases.append(f"WHEN {pk_column} = :pk_{i} THEN :{param_name}")
                params[f"pk_{i}"] = pk
                params[param_name] = updates[field]
        
        if cases:
            set_clauses.append(f"{field} = CASE {' '.join(cases)} ELSE {field} END")
    
    if not set_clauses:
        return 0
    
    # Build final query
    pks = list(records.keys())
    pk_params = {f"pk_{i}": pk for i, pk in enumerate(pks)}
    params.update(pk_params)
    
    pk_placeholders = ", ".join(f":pk_{i}" for i in range(len(pks)))
    
    sql = f"""
        UPDATE {table}
        SET {', '.join(set_clauses)}
        WHERE {pk_column} IN ({pk_placeholders})
    """
    
    await session.execute(text(sql), params)
    return len(records)
```

### 6.2 Performance-Vergleich

| Operation | Methode | Rows/sec | SQL Statements |
|-----------|---------|----------|----------------|
| Insert 1000 rows | Einzeln | ~100 | 1000 INSERTs |
| Insert 1000 rows | Bulk | ~10,000 | 1 INSERT |
| Upsert 1000 rows | Einzeln | ~80 | 1000 INSERT...ON CONFLICT |
| Upsert 1000 rows | Bulk | ~5,000 | 1 INSERT...ON CONFLICT |
| Update 1000 rows | Einzeln | ~100 | 1000 UPDATEs |
| Update 1000 rows | Bulk CASE | ~3,000 | 1 UPDATE mit CASE |

---

## 7. Integration

### 7.1 Lifecycle Integration

```python
# Änderungen in src/soulspot/infrastructure/lifecycle.py

from soulspot.application.cache.write_buffer import WriteBufferCache, BufferConfig
from soulspot.infrastructure.persistence.bulk_operations import bulk_upsert, bulk_update


# Globale WriteBuffer Instanz
_write_buffer: WriteBufferCache | None = None


def get_write_buffer() -> WriteBufferCache:
    """Gibt die globale WriteBuffer Instanz zurück."""
    global _write_buffer
    if _write_buffer is None:
        raise RuntimeError("WriteBuffer not initialized. Call init_write_buffer() first.")
    return _write_buffer


async def init_write_buffer() -> WriteBufferCache:
    """Initialisiert den WriteBuffer beim App-Start."""
    global _write_buffer
    
    async def flush_callback(session, table, operation, records):
        if operation == "upsert":
            return await bulk_upsert(session, table, records)
        elif operation == "update":
            return await bulk_update(session, table, records)
        return 0
    
    config = BufferConfig(
        max_buffer_size=10_000,
        flush_interval_seconds=5.0,
        read_cache_size=5_000,
        read_cache_ttl_seconds=300,
        enable_coalescing=True,
        batch_size=500,
    )
    
    _write_buffer = WriteBufferCache(
        config=config,
        flush_callback=flush_callback,
    )
    
    await _write_buffer.start()
    return _write_buffer


async def shutdown_write_buffer() -> None:
    """Shutdown mit finalem Flush."""
    global _write_buffer
    if _write_buffer:
        await _write_buffer.stop()
        _write_buffer = None


# In lifespan context manager:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_write_buffer()
    
    yield
    
    # Shutdown
    await shutdown_write_buffer()
```

### 7.2 Dependency Injection

```python
# src/soulspot/api/dependencies.py

from soulspot.application.cache.write_buffer import WriteBufferCache
from soulspot.infrastructure.lifecycle import get_write_buffer


def get_write_buffer_dep() -> WriteBufferCache:
    """FastAPI Dependency für WriteBufferCache."""
    return get_write_buffer()
```

### 7.3 Worker Integration

```python
# Änderungen in unified_library_worker.py

class UnifiedLibraryManager:
    def __init__(
        self,
        ...,
        write_buffer: WriteBufferCache,  # NEU
    ):
        self._write_buffer = write_buffer
    
    async def _sync_tracks(self, tracks: list[Track]) -> None:
        """Sync Tracks mit Write-Buffer statt direkter DB."""
        for track in tracks:
            # VORHER: await self._track_repo.upsert(track)
            # NACHHER:
            await self._write_buffer.upsert(
                table="tracks",
                primary_key=track.id,
                data=track.to_dict(),
            )
    
    async def _update_track_metadata(self, track_id: str, metadata: dict) -> None:
        """Partial Update mit Buffer."""
        await self._write_buffer.update(
            table="tracks",
            primary_key=track_id,
            updates=metadata,
        )
```

---

## 8. Testing & Validierung

### 8.1 Unit Tests

```python
# tests/unit/application/cache/test_write_buffer.py

import pytest
import asyncio
from soulspot.application.cache.write_buffer import WriteBufferCache, BufferConfig


@pytest.fixture
def cache():
    return WriteBufferCache(config=BufferConfig(
        flush_interval_seconds=60,  # Disable auto-flush for tests
        max_buffer_size=100,
    ))


class TestWriteBufferCache:
    
    async def test_upsert_is_instant(self, cache):
        """Write sollte sofort zurückkehren."""
        import time
        start = time.time()
        
        await cache.upsert("tracks", "id_1", {"title": "Test"})
        
        elapsed = time.time() - start
        assert elapsed < 0.01  # < 10ms
    
    async def test_read_after_write(self, cache):
        """Read sollte gepufferte Daten zurückgeben."""
        await cache.upsert("tracks", "id_1", {"title": "Test"})
        
        result = await cache.get("tracks", "id_1")
        
        assert result == {"title": "Test"}
    
    async def test_coalescing(self, cache):
        """Mehrfache Writes zur gleichen PK sollten zusammengefasst werden."""
        await cache.upsert("tracks", "id_1", {"title": "V1"})
        await cache.upsert("tracks", "id_1", {"title": "V2"})
        await cache.upsert("tracks", "id_1", {"title": "V3"})
        
        stats = cache.get_stats()
        assert stats["writes_coalesced"] == 2
        assert stats["buffer_size"] == 1
    
    async def test_emergency_flush_on_buffer_full(self, cache):
        """Bei vollem Buffer sollte Emergency-Flush triggern."""
        # Fill buffer beyond max
        for i in range(150):
            await cache.upsert("tracks", f"id_{i}", {"title": f"Track {i}"})
        
        # Buffer sollte geleert sein
        stats = cache.get_stats()
        assert stats["buffer_size"] < 100
    
    async def test_flush_restores_on_error(self, cache):
        """Bei Flush-Error sollten Daten restored werden."""
        await cache.upsert("tracks", "id_1", {"title": "Test"})
        
        # Simuliere Flush-Error
        async def failing_flush_callback(*args):
            raise Exception("DB Error")
        
        cache._flush_callback = failing_flush_callback
        
        with pytest.raises(Exception):
            await cache.flush()
        
        # Daten sollten noch im Buffer sein
        assert cache._buffer_size() == 1
```

### 8.2 Integration Tests

```python
# tests/integration/test_write_buffer_integration.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.cache.write_buffer import WriteBufferCache, BufferConfig
from soulspot.infrastructure.persistence.bulk_operations import bulk_upsert


@pytest.mark.asyncio
async def test_full_write_read_cycle(session: AsyncSession):
    """Test: Write → Flush → Read from DB."""
    
    async def flush_cb(sess, table, op, records):
        return await bulk_upsert(sess, table, records)
    
    cache = WriteBufferCache(
        config=BufferConfig(flush_interval_seconds=60),
        flush_callback=flush_cb,
    )
    
    # Write
    await cache.upsert("tracks", "test_id", {
        "id": "test_id",
        "title": "Test Track",
        "artist_name": "Test Artist",
    })
    
    # Flush
    await cache.flush()
    
    # Read from DB
    result = await session.execute(
        text("SELECT * FROM tracks WHERE id = :id"),
        {"id": "test_id"}
    )
    row = result.fetchone()
    
    assert row is not None
    assert row.title == "Test Track"
```

### 8.3 Live-Test Checkliste

```bash
# 1. Docker starten
make docker-up

# 2. Logs beobachten
docker logs -f soulspot-app

# 3. Spotify Sync triggern
# → Beobachten: UI bleibt responsiv

# 4. Stats endpoint prüfen
curl http://localhost:5000/api/v1/debug/write-buffer/stats

# Erwartete Ausgabe:
# {
#   "writes_buffered": 1234,
#   "writes_coalesced": 567,
#   "flushes_completed": 42,
#   "flush_errors": 0,
#   "cache_hits": 890,
#   "cache_misses": 123,
#   "buffer_size": 0,
#   "read_cache_size": 456,
#   "pending_tables": []
# }

# 5. Buffer manuell flushen
curl -X POST http://localhost:5000/api/v1/debug/write-buffer/flush
```

---

## 9. Metriken & Monitoring

### 9.1 Debug API Endpoints

```python
# src/soulspot/api/routers/debug.py

from fastapi import APIRouter, Depends
from soulspot.application.cache.write_buffer import WriteBufferCache
from soulspot.api.dependencies import get_write_buffer_dep

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/write-buffer/stats")
async def get_buffer_stats(
    write_buffer: WriteBufferCache = Depends(get_write_buffer_dep),
) -> dict:
    """Gibt WriteBuffer Statistiken zurück."""
    return write_buffer.get_stats()


@router.post("/write-buffer/flush")
async def manual_flush(
    write_buffer: WriteBufferCache = Depends(get_write_buffer_dep),
) -> dict:
    """Manueller Flush für Debugging."""
    count = await write_buffer.flush()
    return {"flushed_records": count}


@router.get("/write-buffer/pending")
async def get_pending_writes(
    write_buffer: WriteBufferCache = Depends(get_write_buffer_dep),
) -> dict:
    """Zeigt pending writes pro Tabelle."""
    return {
        "pending_upserts": {
            table: len(records) 
            for table, records in write_buffer._pending_upserts.items()
        },
        "pending_updates": {
            table: len(records)
            for table, records in write_buffer._pending_updates.items()
        },
    }
```

### 9.2 Logging

```python
# In write_buffer.py

import logging

logger = logging.getLogger(__name__)

async def flush(self) -> int:
    """..."""
    
    logger.info(
        f"Flushing {self._buffer_size()} records to DB "
        f"(upserts: {sum(len(v) for v in upserts_to_flush.values())}, "
        f"updates: {sum(len(v) for v in updates_to_flush.values())})"
    )
    
    # ... flush logic ...
    
    logger.info(f"Flush completed: {total_written} records written")
```

### 9.3 Prometheus Metrics (optional)

```python
from prometheus_client import Counter, Gauge, Histogram

# Metrics
WRITES_TOTAL = Counter(
    "write_buffer_writes_total",
    "Total writes to buffer",
    ["table", "operation"],
)

BUFFER_SIZE = Gauge(
    "write_buffer_size",
    "Current buffer size",
)

FLUSH_DURATION = Histogram(
    "write_buffer_flush_duration_seconds",
    "Time spent flushing buffer",
)

FLUSH_ERRORS = Counter(
    "write_buffer_flush_errors_total",
    "Total flush errors",
)
```

---

## 10. Rollout-Plan

### Phase 1: Implementierung (Tag 1-2)

- [ ] `write_buffer.py` erstellen
- [ ] `bulk_operations.py` erstellen
- [ ] Unit Tests schreiben
- [ ] Code Review

### Phase 2: Integration (Tag 3)

- [ ] Lifecycle Hooks einbauen
- [ ] Dependencies registrieren
- [ ] Debug Endpoints hinzufügen
- [ ] Logging einrichten

### Phase 3: Worker Migration (Tag 4)

- [ ] UnifiedLibraryManager anpassen
- [ ] Feature Flag einbauen
- [ ] Lokale Tests

### Phase 4: Testing (Tag 5)

- [ ] Docker Tests
- [ ] Stress Tests (1000+ concurrent writes)
- [ ] Edge Cases (Crash, Concurrent, etc.)
- [ ] UI Responsiveness Tests

### Phase 5: Monitoring (Tag 6)

- [ ] Prometheus Metrics (optional)
- [ ] Alerting (optional)
- [ ] Dashboard (optional)

### Phase 6: Rollout (Tag 7)

- [ ] Feature Flag aktivieren
- [ ] Production Monitoring
- [ ] Documentation finalisieren

---

## 11. FAQ

### Q: Was passiert bei einem Crash?

**A:** Nicht-geflushed Daten gehen verloren (max 5 Sekunden). Das ist der Trade-off für Performance. Für kritische Daten kann man `flush_interval_seconds` reduzieren oder explizit `await cache.flush()` aufrufen.

### Q: Wie groß kann der Buffer werden?

**A:** Max `max_buffer_size` Einträge (default: 10.000). Bei Überschreitung wird Emergency-Flush getriggert. Memory-Impact: ~100MB für 10.000 Einträge (bei ~10KB pro Entity).

### Q: Was wenn der Flush fehlschlägt?

**A:** Daten werden restored und beim nächsten Flush erneut versucht. Error Counter wird erhöht für Monitoring.

### Q: Kann ich Read-after-Write Konsistenz garantieren?

**A:** Ja! Der Read-Path checkt zuerst `pending_upserts`, dann `read_cache`, dann DB. Frisch geschriebene Daten sind sofort lesbar.

### Q: Funktioniert das mit mehreren App-Instanzen?

**A:** Nein! Der Cache ist In-Memory und Instance-lokal. Für Multi-Instance braucht man einen verteilten Cache (Redis, etc.).

### Q: Wie viel schneller ist das wirklich?

**A:** 
- Write Latenz: Von 10-100ms auf 0ms (instant)
- Throughput: Von ~100 rows/sec auf ~5,000 rows/sec
- UI Blockierung: Von 1-30 Sekunden auf 0

---

## Anhang: Sequenzdiagramme

### Write Flow

```
┌────────┐          ┌──────────────┐          ┌────────┐
│ Worker │          │ WriteBuffer  │          │ SQLite │
└───┬────┘          └──────┬───────┘          └───┬────┘
    │                      │                      │
    │ upsert(table, pk, data)                     │
    │─────────────────────►│                      │
    │                      │                      │
    │                      │ store in RAM         │
    │                      │────────┐             │
    │                      │        │             │
    │                      │◄───────┘             │
    │                      │                      │
    │◄─────────────────────│                      │
    │     return (0ms)     │                      │
    │                      │                      │
    │                      │  ... 5s later ...    │
    │                      │                      │
    │                      │ flush()              │
    │                      │─────────────────────►│
    │                      │                      │ BULK INSERT
    │                      │                      │─────┐
    │                      │                      │     │
    │                      │                      │◄────┘
    │                      │◄─────────────────────│
    │                      │     commit           │
    │                      │                      │
```

### Read Flow

```
┌────┐          ┌──────────────┐          ┌────────┐
│ UI │          │ WriteBuffer  │          │ SQLite │
└─┬──┘          └──────┬───────┘          └───┬────┘
  │                    │                      │
  │ get(table, pk)     │                      │
  │───────────────────►│                      │
  │                    │                      │
  │                    │ 1. check pending     │
  │                    │────────┐             │
  │                    │        │ MISS        │
  │                    │◄───────┘             │
  │                    │                      │
  │                    │ 2. check read_cache  │
  │                    │────────┐             │
  │                    │        │ MISS        │
  │                    │◄───────┘             │
  │                    │                      │
  │                    │ 3. query DB          │
  │                    │─────────────────────►│
  │                    │                      │
  │                    │◄─────────────────────│
  │                    │     row data         │
  │                    │                      │
  │                    │ 4. populate cache    │
  │                    │────────┐             │
  │                    │        │             │
  │                    │◄───────┘             │
  │                    │                      │
  │◄───────────────────│                      │
  │    return entity   │                      │
  │                    │                      │
```

---

## 12. Optimierungen & Erweiterungen

> **Dieser Abschnitt enthält zusätzliche Features, die NACH dem MVP implementiert werden sollten.**

### 12.1 Delete-Operations (P1 - PFLICHT)

Die Basis-Implementierung unterstützt nur `upsert()` und `update()`. Delete muss ergänzt werden:

```python
# Ergänzung in WriteBufferCache

def __init__(self, ...):
    ...
    # Layer 1: Write Buffer (ERWEITERT)
    self._pending_upserts: dict[str, dict[Any, dict]] = defaultdict(dict)
    self._pending_updates: dict[str, dict[Any, dict]] = defaultdict(dict)
    self._pending_deletes: dict[str, set[Any]] = defaultdict(set)  # NEU


async def delete(
    self,
    table: str,
    primary_key: Any,
) -> None:
    """
    Puffert eine DELETE-Operation.
    
    WICHTIG: Delete hat Vorrang vor Upsert/Update!
    Wenn ein Entity erst upsertet und dann gelöscht wird,
    wird nur das Delete ausgeführt.
    
    Args:
        table: Tabellenname
        primary_key: Primary Key der Entity
    """
    cache_key = self._make_cache_key(table, primary_key)
    
    async with self._flush_lock:
        # Delete hat Vorrang - entferne pending upserts/updates
        self._pending_upserts[table].pop(primary_key, None)
        self._pending_updates[table].pop(primary_key, None)
        
        # Zum Delete-Set hinzufügen
        self._pending_deletes[table].add(primary_key)
        
        # Aus Read-Cache entfernen
        self._read_cache.delete(cache_key)
        
        self._stats["writes_buffered"] += 1


async def flush(self) -> int:
    """Erweitert um Delete-Handling."""
    async with self._flush_lock:
        upserts_to_flush = dict(self._pending_upserts)
        updates_to_flush = dict(self._pending_updates)
        deletes_to_flush = dict(self._pending_deletes)  # NEU
        
        self._pending_upserts = defaultdict(dict)
        self._pending_updates = defaultdict(dict)
        self._pending_deletes = defaultdict(set)  # NEU
    
    total_written = 0
    
    try:
        async with session_scope_with_retry() as session:
            # 1. Deletes zuerst (wichtig für Konsistenz!)
            for table, pks in deletes_to_flush.items():
                if pks:
                    count = await self._bulk_delete(session, table, pks)
                    total_written += count
            
            # 2. Dann Upserts
            for table, records in upserts_to_flush.items():
                if records:
                    count = await self._bulk_upsert(session, table, records)
                    total_written += count
            
            # 3. Dann Updates
            for table, records in updates_to_flush.items():
                if records:
                    count = await self._bulk_update(session, table, records)
                    total_written += count
            
            await session.commit()
        
        self._stats["flushes_completed"] += 1
        
    except Exception as e:
        # Restore bei Fehler
        async with self._flush_lock:
            for table, records in upserts_to_flush.items():
                self._pending_upserts[table].update(records)
            for table, records in updates_to_flush.items():
                self._pending_updates[table].update(records)
            for table, pks in deletes_to_flush.items():
                self._pending_deletes[table].update(pks)
        
        self._stats["flush_errors"] += 1
        raise
    
    return total_written


async def _bulk_delete(
    self,
    session: Any,
    table: str,
    primary_keys: set[Any],
) -> int:
    """Bulk DELETE mit IN-Klausel."""
    if self._flush_callback:
        return await self._flush_callback(session, table, "delete", primary_keys)
    return len(primary_keys)
```

**bulk_operations.py Ergänzung:**

```python
async def bulk_delete(
    session: AsyncSession,
    table: str,
    primary_keys: set[Any],
) -> int:
    """
    Bulk DELETE mit IN-Klausel.
    
    Generiert:
    ```sql
    DELETE FROM tracks WHERE id IN (:pk_0, :pk_1, :pk_2, ...)
    ```
    """
    if not primary_keys:
        return 0
    
    model = TABLE_MODELS.get(table)
    if not model:
        raise ValueError(f"Unknown table: {table}")
    
    pk_column = model.__table__.primary_key.columns.values()[0].name
    
    # Build DELETE statement
    pk_list = list(primary_keys)
    pk_placeholders = ", ".join(f":pk_{i}" for i in range(len(pk_list)))
    params = {f"pk_{i}": pk for i, pk in enumerate(pk_list)}
    
    sql = f"DELETE FROM {table} WHERE {pk_column} IN ({pk_placeholders})"
    
    await session.execute(text(sql), params)
    return len(pk_list)
```

---

### 12.2 Transaction Chunking (P1)

Bei sehr vielen pending writes kann eine einzelne Transaction zu lange dauern und UI blockieren.

```python
@dataclass
class BufferConfig:
    ...
    batch_size: int = 500  # Max Rows pro Transaction
    max_transaction_time_seconds: float = 2.0  # Max Zeit pro Transaction


async def flush(self) -> int:
    """
    Flusht in Chunks statt alles auf einmal.
    
    Vorteil: Verhindert lange DB-Locks
    """
    async with self._flush_lock:
        upserts_to_flush = dict(self._pending_upserts)
        self._pending_upserts = defaultdict(dict)
    
    total_written = 0
    
    for table, all_records in upserts_to_flush.items():
        # Chunk in batches
        items = list(all_records.items())
        for i in range(0, len(items), self._config.batch_size):
            chunk = dict(items[i:i + self._config.batch_size])
            
            try:
                async with session_scope_with_retry() as session:
                    count = await self._bulk_upsert(session, table, chunk)
                    await session.commit()
                    total_written += count
                    
            except Exception as e:
                # Bei Fehler: Rest zurück in Buffer
                remaining = dict(items[i:])
                async with self._flush_lock:
                    self._pending_upserts[table].update(remaining)
                raise
    
    return total_written
```

---

### 12.3 Table-Prioritäten (P2)

Manche Tabellen brauchen niedrigere Latenz als andere:

```python
@dataclass
class BufferConfig:
    ...
    # Prioritäts-Konfiguration
    high_priority_tables: set[str] = field(
        default_factory=lambda: {"downloads", "download_queue"}
    )
    high_priority_flush_interval: float = 1.0  # 1s statt 5s
    
    # Normal: 5s, High Priority: 1s
    normal_flush_interval: float = 5.0


class WriteBufferCache:
    
    async def _auto_flush_loop(self) -> None:
        """Background Task mit unterschiedlichen Flush-Intervallen."""
        last_full_flush = 0
        last_priority_flush = 0
        
        while self._running:
            now = asyncio.get_event_loop().time()
            
            # High Priority Tables: Flush alle 1s
            if now - last_priority_flush >= self._config.high_priority_flush_interval:
                await self._flush_priority_tables()
                last_priority_flush = now
            
            # Alle Tables: Flush alle 5s
            if now - last_full_flush >= self._config.normal_flush_interval:
                await self.flush()
                last_full_flush = now
            
            await asyncio.sleep(0.1)  # Check alle 100ms
    
    async def _flush_priority_tables(self) -> int:
        """Flusht nur High-Priority Tabellen."""
        total = 0
        
        async with self._flush_lock:
            for table in self._config.high_priority_tables:
                if table in self._pending_upserts and self._pending_upserts[table]:
                    records = self._pending_upserts[table]
                    self._pending_upserts[table] = {}
                    
                    try:
                        async with session_scope_with_retry() as session:
                            total += await self._bulk_upsert(session, table, records)
                            await session.commit()
                    except Exception:
                        # Restore bei Fehler
                        self._pending_upserts[table].update(records)
                        raise
        
        return total
```

---

### 12.4 Backpressure-Mechanismus (P2)

Verhindert Buffer-Overflow bei extremer Last:

```python
class WriteBufferCache:
    
    async def upsert(
        self,
        table: str,
        primary_key: Any,
        data: dict[str, Any],
        block_if_full: bool = True,  # NEU
    ) -> None:
        """
        Mit Backpressure: Blockiert wenn Buffer > 80% voll.
        
        Args:
            block_if_full: Wenn True, wartet auf Flush bei vollem Buffer
        """
        # Backpressure: Bei 80% Füllstand warten
        if block_if_full:
            threshold = self._config.max_buffer_size * 0.8
            while self._buffer_size() > threshold:
                # Trigger Emergency Flush und warte
                await self.flush()
                await asyncio.sleep(0.1)
        
        # Normal upsert...
        async with self._flush_lock:
            ...
```

---

### 12.5 Cache Invalidation nach Migration (P3)

```python
class WriteBufferCache:
    
    async def clear_all_caches(self) -> None:
        """
        Invalidiert alle Caches.
        
        WANN VERWENDEN:
        - Nach Alembic Migration
        - Nach manuellem DB-Edit
        - Bei Cache-Korruption
        
        ACHTUNG: Pending writes werden NICHT gelöscht!
        Rufe erst flush() auf wenn du alles löschen willst.
        """
        self._read_cache.clear()
        self._stats["cache_clears"] = self._stats.get("cache_clears", 0) + 1
    
    async def reset_all(self) -> None:
        """
        Kompletter Reset: Flush + Clear.
        
        DESTRUKTIV: Verwende mit Vorsicht!
        """
        await self.flush()  # Erst alles zur DB schreiben
        await self.clear_all_caches()
        
        # Auch pending löschen (für Notfälle)
        async with self._flush_lock:
            self._pending_upserts.clear()
            self._pending_updates.clear()
            self._pending_deletes.clear()
```

**Integration in Alembic:**

```python
# alembic/env.py

def run_migrations_online():
    ...
    # Nach Migration: Cache invalidieren
    # (Wenn WriteBuffer läuft)
    try:
        from soulspot.infrastructure.lifecycle import get_write_buffer
        buffer = get_write_buffer()
        asyncio.run(buffer.clear_all_caches())
    except Exception:
        pass  # Buffer nicht initialisiert
```

---

### 12.6 Erweiterte Metriken (P3)

```python
@dataclass
class BufferStats:
    """Erweiterte Statistiken für Monitoring."""
    
    # Counters
    writes_buffered: int = 0
    writes_coalesced: int = 0
    flushes_completed: int = 0
    flush_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    deletes_buffered: int = 0
    cache_clears: int = 0
    
    # Gauges
    buffer_size: int = 0
    buffer_high_watermark: int = 0  # Max erreichte Größe
    read_cache_size: int = 0
    
    # Timing (Liste der letzten N Werte)
    flush_durations_ms: list[float] = field(default_factory=list)
    
    # Ratios
    @property
    def coalesce_ratio(self) -> float:
        """Anteil der zusammengefassten Writes."""
        if self.writes_buffered == 0:
            return 0.0
        return self.writes_coalesced / self.writes_buffered
    
    @property
    def cache_hit_ratio(self) -> float:
        """Cache-Trefferquote."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    @property
    def avg_flush_duration_ms(self) -> float:
        """Durchschnittliche Flush-Dauer."""
        if not self.flush_durations_ms:
            return 0.0
        return sum(self.flush_durations_ms) / len(self.flush_durations_ms)


class WriteBufferCache:
    
    async def flush(self) -> int:
        """Mit Timing-Metriken."""
        import time
        start = time.time()
        
        try:
            total = await self._do_flush()
            return total
        finally:
            duration_ms = (time.time() - start) * 1000
            
            # Speichere letzte 100 Flush-Dauern
            self._stats.flush_durations_ms.append(duration_ms)
            if len(self._stats.flush_durations_ms) > 100:
                self._stats.flush_durations_ms.pop(0)
            
            # Update High Watermark
            current_size = self._buffer_size()
            if current_size > self._stats.buffer_high_watermark:
                self._stats.buffer_high_watermark = current_size
```

---

### 12.7 Graceful Degradation (P4)

Bei anhaltenden DB-Problemen nicht crashen, sondern degradieren:

```python
@dataclass
class BufferConfig:
    ...
    # Graceful Degradation
    max_consecutive_errors: int = 5
    degraded_flush_interval: float = 30.0  # Längeres Intervall bei Problemen
    recovery_check_interval: float = 60.0  # Wie oft Recovery prüfen


class WriteBufferCache:
    
    def __init__(self, ...):
        ...
        self._consecutive_errors = 0
        self._degraded_mode = False
    
    async def flush(self) -> int:
        try:
            total = await self._do_flush()
            
            # Bei Erfolg: Error-Counter zurücksetzen
            self._consecutive_errors = 0
            if self._degraded_mode:
                logger.info("WriteBuffer: Recovered from degraded mode")
                self._degraded_mode = False
            
            return total
            
        except Exception as e:
            self._consecutive_errors += 1
            
            if self._consecutive_errors >= self._config.max_consecutive_errors:
                if not self._degraded_mode:
                    self._degraded_mode = True
                    logger.warning(
                        f"WriteBuffer: Entering degraded mode after "
                        f"{self._consecutive_errors} consecutive errors. "
                        f"Flush interval increased to {self._config.degraded_flush_interval}s"
                    )
            
            raise
    
    async def _auto_flush_loop(self) -> None:
        """Mit Degraded-Mode Handling."""
        while self._running:
            # Dynamisches Intervall basierend auf Modus
            interval = (
                self._config.degraded_flush_interval
                if self._degraded_mode
                else self._config.flush_interval_seconds
            )
            
            await asyncio.sleep(interval)
            
            if self._buffer_size() > 0:
                try:
                    await self.flush()
                except Exception:
                    pass  # Weitermachen, nicht crashen
    
    def is_healthy(self) -> bool:
        """Health-Check für Monitoring."""
        return not self._degraded_mode and self._consecutive_errors < 3
```

---

### 12.8 Implementierungs-Prioritäten

| Phase | Feature | Aufwand | Priorität |
|-------|---------|---------|-----------|
| **MVP** | Basis WriteBufferCache | 4h | P0 |
| **MVP** | Delete-Operations | 30min | P1 |
| **V1.1** | Transaction Chunking | 1h | P1 |
| **V1.1** | Table-Prioritäten | 1h | P2 |
| **V1.2** | Backpressure | 30min | P2 |
| **V1.2** | Cache Clear | 15min | P3 |
| **V1.3** | Erweiterte Metriken | 30min | P3 |
| **V2.0** | Graceful Degradation | 1h | P4 |

---

### 12.9 Migrations-Checkliste

Beim Upgrade von MVP auf erweiterte Versionen:

- [ ] **V1.1:** Add `_pending_deletes` to existing WriteBufferCache instances
- [ ] **V1.1:** Update flush_callback signature to handle "delete" operation
- [ ] **V1.1:** Add `batch_size` to BufferConfig if not present
- [ ] **V1.2:** Add `high_priority_tables` to BufferConfig
- [ ] **V1.3:** Replace `_stats` dict with `BufferStats` dataclass
- [ ] **V2.0:** Add degraded mode fields to WriteBufferCache

---

**Ende der Dokumentation**

*Letzte Aktualisierung: 2025-01-XX*
*Version: 1.1 (mit Optimierungen)*
