# Service-Agnostic UI Strategy

**Category:** Architecture / Multi-Service Design  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [UI Architecture](./ui-architecture-principles.md), [Plugin System](../02-architecture/plugin-system.md), [Service-Agnostic Backend](../03-architecture-planning/service-agnostic-backend.md)

---

## Overview

Design UI components and database schema to support multiple music services (Spotify, Tidal, Deezer) with **90%+ code reuse**.

## Problem Statement

**Current State (Spotify-Only):**
- Components: `spotify-card.html`, `spotify-playlist.html`, `spotify-track.html`
- Database: `spotify_sessions`, `spotify_tokens`, `spotify_users`
- Clients: `SpotifyClient`, `SpotifyAuth`
- API Routes: `/api/spotify/auth`, `/api/spotify/sync`

**Problem Adding Tidal:**
- 10+ new component files (duplication)
- 5+ new database tables
- 3+ new client classes
- 4+ new route groups

**Solution:** Separate **generic domain models** (Track, Artist, Playlist) from **service-specific clients** (SpotifyClient, TidalClient).

**Impact:** 90% component reuse, only 10% service-specific code.

## Naming Convention Matrix

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

## Component Classification

### Always Generic (100% Reusable)

```
✅ track-card.html           # Display Track entity
✅ artist-card.html          # Display Artist entity
✅ playlist-detail.html      # Display Playlist entity
✅ audio-player.html         # Play audio (source agnostic)
✅ search-results.html       # Search results (any service)
✅ download-progress.html    # Download status
✅ library-browser.html      # Library view
✅ tag-input.html            # Tag management
✅ notification.html         # Toast notifications
✅ loading-skeleton.html     # Skeleton loaders
```

### Always Service-Specific (0% Reusable)

```
❌ spotify-connect.html      # Spotify-specific auth flow
❌ tidal-hifi-indicator.html # Tidal-specific HiFi badge
❌ spotify-share-dialog.html # Spotify-specific sharing
❌ deezer-family-plan.html   # Deezer-specific feature
```

## Generic Track Card Example

```jinja2
<!-- templates/components/track_card.html - GENERIC -->
{% macro track_card(track, service='generic') %}
<div class="track-card" data-track-id="{{ track.id }}" data-service="{{ service }}">
  <!-- Works for Spotify Track, Tidal Track, Deezer Track -->
  <img src="{{ track.image_url }}" alt="{{ track.title }}" loading="lazy">
  <div class="track-info">
    <h3>{{ track.title }}</h3>
    <p class="artist">{{ track.artist.name }}</p>
    <p class="duration">{{ track.duration_ms | format_duration }}</p>
  </div>
  
  {# Service badge (5% custom logic) #}
  {% if service != 'generic' %}
  <span class="badge badge-{{ service }}">
    <i class="icon-{{ service }}"></i>
  </span>
  {% endif %}
  
  {# Generic actions (95% reuse) #}
  <div class="track-actions">
    <button class="btn-play" hx-post="/api/tracks/{{ track.id }}/play">▶ Play</button>
    <button class="btn-add" hx-post="/api/tracks/{{ track.id }}/queue">+ Add</button>
  </div>
</div>
{% endmacro %}
```

**Usage:**

```jinja2
{# Works for all services #}
{{ track_card(spotify_track, service='spotify') }}
{{ track_card(tidal_track, service='tidal') }}
{{ track_card(local_track, service='local') }}
```

**Existing Example:** `templates/partials/metadata_editor.html` is already generic - uses `track.title`, `track.artist` without Spotify-specific fields.

## Database Schema Strategy

### Generic Tables (Domain Layer)

```python
# All services share these tables
class Track(Base):
    __tablename__ = "tracks"
    id: str  # UUID, service-independent
    title: str
    duration_ms: int
    image_url: str  # URL from any service
    isrc: str  # International Standard Recording Code
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
    track_id: str  # FK to tracks.id
    spotify_id: str  # Spotify URI/ID
    spotify_uri: str  # spotify:track:XXXX

class TidalTrackMapping(Base):
    __tablename__ = "tidal_track_mappings"
    track_id: str  # FK to tracks.id
    tidal_id: int  # Tidal Track ID
    tidal_url: str  # Tidal API URL

class DeezerTrackMapping(Base):
    __tablename__ = "deezer_track_mappings"
    track_id: str  # FK to tracks.id
    deezer_id: int  # Deezer Track ID
```

### Session/Auth Tables (Service-Specific)

```python
# Each service has own session table
class SpotifySession(Base):
    __tablename__ = "spotify_sessions"
    session_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime

class TidalSession(Base):
    __tablename__ = "tidal_sessions"
    session_id: str
    access_token: str
    expires_at: datetime
```

## Cross-Service Matching with ISRC

**ISRC** (International Standard Recording Code) is the universal identifier for tracks.

**Strategy:**

```python
# Find track across all services using ISRC
async def find_track_by_isrc(isrc: str) -> Track | None:
    # 1. Check if track exists in generic tracks table
    track = await track_repo.get_by_isrc(isrc)
    if track:
        return track
    
    # 2. Search Spotify
    spotify_track = await spotify_client.search_by_isrc(isrc)
    if spotify_track:
        track = await create_generic_track(spotify_track)
        await create_mapping(track.id, spotify_track.id, service='spotify')
        return track
    
    # 3. Search Tidal
    tidal_track = await tidal_client.search_by_isrc(isrc)
    if tidal_track:
        track = await create_generic_track(tidal_track)
        await create_mapping(track.id, tidal_track.id, service='tidal')
        return track
    
    return None
```

## API Route Design

### Generic Routes (All Services)

```python
# /api/playlists - Works for all services
@router.get("/playlists")
async def list_playlists(service: str | None = None):
    if service:
        return await playlist_service.get_by_service(service)
    return await playlist_service.get_all()

# /api/tracks/{track_id}/play - Service-agnostic
@router.post("/tracks/{track_id}/play")
async def play_track(track_id: str):
    track = await track_service.get_by_id(track_id)
    return await audio_service.play(track)
```

### Service-Specific Routes (Auth Only)

```python
# /api/spotify/auth - Spotify OAuth flow
@router.get("/spotify/auth/callback")
async def spotify_auth_callback(code: str):
    return await spotify_auth.handle_callback(code)

# /api/tidal/auth - Tidal OAuth flow
@router.get("/tidal/auth/callback")
async def tidal_auth_callback(code: str):
    return await tidal_auth.handle_callback(code)
```

## Service Badge System

**CSS Classes:**

```css
.badge-spotify { background: #1db954; color: white; }
.badge-tidal { background: #00d9ff; color: black; }
.badge-deezer { background: #ff9900; color: white; }
.badge-local { background: #6b7280; color: white; }
```

**Icon System:**

```html
<i class="icon-spotify bi-spotify"></i>
<i class="icon-tidal bi-music-note"></i>
<i class="icon-deezer bi-disc"></i>
<i class="icon-local bi-folder"></i>
```

## Extensibility Checklist

Adding new service (e.g., Apple Music):

1. ✅ Create `AppleMusicClient` implementing `IMusicClient` interface
2. ✅ Create `apple_music_sessions` table
3. ✅ Create `apple_music_track_mappings` table
4. ✅ Add `badge-apple-music` CSS class
5. ✅ Add `icon-apple-music` icon
6. ✅ Add OAuth routes: `/api/apple-music/auth`
7. ✅ **Generic components work immediately** (0 changes)

**Estimated effort:** 4-6 hours (95% of UI requires no changes)

## Related Documentation

- [UI Architecture](./ui-architecture-principles.md) - Component design principles
- [Plugin System](../02-architecture/plugin-system.md) - Service plugin architecture
- [Service-Agnostic Backend](../03-architecture-planning/service-agnostic-backend.md) - Backend strategy
- [Data Standards](../02-architecture/data-standards.md) - Entity definitions
