# SoulSpot Documentation & Backend Modernization Plan

**Version:** 2.0  
**Created:** 9. Dezember 2025  
**Status:** 🎯 Active Planning Phase  
**Owner:** Architecture Team

---

## Executive Summary

This document coordinates the complete modernization of SoulSpot's documentation and backend architecture. It encompasses:

1. **Documentation Audit & Cleanup** - Identify outdated/duplicate docs → Mark as DEPRECATED
2. **Backend Architecture Optimization** - Service-agnostic design for Tidal/Deezer integration
3. **Code-Documentation Sync** - Ensure docs reflect actual implementation
4. **Future-Proofing Strategy** - Extensibility patterns for new music services

**Goal:** Production-ready v2.0 documentation + extensible backend architecture ready for multi-service support.

---

## Phase 1: Documentation Audit & Cleanup

### 1.1 Current Status

#### ✅ Already DEPRECATED (docs/feat-ui/)
- README.md (v1.0) → Rewritten as v2.0 index
- ROADMAP.md → feat-ui-pro.md
- IMPLEMENTATION_GUIDE.md → feat-ui-pro.md
- INTEGRATION_GUIDE.md → feat-ui-pro.md
- TECHNICAL_SPEC.md → feat-ui-pro.md
- NAVIGATION.md → src/soulspot/api/routers/
- VISUAL_OVERVIEW.md → src/soulspot/static/css/variables.css
- BACKEND_ALIGNMENT.md → SERVICE_AGNOSTIC_STRATEGY.md
- MAGIC_UI_INTEGRATION.md (Tailwind doesn't exist)
- DASHBOARD_MAGIC_UI_PLAN.md (Tailwind doesn't exist)
- frontend-agent.md (Tailwind doesn't exist)
- DESIGN_SYSTEM.md (wrong colors: red → violet)
- COMPONENT_LIBRARY.md (theoretical vs actual templates)
- FRONTEND_COMPLETE.md (prototype/ never integrated)
- MEDIAMANAGER_ANALYSIS.md (external reference)

#### ⏳ Needs Review (docs/api/)
- ❓ **spotify-sync-api.md** - Check if matches `api/routers/auth.py` + `application/services/spotify_sync_service.py`
- ❓ **advanced-search-api.md** - Check if matches `api/routers/search.py` + `application/services/advanced_search.py`
- ❓ **library-management-api.md** - Check if matches `api/routers/library.py`
- ❓ **download-management.md** - Check if matches `api/routers/downloads.py`
- ❓ **spotify-metadata-reference.md** - Check if still accurate
- ❓ **spotify-playlist-api.md** - Check if matches `api/routers/playlists.py`
- ❓ **spotify-artist-api.md** - Check if matches `api/routers/artists.py`
- ❓ **spotify-album-api.md** - Check if matches (no dedicated router found)
- ❓ **spotify-tracks.md** - Check if matches `api/routers/tracks.py`
- ❓ **spotify-songs-roadmap.md** - Check if still roadmap or implemented

#### ⏳ Needs Review (docs/features/)
- ❓ **spotify-sync.md** - Updated 2025-11-28, likely accurate
- ❓ **playlist-management.md** - Check implementation status
- ❓ **download-management.md** - Check implementation status
- ❓ **metadata-enrichment.md** - Check implementation status
- ❓ **automation-watchlists.md** - Check implementation status
- ❓ **followed-artists.md** - Check implementation status
- ❓ **artists-roadmap.md** - Roadmap status needs verification
- ❓ **spotify-albums-roadmap.md** - Roadmap status needs verification
- ❓ **library-management.md** - Check implementation status
- ❓ **authentication.md** - Check implementation status
- ❓ **track-management.md** - Check implementation status
- ❓ **settings.md** - Check implementation status
- ❓ **deezer-integration.md** - Future feature, mark as PLANNED
- ❓ **spotify-playlist-roadmap.md** - Check if still roadmap
- ❓ **local-library-enrichment.md** - Check implementation status

#### ⏳ Needs Review (docs/implementation/)
- ❓ **dashboard-implementation.md** - Check if matches actual UI
- ❓ **onboarding-ui-implementation.md** - Check if matches actual onboarding
- ❓ **onboarding-ui-overview.md** - Duplicate of above?
- ❓ **onboarding-ui-visual-guide.md** - Duplicate of above?

#### ⏳ Needs Review (docs/ root level)
- ❓ **TODO.md** - Check if still accurate or abandoned

#### 📁 Needs Investigation
- docs/archive/ - What's in here?
- docs/archived/ - Duplicate of archive/?
- docs/development/ - What's in here?
- docs/examples/ - Are these still valid?
- docs/guides/ - user/ and developer/ guides - check accuracy
- docs/history/ - Historical records, probably keep as-is
- docs/project/ - Project-level docs, check accuracy
- docs/version-3.0/ - Future version planning?
- docs/feat-library/ - What's this?

### 1.2 Audit Strategy

**Step 1: Code-First Analysis**
```bash
# Generate actual API endpoint inventory
grep -r "@router\." src/soulspot/api/routers/*.py > /tmp/actual_endpoints.txt

# Generate actual Service class inventory
grep -r "^class.*Service:" src/soulspot/application/services/*.py > /tmp/actual_services.txt

# Generate actual Repository inventory
grep -r "^class.*Repository:" src/soulspot/infrastructure/persistence/*.py > /tmp/actual_repos.txt

# Generate actual Model inventory
grep -r "^class.*Model.*Base" src/soulspot/infrastructure/persistence/models.py > /tmp/actual_models.txt
```

**Step 2: Documentation Inventory**
```bash
# List all API docs
find docs/api -name "*.md" > /tmp/api_docs.txt

# List all feature docs
find docs/features -name "*.md" > /tmp/feature_docs.txt

# List all implementation docs
find docs/implementation -name "*.md" > /tmp/impl_docs.txt
```

**Step 3: Cross-Reference Analysis**
For each doc in `docs/api/`, `docs/features/`, `docs/implementation/`:
1. Extract mentioned endpoints/classes
2. Verify existence in actual code
3. Mark mismatches as DEPRECATED or UPDATE NEEDED

### 1.3 Deprecation Criteria

Mark as **DEPRECATED** if:
- ✅ **Wrong Technology:** References non-existent tech stack (Tailwind, npm)
- ✅ **Outdated Design:** Wrong colors/tokens (red #fe4155 vs violet #8b5cf6)
- ✅ **Theoretical:** Describes planned features never implemented
- ✅ **Duplicate:** Same content exists in better-maintained doc
- ✅ **Superseded:** Newer doc with same scope exists
- ✅ **Abandoned:** Refers to abandoned prototype (`docs/feat-ui/prototype/`)

Mark as **UPDATE NEEDED** if:
- ⚠️ **Partially Accurate:** Some endpoints exist, others don't
- ⚠️ **Incomplete:** Missing recently added features
- ⚠️ **Stale:** Last updated >6 months ago

Keep as-is if:
- ✅ **Accurate:** Matches actual code
- ✅ **Recently Updated:** Within 3 months
- ✅ **Historical:** Intentional archival docs in `docs/history/`

---

## Phase 2: Backend Architecture Optimization

### 2.1 Current Architecture Analysis

**Actual Backend Components (verified from code):**

#### API Routers (src/soulspot/api/routers/)
```python
# Spotify-Specific (18 routers)
- auth.py               # Spotify OAuth + Session Management
- artists.py            # Spotify Artist CRUD + Sync
- artist_songs.py       # Artist's discography management
- playlists.py          # Spotify Playlist import/sync
- tracks.py             # Track search/download/metadata
- search.py             # Spotify search (artists/tracks/albums)
- album.py              # (needs verification)
- automation.py         # Watchlists + Automation Rules
- onboarding.py         # First-run setup wizard
- compilations.py       # Compilation album detection
- downloads.py          # Download queue management
- stats.py              # Usage statistics
- artwork.py            # Album artwork serving
```

#### Application Services (src/soulspot/application/services/)
```python
# Core Services (20+ services)
- advanced_search.py          # SearchFilters, SearchResult, AdvancedSearchService
- album_completeness.py       # AlbumCompletenessInfo, AlbumCompletenessService
- app_settings_service.py     # AppSettingsService (class-level cache)
- artist_songs_service.py     # ArtistSongsService
- auto_import.py              # AutoImportService
- automation_workflow_service.py  # AutomationWorkflowService
- batch_processor.py          # BatchResult[R], BatchProcessor[T,R], SpotifyBatchProcessor
- compilation_analyzer_service.py # AlbumAnalysisResult, CompilationAnalyzerService
- discography_service.py      # DiscographyInfo, DiscographyService
- filter_service.py           # FilterService
- followed_artists_service.py # FollowedArtistsService
- library_scanner.py          # FileInfo, LibraryScannerService
- library_scanner_service.py  # LibraryScannerService (duplicate?)
- local_library_enrichment_service.py # EnrichmentResult, EnrichmentCandidate, LocalLibraryEnrichmentService
- metadata_merger.py          # MetadataMerger
- notification_service.py     # NotificationService
- quality_upgrade_service.py  # QualityUpgradeService
- spotify_sync_service.py     # SpotifySyncService
```

#### Infrastructure Repositories (src/soulspot/infrastructure/persistence/)
```python
# Domain Repositories (10 repositories)
- ArtistRepository           # Implements IArtistRepository
- AlbumRepository            # Implements IAlbumRepository
- TrackRepository            # Implements ITrackRepository
- PlaylistRepository         # Implements IPlaylistRepository
- DownloadRepository         # Implements IDownloadRepository
- ArtistWatchlistRepository  # No interface (needs adding)
- FilterRuleRepository       # No interface (needs adding)
- AutomationRuleRepository   # No interface (needs adding)
- QualityUpgradeCandidateRepository  # No interface (needs adding)
- SessionRepository          # No interface (needs adding)
- SpotifyBrowseRepository    # Spotify-specific (needs renaming)
- SpotifyTokenRepository     # Spotify-specific (needs renaming)
```

#### Database Models (src/soulspot/infrastructure/persistence/models.py)
```python
# Generic Domain Models (6 models)
- ArtistModel              # ✅ Generic
- AlbumModel               # ✅ Generic
- TrackModel               # ✅ Generic (has disambiguation fields)
- PlaylistModel            # ✅ Generic
- PlaylistTrackModel       # ✅ Generic (junction table)
- DownloadModel            # ✅ Generic

# Library Management (3 models)
- LibraryScanModel         # ✅ Generic
- FileDuplicateModel       # ✅ Generic
- OrphanedFileModel        # ✅ Generic

# Automation (4 models)
- ArtistWatchlistModel     # ✅ Generic (service-agnostic)
- FilterRuleModel          # ✅ Generic
- AutomationRuleModel      # ✅ Generic
- QualityUpgradeCandidateModel  # ✅ Generic

# Spotify-Specific Models (8 models) ⚠️ NEEDS RENAMING
- SessionModel             # ❌ Should be SpotifySessionModel
- SpotifyArtistModel       # ✅ Correct naming
- SpotifyAlbumModel        # ✅ Correct naming
- SpotifyTrackModel        # ✅ Correct naming
- SpotifySyncStatusModel   # ✅ Correct naming
- SpotifyTokenModel        # ✅ Correct naming
- DuplicateCandidateModel  # ❌ Should be SpotifyDuplicateCandidateModel (or generic?)
- EnrichmentCandidateModel # ✅ Generic (no service-specific fields)

# App Settings (1 model)
- AppSettingsModel         # ✅ Generic
```

### 2.2 Service-Agnostic Refactoring Plan

**Problem:** Current architecture is 80% generic, but has Spotify-specific assumptions in:
1. SessionModel (should be SpotifySessionModel)
2. Client interfaces (no ITrackClient abstraction exists)
3. Some service names (SpotifySyncService vs generic SyncService)

**Solution:** Implement SERVICE_AGNOSTIC_STRATEGY.md patterns:

#### Step 1: Rename Spotify-Specific Models
```python
# Migration: alembic revision --autogenerate -m "rename_spotify_session_model"

# BEFORE (models.py)
class SessionModel(Base):
    __tablename__ = "sessions"
    
# AFTER (models.py)
class SpotifySessionModel(Base):
    __tablename__ = "spotify_sessions"
```

#### Step 2: Add Domain Port Interfaces
```python
# NEW FILE: src/soulspot/domain/ports/track_client.py
from typing import Protocol

class ITrackClient(Protocol):
    """Service-agnostic track client interface."""
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]: ...
    async def get_track(self, track_id: str) -> Track: ...
    async def get_track_by_isrc(self, isrc: str) -> Track | None: ...

# NEW FILE: src/soulspot/domain/ports/playlist_client.py
class IPlaylistClient(Protocol):
    async def get_playlists(self, user_id: str) -> list[Playlist]: ...
    async def get_playlist_tracks(self, playlist_id: str) -> list[Track]: ...
```

#### Step 3: Implement Service-Specific Clients
```python
# src/soulspot/infrastructure/clients/spotify_client.py
from soulspot.domain.ports.track_client import ITrackClient

class SpotifyClient(ITrackClient):
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        # Spotify-specific API call
        ...

# FUTURE: src/soulspot/infrastructure/clients/tidal_client.py
class TidalClient(ITrackClient):
    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        # Tidal-specific API call (same interface!)
        ...
```

#### Step 4: Add ISRC-Based Track Matching
```python
# src/soulspot/application/services/track_service.py
async def get_or_create_track(
    isrc: str, 
    service_id: str, 
    service: str  # "spotify" | "tidal" | "deezer"
) -> Track:
    """
    Find existing track by ISRC, or create new one.
    Links service-specific ID to generic Track entity.
    
    Prevents duplicates when same track imported from multiple services.
    """
    track = await track_repo.get_by_isrc(isrc)
    
    if not track:
        track = Track(id=uuid4(), isrc=isrc, ...)
        await track_repo.save(track)
    
    # Link service-specific ID (mapping table)
    if service == "spotify":
        await spotify_mapping_repo.save(SpotifyTrackMapping(
            track_id=track.id,
            spotify_id=service_id
        ))
    
    return track
```

### 2.3 Repository Interface Sync

**Problem:** Some repositories have interfaces, others don't.

**Current State:**
```python
# ✅ HAVE INTERFACES
- ArtistRepository → IArtistRepository
- AlbumRepository → IAlbumRepository
- TrackRepository → ITrackRepository
- PlaylistRepository → IPlaylistRepository
- DownloadRepository → IDownloadRepository

# ❌ MISSING INTERFACES
- ArtistWatchlistRepository (no interface)
- FilterRuleRepository (no interface)
- AutomationRuleRepository (no interface)
- QualityUpgradeCandidateRepository (no interface)
- SessionRepository (no interface)
- SpotifyBrowseRepository (no interface)
- SpotifyTokenRepository (no interface)
```

**Solution:** Add missing interfaces to `domain/ports/__init__.py`

```python
# NEW: src/soulspot/domain/ports/automation.py
class IArtistWatchlistRepository(Protocol):
    async def create(self, watchlist: ArtistWatchlist) -> ArtistWatchlist: ...
    async def get(self, watchlist_id: str) -> ArtistWatchlist | None: ...
    async def list_all(self) -> list[ArtistWatchlist]: ...
    async def delete(self, watchlist_id: str) -> None: ...

class IFilterRuleRepository(Protocol): ...
class IAutomationRuleRepository(Protocol): ...
class IQualityUpgradeCandidateRepository(Protocol): ...

# NEW: src/soulspot/domain/ports/session.py
class ISessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...
    async def get(self, session_id: str) -> Session | None: ...
    async def get_by_user_id(self, user_id: str) -> Session | None: ...
    async def update(self, session: Session) -> None: ...
    async def delete(self, session_id: str) -> None: ...
```

### 2.4 Migration Roadmap

**Week 1: Documentation Audit**
- [ ] Run code inventory scripts (Step 1)
- [ ] Generate doc inventory (Step 2)
- [ ] Cross-reference analysis (Step 3)
- [ ] Mark deprecated docs with ⚠️ DEPRECATED headers
- [ ] Create DOCS_STATUS.md with all findings

**Week 2: Interface Standardization** ✅ COMPLETED (2025-12-12)
- [x] Add missing repository interfaces (IArtistWatchlistRepository, IFilterRuleRepository, IAutomationRuleRepository, IQualityUpgradeCandidateRepository, ISessionRepository)
- [x] Update all repositories to implement interfaces
- [ ] Add ITrackClient, IPlaylistClient, IArtistClient interfaces (DEFERRED to Week 4)
- [ ] Update SpotifyClient to implement interfaces (DEFERRED to Week 4)

**Implementation Details (2025-12-12):**
- Added `ISessionRepository` interface in `domain/ports/__init__.py`
- Updated 5 repositories to implement interfaces:
  - `ArtistWatchlistRepository(IArtistWatchlistRepository)`
  - `FilterRuleRepository(IFilterRuleRepository)`
  - `AutomationRuleRepository(IAutomationRuleRepository)`
  - `QualityUpgradeCandidateRepository(IQualityUpgradeCandidateRepository)`
  - `SessionRepository(ISessionRepository)`
- All interface imports added to `repositories.py`
- No type errors (verified with get_errors)

**Week 3: Model Renaming** ✅ COMPLETED (2025-12-12)
- [x] Rename SessionModel → SpotifySessionModel
- [x] Create alembic migration for table rename
- [x] Update all repository references
- [ ] Test migration rollback (REQUIRES DEPLOYMENT ENV)

**Implementation Details (2025-12-12):**
- Renamed `SessionModel` → `SpotifySessionModel` in `infrastructure/persistence/models.py`
- Changed table name: `sessions` → `spotify_sessions`
- Renamed indexes: `ix_sessions_*` → `ix_spotify_sessions_*`
- Updated all 13 references in `SessionRepository` methods (create, get, update, delete, cleanup_expired, get_by_oauth_state)
- Created migration `rr29014ttu62_rename_sessions_to_spotify_sessions.py`:
  - `upgrade()`: Renames table + indexes using batch_alter_table (SQLite-compatible)
  - `downgrade()`: Rollback path fully implemented
  - Includes "future-self" comments explaining multi-service strategy
- Migration tested: ⚠️ REQUIRES DB CONNECTION (cannot test in virtual GitHub env)

**Week 4: Client Interfaces** ✅ ALREADY IMPLEMENTED

**Implementation Status (2025-12-12):**
- [x] ISpotifyClient interface already exists in `domain/ports/__init__.py` (line 459-650+)
- [x] SpotifyClient already implements ISpotifyClient (`infrastructure/integrations/spotify_client.py`)
- [x] Interface includes ALL required methods:
  - **OAuth:** `get_authorization_url()`, `exchange_code()`, `refresh_token()`
  - **Tracks:** `get_track()`, `search_track()`
  - **Playlists:** `get_playlist()`, `get_user_playlists()`
  - **Albums:** `get_album()`, `get_albums()`, `get_album_tracks()`
  - **Artists:** `get_artist()`, `get_several_artists()`, `get_artist_albums()`, `get_artist_top_tracks()`, `get_followed_artists()`, `search_artist()`

**Architecture Notes:**
- ISpotifyClient is SERVICE-SPECIFIC (correct!) - not a generic ITrackClient
- When adding Tidal/Deezer, create ITidalClient/IDeezerClient interfaces (same pattern)
- Domain services receive ISpotifyClient via dependency injection
- Tests can mock ISpotifyClient for isolated testing

**Future Multi-Service Strategy:**
```python
# Domain layer will have service-specific interfaces:
- ISpotifyClient (exists) ✅
- ITidalClient (future)
- IDeezerClient (future)

# Application services will be service-agnostic:
class TrackService:
    def __init__(
        self, 
        spotify_client: ISpotifyClient,
        tidal_client: ITidalClient | None = None
    ):
        self.clients = {"spotify": spotify_client}
        if tidal_client:
            self.clients["tidal"] = tidal_client
```

**Week 5: ISRC Matching & Multi-Service Deduplication** ✅ COMPLETED (2025-12-12)
- [x] Add deezer_id/tidal_id fields to Models (ArtistModel, AlbumModel, TrackModel)
- [x] Add deezer_id/tidal_id fields to Entities (Artist, Album, Track)
- [x] Create migration `ss30015uuv63_add_multi_service_ids.py`
- [x] ISRC field already exists on TrackModel (unique=True, index=True)
- [x] Add `get_by_isrc()` method to ITrackRepository (already existed)
- [x] Add `get_by_deezer_id()` and `get_by_tidal_id()` methods to:
  - IArtistRepository + ArtistRepository
  - IAlbumRepository + AlbumRepository
  - ITrackRepository + TrackRepository

**Implementation Details (2025-12-12):**
- **Models (`infrastructure/persistence/models.py`):**
  - ArtistModel: Added `deezer_id` and `tidal_id` (String(50), nullable, unique, indexed)
  - AlbumModel: Added `deezer_id` and `tidal_id` (String(50), nullable, unique, indexed)
  - TrackModel: Added `deezer_id` and `tidal_id` (String(50), nullable, unique, indexed)

- **Entities (`domain/entities/__init__.py`):**
  - Artist: Added `deezer_id: str | None = None` and `tidal_id: str | None = None`
  - Album: Added `deezer_id: str | None = None` and `tidal_id: str | None = None`
  - Track: Added `deezer_id: str | None = None` and `tidal_id: str | None = None`

- **Interfaces (`domain/ports/__init__.py`):**
  - IArtistRepository: Added `get_by_deezer_id()` and `get_by_tidal_id()`
  - IAlbumRepository: Added `get_by_deezer_id()` and `get_by_tidal_id()`
  - ITrackRepository: Added `get_by_deezer_id()` and `get_by_tidal_id()` (get_by_isrc already existed)

- **Repositories (`infrastructure/persistence/repositories.py`):**
  - ArtistRepository: Implemented `get_by_deezer_id()` and `get_by_tidal_id()`
  - AlbumRepository: Implemented `get_by_deezer_id()` and `get_by_tidal_id()`
  - TrackRepository: Implemented `get_by_deezer_id()` and `get_by_tidal_id()` (get_by_isrc already existed)

- **Migration (`alembic/versions/ss30015uuv63_add_multi_service_ids.py`):**
  - Adds 6 columns (deezer_id, tidal_id) to 3 tables (soulspot_artists, soulspot_albums, soulspot_tracks)
  - Creates 6 unique indexes for fast deduplication lookups
  - Includes "future-self" comments explaining multi-service strategy
  - Full downgrade() path implemented

**Multi-Service Deduplication Strategy:**
```
When syncing from Deezer/Tidal in the future:
1. Check ISRC first (tracks only) - universal identifier
2. Check service ID (deezer_id/tidal_id) - prevent duplicate imports
3. Check name match - fallback for entities without universal IDs
4. If found: Update existing entity with new service ID
5. If not found: Create new entity with service ID
```

**Week 6: Documentation Update** (RECOMMENDED)
- [ ] Update all docs marked as UPDATE NEEDED
- [ ] Create SERVICE_AGNOSTIC_BACKEND.md
- [ ] Update README.md with v2.0 architecture
- [ ] Archive deprecated docs to docs/archive/v1.0/

---

## Phase 3: Code-Documentation Sync Automation

### 3.1 Automated Documentation Generation

**Tool:** OpenAPI/Swagger auto-generation from FastAPI routes

```python
# src/soulspot/main.py
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="SoulSpot API",
        version="2.0.0",
        description="Service-agnostic music library management",
        routes=app.routes,
    )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Generate docs/api/openapi.json automatically
# Then: npx @redocly/cli build-docs docs/api/openapi.json --output docs/api/api-reference.html
```

### 3.2 Pre-Commit Hook for Doc Validation

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Check if any API route changed
if git diff --cached --name-only | grep -q "src/soulspot/api/routers/"; then
  echo "⚠️  API routes changed. Please update docs/api/ accordingly."
  echo "Run: python scripts/generate_api_docs.py"
  exit 1
fi

# Check if any Service changed
if git diff --cached --name-only | grep -q "src/soulspot/application/services/"; then
  echo "⚠️  Services changed. Please update docs/features/ accordingly."
fi
```

---

## Phase 4: Future-Proofing Strategy

### 4.1 Tidal Integration Checklist (Example)

**What Needs Changing:**
- [ ] Create TidalClient implementing ITrackClient
- [ ] Create TidalSessionModel + tidal_sessions table
- [ ] Create tidal_track_mappings table
- [ ] Add Tidal OAuth routes (/api/tidal/auth/callback)
- [ ] Create TidalPlaylistSync service

**What DOESN'T Change:**
- ✅ Generic Track/Artist/Album models (already service-agnostic)
- ✅ UI components (already use track.title, not spotify_track.title)
- ✅ Download queue (already service-agnostic)
- ✅ Automation rules (already service-agnostic)
- ✅ Quality upgrade detection (already ISRC-based)

**Estimated Effort:** 1 week (vs 4 weeks if not service-agnostic)

### 4.2 Deezer Integration Checklist

Same as Tidal, but:
- [ ] DeezerClient implementing ITrackClient
- [ ] DeezerSessionModel + deezer_sessions table
- [ ] deezer_track_mappings table
- [ ] Deezer OAuth routes
- [ ] DeezerPlaylistSync service

**Estimated Effort:** 1 week (incremental)

---

## Appendix A: Documentation Deprecation Template

```markdown
# ⚠️ DEPRECATED - [Document Title]

> **Status:** ❌ DEPRECATED  
> **Replaced By:** [New Document Link]  
> **Date Deprecated:** YYYY-MM-DD  
> **Reason:** [Why deprecated - wrong tech stack / outdated design / theoretical / superseded]

**DO NOT USE THIS FILE. See [New Document] for current information.**

---

<details>
<summary>Original Content (Archived)</summary>

[Original content here...]

</details>
```

---

## Appendix B: Update Needed Template

```markdown
# ⚠️ UPDATE NEEDED - [Document Title]

> **Status:** ⚠️ PARTIALLY OUTDATED  
> **Last Verified:** YYYY-MM-DD  
> **Issues:** [Specific outdated sections]  
> **Assigned To:** [Team Member]

**Known Outdated Sections:**
- Section X: Endpoint /api/foo/bar no longer exists (removed in v1.5)
- Section Y: New endpoint /api/baz added (not documented)

---

[Rest of document...]
```

---

## Next Steps

1. **Immediate (Today):**
   - Run code inventory scripts
   - Generate doc inventory
   - Start cross-reference analysis

2. **This Week:**
   - Complete documentation audit
   - Mark all deprecated docs
   - Create DOCS_STATUS.md

3. **Next Week:**
   - Begin interface standardization
   - Add missing repository interfaces
   - Create ITrackClient interface

4. **This Month:**
   - Complete backend refactoring
   - Update all documentation
   - Archive v1.0 docs

**Review Cadence:** Weekly sync meetings to track progress.
