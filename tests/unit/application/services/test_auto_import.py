"""Tests for auto-import service."""

from pathlib import Path
from unittest.mock import patch

import pytest

from soulspot.application.services import AutoImportService
from soulspot.config import Settings
from soulspot.config.settings import StorageSettings


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Create mock settings with temporary paths."""
    # Use tmp_path for all storage locations
    download_path = tmp_path / "downloads"
    music_path = tmp_path / "music"
    artwork_path = tmp_path / "artwork"
    temp_path = tmp_path / "tmp"

    # Create the directories
    download_path.mkdir(parents=True, exist_ok=True)
    music_path.mkdir(parents=True, exist_ok=True)
    artwork_path.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir(parents=True, exist_ok=True)

    # Create a Settings object with the temporary storage
    settings = Settings()
    settings.storage = StorageSettings(
        download_path=download_path,
        music_path=music_path,
        artwork_path=artwork_path,
        temp_path=temp_path,
    )
    return settings


@pytest.fixture
def auto_import_service(mock_settings: Settings) -> AutoImportService:
    """Create auto-import service with mock settings."""
    return AutoImportService(mock_settings, poll_interval=1)


def test_auto_import_service_initialization(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test auto-import service initializes correctly."""
    assert auto_import_service._download_path == mock_settings.storage.download_path
    assert auto_import_service._music_path == mock_settings.storage.music_path
    assert auto_import_service._poll_interval == 1
    assert not auto_import_service._running


def test_get_audio_files_empty_directory(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test getting audio files from empty directory."""
    files = auto_import_service._get_audio_files(mock_settings.storage.download_path)
    assert files == []


def test_get_audio_files_with_mp3(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test getting audio files with MP3 file."""
    # Create a test MP3 file
    test_file = mock_settings.storage.download_path / "test.mp3"
    test_file.write_text("test mp3 content")

    # Wait a bit to ensure file is "complete" (modified > 5 seconds ago is checked)
    # We need to mock the file completion check for this test
    with patch.object(auto_import_service, "_is_file_complete", return_value=True):
        files = auto_import_service._get_audio_files(
            mock_settings.storage.download_path
        )

    assert len(files) == 1
    assert files[0] == test_file


def test_get_audio_files_ignores_non_audio(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test that non-audio files are ignored."""
    # Create test files
    (mock_settings.storage.download_path / "test.txt").write_text("text file")
    (mock_settings.storage.download_path / "test.mp3").write_text("mp3 file")

    with patch.object(auto_import_service, "_is_file_complete", return_value=True):
        files = auto_import_service._get_audio_files(
            mock_settings.storage.download_path
        )

    assert len(files) == 1
    assert files[0].suffix == ".mp3"


def test_is_file_complete_empty_file(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test that empty files are not considered complete."""
    test_file = mock_settings.storage.download_path / "empty.mp3"
    test_file.write_text("")

    assert not auto_import_service._is_file_complete(test_file)


def test_is_file_complete_nonexistent_file(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test that nonexistent files are not considered complete."""
    test_file = mock_settings.storage.download_path / "nonexistent.mp3"

    assert not auto_import_service._is_file_complete(test_file)


def test_is_file_complete_valid_file(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test that valid files are considered complete."""
    test_file = mock_settings.storage.download_path / "test.mp3"
    test_file.write_text("test content")

    # Mock time to simulate file being old enough
    with patch("time.time", return_value=test_file.stat().st_mtime + 10):
        assert auto_import_service._is_file_complete(test_file)


@pytest.mark.asyncio
async def test_import_file_success(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test successful file import."""
    # Create source file
    source_file = mock_settings.storage.download_path / "artist" / "album" / "track.mp3"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("test mp3 content")

    # Import file
    await auto_import_service._import_file(source_file)

    # Verify file was moved
    dest_file = mock_settings.storage.music_path / "artist" / "album" / "track.mp3"
    assert dest_file.exists()
    assert dest_file.read_text() == "test mp3 content"
    assert not source_file.exists()


@pytest.mark.asyncio
async def test_import_file_existing_destination(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test import when destination file already exists."""
    # Create source file
    source_file = mock_settings.storage.download_path / "track.mp3"
    source_file.write_text("new content")

    # Create existing destination file
    dest_file = mock_settings.storage.music_path / "track.mp3"
    dest_file.write_text("existing content")

    # Import file
    await auto_import_service._import_file(source_file)

    # Verify source was removed but destination unchanged
    assert not source_file.exists()
    assert dest_file.exists()
    assert dest_file.read_text() == "existing content"


def test_cleanup_empty_dirs(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test cleanup of empty directories."""
    # Create nested empty directories
    empty_dir = mock_settings.storage.download_path / "artist" / "album"
    empty_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup
    auto_import_service._cleanup_empty_dirs(empty_dir)

    # Verify directories were removed but download root remains
    assert not empty_dir.exists()
    assert not (mock_settings.storage.download_path / "artist").exists()
    assert mock_settings.storage.download_path.exists()


def test_cleanup_empty_dirs_with_files(
    auto_import_service: AutoImportService, mock_settings: Settings
) -> None:
    """Test cleanup doesn't remove directories with files."""
    # Create directory with file
    test_dir = mock_settings.storage.download_path / "artist"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "file.txt").write_text("content")

    # Cleanup should not remove directory
    auto_import_service._cleanup_empty_dirs(test_dir)

    assert test_dir.exists()
