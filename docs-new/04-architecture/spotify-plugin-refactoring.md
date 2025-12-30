# Spotify Plugin Refactoring

**Category:** Architecture  
**Status:** ✅ COMPLETED (January 2025)  
**Created:** December 10, 2024  
**Completed:** January 2025  
**Objective:** Move all Spotify-specific components into plugin layer

---

## ✅ Migration Complete

### What Was Implemented

1. **SpotifyPlugin** (`infrastructure/plugins/spotify_plugin.py`)
   - Implements `IMusicServicePlugin` interface
   - Wraps `SpotifyClient` for all API calls
   - Returns typed DTOs: `ArtistDTO`, `AlbumDTO`, `TrackDTO`
   - Pagination via `PaginatedResponse[T]`

2. **All Components Migrated:**
   - ✅ API Routers: Use `SpotifyPlugin` via `get_spotify_plugin()`
   - ✅ Use Cases: Work with `IMusicServicePlugin` interface
   - ✅ Application Services: `LocalLibraryEnrichmentService` etc.
   - ✅ Workers: Create `SpotifyPlugin` per job with token

3. **SpotifyClient Remains:**
   - Used ONLY for OAuth (TokenManager, AuthDependencies)
   - All business logic goes through SpotifyPlugin

---

### Architecture After Migration

```
API Router 
    → Depends(get_spotify_plugin)
        → SpotifyPlugin (DTOs)
            → SpotifyClient (raw HTTP)
                → Spotify API
```

**Layer Separation:**
- **API Layer:** Uses `SpotifyPlugin` for business operations
- **Plugin Layer:** `SpotifyPlugin` implements `IMusicServicePlugin`, returns DTOs
- **Infrastructure Layer:** `SpotifyClient` handles HTTP, OAuth, rate limiting
- **Auth Layer:** `SpotifyAuthService` manages tokens (still uses client directly - OK!)

---

## Historical Context (Planning Documentation)

> **Note:** The rest of this document is historical planning documentation preserved for reference.

---

## Problem Statement (HISTORICAL)

### Current State (WRONG)

```
Spotify logic spread across 3 layers:

Application Layer:
  ├── services/spotify_sync_service.py (1248 lines!)
  ├── services/spotify_image_service.py (740 lines)
  ├── cache/spotify_cache.py (186 lines)
  ├── workers/spotify_sync_worker.py
  └── use_cases/import_spotify_playlist.py

API Layer:
  ├── routers/search.py (Spotify-hardcoded endpoints)
  └── routers/artists.py (follow/unfollow Spotify)

Plugins Layer:
  └── spotify_plugin.py (only interface implementation)

❌ PROBLEM: Spotify code is EVERYWHERE instead of in plugin!
```

---

### Target State (CORRECT)

```
Plugins Layer:
  ├── spotify_plugin.py (Main class - PUBLIC interface)
  └── spotify/
      ├── __init__.py (Nothing exported - all PRIVATE!)
      ├── _sync_service.py (Spotify sync logic)
      ├── _image_service.py (Image downloads)
      └── _cache.py (Spotify API cache)

Infrastructure Layer:
  ├── auth/spotify_token_manager.py (OAuth - stays here)
  └── integrations/spotify_client.py (HTTP Client - stays here)

Application Layer:
  └── workers/streaming_sync_worker.py (GENERIC - uses plugin interface)

✅ SOLUTION: All Spotify logic encapsulated in plugin!
```

---

## Why Is This Important?

### 1. Service-Agnostic

When adding Tidal/Deezer, we should NOT create new application services for each:

```python
# ❌ WRONG (current state):
application/services/
  ├── spotify_sync_service.py
  ├── tidal_sync_service.py  # Duplication!
  ├── deezer_sync_service.py # More duplication!

# ✅ RIGHT (goal):
plugins/
  ├── spotify_plugin.py (all Spotify logic)
  ├── tidal_plugin.py   (all Tidal logic)
  └── deezer_plugin.py  (all Deezer logic)

application/workers/
  └── streaming_sync_worker.py  # ONE for ALL services!
```

---

### 2. Clear Boundaries

- **Plugin** = Service-specific logic (how Spotify syncs)
- **Application** = Generic orchestration (when to sync, error handling)
- **Infrastructure** = Technical details (HTTP, OAuth, database)

---

### 3. Testability

```python
# Current: Spotify logic scattered everywhere
test_spotify_sync_service.py
test_spotify_image_service.py
test_spotify_cache.py
test_spotify_sync_worker.py
test_search_routes.py

# After refactoring: Everything in one module
test_spotify_plugin.py  # Tests EVERYTHING in one place
```

---

## Migration Plan (Step-by-Step)

> **NOTE:** This plan was completed in January 2025. Preserved for historical reference.

### Phase 1: Plugin Structure ✅ DONE

**Step 1.1: Package created**
```bash
mkdir -p src/soulspot/plugins/spotify
touch src/soulspot/plugins/spotify/__init__.py
```

**Step 1.2: `__init__.py` with PRIVATE marker**
```python
# src/soulspot/plugins/spotify/__init__.py
"""Spotify plugin internal modules.

PRIVATE: These modules are ONLY used internally by SpotifyPlugin.
Do NOT import from outside plugins/spotify_plugin.py!

Why private (_prefix)?
- Implementation details may change without notice
- Breaking changes don't affect other modules
- Forces clean interface via spotify_plugin.py
"""
```

---

### Phase 2: Move Spotify-Specific Services ✅ DONE

**Step 2.1: Move sync logic**
```bash
# Moved spotify_sync_service.py content → plugins/spotify/_sync_service.py
# Prefixed with _ to mark as PRIVATE
```

**Step 2.2: Move image service**
```bash
# Moved spotify_image_service.py → plugins/spotify/_image_service.py
```

**Step 2.3: Move cache**
```bash
# Moved spotify_cache.py → plugins/spotify/_cache.py
```

---

### Phase 3: Update SpotifyPlugin ✅ DONE

**Main plugin interface:**
```python
# infrastructure/plugins/spotify_plugin.py

class SpotifyPlugin(IMusicServicePlugin):
    """Spotify service plugin (PUBLIC interface)."""
    
    def __init__(
        self,
        spotify_client: SpotifyClient,
        artist_repo: ArtistRepository,
        album_repo: AlbumRepository,
        track_repo: TrackRepository,
    ):
        self._client = spotify_client
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
        
        # Internal services (PRIVATE)
        from .spotify._sync_service import SpotifySyncService
        from .spotify._image_service import SpotifyImageService
        from .spotify._cache import SpotifyCache
        
        self._sync = SpotifySyncService(spotify_client, ...)
        self._images = SpotifyImageService(spotify_client)
        self._cache = SpotifyCache()
    
    # PUBLIC interface methods
    async def get_artist_details(self, spotify_uri: str) -> ArtistDTO:
        """Fetch artist details from Spotify."""
        return await self._sync.get_artist(spotify_uri)
    
    async def get_followed_artists(self) -> PaginatedResponse[ArtistDTO]:
        """Get user's followed artists."""
        return await self._sync.get_followed_artists()
    
    async def download_artist_image(self, artist_id: str, url: str) -> Path:
        """Download artist image to local cache."""
        return await self._images.download_artist_image(artist_id, url)
```

---

### Phase 4: Update Consumers ✅ DONE

**API Routers:**
```python
# Before (WRONG)
from soulspot.application.services.spotify_sync_service import SpotifySyncService

@router.get("/spotify/artists/{artist_id}")
async def get_artist(
    artist_id: str,
    spotify_sync: SpotifySyncService = Depends(get_spotify_sync_service),
):
    return await spotify_sync.get_artist_details(artist_id)

# After (RIGHT)
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

@router.get("/spotify/artists/{artist_id}")
async def get_artist(
    artist_id: str,
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
):
    return await spotify_plugin.get_artist_details(artist_id)
```

---

**Workers:**
```python
# Before (WRONG)
class SpotifySyncWorker:
    def __init__(self, spotify_sync_service: SpotifySyncService):
        self._sync = spotify_sync_service

# After (RIGHT)
class StreamingSyncWorker:
    """Generic worker for ANY streaming service."""
    
    def __init__(self, plugin: IMusicServicePlugin):
        self._plugin = plugin  # Works with Spotify, Tidal, Deezer!
    
    async def sync_followed_artists(self):
        """Sync followed artists from ANY service."""
        artists = await self._plugin.get_followed_artists()
        # Process artists...
```

---

### Phase 5: Cleanup ✅ DONE

**Removed old services:**
```bash
# Deleted (logic moved to plugin)
rm application/services/spotify_sync_service.py
rm application/services/spotify_image_service.py
rm application/cache/spotify_cache.py
```

**Updated imports:**
- All imports changed from `application.services.spotify_*` to `plugins.spotify_plugin.SpotifyPlugin`
- Verified no broken imports remain

---

## Benefits Achieved

### Before (Scattered)

```
Spotify logic in 3+ layers:
- Application services (sync, images)
- Workers (Spotify-specific worker)
- Cache (Spotify-specific cache)
- Use cases (import playlist)

❌ Problems:
- Hard to find all Spotify code
- Can't reuse for Tidal/Deezer
- Mixed concerns (generic + Spotify)
```

---

### After (Encapsulated)

```
Spotify logic in ONE place:
- plugins/spotify_plugin.py (PUBLIC interface)
- plugins/spotify/_sync_service.py (PRIVATE implementation)
- plugins/spotify/_image_service.py (PRIVATE)
- plugins/spotify/_cache.py (PRIVATE)

✅ Benefits:
- All Spotify code in plugins/spotify/
- Generic workers work with ANY plugin
- Easy to add Tidal/Deezer plugins
- Clear interface (spotify_plugin.py)
```

---

## Adding New Service (Example: Tidal)

With plugin architecture complete, adding Tidal is straightforward:

```python
# 1. Create TidalPlugin
class TidalPlugin(IMusicServicePlugin):
    """Tidal service plugin."""
    
    async def get_artist_details(self, tidal_id: str) -> ArtistDTO:
        """Fetch artist from Tidal API."""
        # Tidal-specific implementation
        ...

# 2. Register in dependency injection
def get_tidal_plugin() -> TidalPlugin:
    return TidalPlugin(tidal_client)

# 3. Use in routes
@router.get("/tidal/artists/{artist_id}")
async def get_artist(
    artist_id: str,
    tidal_plugin: TidalPlugin = Depends(get_tidal_plugin),
):
    return await tidal_plugin.get_artist_details(artist_id)
```

**No changes needed** in:
- Generic workers (`StreamingSyncWorker` works with Tidal!)
- Generic services (already use `IMusicServicePlugin`)
- Domain entities (service-agnostic)

---

## Testing

### Unit Tests (Plugin Isolation)

```python
# tests/unit/plugins/test_spotify_plugin.py

async def test_get_artist_details():
    """Test Spotify artist fetch via plugin."""
    mock_client = MockSpotifyClient()
    plugin = SpotifyPlugin(mock_client, ...)
    
    artist = await plugin.get_artist_details("spotify:artist:123")
    
    assert artist.name == "Test Artist"
    assert artist.spotify_id == "123"

async def test_get_followed_artists():
    """Test followed artists fetch."""
    mock_client = MockSpotifyClient()
    plugin = SpotifyPlugin(mock_client, ...)
    
    result = await plugin.get_followed_artists()
    
    assert result.total > 0
    assert all(isinstance(a, ArtistDTO) for a in result.items)
```

---

### Integration Tests (Full Flow)

```python
# tests/integration/test_spotify_sync.py

async def test_sync_followed_artists_full_flow():
    """Test full sync flow with real SpotifyPlugin."""
    worker = StreamingSyncWorker(spotify_plugin)
    
    artists = await worker.sync_followed_artists()
    
    # Verify artists imported to DB
    db_artists = await artist_repo.get_all()
    assert len(db_artists) == len(artists)
```

---

## Verification Checklist

Migration complete when:

- [x] **All Spotify logic in `plugins/spotify/`**
  - [x] `spotify_plugin.py` (PUBLIC interface)
  - [x] `spotify/_sync_service.py` (PRIVATE)
  - [x] `spotify/_image_service.py` (PRIVATE)
  - [x] `spotify/_cache.py` (PRIVATE)

- [x] **No Spotify-specific services in application layer**
  - [x] Deleted `spotify_sync_service.py`
  - [x] Deleted `spotify_image_service.py`
  - [x] Deleted `spotify_cache.py`

- [x] **Generic workers use plugin interface**
  - [x] `StreamingSyncWorker` works with `IMusicServicePlugin`
  - [x] No hardcoded Spotify dependencies

- [x] **All consumers updated**
  - [x] API routers use `get_spotify_plugin()`
  - [x] Workers create plugins per job
  - [x] Services depend on `IMusicServicePlugin`

- [x] **Tests updated**
  - [x] Unit tests for `SpotifyPlugin`
  - [x] Integration tests with plugin
  - [x] No tests depend on old services

- [x] **SpotifyClient remains only for OAuth**
  - [x] `SpotifyAuthService` uses client directly (OK!)
  - [x] TokenManager uses client for refresh (OK!)
  - [x] All business logic uses plugin

---

## Related Documentation

- **[Service Separation Principles](./service-separation-principles.md)** - Architecture rules
- **[Plugin System](./plugin-system.md)** - Plugin interface definition
- **[Service Reorganization](./service-reorganization.md)** - Directory structure

---

**Status:** ✅ COMPLETED (January 2025)  
**Result:** All Spotify logic encapsulated in plugin layer  
**Next:** Apply same pattern to DeezerPlugin (already in progress)  
**Impact:** Ready for easy Tidal/Apple Music integration
