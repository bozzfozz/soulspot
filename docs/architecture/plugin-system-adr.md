# ADR-001: Plugin-Based Multi-Service Architecture

**Status:** Approved  
**Date:** 2025-12-10  
**Decision Makers:** Product Owner  
**Context:** SoulSpot Transformation from Spotify-centric to Plugin-based Multi-Service System

---

## Executive Summary

Transform SoulSpot from a Spotify-only music library manager to a **plugin-based system** supporting multiple streaming services (Spotify, Tidal, Deezer) as **metadata sources** while maintaining Soulseek (slskd) as the exclusive download backend.

**Core Principle:** Services provide metadata only. SoulSpot manages the unified library. Downloads happen via Soulseek.

---

## Decision Outcomes

### 1. Multi-Service Architecture
**Decision:** Users can connect **multiple services simultaneously** (Spotify + Tidal + Deezer active in parallel).

**Rationale:**
- Users may have subscriptions to multiple services
- Cross-service metadata quality comparison
- No service lock-in

**Technical Impact:**
- Multi-session management (one OAuth session per service)
- DB schema: `service_sessions` table with `service_type` discriminator
- UI: Aggregated view of all connected services

---

### 2. Service-Agnostic Playlists
**Decision:** Playlists are **service-agnostic**. A single playlist can contain tracks from Spotify, Tidal, and Deezer mixed together.

**Rationale:**
- User creates playlists in SoulSpot, not tied to any service
- Tracks are imported/synced from services but become SoulSpot entities
- Maximum flexibility for user curation

**Technical Impact:**
- `Playlist` entity has NO `service_type` field
- `PlaylistTrack` has `source_service` field (nullable) to track origin
- Track deduplication critical (see Decision #3)

**Schema:**
```sql
CREATE TABLE playlists (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE playlist_tracks (
    id UUID PRIMARY KEY,
    playlist_id UUID REFERENCES playlists(id),
    track_id UUID REFERENCES tracks(id),
    source_service VARCHAR(50),  -- 'spotify', 'tidal', 'deezer', NULL (manual)
    position INT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL
);
```

---

### 3. Track Deduplication Strategy
**Decision:** **DEFERRED** – Requires further analysis.

**Options Under Consideration:**
1. **ISRC (International Standard Recording Code)**
   - ✅ Industry standard for recordings
   - ✅ Available in Spotify/Tidal/Deezer APIs
   - ❌ Not all tracks have ISRC (indie releases)

2. **MusicBrainz ID**
   - ✅ Already used in current codebase
   - ✅ High-quality metadata
   - ❌ Requires API lookup (rate-limited)

3. **Fuzzy Matching**
   - ✅ Fallback for tracks without ISRC/MB ID
   - ✅ Artist + Title + Duration tolerance (±3s)
   - ❌ False positives possible (live vs. studio versions)

**Recommended Approach:**
```python
# Deduplication priority cascade
1. Match by ISRC (if present on both sides)
2. Match by MusicBrainz Recording ID (if enriched)
3. Fuzzy match: Artist + Title + Duration (±3s tolerance)
4. If no match: Create new Track entity
```

**Action Item:** Implement deduplication algorithm in Phase 2 (see Roadmap).

---

### 4. Download Backend
**Decision:** **Soulseek (slskd) remains the ONLY download source**.

**Rationale:**
- Services (Spotify/Tidal/Deezer) are metadata-only (no file downloads)
- Soulseek provides high-quality files from community
- No change to existing download infrastructure

**Technical Impact:**
- Plugin interface does NOT include download methods
- Download logic stays in `infrastructure/clients/slskd_client.py`
- Plugins only provide metadata for search optimization

---

### 5. Migration Strategy
**Decision:** **Big Bang Refactoring** (complete rewrite before next release).

**Rationale:**
- Current codebase is 80% complete
- Architectural changes are fundamental (not incremental)
- No production users yet (internal tool)

**Timeline:** 6-8 weeks (see Roadmap Section)

**Alternatives Rejected:**
- ❌ Strangler Fig Pattern: Too slow, temporary complexity not justified

---

### 6. Plugin Distribution
**Decision:** **Hardcoded Monorepo** (official plugins only).

**Rationale:**
- All plugins (Spotify, Tidal, Deezer) maintained by core team
- Atomic releases (core + plugins versioned together)
- Simplified testing (no external dependency conflicts)

**Plugin Location:**
```
src/soulspot/plugins/
├── __init__.py
├── base.py          # IPlugin interface
├── spotify/
│   ├── __init__.py
│   ├── client.py
│   ├── auth.py
│   └── mapper.py    # Service → Domain entity mapping
├── tidal/
│   └── ...
└── deezer/
    └── ...
```

**Future Consideration:** If community requests plugins (e.g., SoundCloud), consider dynamic loading via entry points.

---

### 7. User Experience
**Decision:** **SoulSpot-centric UI** (service-agnostic interface).

**Rationale:**
- Services are implementation details (metadata sources)
- User sees ONE unified library
- No service switcher needed (all services active simultaneously)

**UI Patterns:**
- Library view: Aggregated tracks/artists/albums from all services
- Playlist view: Mixed tracks from any service
- Service indicator: Small badge shows track origin (Spotify/Tidal icon)
- Settings: Connect/disconnect services independently

**Reference:** Existing UI docs in `docs/feat-ui/` apply (no redesign needed).

---

### 8. Database Schema Strategy
**Decision:** **Hybrid Approach**
- **Core Entities:** Shared tables (service-agnostic)
- **Plugin Data:** Isolated tables (service-specific)

**Core Entities (Shared):**
```sql
-- Service-agnostic entities
tracks (id, title, duration, isrc, musicbrainz_id, ...)
artists (id, name, musicbrainz_id, ...)
albums (id, title, release_date, ...)
playlists (id, name, description, ...)
playlist_tracks (id, playlist_id, track_id, source_service, ...)
```

**Plugin-Specific Tables:**
```sql
-- OAuth sessions per service
spotify_sessions (id, access_token, refresh_token, expires_at, ...)
tidal_sessions (...)
deezer_sessions (...)

-- Import cache (optional)
spotify_import_cache (track_id, spotify_track_id, last_sync, ...)
tidal_import_cache (...)
```

**Rationale:**
- Core domain stays clean (no service coupling)
- Plugins manage their own persistence needs
- Easy to add/remove services without touching core schema

---

### 9. Plugin Interface (Mandatory Features)
**Decision:** Every plugin MUST implement:

```python
class IPlugin(Protocol):
    """Base interface for all music service plugins."""
    
    # Metadata
    service_name: str  # "spotify", "tidal", "deezer"
    service_version: str  # Plugin version
    
    # Authentication
    async def authenticate(self, credentials: dict) -> ServiceSession
    async def refresh_token(self, session: ServiceSession) -> ServiceSession
    async def is_authenticated(self) -> bool
    
    # Core Data Retrieval
    async def get_user_playlists(self) -> list[Playlist]
    async def get_playlist_tracks(self, playlist_id: str) -> list[Track]
    async def get_followed_artists(self) -> list[Artist]
    async def get_artist_albums(self, artist_id: str) -> list[Album]
    async def get_album_tracks(self, album_id: str) -> list[Track]
    async def get_new_releases(self, artist_ids: list[str]) -> list[Album]
    
    # Metadata Enrichment
    async def get_track_metadata(self, track_id: str) -> Track
    async def get_artist_metadata(self, artist_id: str) -> Artist
    async def get_album_metadata(self, album_id: str) -> Album
    
    # Search (for matching)
    async def search_tracks(self, query: str) -> list[Track]
    async def search_artists(self, query: str) -> list[Artist]
```

**Mandatory Data Fields:**
- **Track:** title, artist(s), album, duration, ISRC (if available)
- **Artist:** name, MusicBrainz ID (if available)
- **Album:** title, artist, release_date, compilation flag

---

### 10. Plugin Capabilities (Optional Features)
**Decision:** Plugins CAN implement optional features via **capability system**.

**Rationale:**
- Not all services support all features (e.g., Tidal has lyrics, Spotify doesn't)
- SoulSpot adapts UI based on available capabilities

**Capability Interface:**
```python
class IPluginCapabilities(Protocol):
    def supports_lyrics(self) -> bool
    def supports_high_res_audio(self) -> bool
    def supports_podcasts(self) -> bool
    def supports_music_videos(self) -> bool
    def max_audio_quality(self) -> str  # "320kbps", "FLAC", "MQA"
    
    # Optional methods (only if supported)
    async def get_track_lyrics(self, track_id: str) -> str | None
    async def get_artist_radio(self, artist_id: str) -> list[Track]
```

**Example:**
```python
spotify_plugin.supports_lyrics() → False
tidal_plugin.supports_lyrics() → True
deezer_plugin.supports_lyrics() → True

# UI shows "Lyrics" button only if ANY connected plugin supports it
```

---

### 11. Authentication Model
**Decision:** **Master Account** (single-user system).

**Rationale:**
- SoulSpot is a personal music library manager
- No multi-user/multi-tenant requirements
- Simplified authentication (no user_id foreign keys)

**Technical Impact:**
- One set of service sessions per SoulSpot instance
- No `user_id` in core tables
- Settings stored globally (not per-user)

**Schema:**
```sql
-- One session per service (no user_id)
CREATE TABLE service_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) UNIQUE NOT NULL,  -- 'spotify', 'tidal', 'deezer'
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    scope TEXT,  -- OAuth scopes granted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CHECK (service_type IN ('spotify', 'tidal', 'deezer'))
);
```

---

### 12. Sync Strategy
**Decision:** **Automated Daily Sync** via background worker.

**Behavior:**
- Daily at 3 AM (configurable): Sync playlists + followed artists from all connected services
- On-demand sync: User can trigger manual sync via UI
- Incremental sync: Only fetch changes since last sync (using service pagination/cursors)

**Technical Implementation:**
```python
# Background worker (existing pattern in codebase)
async def daily_sync_worker():
    """Syncs all connected services."""
    for plugin in get_active_plugins():
        try:
            await sync_service_data(plugin)
        except PluginError as e:
            logger.error(f"{plugin.service_name} sync failed: {e}")
            await notify_user(f"Sync failed for {plugin.service_name}")
```

**Worker Management:** Reuse existing `app.state` worker pattern (see `infrastructure/lifecycle.py`).

---

### 13. Error Handling & Resilience
**Decision:** **Skip + Notify** with Circuit Breaker pattern.

**Behavior:**
- If a plugin fails (API down, auth expired, rate limit): **Skip** that plugin, continue with others
- User gets **notification** (UI toast or log entry)
- Circuit Breaker: After 3 consecutive failures, mark plugin as "unhealthy" for 30 minutes

**Implementation:**
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout_seconds=1800):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = timeout_seconds
        self.opened_at = None
    
    async def call(self, plugin_method):
        if self.is_open():
            raise PluginUnavailableError(f"Circuit open until {self.reset_time}")
        
        try:
            result = await plugin_method()
            self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise
```

**User Notification:**
- UI: "⚠️ Spotify sync failed. Retrying in 30 minutes."
- Logs: Detailed error for debugging

---

### 14. Plugin Priority (Metadata Quality Ranking)
**Decision:** **Quality-based ranking** when multiple plugins provide same data.

**Ranking Criteria:**
1. **Metadata Completeness** (ISRC, MusicBrainz ID, high-res artwork)
2. **Data Freshness** (most recently updated)
3. **Service Reliability** (historical uptime)

**Example:**
```python
# If Track "Song X" exists in Spotify AND Tidal:
# → Use Tidal metadata (if it has ISRC + MusicBrainz ID)
# → Use Spotify as fallback (if Tidal missing fields)

async def get_best_track_metadata(track_title: str, artist: str) -> Track:
    candidates = []
    for plugin in get_active_plugins():
        results = await plugin.search_tracks(f"{artist} {track_title}")
        candidates.extend(results)
    
    # Sort by quality score
    return max(candidates, key=lambda t: calculate_quality_score(t))

def calculate_quality_score(track: Track) -> int:
    score = 0
    if track.isrc: score += 10
    if track.musicbrainz_id: score += 10
    if track.album and track.album.artwork_url: score += 5
    if track.explicit is not None: score += 2
    return score
```

**Future Enhancement:** Allow user to manually override priority (e.g., "Always prefer Tidal").

---

## Migration Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Establish plugin architecture without breaking existing features.

**Tasks:**
1. Create `IPlugin` interface in `domain/ports/plugin.py`
2. Extract Spotify logic into `plugins/spotify/` (no behavior change)
3. Add `service_type` field to relevant tables (migration)
4. Update repositories to handle multi-service data

**Deliverable:** Spotify works as a plugin (existing tests pass).

---

### Phase 2: Tidal Integration (Week 3-4)
**Goal:** Add second plugin to validate architecture.

**Tasks:**
1. Implement `plugins/tidal/client.py` (OAuth, API calls)
2. Implement `plugins/tidal/mapper.py` (Tidal API → Domain entities)
3. Add `tidal_sessions` table (migration)
4. Implement track deduplication (ISRC-based)
5. Add Tidal tests

**Deliverable:** Users can connect Tidal + Spotify simultaneously.

---

### Phase 3: Deezer Integration (Week 5)
**Goal:** Third plugin for completeness.

**Tasks:**
1. Implement `plugins/deezer/` (similar to Tidal)
2. Add `deezer_sessions` table (migration)
3. Test 3-service aggregation

**Deliverable:** All three services functional.

---

### Phase 4: Plugin Manager & UI (Week 6)
**Goal:** User-facing plugin management.

**Tasks:**
1. Settings page: Connect/disconnect services
2. Service health dashboard (circuit breaker status)
3. Manual sync trigger UI
4. Service badges in track listings

**Deliverable:** Full UI for managing plugins.

---

### Phase 5: Optimization & Testing (Week 7-8)
**Goal:** Production-ready quality.

**Tasks:**
1. Performance optimization (parallel plugin calls)
2. Comprehensive integration tests (multi-service scenarios)
3. Error handling stress tests (simulate API failures)
4. Documentation updates (all ADRs, guides, API docs)
5. Migration guide for existing SoulSpot users

**Deliverable:** Release v2.0.0 (Plugin System).

---

## Technical Debt & Future Work

### Immediate Scope (v2.0.0)
- ✅ Three official plugins (Spotify, Tidal, Deezer)
- ✅ Service-agnostic playlists
- ✅ Automated daily sync
- ✅ Circuit breaker error handling

### Future Enhancements (v2.1+)
- [ ] **Dynamic Plugin Loading** (community plugins via PyPI)
- [ ] **Track Deduplication UI** (manual conflict resolution)
- [ ] **Service Priority Settings** (user-defined preferences)
- [ ] **Lyrics Integration** (via plugins that support it)
- [ ] **Playlist Export** (back to services)
- [ ] **Advanced Search** (cross-service metadata search)
- [ ] **Quality-based Download Hints** (suggest best Soulseek search terms based on plugin metadata)
- [ ] **Cross-Service Track Resolution** (find same track on all services, show quality comparison)
- [ ] **Bidirectional Playlist Sync** (edit in SoulSpot, push changes back to services)
- [ ] **Metadata Conflict Resolution UI** (when services disagree on metadata)

### Known Limitations
- **No Real-time Sync:** Changes in services require daily sync or manual trigger (no webhooks)
- **ISRC Gaps:** Track deduplication relies on ISRC availability (not all tracks have it)
- **Single-User Only:** No multi-tenant support planned

---

## Compliance & Security

### API Rate Limits
- Spotify: 30 requests/second (per app)
- Tidal: Undocumented (assume 10/sec conservative)
- Deezer: 50 requests/5 seconds

**Mitigation:** Implement rate limiter per plugin (reuse existing pattern from `infrastructure/rate_limiter.py` if exists, otherwise create).

### Token Security
- **Storage:** Encrypted at rest (DB-level encryption or application-level via `cryptography` lib)
- **Transmission:** HTTPS only (enforce in nginx/reverse proxy)
- **Rotation:** Auto-refresh tokens via plugin `refresh_token()` method

### GDPR Considerations
- **Data Minimization:** Only store necessary metadata (no user listening history)
- **Right to Deletion:** User can disconnect service → delete all service-specific data
- **Export:** Provide playlist export (JSON/M3U)

---

## Success Metrics

### Phase 1-3 (Development)
- ✅ All existing Spotify tests pass after refactoring
- ✅ Tidal + Deezer plugins pass identical test suites
- ✅ No performance regression (sync time ≤ current Spotify-only sync)

### Phase 4-5 (Quality)
- ✅ Code coverage ≥ 80% (unit + integration)
- ✅ All security scans (bandit, ruff) pass
- ✅ Type coverage 100% (mypy strict)
- ✅ Documentation updated (API, guides, examples)

### Post-Launch (v2.0.0)
- Track deduplication accuracy ≥ 95% (manual validation on 100-track sample)
- Multi-service sync completes in <5 minutes (for typical library: 500 playlists, 10k tracks)
- Zero critical bugs in first month

---

## Appendix A: Plugin Interface (Full Specification)

See `docs/architecture/plugin-interface-spec.md` (to be created in Phase 1).

**Preview:**
```python
# src/soulspot/domain/ports/plugin.py
from abc import Protocol
from datetime import datetime
from typing import Optional

class ServiceSession:
    """OAuth session data (plugin-specific)."""
    access_token: str
    refresh_token: str
    expires_at: datetime

class IPlugin(Protocol):
    """
    Base contract for all music service plugins.
    
    Plugins provide metadata ONLY (no file downloads).
    All methods are async and should handle rate limiting internally.
    """
    
    # Plugin Metadata
    service_name: str  # "spotify", "tidal", "deezer"
    service_version: str  # "1.0.0"
    
    # Authentication (OAuth 2.0)
    async def get_auth_url(self, redirect_uri: str) -> str
    async def authenticate(self, code: str, redirect_uri: str) -> ServiceSession
    async def refresh_token(self, session: ServiceSession) -> ServiceSession
    async def revoke_token(self, session: ServiceSession) -> None
    
    # User Library
    async def get_user_playlists(self, session: ServiceSession) -> list[Playlist]
    async def get_followed_artists(self, session: ServiceSession) -> list[Artist]
    async def get_saved_albums(self, session: ServiceSession) -> list[Album]
    async def get_saved_tracks(self, session: ServiceSession) -> list[Track]
    
    # Detailed Retrieval
    async def get_playlist_tracks(self, session: ServiceSession, playlist_id: str) -> list[Track]
    async def get_artist_albums(self, session: ServiceSession, artist_id: str, include_compilations: bool = True) -> list[Album]
    async def get_album_tracks(self, session: ServiceSession, album_id: str) -> list[Track]
    async def get_new_releases(self, session: ServiceSession, artist_ids: list[str]) -> list[Album]
    
    # Metadata Enrichment
    async def get_track_metadata(self, session: ServiceSession, track_id: str) -> Track
    async def get_artist_metadata(self, session: ServiceSession, artist_id: str) -> Artist
    async def get_album_metadata(self, session: ServiceSession, album_id: str) -> Album
    
    # Search
    async def search_tracks(self, session: ServiceSession, query: str, limit: int = 20) -> list[Track]
    async def search_artists(self, session: ServiceSession, query: str, limit: int = 20) -> list[Artist]
    async def search_albums(self, session: ServiceSession, query: str, limit: int = 20) -> list[Album]
    
    # Capabilities (optional features)
    def supports_lyrics(self) -> bool
    def supports_high_res_audio(self) -> bool
    def supports_podcasts(self) -> bool
    def max_audio_quality(self) -> str  # "320kbps", "FLAC", "MQA"
```

---

## Appendix B: Database Schema Changes

**New Tables:**
```sql
-- Service sessions (replaces spotify_sessions)
CREATE TABLE service_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) UNIQUE NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    scope TEXT,  -- OAuth scopes granted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CHECK (service_type IN ('spotify', 'tidal', 'deezer'))
);

-- Plugin-specific import cache (optional)
CREATE TABLE plugin_import_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- 'track', 'artist', 'album', 'playlist'
    soulspot_id UUID NOT NULL,  -- Foreign key to tracks/artists/albums/playlists
    service_id VARCHAR(255) NOT NULL,  -- Service's internal ID (spotify:track:xyz)
    last_synced_at TIMESTAMPTZ NOT NULL,
    
    UNIQUE (service_type, entity_type, service_id)
);

-- Circuit breaker state
CREATE TABLE plugin_health (
    service_type VARCHAR(50) PRIMARY KEY,
    is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    failure_count INT NOT NULL DEFAULT 0,
    last_failure_at TIMESTAMPTZ,
    circuit_opened_at TIMESTAMPTZ,
    
    CHECK (service_type IN ('spotify', 'tidal', 'deezer'))
);
```

**Modified Tables:**
```sql
-- Add source tracking to playlist_tracks
ALTER TABLE playlist_tracks 
ADD COLUMN source_service VARCHAR(50),  -- 'spotify', 'tidal', 'deezer', NULL
ADD COLUMN added_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Add service_id to tracks (for re-sync)
ALTER TABLE tracks
ADD COLUMN spotify_id VARCHAR(255),
ADD COLUMN tidal_id VARCHAR(255),
ADD COLUMN deezer_id VARCHAR(255);
```

---

## Appendix C: Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **API Changes** (Spotify/Tidal deprecate endpoints) | Medium | High | Version API clients, monitor changelogs, abstract API calls behind plugin interface |
| **Rate Limiting** (exceed service quotas) | Medium | Medium | Implement per-plugin rate limiter, exponential backoff, cache metadata aggressively |
| **Token Expiry** (refresh fails during sync) | Low | Medium | Graceful degradation (skip service), notify user, manual re-auth UI |
| **Deduplication Errors** (false positives) | Medium | Low | Manual review UI (Phase 2.1), allow user to unlink duplicates |
| **Migration Data Loss** (Big Bang risks) | Low | High | **MANDATORY:** Full DB backup before migration, rollback plan, test on copy of prod DB |
| **Plugin Bugs** (one plugin crashes all) | Medium | Medium | Plugin isolation (try/catch per plugin), circuit breaker, independent worker threads |

**Critical Safeguards:**
1. **Database Backups:** Automated daily backups + pre-migration manual backup
2. **Rollback Plan:** Keep `v1.x` branch deployable, document rollback steps
3. **Canary Testing:** Test migration on non-production instance first

---

## Appendix D: Open Questions (For Phase 2+)

1. **Track Deduplication Algorithm:** Finalize ISRC vs. MusicBrainz vs. Fuzzy matching priority.
2. **Conflict Resolution UI:** If two plugins have different metadata for same track, how does user choose?
3. **Playlist Sync Direction:** Should SoulSpot playlists sync BACK to services? (e.g., export to Spotify)
4. **Podcast Support:** Include podcast episodes in track model or separate entity?
5. **Service Health Dashboard:** Where to display circuit breaker status in UI?

**Action:** Schedule design review session in Phase 2 to finalize these.

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-10 | Initial ADR (all 14 decisions) | GitHub Copilot + User Session |

---

**Approval Signatures:**
- Product Owner: ✅ (verbal approval during TaskSync session)
- Lead Developer: _(pending)_
- QA Lead: _(pending)_

**Next Steps:**
1. Review this ADR with team
2. Create Phase 1 implementation tickets (GitHub Issues)
3. Begin `IPlugin` interface implementation

---

## Appendix E: Hybrid Library Concept

**Decision Date:** 2025-12-10 (Session #2)

### Problem Statement
How should SoulSpot differentiate between:
- **Local tracks** (downloaded files on disk)
- **Remote tracks** (followed artists from Spotify/Tidal, not yet downloaded)
- **Tracked metadata** (user wants this, but not available yet)

### Solution: Hybrid Library Model

**Library = Everything User Cares About** (local + remote)

```
SoulSpot Library
├── Local Tracks (downloaded, playable)
├── Followed Artists (from Spotify/Tidal)
│   ├── Complete (all albums downloaded)
│   ├── Partial (some albums missing)
│   └── Remote (no local files yet)
└── Watchlist (user-marked "want this")
```

### Track Availability States

```python
class TrackAvailability(Enum):
    LOCAL = "local"              # File exists on disk
    QUEUED = "queued"           # In download queue
    AVAILABLE = "available"      # Found on Soulseek (not downloaded)
    NOT_FOUND = "not_found"     # Not found anywhere
    FAILED = "failed"           # Download failed
```

### Artist Completeness Tracking

**Progress Bar (Lidarr-style):**
```
Artist: Pink Floyd
████████░░ 80% Complete (16/20 albums)

Album Breakdown:
✅ The Dark Side of the Moon (100%)
✅ The Wall (100%)
⚠️ Wish You Were Here (50% - 3/6 tracks)
❌ The Division Bell (0% - not downloaded)
```

**Calculation:**
```python
def calculate_artist_completeness(artist_id: UUID) -> float:
    albums = get_artist_albums(artist_id)
    total_tracks = sum(a.track_count for a in albums)
    local_tracks = count_local_tracks(artist_id)
    return (local_tracks / total_tracks) * 100 if total_tracks > 0 else 0
```

### UI Design Patterns

#### Artist Card Color Coding
```
Green (100%):     All tracks local ✅
Yellow (50-99%):  Partially complete ⚠️
Red (0-49%):      Mostly missing ❌
Gray:             No albums (new artist)
```

#### Service Badge
```
[Spotify icon] Artist Name   ← Followed from Spotify
[Tidal icon] Artist Name     ← Followed from Tidal
[Multiple icons]             ← Followed on both
```

#### Quick Actions
```
- "Download Missing" button (visible when <100%)
- Context menu: "Download All", "Monitor New Releases", "Unfollow"
```

### Filter Options

**Library View Filters:**
```
[All] [Local Only] [Remote Only] [Incomplete ⚠️]

Local Only:    Show only artists with 100% local files
Remote Only:   Show only followed artists (0% local)
Incomplete:    Show artists with 1-99% completion
```

### New Release Handling

**Settings:**
```python
class NewReleaseSettings:
    handling_mode: Literal["notify_only", "auto_download", "silent_add"]
    auto_download_followed: bool  # Auto-download followed artists?
    quality_preference: str       # "any", "320kbps+", "flac_only"
```

**Workflow:**
```
Daily Sync → New Album Detected
            ↓
    [Settings Check]
            ↓
    ┌───────┴────────┐
    │                │
Notify User    Auto-Download
    │                │
    └────────────────┘
         ↓
  Add to Library
```

### Database Schema Additions

**Track Download State:**
```sql
CREATE TABLE track_download_state (
    track_id UUID PRIMARY KEY REFERENCES tracks(id),
    availability VARCHAR(50) NOT NULL,  -- 'local', 'queued', 'available', 'not_found', 'failed'
    local_path TEXT,                    -- File path if downloaded
    file_size_bytes BIGINT,
    download_queued_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ NOT NULL,
    
    CHECK (availability IN ('local', 'queued', 'available', 'not_found', 'failed'))
);

-- Index for filtering
CREATE INDEX idx_track_download_availability ON track_download_state(availability);
```

**Artist Completeness Cache:**
```sql
CREATE TABLE artist_completeness (
    artist_id UUID PRIMARY KEY REFERENCES artists(id),
    total_albums INT NOT NULL,
    local_albums INT NOT NULL,
    total_tracks INT NOT NULL,
    local_tracks INT NOT NULL,
    completeness_percent DECIMAL(5,2) NOT NULL,  -- 0.00 to 100.00
    last_calculated_at TIMESTAMPTZ NOT NULL,
    
    CHECK (completeness_percent BETWEEN 0 AND 100)
);

-- Auto-update trigger (recalculate on track download)
CREATE FUNCTION update_artist_completeness() RETURNS TRIGGER AS $$
BEGIN
    -- Recalculate completeness for artist
    UPDATE artist_completeness SET
        local_tracks = (SELECT COUNT(*) FROM tracks t 
                       JOIN track_download_state tds ON t.id = tds.track_id
                       WHERE t.artist_id = NEW.artist_id AND tds.availability = 'local'),
        completeness_percent = (local_tracks::decimal / NULLIF(total_tracks, 0)) * 100,
        last_calculated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Followed Artists (Multi-Service):**
```sql
CREATE TABLE followed_artists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id UUID NOT NULL REFERENCES artists(id),
    service_type VARCHAR(50) NOT NULL,           -- 'spotify', 'tidal', 'deezer'
    service_artist_id VARCHAR(255) NOT NULL,     -- Service's internal ID
    followed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    auto_download_enabled BOOLEAN DEFAULT FALSE,
    monitor_new_releases BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMPTZ,
    
    UNIQUE (artist_id, service_type)
);

-- Index for filtering by service
CREATE INDEX idx_followed_artists_service ON followed_artists(service_type);
```

### Implementation Priority

**Phase 1 (Foundation):**
- ✅ `track_download_state` table
- ✅ `artist_completeness` cache
- ✅ Basic UI color coding (green/yellow/red)

**Phase 2 (Auto-Download):**
- ✅ Settings: Auto-download followed artists
- ✅ New release detection + notification
- ✅ "Download Missing" quick action

**Phase 3 (Advanced):**
- ✅ Filter options (All/Local/Remote/Incomplete)
- ✅ Bulk actions (Download All, Monitor All)
- ✅ Service-specific badges

### Success Metrics

- **Completeness Accuracy:** Progress bars reflect actual local files (99%+ accuracy)
- **Performance:** Artist completeness calculation <50ms (cached, updated incrementally)
- **UX Clarity:** User understands availability at a glance (A/B test color coding)
