# Local Library Optimization Plan

**Category:** Architecture  
**Status:** IN PROGRESS 🚧  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Enrichment Service Extraction](./enrichment-service-extraction-plan.md) | [Service Separation](./service-separation-principles.md)

---

## Architecture Clarification

### What is "Local Library"?

**LocalLibrary handles:**
- ✅ Local audio files on disk (scanning, importing, organizing)
- ✅ DB-cached metadata about those files
- ✅ Entities with incomplete metadata (needing enrichment)

**LocalLibrary does NOT handle:**
- ❌ Direct API communication with Spotify/Deezer → Plugins do this
- ❌ Streaming/playback → Separate feature
- ❌ External metadata enrichment → EnrichmentService does this

**Key Distinction:**
```
LocalLibrary  = What's local (files + DB)
Enrichment    = External metadata (via plugins)
Sync Services = Provider sync (Spotify/Deezer playlists)
```

---

## Layer Separation

```
┌───────────────────────────────────────────────────────────┐
│                      API LAYER                             │
│                                                            │
│  api/routers/library.py (1917 LOC - TOO BIG!)             │
│  ├── GET /library/stats                                   │
│  ├── GET /library/artists                                 │
│  ├── GET /library/albums                                  │
│  ├── GET /library/tracks                                  │
│  ├── GET /library/duplicates                              │
│  ├── POST /library/scan      ← Deprecated, use jobs!      │
│  └── DELETE /library/clear-all                            │
└───────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                         │
│                                                            │
│  LibraryScannerService                                    │
│  ├── Scan filesystem → parse tags → import to DB          │
│  ├── Update existing entities                             │
│  └── Report stats (new/updated/errors)                    │
│                                                            │
│  LibraryViewService (NEW!)                                │
│  ├── Build ViewModels for UI                              │
│  ├── Aggregate stats                                      │
│  └── Handle pagination                                    │
│                                                            │
│  LibraryCleanupService (NEW!)                             │
│  ├── Remove duplicates                                    │
│  ├── Clear all library data                               │
│  └── Archive deleted files                                │
│                                                            │
│  LibraryHealthService (NEW!)                              │
│  ├── Check for missing files                              │
│  ├── Detect orphaned DB entries                           │
│  └── Report broken links                                  │
└───────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────┐
│               INFRASTRUCTURE LAYER                         │
│                                                            │
│  Repositories (DB layer)                                  │
│  ├── TrackRepository.get_all_local()                      │
│  ├── ArtistRepository.get_library_artists()               │
│  └── ...                                                  │
│                                                            │
│  FileDiscoveryService (filesystem only!)                  │
│  ├── Walk directories                                     │
│  ├── Filter audio files (.mp3, .flac, etc.)               │
│  └── Return file paths (NO parsing!)                      │
│                                                            │
│  EnrichmentService (uses plugins, NOT clients!)           │
│  ├── After scan: enrich incomplete entities                │
│  ├── Manual: user requests metadata                       │
│  └── Uses: SpotifyPlugin, DeezerPlugin via strategies     │
└───────────────────────────────────────────────────────────┘
```

**Critical Rule:** LocalLibrary services do NOT call plugins directly. EnrichmentService orchestrates plugin usage.

---

## Current Situation

### Strengths ✅

1. **Lidarr Folder Compatibility**
   - Supports `/Artist/Album/Track.mp3` structure
   - Extracts metadata from folder names if tags missing
   - Works with Lidarr-managed libraries

2. **Job Queue Integration**
   - Scans run as background jobs (non-blocking)
   - SSE streaming for real-time progress
   - User can continue using app during scan

3. **Deferred Cleanup**
   - Cleanup operations (duplicates, clear-all) queued
   - UI responsive, job runs in background
   - Results reported via notifications

4. **Clean Plugin Separation**
   - No direct API calls in LocalLibrary code
   - Uses EnrichmentService as intermediary
   - Plugin availability checked properly

---

### Weaknesses 🚨

1. **Monolithic Router (1917 LOC)**
   ```
   api/routers/library.py - 1917 lines!
   ├── Endpoints (stats, artists, albums, tracks, duplicates)
   ├── Enrichment logic (should be in enrichment.py)
   ├── Cleanup operations
   ├── Health checks
   └── Dev endpoints (/scan, /clear-all)
   ```

   **Problem:** Too many concerns in one file. Hard to navigate.

---

2. **Deprecated Code Still Active**
   ```python
   # OLD: Immediate scan endpoint (blocks request)
   @router.post("/library/scan")
   async def scan_library_deprecated():
       """⚠️ DEPRECATED: Use /api/jobs/scan instead."""
       # But still functional and used by old clients!
   ```

   **Problem:** Should be removed or behind feature flag.

---

3. **N+1 Query Problems**
   ```python
   # BAD: Fetch artists, then for each artist fetch albums
   artists = await artist_repo.get_all_local()
   for artist in artists:
       albums = await album_repo.get_by_artist_id(artist.id)  # N queries!
   ```

   **Problem:** 100 artists = 1 + 100 = 101 queries. Should be 1 query with JOIN.

---

4. **Missing Pagination**
   ```python
   @router.get("/library/tracks")
   async def get_all_tracks():
       return await track_repo.get_all_local()  # Returns ALL tracks!
   ```

   **Problem:** Large libraries (10,000+ tracks) cause memory issues and slow responses.

---

5. **Enrichment Code Mixed In**
   ```python
   # In library.py router (WRONG!)
   @router.post("/library/artists/{artist_id}/enrich")
   async def enrich_artist(artist_id: UUID):
       # Should be in enrichment.py router
   ```

   **Problem:** Violates single responsibility. Enrichment is separate concern.

---

## 4-Phase Optimization Plan

### Phase 1: Critical Fixes (1-2 days)

**Objective:** Fix immediate bugs and performance issues.

**Tasks:**

1. **Remove Duplicate Exception Handler**
   ```python
   # Line 557 in library.py - duplicate handler
   @router.exception_handler(DuplicateEntityError)
   async def handle_duplicate(...):
       ...
   # Line 783 - same handler again!
   ```
   **Action:** Remove duplicate at line 783.

---

2. **Deprecate /scan Endpoint**
   ```python
   # Put behind feature flag
   if settings.enable_legacy_scan_endpoint:
       @router.post("/library/scan")
       async def scan_library_deprecated():
           ...
   ```
   **Action:** Default `enable_legacy_scan_endpoint = False`, document migration to `/api/jobs/scan`.

---

3. **Add Pagination to /duplicates**
   ```python
   @router.get("/library/duplicates")
   async def get_duplicates(
       page: int = Query(1, ge=1),
       page_size: int = Query(50, le=1000),
   ):
       result = await duplicate_service.find_duplicates(page, page_size)
       return PaginatedResponse[DuplicateGroup](
           items=result.items,
           total=result.total,
           page=page,
           page_size=page_size,
       )
   ```
   **Action:** Paginate duplicates endpoint (can have 1000+ groups).

---

### Phase 2: Router Split (2-3 days)

**Objective:** Break monolithic router into smaller files (<500 LOC each).

**New Structure:**
```
api/routers/
├── library/
│   ├── __init__.py          ← Main library router (aggregates sub-routers)
│   ├── stats.py             ← GET /library/stats (200 LOC)
│   ├── management.py        ← GET /artists, /albums, /tracks (400 LOC)
│   ├── cleanup.py           ← POST /clear-all, /duplicates (300 LOC)
│   └── health.py            ← GET /health, /missing-files (200 LOC)
├── enrichment.py            ← All enrichment endpoints (moved out!)
└── ...
```

**Migration:**
1. Create `api/routers/library/` directory
2. Move endpoint groups to respective files
3. Update `api/routers/__init__.py` imports
4. Test all endpoints still work

**No breaking changes:** All URLs stay the same, just organized better internally.

---

### Phase 3: Performance (3-5 days)

**Objective:** Eliminate N+1 queries, add caching, paginate everything.

---

**Task 1: Pagination for All List Endpoints**

```python
# Before (BAD)
@router.get("/library/artists")
async def get_artists():
    return await artist_repo.get_all_local()  # ALL artists!

# After (GOOD)
@router.get("/library/artists")
async def get_artists(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=1000),
    sort_by: str = Query("name", regex="^(name|added_at|track_count)$"),
):
    result = await artist_repo.get_paginated(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        filters={"is_local": True},
    )
    return PaginatedResponse[ArtistDTO](**result.dict())
```

**Apply to:** `/artists`, `/albums`, `/tracks`, `/duplicates`

---

**Task 2: Eager Loading for Relations**

```python
# Before (N+1 queries)
artists = await session.execute(
    select(ArtistModel).where(ArtistModel.is_local == True)
)
for artist in artists:
    albums = await session.execute(
        select(AlbumModel).where(AlbumModel.artist_id == artist.id)
    )  # N queries!

# After (1 query with JOIN)
from sqlalchemy.orm import selectinload

artists = await session.execute(
    select(ArtistModel)
    .where(ArtistModel.is_local == True)
    .options(selectinload(ArtistModel.albums))  # Eager load albums
)
# Now artist.albums is already loaded!
```

**Apply to:** Artist → Albums, Album → Tracks, Playlist → Tracks

---

**Task 3: Cache Stats Queries**

```python
# Stats change rarely (only after scan/import)
# Cache for 5 minutes

from functools import lru_cache
from datetime import datetime, timedelta

class LibraryStatsService:
    _cache: dict[str, tuple[datetime, dict]] = {}
    _cache_ttl = timedelta(minutes=5)
    
    async def get_stats(self) -> dict:
        """Get library stats with caching."""
        now = datetime.now()
        
        if "stats" in self._cache:
            cached_at, stats = self._cache["stats"]
            if now - cached_at < self._cache_ttl:
                return stats
        
        # Compute fresh stats
        stats = await self._compute_stats()
        self._cache["stats"] = (now, stats)
        return stats
    
    def invalidate_cache(self):
        """Call after scan/import to clear cache."""
        self._cache.clear()
```

**Cache:** `/library/stats` endpoint (60+ seconds query on large libraries).

---

### Phase 4: Testing (5-7 days)

**Objective:** Add proper test coverage (currently: ONLY live testing).

---

**Unit Tests (services layer)**

```python
# tests/unit/services/test_library_scanner.py

async def test_scan_imports_new_track():
    """Test LibraryScannerService imports new audio file."""
    scanner = LibraryScannerService(...)
    
    result = await scanner.scan_directory("/test/music")
    
    assert result.new_tracks == 1
    assert result.updated_tracks == 0
    assert result.errors == 0

async def test_scan_updates_existing_track():
    """Test scanner updates metadata for existing track."""
    # Create existing track with old metadata
    track = await track_repo.create(Track(...))
    
    # Scan same file with updated tags
    result = await scanner.scan_directory("/test/music")
    
    assert result.new_tracks == 0
    assert result.updated_tracks == 1
    
    # Verify metadata updated
    updated = await track_repo.get_by_id(track.id)
    assert updated.title == "New Title"
```

---

**Integration Tests (API + DB)**

```python
# tests/integration/routers/test_library.py

async def test_get_artists_paginated(client: AsyncClient):
    """Test /library/artists with pagination."""
    # Create 100 test artists
    for i in range(100):
        await artist_repo.create(Artist(name=f"Artist {i}"))
    
    # Fetch page 1
    response = await client.get("/api/library/artists?page=1&page_size=50")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 100
    assert data["page"] == 1
    assert len(data["items"]) == 50
    assert data["has_next"] is True
```

---

**Health Monitoring Dashboard**

```python
# New endpoint: GET /library/health

@router.get("/library/health")
async def get_library_health():
    """Health check for local library."""
    health = await library_health_service.check()
    
    return {
        "status": "healthy" if health.issues == 0 else "degraded",
        "stats": {
            "total_tracks": health.total_tracks,
            "missing_files": health.missing_files,
            "orphaned_db_entries": health.orphaned_entries,
            "broken_links": health.broken_links,
        },
        "checks": [
            {"name": "Files exist", "status": "pass" if health.missing_files == 0 else "warn"},
            {"name": "DB consistency", "status": "pass" if health.orphaned_entries == 0 else "warn"},
            {"name": "Metadata complete", "status": "pass" if health.incomplete_metadata == 0 else "info"},
        ],
    }
```

**UI:** Display health status on Library page, warn if issues detected.

---

## LocalLibrary vs Enrichment

**Critical Distinction:**

| Concern | LocalLibrary | EnrichmentService |
|---------|--------------|-------------------|
| **Focus** | What's local (files + DB) | External metadata |
| **Trigger** | User scan / cron job | After scan / manual request |
| **Data Source** | Filesystem + ID3 tags | Spotify/Deezer/MusicBrainz APIs |
| **External APIs** | ❌ NO | ✅ YES (via plugins) |
| **Service Layer** | LibraryScannerService | EnrichmentService |
| **Router** | `api/routers/library/` | `api/routers/enrichment.py` |

**Example Flow:**
```
1. User clicks "Scan Library"
   → LibraryScannerService scans /music folder
   → Imports 100 tracks with basic metadata (title, artist from tags)
   → Some tracks missing album art / ISRC

2. Scan completes, auto-enrichment triggered
   → EnrichmentService finds incomplete entities
   → For each track: query Spotify/Deezer for metadata
   → Update DB with enriched data (album art, ISRC, genres)
```

**Two separate services, sequential workflow.**

---

## Migration Checklist

### Phase 1: Critical Fixes
- [ ] Remove duplicate exception handler (line 783)
- [ ] Add feature flag for `/library/scan` endpoint
- [ ] Add pagination to `/library/duplicates`
- [ ] Test all fixes locally

### Phase 2: Router Split
- [ ] Create `api/routers/library/` directory
- [ ] Move stats endpoints to `stats.py`
- [ ] Move management endpoints to `management.py`
- [ ] Move cleanup endpoints to `cleanup.py`
- [ ] Move health endpoints to `health.py`
- [ ] Extract enrichment endpoints to `enrichment.py`
- [ ] Update imports in `api/routers/__init__.py`
- [ ] Verify all endpoints still work

### Phase 3: Performance
- [ ] Add pagination to `/library/artists`
- [ ] Add pagination to `/library/albums`
- [ ] Add pagination to `/library/tracks`
- [ ] Add eager loading for artist → albums
- [ ] Add eager loading for album → tracks
- [ ] Implement stats caching with TTL
- [ ] Add cache invalidation on scan/import

### Phase 4: Testing
- [ ] Write unit tests for LibraryScannerService
- [ ] Write unit tests for LibraryViewService
- [ ] Write unit tests for LibraryCleanupService
- [ ] Write integration tests for library endpoints
- [ ] Add health monitoring dashboard
- [ ] Document testing procedures

---

## Related Documentation

- **[Enrichment Service Extraction](./enrichment-service-extraction-plan.md)** - Separate enrichment from library
- **[Service Separation Principles](./service-separation-principles.md)** - Single responsibility pattern
- **[Transaction Patterns](./transaction-patterns.md)** - DB best practices

---

**Status:** 🚧 Phase 1 in progress  
**Next:** Complete critical fixes, then proceed to router split  
**Timeline:** 4 phases × ~3 days = ~12 working days total
