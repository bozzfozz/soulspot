"""full database reset - truncate all tables

Revision ID: AA38023ccD71
Revises: zz37022bbC70
Create Date: 2025-12-18 14:00:00.000000

Hey future me - COMPLETE DATABASE RESET!

This migration DELETES ALL DATA from all tables.
The schema remains intact - only data is removed.

USE CASE:
After major schema changes or ImageService migration, start fresh.
All entities will be re-synced from providers (Spotify, Deezer, etc.)

⚠️ WARNING: This is DESTRUCTIVE - all data will be lost!

What gets truncated:
- ALL application tables (dynamically discovered)
- Excludes: alembic_version (migration tracking)

What is NOT affected:
- Schema (tables, columns, indexes remain)
- Alembic version tracking

To run this migration:
    alembic upgrade head

To SKIP this migration (already have data you want to keep):
    alembic stamp AA38023ccD71
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "AA38023ccD71"
down_revision = "zz37022bbC70"
branch_labels = None
depends_on = None


# Tables that should NEVER be truncated
PROTECTED_TABLES = {
    "alembic_version",  # Migration tracking
    # Add any other system tables here if needed
}


def upgrade() -> None:
    """Truncate ALL data tables - DESTRUCTIVE!
    
    Future me note:
    This dynamically finds ALL tables in the database and truncates them.
    This way we don't miss any tables that might have been added later.
    """
    
    # Get database connection
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Get all table names in the database
    all_tables = inspector.get_table_names()
    
    # Filter out protected tables
    tables_to_truncate = [t for t in all_tables if t not in PROTECTED_TABLES]
    
    print(f"Found {len(tables_to_truncate)} tables to truncate:")
    for table in tables_to_truncate:
        print(f"  - {table}")
    
    # PostgreSQL: Disable foreign key checks and truncate all at once
    # This is the most reliable way to handle cascading deletes
    try:
        # PostgreSQL approach: TRUNCATE multiple tables with CASCADE
        if tables_to_truncate:
            tables_str = ", ".join(tables_to_truncate)
            op.execute(sa.text(f"TRUNCATE TABLE {tables_str} CASCADE"))
            print(f"Successfully truncated all {len(tables_to_truncate)} tables")
    except Exception as pg_error:
        print(f"PostgreSQL TRUNCATE failed: {pg_error}")
        print("Falling back to individual DELETE statements...")
        
        # Fallback: SQLite or other DBs that don't support multi-table TRUNCATE
        # Disable foreign keys temporarily
        try:
            op.execute(sa.text("PRAGMA foreign_keys = OFF"))  # SQLite
        except Exception:
            pass  # Not SQLite
        
        # Delete from each table individually (reverse order for FKs)
        for table in reversed(tables_to_truncate):
            try:
                op.execute(sa.text(f"DELETE FROM {table}"))
                print(f"  Deleted from: {table}")
            except Exception as e:
                print(f"  Warning: Could not delete from {table}: {e}")
        
        # Re-enable foreign keys
        try:
            op.execute(sa.text("PRAGMA foreign_keys = ON"))  # SQLite
        except Exception:
            pass  # Not SQLite
    
    print("Database reset complete!")


def downgrade() -> None:
    """Cannot restore deleted data - no-op.
    
    Future me note:
    There's no way to "undo" a TRUNCATE. The data is gone.
    If you need to downgrade, you'll need to re-sync from providers.
    """
    pass  # No-op - data cannot be restored
