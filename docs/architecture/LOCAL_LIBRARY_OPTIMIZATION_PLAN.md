# SoulSpot Local Library - Optimization & Restructuring Plan

**Version:** 1.1  
**Created:** December 2025  
**Status:** Proposal  
**Authors:** AI Assistant + Human Review

---

## ⚠️ ARCHITEKTUR-KLARSTELLUNG (WICHTIG!)

### Was "Local Library" in SoulSpot bedeutet

Die **Local Library** kümmert sich ausschließlich um:
1. **Lokale Dateien** - Musik auf dem Dateisystem (via LibraryScannerService)
2. **DB-gecachte Daten** - Bereits importierte Artists/Albums/Tracks
3. **Unvollständige Entitäten** - Entitäten die zwar in DB existieren, aber noch keine Metadaten haben

### Was NICHT zur Local Library gehört

❌ **Direkte API-Kommunikation mit Spotify/Deezer/Tidal**
- Das machen **Plugins** (SpotifyPlugin, DeezerPlugin, etc.)
- LocalLibrary nutzt Plugins **indirekt** über Services

❌ **Streaming/Playback**
- Das ist ein separates Feature

### Architektur-Schichten

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL LIBRARY (Router)                                          │
│  - GET /library/stats → Was haben wir lokal?                    │
│  - GET /library/artists → DB-Queries auf lokale Daten           │
│  - POST /library/import/scan → Filesystem scannen               │
│  - GET /library/incomplete-albums → Was fehlt noch?             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL LIBRARY SERVICES (Application Layer)                      │
│                                                                  │
│  • LibraryScannerService - Dateisystem → DB Import              │
│  • LibraryViewService - ViewModels für UI                       │
│  • LibraryCleanupService - Bulk-Operationen                     │
│  • LibraryHealthService - Status-Checks (NEU!)                  │
│                                                                  │
│  ⚠️ Diese Services kommunizieren NICHT mit Spotify/Deezer!      │
└─────────────────────────────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ Repositories    │  │ Enrichment Svc  │  │ File Discovery Svc  │
│ (DB Layer)      │  │ (App Layer)     │  │ (App Layer)         │
│                 │  │                 │  │                     │
│ ArtistRepo      │  │ Uses PLUGINS    │  │ Filesystem-only     │
│ AlbumRepo       │  │ (nicht Clients!)│  │ Kein DB-Zugriff     │
│ TrackRepo       │  │                 │  │                     │
└─────────────────┘  └─────────────────┘  └─────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐  ┌─────────────────┐
│ SQLite/Postgres │  │ SpotifyPlugin   │ ← Plugins als Adapter
└─────────────────┘  │ DeezerPlugin    │
                     │ MusicBrainzPl.  │
                     └─────────────────┘
                            │
                            ▼
                     [Externe APIs]
```

### Wichtige Trennung: Enrichment ≠ Local Library

| Bereich | LocalLibrary | EnrichmentService |
|---------|--------------|-------------------|
| **Fokus** | Was ist lokal vorhanden? | Externe Metadaten holen |
| **Kommunikation** | Nur DB + Filesystem | Nutzt Plugins |
| **Trigger** | User/Scan/Cron | Nach Library-Scan, manuell |
| **Abhängigkeit** | Keine externen APIs | Braucht Plugins |

---

## Executive Summary

Die Local Library Funktionalität in SoulSpot ist funktional, aber über Zeit organisch gewachsen. Dieser Plan strukturiert die notwendigen Optimierungen in 4 Phasen, inspiriert von Best Practices aus **Beets**, **Lidarr** und moderner Python-Architektur.

---

## 📊 Aktuelle Situation

### Stärken ✅
- Solide Lidarr-Kompatibilität (Folder-Parsing)
- JobQueue für Background-Processing
- SSE-basiertes Real-time Status-Streaming
- Deferred Cleanup für UI-Responsiveness
- Saubere Plugin-Trennung für externes Enrichment

### Schwächen ❌
- **Monolithischer Router** (`library.py` = 1917 Zeilen)
- **Deprecated Code** aktiv (alte `/scan` Endpoints)
- **Performance-Issues** (N+1 Queries, fehlende Pagination)
- **Mixed Concerns** (Enrichment-Code im Library-Router)
- **Fehlende Tests** (nur Live-Testing)

---

## 🎯 Ziele

1. **Maintainability:** Router < 500 Zeilen pro Datei
2. **Performance:** Alle List-Endpoints mit Pagination
3. **Clean Architecture:** LocalLibrary ≠ Enrichment (strikte Trennung)
4. **Observability:** Health-Dashboard für Library-Status
5. **Single Responsibility:** LocalLibrary nur für lokale Daten

---

## 🗓️ 4-Phasen-Plan

### Phase 1: Kritische Fixes (1-2 Tage)

**Priorität: 🔴 SOFORT**

| Task | Datei | Aufwand | Beschreibung |
|------|-------|---------|--------------|
| 1.1 | `library.py:557` | 5 min | Doppelten Exception-Handler entfernen |
| 1.2 | `library.py:906` | 30 min | DEV-Endpoint `/clear-all` hinter Feature-Flag |
| 1.3 | `library.py:224` | 30 min | Pagination für `/duplicates` hinzufügen |

**Implementierung 1.1:**
```python
# VORHER (Bug):
except Exception as e:
    raise HTTPException(...)

except Exception as e:  # ← Nie erreicht!
    raise HTTPException(...)

# NACHHER:
except Exception as e:
    raise HTTPException(...)
# Zweiten Block entfernen
```

**Implementierung 1.2:**
```python
# Nur in DEBUG-Modus erlauben
@router.delete("/clear-all")
async def clear_entire_library(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    if not settings.debug:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in DEBUG mode"
        )
    # ... rest of implementation
```

---

### Phase 2: Router-Modularisierung (3-5 Tage)

**Priorität: 🟡 WICHTIG**

**Zielstruktur:**
```
src/soulspot/api/routers/library/
├── __init__.py              # Router aggregation + export
├── scan.py                  # Import/Scan endpoints (~200 LOC)
├── stats.py                 # Statistics, Health (~100 LOC)
├── duplicates.py            # ✓ Bereits existiert (Datei-Duplikate)
├── batch_operations.py      # Rename, Clear (~200 LOC)
└── models.py                # Shared Pydantic models

# SEPARAT - weil es PLUGINS nutzt (nicht nur lokale Daten):
src/soulspot/api/routers/
├── enrichment.py            # Spotify/MB enrichment (nutzt Plugins!)
└── library/...              # Nur lokale Daten (DB + Filesystem)
```

**⚠️ WICHTIG: Enrichment auslagern!**

Der Enrichment-Code gehört NICHT in den Library-Router, weil er externe Plugins nutzt.
```python
# ❌ FALSCH: Enrichment im Library-Router
@router.post("/library/enrichment/trigger")  # Nutzt SpotifyPlugin!

# ✅ RICHTIG: Enrichment in separatem Router
@router.post("/enrichment/trigger")  # In api/routers/enrichment.py
```

**Migration-Strategie:**
1. Neue Dateien erstellen (ohne Breaking Changes)
2. Endpunkte kopieren + refactoren
3. Enrichment-Endpoints in separaten Router verschieben
4. Alt-Datei auf Imports umstellen
5. Alias für Backward-Compatibility
6. Alt-Datei nach Deprecation-Period löschen

**Beispiel `scan.py` (NUR lokale Operationen!):**
```python
# src/soulspot/api/routers/library/scan.py
"""Library scan and import endpoints - LOCAL ONLY, NO PLUGINS!"""

from fastapi import APIRouter, Depends
from soulspot.api.dependencies import get_job_queue, get_library_scanner_service
from .models import ImportScanResponse, ScanStatusResponse

router = APIRouter(tags=["library-scan"])

@router.post("/import/scan", response_model=ImportScanResponse)
async def start_import_scan(...):
    """Start a library import scan as background job.
    
    Hey future me - this scans FILESYSTEM and imports to DB.
    It does NOT call Spotify/Deezer APIs!
    """
    ...

@router.get("/import/status/{job_id}")
async def get_import_status(...):
    ...

@router.get("/import/status/{job_id}/stream")
async def stream_import_status(...):
    """SSE endpoint for real-time progress."""
    ...
```

**Aggregation in `__init__.py`:**
```python
# src/soulspot/api/routers/library/__init__.py
"""Library management API - LOCAL DATA ONLY!

⚠️ This router handles ONLY:
- Filesystem scanning (LibraryScannerService)
- DB queries on local data (Repositories)
- Statistics and health checks

This router does NOT:
- Call Spotify/Deezer/Tidal APIs (that's EnrichmentRouter)
- Stream music (that's PlaybackRouter)
"""

from fastapi import APIRouter
from .scan import router as scan_router
from .duplicates import router as duplicates_router
from .batch_operations import router as batch_router
from .stats import router as stats_router

router = APIRouter(prefix="/library", tags=["library"])

# Include all sub-routers (LOCAL ONLY!)
router.include_router(scan_router)
router.include_router(duplicates_router)
router.include_router(batch_router)
router.include_router(stats_router)

# NOTE: Enrichment is in api/routers/enrichment.py (uses Plugins!)
```

---

### Phase 3: Performance-Optimierungen (2-3 Tage)

**Priorität: 🟡 WICHTIG**

#### 3.1 N+1 Query Fix in Batch-Rename

```python
# VORHER (N+1):
for track_model in tracks:
    artist = await artist_repo.get_by_id(...)  # Query pro Track!

# NACHHER (Eager Loading):
from sqlalchemy.orm import joinedload

stmt = (
    select(TrackModel)
    .options(
        joinedload(TrackModel.artist),
        joinedload(TrackModel.album)
    )
    .where(TrackModel.file_path.isnot(None))
    .limit(limit)
)
```

#### 3.2 Cache-Optimierung für Scan

```python
# src/soulspot/application/services/library_scanner_service.py

from functools import lru_cache
from cachetools import TTLCache

class LibraryScannerService:
    def __init__(self, ...):
        # Persistent Cache mit TTL (5 Minuten)
        self._artist_cache = TTLCache(maxsize=1000, ttl=300)
        self._album_cache = TTLCache(maxsize=5000, ttl=300)
    
    async def _get_or_create_artist_exact(self, name: str) -> tuple[ArtistId, bool]:
        cache_key = name.lower().strip()
        
        # Cache-Hit?
        if cache_key in self._artist_cache:
            return self._artist_cache[cache_key], False
        
        # DB-Lookup
        artist_id = await self._lookup_artist_db(cache_key)
        
        if artist_id:
            self._artist_cache[cache_key] = artist_id
            return artist_id, False
        
        # Create new
        new_id = await self._create_artist(name)
        self._artist_cache[cache_key] = new_id
        return new_id, True
```

#### 3.3 Batch-Insert für Tracks

```python
# VORHER:
for scanned_track in scanned_album.tracks:
    await self._import_track_from_scan(scanned_track)
    await self._session.commit()  # Commit pro Track!

# NACHHER:
BATCH_SIZE = 100
track_models = []

for scanned_track in scanned_album.tracks:
    model = self._prepare_track_model(scanned_track)
    track_models.append(model)
    
    if len(track_models) >= BATCH_SIZE:
        self._session.add_all(track_models)
        await self._session.commit()
        track_models.clear()

# Remaining
if track_models:
    self._session.add_all(track_models)
    await self._session.commit()
```

---

### Phase 4: Feature-Erweiterungen (1-2 Wochen)

**Priorität: 🟢 NICE-TO-HAVE**

#### 4.1 Library Health Dashboard

**Neuer Endpoint:**
```python
# src/soulspot/api/routers/library/stats.py

@router.get("/health", response_model=LibraryHealthResponse)
async def get_library_health(
    session: AsyncSession = Depends(get_db_session),
) -> LibraryHealthResponse:
    """Get comprehensive library health status.
    
    Returns overall health rating and actionable issues.
    """
    from soulspot.application.services.library_health_service import LibraryHealthService
    
    service = LibraryHealthService(session)
    health = await service.check_health()
    
    return LibraryHealthResponse(
        overall_status=health.overall_status,  # green/yellow/red
        last_scan=health.last_scan_timestamp,
        next_scheduled=health.next_scheduled_scan,
        issues=[
            LibraryIssue(
                type=issue.type,
                severity=issue.severity,
                count=issue.count,
                message=issue.message,
                action_url=issue.action_url,
            )
            for issue in health.issues
        ],
        stats=LibraryStats(
            total_artists=health.total_artists,
            total_albums=health.total_albums,
            total_tracks=health.total_tracks,
            total_size_gb=health.total_size_bytes / (1024**3),
            tracks_with_files=health.tracks_with_files,
            enriched_percentage=health.enriched_percentage,
        ),
    )
```

**Health-Service:**
```python
# src/soulspot/application/services/library_health_service.py

@dataclass
class HealthIssue:
    type: str  # broken_files, missing_artwork, duplicates, etc.
    severity: str  # info, warning, error
    count: int
    message: str
    action_url: str


@dataclass
class LibraryHealth:
    overall_status: str  # green, yellow, red
    issues: list[HealthIssue]
    # ... stats


class LibraryHealthService:
    async def check_health(self) -> LibraryHealth:
        issues = []
        
        # Check broken files
        broken_count = await self._count_broken_files()
        if broken_count > 0:
            issues.append(HealthIssue(
                type="broken_files",
                severity="error" if broken_count > 10 else "warning",
                count=broken_count,
                message=f"{broken_count} audio files are corrupted or unreadable",
                action_url="/library/broken-files",
            ))
        
        # Check missing artwork
        missing_art = await self._count_missing_artwork()
        if missing_art > 0:
            issues.append(HealthIssue(
                type="missing_artwork",
                severity="info",
                count=missing_art,
                message=f"{missing_art} albums without artwork",
                action_url="/library/enrichment/trigger",
            ))
        
        # Check duplicates
        duplicates = await self._count_unresolved_duplicates()
        if duplicates > 0:
            issues.append(HealthIssue(
                type="duplicates",
                severity="warning",
                count=duplicates,
                message=f"{duplicates} potential duplicate files",
                action_url="/library/duplicates",
            ))
        
        # Check unenriched
        unenriched = await self._count_unenriched()
        if unenriched > 0:
            issues.append(HealthIssue(
                type="unenriched",
                severity="info",
                count=unenriched,
                message=f"{unenriched} items without Spotify/MusicBrainz data",
                action_url="/library/enrichment/status",
            ))
        
        # Determine overall status
        has_error = any(i.severity == "error" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)
        
        overall = "red" if has_error else ("yellow" if has_warning else "green")
        
        return LibraryHealth(
            overall_status=overall,
            issues=issues,
            # ... stats
        )
```

#### 4.2 Enrichment-Plugin-System (Beets-Inspired)

Inspiriert von Beets' Plugin-Architektur - modulare Enrichment-Quellen:

```python
# src/soulspot/domain/ports/enrichment.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class EnrichmentResult:
    entity_type: str  # artist, album, track
    entity_id: str
    confidence: float
    source: str
    data: dict  # Enriched metadata


class IEnrichmentSource(ABC):
    """Abstract base for enrichment data sources."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier (e.g., 'spotify', 'musicbrainz', 'discogs')."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Priority order (lower = higher priority)."""
        pass
    
    @abstractmethod
    async def search_artist(self, name: str) -> list[EnrichmentResult]:
        pass
    
    @abstractmethod
    async def search_album(
        self, title: str, artist_name: str
    ) -> list[EnrichmentResult]:
        pass


# src/soulspot/infrastructure/enrichment/spotify_source.py

class SpotifyEnrichmentSource(IEnrichmentSource):
    name = "spotify"
    priority = 1
    
    async def search_artist(self, name: str) -> list[EnrichmentResult]:
        results = await self._plugin.search_artists(name, limit=5)
        return [
            EnrichmentResult(
                entity_type="artist",
                entity_id=r.spotify_id,
                confidence=self._calculate_confidence(name, r.name),
                source="spotify",
                data={
                    "spotify_uri": r.spotify_uri,
                    "image_url": r.image_url,
                    "genres": r.genres,
                    "popularity": r.popularity,
                },
            )
            for r in results
        ]


# src/soulspot/infrastructure/enrichment/musicbrainz_source.py

class MusicBrainzEnrichmentSource(IEnrichmentSource):
    name = "musicbrainz"
    priority = 2
    
    async def search_artist(self, name: str) -> list[EnrichmentResult]:
        # MusicBrainz API call
        ...


# Orchestration Service
class EnrichmentOrchestrator:
    """Coordinates multiple enrichment sources."""
    
    def __init__(self, sources: list[IEnrichmentSource]):
        # Sort by priority
        self._sources = sorted(sources, key=lambda s: s.priority)
    
    async def enrich_artist(self, name: str) -> EnrichmentResult | None:
        """Try each source until confident match found."""
        all_results = []
        
        for source in self._sources:
            try:
                results = await source.search_artist(name)
                all_results.extend(results)
                
                # High confidence? Apply immediately
                best = max(results, key=lambda r: r.confidence, default=None)
                if best and best.confidence >= 0.95:
                    return best
                    
            except Exception as e:
                logger.warning(f"Enrichment source {source.name} failed: {e}")
                continue
        
        # Return best overall match if above threshold
        if all_results:
            best_overall = max(all_results, key=lambda r: r.confidence)
            if best_overall.confidence >= 0.8:
                return best_overall
        
        return None
```

#### 4.3 Deprecated Code Cleanup

**Timeline:**
| Version | Action |
|---------|--------|
| v3.5 | Mark deprecated with warnings |
| v3.6 | Remove from documentation |
| v4.0 | Remove code entirely |

**Deprecated Items:**
- `/library/scan` → `/library/import/scan`
- `/library/scan/{id}` → `/library/import/status/{id}`
- `library_scanner.py` Alias → Direct import
- `_prep_file_sync()` → Removed
- `_import_file()` → Removed

---

## 📈 Erfolgsmetriken

| Metrik | Aktuell | Ziel | Messung |
|--------|---------|------|---------|
| Router LOC | 1917 | < 500 pro Datei | `wc -l` |
| Scan Zeit (10k Tracks) | ~5 min | < 2 min | Benchmark |
| Memory (Scan) | Peak ~500MB | < 200MB | Docker stats |
| Duplicate List (1000) | Kein Limit | 50 per Page | Response size |
| Enrichment Rate | 50/min | 100/min | Logs |

---

## 🔧 Technische Details

### Dependencies (neu benötigt)

```toml
# pyproject.toml
[tool.poetry.dependencies]
cachetools = "^5.3.0"  # TTL-Cache für Artist/Album Lookup
```

### Konfiguration (neu)

```python
# src/soulspot/config/settings.py

class LibrarySettings(BaseModel):
    """Library-specific configuration."""
    
    scan_batch_size: int = 100
    cache_ttl_seconds: int = 300
    max_enrichment_candidates: int = 5
    auto_enrichment_confidence_threshold: float = 0.85
```

---

## 📋 Nächste Schritte

1. **Review:** Team-Feedback zu diesem Plan
2. **Priorisierung:** Welche Phase zuerst?
3. **Tickets:** Issues für jede Task erstellen
4. **Implementierung:** Phase 1 starten

---

## ⚠️ WICHTIG: Architektur-Korrektur (Phase 4)

> **KRITISCHE KLARSTELLUNG:** LocalLibraryService kümmert sich NUR um die lokale Library 
> und alles was in der Datenbank schon lokal verfügbar ist - aber noch ohne externen Inhalt.
> 
> **MERKE:** Wir kommunizieren NIEMALS direkt mit Spotify, Deezer und Co. - das machen unsere Plugins für uns!

### Was LocalLibrary CHECKT (Health Dashboard):
- ✅ Broken files (filesystem check)
- ✅ Missing files (file_path in DB aber Datei existiert nicht)
- ✅ Duplicates (gleicher Hash in DB)
- ✅ Orphaned entities (Albums ohne Tracks, etc.)

### Was LocalLibrary NICHT checkt (gehört zu EnrichmentService):
- ❌ Missing artwork (braucht externe CDNs)
- ❌ Unenriched items (braucht Spotify/MusicBrainz)
- ❌ Album completeness (braucht Spotify API)
- ❌ Enrichment status überhaupt

### Endpoints die VERSCHOBEN werden müssen:
```
❌ FALSCH in library.py:
/library/enrichment/*        → /enrichment/*
/library/artists/{id}/enrich → /enrichment/artists/{id}
/library/albums/{id}/enrich  → /enrichment/albums/{id}

Diese Endpoints nutzen SpotifyPlugin/MusicBrainzPlugin 
und gehören daher in einen separaten enrichment.py Router!
```

### LibraryHealthService - Korrigierte Version:
```python
class LibraryHealthService:
    """LOCAL library health - NO external API calls!
    
    Hey future me - check ONLY:
    - broken_files: DB is_broken=True
    - missing_files: file_path in DB but !exists on disk
    - duplicates: same file_hash in DB  
    - orphaned_entities: albums without tracks
    
    NEVER check: enrichment status, artwork availability!
    """
    
    async def check_health(self) -> LibraryHealth:
        issues = []
        
        # LOCAL checks only!
        if (broken := await self._count_broken_files()) > 0:
            issues.append(HealthIssue("broken_files", "error", broken))
        
        if (missing := await self._count_missing_files()) > 0:
            issues.append(HealthIssue("missing_files", "error", missing))
        
        if (dupes := await self._count_duplicates()) > 0:
            issues.append(HealthIssue("duplicates", "warning", dupes))
        
        if (orphans := await self._count_orphaned()) > 0:
            issues.append(HealthIssue("orphaned_entities", "info", orphans))
        
        return LibraryHealth(issues=issues)
```

---

## Referenzen

- [Beets Architecture](https://beets.readthedocs.io/en/stable/dev/index.html) - Plugin-System Inspiration
- [Lidarr Wiki](https://wiki.servarr.com/lidarr) - Folder-Struktur Standards
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/) - Router Modularisierung
- SoulSpot `docs/architecture/DATA_LAYER_PATTERNS.md` - Interne Standards

---

## 📝 Verifizierung gegen Quellcode (Dez 2025)

**Letzte Prüfung:** Dezember 2025

### Phase 1 Bugs - VERIFIZIERT ✅

| Issue | Zeile | Status | Notizen |
|-------|-------|--------|---------|
| Doppelter Exception-Handler | 568-578 | ✅ Bestätigt | Zweiter `except Exception` unreachable |
| DEV `/clear-all` ohne Guard | 894 | ✅ Bestätigt | Kein DEBUG-Check |
| `/duplicates` ohne Pagination | 227 | ✅ Bestätigt | Kein limit/offset |

### Phase 2 Router-Struktur - ANPASSUNGEN NÖTIG ⚠️

**Entdeckter Konflikt:**
Es gibt ZWEI `/duplicates` Endpoints in `library.py`:

```
Zeile 227:  GET /duplicates → get_duplicates() 
            Datei-Duplikate (gleicher Hash)
            KEINE Pagination ❌

Zeile 981:  GET /duplicates → list_duplicate_candidates()
            Track-Duplikate (DuplicateService)
            HAT Pagination ✅
```

**Problem:** Route-Konflikt! Der erste Endpoint überschreibt den zweiten.

**Lösung:**
```python
# Umbenennen der Endpoints:
GET /duplicates/files      → Datei-Duplikate (Hash-basiert)
GET /duplicates/candidates → Track-Duplikate (Similarity-basiert)
```

**Existierende Extraktion:**
- `library_duplicates.py` existiert bereits (149 LOC)
- Enthält Artist/Album Duplicate-Merge Funktionalität
- Nutzt noch `LocalLibraryEnrichmentService` (soll refactored werden)

### Aktuelle Endpoint-Zählung in library.py

| Typ | Anzahl | Beispiele |
|-----|--------|-----------|
| GET | 15 | /stats, /duplicates, /import/status/... |
| POST | 13 | /scan, /import/scan, /batch-rename... |
| DELETE | 2 | /clear, /clear-all |
| **TOTAL** | **30** | |

**Davon Enrichment-Endpoints (sollten ausgelagert werden):**
- GET /enrichment/status (Zeile 1580)
- POST /enrichment/trigger (Zeile 1633)
- POST /enrichment/repair-artwork (Zeile 1660)
- GET /enrichment/candidates (Zeile 1706)
- POST /enrichment/candidates/{id}/apply (Zeile 1754)
- POST /enrichment/candidates/{id}/reject (Zeile 1795)
- POST /enrich-disambiguation (Zeile 1838)

**= 7 Enrichment-Endpoints → nach `/enrichment/*` Router verschieben!**

### Zusammenfassung

✅ Phase 1 Bugs: Alle bestätigt, können behoben werden
⚠️ Phase 2: Route-Konflikt bei `/duplicates` entdeckt - muss gelöst werden
✅ Phase 3: Performance-Patterns sind korrekt
✅ Phase 4: LibraryHealthService Konzept ist korrekt (nur lokale Checks)
