# Service-Agnostic Backend Architecture

**Category:** Architecture  
**Status:** IMPLEMENTED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Plugin System](./plugin-system.md) | [Data Standards](./data-standards.md) | [Core Philosophy](./core-philosophy.md)

---

## Overview

SoulSpot's backend is designed to work with **ANY music service** (Spotify, Tidal, Deezer, Apple Music, etc.) without changing core domain logic.

**Key Principle:**
- **Domain Layer:** Generic, service-agnostic (works with any provider)
- **Infrastructure Layer:** Service-specific (adapters for each provider)

This enables:
- ✅ Add new services without touching domain code
- ✅ Switch providers seamlessly (user preference)
- ✅ Aggregate data from multiple services
- ✅ Deduplicate across providers (same track from Spotify + Deezer)

---

## Layer Separation

```
┌───────────────────────────────────────────────────────────┐
│                      API LAYER                             │
│                                                            │
│  FastAPI Routes                                           │
│  ├── /api/spotify/auth          ← Service-specific auth   │
│  ├── /api/deezer/auth                                     │
│  ├── /api/playlists             ← Service-agnostic        │
│  ├── /api/artists                                         │
│  └── /api/library                                         │
└───────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                         │
│                                                            │
│  Services (Orchestration)                                 │
│  ├── SpotifySyncService         ← Service-specific       │
│  ├── DeezerSyncService                                   │
│  ├── PlaylistService            ← Generic                │
│  ├── TrackService                                        │
│  └── ArtistService                                       │
└───────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                            │
│                  (SERVICE-AGNOSTIC!)                       │
│                                                            │
│  Entities (Generic Models)                                │
│  ├── Track                      ← NO service assumptions  │
│  ├── Artist                                              │
│  ├── Album                                               │
│  └── Playlist                                            │
│                                                            │
│  Ports (Interfaces)                                       │
│  ├── ISpotifyClient             ← Interface              │
│  ├── IDeezerClient                                       │
│  └── ITrackRepository                                    │
└───────────────────────────────────────────────────────────┘
                          ▲
                          │ (Dependency Inversion)
┌───────────────────────────────────────────────────────────┐
│               INFRASTRUCTURE LAYER                         │
│                (SERVICE-SPECIFIC!)                         │
│                                                            │
│  Clients (HTTP Wrappers)                                  │
│  ├── SpotifyClient              ← Spotify API details    │
│  ├── DeezerClient               ← Deezer API details     │
│  └── MusicBrainzClient                                   │
│                                                            │
│  Repositories (Persistence)                               │
│  ├── TrackRepository            ← SQLAlchemy             │
│  ├── ArtistRepository                                    │
│  └── ...                                                 │
└───────────────────────────────────────────────────────────┘
```

**Dependency Direction:** API → Application → Domain ← Infrastructure

**Critical:** Domain defines interfaces (`ISpotifyClient`), Infrastructure implements them (`SpotifyClient`).

---

## Multi-Service ID Strategy

Every entity can have IDs from **multiple services**:

### Artist Entity

```python
@dataclass
class Artist:
    """Service-agnostic artist entity."""
    id: UUID                        # Internal SoulSpot UUID
    name: str
    
    # Universal IDs (service-agnostic)
    musicbrainz_id: str | None      # MusicBrainz MBID (universal)
    
    # Service-specific IDs
    spotify_uri: str | None         # "spotify:artist:4Z8W4fKeB5..."
    deezer_id: str | None           # "12345678"
    tidal_id: str | None            # "87654321"
    apple_music_id: str | None      # Future
    
    # Metadata
    genres: list[str]
    image_url: str | None
    image_path: str | None          # Local cache
```

**Why multiple IDs?**
- User imports artist from Spotify → `spotify_uri` set
- Later, same artist found on Deezer → `deezer_id` added to existing entity
- MusicBrainz enrichment → `musicbrainz_id` added

**One entity, multiple service IDs.**

---

### Track Entity

```python
@dataclass
class Track:
    """Service-agnostic track entity."""
    id: UUID                        # Internal SoulSpot UUID
    title: str
    
    # Universal IDs
    isrc: str | None                # ISRC (International Standard Recording Code)
    musicbrainz_id: str | None      # MusicBrainz Recording MBID
    
    # Service-specific IDs
    spotify_uri: str | None         # "spotify:track:6rqhFg..."
    deezer_id: str | None           # "3135556"
    tidal_id: str | None            # "141815044"
    
    # Metadata
    duration_ms: int
    explicit: bool
    artist_id: UUID                 # Link to Artist entity
    album_id: UUID | None           # Link to Album entity
```

**Why ISRC is critical?**
- ISRC is universal identifier for recordings
- Same track from Spotify/Deezer/Tidal → same ISRC
- Use ISRC to deduplicate before checking service IDs

---

### Album Entity

```python
@dataclass
class Album:
    """Service-agnostic album entity."""
    id: UUID
    title: str
    
    # Universal IDs
    musicbrainz_id: str | None      # MusicBrainz Release MBID
    
    # Service-specific IDs
    spotify_uri: str | None         # "spotify:album:4aawyAB9v..."
    deezer_id: str | None           # "302127"
    tidal_id: str | None            # "251380836"
    
    # Metadata
    release_date: date | None
    total_tracks: int
    artist_id: UUID
    cover_url: str | None
    cover_path: str | None
```

---

## Database Schema

### Artists Table

```sql
CREATE TABLE soulspot_artists (
    id UUID PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    
    -- Universal IDs
    musicbrainz_id VARCHAR(36) UNIQUE,      -- MBID format
    
    -- Service-specific IDs (all nullable, all unique)
    spotify_uri VARCHAR(255) UNIQUE,        -- "spotify:artist:..."
    deezer_id VARCHAR(50) UNIQUE,           -- "12345678"
    tidal_id VARCHAR(50) UNIQUE,            -- "87654321"
    
    -- Metadata
    genres TEXT[],
    image_url TEXT,
    image_path VARCHAR(500),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_artists_spotify_uri ON soulspot_artists(spotify_uri);
CREATE INDEX idx_artists_deezer_id ON soulspot_artists(deezer_id);
CREATE INDEX idx_artists_tidal_id ON soulspot_artists(tidal_id);
CREATE INDEX idx_artists_musicbrainz_id ON soulspot_artists(musicbrainz_id);
```

**All service IDs are nullable and unique:** Entity can exist without Spotify ID, but if Spotify ID present, must be unique.

---

### Tracks Table

```sql
CREATE TABLE soulspot_tracks (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    
    -- Universal IDs
    isrc VARCHAR(12) UNIQUE,                -- ISRC format: CC-XXX-YY-NNNNN
    musicbrainz_id VARCHAR(36) UNIQUE,      -- MBID format
    
    -- Service-specific IDs
    spotify_uri VARCHAR(255) UNIQUE,
    deezer_id VARCHAR(50) UNIQUE,
    tidal_id VARCHAR(50) UNIQUE,
    
    -- Relations
    artist_id UUID NOT NULL REFERENCES soulspot_artists(id),
    album_id UUID REFERENCES soulspot_albums(id),
    
    -- Metadata
    duration_ms INTEGER NOT NULL,
    explicit BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tracks_isrc ON soulspot_tracks(isrc);
CREATE INDEX idx_tracks_spotify_uri ON soulspot_tracks(spotify_uri);
CREATE INDEX idx_tracks_deezer_id ON soulspot_tracks(deezer_id);
CREATE INDEX idx_tracks_artist_id ON soulspot_tracks(artist_id);
```

---

## Deduplication Priority

When importing a track/artist/album, check in this order:

### 1. ISRC (Tracks Only) - Highest Priority

```python
# Check ISRC first (100% reliable for tracks)
if track_dto.isrc:
    existing = await track_repo.get_by_isrc(track_dto.isrc)
    if existing:
        # Track already exists, add service ID if missing
        if not existing.deezer_id and track_dto.deezer_id:
            existing.deezer_id = track_dto.deezer_id
            await track_repo.update(existing)
        return existing
```

**Why first?** ISRC is universal and unique per recording. Most reliable identifier.

---

### 2. MusicBrainz ID - Second Priority

```python
# Check MusicBrainz ID (universal but not always available)
if artist_dto.musicbrainz_id:
    existing = await artist_repo.get_by_musicbrainz_id(artist_dto.musicbrainz_id)
    if existing:
        # Add service ID if missing
        if not existing.spotify_uri and artist_dto.spotify_id:
            existing.spotify_uri = f"spotify:artist:{artist_dto.spotify_id}"
            await artist_repo.update(existing)
        return existing
```

**Why second?** Universal identifier but less common than ISRC (not all entities have MBID).

---

### 3. Service ID - Third Priority

```python
# Check service ID (if already imported from same service)
if track_dto.deezer_id:
    existing = await track_repo.get_by_deezer_id(track_dto.deezer_id)
    if existing:
        # Already imported from Deezer
        return existing
```

**Why third?** Service-specific but reliable. If entity has Deezer ID, it was imported from Deezer.

---

### 4. Name + Metadata Match - Fallback

```python
# Fallback: fuzzy name matching (least reliable)
candidates = await artist_repo.search_by_name(artist_dto.name)
for candidate in candidates:
    # Check similarity (e.g., Levenshtein distance)
    if name_similarity(candidate.name, artist_dto.name) > 0.9:
        # Likely same artist, add service ID
        if not candidate.spotify_uri and artist_dto.spotify_id:
            candidate.spotify_uri = f"spotify:artist:{artist_dto.spotify_id}"
            await artist_repo.update(candidate)
        return candidate
```

**Why fallback?** Unreliable (typos, multiple artists with same name). Only use if no other match.

---

## Import Flow Example: Deezer Track

```python
async def import_track_from_deezer(
    self,
    deezer_track: DeezerTrackDTO,
) -> Track:
    """Import track from Deezer with deduplication."""
    
    # Step 1: Check ISRC (highest priority)
    if deezer_track.isrc:
        existing = await self.track_repo.get_by_isrc(deezer_track.isrc)
        if existing:
            logger.info(f"Track exists (ISRC match): {existing.title}")
            # Add Deezer ID if missing
            if not existing.deezer_id:
                existing.deezer_id = deezer_track.deezer_id
                await self.track_repo.update(existing)
            return existing
    
    # Step 2: Check Deezer ID (already imported from Deezer?)
    if deezer_track.deezer_id:
        existing = await self.track_repo.get_by_deezer_id(deezer_track.deezer_id)
        if existing:
            logger.info(f"Track exists (Deezer ID): {existing.title}")
            return existing
    
    # Step 3: No match, create new track
    track = Track(
        id=uuid4(),
        title=deezer_track.title,
        isrc=deezer_track.isrc,
        deezer_id=deezer_track.deezer_id,
        spotify_uri=None,           # Not from Spotify yet
        tidal_id=None,              # Not from Tidal yet
        duration_ms=deezer_track.duration * 1000,
        explicit=deezer_track.explicit,
        artist_id=artist.id,        # From artist import
        album_id=album.id if album else None,
    )
    
    await self.track_repo.create(track)
    logger.info(f"Track created from Deezer: {track.title}")
    return track
```

**Result:** No duplicates, even if same track imported from multiple services.

---

## Service-Specific vs Generic Code

### Service-Specific (Infrastructure)

```python
# SpotifyClient - Spotify API details
class SpotifyClient:
    """HTTP client for Spotify API."""
    BASE_URL = "https://api.spotify.com/v1"
    
    async def get_artist(self, artist_id: str) -> dict:
        """Fetch artist from Spotify API."""
        return await self._http.get(f"{self.BASE_URL}/artists/{artist_id}")

# DeezerClient - Deezer API details
class DeezerClient:
    """HTTP client for Deezer API."""
    BASE_URL = "https://api.deezer.com"
    
    async def get_artist(self, artist_id: str) -> dict:
        """Fetch artist from Deezer API."""
        return await self._http.get(f"{self.BASE_URL}/artist/{artist_id}")
```

**Service-specific:** URL, auth, error handling, rate limits.

---

### Generic (Domain + Application)

```python
# ArtistService - Works with ANY service
class ArtistService:
    """Generic artist operations (service-agnostic)."""
    
    async def get_artist_details(self, artist_id: UUID) -> Artist:
        """Get artist details (from DB, any service)."""
        return await self.artist_repo.get_by_id(artist_id)
    
    async def search_artists(self, query: str) -> list[Artist]:
        """Search artists (in DB, imported from any service)."""
        return await self.artist_repo.search_by_name(query)
```

**Generic:** No service assumptions, works with data from any provider.

---

## Plugin System Integration

**Plugins abstract service-specific logic:**

```python
# IMusicServicePlugin - Generic interface
class IMusicServicePlugin(Protocol):
    """Interface for music service plugins."""
    
    async def get_artist_details(self, uri: str) -> ArtistDTO:
        """Fetch artist details (generic DTO)."""
        ...
    
    async def search_tracks(self, query: str) -> list[TrackDTO]:
        """Search tracks (generic DTOs)."""
        ...

# SpotifyPlugin - Spotify implementation
class SpotifyPlugin:
    """Spotify service plugin."""
    
    async def get_artist_details(self, spotify_uri: str) -> ArtistDTO:
        """Fetch artist from Spotify, return generic DTO."""
        artist_id = spotify_uri.split(":")[-1]
        response = await self._client.get_artist(artist_id)
        
        return ArtistDTO(
            name=response["name"],
            image_url=response["images"][0]["url"] if response["images"] else None,
            spotify_id=artist_id,
            deezer_id=None,         # Not from Deezer
            tidal_id=None,          # Not from Tidal
            genres=response.get("genres", []),
        )

# DeezerPlugin - Deezer implementation
class DeezerPlugin:
    """Deezer service plugin."""
    
    async def get_artist_details(self, deezer_id: str) -> ArtistDTO:
        """Fetch artist from Deezer, return generic DTO."""
        response = await self._client.get_artist(deezer_id)
        
        return ArtistDTO(
            name=response["name"],
            image_url=response["picture_xl"],
            spotify_id=None,        # Not from Spotify
            deezer_id=deezer_id,
            tidal_id=None,
            genres=[],              # Deezer doesn't provide genres
        )
```

**Application layer uses generic `IMusicServicePlugin`, doesn't care which implementation.**

---

## Adding a New Service (Example: Tidal)

### Step 1: Create Client (Infrastructure)

```python
# infrastructure/clients/tidal_client.py

class TidalClient:
    """HTTP client for Tidal API."""
    BASE_URL = "https://api.tidal.com/v1"
    
    async def get_artist(self, artist_id: str) -> dict:
        """Fetch artist from Tidal API."""
        return await self._http.get(f"{self.BASE_URL}/artists/{artist_id}")
```

---

### Step 2: Create Plugin (Infrastructure)

```python
# infrastructure/plugins/tidal_plugin.py

class TidalPlugin(IMusicServicePlugin):
    """Tidal service plugin."""
    
    async def get_artist_details(self, tidal_id: str) -> ArtistDTO:
        """Fetch artist from Tidal."""
        response = await self._client.get_artist(tidal_id)
        
        return ArtistDTO(
            name=response["name"],
            image_url=response["picture"],
            spotify_id=None,
            deezer_id=None,
            tidal_id=tidal_id,      # Add Tidal ID
            genres=[],
        )
```

---

### Step 3: Update Entities (Domain)

```python
# domain/entities/artist.py

@dataclass
class Artist:
    # ... existing fields ...
    tidal_id: str | None            # Add Tidal ID field
```

---

### Step 4: Update Database Schema (Migration)

```sql
-- alembic migration
ALTER TABLE soulspot_artists
ADD COLUMN tidal_id VARCHAR(50) UNIQUE;

CREATE INDEX idx_artists_tidal_id ON soulspot_artists(tidal_id);
```

---

### Step 5: Update Repositories (Infrastructure)

```python
# infrastructure/persistence/repositories.py

class ArtistRepository:
    async def get_by_tidal_id(self, tidal_id: str) -> Artist | None:
        """Get artist by Tidal ID."""
        result = await self.session.execute(
            select(ArtistModel).where(ArtistModel.tidal_id == tidal_id)
        )
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None
```

---

### Step 6: Register Plugin (Application)

```python
# main.py or dependency injection

from infrastructure.plugins.tidal_plugin import TidalPlugin

# Register Tidal plugin
app.state.tidal_plugin = TidalPlugin(tidal_client)
```

**Done!** Tidal support added without touching domain logic.

---

## Benefits

### 1. Provider-Agnostic Domain

```python
# This code works with data from ANY service
async def get_artist_albums(artist_id: UUID) -> list[Album]:
    """Get artist albums (from any service)."""
    return await album_repo.get_by_artist_id(artist_id)
```

**No service assumptions in domain logic.**

---

### 2. Easy Provider Switching

```python
# User preference: switch from Spotify to Deezer
if user.preferred_service == "spotify":
    plugin = spotify_plugin
elif user.preferred_service == "deezer":
    plugin = deezer_plugin

# Same code, different plugin
artist = await plugin.get_artist_details(artist_uri)
```

---

### 3. Multi-Provider Aggregation

```python
# Fetch same artist from multiple services
spotify_artist = await spotify_plugin.get_artist_details(spotify_uri)
deezer_artist = await deezer_plugin.get_artist_details(deezer_id)

# Merge into single entity
artist = Artist(
    id=uuid4(),
    name=spotify_artist.name,       # Use Spotify name
    spotify_uri=spotify_uri,
    deezer_id=deezer_id,
    genres=spotify_artist.genres,   # Spotify has better genres
    image_url=deezer_artist.image_url,  # Deezer has higher-res images
)
```

**Best of both services.**

---

### 4. Deduplication Across Services

```python
# Import track from Spotify
spotify_track = await spotify_sync.import_track(spotify_uri)

# Later, import same track from Deezer
deezer_track = await deezer_sync.import_track(deezer_id)

# ISRC matches → same Track entity, both IDs added
assert spotify_track.id == deezer_track.id
assert deezer_track.spotify_uri is not None
assert deezer_track.deezer_id is not None
```

**No duplicates, single source of truth.**

---

## Testing Strategy

### Mock Plugins in Tests

```python
# tests/unit/services/test_artist_service.py

class MockSpotifyPlugin:
    """Mock Spotify plugin for testing."""
    async def get_artist_details(self, uri: str) -> ArtistDTO:
        return ArtistDTO(
            name="Test Artist",
            image_url="https://example.com/image.jpg",
            spotify_id="test123",
            deezer_id=None,
            tidal_id=None,
            genres=["rock"],
        )

async def test_import_artist():
    """Test artist import with mock plugin."""
    service = ArtistService(artist_repo, MockSpotifyPlugin())
    artist = await service.import_from_spotify("spotify:artist:test123")
    
    assert artist.name == "Test Artist"
    assert artist.spotify_uri == "spotify:artist:test123"
```

**Test domain logic without external API calls.**

---

## Related Documentation

- **[Plugin System](./plugin-system.md)** - Plugin interface and implementation
- **[Data Standards](./data-standards.md)** - DTO definitions and ID conventions
- **[Core Philosophy](./core-philosophy.md)** - Multi-provider aggregation principle

---

**Last Validated:** 2025-01-XX  
**Status:** ✅ IMPLEMENTED - Spotify, Deezer, MusicBrainz supported  
**Next:** Tidal support planned (Q2 2025)
