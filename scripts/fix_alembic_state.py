#!/usr/bin/env python3
"""Fix corrupted alembic_version state.

Hey future me - this script fixes a specific issue where the alembic_version table
contains multiple revisions that have an ancestor-descendant relationship.

The Problem:
When alembic_version contains BOTH 'ddd38026ggH74' AND 'BBB38024eeE72',
alembic fails with:
    "Requested revision ddd38026ggH74 overlaps with other requested revisions BBB38024eeE72"

This happens because BBB38024eeE72 is an ANCESTOR of ddd38026ggH74.
Having both means the database is in an invalid state - if you're at the descendant,
you've already passed through the ancestor.

The Fix:
Remove ancestor revisions from alembic_version, keeping only the most recent head(s).
This allows alembic upgrade head to continue correctly.

Usage:
    python scripts/fix_alembic_state.py

    # Or with custom database URL:
    DATABASE_URL=sqlite+aiosqlite:///./my.db python scripts/fix_alembic_state.py
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def fix_alembic_state() -> bool:
    """Fix corrupted alembic_version state.

    Returns:
        True if fix was applied, False if no fix was needed.
    """
    try:
        import sqlalchemy as sa
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError:
        print("ERROR: Required packages not installed (sqlalchemy, alembic)")
        return False

    # Get database URL from environment or settings
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        try:
            from soulspot.config import get_settings
            settings = get_settings()
            db_url = settings.database.url
        except ImportError:
            db_url = "sqlite+aiosqlite:////config/soulspot.db"

    # Convert async URL to sync for direct SQLAlchemy access
    sync_url = db_url.replace("+aiosqlite", "").replace("sqlite+", "sqlite:///")
    if sync_url.startswith("sqlite://////"):
        sync_url = sync_url.replace("sqlite://////", "sqlite:////")

    print(f"Checking database: {sync_url}")

    # Check if database file exists
    if sync_url.startswith("sqlite:///"):
        db_path = sync_url.replace("sqlite:///", "")
        if not Path(db_path).exists():
            print("  Database file does not exist yet - nothing to fix")
            return False

    try:
        engine = sa.create_engine(sync_url)
        inspector = sa.inspect(engine)

        # Check if alembic_version table exists
        if "alembic_version" not in inspector.get_table_names():
            print("  alembic_version table does not exist - nothing to fix")
            return False

        # Get current versions in alembic_version
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT version_num FROM alembic_version"))
            current_versions = [row[0] for row in result.fetchall()]

        print(f"  Current versions: {current_versions}")

        if len(current_versions) <= 1:
            print("  Only one version found - no overlap possible")
            return False

        # Load alembic script to check ancestry
        # Find alembic.ini
        alembic_ini = Path(__file__).parent.parent / "alembic.ini"
        if not alembic_ini.exists():
            alembic_ini = Path("/app/alembic.ini")

        if not alembic_ini.exists():
            print(f"  WARNING: alembic.ini not found at {alembic_ini}")
            return False

        config = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(config)

        # Get ancestors for each version
        def get_ancestors(rev_id: str) -> set:
            """Get all ancestor revision IDs."""
            ancestors = set()
            try:
                rev = script.get_revision(rev_id)
                if not rev:
                    return ancestors

                def collect(r, visited):
                    if r.revision in visited:
                        return
                    visited.add(r.revision)
                    if r.down_revision:
                        downs = r.down_revision if isinstance(r.down_revision, tuple) else [r.down_revision]
                        for d in downs:
                            dr = script.get_revision(d)
                            if dr:
                                collect(dr, visited)

                collect(rev, ancestors)
                ancestors.discard(rev_id)  # Don't include self
            except Exception as e:
                print(f"  Warning: Could not get ancestors for {rev_id}: {e}")
            return ancestors

        # Find versions that are ancestors of other versions
        versions_to_remove = set()
        for v1 in current_versions:
            ancestors = get_ancestors(v1)
            for v2 in current_versions:
                if v1 != v2 and v2 in ancestors:
                    # v2 is an ancestor of v1, so v2 should be removed
                    versions_to_remove.add(v2)
                    print(f"  Found overlap: {v2} is ancestor of {v1}")

        if not versions_to_remove:
            print("  No overlapping versions found")
            return False

        # Remove ancestor versions
        print(f"  Removing overlapping versions: {versions_to_remove}")
        with engine.connect() as conn:
            for v in versions_to_remove:
                conn.execute(
                    sa.text("DELETE FROM alembic_version WHERE version_num = :v"),
                    {"v": v}
                )
            conn.commit()

        # Verify the fix
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT version_num FROM alembic_version"))
            final_versions = [row[0] for row in result.fetchall()]

        print(f"  Fixed! Remaining versions: {final_versions}")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  Alembic State Fixer")
    print("=" * 60)
    print()

    fixed = fix_alembic_state()

    print()
    if fixed:
        print("Fix applied successfully!")
        print("You can now run: alembic upgrade head")
    else:
        print("No fix was needed.")

    sys.exit(0)
