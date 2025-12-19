# Enrichment Service Extraction Plan

> **ZIEL:** Enrichment-Funktionalität aus LocalLibrary auslagern in eigenständige,
> plugin-artige Architektur - ähnlich wie bei ImageService.

## 📊 Status Quo

### Aktuelle Architektur (PROBLEMATISCH)

```
api/routers/library.py (1917 LOC!)
     │
     ├── /enrichment/status         ← EnrichmentService
     ├── /enrichment/trigger        ← JobQueue
     ├── /enrichment/repair-artwork ← LocalLibraryEnrichmentService
     ├── /enrichment/candidates     ← EnrichmentService
     ├── /enrichment/candidates/{id}/apply  ← EnrichmentService
     ├── /enrichment/candidates/{id}/reject ← EnrichmentCandidateRepository
     └── /enrich-disambiguation     ← LocalLibraryEnrichmentService (MusicBrainz)
```

**Probleme:**
1. ❌ Enrichment-Endpoints in `library.py` Router (gehören nicht zu LocalLibrary!)
2. ❌ `LocalLibraryEnrichmentService` ruft direkt Spotify/MusicBrainz auf
3. ❌ Keine klare Trennung: LocalLibrary = DB+Filesystem, Enrichment = Externe APIs
4. ❌ `LocalLibraryEnrichmentService` ist 2969 Zeilen - viel zu groß!

### Referenz: ImageService Architektur (GUT!)

```
domain/ports/image_service.py     ← Interface (IImageService)
     │
application/services/images/
     ├── image_service.py         ← Implementation (1434 LOC)
     └── __init__.py              ← Re-export
     │
     └── (Nutzt Plugins für URLs, lädt selbst herunter)
         - SpotifyPlugin.get_artist_image_url()
         - DeezerPlugin.get_album_image()
         - Keine direkte HTTP-Calls!
```

**Was ImageService richtig macht:**
- ✅ Port (Interface) in `domain/ports/`
- ✅ Implementation in `application/services/images/`
- ✅ Nutzt Plugins für externe Daten
- ✅ Kümmert sich nur um EINE Sache (Bilder)
- ✅ Stateless, keine DB-Modelle im Service

---

## 🎯 Ziel-Architektur

### Neue Struktur

```
domain/ports/
     └── enrichment_service.py        ← NEU: Interface (IEnrichmentService)

application/services/enrichment/
     ├── __init__.py                  ← Re-export
     ├── enrichment_service.py        ← NEU: Orchestrierung (< 500 LOC)
     ├── candidate_service.py         ← NEU: Candidate-Management
     └── strategies/                  ← NEU: Provider-spezifische Strategien
         ├── __init__.py
         ├── base.py                  ← EnrichmentStrategy ABC
         ├── spotify_enrichment.py    ← Spotify-Matching
         ├── musicbrainz_enrichment.py ← MusicBrainz-Matching
         └── deezer_enrichment.py     ← Deezer-Matching (Zukunft)

api/routers/
     └── enrichment.py                ← NEU: Separater Router

infrastructure/plugins/
     └── (existiert bereits)
         - SpotifyPlugin              ← Erweitern: search_artist(), get_artist_details()
         - MusicBrainzPlugin          ← Erweitern: search_artist(), get_disambiguation()
         - DeezerPlugin               ← Erweitern: search_artist()
```

### Datenfluss (NEU)

```
User UI
   │
   ▼
api/routers/enrichment.py
   │
   ▼
EnrichmentService (Orchestrierung)
   │
   ├── CandidateService (DB: EnrichmentCandidate CRUD)
   │
   └── EnrichmentStrategy (Provider-spezifisch)
         │
         └── SpotifyPlugin / MusicBrainzPlugin / DeezerPlugin
               │
               └── Externe APIs (Spotify, MB, Deezer)
```

---

## 📋 Migrations-Phasen

### Phase 1: Port + Neue Struktur (1-2 Tage)

#### 1.1 Port erstellen
```python
# src/soulspot/domain/ports/enrichment_service.py
"""Enrichment Service Port (Interface).

Future me note:
This defines the CONTRACT for enrichment operations in SoulSpot.
The actual implementation is in application/services/enrichment/

Why is this here (in domain/ports)?
- Clean Architecture: Domain defines interfaces, Infrastructure implements
- Dependency Inversion: Services depend on this interface, not concrete implementation
- Testing: Easy to mock for unit tests
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol


EntityType = Literal["artist", "album", "track"]


class EnrichmentSource(Enum):
    """Available enrichment providers."""
    SPOTIFY = "spotify"
    MUSICBRAINZ = "musicbrainz"
    DEEZER = "deezer"


@dataclass(frozen=True)
class EnrichmentMatch:
    """A potential match from an enrichment provider.
    
    Future me note:
    This is immutable (frozen) - it's a snapshot at search time.
    If you need to modify, create a new one.
    """
    source: EnrichmentSource
    external_id: str           # Spotify URI, MusicBrainz MBID, Deezer ID
    name: str                  # Name from provider
    confidence: float          # 0.0 - 1.0
    image_url: str | None
    extra_info: dict           # followers, genres, disambiguation, etc.


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""
    success: bool
    entity_type: EntityType
    entity_id: str
    
    # Match info (if success)
    applied_match: EnrichmentMatch | None = None
    
    # Candidates (if ambiguous)
    candidates_created: int = 0
    
    # Error (if failed)
    error: str | None = None
    
    @classmethod
    def failure(cls, entity_type: EntityType, entity_id: str, error: str) -> "EnrichmentResult":
        return cls(success=False, entity_type=entity_type, entity_id=entity_id, error=error)


class IEnrichmentService(Protocol):
    """Enrichment Service Port (Interface).
    
    Future me note:
    All EnrichmentService implementations must follow this protocol.
    This enables:
    - Dependency injection
    - Easy mocking for tests
    - Alternative implementations
    
    NOTE: This service ORCHESTRATES enrichment.
    Actual provider communication is via Plugins (SpotifyPlugin, MusicBrainzPlugin).
    """
    
    async def enrich_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        sources: list[EnrichmentSource] | None = None,
    ) -> EnrichmentResult:
        """Enrich a single entity from configured sources.
        
        Args:
            entity_type: "artist", "album", or "track"
            entity_id: Internal entity ID
            sources: Which providers to try (default: all enabled)
            
        Returns:
            EnrichmentResult with match or candidates
        """
        ...
    
    async def enrich_batch(
        self,
        entity_type: EntityType,
        limit: int = 50,
        sources: list[EnrichmentSource] | None = None,
    ) -> dict[str, int]:
        """Enrich multiple entities in batch.
        
        Args:
            entity_type: "artist" or "album"
            limit: Max entities to process
            sources: Which providers to try
            
        Returns:
            Stats dict: {"enriched": 5, "candidates_created": 3, "skipped": 2}
        """
        ...
    
    async def get_enrichment_status(self) -> "EnrichmentStatusDTO":
        """Get counts of unenriched entities and pending candidates."""
        ...
```

#### 1.2 Strategy Pattern für Provider
```python
# src/soulspot/application/services/enrichment/strategies/base.py
"""Base enrichment strategy.

Future me note:
Each provider (Spotify, MusicBrainz, Deezer) implements this interface.
The EnrichmentService uses strategies without knowing provider details.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from soulspot.domain.ports.enrichment_service import EnrichmentMatch, EntityType


@dataclass
class SearchContext:
    """Context for enrichment search."""
    entity_type: EntityType
    entity_id: str
    entity_name: str
    
    # Optional hints for better matching
    artist_name: str | None = None    # For albums: parent artist
    album_name: str | None = None     # For tracks: parent album
    year: int | None = None
    isrc: str | None = None           # For tracks


class EnrichmentStrategy(ABC):
    """Abstract base class for enrichment strategies.
    
    Future me note:
    Each strategy wraps a Plugin and adds matching logic.
    The strategy does NOT make HTTP calls - it uses the Plugin.
    """
    
    @property
    @abstractmethod
    def source(self) -> str:
        """Return source identifier (e.g., 'spotify', 'musicbrainz')."""
        ...
    
    @abstractmethod
    async def search(self, context: SearchContext) -> list[EnrichmentMatch]:
        """Search provider for matches.
        
        Args:
            context: Search context with entity info
            
        Returns:
            List of potential matches, sorted by confidence
        """
        ...
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this strategy can be used (provider enabled + auth)."""
        ...
```

#### 1.3 Spotify Strategy
```python
# src/soulspot/application/services/enrichment/strategies/spotify_enrichment.py
"""Spotify enrichment strategy.

Future me note:
This wraps SpotifyPlugin and adds fuzzy matching logic.
Does NOT make direct HTTP calls - uses plugin.search_artists() etc.
"""

from rapidfuzz import fuzz

from soulspot.domain.ports.enrichment_service import EnrichmentMatch, EnrichmentSource
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
from .base import EnrichmentStrategy, SearchContext


class SpotifyEnrichmentStrategy(EnrichmentStrategy):
    """Enrichment via Spotify API.
    
    Future me note:
    - Uses SpotifyPlugin for API calls
    - Adds fuzzy name matching with rapidfuzz
    - Handles DJ/The/MC prefix normalization
    """
    
    def __init__(self, plugin: SpotifyPlugin, settings_service):
        self._plugin = plugin
        self._settings = settings_service
        
    @property
    def source(self) -> str:
        return "spotify"
    
    async def is_available(self) -> bool:
        """Check if Spotify is enabled and authenticated."""
        from soulspot.domain.ports.plugin import PluginCapability
        
        if not await self._settings.is_provider_enabled("spotify"):
            return False
        return self._plugin.can_use(PluginCapability.SEARCH_ARTISTS)
    
    async def search(self, context: SearchContext) -> list[EnrichmentMatch]:
        """Search Spotify for matching entities."""
        matches = []
        
        if context.entity_type == "artist":
            results = await self._plugin.search_artists(context.entity_name, limit=10)
            
            for r in results:
                confidence = self._calculate_artist_confidence(
                    context.entity_name, r.name, r.followers
                )
                matches.append(EnrichmentMatch(
                    source=EnrichmentSource.SPOTIFY,
                    external_id=r.spotify_uri,
                    name=r.name,
                    confidence=confidence,
                    image_url=r.image_url,
                    extra_info={"followers": r.followers, "genres": r.genres},
                ))
        
        elif context.entity_type == "album":
            query = f"{context.artist_name} {context.entity_name}"
            results = await self._plugin.search_albums(query, limit=10)
            
            for r in results:
                confidence = self._calculate_album_confidence(
                    context.entity_name, r.name, context.artist_name, r.artist_name
                )
                matches.append(EnrichmentMatch(
                    source=EnrichmentSource.SPOTIFY,
                    external_id=r.spotify_uri,
                    name=r.name,
                    confidence=confidence,
                    image_url=r.image_url,
                    extra_info={"artist": r.artist_name, "release_date": r.release_date},
                ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)
    
    def _calculate_artist_confidence(
        self, local_name: str, spotify_name: str, followers: int
    ) -> float:
        """Calculate match confidence for artist.
        
        Future me note:
        Uses fuzzy matching + popularity boost. Normalized names help
        match "DJ Paul Elstak" to "Paul Elstak".
        """
        from soulspot.application.services.local_library_enrichment_service import (
            normalize_artist_name
        )
        
        # Fuzzy match on normalized names
        norm_local = normalize_artist_name(local_name)
        norm_spotify = normalize_artist_name(spotify_name)
        
        base_score = fuzz.ratio(norm_local, norm_spotify) / 100.0
        
        # Popularity boost (verified artists are more likely correct)
        pop_boost = min(0.1, (followers or 0) / 1_000_000 * 0.1)
        
        return min(1.0, base_score + pop_boost)
```

### Phase 2: Router Extraktion (1 Tag)

#### 2.1 Neuen Router erstellen
```python
# src/soulspot/api/routers/enrichment.py
"""Enrichment API Router.

Future me note:
This router handles ALL enrichment operations. Moved OUT of library.py
because enrichment uses external APIs (Spotify, MusicBrainz, Deezer)
which is NOT what LocalLibrary does.

LocalLibrary = DB + Filesystem ONLY
Enrichment = External API communication
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_job_queue
from soulspot.application.workers.job_queue import JobQueue, JobType, JobStatus

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# === ENDPOINTS (moved from library.py) ===

@router.get("/status")
async def get_enrichment_status(
    session: AsyncSession = Depends(get_db_session),
    job_queue: JobQueue = Depends(get_job_queue),
):
    """Get enrichment status with unenriched counts."""
    from soulspot.application.services.enrichment import EnrichmentService
    
    service = EnrichmentService(session)
    status = await service.get_enrichment_status()
    
    # Add job queue status
    is_running = False
    enrichment_jobs = await job_queue.list_jobs(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT, limit=1
    )
    if enrichment_jobs and enrichment_jobs[0].status in (JobStatus.PENDING, JobStatus.RUNNING):
        is_running = True
    
    return {**status.to_dict(), "is_running": is_running}


@router.post("/trigger")
async def trigger_enrichment(job_queue: JobQueue = Depends(get_job_queue)):
    """Manually trigger enrichment job."""
    job_id = await job_queue.enqueue(
        job_type=JobType.LIBRARY_SPOTIFY_ENRICHMENT,
        payload={"triggered_by": "manual_api"},
    )
    return {"job_id": job_id, "message": "Enrichment job queued"}


@router.get("/candidates")
async def get_candidates(
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    """Get pending enrichment candidates for review."""
    from soulspot.application.services.enrichment import CandidateService
    
    service = CandidateService(session)
    candidates, total = await service.list_pending(entity_type, limit, offset)
    return {"candidates": candidates, "total": total}


@router.post("/candidates/{candidate_id}/apply")
async def apply_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Apply a user-selected enrichment candidate."""
    from soulspot.application.services.enrichment import CandidateService
    
    service = CandidateService(session)
    result = await service.apply(candidate_id)
    return result


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Reject an enrichment candidate."""
    from soulspot.application.services.enrichment import CandidateService
    
    service = CandidateService(session)
    await service.reject(candidate_id)
    return {"success": True, "message": "Candidate rejected"}


@router.post("/repair-artwork")
async def repair_artwork(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Re-download artwork for entities with URI but missing artwork."""
    from soulspot.application.services.enrichment import EnrichmentService
    
    service = EnrichmentService(session)
    result = await service.repair_missing_artwork(limit)
    return result


@router.post("/disambiguation")
async def enrich_disambiguation(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """Enrich with MusicBrainz disambiguation data."""
    from soulspot.application.services.enrichment import EnrichmentService
    
    service = EnrichmentService(session)
    result = await service.enrich_disambiguation_batch(limit)
    return result
```

#### 2.2 Router in main.py registrieren
```python
# In src/soulspot/main.py, add:

from soulspot.api.routers import enrichment

app.include_router(enrichment.router)
```

#### 2.3 Alte Endpoints in library.py deprecaten
```python
# In library.py, add deprecation warnings:

@router.get("/enrichment/status", deprecated=True)
async def get_enrichment_status_deprecated(...):
    """DEPRECATED: Use /enrichment/status instead."""
    # Redirect or call new endpoint
    return RedirectResponse(url="/enrichment/status", status_code=308)
```

### Phase 3: Service Refactoring (2-3 Tage)

#### 3.1 LocalLibraryEnrichmentService aufteilen

**VORHER (2969 LOC in einer Datei):**
```
LocalLibraryEnrichmentService
├── enrich_batch()           → EnrichmentService
├── enrich_artist()          → SpotifyEnrichmentStrategy
├── enrich_album()           → SpotifyEnrichmentStrategy
├── repair_missing_artwork() → EnrichmentService
├── enrich_disambiguation()  → MusicBrainzEnrichmentStrategy
├── _calculate_confidence()  → Strategy-spezifisch
├── _create_candidates()     → CandidateService
└── _apply_match()           → CandidateService
```

**NACHHER (mehrere fokussierte Dateien):**
```
enrichment/
├── enrichment_service.py     ← Orchestrierung (~400 LOC)
├── candidate_service.py      ← CRUD für Candidates (~200 LOC)
└── strategies/
    ├── spotify.py            ← Spotify-Matching (~300 LOC)
    └── musicbrainz.py        ← MB-Matching (~200 LOC)
```

#### 3.2 EnrichmentService (Orchestrierung)
```python
# src/soulspot/application/services/enrichment/enrichment_service.py
"""Enrichment Service - Orchestrates enrichment operations.

Future me note:
This is THE entry point for enrichment. It:
1. Checks which providers are available
2. Calls appropriate strategies
3. Handles high-confidence auto-apply vs candidate creation
4. Coordinates with ImageService for artwork

This service does NOT:
- Make HTTP calls (uses Plugins via Strategies)
- Know provider-specific details (delegated to Strategies)
- Manage candidates directly (uses CandidateService)
"""

from dataclasses import dataclass
import logging

from soulspot.domain.ports.enrichment_service import (
    IEnrichmentService, EnrichmentResult, EntityType, EnrichmentSource
)

logger = logging.getLogger(__name__)


# Thresholds for auto-apply vs candidate creation
AUTO_APPLY_THRESHOLD = 0.90  # Above this: auto-apply match
CANDIDATE_THRESHOLD = 0.60   # Above this but below auto: create candidates


class EnrichmentService(IEnrichmentService):
    """Orchestrates enrichment across multiple providers.
    
    Future me note:
    - Uses Strategy pattern for provider-specific logic
    - Falls back through providers if one fails
    - Creates candidates for ambiguous matches
    """
    
    def __init__(
        self,
        session,
        spotify_strategy=None,
        musicbrainz_strategy=None,
        deezer_strategy=None,
    ):
        self._session = session
        self._strategies = {
            EnrichmentSource.SPOTIFY: spotify_strategy,
            EnrichmentSource.MUSICBRAINZ: musicbrainz_strategy,
            EnrichmentSource.DEEZER: deezer_strategy,
        }
    
    async def enrich_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        sources: list[EnrichmentSource] | None = None,
    ) -> EnrichmentResult:
        """Enrich a single entity from configured sources."""
        
        # Get entity from DB for search context
        context = await self._build_context(entity_type, entity_id)
        if not context:
            return EnrichmentResult.failure(entity_type, entity_id, "Entity not found")
        
        # Try each source in order
        sources = sources or [EnrichmentSource.SPOTIFY, EnrichmentSource.DEEZER, EnrichmentSource.MUSICBRAINZ]
        
        all_matches = []
        for source in sources:
            strategy = self._strategies.get(source)
            if not strategy or not await strategy.is_available():
                continue
            
            matches = await strategy.search(context)
            all_matches.extend(matches)
        
        if not all_matches:
            return EnrichmentResult.failure(entity_type, entity_id, "No matches found")
        
        # Sort by confidence
        all_matches.sort(key=lambda m: m.confidence, reverse=True)
        best_match = all_matches[0]
        
        # Decision: auto-apply, create candidates, or skip
        if best_match.confidence >= AUTO_APPLY_THRESHOLD:
            # High confidence: auto-apply
            await self._apply_match(entity_type, entity_id, best_match)
            return EnrichmentResult(
                success=True,
                entity_type=entity_type,
                entity_id=entity_id,
                applied_match=best_match,
            )
        
        elif best_match.confidence >= CANDIDATE_THRESHOLD:
            # Medium confidence: create candidates for user review
            candidates = [m for m in all_matches if m.confidence >= CANDIDATE_THRESHOLD][:5]
            await self._create_candidates(entity_type, entity_id, candidates)
            return EnrichmentResult(
                success=True,
                entity_type=entity_type,
                entity_id=entity_id,
                candidates_created=len(candidates),
            )
        
        else:
            # Low confidence: skip
            return EnrichmentResult.failure(
                entity_type, entity_id, f"Best match confidence too low: {best_match.confidence:.2f}"
            )
```

### Phase 4: Cleanup (1 Tag)

#### 4.1 Alte Services entfernen/deprecaten
```python
# Deprecation in local_library_enrichment_service.py

import warnings

class LocalLibraryEnrichmentService:
    """DEPRECATED: Use EnrichmentService instead.
    
    Future me note:
    This class is deprecated since v2.x. Migration guide:
    - enrich_batch() → EnrichmentService.enrich_batch()
    - repair_artwork() → EnrichmentService.repair_missing_artwork()
    - enrich_disambiguation() → EnrichmentService.enrich_disambiguation_batch()
    
    Will be removed in v3.0.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "LocalLibraryEnrichmentService is deprecated. Use EnrichmentService.",
            DeprecationWarning,
            stacklevel=2,
        )
        # ... existing init for backwards compatibility
```

#### 4.2 Import-Pfade aktualisieren

**Alte Imports:**
```python
from soulspot.application.services.local_library_enrichment_service import LocalLibraryEnrichmentService
from soulspot.application.services.enrichment_service import EnrichmentService
```

**Neue Imports:**
```python
from soulspot.application.services.enrichment import EnrichmentService, CandidateService
```

#### 4.3 Tests migrieren
- Unit-Tests für jede Strategy
- Integration-Tests für EnrichmentService
- Mocks für Plugins (keine echten API-Calls in Tests)

---

## 📁 Finale Dateistruktur

```
src/soulspot/
├── domain/
│   └── ports/
│       ├── image_service.py        ← ✅ Existiert
│       └── enrichment_service.py   ← NEU
│
├── application/
│   └── services/
│       ├── images/                 ← ✅ Existiert
│       │   ├── __init__.py
│       │   └── image_service.py
│       │
│       ├── enrichment/             ← NEU
│       │   ├── __init__.py
│       │   ├── enrichment_service.py
│       │   ├── candidate_service.py
│       │   └── strategies/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── spotify.py
│       │       ├── musicbrainz.py
│       │       └── deezer.py
│       │
│       └── local_library_enrichment_service.py  ← DEPRECATED
│
└── api/
    └── routers/
        ├── library.py              ← Ohne Enrichment-Endpoints!
        └── enrichment.py           ← NEU
```

---

## ⏱️ Zeitplan

| Phase | Aufwand | Abhängigkeiten |
|-------|---------|----------------|
| Phase 1: Port + Struktur | 1-2 Tage | - |
| Phase 2: Router Extraktion | 1 Tag | Phase 1 |
| Phase 3: Service Refactoring | 2-3 Tage | Phase 2 |
| Phase 4: Cleanup | 1 Tag | Phase 3 |
| **GESAMT** | **5-7 Tage** | |

---

## ✅ Erfolgskriterien

1. **Trennung:** `library.py` hat KEINE Enrichment-Endpoints mehr
2. **Plugin-Architektur:** EnrichmentService nutzt Strategies die Plugins wrappen
3. **Testbarkeit:** Strategies sind einzeln testbar mit gemockten Plugins
4. **LOC-Reduktion:** `LocalLibraryEnrichmentService` (2969 LOC) → mehrere Dateien < 500 LOC
5. **Backwards-Compat:** Alte Imports zeigen DeprecationWarning, funktionieren aber noch

---

## 🚨 Risiken & Mitigationen

| Risiko | Mitigation |
|--------|------------|
| Breaking Changes in API | Alte Endpoints mit RedirectResponse |
| JobQueue-Integration | Worker nutzt neuen Service, alte Schnittstelle bleibt |
| Enrichment-Candidates DB | Schema bleibt gleich, nur Service-Layer ändert sich |
| Performance-Regression | Benchmarks vor/nach, gleiche Batch-Logik |

---

## Referenzen

- `docs/architecture/LOCAL_LIBRARY_OPTIMIZATION_PLAN.md` - Übergeordneter Plan
- `src/soulspot/domain/ports/image_service.py` - Referenz-Port-Design
- `src/soulspot/application/services/images/image_service.py` - Referenz-Implementation
- `docs/architecture/DATA_LAYER_PATTERNS.md` - Entity/Repository-Patterns
