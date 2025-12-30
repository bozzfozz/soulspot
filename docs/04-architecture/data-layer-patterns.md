# SoulSpot Data Layer Patterns

> **Quick Reference for Common Operations**

This document shows concrete examples of how to correctly implement various data operations in SoulSpot.

---

## 1. Adding a New Service Endpoint

### Step 1: Route (API Layer)

```python
# src/soulspot/api/routers/artists.py

from fastapi import APIRouter, Depends
from soulspot.api.dependencies import get_artist_service
from soulspot.application.services.artist_service import ArtistService

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/{artist_id}")
async def get_artist(
    artist_id: str,
    service: ArtistService = Depends(get_artist_service),  # ← Service injected!
):
    """
    Hey future me - Routes are THIN!
    Only HTTP handling, no business logic.
    """
    return await service.get_artist_by_id(artist_id)
```

**Rule**: Routes do HTTP only. Business logic belongs in Services.

### Step 2: Service (Application Layer)

```python
# src/soulspot/application/services/artist_service.py

from soulspot.domain.dtos import ArtistDTO
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.persistence.repositories import ArtistRepository


class ArtistService:
    """
    Hey future me - Services orchestrate Plugins and Repos!
    They contain business logic.
    """
    
    def __init__(
        self,
        spotify_plugin: SpotifyPlugin,
        artist_repo: ArtistRepository,
    ):
        self._spotify = spotify_plugin
        self._repo = artist_repo

    async def get_artist_by_id(self, spotify_id: str) -> ArtistDTO:
        # 1. Check DB first (cached)
        existing = await self._repo.get_by_spotify_uri(
            f"spotify:artist:{spotify_id}"
        )
        
        if existing:
            # Convert Entity to DTO for API response
            return ArtistDTO(
                name=existing.name,
                source_service="database",
                spotify_uri=str(existing.spotify_uri),
                spotify_id=spotify_id,
                image_url=existing.image_url,
            )
        
        # 2. Not in DB - fetch from Spotify
        return await self._spotify.get_artist(spotify_id)
```

**Rule**: Services orchestrate. Never call infrastructure directly from routes.

### Step 3: Dependency (API Layer)

```python
# src/soulspot/api/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.artist_service import ArtistService
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.persistence.repositories import ArtistRepository


async def get_artist_service(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
) -> ArtistService:
    """Factory for ArtistService with all dependencies."""
    return ArtistService(
        spotify_plugin=spotify_plugin,
        artist_repo=ArtistRepository(session),
    )
```

**Rule**: Dependencies construct services with all required dependencies.

---

## 2. Adding a New Plugin Method

### Example: `get_chart_tracks()` in DeezerPlugin

```python
# src/soulspot/infrastructure/plugins/deezer_plugin.py

async def get_chart_tracks(self, limit: int = 50) -> list[TrackDTO]:
    """
    Get current chart tracks from Deezer.
    
    Hey future me - Client returns raw dict, we convert to DTOs!
    Conversion happens HERE in plugin, not in client.
    """
    # 1. Raw API call via client
    raw_data = await self._client.get_chart_tracks(limit=limit)
    
    # 2. Convert to DTOs
    tracks: list[TrackDTO] = []
    for item in raw_data.get("tracks", {}).get("data", []):
        tracks.append(self._convert_track(item))  # ← _convert_track!
    
    return tracks


def _convert_track(self, data: dict) -> TrackDTO:
    """
    Convert raw Deezer API track to TrackDTO.
    
    Hey future me - ALL conversions here!
    Check which fields API provides and map correctly.
    """
    album_data = data.get("album", {})
    artist_data = data.get("artist", {})
    
    return TrackDTO(
        title=data.get("title", "Unknown"),
        artist_name=artist_data.get("name", "Unknown Artist"),
        source_service="deezer",
        
        # Deezer-specific ID
        deezer_id=str(data.get("id", "")),
        
        # Album reference (if available)
        album_name=album_data.get("title"),
        album_deezer_id=str(album_data.get("id", "")) if album_data.get("id") else None,
        
        # Artist reference
        artist_deezer_id=str(artist_data.get("id", "")) if artist_data.get("id") else None,
        
        # Track metadata
        duration_ms=(data.get("duration", 0)) * 1000,  # Deezer gives seconds!
        explicit=data.get("explicit_lyrics", False),
        preview_url=data.get("preview"),
    )
```

**Rule**: Plugins convert external formats to DTOs. Never return raw dicts.

---

## 3. Adding a New Repository Method

### ⚠️ CRITICAL: Update Interface AND Implementation!

### Step 1: Interface (Domain Port)

```python
# src/soulspot/domain/ports/__init__.py

class IArtistRepository(ABC):
    # ... existing methods ...
    
    @abstractmethod
    async def get_by_deezer_id(self, deezer_id: str) -> Artist | None:
        """Get an artist by Deezer ID.
        
        Hey future me - Multi-service lookup for deduplication!
        Check if artist exists before creating new one.
        """
        pass
```

### Step 2: Implementation (Infrastructure)

```python
# src/soulspot/infrastructure/persistence/repositories.py

class ArtistRepository(IArtistRepository):
    # ... existing methods ...
    
    async def get_by_deezer_id(self, deezer_id: str) -> Artist | None:
        """Get an artist by Deezer ID."""
        result = await self._session.execute(
            select(ArtistModel).where(ArtistModel.deezer_id == deezer_id)
        )
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_entity(model)  # ← Model → Entity conversion!
    
    def _to_entity(self, model: ArtistModel) -> Artist:
        """Convert ORM Model to Domain Entity.
        
        Hey future me - this is the Model→Entity bridge!
        """
        return Artist(
            id=ArtistId(model.id),
            name=model.name,
            spotify_uri=SpotifyUri(model.spotify_uri) if model.spotify_uri else None,
            deezer_id=model.deezer_id,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            # ... more fields
        )
```

**Rule**: ALWAYS update Port interface when adding repository methods. Otherwise type checking fails.

---

## 4. Extracting `spotify_id` from Different Contexts

### From Entity (Domain)

```python
# Entity has ONLY spotify_uri
artist: Artist = await repo.get_by_id(artist_id)

# Extract ID
if artist.spotify_uri:
    spotify_id = str(artist.spotify_uri).split(":")[-1]
```

### From Model (ORM)

```python
# Model has spotify_uri Column + spotify_id Property
artist_model: ArtistModel = result.scalar_one()

# Option 1: Use property (if defined)
spotify_id = artist_model.spotify_id  # ← @property in model

# Option 2: Manual extraction (always safe)
spotify_id = artist_model.spotify_uri.split(":")[-1] if artist_model.spotify_uri else None
```

### From DTO

```python
# DTO has BOTH fields
artist_dto: ArtistDTO = await plugin.get_artist("xyz")

# Use directly
spotify_id = artist_dto.spotify_id      # ← Already extracted
spotify_uri = artist_dto.spotify_uri    # ← Full URI
```

### In Jinja2 Templates

```html
<!-- artist is Model or DTO -->
{% if artist.spotify_uri %}
    <a href="https://open.spotify.com/artist/{{ artist.spotify_uri.split(':')[-1] }}">
        Open in Spotify
    </a>
{% endif %}

<!-- If model has spotify_id property -->
{% if artist.spotify_id %}
    <a href="https://open.spotify.com/artist/{{ artist.spotify_id }}">
        Open in Spotify
    </a>
{% endif %}
```

---

## 5. Multi-Provider Aggregation Pattern

```python
# src/soulspot/application/services/charts_service.py

async def get_aggregated_chart_tracks(self) -> list[TrackDTO]:
    """
    Get chart tracks from ALL enabled providers.
    
    Hey future me - THIS is the multi-provider pattern!
    1. Query ALL active providers
    2. Aggregate results
    3. Deduplicate (ISRC is the key!)
    """
    all_tracks: list[TrackDTO] = []
    seen_isrcs: set[str] = set()
    
    # 1. Deezer (no auth needed for charts)
    if self._deezer_plugin.can_use(PluginCapability.BROWSE_CHARTS):
        try:
            deezer_tracks = await self._deezer_plugin.get_chart_tracks()
            for track in deezer_tracks:
                # Deduplicate via ISRC
                if track.isrc and track.isrc in seen_isrcs:
                    continue
                if track.isrc:
                    seen_isrcs.add(track.isrc)
                all_tracks.append(track)
        except PluginError as e:
            logger.warning(f"Deezer charts failed: {e}")
    
    # 2. Spotify (auth required)
    if self._spotify_plugin.can_use(PluginCapability.BROWSE_CHARTS):
        try:
            spotify_tracks = await self._spotify_plugin.get_chart_tracks()
            for track in spotify_tracks:
                if track.isrc and track.isrc in seen_isrcs:
                    continue
                if track.isrc:
                    seen_isrcs.add(track.isrc)
                all_tracks.append(track)
        except PluginError as e:
            logger.warning(f"Spotify charts failed: {e}")
    
    return all_tracks
```

**Key Points**:
- Query **all** enabled providers
- Use ISRC for deduplication (same recording across services)
- Graceful fallback (continue if one provider fails)
- Log errors without breaking flow

---

## 6. Track Persistence from Providers (NEW!)

### ⚠️ CRITICAL: Unified Pattern for All Providers!

**ALWAYS use `TrackRepository.upsert_from_provider()`!**

This method is the **only correct way** to persist tracks from external providers (Spotify, Deezer, Tidal).

### Why?

1. **Unified Deduplication**: ISRC → Provider ID → title+album
2. **Consistent album_id**: ALWAYS internal UUIDs, never provider IDs
3. **Clean Architecture**: Services → Repository → ORM (not Services → ORM directly)
4. **Multi-Provider Ready**: Tracks get `source="hybrid"` when multiple provider IDs exist

### Correct Usage

```python
# src/soulspot/application/services/deezer_sync_service.py

async def _save_track_with_artist(
    self,
    track_dto: TrackDTO,
    artist_id: str,  # ← Internal UUID!
    album_id: str | None,  # ← Internal UUID!
) -> None:
    """
    Hey future me - use TrackRepository.upsert_from_provider()!
    Never use ORM directly (TrackModel).
    """
    await self._track_repo.upsert_from_provider(
        title=track_dto.title,
        artist_id=artist_id,  # Internal UUID (from ProviderMappingService)
        album_id=album_id,  # Internal UUID (from AlbumRepository lookup)
        source="deezer",
        duration_ms=track_dto.duration_ms or 0,
        track_number=track_dto.track_number or 1,
        disc_number=track_dto.disc_number or 1,
        explicit=track_dto.explicit or False,
        isrc=track_dto.isrc,  # CRITICAL for deduplication!
        deezer_id=track_dto.deezer_id,
        preview_url=track_dto.preview_url,
    )
```

### ❌ WRONG: Direct ORM

```python
# ❌ NEVER DO THIS!
from soulspot.infrastructure.persistence.models import TrackModel

track = TrackModel(
    title=dto.title,
    artist_id=artist_id,
    album_id=album_id,  # What is this - Spotify ID or UUID??
    deezer_id=dto.deezer_id,
)
self._session.add(track)
```

**Why wrong?**
- No deduplication logic
- Unclear if `album_id` is provider ID or internal UUID
- Breaks multi-provider support
- Bypasses Clean Architecture

### ❌ DEPRECATED: SpotifyBrowseRepository.upsert_track()

```python
# ❌ DEPRECATED - don't use for new features!
await self.repo.upsert_track(
    spotify_id=track.id,
    album_id=album.id,  # Spotify ID! Confusing!
    name=track.title,
)

# ✅ INSTEAD:
# 1. Lookup album UUID
album = await album_repo.get_by_spotify_uri(f"spotify:album:{album.id}")
# 2. Use TrackRepository
await track_repo.upsert_from_provider(
    title=track.title,
    artist_id=str(album.artist_id.value),  # UUID!
    album_id=str(album.id.value),  # UUID!
    source="spotify",
    spotify_uri=f"spotify:track:{track.id}",
    ...
)
```

---

## 7. Common Error Fixes

### AttributeError: 'XModel' has no attribute 'spotify_id'

```python
# ❌ ERROR
artist_model = await session.get(ArtistModel, id)
print(artist_model.spotify_id)  # AttributeError!

# ✅ FIX 1: Add property in model
# In models.py:
@property
def spotify_id(self) -> str | None:
    if not self.spotify_uri:
        return None
    return self.spotify_uri.split(":")[-1]

# ✅ FIX 2: Manual extraction
spotify_id = artist_model.spotify_uri.split(":")[-1] if artist_model.spotify_uri else None
```

### TypeError: 'NoneType' object is not subscriptable

```python
# ❌ ERROR
spotify_id = artist.spotify_uri.split(":")[-1]  # Crash if None!

# ✅ FIX: None check
spotify_id = artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None

# ✅ EVEN BETTER: Walrus operator (Python 3.8+)
spotify_id = uri.split(":")[-1] if (uri := artist.spotify_uri) else None
```

### Plugin returns raw dict instead of DTO

```python
# ❌ ERROR (in plugin)
async def get_artist(self, artist_id: str):
    return await self._client.get_artist(artist_id)  # raw dict!

# ✅ FIX: Convert to DTO
async def get_artist(self, artist_id: str) -> ArtistDTO:
    raw = await self._client.get_artist(artist_id)
    return self._convert_artist(raw)
```

---

## Quick Checklist for New Features

- [ ] Route calls Service (not Client/Repo directly)
- [ ] Service returns DTOs
- [ ] Plugin converts raw → DTO
- [ ] Repository method also defined in Interface (Port)
- [ ] `spotify_uri` in DB, `spotify_id` only as property
- [ ] Multi-provider uses `can_use()` for capability checks
- [ ] Error handling with `PluginError` for plugin errors
- [ ] **Track persistence via `TrackRepository.upsert_from_provider()` (NEW!)**
- [ ] **`artist_id`/`album_id` are ALWAYS internal UUIDs**

---

## Summary

**Layer Responsibilities**:
```
┌─────────────────────────────────────────────────┐
│ Routes (API)     → HTTP handling only            │
├─────────────────────────────────────────────────┤
│ Services (App)   → Business logic, orchestration │
├─────────────────────────────────────────────────┤
│ Plugins (Infra)  → External API → DTO conversion│
├─────────────────────────────────────────────────┤
│ Repositories     → DB access, Entity ↔ Model    │
└─────────────────────────────────────────────────┘
```

**Key Patterns**:
1. **Routes are thin**: Only HTTP, delegate to services
2. **Services orchestrate**: Combine plugins + repositories
3. **Plugins convert**: Raw API → DTOs
4. **Repositories abstract**: ORM from domain
5. **Multi-provider**: Aggregate all services, deduplicate
6. **Track persistence**: Always use `upsert_from_provider()`

---

## See Also

- [Data Standards](./data-standards.md) - DTO definitions
- [Core Philosophy](./core-philosophy.md) - Multi-provider principle
- [Plugin System](./plugin-system.md) - Plugin interface
- [Configuration](./configuration.md) - Database-first config

---

**Document Status**: Migrated from `docs/architecture/DATA_LAYER_PATTERNS.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/api/routers/` - Route examples
- `src/soulspot/application/services/` - Service examples
- `src/soulspot/infrastructure/plugins/` - Plugin examples
- `src/soulspot/infrastructure/persistence/repositories.py` - Repository patterns
