# SoulSpot Naming Conventions

> **PFLICHTLEKTÜRE** für konsistente Benennung im gesamten Codebase.

---

## 1. Dateinamen

### 1.1 Python Module

| Typ | Pattern | Beispiele |
|-----|---------|-----------|
| Services | `{domain}_service.py` | `artist_service.py`, `playlist_sync_service.py` |
| Repositories | `repositories.py` oder `{domain}_repository.py` | `repositories.py`, `track_repository.py` |
| Routers | `{domain}.py` | `artists.py`, `playlists.py`, `library.py` |
| Entities | `{entity}.py` | `artist.py`, `track.py`, `playlist.py` |
| DTOs | `dtos.py` oder `{domain}_dto.py` | `dtos.py`, `artist_dto.py` |
| Schemas | `schemas.py` oder `{domain}_schemas.py` | `schemas.py`, `artist_schemas.py` |
| Clients | `{service}_client.py` | `spotify_client.py`, `deezer_client.py` |
| Plugins | `{service}_plugin.py` | `spotify_plugin.py`, `deezer_plugin.py` |
| Workers | `{purpose}_worker.py` | `token_refresh_worker.py`, `sync_worker.py` |
| Utils | `{purpose}.py` | `string_utils.py`, `date_helpers.py` |

### 1.2 Ordnerstruktur

```
src/soulspot/
├── api/
│   ├── routers/          # snake_case, singular domain
│   │   ├── artists.py    # NOT artist.py
│   │   ├── playlists.py
│   │   └── library.py
│   └── schemas/          # Pydantic models für API
├── application/
│   └── services/         # Business logic
│       ├── artist_service.py
│       └── playlist_sync_service.py
├── domain/
│   ├── entities/         # Domain objects
│   └── ports/            # Interfaces
├── infrastructure/
│   ├── clients/          # HTTP clients
│   ├── plugins/          # Service plugins
│   └── persistence/      # Database layer
```

---

## 2. Klassennamen

### 2.1 Entities (Domain Layer)

```python
# Pattern: PascalCase, Singular, kein Suffix
class Artist:
    pass

class Track:
    pass

class Playlist:
    pass

# ❌ FALSCH
class ArtistEntity:  # Redundant suffix
class Artists:  # Plural
```

### 2.2 DTOs (Data Transfer Objects)

```python
# Pattern: PascalCase + "DTO" Suffix
class ArtistDTO:
    pass

class TrackDTO:
    pass

class SearchResultDTO:
    pass

# ❌ FALSCH
class ArtistData:  # Unklar was es ist
class ArtistModel:  # Verwirrung mit SQLAlchemy Model
```

### 2.3 Models (SQLAlchemy)

```python
# Pattern: PascalCase + "Model" Suffix
class ArtistModel(Base):
    __tablename__ = "artists"

class TrackModel(Base):
    __tablename__ = "tracks"

# ❌ FALSCH
class Artist(Base):  # Konflikt mit Entity
class ArtistsTable(Base):  # Inkonsistent
```

### 2.4 Services

```python
# Pattern: PascalCase + "Service" Suffix
class ArtistService:
    pass

class PlaylistSyncService:
    pass

class LibraryScanService:
    pass

# ❌ FALSCH
class ArtistManager:  # Inkonsistent
class ArtistHelper:  # Zu generisch
```

### 2.5 Repositories

```python
# Pattern: PascalCase + "Repository" Suffix
class ArtistRepository:
    pass

class TrackRepository:
    pass

# ❌ FALSCH
class ArtistRepo:  # Abkürzung
class ArtistDAO:  # Anderes Pattern
```

### 2.6 Clients (Infrastructure)

```python
# Pattern: Service + "Client"
class SpotifyClient:
    pass

class DeezerClient:
    pass

class MusicBrainzClient:
    pass
```

### 2.7 Plugins

```python
# Pattern: Service + "Plugin"
class SpotifyPlugin:
    pass

class DeezerPlugin:
    pass

class TidalPlugin:
    pass
```

### 2.8 Workers

```python
# Pattern: Purpose + "Worker"
class TokenRefreshWorker:
    pass

class PlaylistSyncWorker:
    pass

class DownloadWorker:
    pass
```

### 2.9 Exceptions

```python
# Pattern: PascalCase + "Error"
class EntityNotFoundError(SoulSpotError):
    pass

class BusinessRuleViolation(SoulSpotError):  # Ausnahme: kein "Error"
    pass

class ExternalServiceError(SoulSpotError):
    pass

# ❌ FALSCH
class NotFound:  # Zu generisch
class ArtistNotFoundException:  # Zu spezifisch
```

### 2.10 Interfaces (Ports)

```python
# Pattern: "I" Prefix + PascalCase
class ISpotifyClient(Protocol):
    pass

class IArtistRepository(Protocol):
    pass

class ITokenStore(Protocol):
    pass

# ❌ FALSCH
class SpotifyClientInterface:  # Zu lang
class AbstractSpotifyClient:  # Java-Style
```

---

## 3. Funktions- und Methodennamen

### 3.1 Repository Methods

```python
class ArtistRepository:
    # GET patterns
    async def get_by_id(self, id: UUID) -> ArtistModel | None:
        """Get single by primary key."""
    
    async def get_by_spotify_uri(self, uri: str) -> ArtistModel | None:
        """Get single by unique field."""
    
    async def get_all(self, offset: int = 0, limit: int = 100) -> list[ArtistModel]:
        """Get paginated list."""
    
    async def get_by_genre(self, genre: str) -> list[ArtistModel]:
        """Get filtered list."""
    
    # COUNT
    async def count(self) -> int:
        """Count all."""
    
    async def count_by_genre(self, genre: str) -> int:
        """Count filtered."""
    
    # EXISTS
    async def exists(self, id: UUID) -> bool:
        """Check existence."""
    
    # CREATE/UPDATE/DELETE
    async def create(self, entity: ArtistModel) -> ArtistModel:
        """Create new."""
    
    async def update(self, entity: ArtistModel) -> ArtistModel:
        """Update existing."""
    
    async def delete(self, entity: ArtistModel) -> None:
        """Delete."""
    
    async def delete_by_id(self, id: UUID) -> bool:
        """Delete by ID, return success."""
```

**Pattern:**
- `get_by_{field}` - Einzelnes Objekt nach Feld
- `get_all` - Liste mit Pagination
- `get_by_{criteria}` - Gefilterte Liste
- `count` / `count_by_{criteria}` - Zählen
- `exists` - Boolean Check
- `create` / `update` / `delete` - CRUD

### 3.2 Service Methods

```python
class ArtistService:
    # GET/LIST patterns (verb_noun)
    async def get_artist(self, id: UUID) -> ArtistDTO:
        """Get single artist."""
    
    async def list_artists(self, page: int, page_size: int) -> PaginatedResponse:
        """List with pagination."""
    
    async def search_artists(self, query: str) -> list[ArtistDTO]:
        """Search by query."""
    
    # ACTION patterns (verb_noun)
    async def sync_artist(self, id: UUID) -> SyncResultDTO:
        """Sync with external service."""
    
    async def import_artist(self, spotify_id: str) -> ArtistDTO:
        """Import from external service."""
    
    async def delete_artist(self, id: UUID) -> None:
        """Delete artist."""
    
    async def enrich_artist(self, id: UUID) -> ArtistDTO:
        """Enrich with metadata."""
```

**Pattern:**
- `get_{entity}` - Einzelnes holen
- `list_{entities}` - Liste holen
- `search_{entities}` - Suchen
- `sync_{entity}` - Synchronisieren
- `import_{entity}` - Importieren
- `delete_{entity}` - Löschen
- `enrich_{entity}` - Anreichern

### 3.3 Private Methods

```python
class ArtistService:
    # Private helpers mit _ Prefix
    def _to_dto(self, model: ArtistModel) -> ArtistDTO:
        """Convert model to DTO."""
    
    async def _fetch_from_spotify(self, spotify_id: str) -> dict:
        """Internal Spotify fetch."""
    
    def _validate_artist(self, data: ArtistCreate) -> None:
        """Internal validation."""
```

### 3.4 Plugin Methods

```python
class SpotifyPlugin:
    # Capability methods
    async def get_artist(self, spotify_id: str) -> ArtistDTO:
        pass
    
    async def get_artist_albums(self, spotify_id: str) -> list[AlbumDTO]:
        pass
    
    async def search_artists(self, query: str) -> list[ArtistDTO]:
        pass
    
    # Internal conversion (private)
    def _convert_artist_to_dto(self, raw: dict) -> ArtistDTO:
        pass
    
    def _convert_album_to_dto(self, raw: dict) -> AlbumDTO:
        pass
```

**Pattern:**
- Public: `get_{entity}`, `search_{entities}`, `get_{entity}_{related}`
- Private: `_convert_{entity}_to_dto`

---

## 4. Variablen und Parameter

### 4.1 IDs

```python
# Pattern: {entity}_id für UUIDs
artist_id: UUID
track_id: UUID
playlist_id: UUID

# Pattern: spotify_{entity}_id für externe IDs
spotify_artist_id: str
spotify_track_id: str
deezer_artist_id: str

# ❌ FALSCH
id: UUID  # Zu generisch
artistId: UUID  # camelCase
artist_uuid: UUID  # Redundant
```

### 4.2 Collections

```python
# Pattern: Plural
artists: list[ArtistDTO]
tracks: list[TrackDTO]
genre_names: list[str]

# ❌ FALSCH
artist_list: list[ArtistDTO]  # Redundant
artistArray: list[ArtistDTO]  # camelCase
```

### 4.3 Booleans

```python
# Pattern: is_*, has_*, can_*
is_synced: bool
is_active: bool
has_albums: bool
has_spotify_uri: bool
can_download: bool

# ❌ FALSCH
synced: bool  # Unklar ob bool
active: bool  # Könnte auch str sein
```

### 4.4 Counts

```python
# Pattern: {entity}_count oder total_{entities}
track_count: int
total_tracks: int
album_count: int

# ❌ FALSCH
tracks_num: int  # Inkonsistent
numTracks: int  # camelCase
```

### 4.5 Timestamps

```python
# Pattern: {action}_at
created_at: datetime
updated_at: datetime
synced_at: datetime
deleted_at: datetime | None

# ❌ FALSCH
creation_date: datetime  # Inkonsistent
syncedTime: datetime  # camelCase
```

---

## 5. Constants

```python
# Pattern: UPPER_SNAKE_CASE
MAX_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 30
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"

# In Enums
class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

## 6. Async-Funktionen

**KEINE `_async` Suffixe!** Wir sind immer async.

```python
# ✅ RICHTIG
async def get_artist(self, artist_id: UUID) -> ArtistDTO:
    pass

async def delete_artist(self, artist_id: UUID) -> None:
    pass

# ❌ FALSCH
async def get_artist_async(self, artist_id: UUID) -> ArtistDTO:
    pass

async def delete_artist_async(self, artist_id: UUID) -> None:
    pass
```

**Ausnahme:** Wenn sync und async Varianten existieren:
```python
def get_config(self) -> Config:  # Sync
    pass

async def get_config_async(self) -> Config:  # Async alternative
    pass
```

---

## 7. Route Paths

```python
# Pattern: Plural, lowercase, kebab-case für multi-word
@router.get("/artists")
@router.get("/artists/{artist_id}")
@router.post("/artists/{artist_id}/sync")
@router.get("/new-releases")  # kebab-case
@router.get("/followed-artists")

# ❌ FALSCH
@router.get("/artist")  # Singular
@router.get("/Artist")  # PascalCase
@router.get("/new_releases")  # snake_case in URL
```

---

## 8. Database Table/Column Names

### Tables
```python
# Pattern: Plural, snake_case
__tablename__ = "artists"
__tablename__ = "tracks"
__tablename__ = "spotify_sessions"
__tablename__ = "download_tasks"

# ❌ FALSCH
__tablename__ = "Artist"  # Singular, PascalCase
__tablename__ = "tbl_artists"  # Prefix
```

### Columns
```python
# Pattern: snake_case
id = Column(UUID)
name = Column(String)
spotify_uri = Column(String)
created_at = Column(DateTime)
is_active = Column(Boolean)

# ❌ FALSCH
spotifyUri = Column(String)  # camelCase
createdAt = Column(DateTime)  # camelCase
```

---

## 9. Quick Reference Table

| What | Convention | Example |
|------|------------|---------|
| Files | snake_case | `artist_service.py` |
| Classes | PascalCase | `ArtistService` |
| Functions | snake_case | `get_artist` |
| Variables | snake_case | `artist_id` |
| Constants | UPPER_SNAKE_CASE | `MAX_PAGE_SIZE` |
| Interfaces | I-Prefix | `IArtistRepository` |
| DTOs | DTO-Suffix | `ArtistDTO` |
| Models | Model-Suffix | `ArtistModel` |
| Repos | Repository-Suffix | `ArtistRepository` |
| Services | Service-Suffix | `ArtistService` |
| Plugins | Plugin-Suffix | `SpotifyPlugin` |
| Workers | Worker-Suffix | `SyncWorker` |
| Exceptions | Error-Suffix | `EntityNotFoundError` |
| DB Tables | plural snake_case | `artists` |
| API Paths | plural kebab-case | `/new-releases` |

---

## 10. Zusammenfassung

```
┌─────────────────────────────────────────────────────────────────┐
│                         NAMING RULES                             │
├─────────────────────────────────────────────────────────────────┤
│  PascalCase  │ Classes, Enums, Type Aliases                     │
│  snake_case  │ Functions, Variables, Files, DB Tables           │
│  UPPER_CASE  │ Constants, Enum Values                           │
│  kebab-case  │ API URL Paths only                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         SUFFIXES                                 │
├─────────────────────────────────────────────────────────────────┤
│  -Service    │ Business logic classes                           │
│  -Repository │ Data access classes                              │
│  -DTO        │ Data transfer objects                            │
│  -Model      │ SQLAlchemy ORM classes                           │
│  -Plugin     │ External service adapters                        │
│  -Worker     │ Background task handlers                         │
│  -Client     │ HTTP client wrappers                             │
│  -Error      │ Custom exceptions                                │
│  I-          │ Interface/Protocol definitions                   │
└─────────────────────────────────────────────────────────────────┘
```
