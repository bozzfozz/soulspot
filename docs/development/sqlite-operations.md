# SQLite Operations Guide

## Overview

SoulSpot uses SQLite as its default database for local deployments. This document describes SQLite-specific considerations, configurations, and best practices implemented in the application.

## SQLite Configuration

### Foreign Key Constraints

**Status:** ✅ **ENABLED**

Foreign key constraints are **enabled by default** for all SQLite connections.

**Implementation:**
```python
# src/soulspot/infrastructure/persistence/database.py
@event.listens_for(self._engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
    """Set SQLite pragmas on connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

This ensures referential integrity is maintained across all tables.

### Connection Configuration

SQLite connections are configured with the following parameters:

```python
engine_kwargs = {
    "connect_args": {
        "check_same_thread": False,  # Allow multi-threaded access
        "timeout": 30,  # Wait up to 30 seconds for database lock
    }
}
```

**Key Settings:**
- `check_same_thread=False`: Allows SQLAlchemy async to work correctly
- `timeout=30`: Prevents immediate failures on concurrent writes

## SQLite Limitations & Workarounds

### 1. Concurrent Write Operations

**Limitation:** SQLite locks the entire database during write operations. Only one write can occur at a time.

**Impact:** High-concurrency write workloads may experience `SQLITE_BUSY` or `database is locked` errors.

**Mitigation Strategies:**
- **30-second timeout** configured to allow waiting for lock release
- **Async/await patterns** prevent blocking the main thread during waits
- **Transaction batching** recommended for bulk operations
- **Read operations** are non-blocking and highly concurrent

**When to Consider PostgreSQL:**
- More than 10 concurrent write operations per second
- Multiple background workers performing simultaneous writes
- Production deployments with high user concurrency

### 2. Type Affinity vs. Strict Types

**Limitation:** SQLite uses type affinity rather than strict typing. A TEXT value can be inserted into an INTEGER column.

**Mitigation:**
- **SQLAlchemy ORM** provides type validation before database insertion
- **Pydantic models** validate data types at API boundaries
- **Explicit CHECK constraints** added in migrations where strict typing is critical

**Example:**
```sql
-- Migration: Ensure status is valid
CREATE TABLE downloads (
    id INTEGER PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('pending', 'downloading', 'completed', 'failed'))
);
```

### 3. No Connection Pooling

**Limitation:** SQLite does not benefit from connection pooling like PostgreSQL.

**Implementation:**
```python
# Pool settings NOT applied for SQLite
if "sqlite" in settings.database.url:
    # SQLite-specific config only
    pass
elif "postgresql" in settings.database.url:
    # Pool settings applied
    engine_kwargs.update({
        "pool_size": settings.database.pool_size,
        "max_overflow": settings.database.max_overflow,
    })
```

**Impact:** Connection overhead is minimal for SQLite, so this is not a performance concern.

## Testing with SQLite

### Test Database Configuration

Tests use SQLite in one of two modes:

1. **In-Memory Database** (unit tests):
   ```python
   DATABASE_URL=sqlite+aiosqlite:///:memory:
   ```
   - Fastest performance
   - Isolated per test
   - Lost after test completion

2. **File-Based Database** (integration tests):
   ```python
   DATABASE_URL=sqlite+aiosqlite:///./test_soulspot.db
   ```
   - More realistic behavior
   - Can inspect after test failure
   - Requires cleanup

### Migration Testing

All Alembic migrations are tested against SQLite to ensure compatibility:

```bash
# Test migrations
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**Note:** Some PostgreSQL-specific features (e.g., ARRAY types) require SQLite alternatives in migrations.

## Performance Considerations

### Write-Ahead Logging (WAL)

Consider enabling WAL mode for better concurrent read performance:

```sql
PRAGMA journal_mode=WAL;
```

**Benefits:**
- Readers don't block writers
- Writers don't block readers
- Better performance for read-heavy workloads

**Trade-offs:**
- Slightly more disk space
- Not recommended for network filesystems

**Status:** Currently NOT enabled (default journal mode). Can be added if needed.

### Index Usage

All performance-critical queries have supporting indexes defined in migrations:

```python
# Example: alembic/versions/cc17880fff37_add_performance_indexes.py
op.create_index(
    'ix_downloads_status_priority',
    'downloads',
    ['status', 'priority'],
    unique=False
)
```

## Monitoring

### Database Lock Monitoring

Monitor for database lock errors in logs:

```python
# Errors logged at WARNING level
logger.warning("Database lock timeout: %s", e)
```

**Action Items:**
1. Check for long-running transactions
2. Review concurrent write patterns
3. Consider migration to PostgreSQL if persistent

### Query Performance

Enable SQL logging for debugging:

```bash
# .env
DATABASE_ECHO=true
```

**Note:** Disable in production due to performance overhead.

## Migration to PostgreSQL

When SQLite limitations become a bottleneck, migration to PostgreSQL is straightforward:

1. **Update connection string:**
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost/soulspot
   ```

2. **Install asyncpg:**
   ```bash
   pip install asyncpg
   ```

3. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Update connection pool settings** (automatically applied for PostgreSQL)

**Data Migration:**
```bash
# Export from SQLite
sqlite3 soulspot.db .dump > dump.sql

# Import to PostgreSQL (requires SQL conversion)
# Use tools like pgloader for automated conversion
```

## Security Considerations

### Path Validation

All database file paths should be validated to prevent path traversal:

```python
from soulspot.infrastructure.security import validate_safe_path
from pathlib import Path

# Validate database file is within expected directory
db_path = validate_safe_path(
    "soulspot.db",
    settings.storage.data_path,
    allowed_extensions={".db", ".sqlite", ".sqlite3"}
)
```

### File Permissions

Ensure SQLite database files have appropriate permissions:

```bash
# Recommended permissions
chmod 600 soulspot.db
chmod 700 soulspot.db-wal soulspot.db-shm  # WAL mode files
```

## Troubleshooting

### "database is locked" Errors

**Symptoms:** `OperationalError: database is locked`

**Solutions:**
1. Check for long-running transactions
2. Verify timeout setting (currently 30s)
3. Review concurrent write patterns
4. Consider increasing timeout if temporary spikes
5. Migrate to PostgreSQL for sustained high write volume

### "FOREIGN KEY constraint failed"

**Symptoms:** Insert/update fails with foreign key error

**Solutions:**
1. Verify foreign keys are enabled: `PRAGMA foreign_keys;`
2. Check migration order (dependencies created first)
3. Review cascade delete/update rules

### Performance Degradation

**Symptoms:** Queries slow over time

**Solutions:**
1. Run `VACUUM` to reclaim space and rebuild indexes:
   ```sql
   VACUUM;
   ```
2. Analyze query plans:
   ```sql
   EXPLAIN QUERY PLAN SELECT ...;
   ```
3. Add missing indexes based on slow query logs

## Best Practices

1. ✅ **Keep transactions short** - Minimize database lock time
2. ✅ **Use async/await** - Don't block on database waits
3. ✅ **Batch writes** - Group multiple inserts/updates
4. ✅ **Add indexes** - Support common query patterns
5. ✅ **Monitor logs** - Watch for lock timeout warnings
6. ✅ **Test migrations** - Verify on SQLite before deploy
7. ✅ **Plan for scale** - Know when to migrate to PostgreSQL

## References

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [SQLite Performance Tuning](https://www.sqlite.org/optoverview.html)
- [SQLAlchemy SQLite Dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)

---

**Last Updated:** 2025-11-21  
**Maintained By:** SoulSpot Development Team
