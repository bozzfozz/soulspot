````instructions
---
description: 'SoulSpot Clean Architecture - Layer Rules and Data Flow'
applyTo: '**/*'
---

# SoulSpot Architecture - Das goldene Regelwerk

## 0. WARUM DIESES DOKUMENT EXISTIERT

Dieses Dokument verhindert die häufigsten Fehler:
- ❌ `'ArtistModel' object has no attribute 'spotify_id'`
- ❌ `'DeezerPlugin' object has no attribute '_convert_track_to_dto'`
- ❌ Routes rufen Clients/Repos direkt auf statt Services
- ❌ Domain Entities mit ORM-Abhängigkeiten

**Lies das BEVOR du Code schreibst!**

**Verwandte Dokumente:**
- `docs/architecture/DATA_STANDARDS.md` - SoulSpot Datenformate & Feldmappings
- `docs/architecture/DATA_LAYER_PATTERNS.md` - Code-Beispiele für häufige Operationen
- `docs/architecture/ERROR_HANDLING.md` - Exception-Handling & HTTP-Mapping
- `docs/architecture/TRANSACTION_PATTERNS.md` - Wer committet wann
- `docs/architecture/API_RESPONSE_FORMATS.md` - Standardisierte API-Responses
- `docs/architecture/NAMING_CONVENTIONS.md` - Benennungsregeln für alles
- `docs/architecture/WORKER_PATTERNS.md` - Background Worker Lifecycle
- `docs/architecture/AUTH_PATTERNS.md` - OAuth & Session Management

---

## 1. LAYER-ARCHITEKTUR (Uncle Bob's Clean Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYER (Thin!)                          │
│  src/soulspot/api/routers/*.py                                      │
│  - FastAPI Routes (HTTP Request/Response handling ONLY)             │
│  - Ruft Services auf, NIEMALS Clients/Repos direkt!                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                               │
│  src/soulspot/application/services/*.py                             │
│  src/soulspot/application/workers/*.py                              │
│  - Business Logic Orchestration                                      │
│  - Verwendet Plugins für externe Services                           │
│  - Verwendet Repositories für DB-Zugriff                            │
│  - Input: DTOs → Output: DTOs                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
┌──────────────────────┐ ┌─────────────┐ ┌──────────────────────┐
│   PLUGINS            │ │   DOMAIN    │ │   REPOSITORIES       │
│   (Infrastructure)   │ │   (Core)    │ │   (Infrastructure)   │
│                      │ │             │ │                      │
│   SpotifyPlugin      │ │   Entities  │ │   ArtistRepository   │
│   DeezerPlugin       │ │   DTOs      │ │   TrackRepository    │
│   TidalPlugin        │ │   Ports     │ │   AlbumRepository    │
│                      │ │             │ │                      │
│   Output: DTOs       │ │   KEINE     │ │   Input: Entities    │
│                      │ │   externen  │ │   Output: Models     │
│                      │ │   Deps!     │ │   (intern)           │
└──────────────────────┘ └─────────────┘ └──────────────────────┘
          │                                         │
          ▼                                         ▼
┌──────────────────────┐               ┌──────────────────────┐
│   CLIENTS            │               │   MODELS (ORM)       │
│   (Infrastructure)   │               │   (Infrastructure)   │
│                      │               │                      │
│   SpotifyClient      │               │   ArtistModel        │
│   DeezerClient       │               │   TrackModel         │
│   TidalClient        │               │   AlbumModel         │
│                      │               │                      │
│   Output: raw dict   │               │   SQLAlchemy Tables  │
└──────────────────────┘               └──────────────────────┘
          │                                         │
          ▼                                         ▼
   [Spotify API]                            [SQLite/PostgreSQL]
```

---

## 2. DIE 5 OBJEKT-TYPEN - WANN NUTZE WAS?

### 2.1 Entities (Domain Layer)
**Ort:** `src/soulspot/domain/entities/`
**Zweck:** Reine Business-Objekte OHNE externe Abhängigkeiten

```python
# ✅ RICHTIG: Entity ist REIN (keine ORM, keine API Imports)
@dataclass
class Artist:
    id: ArtistId
    name: str
    spotify_uri: SpotifyUri | None = None  # ← SPOTIFY_URI nicht ID!
    musicbrainz_id: str | None = None
    # ...
```

**⚠️ REGELN für Entities:**
- KEIN Import von SQLAlchemy, httpx, oder Infrastructure Code
- Verwende `spotify_uri` (vollständiger URI), NICHT `spotify_id`
- Dataclass mit Validierung in `__post_init__`
- Werden NUR in Application Layer und Domain Layer verwendet

### 2.2 DTOs (Domain Layer)
**Ort:** `src/soulspot/domain/dtos/`
**Zweck:** Daten-Transport zwischen Plugins und Services

```python
# ✅ RICHTIG: DTO hat BEIDE - spotify_uri UND spotify_id
@dataclass
class ArtistDTO:
    name: str
    source_service: str  # "spotify", "deezer", etc.
    
    # Service-spezifische IDs (Plugin setzt nur das eigene)
    spotify_id: str | None = None      # ← NUR die ID: "4dpARuHxo51G3z768sgnrY"
    spotify_uri: str | None = None     # ← Voller URI: "spotify:artist:4dpARuHxo51G3z768sgnrY"
    deezer_id: str | None = None
    tidal_id: str | None = None
```

**⚠️ REGELN für DTOs:**
- DTOs haben BEIDE: `spotify_id` (kurz) UND `spotify_uri` (voll)
- Plugins MÜSSEN DTOs zurückgeben, nie raw dicts
- DTOs sind die "Lingua Franca" zwischen allen Schichten

### 2.3 Models (Infrastructure Layer)
**Ort:** `src/soulspot/infrastructure/persistence/models.py`
**Zweck:** SQLAlchemy ORM-Klassen für DB-Persistenz

```python
# ✅ RICHTIG: Model hat spotify_uri Column + spotify_id Property
class ArtistModel(Base):
    __tablename__ = "soulspot_artists"
    
    # DB Column - speichert den VOLLEN URI
    spotify_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    @property
    def spotify_id(self) -> str | None:
        """Backward-Compatibility Property für Legacy-Code."""
        if not self.spotify_uri:
            return None
        return self.spotify_uri.split(":")[-1]  # Extrahiert ID aus URI
```

**⚠️ REGELN für Models:**
- DB speichert `spotify_uri` (Column), NICHT `spotify_id`
- `spotify_id` ist ein @property für Backward-Compatibility
- Models werden NUR in Repositories verwendet, nie in Routes!

### 2.4 Plugins (Infrastructure Layer)
**Ort:** `src/soulspot/infrastructure/plugins/`
**Zweck:** Konvertiert externe API-Responses zu Standard-DTOs

```python
# ✅ RICHTIG: Plugin konvertiert raw API → DTO
class SpotifyPlugin(IMusicServicePlugin):
    def __init__(self, client: SpotifyClient, access_token: str | None = None):
        self._client = client  # Low-level HTTP client
        self._access_token = access_token
    
    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Get artist and return as DTO."""
        raw = await self._client.get_artist(artist_id, self._access_token)
        return self._convert_artist(raw)  # ← Konvertierung hier!
    
    def _convert_artist(self, data: dict) -> ArtistDTO:
        """Internal: raw dict → ArtistDTO."""
        return ArtistDTO(
            name=data["name"],
            source_service="spotify",
            spotify_id=data["id"],
            spotify_uri=data["uri"],
            image_url=data["images"][0]["url"] if data.get("images") else None,
            # ...
        )
```

**⚠️ REGELN für Plugins:**
- Plugins geben IMMER DTOs zurück, nie raw dicts
- Konvertierungs-Methoden heißen `_convert_artist()`, `_convert_track()`, etc.
- Plugins implementieren `IMusicServicePlugin` Interface
- Plugins sind ADAPTER (Hexagonal Architecture)

### 2.5 Clients (Infrastructure Layer)
**Ort:** `src/soulspot/infrastructure/integrations/`
**Zweck:** Low-Level HTTP-Calls zur externen API

```python
# ✅ RICHTIG: Client gibt raw dict zurück
class SpotifyClient:
    async def get_artist(self, artist_id: str, access_token: str) -> dict:
        """Low-level API call - returns raw JSON as dict."""
        response = await self._client.get(
            f"{self.API_BASE_URL}/artists/{artist_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        return response.json()  # ← Raw dict, keine Konvertierung!
```

**⚠️ REGELN für Clients:**
- Clients geben raw dicts zurück (JSON von API)
- KEINE DTO-Konvertierung in Clients!
- Clients handlen HTTP-Details (Headers, Auth, Retries)
- Ein Client pro externer API (SpotifyClient, DeezerClient, etc.)

---

## 3. DATENFLUSS - WER RUFT WEN AUF?

### 3.1 Von API Route bis zur Datenbank

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  API Route (api/routers/discover.py)                                │
│                                                                     │
│  @router.get("/discover/new-releases")                              │
│  async def get_new_releases(service: NewReleasesService):           │
│      return await service.get_new_releases()  # ← Ruft Service!     │
│                                                                     │
│  ❌ VERBOTEN: await spotify_client.get_new_releases(...)            │
│  ❌ VERBOTEN: await session.execute(select(AlbumModel)...)          │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Application Service (application/services/new_releases_service.py) │
│                                                                     │
│  class NewReleasesService:                                          │
│      def __init__(self,                                             │
│          spotify_plugin: SpotifyPlugin,  # ← Plugin, NICHT Client!  │
│          album_repo: AlbumRepository):                              │
│          ...                                                        │
│                                                                     │
│      async def get_new_releases(self) -> list[AlbumDTO]:            │
│          albums = await self._spotify.get_browse_new_releases()     │
│          return albums  # ← DTOs, keine Models!                     │
└─────────────────────────────────────────────────────────────────────┘
     │
     ├─────────────────────────┬─────────────────────────┐
     │                         │                         │
     ▼                         ▼                         ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────────┐
│ SpotifyPlugin  │    │ DeezerPlugin   │    │ AlbumRepository    │
│                │    │                │    │                    │
│ → ArtistDTO    │    │ → ArtistDTO    │    │ Input: Entity      │
│ → AlbumDTO     │    │ → AlbumDTO     │    │ Output: Entity     │
│ → TrackDTO     │    │ → TrackDTO     │    │                    │
└────────────────┘    └────────────────┘    └────────────────────┘
     │                         │                         │
     ▼                         ▼                         ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────────┐
│ SpotifyClient  │    │ DeezerClient   │    │ ArtistModel (ORM)  │
│ → raw dict     │    │ → raw dict     │    │ AlbumModel (ORM)   │
└────────────────┘    └────────────────┘    └────────────────────┘
```

### 3.2 Zusammenfassung Datenfluss

| Schicht | Input | Output | Darf aufrufen |
|---------|-------|--------|---------------|
| **API Route** | HTTP Request | HTTP Response | Services |
| **Service** | DTOs | DTOs | Plugins, Repositories |
| **Plugin** | - | DTOs | Client (nur der eigene!) |
| **Client** | - | raw dict | externe API |
| **Repository** | Entity | Entity | Models (ORM) |
| **Model** | - | - | SQLAlchemy (DB) |

---

## 4. ATTRIBUT-NAMING - spotify_id vs spotify_uri

### 4.1 Die Regel

| Kontext | Verwende | Format | Beispiel |
|---------|----------|--------|----------|
| **DB Column (Model)** | `spotify_uri` | `spotify:type:id` | `spotify:artist:4dpARuHxo51G3z768sgnrY` |
| **DTO (Transfer)** | BEIDE | - | `spotify_id="4dpARu..."`, `spotify_uri="spotify:artist:..."` |
| **Entity (Domain)** | `spotify_uri` | `spotify:type:id` | `SpotifyUri` ValueObject |
| **API Request** | `spotify_id` | nur ID | `4dpARuHxo51G3z768sgnrY` |

### 4.2 Konvertierung

```python
# URI → ID (wenn du nur die ID brauchst)
spotify_uri = "spotify:artist:4dpARuHxo51G3z768sgnrY"
spotify_id = spotify_uri.split(":")[-1]  # → "4dpARuHxo51G3z768sgnrY"

# ID → URI (wenn du den vollen URI brauchst)
entity_type = "artist"  # oder "album", "track"
spotify_id = "4dpARuHxo51G3z768sgnrY"
spotify_uri = f"spotify:{entity_type}:{spotify_id}"
```

### 4.3 Warum Model.spotify_id ein @property ist

```python
# models.py - Das PATTERN für alle Models
class ArtistModel(Base):
    spotify_uri: Mapped[str | None] = mapped_column(...)  # ← DB Column
    
    @property
    def spotify_id(self) -> str | None:
        """Extract ID from URI for backward compatibility."""
        if not self.spotify_uri:
            return None
        return self.spotify_uri.split(":")[-1]
```

**Grund:** Legacy-Code und Workers erwarten `.spotify_id`, aber wir speichern nur `spotify_uri` in der DB. Das Property bridged beide Welten.

---

## 5. HÄUFIGE FEHLER UND FIXES

### ❌ Fehler 1: Route ruft Client direkt auf

```python
# ❌ FALSCH!
@router.get("/artists/{id}")
async def get_artist(spotify_client: SpotifyClient, id: str):
    return await spotify_client.get_artist(id)  # ← Client gibt raw dict!

# ✅ RICHTIG
@router.get("/artists/{id}")
async def get_artist(artist_service: ArtistService, id: str):
    return await artist_service.get_artist(id)  # ← Service gibt DTO!
```

### ❌ Fehler 2: Service erwartet spotify_id, Model hat nur spotify_uri

```python
# ❌ FALSCH - Model hat kein spotify_id Attribut (nur Property)
artist = await repo.get_by_spotify_uri(uri)
existing_ids.add(artist.spotify_id)  # ← AttributeError wenn Property fehlt!

# ✅ RICHTIG - Extrahiere ID aus URI
artist = await repo.get_by_spotify_uri(uri)
existing_ids.add(artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None)

# ✅ NOCH BESSER - Model hat @property spotify_id
# (Dann funktioniert auch artist.spotify_id)
```

### ❌ Fehler 3: Plugin-Methode falsch benannt

```python
# ❌ FALSCH - Methode existiert nicht
tracks = await plugin._convert_track_to_dto(data)

# ✅ RICHTIG - Methode heißt _convert_track()
tracks = await plugin._convert_track(data)
```

### ❌ Fehler 4: Worker greift auf Model wie auf DTO zu

```python
# ❌ FALSCH - Workers arbeiten mit Models, nicht DTOs
for artist in await repo.list_all():
    spotify_id = artist.spotify_id  # ← Geht NUR wenn @property existiert!

# ✅ RICHTIG - Prüfe ob Model das Property hat
for artist in await repo.list_all():
    if artist.spotify_uri:
        spotify_id = artist.spotify_uri.split(":")[-1]
```

### ❌ Fehler 5: Domain Entity bekommt spotify_id

```python
# ❌ FALSCH - Entities haben NICHT spotify_id!
@dataclass
class Artist:
    spotify_id: str | None = None  # ← VERBOTEN im Domain Layer!

# ✅ RICHTIG - Entities haben spotify_uri
@dataclass
class Artist:
    spotify_uri: SpotifyUri | None = None
```

---

## 6. CHECKLISTE VOR JEDEM COMMIT

**Vor jedem Code-Commit prüfe:**

- [ ] **Routes** rufen nur Services auf (nie Clients/Repos)
- [ ] **Services** verwenden Plugins für externe APIs
- [ ] **Plugins** geben DTOs zurück, keine dicts
- [ ] **DTOs** haben sowohl `spotify_id` als auch `spotify_uri`
- [ ] **Entities** haben NUR `spotify_uri`, KEIN `spotify_id`
- [ ] **Models** haben `spotify_uri` Column + `spotify_id` @property
- [ ] Neue Repository-Methoden auch im Interface (Port) hinzugefügt?
- [ ] Keine direkten SQLAlchemy-Imports in Domain-Layer?

---

## 7. QUICK REFERENCE - WO FINDE ICH WAS?

| Was brauchst du? | Wo liegt es? |
|------------------|--------------|
| API Routes | `src/soulspot/api/routers/` |
| Services (Business Logic) | `src/soulspot/application/services/` |
| Workers (Background Tasks) | `src/soulspot/application/workers/` |
| Plugins (API→DTO Adapter) | `src/soulspot/infrastructure/plugins/` |
| Clients (HTTP Calls) | `src/soulspot/infrastructure/integrations/` |
| Repositories (DB Access) | `src/soulspot/infrastructure/persistence/repositories.py` |
| Models (ORM) | `src/soulspot/infrastructure/persistence/models.py` |
| Entities (Domain Objects) | `src/soulspot/domain/entities/` |
| DTOs (Transfer Objects) | `src/soulspot/domain/dtos/` |
| Ports (Interfaces) | `src/soulspot/domain/ports/` |

---

## 8. DIAGRAMM: VOLLSTÄNDIGER REQUEST-FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GET /api/discover/new-releases                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  discover_router.py                                                         │
│  ─────────────────                                                          │
│  @router.get("/new-releases")                                               │
│  async def new_releases(service: ChartsService = Depends(...)):             │
│      return await service.get_multi_provider_new_releases()                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  charts_service.py                                                          │
│  ─────────────────                                                          │
│  async def get_multi_provider_new_releases(self) -> list[AlbumDTO]:         │
│      results = []                                                           │
│                                                                             │
│      # 1. Deezer (kein Auth nötig)                                          │
│      if self._deezer.can_use(PluginCapability.BROWSE_NEW_RELEASES):         │
│          deezer_albums = await self._deezer.get_browse_new_releases()       │
│          results.extend(deezer_albums)                                      │
│                                                                             │
│      # 2. Spotify (Auth required)                                           │
│      if self._spotify.can_use(PluginCapability.BROWSE_NEW_RELEASES):        │
│          spotify_albums = await self._spotify.get_browse_new_releases()     │
│          results.extend(spotify_albums)                                     │
│                                                                             │
│      return deduplicate_by_title_artist(results)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                                           ▼
┌────────────────────────────┐            ┌────────────────────────────┐
│  DeezerPlugin              │            │  SpotifyPlugin             │
│  ────────────              │            │  ─────────────             │
│  async def get_browse_     │            │  async def get_browse_     │
│    new_releases():         │            │    new_releases():         │
│                            │            │                            │
│    raw = await self._      │            │    raw = await self._      │
│      client.get_chart()    │            │      client.get_new_       │
│                            │            │        releases(token)     │
│    return [                │            │                            │
│      self._convert_album(  │            │    return [                │
│        item                │            │      self._convert_album(  │
│      ) for item in raw     │            │        item                │
│    ]                       │            │      ) for item in raw     │
│                            │            │    ]                       │
│  → list[AlbumDTO]          │            │  → list[AlbumDTO]          │
└────────────────────────────┘            └────────────────────────────┘
              │                                           │
              ▼                                           ▼
┌────────────────────────────┐            ┌────────────────────────────┐
│  DeezerClient              │            │  SpotifyClient             │
│  ────────────              │            │  ─────────────             │
│  async def get_chart():    │            │  async def get_new_        │
│    response = await self.  │            │    releases(token):        │
│      _client.get(          │            │    response = await self.  │
│        "/chart/0/albums"   │            │      _client.get(          │
│      )                     │            │        "/browse/new-       │
│    return response.json()  │            │          releases",        │
│                            │            │        headers=...         │
│  → raw dict                │            │      )                     │
│                            │            │    return response.json()  │
└────────────────────────────┘            │  → raw dict                │
              │                           └────────────────────────────┘
              ▼                                           │
    [Deezer API]                                          ▼
                                               [Spotify API]
```

---

## 9. GOLDEN RULES - IMMER BEACHTEN!

1. **Dependency Direction:** API → Application → Domain ← Infrastructure
2. **Domain ist REIN:** Keine Imports von SQLAlchemy, httpx, FastAPI in `domain/`
3. **Plugins geben DTOs:** Nie raw dicts aus Plugins zurückgeben
4. **Routes sind DÜNN:** Nur HTTP-Handling, Business Logic in Services
5. **spotify_uri in DB:** Voller URI speichern, ID per Property extrahieren
6. **Interface + Implementation:** Jede Repo-Methode auch im Interface (Port)

---

*Letztes Update: Nach stundenlangem Debugging von AttributeErrors* 😤
````
