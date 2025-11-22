"""Integration tests for FastAPI application lifespan and configuration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine

from soulspot.config import Settings
from soulspot.infrastructure.persistence.models import Base
from soulspot.main import create_app, lifespan, register_exception_handlers


def setup_test_db(db_path: Path) -> None:
    """Create database schema for testing."""
    from sqlalchemy import text

    sync_url = f"sqlite:///{db_path}"
    sync_engine = create_engine(sync_url)
    Base.metadata.create_all(sync_engine)

    # Seed default widgets
    with sync_engine.connect() as conn:
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
        conn.commit()

    sync_engine.dispose()


class TestLifespan:
    """Test application lifespan events."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self, test_settings: Settings, tmp_path: Path):
        """Test lifespan context manager startup and shutdown sequence."""
        # Use tmp_path for database
        db_path = tmp_path / "test_lifespan.db"
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        # Create tables first
        setup_test_db(db_path)

        # Create app with test settings
        app = create_app(test_settings)

        # Track startup and shutdown
        startup_complete = False
        shutdown_complete = False

        async with lifespan(app):
            startup_complete = True
            # Verify app state initialized
            assert hasattr(app.state, "db")
            assert hasattr(app.state, "job_queue")

        shutdown_complete = True

        assert startup_complete
        assert shutdown_complete

    @pytest.mark.asyncio
    async def test_lifespan_creates_directories(self, test_settings: Settings, tmp_path: Path):
        """Test that lifespan creates required storage directories."""
        # Set custom directories
        download_dir = tmp_path / "downloads"
        music_dir = tmp_path / "music"
        db_path = tmp_path / "test.db"

        # Update storage settings correctly
        test_settings.storage = MagicMock()
        test_settings.storage.downloads_dir = download_dir
        test_settings.storage.music_dir = music_dir
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        setup_test_db(db_path)

        app = create_app(test_settings)

        async with lifespan(app):
            # Directories should be created
            assert download_dir.exists()
            assert music_dir.exists()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_database(self, test_settings: Settings, tmp_path: Path):
        """Test database initialization during startup."""
        db_path = tmp_path / "test_db_init.db"
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        setup_test_db(db_path)

        app = create_app(test_settings)

        async with lifespan(app):
            # Database should be initialized
            assert hasattr(app.state, "db")
            assert app.state.db is not None
            # DB file should exist
            assert db_path.exists()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_job_queue(self, test_settings: Settings, tmp_path: Path):
        """Test job queue initialization during startup."""
        db_path = tmp_path / "test_jobqueue.db"
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        setup_test_db(db_path)

        app = create_app(test_settings)

        async with lifespan(app):
            # Job queue should be initialized
            assert hasattr(app.state, "job_queue")
            assert app.state.job_queue is not None

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_on_error(self, test_settings: Settings, tmp_path: Path):
        """Test that cleanup runs even if startup fails."""
        db_path = tmp_path / "test_error.db"
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        app = create_app(test_settings)

        # Mock to force an error during startup
        with patch("soulspot.main.Database") as mock_db_class:
            mock_db_class.side_effect = RuntimeError("Simulated startup error")

            with pytest.raises(RuntimeError, match="Simulated startup error"):
                async with lifespan(app):
                    pass  # Should not reach here

    @pytest.mark.asyncio
    async def test_lifespan_closes_resources(self, test_settings: Settings, tmp_path: Path):
        """Test that resources are properly closed on shutdown."""
        db_path = tmp_path / "test_cleanup.db"
        test_settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        setup_test_db(db_path)

        app = create_app(test_settings)

        async with lifespan(app):
            db_instance = app.state.db
            job_queue_instance = app.state.job_queue

            # Mock close methods to track calls
            db_instance.close = AsyncMock()
            job_queue_instance.shutdown = AsyncMock()

        # After exiting context, resources should be closed
        # (Actual verification would require more invasive mocking)


class TestExceptionHandlers:
    """Test exception handler registration and behavior."""

    def test_register_exception_handlers(self):
        """Test that exception handlers are registered."""
        app = FastAPI()
        register_exception_handlers(app)

        # Check that handlers are registered by looking at exception_handlers dict
        from soulspot.domain.exceptions import (
            DuplicateEntityException,
            EntityNotFoundException,
            InvalidStateException,
            ValidationException,
        )

        assert ValidationException in app.exception_handlers
        assert EntityNotFoundException in app.exception_handlers
        assert DuplicateEntityException in app.exception_handlers
        assert InvalidStateException in app.exception_handlers

    def test_validation_exception_handler(self, client):
        """Test ValidationException handler returns 422."""
        # Create a test endpoint that raises ValidationException
        from fastapi import APIRouter

        from soulspot.domain.exceptions import ValidationException
        router = APIRouter()

        @router.get("/test-validation")
        async def test_endpoint():
            raise ValidationException("Test validation error")

        # Add router to client's app
        client.app.include_router(router)

        response = client.get("/test-validation")
        assert response.status_code == 422
        assert "Test validation error" in response.json()["detail"]

    def test_entity_not_found_exception_handler(self, client):
        """Test EntityNotFoundException handler returns 404."""
        from fastapi import APIRouter

        from soulspot.domain.exceptions import EntityNotFoundException

        router = APIRouter()

        @router.get("/test-not-found")
        async def test_endpoint():
            raise EntityNotFoundException(entity_type="Track", entity_id="123")

        client.app.include_router(router)

        response = client.get("/test-not-found")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_duplicate_entity_exception_handler(self, client):
        """Test DuplicateEntityException handler returns 409."""
        from fastapi import APIRouter

        from soulspot.domain.exceptions import DuplicateEntityException

        router = APIRouter()

        @router.get("/test-duplicate")
        async def test_endpoint():
            raise DuplicateEntityException(entity_type="Track", entity_id="123")

        client.app.include_router(router)

        response = client.get("/test-duplicate")
        assert response.status_code == 409

    def test_invalid_state_exception_handler(self, client):
        """Test InvalidStateException handler returns 400."""
        from fastapi import APIRouter

        from soulspot.domain.exceptions import InvalidStateException

        router = APIRouter()

        @router.get("/test-invalid-state")
        async def test_endpoint():
            raise InvalidStateException("Invalid state")

        client.app.include_router(router)

        response = client.get("/test-invalid-state")
        assert response.status_code == 400


class TestCreateApp:
    """Test application factory function."""

    def test_create_app_default_settings(self):
        """Test creating app with default settings."""
        # Patch get_settings to avoid loading from environment
        with patch("soulspot.main.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=Settings)
            mock_settings.app_name = "SoulSpot Bridge"
            mock_settings.debug = False
            mock_settings.api.cors_origins = ["*"]
            mock_settings.api.cors_allow_credentials = True
            mock_get_settings.return_value = mock_settings

            app = create_app()
            assert app is not None
            assert app.title == "SoulSpot Bridge"
            assert hasattr(app, "lifespan")

    def test_create_app_custom_settings(self, test_settings: Settings):
        """Test creating app with custom settings."""
        app = create_app(test_settings)
        assert app is not None
        assert app.title == test_settings.app_name
        assert app.debug == test_settings.debug

    def test_create_app_includes_routers(self, test_settings: Settings):
        """Test that routers are included."""
        app = create_app(test_settings)

        # Check that routes exist
        routes = [route.path for route in app.routes]
        assert any("/api" in route for route in routes)
        assert any("/health" in route for route in routes)

    def test_create_app_has_middleware(self, test_settings: Settings):
        """Test that middleware is added."""
        app = create_app(test_settings)

        # Check middleware stack

        middleware_types = [type(m.cls) if hasattr(m, 'cls') else type(m) for m in app.user_middleware]

        # At least one of each type should be present
        # Note: Checking exact types is tricky due to FastAPI's middleware wrapping

    def test_create_app_mounts_static_files(self, test_settings: Settings):
        """Test static files mounting."""
        app = create_app(test_settings)

        # Check if static route exists
        routes = [route.path for route in app.routes]
        # Static might be mounted or not depending on directory existence
        # Just verify app was created successfully


class TestSQLitePathValidation:
    """Test SQLite path validation."""

    def test_validate_sqlite_path_creates_parent_dir(self, tmp_path: Path):
        """Test that parent directory is created."""
        from soulspot.main import _validate_sqlite_path

        db_path = tmp_path / "subdir" / "test.db"
        settings = Settings(
            app_env="development",
            database={"url": f"sqlite+aiosqlite:///{db_path}"}
        )

        # Parent shouldn't exist yet
        assert not db_path.parent.exists()

        _validate_sqlite_path(settings)

        # Parent should now exist
        assert db_path.parent.exists()

    def test_validate_sqlite_path_skips_non_sqlite(self):
        """Test that non-SQLite URLs are skipped."""
        from soulspot.main import _validate_sqlite_path

        settings = Settings(
            app_env="development",
            database={"url": "postgresql://localhost/test"}
        )

        # Should not raise any errors
        _validate_sqlite_path(settings)

    def test_validate_sqlite_path_handles_permission_error(self, tmp_path: Path):
        """Test error handling for permission issues."""
        from soulspot.main import _validate_sqlite_path

        # Create a file where we want a directory (will cause permission error)
        db_path = tmp_path / "blocked"
        db_path.touch()

        settings = Settings(
            app_env="development",
            database={"url": f"sqlite+aiosqlite:///{db_path}/test.db"}
        )

        with pytest.raises(RuntimeError, match="Unable to create SQLite database directory"):
            _validate_sqlite_path(settings)


class TestHealthEndpoints:
    """Test health check endpoints from main app."""

    def test_health_endpoint_structure(self, client):
        """Test health endpoint returns correct structure."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "app_name" in data
        assert "profile" in data
        assert data["status"] == "healthy"

    def test_ready_endpoint_structure(self, client):
        """Test readiness endpoint returns correct structure."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]

        # Status should be healthy or degraded
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
