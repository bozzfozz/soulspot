# SoulSpot Data Standards

> **The Definitive Reference for Internal Data Formats**

## Overview

This document defines **SoulSpot's internal data standards**. All plugins must convert external API responses into these standard formats (DTOs).

**Key Principle**: External services use different formats (Spotify JSON ≠ Deezer JSON). SoulSpot normalizes everything into unified DTOs at the plugin boundary.

---

## 1. Core Data Transfer Objects (DTOs)

SoulSpot uses **DTOs** as the standard internal format for all data:

| DTO | Purpose | Source |
|-----|-------|--------|
| `ArtistDTO` | Artist metadata | Plugins (Spotify, Deezer, Tidal, MusicBrainz) |
| `AlbumDTO` | Album metadata | Plugins |
| `TrackDTO` | Track metadata | Plugins |
| `PlaylistDTO` | Playlist metadata | Plugins |
| `UserProfileDTO` | User profile | Plugins |
| `SearchResultDTO` | Search results | Plugins |
| `PaginatedResponse[T]` | Paginated lists | Plugins |

**Location**: `src/soulspot/infrastructure/plugins/dto.py`

---

## 2. Multi-Service ID Fields (CRITICAL!)

Every DTO includes ID fields for **EVERY supported service**:

### Artist Example
```python
ArtistDTO(
    # SoulSpot internal UUID (set by ProviderMappingService)
    internal_id: str | None = None,     # "550e8400-e29b-41d4-a716-446655440000"
    
    # Spotify IDs
    spotify_id: str | None = None,      # "4dpARuHxo51G3z768sgnrY" (ID only)
    spotify_uri: str | None = None,     # "spotify:artist:4dpARuHxo51G3z768sgnrY" (full URI)
    
    # Other service IDs
    deezer_id: str | None = None,       # "12345"
    tidal_id: str | None = None,        # "7654321"
    musicbrainz_id: str | None = None,  # "f27ec8db-af05-4f36-916e-3d57f91ecf5e"
)
```

### ID Field Rules

| Field | Format | When to Set |
|-------|--------|------------|
| `internal_id` | UUID string | **ONLY** by `ProviderMappingService` (after DB lookup) |
| `spotify_id` | ID part only | Plugin sets when data comes from Spotify |
| `spotify_uri` | `spotify:type:id` | Plugin sets when data comes from Spotify |
| `deezer_id` | String | Plugin sets when data comes from Deezer |
| `musicbrainz_id` | UUID | Plugin sets when data comes from MusicBrainz |

**Why Both `spotify_id` and `spotify_uri`?**
- **spotify_uri**: Database storage format (full URI for disambiguation)
- **spotify_id**: API request format (Spotify API wants just the ID)
- Conversion: `spotify_id` extracted from `spotify_uri` via `@property`

---

## 3. Required Fields by DTO

### 3.1 ArtistDTO

```python
@dataclass
class ArtistDTO:
    # REQUIRED
    name: str                  # Artist name
    source_service: str        # "spotify", "deezer", "tidal", "musicbrainz"
    
    # OPTIONAL - at least ONE ID should be set
    internal_id: str | None    # Set by ProviderMappingService
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    tidal_id: str | None       
    musicbrainz_id: str | None 
    
    # OPTIONAL metadata
    image: ImageRef            # Profile image (url + path)
    genres: list[str]          # ["rock", "alternative"]
    tags: list[str]            # User-defined tags
    popularity: int | None     # 0-100 (Spotify)
    followers: int | None      # Follower count
    disambiguation: str | None # MusicBrainz disambiguation
    external_urls: dict        # {"spotify": "https://..."}
```

**ImageRef Value Object**:
```python
artist.image.url   # CDN URL (external)
artist.image.path  # Local cache path
artist.image.has_image  # True if any image available
```

### 3.2 AlbumDTO

```python
@dataclass
class AlbumDTO:
    # REQUIRED
    title: str                 # Album title
    artist_name: str           # Primary artist
    source_service: str        # "spotify", "deezer", etc.
    
    # OPTIONAL - at least ONE ID should be set
    internal_id: str | None    
    artist_internal_id: str | None  # Artist's SoulSpot UUID
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    artist_spotify_id: str | None   # Artist's Spotify ID
    artist_deezer_id: str | None    
    
    # OPTIONAL metadata
    release_date: str | None   # "YYYY-MM-DD" or "YYYY"
    release_year: int | None   # Extracted year
    cover: ImageRef            # Cover art (url + path)
    total_tracks: int | None   
    
    # Album type (Lidarr-style)
    album_type: str = "album"  # "album", "single", "ep", "compilation"
    primary_type: str = "Album"
    secondary_types: list[str] # ["Compilation", "Live"]
    
    # Nested tracks (optional, usually loaded separately)
    tracks: list[TrackDTO]     
```

### 3.3 TrackDTO

```python
@dataclass
class TrackDTO:
    # REQUIRED
    title: str                 # Track title
    artist_name: str           # Primary artist
    source_service: str        # "spotify", "deezer", etc.
    
    # IDs
    internal_id: str | None    
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    isrc: str | None           # CRITICAL for cross-service matching!
    
    # Artist references
    internal_artist_id: str | None
    artist_spotify_id: str | None
    
    # Album references (optional for singles)
    internal_album_id: str | None
    album_name: str | None
    album_spotify_id: str | None
    
    # Metadata
    duration_ms: int = 0       # Duration in milliseconds
    track_number: int | None   
    disc_number: int = 1       
    explicit: bool = False     
    popularity: int | None     # 0-100
    preview_url: str | None    # 30-second preview
    cover: ImageRef            # Track/single cover (url + path)
    
    # Nested objects
    additional_artists: list[ArtistDTO]  # Featured artists
    artists: list[ArtistDTO]   # Primary + additional
    album: AlbumDTO | None     # Optional album context
```

**ISRC Importance**: ISRC (International Standard Recording Code) is the **primary key** for matching tracks across services:
- `USABC1234567` identifies the same recording on Spotify, Deezer, Tidal, Apple Music
- Use ISRC for deduplication when aggregating multi-provider results

---

## 4. Plugin Translation Rules

### 4.1 Spotify → SoulSpot

```python
# src/soulspot/infrastructure/plugins/spotify_plugin.py

def _convert_artist(self, raw: dict) -> ArtistDTO:
    """
    Spotify API          →  SoulSpot DTO
    ───────────────────────────────────────
    raw["name"]          →  name
    raw["id"]            →  spotify_id
    raw["uri"]           →  spotify_uri
    raw["images"][0-1]   →  image.url (320px preferred)
    raw["genres"]        →  genres
    raw["popularity"]    →  popularity
    raw["followers"]["total"] → followers
    raw["external_urls"] →  external_urls
    """
    return ArtistDTO(
        name=raw.get("name", "Unknown"),
        source_service="spotify",
        spotify_id=raw.get("id"),
        spotify_uri=raw.get("uri"),
        image=ImageRef(url=self._extract_image(raw, size=320)),
        genres=raw.get("genres", []),
        popularity=raw.get("popularity"),
        followers=raw.get("followers", {}).get("total"),
        external_urls=raw.get("external_urls", {}),
    )
```

### 4.2 Deezer → SoulSpot

```python
# src/soulspot/infrastructure/plugins/deezer_plugin.py

def _convert_artist(self, raw: dict) -> ArtistDTO:
    """
    Deezer API           →  SoulSpot DTO
    ───────────────────────────────────────
    raw["name"]          →  name
    raw["id"]            →  deezer_id (as String!)
    raw["picture_medium"] → image.url
    raw["nb_fan"]        →  followers
    raw["link"]          →  external_urls["deezer"]
    """
    return ArtistDTO(
        name=raw.get("name", "Unknown"),
        source_service="deezer",
        deezer_id=str(raw.get("id", "")),  # ALWAYS String!
        image=ImageRef(url=raw.get("picture_medium")),
        followers=raw.get("nb_fan"),
        external_urls={"deezer": raw.get("link", "")},
    )
```

### 4.3 Track Mapping - ISRC is KEY!

```python
def _convert_track(self, raw: dict) -> TrackDTO:
    """Track conversion with ISRC for cross-service matching."""
    return TrackDTO(
        title=raw.get("name"),
        artist_name=raw.get("artists", [{}])[0].get("name"),
        source_service="spotify",
        
        spotify_id=raw.get("id"),
        spotify_uri=raw.get("uri"),
        
        # CRITICAL: ISRC for deduplication!
        isrc=raw.get("external_ids", {}).get("isrc"),
        
        duration_ms=raw.get("duration_ms", 0),
        explicit=raw.get("explicit", False),
        popularity=raw.get("popularity"),
        preview_url=raw.get("preview_url"),
        track_number=raw.get("track_number"),
        disc_number=raw.get("disc_number", 1),
    )
```

---

## 5. Data Flow Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL APIs                                │
│                                                                    │
│  Spotify: {"name": "...", "id": "...", "uri": "spotify:artist:..."} │
│  Deezer:  {"name": "...", "id": 12345, "picture_medium": "..."}     │
│  Tidal:   {"name": "...", "id": "...", "imageUrl": "..."}          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ raw dict/JSON
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                         PLUGINS (Translation Layer)                 │
│                                                                    │
│  SpotifyPlugin._convert_artist(raw) → ArtistDTO                    │
│  DeezerPlugin._convert_artist(raw)  → ArtistDTO                    │
│  TidalPlugin._convert_artist(raw)   → ArtistDTO                    │
│                                                                    │
│  ALL return the SAME format!                                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Standard DTOs
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    SOULSPOT INTERNAL STANDARD                       │
│                                                                    │
│  ArtistDTO:                                                        │
│    name: "The Beatles"                                             │
│    source_service: "spotify"                                       │
│    spotify_id: "3WrFJ7ztbogyGnTHbHJFl2"                            │
│    spotify_uri: "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2"            │
│    deezer_id: None  (from Spotify)                                 │
│    image: ImageRef(url="https://i.scdn.co/image/...")              │
│    genres: ["british invasion", "rock"]                            │
│                                                                    │
│  → All services use THIS format!                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Standard DTOs
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│               PROVIDER MAPPING SERVICE (ID Resolution)              │
│                                                                    │
│  map_artist_dto(dto) → dto with internal_id                        │
│                                                                    │
│  DB Lookup:                                                        │
│    1. spotify_uri present? → internal_id                           │
│    2. deezer_id present? → internal_id                             │
│    3. Name match? → internal_id                                    │
│                                                                    │
│  Output: Same DTO but with internal_id if found                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ DTOs with internal_id
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│               APPLICATION SERVICES (Business Logic)                 │
│                                                                    │
│  FollowedArtistsService.sync()                                     │
│  ChartsService.get_charts()                                        │
│  DiscoverService.get_related()                                     │
│                                                                    │
│  → Work ONLY with standard DTOs                                    │
│  → No service-specific logic                                       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 6. Plugin Conversion Checklist

When adding a new service (e.g., Apple Music), ensure:

### 6.1 Artist Conversion
- [ ] `name` → Required field
- [ ] `source_service` → "apple_music"
- [ ] `apple_music_id` → Service ID (as String!)
- [ ] `image.url` → Image URL extracted
- [ ] `genres` → Genre list (if available)
- [ ] `external_urls` → Profile link

### 6.2 Track Conversion
- [ ] `title` → Required field
- [ ] `artist_name` → Primary artist
- [ ] `source_service` → "apple_music"
- [ ] `apple_music_id` → Track ID
- [ ] **`isrc`** → CRITICAL for cross-service matching!
- [ ] `duration_ms` → Duration in milliseconds
- [ ] `explicit` → Explicit flag
- [ ] `preview_url` → Preview link (if available)

### 6.3 Album Conversion
- [ ] `title` → Required field
- [ ] `artist_name` → Required field
- [ ] `source_service` → "apple_music"
- [ ] `album_type` → "album", "single", "ep", "compilation"
- [ ] `release_date` → ISO format "YYYY-MM-DD"
- [ ] `cover.url` → Cover art

---

## 7. Important Conventions

### 7.1 String IDs Everywhere!

```python
# ❌ WRONG - Integer ID
deezer_id=raw["id"]  # Deezer returns Integer!

# ✅ RIGHT - String ID
deezer_id=str(raw.get("id", ""))
```

**Why?** Database stores all IDs as strings, mixing types causes errors.

### 7.2 source_service is Required!

```python
# ❌ WRONG - Where did data come from?
ArtistDTO(name="Beatles")

# ✅ RIGHT - Source is clear
ArtistDTO(name="Beatles", source_service="spotify")
```

**Why?** Multi-provider aggregation needs to track which service provided the data.

### 7.3 Defensive Coding

```python
# ❌ WRONG - Crashes if data missing
image_url=raw["images"][0]["url"]

# ✅ RIGHT - Defensive extraction
images = raw.get("images", [])
image_url = images[0].get("url") if images else None
```

### 7.4 Consistent Image Sizes

```python
# Standard: 320px for thumbnails, 640px for large views
def _extract_image(self, raw: dict, size: int = 320) -> str | None:
    images = raw.get("images", [])
    if not images:
        return None
    
    # Find image with matching size
    for img in images:
        if img.get("width", 0) == size:
            return img.get("url")
    
    # Fallback: first image
    return images[0].get("url")
```

---

## 8. Quick Reference: Field Mapping

### Spotify → SoulSpot

| Spotify | SoulSpot DTO |
|---------|--------------|
| `id` | `spotify_id` |
| `uri` | `spotify_uri` |
| `name` | `name` / `title` |
| `images[].url` | `image.url` / `cover.url` |
| `genres` | `genres` |
| `popularity` | `popularity` |
| `followers.total` | `followers` |
| `duration_ms` | `duration_ms` |
| `track_number` | `track_number` |
| `disc_number` | `disc_number` |
| `explicit` | `explicit` |
| `preview_url` | `preview_url` |
| `external_ids.isrc` | `isrc` |
| `release_date` | `release_date` |
| `album_type` | `album_type` |

### Deezer → SoulSpot

| Deezer | SoulSpot DTO |
|--------|--------------|
| `id` | `deezer_id` (as String!) |
| `name` / `title` | `name` / `title` |
| `picture_medium` | `image.url` |
| `cover_medium` | `cover.url` |
| `nb_fan` | `followers` |
| `duration` | `duration_ms * 1000` (Deezer gives seconds!) |
| `track_position` | `track_number` |
| `disk_number` | `disc_number` |
| `explicit_lyrics` | `explicit` |
| `preview` | `preview_url` |
| `isrc` | `isrc` |
| `release_date` | `release_date` |
| `record_type` | `album_type` |

---

## Summary

**Key Principles**:
1. **Unified Format**: All plugins convert to standard DTOs
2. **Multi-Service IDs**: Every DTO has fields for ALL services
3. **ISRC is Critical**: Use ISRC for cross-service track matching
4. **String IDs**: All service IDs stored as strings
5. **Defensive Coding**: Handle missing data gracefully
6. **Source Tracking**: Always set `source_service`

**DTO Hierarchy**:
```
External API Response (raw dict)
        ↓
Plugin Translation (_convert_* methods)
        ↓
Standard DTO (ArtistDTO, AlbumDTO, TrackDTO)
        ↓
Provider Mapping (internal_id resolution)
        ↓
Application Services (business logic)
```

---

## See Also

- [Core Philosophy](./core-philosophy.md) - Multi-provider aggregation principle
- [Data Layer Patterns](./data-layer-patterns.md) - Code examples for common operations
- [Plugin System](./plugin-system.md) - Plugin interface and implementation
- `src/soulspot/infrastructure/plugins/dto.py` - DTO definitions

---

**Document Status**: Migrated from `docs/architecture/DATA_STANDARDS.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/infrastructure/plugins/dto.py` - DTO definitions (lines 1-800+)
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - Spotify conversion methods
- `src/soulspot/infrastructure/plugins/deezer_plugin.py` - Deezer conversion methods
