# Naming Conventions

**Category:** Standards  
**Status:** ENFORCED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Architecture Redesign Proposal](./architecture-redesign-proposal.md) | [Service Separation](./service-separation-principles.md)

---

## Overview

Consistent naming is critical for:
- **Readability:** Developers instantly recognize file/class purpose
- **Maintainability:** No guessing "is it `TrackService` or `TrackManager`?"
- **Scalability:** Clear patterns prevent naming chaos as codebase grows

**Golden Rule:** If you see a filename or class name, you should immediately know:
1. What layer it belongs to (API/Application/Domain/Infrastructure)
2. What it does (service/repository/client/entity/DTO)
3. What domain it handles (artist/track/playlist)

---

## File Naming Patterns

### Services

**Pattern:** `{domain}_service.py`

```
application/services/
├── artist_service.py               ← ArtistService
├── playlist_sync_service.py        ← PlaylistSyncService
├── library_scanner_service.py      ← LibraryScannerService
└── enrichment_service.py           ← EnrichmentService
```

**Why singular domain?** One service per domain. If you need multiple, add purpose: `artist_discovery_service.py`, `artist_sync_service.py`.

---

### Repositories

**Pattern:** `repositories.py` (centralized) OR `{domain}_repository.py` (split)

```
infrastructure/persistence/
├── repositories.py                 ← All repositories (current approach)
│   ├── class ArtistRepository
│   ├── class TrackRepository
│   └── ...
└── (alternative) Split approach:
    ├── artist_repository.py        ← Only ArtistRepository
    ├── track_repository.py         ← Only TrackRepository
    └── ...
```

**Current:** SoulSpot uses centralized `repositories.py`. If it exceeds 1000 LOC, split.

---

### Routers

**Pattern:** `{domain}.py` (singular!)

```
api/routers/
├── artists.py                      ← Artist endpoints
├── playlists.py                    ← Playlist endpoints
├── library.py                      ← Library endpoints
├── auth.py                         ← Auth endpoints
└── settings.py                     ← Settings endpoints
```

**❌ WRONG:** `artist.py` (ambiguous - is it entity or router?)  
**✅ RIGHT:** `artists.py` (clear - it's the router for artist endpoints)

**Exception:** Singular OK if domain is inherently singular: `auth.py`, `onboarding.py`.

---

### Entities

**Pattern:** `{entity}.py` (singular, no suffix!)

```
domain/entities/
├── artist.py                       ← class Artist
├── track.py                        ← class Track
├── playlist.py                     ← class Playlist
└── download.py                     ← class Download
```

**❌ FORBIDDEN:**
- `artist_entity.py` (redundant suffix)
- `artists.py` (plural - confuses with routers)

---

### DTOs (Data Transfer Objects)

**Pattern:** `dto.py` OR `{domain}_dto.py`

```
infrastructure/plugins/
├── dto.py                          ← All DTOs (ArtistDTO, TrackDTO, ...)
└── (alternative) Split approach:
    ├── artist_dto.py               ← Only ArtistDTO
    ├── track_dto.py                ← Only TrackDTO
    └── ...
```

**Current:** SoulSpot uses centralized `dto.py`. If it exceeds 1000 LOC, split.

---

### Schemas (Pydantic API Models)

**Pattern:** `schemas.py` OR `{domain}_schema.py`

```
api/schemas/
├── schemas.py                      ← All Pydantic API models
└── (alternative) Split approach:
    ├── artist_schema.py            ← Only artist API models
    ├── playlist_schema.py          ← Only playlist API models
    └── ...
```

**Used for:** Request/response validation in FastAPI routes.

---

### Clients (External API Wrappers)

**Pattern:** `{service}_client.py`

```
infrastructure/clients/
├── spotify_client.py               ← SpotifyClient (HTTP wrapper)
├── deezer_client.py                ← DeezerClient
├── musicbrainz_client.py           ← MusicBrainzClient
└── slskd_client.py                 ← SlskdClient
```

**❌ WRONG:** `spotify.py` (ambiguous)  
**✅ RIGHT:** `spotify_client.py` (clear - it's a client)

---

### Plugins (Service Abstraction Layer)

**Pattern:** `{service}_plugin.py`

```
infrastructure/plugins/
├── spotify_plugin.py               ← SpotifyPlugin (implements IMusicServicePlugin)
├── deezer_plugin.py                ← DeezerPlugin
└── tidal_plugin.py                 ← TidalPlugin
```

**Difference from Clients:**
- **Client:** Low-level HTTP wrapper (handles auth, requests, errors)
- **Plugin:** High-level service abstraction (implements domain interface)

Example:
```python
# Client: Low-level HTTP
class SpotifyClient:
    async def get_artist(self, artist_id: str) -> dict:
        """Raw Spotify API response."""
        return await self._http.get(f"/artists/{artist_id}")

# Plugin: Domain abstraction
class SpotifyPlugin(IMusicServicePlugin):
    async def get_artist_details(self, spotify_uri: str) -> ArtistDTO:
        """Returns domain DTO."""
        response = await self._client.get_artist(artist_id)
        return ArtistDTO(name=response["name"], ...)
```

---

### Workers (Background Tasks)

**Pattern:** `{purpose}_worker.py`

```
infrastructure/workers/
├── token_refresh_worker.py         ← TokenRefreshWorker
├── sync_worker.py                  ← SyncWorker (Spotify/Deezer sync)
├── download_worker.py              ← DownloadWorker
└── cache_cleanup_worker.py         ← CacheCleanupWorker
```

**❌ WRONG:** `worker_token_refresh.py` (suffix first confuses sorting)  
**✅ RIGHT:** `token_refresh_worker.py` (domain first, purpose clear)

---

### Utilities

**Pattern:** `{purpose}.py` (no `_utils` suffix!)

```
utils/
├── string_utils.py                 ← String manipulation helpers
├── date_helpers.py                 ← Date/time utilities
├── validators.py                   ← Input validation functions
└── formatters.py                   ← Output formatting
```

**❌ WRONG:** `utils.py` (too generic)  
**✅ RIGHT:** `string_utils.py` (specific purpose)

---

## Folder Structure Standards

```
src/soulspot/
├── api/
│   ├── routers/                    ← {domain}.py (plural or singular if inherently singular)
│   ├── schemas/                    ← schemas.py (Pydantic API models)
│   └── dependencies.py             ← FastAPI dependencies
│
├── application/
│   └── services/                   ← {domain}_service.py
│
├── domain/
│   ├── entities/                   ← {entity}.py (singular, no suffix)
│   └── ports/                      ← {port}.py (interfaces)
│
├── infrastructure/
│   ├── clients/                    ← {service}_client.py
│   ├── plugins/                    ← {service}_plugin.py
│   ├── persistence/
│   │   ├── models.py               ← SQLAlchemy models (all in one file)
│   │   └── repositories.py         ← All repositories (or split)
│   └── workers/                    ← {purpose}_worker.py
│
└── config/
    └── settings.py                 ← Application settings
```

---

## Class Naming Patterns

### Entities (Domain Models)

**Pattern:** `PascalCase` singular, **NO suffix**

```python
# ✅ CORRECT
class Artist:
    """Domain entity representing an artist."""
    id: UUID
    name: str
    spotify_uri: str | None

class Track:
    """Domain entity representing a track."""
    id: UUID
    title: str
    isrc: str | None

class Playlist:
    """Domain entity representing a playlist."""
    id: UUID
    name: str
    tracks: list[Track]
```

**❌ FORBIDDEN:**
```python
class ArtistEntity:       # Redundant suffix
class Artists:            # Plural (reserve for collections)
class artist:             # Lowercase (not PascalCase)
```

---

### DTOs (Data Transfer Objects)

**Pattern:** `PascalCase` + `DTO` suffix

```python
# ✅ CORRECT
class ArtistDTO:
    """DTO for artist data from plugins."""
    name: str
    image_url: str | None
    spotify_id: str | None
    deezer_id: str | None

class TrackDTO:
    """DTO for track data from plugins."""
    title: str
    isrc: str | None
    duration_ms: int

class SearchResultDTO:
    """DTO for search results."""
    artists: list[ArtistDTO]
    tracks: list[TrackDTO]
    total: int
```

**❌ FORBIDDEN:**
```python
class ArtistData:         # Ambiguous (data what?)
class ArtistModel:        # Confusing (is it SQLAlchemy model?)
class Artist:             # Conflicts with domain entity
```

---

### Models (SQLAlchemy ORM)

**Pattern:** `PascalCase` + `Model` suffix

```python
# ✅ CORRECT
class ArtistModel(Base):
    """SQLAlchemy model for artists table."""
    __tablename__ = "soulspot_artists"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    spotify_uri: Mapped[str | None] = mapped_column(String(255), unique=True)

class TrackModel(Base):
    """SQLAlchemy model for tracks table."""
    __tablename__ = "soulspot_tracks"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
```

**Why `Model` suffix?** Distinguish from domain entities:
- `Artist` = Domain entity (business logic)
- `ArtistModel` = Database model (persistence)

**❌ FORBIDDEN:**
```python
class Artist(Base):       # Conflicts with domain entity!
class ArtistTable:        # Confusing (model != table)
```

---

### Services

**Pattern:** `PascalCase` + `Service` suffix

```python
# ✅ CORRECT
class ArtistService:
    """Business logic for artist operations."""
    async def get_artist_details(self, artist_id: UUID) -> Artist:
        ...

class PlaylistSyncService:
    """Sync playlists from music services."""
    async def sync_spotify_playlists(self, user_id: UUID) -> SyncResult:
        ...

class LibraryScannerService:
    """Scan local library and import tracks."""
    async def scan_directory(self, path: Path) -> ScanResult:
        ...
```

**❌ FORBIDDEN:**
```python
class ArtistManager:      # Use "Service" not "Manager"
class ArtistHelper:       # Too vague
class ArtistLogic:        # Redundant (services ARE logic)
```

---

### Repositories

**Pattern:** `PascalCase` + `Repository` suffix

```python
# ✅ CORRECT
class ArtistRepository:
    """Data access layer for artists."""
    async def get_by_id(self, artist_id: UUID) -> Artist | None:
        ...
    
    async def get_by_spotify_uri(self, uri: str) -> Artist | None:
        ...

class TrackRepository:
    """Data access layer for tracks."""
    async def get_by_isrc(self, isrc: str) -> Track | None:
        ...
```

**❌ FORBIDDEN:**
```python
class ArtistRepo:         # Don't abbreviate
class ArtistDAO:          # DAO is different pattern (use Repository)
class ArtistStore:        # Ambiguous
```

---

### Clients (HTTP Wrappers)

**Pattern:** `Service` + `Client`

```python
# ✅ CORRECT
class SpotifyClient:
    """HTTP client for Spotify API."""
    async def get_artist(self, artist_id: str) -> dict:
        ...

class DeezerClient:
    """HTTP client for Deezer API."""
    async def get_album(self, album_id: str) -> dict:
        ...

class MusicBrainzClient:
    """HTTP client for MusicBrainz API."""
    async def search_recording(self, isrc: str) -> dict:
        ...
```

**❌ FORBIDDEN:**
```python
class SpotifyAPI:         # Use "Client" not "API"
class SpotifyService:     # Service is higher-level (use Client for HTTP wrapper)
```

---

### Plugins (Service Abstraction)

**Pattern:** `Service` + `Plugin`

```python
# ✅ CORRECT
class SpotifyPlugin(IMusicServicePlugin):
    """Spotify service plugin implementation."""
    async def get_artist_details(self, uri: str) -> ArtistDTO:
        ...

class DeezerPlugin(IMusicServicePlugin):
    """Deezer service plugin implementation."""
    async def search_tracks(self, query: str) -> list[TrackDTO]:
        ...
```

**❌ FORBIDDEN:**
```python
class SpotifyAdapter:     # Use "Plugin" in SoulSpot (adapter is too generic)
class SpotifyService:     # Confusing (is it service or plugin?)
```

---

## Forbidden Patterns

### ❌ Plural Class Names

```python
# WRONG
class Artists:            # Collections should be typed: list[Artist]
class Tracks:
class Playlists:

# RIGHT
class Artist:
class Track:
class Playlist:

# Use plurals for collections
artists: list[Artist] = [...]
```

---

### ❌ Redundant Suffixes

```python
# WRONG
class ArtistEntity:       # Entity is implied (in domain/entities/)
class TrackModel:         # Only for SQLAlchemy models!
class PlaylistDTO:        # Only for data transfer objects!

# RIGHT
class Artist:             # Domain entity
class ArtistModel:        # SQLAlchemy model (suffix OK here)
class ArtistDTO:          # DTO (suffix OK here)
```

---

### ❌ Inconsistent Abbreviations

```python
# WRONG
class ArtistRepo:         # Don't abbreviate Repository
class TrackSvc:           # Don't abbreviate Service
class PlaylistMgr:        # Don't abbreviate Manager

# RIGHT
class ArtistRepository:
class TrackService:
class PlaylistManager:    # (But prefer "Service" over "Manager")
```

---

### ❌ Mixing Conventions

```python
# WRONG (mixing snake_case and PascalCase)
class artist_service:     # Use PascalCase for classes
class Track_Repository:   # No underscores in PascalCase

# RIGHT
class ArtistService:
class TrackRepository:
```

---

## Migration Guidelines

### Renaming Files

1. **Check imports:** Use `grep -r "old_name"` to find all imports
2. **Update imports:** Change all `from old_name import` to `from new_name import`
3. **Update references:** Change all `old_name.Class` to `new_name.Class`
4. **Git rename:** Use `git mv old_name.py new_name.py` to preserve history

```bash
# Example: Rename artist_manager.py → artist_service.py
grep -r "artist_manager" src/
git mv src/application/services/artist_manager.py src/application/services/artist_service.py

# Update all imports
sed -i 's/from artist_manager import/from artist_service import/g' src/**/*.py
```

---

### Renaming Classes

1. **Find usages:** `grep -r "class OldName"`
2. **Rename class:** `class OldName → class NewName`
3. **Update imports:** `from module import OldName → from module import NewName`
4. **Update references:** `old_instance = OldName() → new_instance = NewName()`

---

## Verification Checklist

Before committing, verify:

- [ ] **File names:**
  - Services: `{domain}_service.py`
  - Routers: `{domain}.py` (plural or singular if inherent)
  - Entities: `{entity}.py` (singular, no suffix)
  - DTOs: `dto.py` or `{domain}_dto.py`
  - Clients: `{service}_client.py`
  - Plugins: `{service}_plugin.py`
  - Workers: `{purpose}_worker.py`

- [ ] **Class names:**
  - Entities: `PascalCase` (singular, no suffix)
  - DTOs: `PascalCase + DTO`
  - Models: `PascalCase + Model`
  - Services: `PascalCase + Service`
  - Repositories: `PascalCase + Repository`
  - Clients: `Service + Client`
  - Plugins: `Service + Plugin`

- [ ] **Forbidden patterns avoided:**
  - No plural class names (`Artists` ❌)
  - No redundant suffixes (`ArtistEntity` ❌)
  - No abbreviations (`ArtistRepo` ❌)
  - No mixing conventions (`artist_Service` ❌)

---

## Related Documentation

- **[Architecture Redesign Proposal](./architecture-redesign-proposal.md)** - New directory structure
- **[Service Separation Principles](./service-separation-principles.md)** - When to split services

---

**Last Validated:** 2025-01-XX  
**Status:** ✅ ENFORCED - Violations blocked in code review  
**Tooling:** Ruff custom rules + pre-commit hooks check naming conventions
