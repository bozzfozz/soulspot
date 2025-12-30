# Service Separation Plan

**Category:** Architecture  
**Status:** IN PROGRESS 🔄  
**Last Updated:** 2025-01-XX  
**Priority:** HIGH - Architecture Conformance  
**Related Docs:** [Service Separation Principles](./service-separation-principles.md) | [Service Reorganization](./service-reorganization.md)

---

## Problem Analysis

### Current State

```
SpotifySyncService (1839 lines!)
├── Sync Followed Artists (Spotify-specific, needs OAuth)
├── Sync User Playlists (Spotify-specific, needs OAuth)
├── Sync Liked Songs (Spotify-specific, needs OAuth)
├── Sync Saved Albums (Spotify-specific, needs OAuth)
├── Sync Artist Albums (Multi-provider, Spotify + Deezer fallback)
├── Sync Album Tracks (Multi-provider)
├── Get Artist/Album/Track (generic - DB queries)
├── get_album_detail_view (generic - ViewModel)
└── Utility Methods (duration calc, etc.)
```

### Problems

| Problem | Rule Violation |
|---------|----------------|
| **God Class** | Single Responsibility Principle violated - 1839 lines |
| **Mixed Concerns** | Spotify-specific + generic + ViewModels mixed |
| **Missing DeezerSyncService** | No separate service for Deezer sync |
| **ViewModels in SyncService** | ViewModels belong in separate ViewService |
| **DB Queries in SyncService** | Repositories should handle DB queries |

---

## Target Architecture

### Service Structure (Clean Architecture)

```
src/soulspot/application/services/
│
├── SYNC SERVICES (Provider-specific)
│   ├── spotify_sync_service.py      # ONLY Spotify OAuth-based sync
│   │   ├── sync_followed_artists()  # Needs Spotify OAuth
│   │   ├── sync_user_playlists()    # Needs Spotify OAuth
│   │   ├── sync_liked_songs()       # Needs Spotify OAuth
│   │   └── sync_saved_albums()      # Needs Spotify OAuth
│   │
│   ├── deezer_sync_service.py       # ONLY Deezer-specific sync (NEW!)
│   │   ├── sync_charts()            # Deezer Charts (no auth needed)
│   │   ├── sync_new_releases()      # Deezer New Releases
│   │   └── sync_artist_albums()     # Deezer Artist Albums (fallback)
│   │
│   └── tidal_sync_service.py        # FUTURE: Tidal sync (when we have Tidal)
│
├── ORCHESTRATION SERVICES (Multi-provider)
│   ├── provider_sync_orchestrator.py  # Coordinates multiple providers (NEW!)
│   │   ├── sync_artist_albums()     # Try Spotify → Deezer fallback
│   │   ├── sync_album_tracks()      # Try Spotify → Deezer fallback
│   │   └── get_aggregated_new_releases()
│   │
│   └── followed_artists_service.py  # Already exists! Multi-provider aggregation
│       ├── get_followed_artists()   # Spotify + Deezer + ...
│       └── sync_to_library()        # Unified library
│
├── VIEW SERVICES (Template-ready ViewModels)
│   └── library_view_service.py      # ViewModels for UI (NEW!)
│       ├── get_album_detail_view()  # AlbumDetailView for template
│       ├── get_artist_detail_view() # ArtistDetailView for template
│       └── get_track_list_view()    # TrackListView for template
│
└── EXISTING SERVICES (unchanged)
    ├── new_releases_service.py      # Aggregates new releases
    ├── charts_service.py            # Aggregates charts
    ├── discover_service.py          # Discovery recommendations
    └── ... (other services)
```

---

### Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API Routes                                  │
│  /spotify/artists/{id}/albums/{album_id}                            │
│  /library/artists                                                   │
│  /discover/new-releases                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
┌──────────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│ LibraryViewService   │ │ProviderSyncOrch.│ │ NewReleasesService   │
│ (ViewModels)         │ │ (Orchestration) │ │ (Aggregation)        │
└──────────────────────┘ └─────────────────┘ └──────────────────────┘
          │                       │                      │
          │           ┌───────────┼───────────┐          │
          │           ▼           ▼           ▼          │
          │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
          │  │SpotifySync  │ │DeezerSync   │ │TidalSync    │
          │  │Service      │ │Service      │ │Service      │
          │  └─────────────┘ └─────────────┘ └─────────────┘
          │           │           │           │
          │           ▼           ▼           ▼
          │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
          │  │SpotifyPlugin│ │DeezerPlugin │ │TidalPlugin  │
          │  └─────────────┘ └─────────────┘ └─────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      REPOSITORIES                                    │
│  ArtistRepository, AlbumRepository, TrackRepository                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Migration Steps

### Phase 1: ViewModels Extract (LOW RISK) ✅ DONE

**Status:** COMPLETED (Session 2025-01-XX)

**Objective:** Extract ViewModels from SpotifySyncService into separate service.

**Completed Steps:**
1. ✅ **Created** `library_view_service.py` with `get_album_detail_view()`
2. ✅ **Exported** in `services/__init__.py`
3. ✅ **Dependency** `get_library_view_service()` in `dependencies.py`
4. ✅ **Route** `/spotify/artists/{artist_id}/albums/{album_id}` now uses `LibraryViewService`
5. ✅ **Graceful Degradation** - Shows cached data when no Spotify auth

**Files Changed:**
- CREATE: `src/soulspot/application/services/library_view_service.py`
- MODIFY: `src/soulspot/application/services/__init__.py` (export added)
- MODIFY: `src/soulspot/api/dependencies.py` (DI for LibraryViewService)
- MODIFY: `src/soulspot/api/routers/ui.py` (route dependency changed)

**Backward Compatibility:**
- `SpotifySyncService.get_album_detail_view()` remains for now (other routes)
- Will be removed in Phase 4

---

### Phase 2: DeezerSyncService Create (MEDIUM RISK)

**Status:** TODO

**Objective:** Create Deezer-specific sync service.

---

**Step 2.1: Create Service**

```python
# application/services/deezer_sync_service.py

class DeezerSyncService:
    """Deezer-specific sync operations."""
    
    def __init__(
        self,
        deezer_plugin: DeezerPlugin,
        artist_repo: ArtistRepository,
        album_repo: AlbumRepository,
        track_repo: TrackRepository,
    ):
        self._plugin = deezer_plugin
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
    
    async def sync_charts(
        self,
        chart_type: str = "tracks",
        limit: int = 50,
    ) -> list[Track]:
        """Sync Deezer charts (no auth needed)."""
        chart_data = await self._plugin.get_charts(chart_type, limit)
        
        tracks = []
        for item in chart_data.items:
            track = await self._import_track(item)
            tracks.append(track)
        
        return tracks
    
    async def sync_new_releases(
        self,
        limit: int = 50,
    ) -> list[Album]:
        """Sync Deezer new releases (no auth needed)."""
        releases = await self._plugin.get_new_releases(limit)
        
        albums = []
        for release in releases.items:
            album = await self._import_album(release)
            albums.append(album)
        
        return albums
    
    async def sync_artist_albums(
        self,
        deezer_id: str,
    ) -> list[Album]:
        """Sync artist albums from Deezer."""
        albums_data = await self._plugin.get_artist_albums(deezer_id)
        
        albums = []
        for album_data in albums_data.items:
            album = await self._import_album(album_data)
            albums.append(album)
        
        return albums
    
    async def _import_track(self, track_dto: TrackDTO) -> Track:
        """Import track with deduplication."""
        # Check ISRC first
        if track_dto.isrc:
            existing = await self._track_repo.get_by_isrc(track_dto.isrc)
            if existing:
                # Add Deezer ID if missing
                if not existing.deezer_id:
                    existing.deezer_id = track_dto.deezer_id
                    await self._track_repo.update(existing)
                return existing
        
        # Create new track
        track = Track(
            id=uuid4(),
            title=track_dto.title,
            isrc=track_dto.isrc,
            deezer_id=track_dto.deezer_id,
            duration_ms=track_dto.duration_ms,
            # ... other fields
        )
        await self._track_repo.create(track)
        return track
```

---

**Step 2.2: Extract Deezer Logic**

Move Deezer-related code from `followed_artists_service.py` or other services to `DeezerSyncService`.

---

### Phase 3: ProviderSyncOrchestrator (MEDIUM RISK)

**Status:** TODO

**Objective:** Create orchestrator for multi-provider sync operations.

---

**Step 3.1: Create Orchestrator**

```python
# application/services/provider_sync_orchestrator.py

class ProviderSyncOrchestrator:
    """Orchestrates multi-provider sync operations."""
    
    def __init__(
        self,
        spotify_sync: SpotifySyncService,
        deezer_sync: DeezerSyncService,
        settings_service: AppSettingsService,
    ):
        self._spotify = spotify_sync
        self._deezer = deezer_sync
        self._settings = settings_service
    
    async def sync_artist_albums(
        self,
        artist_id: UUID,
    ) -> list[Album]:
        """Sync artist albums from available providers.
        
        Priority:
        1. Spotify (if authenticated)
        2. Deezer (fallback, no auth needed)
        """
        # Try Spotify first
        artist = await self._artist_repo.get_by_id(artist_id)
        
        if artist.spotify_uri and await self._spotify.is_authenticated():
            try:
                return await self._spotify.sync_artist_albums(artist.spotify_uri)
            except Exception as e:
                logger.warning(f"Spotify sync failed: {e}, falling back to Deezer")
        
        # Fallback to Deezer
        if artist.deezer_id:
            return await self._deezer.sync_artist_albums(artist.deezer_id)
        
        raise ValueError("No provider IDs available for artist")
    
    async def sync_album_tracks(
        self,
        album_id: UUID,
    ) -> list[Track]:
        """Sync album tracks from available providers."""
        album = await self._album_repo.get_by_id(album_id)
        
        # Try Spotify first
        if album.spotify_uri and await self._spotify.is_authenticated():
            try:
                return await self._spotify.sync_album_tracks(album.spotify_uri)
            except Exception:
                pass  # Fallback below
        
        # Fallback to Deezer
        if album.deezer_id:
            return await self._deezer.sync_album_tracks(album.deezer_id)
        
        raise ValueError("No provider IDs available for album")
```

---

**Step 3.2: Migrate Multi-Provider Methods**

Move methods like `sync_artist_albums()` from `SpotifySyncService` to `ProviderSyncOrchestrator`.

---

### Phase 4: SpotifySyncService Cleanup (HIGH RISK)

**Status:** TODO

**Objective:** Remove generic/multi-provider code from `SpotifySyncService`.

**What Stays in SpotifySyncService:**
- ✅ `sync_followed_artists()` (Spotify OAuth required)
- ✅ `sync_user_playlists()` (Spotify OAuth required)
- ✅ `sync_liked_songs()` (Spotify OAuth required)
- ✅ `sync_saved_albums()` (Spotify OAuth required)

**What Moves:**
- ❌ `sync_artist_albums()` → `ProviderSyncOrchestrator`
- ❌ `sync_album_tracks()` → `ProviderSyncOrchestrator`
- ❌ `get_album_detail_view()` → `LibraryViewService` (done ✅)
- ❌ Generic DB queries → Repositories

---

## Benefits

### Before (Mixed Concerns)

```python
class SpotifySyncService:
    # Spotify-specific
    async def sync_followed_artists(): ...
    async def sync_user_playlists(): ...
    
    # Generic (wrong!)
    async def sync_artist_albums(): ...  # Works with any provider
    async def get_album_detail_view(): ...  # ViewModel
    
    # Utility (wrong!)
    def _calculate_duration(): ...
```

**Problems:**
- 1839 lines - too large
- Mixed Spotify-specific + generic code
- Hard to test individual concerns
- Can't reuse generic logic for Deezer

---

### After (Separated Concerns)

```python
# Spotify-specific
class SpotifySyncService:
    async def sync_followed_artists(): ...  # ONLY Spotify OAuth
    async def sync_user_playlists(): ...
    async def sync_liked_songs(): ...
    async def sync_saved_albums(): ...

# Deezer-specific
class DeezerSyncService:
    async def sync_charts(): ...            # ONLY Deezer
    async def sync_new_releases(): ...
    async def sync_artist_albums(): ...

# Multi-provider orchestration
class ProviderSyncOrchestrator:
    async def sync_artist_albums(): ...     # Try Spotify → fallback Deezer
    async def sync_album_tracks(): ...

# ViewModels
class LibraryViewService:
    async def get_album_detail_view(): ...  # Template-ready data
```

**Benefits:**
- Clear responsibilities (~200-300 lines each)
- Easy to test provider-specific logic
- Generic code reusable for new providers
- Add Tidal: create `TidalSyncService`, update orchestrator

---

## Testing Strategy

### Unit Tests (Per Service)

```python
# tests/unit/services/test_spotify_sync_service.py
async def test_sync_followed_artists():
    """Test Spotify-specific followed artists sync."""
    mock_plugin = MockSpotifyPlugin()
    service = SpotifySyncService(mock_plugin, ...)
    
    artists = await service.sync_followed_artists()
    assert len(artists) > 0

# tests/unit/services/test_deezer_sync_service.py
async def test_sync_charts():
    """Test Deezer-specific charts sync."""
    mock_plugin = MockDeezerPlugin()
    service = DeezerSyncService(mock_plugin, ...)
    
    tracks = await service.sync_charts("tracks", 50)
    assert len(tracks) == 50

# tests/unit/services/test_provider_sync_orchestrator.py
async def test_sync_artist_albums_spotify_fallback():
    """Test orchestrator tries Spotify, falls back to Deezer."""
    # Mock Spotify failure
    spotify_sync = MockSpotifySyncService(fail=True)
    deezer_sync = MockDeezerSyncService()
    
    orchestrator = ProviderSyncOrchestrator(spotify_sync, deezer_sync, ...)
    albums = await orchestrator.sync_artist_albums(artist_id)
    
    # Verify Deezer was called (fallback)
    assert deezer_sync.sync_artist_albums.called
```

---

## Migration Checklist

- [x] **Phase 1: ViewModels Extract** ✅ COMPLETE
  - [x] Create `LibraryViewService`
  - [x] Migrate `get_album_detail_view()`
  - [x] Update routes to use new service
  - [x] Maintain backward compatibility

- [ ] **Phase 2: DeezerSyncService Create**
  - [ ] Create `DeezerSyncService` class
  - [ ] Implement `sync_charts()`
  - [ ] Implement `sync_new_releases()`
  - [ ] Implement `sync_artist_albums()`
  - [ ] Add unit tests
  - [ ] Export in `services/__init__.py`

- [ ] **Phase 3: ProviderSyncOrchestrator**
  - [ ] Create `ProviderSyncOrchestrator` class
  - [ ] Implement `sync_artist_albums()` with fallback
  - [ ] Implement `sync_album_tracks()` with fallback
  - [ ] Migrate multi-provider methods from `SpotifySyncService`
  - [ ] Add unit tests with mocked providers

- [ ] **Phase 4: SpotifySyncService Cleanup**
  - [ ] Remove `sync_artist_albums()` (moved to orchestrator)
  - [ ] Remove `sync_album_tracks()` (moved to orchestrator)
  - [ ] Remove `get_album_detail_view()` (moved to ViewService)
  - [ ] Remove generic utility methods (move to shared utils)
  - [ ] Verify only Spotify OAuth methods remain
  - [ ] Update all consumers to use new services

- [ ] **Phase 5: Integration Testing**
  - [ ] Test full sync workflows (Spotify + Deezer)
  - [ ] Test fallback behavior (Spotify fails → Deezer succeeds)
  - [ ] Test UI routes with new ViewService
  - [ ] Verify backward compatibility maintained

---

## Timeline

| Phase | Duration | Risk Level |
|-------|----------|------------|
| Phase 1: ViewModels | DONE ✅ | - |
| Phase 2: DeezerSyncService | 2-3 days | Medium |
| Phase 3: Orchestrator | 3-4 days | Medium |
| Phase 4: Cleanup | 2-3 days | High |
| Phase 5: Testing | 2-3 days | High |
| **Total** | **9-13 days** | **Medium-High** |

**Risk Mitigation:**
- Maintain backward compatibility throughout
- Add comprehensive unit tests per phase
- Test provider fallback extensively
- Keep old methods until all consumers migrated

---

## Related Documentation

- **[Service Separation Principles](./service-separation-principles.md)** - Architecture rules
- **[Service Reorganization](./service-reorganization.md)** - Directory structure reorganization
- **[Plugin System](./plugin-system.md)** - Plugin architecture for providers

---

**Status:** 🔄 In Progress (Phase 1 complete, Phase 2-4 planned)  
**Next Step:** Implement `DeezerSyncService` (Phase 2)  
**Priority:** HIGH - Needed for proper multi-provider architecture
