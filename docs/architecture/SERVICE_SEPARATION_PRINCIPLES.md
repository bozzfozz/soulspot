# SoulSpot Service Separation Principles

> **ZIEL:** Klare Trennung in JEDEM Service - Single Responsibility, Plugin-Architektur, saubere Schichten.

## 🎯 Das Trennungsprinzip

### Kernregel
```
┌─────────────────────────────────────────────────────────────────┐
│   SERVICES RUFEN NIEMALS EXTERNE APIs DIREKT AUF               │
│   → Das machen PLUGINS für uns!                                 │
│                                                                 │
│   LocalLibrary-Services = NUR DB + Filesystem                  │
│   Enrichment/Sync-Services = Orchestrieren Plugins             │
│   Plugins = Kapseln externe API-Kommunikation                  │
└─────────────────────────────────────────────────────────────────┘
```

### Architektur-Schichten

```
┌─────────────────────────────────────────────────────┐
│                    API Layer                         │
│              (FastAPI Routers)                       │
│     - HTTP Request/Response Handling                 │
│     - Input Validation                               │
│     - Dependency Injection                           │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│               Application Layer                      │
│              (Services)                              │
│     - Business Logic Orchestration                   │
│     - Workflow Coordination                          │
│     - NO DIRECT HTTP CALLS!                          │
└─────────────────────┬───────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌─────────────────────┐  ┌─────────────────────────────┐
│   Infrastructure    │  │      Infrastructure         │
│   (Repositories)    │  │      (Plugins)              │
│                     │  │                             │
│  - DB Access        │  │  - SpotifyPlugin            │
│  - SQLAlchemy       │  │  - DeezerPlugin             │
│  - Entity Mapping   │  │  - MusicBrainzPlugin (NEU!) │
│                     │  │  - slskdClient              │
└─────────────────────┘  │  - CoverArtPlugin (NEU!)    │
                         └─────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   External APIs     │
                         │                     │
                         │  - Spotify API      │
                         │  - Deezer API       │
                         │  - MusicBrainz API  │
                         │  - slskd API        │
                         │  - CoverArtArchive  │
                         └─────────────────────┘
```

---

## ✅ Service-Kategorien mit Regeln

### 1. LocalLibrary-Services
**Dürfen:** DB-Queries, Filesystem-Operationen, ID3-Tag-Parsing
**Dürfen NICHT:** Externe APIs aufrufen

| Service | Status | Notizen |
|---------|--------|---------|
| `library_scanner_service.py` | ✅ OK | Nur mutagen (lokal) |
| `library_cleanup_service.py` | ✅ OK | Nur DB |
| `library_view_service.py` | ✅ OK | Nur DB |
| `file_discovery_service.py` | ✅ OK | Nur Filesystem |

### 2. Enrichment-Services
**Dürfen:** Plugins aufrufen, Candidates verwalten
**Dürfen NICHT:** Clients direkt importieren

| Service | Status | Problem | Lösung |
|---------|--------|---------|--------|
| `local_library_enrichment_service.py` | 🚨 URGENT | 4 direkte Client-Imports, 2969 LOC | Siehe `ENRICHMENT_SERVICE_EXTRACTION_PLAN.md` |
| `enrichment_service.py` | ✅ OK | Nur DB-Queries | - |
| `discography_service.py` | ⚠️ REFACTOR | MusicBrainzClient direkt | MusicBrainzPlugin erstellen |
| `album_completeness.py` | ⚠️ REFACTOR | MusicBrainzClient (TYPE_CHECKING) | MusicBrainzPlugin nutzen |

### 3. Sync-Services
**Dürfen:** Plugins aufrufen für Daten-Sync
**Dürfen NICHT:** HTTP-Clients selbst erstellen

| Service | Status | Notizen |
|---------|--------|---------|
| `spotify_sync_service.py` | ✅ OK | Nutzt SpotifyPlugin |
| `deezer_sync_service.py` | ✅ OK | Nutzt DeezerPlugin |
| `album_sync_service.py` | ✅ OK | - |
| `provider_sync_orchestrator.py` | ✅ OK | Orchestriert Plugins |

### 4. Auth-Services (AUSNAHME)
**Dürfen:** OAuth-Clients direkt nutzen (legitimiert!)
**Warum:** OAuth-Flow braucht direkten Zugriff auf Token-Endpoints

| Service | Status | Notizen |
|---------|--------|---------|
| `spotify_auth_service.py` | ✅ OK (Ausnahme) | OAuth ist legitim |
| `deezer_auth_service.py` | ✅ OK (Ausnahme) | OAuth ist legitim |
| `token_manager.py` | ⚠️ PRÜFEN | httpx Import - ist das nötig? |

### 5. UI/View-Services
**Dürfen:** Repositories aufrufen, ViewModels bauen
**Dürfen NICHT:** Externe APIs

| Service | Status | Notizen |
|---------|--------|---------|
| `stats_service.py` | ✅ OK | Nur DB-Aggregation |
| `filter_service.py` | ✅ OK | Nur DB-Queries |
| `discover_service.py` | ✅ OK | Nutzt Plugins korrekt |
| `new_releases_service.py` | ✅ OK | Nutzt Plugins korrekt |

---

## 🚨 Aktuelle Verletzungen

### URGENT - Sofort beheben

#### 1. `LocalLibraryEnrichmentService` (2969 LOC)
```python
# ❌ VERBOTEN - Direkte Client-Imports!
from soulspot.infrastructure.integrations.coverartarchive_client import CoverArtArchiveClient
from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
```

**Lösung:** Siehe `ENRICHMENT_SERVICE_EXTRACTION_PLAN.md`
- → `SpotifyEnrichmentStrategy` (nutzt SpotifyPlugin)
- → `MusicBrainzEnrichmentStrategy` (nutzt neues MusicBrainzPlugin)
- → `DeezerEnrichmentStrategy` (nutzt DeezerPlugin)
- → `CoverArtStrategy` (nutzt neues CoverArtPlugin)

### REFACTOR - Bald beheben

#### 2. `DiscographyService` 
```python
# ⚠️ Direkter Import
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
```

**Lösung:** MusicBrainzPlugin erstellen:
```python
# src/soulspot/infrastructure/plugins/musicbrainz_plugin.py
class MusicBrainzPlugin:
    """MusicBrainz Plugin - kapselt MB API Kommunikation.
    
    Future me note:
    - Rate limited: 1 req/sec (enforced in plugin)
    - Capabilities: SEARCH_ARTIST, GET_DISAMBIGUATION, etc.
    """
    
    async def search_artists(self, name: str) -> list[MBArtistDTO]: ...
    async def get_disambiguation(self, mbid: str) -> str | None: ...
    async def search_releases(self, artist: str, album: str) -> list[MBReleaseDTO]: ...
```

#### 3. `AlbumCompletenessService`
```python
# ⚠️ TYPE_CHECKING Import - besser als direkter Import aber inkonsistent
if TYPE_CHECKING:
    from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
```

**Lösung:** Nach MusicBrainzPlugin-Erstellung umstellen.

#### 4. `TokenManager`
```python
# ⚠️ httpx direkt importiert
import httpx
```

**Aktion:** Prüfen ob httpx wirklich nötig oder via Client gehen kann.

---

## 📋 Neue Plugins zu erstellen

### 1. MusicBrainzPlugin (Priorität: HOCH)
```python
# src/soulspot/infrastructure/plugins/musicbrainz_plugin.py

from soulspot.domain.ports.plugin import PluginCapability, BasePlugin

class MusicBrainzPlugin(BasePlugin):
    """MusicBrainz API Plugin.
    
    Capabilities:
    - SEARCH_ARTISTS: Suche nach Künstlern
    - GET_DISAMBIGUATION: Hole Disambiguation-String
    - SEARCH_RELEASES: Suche nach Releases
    
    Rate Limit: 1 req/sec (enforced hier, nicht im Service!)
    """
    
    # Capabilities die KEINE Auth brauchen (MB ist public)
    CAPABILITIES = [
        PluginCapability.SEARCH_ARTISTS,
        PluginCapability.SEARCH_ALBUMS,
    ]
    
    def __init__(self, mb_client: MusicBrainzClient):
        self._client = mb_client
        self._last_request = 0
    
    async def search_artists(self, name: str, limit: int = 10) -> list[MBArtistDTO]:
        """Search MusicBrainz for artists."""
        await self._rate_limit()  # 1 sec between requests
        results = await self._client.search_artist(name, limit)
        return [MBArtistDTO.from_response(r) for r in results]
```

**Nutzer nach Erstellung:**
- `discography_service.py`
- `album_completeness.py`
- `MusicBrainzEnrichmentStrategy`

### 2. CoverArtPlugin (Priorität: MITTEL)
```python
# src/soulspot/infrastructure/plugins/coverart_plugin.py

class CoverArtPlugin(BasePlugin):
    """Cover Art Archive Plugin.
    
    Provides album artwork from MusicBrainz Cover Art Archive.
    Falls back to various image sources.
    """
    
    async def get_cover_art(self, mbid: str, size: str = "500") -> str | None:
        """Get cover art URL for MusicBrainz release ID."""
        ...
```

**Nutzer nach Erstellung:**
- `CoverArtEnrichmentStrategy`
- `ImageService` (optional, als zusätzliche Quelle)

---

## 🏗️ Master-Refactoring-Roadmap

### Phase 1: Basis-Infrastruktur (1 Woche)
1. ☐ MusicBrainzPlugin erstellen
2. ☐ CoverArtPlugin erstellen
3. ☐ Plugin-Interface in `domain/ports/plugin.py` erweitern
4. ☐ Dependency Injection für neue Plugins

### Phase 2: LocalLibraryEnrichmentService aufbrechen (2 Wochen)
1. ☐ Siehe `ENRICHMENT_SERVICE_EXTRACTION_PLAN.md`
2. ☐ Strategy-Pattern für Enrichment-Quellen
3. ☐ Neuer `/enrichment/*` Router
4. ☐ Alte Endpoints deprecaten

### Phase 3: Restliche Services migrieren (1 Woche)
1. ☐ `discography_service.py` → MusicBrainzPlugin
2. ☐ `album_completeness.py` → MusicBrainzPlugin
3. ☐ `token_manager.py` httpx-Nutzung prüfen

### Phase 4: Dokumentation & Tests (1 Woche)
1. ☐ Architecture Decision Records (ADRs)
2. ☐ Plugin-Entwickler-Guide
3. ☐ Integration Tests für Plugins

---

## 📜 Code-Guidelines für Entwickler

### ✅ SO MACHEN:
```python
# Service nutzt Plugin über Dependency Injection
class DiscographyService:
    def __init__(self, mb_plugin: IMusicBrainzPlugin):
        self._mb_plugin = mb_plugin
    
    async def get_artist_discography(self, artist_name: str):
        # Plugin aufrufen, nicht Client direkt!
        releases = await self._mb_plugin.search_releases(artist_name)
        ...
```

### ❌ NICHT SO:
```python
# ❌ VERBOTEN: Direkter Client-Import in Service!
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

class DiscographyService:
    def __init__(self, session):
        # ❌ Client selbst erstellen
        self._mb_client = MusicBrainzClient()
```

### ✅ Auth-Services (EINZIGE AUSNAHME):
```python
# Auth-Services DÜRFEN Clients direkt nutzen für OAuth
class SpotifyAuthService:
    def __init__(self, spotify_client: SpotifyClient):
        # ✅ OK für Auth-Flow
        self._client = spotify_client
```

---

## 🔍 Checkliste für neue Services

Bevor du einen neuen Service erstellst:

- [ ] **Single Responsibility:** Hat der Service genau EINE Aufgabe?
- [ ] **Keine direkten HTTP-Calls:** Nutzt der Service Plugins/Repositories?
- [ ] **Dependency Injection:** Werden Abhängigkeiten injiziert (nicht self-created)?
- [ ] **LOC < 500:** Ist der Service unter 500 Zeilen? (Wenn nicht: splitten überlegen)
- [ ] **Interface definiert:** Gibt es ein Port in `domain/ports/`?
- [ ] **Docstring:** Erklärt der Docstring WAS der Service tut und WAS NICHT?

---

## Referenzen

- `docs/architecture/ENRICHMENT_SERVICE_EXTRACTION_PLAN.md` - Detailplan für Enrichment
- `docs/architecture/LOCAL_LIBRARY_OPTIMIZATION_PLAN.md` - LocalLibrary Cleanup
- `src/soulspot/domain/ports/image_service.py` - Vorbildliches Port-Design
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - Plugin-Referenzimplementation
