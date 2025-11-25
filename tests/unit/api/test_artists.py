"""Tests for artists API endpoints."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.routers.artists import (
    ArtistListResponse,
    ArtistResponse,
    SyncArtistsResponse,
    _artist_to_response,
)
from soulspot.domain.entities import Artist
from soulspot.domain.value_objects import ArtistId, SpotifyUri


class TestArtistToResponse:
    """Test the _artist_to_response helper function."""

    def test_convert_artist_with_all_fields(self) -> None:
        """Test converting artist with all fields populated."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:abc123"),
            musicbrainz_id="mb-123",
            image_url="https://example.com/image.jpg",
            genres=["rock", "alternative"],
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        result = _artist_to_response(artist)

        assert isinstance(result, ArtistResponse)
        assert result.name == "Test Artist"
        assert result.spotify_uri == "spotify:artist:abc123"
        assert result.musicbrainz_id == "mb-123"
        assert result.image_url == "https://example.com/image.jpg"
        assert result.genres == ["rock", "alternative"]
        assert "2024-01-01" in result.created_at
        assert "2024-01-02" in result.updated_at

    def test_convert_artist_with_minimal_fields(self) -> None:
        """Test converting artist with only required fields."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Minimal Artist",
        )

        result = _artist_to_response(artist)

        assert result.name == "Minimal Artist"
        assert result.spotify_uri is None
        assert result.musicbrainz_id is None
        assert result.image_url is None
        assert result.genres == []

    def test_convert_artist_with_empty_genres(self) -> None:
        """Test converting artist with None genres becomes empty list."""
        artist = Artist(
            id=ArtistId.generate(),
            name="No Genres Artist",
            genres=[],
        )

        result = _artist_to_response(artist)

        assert result.genres == []


class TestArtistResponseModels:
    """Test Pydantic response models."""

    def test_artist_response_model(self) -> None:
        """Test ArtistResponse model validation."""
        response = ArtistResponse(
            id="test-id",
            name="Test Artist",
            spotify_uri="spotify:artist:abc",
            musicbrainz_id=None,
            image_url=None,
            genres=["rock"],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )

        assert response.id == "test-id"
        assert response.name == "Test Artist"
        assert response.genres == ["rock"]

    def test_sync_artists_response_model(self) -> None:
        """Test SyncArtistsResponse model validation."""
        response = SyncArtistsResponse(
            artists=[
                ArtistResponse(
                    id="test-id",
                    name="Test Artist",
                    genres=[],
                    created_at="2024-01-01T00:00:00",
                    updated_at="2024-01-01T00:00:00",
                )
            ],
            stats={"total_fetched": 1, "created": 1, "updated": 0, "errors": 0},
            message="Success",
        )

        assert len(response.artists) == 1
        assert response.stats["created"] == 1

    def test_artist_list_response_model(self) -> None:
        """Test ArtistListResponse model validation."""
        response = ArtistListResponse(
            artists=[],
            total_count=0,
            limit=100,
            offset=0,
        )

        assert response.total_count == 0
        assert response.limit == 100


class TestArtistRepository:
    """Test ArtistRepository count_all method."""

    @pytest.mark.asyncio
    async def test_count_all_returns_count(self) -> None:
        """Test that count_all returns total count of artists."""
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        session = AsyncMock(spec=AsyncSession)
        repo = ArtistRepository(session)

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.count_all()

        assert result == 42
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_all_returns_zero_for_empty(self) -> None:
        """Test that count_all returns 0 when no artists exist."""
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        session = AsyncMock(spec=AsyncSession)
        repo = ArtistRepository(session)

        # Mock the execute result with None (empty result)
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.count_all()

        assert result == 0


class TestFollowedArtistsServiceIntegration:
    """Test FollowedArtistsService methods."""

    @pytest.mark.asyncio
    async def test_sync_followed_artists_creates_artists(self) -> None:
        """Test that sync creates new artists from Spotify data."""
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )

        session = AsyncMock(spec=AsyncSession)
        spotify_client = AsyncMock()

        # Mock Spotify API response (single page)
        spotify_client.get_followed_artists.return_value = {
            "artists": {
                "items": [
                    {
                        "id": "spotify123",
                        "name": "Test Artist",
                        "genres": ["rock"],
                        "images": [
                            {"url": "https://example.com/large.jpg"},
                            {"url": "https://example.com/medium.jpg"},
                        ],
                    }
                ],
                "cursors": {"after": None},  # No more pages
            }
        }

        service = FollowedArtistsService(session, spotify_client)

        # Mock the repository methods
        service.artist_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.artist_repo.add = AsyncMock()

        artists, stats = await service.sync_followed_artists("test_token")

        assert len(artists) == 1
        assert artists[0].name == "Test Artist"
        assert stats["total_fetched"] == 1
        assert stats["created"] == 1
        assert stats["updated"] == 0

    @pytest.mark.asyncio
    async def test_sync_followed_artists_updates_existing(self) -> None:
        """Test that sync updates existing artists."""
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )

        session = AsyncMock(spec=AsyncSession)
        spotify_client = AsyncMock()

        # Mock Spotify API response
        spotify_client.get_followed_artists.return_value = {
            "artists": {
                "items": [
                    {
                        "id": "spotify123",
                        "name": "Updated Artist Name",
                        "genres": ["rock", "metal"],
                        "images": [],
                    }
                ],
                "cursors": {"after": None},
            }
        }

        service = FollowedArtistsService(session, spotify_client)

        # Mock existing artist
        existing_artist = Artist(
            id=ArtistId.generate(),
            name="Old Artist Name",
            spotify_uri=SpotifyUri.from_string("spotify:artist:spotify123"),
            genres=["rock"],
        )
        service.artist_repo.get_by_spotify_uri = AsyncMock(return_value=existing_artist)
        service.artist_repo.update = AsyncMock()

        artists, stats = await service.sync_followed_artists("test_token")

        assert len(artists) == 1
        assert artists[0].name == "Updated Artist Name"
        assert stats["updated"] == 1
        assert stats["created"] == 0

    @pytest.mark.asyncio
    async def test_preview_followed_artists(self) -> None:
        """Test preview method returns raw Spotify data."""
        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )

        session = AsyncMock(spec=AsyncSession)
        spotify_client = AsyncMock()

        expected_data: dict[str, Any] = {
            "artists": {
                "items": [{"id": "123", "name": "Test"}],
                "total": 1,
            }
        }
        spotify_client.get_followed_artists.return_value = expected_data

        service = FollowedArtistsService(session, spotify_client)
        result = await service.preview_followed_artists("test_token", limit=10)

        assert result == expected_data
        spotify_client.get_followed_artists.assert_called_once_with(
            access_token="test_token",
            limit=10,
        )
