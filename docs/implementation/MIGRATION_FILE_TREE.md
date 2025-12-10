# File Migration Map - Spotify to Plugin System

**Purpose:** Exact file movements, deletions, and refactorings for Spotify migration.

**Strategy:** Dual-path approach (old + new coexist during Phase 0, cleanup in Phase 2)

**Last Updated:** 2025-12-10

---

## Current State (Before Migration)

```
src/soulspot/
├── infrastructure/
│   ├── integrations/
│   │   └── spotify_client.py                    # 982 lines - HTTP client + OAuth
│   └── auth/
│       └── spotify_token_manager.py             # Token refresh logic
│
├── application/
│   ├── services/
│   │   ├── spotify_sync_service.py              # 1248 lines! (Sync playlists/artists)
│   │   └── spotify_image_service.py             # 740 lines (Download artwork)
│   ├── cache/
│   │   └── spotify_cache.py                     # 186 lines (API response cache)
│   ├── workers/
│   │   └── spotify_sync_worker.py               # Background sync worker
│   └── use_cases/
│       └── import_spotify_playlist.py           # Use case for playlist import
│
├── api/
│   └── routers/
│       ├── spotify.py                           # OAuth routes (/api/spotify/auth)
│       ├── search.py                            # Hardcoded Spotify search
│       └── artists.py                           # Follow/unfollow Spotify artists
│
└── domain/
    └── ports/
        └── (no plugin interface yet)
```

**Total Spotify-specific code:** ~3500 lines spread across 9 files

---

## Target State (After Phase 1)

```
src/soulspot/
├── plugins/                                     # NEW top-level directory
│   ├── __init__.py                              # Empty (nothing exported)
│   └── spotify/
│       ├── __init__.py                          # Exports SpotifyPlugin only
│       ├── plugin.py                            # SpotifyPlugin(IPlugin) - main class
│       ├── _client.py                           # MOVED FROM infrastructure/integrations/
│       ├── _auth.py                             # OAuth logic (extracted from _client.py)
│       ├── _sync_service.py                     # MOVED FROM application/services/
│       ├── _image_service.py                    # MOVED FROM application/services/
│       ├── _cache.py                            # MOVED FROM application/cache/
│       └── _mapper.py                           # NEW: Spotify API → Domain entities
│
├── infrastructure/
│   ├── integrations/
│   │   └── spotify_client.py                    # DEPRECATED (Phase 0), DELETE (Phase 2)
│   └── auth/
│       └── spotify_token_manager.py             # KEEP (used by SpotifyPlugin)
│
├── application/
│   ├── services/
│   │   ├── spotify_sync_service.py              # DEPRECATED (Phase 0), DELETE (Phase 2)
│   │   ├── spotify_image_service.py             # DEPRECATED (Phase 0), DELETE (Phase 2)
│   │   └── plugin_sync_service.py               # NEW: Generic sync (works with ANY plugin)
│   ├── cache/
│   │   └── spotify_cache.py                     # DEPRECATED (Phase 0), DELETE (Phase 2)
│   ├── workers/
│   │   ├── spotify_sync_worker.py               # DEPRECATED (Phase 0), DELETE (Phase 2)
│   │   └── plugin_sync_worker.py                # NEW: Generic worker (multi-plugin)
│   └── use_cases/
│       └── import_playlist.py                   # REFACTORED: Generic (service-agnostic)
│
├── api/
│   └── routers/
│       ├── spotify.py                           # REFACTORED: Uses SpotifyPlugin
│       ├── auth/
│       │   ├── spotify.py                       # NEW: Moved OAuth routes here
│       │   ├── tidal.py                         # NEW: Phase 2
│       │   └── deezer.py                        # NEW: Phase 2
│       ├── search.py                            # REFACTORED: Multi-service search
│       └── artists.py                           # REFACTORED: Generic follow/unfollow
│
└── domain/
    └── ports/
        ├── plugin.py                            # NEW: IPlugin interface
        ├── download_backend.py                  # NEW: IDownloadBackend interface
        └── metadata_provider.py                 # NEW: IMetadataProvider interface
```

**Result:** ~3500 lines Spotify code now in `src/soulspot/plugins/spotify/` (isolated)

---

## Migration Steps (Phase-by-Phase)

### **Phase 0: Add Plugin System (No Deletions)**

**Strategy:** Old code stays, new code added parallel.

```bash
# 1. Create plugin interfaces
mkdir -p src/soulspot/domain/ports/
touch src/soulspot/domain/ports/plugin.py
touch src/soulspot/domain/ports/download_backend.py
touch src/soulspot/domain/ports/metadata_provider.py

# 2. Create PluginManager
touch src/soulspot/application/plugin_manager.py

# 3. Update services (inject PluginManager, but still use old SpotifyClient)
# Edit: src/soulspot/application/services/playlist_service.py
# Add: self.plugin_manager parameter (optional, fallback to old client)

# 4. Update FastAPI (register plugins, but routes use old code)
# Edit: src/soulspot/main.py
# Add: plugin_manager initialization (but don't use yet)
```

**Result:** Plugin system exists, but Spotify still uses old code path. ✅ All tests pass.

---

### **Phase 1: Migrate Spotify to Plugin**

**Strategy:** Move files, keep old ones as `@deprecated`.

```bash
# 1. Create plugin directory
mkdir -p src/soulspot/plugins/spotify/

# 2. Move Spotify code
mv src/soulspot/infrastructure/integrations/spotify_client.py \
   src/soulspot/plugins/spotify/_client.py

mv src/soulspot/application/services/spotify_sync_service.py \
   src/soulspot/plugins/spotify/_sync_service.py

mv src/soulspot/application/services/spotify_image_service.py \
   src/soulspot/plugins/spotify/_image_service.py

mv src/soulspot/application/cache/spotify_cache.py \
   src/soulspot/plugins/spotify/_cache.py

# 3. Create SpotifyPlugin wrapper
cat > src/soulspot/plugins/spotify/plugin.py << 'EOF'
from soulspot.domain.ports.plugin import IPlugin
from ._client import SpotifyClient
from ._sync_service import SpotifySyncService
# ... etc
EOF

# 4. Add @deprecated to old files (stub redirects)
cat > src/soulspot/infrastructure/integrations/spotify_client.py << 'EOF'
import warnings
from soulspot.plugins.spotify._client import SpotifyClient

warnings.warn(
    "SpotifyClient moved to soulspot.plugins.spotify. "
    "This import path is deprecated and will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["SpotifyClient"]
EOF

# 5. Update imports in routes
sed -i 's|from soulspot.infrastructure.integrations.spotify_client import|from soulspot.plugins.spotify import|g' \
    src/soulspot/api/routers/*.py

# 6. Update tests
sed -i 's|infrastructure.integrations.spotify_client|plugins.spotify._client|g' \
    tests/**/*.py
```

**Result:** Spotify works via plugin system. Old imports still work (deprecated). ✅ All tests pass.

---

### **Phase 2: Cleanup (Cloud Agent Task - NOT in Virtual Environment)**

**Strategy:** Mark deprecated code for deletion (Cloud Agent will remove later).

**⚠️ IMPORTANT:** Virtual environment (GitHub Codespace) does NOT delete files. All deletions happen via Cloud Agent in production.

```bash
# ❌ DO NOT DELETE FILES IN VIRTUAL ENV!
# Instead, mark for deprecation:

# 1. Add deprecation markers to old files
cat >> src/soulspot/infrastructure/integrations/spotify_client.py << 'EOF'
# DEPRECATED: Moved to soulspot.plugins.spotify
# TODO(cloud-agent): Delete this file after Phase 2 validation
warnings.warn(
    "This module is deprecated. Use soulspot.plugins.spotify instead.",
    DeprecationWarning,
    stacklevel=2
)
EOF

# 2. Create deprecation manifest for Cloud Agent
cat > docs/implementation/DEPRECATION_MANIFEST.md << 'EOF'
# Files to Delete (Cloud Agent Task)

## After Phase 2 Validation:
- src/soulspot/infrastructure/integrations/spotify_client.py
- src/soulspot/application/services/spotify_sync_service.py
- src/soulspot/application/services/spotify_image_service.py
- src/soulspot/application/cache/spotify_cache.py
- src/soulspot/application/workers/spotify_sync_worker.py
- tests/unit/infrastructure/integrations/test_spotify_client.py
- tests/unit/application/services/test_spotify_sync_service.py
EOF

# 3. Update imports (deprecation warnings)
# Routes now use new plugin imports, old imports trigger warnings
```

**Result:** Deprecated code marked, Cloud Agent deletes later. ✅ Safe migration.

---

## File-by-File Migration Details

### **1. spotify_client.py → plugins/spotify/_client.py**

**Changes:**
```python
# BEFORE (infrastructure/integrations/spotify_client.py)
class SpotifyClient:
    def __init__(self, settings: SpotifySettings):
        # Standalone client

# AFTER (plugins/spotify/_client.py)
class SpotifyClient:
    def __init__(self, settings: SpotifySettings):
        # Same implementation, just moved
```

**No logic changes** - pure file move.

---

### **2. spotify_sync_service.py → plugins/spotify/_sync_service.py**

**Changes:**
```python
# BEFORE (application/services/spotify_sync_service.py)
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

class SpotifySyncService:
    def __init__(self, client: SpotifyClient):
        # Service logic

# AFTER (plugins/spotify/_sync_service.py)
from ._client import SpotifyClient  # Relative import

class SpotifySyncService:
    def __init__(self, client: SpotifyClient):
        # Same logic, relative import
```

**Changes:** Only imports (relative instead of absolute).

---

### **3. NEW: plugins/spotify/plugin.py**

**Purpose:** Implement IPlugin interface, orchestrate internal services.

```python
from soulspot.domain.ports.plugin import IPlugin, ServiceSession
from ._client import SpotifyClient
from ._sync_service import SpotifySyncService
from ._image_service import SpotifyImageService
from ._cache import SpotifyCache

class SpotifyPlugin(IPlugin):
    """Spotify plugin implementing IPlugin interface."""
    
    service_name = "spotify"
    service_version = "1.0.0"
    service_display_name = "Spotify"
    
    def __init__(self, settings, token_manager):
        # Initialize internal services (PRIVATE - not exposed)
        self._client = SpotifyClient(settings)
        self._cache = SpotifyCache()
        self._sync_service = SpotifySyncService(self._client, self._cache)
        self._image_service = SpotifyImageService(self._client)
    
    # Implement IPlugin methods (delegates to internal services)
    async def get_user_playlists(self, session: ServiceSession):
        return await self._sync_service.get_playlists(session)
    
    async def get_followed_artists(self, session: ServiceSession):
        return await self._sync_service.get_artists(session)
    
    # ... all other IPlugin methods
```

**NEW FILE** - glue code between IPlugin and internal services.

---

### **4. NEW: plugins/spotify/_mapper.py**

**Purpose:** Convert Spotify API JSON → Domain entities.

```python
from soulspot.domain.entities import Track, Artist, Album

def spotify_track_to_domain(spotify_json: dict) -> Track:
    """Convert Spotify API track → Domain Track entity."""
    return Track(
        title=spotify_json['name'],
        artist=spotify_json['artists'][0]['name'],
        album=spotify_json['album']['name'],
        isrc=spotify_json.get('external_ids', {}).get('isrc'),
        duration_ms=spotify_json['duration_ms'],
        spotify_id=spotify_json['id'],
    )

def spotify_artist_to_domain(spotify_json: dict) -> Artist:
    # Similar mapping
    ...
```

**NEW FILE** - extracts mapping logic from services.

---

## Deprecation Strategy

### **Phase 0-1: Dual Path (Both Work)**

```python
# Old route (still works)
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

client = SpotifyClient(settings)
playlists = await client.get_user_playlists()

# New route (also works)
from soulspot.plugins.spotify import SpotifyPlugin

plugin = SpotifyPlugin(settings, token_manager)
playlists = await plugin.get_user_playlists(session)
```

**Tests:** Both paths tested, both must pass.

---

### **Phase 2: Delete Old Path**

```python
# Old route DELETED
# → ImportError if used

# New route (only way)
from soulspot.plugins.spotify import SpotifyPlugin
```

**Tests:** Only plugin tests remain.

---

## Rollback Plan (If Migration Fails)

### **During Phase 0:**
```bash
# No deletions happened, just revert plugin additions
git revert <phase-0-commits>
# Old code untouched, still works
```

### **During Phase 1:**
```bash
# Old code still exists (deprecated but functional)
# Switch routes back to old imports
sed -i 's|plugins.spotify|infrastructure.integrations.spotify_client|g' \
    src/soulspot/api/routers/*.py
# Remove deprecation warnings
sed -i '/DeprecationWarning/d' src/soulspot/infrastructure/integrations/*.py
```

### **During Phase 2 (Cloud Agent Deletion Phase):**
```bash
# Virtual env: No deletions happened
# Cloud Agent: Can restore deleted files from Git history
git checkout <pre-deletion-commit> -- src/soulspot/infrastructure/integrations/
git checkout <pre-deletion-commit> -- src/soulspot/application/services/spotify*.py
```

**⚠️ CRITICAL:** Virtual environment never deletes files. Cloud Agent handles all deletions in production after validation.

---

## Testing During Migration

### **Phase 0: Plugin System Tests**
```python
# tests/unit/domain/ports/test_plugin.py
def test_iplugin_interface_exists():
    assert IPlugin is not None

# tests/unit/application/test_plugin_manager.py
def test_plugin_manager_registers_mock_plugin():
    manager = PluginManager()
    manager.register(MockPlugin())
    assert manager.has_plugin("mock")
```

**Old Spotify tests:** Still pass (use old imports)

---

### **Phase 1: Dual Path Tests**
```python
# tests/unit/plugins/spotify/test_spotify_plugin.py
@pytest.mark.asyncio
async def test_spotify_plugin_get_playlists():
    plugin = SpotifyPlugin(settings, token_manager)
    playlists = await plugin.get_user_playlists(mock_session)
    assert len(playlists) > 0

# tests/integration/test_spotify_old_vs_new.py
@pytest.mark.asyncio
async def test_old_client_vs_plugin_same_results():
    # Old path
    old_client = SpotifyClient(settings)
    old_playlists = await old_client.get_user_playlists()
    
    # New path
    plugin = SpotifyPlugin(settings, token_manager)
    new_playlists = await plugin.get_user_playlists(session)
    
    # Results should match
    assert len(old_playlists) == len(new_playlists)
```

**Both paths tested** - ensures no regression.

---

### **Phase 2: Plugin-Only Tests**
```python
# Old tests deleted
# Only plugin tests remain

# tests/unit/plugins/spotify/test_spotify_plugin.py
# tests/integration/test_multi_plugin.py (Spotify + Tidal + Deezer)
```

---

## Import Path Changes Summary

| File | Old Import | New Import | Phase |
|------|-----------|------------|-------|
| Routes | `from infrastructure.integrations.spotify_client import` | `from plugins.spotify import SpotifyPlugin` | Phase 1 |
| Services | `from infrastructure.integrations.spotify_client import` | Internal (plugins/spotify/plugin.py) | Phase 1 |
| Tests | `from infrastructure.integrations import` | `from plugins.spotify import` | Phase 1 |
| Domain | N/A | `from domain.ports.plugin import IPlugin` | Phase 0 |

---

## Success Criteria

### **Phase 0 Complete:**
✅ Plugin interfaces exist (`IPlugin`, `IDownloadBackend`, `IMetadataProvider`)  
✅ PluginManager functional  
✅ Old Spotify code untouched (all tests pass)

### **Phase 1 Complete:**
✅ Spotify code moved to `plugins/spotify/`  
✅ SpotifyPlugin implements IPlugin  
✅ Routes use SpotifyPlugin  
✅ Old imports deprecated (but work)  
✅ All tests pass (dual path)

### **Phase 2 Complete:**
✅ Old Spotify files deleted  
✅ Only plugin code remains  
✅ All tests use plugin imports  
✅ Codebase smaller + cleaner
