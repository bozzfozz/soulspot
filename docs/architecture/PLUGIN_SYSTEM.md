# SoulSpot Plugin System

> **Version:** 1.0.0  
> **Status:** Production-Ready (Spotify), Stubs (Deezer, Tidal)

## Overview

Das Plugin-System ermöglicht es SoulSpot, Daten von verschiedenen Music Services (Spotify, Deezer, Tidal) in einem **einheitlichen Format** zu verarbeiten. Jedes Plugin konvertiert API-Responses zu Standard-DTOs, sodass Application Services keine Service-spezifische Logik benötigen.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │  PlaylistService │    │  ArtistService  │                   │
│   └────────┬────────┘    └────────┬────────┘                   │
│            │                      │                             │
│            └──────────┬───────────┘                             │
│                       ▼                                         │
│              PluginRegistry                                     │
│                       │                                         │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────────┐
│                       ▼            Infrastructure Layer          │
│   ┌───────────────────────────────────────────────────────┐    │
│   │              IMusicServicePlugin                       │    │
│   │  (get_artist, get_album, get_track → DTOs)            │    │
│   └───────────────────────────────────────────────────────┘    │
│            │              │              │                      │
│   ┌────────┴───┐  ┌───────┴───┐  ┌──────┴────┐                │
│   │SpotifyPlugin│  │DeezerPlugin│  │TidalPlugin│                │
│   │   ✅ Done   │  │  📝 Stub  │  │  📝 Stub │                │
│   └────────────┘  └───────────┘  └───────────┘                │
│            │                                                    │
│            ▼                                                    │
│   ┌────────────────┐                                           │
│   │ SpotifyClient  │  (Low-level HTTP, unchanged)              │
│   └────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### 1. Standard DTOs

Alle Plugins geben **DTOs** zurück, nie rohes JSON. DTOs sind in `src/soulspot/domain/dtos/` definiert:

| DTO | Beschreibung |
|-----|--------------|
| `ArtistDTO` | Künstler mit IDs für alle Services |
| `AlbumDTO` | Album mit Tracks, Artwork, Release-Info |
| `TrackDTO` | Track mit ISRC für Cross-Service-Matching |
| `PlaylistDTO` | Playlist mit Owner, Tracks, Snapshot |
| `SearchResultDTO` | Kombinierte Suchergebnisse |
| `UserProfileDTO` | User-Account-Info |
| `PaginatedResponse[T]` | Generischer Pagination-Wrapper |

### 2. Plugin Interface

Jedes Plugin implementiert `IMusicServicePlugin` aus `src/soulspot/domain/ports/plugin.py`:

```python
class IMusicServicePlugin(ABC):
    @property
    def service_type(self) -> ServiceType: ...
    @property
    def auth_type(self) -> AuthType: ...
    
    # Auth
    async def get_auth_url(self, state: str | None = None) -> str: ...
    async def handle_callback(self, code: str, ...) -> AuthStatus: ...
    
    # Data (alles gibt DTOs zurück!)
    async def get_artist(self, artist_id: str) -> ArtistDTO: ...
    async def get_album(self, album_id: str) -> AlbumDTO: ...
    async def get_track(self, track_id: str) -> TrackDTO: ...
    async def search(self, query: str, ...) -> SearchResultDTO: ...
    # ...
```

### 3. Plugin Registry

Zentrale Stelle für Plugin-Management:

```python
from soulspot.infrastructure.plugins import get_plugin_registry, SpotifyPlugin

# Registrierung
registry = get_plugin_registry()
registry.register(spotify_plugin)

# Verwendung
spotify = registry.get(ServiceType.SPOTIFY)
artist = await spotify.get_artist("4dpARuHxo51G3z768sgnrY")
```

## Usage Examples

### Basic Usage

```python
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.integrations import SpotifyClient

# Setup
client = SpotifyClient(spotify_settings)
plugin = SpotifyPlugin(client, access_token="...")

# Artist abrufen (gibt ArtistDTO zurück!)
artist = await plugin.get_artist("4dpARuHxo51G3z768sgnrY")
print(artist.name)  # "Adele"
print(artist.genres)  # ["pop", "soul"]
print(artist.spotify_id)  # "4dpARuHxo51G3z768sgnrY"

# Album mit Tracks
album = await plugin.get_album("1ATL5GLyefJaxhQzSPVrLX")
print(album.title)  # "30"
print(len(album.tracks))  # 12

# Suche
results = await plugin.search("Adele", types=["artist", "album"])
print(results.total_artists)  # 50
print(results.artists[0].name)  # "Adele"
```

### In Application Services

```python
from soulspot.infrastructure.plugins import get_plugin_registry
from soulspot.domain.ports.plugin import ServiceType

class PlaylistImportService:
    def __init__(self, registry: PluginRegistry):
        self.registry = registry
    
    async def import_playlist(self, service: ServiceType, playlist_id: str):
        plugin = self.registry.require(service)
        
        # Plugin gibt PlaylistDTO zurück - einheitliches Format!
        playlist = await plugin.get_playlist(playlist_id)
        
        # Tracks holen (paginiert)
        all_tracks = []
        offset = 0
        while True:
            response = await plugin.get_playlist_tracks(playlist_id, offset=offset)
            all_tracks.extend(response.items)
            if not response.has_next:
                break
            offset = response.next_offset
        
        # Jetzt haben wir list[TrackDTO] - egal ob Spotify/Deezer/Tidal
        return playlist, all_tracks
```

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

## Adding a New Plugin

1. **Create Plugin Class** in `src/soulspot/infrastructure/plugins/`:

```python
# src/soulspot/infrastructure/plugins/newservice_plugin.py
from soulspot.domain.ports.plugin import IMusicServicePlugin, ServiceType

class NewServicePlugin(IMusicServicePlugin):
    @property
    def service_type(self) -> ServiceType:
        return ServiceType.NEWSERVICE  # Add to ServiceType enum first!
    
    async def get_artist(self, artist_id: str) -> ArtistDTO:
        # Fetch from API
        data = await self._client.get_artist(artist_id)
        # Convert to DTO
        return self._convert_artist(data)
    
    def _convert_artist(self, data: dict) -> ArtistDTO:
        return ArtistDTO(
            name=data["name"],
            source_service="newservice",
            # Map all available fields...
        )
```

2. **Add ServiceType** in `src/soulspot/domain/ports/plugin.py`:

```python
class ServiceType(str, Enum):
    SPOTIFY = "spotify"
    DEEZER = "deezer"
    TIDAL = "tidal"
    NEWSERVICE = "newservice"  # Add here
```

3. **Export in `__init__.py`**:

```python
# src/soulspot/infrastructure/plugins/__init__.py
from .newservice_plugin import NewServicePlugin
__all__ = [..., "NewServicePlugin"]
```

4. **Register on Startup**:

```python
# In app startup / dependency injection
registry = get_plugin_registry()
registry.register(NewServicePlugin(client))
```

## DTO Field Mapping

### ArtistDTO

| Field | Spotify | Deezer | Tidal |
|-------|---------|--------|-------|
| `name` | `name` | `name` | `name` |
| `spotify_id` | `id` | - | - |
| `deezer_id` | - | `id` | - |
| `tidal_id` | - | - | `id` |
| `image_url` | `images[1].url` | `picture_medium` | `picture` |
| `genres` | `genres[]` | - (nur top-level) | - |
| `popularity` | `popularity` | `nb_fan` | `popularity` |

### TrackDTO

| Field | Spotify | Deezer | Tidal |
|-------|---------|--------|-------|
| `title` | `name` | `title` | `title` |
| `isrc` | `external_ids.isrc` | `isrc` | `isrc` |
| `duration_ms` | `duration_ms` | `duration * 1000` | `duration * 1000` |
| `explicit` | `explicit` | `explicit_lyrics` | `explicit` |
| `preview_url` | `preview_url` | `preview` | - |

## Testing

### Unit Tests

```python
import pytest
from soulspot.infrastructure.plugins import SpotifyPlugin

@pytest.fixture
def mock_client():
    client = Mock(spec=SpotifyClient)
    client.get_artist.return_value = {
        "id": "123",
        "name": "Test Artist",
        "genres": ["rock"],
        "images": [{"url": "http://..."}],
    }
    return client

async def test_get_artist_returns_dto(mock_client):
    plugin = SpotifyPlugin(mock_client, access_token="test")
    
    artist = await plugin.get_artist("123")
    
    assert isinstance(artist, ArtistDTO)
    assert artist.name == "Test Artist"
    assert artist.source_service == "spotify"
    assert artist.spotify_id == "123"
```

### Integration Tests

```python
@pytest.mark.integration
async def test_spotify_plugin_live():
    """Requires SPOTIFY_ACCESS_TOKEN env var."""
    token = os.environ.get("SPOTIFY_ACCESS_TOKEN")
    if not token:
        pytest.skip("No access token")
    
    plugin = SpotifyPlugin(SpotifyClient(settings), token)
    
    # Real API call
    artist = await plugin.get_artist("4dpARuHxo51G3z768sgnrY")
    
    assert artist.name == "Adele"
    assert artist.spotify_id == "4dpARuHxo51G3z768sgnrY"
```

## Migration from Direct SpotifyClient Usage

### Before (Direct Client)

```python
# Service musste JSON konvertieren
data = await spotify_client.get_artist(artist_id, token)
artist = Artist(
    id=ArtistId(str(uuid4())),
    name=data["name"],
    spotify_uri=data["uri"],
    genres=data.get("genres", []),
    # ... viel Boilerplate
)
```

### After (Plugin)

```python
# Plugin gibt DTO zurück - Service erstellt nur Entity
dto = await spotify_plugin.get_artist(artist_id)
artist = Artist(
    id=ArtistId(str(uuid4())),
    name=dto.name,
    spotify_uri=dto.spotify_uri,
    genres=dto.genres,
    # Viel cleaner!
)
```

## Future Work

- [ ] **DeezerPlugin** vollständig implementieren
- [ ] **TidalPlugin** vollständig implementieren
- [ ] **MusicBrainz Metadata Plugin** (IMetadataPlugin)
- [ ] **Plugin Health Checks** (Rate Limit Status, Token Validity)
- [ ] **Caching Layer** für häufige Abfragen
- [ ] **Parallel Multi-Service Search** (alle Plugins gleichzeitig)
- [ ] **SpotifySyncService** auf SpotifyPlugin umstellen
- [ ] **API Router** Dependencies auf SpotifyPlugin umstellen

## Migration Status

### Application Services - Refactored ✅

| Service | Status | Notes |
|---------|--------|-------|
| `AlbumCompletenessService` | ✅ Done | Uses SpotifyPlugin for album fetching |
| `DiscographyService` | ✅ Done | Removed unused SpotifyClient dependency |
| `WatchlistService` | ✅ Done | Uses SpotifyPlugin for artist albums |
| `ArtworkService` | ✅ Done | Uses SpotifyPlugin for album/track artwork |
| `PostProcessingPipeline` | ✅ Done | Passes SpotifyPlugin to ArtworkService |
| `AutoImportService` | ✅ Done | Passes SpotifyPlugin to pipeline |
| `FollowedArtistsService` | ✅ Done | Uses SpotifyPlugin for followed artists sync |
| `ArtistSongsService` | ✅ Done | Uses SpotifyPlugin for top tracks |

### Not Yet Migrated

| Service | Reason |
|---------|--------|
| `SpotifySyncService` | Large service (~1248 lines), needs careful migration |
| API Routers | Many routers use SpotifyClient directly via dependencies |

### Breaking Changes

Services that were refactored no longer accept `access_token` parameter!
The SpotifyPlugin handles token management internally.

**Before:**
```python
service = FollowedArtistsService(session, spotify_client)
await service.sync_followed_artists(access_token)
```

**After:**
```python
service = FollowedArtistsService(session, spotify_plugin)  # Plugin has token
await service.sync_followed_artists()  # No token param!
```

