# Service-Agnostic Backend Architecture

**Version:** 2.0  
**Created:** 12. Dezember 2025  
**Status:** ✅ Implemented  
**Owner:** Architecture Team

---

## Executive Summary

SoulSpot's backend is designed to be **service-agnostic** - meaning the core domain models (Track, Artist, Album, Playlist) work with ANY music service (Spotify, Tidal, Deezer), while service-specific code is isolated in dedicated clients and adapters.

**Key Principle:**  
```
Domain Layer (generic) ← Application Layer ← Infrastructure Layer (service-specific)
```

---

## 1. Architecture Overview

### 1.1 Layer Separation

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  /api/spotify/auth   /api/playlists   /api/library   /api/tracks│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Application Layer (Services)                   │
│  SpotifySyncService  PlaylistService  TrackService  LibraryService│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Domain Layer (Entities + Ports)               │
│  Track  Artist  Album  Playlist  │  ISpotifyClient  ITrackRepo   │
│  (generic entities)              │  (interfaces)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                Infrastructure Layer (Implementations)            │
│  SpotifyClient  TidalClient*  DeezerClient*  │  Repositories     │
│  (service-specific)                          │  (SQLAlchemy)     │
└─────────────────────────────────────────────────────────────────┘
                                              * = Future
```

### 1.2 Dependency Direction

```
API → Application → Domain ← Infrastructure
                      ▲
                      │
        Domain defines interfaces (ports)
        Infrastructure implements them (adapters)
```

**Critical Rule:** Domain layer has NO external dependencies. It defines interfaces (ports) that infrastructure implements.

---

## 2. Multi-Service ID Strategy

### 2.1 Entity ID Fields

Every major entity (Artist, Album, Track) has service-specific IDs:

```python
# src/soulspot/domain/entities/__init__.py

@dataclass
class Artist:
    id: ArtistId           # Internal UUID
    name: str
    # Service IDs (nullable, unique, indexed)
    spotify_uri: SpotifyUri | None = None   # spotify:artist:xxx
    deezer_id: str | None = None            # 12345
    tidal_id: str | None = None             # 67890
    musicbrainz_id: str | None = None       # Universal ID (best for dedup)

@dataclass
class Track:
    id: TrackId
    title: str
    isrc: str | None = None                 # International Standard Recording Code
    spotify_uri: SpotifyUri | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
```

### 2.2 Deduplication Strategy

When importing from multiple services, use this priority:

```
1. ISRC (Tracks only)     → Universal identifier, 100% reliable
2. MusicBrainz ID         → Universal, but not always available
3. Service ID             → Check if entity already imported from same service
4. Name + Metadata Match  → Fallback, fuzzy matching
```

**Example Flow (importing from Deezer):**

```python
async def import_track_from_deezer(deezer_track: DeezerTrack) -> Track:
    # Step 1: Check ISRC (most reliable)
    if deezer_track.isrc:
        existing = await track_repo.get_by_isrc(deezer_track.isrc)
        if existing:
            # Same track from different service - add Deezer ID
            existing.deezer_id = deezer_track.id
            await track_repo.update(existing)
            return existing
    
    # Step 2: Check if already imported from Deezer
    existing = await track_repo.get_by_deezer_id(deezer_track.id)
    if existing:
        return existing  # Already imported
    
    # Step 3: Create new track
    track = Track(
        id=TrackId.generate(),
        title=deezer_track.title,
        isrc=deezer_track.isrc,
        deezer_id=deezer_track.id,
        ...
    )
    await track_repo.add(track)
    return track
```

### 2.3 Database Schema

```sql
-- Tracks table with multi-service IDs
CREATE TABLE soulspot_tracks (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    isrc VARCHAR(12) UNIQUE,              -- Universal identifier
    spotify_uri VARCHAR(100) UNIQUE,      -- spotify:track:xxx
    deezer_id VARCHAR(50) UNIQUE,         -- Deezer track ID
    tidal_id VARCHAR(50) UNIQUE,          -- Tidal track ID
    musicbrainz_id VARCHAR(36) UNIQUE,    -- MusicBrainz Recording ID
    ...
);

-- Indexes for fast deduplication lookups
CREATE INDEX ix_soulspot_tracks_isrc ON soulspot_tracks(isrc);
CREATE INDEX ix_soulspot_tracks_deezer_id ON soulspot_tracks(deezer_id);
CREATE INDEX ix_soulspot_tracks_tidal_id ON soulspot_tracks(tidal_id);
```

---

## 3. Repository Pattern

### 3.1 Interface Definition (Ports)

```python
# src/soulspot/domain/ports/__init__.py

class ITrackRepository(ABC):
    """Service-agnostic track repository interface."""
    
    # Generic CRUD
    @abstractmethod
    async def add(self, track: Track) -> None: ...
    
    @abstractmethod
    async def get_by_id(self, track_id: TrackId) -> Track | None: ...
    
    # Multi-service lookups
    @abstractmethod
    async def get_by_isrc(self, isrc: str) -> Track | None: ...
    
    @abstractmethod
    async def get_by_deezer_id(self, deezer_id: str) -> Track | None: ...
    
    @abstractmethod
    async def get_by_tidal_id(self, tidal_id: str) -> Track | None: ...
```

### 3.2 Implementation (Adapters)

```python
# src/soulspot/infrastructure/persistence/repositories.py

class TrackRepository(ITrackRepository):
    """SQLAlchemy implementation of Track repository."""
    
    async def get_by_isrc(self, isrc: str) -> Track | None:
        stmt = select(TrackModel).where(TrackModel.isrc == isrc)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_deezer_id(self, deezer_id: str) -> Track | None:
        stmt = select(TrackModel).where(TrackModel.deezer_id == deezer_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
```

---

## 4. Service Client Pattern

### 4.1 Service-Specific Interfaces

Each music service gets its OWN interface (not a shared ITrackClient):

```python
# src/soulspot/domain/ports/__init__.py

class ISpotifyClient(ABC):
    """Spotify-specific client interface."""
    
    # OAuth (Spotify-specific flow)
    @abstractmethod
    async def get_authorization_url(self, state: str) -> str: ...
    
    @abstractmethod
    async def exchange_code(self, code: str) -> SpotifyTokens: ...
    
    # Track operations
    @abstractmethod
    async def get_track(self, track_id: str, access_token: str) -> SpotifyTrack: ...
    
    @abstractmethod
    async def search_track(self, query: str, access_token: str) -> list[SpotifyTrack]: ...

# Future: Similar interfaces for Tidal/Deezer
class ITidalClient(ABC):
    """Tidal-specific client interface."""
    ...

class IDeezerClient(ABC):
    """Deezer-specific client interface."""
    ...
```

### 4.2 Why NOT a Generic ITrackClient?

**Reasoning:**
1. Each service has unique features (Spotify Connect, Tidal HiFi, Deezer Flow)
2. OAuth flows differ significantly
3. API response shapes differ
4. Rate limits/auth tokens work differently

**Correct Approach:**
- Service-specific clients (`SpotifyClient`, `TidalClient`)
- Generic domain entities (`Track`, `Artist`)
- Conversion happens at the boundary (client → domain entity)

```python
class SpotifyClient(ISpotifyClient):
    async def get_track(self, track_id: str, access_token: str) -> Track:
        # Spotify API call
        response = await self._api.get(f"/tracks/{track_id}")
        
        # Convert Spotify-specific response to generic Track entity
        return Track(
            id=TrackId.generate(),
            title=response["name"],
            isrc=response.get("external_ids", {}).get("isrc"),
            spotify_uri=SpotifyUri(response["uri"]),
            duration_ms=response["duration_ms"],
            ...
        )
```

---

## 5. Session Management

### 5.1 Service-Specific Sessions

```python
# src/soulspot/infrastructure/persistence/models.py

class SpotifySessionModel(Base):
    """Spotify OAuth session storage."""
    __tablename__ = "spotify_sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(String(500))
    refresh_token: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

# Future: TidalSessionModel, DeezerSessionModel
```

### 5.2 Why NOT a Generic SessionModel?

Each service has different:
- Token formats
- Refresh mechanisms
- Expiration policies
- Scopes/permissions

**Example:**
- Spotify: access_token + refresh_token, 1h expiry
- Tidal: access_token + refresh_token + session_id, different expiry
- Deezer: access_token only (no refresh), different OAuth params

---

## 6. Adding a New Service (Checklist)

### When adding Tidal/Deezer support:

**1. Domain Layer (no changes needed for entities)**
- [ ] Create `ITidalClient` interface in `domain/ports/`
- [ ] Add `tidal_id` to entities (already done for Artist/Album/Track)

**2. Infrastructure Layer**
- [ ] Create `TidalClient` implementing `ITidalClient`
- [ ] Create `TidalSessionModel` for OAuth tokens
- [ ] Create `TidalSessionRepository`
- [ ] Add Alembic migration for `tidal_sessions` table

**3. Application Layer**
- [ ] Create `TidalSyncService` (similar to `SpotifySyncService`)
- [ ] Update `TrackService` to handle Tidal imports

**4. API Layer**
- [ ] Create `/api/tidal/auth` routes
- [ ] Create `/api/tidal/sync` routes

**5. Configuration**
- [ ] Add `TIDAL_CLIENT_ID`, `TIDAL_CLIENT_SECRET` to `.env`
- [ ] Update `config.py` with Tidal settings

---

## 7. Implementation Status

| Component | Spotify | Tidal | Deezer |
|-----------|---------|-------|--------|
| **Entity IDs** | ✅ spotify_uri | ✅ tidal_id | ✅ deezer_id |
| **Client Interface** | ✅ ISpotifyClient | ⏳ Planned | ⏳ Planned |
| **Client Impl** | ✅ SpotifyClient | ⏳ Planned | ⏳ Planned |
| **Session Model** | ✅ SpotifySessionModel | ⏳ Planned | ⏳ Planned |
| **Repository Lookups** | ✅ get_by_spotify_uri | ✅ get_by_tidal_id | ✅ get_by_deezer_id |
| **OAuth Routes** | ✅ /api/spotify/auth | ⏳ Planned | ⏳ Planned |
| **Sync Service** | ✅ SpotifySyncService | ⏳ Planned | ⏳ Planned |

---

## 8. Related Documentation

- [SERVICE_AGNOSTIC_STRATEGY.md](../feat-ui/SERVICE_AGNOSTIC_STRATEGY.md) - UI component strategy
- [MODERNIZATION_PLAN.md](../MODERNIZATION_PLAN.md) - Backend modernization roadmap
- [Domain Ports](../../src/soulspot/domain/ports/__init__.py) - Interface definitions
- [Repositories](../../src/soulspot/infrastructure/persistence/repositories.py) - Implementations

---

## 9. Migration History

| Migration | Description | Date |
|-----------|-------------|------|
| `rr29014ttu62` | Rename `sessions` → `spotify_sessions` | 2025-12-12 |
| `ss30015uuv63` | Add `deezer_id`/`tidal_id` to Artist/Album/Track | 2025-12-12 |

---

**Document maintained by:** Architecture Team  
**Last updated:** 12. Dezember 2025
