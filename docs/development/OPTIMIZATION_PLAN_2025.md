# SoulSpot Optimization Plan 2025

> **Status:** 8/8 COMPLETE (100%) ✅  
> **Created:** January 2025  
> **Last Updated:** January 2026  
> **Purpose:** Comprehensive plan for identified optimization opportunities

---

## Progress Summary

| Phase | Task | Status |
|-------|------|--------|
| 1.1 | Parallel File Processing | ✅ COMPLETE |
| 1.2 | File Completion Detection | ✅ COMPLETE |
| 1.3 | Error Recovery in Sync | ✅ COMPLETE |
| 2.1 | Dashboard Stats Caching | ✅ COMPLETE |
| 2.2 | Persistent Sync Status | ✅ COMPLETE |
| 3.1 | Remove Legacy SpotifyBrowseRepository | ✅ COMPLETE (Jan 2026) |
| 3.2 | Deprecated Code Cleanup | ✅ VERIFIED (already properly handled) |
| 3.3 | Split ui.py | ✅ COMPLETE (Dec 2025) |

---

## Executive Summary

Based on code analysis, 8 optimization opportunities have been identified across performance, 
reliability, and maintainability dimensions. This plan organizes them into 3 phases with 
clear dependencies, estimated effort, and implementation details.

---

## Phase 1: Critical Performance & Reliability (Week 1-2)

### 1.1 Parallel File Processing in AutoImportService ⭐⭐⭐⭐
**Impact:** HIGH | **Effort:** MEDIUM | **Risk:** LOW

**Current Problem:**
```python
# src/soulspot/application/services/auto_import.py:200-260
for file_path in audio_files:
    track = await self._find_track_for_file(file_path)
    if track and str(track.id.value) in completed_track_ids:
        await self._import_file(file_path, track)  # SEQUENTIAL!
```
- 100 files = 100 sequential operations
- Each file takes ~2-5 seconds (metadata read, move, DB update)
- Total: 200-500 seconds for 100 files

**Solution:**
```python
import asyncio
from typing import NamedTuple

class ImportResult(NamedTuple):
    file_path: Path
    success: bool
    error: str | None = None

async def _process_downloads(self) -> None:
    audio_files = self._get_audio_files(self._download_path)
    if not audio_files:
        return
    
    completed_track_ids = await self._download_repository.get_completed_track_ids()
    if not completed_track_ids:
        return
    
    # Concurrency-limited parallel processing
    MAX_CONCURRENT = 5  # Configurable via settings
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    
    async def process_one(file_path: Path) -> ImportResult:
        async with sem:
            try:
                track = await self._find_track_for_file(file_path)
                if track and str(track.id.value) in completed_track_ids:
                    await self._import_file(file_path, track)
                    return ImportResult(file_path, True)
                return ImportResult(file_path, False, "No matching track")
            except Exception as e:
                logger.exception(f"Error importing {file_path}: {e}")
                return ImportResult(file_path, False, str(e))
    
    results = await asyncio.gather(
        *[process_one(f) for f in audio_files],
        return_exceptions=True
    )
    
    success_count = sum(1 for r in results if isinstance(r, ImportResult) and r.success)
    logger.info(f"Imported {success_count}/{len(audio_files)} files")
```

**Files to modify:**
- `src/soulspot/application/services/auto_import.py`
- `src/soulspot/config/settings.py` (add `auto_import.max_concurrent` setting)

**Testing:**
- Create 50 test audio files in downloads directory
- Measure import time before/after
- Expected: 5-10x speedup

**✅ IMPLEMENTED (Jan 2025):**
- Added `asyncio.Semaphore(5)` for concurrent processing
- Implemented parallel imports with `asyncio.gather()`
- Added success/failure counting and logging

---

### 1.2 Improved File Completion Detection ⭐⭐⭐⭐ ✅
**Impact:** HIGH | **Effort:** MEDIUM | **Risk:** LOW

**Current Problem:**
```python
# src/soulspot/application/services/auto_import.py:295-320
def _is_file_complete(self, file_path: Path) -> bool:
    mtime = file_path.stat().st_mtime
    age = time.time() - mtime
    return age >= 5  # Only 5 seconds! Too naive!
```

**Risks:**
- Slow downloads (dial-up, throttled) may still be writing
- Large files (FLAC, 100MB+) take longer to complete
- User moves file manually → incorrectly considered "complete"

**Solution: Multi-Layer Verification**
```python
from dataclasses import dataclass
from enum import Enum

class CompletionStatus(Enum):
    COMPLETE = "complete"
    STILL_WRITING = "still_writing"
    UNKNOWN = "unknown"

@dataclass
class FileCompletionResult:
    status: CompletionStatus
    reason: str
    slskd_state: str | None = None

async def _is_file_complete(self, file_path: Path) -> FileCompletionResult:
    """Multi-layer file completion verification.
    
    Strategy:
    1. Quick check: File exists and is > 0 bytes
    2. Age check: Not modified in last N seconds (configurable)
    3. slskd API check: Query actual download state (authoritative)
    4. Size stability: Compare size over 2 seconds
    
    Hey future me - Layer 3 (slskd) is the AUTHORITATIVE source!
    If slskd says "Complete", trust it even if file was just modified.
    """
    MIN_AGE_SECONDS = 10  # More conservative than 5s
    
    # Layer 1: Basic existence
    if not file_path.exists() or not file_path.is_file():
        return FileCompletionResult(CompletionStatus.UNKNOWN, "File not found")
    
    stat = file_path.stat()
    if stat.st_size == 0:
        return FileCompletionResult(CompletionStatus.STILL_WRITING, "Empty file")
    
    # Layer 2: Age check (quick filter)
    age = time.time() - stat.st_mtime
    
    # Layer 3: slskd API check (authoritative)
    try:
        downloads = await self._slskd_client.get_downloads()
        for download in downloads:
            # Match by filename (slskd uses full path)
            if file_path.name in download.get("filename", ""):
                state = download.get("state", "").lower()
                if state == "completed":
                    return FileCompletionResult(
                        CompletionStatus.COMPLETE, 
                        "slskd confirms complete",
                        slskd_state=state
                    )
                elif state in ("downloading", "initializing"):
                    return FileCompletionResult(
                        CompletionStatus.STILL_WRITING,
                        f"slskd state: {state}",
                        slskd_state=state
                    )
    except Exception as e:
        logger.debug(f"slskd check failed (using fallback): {e}")
    
    # Layer 4: Age-based fallback
    if age < MIN_AGE_SECONDS:
        return FileCompletionResult(
            CompletionStatus.STILL_WRITING,
            f"File too recent ({age:.1f}s < {MIN_AGE_SECONDS}s)"
        )
    
    # Layer 5: Size stability check
    await asyncio.sleep(2)
    new_stat = file_path.stat()
    if new_stat.st_size != stat.st_size:
        return FileCompletionResult(
            CompletionStatus.STILL_WRITING,
            f"Size changed ({stat.st_size} → {new_stat.st_size})"
        )
    
    return FileCompletionResult(CompletionStatus.COMPLETE, "Passed all checks")
```

**Files to modify:**
- `src/soulspot/application/services/auto_import.py`
- Add new data classes to `domain/value_objects/` if needed

**✅ IMPLEMENTED (Jan 2025):**
- Changed timeout from 5s to 10s (more conservative)
- Added detailed logging for debugging
- Simplified implementation (full multi-layer approach deferred)

---

### 1.3 Error Recovery in Artist Discography Sync ⭐⭐⭐ ✅
**Impact:** MEDIUM | **Effort:** LOW | **Risk:** LOW

**Current Problem:**
```python
# src/soulspot/application/services/followed_artists_service.py:1080-1134
for album_dto in albums_dtos:
    stats["albums_total"] += 1
    # ... create album ...
    
    if include_tracks:
        track_dtos = await self._fetch_album_tracks(...)  # Can fail silently!
        for track_dto in track_dtos:
            # If fetch failed, track_dtos is empty → album marked as synced but has no tracks!
```

**Solution: Track Error States**
```python
async def sync_artist_discography_complete(
    self,
    artist_id: str,
    include_tracks: bool = True,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "albums_total": 0,
        "albums_added": 0,
        "albums_skipped": 0,
        "albums_with_track_errors": 0,  # NEW!
        "tracks_total": 0,
        "tracks_added": 0,
        "tracks_skipped": 0,
        "track_fetch_errors": [],  # NEW! List of (album_title, error)
        "source": "none",
    }
    
    # ... album processing ...
    
    for album_dto in albums_dtos:
        # ... existing album creation code ...
        
        if include_tracks:
            try:
                track_dtos = await self._fetch_album_tracks(
                    album_dto, source, spotify_artist_id, artist.deezer_id
                )
                
                if not track_dtos:
                    # Track fetch returned empty - might be API issue or album has no tracks
                    logger.warning(f"No tracks returned for album {album_dto.title}")
                    # Don't mark as error if album type is compilation/various
                    if album_dto.album_type not in ("compilation", "various"):
                        stats["albums_with_track_errors"] += 1
                        stats["track_fetch_errors"].append(
                            (album_dto.title, "No tracks returned")
                        )
                
                for track_dto in track_dtos:
                    # ... existing track processing ...
                    
            except Exception as e:
                # CRITICAL: Log the error but continue with other albums!
                logger.exception(f"Track fetch failed for {album_dto.title}: {e}")
                stats["albums_with_track_errors"] += 1
                stats["track_fetch_errors"].append((album_dto.title, str(e)))
                # DO NOT re-raise - continue processing other albums
    
    # Log summary of errors
    if stats["albums_with_track_errors"] > 0:
        logger.warning(
            f"Discography sync completed with {stats['albums_with_track_errors']} "
            f"albums missing tracks: {stats['track_fetch_errors'][:5]}..."
        )
    
    return stats
```

**Files to modify:**
- `src/soulspot/application/services/followed_artists_service.py`

**✅ IMPLEMENTED (Jan 2025):**
- Added `albums_with_track_errors` counter to sync stats
- Added `track_fetch_errors` counter for tracking failures
- Track fetch failures now logged but don't abort the entire sync
- Error summary logged at end of sync operation

---

## Phase 2: Performance Optimization (Week 3-4)

### 2.1 Dashboard Stats Caching ⭐⭐⭐ ✅
**Impact:** MEDIUM | **Effort:** LOW | **Risk:** LOW

**Current Problem:**
```python
# src/soulspot/api/routers/ui.py:130-180
# 8 separate DB queries on EVERY page load!
playlists_result = await session.execute(playlists_stmt)
tracks_result = await session.execute(tracks_with_files_stmt)
# ... 6 more queries
```

**Solution A: StatsService with TTL Cache**
```python
# src/soulspot/application/services/stats_service.py

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

@dataclass
class DashboardStats:
    playlist_count: int
    tracks_downloaded: int
    total_tracks: int
    completed_downloads: int
    queue_size: int
    active_downloads: int
    spotify_artists: int
    spotify_albums: int
    spotify_tracks: int
    cached_at: datetime
    
    @property
    def is_stale(self) -> bool:
        """Check if stats are older than 60 seconds."""
        return datetime.now() - self.cached_at > timedelta(seconds=60)

class StatsService:
    """Service for aggregated statistics with caching.
    
    Hey future me - this caches dashboard stats to reduce DB load!
    Stats are refreshed every 60 seconds (configurable).
    """
    
    def __init__(
        self,
        session: AsyncSession,
        cache_ttl_seconds: int = 60,
    ):
        self._session = session
        self._cache_ttl = cache_ttl_seconds
        self._cached_stats: DashboardStats | None = None
    
    async def get_dashboard_stats(self, force_refresh: bool = False) -> DashboardStats:
        """Get dashboard stats with caching.
        
        Args:
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            DashboardStats with all counts
        """
        if not force_refresh and self._cached_stats and not self._cached_stats.is_stale:
            return self._cached_stats
        
        # Single optimized query using CTEs or UNION ALL
        # This is 1 round-trip instead of 8!
        stats = await self._fetch_all_stats()
        self._cached_stats = stats
        return stats
    
    async def _fetch_all_stats(self) -> DashboardStats:
        """Fetch all stats in a single optimized query."""
        from sqlalchemy import func, select, union_all
        from soulspot.infrastructure.persistence.models import (
            DownloadModel, PlaylistModel, TrackModel, PlaylistTrackModel
        )
        
        # Option 1: Multiple counts in one query
        stmt = select(
            func.count(PlaylistModel.id).label("playlists"),
        ).select_from(PlaylistModel)
        
        # ... build combined query ...
        
        # For simplicity, we can still do multiple queries but in parallel:
        import asyncio
        
        results = await asyncio.gather(
            self._count_playlists(),
            self._count_tracks_with_files(),
            self._count_total_playlist_tracks(),
            self._count_completed_downloads(),
            self._count_queue_size(),
            self._count_active_downloads(),
        )
        
        return DashboardStats(
            playlist_count=results[0],
            tracks_downloaded=results[1],
            total_tracks=results[2],
            completed_downloads=results[3],
            queue_size=results[4],
            active_downloads=results[5],
            spotify_artists=0,  # TODO: Add spotify counts
            spotify_albums=0,
            spotify_tracks=0,
            cached_at=datetime.now(),
        )
```

**Solution B: WebSocket for Real-Time Updates (Future)**
For truly dynamic dashboards, implement SSE or WebSocket to push stats changes.
This is Phase 3 material.

**Files to modify:**
- Create `src/soulspot/application/services/stats_service.py`
- Update `src/soulspot/api/routers/ui.py` to use StatsService
- Add dependency injection for StatsService

**✅ IMPLEMENTED (Jan 2025):**
- Created `StatsService` with `_dashboard_cache` and `_cache_expires` class variables
- Added `get_dashboard_stats()` with 60s TTL caching
- Parallel queries via `asyncio.gather()` for fast refresh
- Cache returns stale data instantly, refresh happens in background

---

### 2.2 Persistent Sync Status ⭐⭐⭐ ✅
**Impact:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW

**Current Problem:**
```python
# src/soulspot/application/services/spotify_sync_service.py
# src/soulspot/application/services/deezer_sync_service.py
self._last_sync_times: dict[str, datetime] = {}  # In-memory! Lost on restart!
```

**Issue:** After container restart, all sync cooldowns reset → immediate API spam.

**Solution: Use app_settings Table**
```python
# Add to app_settings_service.py

async def get_last_sync_time(self, sync_type: str) -> datetime | None:
    """Get last sync time for a sync type from persistent storage.
    
    Args:
        sync_type: e.g., "spotify.artists", "deezer.charts"
        
    Returns:
        Last sync datetime (UTC) or None if never synced
    """
    key = f"sync.{sync_type}.last_run"
    value = await self.get_string(key, default=None)
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None

async def set_last_sync_time(self, sync_type: str, time: datetime | None = None) -> None:
    """Set last sync time for a sync type.
    
    Args:
        sync_type: e.g., "spotify.artists"
        time: Sync time (UTC). Defaults to now.
    """
    key = f"sync.{sync_type}.last_run"
    sync_time = time or datetime.now(UTC)
    await self.set_string(key, sync_time.isoformat())

# Update sync services to use persistent storage:
class SpotifySyncService:
    async def _should_sync(self, sync_type: str, cooldown_minutes: int) -> bool:
        """Check if sync should run based on cooldown (PERSISTENT!)."""
        last_sync = await self._settings_service.get_last_sync_time(
            f"spotify.{sync_type}"
        )
        if not last_sync:
            return True
        
        elapsed = (datetime.now(UTC) - last_sync).total_seconds() / 60
        return elapsed >= cooldown_minutes
    
    async def _mark_synced(self, sync_type: str) -> None:
        """Mark sync as completed (PERSISTENT!)."""
        await self._settings_service.set_last_sync_time(f"spotify.{sync_type}")
```

**Migration Consideration:**
- Existing in-memory cache can remain as L1 cache
- DB lookup only when in-memory cache misses
- This is a performance optimization, not required

**Files to modify:**
- `src/soulspot/application/services/app_settings_service.py`
- `src/soulspot/application/services/spotify_sync_service.py`
- `src/soulspot/application/services/deezer_sync_service.py`

**✅ IMPLEMENTED (Jan 2025):**
- Added `get_datetime()`, `set_datetime()`, `get_last_sync_time()`, `set_last_sync_time()` to AppSettingsService
- Refactored SpotifySyncService `_should_sync()` and `_mark_synced()` to async with DB persistence
- L1 cache (in-memory) + L2 cache (DB) pattern implemented
- Sync times now survive container restarts!
- Keys stored as `sync.spotify.{sync_type}.last_run` in app_settings table

---

## Phase 3: Technical Debt & Maintainability (Week 5-6)

### 3.1 Remove Legacy SpotifyBrowseRepository ⭐⭐⭐ ✅
**Impact:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW

**Status:** ✅ COMPLETE (January 2026)

**Original Problem:**
```python
# SpotifyBrowseRepository was the old name before multi-provider support
# Created November 2025: ProviderBrowseRepository (unified tables with source filter)
# Problem: 44+ code references still using old SpotifyBrowseRepository name
```

**Migration Strategy:**
1. **Two-Layer Backwards Compatibility** (during transition):
   - Class alias in `repositories.py`: `SpotifyBrowseRepository = ProviderBrowseRepository`
   - Dependency function alias in `dependencies.py`: `get_spotify_browse_repository()` → `get_provider_browse_repository()`

2. **Systematic File-by-File Migration** (completed Jan 2026):
   - Updated all imports from `SpotifyBrowseRepository` → `ProviderBrowseRepository`
   - Changed type hints in function signatures
   - Renamed parameters: `spotify_repository` → `provider_repository`
   - Added multi-provider architecture comments throughout

**Files Modified:**
- `src/soulspot/api/dependencies.py` - Dependency injection functions
- `src/soulspot/api/routers/ui/dashboard.py` - Dashboard statistics
- `src/soulspot/api/routers/stats.py` - Stats API endpoints
- `src/soulspot/api/routers/settings.py` - Database stats endpoint
- `src/soulspot/application/services/stats_service.py` - Stats service
- `src/soulspot/application/services/library_view_service.py` - View service
- `src/soulspot/infrastructure/persistence/repositories.py` - Repository definitions

**Implementation Example:**
```python
# Before:
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

async def get_dashboard(
    spotify_repository: SpotifyBrowseRepository = Depends(get_spotify_browse_repository)
):
    artist_count = await spotify_repository.count_artists()

# After:
from soulspot.infrastructure.persistence.repositories import ProviderBrowseRepository

async def get_dashboard(
    provider_repository: ProviderBrowseRepository = Depends(get_provider_browse_repository)
):
    # Multi-provider: filters by source='spotify' by default, extensible to Deezer/Tidal
    artist_count = await provider_repository.count_artists()
```

**Architecture Notes:**
- `ProviderBrowseRepository` uses unified tables (ArtistModel, AlbumModel, TrackModel)
- Filters by `source` field: 'spotify', 'deezer', 'tidal', etc.
- All methods accept optional `source` parameter for multi-provider queries
- Fully backwards compatible via filtering (source='spotify' by default)

**Verification Results:**
- ✅ All 44+ code references migrated to new name
- ✅ Workers already using new name (verified separately)
- ✅ Services already using new name (spotify_sync_service, discography_service)
- ✅ No active runtime imports of old name (only compatibility aliases remain)
- ✅ Multi-provider comments added throughout

**Post-Migration Cleanup (Optional):**
After production validation period, consider removing compatibility aliases:
1. Remove `SpotifyBrowseRepository = ProviderBrowseRepository` from repositories.py (line 6146)
2. Remove `get_spotify_browse_repository()` function from dependencies.py (lines 714-723)

---

### 3.2 Deprecated Code Cleanup ⭐⭐ ✅
**Impact:** LOW | **Effort:** LOW | **Risk:** LOW

**Files to clean:**
1. `src/soulspot/application/workers/__init__.py` - Remove deprecated exports
2. `src/soulspot/templates/includes/_theme.html` - Delete or convert to redirect
3. `src/soulspot/application/services/deezer_sync_service.py` - Remove `sync_charts()` method
4. `src/soulspot/api/routers/library/scan.py` - Remove deprecated endpoints or add redirect

**Action:**
```python
# Option A: Delete deprecated code entirely
# Option B: Add deprecation warnings that log usage

import warnings

@deprecated("Use /import/scan instead. Will be removed in v2.0")
async def start_scan(...):
    warnings.warn(
        "start_scan is deprecated, use import_scan instead",
        DeprecationWarning,
        stacklevel=2
    )
    return await import_scan(...)
```

**✅ VERIFIED (Jan 2025):**
All deprecated code is already properly handled:
- `workers/__init__.py`: Deprecated exports commented out with clear comments
- `_theme.html`: Contains DEPRECATED comment, kept for backward compatibility
- `sync_charts()`: Returns deprecated warning dict, doesn't write to DB
- `sync_new_releases()`: Returns deprecated warning dict, doesn't write to DB
- `library/scan.py`: Deprecated endpoints redirect to new endpoints

**Decision:** Keep deprecated code with warnings rather than breaking existing clients.
This is proper deprecation practice - remove in next major version.
```

---

### 3.3 Split ui.py Router ✅ COMPLETE
**Impact:** LOW (maintainability) | **Effort:** HIGH | **Risk:** MEDIUM

**Status:** ✅ IMPLEMENTED (December 2025)

**Original Problem:** `ui.py` had 3400+ lines - difficult to navigate and maintain.

**Implemented Structure:**
```
src/soulspot/api/routers/ui/
├── __init__.py              # Re-exports all routers
├── _shared.py               # Shared utilities (templates, helpers)
├── dashboard.py             # /, /dashboard, /playlists/*, /styleguide, /auth, /onboarding
├── downloads.py             # /downloads, /download-manager, /download-center
├── search.py                # /search, /search/quick
├── library_core.py          # /library, /library/stats-partial, /library/import
├── library_browse.py        # /library/artists, /library/albums, /library/tracks, /library/compilations
├── library_detail.py        # /library/artists/{name}, /library/albums/{key}, /tracks/{id}/metadata-editor
├── library_maintenance.py   # /library/duplicates, /library/broken-files, /library/incomplete-albums
└── spotify_browse.py        # /browse/new-releases, /spotify/discover, deprecated routes
```

**Result:**
- 3400-line monolith → 9 focused modules (~300-900 lines each)
- Clear separation of concerns
- Easier navigation and maintenance
- Python prefers ui/ package over ui.py module

---

## Implementation Timeline

```
Week 1: Phase 1.1 + 1.2 (Parallel imports + File completion) - ✅ COMPLETE (Jan 2025)
Week 2: Phase 1.3 (Error recovery) + Testing - ✅ COMPLETE (Jan 2025)
Week 3: Phase 2.1 (Stats caching) - ✅ COMPLETE (Jan 2025)
Week 4: Phase 2.2 (Persistent sync status) - ✅ COMPLETE (Jan 2025)
Week 5: Phase 3.1 + 3.2 (Legacy cleanup) - ✅ COMPLETE (Jan 2026)
Week 6: Phase 3.3 (Split ui.py) - ✅ COMPLETE (Dec 2025)
```

**All phases complete! 🎉**

---

## Success Metrics

| Metric | Before | Target | How to Measure |
|--------|--------|--------|----------------|
| 100-file import time | 200-500s | 40-100s | Time auto-import batch |
| Dashboard load queries | 8 | 1-2 | SQLAlchemy logging |
| Post-restart sync spam | All syncs run | Respects cooldowns | Log analysis |
| Partial track syncs | Silent failures | Logged + stats | Check stats.albums_with_track_errors |

---

## Dependencies

```
1.1 Parallel Processing ──────┐
1.2 File Completion ──────────┼── Can be done in parallel
1.3 Error Recovery ───────────┘

2.1 Stats Caching ────────────── Standalone
2.2 Persistent Sync Status ───── Requires AppSettingsService update

3.1 Legacy Repo Removal ──────┬── Sequential (3.1 before 3.2)
3.2 Deprecated Cleanup ───────┘
3.3 Split ui.py ──────────────── ✅ COMPLETE (Dec 2025)
```

---

## Notes

- All changes should follow existing patterns (async/await, repository pattern, etc.)
- Add tests for each change before merging
- Update documentation in `docs/` as needed
- Consider feature flags for risky changes
