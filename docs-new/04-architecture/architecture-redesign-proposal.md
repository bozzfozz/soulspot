# Architecture Redesign Proposal

**Category:** Architecture (Planning)  
**Status:** PROPOSAL  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Core Philosophy](./core-philosophy.md) | [Data Layer Patterns](./data-layer-patterns.md)

---

## Executive Summary

**Problem:** SoulSpot implements Clean Architecture but has grown to 100+ files with "god files" (repositories.py: 6418 LOC, services: 3100 LOC) despite architectural principles.

**Proposal:** Pragmatic Clean Architecture with 3 layers instead of 4, reducing from 100+ files to ~40 files while maintaining 100% functionality.

**Impact:**

| Metric | Current | Proposed | Improvement |
|--------|---------|----------|-------------|
| **Files** | 100+ | ~40 | -60% |
| **Services** | 40+ | 8-10 | -75% |
| **Workers** | 18 | 1 + Handlers | -90% |
| **LOC** | ~20,000 | ~8,000 | -60% |
| **Functionality** | 100% | 100% | ±0% |

---

## Problem Analysis

### Current Issues

#### 1. God Files (Despite Architecture!)

| File | LOC | Problem |
|------|-----|---------|
| `repositories.py` | 6,418 | All 15+ repos in one file |
| `local_library_enrichment_service.py` | 3,100 | 20+ methods in single service |
| `ports/__init__.py` | 1,678 | All interfaces together |
| `dependencies.py` | 1,244 | Massive DI configuration |
| `entities/__init__.py` | 1,125 | All entities together |

**Why this happened:** Strict layer separation led to many small files that got merged or ballooned.

---

#### 2. Service Proliferation

```
application/services/
├── 40+ service files
├── Many with <200 LOC (too granular)
├── Overlapping responsibilities
├── Unclear separation: Service vs Use Case
└── No clear feature grouping
```

**Examples:**
- `playlist_service.py` - Basic playlist operations
- `spotify_playlist_service.py` - Spotify-specific playlists
- `deezer_playlist_service.py` - Deezer-specific playlists
- **Problem:** Should be ONE `playlist.py` service with provider injection

---

#### 3. Worker Chaos

```
application/workers/
├── download_worker.py
├── download_monitor_worker.py       # Overlap!
├── download_status_sync_worker.py   # Overlap!
├── queue_dispatcher_worker.py       # Overlap!
├── library_enrichment_worker.py     # DEPRECATED
├── library_discovery_worker.py      # Replaced enrichment
└── ... 12 more workers
```

**Problem:** 18 workers with overlapping responsibilities when a unified job scheduler could handle all.

---

#### 4. Layer Violations (~40 places!)

```python
# ❌ Application imports Infrastructure directly
from soulspot.infrastructure.persistence.models import AlbumModel
from soulspot.infrastructure.persistence.repositories import ArtistRepository

# ❌ API imports Infrastructure directly
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
```

**Why:** Dependency Injection configuration became too complex, leading to shortcuts.

---

## Proposed Architecture

### Design Principles

1. **YAGNI (You Ain't Gonna Need It)**
   - Abstractions only where truly needed
   - No speculative "future-proofing"

2. **Single Responsibility - But Pragmatic**
   - One service file per feature area (not per method)
   - File size limit: ~500 LOC

3. **Ports Only for External Services**
   - Interfaces only for external APIs (Spotify, Deezer, slskd)
   - No internal interfaces without clear multi-implementation need

4. **Consolidate Related Functionality**
   - Group by feature, not by layer granularity

---

### 3-Layer Structure

```
┌─────────────────────────────────────────────────────┐
│                    API Layer                         │
│  FastAPI Routes, Dependencies, Request/Response     │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                   Core Layer                         │
│  Services, Jobs, Models, Ports (external only)      │
│  = Former: Domain + Application merged              │
└─────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Providers  │  │   Storage   │  │     UI      │
│  Spotify    │  │  Database   │  │  Templates  │
│  Deezer     │  │  Repos      │  │  Static     │
│  slskd      │  │  Models     │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

**Key Changes:**
- **Merge Domain + Application** → Core (they're always changed together)
- **Keep clear external boundaries** → Providers, Storage remain separate
- **Simplify DI** → Fewer abstractions = simpler dependencies

---

### Proposed Directory Structure

```
src/soulspot/
│
├── 📁 core/                          # Business Logic (~3,500 LOC total)
│   ├── 📄 models.py                  # ~500 LOC - Entities, DTOs, Enums
│   ├── 📄 exceptions.py              # ~200 LOC - Domain exceptions
│   │
│   ├── 📁 ports/                     # External service interfaces ONLY
│   │   ├── 📄 music_provider.py      # ~150 LOC - IMusicProvider
│   │   └── 📄 download_provider.py   # ~100 LOC - IDownloadProvider
│   │
│   ├── 📁 services/                  # Feature-based services
│   │   ├── 📄 library.py             # ~500 LOC - scan, stats, duplicates
│   │   ├── 📄 enrichment.py          # ~600 LOC - enrich artists/albums/tracks
│   │   ├── 📄 download.py            # ~400 LOC - enqueue, process, import
│   │   ├── 📄 playlist.py            # ~300 LOC - sync, manage playlists
│   │   ├── 📄 discovery.py           # ~400 LOC - browse, search, recommend
│   │   ├── 📄 sync.py                # ~400 LOC - sync Spotify/Deezer data
│   │   ├── 📄 auth.py                # ~300 LOC - OAuth flows
│   │   └── 📄 settings.py            # ~200 LOC - app settings
│   │
│   └── 📁 jobs/                      # Unified background system
│       ├── 📄 scheduler.py           # ~200 LOC - JobScheduler class
│       └── 📄 handlers.py            # ~400 LOC - Job handlers
│
├── 📁 providers/                     # External service implementations
│   ├── 📁 spotify/
│   │   ├── 📄 client.py              # ~400 LOC - HTTP client
│   │   └── 📄 plugin.py              # ~300 LOC - IMusicProvider impl
│   ├── 📁 deezer/
│   │   ├── 📄 client.py              # ~300 LOC
│   │   └── 📄 plugin.py              # ~250 LOC
│   └── 📁 slskd/
│       ├── 📄 client.py              # ~300 LOC
│       └── 📄 plugin.py              # ~150 LOC
│
├── 📁 storage/                       # Persistence layer
│   ├── 📄 database.py                # ~100 LOC - Engine + Session factory
│   ├── 📄 models.py                  # ~500 LOC - SQLAlchemy models
│   └── 📁 repositories/              # Split by entity
│       ├── 📄 artist.py              # ~150 LOC each
│       ├── 📄 album.py
│       ├── 📄 track.py
│       ├── 📄 playlist.py
│       └── 📄 download.py
│
└── 📁 api/                           # FastAPI layer
    ├── 📄 main.py                    # ~100 LOC - App factory
    ├── 📄 dependencies.py            # ~200 LOC (from 1244!)
    └── 📁 routes/
        ├── 📄 library.py             # ~300 LOC
        ├── 📄 downloads.py           # ~250 LOC
        ├── 📄 playlists.py           # ~200 LOC
        ├── 📄 discovery.py           # ~250 LOC
        └── 📄 settings.py            # ~150 LOC
```

**Total:** ~40 files instead of 100+

---

## Service Consolidation Examples

### Before (Fragmented)

```
application/services/
├── playlist_service.py                    # 250 LOC
├── spotify_playlist_service.py            # 180 LOC
├── deezer_playlist_service.py             # 150 LOC
├── playlist_sync_service.py               # 200 LOC
└── local_playlist_service.py              # 120 LOC
Total: 5 files, 900 LOC
```

### After (Consolidated)

```python
# core/services/playlist.py - 300 LOC

class PlaylistService:
    """Unified playlist service for all providers."""
    
    def __init__(
        self,
        spotify_plugin: SpotifyPlugin,
        deezer_plugin: DeezerPlugin,
        playlist_repo: PlaylistRepository,
    ):
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin
        self._repo = playlist_repo
    
    async def sync_playlists(self, provider: str) -> dict[str, int]:
        """Sync playlists from specified provider."""
        if provider == "spotify":
            return await self._sync_spotify()
        elif provider == "deezer":
            return await self._sync_deezer()
        ...
    
    async def _sync_spotify(self) -> dict[str, int]:
        """Spotify-specific sync logic."""
        ...
    
    async def _sync_deezer(self) -> dict[str, int]:
        """Deezer-specific sync logic."""
        ...
```

**Result:** 1 file, 300 LOC (from 5 files, 900 LOC)

---

## Worker Consolidation

### Before (18 Workers)

```
application/workers/
├── download_worker.py
├── download_monitor_worker.py
├── download_status_sync_worker.py
├── queue_dispatcher_worker.py
├── spotify_sync_worker.py
├── playlist_sync_worker.py
├── token_refresh_worker.py
├── library_enrichment_worker.py
├── library_discovery_worker.py
├── watchlist_worker.py
├── discography_worker.py
├── new_releases_worker.py
├── auto_import_worker.py
├── quality_upgrade_worker.py
├── cleanup_worker.py
└── ... 3 more
```

### After (1 Scheduler + Handlers)

```python
# core/jobs/scheduler.py - Unified job scheduler

class JobScheduler:
    """Single scheduler for all background jobs."""
    
    async def schedule_periodic_jobs(self):
        """Schedule all periodic tasks."""
        self.add_job(handle_token_refresh, interval=300)     # 5 min
        self.add_job(handle_spotify_sync, interval=1800)     # 30 min
        self.add_job(handle_download_status, interval=60)    # 1 min
        self.add_job(handle_cleanup, cron="0 3 * * *")       # Daily 3am
        ...

# core/jobs/handlers.py - Job handler functions

async def handle_token_refresh():
    """Refresh OAuth tokens."""
    ...

async def handle_spotify_sync():
    """Sync Spotify data."""
    ...

async def handle_download_status():
    """Check download status."""
    ...
```

**Result:** 1 scheduler + 1 handlers file (from 18 worker files)

---

## Migration Strategy

### Phase 1: Proof of Concept (1 week)

**Goal:** Demonstrate new structure with ONE feature

1. **Choose:** Library feature (scan, stats, duplicates)
2. **Create:** `core/services/library.py`
3. **Migrate:** Existing library services → New consolidated service
4. **Test:** Verify functionality unchanged
5. **Measure:** LOC reduction, complexity metrics

**Success Criteria:**
- ✅ Feature works identically
- ✅ <500 LOC per file
- ✅ No layer violations
- ✅ Tests pass

---

### Phase 2: Incremental Migration (4-6 weeks)

**Approach:** Feature-by-feature migration

| Week | Feature | Files Created | Files Removed |
|------|---------|---------------|---------------|
| 1 | Library | `core/services/library.py` | 3 service files |
| 2 | Download | `core/services/download.py` | 5 service files |
| 3 | Playlist | `core/services/playlist.py` | 4 service files |
| 4 | Discovery | `core/services/discovery.py` | 3 service files |
| 5 | Workers | `core/jobs/*` | 18 worker files |
| 6 | Cleanup | Repository split | `repositories.py` |

**Key Rule:** Never break existing functionality. Run tests after each migration.

---

### Phase 3: Optimization (2 weeks)

1. **Remove dead code** - Unused services, deprecated methods
2. **Extract common patterns** - Base classes, utilities
3. **Update documentation** - Architecture docs, API docs
4. **Performance testing** - Ensure no regressions

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Breaking changes** | HIGH | Feature flags, parallel implementations |
| **Lost functionality** | HIGH | Comprehensive test suite before starting |
| **Developer confusion** | MED | Clear migration guide, pair programming |
| **Performance regression** | MED | Benchmark before/after each phase |
| **Scope creep** | MED | Strict "no new features during refactor" rule |

---

## What NOT to Change

**Keep these patterns (they work well):**

1. ✅ **Plugin system** - Elegant and extensible
2. ✅ **Domain entities** - Clean, pure business objects
3. ✅ **Error handling** - Professional with correlation IDs
4. ✅ **Structured logging** - JSON-based with context
5. ✅ **Database models** - SQLAlchemy setup is solid
6. ✅ **OAuth flows** - Working authentication

**Only consolidate, don't redesign these.**

---

## Success Metrics

**Before starting:**
- Measure: Files, LOC, cyclomatic complexity, test coverage
- Benchmark: API response times, worker execution times

**After each phase:**
- ✅ All tests pass
- ✅ API response times within 5% of baseline
- ✅ No increase in error rates
- ✅ LOC reduced by target percentage
- ✅ Developer productivity improved (measured by feature completion time)

---

## Decision Points

**Should we proceed?**

### YES if:
- Team agrees codebase is hard to navigate
- Onboarding new developers is slow
- File navigation is painful (too many files)
- Willing to pause new features for 6-8 weeks

### NO if:
- Current architecture is working fine
- Team is small and already knows codebase well
- Urgent features needed soon
- Risk tolerance is low

---

## Related Documentation

- **[Core Philosophy](./core-philosophy.md)** - Core architectural principles
- **[Data Layer Patterns](./data-layer-patterns.md)** - Current patterns to preserve
- **[Worker Patterns](./worker-patterns.md)** - Current worker architecture

---

**Status:** PROPOSAL - Awaiting team discussion and decision  
**Next Steps:** Review with team → Go/No-Go decision → POC (if approved)
