# SoulSpot Error Handling Standards

> **Required Reading for All Error Handling Code**

## Overview

SoulSpot uses a **domain-driven error handling** approach:
- Services throw **Domain Exceptions**
- Routes catch and map to **HTTP responses**
- Never throw HTTP exceptions from services
- Global exception handler for unexpected errors

---

## The Golden Rule

```
Services throw Domain Exceptions → Routes catch and map to HTTP
```

**FORBIDDEN:**
- ❌ `raise ValueError("...")` in services
- ❌ `raise HTTPException(...)` in services
- ❌ `except Exception as e:` in routes (too broad)
- ❌ `raise RuntimeError(...)` anywhere

**ALLOWED:**
- ✅ `raise EntityNotFoundError(...)` in services
- ✅ `raise BusinessRuleViolation(...)` in services
- ✅ `except EntityNotFoundError:` in routes
- ✅ Global exception handler for unexpected errors

---

## Exception Hierarchy

**Source**: `src/soulspot/domain/exceptions/__init__.py`

```python
# Base Exception - never throw directly
class DomainException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

# Entity not found (→ HTTP 404)
class EntityNotFoundException(DomainException):
    """Entity was not found in database or external service."""
    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(f"{entity_type} with id {entity_id} not found")
        self.entity_type = entity_type
        self.entity_id = entity_id

# Alias for consistent naming
EntityNotFoundError = EntityNotFoundException

# Business rule violated (→ HTTP 400)
class BusinessRuleViolation(DomainException):
    """A business rule was violated."""
    pass

# External service error (→ HTTP 502)
class ExternalServiceError(DomainException):
    """External service (Spotify, Deezer, etc.) returned an error."""
    pass

# Authentication failed (→ HTTP 401)
class AuthenticationError(DomainException):
    """User is not authenticated or token expired."""
    pass

# Authorization failed (→ HTTP 403)
class AuthorizationError(DomainException):
    """User is authenticated but not authorized for this action."""
    pass

# Validation error (→ HTTP 422)
class ValidationError(DomainException):
    """Input validation failed."""
    pass

# Rate limit reached (→ HTTP 429)
class RateLimitExceededError(DomainException):
    """External service rate limit was exceeded."""
    pass

# Configuration error (→ HTTP 503)
class ConfigurationError(DomainException):
    """Application misconfiguration."""
    pass

# Duplicate entity (→ HTTP 409)
class DuplicateEntityException(DomainException):
    """Entity already exists."""
    pass
```

---

## Exception → HTTP Mapping

| Domain Exception | HTTP Status | When to Use |
|------------------|-------------|-------------|
| `EntityNotFoundException` / `EntityNotFoundError` | 404 | Artist/Track/Playlist not found |
| `BusinessRuleViolation` | 400 | Invalid operation (e.g., duplicate playlist) |
| `ExternalServiceError` | 502 | Spotify/Deezer API error |
| `AuthenticationError` | 401 | Not logged in, token expired |
| `AuthorizationError` | 403 | Logged in but no permission |
| `ValidationException` / `ValidationError` | 422 | Invalid input data |
| `RateLimitExceededError` | 429 | API limit reached |
| `ConfigurationError` | 503 | App config missing/invalid |
| `DuplicateEntityException` | 409 | Entity already exists |
| Unexpected Exception | 500 | Anything else (bugs) |

---

## Service Layer Pattern

### Correct Pattern

```python
# ✅ RIGHT: Throw domain exceptions
from soulspot.domain.exceptions import EntityNotFoundError, BusinessRuleViolation

class ArtistService:
    async def get_artist(self, artist_id: UUID) -> ArtistDTO:
        """Get artist by ID.
        
        Raises:
            EntityNotFoundError: Artist not found in database
        """
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            raise EntityNotFoundError("Artist", artist_id)
        return self._to_dto(artist)
    
    async def sync_artist(self, artist_id: UUID) -> ArtistDTO:
        """Sync artist with Spotify.
        
        Raises:
            EntityNotFoundError: Artist not found
            BusinessRuleViolation: Artist has no Spotify URI
            ExternalServiceError: Spotify API failed
        """
        artist = await self.get_artist(artist_id)
        
        if not artist.spotify_id:
            raise BusinessRuleViolation("Artist has no Spotify URI - cannot sync")
        
        try:
            spotify_data = await self._spotify.get_artist(artist.spotify_id)
        except SpotifyApiError as e:
            raise ExternalServiceError(f"Spotify API failed: {e}")
        
        # ... rest of sync logic
```

### Wrong Patterns

```python
# ❌ WRONG: ValueError/RuntimeError
class ArtistService:
    async def sync_artist(self, artist_id: UUID) -> ArtistDTO:
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            raise ValueError("Artist not found")  # ❌ Don't use generic exceptions
        
        if not artist.spotify_id:
            raise RuntimeError("No Spotify URI")  # ❌ Don't use RuntimeError
        
        # ...

# ❌ WRONG: HTTPException in service
class ArtistService:
    async def get_artist(self, artist_id: UUID) -> ArtistDTO:
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            raise HTTPException(status_code=404, detail="Not found")  # ❌ Don't use HTTP exceptions
        return artist
```

---

## Route Layer Pattern

### Correct Pattern

```python
# ✅ RIGHT: Catch domain exceptions, map to HTTP
from fastapi import HTTPException
from soulspot.domain.exceptions import EntityNotFoundError, BusinessRuleViolation

@router.get("/artists/{artist_id}")
async def get_artist(
    artist_id: UUID,
    service: ArtistService = Depends(get_artist_service),
):
    try:
        return await service.get_artist(artist_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolation as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/artists/{artist_id}/sync")
async def sync_artist(
    artist_id: UUID,
    service: ArtistService = Depends(get_artist_service),
):
    try:
        return await service.sync_artist(artist_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Global Exception Handler

```python
# src/soulspot/main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from soulspot.domain.exceptions import DomainException

app = FastAPI()

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    """Global handler for all domain exceptions."""
    # Map to appropriate HTTP status
    status_code = 500  # Default
    if isinstance(exc, EntityNotFoundException):
        status_code = 404
    elif isinstance(exc, BusinessRuleViolation):
        status_code = 400
    elif isinstance(exc, ExternalServiceError):
        status_code = 502
    elif isinstance(exc, AuthenticationError):
        status_code = 401
    elif isinstance(exc, AuthorizationError):
        status_code = 403
    elif isinstance(exc, ValidationError):
        status_code = 422
    elif isinstance(exc, RateLimitExceededError):
        status_code = 429
    elif isinstance(exc, ConfigurationError):
        status_code = 503
    elif isinstance(exc, DuplicateEntityException):
        status_code = 409
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
    )
```

**Benefit**: Routes don't need to catch every exception type individually.

---

## Plugin Error Handling

### Plugin Exception

```python
# src/soulspot/domain/ports/plugin.py

class PluginError(DomainException):
    """Error from external service plugin."""
    def __init__(
        self,
        service: ServiceType,
        message: str,
        original_error: Exception | None = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.service = service
        self.original_error = original_error
        self.recoverable = recoverable
```

### Plugin Error Pattern

```python
# src/soulspot/infrastructure/plugins/spotify_plugin.py

class SpotifyPlugin:
    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Get artist from Spotify.
        
        Raises:
            PluginError: Spotify API error
        """
        try:
            data = await self._client.get_artist(artist_id)
            return self._convert_artist(data)
        except SpotifyApiError as e:
            if e.status_code == 404:
                raise PluginError(
                    ServiceType.SPOTIFY,
                    f"Artist {artist_id} not found",
                    original_error=e,
                    recoverable=False,
                )
            elif e.status_code == 429:
                raise PluginError(
                    ServiceType.SPOTIFY,
                    "Rate limit exceeded",
                    original_error=e,
                    recoverable=True,
                )
            else:
                raise PluginError(
                    ServiceType.SPOTIFY,
                    f"Spotify API error: {e}",
                    original_error=e,
                    recoverable=True,
                )
```

---

## Error Response Format

### Standard Error Response

```json
{
    "detail": "Artist with id 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

### Validation Error Response

```json
{
    "detail": [
        {
            "loc": ["body", "name"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

---

## Common Error Scenarios

### 1. Entity Not Found

```python
# Service
artist = await self._repo.get_by_id(artist_id)
if not artist:
    raise EntityNotFoundError("Artist", artist_id)

# Route (automatic via global handler)
# Returns: HTTP 404 {"detail": "Artist with id ... not found"}
```

### 2. Business Rule Violation

```python
# Service
if playlist.owner_id != user_id:
    raise BusinessRuleViolation("Cannot delete playlist owned by another user")

# Route (automatic via global handler)
# Returns: HTTP 400 {"detail": "Cannot delete playlist owned by another user"}
```

### 3. External Service Failure

```python
# Service
try:
    data = await self._spotify.get_artist(artist_id)
except PluginError as e:
    raise ExternalServiceError(f"Spotify: {e.message}")

# Route (automatic via global handler)
# Returns: HTTP 502 {"detail": "Spotify: Rate limit exceeded"}
```

### 4. Authentication Required

```python
# Service
if not self._spotify.is_authenticated:
    raise AuthenticationError("Spotify authentication required")

# Route (automatic via global handler)
# Returns: HTTP 401 {"detail": "Spotify authentication required"}
```

---

## Summary

**Error Handling Flow**:
```
┌─────────────────────────────────────────────────────────────┐
│ Service Layer                                               │
│  - Throw domain exceptions                                  │
│  - Document exceptions in docstrings                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Route Layer                                                 │
│  - Catch domain exceptions (optional with global handler)   │
│  - Map to HTTP responses                                    │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Global Exception Handler                                    │
│  - Catch uncaught domain exceptions                         │
│  - Map to HTTP status codes                                 │
│  - Log unexpected errors                                    │
└─────────────────────────────────────────────────────────────┘
```

**Best Practices**:
1. **Use domain exceptions** in services, never HTTP exceptions
2. **Document exceptions** in service method docstrings
3. **Be specific** - Use appropriate exception types
4. **Include context** - Add entity type and ID to error messages
5. **Log unexpected errors** - Global handler logs 500s
6. **Preserve original error** - PluginError includes original_error

---

## See Also

- [Domain Exceptions](../../05-development/domain-exceptions.md) - Exception class reference
- [API Error Responses](../03-api-reference/README.md#error-handling) - API error format
- [Plugin System](./plugin-system.md) - Plugin error patterns

---

**Document Status**: Migrated from `docs/architecture/ERROR_HANDLING.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/domain/exceptions/__init__.py` - Exception definitions
- `src/soulspot/main.py` - Global exception handler
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - Plugin error examples
