"""Tests for unified search API endpoints.

Hey future me - diese Tests prüfen die neuen Spotify + Soulseek Search endpoints.
Die Search-Router verwendet den shared Token (single-user architecture) um
Spotify-Suchen ohne per-browser Sessions zu ermöglichen.

Tests fokussieren sich auf:
1. Spotify artist/album/track search endpoint responses
2. Soulseek file search endpoint responses
3. Error handling bei fehlenden Tokens oder API-Fehlern
4. Response model validation
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from soulspot.api.routers.search import (
    SoulseekFileResult,
    SoulseekSearchResponse,
    SpotifyAlbumResult,
    SpotifyArtistResult,
    SpotifySearchResponse,
    SpotifyTrackResult,
    router,
    search_spotify_artists,
    search_spotify_tracks,
    search_soulseek,
)


class TestSpotifySearchResponseModels:
    """Test Pydantic response models for Spotify search."""

    def test_spotify_artist_result_model(self) -> None:
        """Test SpotifyArtistResult model with all fields."""
        result = SpotifyArtistResult(
            id="artist123",
            name="Test Artist",
            popularity=85,
            followers=1234567,
            genres=["rock", "indie"],
            image_url="https://example.com/artist.jpg",
            spotify_url="https://open.spotify.com/artist/artist123",
        )

        assert result.id == "artist123"
        assert result.name == "Test Artist"
        assert result.popularity == 85
        assert result.followers == 1234567
        assert result.genres == ["rock", "indie"]
        assert result.image_url == "https://example.com/artist.jpg"

    def test_spotify_artist_result_minimal(self) -> None:
        """Test SpotifyArtistResult with only required fields."""
        result = SpotifyArtistResult(
            id="artist123",
            name="Minimal Artist",
        )

        assert result.id == "artist123"
        assert result.name == "Minimal Artist"
        assert result.popularity == 0
        assert result.followers == 0
        assert result.genres == []
        assert result.image_url is None

    def test_spotify_album_result_model(self) -> None:
        """Test SpotifyAlbumResult model validation."""
        result = SpotifyAlbumResult(
            id="album123",
            name="Test Album",
            artist_name="Test Artist",
            artist_id="artist123",
            release_date="2024-01-01",
            album_type="album",
            total_tracks=12,
            image_url="https://example.com/album.jpg",
            spotify_url="https://open.spotify.com/album/album123",
        )

        assert result.id == "album123"
        assert result.name == "Test Album"
        assert result.artist_name == "Test Artist"
        assert result.album_type == "album"
        assert result.total_tracks == 12

    def test_spotify_track_result_model(self) -> None:
        """Test SpotifyTrackResult model validation."""
        result = SpotifyTrackResult(
            id="track123",
            name="Test Track",
            artist_name="Test Artist",
            artist_id="artist123",
            album_name="Test Album",
            album_id="album123",
            duration_ms=180000,
            popularity=75,
            preview_url="https://example.com/preview.mp3",
            spotify_url="https://open.spotify.com/track/track123",
            isrc="USRC12345678",
        )

        assert result.id == "track123"
        assert result.name == "Test Track"
        assert result.duration_ms == 180000
        assert result.isrc == "USRC12345678"

    def test_spotify_search_response_model(self) -> None:
        """Test SpotifySearchResponse combining all result types."""
        response = SpotifySearchResponse(
            artists=[
                SpotifyArtistResult(id="a1", name="Artist 1"),
            ],
            albums=[
                SpotifyAlbumResult(id="al1", name="Album 1", artist_name="Artist 1"),
            ],
            tracks=[
                SpotifyTrackResult(id="t1", name="Track 1", artist_name="Artist 1"),
            ],
            query="test query",
        )

        assert len(response.artists) == 1
        assert len(response.albums) == 1
        assert len(response.tracks) == 1
        assert response.query == "test query"


class TestSoulseekSearchResponseModels:
    """Test Pydantic response models for Soulseek search."""

    def test_soulseek_file_result_model(self) -> None:
        """Test SoulseekFileResult model with all fields."""
        result = SoulseekFileResult(
            username="uploader123",
            filename="/Music/Artist/Album/01-Track.flac",
            size=45678901,
            bitrate=320,
            length=180,
            quality=85,
        )

        assert result.username == "uploader123"
        assert result.filename == "/Music/Artist/Album/01-Track.flac"
        assert result.size == 45678901
        assert result.bitrate == 320
        assert result.length == 180

    def test_soulseek_search_response_model(self) -> None:
        """Test SoulseekSearchResponse model validation."""
        response = SoulseekSearchResponse(
            files=[
                SoulseekFileResult(
                    username="user1",
                    filename="/music/track.mp3",
                    size=5000000,
                    bitrate=320,
                    length=200,
                    quality=90,
                ),
            ],
            query="test query",
            total=1,
        )

        assert len(response.files) == 1
        assert response.query == "test query"
        assert response.total == 1


class TestSearchSpotifyArtistsEndpoint:
    """Test Spotify artist search endpoint."""

    @pytest.mark.asyncio
    async def test_search_artists_success(self) -> None:
        """Test successful artist search returns formatted results."""
        # Arrange: Mock Spotify client response
        mock_client = AsyncMock()
        mock_client.search_artist = AsyncMock(
            return_value={
                "artists": {
                    "items": [
                        {
                            "id": "artist123",
                            "name": "Test Artist",
                            "popularity": 85,
                            "followers": {"total": 1234567},
                            "genres": ["rock", "indie"],
                            "images": [{"url": "https://example.com/image.jpg"}],
                            "external_urls": {
                                "spotify": "https://open.spotify.com/artist/artist123"
                            },
                        }
                    ]
                }
            }
        )

        # Act
        result = await search_spotify_artists(
            query="Test Artist",
            limit=20,
            spotify_client=mock_client,
            access_token="test_token",
        )

        # Assert
        assert len(result.artists) == 1
        assert result.artists[0].id == "artist123"
        assert result.artists[0].name == "Test Artist"
        assert result.artists[0].popularity == 85
        assert result.artists[0].followers == 1234567
        assert result.artists[0].genres == ["rock", "indie"]
        assert result.artists[0].image_url == "https://example.com/image.jpg"
        assert result.query == "Test Artist"

        # Verify client was called correctly
        mock_client.search_artist.assert_called_once_with(
            "Test Artist", "test_token", limit=20
        )

    @pytest.mark.asyncio
    async def test_search_artists_no_images(self) -> None:
        """Test artist search handles artists without images."""
        mock_client = AsyncMock()
        mock_client.search_artist = AsyncMock(
            return_value={
                "artists": {
                    "items": [
                        {
                            "id": "artist456",
                            "name": "No Image Artist",
                            "popularity": 50,
                            "followers": {"total": 100},
                            "genres": [],
                            "images": [],
                            "external_urls": {},
                        }
                    ]
                }
            }
        )

        result = await search_spotify_artists(
            query="No Image",
            limit=10,
            spotify_client=mock_client,
            access_token="test_token",
        )

        assert len(result.artists) == 1
        assert result.artists[0].image_url is None
        assert result.artists[0].spotify_url is None

    @pytest.mark.asyncio
    async def test_search_artists_empty_results(self) -> None:
        """Test artist search with no results returns empty list."""
        mock_client = AsyncMock()
        mock_client.search_artist = AsyncMock(return_value={"artists": {"items": []}})

        result = await search_spotify_artists(
            query="Nonexistent Artist",
            limit=20,
            spotify_client=mock_client,
            access_token="test_token",
        )

        assert len(result.artists) == 0
        assert result.query == "Nonexistent Artist"

    @pytest.mark.asyncio
    async def test_search_artists_api_error(self) -> None:
        """Test artist search handles Spotify API errors gracefully."""
        mock_client = AsyncMock()
        mock_client.search_artist = AsyncMock(
            side_effect=Exception("Spotify API error")
        )

        with pytest.raises(HTTPException) as exc_info:
            await search_spotify_artists(
                query="Test",
                limit=20,
                spotify_client=mock_client,
                access_token="test_token",
            )

        assert exc_info.value.status_code == 500
        assert "Spotify search failed" in exc_info.value.detail


class TestSearchSpotifyTracksEndpoint:
    """Test Spotify track search endpoint."""

    @pytest.mark.asyncio
    async def test_search_tracks_success(self) -> None:
        """Test successful track search returns formatted results."""
        mock_client = AsyncMock()
        mock_client.search_track = AsyncMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "id": "track123",
                            "name": "Test Track",
                            "artists": [{"id": "artist123", "name": "Test Artist"}],
                            "album": {"id": "album123", "name": "Test Album"},
                            "duration_ms": 180000,
                            "popularity": 75,
                            "preview_url": "https://example.com/preview.mp3",
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/track123"
                            },
                            "external_ids": {"isrc": "USRC12345678"},
                        }
                    ]
                }
            }
        )

        result = await search_spotify_tracks(
            query="Test Track",
            limit=20,
            spotify_client=mock_client,
            access_token="test_token",
        )

        assert len(result.tracks) == 1
        assert result.tracks[0].id == "track123"
        assert result.tracks[0].name == "Test Track"
        assert result.tracks[0].artist_name == "Test Artist"
        assert result.tracks[0].duration_ms == 180000
        assert result.query == "Test Track"


class TestSearchSoulseekEndpoint:
    """Test Soulseek search endpoint."""

    @pytest.mark.asyncio
    async def test_search_soulseek_success(self) -> None:
        """Test successful Soulseek search returns formatted results."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value=[
                {
                    "username": "uploader1",
                    "filename": "/Music/Artist/Track.flac",
                    "size": 45678901,
                    "bitrate": 1411,
                    "length": 180,
                    "quality": 95,
                },
                {
                    "username": "uploader2",
                    "filename": "/Music/Artist/Track.mp3",
                    "size": 8000000,
                    "bitrate": 320,
                    "length": 180,
                    "quality": 85,
                },
            ]
        )

        result = await search_soulseek(
            query="Artist Track",
            timeout=30,
            slskd_client=mock_client,
        )

        assert len(result.files) == 2
        assert result.files[0].username == "uploader1"
        assert result.files[0].bitrate == 1411
        assert result.files[1].bitrate == 320
        assert result.query == "Artist Track"
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_search_soulseek_empty_results(self) -> None:
        """Test Soulseek search with no results."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])

        result = await search_soulseek(
            query="Very Obscure Track",
            timeout=30,
            slskd_client=mock_client,
        )

        assert len(result.files) == 0
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_search_soulseek_api_error(self) -> None:
        """Test Soulseek search handles slskd errors gracefully."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("slskd connection failed"))

        with pytest.raises(HTTPException) as exc_info:
            await search_soulseek(
                query="Test",
                timeout=30,
                slskd_client=mock_client,
            )

        assert exc_info.value.status_code == 500
        assert "Soulseek search failed" in exc_info.value.detail
