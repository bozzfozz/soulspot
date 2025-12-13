# Backend Optimierung - Analyse & Vorschläge

> **Erstellt:** 2025-01-13
> **Status:** Analyse Complete
> **Priorität:** Nach Abschluss Download Manager Features

---

## Übersicht

Diese Analyse identifiziert Optimierungspotential im SoulSpot Backend basierend auf:
- Code-Analyse der Architektur
- Performance-Patterns und Anti-Patterns
- Best Practices für async Python / FastAPI

---

## 🔴 Hohe Priorität

### 1. HTTP Client Connection Pooling ❌ INEFFIZIENT

**Problem:**  
Jeder Request erstellt neue `httpx.AsyncClient` Instanz:
```python
# artwork_service.py, lyrics_service.py, onboarding.py
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

**Konsequenz:**  
- TCP Connection Overhead bei jedem Request
- Keine Keep-Alive Nutzung
- Langsamer bei vielen aufeinanderfolgenden Calls

**Lösung:**  
Shared Client Pool als Singleton:
```python
# infrastructure/integrations/http_pool.py
from contextlib import asynccontextmanager

class HttpClientPool:
    _client: httpx.AsyncClient | None = None
    
    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            cls._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return cls._client
    
    @classmethod
    async def close(cls) -> None:
        if cls._client:
            await cls._client.aclose()
            cls._client = None

# In Services:
client = await HttpClientPool.get_client()
response = await client.get(url)
```

**Betroffene Files:**
- `application/services/postprocessing/artwork_service.py` (4 Stellen)
- `application/services/postprocessing/lyrics_service.py` (3 Stellen)
- `application/services/spotify_image_service.py` (2 Stellen)
- `api/routers/onboarding.py` (1 Stelle)

**Aufwand:** 2-3h | **Impact:** Hoch

---

### 2. N+1 Query Pattern in Playlists ⚠️ TEILWEISE BEHOBEN

**Problem:**  
Kommentare zeigen erkannte N+1 Probleme:
```python
# playlists.py:455 - "SUPER inefficient. Should be a single JOIN query"
# playlists.py:692 - "Same N+1 query antipattern"
```

**Status:**  
- `joinedload()` wird verwendet ✅
- Aber nicht überall konsistent

**Lösung:**  
Repository-Layer mit Standard-Queries:
```python
# repositories.py
class TrackRepository:
    async def get_with_relations(self, track_id: int) -> Track | None:
        """Get track with artist and album eagerly loaded."""
        stmt = (
            select(TrackModel)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            .where(TrackModel.id == track_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_many_with_relations(self, track_ids: list[int]) -> list[Track]:
        """Batch load tracks with relations - avoids N+1."""
        stmt = (
            select(TrackModel)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
            .where(TrackModel.id.in_(track_ids))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

**Aufwand:** 4-6h (Repository + Router Refactoring) | **Impact:** Hoch bei großen Playlists

---

### 3. Missing Background Tasks ❌ NICHT IMPLEMENTIERT

**Problem:**  
Langwierige Operationen blockieren HTTP Responses:
```python
# settings.py:849 - "auf Background Tasks umstellen (FastAPI BackgroundTasks oder Celery)"
```

**Lösung:**  
FastAPI BackgroundTasks für non-blocking Operations:
```python
from fastapi import BackgroundTasks

@router.post("/library/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_library_scan)
    return {"status": "scan_queued"}

async def run_full_library_scan():
    async with db.session_scope() as session:
        await scanner.scan_directory("/music")
```

**Use Cases:**
- Library Scan (kann Minuten dauern)
- Metadata Enrichment (viele API calls)
- Bulk Downloads
- Album Art Sync

**Aufwand:** 2-3h pro Endpoint | **Impact:** Hoch für UX

---

## 🟡 Mittlere Priorität

### 4. Caching Layer vorhanden, aber nicht konsistent genutzt

**Status:**  
- LRUCache Implementation existiert ✅ (`application/cache/enhanced_cache.py`)
- SpotifyCache, MusicBrainzCache, TrackFileCache ✅
- Aber: Viele Services umgehen den Cache

**Problem:**  
```python
# Direct API call without cache check
album = await self.spotify_plugin.get_album(album_id)
```

**Lösung:**  
Cache-First Pattern enforced:
```python
class SpotifyService:
    def __init__(self, cache: SpotifyCache, plugin: SpotifyPlugin):
        self.cache = cache
        self.plugin = plugin
    
    async def get_album(self, album_id: str) -> AlbumDTO:
        # 1. Check cache
        cached = await self.cache.get(f"album:{album_id}")
        if cached:
            return cached
        
        # 2. API call
        album = await self.plugin.get_album(album_id)
        
        # 3. Cache result
        await self.cache.set(f"album:{album_id}", album, ttl=3600)
        return album
```

**Aufwand:** 4-6h | **Impact:** Mittel (reduziert API calls um ~70%)

---

### 5. Dependency Injection Overhead

**Problem:**  
Jeder Request erstellt neue Service-Instanzen:
```python
async def get_spotify_plugin(...) -> SpotifyPlugin:
    # Creates NEW plugin instance EVERY request
    ...
```

**Lösung:**  
Request-scoped Caching mit `request.state`:
```python
async def get_spotify_plugin(request: Request, ...) -> SpotifyPlugin:
    # Reuse within same request
    if hasattr(request.state, 'spotify_plugin'):
        return request.state.spotify_plugin
    
    plugin = SpotifyPlugin(...)
    request.state.spotify_plugin = plugin
    return plugin
```

**Oder:** Singleton Plugins in `app.state` (für stateless plugins)

**Aufwand:** 2h | **Impact:** Mittel (reduziert Object Creation)

---

### 6. Missing Index-Hints für häufige Queries

**Problem:**  
Queries ohne explizite Index-Nutzung:
```python
# Häufiger Query ohne Index-Hint
await session.execute(
    select(TrackModel).where(TrackModel.spotify_uri == uri)
)
```

**Lösung:**  
1. Prüfe vorhandene Indexes in Migrationen ✅ (cc17880fff37_add_performance_indexes.py existiert)
2. Füge fehlende hinzu:

```python
# Neue Migration: add_query_performance_indexes.py
def upgrade():
    # Häufige Lookup-Queries
    op.create_index('ix_tracks_isrc', 'tracks', ['isrc'])
    op.create_index('ix_tracks_artist_id_album_id', 'tracks', ['artist_id', 'album_id'])
    op.create_index('ix_downloads_status_priority', 'downloads', ['status', 'priority'])
    
    # Full-text search (wenn SQLite FTS aktiviert)
    op.execute("CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(title, artist_name)")
```

**Aufwand:** 1-2h | **Impact:** Hoch für große Libraries (10k+ Tracks)

---

### 7. Worker Health Monitoring erweitern

**Status:**  
- Circuit Breaker für DownloadStatusSyncWorker ✅
- Aber: Andere Worker haben kein Health Monitoring

**Lösung:**  
Unified Worker Health System:
```python
class WorkerHealthRegistry:
    workers: dict[str, WorkerHealth] = {}
    
    @classmethod
    def register(cls, name: str, worker: BaseWorker):
        cls.workers[name] = WorkerHealth(
            name=name,
            worker=worker,
            last_run=None,
            error_count=0,
        )
    
    @classmethod
    async def get_all_health(cls) -> dict[str, WorkerHealthStatus]:
        return {
            name: await health.get_status()
            for name, health in cls.workers.items()
        }

# API Endpoint
@router.get("/health/workers")
async def get_worker_health():
    return await WorkerHealthRegistry.get_all_health()
```

**Aufwand:** 4h | **Impact:** Mittel (besseres Monitoring)

---

## 🟢 Niedrige Priorität (Nice-to-Have)

### 8. Async Batch Processing parallelisieren

**Problem:**  
Kommentare zeigen geplante Parallelisierung:
```python
# enhanced_cache.py:316 - "Consider adding parallelization (asyncio.gather)"
# discography_service.py:214 - "Consider adding batch parallelization"
```

**Lösung:**  
```python
async def enrich_tracks_parallel(tracks: list[Track]) -> list[Track]:
    # Parallel enrichment mit Rate Limiting
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent
    
    async def enrich_one(track: Track) -> Track:
        async with semaphore:
            return await enrich_track(track)
    
    return await asyncio.gather(*[enrich_one(t) for t in tracks])
```

**Aufwand:** 2-3h pro Service | **Impact:** Mittel

---

### 9. Response Compression bereits vorhanden ✅

```python
# main.py
app.add_middleware(GZipMiddleware, minimum_size=settings.api.gzip_minimum_size)
```

**Status:** Bereits implementiert! ✅

---

### 10. Connection Pool Tuning

**Status:**  
Pool Settings bereits konfigurierbar:
```python
# settings.py
pool_size: int = 5
max_overflow: int = 10
pool_recycle: int = 3600
```

**Empfehlung:**  
Für Production mit vielen gleichzeitigen Workers:
```yaml
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_RECYCLE=1800  # 30min statt 1h
```

---

## 📊 Zusammenfassung

| # | Optimierung | Aufwand | Impact | Priorität |
|---|------------|---------|--------|-----------|
| 1 | HTTP Client Pooling | 2-3h | Hoch | 🔴 |
| 2 | N+1 Query Fixes | 4-6h | Hoch | 🔴 |
| 3 | Background Tasks | 6-8h | Hoch | 🔴 |
| 4 | Caching Konsistenz | 4-6h | Mittel | 🟡 |
| 5 | DI Overhead | 2h | Mittel | 🟡 |
| 6 | DB Indexes | 1-2h | Hoch | 🟡 |
| 7 | Worker Health | 4h | Mittel | 🟡 |
| 8 | Parallel Batch | 4-6h | Mittel | 🟢 |
| 9 | GZip | ✅ Done | - | - |
| 10 | Pool Tuning | Config | Mittel | 🟢 |

---

## 🎯 Empfohlene Reihenfolge

### Sprint 1 (Core Performance)
1. **HTTP Client Pooling** - Quick win, großer Impact
2. **DB Indexes prüfen** - Schnell umgesetzt
3. **Background Tasks für Library Scan** - Bessere UX

### Sprint 2 (Consistency)
4. **N+1 Fixes** - Repository Layer Refactoring
5. **Caching Konsistenz** - Service Layer Anpassung

### Sprint 3 (Monitoring)
6. **Worker Health System** - Unified Monitoring
7. **Parallel Batch Processing** - Where it matters

---

## 📚 Verwandte Dokumente

- [Architecture Overview](architecture/README.md)
- [Download Manager Features](features/DOWNLOAD_MANAGER_FEATURES.md)
- [TODO](TODO.md)
