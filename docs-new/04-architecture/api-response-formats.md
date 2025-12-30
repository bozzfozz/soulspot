# API Response Formats

**Category:** Architecture  
**Last Updated:** 2024-01-XX  
**Related Docs:** [Error Handling](./error-handling.md) | [Data Standards](./data-standards.md)

---

## Overview

All SoulSpot API endpoints **MUST** return typed Pydantic models for consistency, type safety, and automatic OpenAPI documentation generation.

**Golden Rule:**
```python
# ✅ ALWAYS return typed Pydantic models
async def get_artist(artist_id: UUID) -> ArtistResponse:
    ...

# ❌ NEVER return untyped dicts
async def get_artist(artist_id: UUID) -> dict[str, Any]:  # FORBIDDEN!
    ...
```

---

## Standard Response Models

### StatusResponse (Actions Without Data)

For operations that don't return entity data (create, delete, update acknowledgements):

```python
# src/soulspot/api/schemas/responses.py

from pydantic import BaseModel, Field
from datetime import datetime, timezone

class StatusResponse(BaseModel):
    """Standard response for actions without data return."""
    status: str  # "success", "created", "deleted", "updated"
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Usage
@router.delete("/artists/{artist_id}")
async def delete_artist(artist_id: UUID) -> StatusResponse:
    await service.delete_artist(artist_id)
    return StatusResponse(
        status="deleted",
        message=f"Artist {artist_id} deleted successfully"
    )
```

**When to use:**
- DELETE operations (resource deleted)
- POST operations without returning created entity
- PUT/PATCH operations confirming update
- Trigger endpoints (job started, worker restarted)

---

### Entity Response (Single Objects)

For returning single entities:

```python
class ArtistResponse(BaseModel):
    """Response for single artist."""
    id: UUID
    name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    musicbrainz_id: str | None = None
    image_url: str | None = None
    genres: list[str] = []
    follower_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)

# Usage
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    artist = await service.get_artist(artist_id)
    return ArtistResponse.model_validate(artist)
```

**Pattern:**
- Entity-specific response models (ArtistResponse, AlbumResponse, TrackResponse)
- Based on DTOs with presentation-layer additions (URLs, computed fields)
- Use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility
- Use `model_validate()` for DTO/Entity conversion

**Source:** `src/soulspot/api/schemas/responses.py`

---

### PaginatedResponse (Lists)

For returning paginated lists:

```python
from typing import Generic, TypeVar
from pydantic import BaseModel, computed_field

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response for lists."""
    items: list[T]
    total: int
    page: int
    page_size: int
    
    @computed_field
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page * self.page_size < self.total
    
    @computed_field
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1
    
    @computed_field
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size

# Usage
@router.get("/artists")
async def list_artists(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ArtistResponse]:
    result = await service.list_artists(page=page, page_size=page_size)
    return PaginatedResponse(
        items=[ArtistResponse.model_validate(a) for a in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )
```

**Features:**
- Generic type parameter for item type
- Computed fields for navigation (has_next, has_previous, total_pages)
- Standard pagination parameters (page, page_size)
- Total count for UI progress indicators

**Source:** `src/soulspot/api/schemas/responses.py` (lines 45-80)

---

### ErrorResponse (Errors)

For error responses (handled by global exception handler):

```python
class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str
    error_type: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Automatic conversion via global handler
@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=exc.http_status_code,
        content=ErrorResponse(
            detail=str(exc),
            error_type=exc.__class__.__name__,
        ).model_dump()
    )
```

**When used:**
- Automatically for all DomainException subclasses
- Manually for validation errors
- 4xx/5xx HTTP errors

**Source:** `src/soulspot/main.py` (global exception handler)

---

## Response Type Conventions

### Collection Endpoints

```python
# List all (paginated)
@router.get("/artists")
async def list_artists(...) -> PaginatedResponse[ArtistResponse]:
    ...

# List related entities (paginated)
@router.get("/artists/{artist_id}/albums")
async def list_artist_albums(...) -> PaginatedResponse[AlbumResponse]:
    ...

# Search (paginated)
@router.get("/search/artists")
async def search_artists(...) -> PaginatedResponse[ArtistResponse]:
    ...
```

**Always paginate** collection endpoints to prevent performance issues.

---

### Single Entity Endpoints

```python
# Get by ID
@router.get("/artists/{artist_id}")
async def get_artist(...) -> ArtistResponse:
    ...

# Create (return created entity)
@router.post("/artists")
async def create_artist(...) -> ArtistResponse:
    ...

# Update (return updated entity)
@router.put("/artists/{artist_id}")
async def update_artist(...) -> ArtistResponse:
    ...
```

**Return full entity** after mutations for UI state updates.

---

### Action Endpoints

```python
# Delete (return status)
@router.delete("/artists/{artist_id}")
async def delete_artist(...) -> StatusResponse:
    ...

# Trigger job (return status)
@router.post("/downloads/trigger")
async def trigger_download(...) -> StatusResponse:
    ...

# Import/Export (return status)
@router.post("/library/import")
async def import_library(...) -> StatusResponse:
    ...
```

**Return StatusResponse** for operations without meaningful entity data.

---

## Nested Resources

For nested/related entities:

```python
class AlbumDetailResponse(BaseModel):
    """Album with nested tracks."""
    id: UUID
    title: str
    artist: ArtistResponse  # Nested artist
    tracks: list[TrackResponse]  # Nested tracks
    release_date: date | None = None
    artwork_url: str | None = None

# Usage
@router.get("/albums/{album_id}/details")
async def get_album_details(album_id: UUID) -> AlbumDetailResponse:
    ...
```

**Guidelines:**
- Use nested responses sparingly (increases payload size)
- Prefer `/albums/{id}` + separate `/albums/{id}/tracks` for flexibility
- Nest only for common use cases (album with artist, playlist with tracks)

**Source:** `src/soulspot/api/schemas/responses.py`

---

## Status Codes by Operation

| Operation | Success Code | Response Type | Example |
|-----------|--------------|---------------|---------|
| **GET** (single) | 200 OK | EntityResponse | `ArtistResponse` |
| **GET** (list) | 200 OK | PaginatedResponse | `PaginatedResponse[ArtistResponse]` |
| **POST** (create) | 201 Created | EntityResponse | `ArtistResponse` |
| **POST** (action) | 200 OK | StatusResponse | `StatusResponse(status="triggered")` |
| **PUT** (replace) | 200 OK | EntityResponse | `ArtistResponse` |
| **PATCH** (update) | 200 OK | EntityResponse | `ArtistResponse` |
| **DELETE** | 204 No Content | None | (empty body) |

**Note:** DELETE endpoints return `204 No Content` with empty body, not StatusResponse.

---

## HTMX Partial Responses

For HTMX requests (detected via `HX-Request` header):

```python
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@router.get("/artists/{artist_id}")
async def get_artist(
    request: Request,
    artist_id: UUID,
) -> ArtistResponse | HTMLResponse:
    """Return JSON for API, HTML partial for HTMX."""
    
    artist = await service.get_artist(artist_id)
    
    # HTMX request - return HTML partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/artist_card.html",
            {"request": request, "artist": artist}
        )
    
    # API request - return JSON
    return ArtistResponse.model_validate(artist)
```

**Pattern:**
- Check `HX-Request` header
- Return HTML partial for HTMX
- Return JSON for API clients

**Source:** `src/soulspot/api/routers/library.py` (lines 200-250)

---

## Response Model Best Practices

### 1. Always Use Type Annotations

```python
# ✅ CORRECT - Explicit return type
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    ...

# ❌ WRONG - No type annotation
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID):
    ...
```

---

### 2. Use DTOs for Data Transfer

```python
# ✅ CORRECT - Service returns DTO, route converts to response
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    artist_dto = await service.get_artist(artist_id)  # Returns DTO
    return ArtistResponse.model_validate(artist_dto)

# ❌ WRONG - Service returns response model (couples layers!)
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    return await service.get_artist(artist_id)  # Service shouldn't know about API models!
```

---

### 3. Use Computed Fields for Derived Data

```python
class TrackResponse(BaseModel):
    id: UUID
    title: str
    duration_ms: int
    
    @computed_field
    @property
    def duration_formatted(self) -> str:
        """Human-readable duration (MM:SS)."""
        minutes = self.duration_ms // 60000
        seconds = (self.duration_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"
```

**Benefits:**
- Keeps DTOs simple (no presentation logic)
- Computed on serialization (not stored)
- Easy to change without DB migrations

---

### 4. Use Field Aliases for API Naming

```python
class ArtistResponse(BaseModel):
    id: UUID
    name: str
    spotify_id: str | None = Field(None, alias="spotifyId")  # camelCase for frontend
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,  # Accept both "spotify_id" and "spotifyId"
    )
```

---

## Common Patterns

### Empty List vs. 404

```python
# ✅ CORRECT - Empty list for no results (200 OK)
@router.get("/artists/{artist_id}/albums")
async def list_artist_albums(artist_id: UUID) -> PaginatedResponse[AlbumResponse]:
    albums = await service.get_artist_albums(artist_id)
    return PaginatedResponse(items=albums, total=0, page=1, page_size=20)

# ❌ WRONG - 404 for no results
@router.get("/artists/{artist_id}/albums")
async def list_artist_albums(artist_id: UUID) -> PaginatedResponse[AlbumResponse]:
    albums = await service.get_artist_albums(artist_id)
    if not albums:
        raise HTTPException(404, "No albums found")  # Wrong!
    return PaginatedResponse(items=albums, total=len(albums), page=1, page_size=20)
```

**Rule:** Collections return empty lists (200 OK), not 404. Only single entities return 404.

---

### Optional Fields

```python
class ArtistResponse(BaseModel):
    id: UUID
    name: str
    image_url: str | None = None  # Optional field with default
    genres: list[str] = []  # Optional list with empty default
```

**Guidelines:**
- Use `| None = None` for truly optional fields
- Use `= []` for optional lists (better than `| None`)
- Use `= {}` for optional dicts (better than `| None`)

---

## Anti-Patterns to Avoid

### ❌ Returning Dicts

```python
# ❌ WRONG - Untyped dict
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> dict[str, Any]:
    return {"id": str(artist_id), "name": "Artist Name"}

# ✅ CORRECT - Typed response model
@router.get("/artists/{artist_id}")
async def get_artist(artist_id: UUID) -> ArtistResponse:
    return ArtistResponse(id=artist_id, name="Artist Name")
```

---

### ❌ Inconsistent Response Structures

```python
# ❌ WRONG - Different structures for same endpoint
@router.get("/artists")
async def list_artists(format: str = "json"):
    if format == "json":
        return {"items": [...], "total": 10}
    else:
        return {"artists": [...], "count": 10}  # Different keys!

# ✅ CORRECT - Consistent structure always
@router.get("/artists")
async def list_artists() -> PaginatedResponse[ArtistResponse]:
    return PaginatedResponse(items=[...], total=10, page=1, page_size=20)
```

---

### ❌ Mixing Entity Types in Lists

```python
# ❌ WRONG - Mixed types in list
@router.get("/search")
async def search(query: str) -> dict[str, Any]:
    return {
        "results": [
            {"type": "artist", "name": "Artist 1"},
            {"type": "album", "title": "Album 1"},  # Different fields!
        ]
    }

# ✅ CORRECT - Union type or separate lists
from typing import Union

class SearchResult(BaseModel):
    artists: list[ArtistResponse] = []
    albums: list[AlbumResponse] = []
    tracks: list[TrackResponse] = []

@router.get("/search")
async def search(query: str) -> SearchResult:
    ...
```

---

## Testing Response Models

```python
# tests/unit/api/test_responses.py

def test_artist_response_validation():
    """Test ArtistResponse model validation."""
    # Valid data
    data = {
        "id": uuid4(),
        "name": "Artist Name",
        "spotify_id": "abc123",
    }
    response = ArtistResponse(**data)
    assert response.name == "Artist Name"
    
    # Missing required field
    with pytest.raises(ValidationError):
        ArtistResponse(id=uuid4())  # Missing "name"

def test_paginated_response_computed_fields():
    """Test PaginatedResponse computed properties."""
    response = PaginatedResponse[ArtistResponse](
        items=[],
        total=100,
        page=2,
        page_size=20,
    )
    
    assert response.has_next is True
    assert response.has_previous is True
    assert response.total_pages == 5
```

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    API RESPONSE HIERARCHY                        │
├─────────────────────────────────────────────────────────────────┤
│  StatusResponse          │ Actions (create, delete, trigger)    │
│  EntityResponse          │ Single objects (get, update)         │
│  PaginatedResponse[T]    │ Lists (list, search)                 │
│  ErrorResponse           │ Errors (4xx, 5xx)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE GUIDELINES                           │
├─────────────────────────────────────────────────────────────────┤
│  ✅ ALWAYS   │ Use typed Pydantic models                        │
│  ✅ ALWAYS   │ Return full entity after mutations               │
│  ✅ ALWAYS   │ Paginate collection endpoints                    │
│  ✅ ALWAYS   │ Use computed fields for derived data             │
│  ❌ NEVER    │ Return dict[str, Any] or untyped dicts          │
│  ❌ NEVER    │ Return 404 for empty collections                │
│  ❌ NEVER    │ Mix entity types in single list                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- **[Error Handling](./error-handling.md)** - ErrorResponse, exception mapping
- **[Data Standards](./data-standards.md)** - DTO definitions
- **[Data Layer Patterns](./data-layer-patterns.md)** - Service → Response conversion

---

**Last Validated:** 2024-01-XX (against current implementation)  
**Source Files:** `src/soulspot/api/schemas/responses.py`, router implementations
