# Database Module - Version 3.0

## Overview

The **Database Module** is a core infrastructure module that manages all database read/write operations for the entire SoulSpot Bridge system. All other modules access the database exclusively through the Database Module, which provides caching, transaction management, and query optimization.

## Why a Dedicated Database Module?

### Problems with Direct Database Access

**Without Database Module (Version 2.x):**
```python
# ❌ Every module has direct SQLAlchemy access
# In Spotify module:
async with session_factory() as session:
    result = await session.execute(select(Track).where(...))
    
# In Soulseek module:
async with session_factory() as session:
    result = await session.execute(select(Download).where(...))
```

**Problems:**
- 🔴 Each module manages its own database connections
- 🔴 No central caching strategy
- 🔴 Duplicate queries across modules
- 🔴 Hard to optimize database performance
- 🔴 Transaction boundaries unclear
- 🔴 Schema migrations affect all modules
- 🔴 No query auditing/logging

### Benefits of Database Module

**With Database Module (Version 3.0):**
```python
# ✅ All database access through Database Module
# In Spotify module:
track = await db_module.get("track", track_id)
await db_module.save("track", track_data)

# In Soulseek module:
download = await db_module.get("download", download_id)
await db_module.update("download", download_id, {"status": "completed"})
```

**Benefits:**
- ✅ **Central caching**: Query results cached automatically
- ✅ **Connection pooling**: Single pool for entire system
- ✅ **Query optimization**: Database Module can batch, deduplicate, optimize
- ✅ **Transaction management**: Clear transaction boundaries
- ✅ **Schema abstraction**: Modules don't know database schema details
- ✅ **Easy testing**: Mock Database Module instead of entire database
- ✅ **Query auditing**: All queries logged in one place
- ✅ **Performance monitoring**: Track slow queries, connection usage
- ✅ **Migration safety**: Database Module handles schema changes

## Architecture

### Module Structure

```
modules/database/
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── architecture.md      # Database design, caching strategy
│   ├── api.md              # Database Module API
│   ├── events.md           # Database events (cache invalidation)
│   ├── configuration.md    # Database configuration
│   └── development.md      # Development guide
│
├── backend/
│   ├── api/
│   │   └── routes.py       # Health check, stats endpoints
│   │
│   ├── application/
│   │   ├── services/
│   │   │   ├── query_service.py      # Query execution
│   │   │   ├── cache_service.py      # Cache management
│   │   │   └── transaction_service.py # Transaction management
│   │   └── use_cases/
│   │       ├── get_entity.py
│   │       ├── save_entity.py
│   │       └── query_entities.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── query_result.py
│   │   │   └── cache_entry.py
│   │   ├── value_objects/
│   │   │   ├── entity_type.py
│   │   │   └── query_filter.py
│   │   └── ports/
│   │       ├── repository_port.py
│   │       └── cache_port.py
│   │
│   ├── infrastructure/
│   │   ├── repositories/
│   │   │   ├── sqlalchemy_repository.py
│   │   │   └── cache_repository.py
│   │   ├── cache/
│   │   │   ├── redis_cache.py         # Optional: Redis cache
│   │   │   └── memory_cache.py        # In-memory cache
│   │   └── migrations/
│   │       └── alembic/               # Database migrations
│   │
│   └── config/
│       └── settings.py
│
├── frontend/
│   └── cards/
│       └── database_stats_card.html   # Database statistics
│
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

### Database Module is NOT a submodule

**Important:** The Database Module is a **standalone core module**, not a submodule of another module. It sits at the same level as Spotify, Soulseek, etc.

```
modules/
├── database/          # ✅ Core infrastructure module
├── soulseek/          # Feature module (uses database/)
├── spotify/           # Feature module (uses database/)
├── metadata/          # Feature module (uses database/)
└── library/           # Feature module (uses database/)
```

## Configuration

### Simple Configuration (Version 3.0)

```bash
# .env or onboarding configuration
DATABASE=/config/soulspot.db
```

**Not this:**
```bash
# ❌ Old style (Version 2.x)
DATABASE_URL=sqlite+aiosqlite:///config/soulspot.db
```

**Why simpler?**
- Database Module handles database driver selection internally
- Modules don't need to know SQLAlchemy details
- Easy to switch from SQLite to PostgreSQL without changing config format

### Internal Configuration

```python
# modules/database/backend/config/settings.py
class DatabaseSettings:
    """
    Database Module configuration.
    
    Hey future me - we use SQLite with WAL mode for better concurrency.
    For production, users can switch to PostgreSQL by just changing
    DATABASE_TYPE in config. The Database Module handles the rest.
    """
    
    # User-facing config (simple)
    database_path: str = "/config/soulspot.db"
    database_type: str = "sqlite"  # or "postgresql"
    
    # Internal config (Database Module manages this)
    connection_pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    cache_ttl: int = 300  # 5 minutes
    cache_max_size: int = 1000
    enable_query_logging: bool = True
    
    @property
    def database_url(self) -> str:
        """
        Internal database URL for SQLAlchemy.
        
        This is NOT exposed to other modules. Database Module
        constructs this based on user's simple config.
        """
        if self.database_type == "sqlite":
            return f"sqlite+aiosqlite:///{self.database_path}"
        elif self.database_type == "postgresql":
            # Parse from DATABASE=/host:port/dbname format
            return self._construct_postgres_url()
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
```

## Database Module API

### Basic Operations

All modules interact with the database through these simple operations:

```python
# modules/database/backend/application/services/database_service.py
class DatabaseService:
    """
    Central database service for all modules.
    
    Hey future me - this is the ONLY way modules should access the database.
    Direct SQLAlchemy usage is forbidden in feature modules.
    """
    
    async def get(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> dict | None:
        """
        Get a single entity by ID.
        
        Args:
            entity_type: Entity type (e.g., "track", "download", "playlist")
            entity_id: Entity ID (UUID or other identifier)
            
        Returns:
            Entity data as dict, or None if not found
            
        Examples:
            >>> track = await db_service.get("track", "spotify:123")
            >>> print(track["title"])
            "Let It Be"
            
        Notes:
            - Results are cached automatically
            - Cache is invalidated on save/update/delete
        """
        # Check cache first
        cached = await self.cache_service.get(entity_type, entity_id)
        if cached:
            return cached
            
        # Query database
        result = await self.query_service.get_by_id(entity_type, entity_id)
        
        # Cache result
        if result:
            await self.cache_service.set(entity_type, entity_id, result)
            
        return result
    
    async def save(
        self, 
        entity_type: str, 
        entity_data: dict
    ) -> str:
        """
        Save a new entity.
        
        Args:
            entity_type: Entity type (e.g., "track", "download")
            entity_data: Entity data as dict
            
        Returns:
            Entity ID of created entity
            
        Examples:
            >>> track_id = await db_service.save("track", {
            ...     "spotify_id": "spotify:123",
            ...     "title": "Let It Be",
            ...     "artist": "The Beatles"
            ... })
            
        Raises:
            DatabaseError: If save fails
        """
        # Validate entity data
        self._validate_entity(entity_type, entity_data)
        
        # Save to database
        entity_id = await self.query_service.insert(entity_type, entity_data)
        
        # Invalidate related caches
        await self.cache_service.invalidate_pattern(entity_type)
        
        # Publish event
        await self.event_bus.publish(f"database.{entity_type}.created", {
            "entity_id": entity_id,
            "entity_type": entity_type
        })
        
        return entity_id
    
    async def update(
        self, 
        entity_type: str, 
        entity_id: str, 
        updates: dict
    ) -> bool:
        """
        Update an existing entity.
        
        Args:
            entity_type: Entity type
            entity_id: Entity ID
            updates: Fields to update
            
        Returns:
            True if updated, False if not found
            
        Examples:
            >>> await db_service.update("download", "dl-456", {
            ...     "status": "completed",
            ...     "completed_at": datetime.now()
            ... })
        """
        success = await self.query_service.update(entity_type, entity_id, updates)
        
        if success:
            # Invalidate cache
            await self.cache_service.invalidate(entity_type, entity_id)
            
            # Publish event
            await self.event_bus.publish(f"database.{entity_type}.updated", {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "fields": list(updates.keys())
            })
            
        return success
    
    async def delete(
        self, 
        entity_type: str, 
        entity_id: str
    ) -> bool:
        """Delete an entity."""
        success = await self.query_service.delete(entity_type, entity_id)
        
        if success:
            await self.cache_service.invalidate(entity_type, entity_id)
            await self.event_bus.publish(f"database.{entity_type}.deleted", {
                "entity_id": entity_id,
                "entity_type": entity_type
            })
            
        return success
    
    async def query(
        self, 
        entity_type: str, 
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> list[dict]:
        """
        Query entities with filters.
        
        Args:
            entity_type: Entity type to query
            filters: Filter conditions (e.g., {"status": "pending"})
            order_by: Sort field (e.g., "created_at DESC")
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of entities matching filters
            
        Examples:
            >>> pending = await db_service.query("download", 
            ...     filters={"status": "pending"},
            ...     order_by="created_at DESC",
            ...     limit=10
            ... )
            
        Notes:
            - Query results are cached for 5 minutes by default
            - Cache key includes all parameters
        """
        # Generate cache key
        cache_key = self._make_query_cache_key(
            entity_type, filters, order_by, limit, offset
        )
        
        # Check cache
        cached = await self.cache_service.get_query(cache_key)
        if cached:
            return cached
            
        # Execute query
        results = await self.query_service.query(
            entity_type, filters, order_by, limit, offset
        )
        
        # Cache results
        await self.cache_service.set_query(cache_key, results)
        
        return results
    
    async def count(
        self, 
        entity_type: str, 
        filters: dict | None = None
    ) -> int:
        """
        Count entities matching filters.
        
        Examples:
            >>> total_downloads = await db_service.count("download")
            >>> pending_downloads = await db_service.count("download", 
            ...     filters={"status": "pending"}
            ... )
        """
        return await self.query_service.count(entity_type, filters)
    
    async def transaction(self):
        """
        Start a database transaction.
        
        Examples:
            >>> async with db_service.transaction() as tx:
            ...     await tx.save("track", track_data)
            ...     await tx.save("download", download_data)
            ...     # Both saved atomically, or both rolled back
        """
        return self.transaction_service.begin()
```

### Example Usage in Feature Modules

**Spotify Module using Database Module:**

```python
# modules/spotify/backend/application/services/playlist_service.py
class PlaylistService:
    """
    Spotify playlist management service.
    
    Hey future me - we no longer use SQLAlchemy directly.
    All database operations go through the Database Module.
    """
    
    def __init__(
        self,
        db_service: DatabaseService,  # Injected
        spotify_client: SpotifyClient
    ):
        self.db = db_service
        self.spotify = spotify_client
    
    async def sync_playlists(self, user_id: str) -> list[dict]:
        """
        Sync user's playlists from Spotify to database.
        
        This method fetches playlists from Spotify API and saves them
        to the database via the Database Module. We don't touch
        SQLAlchemy or know anything about database schema.
        """
        # Fetch from Spotify API
        spotify_playlists = await self.spotify.get_user_playlists(user_id)
        
        synced_playlists = []
        for playlist_data in spotify_playlists:
            # Check if already exists in database
            existing = await self.db.get("playlist", playlist_data["spotify_id"])
            
            if existing:
                # Update existing playlist
                await self.db.update("playlist", playlist_data["spotify_id"], {
                    "name": playlist_data["name"],
                    "track_count": playlist_data["track_count"],
                    "last_synced_at": datetime.now()
                })
            else:
                # Save new playlist
                playlist_id = await self.db.save("playlist", {
                    "spotify_id": playlist_data["spotify_id"],
                    "user_id": user_id,
                    "name": playlist_data["name"],
                    "track_count": playlist_data["track_count"],
                    "created_at": datetime.now(),
                    "last_synced_at": datetime.now()
                })
            
            synced_playlists.append(playlist_data)
        
        return synced_playlists
    
    async def get_user_playlists(self, user_id: str) -> list[dict]:
        """Get user's playlists from database (cached)."""
        return await self.db.query("playlist", filters={"user_id": user_id})
```

**Soulseek Module using Database Module:**

```python
# modules/soulseek/submodules/downloads/backend/application/services/download_service.py
class DownloadService:
    """
    Download management service.
    
    Hey future me - same pattern as Spotify. All database access
    goes through Database Module. No SQLAlchemy imports here.
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        slskd_client: SlskdClient
    ):
        self.db = db_service
        self.slskd = slskd_client
    
    async def start_download(
        self, 
        track_id: str, 
        search_result: dict
    ) -> str:
        """
        Start a download.
        
        This saves the download record to database and initiates
        the download via slskd. Database Module handles all
        database operations and caching.
        """
        # Create download record
        download_id = await self.db.save("download", {
            "track_id": track_id,
            "status": "pending",
            "file_path": search_result["file_path"],
            "username": search_result["username"],
            "quality_score": search_result["quality_score"],
            "created_at": datetime.now()
        })
        
        # Start download via slskd
        slskd_download_id = await self.slskd.start_download(
            username=search_result["username"],
            file_path=search_result["file_path"]
        )
        
        # Update download with slskd ID
        await self.db.update("download", download_id, {
            "slskd_download_id": slskd_download_id,
            "status": "downloading",
            "started_at": datetime.now()
        })
        
        return download_id
    
    async def get_download_queue(self) -> list[dict]:
        """Get all pending/downloading items (cached query)."""
        return await self.db.query("download",
            filters={"status": ["pending", "downloading"]},
            order_by="created_at ASC"
        )
    
    async def mark_completed(self, download_id: str, file_path: str):
        """Mark download as completed."""
        await self.db.update("download", download_id, {
            "status": "completed",
            "completed_at": datetime.now(),
            "local_file_path": file_path
        })
```

## Caching Strategy

### Why Caching Matters

Without caching, every module query hits the database:

```python
# ❌ Without caching (slow)
# Module A:
track = await db.query("SELECT * FROM tracks WHERE id = 'spotify:123'")

# Module B (100ms later):
track = await db.query("SELECT * FROM tracks WHERE id = 'spotify:123'")
# Same query executed twice! Database hit twice!
```

With Database Module caching:

```python
# ✅ With caching (fast)
# Module A:
track = await db_service.get("track", "spotify:123")
# Query executed, result cached

# Module B (100ms later):
track = await db_service.get("track", "spotify:123")
# Result returned from cache! No database hit!
```

### Cache Implementation

```python
# modules/database/backend/application/services/cache_service.py
class CacheService:
    """
    Cache management for database queries.
    
    Hey future me - we use a two-tier cache:
    1. In-memory cache (fast, limited size)
    2. Redis cache (optional, for multi-instance deployments)
    
    Cache invalidation happens automatically on writes.
    """
    
    def __init__(
        self,
        memory_cache: MemoryCache,
        redis_cache: RedisCache | None = None,
        ttl: int = 300  # 5 minutes
    ):
        self.memory = memory_cache
        self.redis = redis_cache
        self.ttl = ttl
    
    async def get(self, entity_type: str, entity_id: str) -> dict | None:
        """Get from cache (memory first, then Redis)."""
        key = f"{entity_type}:{entity_id}"
        
        # Try memory cache first (fastest)
        result = self.memory.get(key)
        if result:
            return result
        
        # Try Redis cache (slower but persistent)
        if self.redis:
            result = await self.redis.get(key)
            if result:
                # Populate memory cache
                self.memory.set(key, result, ttl=self.ttl)
                return result
        
        return None
    
    async def set(
        self, 
        entity_type: str, 
        entity_id: str, 
        value: dict
    ):
        """Set in cache (both memory and Redis)."""
        key = f"{entity_type}:{entity_id}"
        
        # Set in memory cache
        self.memory.set(key, value, ttl=self.ttl)
        
        # Set in Redis cache
        if self.redis:
            await self.redis.set(key, value, ttl=self.ttl)
    
    async def invalidate(self, entity_type: str, entity_id: str):
        """
        Invalidate cache entry.
        
        Called automatically when entity is updated/deleted.
        """
        key = f"{entity_type}:{entity_id}"
        self.memory.delete(key)
        if self.redis:
            await self.redis.delete(key)
    
    async def invalidate_pattern(self, pattern: str):
        """
        Invalidate all cache entries matching pattern.
        
        Examples:
            >>> # Invalidate all tracks
            >>> await cache.invalidate_pattern("track:*")
            
            >>> # Invalidate all pending downloads
            >>> await cache.invalidate_pattern("download:*:status:pending")
        """
        self.memory.delete_pattern(pattern)
        if self.redis:
            await self.redis.delete_pattern(pattern)
```

## Module Communication

### Database Module ↔ Feature Modules

**Database Module does NOT call other modules:**
```python
# ❌ Database Module should NOT do this:
class DatabaseService:
    async def save(self, entity_type: str, data: dict):
        entity_id = await self.repository.insert(entity_type, data)
        
        # ❌ DON'T call other modules directly
        await spotify_service.notify_track_saved(entity_id)
```

**Instead, use events:**
```python
# ✅ Database Module publishes events:
class DatabaseService:
    async def save(self, entity_type: str, data: dict):
        entity_id = await self.repository.insert(entity_type, data)
        
        # ✅ Publish event for interested modules
        await self.event_bus.publish(f"database.{entity_type}.created", {
            "entity_id": entity_id,
            "entity_type": entity_type
        })
        
        return entity_id

# ✅ Other modules subscribe to events:
# In Spotify module:
@event_bus.subscribe("database.track.created")
async def on_track_created(event: Event):
    track_id = event.data["entity_id"]
    # Do something with the new track
```

### Inter-Module Communication Flow

```
User Action
    ↓
Spotify Module
    ↓ (save track)
Database Module ──→ Save to DB
    ↓ (publish event)
Event Bus
    ↓ (broadcast)
┌───────┬────────┬──────────┐
│       │        │          │
Metadata  Library  Soulseek  Notifications
Module    Module   Module    Module
│         │        │          │
└─────────┴────────┴──────────┘
(Each subscribes to database.track.created)
```

**Example Flow: User adds track to playlist**

1. User clicks "Add to playlist" (Spotify Module frontend)
2. Spotify Module calls Database Module: `db_service.save("playlist_track", data)`
3. Database Module:
   - Saves to database
   - Invalidates relevant caches
   - Publishes event: `database.playlist_track.created`
4. Event Bus broadcasts to all modules
5. Library Module (subscribed) receives event, updates library view
6. Metadata Module (subscribed) receives event, fetches metadata
7. **No direct module-to-module calls!** All through Database Module and events.

## Entity Types and Schema

### Entity Type Registry

The Database Module maintains a registry of all entity types:

```python
# modules/database/backend/domain/entities/entity_registry.py
class EntityRegistry:
    """
    Registry of all entity types in the system.
    
    Hey future me - this is where we define all tables/entities.
    Each module registers its entity types during initialization.
    """
    
    _registry: dict[str, EntitySchema] = {}
    
    @classmethod
    def register(cls, entity_type: str, schema: EntitySchema):
        """
        Register an entity type.
        
        Called by modules during startup to register their entities.
        
        Examples:
            >>> # In Spotify module __init__.py
            >>> EntityRegistry.register("playlist", PlaylistSchema)
            >>> EntityRegistry.register("track", TrackSchema)
            
            >>> # In Soulseek module __init__.py
            >>> EntityRegistry.register("download", DownloadSchema)
            >>> EntityRegistry.register("search_result", SearchResultSchema)
        """
        if entity_type in cls._registry:
            raise ValueError(f"Entity type '{entity_type}' already registered")
        cls._registry[entity_type] = schema
    
    @classmethod
    def get_schema(cls, entity_type: str) -> EntitySchema:
        """Get schema for entity type."""
        if entity_type not in cls._registry:
            raise ValueError(f"Unknown entity type: {entity_type}")
        return cls._registry[entity_type]
    
    @classmethod
    def list_entity_types(cls) -> list[str]:
        """List all registered entity types."""
        return list(cls._registry.keys())
```

### Example Entity Schema

```python
# modules/spotify/backend/infrastructure/schemas/playlist_schema.py
from modules.database.backend.domain.entities import EntitySchema

class PlaylistSchema(EntitySchema):
    """
    Schema definition for Spotify playlists.
    
    This tells the Database Module how to store playlists.
    """
    
    entity_type = "playlist"
    table_name = "spotify_playlists"  # Prefixed to avoid conflicts
    
    fields = {
        "id": {"type": "uuid", "primary_key": True},
        "spotify_id": {"type": "string", "unique": True, "index": True},
        "user_id": {"type": "string", "index": True},
        "name": {"type": "string"},
        "description": {"type": "text", "nullable": True},
        "track_count": {"type": "integer", "default": 0},
        "created_at": {"type": "datetime"},
        "last_synced_at": {"type": "datetime", "nullable": True}
    }
    
    indexes = [
        {"fields": ["user_id", "spotify_id"], "unique": True}
    ]
```

## Error Handling

All Database Module errors follow the standard error format:

```python
# Example: Connection error
{
    "code": "DATABASE_CONNECTION_FAILED",
    "message": "Could not connect to database",
    "context": {
        "module": "database",
        "operation": "get",
        "database_path": "/config/soulspot.db"
    },
    "resolution": """
        1. Check if database file exists: ls -la /config/soulspot.db
        2. Check file permissions: should be writable
        3. Check disk space: df -h /config
        4. Check database file is not corrupted: sqlite3 /config/soulspot.db "PRAGMA integrity_check"
    """,
    "docs_url": "https://docs.soulspot.app/troubleshooting/database-errors"
}
```

```python
# Example: Query timeout
{
    "code": "DATABASE_QUERY_TIMEOUT",
    "message": "Query exceeded timeout of 30 seconds",
    "context": {
        "module": "database",
        "operation": "query",
        "entity_type": "download",
        "timeout": 30,
        "query": "SELECT * FROM downloads WHERE status = 'pending'"
    },
    "resolution": """
        This query is taking too long. Possible causes:
        1. Too many results - add limit/pagination
        2. Missing index - check query filters use indexed fields
        3. Database locked - check for long-running transactions
        4. Slow disk - check disk I/O performance
    """,
    "docs_url": "https://docs.soulspot.app/troubleshooting/slow-queries"
}
```

## Testing

### Mocking Database Module

Feature modules can easily mock the Database Module for testing:

```python
# tests/unit/test_spotify_playlist_service.py
from unittest.mock import AsyncMock
import pytest

@pytest.fixture
def mock_db_service():
    """Mock Database Module for testing."""
    mock = AsyncMock()
    
    # Mock get() to return test data
    mock.get.return_value = {
        "id": "playlist-123",
        "name": "Test Playlist",
        "track_count": 42
    }
    
    # Mock save() to return ID
    mock.save.return_value = "playlist-456"
    
    return mock

async def test_sync_playlists(mock_db_service):
    """Test playlist sync without real database."""
    service = PlaylistService(
        db_service=mock_db_service,  # Inject mock
        spotify_client=mock_spotify_client
    )
    
    playlists = await service.sync_playlists("user-123")
    
    # Verify database interactions
    assert mock_db_service.save.called
    assert mock_db_service.update.called
```

## Performance Monitoring

The Database Module provides performance metrics:

```python
# GET /api/database/stats
{
    "connections": {
        "active": 5,
        "idle": 3,
        "total": 8,
        "max_pool_size": 10
    },
    "cache": {
        "memory": {
            "hit_rate": 0.87,  # 87% cache hit rate
            "size": 456,
            "max_size": 1000
        },
        "redis": {
            "hit_rate": 0.92,
            "size": 1234
        }
    },
    "queries": {
        "total": 12345,
        "slow_queries": 3,  # Queries > 1s
        "average_time_ms": 15.3
    },
    "top_slow_queries": [
        {
            "query": "SELECT * FROM downloads WHERE ...",
            "count": 23,
            "avg_time_ms": 1234
        }
    ]
}
```

## Migration from Version 2.x

### Before (Direct SQLAlchemy):

```python
# ❌ modules/spotify/backend/infrastructure/repositories/playlist_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class PlaylistRepository:
    async def get_by_id(self, session: AsyncSession, playlist_id: str):
        result = await session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        return result.scalar_one_or_none()
```

### After (Database Module):

```python
# ✅ modules/spotify/backend/application/services/playlist_service.py
class PlaylistService:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def get_playlist(self, playlist_id: str):
        return await self.db.get("playlist", playlist_id)
```

**Migration steps:**
1. Database Module implemented first (Phase 1)
2. Modules updated one-by-one to use Database Module (Phase 2-3)
3. Direct SQLAlchemy imports removed from feature modules (Phase 4)

## Summary

### Key Points

1. **Database Module is a core infrastructure module** (not a submodule)
2. **All feature modules access database ONLY through Database Module**
3. **Simple configuration**: `DATABASE=/config/soulspot.db` (not `sqlite+aiosqlite://...`)
4. **Automatic caching**: Query results cached automatically
5. **Event-driven**: Database Module publishes events on changes
6. **No direct module-to-module calls**: Communication via events
7. **Easy testing**: Mock Database Module instead of entire database
8. **Performance monitoring**: Built-in query logging and statistics

### Benefits

✅ **Centralized data access**: Single source of truth  
✅ **Better performance**: Automatic caching, connection pooling  
✅ **Easier testing**: Mock one module instead of entire database  
✅ **Clear boundaries**: Modules don't touch SQLAlchemy  
✅ **Query optimization**: Database Module can batch, optimize, deduplicate  
✅ **No merge conflicts**: Modules work independently  
✅ **Schema abstraction**: Easy to switch databases  
✅ **Monitoring**: Track all queries in one place  

### Next Steps

1. Implement Database Module (core functionality)
2. Implement caching layer (memory + optional Redis)
3. Update Soulseek module to use Database Module
4. Update Spotify module to use Database Module
5. Remove direct SQLAlchemy usage from feature modules
6. Add performance monitoring dashboard
