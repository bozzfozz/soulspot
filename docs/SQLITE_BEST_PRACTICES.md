# SQLite Usage and Best Practices

## Overview
SoulSpot uses SQLite as its default database. This document outlines SQLite-specific considerations, limitations, and best practices for development and production deployment.

## Current Configuration

### Database URL
```
sqlite+aiosqlite:///./soulspot.db
```

### Key Settings
- Async driver: `aiosqlite`
- SQLAlchemy 2.0 async engine
- Connection pooling: Default SQLAlchemy pool

## SQLite-Specific Considerations

### 1. Foreign Keys (CRITICAL)
**Issue:** SQLite has foreign keys DISABLED by default.

**Current Status:** ⚠️ Not explicitly enabled in code

**Solution Required:**
```python
# In database.py or engine setup
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    if "sqlite" in str(dbapi_conn):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

**Impact if not enabled:**
- Orphaned records (e.g., tracks without artists)
- Cascade deletes won't work
- Data integrity violations possible

**Action:** Add pragma in `src/soulspot/infrastructure/persistence/database.py`

### 2. Concurrent Writes
**Issue:** SQLite locks the entire database during write operations.

**Symptoms:**
- `OperationalError: database is locked`
- Write contention in multi-worker setups
- Background workers may conflict with API writes

**Current Mitigation:**
- Single-threaded FastAPI app (mostly)
- Background workers run async but share connection

**Recommendations:**
```python
# Add to database configuration
engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=1,  # SQLite: single writer
    max_overflow=0,  # No overflow connections
    connect_args={
        "timeout": 30,  # Wait up to 30s for lock
    }
)
```

**Retry Logic for Locked Database:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(OperationalError),
)
async def write_with_retry(session, operation):
    """Retry write operations on database lock."""
    await operation(session)
    await session.commit()
```

### 3. Type Affinity (Not Strict Typing)
**Issue:** SQLite uses type affinity, not strict types.

**Example:**
```python
# SQLAlchemy defines: Column(Integer)
# SQLite allows: INSERT INTO table (int_col) VALUES ('text');
```

**Mitigation:**
- Use SQLAlchemy's type coercion (already in place)
- Pydantic validation before DB writes (already in place)
- CHECK constraints for critical columns

**Recommendation:**
```sql
-- Add CHECK constraints in migrations
ALTER TABLE tracks ADD CONSTRAINT check_duration 
    CHECK (duration_ms >= 0 AND typeof(duration_ms) = 'integer');
```

### 4. Transaction Isolation
**Default:** DEFERRED (read doesn't lock, write locks)

**Modes Available:**
- `DEFERRED`: Default, lazy locking
- `IMMEDIATE`: Lock on BEGIN
- `EXCLUSIVE`: Lock entire database

**Recommendation for Critical Operations:**
```python
# For operations requiring consistency
async with session.begin():
    # IMMEDIATE transaction
    await session.execute("BEGIN IMMEDIATE")
    # ... do work ...
```

### 5. Performance Considerations

#### Write Performance
- **Batch Inserts:** Use `session.add_all()` instead of multiple `session.add()`
- **Transaction Batching:** Commit in batches (e.g., every 100 rows)
- **WAL Mode:** Consider Write-Ahead Logging for better concurrency

```python
# Enable WAL mode (recommended for production)
engine = create_async_engine(
    database_url,
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine.sync_engine, "connect")
def enable_wal(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
```

#### Read Performance
- **Indexes:** Ensure proper indexing (check `alembic/versions/cc17880fff37_add_performance_indexes.py`)
- **Query Optimization:** Use `selectinload()` for relationships to avoid N+1 queries

### 6. Database Size Limits
- **Max Database Size:** 281 TB (theoretical)
- **Practical Limit:** ~1 GB for smooth operations
- **Max Row Size:** ~1 GB
- **Max Columns:** 2000 (default), 32767 (configurable)

**Monitoring:**
```python
# Check database size
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();

# Vacuum to reclaim space
VACUUM;
```

### 7. Backup Strategy
SQLite backups are straightforward:

```bash
# Hot backup (while app is running)
sqlite3 soulspot.db ".backup soulspot_backup.db"

# Or use Python
import shutil
shutil.copy2('soulspot.db', 'soulspot_backup.db')
```

**Automated Backup Schedule:**
- Daily backups before midnight
- Keep last 7 days
- Weekly backups (keep last 4)
- Monthly backups (keep last 12)

### 8. Migration Considerations

#### Safe Migrations
SQLite has limited ALTER TABLE support:
- ✅ Can: Rename table, Add column
- ❌ Cannot: Drop column, Modify column type, Add constraint

**Alembic Strategy for Complex Changes:**
```python
def upgrade():
    # 1. Create new table with desired schema
    # 2. Copy data from old table
    # 3. Drop old table
    # 4. Rename new table
    pass
```

**Current Migration Files:**
- `aa15670cdf15_add_library_management_schema.py`
- `bb16770eeg26_add_automation_and_watchlist_schema.py`
- `cc17880fff37_add_performance_indexes.py`
- `0b88b6152c1d_add_dashboard_widget_schema.py`
- `46d1c2c2f85b_add_priority_field_to_downloads.py`

**TODO:** Review each for SQLite compatibility

## When to Migrate Away from SQLite

### Signals:
1. **Database locks** occurring frequently
2. **Concurrent user count** > 10 active users
3. **Database size** approaching 1 GB
4. **Geo-distributed** deployment needed
5. **Replication** requirements

### Migration Path:
SQLite → PostgreSQL

**Advantages of PostgreSQL:**
- Better concurrency (MVCC)
- Full-featured (stored procedures, triggers)
- Better type system
- Network access
- Horizontal scaling options

**Migration Tools:**
- `pgloader` - Automated SQLite to PostgreSQL
- Custom Python script using SQLAlchemy

## Development vs Production

### Development (Current)
```python
SQLITE_DATABASE_URL = "sqlite+aiosqlite:///./soulspot.db"
```
- ✅ Simple setup
- ✅ No external dependencies
- ✅ Fast for small datasets
- ⚠️ Foreign keys need enabling

### Production (Recommendations)
```python
# Option 1: SQLite with optimizations
SQLITE_DATABASE_URL = "sqlite+aiosqlite:///./data/soulspot.db"
+ WAL mode
+ Foreign keys enabled
+ Connection pooling tuned
+ Regular VACUUM
+ Automated backups

# Option 2: PostgreSQL (recommended for >5 concurrent users)
POSTGRES_DATABASE_URL = "postgresql+asyncpg://user:pass@host/db"
```

## Testing Strategy

### Test Database
```python
# tests/conftest.py
@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
```

### Test Concurrent Writes
```python
# tests/integration/test_sqlite_concurrency.py
async def test_concurrent_writes():
    """Test that concurrent writes handle locks gracefully."""
    # ... implementation ...
```

## Monitoring & Observability

### Key Metrics
1. **Database size:** Track growth rate
2. **Lock wait time:** Monitor `database is locked` errors
3. **Query performance:** Slow query log
4. **Connection pool:** Active/idle connections
5. **Transaction rate:** Commits/rollbacks per second

### Logging
```python
# Enable SQLAlchemy logging for debugging
engine = create_async_engine(
    database_url,
    echo=True,  # Log all SQL (development only)
    echo_pool=True,  # Log connection pool events
)
```

## Checklist for Production Deployment

- [ ] Enable foreign keys (PRAGMA foreign_keys=ON)
- [ ] Enable WAL mode (PRAGMA journal_mode=WAL)
- [ ] Set connection timeout (timeout=30 in connect_args)
- [ ] Configure connection pool (pool_size=1, max_overflow=0)
- [ ] Add retry logic for OperationalError
- [ ] Set up automated backups
- [ ] Monitor database size and locks
- [ ] Test concurrent write scenarios
- [ ] Review all migrations for SQLite compatibility
- [ ] Document recovery procedures

## References
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [SQLite in Production](https://www.sqlite.org/whentouse.html)
- [SQLAlchemy SQLite Documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/)

---

**Last Updated:** 2025-11-20  
**Reviewed By:** QA & Test Automation Specialist Agent
