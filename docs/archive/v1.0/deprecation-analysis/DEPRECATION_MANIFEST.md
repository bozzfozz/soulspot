# Deprecation Manifest - Files to Delete (Cloud Agent Task)

**Purpose:** List of deprecated files to be deleted by Cloud Agent after Phase 2 validation.

**⚠️ DO NOT DELETE IN VIRTUAL ENVIRONMENT!**

**Last Updated:** 2025-12-10

---

## Phase 2 Deletions (After Spotify Plugin Validated)

### **Files Marked for Deletion:**

#### **Infrastructure Layer (Spotify Client)**
```
src/soulspot/infrastructure/integrations/spotify_client.py
```
**Reason:** Moved to `src/soulspot/plugins/spotify/_client.py`  
**Status:** Deprecated in Phase 1, delete in Phase 2  
**Validation:** SpotifyPlugin tests pass, old imports no longer used

---

#### **Application Layer (Spotify Services)**
```
src/soulspot/application/services/spotify_sync_service.py
src/soulspot/application/services/spotify_image_service.py
```
**Reason:** Moved to `src/soulspot/plugins/spotify/_sync_service.py` and `_image_service.py`  
**Status:** Deprecated in Phase 1, delete in Phase 2  
**Validation:** SpotifyPlugin encapsulates all sync/image logic

---

#### **Application Layer (Spotify Cache)**
```
src/soulspot/application/cache/spotify_cache.py
```
**Reason:** Moved to `src/soulspot/plugins/spotify/_cache.py`  
**Status:** Deprecated in Phase 1, delete in Phase 2  
**Validation:** Plugin uses internal cache

---

#### **Workers (Spotify-Specific Worker)**
```
src/soulspot/application/workers/spotify_sync_worker.py
```
**Reason:** Replaced by generic `plugin_sync_worker.py` (works with ALL plugins)  
**Status:** Deprecated in Phase 1, delete in Phase 2  
**Validation:** `plugin_sync_worker.py` handles Spotify + Tidal + Deezer

---

#### **Tests (Old Spotify Tests)**
```
tests/unit/infrastructure/integrations/test_spotify_client.py
tests/unit/application/services/test_spotify_sync_service.py
tests/unit/application/services/test_spotify_image_service.py
tests/unit/application/cache/test_spotify_cache.py
tests/unit/application/workers/test_spotify_sync_worker.py
```
**Reason:** Replaced by plugin tests in `tests/unit/plugins/spotify/`  
**Status:** Deprecated in Phase 1, delete in Phase 2  
**Validation:** New plugin tests cover same functionality

---

#### **Integration Tests (Dual-Path Tests)**
```
tests/integration/migration/test_spotify_old_vs_new.py
```
**Reason:** Temporary test to validate migration equivalence  
**Status:** Delete after Phase 1 validation passes  
**Validation:** Old + new paths return identical results

---

## Deprecation Strategy (Phase 1)

### **Step 1: Add Deprecation Warnings**

**Example (`spotify_client.py`):**
```python
import warnings

warnings.warn(
    "SpotifyClient has moved to soulspot.plugins.spotify. "
    "This import path is deprecated and will be removed in v2.0. "
    "Use 'from soulspot.plugins.spotify import SpotifyPlugin' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Original code below (still works for now)
class SpotifyClient:
    ...
```

### **Step 2: Add TODO Comments for Cloud Agent**

**Example (`spotify_sync_service.py`):**
```python
# TODO(cloud-agent): DELETE THIS FILE AFTER PHASE 2 VALIDATION
# Replaced by: src/soulspot/plugins/spotify/_sync_service.py
# Validation: tests/unit/plugins/spotify/test_spotify_plugin.py passes

import warnings

warnings.warn(
    "SpotifySyncService moved to plugin internal module. "
    "Use SpotifyPlugin.get_user_playlists() instead.",
    DeprecationWarning,
    stacklevel=2
)

# Original code below
class SpotifySyncService:
    ...
```

---

## Validation Checklist (Before Cloud Agent Deletes)

### **Phase 1 Validation:**
- [ ] SpotifyPlugin tests pass (100%)
- [ ] Dual-path integration tests pass (old vs new identical)
- [ ] All routes use new plugin imports
- [ ] No production code uses deprecated imports
- [ ] Deprecation warnings appear in logs (but don't break)

### **Phase 2 Validation (Pre-Deletion):**
- [ ] SpotifyPlugin works in production for 1 week
- [ ] No deprecation warnings in production logs
- [ ] Test suite only uses plugin imports
- [ ] Rollback plan tested (restore old files works)

---

## Cloud Agent Deletion Script

**⚠️ ONLY RUN IN PRODUCTION, NOT IN VIRTUAL ENV!**

```bash
#!/bin/bash
# File: scripts/cloud-agent-delete-deprecated.sh

set -e  # Exit on error

echo "🗑️  Cloud Agent: Deleting deprecated files..."

# 1. Backup before deletion
git checkout -b backup-pre-deletion
git push origin backup-pre-deletion

# 2. Delete infrastructure files
rm src/soulspot/infrastructure/integrations/spotify_client.py
echo "✅ Deleted: spotify_client.py"

# 3. Delete application services
rm src/soulspot/application/services/spotify_sync_service.py
rm src/soulspot/application/services/spotify_image_service.py
echo "✅ Deleted: Spotify services"

# 4. Delete cache
rm src/soulspot/application/cache/spotify_cache.py
echo "✅ Deleted: Spotify cache"

# 5. Delete worker
rm src/soulspot/application/workers/spotify_sync_worker.py
echo "✅ Deleted: Spotify worker"

# 6. Delete old tests
rm tests/unit/infrastructure/integrations/test_spotify_client.py
rm tests/unit/application/services/test_spotify_sync_service.py
rm tests/unit/application/services/test_spotify_image_service.py
rm tests/unit/application/cache/test_spotify_cache.py
rm tests/unit/application/workers/test_spotify_sync_worker.py
echo "✅ Deleted: Old tests"

# 7. Delete dual-path integration tests
rm -rf tests/integration/migration/
echo "✅ Deleted: Migration tests"

# 8. Run tests to confirm nothing broke
pytest tests/unit/plugins/spotify/ -v
pytest tests/integration/ -v

echo "✅ Cloud Agent deletion complete!"
echo "📊 Summary:"
echo "   - Deleted: 10 files (~3500 lines)"
echo "   - Tests: All pass"
echo "   - Backup: backup-pre-deletion branch"
```

---

## Rollback Procedure (If Deletion Breaks Production)

### **Step 1: Restore from Backup Branch**
```bash
git checkout backup-pre-deletion
git push origin main --force
```

### **Step 2: Revert Plugin Migration (Nuclear Option)**
```bash
# Restore old files
git checkout backup-pre-deletion -- src/soulspot/infrastructure/integrations/
git checkout backup-pre-deletion -- src/soulspot/application/services/
git checkout backup-pre-deletion -- src/soulspot/application/workers/

# Revert routes to old imports
sed -i 's|plugins.spotify|infrastructure.integrations.spotify_client|g' \
    src/soulspot/api/routers/*.py

# Deploy
git add .
git commit -m "ROLLBACK: Restored old Spotify code"
git push origin main
```

---

## Success Criteria (Phase 2 Complete)

✅ All deprecated files deleted by Cloud Agent  
✅ Test suite passes (100%)  
✅ Production runs for 1 week without errors  
✅ No deprecation warnings in logs  
✅ Codebase ~3500 lines smaller  
✅ Backup branch exists for rollback

---

## Files Summary

| Category | Files to Delete | Lines Removed |
|----------|----------------|---------------|
| Infrastructure | 1 | ~982 |
| Application Services | 2 | ~1988 |
| Cache | 1 | ~186 |
| Workers | 1 | ~150 |
| Tests | 6 | ~500 |
| **Total** | **11** | **~3806** |

**Result:** Cleaner codebase, plugin-only architecture. ✅
