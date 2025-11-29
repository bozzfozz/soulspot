"""Database session management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from soulspot.config import Settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection and session manager."""

    # Hey future me, this init is WHERE THE MAGIC (and pain) HAPPENS. We support BOTH PostgreSQL
    # AND SQLite because dev/test uses SQLite, production uses Postgres. The pool settings ONLY
    # apply to Postgres - SQLite doesn't pool connections! If you try to set pool_size on SQLite,
    # it'll silently ignore it or blow up depending on the driver version. The "check_same_thread":
    # False is CRITICAL for SQLite + async - without it, you get cryptic "objects created in a
    # thread can only be used in that same thread" errors. The 30s timeout helps with "database
    # is locked" errors when multiple workers hit SQLite simultaneously. Don't reduce it!
    def __init__(self, settings: Settings) -> None:
        """Initialize database with settings."""
        self.settings = settings

        # Configure connection pool for PostgreSQL
        engine_kwargs: dict[str, Any] = {
            "echo": settings.database.echo,
            "pool_pre_ping": settings.database.pool_pre_ping,
        }

        # Only apply pool settings for PostgreSQL
        if "postgresql" in settings.database.url:
            engine_kwargs.update(
                {
                    "pool_size": settings.database.pool_size,
                    "max_overflow": settings.database.max_overflow,
                    "pool_timeout": settings.database.pool_timeout,
                    "pool_recycle": settings.database.pool_recycle,
                }
            )
        elif "sqlite" in settings.database.url:
            # SQLite-specific configuration
            engine_kwargs.update(
                {
                    "connect_args": {
                        "check_same_thread": False,
                        "timeout": 30,  # Wait up to 30s for lock
                    }
                }
            )

        self._engine = create_async_engine(
            settings.database.url,
            **engine_kwargs,
        )

        # Enable foreign keys for SQLite
        if "sqlite" in settings.database.url:
            self._enable_sqlite_foreign_keys()

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    # Yo future me, SQLite is EVIL - it has foreign keys DISABLED BY DEFAULT! This hook turns
    # them on for EVERY connection. Without this, you can delete a track that still has downloads
    # pointing to it, and the DB won't complain. Cascades won't work. Relationships break silently.
    # This was a nasty bug to track down - data inconsistencies everywhere until I added this.
    # The event listener runs on EVERY new connection from the pool, so don't do heavy work here!
    def _enable_sqlite_foreign_keys(self) -> None:
        """Enable foreign key constraints for SQLite.

        SQLite has foreign keys disabled by default. This method enables them
        for all connections.
        """

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
            """Set SQLite pragmas on connection."""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            logger.debug("Enabled foreign keys for SQLite connection")

    # Listen future me, this is a GENERATOR (note the yield!), not a regular async function.
    # Use it with "async for session in db.get_session():" - NOT "session = await db.get_session()".
    # I spent 2 hours debugging that once. The auto-commit happens ONLY if no exception occurs.
    # If anything goes wrong, we rollback and re-raise. The except block catches EVERYTHING
    # intentionally - we don't want partial transactions committed.
    #
    # IMPORTANT: The `async with self._session_factory() as session:` context manager handles
    # session cleanup automatically when exiting. Do NOT call session.close() explicitly HERE!
    # SQLAlchemy's async_sessionmaker's __aexit__ already closes the session. Calling close()
    # again causes IllegalStateChangeError because the session is already in a closing state.
    # This was a nasty bug - "Method 'close()' can't be called here; method '_connection_for_bind()'
    # is already in progress" - the fix is simply removing the redundant close() call.
    #
    # HOWEVER: If you use "async for session in db.get_session(): ... break" pattern (early exit),
    # you MUST call session.close() explicitly in the consumer code! The break exits the generator
    # before the context manager's __aexit__ runs. See session_store.py and token_manager.py.
    # Pattern comparison:
    #   - "async for ... (full iteration)" → auto-close ✓
    #   - "async for ... break" → manual close() required in consumer!
    #   - "async with db.session_scope()" → auto-close ✓ (preferred for single operations)
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                # Rollback on any exception - this is intentionally broad to ensure
                # transaction integrity. All exceptions are re-raised for proper handling.
                await session.rollback()
                raise

    # Hey, this is basically IDENTICAL to get_session() but it's a context manager instead of
    # a generator. Use it with "async with db.session_scope() as session:" - this is the PREFERRED
    # way! It's clearer and harder to mess up than get_session(). I should probably deprecate
    # get_session() but it's used in some old code. Same transaction semantics: commit on success,
    # rollback on exception.
    #
    # IMPORTANT: Same as get_session() - the async context manager handles cleanup automatically.
    # Do NOT call session.close() explicitly! See get_session() comment for why.
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional scope for database operations."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                # Rollback on any exception - this is intentionally broad to ensure
                # transaction integrity. All exceptions are re-raised for proper handling.
                await session.rollback()
                raise

    # Yo, dispose() closes ALL connections in the pool and shuts down the engine. CRITICAL on
    # shutdown or you'll leave dangling connections! Postgres might complain about "too many
    # connections" if you keep creating Database instances without closing them. Always call
    # this in shutdown hooks or finally blocks. For SQLite it's less critical but still good
    # practice to release the file lock.
    async def close(self) -> None:
        """Close database connection."""
        await self._engine.dispose()

    # Hey future me, this is ONLY for testing! Don't use in production - use Alembic migrations
    # instead. This creates tables synchronously using run_sync which blocks the async engine.
    # It's fine for test setup but defeats the purpose of async in real code. Also, this creates
    # tables based on current model definitions - if your DB is out of sync with models (e.g.,
    # you added a migration but didn't run it), this will create the NEW schema, not match
    # production. Good for pytest fixtures, bad for literally anything else!
    async def create_tables(self) -> None:
        """Create all tables (for testing only)."""
        from soulspot.infrastructure.persistence.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Listen up, drop_tables is DESTRUCTIVE! Testing only! I once accidentally ran this against
    # a dev database and lost a week of test data. Now I'm paranoid. This drops ALL tables defined
    # in Base.metadata - if you have tables created outside SQLAlchemy (manual SQL, legacy, etc.),
    # this won't touch them. Only use in test teardown!
    async def drop_tables(self) -> None:
        """Drop all tables (for testing only)."""
        from soulspot.infrastructure.persistence.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    # Yo future me, pool stats are GOLD for debugging connection leaks and performance issues.
    # If "checked_out" stays high, you're leaking sessions (forgot to close them). If "overflow"
    # is high, your pool_size is too small for your workload. SQLite returns a dummy response
    # because it doesn't pool - every connection is ad-hoc. The getattr() calls with lambda
    # defaults are defensive coding - different pool types (NullPool, StaticPool, QueuePool)
    # expose different stats. Without the defaults, this would crash on some pool types. Use
    # this in health checks or monitoring dashboards!
    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics for monitoring.

        Returns:
            Dictionary with pool statistics including size, checked out connections, etc.
            Returns empty dict for SQLite as it doesn't use connection pooling.
        """
        # Pool stats only available for databases that use connection pooling
        if "sqlite" in self.settings.database.url:
            return {
                "pool_type": "sqlite",
                "note": "SQLite does not use connection pooling",
            }

        pool = self._engine.pool
        # Note: Pool statistics methods may not be available on all pool types
        # Using getattr with defaults to handle this safely
        return {
            "pool_size": getattr(pool, "size", lambda: 0)(),
            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
            "overflow": getattr(pool, "overflow", lambda: 0)(),
            "checked_in": getattr(pool, "checkedin", lambda: 0)(),
            "pool_timeout": self.settings.database.pool_timeout,
            "pool_recycle": self.settings.database.pool_recycle,
            "max_overflow": self.settings.database.max_overflow,
        }
