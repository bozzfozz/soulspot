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


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary database file for tests."""
    return tmp_path_factory.mktemp("data") / "test.db"


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


@pytest.fixture
async def db(
    test_settings: Settings, test_db_path: Path
) -> AsyncGenerator[Database, None]:
    """Create and initialize database with schema for tests."""
    # Ensure database file exists
    test_db_path.touch(exist_ok=True)

    # Create tables using SQLAlchemy models (sync)
    from sqlalchemy import text

    from soulspot.infrastructure.persistence.models import Base

    sync_url = f"sqlite:///{test_db_path}"
    sync_engine = create_engine(sync_url)

    # Create all tables
    Base.metadata.create_all(sync_engine)

    # Seed widget registry and default page (from migration)
    with sync_engine.connect() as conn:
        # Insert default widgets (use INSERT OR IGNORE for test reruns)
        conn.execute(
            text("""
                INSERT OR IGNORE INTO widgets (type, name, template_path, default_config) VALUES
                ('active_jobs', 'Active Jobs', 'partials/widgets/active_jobs.html', '{"refresh_interval": 5}'),
                ('spotify_search', 'Spotify Search', 'partials/widgets/spotify_search.html', '{"max_results": 10}'),
                ('missing_tracks', 'Missing Tracks', 'partials/widgets/missing_tracks.html', '{"show_all": false}'),
                ('quick_actions', 'Quick Actions', 'partials/widgets/quick_actions.html', '{"actions": ["scan", "import", "fix"]}'),
                ('metadata_manager', 'Metadata Manager', 'partials/widgets/metadata_manager.html', '{"filter": "all"}')
            """)
        )

        # Insert default page (use INSERT OR IGNORE for test reruns)
        conn.execute(
            text("""
                INSERT OR IGNORE INTO pages (name, slug, is_default, created_at, updated_at) VALUES
                ('My Dashboard', 'default', 1, datetime('now'), datetime('now'))
            """)
        )

        conn.commit()

    sync_engine.dispose()

    # Now create async database
    database = Database(test_settings)

    yield database

    # Cleanup
    await database.close()


@pytest.fixture
async def db_session(db: Database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    async for session in db.get_session():
        yield session


@pytest.fixture
async def app_with_db(test_settings: Settings, db: Database):
    """Create FastAPI app with initialized database (no lifespan)."""
    # Create app without lifespan to avoid automatic initialization
    from unittest.mock import AsyncMock

    from fastapi import FastAPI

    app = FastAPI(
        title=test_settings.app_name,
        debug=test_settings.debug,
    )

    # Manually set db in app state for tests
    app.state.db = db

    # Add mock job queue to avoid 503 errors in download endpoint tests
    from unittest.mock import MagicMock

    from soulspot.application.workers.job_queue import JobQueue

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

    # Add basic health endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    yield app


@pytest.fixture
def client(app_with_db) -> TestClient:
    """Create synchronous test client with initialized app."""
    with TestClient(app_with_db) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app_with_db) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with initialized app."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
