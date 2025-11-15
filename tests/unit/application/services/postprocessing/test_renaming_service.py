"""Tests for file renaming service."""

from pathlib import Path

import pytest

from soulspot.application.services.postprocessing.renaming_service import (
    RenamingService,
)
from soulspot.config import Settings
from soulspot.config.settings import PostProcessingSettings, StorageSettings
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Create mock settings with temporary paths."""
    music_path = tmp_path / "music"
    music_path.mkdir(parents=True, exist_ok=True)

    settings = Settings()
    settings.storage = StorageSettings(
        download_path=tmp_path / "downloads",
        music_path=music_path,
        artwork_path=tmp_path / "artwork",
        temp_path=tmp_path / "tmp",
    )
    settings.postprocessing = PostProcessingSettings(
        file_naming_template="{artist}/{album}/{track_number:02d} - {title}",
    )
    return settings


@pytest.fixture
def renaming_service(mock_settings: Settings) -> RenamingService:
    """Create renaming service with mock settings."""
    return RenamingService(mock_settings)


@pytest.fixture
def sample_track() -> Track:
    """Create a sample track."""
    return Track(
        id=TrackId.generate(),
        title="Test Track",
        artist_id=ArtistId.generate(),
        track_number=5,
        disc_number=1,
        duration_ms=180000,
    )


@pytest.fixture
def sample_artist() -> Artist:
    """Create a sample artist."""
    return Artist(id=ArtistId.generate(), name="Test Artist")


@pytest.fixture
def sample_album() -> Album:
    """Create a sample album."""
    return Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=ArtistId.generate(),
        release_year=2024,
    )


def test_renaming_service_initialization(
    renaming_service: RenamingService, mock_settings: Settings
) -> None:
    """Test renaming service initializes correctly."""
    assert renaming_service._settings == mock_settings
    assert renaming_service._template == "{artist}/{album}/{track_number:02d} - {title}"


def test_generate_filename_basic(
    renaming_service: RenamingService,
    sample_track: Track,
    sample_artist: Artist,
    sample_album: Album,
) -> None:
    """Test basic filename generation."""
    filename = renaming_service.generate_filename(
        sample_track, sample_artist, sample_album, ".mp3"
    )

    assert filename == "Test Artist/Test Album/05 - Test Track.mp3"


def test_generate_filename_without_album(
    renaming_service: RenamingService,
    sample_track: Track,
    sample_artist: Artist,
) -> None:
    """Test filename generation without album."""
    filename = renaming_service.generate_filename(
        sample_track, sample_artist, None, ".flac"
    )

    assert "Test Artist" in filename
    assert "Test Track" in filename
    assert filename.endswith(".flac")


def test_sanitize_filename_illegal_chars(renaming_service: RenamingService) -> None:
    """Test filename sanitization removes illegal characters."""
    dirty_filename = 'Test<>:"/\\|?*Track.mp3'
    clean_filename = renaming_service._sanitize_filename(dirty_filename)

    # All illegal chars should be replaced with underscore
    assert "<" not in clean_filename
    assert ">" not in clean_filename
    assert '"' not in clean_filename


def test_sanitize_filename_path_components(renaming_service: RenamingService) -> None:
    """Test filename sanitization handles path components."""
    filename = "Artist Name/Album Name/Track Name.mp3"
    sanitized = renaming_service._sanitize_filename(filename)

    # Should preserve directory structure
    assert "/" in sanitized
    parts = sanitized.split("/")
    assert len(parts) == 3


@pytest.mark.asyncio
async def test_rename_file_success(
    renaming_service: RenamingService,
    sample_track: Track,
    sample_artist: Artist,
    sample_album: Album,
    tmp_path: Path,
) -> None:
    """Test successful file renaming."""
    # Create source file
    source_path = tmp_path / "downloads" / "temp_file.mp3"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("test content")

    # Rename file
    new_path = await renaming_service.rename_file(
        source_path, sample_track, sample_artist, sample_album
    )

    # Verify file was moved
    assert new_path.exists()
    assert "Test Artist" in str(new_path)
    assert "Test Album" in str(new_path)
    assert new_path.read_text() == "test content"
    assert not source_path.exists()


@pytest.mark.asyncio
async def test_rename_file_existing_destination(
    renaming_service: RenamingService,
    sample_track: Track,
    sample_artist: Artist,
    sample_album: Album,
    tmp_path: Path,
) -> None:
    """Test renaming when destination file already exists."""
    # Create source file
    source_path = tmp_path / "downloads" / "temp_file.mp3"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("new content")

    # Pre-create destination file
    dest_dir = tmp_path / "music" / "Test Artist" / "Test Album"
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing_file = dest_dir / "05 - Test Track.mp3"
    existing_file.write_text("existing content")

    # Rename file - should create a unique name
    new_path = await renaming_service.rename_file(
        source_path, sample_track, sample_artist, sample_album
    )

    # Verify both files exist
    assert new_path.exists()
    assert existing_file.exists()
    assert new_path != existing_file
    assert new_path.read_text() == "new content"
    assert existing_file.read_text() == "existing content"


def test_validate_template_valid(renaming_service: RenamingService) -> None:
    """Test template validation with valid template."""
    assert renaming_service.validate_template("{artist}/{title}")
    assert renaming_service.validate_template("{artist}/{album}/{track_number:02d}")
    # New template format
    assert renaming_service.validate_template(
        "{Artist CleanName} - {Album Type} - {Release Year} - {Album CleanTitle}/{medium:02d}{track:02d} - {Track CleanTitle}"
    )


def test_validate_template_invalid(renaming_service: RenamingService) -> None:
    """Test template validation with invalid variables."""
    assert not renaming_service.validate_template("{artist}/{invalid_field}")
    assert not renaming_service.validate_template("{unknown}/{title}")


def test_generate_filename_new_format(tmp_path: Path) -> None:
    """Test filename generation with new format."""
    settings = Settings()
    settings.storage = StorageSettings(
        download_path=tmp_path / "downloads",
        music_path=tmp_path / "music",
        artwork_path=tmp_path / "artwork",
        temp_path=tmp_path / "tmp",
    )
    settings.postprocessing = PostProcessingSettings(
        file_naming_template="{Artist CleanName} - {Album Type} - {Release Year} - {Album CleanTitle}/{medium:02d}{track:02d} - {Track CleanTitle}",
    )
    service = RenamingService(settings)

    track = Track(
        id=TrackId.generate(),
        title="Test Track",
        artist_id=ArtistId.generate(),
        track_number=5,
        disc_number=1,
        duration_ms=180000,
    )
    artist = Artist(id=ArtistId.generate(), name="Test Artist")
    album = Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=ArtistId.generate(),
        release_year=2024,
    )

    filename = service.generate_filename(track, artist, album, ".mp3")

    assert "Test Artist - Album - 2024 - Test Album" in filename
    assert "0105 - Test Track.mp3" in filename


def test_clean_name_method(tmp_path: Path) -> None:
    """Test the _clean_name method."""
    settings = Settings()
    settings.storage = StorageSettings(
        download_path=tmp_path / "downloads",
        music_path=tmp_path / "music",
        artwork_path=tmp_path / "artwork",
        temp_path=tmp_path / "tmp",
    )
    service = RenamingService(settings)

    # Test cleaning problematic characters
    assert service._clean_name("Test/Name") == "Test-Name"
    assert service._clean_name("Test:Name") == "Test -Name"
    assert service._clean_name("Test?Name") == "TestName"
    assert service._clean_name("Test*Name") == "TestName"
    assert service._clean_name('Test"Name') == "Test'Name"
    assert service._clean_name("Test<Name>") == "Test(Name)"
    assert service._clean_name("Test|Name") == "Test-Name"

    # Test whitespace handling
    assert service._clean_name("  Test  Name  ") == "Test Name"
    assert service._clean_name("Test   Name") == "Test Name"
