# Performance Optimization Guide

## Overview

This document describes the performance optimizations implemented in SoulSpot as part of the Performance & Scalability epic. These optimizations focus on query performance, database indexing, connection pooling, batch operations, and caching strategies.

## Table of Contents

1. [Query Optimization](#query-optimization)
2. [Database Indexes](#database-indexes)
3. [Connection Pool Tuning](#connection-pool-tuning)
4. [Batch Operations](#batch-operations)
5. [Enhanced Caching](#enhanced-caching)
6. [Performance Monitoring](#performance-monitoring)
7. [Configuration Guide](#configuration-guide)

---

## Query Optimization

### Eager Loading (N+1 Query Prevention)

We've added eager loading to prevent N+1 query problems using SQLAlchemy's `selectinload` strategy.

**Optimized Repositories:**

#### PlaylistRepository
- `get_by_id()` - Eagerly loads `playlist_tracks`
- `get_by_spotify_uri()` - Eagerly loads `playlist_tracks`
- `list_all()` - Eagerly loads `playlist_tracks`

#### DownloadRepository
- `get_by_id()` - Eagerly loads `track`
- `get_by_track()` - Eagerly loads `track`

**Performance Impact:**
- **Before:** 1 query + N queries (one per related item)
- **After:** 2 queries (one for parent, one for all children)
- **Improvement:** ~50-80% reduction in database round trips for list operations

### Batch Operations

Added bulk insert/update methods to reduce database round trips:

```python
# TrackRepository
await track_repo.add_batch(tracks)      # Insert multiple tracks
await track_repo.update_batch(tracks)   # Update multiple tracks
```

**Performance Impact:**
- **Before:** N separate INSERT/UPDATE statements
- **After:** Batched operations with fewer round trips
- **Improvement:** ~10-50x faster for bulk operations (depending on batch size)

---

## Database Indexes

### Migration: cc17880fff37_add_performance_indexes

New indexes added for common query patterns:

#### 1. Track Indexes

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_tracks_album_track_number` | album_id, track_number | Album track listing with ordering |
| `ix_tracks_album_disc_track` | album_id, disc_number, track_number | Multi-disc album queries |
| `ix_tracks_file_path` | file_path | File system lookups |
| `ix_tracks_updated_at` | updated_at | Change tracking and sync |
| `ix_tracks_last_scanned_at` | last_scanned_at | Library management queries |
| `ix_tracks_broken_updated` | is_broken, updated_at | Broken file monitoring |

#### 2. Album Indexes

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_albums_artist_id` | artist_id | Artist->Albums relationship |
| `ix_albums_updated_at` | updated_at | Change tracking |

#### 3. Artist Indexes

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_artists_updated_at` | updated_at | Change tracking |

#### 4. Download Indexes

| Index Name | Columns | Purpose |
|------------|---------|---------|
| `ix_downloads_status_priority` | status, priority | Queue processing optimization |
| `ix_downloads_completed_at` | completed_at | Completed downloads filtering |

**Performance Impact:**
- **Query Speed:** 2-10x faster for indexed queries
- **Join Performance:** Significant improvement for multi-table queries
- **Sorting:** Much faster ORDER BY on indexed columns

### Running the Migration

```bash
alembic upgrade head
```

**Note:** The migration is idempotent and can be safely re-run.

---

## Connection Pool Tuning

### Enhanced Configuration

New database settings for production optimization:

```python
class DatabaseSettings(BaseSettings):
    pool_size: int = 5              # Base pool size
    max_overflow: int = 10          # Additional connections allowed
    pool_timeout: float = 30.0      # Wait time for connection (seconds)
    pool_recycle: int = 3600        # Connection recycle time (seconds)
    pool_pre_ping: bool = True      # Test connections before use
```

### Environment Variables

Configure via environment variables:

```bash
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30.0
DATABASE_POOL_RECYCLE=3600
DATABASE_POOL_PRE_PING=true
```

### Recommended Settings

#### Development
```
POOL_SIZE=3
MAX_OVERFLOW=5
POOL_TIMEOUT=10.0
```

#### Production (Low Load)
```
POOL_SIZE=5
MAX_OVERFLOW=10
POOL_TIMEOUT=30.0
```

#### Production (High Load)
```
POOL_SIZE=20
MAX_OVERFLOW=30
POOL_TIMEOUT=60.0
```

### Monitoring Pool Health

```python
from soulspot.infrastructure.persistence.database import Database

# Get pool statistics
stats = db.get_pool_stats()
print(stats)
# {
#     "pool_size": 5,
#     "checked_out": 2,
#     "overflow": 0,
#     "checked_in": 3,
#     ...
# }
```

**Key Metrics to Monitor:**
- `checked_out`: Currently active connections
- `overflow`: Overflow connections in use
- Alert when: `checked_out + overflow` approaches `pool_size + max_overflow`

---

## Batch Operations

### Batch Processing Framework

Generic batch processor for efficient bulk operations:

```python
from soulspot.application.services.batch_processor import BatchProcessor

# Define processor function
async def process_items(items: list[Track]) -> list[Track]:
    # Process batch of items
    return processed_items

# Create batch processor
processor = BatchProcessor(
    batch_size=50,
    processor_func=process_items,
    max_wait_time=5.0,
    auto_flush=True
)

# Add items (auto-flushes when batch_size reached)
for item in items:
    await processor.add(item)

# Flush remaining
result = await processor.flush()
```

### Spotify Batch Processing

Specialized batch processor for Spotify API:

```python
from soulspot.application.services.batch_processor import SpotifyBatchProcessor

processor = SpotifyBatchProcessor(spotify_client)

# Queue tracks for batch fetching
await processor.add_track("track_id_1")
await processor.add_track("track_id_2")
# ... up to 50 tracks

# Flush all batches
results = await processor.flush_all()
```

**Performance Impact:**
- **Spotify API:** Up to 50x fewer requests (1 request per 50 tracks vs 50 requests)
- **Rate Limiting:** Better rate limit compliance
- **Latency:** Reduced overall latency for bulk operations

---

## Enhanced Caching

### LRU Cache with Metrics

New caching implementation with advanced features:

```python
from soulspot.application.cache.enhanced_cache import LRUCache

# Create cache
cache = LRUCache[str, Track](max_size=1000)

# Basic operations
await cache.set("track_123", track, ttl_seconds=3600)
track = await cache.get("track_123")

# Batch operations
await cache.set_batch({"key1": val1, "key2": val2})

# Metrics
metrics = cache.get_metrics()
print(f"Hit rate: {metrics.hit_rate}%")

# Statistics
stats = cache.get_stats()
print(f"Utilization: {stats['utilization_percent']}%")
```

### Cache Warming

Pre-populate cache for hot paths:

```python
from soulspot.application.cache.enhanced_cache import CacheWarmer

warmer = CacheWarmer(cache)

# Warm from data source
async def load_track(track_id: str) -> Track:
    return await track_repo.get_by_id(track_id)

await warmer.warm_from_loader(
    keys=["track_1", "track_2", "track_3"],
    loader=load_track,
    ttl_seconds=3600
)
```

### Cache Features

1. **LRU Eviction**: Automatically evicts least recently used items when max size reached
2. **TTL Expiration**: Automatic expiration after configured time
3. **Metrics Tracking**:
   - Hits / Misses
   - Hit Rate (%)
   - Evictions
   - Writes
4. **Batch Operations**: Efficient bulk caching
5. **Thread-Safe**: Async lock protection

**Performance Impact:**
- **Cache Hit Rate:** Target 70%+ for hot paths
- **Latency Reduction:** 10-100x faster for cache hits vs database queries
- **Database Load:** Significant reduction in query load

---

## Performance Monitoring

### Key Metrics to Track

#### 1. Query Performance
```python
# Monitor slow queries
# Log queries taking >100ms in production
# DATABASE_ECHO=true for development debugging
```

#### 2. Connection Pool
```python
stats = db.get_pool_stats()
# Alert if: checked_out + overflow > 80% of max
```

#### 3. Cache Effectiveness
```python
metrics = cache.get_metrics()
# Alert if: hit_rate < 70%
# Check: evictions (should be low for optimal sizing)
```

#### 4. Batch Processing
```python
result = await processor.flush()
# Monitor: success_rate (should be >95%)
# Monitor: failure_count (investigate spikes)
```

### Health Check Integration

Add pool stats to health endpoint:

```python
@router.get("/health/database")
async def database_health(db: Database = Depends(get_database)):
    pool_stats = db.get_pool_stats()
    
    # Calculate health status
    utilization = (
        pool_stats["checked_out"] / 
        (pool_stats["pool_size"] + pool_stats["max_overflow"])
    )
    
    status = "healthy" if utilization < 0.7 else "degraded"
    
    return {
        "status": status,
        "pool": pool_stats,
        "utilization": f"{utilization:.1%}"
    }
```

---

## Configuration Guide

### Complete Performance Configuration

`.env` file example:

```bash
# Database Connection Pool
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30.0
DATABASE_POOL_RECYCLE=3600
DATABASE_POOL_PRE_PING=true

# Query Debugging (disable in production)
DATABASE_ECHO=false

# For production monitoring
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Performance Tuning Checklist

- [ ] Run database migration for indexes
- [ ] Configure connection pool for workload
- [ ] Set up cache monitoring
- [ ] Enable slow query logging
- [ ] Monitor connection pool utilization
- [ ] Track cache hit rates
- [ ] Review batch operation metrics
- [ ] Set up alerting for degraded performance

### Rollback Strategy

If performance issues occur:

1. **Indexes:** Can be dropped individually:
   ```sql
   DROP INDEX ix_tracks_album_track_number;
   ```

2. **Connection Pool:** Revert to defaults:
   ```bash
   unset DATABASE_POOL_SIZE
   unset DATABASE_MAX_OVERFLOW
   ```

3. **Migration:** Rollback via Alembic:
   ```bash
   alembic downgrade -1
   ```

---

## Best Practices

### Query Optimization
1. ✅ Use eager loading for known relationships
2. ✅ Add batch operations for bulk inserts/updates
3. ✅ Use pagination for large result sets
4. ✅ Profile queries in development
5. ❌ Avoid SELECT * - fetch only needed columns

### Caching
1. ✅ Cache read-heavy, rarely-changing data
2. ✅ Use appropriate TTL values
3. ✅ Monitor hit rates
4. ✅ Implement cache warming for critical paths
5. ❌ Don't cache frequently-changing data

### Connection Pool
1. ✅ Size pool for concurrent request load
2. ✅ Enable pool_pre_ping in production
3. ✅ Monitor pool exhaustion
4. ✅ Set reasonable timeouts
5. ❌ Don't set pool too large (database connection limits)

### Batch Operations
1. ✅ Use for bulk data operations
2. ✅ Set appropriate batch sizes (50-100)
3. ✅ Handle partial failures gracefully
4. ✅ Respect external API rate limits
5. ❌ Don't batch time-sensitive operations

---

## Troubleshooting

### Problem: Slow Queries

**Symptoms:** High response times, database CPU usage

**Solutions:**
1. Check if indexes are applied: `alembic current`
2. Enable query logging: `DATABASE_ECHO=true`
3. Review EXPLAIN QUERY PLAN for slow queries
4. Add missing indexes if needed

### Problem: Connection Pool Exhaustion

**Symptoms:** TimeoutError, "QueuePool limit exceeded"

**Solutions:**
1. Increase `POOL_SIZE` and `MAX_OVERFLOW`
2. Check for connection leaks (unreleased sessions)
3. Review slow queries holding connections
4. Monitor `get_pool_stats()` for utilization

### Problem: Low Cache Hit Rate

**Symptoms:** Hit rate <50%, high database load

**Solutions:**
1. Increase cache `max_size`
2. Adjust TTL values
3. Implement cache warming
4. Review access patterns (may not be cache-friendly)

### Problem: Batch Processing Failures

**Symptoms:** High failure_count, slow bulk operations

**Solutions:**
1. Reduce batch_size
2. Add retry logic with exponential backoff
3. Check external API rate limits
4. Review error logs for specific failures

---

## Performance Benchmarks

### Expected Improvements

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| List playlists with tracks | 1s | 200ms | 5x faster |
| Bulk track insert (100 items) | 5s | 100ms | 50x faster |
| Indexed query (by album) | 500ms | 50ms | 10x faster |
| Cache hit (track metadata) | 100ms | <1ms | 100x faster |
| Spotify batch fetch (50 tracks) | 50s | 1s | 50x faster |

*Actual results may vary based on hardware, data size, and workload*

---

## Additional Resources

- [SQLAlchemy Performance Guide](https://docs.sqlalchemy.org/en/20/faq/performance.html)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [FastAPI Performance Tips](https://fastapi.tiangolo.com/advanced/performance/)
- [Cache Patterns](https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html)

---

## Changelog

### 2025-11-16 - Initial Release
- Added eager loading to prevent N+1 queries
- Created 11 new database indexes
- Enhanced connection pool configuration
- Implemented batch processing framework
- Added LRU cache with metrics
- Created comprehensive documentation
