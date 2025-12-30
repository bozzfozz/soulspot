# SoulSpot Plugin System

> **Multi-Provider Music Service Integration**

## Overview

The Plugin System enables SoulSpot to process data from different music services (Spotify, Deezer, Tidal) in a **unified format**. Each plugin converts API responses to standard DTOs, so application services don't need service-specific logic.

**Key Principle**: External APIs → Plugin Translation → Standard DTOs → Application Logic

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Application Layer                           │
│                                                                  │
│   ┌─────────────────┐    ┌─────────────────┐                    │
│   │  PlaylistService │    │  ArtistService  │                    │
│   └────────┬────────┘    └────────┬────────┘                    │
│            │                      │                              │
│            └──────────┬───────────┘                              │
│                       ▼                                          │
│              Plugin Registry                                     │
│                       │                                          │
└───────────────────────┼──────────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────────┐
│                       ▼            Infrastructure Layer           │
│   ┌───────────────────────────────────────────────────────┐     │
│   │              IMusicServicePlugin                       │     │
│   │  (get_artist, get_album, get_track → DTOs)            │     │
│   └───────────────────────────────────────────────────────┘     │
│            │              │              │                       │
│   ┌────────┴───┐  ┌───────┴───┐  ┌──────┴────┐                 │
│   │SpotifyPlugin│  │DeezerPlugin│  │TidalPlugin│  (Future)      │
│   │   ✅ Full   │  │  ✅ Full  │  │  📝 Stub  │                 │
│   └────────────┘  └───────────┘  └───────────┘                 │
│            │                                                     │
│            ▼                                                     │
│   ┌────────────────┐                                            │
│   │ SpotifyClient  │  (Low-level HTTP, unchanged)               │
│   └────────────────┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. Standard DTOs

All plugins return **DTOs**, never raw JSON. DTOs defined in `src/soulspot/infrastructure/plugins/dto.py`:

| DTO | Description |
|-----|-------------|
| `ArtistDTO` | Artist with IDs for all services |
| `AlbumDTO` | Album with tracks, artwork, release info |
| `TrackDTO` | Track with ISRC for cross-service matching |
| `PlaylistDTO` | Playlist with owner, tracks, snapshot |
| `SearchResultDTO` | Combined search results |
| `UserProfileDTO` | User account info |
| `PaginatedResponse[T]` | Generic pagination wrapper |

**Why DTOs?**
- Uniform interface for application services
- Type safety (not raw dicts)
- Multi-provider aggregation (same DTO from different sources)

### 2. Plugin Interface

Each plugin implements `IMusicServicePlugin` from `src/soulspot/domain/ports/plugin.py`:

```python
class IMusicServicePlugin(ABC):
    @property
    def service_type(self) -> ServiceType: ...
    
    @property
    def auth_type(self) -> AuthType: ...
    
    # Auth
    async def get_auth_url(self, state: str | None = None) -> str: ...
    async def handle_callback(self, code: str, ...) -> AuthStatus: ...
    
    # Capabilities
    def can_use(self, capability: PluginCapability) -> bool: ...
    def get_capabilities(self) -> list[CapabilityInfo]: ...
    
    # Data (all return DTOs!)
    async def get_artist(self, artist_id: str) -> ArtistDTO: ...
    async def get_album(self, album_id: str) -> AlbumDTO: ...
    async def get_track(self, track_id: str) -> TrackDTO: ...
    async def search(self, query: str, ...) -> SearchResultDTO: ...
    # ...
```

**Code Reference**: `src/soulspot/domain/ports/plugin.py` (lines 1-300+)

### 3. Plugin Capabilities

Each plugin declares what it can do via `PluginCapability` enum:

```python
class PluginCapability(Enum):
    # User Library
    USER_FOLLOWED_ARTISTS = "user_followed_artists"
    USER_PLAYLISTS = "user_playlists"
    USER_SAVED_ALBUMS = "user_saved_albums"
    USER_SAVED_TRACKS = "user_saved_tracks"
    
    # Browse
    BROWSE_NEW_RELEASES = "browse_new_releases"
    BROWSE_FEATURED_PLAYLISTS = "browse_featured_playlists"
    BROWSE_CHARTS = "browse_charts"
    BROWSE_GENRES = "browse_genres"
    
    # Metadata
    GET_ARTIST = "get_artist"
    GET_ALBUM = "get_album"
    GET_TRACK = "get_track"
    GET_ARTIST_ALBUMS = "get_artist_albums"
    GET_ARTIST_TOP_TRACKS = "get_artist_top_tracks"
    
    # Search
    SEARCH_ARTISTS = "search_artists"
    SEARCH_ALBUMS = "search_albums"
    SEARCH_TRACKS = "search_tracks"
```

**Capability Check Pattern**:
```python
# Check if capability can be used RIGHT NOW
# (considers both: is feature supported + is auth available if needed)
if spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
    artists = await spotify_plugin.get_followed_artists()

if deezer_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
    releases = await deezer_plugin.get_browse_new_releases()
```

**Why Capabilities?**
- Services have different features (Deezer has charts, Spotify doesn't)
- Auth requirements differ (Spotify needs auth for everything, Deezer browse is public)
- `can_use()` combines feature check + auth check in one call

---

## Usage Examples

### Basic Usage

```python
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.integrations import SpotifyClient

# Setup
client = SpotifyClient(spotify_settings)
plugin = SpotifyPlugin(client, access_token="...")

# Get artist (returns ArtistDTO!)
artist = await plugin.get_artist("4dpARuHxo51G3z768sgnrY")
print(artist.name)  # "Adele"
print(artist.genres)  # ["pop", "soul"]
print(artist.spotify_id)  # "4dpARuHxo51G3z768sgnrY"

# Get album with tracks
album = await plugin.get_album("1ATL5GLyefJaxhQzSPVrLX")
print(album.title)  # "30"
print(len(album.tracks))  # 12

# Search
results = await plugin.search("Adele", types=["artist", "album"])
print(results.total_artists)  # 50
print(results.artists[0].name)  # "Adele"
```

### In Application Services

```python
from soulspot.infrastructure.plugins import SpotifyPlugin, DeezerPlugin
from soulspot.domain.ports.plugin import PluginCapability

class BrowseService:
    def __init__(self, spotify: SpotifyPlugin, deezer: DeezerPlugin):
        self._spotify = spotify
        self._deezer = deezer
    
    async def get_new_releases(self) -> list[AlbumDTO]:
        """Get new releases from ALL available providers."""
        all_releases = []
        seen_keys = set()
        
        # 1. Deezer (no auth needed)
        if self._deezer.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for release in await self._deezer.get_browse_new_releases():
                key = self._normalize(release.artist, release.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    release.source = "deezer"
                    all_releases.append(release)
        
        # 2. Spotify (auth required)
        if self._spotify.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for release in await self._spotify.get_new_releases():
                key = self._normalize(release.artist, release.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    release.source = "spotify"
                    all_releases.append(release)
        
        return sorted(all_releases, key=lambda x: x.release_date, reverse=True)
```

**Pattern**: Multi-provider aggregation with deduplication

### Error Handling

```python
from soulspot.domain.ports.plugin import PluginError, ServiceType

try:
    artist = await plugin.get_artist("invalid_id")
except PluginError as e:
    print(f"Service: {e.service.value}")  # "spotify"
    print(f"Error: {e.message}")
    print(f"Recoverable: {e.recoverable}")
    if e.original_error:
        # Original HTTP error
        print(f"Original: {e.original_error}")
```

---

## Adding a New Plugin

### 1. Create Plugin Class

```python
# src/soulspot/infrastructure/plugins/newservice_plugin.py
from soulspot.domain.ports.plugin import IMusicServicePlugin, ServiceType

class NewServicePlugin(IMusicServicePlugin):
    @property
    def service_type(self) -> ServiceType:
        return ServiceType.NEWSERVICE  # Add to ServiceType enum first!
    
    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2  # or NO_AUTH
    
    def can_use(self, capability: PluginCapability) -> bool:
        """Check if capability is available."""
        # Check if capability is supported
        if capability not in self._supported_capabilities:
            return False
        
        # Check if auth required for this capability
        if self._capability_requires_auth(capability):
            return self.is_authenticated
        
        return True
    
    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Fetch artist from API and convert to DTO."""
        # 1. Fetch from API
        data = await self._client.get_artist(artist_id)
        
        # 2. Convert to DTO
        return self._convert_artist(data)
    
    def _convert_artist(self, data: dict) -> ArtistDTO:
        """Convert raw API response to ArtistDTO."""
        return ArtistDTO(
            name=data["name"],
            source_service="newservice",
            newservice_id=str(data["id"]),
            image=ImageRef(url=data.get("image_url")),
            genres=data.get("genres", []),
            # Map all available fields...
        )
```

### 2. Add ServiceType Enum Value

```python
# src/soulspot/domain/ports/plugin.py

class ServiceType(Enum):
    SPOTIFY = "spotify"
    DEEZER = "deezer"
    TIDAL = "tidal"
    NEWSERVICE = "newservice"  # ← Add here
```

### 3. Register Plugin

```python
# src/soulspot/infrastructure/plugins/__init__.py

from .newservice_plugin import NewServicePlugin

def get_plugin_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(spotify_plugin)
    registry.register(deezer_plugin)
    registry.register(newservice_plugin)  # ← Add here
    return registry
```

---

## Plugin Conversion Checklist

When implementing `_convert_*()` methods:

- [ ] Set `source_service` to plugin name
- [ ] Convert all IDs to strings
- [ ] Map service-specific ID field (e.g., `deezer_id`, `spotify_id`)
- [ ] Extract ISRC (critical for track deduplication!)
- [ ] Use `ImageRef` for images (url + path)
- [ ] Handle missing data defensively (`.get()` with defaults)
- [ ] Convert durations to milliseconds
- [ ] Normalize booleans (explicit flags)

**Example Track Conversion**:
```python
def _convert_track(self, data: dict) -> TrackDTO:
    return TrackDTO(
        title=data.get("name", "Unknown"),
        artist_name=data.get("artists", [{}])[0].get("name", "Unknown"),
        source_service="spotify",
        
        # IDs
        spotify_id=data.get("id"),
        spotify_uri=data.get("uri"),
        isrc=data.get("external_ids", {}).get("isrc"),  # CRITICAL!
        
        # Metadata
        duration_ms=data.get("duration_ms", 0),
        explicit=data.get("explicit", False),
        popularity=data.get("popularity"),
        preview_url=data.get("preview_url"),
        
        # Album reference (if needed)
        album_name=data.get("album", {}).get("name"),
        album_spotify_id=data.get("album", {}).get("id"),
    )
```

---

## Summary

**Plugin System Benefits**:
1. **Unified Interface**: All plugins return same DTOs
2. **Multi-Provider**: Easily aggregate data from multiple services
3. **Type Safety**: DTOs enforce structure, not raw dicts
4. **Swappable**: Add/remove services without changing application code
5. **Capability-Based**: Services declare what they support

**Plugin Lifecycle**:
```
External API Response (raw dict)
        ↓
Plugin _convert_*() method
        ↓
Standard DTO (ArtistDTO, AlbumDTO, TrackDTO)
        ↓
Application Service (business logic)
        ↓
API Response (JSON)
```

**Key Files**:
- `src/soulspot/domain/ports/plugin.py` - Plugin interface + capabilities
- `src/soulspot/infrastructure/plugins/dto.py` - Standard DTOs
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - Spotify implementation
- `src/soulspot/infrastructure/plugins/deezer_plugin.py` - Deezer implementation

---

## See Also

- [Data Standards](./data-standards.md) - DTO field definitions
- [Core Philosophy](./core-philosophy.md) - Multi-provider aggregation principle
- [Data Layer Patterns](./data-layer-patterns.md) - Plugin usage patterns
- [Error Handling](./error-handling.md) - Plugin error patterns

---

**Document Status**: Migrated from `docs/architecture/PLUGIN_SYSTEM.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/domain/ports/plugin.py` - Plugin interface + capabilities
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - Spotify plugin implementation
- `src/soulspot/infrastructure/plugins/deezer_plugin.py` - Deezer plugin implementation
- `src/soulspot/infrastructure/plugins/dto.py` - DTO definitions
