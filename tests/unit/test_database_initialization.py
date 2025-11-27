# AI-Model: Claude 3.5 Sonnet (anthropic)
"""Unit tests for database initialization and SQLite path validation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSQLitePathValidation:
    """Tests for SQLite database path validation logic."""

    def test_validate_directory_creation(self, tmp_path: Path) -> None:
        """Test that parent directories are created for SQLite databases."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        # Create a settings object with a database in a subdirectory
        db_path = tmp_path / "data" / "test.db"

        # Mock settings
        with patch.object(Settings, "_get_sqlite_db_path", return_value=db_path):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = db_path

            # Validate path
            _validate_sqlite_path(settings)

            # Verify directory was created
            assert db_path.parent.exists()
            assert db_path.parent.is_dir()

    def test_validate_directory_permissions(self, tmp_path: Path) -> None:
        """Test that directory write permissions are validated."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        db_path = tmp_path / "writable" / "test.db"
        db_path.parent.mkdir(parents=True)

        # Mock settings
        with patch.object(Settings, "_get_sqlite_db_path", return_value=db_path):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = db_path

            # Should not raise an exception
            _validate_sqlite_path(settings)

    def test_validate_current_directory(self) -> None:
        """Test that current directory validation works without mkdir."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        db_path = Path("test.db")

        # Mock settings
        with patch.object(Settings, "_get_sqlite_db_path", return_value=db_path):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = db_path

            # Should not raise an exception for current directory
            _validate_sqlite_path(settings)

    def test_validate_non_sqlite_database(self) -> None:
        """Test that validation is skipped for non-SQLite databases."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        # Mock settings with PostgreSQL URL
        with patch.object(Settings, "_get_sqlite_db_path", return_value=None):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = None

            # Should return early without doing anything
            _validate_sqlite_path(settings)

    def test_validate_permission_error(self, tmp_path: Path) -> None:
        """Test that permission errors are caught and reported clearly."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        # Create a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        db_path = readonly_dir / "test.db"

        # Mock settings
        with patch.object(Settings, "_get_sqlite_db_path", return_value=db_path):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = db_path

            # Should raise RuntimeError with clear message
            with pytest.raises(RuntimeError, match="Unable to write files"):
                _validate_sqlite_path(settings)

        # Cleanup: restore permissions so pytest can clean up tmp_path
        readonly_dir.chmod(0o755)

    def test_validate_nested_directory_creation(self, tmp_path: Path) -> None:
        """Test that deeply nested directories are created correctly."""
        from soulspot.config import Settings
        from soulspot.main import _validate_sqlite_path

        # Create a deeply nested path
        db_path = tmp_path / "a" / "b" / "c" / "d" / "test.db"

        # Mock settings
        with patch.object(Settings, "_get_sqlite_db_path", return_value=db_path):
            settings = MagicMock(spec=Settings)
            settings._get_sqlite_db_path.return_value = db_path

            # Validate path
            _validate_sqlite_path(settings)

            # Verify all nested directories were created
            assert db_path.parent.exists()
            assert db_path.parent.is_dir()
            # Verify we can write to the directory
            test_file = db_path.parent / "test_write"
            test_file.write_text("test")
            assert test_file.exists()
