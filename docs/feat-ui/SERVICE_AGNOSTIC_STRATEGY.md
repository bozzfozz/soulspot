# Service-Agnostic Component Strategy

**Goal:** Design UI components and database schema to support multiple music services (Spotify, Tidal, Deezer) with 90%+ code reuse.

---

## 1. Problem Statement

**Current State (Spotify-Only):**
- Components: `spotify-card.html`, `spotify-playlist.html`, `spotify-track.html`
- Database: `spotify_sessions`, `spotify_tokens`, `spotify_users`
- Clients: `SpotifyClient`, `SpotifyAuth`
- API Routes: `/api/spotify/auth`, `/api/spotify/sync`

**Problem:** Adding Tidal requires:
- 10+ new component files (spotify → tidal duplication)
- 5+ new database tables
- 3+ new client classes
- 4+ new route groups

**Solution:** Separate **generic domain models** (Track, Artist, Playlist) from **service-specific clients** (SpotifyClient, TidalClient).

**Impact:** 90% component reuse, only 10% service-specific code.

---

## 2. Naming Convention Matrix

| Layer | Generic (✅ Reusable) | Service-Specific (❌ Not Reused) |
|-------|---------------------|----------------------------------|
| **Components** | `track-card.html` | N/A (use generic) |
| **Templates** | `playlist-detail.html` | `spotify-auth-callback.html` |
| **JavaScript** | `audio-player.js` | `spotify-oauth-handler.js` |
| **Clients** | `ITrackClient` (interface) | `SpotifyClient`, `TidalClient` |
| **Database** | `tracks`, `artists`, `playlists` | `spotify_sessions`, `tidal_tokens` |
| **API Routes** | `/api/playlists`, `/api/tracks` | `/api/spotify/auth`, `/api/tidal/auth` |
| **Services** | `PlaylistService` | `SpotifyPlaylistSync` |

### Rule
- **Generic:** If 2+ services can use it → make generic
- **Service-Specific:** If only 1 service needs it → prefix with service name

---

## 3. Component Classification

### Always Generic (100% Reusable)

```
✅ track-card.html           # Display Track entity (Spotify/Tidal/Deezer)
✅ artist-card.html          # Display Artist entity
✅ playlist-detail.html       # Display Playlist entity
✅ audio-player.html         # Play audio (source agnostic)
✅ search-results.html       # Search results (any service)
✅ download-progress.html    # Download status (any service)
✅ library-browser.html      # Library view (any service)
✅ tag-input.html            # Tag management (generic)
✅ notification.html         # Toast notifications (generic)
✅ loading-skeleton.html     # Skeleton loaders (generic)
```

### Always Service-Specific (0% Reusable)

```
❌ spotify-connect.html      # Spotify-specific auth flow
❌ tidal-hifi-indicator.html # Tidal-specific HiFi badge
❌ spotify-share-dialog.html # Spotify-specific sharing
❌ deezer-family-plan.html   # Deezer-specific feature
```

### Example: Track Card Component (Generic)

```html
<!-- templates/includes/_track_card.html -->
{%- macro track_card(track, actions=true) -%}
  <div class="track-card" data-track-id="{{ track.id }}">
    <!-- Works for Spotify Track, Tidal Track, Deezer Track -->
    <img src="{{ track.image_url }}" alt="{{ track.title }}" />
    <div class="track-info">
      <h3>{{ track.title }}</h3>
      <p class="artist">{{ track.artist.name }}</p>
      <p class="duration">{{ track.duration_ms | format_duration }}</p>
    </div>
    
    {% if actions %}
      <div class="track-actions">
        <button class="btn-play" data-action="play">▶ Play</button>
        <button class="btn-add" data-action="add">+ Add</button>
      </div>
    {% endif %}
  </div>
{%- endmacro -%}
```

**Existing Example:** `templates/partials/metadata_editor.html` is **already generic** – it uses `track.title`, `track.artist`, `track.album` without Spotify-specific fields. This is the correct pattern to follow.

---

## 4. Database Schema Strategy

### Generic Tables (Domain Layer)

```python
# All services share these tables
class Track(Base):
    __tablename__ = "tracks"
    id: str  # UUID, service-independent
    title: str
    duration_ms: int
    image_url: str  # URL from any service
    isrc: str  # International Standard Recording Code (unique identifier)
    created_at: datetime
    updated_at: datetime

class Artist(Base):
    __tablename__ = "artists"
    id: str
    name: str
    image_url: str
    biography: str
    created_at: datetime

class Playlist(Base):
    __tablename__ = "playlists"
    id: str
    title: str
    description: str
    image_url: str
    owner_id: str
    track_count: int
    created_at: datetime
```

### Service-Specific Mapping Tables

```python
# Link generic tables to service IDs
class SpotifyTrackMapping(Base):
    __tablename__ = "spotify_track_mappings"
    track_id: str  # Foreign key to tracks.id
    spotify_id: str  # Spotify URI/ID
    spotify_uri: str  # spotify:track:XXXX

class TidalTrackMapping(Base):
    __tablename__ = "tidal_track_mappings"
    track_id: str  # Foreign key to tracks.id
    tidal_id: int  # Tidal Track ID
    tidal_url: str  # Tidal API URL

class DeezerTrackMapping(Base):
    __tablename__ = "deezer_track_mappings"
    track_id: str  # Foreign key to tracks.id
    deezer_id: int  # Deezer Track ID
    deezer_url: str  # Deezer API URL
```

**Critical: ISRC-Based Matching Strategy**

ISRC (International Standard Recording Code) is the **universal identifier** for tracks across all services. Use it to link tracks:

```python
# Service-agnostic track creation/lookup
async def get_or_create_track(isrc: str, service_id: str, service: str) -> Track:
    """
    Find existing track by ISRC, or create new one.
    Links service-specific ID to generic Track entity.
    
    Example:
      - User imports Spotify track with ISRC "USRC12345678"
      - Later imports same track from Tidal with same ISRC
      - Both map to same Track entity (no duplication)
    """
    track = await track_repo.get_by_isrc(isrc)
    
    if not track:
        # Create new generic track
        track = Track(id=uuid4(), isrc=isrc, ...)
        await track_repo.save(track)
    
    # Link service-specific ID
    if service == "spotify":
        await spotify_mapping_repo.save(SpotifyTrackMapping(
            track_id=track.id,
            spotify_id=service_id,
            spotify_uri=f"spotify:track:{service_id}"
        ))
    elif service == "tidal":
        await tidal_mapping_repo.save(TidalTrackMapping(
            track_id=track.id,
            tidal_id=int(service_id),
            tidal_url=f"https://api.tidal.com/v1/tracks/{service_id}"
        ))
    
    return track
```

### Service-Specific Session Tables

```python
# Each service manages its own OAuth tokens
class SpotifySession(Base):
    __tablename__ = "spotify_sessions"
    user_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime

class TidalSession(Base):
    __tablename__ = "tidal_sessions"
    user_id: str
    access_token: str
    country_code: str
    expires_at: datetime

class DeezerSession(Base):
    __tablename__ = "deezer_sessions"
    user_id: str
    access_token: str
```

---

## 5. API Route Organization

### Generic Routes (Service-Agnostic)

```python
# src/soulspot/api/routers/playlists.py
@router.get("/playlists")
async def list_playlists(service: PlaylistService):
    # Works for all services
    return await service.list_all()

@router.get("/playlists/{playlist_id}/tracks")
async def get_playlist_tracks(playlist_id: str, service: PlaylistService):
    # Works for Spotify/Tidal/Deezer
    return await service.get_tracks(playlist_id)

@router.post("/playlists/{playlist_id}/sync")
async def sync_playlist(playlist_id: str, sync_service: PlaylistSyncService):
    # Sync works for any service
    return await sync_service.sync(playlist_id)
```

### Service-Specific Routes

```python
# src/soulspot/api/routers/spotify.py
@router.get("/spotify/auth/callback")
async def spotify_callback(code: str, spotify_service: SpotifyService):
    # Spotify-specific OAuth callback
    return await spotify_service.handle_oauth_callback(code)

# src/soulspot/api/routers/tidal.py
@router.get("/tidal/auth/callback")
async def tidal_callback(code: str, tidal_service: TidalService):
    # Tidal-specific OAuth callback
    return await tidal_service.handle_oauth_callback(code)
```

---

## 6. Client Architecture

### Interface (Generic)

```python
# src/soulspot/domain/ports/track_client.py
from typing import Protocol

class ITrackClient(Protocol):
    """Service-agnostic track client interface"""
    
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        """Search for tracks (works for Spotify, Tidal, Deezer)"""
        ...
    
    async def get_track(self, track_id: str) -> Track:
        """Get track details"""
        ...
    
    async def get_track_by_isrc(self, isrc: str) -> Track | None:
        """Get track by ISRC (international identifier)"""
        ...
```

### Implementation (Service-Specific)

```python
# src/soulspot/infrastructure/clients/spotify_client.py
class SpotifyClient(ITrackClient):
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        # Spotify-specific API call
        response = await self.http_client.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": limit}
        )
        return self._convert_spotify_tracks(response)

# src/soulspot/infrastructure/clients/tidal_client.py
class TidalClient(ITrackClient):
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        # Tidal-specific API call
        response = await self.http_client.get(
            "https://api.tidal.com/v1/search/tracks",
            params={"query": query, "limit": limit}
        )
        return self._convert_tidal_tracks(response)
```

---

## 7. Tidal/Deezer Integration Checklist

### Phase 1: Setup (No Component Changes)
- [ ] Create `TidalSession` database table
- [ ] Create `tidal_track_mappings` table
- [ ] Implement `ITrackClient` interface for Tidal
- [ ] Implement `TidalClient` class
- [ ] Add Tidal OAuth routes (`/api/tidal/auth`)
- [ ] No component changes needed

### Phase 2: Service Integration (Reuse Generic Components)
- [ ] Create `TidalPlaylistService` (implements `IPlaylistService`)
- [ ] Create `TidalSyncService` (implements `ISyncService`)
- [ ] Generic playlist routes now work with Tidal
- [ ] Reuse all playlist components (100% compatible)

### Phase 3: UI Updates (Add Service Selector)
- [ ] Add service dropdown to playlist browser
- [ ] Add service indicator to track cards
- [ ] Reuse all existing templates
- [ ] No new component files needed

### Phase 4: Testing & Polish
- [ ] Test Tidal sync workflow
- [ ] Test cross-service search
- [ ] A11Y testing for all new routes
- [ ] Documentation updates

---

## 8. Migration Example: Adding Tidal

### Before: Spotify-Only

```
File structure (Spotify-specific):
  templates/
    spotify-connect.html
    spotify-playlist.html
    spotify-track-card.html
  src/infrastructure/clients/
    spotify_client.py
  database:
    spotify_sessions
```

### After: Spotify + Tidal (90% Reuse)

```
File structure (Generic + Service-Specific):
  templates/
    playlist.html              ← Generic, reused for both
    track-card.html            ← Generic, reused for both
    spotify-connect.html       ← Spotify-specific auth
    tidal-connect.html         ← NEW Tidal-specific auth
  src/infrastructure/clients/
    spotify_client.py          ← Implements ITrackClient
    tidal_client.py            ← NEW Implements ITrackClient
  database:
    tracks                     ← Generic
    spotify_sessions           ← Spotify-specific
    tidal_sessions             ← NEW Tidal-specific
    spotify_track_mappings     ← NEW Mapping table
    tidal_track_mappings       ← NEW Mapping table
```

### Code Migration Example

```bash
# AUDIT: Check existing files for Spotify-specific naming
grep -r "spotify" src/soulspot/templates/ --include="*.html" | grep -v "spotify-connect\|spotify-auth"

# EXAMPLE OUTPUT (files that should be generic):
# templates/partials/spotify_search_results.html  → should be search_results.html
# templates/partials/followed_artists_list.html   → already generic! ✓
# templates/partials/metadata_editor.html         → already generic! ✓

# RENAME: Service-specific to generic (only if needed)
cd src/soulspot/templates/partials
mv spotify_search_results.html search_results.html

# UPDATE REFERENCES: Find all imports of renamed file
grep -r "spotify_search_results" src/soulspot/ --include="*.py" --include="*.html"
# Replace with: search_results.html

# CREATE: Tidal client (implements same interface)
touch src/soulspot/infrastructure/clients/tidal_client.py

# DATABASE: Add mapping tables + Tidal session table
alembic revision --autogenerate -m "add_tidal_support_tables"
alembic upgrade head
```

**Status Check:** Most SoulSpot templates are **already generic**:
- ✓ `metadata_editor.html` – uses `track.title`, not `spotify_track.title`
- ✓ `track_item.html` – generic track display
- ✓ `download_item.html` – service-agnostic download UI
- ✗ `spotify_search_results.html` – **needs renaming** to `search_results.html`

---

## 9. Component Reuse Matrix

| Scenario | Spotify | Tidal | Deezer | Reuse % |
|----------|---------|-------|--------|---------|
| **Display track** | ✅ track-card.html | ✅ track-card.html | ✅ track-card.html | **100%** |
| **List playlists** | ✅ playlist.html | ✅ playlist.html | ✅ playlist.html | **100%** |
| **Play audio** | ✅ audio-player.js | ✅ audio-player.js | ✅ audio-player.js | **100%** |
| **Search** | ✅ search.js | ✅ search.js | ✅ search.js | **100%** |
| **OAuth flow** | ✅ spotify-auth.html | ✅ tidal-auth.html | ✅ deezer-auth.html | **0%** |
| **Import library** | ✅ import-modal.html | ✅ import-modal.html | ✅ import-modal.html | **100%** |
| **Download track** | ✅ download-item.html | ✅ download-item.html | ✅ download-item.html | **100%** |
| **Service settings** | ✅ settings.html | ✅ settings.html | ✅ settings.html | **100%** |

**Average Component Reuse: 95%**

---

## 10. Naming Convention Examples

✅ **Correct:**
```
components/
  track-card.html           # Generic
  artist-card.html          # Generic
  spotify-connect.html      # Service-specific
  tidal-hifi.html          # Service-specific

database/
  tracks                    # Generic
  spotify_sessions          # Service-specific
  tidal_sessions            # Service-specific

clients/
  track_client.py           # Interface
  spotify_client.py         # Implementation
  tidal_client.py           # Implementation
```

❌ **Incorrect:**
```
components/
  spotify-track-card.html   # Should be generic
  tidal-track-card.html     # Duplicate!
  spotify-playlist.html     # Should be generic
  tidal-playlist.html       # Duplicate!

database/
  spotify_tracks            # Should be generic
  tidal_tracks              # Duplicate!
```

---

## 11. Future Extensibility

**Pattern ensures:**
- ✅ Add new service: Only implement `ITrackClient` + add `_sessions` table
- ✅ Reuse 95% of components
- ✅ Reuse all routes (generic API)
- ✅ No template duplication
- ✅ No refactoring of existing code

**Add Deezer in 1 day** (instead of 1 week of refactoring)
