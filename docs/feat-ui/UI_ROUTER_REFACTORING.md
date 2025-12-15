# UI Router Clean Architecture Refactoring - Combined Approach

## Status: Postponed for Web UI Design Phase

The refactoring of `src/soulspot/api/routers/ui.py` is intentionally **postponed** to be combined with the Web UI Design modernization phase.

## Rationale

ui.py contains **16 direct Model imports** across **35 HTMX rendering routes**. These routes are tightly coupled with:

1. **Template structure** - Jinja2 templates in `src/soulspot/templates/`
2. **HTMX patterns** - Partial rendering, live updates, polling
3. **Data fetching logic** - Complex JOINs for artist/album/track listings
4. **UI/UX patterns** - Pagination, filtering, sorting

Refactoring ui.py in isolation would result in:
- ❌ Potential duplicate work when redesigning UI components
- ❌ Services that may not align with new UI architecture
- ❌ Template changes requiring service updates

## Combined Approach Benefits

By combining ui.py refactoring with Web UI Design:

- ✅ **Unified data requirements** - Design UI components knowing exact data needs
- ✅ **Optimized queries** - Service methods match new component patterns
- ✅ **Single pass refactoring** - No rework when UI changes
- ✅ **Better architecture** - Services designed for actual UI needs, not current implementation

## Current Clean Architecture Status (Phase 1 Complete)

### Refactored Routers (4/5)

| Router | Routes | Model Imports | Status |
|--------|--------|---------------|--------|
| library.py | 8 | 2 (pragmatic) | ✅ Complete |
| stats.py | 2 | 1 (pragmatic) | ✅ Complete |
| tracks.py | 1 | 1 (pragmatic) | ✅ Complete |
| playlists.py | 6 | 0 | ✅ Complete |
| **ui.py** | 0 | **16** | 🔄 **Postponed** |

**Total Progress:**
- Model imports: 33 → 20 (39% reduction)
- Routes refactored: 16 routes
- Services created: 5 services (~1200 LOC)

### Services Created in Phase 1

1. **EnrichmentService** (330 LOC) - Enrichment status, candidate management
2. **DuplicateService** (230 LOC) - Duplicate resolution, file deletion
3. **LibraryCleanupService** (130 LOC) - Bulk delete with orphan cleanup
4. **StatsService** (320 LOC) - Centralized statistics
5. **PlaylistService** (220 LOC) - Missing tracks, blacklist management

## Web UI Design Phase - Planned Approach

### Service to Create: UIRenderingService

**Purpose:** Centralize data fetching for UI components

**Methods (estimated):**
```python
class UIRenderingService:
    # Artist browser
    async def get_artists_for_browser(
        limit: int,
        offset: int,
        sort: str,
        filter: str,
    ) -> ArtistBrowserResult
    
    # Album browser
    async def get_albums_for_browser(
        limit: int,
        offset: int,
        type_filter: AlbumType,
    ) -> AlbumBrowserResult
    
    # Track listings
    async def get_tracks_for_browser(
        limit: int,
        offset: int,
        filters: TrackFilters,
    ) -> TrackBrowserResult
    
    # Dashboard data
    async def get_dashboard_stats() -> DashboardStats
    
    # Download queue rendering
    async def get_download_queue(
        status_filter: list[str],
        limit: int,
    ) -> DownloadQueueResult
```

### UI Routes to Refactor (16 Model imports)

**Priority 1: Library Browser (8 routes)**
- `/library/artists` - Artist listing with pagination
- `/library/albums` - Album listing with type filters
- `/library/tracks` - Track listing with filters
- `/library/artists/{artist_name}` - Artist detail view
- `/library/albums/{album_key}` - Album detail view
- `/library/compilations` - Compilations view
- `/library/stats-partial` - Live stats updates
- `/tracks/{track_id}/metadata-editor` - Metadata editor

**Priority 2: Browse/Discovery (2 routes)**
- `/browse/new-releases` - New releases from Spotify/Deezer
- `/spotify/discover` - Discovery recommendations

**Priority 3: Dashboard (3 routes)**
- `/` - Dashboard with widgets
- `/dashboard` - Full dashboard view
- `/downloads/queue-partial` - Queue updates

**Priority 4: Misc (3 routes)**
- `/search/quick` - Quick search results
- `/library/duplicates` - Duplicate detection UI
- `/library/broken-files` - Broken files view

### Estimated Effort

**Phase 1 (Complete):** 16 routes, 5 services, ~1200 LOC - **Completed**

**Phase 2 (Web UI + ui.py):**
- UIRenderingService: ~400 LOC
- 16 route refactorings: ~800 LOC changes
- Template updates: Variable
- **Total:** 8-12 hours

## Integration Points

### With Clean Architecture

ui.py refactoring will follow same patterns:
1. Route receives request → validates input
2. Calls UIRenderingService method
3. Service uses Repositories (not Models directly)
4. Service returns DTO
5. Route renders template with DTO data

### With Web UI Design

UI components will inform service design:
- **Component data needs** → Service method signatures
- **Real-time updates** → Service caching strategy
- **Pagination patterns** → Service offset/limit logic
- **Filter/sort UX** → Service query building

## Success Criteria

### After Phase 2 Complete:

**Code Quality:**
- ✅ Zero direct Model imports in ui.py
- ✅ All queries through UIRenderingService
- ✅ Consistent error handling
- ✅ Type-safe DTOs

**Architecture:**
- ✅ 100% Clean Architecture compliance in API layer
- ✅ All routes < 50 LOC
- ✅ Testable services with mocked repositories
- ✅ No N+1 queries

**Performance:**
- ✅ Optimized JOIN queries
- ✅ Minimal database round-trips
- ✅ Efficient pagination

## Timeline

**Phase 1 (Complete):** ✅ Completed December 2025
- library.py, stats.py, tracks.py, playlists.py refactored
- 5 services created
- 39% Model import reduction

**Phase 2 (Planned):** 🔄 Q1 2026
- Web UI Design modernization
- ui.py Clean Architecture refactoring
- UIRenderingService creation
- Target: 100% Clean Architecture compliance

## Related Documentation

- [Clean Architecture Overview](../architecture/CORE_PHILOSOPHY.md)
- [Repository Pattern](../architecture/REPOSITORY_PATTERN.md)
- [Service Layer Guidelines](../development/SERVICE_LAYER.md)
- [HTMX Integration](../feat-ui/HTMX_PATTERNS.md) *(to be created)*

---

**Last Updated:** December 15, 2025  
**Status:** Phase 1 Complete, Phase 2 Planned
