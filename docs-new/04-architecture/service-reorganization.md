# Service Reorganization Plan

**Category:** Architecture  
**Status:** PARTIALLY IMPLEMENTED 🔄  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Service Separation Plan](./service-separation-plan.md) | [Service Separation Principles](./service-separation-principles.md)

---

## Overview

The `application/services/` directory has **43 loose files** - too many for maintainability. This plan reorganizes services into feature-based subdirectories following single responsibility principle.

**Goal:** Reduce cognitive load, improve discoverability, enforce domain boundaries.

---

## Current Problem

```
services/
├── __init__.py
├── advanced_search.py
├── album_completeness.py
├── album_sync_service.py
├── app_settings_service.py
├── artist_songs_service.py
├── artwork_service.py           ← DEPRECATED (migrated to images/)
├── auto_import.py
├── automation_workflow_service.py
├── batch_processor.py
├── charts_service.py
├── ... (43 files total!)
```

**Issues:**
- Hard to find related services (scanning 43 files)
- No clear domain boundaries (sync vs library vs automation)
- Feature evolution adds more files instead of organizing existing ones

---

## ✅ Completed: ImageService Migration (January 2025)

**Status:** COMPLETE ✅

### What Was Done

1. **Created `services/images/` directory**
   - `image_service.py` - Central service for all image operations
   - `downloader.py` - Download logic with HTTP client pooling
   - `cache.py` - Cache management and optimization
   - `artwork_service.py` - **DEPRECATED** (legacy, can be deleted)

2. **Interface Definition**
   - `domain/ports/image_service.py` - `IImageService` interface
   - Exports added to `services/__init__.py`

3. **Full Migration Complete**
   - ✅ `SpotifySyncService` migrated to `ImageService`
   - ✅ `SpotifySyncWorker` migrated to `ImageService`
   - ✅ `LocalLibraryEnrichmentService` migrated to `ImageService`
   - ✅ `EnrichmentService` migrated to `ImageService`
   - ✅ Settings endpoints migrated to `ImageService`
   - ✅ Library endpoints migrated to `ImageService`

4. **Next Steps**
   - [ ] Delete `artwork_service.py` (no more consumers)
   - [ ] Remove deprecated imports from `__init__.py`

---

### ImageService Usage

```python
from soulspot.application.services.images import (
    ImageService,
    ImageDownloadErrorCode,
    ImageDownloadResult,
)

# For templates (sync)
image_service = ImageService()
url = image_service.get_display_url(source_url, local_path, "artist")

# For downloads (provider-based) - defaults to "spotify"
path = await image_service.download_artist_image(spotify_id, url)

# For other providers
path = await image_service.download_artist_image(deezer_id, url, provider="deezer")
path = await image_service.download_album_image(mbid, url, provider="musicbrainz")

# For batch operations with error tracking
result = await image_service.download_artist_image_with_result(id, url, provider="deezer")
if result.success:
    print(f"Saved to: {result.path}")  # e.g., "artists/deezer/123456.webp"
else:
    print(f"Error: {result.error_code} - {result.error_message}")

# For multi-provider entities (BEST IMAGE FROM ANY PROVIDER)
url = image_service.get_best_image(
    entity_type="artist",
    provider_ids={
        "spotify": "1dfeR4HaWDbWqFHLkxsg1d",
        "deezer": "123456",
        "musicbrainz": "abc-def-ghi",
    },
    fallback_url="https://i.scdn.co/image/..."  # Optional CDN fallback
)
# Returns best available: spotify → deezer → tidal → musicbrainz → fallback → placeholder
```

**Supported Providers (Priority Order):**
1. `spotify` (default) → `artists/spotify/{spotify_id}.webp`
2. `deezer` → `artists/deezer/{deezer_id}.webp`
3. `tidal` → `artists/tidal/{tidal_id}.webp`
4. `musicbrainz` → `artists/musicbrainz/{mbid}.webp`

---

## Proposed Target Structure

```
services/
├── __init__.py                    # Re-exports for backward compatibility
│
├── core/                          # Core services (always needed)
│   ├── __init__.py
│   ├── settings_service.py        # app_settings_service.py
│   ├── credentials_service.py
│   ├── session_store.py
│   └── token_manager.py
│
├── sync/                          # Provider sync (Spotify, Deezer, etc.)
│   ├── __init__.py
│   ├── spotify/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # spotify_auth_service.py
│   │   ├── sync_service.py        # spotify_sync_service.py
│   │   └── session_service.py
│   ├── deezer/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # deezer_auth_service.py
│   │   └── sync_service.py        # deezer_sync_service.py
│   └── orchestrator.py            # provider_sync_orchestrator.py
│
├── images/                        # Image handling ✅ COMPLETE
│   ├── __init__.py
│   ├── image_service.py           # Central service
│   ├── downloader.py              # Download logic
│   ├── cache.py                   # Cache management
│   └── artwork_service.py         # Legacy (deprecated)
│
├── library/                       # Local library
│   ├── __init__.py
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── scanner_service.py     # library_scanner_service.py
│   │   ├── file_discovery.py      # file_discovery_service.py
│   │   └── scanner.py             # library_scanner.py
│   ├── view_service.py            # library_view_service.py
│   ├── cleanup_service.py         # library_cleanup_service.py
│   └── enrichment_service.py      # local_library_enrichment_service.py
│
├── automation/                    # Automation workflows
│   ├── __init__.py
│   ├── watchlist_service.py
│   ├── filter_service.py
│   ├── workflow_service.py        # automation_workflow_service.py
│   ├── auto_import.py
│   └── quality_upgrade_service.py
│
├── downloads/                     # Download management
│   ├── __init__.py
│   ├── manager_service.py         # download_manager_service.py
│   ├── batch_processor.py
│   └── postprocessing/            # Already a subdirectory
│       ├── __init__.py
│       ├── metadata_service.py
│       └── audio_processor.py
│
├── discovery/                     # Discovery features
│   ├── __init__.py
│   ├── discover_service.py
│   ├── new_releases_service.py
│   ├── charts_service.py
│   └── advanced_search.py
│
├── enrichment/                    # Metadata enrichment
│   ├── __init__.py
│   ├── enrichment_service.py
│   ├── candidate_service.py
│   ├── album_completeness.py
│   └── discography_service.py
│
└── playlist/                      # Playlist operations
    ├── __init__.py
    ├── playlist_service.py
    ├── compilation_service.py
    └── blocklist_service.py
```

---

## Migration Strategy

### Phase 1: Core Services (1-2 days)

**Objective:** Extract always-needed infrastructure services.

```bash
mkdir -p src/soulspot/application/services/core
mv app_settings_service.py core/settings_service.py
mv credentials_service.py core/
mv session_store.py core/
mv token_manager.py core/
```

**Update imports:**
```python
# Before
from soulspot.application.services.app_settings_service import AppSettingsService

# After
from soulspot.application.services.core import AppSettingsService
```

**Backward compatibility:**
```python
# services/__init__.py
from .core.settings_service import AppSettingsService
__all__ = ["AppSettingsService", ...]
```

---

### Phase 2: Provider Sync (2-3 days)

**Objective:** Group Spotify/Deezer sync services.

```bash
mkdir -p src/soulspot/application/services/sync/spotify
mkdir -p src/soulspot/application/services/sync/deezer

mv spotify_auth_service.py sync/spotify/auth_service.py
mv spotify_sync_service.py sync/spotify/sync_service.py
mv spotify_session_service.py sync/spotify/session_service.py

mv deezer_auth_service.py sync/deezer/auth_service.py
mv deezer_sync_service.py sync/deezer/sync_service.py

mv provider_sync_orchestrator.py sync/orchestrator.py
```

**Namespace organization:**
```python
# sync/spotify/__init__.py
from .auth_service import SpotifyAuthService
from .sync_service import SpotifySyncService
from .session_service import SpotifySessionService

__all__ = ["SpotifyAuthService", "SpotifySyncService", "SpotifySessionService"]
```

---

### Phase 3: Library Services (2-3 days)

**Objective:** Consolidate local library operations.

```bash
mkdir -p src/soulspot/application/services/library/scanner

mv library_scanner_service.py library/scanner/scanner_service.py
mv file_discovery_service.py library/scanner/file_discovery.py
mv library_scanner.py library/scanner/scanner.py

mv library_view_service.py library/view_service.py
mv library_cleanup_service.py library/cleanup_service.py
mv local_library_enrichment_service.py library/enrichment_service.py
```

---

### Phase 4: Automation (1-2 days)

**Objective:** Group automation workflows.

```bash
mkdir -p src/soulspot/application/services/automation

mv watchlist_service.py automation/
mv filter_service.py automation/
mv automation_workflow_service.py automation/workflow_service.py
mv auto_import.py automation/
mv quality_upgrade_service.py automation/
```

---

### Phase 5: Downloads (1-2 days)

**Objective:** Consolidate download management.

```bash
mkdir -p src/soulspot/application/services/downloads

mv download_manager_service.py downloads/manager_service.py
mv batch_processor.py downloads/
# postprocessing/ already exists as subdirectory
mv postprocessing/ downloads/
```

---

### Phase 6: Discovery & Enrichment (1-2 days)

**Objective:** Separate discovery features and enrichment.

```bash
mkdir -p src/soulspot/application/services/discovery
mkdir -p src/soulspot/application/services/enrichment

mv discover_service.py discovery/
mv new_releases_service.py discovery/
mv charts_service.py discovery/
mv advanced_search.py discovery/

mv enrichment_service.py enrichment/
mv candidate_service.py enrichment/
mv album_completeness.py enrichment/
mv discography_service.py enrichment/
```

---

### Phase 7: Cleanup & Testing (2-3 days)

1. **Remove deprecated code:**
   ```bash
   rm services/artwork_service.py  # Fully migrated to images/
   ```

2. **Update all imports:**
   - Use automated refactoring tools (e.g., `rope`, `bowler`)
   - Update tests to use new import paths

3. **Verify backward compatibility:**
   ```python
   # services/__init__.py - All old imports still work
   from .core.settings_service import AppSettingsService
   from .sync.spotify import SpotifySyncService
   from .images.image_service import ImageService
   # ... etc.
   ```

4. **Run full test suite:**
   ```bash
   pytest tests/ -v
   mypy src/
   ruff check src/
   ```

---

## Benefits

### Before (43 Files)
```
services/
├── advanced_search.py
├── album_completeness.py
├── album_sync_service.py
├── app_settings_service.py
├── ... (39 more files)
```

**Problems:**
- Finding related services: scan 43 files
- Understanding domain boundaries: unclear
- Adding new service: where does it go?

---

### After (7 Directories)
```
services/
├── core/           # 4 files - core infrastructure
├── sync/           # 7 files - provider sync
├── images/         # 3 files - image handling ✅
├── library/        # 6 files - local library
├── automation/     # 5 files - automation workflows
├── downloads/      # 3 files + postprocessing/
├── discovery/      # 4 files - discovery features
├── enrichment/     # 4 files - metadata enrichment
└── playlist/       # 3 files - playlist operations
```

**Benefits:**
- Finding services: Check relevant directory (5-7 files max)
- Domain boundaries: Clear from directory structure
- Adding new service: Obvious placement by domain

---

## Backward Compatibility

**Critical:** All existing imports must continue to work.

```python
# services/__init__.py
"""
Re-exports for backward compatibility.
Old code can still import from services directly.
"""

# Core
from .core.settings_service import AppSettingsService
from .core.credentials_service import CredentialsService

# Sync
from .sync.spotify import SpotifySyncService
from .sync.deezer import DeezerSyncService
from .sync.orchestrator import ProviderSyncOrchestrator

# Images
from .images.image_service import ImageService

# Library
from .library.scanner import LibraryScannerService
from .library.view_service import LibraryViewService
from .library.cleanup_service import LibraryCleanupService

# ... all other services ...

__all__ = [
    "AppSettingsService",
    "SpotifySyncService",
    "ImageService",
    # ... all exports ...
]
```

**Old code still works:**
```python
# This still works after migration
from soulspot.application.services import SpotifySyncService
```

**New code uses organized structure:**
```python
# This is now preferred
from soulspot.application.services.sync.spotify import SpotifySyncService
```

---

## Migration Checklist

- [x] **Phase 0: ImageService** (COMPLETE ✅)
  - [x] Create `services/images/` directory
  - [x] Migrate all consumers to `ImageService`
  - [x] Deprecate `artwork_service.py`
  - [ ] Delete `artwork_service.py` (when ready)

- [ ] **Phase 1: Core Services**
  - [ ] Create `services/core/` directory
  - [ ] Move 4 core infrastructure services
  - [ ] Update imports (automated refactoring)
  - [ ] Add backward compatibility exports

- [ ] **Phase 2: Provider Sync**
  - [ ] Create `services/sync/spotify/` and `services/sync/deezer/`
  - [ ] Move Spotify services (3 files)
  - [ ] Move Deezer services (2 files)
  - [ ] Move orchestrator
  - [ ] Update imports

- [ ] **Phase 3: Library Services**
  - [ ] Create `services/library/scanner/`
  - [ ] Move scanner services (3 files)
  - [ ] Move view/cleanup/enrichment services (3 files)
  - [ ] Update imports

- [ ] **Phase 4-6: Remaining Domains**
  - [ ] Automation (5 files)
  - [ ] Downloads (3 files + postprocessing/)
  - [ ] Discovery (4 files)
  - [ ] Enrichment (4 files)
  - [ ] Playlist (3 files)

- [ ] **Phase 7: Cleanup**
  - [ ] Remove deprecated files
  - [ ] Run automated import updates
  - [ ] Verify backward compatibility
  - [ ] Full test suite pass
  - [ ] Update documentation

---

## Timeline

**Total Estimated Time:** 12-15 days (with testing)

| Phase | Duration | Risk |
|-------|----------|------|
| Phase 0: ImageService | DONE ✅ | - |
| Phase 1: Core | 1-2 days | Low (isolated) |
| Phase 2: Sync | 2-3 days | Medium (many consumers) |
| Phase 3: Library | 2-3 days | Medium (complex) |
| Phase 4: Automation | 1-2 days | Low |
| Phase 5: Downloads | 1-2 days | Low |
| Phase 6: Discovery/Enrichment | 1-2 days | Low |
| Phase 7: Cleanup/Testing | 2-3 days | High (validation) |

**Risk Mitigation:**
- Maintain backward compatibility throughout
- Migrate one phase at a time
- Run full test suite after each phase
- Keep old imports working via re-exports

---

## Related Documentation

- **[Service Separation Plan](./service-separation-plan.md)** - Service responsibility breakdown
- **[Service Separation Principles](./service-separation-principles.md)** - Architecture rules
- **[ImageService](./image-service.md)** - Example of successful migration

---

**Status:** 🔄 In Progress (ImageService complete, full reorganization optional)  
**Next Step:** Delete `artwork_service.py` when ready, then decide on full reorganization  
**Estimated ROI:** High - improves maintainability significantly, ~12-15 days investment
