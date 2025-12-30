# Service Separation Principles

**Category:** Architecture  
**Status:** ENFORCED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Service Separation Plan](./service-separation-plan.md) | [Plugin System](./plugin-system.md)

---

## The Separation Principle

### Core Rule

```
┌─────────────────────────────────────────────────────────────────┐
│   SERVICES NEVER CALL EXTERNAL APIs DIRECTLY                   │
│   → PLUGINS do that for us!                                     │
│                                                                 │
│   LocalLibrary Services = ONLY DB + Filesystem                 │
│   Enrichment/Sync Services = Orchestrate Plugins               │
│   Plugins = Encapsulate external API communication             │
└─────────────────────────────────────────────────────────────────┘
```

---

### Architecture Layers

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
│  - Entity Mapping   │  │  - MusicBrainzPlugin (NEW!) │
│                     │  │  - slskdClient              │
└─────────────────────┘  │  - CoverArtPlugin (NEW!)    │
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

**Dependency Direction:** API → Application → Infrastructure (Repos + Plugins) → External APIs

---

## Service Categories with Rules

### 1. LocalLibrary Services

**Allowed:** DB queries, filesystem operations, ID3 tag parsing  
**Forbidden:** External API calls

| Service | Status | Notes |
|---------|--------|-------|
| `library_scanner_service.py` | ✅ OK | Only mutagen (local) |
| `library_cleanup_service.py` | ✅ OK | Only DB |
| `library_view_service.py` | ✅ OK | Only DB |
| `file_discovery_service.py` | ✅ OK | Only filesystem |

**Pattern:**
```python
class LibraryScannerService:
    """Scan local files and import to DB."""
    
    def __init__(
        self,
        track_repo: TrackRepository,
        artist_repo: ArtistRepository,
    ):
        self._track_repo = track_repo
        self._artist_repo = artist_repo
    
    async def scan_directory(self, path: Path) -> ScanResult:
        """Scan directory for audio files (NO external APIs!)."""
        # ✅ OK: Filesystem
        files = list(path.glob("**/*.mp3"))
        
        for file in files:
            # ✅ OK: ID3 parsing (mutagen library)
            tags = mutagen.File(file)
            
            # ✅ OK: DB query
            track = await self._track_repo.create(Track(...))
```

---

### 2. Enrichment Services

**Allowed:** Call plugins, manage candidates  
**Forbidden:** Import clients directly

| Service | Status | Problem | Solution |
|---------|--------|---------|----------|
| `local_library_enrichment_service.py` | 🚨 URGENT | 4 direct client imports, 2969 LOC | See `ENRICHMENT_SERVICE_EXTRACTION_PLAN.md` |
| `enrichment_service.py` | ✅ OK | Only DB queries | - |
| `discography_service.py` | ⚠️ REFACTOR | MusicBrainzClient direct | Create MusicBrainzPlugin |
| `album_completeness.py` | ⚠️ REFACTOR | MusicBrainzClient (TYPE_CHECKING) | Use MusicBrainzPlugin |

**Wrong Pattern:**
```python
# ❌ FORBIDDEN - Direct client import!
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

class DiscographyService:
    def __init__(self, musicbrainz_client: MusicBrainzClient):
        self._client = musicbrainz_client  # WRONG!
    
    async def get_artist_discography(self, mbid: str):
        # Direct API call - violates separation principle
        return await self._client.get_artist_releases(mbid)
```

**Right Pattern:**
```python
# ✅ CORRECT - Use plugin!
from soulspot.infrastructure.plugins.musicbrainz_plugin import MusicBrainzPlugin

class DiscographyService:
    def __init__(self, musicbrainz_plugin: MusicBrainzPlugin):
        self._plugin = musicbrainz_plugin  # CORRECT!
    
    async def get_artist_discography(self, mbid: str) -> list[AlbumDTO]:
        # Plugin returns typed DTOs, handles API details
        return await self._plugin.get_artist_releases(mbid)
```

---

### 3. Sync Services

**Allowed:** Call plugins for data sync  
**Forbidden:** Create HTTP clients themselves

| Service | Status | Notes |
|---------|--------|-------|
| `spotify_sync_service.py` | ✅ OK | Uses SpotifyPlugin |
| `deezer_sync_service.py` | ✅ OK | Uses DeezerPlugin |
| `album_sync_service.py` | ✅ OK | - |
| `provider_sync_orchestrator.py` | ✅ OK | Orchestrates plugins |

**Pattern:**
```python
class SpotifySyncService:
    """Sync data from Spotify (via plugin)."""
    
    def __init__(
        self,
        spotify_plugin: SpotifyPlugin,  # Plugin, not client!
        artist_repo: ArtistRepository,
    ):
        self._plugin = spotify_plugin
        self._artist_repo = artist_repo
    
    async def sync_followed_artists(self) -> list[Artist]:
        """Sync user's followed artists."""
        # ✅ Plugin call returns typed DTOs
        followed = await self._plugin.get_followed_artists()
        
        artists = []
        for artist_dto in followed.items:
            # Import to DB
            artist = await self._import_artist(artist_dto)
            artists.append(artist)
        
        return artists
```

---

### 4. Auth Services (EXCEPTION!)

**Allowed:** Use OAuth clients directly (justified!)  
**Why:** OAuth flow needs direct access to token endpoints

| Service | Status | Notes |
|---------|--------|-------|
| `spotify_auth_service.py` | ✅ OK (exception) | OAuth is legitimate |
| `deezer_auth_service.py` | ✅ OK (exception) | OAuth is legitimate |
| `token_manager.py` | ⚠️ CHECK | httpx import - is this necessary? |

**Why Exception?**

OAuth flow requires:
1. Redirect user to provider authorization page
2. Receive authorization code callback
3. Exchange code for access token (POST to token endpoint)
4. Refresh token when expired (POST to token endpoint)

These are **authentication infrastructure concerns**, not business logic.

```python
# ✅ OK: OAuth client in auth service
class SpotifyAuthService:
    def __init__(self, spotify_client: SpotifyClient):
        self._client = spotify_client  # OK for auth!
    
    async def exchange_code_for_token(self, code: str) -> SpotifyToken:
        """Exchange authorization code for access token."""
        # Direct token endpoint call is justified here
        return await self._client.exchange_code(code)
```

---

### 5. UI/View Services

**Allowed:** Call repositories, build ViewModels  
**Forbidden:** External APIs

| Service | Status | Notes |
|---------|--------|-------|
| `stats_service.py` | ✅ OK | Only DB aggregation |
| `filter_service.py` | ✅ OK | Only DB queries |
| `discover_service.py` | ✅ OK | Uses plugins correctly |
| `new_releases_service.py` | ✅ OK | Uses plugins correctly |

**Pattern:**
```python
class LibraryViewService:
    """Build ViewModels for UI templates."""
    
    def __init__(
        self,
        album_repo: AlbumRepository,
        track_repo: TrackRepository,
    ):
        self._album_repo = album_repo
        self._track_repo = track_repo
    
    async def get_album_detail_view(self, album_id: UUID) -> AlbumDetailView:
        """Build album detail ViewModel (NO external APIs!)."""
        # ✅ OK: DB queries only
        album = await self._album_repo.get_by_id(album_id)
        tracks = await self._track_repo.get_by_album_id(album_id)
        
        return AlbumDetailView(
            album=album,
            tracks=tracks,
            total_duration=sum(t.duration_ms for t in tracks),
        )
```

---

## Current Violations

### 🚨 URGENT - Fix Immediately

#### 1. `LocalLibraryEnrichmentService` (2969 LOC)

```python
# ❌ FORBIDDEN - Direct client imports!
from soulspot.infrastructure.integrations.coverartarchive_client import CoverArtArchiveClient
from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
```

**Solution:** See `ENRICHMENT_SERVICE_EXTRACTION_PLAN.md`

Create strategies using plugins:
- → `SpotifyEnrichmentStrategy` (uses SpotifyPlugin)
- → `MusicBrainzEnrichmentStrategy` (uses new MusicBrainzPlugin)
- → `DeezerEnrichmentStrategy` (uses DeezerPlugin)
- → `CoverArtStrategy` (uses new CoverArtPlugin)

---

### ⚠️ REFACTOR - Fix Soon

#### 2. `DiscographyService`

```python
# ⚠️ Direct import
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

class DiscographyService:
    def __init__(self, musicbrainz_client: MusicBrainzClient):
        self._client = musicbrainz_client  # Should be plugin!
```

**Solution:**
1. Create `MusicBrainzPlugin` (implements `IMusicServicePlugin`)
2. Update `DiscographyService` to use plugin
3. Plugin wraps `MusicBrainzClient` internally

---

#### 3. `AlbumCompletenessService`

```python
# ⚠️ TYPE_CHECKING import (still wrong!)
if TYPE_CHECKING:
    from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
```

**Why wrong?** Still creates dependency on client, even if only for typing.

**Solution:** Use `IMusicBrainzPlugin` interface for typing.

---

## Plugin Creation Checklist

When creating a new plugin for an external service:

### Step 1: Define Interface (if needed)

```python
# domain/ports/music_service_plugin.py

class IMusicBrainzPlugin(Protocol):
    """MusicBrainz service plugin interface."""
    
    async def get_artist_releases(self, mbid: str) -> list[AlbumDTO]:
        """Get artist releases from MusicBrainz."""
        ...
    
    async def search_recording(self, isrc: str) -> TrackDTO | None:
        """Search recording by ISRC."""
        ...
```

---

### Step 2: Implement Plugin

```python
# infrastructure/plugins/musicbrainz_plugin.py

class MusicBrainzPlugin:
    """MusicBrainz service plugin."""
    
    def __init__(self, musicbrainz_client: MusicBrainzClient):
        """Plugin wraps client internally."""
        self._client = musicbrainz_client
    
    async def get_artist_releases(self, mbid: str) -> list[AlbumDTO]:
        """Get artist releases (returns typed DTOs)."""
        response = await self._client.get_artist(mbid, includes=["releases"])
        
        albums = []
        for release in response["releases"]:
            albums.append(AlbumDTO(
                title=release["title"],
                release_date=release.get("date"),
                musicbrainz_id=release["id"],
                total_tracks=release.get("track-count", 0),
            ))
        
        return albums
```

---

### Step 3: Update Service to Use Plugin

```python
# Before (WRONG)
class DiscographyService:
    def __init__(self, musicbrainz_client: MusicBrainzClient):
        self._client = musicbrainz_client

# After (RIGHT)
class DiscographyService:
    def __init__(self, musicbrainz_plugin: MusicBrainzPlugin):
        self._plugin = musicbrainz_plugin
```

---

### Step 4: Update Dependency Injection

```python
# api/dependencies.py

def get_musicbrainz_plugin() -> MusicBrainzPlugin:
    """Get MusicBrainz plugin."""
    return MusicBrainzPlugin(
        musicbrainz_client=get_musicbrainz_client()
    )

def get_discography_service(
    musicbrainz_plugin: MusicBrainzPlugin = Depends(get_musicbrainz_plugin),
) -> DiscographyService:
    """Get discography service."""
    return DiscographyService(musicbrainz_plugin)
```

---

## Benefits of Plugin Architecture

### 1. Clear Boundaries

```
Service  = Business logic (WHAT to do)
Plugin   = Provider integration (HOW to get data)
Client   = HTTP wrapper (technical details)
```

---

### 2. Easy Testing

```python
# Mock plugin, not client
class MockMusicBrainzPlugin:
    async def get_artist_releases(self, mbid: str) -> list[AlbumDTO]:
        return [AlbumDTO(...)]  # Test data

# Test service in isolation
async def test_discography_service():
    service = DiscographyService(MockMusicBrainzPlugin())
    albums = await service.get_artist_discography("mbid-123")
    assert len(albums) > 0
```

---

### 3. Provider Swapping

```python
# Service works with ANY plugin implementing interface
class EnrichmentService:
    def __init__(self, plugins: list[IMusicServicePlugin]):
        self._plugins = plugins
    
    async def enrich_track(self, track: Track):
        """Try enrichment from all available plugins."""
        for plugin in self._plugins:
            if plugin.can_enrich(track):
                data = await plugin.get_track_details(track.isrc)
                # Apply enrichment
```

Easily add new providers without changing `EnrichmentService`.

---

## Verification Checklist

Before committing service changes:

- [ ] **No direct client imports** in application services
  - Allowed only in: `infrastructure/plugins/*_plugin.py`, auth services
  - Forbidden in: sync services, enrichment services, library services

- [ ] **Plugins used for external data**
  - Services depend on plugins, not clients
  - Plugins return typed DTOs

- [ ] **LocalLibrary services DB/filesystem only**
  - No HTTP calls
  - No plugin dependencies (except enrichment services)

- [ ] **Separation principles enforced**
  - Service = orchestration (WHAT)
  - Plugin = integration (HOW)
  - Client = HTTP (technical)

---

## Related Documentation

- **[Service Separation Plan](./service-separation-plan.md)** - Migration plan for violating services
- **[Plugin System](./plugin-system.md)** - Plugin architecture details
- **[Enrichment Service Extraction](./enrichment-service-extraction-plan.md)** - Fix LocalLibraryEnrichmentService

---

**Status:** ✅ ENFORCED - Violations blocked in code review  
**Next:** Fix `LocalLibraryEnrichmentService` urgently (2969 LOC, 4 client imports)  
**Priority:** HIGH - Core architectural principle
