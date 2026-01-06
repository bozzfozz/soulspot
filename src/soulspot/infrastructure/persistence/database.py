"""Database session management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from soulspot.config import Settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection and session manager."""

    # Hey future me, this init is WHERE THE MAGIC (and pain) HAPPENS. We support BOTH PostgreSQL
    # AND SQLite because dev/test uses SQLite, production uses Postgres. The pool settings ONLY
    # apply to Postgres - SQLite doesn't pool connections! If you try to set pool_size on SQLite,
    # it'll silently ignore it or blow up depending on the driver version. The "check_same_thread":
    # False is CRITICAL for SQLite + async - without it, you get cryptic "objects created in a
    # thread can only be used in that same thread" errors. The 60s timeout helps with "database
    # is locked" errors when multiple workers hit SQLite simultaneously. Don't reduce it!
    #
    # UPDATE (Dec 2025): SQLite now uses NullPool instead of QueuePool!
    # NullPool = no connection caching, each session gets its own connection that's closed immediately.
    # This eliminates connection sharing issues that cause "database is locked" errors.
    # QueuePool was reusing connections across sessions, which SQLite doesn't handle well with
    # multiple concurrent async operations.
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
            # Hey future me - NullPool is CRITICAL for SQLite + async (Dec 2025)!
            #
            # Problem: SQLite only allows ONE writer at a time. With QueuePool, multiple
            # sessions might share the same connection, causing "database is locked" errors
            # when one session tries to write while another is already writing.
            #
            # Solution: NullPool creates a fresh connection for each session and closes it
            # immediately after use. No connection sharing = no lock contention between sessions.
            # Each operation gets exclusive access to the database during its transaction.
            #
            # Trade-off: Slightly more overhead from opening/closing connections, but SQLite
            # opens are fast (~1ms) and the reliability gain is worth it.
            #
            # UPDATE (Jan 2026): PHASED STARTUP FIX - Increased timeout to 30s!
            # Old: 500ms timeout = fail fast, but causes "database is locked" during
            #      concurrent writes in UnifiedLibraryManager (Artist Sync + Album Sync)
            # New: 30s timeout = allows writers to queue up and wait for lock release
            #
            # This combined with PHASED STARTUP (exclude LIBRARY_SCAN from recovery)
            # eliminates most "database is locked" errors. The 30s is a MAX timeout -
            # operations complete as soon as lock is released (usually <1s).
            engine_kwargs.update(
                {
                    "poolclass": NullPool,  # No connection caching - each session gets fresh connection
                    "connect_args": {
                        "check_same_thread": False,
                        "timeout": 30,  # 30s - allow writers to queue (PHASED STARTUP FIX Jan 2026)
                    },
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
    #
    # UPDATE (Dec 2025): Also enabling WAL mode now! WAL (Write-Ahead Logging) is CRUCIAL for
    # concurrent access - it allows readers and writers to work simultaneously without blocking.
    # Without WAL, you get "database is locked" errors when scanning the library (writes) while
    # the UI is loading data (reads). WAL creates -wal and -shm files next to the .db file.
    # IMPORTANT: WAL mode persists in the database file, so this only needs to run once per DB
    # but running it every connection is safe (just a no-op if already set).
    #
    # UPDATE (Dec 2025 v2): Added MORE optimizations for lock reduction!
    # - synchronous=NORMAL: Safe enough for most use cases, faster than FULL
    # - cache_size=-64000: 64MB cache reduces disk I/O significantly
    # - temp_store=MEMORY: Temp tables in RAM instead of disk
    # - mmap_size=268435456: 256MB memory-mapped I/O for faster reads
    # These combined with WAL mode should eliminate most "database is locked" errors.
    def _enable_sqlite_foreign_keys(self) -> None:
        """Enable foreign key constraints, WAL mode, and performance optimizations for SQLite.

        SQLite has foreign keys disabled by default. This method enables them
        for all connections. Also enables WAL mode and performance optimizations
        for better concurrency and reduced lock contention.
        """

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
            """Set SQLite pragmas on connection."""
            cursor = dbapi_conn.cursor()

            # === REQUIRED FOR DATA INTEGRITY ===
            # Enable foreign keys (required for cascade deletes to work)
            cursor.execute("PRAGMA foreign_keys=ON")

            # === CONCURRENCY OPTIMIZATIONS ===
            # Enable WAL mode for better concurrency (readers don't block writers)
            # This prevents "database is locked" errors during library scans
            cursor.execute("PRAGMA journal_mode=WAL")

            # Set busy timeout to 30000ms (30 seconds)
            # PHASED STARTUP FIX (Jan 2026): Increased from 500ms to 30s!
            # 
            # Problem: 500ms was too aggressive for our phased startup:
            # - UnifiedLibraryManager.initial_sync runs ~10s
            # - DeezerSyncService writes Albums per Artist (many small transactions)
            # - 500ms timeout caused "database is locked" during overlapping writes
            #
            # Solution: 30s timeout gives enough buffer for long transactions to complete.
            # The phased startup (exclude LIBRARY_SCAN from recovery) prevents most
            # concurrent writes, but DeezerSync within UnifiedLibraryManager can still
            # have overlapping transactions during album sync.
            #
            # Note: This is NOT a performance hit because:
            # - WAL mode allows concurrent reads (UI stays responsive)
            # - Writers queue up instead of failing immediately
            # - 30s is a MAX timeout, not a delay - if lock is released in 100ms, we continue
            cursor.execute("PRAGMA busy_timeout=30000")

            # === PERFORMANCE OPTIMIZATIONS (Dec 2025 v2) ===
            # synchronous=NORMAL: Faster than FULL, safe with WAL mode
            # FULL syncs on every transaction - overkill for most use cases
            # NORMAL syncs on checkpoint only - good balance of safety/speed
            cursor.execute("PRAGMA synchronous=NORMAL")

            # cache_size=-64000: 64MB cache (negative = KB, positive = pages)
            # More cache = less disk I/O = faster operations = shorter lock time
            cursor.execute("PRAGMA cache_size=-64000")

            # temp_store=MEMORY: Temp tables/indexes in RAM instead of disk
            # Faster for sorting, grouping, and complex queries
            cursor.execute("PRAGMA temp_store=MEMORY")

            # mmap_size: Memory-mapped I/O for faster reads
            # 256MB = 268435456 bytes - good for databases up to 1GB
            # Reads bypass the page cache and go directly to mapped memory
            cursor.execute("PRAGMA mmap_size=268435456")

            cursor.close()
            logger.debug(
                "SQLite optimizations enabled: foreign_keys, WAL, "
                "busy_timeout=30s, cache=64MB, mmap=256MB (PHASED STARTUP FIX Jan 2026)"
            )

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
    # UPDATE (Nov 2025): The "async for ... break" pattern causes race conditions!
    # When consumer uses "break", Python sends GeneratorExit to the generator.
    # If this happens DURING a SQLAlchemy operation (e.g., _connection_for_bind()),
    # the context manager's __aexit__ tries to close() while operation is in progress
    # → IllegalStateChangeError!
    #
    # FIX: Wrap the context manager in try/except to catch IllegalStateChangeError
    # during cleanup. This is safe - it means the session was already being closed
    # by another path and we can ignore the duplicate close attempt.
    #
    # Pattern comparison:
    #   - "async for ... (full iteration)" → auto-close ✓
    #   - "async for ... break" → auto-close ✓ (DON'T call session.close() in consumer!)
    #   - "async with db.session_scope()" → auto-close ✓ (preferred for single operations)
    #
    # Updated session_store.py and token_manager.py to remove redundant close() calls.
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        from sqlalchemy.exc import IllegalStateChangeError

        try:
            async with self._session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except GeneratorExit:
                    # Consumer broke out with 'break' - don't commit, just cleanup
                    raise
                except Exception:
                    # Rollback on any exception - this is intentionally broad to ensure
                    # transaction integrity. All exceptions are re-raised for proper handling.
                    await session.rollback()
                    raise
        except IllegalStateChangeError:
            # Context manager tried to close() while operation was in progress.
            # This happens with async for...break pattern. Safe to ignore - the
            # session will be cleaned up by GC eventually.
            pass
        except GeneratorExit:
            # Consumer broke out - suppress to avoid "coroutine ignored GeneratorExit"
            pass

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

    # Hey future me - this is THE FIX for "database is locked" errors!
    # Same as session_scope() but with AUTOMATIC RETRY on SQLite lock errors.
    # Use this for operations that might conflict with concurrent writers.
    # The retry logic uses exponential backoff: 0.5s → 1s → 2s (capped at 5s).
    #
    # When to use:
    # - Background workers doing bulk writes
    # - Library scanner operations
    # - Any operation that might run during heavy DB activity
    #
    # When NOT to use:
    # - Interactive UI requests (use regular session_scope, user shouldn't wait 5s)
    # - Read-only operations (they don't lock in WAL mode)
    @asynccontextmanager
    async def session_scope_with_retry(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.5,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional scope with automatic retry on lock errors.

        This is like session_scope() but automatically retries on "database is locked"
        errors. Perfect for background workers and bulk operations that might conflict
        with concurrent writers.

        Args:
            max_attempts: Maximum retry attempts (default: 3)
            initial_delay: Initial delay between retries in seconds (default: 0.5)

        Yields:
            Database session with auto-commit on success

        Example:
            async with db.session_scope_with_retry() as session:
                repo = TrackRepository(session)
                await repo.add(track)
                # If "database is locked", automatically retries up to 3 times
        """
        import asyncio
        import time

        from sqlalchemy.exc import OperationalError

        from soulspot.infrastructure.persistence.retry import DatabaseLockMetrics

        metrics = DatabaseLockMetrics.get_instance()
        last_exception: Exception | None = None
        delay = initial_delay
        start_time = time.monotonic()

        metrics.record_attempt()

        for attempt in range(max_attempts):
            try:
                async with self._session_factory() as session:
                    try:
                        yield session
                        await session.commit()
                        # Success!
                        wait_time_ms = (time.monotonic() - start_time) * 1000
                        if attempt > 0:
                            metrics.record_success(wait_time_ms)
                        else:
                            metrics.record_success(0)
                        return
                    except OperationalError as e:
                        error_msg = str(e).lower()
                        if "locked" not in error_msg and "busy" not in error_msg:
                            metrics.record_failure()
                            raise
                        last_exception = e
                        await session.rollback()
                    except Exception:
                        await session.rollback()
                        raise

                # Retry logic for lock errors
                if attempt < max_attempts - 1:
                    metrics.record_retry()
                    logger.warning(
                        "Database locked (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 5.0)
                else:
                    metrics.record_failure()
                    logger.error(
                        "Database locked after %d attempts, giving up",
                        max_attempts,
                    )

            except OperationalError as e:
                error_msg = str(e).lower()
                if "locked" not in error_msg and "busy" not in error_msg:
                    metrics.record_failure()
                    raise

                last_exception = e

                if attempt < max_attempts - 1:
                    metrics.record_retry()
                    logger.warning(
                        "Database locked on commit (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 5.0)
                else:
                    metrics.record_failure()
                    logger.error(
                        "Database locked after %d attempts, giving up",
                        max_attempts,
                    )

        if last_exception:
            raise last_exception

    # Yo future me, dispose() closes ALL connections in the pool and shuts down the engine. CRITICAL on
    # shutdown or you'll leave dangling connections! Postgres might complain about "too many
    # connections" if you keep creating Database instances without closing them. Always call
    # this in shutdown hooks or finally blocks. For SQLite it's less critical but still good
    # practice to release the file lock.
    async def close(self) -> None:
        """Close database connection."""
        await self._engine.dispose()

    # Hey future me - this exposes the session factory for workers that need their own sessions!
    # Use this when you need to create sessions in a loop (like QueueDispatcherWorker) where
    # each iteration should have its own short-lived session. DON'T use this for request-scoped
    # sessions in FastAPI routes - use get_session() or session_scope() instead.
    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory for creating independent sessions.

        Returns:
            The async sessionmaker instance for creating new sessions.

        Use this for background workers that need to manage their own session lifecycle.
        For request-scoped sessions, use session_scope() or get_session() instead.
        """
        return self._session_factory

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
