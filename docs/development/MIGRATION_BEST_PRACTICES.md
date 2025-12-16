# Alembic Migration Best Practices

## Common Issues and Solutions

### Issue: "table _alembic_tmp_* already exists" Error

**Problem:**
When running migrations in SQLite, Alembic uses batch operations that create temporary tables (prefixed with `_alembic_tmp_`). If a migration fails partway through, these temporary tables can be left behind in the database, causing subsequent migration attempts to fail with:

```
sqlite3.OperationalError: table _alembic_tmp_soulspot_artists already exists
```

**Root Cause:**
SQLite doesn't support many DDL operations directly (like ALTER COLUMN for renaming), so Alembic's batch operations:
1. Create a temporary table with the new schema
2. Copy data from the original table
3. Drop the original table
4. Rename the temporary table

If step 3 or 4 fails, the temporary table remains in the database.

**Solution:**
Make migrations idempotent and resilient by:

1. **Cleanup orphaned tables** before attempting operations
2. **Check column existence** before renaming
3. **Use explicit error handling** with helpful messages

**Example Implementation:**

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

def _cleanup_orphaned_tables(connection) -> None:
    """Clean up orphaned temporary tables from failed migrations."""
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    
    for table_name in tables:
        if table_name.startswith("_alembic_tmp_"):
            print(f"Cleaning up orphaned table: {table_name}")
            connection.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))
            connection.commit()

def _column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade() -> None:
    connection = op.get_bind()
    
    # Always cleanup first
    _cleanup_orphaned_tables(connection)
    
    # Check before renaming
    if _column_exists(connection, "my_table", "old_name"):
        with op.batch_alter_table("my_table") as batch_op:
            batch_op.alter_column(
                "old_name",
                new_column_name="new_name",
                existing_type=sa.String(255),
            )
    elif _column_exists(connection, "my_table", "new_name"):
        print("Column already renamed - skipping")
    else:
        print("WARNING: Neither old nor new column found")
```

## Best Practices

### 1. Always Make Migrations Idempotent

A migration should be safe to run multiple times. Check current state before applying changes.

### 2. Add Descriptive Comments

Use "Hey future me" style comments to explain:
- Why the migration is needed
- What edge cases it handles
- What the previous state was
- What the new state will be

### 3. Test Both Upgrade and Downgrade

Always test both directions:
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head  # Should work again
```

### 4. Clean Up Before Complex Operations

For batch operations that create temporary tables:
```python
def upgrade() -> None:
    connection = op.get_bind()
    _cleanup_orphaned_tables(connection)
    
    # Your migration logic here
    
    # Clean up again between multiple batch operations
    _cleanup_orphaned_tables(connection)
    
    # Next batch operation
```

### 5. Handle Missing Tables/Columns Gracefully

Don't assume the database is in the expected state:
```python
if _table_exists(connection, "my_table"):
    if _column_exists(connection, "my_table", "my_column"):
        # Safe to proceed
        ...
    else:
        print("Column doesn't exist - skipping")
else:
    print("Table doesn't exist - skipping")
```

### 6. Use Explicit Column Types

Always specify `existing_type` for column alterations:
```python
batch_op.alter_column(
    "old_name",
    new_column_name="new_name",
    existing_type=sa.String(255),  # Explicit!
    existing_nullable=True,
)
```

## Testing Migrations Locally

### Test Fresh Database
```bash
# Remove existing database
rm -f soulspot.db

# Run migrations
alembic upgrade head
```

### Test Failed Migration Recovery
```bash
# Manually create orphaned table to simulate failure
sqlite3 soulspot.db "CREATE TABLE _alembic_tmp_test (id INTEGER);"

# Migration should clean up and succeed
alembic upgrade head
```

### Test Idempotency
```bash
# Run migration
alembic upgrade head

# Manually mark as not applied
alembic downgrade -1

# Run again - should work without errors
alembic upgrade head
```

## Debugging Failed Migrations

### Check Current Version
```bash
alembic current
```

### Check Migration History
```bash
alembic history
```

### View SQL Without Executing
```bash
alembic upgrade head --sql
```

### Manual Database Inspection
```bash
sqlite3 soulspot.db

.tables  -- List all tables
.schema soulspot_artists  -- View table schema
SELECT * FROM alembic_version;  -- Current migration version
```

### Manual Cleanup
If migrations are stuck:
```bash
sqlite3 soulspot.db
> DROP TABLE IF EXISTS _alembic_tmp_soulspot_artists;
> DROP TABLE IF EXISTS _alembic_tmp_soulspot_playlists;
> .quit
```

Then retry the migration.

## Reference

- [Alembic Batch Operations](https://alembic.sqlalchemy.org/en/latest/batch.html)
- [SQLAlchemy Inspector](https://docs.sqlalchemy.org/en/latest/core/reflection.html)
- [Migration xx35020zzA68](../../alembic/versions/xx35020zzA68_rename_image_url_to_artwork_url.py) - Example of robust migration
