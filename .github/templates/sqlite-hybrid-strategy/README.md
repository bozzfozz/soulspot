# SQLite Hybrid Strategy Template

> **Wiederverwendbare SQLite-Concurrency-Lösung für Python-Projekte**

## Problem

SQLite hat ein **Single-Writer-Limit**. Bei Multi-Worker/Async-Projekten führt das zu:
- "database is locked" Errors
- UI-Freezes während Background-Jobs schreiben
- Retry-Loops die die CPU belasten

## Lösung: Hybrid-Strategie

Diese Template kombiniert drei bewährte Ansätze für SQLite-Concurrency:

| Komponente | Use Case | Write-Latenz |
|------------|----------|--------------|
| **RetryStrategy** | API/User-Actions | ~100-500ms (real) |
| **WriteBufferCache** | Background Workers | ~0ms (RAM → Batch) |
| **LogDatabase** | Application Logging | ~0ms (separate DB) |

## Dateien

```
sqlite-hybrid-strategy/
├── README.md                  # Diese Datei
├── pyproject.toml            # Für standalone Package
└── src/
    └── sqlite_hybrid/
        ├── __init__.py
        ├── retry.py           # RetryStrategy mit Exponential Backoff
        ├── write_buffer.py    # WriteBufferCache für Batch-Writes
        └── log_database.py    # Separate Log-DB
```

## Quick Start

### 1. Dateien kopieren

Kopiere den `src/sqlite_hybrid/` Ordner in dein Projekt:

```
your_project/
├── infrastructure/
│   └── persistence/
│       ├── retry.py
│       ├── write_buffer.py
│       └── log_database.py
```

### 2. SQLite konfigurieren

```python
# In deinem Database-Setup (SQLAlchemy)
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=500")      # ← Kurz! RetryStrategy handelt
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")     # 64MB
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=268435456")   # 256MB
    cursor.close()
```

### 3. Bei App-Start initialisieren

```python
from your_project.infrastructure.persistence.write_buffer import (
    WriteBufferCache, BufferConfig
)
from your_project.infrastructure.persistence.log_database import LogDatabase

# WriteBufferCache für Background Workers
write_buffer = WriteBufferCache(
    session_factory=db.get_session_factory(),
    config=BufferConfig(
        max_buffer_size=1000,      # Max pending writes
        flush_interval_seconds=5.0, # Flush alle 5s
        flush_batch_size=100,       # Max pro Batch
        table_priorities={          # High-Write Tables zuerst
            "downloads": 1,
            "tracks": 2,
        },
    ),
)
await write_buffer.start()

# LogDatabase für non-blocking Logging
log_database = LogDatabase(
    db_path="/path/to/logs.db",  # Separate DB!
    retention_days=7,
)
await log_database.start()
```

### 4. Bei App-Shutdown

```python
# WICHTIG: VOR dem Schließen der Main-DB!
await write_buffer.stop()   # Flusht remaining writes
await log_database.stop()   # Flusht pending logs

# Dann Main-DB schließen
await db.close()
```

## Verwendung

### API/User-Actions: RetryStrategy

```python
from your_project.infrastructure.persistence.retry import with_db_retry

@with_db_retry(max_retries=3, base_delay=0.1)
async def save_user_data(session, data):
    user = User(**data)
    session.add(user)
    await session.commit()
    return user
```

### Background Workers: WriteBufferCache

```python
# Statt direktem DB-Write:
# session.add(download)
# await session.commit()

# Buffer benutzen:
await write_buffer.buffer_upsert(
    table="downloads",
    data={"id": download_id, "status": "complete", "progress": 100},
    key_columns=["id"],
)
# → Wird automatisch in Batches geflusht
```

### Logging: LogDatabase

```python
import logging
from your_project.infrastructure.persistence.log_database import DatabaseLogHandler

# Handler zum Logger hinzufügen
handler = DatabaseLogHandler(log_database)
logging.getLogger().addHandler(handler)

# Logs gehen jetzt in logs.db statt auf Main-DB zu schreiben
logger.info("Download complete", extra={"track_id": 123})
```

## Konfiguration

### WriteBufferCache Config

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `max_buffer_size` | 1000 | Backpressure wenn überschritten |
| `flush_interval_seconds` | 5.0 | Periodischer Flush |
| `flush_batch_size` | 100 | Max Writes pro Batch |
| `table_priorities` | {} | Niedrigere Zahl = höhere Priorität |

### LogDatabase Config

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `db_path` | None | Pfad zur Log-DB (None = in-memory) |
| `retention_days` | 7 | Auto-Cleanup älterer Logs |
| `max_batch_size` | 50 | Logs pro Batch-Write |
| `flush_interval_seconds` | 2.0 | Flush-Intervall |

### RetryStrategy Config

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `max_retries` | 3 | Maximale Versuche |
| `base_delay` | 0.1 | Basis-Delay (verdoppelt sich) |
| `max_delay` | 2.0 | Maximum Delay |
| `jitter` | True | Zufälliger Offset (verhindert Thundering Herd) |

## Monitoring

### Metriken abrufen

```python
# WriteBufferCache Stats
stats = write_buffer.get_stats()
# {"pending_count": 5, "total_flushed": 1234, "flush_count": 50, ...}

# LogDatabase Stats
stats = await log_database.get_log_stats()
# {"total_logged": 5678, "pending_count": 10, ...}

# RetryStrategy Metrics
from your_project.infrastructure.persistence.retry import DatabaseLockMetrics
metrics = DatabaseLockMetrics.get_metrics()
# {"total_lock_errors": 12, "total_retries": 36, ...}
```

### Debug API (Optional)

Du kannst FastAPI-Endpoints für Monitoring erstellen:

```python
# routes/debug.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/debug/db")

@router.get("/stats")
async def get_db_stats(request: Request):
    buffer = request.app.state.write_buffer
    log_db = request.app.state.log_database
    
    return {
        "write_buffer": buffer.get_stats(),
        "log_database": await log_db.get_log_stats(),
        "retry_metrics": DatabaseLockMetrics.get_metrics(),
    }

@router.post("/buffer/flush")
async def force_flush(request: Request):
    flushed = await request.app.state.write_buffer.force_flush()
    return {"flushed_count": flushed}
```

## Wann diese Strategie nutzen?

| Szenario | Empfehlung |
|----------|------------|
| SQLite + Multi-Worker (Async) | ✅ **Ja!** |
| SQLite + Single-Thread | ⚠️ RetryStrategy reicht |
| PostgreSQL/MySQL | ❌ Nicht nötig |
| Read-heavy, wenig Writes | ⚠️ WAL + Retry reicht |
| Write-heavy Background Jobs | ✅ **WriteBufferCache!** |

## Referenz

- **SQLite WAL Mode:** [sqlite.org/wal.html](https://www.sqlite.org/wal.html)
- **SQLite Locking:** [sqlite.org/lockingv3.html](https://www.sqlite.org/lockingv3.html)
- **SQLAlchemy Async:** [docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

## Lizenz

MIT - Frei verwendbar in eigenen Projekten.
