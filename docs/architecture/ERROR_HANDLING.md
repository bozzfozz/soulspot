# SoulSpot Error Handling Standards

> **PFLICHTLEKTÜRE** für alle, die Error Handling schreiben oder ändern.

---

## 1. Die goldene Regel

```
Services werfen Domain Exceptions → Routes fangen und mappen zu HTTP
```

**VERBOTEN:**
- ❌ `raise ValueError("...")` in Services
- ❌ `raise HTTPException(...)` in Services
- ❌ `except Exception as e:` in Routes (zu breit)
- ❌ `raise RuntimeError(...)` irgendwo

**ERLAUBT:**
- ✅ `raise EntityNotFoundError(...)` in Services
- ✅ `raise BusinessRuleViolation(...)` in Services
- ✅ `except EntityNotFoundError:` in Routes
- ✅ Global Exception Handler für unerwartete Fehler

---

## 2. Exception-Hierarchie

```
src/soulspot/domain/exceptions/__init__.py  ← EINZIGE QUELLE FÜR EXCEPTIONS
```

```python
# Base Exception - nie direkt werfen
class DomainException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

# Entity existiert nicht (→ HTTP 404)
class EntityNotFoundException(DomainException):
    """Entity was not found in database or external service."""
    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(f"{entity_type} with id {entity_id} not found")
        self.entity_type = entity_type
        self.entity_id = entity_id

# Alias für konsistente Namensgebung
EntityNotFoundError = EntityNotFoundException

# Business-Regel verletzt (→ HTTP 400)
class BusinessRuleViolation(DomainException):
    """A business rule was violated."""
    pass

# Externe Service-Fehler (→ HTTP 502)
class ExternalServiceError(DomainException):
    """External service (Spotify, Deezer, etc.) returned an error."""
    pass

# Authentifizierung fehlgeschlagen (→ HTTP 401)
class AuthenticationError(DomainException):
    """User is not authenticated or token expired."""
    pass

# Autorisierung fehlgeschlagen (→ HTTP 403)
class AuthorizationError(DomainException):
    """User is authenticated but not authorized for this action."""
    pass

# Validierungsfehler (→ HTTP 422)
class ValidationError(DomainException):
    """Input validation failed."""
    pass

# Rate Limit erreicht (→ HTTP 429)
class RateLimitExceededError(DomainException):
    """External service rate limit was exceeded."""
    pass

# Konfigurationsfehler (→ HTTP 503)
class ConfigurationError(DomainException):
    """Application misconfiguration."""
    pass
```

---

## 3. Exception → HTTP Mapping

| Domain Exception | HTTP Status | Wann verwenden |
|------------------|-------------|----------------|
| `EntityNotFoundException` / `EntityNotFoundError` | 404 | Artist/Track/Playlist nicht gefunden |
| `BusinessRuleViolation` | 400 | Ungültige Operation (z.B. doppelte Playlist) |
| `ExternalServiceError` | 502 | Spotify/Deezer API-Fehler |
| `AuthenticationError` | 401 | Nicht eingeloggt, Token abgelaufen |
| `AuthorizationError` | 403 | Eingeloggt aber keine Berechtigung |
| `ValidationException` / `ValidationError` | 422 | Ungültige Eingabedaten |
| `RateLimitExceededError` | 429 | API-Limit erreicht |
| `ConfigurationError` | 503 | App-Konfiguration fehlt/ungültig |
| `DuplicateEntityException` | 409 | Entity existiert bereits |
| Unerwartete Exception | 500 | Alles andere (Bugs) |

---

## 4. Service-Layer Pattern

```python
# ✅ RICHTIG: Domain Exception werfen
from soulspot.domain.exceptions import EntityNotFoundError, BusinessRuleViolation

class ArtistService:
    async def get_artist(self, artist_id: UUID) -> ArtistDTO:
        """Get artist by ID.
        
        Raises:
            EntityNotFoundError: Artist not found in database
        """
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            raise EntityNotFoundError(f"Artist not found: {artist_id}")
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

```python
# ❌ FALSCH: ValueError/RuntimeError werfen
class ArtistService:
    async def sync_artist(self, artist_id: UUID) -> ArtistDTO:
        artist = await self._artist_repo.get_by_id(artist_id)
        if not artist:
            raise ValueError(f"Artist not found: {artist_id}")  # ❌
        
        if not artist.spotify_uri:
            raise RuntimeError("No Spotify URI")  # ❌
```

---

## 5. Route-Layer Pattern

```python
# ✅ RICHTIG: Spezifische Exceptions fangen
from soulspot.domain.exceptions import (
    EntityNotFoundError,
    BusinessRuleViolation,
    ExternalServiceError,
)

@router.get("/artists/{artist_id}")
async def get_artist(
    artist_id: UUID,
    service: ArtistService = Depends(get_artist_service),
) -> ArtistResponse:
    """Get artist details."""
    try:
        return await service.get_artist(artist_id)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")


@router.post("/artists/{artist_id}/sync")
async def sync_artist(
    artist_id: UUID,
    service: ArtistService = Depends(get_artist_service),
) -> ArtistResponse:
    """Sync artist with Spotify."""
    try:
        return await service.sync_artist(artist_id)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")
    except BusinessRuleViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        raise HTTPException(status_code=502, detail=f"External service error: {e}")
```

```python
# ❌ FALSCH: Generische Exception fangen
@router.post("/artists/{artist_id}/sync")
async def sync_artist(artist_id: UUID) -> ArtistResponse:
    try:
        return await service.sync_artist(artist_id)
    except Exception as e:  # ❌ Zu breit!
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 6. Global Exception Handler

In `src/soulspot/main.py` oder `src/soulspot/api/exception_handlers.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from soulspot.domain.exceptions import (
    SoulSpotError,
    EntityNotFoundError,
    BusinessRuleViolation,
    ExternalServiceError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    RateLimitExceededError,
)

# Mapping: Exception-Klasse → (HTTP Status, Log Level)
EXCEPTION_MAPPING = {
    EntityNotFoundError: (404, "info"),
    BusinessRuleViolation: (400, "warning"),
    ValidationError: (422, "warning"),
    AuthenticationError: (401, "info"),
    AuthorizationError: (403, "warning"),
    ExternalServiceError: (502, "error"),
    RateLimitExceededError: (429, "warning"),
}

@app.exception_handler(SoulSpotError)
async def soulspot_exception_handler(request: Request, exc: SoulSpotError):
    """Handle all domain exceptions uniformly."""
    status_code, log_level = EXCEPTION_MAPPING.get(
        type(exc), (500, "error")
    )
    
    # Log based on severity
    getattr(logger, log_level)(f"{type(exc).__name__}: {exc}")
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "status": status_code,
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors (bugs)."""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "status": 500,
        }
    )
```

---

## 7. HTTPException Detail Format

Alle HTTPException details MÜSSEN diesem Format folgen:

```python
# Pattern: "{Entity} {action} {reason}: {identifier}"

# 404 - Entity not found
raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")
raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")
raise HTTPException(status_code=404, detail=f"Playlist not found: {playlist_id}")

# 400 - Bad request / Business rule violation
raise HTTPException(status_code=400, detail=f"Artist has no Spotify URI: {artist_id}")
raise HTTPException(status_code=400, detail=f"Invalid playlist name: {name}")

# 409 - Conflict
raise HTTPException(status_code=409, detail=f"Playlist already exists: {name}")
raise HTTPException(status_code=409, detail=f"Artist already being synced: {artist_id}")

# 502 - External service error
raise HTTPException(status_code=502, detail=f"Spotify API error: {error_message}")
raise HTTPException(status_code=502, detail=f"Deezer API error: {error_message}")
```

**VERBOTEN:**
```python
# ❌ Zu generisch
raise HTTPException(status_code=404, detail="Not found")

# ❌ Interne Exception exposed
raise HTTPException(status_code=500, detail=str(e))

# ❌ Technische Details
raise HTTPException(status_code=500, detail=f"Database error: {e.args}")
```

---

## 8. Externe Service Fehler

Wenn externe APIs (Spotify, Deezer, MusicBrainz) fehlschlagen:

```python
# In Client (Infrastructure Layer)
class SpotifyClient:
    async def get_artist(self, spotify_id: str) -> dict[str, Any]:
        try:
            response = await self._http.get(f"/artists/{spotify_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise EntityNotFoundError(f"Spotify artist not found: {spotify_id}")
            elif e.response.status_code == 429:
                raise RateLimitExceededError("Spotify rate limit exceeded")
            else:
                raise ExternalServiceError(f"Spotify API error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ExternalServiceError(f"Spotify connection error: {e}")
```

---

## 9. Logging bei Exceptions

```python
# ✅ RICHTIG: Log vor dem Raise
logger.warning(f"Artist not found: {artist_id}")
raise EntityNotFoundError(f"Artist not found: {artist_id}")

# ✅ RICHTIG: Log beim Catch
except EntityNotFoundError as e:
    logger.info(f"Expected error: {e}")  # 404 ist normal
    raise HTTPException(status_code=404, detail=str(e))

except ExternalServiceError as e:
    logger.error(f"External service failed: {e}")  # 502 ist problematisch
    raise HTTPException(status_code=502, detail=str(e))

# ❌ FALSCH: Kein Logging
raise EntityNotFoundError(f"Artist not found: {artist_id}")  # Wo kam das her?
```

---

## 10. Checkliste für neue Exceptions

Wenn du eine neue Exception brauchst:

- [ ] Erbt von `SoulSpotError` (nicht von `Exception` direkt)
- [ ] Hat beschreibenden Namen (endet auf `Error`)
- [ ] Ist in `src/soulspot/domain/exceptions.py` definiert
- [ ] Hat HTTP-Status-Mapping in Global Handler
- [ ] Hat docstring mit Verwendungszweck
- [ ] Wird in `__all__` exportiert

---

## 11. Migration von altem Code

### Vorher (falsch):
```python
if not artist:
    raise ValueError(f"Artist not found: {artist_id}")
```

### Nachher (richtig):
```python
from soulspot.domain.exceptions import EntityNotFoundError

if not artist:
    raise EntityNotFoundError(f"Artist not found: {artist_id}")
```

### Vorher (falsch):
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### Nachher (richtig):
```python
except EntityNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except BusinessRuleViolation as e:
    raise HTTPException(status_code=400, detail=str(e))
# Unerwartete Fehler gehen zum Global Handler
```

---

## 12. Zusammenfassung

```
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                                │
│  • Fängt spezifische Domain Exceptions                          │
│  • Mapped zu HTTPException mit strukturierter Message           │
│  • NIEMALS generische Exception fangen                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│  • Wirft Domain Exceptions (EntityNotFoundError, etc.)          │
│  • NIEMALS ValueError, RuntimeError, HTTPException              │
│  • Dokumentiert Exceptions in Docstrings                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                          │
│  • Clients konvertieren HTTP-Fehler zu Domain Exceptions        │
│  • Repos werfen EntityNotFoundError wenn nicht gefunden         │
│  • Transaktionsfehler werden zu BusinessRuleViolation           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DOMAIN LAYER                               │
│  • Definiert alle Exception-Klassen                             │
│  • src/soulspot/domain/exceptions.py = EINZIGE QUELLE           │
│  • Keine Abhängigkeiten zu anderen Layern                       │
└─────────────────────────────────────────────────────────────────┘
```
