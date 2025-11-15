"""Tests for artwork service."""

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from PIL import Image as PILImage

from soulspot.application.services.postprocessing.artwork_service import ArtworkService
from soulspot.config import Settings
from soulspot.config.settings import PostProcessingSettings, StorageSettings
from soulspot.domain.entities import Album, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Create mock settings with temporary paths."""
    artwork_path = tmp_path / "artwork"
    artwork_path.mkdir(parents=True, exist_ok=True)

    settings = Settings()
    settings.storage = StorageSettings(
        download_path=tmp_path / "downloads",
        music_path=tmp_path / "music",
        artwork_path=artwork_path,
        temp_path=tmp_path / "tmp",
    )
    settings.postprocessing = PostProcessingSettings(
        artwork_max_size=800,
        artwork_quality=90,
    )
    return settings


@pytest.fixture
def artwork_service(mock_settings: Settings) -> ArtworkService:
    """Create artwork service with mock settings."""
    return ArtworkService(mock_settings)


@pytest.fixture
def sample_track() -> Track:
    """Create a sample track."""
    return Track(
        id=TrackId.generate(),
        title="Test Track",
        artist_id=ArtistId.generate(),
        duration_ms=180000,
    )


@pytest.fixture
def sample_album() -> Album:
    """Create a sample album with MusicBrainz ID."""
    return Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=ArtistId.generate(),
        musicbrainz_id="test-mb-id-12345",
    )


def test_artwork_service_initialization(
    artwork_service: ArtworkService, mock_settings: Settings
) -> None:
    """Test artwork service initializes correctly."""
    assert artwork_service._artwork_path == mock_settings.storage.artwork_path
    assert artwork_service._max_size == 800
    assert artwork_service._quality == 90


@pytest.mark.asyncio
async def test_download_from_coverart_success(
    artwork_service: ArtworkService, sample_album: Album
) -> None:
    """Test successful artwork download from CoverArtArchive."""
    # Create a simple test image
    img = PILImage.new("RGB", (100, 100), color="red")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_data = img_bytes.getvalue()

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.content = img_data
        mock_response.raise_for_status = Mock()

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await artwork_service._download_from_coverart(
            sample_album.musicbrainz_id or ""
        )

        assert result is not None
        assert len(result) > 0


@pytest.mark.asyncio
async def test_download_from_coverart_not_found(
    artwork_service: ArtworkService,
) -> None:
    """Test artwork download when not found on CoverArtArchive."""
    with patch("httpx.AsyncClient") as mock_client:
        from httpx import HTTPStatusError, Response

        mock_response = Response(404)
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=HTTPStatusError(
                "Not found", request=Mock(), response=mock_response
            )
        )

        result = await artwork_service._download_from_coverart("invalid-id")

        assert result is None


def test_process_image_resize(artwork_service: ArtworkService) -> None:
    """Test image resizing when larger than max size."""
    # Create a large test image
    large_img = PILImage.new("RGB", (2000, 2000), color="blue")
    img_bytes = BytesIO()
    large_img.save(img_bytes, format="JPEG")
    img_data = img_bytes.getvalue()

    # Process image
    processed_data = artwork_service._process_image_sync(img_data)

    # Verify it was resized
    processed_img = PILImage.open(BytesIO(processed_data))
    assert max(processed_img.size) <= 800


def test_process_image_no_resize_small(artwork_service: ArtworkService) -> None:
    """Test that small images are not resized."""
    # Create a small test image
    small_img = PILImage.new("RGB", (400, 400), color="green")
    img_bytes = BytesIO()
    small_img.save(img_bytes, format="JPEG", quality=100)

    # Process image
    img_bytes.seek(0)
    processed_data = artwork_service._process_image_sync(img_bytes.getvalue())

    # Size should be similar (may differ due to optimization)
    # But dimensions should be the same
    processed_img = PILImage.open(BytesIO(processed_data))
    assert processed_img.size == (400, 400)


@pytest.mark.asyncio
async def test_save_artwork(
    artwork_service: ArtworkService, sample_album: Album
) -> None:
    """Test saving artwork to disk."""
    # Create test image data
    img = PILImage.new("RGB", (100, 100), color="yellow")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_data = img_bytes.getvalue()

    # Save artwork
    saved_path = await artwork_service.save_artwork(img_data, sample_album)

    # Verify file was created
    assert saved_path.exists()
    assert saved_path.suffix == ".jpg"
    assert saved_path.parent == artwork_service._artwork_path

    # Verify content
    saved_data = saved_path.read_bytes()
    assert len(saved_data) > 0
