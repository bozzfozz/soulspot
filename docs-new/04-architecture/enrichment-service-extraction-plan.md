# Enrichment Service Extraction Plan

**Category:** Architecture (Refactoring Plan)  
**Status:** PLANNING  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Plugin System](./plugin-system.md) | [Service Separation Principles](./service-separation-principles.md)

---

## Overview

**Goal:** Extract enrichment functionality from LocalLibrary into standalone, plugin-based architecture (similar to ImageService).

**Problem:** Enrichment endpoints currently mixed into `library.py` router, and `LocalLibraryEnrichmentService` directly calls external APIs (violates plugin architecture).

---

## Current Architecture (PROBLEMATIC)

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

**Problems:**
1. ❌ Enrichment endpoints in `library.py` router (belong in separate router!)
2. ❌ `LocalLibraryEnrichmentService` calls Spotify/MusicBrainz directly (should use plugins!)
3. ❌ No clear separation: LocalLibrary = DB+Filesystem, Enrichment = External APIs
4. ❌ `LocalLibraryEnrichmentService` is 2969 LOC - too large!

---

## Reference: ImageService Architecture (GOOD!)

```
domain/ports/image_service.py     ← Interface (IImageService)
     │
application/services/images/
     ├── image_service.py         ← Implementation (1434 LOC)
     └── __init__.py              ← Re-export
     │
     └── Uses Plugins for URLs, downloads itself
         - SpotifyPlugin.get_artist_image_url()
         - DeezerPlugin.get_album_image()
         - No direct HTTP calls!
```

**What ImageService does right:**
- ✅ Port (interface) in `domain/ports/`
- ✅ Implementation in `application/services/images/`
- ✅ Uses plugins for external data
- ✅ Single responsibility (images only)
- ✅ Stateless, no DB models in service

---

## Target Architecture

### New Structure

```
domain/ports/
     └── enrichment_service.py        ← NEW: Interface (IEnrichmentService)

application/services/enrichment/
     ├── __init__.py                  ← Re-export
     ├── enrichment_service.py        ← NEW: Orchestration (<500 LOC)
     ├── candidate_service.py         ← NEW: Candidate management
     └── strategies/                  ← NEW: Provider-specific strategies
         ├── __init__.py
         ├── base.py                  ← EnrichmentStrategy ABC
         ├── spotify_enrichment.py    ← Spotify matching logic
         ├── musicbrainz_enrichment.py ← MusicBrainz matching logic
         └── deezer_enrichment.py     ← Deezer matching logic (future)

api/routers/
     └── enrichment.py                ← NEW: Separate router

infrastructure/plugins/
     └── (already exists)
         - SpotifyPlugin              ← Extend: search_artist(), get_artist_details()
         - MusicBrainzPlugin          ← Extend: search_artist(), get_disambiguation()
         - DeezerPlugin               ← Extend: search_artist()
```

### Data Flow

```
User UI
   │
   ▼
api/routers/enrichment.py
   │
   ▼
EnrichmentService (Orchestration)
   │
   ├── CandidateService (DB: EnrichmentCandidate CRUD)
   │
   └── EnrichmentStrategy (Provider-specific)
         │
         └── SpotifyPlugin / MusicBrainzPlugin / DeezerPlugin
               │
               └── External APIs (Spotify, MusicBrainz, Deezer)
```

---

## Port Definition (Interface)

```python
# src/soulspot/domain/ports/enrichment_service.py

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
    
    Immutable snapshot at search time.
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


class IEnrichmentService(Protocol):
    """Enrichment Service Port (Interface).
    
    All EnrichmentService implementations must follow this protocol.
    Enables: DI, mocking, alternative implementations.
    
    NOTE: This service ORCHESTRATES enrichment.
    Actual provider communication via Plugins (SpotifyPlugin, MusicBrainzPlugin).
    """
    
    async def enrich_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        sources: list[EnrichmentSource] | None = None,
    ) -> EnrichmentResult:
        """Enrich single entity from configured sources.
        
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
            Stats: {"enriched": 5, "candidates_created": 3, "skipped": 2}
        """
        ...
    
    async def get_enrichment_status(self) -> dict:
        """Get counts of unenriched entities and pending candidates."""
        ...
```

---

## Strategy Pattern (Provider-Specific Logic)

### Base Strategy

```python
# src/soulspot/application/services/enrichment/strategies/base.py

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
    """Abstract base for enrichment strategies.
    
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
        """Check if strategy can be used (provider enabled + auth)."""
        ...
```

---

### Spotify Strategy

```python
# src/soulspot/application/services/enrichment/strategies/spotify_enrichment.py

from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
from .base import EnrichmentStrategy, SearchContext, EnrichmentMatch

class SpotifyEnrichmentStrategy(EnrichmentStrategy):
    """Spotify enrichment strategy."""
    
    def __init__(self, spotify_plugin: SpotifyPlugin):
        self._spotify = spotify_plugin
    
    @property
    def source(self) -> str:
        return "spotify"
    
    async def search(self, context: SearchContext) -> list[EnrichmentMatch]:
        """Search Spotify for matches."""
        
        if not await self.is_available():
            return []
        
        # Use plugin's search method
        if context.entity_type == "artist":
            results = await self._spotify.search_artists(context.entity_name)
        elif context.entity_type == "album":
            # Search with artist hint if available
            query = f"{context.entity_name}"
            if context.artist_name:
                query += f" artist:{context.artist_name}"
            results = await self._spotify.search_albums(query)
        elif context.entity_type == "track":
            # Use ISRC if available (most accurate)
            if context.isrc:
                results = await self._spotify.search_by_isrc(context.isrc)
            else:
                query = f"{context.entity_name}"
                if context.artist_name:
                    query += f" artist:{context.artist_name}"
                results = await self._spotify.search_tracks(query)
        
        # Convert to EnrichmentMatch with confidence scoring
        matches = []
        for result in results[:5]:  # Top 5 results
            confidence = self._calculate_confidence(context, result)
            matches.append(EnrichmentMatch(
                source="spotify",
                external_id=result.spotify_id,
                name=result.name,
                confidence=confidence,
                image_url=result.image_url,
                extra_info={
                    "followers": getattr(result, "followers", 0),
                    "genres": getattr(result, "genres", []),
                },
            ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)
    
    def _calculate_confidence(self, context: SearchContext, result) -> float:
        """Calculate confidence score (0.0 - 1.0) for match.
        
        Factors:
        - Name similarity (Levenshtein distance)
        - Year match (for albums)
        - ISRC match (for tracks) = 1.0 confidence
        - Popularity (follower count)
        """
        # Simplified example - real implementation uses fuzzy matching
        if context.entity_name.lower() == result.name.lower():
            return 0.95
        elif context.entity_name.lower() in result.name.lower():
            return 0.75
        else:
            return 0.50
    
    async def is_available(self) -> bool:
        """Check if Spotify is available."""
        return self._spotify.can_use(PluginCapability.SEARCH_ARTISTS)
```

---

## Enrichment Service (Orchestration)

```python
# src/soulspot/application/services/enrichment/enrichment_service.py

from soulspot.domain.ports.enrichment_service import (
    IEnrichmentService,
    EnrichmentResult,
    EnrichmentSource,
    EntityType,
)
from .strategies.base import EnrichmentStrategy, SearchContext
from .strategies.spotify_enrichment import SpotifyEnrichmentStrategy
from .strategies.musicbrainz_enrichment import MusicBrainzEnrichmentStrategy


class EnrichmentService:
    """Orchestrates enrichment across multiple providers.
    
    Responsibilities:
    - Determine which strategies to use
    - Execute searches across strategies
    - Create enrichment candidates for ambiguous results
    - Apply best matches automatically (if confidence > threshold)
    """
    
    def __init__(
        self,
        artist_repository: ArtistRepository,
        album_repository: AlbumRepository,
        track_repository: TrackRepository,
        candidate_repository: EnrichmentCandidateRepository,
        strategies: list[EnrichmentStrategy],
    ):
        self._artist_repo = artist_repository
        self._album_repo = album_repository
        self._track_repo = track_repository
        self._candidate_repo = candidate_repository
        self._strategies = {s.source: s for s in strategies}
    
    async def enrich_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        sources: list[EnrichmentSource] | None = None,
    ) -> EnrichmentResult:
        """Enrich single entity."""
        
        # Get entity from DB
        entity = await self._get_entity(entity_type, entity_id)
        if not entity:
            return EnrichmentResult.failure(
                entity_type, entity_id, "Entity not found"
            )
        
        # Build search context
        context = self._build_context(entity_type, entity)
        
        # Search across strategies
        all_matches = []
        for source in (sources or list(self._strategies.keys())):
            strategy = self._strategies.get(source)
            if strategy and await strategy.is_available():
                matches = await strategy.search(context)
                all_matches.extend(matches)
        
        if not all_matches:
            return EnrichmentResult.failure(
                entity_type, entity_id, "No matches found"
            )
        
        # Sort by confidence
        all_matches.sort(key=lambda m: m.confidence, reverse=True)
        best_match = all_matches[0]
        
        # Auto-apply if high confidence
        if best_match.confidence >= 0.90:
            await self._apply_match(entity_type, entity_id, best_match)
            return EnrichmentResult(
                success=True,
                entity_type=entity_type,
                entity_id=entity_id,
                applied_match=best_match,
            )
        
        # Create candidates for manual review
        candidates_created = await self._create_candidates(
            entity_type, entity_id, all_matches
        )
        
        return EnrichmentResult(
            success=True,
            entity_type=entity_type,
            entity_id=entity_id,
            candidates_created=candidates_created,
        )
```

---

## Migration Plan

### Phase 1: Create New Structure (1-2 days)

1. **Create port:** `domain/ports/enrichment_service.py`
2. **Create strategies:** `application/services/enrichment/strategies/`
   - `base.py` - Abstract base
   - `spotify_enrichment.py` - Spotify strategy
   - `musicbrainz_enrichment.py` - MusicBrainz strategy
3. **Create service:** `application/services/enrichment/enrichment_service.py`
4. **Create router:** `api/routers/enrichment.py`

### Phase 2: Extend Plugins (1 day)

1. **SpotifyPlugin:** Add `search_artists()`, `search_albums()`, `search_tracks()`
2. **MusicBrainzPlugin:** Add `search_artist()`, `get_disambiguation()`
3. **DeezerPlugin:** Add `search_artist()` (future)

### Phase 3: Migrate Endpoints (1 day)

1. **Move endpoints** from `library.py` to `enrichment.py`
2. **Update dependencies** to use new `EnrichmentService`
3. **Test all enrichment flows**

### Phase 4: Deprecate Old Service (1 day)

1. **Mark `LocalLibraryEnrichmentService` as deprecated**
2. **Remove enrichment methods** from LocalLibraryService
3. **Update all callers** to use new EnrichmentService

### Phase 5: Cleanup (0.5 days)

1. **Delete deprecated code**
2. **Update documentation**
3. **Remove unused imports**

---

## Success Criteria

- ✅ Enrichment endpoints in separate `enrichment.py` router
- ✅ No direct API calls in services (all via plugins)
- ✅ Clear strategy pattern for providers
- ✅ LocalLibraryService <500 LOC
- ✅ All tests pass
- ✅ No breaking changes to API

---

## Related Documentation

- **[Plugin System](./plugin-system.md)** - Plugin interface and usage
- **[Service Separation Principles](./service-separation-principles.md)** - Service design guidelines
- **[Data Layer Patterns](./data-layer-patterns.md)** - Repository usage patterns

---

**Status:** PLANNING - Ready for implementation  
**Estimated Effort:** 4-5 days  
**Priority:** MEDIUM - Improves architecture, not urgent
