# SoulSpot API Response Standards

> **PFLICHTLEKTÜRE** für alle, die API-Endpoints schreiben.

---

## 1. Die goldene Regel

```
Alle Endpoints MÜSSEN typisierte Pydantic-Models zurückgeben.
```

**VERBOTEN:**
- ❌ `-> dict[str, Any]`
- ❌ `-> Any`
- ❌ `-> None` ohne Statuscode-Spezifikation
- ❌ Inkonsistente Response-Strukturen

**ERLAUBT:**
- ✅ `-> ArtistResponse`
- ✅ `-> PaginatedResponse[ArtistDTO]`
- ✅ `-> StatusResponse`

---

## 2. Standard Response Models

### 2.1 Success Response (für Aktionen)

```python
# src/soulspot/api/schemas/responses.py

from pydantic import BaseModel
from datetime import datetime

class StatusResponse(BaseModel):
    """Standard response for actions without data return."""
    status: str  # "success", "created", "deleted", etc.
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Verwendung
@router.delete("/artists/{artist_id}")
async def delete_artist(artist_id: UUID) -> StatusResponse:
    await service.delete(artist_id)
    return StatusResponse(status="deleted", message=f"Artist {artist_id} deleted")
```

### 2.2 Entity Response (für einzelne Objekte)

```python
# Entity-spezifische Responses basieren auf DTOs
class ArtistResponse(BaseModel):
    """Response for single artist."""
    id: UUID
    name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    image_url: str | None = None
    genres: list[str] = []
    
    model_config = ConfigDict(from_attributes=True)

# Verwendung
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    return await service.get_artist(artist_id)
```

### 2.3 Paginated Response (für Listen)

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
    
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size

# Verwendung
@router.get("/artists")
async def list_artists(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ArtistResponse]:
    return await service.list_artists(page=page, page_size=page_size)
```

### 2.4 Error Response (für Fehler)

```python
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str  # Exception class name
    message: str  # Human-readable message
    status: int  # HTTP status code
    details: dict[str, Any] | None = None  # Optional additional info
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Wird von Global Exception Handler verwendet
# Nicht direkt in Endpoints verwenden
```

---

## 3. Pagination Standard

### 3.1 Query Parameters

```python
# Standard Pagination Query Parameters
page: int = Query(1, ge=1, description="Page number (1-indexed)")
page_size: int = Query(20, ge=1, le=100, description="Items per page")

# Optional: Sort Parameters
sort_by: str = Query("created_at", description="Field to sort by")
sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction")
```

### 3.2 Response Structure

```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "has_next": true,
  "has_previous": false
}
```

### 3.3 Implementation Pattern

```python
# In Service
async def list_artists(
    self,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[ArtistDTO]:
    offset = (page - 1) * page_size
    
    total = await self._repo.count()
    items = await self._repo.get_all(offset=offset, limit=page_size)
    
    return PaginatedResponse(
        items=[self._to_dto(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_previous=page > 1,
    )
```

---

## 4. Collection Responses (ohne Pagination)

Für kleine, vollständige Listen:

```python
class ArtistListResponse(BaseModel):
    """Response for small artist lists."""
    items: list[ArtistResponse]
    count: int

# Verwendung für bekannt kleine Listen
@router.get("/artists/{artist_id}/genres")
async def get_artist_genres(artist_id: UUID) -> GenreListResponse:
    genres = await service.get_artist_genres(artist_id)
    return GenreListResponse(items=genres, count=len(genres))
```

---

## 5. Async Operation Response

Für lang laufende Operationen:

```python
class AsyncOperationResponse(BaseModel):
    """Response for async/background operations."""
    operation_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    progress: int | None = None  # 0-100
    message: str | None = None
    result_url: str | None = None  # Where to fetch result

# Verwendung
@router.post("/library/scan")
async def start_scan() -> AsyncOperationResponse:
    operation_id = await service.start_scan()
    return AsyncOperationResponse(
        operation_id=operation_id,
        status="pending",
        message="Scan started",
    )

@router.get("/library/scan/{operation_id}")
async def get_scan_status(operation_id: UUID) -> AsyncOperationResponse:
    return await service.get_scan_status(operation_id)
```

---

## 6. Aggregate/Stats Response

Für Statistiken und Zusammenfassungen:

```python
class LibraryStatsResponse(BaseModel):
    """Library statistics response."""
    total_artists: int
    total_albums: int
    total_tracks: int
    total_size_bytes: int
    last_scan: datetime | None
    
class SyncStatsResponse(BaseModel):
    """Sync operation statistics."""
    items_processed: int
    items_added: int
    items_updated: int
    items_removed: int
    errors: int
    duration_seconds: float
```

---

## 7. HTTP Status Codes

| Operation | Success Code | Response Type |
|-----------|--------------|---------------|
| GET single | 200 | EntityResponse |
| GET list | 200 | PaginatedResponse |
| POST create | 201 | EntityResponse |
| POST action | 200 | StatusResponse |
| PUT update | 200 | EntityResponse |
| DELETE | 200 | StatusResponse |
| Async start | 202 | AsyncOperationResponse |

### Implementation

```python
from fastapi import status

@router.post("/artists", status_code=status.HTTP_201_CREATED)
async def create_artist(data: ArtistCreate) -> ArtistResponse:
    return await service.create(data)

@router.post("/artists/{artist_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_artist(artist_id: UUID) -> AsyncOperationResponse:
    return await service.start_sync(artist_id)
```

---

## 8. Konsistente Feldnamen

| Konzept | Feldname | Typ | Beispiel |
|---------|----------|-----|----------|
| Primärschlüssel | `id` | UUID | `"550e8400-e29b-41d4-a716-446655440000"` |
| Spotify ID | `spotify_id` | str \| None | `"4Z8W4fKeB5YxbusRsdQVPb"` |
| Deezer ID | `deezer_id` | str \| None | `"12345"` |
| Name | `name` | str | `"Artist Name"` |
| Titel | `title` | str | `"Album Title"` |
| Zeitstempel | `created_at`, `updated_at` | datetime | ISO 8601 |
| Bild-URL | `image_url` | str \| None | URL |
| Genres | `genres` | list[str] | `["rock", "alternative"]` |
| Zähler | `total`, `count` | int | `42` |
| Boolean | `is_*`, `has_*` | bool | `is_synced`, `has_albums` |

---

## 9. Anti-Patterns

### ❌ Dict statt Pydantic
```python
# FALSCH
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> dict[str, Any]:
    return {"name": artist.name, "id": str(artist.id)}

# RICHTIG
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    return ArtistResponse.model_validate(artist)
```

### ❌ Inkonsistente Pagination
```python
# FALSCH - Verschiedene Strukturen
{"data": [...], "meta": {"total": 100}}  # Route A
{"items": [...], "count": 100}  # Route B
{"results": [...], "pagination": {...}}  # Route C

# RICHTIG - Eine Struktur
{"items": [...], "total": 100, "page": 1, "page_size": 20, ...}
```

### ❌ Fehlende Typisierung
```python
# FALSCH
@router.get("/stats")
async def get_stats():
    return service.get_stats()

# RICHTIG
@router.get("/stats")
async def get_stats() -> LibraryStatsResponse:
    return await service.get_stats()
```

### ❌ Raw Exception Messages
```python
# FALSCH
except Exception as e:
    return {"error": str(e)}

# RICHTIG - Use Global Exception Handler
# Exceptions werden automatisch zu ErrorResponse konvertiert
```

---

## 10. OpenAPI Documentation

Alle Responses sollten dokumentiert sein:

```python
from fastapi import APIRouter

router = APIRouter(
    prefix="/artists",
    tags=["artists"],
    responses={
        404: {"model": ErrorResponse, "description": "Artist not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)

@router.get(
    "/{artist_id}",
    response_model=ArtistResponse,
    summary="Get artist by ID",
    description="Retrieve detailed information about a specific artist.",
    responses={
        200: {"description": "Artist found"},
        404: {"description": "Artist not found"},
    },
)
async def get_artist(artist_id: UUID) -> ArtistResponse:
    """Get artist details by ID."""
    return await service.get_artist(artist_id)
```

---

## 11. Checkliste für neue Endpoints

- [ ] Return type ist Pydantic Model (nicht dict/Any)
- [ ] HTTP Status Code explizit gesetzt (für non-200)
- [ ] Pagination verwendet `PaginatedResponse[T]`
- [ ] Feldnamen folgen Standard (id, spotify_id, created_at, etc.)
- [ ] OpenAPI responses dokumentiert
- [ ] Error responses nutzen Global Handler
- [ ] Async operations nutzen `AsyncOperationResponse`

---

## 12. Response Model Exports

```python
# src/soulspot/api/schemas/__init__.py

from .responses import (
    StatusResponse,
    ErrorResponse,
    PaginatedResponse,
    AsyncOperationResponse,
)
from .artists import ArtistResponse, ArtistCreate, ArtistUpdate
from .albums import AlbumResponse, AlbumCreate
from .tracks import TrackResponse
from .playlists import PlaylistResponse, PlaylistCreate

__all__ = [
    # Base responses
    "StatusResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "AsyncOperationResponse",
    # Entity responses
    "ArtistResponse",
    "ArtistCreate",
    "ArtistUpdate",
    "AlbumResponse",
    "AlbumCreate",
    "TrackResponse",
    "PlaylistResponse",
    "PlaylistCreate",
]
```

---

## 13. Zusammenfassung

```
┌─────────────────────────────────────────────────────────────────┐
│                    STANDARD RESPONSE TYPES                       │
├─────────────────────────────────────────────────────────────────┤
│  StatusResponse         │ Für Aktionen ohne Datenrückgabe       │
│  EntityResponse         │ Für einzelne Objekte                  │
│  PaginatedResponse[T]   │ Für Listen mit Pagination             │
│  CollectionResponse     │ Für kleine, vollständige Listen       │
│  AsyncOperationResponse │ Für async/background Operationen      │
│  ErrorResponse          │ Für Fehlermeldungen (via Handler)     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    VERBOTEN                                      │
├─────────────────────────────────────────────────────────────────┤
│  ❌ dict[str, Any]      │ Keine Typsicherheit                   │
│  ❌ Any                 │ Keine Dokumentation                   │
│  ❌ Inkonsistente Namen │ Verwirrung für API-Nutzer             │
│  ❌ Raw Exceptions      │ Security Risk                         │
└─────────────────────────────────────────────────────────────────┘
```
