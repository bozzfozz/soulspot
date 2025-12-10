# Implementation Plan: Core Architecture for Plugin System

**Goal:** Prepare SoulSpot core to support plugin-based architecture WITHOUT breaking existing Spotify functionality.

**Strategy:** Add plugin infrastructure first, THEN migrate Spotify to plugin.

**Timeline:** 2 weeks (Phase 0)

---

## Phase 0: Core Plugin Infrastructure

**Duration:** Week 1-2  
**Goal:** Plugin system ready, Spotify still works via old code path

---

### Task 0.1: Define Plugin Interface

**File:** `src/soulspot/domain/ports/plugin.py`

**Create:**
```python
from abc import Protocol
from datetime import datetime
from typing import Optional
from ..entities import Track, Artist, Album, Playlist

class ServiceSession:
    """OAuth session data (plugin-agnostic)."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: Optional[str] = None

class IPlugin(Protocol):
    """
    Base contract for all music service plugins.
    
    Plugins provide metadata ONLY (no file downloads).
    SoulSpot core handles library management, downloads, UI.
    """
    
    # Plugin Metadata
    service_name: str          # "spotify", "tidal", "deezer"
    service_version: str       # "1.0.0"
    service_display_name: str  # "Spotify", "TIDAL", "Deezer"
    
    # === AUTHENTICATION ===
    async def get_auth_url(self, redirect_uri: str, state: str) -> str
    async def authenticate(self, code: str, redirect_uri: str) -> ServiceSession
    async def refresh_token(self, session: ServiceSession) -> ServiceSession
    async def revoke_token(self, session: ServiceSession) -> None
    async def is_authenticated(self) -> bool
    
    # === USER LIBRARY ===
    async def get_user_playlists(self, session: ServiceSession) -> list[Playlist]
    async def get_followed_artists(self, session: ServiceSession) -> list[Artist]
    async def get_saved_albums(self, session: ServiceSession) -> list[Album]
    async def get_saved_tracks(self, session: ServiceSession) -> list[Track]
    
    # === DETAILED RETRIEVAL ===
    async def get_playlist_tracks(
        self, session: ServiceSession, playlist_id: str
    ) -> list[Track]
    
    async def get_artist_albums(
        self, 
        session: ServiceSession, 
        artist_id: str,
        include_compilations: bool = True
    ) -> list[Album]
    
    async def get_album_tracks(
        self, session: ServiceSession, album_id: str
    ) -> list[Track]
    
    async def get_new_releases(
        self, session: ServiceSession, artist_ids: list[str]
    ) -> list[Album]
    
    # === METADATA ENRICHMENT ===
    async def get_track_metadata(
        self, session: ServiceSession, track_id: str
    ) -> Track
    
    async def get_artist_metadata(
        self, session: ServiceSession, artist_id: str
    ) -> Artist
    
    async def get_album_metadata(
        self, session: ServiceSession, album_id: str
    ) -> Album
    
    # === SEARCH ===
    async def search_tracks(
        self, session: ServiceSession, query: str, limit: int = 20
    ) -> list[Track]
    
    async def search_artists(
        self, session: ServiceSession, query: str, limit: int = 20
    ) -> list[Artist]
    
    async def search_albums(
        self, session: ServiceSession, query: str, limit: int = 20
    ) -> list[Album]
    
    # === CAPABILITIES (Optional Features) ===
    def supports_lyrics(self) -> bool
    def supports_high_res_audio(self) -> bool
    def supports_podcasts(self) -> bool
    def max_audio_quality(self) -> str  # "320kbps", "FLAC", "MQA"
```

**Tests:** `tests/unit/domain/ports/test_plugin.py`
```python
def test_plugin_interface_has_required_methods():
    """Ensure IPlugin has all mandatory methods."""
    required_methods = [
        'get_auth_url', 'authenticate', 'refresh_token',
        'get_user_playlists', 'get_followed_artists',
        # ... all methods
    ]
    for method in required_methods:
        assert hasattr(IPlugin, method)
```

**Status:** 🔵 Not Started  
**Depends On:** None  
**Blocks:** Task 0.2

---

### Task 0.2: Create Plugin Manager

**File:** `src/soulspot/application/plugin_manager.py`

**Purpose:** Registry for all plugins, handles plugin lifecycle.

**Create:**
```python
from typing import Optional
from ..domain.ports.plugin import IPlugin

class PluginManager:
    """
    Manages all registered music service plugins.
    
    Usage:
        manager = PluginManager()
        manager.register(SpotifyPlugin())
        manager.register(TidalPlugin())
        
        # Get all plugins
        for plugin in manager.get_all():
            playlists = await plugin.get_user_playlists(session)
        
        # Get specific plugin
        spotify = manager.get('spotify')
    """
    
    def __init__(self):
        self._plugins: dict[str, IPlugin] = {}
    
    def register(self, plugin: IPlugin) -> None:
        """Register a plugin (called during app startup)."""
        if plugin.service_name in self._plugins:
            raise ValueError(f"Plugin '{plugin.service_name}' already registered")
        self._plugins[plugin.service_name] = plugin
    
    def unregister(self, service_name: str) -> None:
        """Unregister a plugin."""
        if service_name in self._plugins:
            del self._plugins[service_name]
    
    def get(self, service_name: str) -> Optional[IPlugin]:
        """Get plugin by service name."""
        return self._plugins.get(service_name)
    
    def get_all(self) -> list[IPlugin]:
        """Get all registered plugins."""
        return list(self._plugins.values())
    
    def get_active(self) -> list[IPlugin]:
        """Get all authenticated plugins (have valid session)."""
        # TODO: Check session validity in database
        return self.get_all()
    
    def has_plugin(self, service_name: str) -> bool:
        """Check if plugin is registered."""
        return service_name in self._plugins
    
    def list_services(self) -> list[str]:
        """Get list of registered service names."""
        return list(self._plugins.keys())
```

**Tests:** `tests/unit/application/test_plugin_manager.py`
```python
def test_plugin_manager_register():
    manager = PluginManager()
    plugin = MockPlugin(service_name="spotify")
    
    manager.register(plugin)
    
    assert manager.has_plugin("spotify")
    assert manager.get("spotify") == plugin

def test_plugin_manager_duplicate_registration():
    manager = PluginManager()
    plugin1 = MockPlugin(service_name="spotify")
    plugin2 = MockPlugin(service_name="spotify")
    
    manager.register(plugin1)
    
    with pytest.raises(ValueError, match="already registered"):
        manager.register(plugin2)
```

**Status:** 🔵 Not Started  
**Depends On:** Task 0.1 (IPlugin interface)  
**Blocks:** Task 0.3

---

### Task 0.3: Update Service Layer

**File:** `src/soulspot/application/services/playlist_service.py`

**Change:** Accept `PluginManager` instead of direct `SpotifyClient`.

**Before:**
```python
class PlaylistService:
    def __init__(self, spotify_client: SpotifyClient):
        self.spotify = spotify_client
    
    async def sync_playlists(self):
        playlists = await self.spotify.get_user_playlists()
        # ...
```

**After:**
```python
class PlaylistService:
    def __init__(self, plugin_manager: PluginManager):
        self.plugins = plugin_manager
    
    async def sync_playlists(self):
        """Sync playlists from ALL active plugins."""
        for plugin in self.plugins.get_active():
            try:
                session = await self._get_session(plugin.service_name)
                playlists = await plugin.get_user_playlists(session)
                await self._import_playlists(playlists, plugin.service_name)
            except Exception as e:
                logger.error(f"Sync failed for {plugin.service_name}: {e}")
                # Continue with next plugin (skip + notify pattern)
```

**Also Update:**
- `artist_service.py`
- `track_service.py`
- `sync_service.py`

**Tests:** Update existing tests to use `PluginManager` with mock plugins.

**Status:** 🔵 Not Started  
**Depends On:** Task 0.2 (PluginManager)  
**Blocks:** Task 0.4

---

### Task 0.4: FastAPI Dependency Injection

**File:** `src/soulspot/main.py`

**Change:** Register plugins during app startup.

**Add:**
```python
from .application.plugin_manager import PluginManager
from .infrastructure.plugins.spotify import SpotifyPlugin  # Will create later

# Global plugin manager (singleton)
plugin_manager = PluginManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown logic."""
    # Register plugins
    plugin_manager.register(SpotifyPlugin())
    # plugin_manager.register(TidalPlugin())  # Phase 1
    # plugin_manager.register(DeezerPlugin())  # Phase 1
    
    logger.info(f"Registered plugins: {plugin_manager.list_services()}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down plugins...")

app = FastAPI(lifespan=lifespan)

# Dependency for routes
def get_plugin_manager() -> PluginManager:
    return plugin_manager
```

**Route Example:**
```python
# src/soulspot/api/routers/library.py
@router.get("/sync")
async def sync_library(
    plugins: PluginManager = Depends(get_plugin_manager)
):
    """Sync library from all connected services."""
    service = PlaylistService(plugins)
    await service.sync_playlists()
    return {"status": "synced", "services": plugins.list_services()}
```

**Status:** 🔵 Not Started  
**Depends On:** Task 0.3 (Service Layer)  
**Blocks:** None (ready for Phase 1)

---

### Task 0.5: Session Management Abstraction

**File:** `src/soulspot/infrastructure/session_manager.py`

**Purpose:** Manage OAuth sessions for multiple services.

**Create:**
```python
from typing import Optional
from ..domain.ports.plugin import ServiceSession

class SessionManager:
    """
    Manages OAuth sessions for all services.
    
    Stores/retrieves sessions from database.
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_session(self, service_name: str) -> Optional[ServiceSession]:
        """Get active session for service."""
        # Query service_sessions table
        row = await self.db.execute(
            "SELECT * FROM service_sessions WHERE service_type = ?",
            (service_name,)
        )
        if not row:
            return None
        
        return ServiceSession(
            access_token=row['access_token'],
            refresh_token=row['refresh_token'],
            expires_at=row['expires_at']
        )
    
    async def save_session(
        self, service_name: str, session: ServiceSession
    ) -> None:
        """Save/update session in database."""
        await self.db.execute(
            """
            INSERT INTO service_sessions (service_type, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (service_type) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                updated_at = NOW()
            """,
            (service_name, session.access_token, session.refresh_token, session.expires_at)
        )
    
    async def delete_session(self, service_name: str) -> None:
        """Delete session (user disconnected service)."""
        await self.db.execute(
            "DELETE FROM service_sessions WHERE service_type = ?",
            (service_name,)
        )
    
    async def is_authenticated(self, service_name: str) -> bool:
        """Check if service has valid session."""
        session = await self.get_session(service_name)
        if not session:
            return False
        
        # Check expiry
        from datetime import datetime, timezone
        return session.expires_at > datetime.now(timezone.utc)
```

**Status:** 🔵 Not Started  
**Depends On:** Task 0.1 (ServiceSession)  
**Blocks:** Task 0.4

---

### Task 0.6: Settings Management (Multi-Service Config)

**File:** `src/soulspot/config/plugin_settings.py`

**Purpose:** Manage plugin-specific configuration (API keys, secrets).

**Create:**
```python
from pydantic_settings import BaseSettings

class PluginSettings(BaseSettings):
    """Base settings for all plugins."""
    enabled: bool = True
    
class SpotifyPluginSettings(PluginSettings):
    """Spotify-specific settings."""
    client_id: str
    client_secret: str
    redirect_uri: str
    
    class Config:
        env_prefix = "SPOTIFY_"

class TidalPluginSettings(PluginSettings):
    """Tidal-specific settings."""
    client_id: str
    client_secret: str
    redirect_uri: str
    
    class Config:
        env_prefix = "TIDAL_"

class DeezerPluginSettings(PluginSettings):
    """Deezer-specific settings."""
    app_id: str
    secret_key: str
    redirect_uri: str
    
    class Config:
        env_prefix = "DEEZER_"

class AllPluginSettings(BaseSettings):
    """All plugin settings."""
    spotify: SpotifyPluginSettings
    tidal: TidalPluginSettings | None = None  # Optional
    deezer: DeezerPluginSettings | None = None  # Optional
    
    @classmethod
    def load(cls) -> "AllPluginSettings":
        """Load settings from environment."""
        return cls(
            spotify=SpotifyPluginSettings(),
            tidal=TidalPluginSettings() if _tidal_enabled() else None,
            deezer=DeezerPluginSettings() if _deezer_enabled() else None,
        )

def _tidal_enabled() -> bool:
    """Check if Tidal plugin is configured."""
    import os
    return bool(os.getenv("TIDAL_CLIENT_ID"))

def _deezer_enabled() -> bool:
    """Check if Deezer plugin is configured."""
    import os
    return bool(os.getenv("DEEZER_APP_ID"))
```

**.env.example update:**
```bash
# Spotify Plugin (required)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/spotify/callback

# Tidal Plugin (optional)
#TIDAL_CLIENT_ID=your_tidal_client_id
#TIDAL_CLIENT_SECRET=your_tidal_client_secret
#TIDAL_REDIRECT_URI=http://localhost:8000/api/auth/tidal/callback

# Deezer Plugin (optional)
#DEEZER_APP_ID=your_deezer_app_id
#DEEZER_SECRET=your_deezer_secret
#DEEZER_REDIRECT_URI=http://localhost:8000/api/auth/deezer/callback
```

**Status:** 🔵 Not Started  
**Depends On:** None  
**Blocks:** Task 0.4 (FastAPI DI needs settings)

---

### Task 0.7: Rate Limiter (Per-Plugin)

**File:** `src/soulspot/infrastructure/rate_limiter.py`

**Purpose:** Prevent API rate limit violations (per-service).

**Create:**
```python
import asyncio
from datetime import datetime, timedelta
from collections import deque

class RateLimiter:
    """
    Token bucket rate limiter (per-service).
    
    Usage:
        limiter = RateLimiter(max_requests=30, window_seconds=1)
        
        async with limiter:
            response = await api_call()
    """
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: deque[datetime] = deque()
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        """Acquire rate limit token."""
        async with self._lock:
            now = datetime.now()
            
            # Remove old requests outside window
            while self.requests and self.requests[0] < now - self.window:
                self.requests.popleft()
            
            # Wait if at limit
            if len(self.requests) >= self.max_requests:
                sleep_time = (self.requests[0] + self.window - now).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Retry after sleep
                    return await self.__aenter__()
            
            # Record this request
            self.requests.append(now)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release (no-op for token bucket)."""
        pass

# Plugin-specific limiters
RATE_LIMITERS = {
    "spotify": RateLimiter(max_requests=30, window_seconds=1),
    "tidal": RateLimiter(max_requests=10, window_seconds=1),
    "deezer": RateLimiter(max_requests=50, window_seconds=5),
}

def get_rate_limiter(service_name: str) -> RateLimiter:
    """Get rate limiter for service."""
    return RATE_LIMITERS.get(service_name, RateLimiter(10, 1))
```

**Plugin Integration:**
```python
# In SpotifyPlugin.get_user_playlists():
async def get_user_playlists(self, session):
    async with get_rate_limiter("spotify"):
        response = await self._client.get("/me/playlists")
    return response
```

**Status:** 🔵 Not Started  
**Depends On:** None  
**Blocks:** Phase 1 (Plugins use rate limiter)

---

### Task 0.8: Circuit Breaker (Plugin Health Tracking)

**File:** `src/soulspot/infrastructure/circuit_breaker.py`

**Purpose:** Auto-disable failing plugins, prevent cascade failures.

**DB Schema:**
```sql
-- Add to migration (Phase 0)
CREATE TABLE plugin_health (
    service_type VARCHAR(50) PRIMARY KEY,
    is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    failure_count INT NOT NULL DEFAULT 0,
    consecutive_failures INT NOT NULL DEFAULT 0,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    circuit_opened_at TIMESTAMPTZ,
    last_error TEXT,
    
    CHECK (service_type IN ('spotify', 'tidal', 'deezer'))
);

CREATE INDEX idx_plugin_health_unhealthy 
    ON plugin_health(is_healthy) 
    WHERE is_healthy = FALSE;
```

**Create:**
```python
from datetime import datetime, timezone, timedelta

class CircuitBreaker:
    """
    Circuit breaker pattern for plugin failure handling.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, circuit is open (plugin disabled)
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 3,
        timeout_seconds: int = 1800,  # 30 minutes
        db_session=None,
    ):
        self.service_name = service_name
        self.threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.db = db_session
    
    async def is_open(self) -> bool:
        """Check if circuit is open (plugin disabled)."""
        health = await self._get_health()
        if not health:
            return False
        
        if not health['is_healthy']:
            # Check if timeout expired (switch to HALF_OPEN)
            if health['circuit_opened_at']:
                elapsed = datetime.now(timezone.utc) - health['circuit_opened_at']
                if elapsed > self.timeout:
                    # Try again (HALF_OPEN)
                    return False
            return True
        
        return False
    
    async def record_success(self):
        """Record successful call (reset failures)."""
        await self.db.execute(
            """
            UPDATE plugin_health SET
                is_healthy = TRUE,
                failure_count = 0,
                consecutive_failures = 0,
                last_success_at = NOW(),
                circuit_opened_at = NULL
            WHERE service_type = ?
            """,
            (self.service_name,)
        )
    
    async def record_failure(self, error: str):
        """Record failed call (increment counter, maybe open circuit)."""
        await self.db.execute(
            """
            INSERT INTO plugin_health (service_type, failure_count, consecutive_failures, last_failure_at, last_error)
            VALUES (?, 1, 1, NOW(), ?)
            ON CONFLICT (service_type) DO UPDATE SET
                failure_count = plugin_health.failure_count + 1,
                consecutive_failures = plugin_health.consecutive_failures + 1,
                last_failure_at = NOW(),
                last_error = excluded.last_error
            """,
            (self.service_name, error)
        )
        
        # Check if threshold exceeded
        health = await self._get_health()
        if health and health['consecutive_failures'] >= self.threshold:
            # Open circuit
            await self.db.execute(
                """
                UPDATE plugin_health SET
                    is_healthy = FALSE,
                    circuit_opened_at = NOW()
                WHERE service_type = ?
                """,
                (self.service_name,)
            )
    
    async def _get_health(self):
        """Get current health status from DB."""
        result = await self.db.execute(
            "SELECT * FROM plugin_health WHERE service_type = ?",
            (self.service_name,)
        )
        return result.fetchone() if result else None
```

**Plugin Integration:**
```python
# In PluginManager.execute_on_plugin():
async def execute_on_plugin(self, service_name: str, method: str, *args):
    plugin = self.get(service_name)
    circuit_breaker = CircuitBreaker(service_name, db_session=self.db)
    
    if await circuit_breaker.is_open():
        raise PluginUnavailableError(f"{service_name} is currently unavailable")
    
    try:
        result = await getattr(plugin, method)(*args)
        await circuit_breaker.record_success()
        return result
    except Exception as e:
        await circuit_breaker.record_failure(str(e))
        raise
```

**Status:** 🔵 Not Started  
**Depends On:** Task 0.2 (PluginManager), DB Migration (plugin_health table)  
**Blocks:** None (optional for Phase 0, required for Phase 2)

---

### Task 0.9: DB Migration (Existing Data)

**File:** `alembic/versions/qq28013ttt61_migrate_to_plugin_system.py`

**Purpose:** Migrate existing Spotify data to new plugin schema.

**Migration Script:**
```python
"""Migrate to plugin system (multi-service)

Revision ID: qq28013ttt61
Revises: pp27012rrs60
Create Date: 2025-12-10

Changes:
1. Rename spotify_sessions → service_sessions (add service_type)
2. Add plugin_health table
3. Add track_download_state table
4. Add artist_completeness table
5. Add followed_artists table
6. Migrate existing data
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. Rename spotify_sessions → service_sessions
    op.rename_table('spotify_sessions', 'service_sessions_old')
    
    # 2. Create new service_sessions table
    op.create_table(
        'service_sessions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('service_type', sa.String(50), unique=True, nullable=False),
        sa.Column('access_token', sa.Text()),
        sa.Column('refresh_token', sa.Text()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('scope', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("service_type IN ('spotify', 'tidal', 'deezer')")
    )
    
    # 3. Migrate data (spotify_sessions → service_sessions with service_type='spotify')
    op.execute("""
        INSERT INTO service_sessions (id, service_type, access_token, refresh_token, expires_at, created_at, updated_at)
        SELECT id, 'spotify', access_token, refresh_token, expires_at, created_at, updated_at
        FROM service_sessions_old
    """)
    
    # 4. Drop old table
    op.drop_table('service_sessions_old')
    
    # 5. Create plugin_health table
    op.create_table(
        'plugin_health',
        sa.Column('service_type', sa.String(50), primary_key=True),
        sa.Column('is_healthy', sa.Boolean(), nullable=False, default=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, default=0),
        sa.Column('last_success_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('last_failure_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('circuit_opened_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('last_error', sa.Text()),
        sa.CheckConstraint("service_type IN ('spotify', 'tidal', 'deezer')")
    )
    
    # 6. Create track_download_state table
    op.create_table(
        'track_download_state',
        sa.Column('track_id', sa.UUID(), primary_key=True),
        sa.Column('availability', sa.String(50), nullable=False),
        sa.Column('local_path', sa.Text()),
        sa.Column('file_size_bytes', sa.BigInteger()),
        sa.Column('file_format', sa.String(20)),
        sa.Column('bitrate_kbps', sa.Integer()),
        sa.Column('download_queued_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('download_started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('downloaded_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('download_attempts', sa.Integer(), default=0),
        sa.Column('last_error', sa.Text()),
        sa.Column('soulseek_search_results_count', sa.Integer()),
        sa.Column('last_checked_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.CheckConstraint("availability IN ('local', 'queued', 'available', 'not_found', 'failed')")
    )
    
    # 7. Create artist_completeness table
    op.create_table(
        'artist_completeness',
        sa.Column('artist_id', sa.UUID(), primary_key=True),
        sa.Column('total_albums', sa.Integer(), nullable=False, default=0),
        sa.Column('local_albums', sa.Integer(), nullable=False, default=0),
        sa.Column('partial_albums', sa.Integer(), nullable=False, default=0),
        sa.Column('missing_albums', sa.Integer(), nullable=False, default=0),
        sa.Column('total_tracks', sa.Integer(), nullable=False, default=0),
        sa.Column('local_tracks', sa.Integer(), nullable=False, default=0),
        sa.Column('queued_tracks', sa.Integer(), nullable=False, default=0),
        sa.Column('missing_tracks', sa.Integer(), nullable=False, default=0),
        sa.Column('completeness_percent', sa.Numeric(5, 2), nullable=False, default=0.00),
        sa.Column('last_calculated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ondelete='CASCADE'),
        sa.CheckConstraint('completeness_percent BETWEEN 0 AND 100')
    )
    
    # 8. Create followed_artists table
    op.create_table(
        'followed_artists',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('artist_id', sa.UUID(), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('service_artist_id', sa.String(255), nullable=False),
        sa.Column('auto_download_enabled', sa.Boolean(), default=False),
        sa.Column('monitor_new_releases', sa.Boolean(), default=True),
        sa.Column('quality_preference', sa.String(50)),
        sa.Column('followed_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_synced_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('last_new_release_check', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('artist_id', 'service_type'),
        sa.CheckConstraint("service_type IN ('spotify', 'tidal', 'deezer')"),
        sa.CheckConstraint("quality_preference IN ('any', '320kbps', 'flac_only') OR quality_preference IS NULL")
    )
    
    # 9. Backfill track_download_state (mark existing tracks as local)
    op.execute("""
        INSERT INTO track_download_state (track_id, availability, local_path, downloaded_at, last_checked_at, created_at, updated_at)
        SELECT id, 'local', local_path, created_at, NOW(), created_at, NOW()
        FROM tracks
        WHERE local_path IS NOT NULL
    """)
    
    # 10. Backfill followed_artists (migrate from existing followed_artists if exists)
    # (Adjust based on your current schema)
    
    # 11. Create indexes
    op.create_index('idx_track_download_availability', 'track_download_state', ['availability'])
    op.create_index('idx_artist_completeness_percent', 'artist_completeness', ['completeness_percent'])
    op.create_index('idx_followed_artists_service', 'followed_artists', ['service_type'])

def downgrade():
    # Reverse migration (if needed)
    op.drop_table('followed_artists')
    op.drop_table('artist_completeness')
    op.drop_table('track_download_state')
    op.drop_table('plugin_health')
    
    # Restore old spotify_sessions table
    # (Complex, better to backup before migration!)
```

**Status:** 🔵 Not Started  
**Depends On:** All Phase 0 tasks  
**Blocks:** Phase 1 (can't test plugins without DB schema)

---

### Task 0.10: IDownloadBackend Interface

**File:** `src/soulspot/domain/ports/download_backend.py`

**Purpose:** Abstract download system to allow future backends (YouTube-DL, Torrents, etc.).

**Create Interface:**
```python
from typing import Protocol
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class DownloadStatus(str, Enum):
    """Download lifecycle states."""
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class DownloadResult:
    """Result of download operation."""
    download_id: str
    status: DownloadStatus
    local_path: str | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

class IDownloadBackend(Protocol):
    """
    Interface for download backends (Soulseek, YouTube-DL, etc.).
    
    SoulSpot Core depends ONLY on this interface, not concrete implementations.
    """
    
    async def search_and_download(
        self,
        query: str,
        priority: int = 5,
        timeout_seconds: int = 300
    ) -> DownloadResult:
        """
        Search for track and start download.
        
        Args:
            query: Search query (e.g., "Artist - Track Title")
            priority: Download priority (1=highest, 10=lowest)
            timeout_seconds: Max time to wait for download
        
        Returns:
            DownloadResult with download_id and initial status
        """
        ...
    
    async def get_download_status(self, download_id: str) -> DownloadResult:
        """Get current status of download."""
        ...
    
    async def cancel_download(self, download_id: str) -> bool:
        """Cancel active download. Returns True if cancelled."""
        ...
    
    async def list_active_downloads(self) -> list[DownloadResult]:
        """Get all currently active downloads."""
        ...
    
    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed downloads from queue. Returns count removed."""
        ...
```

**Implement Soulseek Backend:**

**File:** `src/soulspot/infrastructure/clients/slskd_download_backend.py`

```python
import httpx
import asyncio
from datetime import datetime, timezone

class SlskdDownloadBackend:
    """Soulseek (slskd) implementation of IDownloadBackend."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"X-API-Key": self.api_key},
                timeout=30.0
            )
        return self._client
    
    async def search_and_download(
        self,
        query: str,
        priority: int = 5,
        timeout_seconds: int = 300
    ) -> DownloadResult:
        """Search Soulseek network and download first good match."""
        client = await self._get_client()
        
        # Start search
        search_response = await client.post(
            f"{self.base_url}/api/v0/searches",
            json={"searchText": query}
        )
        search_id = search_response.json()['id']
        
        # Wait for results (with timeout)
        start_time = datetime.now(timezone.utc)
        best_file = None
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout_seconds:
            results = await client.get(f"{self.base_url}/api/v0/searches/{search_id}")
            files = results.json().get('files', [])
            
            if files:
                # Pick best quality (highest bitrate)
                best_file = max(files, key=lambda f: f.get('bitrate', 0))
                break
            
            await asyncio.sleep(2)  # Poll every 2 seconds
        
        if not best_file:
            return DownloadResult(
                download_id=search_id,
                status=DownloadStatus.FAILED,
                error_message="No results found within timeout"
            )
        
        # Start download
        download_response = await client.post(
            f"{self.base_url}/api/v0/downloads",
            json={
                "username": best_file['username'],
                "filename": best_file['filename'],
                "priority": priority
            }
        )
        
        download_id = download_response.json()['id']
        
        return DownloadResult(
            download_id=download_id,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(timezone.utc)
        )
    
    async def get_download_status(self, download_id: str) -> DownloadResult:
        """Check slskd download status."""
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/api/v0/downloads/{download_id}")
        data = response.json()
        
        # Map slskd state to our DownloadStatus
        state_mapping = {
            "Queued": DownloadStatus.PENDING,
            "InProgress": DownloadStatus.DOWNLOADING,
            "Completed": DownloadStatus.COMPLETED,
            "Cancelled": DownloadStatus.CANCELLED,
            "Errored": DownloadStatus.FAILED
        }
        
        return DownloadResult(
            download_id=download_id,
            status=state_mapping.get(data['state'], DownloadStatus.PENDING),
            local_path=data.get('localPath'),
            file_size_bytes=data.get('size'),
            started_at=data.get('startedAt'),
            completed_at=data.get('completedAt'),
            error_message=data.get('error')
        )
    
    async def cancel_download(self, download_id: str) -> bool:
        client = await self._get_client()
        response = await client.delete(f"{self.base_url}/api/v0/downloads/{download_id}")
        return response.status_code == 204
    
    async def list_active_downloads(self) -> list[DownloadResult]:
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/api/v0/downloads")
        downloads = response.json()
        
        return [
            await self.get_download_status(d['id'])
            for d in downloads
            if d['state'] in ['Queued', 'InProgress']
        ]
    
    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed downloads older than N hours."""
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/api/v0/downloads")
        downloads = response.json()
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        removed = 0
        
        for dl in downloads:
            if dl['state'] == 'Completed' and dl.get('completedAt'):
                completed_at = datetime.fromisoformat(dl['completedAt'])
                if completed_at < cutoff:
                    await client.delete(f"{self.base_url}/api/v0/downloads/{dl['id']}")
                    removed += 1
        
        return removed
    
    async def close(self):
        if self._client:
            await self._client.aclose()
```

**Dependency Injection (main.py):**
```python
from soulspot.domain.ports.download_backend import IDownloadBackend
from soulspot.infrastructure.clients.slskd_download_backend import SlskdDownloadBackend

def create_app():
    # Initialize backend
    download_backend: IDownloadBackend = SlskdDownloadBackend(
        base_url=settings.SLSKD_URL,
        api_key=settings.SLSKD_API_KEY
    )
    
    # Inject into services
    download_service = DownloadService(backend=download_backend)
    
    app.state.download_backend = download_backend
    app.state.download_service = download_service
```

**Status:** 🔵 Not Started  
**Depends On:** None (core interface)  
**Blocks:** Task 0.11 (Download Queue Integration depends on this)

---

### Task 0.11: IMetadataProvider Interface

**File:** `src/soulspot/domain/ports/metadata_provider.py`

**Purpose:** Abstract metadata enrichment sources (MusicBrainz, Discogs, Last.fm).

**Create Interface:**
```python
from typing import Protocol
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TrackMetadata:
    """Enriched track metadata from provider."""
    musicbrainz_id: str | None = None
    isrc: str | None = None
    duration_ms: int | None = None
    release_date: datetime | None = None
    album_name: str | None = None
    album_artist: str | None = None
    genres: list[str] | None = None
    tags: list[str] | None = None
    
@dataclass
class AlbumMetadata:
    """Enriched album metadata."""
    musicbrainz_id: str | None = None
    title: str
    artist: str
    release_date: datetime | None = None
    album_type: str | None = None  # 'album', 'single', 'compilation'
    label: str | None = None
    artwork_url: str | None = None
    genres: list[str] | None = None
    total_tracks: int | None = None

@dataclass
class ArtistMetadata:
    """Enriched artist metadata."""
    musicbrainz_id: str | None = None
    name: str
    sort_name: str | None = None
    disambiguation: str | None = None
    country: str | None = None
    begin_date: datetime | None = None
    genres: list[str] | None = None
    image_url: str | None = None

class IMetadataProvider(Protocol):
    """
    Interface for metadata enrichment providers.
    
    Unlike IPlugin (streaming services), IMetadataProvider focuses on
    enriching existing data with additional metadata (MusicBrainz IDs,
    genres, release dates, artwork, etc.).
    """
    
    provider_name: str  # "musicbrainz", "discogs", "lastfm"
    
    async def lookup_track_by_isrc(self, isrc: str) -> TrackMetadata | None:
        """Lookup track metadata by ISRC code."""
        ...
    
    async def lookup_track_by_name(
        self,
        title: str,
        artist: str,
        album: str | None = None
    ) -> TrackMetadata | None:
        """Fuzzy search track by name/artist."""
        ...
    
    async def get_track_details(self, provider_id: str) -> TrackMetadata | None:
        """Get full track details by provider's ID (e.g., MusicBrainz ID)."""
        ...
    
    async def get_album_details(self, provider_id: str) -> AlbumMetadata | None:
        """Get album metadata by provider's ID."""
        ...
    
    async def get_artist_details(self, provider_id: str) -> ArtistMetadata | None:
        """Get artist metadata by provider's ID."""
        ...
    
    async def search_artist(self, name: str, limit: int = 5) -> list[ArtistMetadata]:
        """Search for artist by name (fuzzy match)."""
        ...
```

**MusicBrainz Implementation:**

**File:** `src/soulspot/infrastructure/metadata/musicbrainz_provider.py`

```python
import httpx
import asyncio
from datetime import datetime

class MusicBrainzProvider:
    """MusicBrainz metadata enrichment provider."""
    
    provider_name = "musicbrainz"
    API_BASE = "https://musicbrainz.org/ws/2"
    
    def __init__(self, user_agent: str = "SoulSpot/1.0 (contact@example.com)"):
        self.user_agent = user_agent
        self._last_request = 0
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=10.0
            )
        return self._client
    
    async def _rate_limit(self):
        """Enforce 1 req/s rate limit (MusicBrainz ToS)."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request = asyncio.get_event_loop().time()
    
    async def lookup_track_by_isrc(self, isrc: str) -> TrackMetadata | None:
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/recording",
            params={"query": f"isrc:{isrc}", "fmt": "json", "limit": 1}
        )
        
        if response.status_code != 200 or not response.json().get('recordings'):
            return None
        
        recording = response.json()['recordings'][0]
        return self._parse_track_metadata(recording)
    
    async def lookup_track_by_name(
        self,
        title: str,
        artist: str,
        album: str | None = None
    ) -> TrackMetadata | None:
        await self._rate_limit()
        client = await self._get_client()
        
        query_parts = [f'recording:"{title}"', f'artist:"{artist}"']
        if album:
            query_parts.append(f'release:"{album}"')
        query = " AND ".join(query_parts)
        
        response = await client.get(
            f"{self.API_BASE}/recording",
            params={"query": query, "fmt": "json", "limit": 1}
        )
        
        if response.status_code != 200 or not response.json().get('recordings'):
            return None
        
        recording = response.json()['recordings'][0]
        return self._parse_track_metadata(recording)
    
    async def get_track_details(self, mbid: str) -> TrackMetadata | None:
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/recording/{mbid}",
            params={"inc": "artists+releases+isrcs+genres+tags", "fmt": "json"}
        )
        
        if response.status_code != 200:
            return None
        
        return self._parse_track_metadata(response.json())
    
    async def get_album_details(self, mbid: str) -> AlbumMetadata | None:
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/release/{mbid}",
            params={"inc": "artists+labels+recordings+genres", "fmt": "json"}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        return AlbumMetadata(
            musicbrainz_id=data['id'],
            title=data['title'],
            artist=data['artist-credit'][0]['name'] if data.get('artist-credit') else "",
            release_date=self._parse_date(data.get('date')),
            album_type=data.get('release-group', {}).get('primary-type', '').lower(),
            label=data.get('label-info', [{}])[0].get('label', {}).get('name'),
            total_tracks=len(data.get('media', [{}])[0].get('tracks', [])),
            genres=[g['name'] for g in data.get('genres', [])]
        )
    
    async def get_artist_details(self, mbid: str) -> ArtistMetadata | None:
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/artist/{mbid}",
            params={"inc": "genres+tags", "fmt": "json"}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        return ArtistMetadata(
            musicbrainz_id=data['id'],
            name=data['name'],
            sort_name=data.get('sort-name'),
            disambiguation=data.get('disambiguation'),
            country=data.get('country'),
            begin_date=self._parse_date(data.get('life-span', {}).get('begin')),
            genres=[g['name'] for g in data.get('genres', [])]
        )
    
    async def search_artist(self, name: str, limit: int = 5) -> list[ArtistMetadata]:
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/artist",
            params={"query": f'artist:"{name}"', "fmt": "json", "limit": limit}
        )
        
        if response.status_code != 200:
            return []
        
        return [
            ArtistMetadata(
                musicbrainz_id=a['id'],
                name=a['name'],
                sort_name=a.get('sort-name'),
                disambiguation=a.get('disambiguation'),
                country=a.get('country')
            )
            for a in response.json().get('artists', [])
        ]
    
    def _parse_track_metadata(self, data: dict) -> TrackMetadata:
        """Parse MusicBrainz recording into TrackMetadata."""
        return TrackMetadata(
            musicbrainz_id=data['id'],
            isrc=data.get('isrcs', [None])[0],
            duration_ms=data.get('length'),
            album_name=data.get('releases', [{}])[0].get('title'),
            genres=[g['name'] for g in data.get('genres', [])],
            tags=[t['name'] for t in data.get('tags', [])]
        )
    
    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse MusicBrainz date (YYYY, YYYY-MM, or YYYY-MM-DD)."""
        if not date_str:
            return None
        
        try:
            if len(date_str) == 4:  # YYYY
                return datetime(int(date_str), 1, 1)
            elif len(date_str) == 7:  # YYYY-MM
                year, month = date_str.split('-')
                return datetime(int(year), int(month), 1)
            else:  # YYYY-MM-DD
                return datetime.fromisoformat(date_str)
        except ValueError:
            return None
    
    async def close(self):
        if self._client:
            await self._client.aclose()
```

**MetadataManager (orchestrates providers):**

**File:** `src/soulspot/application/services/metadata_manager.py`

```python
class MetadataManager:
    """Manages metadata enrichment providers (MusicBrainz, Discogs, etc.)."""
    
    def __init__(self):
        self._providers: dict[str, IMetadataProvider] = {}
        self._priority_order: list[str] = []  # Provider preference order
    
    def register(self, provider: IMetadataProvider, priority: int = 10):
        """Register metadata provider with priority (lower = higher priority)."""
        self._providers[provider.provider_name] = provider
        self._priority_order.append((priority, provider.provider_name))
        self._priority_order.sort()  # Sort by priority
    
    async def enrich_track(self, track: Track) -> Track:
        """Enrich track with metadata from all providers (priority order)."""
        # Try ISRC lookup first (most accurate)
        if track.isrc:
            for _, provider_name in self._priority_order:
                provider = self._providers[provider_name]
                metadata = await provider.lookup_track_by_isrc(track.isrc)
                if metadata:
                    track = self._merge_track_metadata(track, metadata)
                    break
        
        # Fallback: fuzzy name search
        if not track.musicbrainz_id:
            for _, provider_name in self._priority_order:
                provider = self._providers[provider_name]
                metadata = await provider.lookup_track_by_name(
                    track.title,
                    track.artist,
                    track.album
                )
                if metadata:
                    track = self._merge_track_metadata(track, metadata)
                    break
        
        return track
    
    def _merge_track_metadata(self, track: Track, metadata: TrackMetadata) -> Track:
        """Merge metadata into track (only fill missing fields)."""
        if not track.musicbrainz_id and metadata.musicbrainz_id:
            track.musicbrainz_id = metadata.musicbrainz_id
        if not track.isrc and metadata.isrc:
            track.isrc = metadata.isrc
        if not track.duration_ms and metadata.duration_ms:
            track.duration_ms = metadata.duration_ms
        if not track.genres and metadata.genres:
            track.genres = metadata.genres
        return track
```

**Integration with TrackService:**
```python
# In TrackService.import_track():
async def import_track(self, track: Track) -> UUID:
    """Import track from plugin, enrich with metadata providers."""
    # Save to DB
    track_id = await self.repo.create(track)
    
    # Enrich with metadata (MusicBrainz, etc.)
    enriched_track = await self.metadata_manager.enrich_track(track)
    await self.repo.update(track_id, **enriched_track.dict())
    
    return track_id
```

**Status:** 🔵 Not Started  
**Depends On:** None  
**Blocks:** None (optional enrichment layer)

---

### Task 0.12: Download Queue Integration

**File:** `src/soulspot/application/services/download_service.py`

**Purpose:** Bridge between Plugin-synced tracks and download backend.

**Update DownloadService to use IDownloadBackend:**

**Workflow:**
```
Plugin syncs new album → TrackService creates Track entities
                      → DownloadService queues missing tracks for download
                      → Soulseek worker processes queue
                      → track_download_state updated to 'local'
```

**Update:**
```python
from soulspot.domain.ports.download_backend import IDownloadBackend, DownloadStatus

class DownloadService:
    """Manages download queue for all tracks."""
    
    def __init__(
        self,
        backend: IDownloadBackend,  # ← Now uses interface!
        plugin_manager: PluginManager,
        db_session
    ):
        self.backend = backend  # Works with ANY IDownloadBackend
        self.plugins = plugin_manager
        self.db = db_session
    
    async def queue_track(self, track_id: UUID, priority: int = 5):
        """Add track to download queue."""
        # Update track_download_state
        await self.db.execute(
            """
            INSERT INTO track_download_state (track_id, availability, download_queued_at, last_checked_at)
            VALUES (?, 'queued', NOW(), NOW())
            ON CONFLICT (track_id) DO UPDATE SET
                availability = 'queued',
                download_queued_at = NOW(),
                download_attempts = 0
            """,
            (track_id,)
        )
        
        # Queue via backend (abstracted!)
        track = await self._get_track(track_id)
        search_query = f"{track.artist} {track.title}"
        
        result = await self.backend.search_and_download(search_query, priority=priority)
        
        # Store download_id for status tracking
        await self.db.execute(
            "UPDATE track_download_state SET download_id = ? WHERE track_id = ?",
            (result.download_id, track_id)
        )
    
    async def queue_album(self, album_id: UUID):
        """Queue all tracks in album for download."""
        tracks = await self._get_album_tracks(album_id)
        for track in tracks:
            if not await self._is_local(track.id):
                await self.queue_track(track.id)
    
    async def queue_artist_missing(self, artist_id: UUID):
        """Queue all missing tracks for artist."""
        albums = await self._get_artist_albums(artist_id)
        for album in albums:
            await self.queue_album(album.id)
    
    async def on_download_complete(self, track_id: UUID, local_path: str, file_size: int):
        """Called by Soulseek worker when download finishes."""
        await self.db.execute(
            """
            UPDATE track_download_state SET
                availability = 'local',
                local_path = ?,
                file_size_bytes = ?,
                downloaded_at = NOW(),
                updated_at = NOW()
            WHERE track_id = ?
            """,
            (local_path, file_size, track_id)
        )
        
        # Trigger artist completeness recalculation
        await self._recalculate_artist_completeness(track_id)
    
    async def on_download_failed(self, track_id: UUID, error: str):
        """Called by Soulseek worker when download fails."""
        await self.db.execute(
            """
            UPDATE track_download_state SET
                availability = 'failed',
                download_attempts = download_attempts + 1,
                last_error = ?,
                updated_at = NOW()
            WHERE track_id = ?
            """,
            (error, track_id)
        )
```

**Integration with Plugin Sync:**
```python
# In PlaylistService.sync_playlists():
async def sync_playlists(self):
    for plugin in self.plugins.get_active():
        playlists = await plugin.get_user_playlists(session)
        
        for playlist in playlists:
            tracks = await plugin.get_playlist_tracks(session, playlist.id)
            
            # Import tracks to DB
            for track in tracks:
                track_id = await self.track_service.import_track(track)
                
                # Auto-queue for download if enabled
                if self.settings.auto_download_playlists:
                    if not await self.download_service.is_local(track_id):
                        await self.download_service.queue_track(track_id)
```

**Status:** 🔵 Not Started  
**Depends On:** Task 0.3 (Service Layer), Task 0.9 (DB Migration), Task 0.10 (IDownloadBackend)  
**Blocks:** Phase 1 (Plugins need download integration)

---

### Task 0.13: Background Workers Refactoring

**File:** `src/soulspot/infrastructure/clients/musicbrainz_client.py`

**Purpose:** Enrich track metadata via MusicBrainz (for deduplication + quality).

**Create:**
```python
import httpx
import asyncio

class MusicBrainzClient:
    """
    Client for MusicBrainz API (metadata enrichment).
    
    Rate limit: 1 request/second (respect musicbrainz.org ToS!)
    """
    
    API_BASE = "https://musicbrainz.org/ws/2"
    
    def __init__(self, user_agent: str = "SoulSpot/1.0"):
        self.user_agent = user_agent
        self._last_request = 0
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=10.0
            )
        return self._client
    
    async def _rate_limit(self):
        """Enforce 1 req/s rate limit."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request = asyncio.get_event_loop().time()
    
    async def lookup_by_isrc(self, isrc: str) -> dict | None:
        """
        Lookup recording by ISRC.
        
        Returns:
            {
                'id': 'mbid-xyz',
                'title': 'Track Title',
                'artist': 'Artist Name',
                'length': 240000  # milliseconds
            }
        """
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/recording",
            params={"query": f"isrc:{isrc}", "fmt": "json"}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data.get('recordings'):
            return None
        
        # Return first match
        recording = data['recordings'][0]
        return {
            'id': recording['id'],
            'title': recording['title'],
            'artist': recording['artist-credit'][0]['name'] if recording.get('artist-credit') else None,
            'length': recording.get('length')
        }
    
    async def get_recording_details(self, mbid: str) -> dict | None:
        """Get full recording details by MusicBrainz ID."""
        await self._rate_limit()
        client = await self._get_client()
        
        response = await client.get(
            f"{self.API_BASE}/recording/{mbid}",
            params={"inc": "artists+releases+isrcs", "fmt": "json"}
        )
        
        if response.status_code != 200:
            return None
        
        return response.json()
    
    async def close(self):
        if self._client:
            await self._client.aclose()
```

**Integration:**
```python
# In TrackService.import_track():
async def import_track(self, track: Track) -> UUID:
    """Import track from plugin, enrich with MusicBrainz."""
    # Save to DB
    track_id = await self.repo.create(track)
    
    # Enrich with MusicBrainz (if ISRC available)
    if track.isrc and not track.musicbrainz_id:
        mb_data = await self.musicbrainz.lookup_by_isrc(track.isrc)
        if mb_data:
            await self.repo.update(track_id, musicbrainz_id=mb_data['id'])
    
    return track_id
```

**Status:** 🟡 Optional (can skip for Phase 0)  
**Depends On:** None  
**Blocks:** None

---

### Task 0.14: Testing Strategy

**File:** `tests/README_testing_strategy.md`

**Purpose:** Define test matrix for multi-plugin system.

**Test Levels:**

1. **Unit Tests** (per plugin, isolated)
```python
# tests/unit/plugins/spotify/test_spotify_plugin.py
@pytest.mark.asyncio
async def test_spotify_plugin_get_playlists(mock_session):
    plugin = SpotifyPlugin(settings)
    playlists = await plugin.get_user_playlists(mock_session)
    assert len(playlists) > 0
```

2. **Contract Tests** (IPlugin interface compliance)
```python
# tests/contract/test_plugin_contract.py
@pytest.mark.parametrize("plugin_class", [SpotifyPlugin, TidalPlugin, DeezerPlugin])
@pytest.mark.asyncio
async def test_plugin_implements_interface(plugin_class):
    """Ensure all plugins implement IPlugin correctly."""
    plugin = plugin_class(mock_settings)
    
    # Check all required methods exist
    assert hasattr(plugin, 'get_user_playlists')
    assert hasattr(plugin, 'authenticate')
    # ... all methods
    
    # Check return types
    playlists = await plugin.get_user_playlists(mock_session)
    assert all(isinstance(p, Playlist) for p in playlists)
```

3. **Integration Tests** (multi-plugin scenarios)
```python
# tests/integration/test_multi_plugin.py
@pytest.mark.asyncio
async def test_sync_multiple_services(plugin_manager, db):
    """Test syncing from Spotify + Tidal simultaneously."""
    plugin_manager.register(SpotifyPlugin(mock_settings))
    plugin_manager.register(TidalPlugin(mock_settings))
    
    service = PlaylistService(plugin_manager)
    await service.sync_playlists()
    
    # Verify playlists from both services
    spotify_playlists = await db.query("SELECT * FROM playlists WHERE source_service='spotify'")
    tidal_playlists = await db.query("SELECT * FROM playlists WHERE source_service='tidal'")
    
    assert len(spotify_playlists) > 0
    assert len(tidal_playlists) > 0
```

4. **Performance Tests**
```python
# tests/performance/test_large_library.py
@pytest.mark.slow
async def test_sync_1000_playlists(plugin_manager):
    """Ensure sync completes in <5 minutes for 1000 playlists."""
    start = time.time()
    await service.sync_playlists()
    duration = time.time() - start
    
    assert duration < 300  # 5 minutes
```

**Test Matrix:**

| Scenario | Plugins | Expected Behavior |
|----------|---------|-------------------|
| Single (Spotify only) | Spotify | Works like current system |
| Dual (Spotify + Tidal) | Spotify, Tidal | Both sync, no conflicts |
| Triple (All) | Spotify, Tidal, Deezer | All sync, deduplication works |
| One fails | Spotify (fails), Tidal (ok) | Tidal continues, Spotify skipped |
| Circuit breaker | Spotify (3 failures) | Spotify disabled for 30min |

**Status:** 🔵 Not Started  
**Depends On:** Phase 1 (Plugins implemented)  
**Blocks:** None (ongoing during implementation)

---

## Phase 1: Spotify as First Plugin

**Duration:** Week 3-4  
**Goal:** SpotifyClient becomes SpotifyPlugin, implements IPlugin

---

### Task 1.1: Create Plugin Base Directory

**CRITICAL:** Plugins are **SEPARATE** from core infrastructure.

**Structure:**
```
src/soulspot/plugins/          ← NEW top-level directory (NOT in infrastructure!)
├── __init__.py
└── spotify/
    ├── __init__.py
    ├── plugin.py              # SpotifyPlugin(IPlugin) - implements interface
    ├── client.py              # MOVE FROM infrastructure/integrations/spotify_client.py
    ├── auth.py                # OAuth PKCE logic (extract from client.py)
    └── mapper.py              # NEW: Spotify JSON → Domain entities (Track, Artist, etc.)
```

**Why separate?**
- ✅ Spotify logic stays isolated (Core has ZERO Spotify imports)
- ✅ Tidal/Deezer plugins follow same pattern (self-contained)
- ✅ Core only knows `IPlugin` interface (abstract)
- ✅ Plugins can be versioned independently

**Migration:**
```bash
# Move existing SpotifyClient
mv src/soulspot/infrastructure/integrations/spotify_client.py \
   src/soulspot/plugins/spotify/client.py

# Update imports in tests
sed -i 's|infrastructure.integrations.spotify_client|plugins.spotify.client|g' tests/**/*.py
```

**Status:** 🔵 Not Started  
**Depends On:** Phase 0 complete  
**Blocks:** Task 1.2

---

### Task 1.2: Refactor SpotifyClient → SpotifyPlugin

**File:** `src/soulspot/infrastructure/plugins/spotify/plugin.py`

**Strategy:** Wrapper around existing `SpotifyClient`.

**Create:**
```python
from ....domain.ports.plugin import IPlugin, ServiceSession
from .client import SpotifyClient  # Existing client

class SpotifyPlugin(IPlugin):
    """Spotify plugin implementing IPlugin interface."""
    
    service_name = "spotify"
    service_version = "1.0.0"
    service_display_name = "Spotify"
    
    def __init__(self, client_id: str, client_secret: str):
        self._client = SpotifyClient(client_id, client_secret)
    
    # === Implement all IPlugin methods ===
    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        return self._client.get_authorization_url(redirect_uri, state)
    
    async def authenticate(self, code: str, redirect_uri: str) -> ServiceSession:
        token_data = await self._client.exchange_code(code, redirect_uri)
        return ServiceSession(
            access_token=token_data['access_token'],
            refresh_token=token_data['refresh_token'],
            expires_at=token_data['expires_at']
        )
    
    async def get_user_playlists(self, session: ServiceSession) -> list[Playlist]:
        # Use existing client logic
        playlists_data = await self._client.get_current_user_playlists(
            session.access_token
        )
        return [self._map_playlist(p) for p in playlists_data]
    
    # ... implement all other methods
    
    # === Capabilities ===
    def supports_lyrics(self) -> bool:
        return False  # Spotify API doesn't provide lyrics
    
    def supports_high_res_audio(self) -> bool:
        return False  # Max 320kbps
    
    def max_audio_quality(self) -> str:
        return "320kbps"
```

**Status:** 🔵 Not Started  
**Depends On:** Task 1.1

---

### Task 1.3: Update Tests

**Files:**
- `tests/unit/infrastructure/plugins/test_spotify_plugin.py`
- Update existing Spotify tests to use `SpotifyPlugin`

**Add:**
```python
@pytest.mark.asyncio
async def test_spotify_plugin_implements_interface():
    """Ensure SpotifyPlugin implements IPlugin."""
    plugin = SpotifyPlugin(client_id="test", client_secret="test")
    
    assert plugin.service_name == "spotify"
    assert hasattr(plugin, 'get_user_playlists')
    assert hasattr(plugin, 'authenticate')
    # ... check all methods

@pytest.mark.asyncio
async def test_spotify_plugin_get_playlists(mock_session):
    """Test playlist retrieval."""
    plugin = SpotifyPlugin(client_id="test", client_secret="test")
    
    playlists = await plugin.get_user_playlists(mock_session)
    
    assert len(playlists) > 0
    assert all(isinstance(p, Playlist) for p in playlists)
```

**Status:** 🔵 Not Started  
**Depends On:** Task 1.2

---

## Success Criteria

**Phase 0 Complete When:**
- ✅ `IPlugin` interface defined
- ✅ `PluginManager` functional
- ✅ Service layer uses `PluginManager`
- ✅ FastAPI registers plugins on startup
- ✅ SessionManager handles multi-service sessions
- ✅ All existing tests pass (Spotify still works!)

**Phase 1 Complete When:**
- ✅ `SpotifyPlugin` implements `IPlugin`
- ✅ Spotify works via plugin system
- ✅ Old `SpotifyClient` marked `@deprecated`
- ✅ Tests pass for both old + new code paths

---

## Risk Mitigation

**Risk:** Breaking existing Spotify functionality during refactor.

**Mitigation:**
1. Keep old `SpotifyClient` working during Phase 0
2. Add `SpotifyPlugin` in parallel (Phase 1)
3. Run both code paths side-by-side
4. Compare outputs (should be identical)
5. Only remove old code when new code proven stable (2 weeks)

**Rollback Plan:**
- Git feature branch: `feature/plugin-system`
- Daily commits with descriptive messages
- If Phase 0 fails → revert branch, back to `main`

---

## Timeline

| Week | Phase | Tasks | Deliverable |
|------|-------|-------|-------------|
| 1 | Phase 0 (Part 1) | 0.1, 0.2, 0.5 | Plugin infrastructure |
| 2 | Phase 0 (Part 2) | 0.3, 0.4 | Service layer + DI |
| 3 | Phase 1 (Part 1) | 1.1, 1.2 | SpotifyPlugin |
| 4 | Phase 1 (Part 2) | 1.3, cleanup | Tests + stabilization |

**Total:** 4 weeks (1 month)

---

## Next Steps

**After this plan is approved:**
1. Create GitHub Issues from tasks (0.1 → Issue #1, 0.2 → Issue #2, etc.)
2. Start with Task 0.1 (IPlugin interface)
3. Daily progress updates
4. Weekly review meetings

---

**Status:** 📝 Draft  
**Last Updated:** 2025-12-10  
**Approval Needed:** Yes
