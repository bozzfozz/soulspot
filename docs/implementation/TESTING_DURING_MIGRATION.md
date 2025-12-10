# Testing Strategy During Migration

**Purpose:** Ensure zero regressions while migrating from Spotify-only to Plugin system.

**Principle:** Tests act as safety net - all existing tests MUST stay green during migration.

**Last Updated:** 2025-12-10

---

## Testing Philosophy

### **Golden Rule: No Breaking Changes**

```
Phase 0 (Core Infrastructure):
  → Old Spotify code untouched
  → New plugin system added parallel
  → ALL existing tests pass (100%)

Phase 1 (Spotify Plugin):
  → Old Spotify code deprecated (but works)
  → New SpotifyPlugin added
  → ALL tests still pass (dual path)

Phase 2 (Cleanup):
  → Old Spotify code deleted
  → Only plugin tests remain
  → Tests use plugin imports only
```

**Result:** User sees ZERO downtime, ZERO broken features.

---

## Test Categories During Migration

### **1. Existing Tests (Must Stay Green)**

**Location:** `tests/unit/infrastructure/`, `tests/integration/api/`

**Status:** ✅ Must pass in Phase 0 & Phase 1, deleted in Phase 2

**Example:**
```python
# tests/unit/infrastructure/integrations/test_spotify_client.py
@pytest.mark.asyncio
async def test_spotify_client_get_playlists():
    """Test existing SpotifyClient (old path)."""
    client = SpotifyClient(settings)
    playlists = await client.get_user_playlists()
    assert len(playlists) > 0
```

**Phase 0:** ✅ Passes (client unchanged)  
**Phase 1:** ✅ Passes (client moved, deprecated import works)  
**Phase 2:** ❌ Deleted (old client gone)

---

### **2. New Plugin Tests (Added in Phase 0)**

**Location:** `tests/unit/domain/ports/`, `tests/unit/application/`

**Status:** ✅ Added in Phase 0, expanded in Phase 1

**Example:**
```python
# tests/unit/domain/ports/test_plugin.py
def test_iplugin_interface_has_required_methods():
    """Test IPlugin interface has all mandatory methods."""
    required = ['get_auth_url', 'authenticate', 'get_user_playlists']
    for method in required:
        assert hasattr(IPlugin, method)

# tests/unit/application/test_plugin_manager.py
def test_plugin_manager_register_plugin():
    """Test PluginManager can register mock plugin."""
    manager = PluginManager()
    plugin = MockPlugin(service_name="test")
    manager.register(plugin)
    assert manager.has_plugin("test")
```

**Phase 0:** ✅ Passes (interfaces + manager work)  
**Phase 1:** ✅ Passes (SpotifyPlugin added)  
**Phase 2:** ✅ Passes (core plugin system)

---

### **3. Spotify Plugin Tests (Added in Phase 1)**

**Location:** `tests/unit/plugins/spotify/`, `tests/integration/plugins/`

**Status:** 🆕 Created in Phase 1, permanent

**Example:**
```python
# tests/unit/plugins/spotify/test_spotify_plugin.py
@pytest.mark.asyncio
async def test_spotify_plugin_implements_iplugin():
    """Test SpotifyPlugin implements IPlugin interface."""
    plugin = SpotifyPlugin(settings, token_manager)
    assert plugin.service_name == "spotify"
    assert hasattr(plugin, 'get_user_playlists')
    # ... all IPlugin methods

@pytest.mark.asyncio
async def test_spotify_plugin_get_playlists(mock_session):
    """Test SpotifyPlugin.get_user_playlists()."""
    plugin = SpotifyPlugin(settings, token_manager)
    playlists = await plugin.get_user_playlists(mock_session)
    assert len(playlists) > 0
    assert all(isinstance(p, Playlist) for p in playlists)
```

**Phase 0:** ❌ Doesn't exist yet  
**Phase 1:** ✅ Passes (SpotifyPlugin works)  
**Phase 2:** ✅ Passes (main test suite)

---

### **4. Dual-Path Integration Tests (Phase 1 Only)**

**Location:** `tests/integration/migration/`

**Status:** 🆕 Created in Phase 1, ❌ deleted in Phase 2

**Purpose:** Ensure old + new paths return SAME results.

**Example:**
```python
# tests/integration/migration/test_spotify_old_vs_new.py
@pytest.mark.asyncio
async def test_old_client_vs_plugin_playlists_match():
    """Ensure old SpotifyClient and new SpotifyPlugin return same data."""
    # Old path (deprecated)
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
    old_client = SpotifyClient(settings)
    old_playlists = await old_client.get_user_playlists()
    
    # New path (plugin)
    from soulspot.plugins.spotify import SpotifyPlugin
    plugin = SpotifyPlugin(settings, token_manager)
    new_playlists = await plugin.get_user_playlists(session)
    
    # Results should match
    assert len(old_playlists) == len(new_playlists)
    assert old_playlists[0].id == new_playlists[0].id
```

**Phase 0:** ❌ Doesn't exist yet  
**Phase 1:** ✅ Passes (proves migration correctness)  
**Phase 2:** ❌ Deleted (old path gone)

---

### **5. Contract Tests (Phase 1+)**

**Location:** `tests/contract/`

**Status:** 🆕 Created in Phase 1, permanent

**Purpose:** Ensure ALL plugins implement IPlugin correctly.

**Example:**
```python
# tests/contract/test_plugin_contract.py
@pytest.mark.parametrize("plugin_class", [
    SpotifyPlugin,
    # TidalPlugin,  # Phase 2
    # DeezerPlugin, # Phase 2
])
@pytest.mark.asyncio
async def test_plugin_implements_iplugin_methods(plugin_class):
    """Test all plugins implement IPlugin interface."""
    plugin = plugin_class(mock_settings, mock_token_manager)
    
    # Check all required methods exist
    assert hasattr(plugin, 'get_auth_url')
    assert hasattr(plugin, 'authenticate')
    assert hasattr(plugin, 'get_user_playlists')
    # ... all IPlugin methods
    
    # Check return types
    playlists = await plugin.get_user_playlists(mock_session)
    assert isinstance(playlists, list)
    assert all(isinstance(p, Playlist) for p in playlists)
```

**Phase 0:** ❌ Doesn't exist yet  
**Phase 1:** ✅ Passes (Spotify only)  
**Phase 2:** ✅ Passes (Spotify + Tidal + Deezer)

---

## Test Execution Strategy (Phase-by-Phase)

### **Phase 0: Core Infrastructure**

**Goal:** Add plugin system WITHOUT breaking existing tests.

**Test Commands:**
```bash
# 1. Run existing tests (must stay green)
pytest tests/unit/infrastructure/ -v
pytest tests/integration/api/ -v

# 2. Run new plugin tests
pytest tests/unit/domain/ports/ -v
pytest tests/unit/application/test_plugin_manager.py -v

# 3. Full suite (all green)
pytest tests/ -v
```

**Success Criteria:**
- ✅ 490 unit tests pass (existing)
- ✅ 156 integration tests pass (existing)
- ✅ +15 new plugin tests pass
- ✅ **Total: 661 tests pass**

---

### **Phase 1: Spotify Plugin Migration**

**Goal:** Migrate Spotify to plugin WHILE keeping old path working.

**Test Commands:**
```bash
# 1. Old Spotify tests (still pass via deprecated imports)
pytest tests/unit/infrastructure/integrations/test_spotify_client.py -v
pytest tests/unit/application/services/test_spotify_sync_service.py -v

# 2. New Spotify plugin tests
pytest tests/unit/plugins/spotify/ -v

# 3. Dual-path integration tests (prove equivalence)
pytest tests/integration/migration/ -v

# 4. Contract tests (SpotifyPlugin implements IPlugin)
pytest tests/contract/ -v

# 5. Full suite (all green)
pytest tests/ -v
```

**Success Criteria:**
- ✅ 490 old unit tests pass (via deprecated imports)
- ✅ +50 new SpotifyPlugin tests pass
- ✅ +10 dual-path integration tests pass (old vs new)
- ✅ +5 contract tests pass
- ✅ **Total: 721 tests pass**

---

### **Phase 2: Cleanup (Delete Old Code)**

**Goal:** Remove deprecated code, keep only plugin tests.

**Test Commands:**
```bash
# 1. Delete old tests
rm -rf tests/unit/infrastructure/integrations/test_spotify_client.py
rm -rf tests/unit/application/services/test_spotify_sync_service.py
rm -rf tests/integration/migration/  # Dual-path tests no longer needed

# 2. Update imports in remaining tests
sed -i 's|infrastructure.integrations.spotify_client|plugins.spotify|g' tests/**/*.py

# 3. Run plugin tests only
pytest tests/unit/plugins/ -v
pytest tests/contract/ -v

# 4. Full suite (all green)
pytest tests/ -v
```

**Success Criteria:**
- ✅ 50 SpotifyPlugin tests pass
- ✅ 5 contract tests pass
- ✅ Old Spotify tests deleted (-50 tests)
- ✅ **Total: 626 tests pass** (smaller, cleaner suite)

---

## Mock Strategy

### **Phase 0: Mock PluginManager**

```python
# tests/unit/application/services/test_playlist_service.py
from unittest.mock import Mock

def test_playlist_service_with_mock_plugin_manager():
    """Test PlaylistService with mocked PluginManager."""
    mock_manager = Mock(spec=PluginManager)
    mock_plugin = Mock(spec=IPlugin)
    mock_manager.get_active.return_value = [mock_plugin]
    
    service = PlaylistService(mock_manager)
    # ... test service logic
```

**Why:** PluginManager not implemented yet, but services need it.

---

### **Phase 1: Mock SpotifyPlugin**

```python
# tests/unit/api/routers/test_spotify_routes.py
from unittest.mock import AsyncMock

@pytest.fixture
def mock_spotify_plugin():
    """Mock SpotifyPlugin for route testing."""
    mock = AsyncMock(spec=SpotifyPlugin)
    mock.service_name = "spotify"
    mock.get_user_playlists.return_value = [
        Playlist(id="1", name="Test Playlist")
    ]
    return mock

def test_spotify_playlist_route(mock_spotify_plugin):
    """Test /api/spotify/playlists route."""
    response = client.get("/api/spotify/playlists")
    assert response.status_code == 200
```

**Why:** Avoid hitting real Spotify API in tests.

---

## Test Fixtures (Reusable Across Phases)

### **Mock ServiceSession**

```python
# tests/conftest.py
import pytest
from datetime import datetime, timedelta, timezone

@pytest.fixture
def mock_session():
    """Mock OAuth session for plugin tests."""
    return ServiceSession(
        access_token="mock_access_token",
        refresh_token="mock_refresh_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
```

---

### **Mock Plugin**

```python
# tests/conftest.py
@pytest.fixture
def mock_plugin():
    """Mock plugin implementing IPlugin."""
    class MockPlugin:
        service_name = "mock"
        service_version = "1.0.0"
        
        async def get_user_playlists(self, session):
            return [Playlist(id="1", name="Mock Playlist")]
        
        async def authenticate(self, code, redirect_uri):
            return mock_session()
        
        # ... all IPlugin methods (mocked)
    
    return MockPlugin()
```

---

### **Test Database (Integration Tests)**

```python
# tests/conftest.py
@pytest.fixture
async def test_db():
    """In-memory SQLite DB for integration tests."""
    from soulspot.infrastructure.persistence.database import create_db_engine
    
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    
    # Run migrations
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    
    yield engine
    
    # Cleanup
    await engine.dispose()
```

---

## Continuous Integration (CI) Strategy

### **GitHub Actions Workflow**

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: poetry install --with dev
      
      - name: Run Phase 0 tests (existing + plugin system)
        if: github.ref == 'refs/heads/phase-0'
        run: |
          pytest tests/unit/infrastructure/ -v
          pytest tests/unit/domain/ports/ -v
          pytest tests/unit/application/test_plugin_manager.py -v
      
      - name: Run Phase 1 tests (dual path)
        if: github.ref == 'refs/heads/phase-1'
        run: |
          pytest tests/ -v  # All tests (old + new)
          pytest tests/integration/migration/ -v  # Dual-path validation
      
      - name: Run Phase 2 tests (plugin-only)
        if: github.ref == 'refs/heads/main'
        run: |
          pytest tests/unit/plugins/ -v
          pytest tests/contract/ -v
          pytest tests/integration/ -v
```

---

## Test Coverage Requirements

### **Phase 0:**
- Unit test coverage: **≥90%** (for new plugin code)
- Integration test coverage: **≥80%** (existing tests)

### **Phase 1:**
- SpotifyPlugin coverage: **≥95%** (critical migration)
- Dual-path tests: **100%** (must prove equivalence)

### **Phase 2:**
- Overall coverage: **≥90%** (clean plugin system)

---

## Rollback Testing

### **Scenario: Phase 1 Migration Breaks Production**

**Test:**
```bash
# 1. Switch to deprecated imports in routes
sed -i 's|plugins.spotify|infrastructure.integrations.spotify_client|g' \
    src/soulspot/api/routers/*.py

# 2. Run old tests (should pass)
pytest tests/unit/infrastructure/ -v

# 3. Deploy rollback
git revert <phase-1-commits>
```

**Success Criteria:**
- ✅ Old tests pass immediately
- ✅ Production routes work
- ✅ No data loss

---

## Test Naming Conventions

```python
# Unit tests
def test_<component>_<scenario>_<expected>():
    # Example: test_plugin_manager_register_duplicate_raises_error

# Integration tests
@pytest.mark.asyncio
async def test_<feature>_<scenario>_<expected>():
    # Example: test_spotify_sync_multiple_playlists_saves_to_db

# Contract tests
@pytest.mark.parametrize("plugin_class", [...])
async def test_<interface>_<method>_<expected>(plugin_class):
    # Example: test_iplugin_get_playlists_returns_list
```

---

## Success Metrics (Per Phase)

### **Phase 0 Success:**
| Metric | Target | Actual |
|--------|--------|--------|
| Existing tests pass | 100% | ✅ |
| New plugin tests added | +15 | ✅ |
| Test coverage (new code) | ≥90% | ✅ |

### **Phase 1 Success:**
| Metric | Target | Actual |
|--------|--------|--------|
| Old tests pass (deprecated) | 100% | ✅ |
| New SpotifyPlugin tests | +50 | ✅ |
| Dual-path tests (old vs new) | +10 | ✅ |
| Contract tests | +5 | ✅ |

### **Phase 2 Success:**
| Metric | Target | Actual |
|--------|--------|--------|
| Plugin tests pass | 100% | ✅ |
| Old tests deleted | -50 | ✅ |
| Test suite size | Smaller | ✅ |
| Overall coverage | ≥90% | ✅ |

---

## Final Checklist

**Before merging Phase 0:**
- [ ] All existing tests pass (100%)
- [ ] New plugin tests pass (+15)
- [ ] No breaking changes to API
- [ ] Documentation updated

**Before merging Phase 1:**
- [ ] Old tests pass (via deprecated imports)
- [ ] New SpotifyPlugin tests pass (+50)
- [ ] Dual-path integration tests pass (+10)
- [ ] Contract tests pass (+5)
- [ ] Rollback tested (works)

**Before merging Phase 2:**
- [ ] Old tests deleted
- [ ] Plugin tests pass (100%)
- [ ] No deprecated imports remain
- [ ] Codebase cleaner + smaller
