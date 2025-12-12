# SoulSpot Documentation & Backend Modernization - Action Plan

**Version:** 1.0  
**Created:** 9. Dezember 2025  
**Owner:** Entwicklerteam  
**Timeline:** 5 Wochen (9. Dezember 2025 - 13. Januar 2026)

---

## Quick Start Summary

**✅ COMPLETED TODAY:**
1. Created `MODERNIZATION_PLAN.md` - Master plan for documentation cleanup + backend optimization
2. Created `DOCS_STATUS.md` - Comprehensive audit of all documentation vs. actual codebase
3. Marked **2 API docs as DEPRECATED:**
   - `docs/api/spotify-album-api.md` → No albums.py router exists
   - `docs/api/spotify-songs-roadmap.md` → Roadmap outdated, artist_songs.py implemented

**📊 KEY FINDINGS:**
- **200+ API endpoints** across 18 routers
- **57% API documentation coverage** (113/200+ endpoints documented)
- **63 undocumented endpoints** across 9 routers (settings.py, metadata.py, onboarding.py, etc.)
- **14 outdated docs** in feat-ui/ already marked DEPRECATED
- **7 missing repository interfaces** needed for clean architecture
- **SessionModel needs renaming** to SpotifySessionModel for service-agnostic design

---

## Week 1: Documentation Audit & Critical Deprecation

**Duration:** 9. - 13. Dezember 2025  
**Goal:** Mark all outdated docs, create missing critical API docs

### Tasks

- [x] **Day 1: Generate Inventories** ✅ COMPLETED
  - [x] Code inventory (200+ endpoints, 50+ services, 28 models)
  - [x] Doc inventory (48 files)
  - [x] Cross-reference analysis (DOCS_STATUS.md)

- [ ] **Day 2-3: Mark Deprecated Docs**
  - [x] `spotify-album-api.md` → DEPRECATED ✅
  - [x] `spotify-songs-roadmap.md` → DEPRECATED ✅
  - [ ] `features/spotify-playlist-roadmap.md` → DEPRECATED (if playlist-management.md covers same content)
  - [ ] `features/deezer-integration.md` → Mark as **PLANNED** (future feature)
  - [ ] Merge 3 onboarding docs (`onboarding-ui-implementation.md`, `onboarding-ui-overview.md`, `onboarding-ui-visual-guide.md`) into `onboarding-complete-guide.md`

- [ ] **Day 4-5: Create Missing Critical API Docs** ✅ COMPLETED
  - [x] `docs/api/settings-api.md` (24 endpoints) - ✅ EXISTS
  - [x] `docs/api/artist-songs-api.md` (5 endpoints) - ✅ EXISTS
  - [x] `docs/api/metadata-api.md` (6 endpoints) - ✅ EXISTS
  - [x] `docs/api/onboarding-api.md` (5 endpoints) - ✅ EXISTS
  - [x] `docs/api/compilations-api.md` (7 endpoints) - ✅ EXISTS

### Template für neue API Docs

```markdown
# [Feature] API Reference

> **Version:** 2.0  
> **Last Updated:** YYYY-MM-DD  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/[router].py`

---

## Endpoints

### [HTTP METHOD] `/api/[path]`

**Purpose:** [What does this endpoint do?]

**Request:**
```json
{
  "param": "value"
}
```

**Response:**
```json
{
  "result": "data"
}
```

**Errors:**
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

**Code Example:**
```python
# src/soulspot/api/routers/[router].py (lines X-Y)
@router.post("/[path]")
async def endpoint_name(...):
    ...
```
```

### Deliverables Week 1

- [ ] **DOCS_STATUS.md** (✅ Done)
- [ ] **MODERNIZATION_PLAN.md** (✅ Done)
- [ ] **5 new API docs** (settings, artist-songs, metadata, onboarding, compilations)
- [ ] **4 deprecated docs marked** (spotify-album, spotify-songs, spotify-playlist-roadmap, deezer)
- [ ] **1 merged implementation guide** (onboarding-complete-guide.md)

---

## Week 2: Backend Interface Standardization

**Duration:** 16. - 20. Dezember 2025  
**Goal:** Add missing repository + client interfaces for clean architecture

### Tasks

- [ ] **Day 1: Add Missing Repository Interfaces**

Create in `src/soulspot/domain/ports/`:

```python
# domain/ports/automation.py
class IArtistWatchlistRepository(Protocol):
    async def create(self, watchlist: ArtistWatchlist) -> ArtistWatchlist: ...
    async def get(self, watchlist_id: str) -> ArtistWatchlist | None: ...
    async def list_all(self) -> list[ArtistWatchlist]: ...
    async def delete(self, watchlist_id: str) -> None: ...

class IFilterRuleRepository(Protocol): ...
class IAutomationRuleRepository(Protocol): ...
class IQualityUpgradeCandidateRepository(Protocol): ...

# domain/ports/session.py
class ISessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...
    async def get(self, session_id: str) -> Session | None: ...
    async def get_by_user_id(self, user_id: str) -> Session | None: ...
    async def update(self, session: Session) -> None: ...
    async def delete(self, session_id: str) -> None: ...

# domain/ports/spotify.py
class ISpotifyBrowseRepository(Protocol): ...
class ISpotifyTokenRepository(Protocol): ...
```

- [ ] **Day 2-3: Add Client Interfaces**

Create in `src/soulspot/domain/ports/`:

```python
# domain/ports/track_client.py
class ITrackClient(Protocol):
    """Service-agnostic track client interface."""
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]: ...
    async def get_track(self, track_id: str) -> Track: ...
    async def get_track_by_isrc(self, isrc: str) -> Track | None: ...

# domain/ports/playlist_client.py
class IPlaylistClient(Protocol):
    async def get_playlists(self, user_id: str) -> list[Playlist]: ...
    async def get_playlist_tracks(self, playlist_id: str) -> list[Track]: ...

# domain/ports/artist_client.py
class IArtistClient(Protocol):
    async def get_artist(self, artist_id: str) -> Artist: ...
    async def get_artist_albums(self, artist_id: str) -> list[Album]: ...

# domain/ports/auth_client.py
class IAuthClient(Protocol):
    async def authorize(self, redirect_uri: str) -> str: ...
    async def get_access_token(self, code: str) -> Token: ...
    async def refresh_token(self, refresh_token: str) -> Token: ...
```

- [ ] **Day 4: Update Repositories to Implement Interfaces**

Modify in `src/soulspot/infrastructure/persistence/repositories.py`:

```python
from soulspot.domain.ports import (
    IArtistWatchlistRepository,
    IFilterRuleRepository,
    IAutomationRuleRepository,
    IQualityUpgradeCandidateRepository,
    ISessionRepository,
    ISpotifyBrowseRepository,
    ISpotifyTokenRepository,
)

class ArtistWatchlistRepository(IArtistWatchlistRepository):
    # Existing implementation already matches interface
    ...
```

- [ ] **Day 5: Update SpotifyClient to Implement Interfaces**

Modify `src/soulspot/infrastructure/clients/spotify_client.py`:

```python
from soulspot.domain.ports import ITrackClient, IPlaylistClient, IArtistClient, IAuthClient

class SpotifyClient(ITrackClient, IPlaylistClient, IArtistClient, IAuthClient):
    # Existing implementation already matches most methods
    # Add missing methods if needed
    ...
```

### Deliverables Week 2

- [ ] **7 new repository interfaces** in `domain/ports/`
- [ ] **4 new client interfaces** in `domain/ports/`
- [ ] **All repositories updated** to implement interfaces
- [ ] **SpotifyClient updated** to implement ITrackClient, IPlaylistClient, IArtistClient, IAuthClient
- [ ] **Type checking passes** (`mypy --strict`)

---

## Week 3: Database Model Renaming

**Duration:** 23. - 27. Dezember 2025  
**Goal:** Rename SessionModel → SpotifySessionModel for service-agnostic architecture

### Tasks

- [ ] **Day 1: Create Alembic Migration**

```bash
cd /path/to/soulspot
alembic revision -m "rename_session_to_spotify_session"
```

Edit migration file:

```python
# alembic/versions/XXXXXX_rename_session_to_spotify_session.py
def upgrade():
    op.rename_table('sessions', 'spotify_sessions')

def downgrade():
    op.rename_table('spotify_sessions', 'sessions')
```

- [ ] **Day 2: Update Model Definition**

Modify `src/soulspot/infrastructure/persistence/models.py`:

```python
# BEFORE
class SessionModel(Base):
    __tablename__ = "sessions"
    ...

# AFTER
class SpotifySessionModel(Base):
    __tablename__ = "spotify_sessions"
    ...
```

- [ ] **Day 3: Update All Repository References**

Search and replace in codebase:

```bash
grep -r "SessionModel" src/ | wc -l  # Find all references
# Replace SessionModel → SpotifySessionModel
# Replace sessions → spotify_sessions (table name)
```

- [ ] **Day 4: Test Migration**

```bash
# Backup database first!
alembic upgrade head
# Verify data integrity
# Test all auth flows

# Test rollback
alembic downgrade -1
# Verify rollback works

# Re-apply migration
alembic upgrade head
```

- [ ] **Day 5: Update Documentation**

Update docs to reflect new model name:
- [ ] `docs/api/spotify-sync-api.md`
- [ ] `docs/features/authentication.md`
- [ ] Database schema diagram (if exists)

### Deliverables Week 3

- [ ] **Alembic migration created and tested**
- [ ] **SessionModel → SpotifySessionModel** in code
- [ ] **All references updated**
- [ ] **Migration rollback tested**
- [ ] **Documentation updated**

---

## Week 4: ISRC-Based Track Matching

**Duration:** 30. Dezember 2025 - 3. Januar 2026  
**Goal:** Implement service-agnostic track matching via ISRC

### Tasks

- [ ] **Day 1: Add ISRC Field to Track Entity**

Check if Track already has ISRC field:

```bash
grep -r "isrc" src/soulspot/domain/entities/track.py
grep -r "isrc" src/soulspot/infrastructure/persistence/models.py
```

If missing, add to TrackModel:

```python
class TrackModel(Base):
    __tablename__ = "tracks"
    ...
    isrc = Column(String, unique=True, nullable=True, index=True)  # International Standard Recording Code
```

Create migration:

```bash
alembic revision --autogenerate -m "add_isrc_to_tracks"
```

- [ ] **Day 2: Create Mapping Tables**

Create `src/soulspot/infrastructure/persistence/models.py`:

```python
class SpotifyTrackMapping(Base):
    """Maps Spotify Track IDs to generic Track entities."""
    __tablename__ = "spotify_track_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    track_id = Column(UUID(as_uuid=True), ForeignKey("tracks.id"), nullable=False, index=True)
    spotify_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    track = relationship("TrackModel", back_populates="spotify_mappings")

# For future Tidal integration
class TidalTrackMapping(Base):
    __tablename__ = "tidal_track_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    track_id = Column(UUID(as_uuid=True), ForeignKey("tracks.id"), nullable=False, index=True)
    tidal_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

Create migration:

```bash
alembic revision --autogenerate -m "add_service_track_mapping_tables"
```

- [ ] **Day 3: Implement get_or_create_track() Service**

Create in `src/soulspot/application/services/track_service.py`:

```python
from soulspot.domain.ports import ITrackRepository, ISpotifyTrackMappingRepository

class TrackService:
    def __init__(
        self,
        track_repo: ITrackRepository,
        spotify_mapping_repo: ISpotifyTrackMappingRepository,
    ):
        self.track_repo = track_repo
        self.spotify_mapping_repo = spotify_mapping_repo
    
    async def get_or_create_track(
        self,
        isrc: str | None,
        service_id: str,
        service: str,  # "spotify" | "tidal" | "deezer"
        track_data: dict,
    ) -> Track:
        """
        Find existing track by ISRC, or create new one.
        Links service-specific ID to generic Track entity.
        
        Prevents duplicates when same track imported from multiple services.
        """
        # 1. Try to find existing track by ISRC
        if isrc:
            track = await self.track_repo.get_by_isrc(isrc)
            if track:
                # Track exists - link service-specific ID
                await self._link_service_id(track.id, service_id, service)
                return track
        
        # 2. No existing track - create new one
        track = Track(
            id=uuid4(),
            isrc=isrc,
            title=track_data["title"],
            duration_ms=track_data["duration_ms"],
            # ... other fields
        )
        await self.track_repo.save(track)
        
        # 3. Link service-specific ID
        await self._link_service_id(track.id, service_id, service)
        
        return track
    
    async def _link_service_id(self, track_id: UUID, service_id: str, service: str):
        """Create mapping between generic Track and service-specific ID."""
        if service == "spotify":
            await self.spotify_mapping_repo.save(SpotifyTrackMapping(
                track_id=track_id,
                spotify_id=service_id
            ))
        # Future: elif service == "tidal": ...
```

- [ ] **Day 4: Backfill ISRC for Existing Tracks**

Create backfill script `scripts/backfill_isrc.py`:

```python
"""
Backfill ISRC codes for existing tracks via MusicBrainz or Spotify.
"""

async def backfill_isrc():
    tracks_without_isrc = await track_repo.find_missing_isrc()
    
    for track in tracks_without_isrc:
        # 1. Try Spotify first (if SpotifyTrackMapping exists)
        spotify_mapping = await spotify_mapping_repo.get_by_track_id(track.id)
        if spotify_mapping:
            spotify_track = await spotify_client.get_track(spotify_mapping.spotify_id)
            if spotify_track.get("external_ids", {}).get("isrc"):
                track.isrc = spotify_track["external_ids"]["isrc"]
                await track_repo.update(track)
                continue
        
        # 2. Fallback to MusicBrainz
        mb_result = await musicbrainz_client.search_recording(
            artist=track.artist_name,
            track=track.title,
        )
        if mb_result and mb_result.get("isrc"):
            track.isrc = mb_result["isrc"]
            await track_repo.update(track)
```

Run backfill:

```bash
python scripts/backfill_isrc.py
```

- [ ] **Day 5: Update Documentation**

Create `docs/BACKEND_OPTIMIZATION.md`:

```markdown
# Backend Optimization - Service-Agnostic Architecture

## ISRC-Based Track Matching

### Problem
When importing the same track from Spotify AND Tidal, SoulSpot creates 2 duplicate Track entities.

### Solution
Use ISRC (International Standard Recording Code) as universal identifier.

### Implementation
- Track.isrc field (unique index)
- Service-specific mapping tables (spotify_track_mappings, tidal_track_mappings)
- TrackService.get_or_create_track() method

### Example
```python
# User imports track from Spotify
spotify_track = await spotify_client.get_track("spotify:track:123")
track = await track_service.get_or_create_track(
    isrc="USRC17607839",
    service_id="spotify:track:123",
    service="spotify",
    track_data=spotify_track,
)

# Later, user imports SAME track from Tidal
tidal_track = await tidal_client.get_track("tidal:track:456")
track = await track_service.get_or_create_track(
    isrc="USRC17607839",  # Same ISRC!
    service_id="tidal:track:456",
    service="tidal",
    track_data=tidal_track,
)

# Result: Only ONE Track entity, linked to BOTH services
```
```

### Deliverables Week 4

- [ ] **ISRC field added** to Track model
- [ ] **Mapping tables created** (spotify_track_mappings, tidal_track_mappings)
- [ ] **TrackService.get_or_create_track()** implemented
- [ ] **ISRC backfill completed** for existing tracks
- [ ] **BACKEND_OPTIMIZATION.md** documentation created

---

## Week 5: Documentation Update & Final Review

**Duration:** 6. - 10. Januar 2026  
**Goal:** Update all outdated docs, archive deprecated docs, create v2.0 index

### Tasks

- [ ] **Day 1-2: Update API Docs Marked as UPDATE NEEDED**
  - [ ] `spotify-sync-api.md` - Add 4 missing endpoints
  - [ ] `spotify-artist-api.md` - Add Followed Artists section
  - [ ] `advanced-search-api.md` - Verify 5 endpoints
  - [ ] `spotify-tracks.md` - Verify 5 endpoints
  - [ ] `spotify-metadata-reference.md` - Verify against metadata.py

- [ ] **Day 3: Update Feature Docs**
  - [ ] `authentication.md` - Add Session Management, Onboarding sections
  - [ ] `track-management.md` - Verify coverage
  - [ ] `settings.md` - Likely incomplete, needs review
  - [ ] `artists-roadmap.md` - Rename to `artists-management.md` if implemented
  - [ ] `spotify-albums-roadmap.md` - Clarify status

- [ ] **Day 4: Create Missing Feature Docs**
  - [ ] `album-completeness.md`
  - [ ] `auto-import.md`
  - [ ] `batch-operations.md`
  - [ ] `compilation-detection.md`
  - [ ] `notifications.md`

- [ ] **Day 5: Archive & Index**
  - [ ] Move deprecated docs to `docs/archive/v1.0/`
  - [ ] Update `docs/README.md` with v2.0 index
  - [ ] Update `docs/api/README.md` to reflect new API docs
  - [ ] Update `docs/features/README.md` to reflect new feature docs
  - [ ] Create `CHANGELOG.md` entry for v2.0 documentation update

### Deliverables Week 5

- [ ] **All UPDATE NEEDED docs updated**
- [ ] **5 new feature docs created**
- [ ] **Deprecated docs archived** to `docs/archive/v1.0/`
- [ ] **docs/README.md** updated to v2.0
- [ ] **CHANGELOG.md** entry created

---

## Post-Completion Checklist

### Documentation Quality Gates

- [ ] All routers have dedicated API documentation
- [ ] All services have feature documentation
- [ ] No DEPRECATED docs in active directories (all archived)
- [ ] README.md indexes updated to v2.0
- [ ] Code examples in docs match actual code
- [ ] All links between docs work

### Backend Architecture Quality Gates

- [ ] All repositories have interfaces defined in `domain/ports/`
- [ ] SpotifyClient implements ITrackClient, IPlaylistClient, IArtistClient, IAuthClient
- [ ] SessionModel renamed to SpotifySessionModel
- [ ] ISRC field added to Track model
- [ ] Service-specific mapping tables created
- [ ] TrackService.get_or_create_track() implemented
- [ ] Type checking passes (`mypy --strict`)
- [ ] All tests pass (`pytest tests/ -q`)

### Review Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| API Documentation Coverage | 57% (113/200) | TBD | 95%+ (190/200) |
| Feature Documentation Coverage | 72% (13/18) | TBD | 100% (18/18) |
| Repository Interfaces | 42% (5/12) | TBD | 100% (12/12) |
| Service-Agnostic Models | 71% (20/28) | TBD | 100% (28/28) |
| Deprecated Docs Archived | 29% (14/48) | TBD | 100% (all moved) |

---

## Maintenance Plan (Post-v2.0)

### Weekly Documentation Review

**Every Monday:**
- [ ] Check for new routers added (grep for `@router.` in new PRs)
- [ ] Check for new services added (grep for `class.*Service` in new PRs)
- [ ] Update API docs if endpoints changed
- [ ] Update feature docs if services changed

### Quarterly Architecture Review

**Every 3 months:**
- [ ] Review `domain/ports/` for missing interfaces
- [ ] Review models for service-agnostic compliance
- [ ] Review ISRC coverage (should be 90%+ of tracks)
- [ ] Plan next backend optimization phase

### Pre-Commit Hooks (Future)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Check if any API route changed
if git diff --cached --name-only | grep -q "src/soulspot/api/routers/"; then
  echo "⚠️  API routes changed. Please update docs/api/ accordingly."
  echo "Run: python scripts/generate_api_docs.py"
  # Uncomment to enforce:
  # exit 1
fi
```

---

## Resources & References

### Key Documents

- **Master Plan:** `docs/MODERNIZATION_PLAN.md` (comprehensive 5-week roadmap)
- **Status Report:** `docs/DOCS_STATUS.md` (current state analysis)
- **This File:** `docs/ACTION_PLAN.md` (week-by-week tasks)

### Architecture Patterns

- **Service-Agnostic Strategy:** `docs/feat-ui/SERVICE_AGNOSTIC_STRATEGY.md`
- **Hexagonal Architecture:** `docs/project/architecture.md` (if exists)
- **ISRC Matching:** See Week 4 implementation

### Codebase References

- **API Routers:** `src/soulspot/api/routers/*.py` (18 routers, 200+ endpoints)
- **Application Services:** `src/soulspot/application/services/*.py` (50+ services)
- **Domain Ports:** `src/soulspot/domain/ports/*.py` (interfaces)
- **Infrastructure:** `src/soulspot/infrastructure/` (repositories, clients)

---

## Contact & Support

**Questions?**
- Review `MODERNIZATION_PLAN.md` for detailed technical explanations
- Check `DOCS_STATUS.md` for specific file-by-file analysis
- Consult `copilot-instructions.md` for coding patterns

**Weekly Sync Meetings:**
- Mondays @ 10:00 - Review progress, unblock issues
- Fridays @ 15:00 - Week wrap-up, plan next week

**Review Cadence:**
- Weekly sync meetings to track progress
- Next review: Week of 16. Dezember 2025

---

**Good luck! 🚀**
