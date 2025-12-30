# ADR-001: Plugin-Based Multi-Service Architecture

**Category:** Architecture Decision Record  
**Status:** ACCEPTED ✅  
**Date:** 2025-01  
**Decision Makers:** Core Team  
**Related:** [Plugin System](./plugin-system.md) | [Service-Agnostic Backend](./service-agnostic-backend.md)

---

## Executive Summary

**Transform SoulSpot from Spotify-centric music library manager to plugin-based system supporting multiple streaming services (Spotify, Tidal, Deezer) as metadata sources, while maintaining Soulseek (slskd) as the exclusive download backend.**

**Core Principle:** Services provide metadata only—SoulSpot manages the unified library, downloads happen via Soulseek.

---

## Decision Overview

| Decision | Outcome | Status |
|----------|---------|--------|
| **D1: Multi-Service Architecture** | Users connect multiple services simultaneously | ✅ Accepted |
| **D2: Service-Agnostic Playlists** | Playlists NOT tied to any service | ✅ Accepted |
| **D3: Track Deduplication** | ISRC → MusicBrainz → Fuzzy cascade | ⏳ Phase 2 |
| **D4: Download Backend** | Soulseek (slskd) remains ONLY source | ✅ Accepted |
| **D5: Migration Strategy** | Big Bang refactoring (6-8 weeks) | ✅ Accepted |
| **D6: Plugin Distribution** | Hardcoded monorepo (official only) | ✅ Accepted |
| **D7: User Experience** | SoulSpot-centric UI (service-agnostic) | ✅ Accepted |
| **D8: Database Schema** | Hybrid (shared core + isolated plugin data) | ✅ Accepted |
| **D9: Plugin Interface** | Mandatory features for ALL plugins | ✅ Accepted |
| **D10: Plugin Capabilities** | Optional features (lyrics, hi-res) | ✅ Accepted |
| **D11: Authentication** | Master account (single-user) | ✅ Accepted |
| **D12: Sync Strategy** | Daily auto-sync + on-demand | ✅ Accepted |
| **D13: Error Handling** | Skip + notify with circuit breaker | ✅ Accepted |

---

## Decision 1: Multi-Service Architecture

**Decision:** Users can connect multiple services (Spotify + Tidal + Deezer) simultaneously.

### Rationale
- **Cross-service metadata quality:** Compare album art, track metadata across providers
- **No vendor lock-in:** Switch services freely without losing library
- **Graceful degradation:** If one service is down, others still work

### Technical Impact
- **Multi-session management:** One OAuth session per service
- **Database schema:** `service_sessions` table with `service_type` discriminator
- **UI:** Aggregated view showing tracks from all connected services

### Implementation
```python
# User connects both Spotify and Deezer
sessions = [
    SpotifySession(access_token="sp_token", ...),
    DeezerSession(access_token="dz_token", ...)
]

# Browse new releases from BOTH
all_releases = []
for session in sessions:
    plugin = get_plugin(session.service_type)
    releases = await plugin.get_new_releases(session)
    all_releases.extend(releases)
```

**Status:** ✅ IMPLEMENTED

---

## Decision 2: Service-Agnostic Playlists

**Decision:** Playlists are NOT tied to any service. A single SoulSpot playlist can contain tracks from Spotify, Tidal, and Deezer mixed together.

### Rationale
- User creates playlists **in SoulSpot**, not tied to any service
- Tracks imported/synced from services become **SoulSpot entities**
- Maximum flexibility: Add Spotify track → Deezer track to same playlist

### Technical Impact
- `Playlist` entity has **NO** `service_type` field
- `PlaylistTrack` has **`source_service`** nullable field (tracks origin)
- Track deduplication becomes **critical** (see D3)

### Schema
```sql
CREATE TABLE playlists (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
    -- NO service_type field!
);

CREATE TABLE playlist_tracks (
    id UUID PRIMARY KEY,
    playlist_id UUID NOT NULL REFERENCES playlists(id),
    track_id UUID NOT NULL REFERENCES tracks(id),
    source_service VARCHAR(50),  -- 'spotify', 'deezer', 'tidal' (nullable)
    position INT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL
);
```

**Status:** ✅ IMPLEMENTED

---

## Decision 3: Track Deduplication Strategy

**Decision:** DEFERRED to Phase 2. Requires further analysis.

### Options Considered

| Method | Accuracy | Availability | Rate Limits |
|--------|----------|--------------|-------------|
| **ISRC** | High | Spotify, Tidal, Deezer APIs | None |
| **MusicBrainz ID** | Very High | Requires enrichment | 1 req/sec |
| **Fuzzy Match** | Medium | Always available | None |

### Recommended Approach (Phase 2)
**Priority cascade:**
1. **ISRC match** (if present on both sides)
2. **MusicBrainz Recording ID** (if enriched)
3. **Fuzzy match:** Artist + Title + Duration (±3s tolerance)
4. **Create new track** (if no match)

### Example
```python
async def find_or_create_track(track_dto: TrackDTO) -> Track:
    # 1. Try ISRC
    if track_dto.isrc:
        existing = await track_repo.get_by_isrc(track_dto.isrc)
        if existing:
            return existing
    
    # 2. Try MusicBrainz ID
    if track_dto.musicbrainz_id:
        existing = await track_repo.get_by_musicbrainz_id(track_dto.musicbrainz_id)
        if existing:
            return existing
    
    # 3. Fuzzy match
    candidates = await track_repo.search(
        artist=track_dto.artist,
        title=track_dto.title,
        duration_tolerance_seconds=3
    )
    if candidates:
        return candidates[0]  # Best match
    
    # 4. Create new
    return await track_repo.create(track_dto)
```

**Status:** ⏳ DEFERRED - Implement in Phase 2

---

## Decision 4: Download Backend

**Decision:** Soulseek (slskd) remains the ONLY download source. Streaming services provide metadata only.

### Rationale
- **Spotify/Tidal/Deezer:** Metadata-only APIs, no file downloads
- **Soulseek:** Provides high-quality community files (FLAC, 320kbps MP3)
- **No change to existing infrastructure:** Download logic stays in `infrastructure/clients/slskd_client.py`

### Technical Impact
- **Plugin interface does NOT include download methods**
- Plugins implement: `get_track_metadata()`, `search_tracks()`, etc.
- Plugins do NOT implement: `download_track()`

### Workflow
```python
# 1. User finds track via Spotify plugin
spotify_track = await spotify_plugin.get_track_metadata("spotify:track:xyz")

# 2. Import to SoulSpot library
soulspot_track = await import_service.import_track(spotify_track)

# 3. Download via Soulseek (separate operation)
await download_manager.queue_download(soulspot_track.id)
# Uses slskd_client internally
```

**Status:** ✅ ACCEPTED

---

## Decision 5: Migration Strategy

**Decision:** Big Bang Refactoring—complete rewrite before next release.

### Rationale
- **Current codebase:** ~80% complete, architectural changes are fundamental
- **No incremental path:** Cannot run old + new systems simultaneously
- **No production users yet:** SoulSpot is an internal tool
- **Timeline:** 6-8 weeks acceptable

### Alternative Rejected: Strangler Fig Pattern
- **Too slow:** Temporary complexity not justified
- **Dual systems:** Confusing state management
- **Not worth it:** No external users to protect

**Status:** ✅ COMPLETED (January 2025)

---

## Decision 6: Plugin Distribution

**Decision:** Hardcoded monorepo—official plugins only (Spotify, Tidal, Deezer).

### Rationale
- All plugins maintained by **core team**
- Atomic releases: Core + plugins versioned together (e.g., `v1.5.0`)
- Simplified testing: No external dependency conflicts

### Plugin Location
```
src/soulspot/plugins/
├── __init__.py
├── base.py              # IPlugin interface
├── spotify/
│   ├── client.py        # SpotifyClient (API wrapper)
│   ├── auth.py          # OAuth flow
│   └── mapper.py        # Service → Domain mapping
├── tidal/
│   └── ...
└── deezer/
    └── ...
```

### Future Consideration
If community requests SoundCloud/Qobuz support, consider dynamic loading via `entry_points`.

**Status:** ✅ IMPLEMENTED

---

## Decision 7: User Experience

**Decision:** SoulSpot-centric UI—services are implementation details (metadata sources).

### Rationale
- User sees **ONE unified library** (aggregated from all services)
- No "service switcher"—all services active simultaneously
- Small badge shows track origin (Spotify/Tidal icon)

### UI Patterns
- **Library view:** Aggregated tracks/artists/albums from ALL services
- **Playlist view:** Mixed tracks (any service)
- **Service indicator:** Small badge shows track origin
- **Settings:** Connect/disconnect services independently

### Example
```
┌─────────────────────────────────────────────┐
│ My Library                                  │
├─────────────────────────────────────────────┤
│ ♫ Bohemian Rhapsody          [Spotify 🟢]  │
│ ♫ Stairway to Heaven         [Deezer  🔵]  │
│ ♫ Hotel California           [Tidal   🔷]  │
└─────────────────────────────────────────────┘
```

**Status:** ✅ IMPLEMENTED

---

## Decision 8: Database Schema Strategy

**Decision:** Hybrid approach—shared core entities + isolated plugin data.

### Core Entities (Service-Agnostic)
```sql
CREATE TABLE tracks (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    duration_ms INT,
    isrc VARCHAR(20),
    musicbrainz_id VARCHAR(50),
    -- NO spotify_id, tidal_id here!
);

CREATE TABLE artists (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    musicbrainz_id VARCHAR(50)
    -- NO service IDs here!
);

CREATE TABLE albums (...);
CREATE TABLE playlists (...);
CREATE TABLE playlist_tracks (
    id UUID PRIMARY KEY,
    playlist_id UUID REFERENCES playlists(id),
    track_id UUID REFERENCES tracks(id),
    source_service VARCHAR(50)  -- 'spotify', 'deezer', etc.
);
```

### Plugin-Specific Tables
```sql
-- Spotify OAuth tokens (isolated)
CREATE TABLE spotify_sessions (
    id UUID PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE tidal_sessions (...);
CREATE TABLE deezer_sessions (...);

-- Optional: Import cache (performance)
CREATE TABLE spotify_import_cache (
    track_id UUID REFERENCES tracks(id),
    spotify_track_id VARCHAR(255) NOT NULL,
    last_synced_at TIMESTAMPTZ
);
```

### Rationale
- **Core domain stays clean:** No service coupling
- **Plugins manage own persistence:** Easy to add/remove services
- **No migration pain:** Drop Tidal support = drop `tidal_sessions` table

**Status:** ✅ IMPLEMENTED

---

## Decision 9: Plugin Interface (Mandatory Features)

**Decision:** Every plugin MUST implement these core methods.

### Interface
```python
class IPlugin(Protocol):
    """Base interface for ALL music service plugins."""
    
    # Identity
    service_name: str                    # 'spotify', 'tidal', 'deezer'
    service_version: str                 # '1.0.0'
    
    # Authentication
    async def authenticate(self, credentials: dict) -> ServiceSession: ...
    async def refresh_token(self, session: ServiceSession) -> ServiceSession: ...
    async def is_authenticated(self, session: ServiceSession) -> bool: ...
    
    # User library
    async def get_user_playlists(self, session: ServiceSession) -> list[Playlist]: ...
    async def get_playlist_tracks(self, session: ServiceSession, playlist_id: str) -> list[Track]: ...
    async def get_followed_artists(self, session: ServiceSession) -> list[Artist]: ...
    async def get_artist_albums(self, session: ServiceSession, artist_id: str) -> list[Album]: ...
    async def get_album_tracks(self, session: ServiceSession, album_id: str) -> list[Track]: ...
    
    # Discovery
    async def get_new_releases(self, session: ServiceSession, artist_ids: list[str]) -> list[Album]: ...
    
    # Metadata
    async def get_track_metadata(self, session: ServiceSession, track_id: str) -> Track: ...
    async def get_artist_metadata(self, session: ServiceSession, artist_id: str) -> Artist: ...
    async def get_album_metadata(self, session: ServiceSession, album_id: str) -> Album: ...
    
    # Search
    async def search_tracks(self, session: ServiceSession, query: str) -> list[Track]: ...
    async def search_artists(self, session: ServiceSession, query: str) -> list[Artist]: ...
```

### Mandatory Data Fields
**Track must include:**
- Title, artists, album, duration
- **ISRC** (if available)

**Artist must include:**
- Name
- **MusicBrainz ID** (if available)

**Album must include:**
- Title, artist, release date
- Compilation flag (yes/no)

**Status:** ✅ IMPLEMENTED

---

## Decision 10: Plugin Capabilities (Optional Features)

**Decision:** Plugins CAN implement optional features via capability system.

### Rationale
Not all services support all features:
- **Tidal:** Has lyrics
- **Spotify:** No lyrics API
- SoulSpot adapts UI based on available capabilities

### Capability Interface
```python
class IPluginCapabilities(Protocol):
    """Optional features a plugin may support."""
    
    supports_lyrics: bool                # Tidal ✅, Spotify ❌
    supports_high_res_audio: bool        # Tidal ✅ (MQA), Spotify ❌
    supports_podcasts: bool              # Spotify ✅, Deezer ✅, Tidal ❌
    supports_music_videos: bool          # Tidal ✅, others ❌
    
    max_audio_quality: str               # '320kbps', 'FLAC', 'MQA'
    
    # Optional methods (if supported)
    async def get_track_lyrics(self, session, track_id: str) -> str | None: ...
    async def get_artist_radio(self, session, artist_id: str) -> list[Track]: ...
```

### Example Usage
```python
# UI adapts based on capabilities
if spotify_plugin.supports_lyrics:
    show_lyrics_button()  # False for Spotify

if tidal_plugin.supports_lyrics:
    show_lyrics_button()  # True for Tidal

# Show "Lyrics" button if ANY connected plugin supports
if any(p.supports_lyrics for p in active_plugins):
    show_lyrics_button()
```

**Status:** ✅ IMPLEMENTED

---

## Decision 11: Authentication Model

**Decision:** Master account (single-user system).

### Rationale
- SoulSpot is a **personal music library manager** (not multi-tenant)
- No multi-user requirements
- Simplified authentication: No `user_id` foreign keys

### Technical Impact
- **One set of service sessions** per SoulSpot instance
- No `user_id` in core tables (`tracks`, `artists`, etc.)
- Settings stored **globally**, not per-user

### Schema
```sql
CREATE TABLE service_sessions (
    id UUID PRIMARY KEY,
    service_type VARCHAR(50) UNIQUE NOT NULL,  -- 'spotify', 'tidal', 'deezer'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    scope TEXT,                                 -- OAuth scopes
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    
    CHECK (service_type IN ('spotify', 'tidal', 'deezer'))
);
```

**Future Consideration:** If multi-user support needed, add `user_id UUID` to all tables.

**Status:** ✅ IMPLEMENTED

---

## Decision 12: Sync Strategy

**Decision:** Automated daily sync + on-demand manual sync.

### Behavior
- **Daily sync:** At 3 AM (configurable), sync playlists + followed artists from ALL connected services
- **On-demand sync:** User triggers manual sync via UI
- **Incremental sync:** Only fetch changes since last sync (using service pagination/cursors)

### Implementation
```python
# Background worker (reuses existing worker pattern)
async def daily_sync_worker():
    """Sync all connected services."""
    while True:
        await asyncio.sleep(60 * 60)  # 1 hour check
        
        if should_sync():  # 3 AM check
            for plugin in get_active_plugins():
                try:
                    session = await get_service_session(plugin.service_name)
                    
                    # Sync playlists
                    playlists = await plugin.get_user_playlists(session)
                    await import_service.import_playlists(playlists)
                    
                    # Sync followed artists
                    artists = await plugin.get_followed_artists(session)
                    await import_service.import_artists(artists)
                    
                except PluginError as e:
                    logger.error(f"Sync failed for {plugin.service_name}: {e}")
                    await notify_user(f"{plugin.service_name} sync failed")
```

### Worker Management
Reuses existing `app.state` worker pattern (`infrastructure/lifecycle.py`).

**Status:** ✅ IMPLEMENTED

---

## Decision 13: Error Handling & Resilience

**Decision:** Skip + Notify with Circuit Breaker pattern.

### Behavior
If a plugin fails (API down, auth expired, rate limit):
1. **SKIP** that plugin, continue with others
2. User gets notification (UI toast or log entry)
3. **Circuit breaker:** After 3 consecutive failures, mark plugin "unhealthy" for 30 minutes

### Example
```python
# Multi-service search (graceful degradation)
async def search_all_services(query: str) -> list[Track]:
    """Search across ALL connected services."""
    results = []
    
    for plugin in get_active_plugins():
        try:
            session = await get_service_session(plugin.service_name)
            tracks = await plugin.search_tracks(session, query)
            results.extend(tracks)
        
        except PluginError as e:
            # Log error, skip plugin, notify user
            logger.warning(f"Search failed for {plugin.service_name}: {e}")
            await circuit_breaker.record_failure(plugin.service_name)
            
            # User still sees results from other services
            continue
    
    return deduplicate_tracks(results)  # See D3
```

### Circuit Breaker
```python
# After 3 failures, mark unhealthy for 30 minutes
if circuit_breaker.is_open(plugin.service_name):
    logger.info(f"Skipping {plugin.service_name} (circuit breaker open)")
    continue
```

**Status:** ✅ IMPLEMENTED

---

## Implementation Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| **Phase 1:** Plugin infrastructure | 2 weeks | ✅ DONE |
| **Phase 2:** Spotify plugin migration | 2 weeks | ✅ DONE |
| **Phase 3:** Deezer plugin | 1 week | ✅ DONE |
| **Phase 4:** Tidal plugin | 1 week | ✅ DONE |
| **Phase 5:** Track deduplication | 1 week | ⏳ TODO |
| **Phase 6:** UI polish | 1 week | ✅ DONE |

**Total:** 8 weeks (January 2025)

---

## Consequences

### Positive
✅ **Multi-service support:** Users not locked to one provider  
✅ **Future-proof:** Easy to add Qobuz, SoundCloud, etc.  
✅ **Clean architecture:** Plugin pattern enforces separation  
✅ **Graceful degradation:** One service down ≠ app broken  

### Negative
❌ **Increased complexity:** More code paths to test  
❌ **Deduplication challenges:** See D3 (Phase 2)  
❌ **Session management overhead:** Multiple OAuth tokens  

### Neutral
⚪ **Migration effort:** 6-8 weeks acceptable for internal tool  
⚪ **No breaking changes:** User data preserved  

---

## Related Documentation

- **[Plugin System](./plugin-system.md)** - Implementation details
- **[Service-Agnostic Backend](./service-agnostic-backend.md)** - Architecture patterns
- **[Data Standards](./data-standards.md)** - DTO definitions
- **[Database Schema](./database-schema-hybrid-library.md)** - Table structures (Appendix E)

---

**Approved:** 2025-01  
**Implemented:** ✅ Core features complete, deduplication Phase 2  
**Review Date:** 2025-06 (after 6 months production use)
