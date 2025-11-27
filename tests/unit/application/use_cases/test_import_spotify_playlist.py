"""Tests for Import Spotify Playlist use case."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistRequest,
    ImportSpotifyPlaylistResponse,
    ImportSpotifyPlaylistUseCase,
)
from soulspot.domain.entities import Playlist, PlaylistSource, Track
from soulspot.domain.value_objects import ArtistId, PlaylistId, SpotifyUri, TrackId


@pytest.fixture
def spotify_client_mock() -> AsyncMock:
    """Create mock Spotify client."""
    return AsyncMock()


@pytest.fixture
def playlist_repository_mock() -> AsyncMock:
    """Create mock playlist repository."""
    return AsyncMock()


@pytest.fixture
def track_repository_mock() -> AsyncMock:
    """Create mock track repository."""
    return AsyncMock()


@pytest.fixture
def artist_repository_mock() -> AsyncMock:
    """Create mock artist repository."""
    return AsyncMock()


@pytest.fixture
def album_repository_mock() -> AsyncMock:
    """Create mock album repository."""
    return AsyncMock()


@pytest.fixture
def use_case(
    spotify_client_mock: AsyncMock,
    playlist_repository_mock: AsyncMock,
    track_repository_mock: AsyncMock,
    artist_repository_mock: AsyncMock,
    album_repository_mock: AsyncMock,
) -> ImportSpotifyPlaylistUseCase:
    """Create use case with mocked dependencies."""
    return ImportSpotifyPlaylistUseCase(
        spotify_client=spotify_client_mock,
        playlist_repository=playlist_repository_mock,
        track_repository=track_repository_mock,
        artist_repository=artist_repository_mock,
        album_repository=album_repository_mock,
    )


class TestImportSpotifyPlaylistUseCase:
    """Test Import Spotify Playlist use case."""

    async def test_execute_success_with_new_playlist(
        self,
        use_case: ImportSpotifyPlaylistUseCase,
        spotify_client_mock: AsyncMock,
        playlist_repository_mock: AsyncMock,
        track_repository_mock: AsyncMock,
        artist_repository_mock: AsyncMock,
        album_repository_mock: AsyncMock,
    ) -> None:
        """Test successful playlist import with new playlist."""
        # Arrange
        request = ImportSpotifyPlaylistRequest(
            playlist_id="test-playlist-id",
            access_token="test-token",
            fetch_all_tracks=True,
        )

        # Mock Spotify API responses
        spotify_client_mock.get_playlist.return_value = {
            "id": "test-playlist-id",
            "name": "Test Playlist",
            "description": "A test playlist",
            "tracks": {
                "items": [
                    {
                        "track": {
                            "id": "track-1",
                            "name": "Test Track 1",
                            "duration_ms": 180000,
                            "uri": "spotify:track:track-1",
                            "artists": [
                                {
                                    "id": "artist-1",
                                    "name": "Test Artist 1",
                                    "uri": "spotify:artist:artist-1",
                                }
                            ],
                        }
                    },
                    {
                        "track": {
                            "id": "track-2",
                            "name": "Test Track 2",
                            "duration_ms": 200000,
                            "uri": "spotify:track:track-2",
                            "artists": [
                                {
                                    "id": "artist-2",
                                    "name": "Test Artist 2",
                                    "uri": "spotify:artist:artist-2",
                                }
                            ],
                        }
                    },
                ],
                "next": None,
            },
        }

        # Mock get_several_artists for batch artist fetching
        spotify_client_mock.get_several_artists.return_value = [
            {
                "id": "artist-1",
                "name": "Test Artist 1",
                "images": [],
                "genres": [],
            },
            {
                "id": "artist-2",
                "name": "Test Artist 2",
                "images": [],
                "genres": [],
            },
        ]

        # Mock repository responses - no existing playlist, tracks, or artists
        playlist_repository_mock.get_by_spotify_uri.return_value = None
        track_repository_mock.get_by_spotify_uri.return_value = None
        artist_repository_mock.get_by_spotify_uri.return_value = None
        artist_repository_mock.get_by_name.return_value = None
        album_repository_mock.get_by_spotify_uri.return_value = None
        artist_repository_mock.add.side_effect = lambda x: x
        track_repository_mock.add.side_effect = lambda x: x
        playlist_repository_mock.add.side_effect = lambda x: x
        playlist_repository_mock.add_track.return_value = None

        # Act
        response = await use_case.execute(request)

        # Assert
        assert isinstance(response, ImportSpotifyPlaylistResponse)
        assert response.playlist.name == "Test Playlist"
        assert response.playlist.description == "A test playlist"
        assert response.playlist.source == PlaylistSource.SPOTIFY
        assert response.tracks_imported == 2
        assert response.tracks_failed == 0
        assert len(response.errors) == 0

        # Verify API calls
        spotify_client_mock.get_playlist.assert_called_once_with(
            "test-playlist-id", "test-token"
        )
        # Artists are fetched via get_several_artists batch call
        spotify_client_mock.get_several_artists.assert_called_once()
        assert playlist_repository_mock.add.call_count == 1
        assert track_repository_mock.add.call_count == 2
        assert artist_repository_mock.add.call_count == 2
        assert playlist_repository_mock.add_track.call_count == 2

    async def test_execute_success_with_existing_playlist(
        self,
        use_case: ImportSpotifyPlaylistUseCase,
        spotify_client_mock: AsyncMock,
        playlist_repository_mock: AsyncMock,
        track_repository_mock: AsyncMock,
        artist_repository_mock: AsyncMock,
    ) -> None:
        """Test successful playlist import with existing playlist."""
        # Arrange
        request = ImportSpotifyPlaylistRequest(
            playlist_id="existing-playlist-id",
            access_token="test-token",
            fetch_all_tracks=True,
        )

        existing_playlist_id = PlaylistId.generate()
        existing_playlist = Playlist(
            id=existing_playlist_id,
            name="Old Name",
            description="Old description",
            source=PlaylistSource.SPOTIFY,
            spotify_uri=SpotifyUri("spotify:playlist:existing-playlist-id"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock Spotify API responses
        spotify_client_mock.get_playlist.return_value = {
            "id": "existing-playlist-id",
            "name": "Updated Playlist Name",
            "description": "Updated description",
            "tracks": {"items": [], "next": None},
        }

        # Mock repository responses - existing playlist
        playlist_repository_mock.get_by_spotify_uri.return_value = existing_playlist
        playlist_repository_mock.update.side_effect = lambda x: x

        # Act
        response = await use_case.execute(request)

        # Assert
        assert isinstance(response, ImportSpotifyPlaylistResponse)
        assert response.playlist.id == existing_playlist_id
        assert response.playlist.name == "Updated Playlist Name"
        assert response.playlist.description == "Updated description"
        assert response.tracks_imported == 0
        assert response.tracks_failed == 0

    async def test_execute_failure_spotify_api_error(
        self,
        use_case: ImportSpotifyPlaylistUseCase,
        spotify_client_mock: AsyncMock,
    ) -> None:
        """Test failure when Spotify API returns error."""
        # Arrange
        request = ImportSpotifyPlaylistRequest(
            playlist_id="error-playlist-id",
            access_token="invalid-token",
        )

        spotify_client_mock.get_playlist.side_effect = Exception("Spotify API error")

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to fetch playlist from Spotify"):
            await use_case.execute(request)

    async def test_execute_with_partial_track_failures(
        self,
        use_case: ImportSpotifyPlaylistUseCase,
        spotify_client_mock: AsyncMock,
        playlist_repository_mock: AsyncMock,
        track_repository_mock: AsyncMock,
        artist_repository_mock: AsyncMock,
    ) -> None:
        """Test playlist import with some track failures."""
        # Arrange
        request = ImportSpotifyPlaylistRequest(
            playlist_id="test-playlist-id",
            access_token="test-token",
            fetch_all_tracks=True,
        )

        # Mock Spotify API with one valid and one invalid track
        spotify_client_mock.get_playlist.return_value = {
            "id": "test-playlist-id",
            "name": "Test Playlist",
            "description": None,
            "tracks": {
                "items": [
                    {
                        "track": {
                            "id": "track-1",
                            "name": "Valid Track",
                            "duration_ms": 180000,
                            "uri": "spotify:track:track-1",
                            "artists": [
                                {
                                    "id": "artist-1",
                                    "name": "Test Artist",
                                    "uri": "spotify:artist:artist-1",
                                }
                            ],
                        }
                    },
                    {
                        "track": None,  # Invalid track
                    },
                ],
                "next": None,
            },
        }

        # Mock repository responses
        playlist_repository_mock.get_by_spotify_uri.return_value = None
        track_repository_mock.get_by_spotify_uri.return_value = None
        artist_repository_mock.get_by_name.return_value = None
        artist_repository_mock.add.side_effect = lambda x: x
        track_repository_mock.add.side_effect = lambda x: x
        playlist_repository_mock.add.side_effect = lambda x: x
        playlist_repository_mock.add_track.return_value = None

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.tracks_imported == 1
        assert response.tracks_failed == 1
        assert len(response.errors) > 0

    async def test_execute_with_existing_tracks(
        self,
        use_case: ImportSpotifyPlaylistUseCase,
        spotify_client_mock: AsyncMock,
        playlist_repository_mock: AsyncMock,
        track_repository_mock: AsyncMock,
        artist_repository_mock: AsyncMock,
    ) -> None:
        """Test playlist import with existing tracks."""
        # Arrange
        request = ImportSpotifyPlaylistRequest(
            playlist_id="test-playlist-id",
            access_token="test-token",
            fetch_all_tracks=True,
        )

        existing_track_id = TrackId.generate()
        existing_track = Track(
            id=existing_track_id,
            title="Existing Track",
            artist_id=ArtistId.generate(),
            duration_ms=180000,
            spotify_uri=SpotifyUri("spotify:track:track-1"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock Spotify API responses
        spotify_client_mock.get_playlist.return_value = {
            "id": "test-playlist-id",
            "name": "Test Playlist",
            "description": None,
            "tracks": {
                "items": [
                    {
                        "track": {
                            "id": "track-1",
                            "name": "Existing Track",
                            "duration_ms": 180000,
                            "uri": "spotify:track:track-1",
                            "artists": [
                                {
                                    "id": "artist-1",
                                    "name": "Test Artist",
                                    "uri": "spotify:artist:artist-1",
                                }
                            ],
                        }
                    },
                ],
                "next": None,
            },
        }

        # Mock repository responses - existing track
        playlist_repository_mock.get_by_spotify_uri.return_value = None
        track_repository_mock.get_by_spotify_uri.return_value = existing_track
        playlist_repository_mock.add.side_effect = lambda x: x
        playlist_repository_mock.add_track.return_value = None
        track_repository_mock.update.side_effect = lambda x: x

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.tracks_imported == 1
        assert response.tracks_failed == 0
        # Should not create new track, just update existing one
        assert track_repository_mock.add.call_count == 0
        assert track_repository_mock.update.call_count == 1
        assert playlist_repository_mock.add_track.call_count == 1
