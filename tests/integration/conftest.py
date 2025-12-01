"""Integration test fixtures and configuration."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.config import Settings
from soulspot.infrastructure.persistence import Database


@pytest.fixture(scope="function")
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file for tests."""
    return tmp_path / "test.db"


@pytest.fixture
def test_settings(test_db_path: Path) -> Settings:
    """Create test settings with file-based database."""
    return Settings(
        app_env="development",
        debug=True,
        database={"url": f"sqlite+aiosqlite:///{test_db_path}"},
        observability={
            "enable_dependency_health_checks": False,
        },
    )


@pytest.fixture(scope="function")
async def db(
    test_settings: Settings, test_db_path: Path
) -> AsyncGenerator[Database, None]:
    """Create and initialize database with schema for tests."""
    # Ensure database file exists
    test_db_path.touch(exist_ok=True)

    # Create tables using SQLAlchemy models (sync)
    from soulspot.infrastructure.persistence.models import Base

    sync_url = f"sqlite:///{test_db_path}"
    sync_engine = create_engine(sync_url)

    # Create all tables
    Base.metadata.create_all(sync_engine)

    # Note: Widget system was removed in migration ee19001hhj49
    # No need to seed widget or page data anymore

    sync_engine.dispose()

    # Now create async database
    database = Database(test_settings)

    yield database

    # Cleanup - ensure all connections are closed
    await database.close()


@pytest.fixture(scope="function")
async def db_session(db: Database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests.

    Hey future me - we use session_scope context manager instead of get_session generator!
    The context manager properly handles connection cleanup. Do NOT call session.close()
    explicitly - the context manager's exit handler already does that, and calling it again
    causes IllegalStateChangeError ("Method 'close()' can't be called here").
    """
    async with db.session_scope() as session:
        yield session


@pytest.fixture(scope="function")
async def app_with_db(test_settings: Settings, db: Database):
    """Create FastAPI app with initialized database (no lifespan)."""
    # Create app without lifespan to avoid automatic initialization
    from typing import Any
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from soulspot.application.workers.job_queue import JobQueue
    from soulspot.infrastructure.observability.health import (
        HealthStatus,
        check_database_health,
    )

    app = FastAPI(
        title=test_settings.app_name,
        debug=test_settings.debug,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://localhost:8765"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Manually set db in app state for tests
    app.state.db = db

    # Initialize session store for auth endpoints
    # Hey future me - pass session_scope context manager factory, NOT the Database object!
    # The old code passed `db` directly which caused "GC cleaning up non-checked-in connection"
    # errors because DatabaseSessionStore needs a context manager factory to properly
    # manage connection lifecycle.
    from soulspot.application.services.session_store import DatabaseSessionStore

    session_store = DatabaseSessionStore(session_scope=db.session_scope)
    app.state.session_store = session_store

    # Add mock job queue to avoid 503 errors in download endpoint tests
    mock_job_queue = AsyncMock(spec=JobQueue)
    mock_job_queue.enqueue = AsyncMock(return_value=None)
    mock_job_queue.pause = AsyncMock(return_value=None)
    mock_job_queue.resume = AsyncMock(return_value=None)
    # Use MagicMock for synchronous methods
    mock_job_queue.is_paused = MagicMock(return_value=False)
    mock_job_queue.get_max_concurrent_jobs = MagicMock(return_value=3)
    mock_job_queue.get_stats = MagicMock(
        return_value={
            "running": 0,
            "pending": 0,
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
    )
    app.state.job_queue = mock_job_queue

    # Include routes from main app
    from fastapi.staticfiles import StaticFiles

    from soulspot.api.routers import api_router, ui

    # Mount static files if directory exists
    static_dir = Path(__file__).parent.parent.parent / "src" / "soulspot" / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include API routers
    app.include_router(api_router, prefix="/api")

    # Include UI router at root
    app.include_router(ui.router, tags=["UI"])

    # Register exception handlers for proper error handling in tests
    from soulspot.main import register_exception_handlers

    register_exception_handlers(app)

    # Add health endpoints matching main.py
    @app.get(
        "/health",
        tags=["Health"],
        summary="Basic health check",
    )
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app_name": test_settings.app_name,
            "profile": test_settings.profile.value,
        }

    @app.get(
        "/ready",
        tags=["Health"],
        summary="Readiness check with dependencies",
    )
    async def readiness_check() -> dict[str, Any]:
        """Readiness check endpoint with database connectivity check."""
        checks = {}
        overall_status = HealthStatus.HEALTHY

        # Database connectivity check
        if hasattr(app.state, "db"):
            db_check = await check_database_health(app.state.db)
            checks["database"] = {
                "status": db_check.status.value,
                "message": db_check.message,
            }
            if db_check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                db_check.status == HealthStatus.DEGRADED
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.DEGRADED
        else:
            checks["database"] = {
                "status": HealthStatus.UNHEALTHY.value,
                "message": "Database not initialized",
            }
            overall_status = HealthStatus.UNHEALTHY

        return {
            "status": overall_status.value,
            "checks": checks,
        }

    yield app


@pytest.fixture(scope="function")
def client(app_with_db) -> TestClient:
    """Create synchronous test client with initialized app."""
    with TestClient(app_with_db) as test_client:
        yield test_client


@pytest.fixture(scope="function")
async def async_client(app_with_db) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with initialized app."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
