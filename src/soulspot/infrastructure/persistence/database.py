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
            finally:
                await session.close()

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
            finally:
                await session.close()

    async def close(self) -> None:
        """Close database connection."""
        await self._engine.dispose()

    async def create_tables(self) -> None:
        """Create all tables (for testing only)."""
        from soulspot.infrastructure.persistence.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all tables (for testing only)."""
        from soulspot.infrastructure.persistence.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

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
