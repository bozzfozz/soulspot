"""Unit tests for album sync service."""

from unittest.mock import AsyncMock

import pytest

from soulspot.application.services.album_sync_service import AlbumSyncService
from soulspot.domain.entities import Album, Artist
from soulspot.domain.value_objects import AlbumId, ArtistId, SpotifyUri


class TestAlbumSyncService:
    """Test album sync service functionality."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_spotify_client(self) -> AsyncMock:
        """Create mock Spotify client."""
        client = AsyncMock()
        client.get_artist_albums = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def service(
        self, mock_session: AsyncMock, mock_spotify_client: AsyncMock
    ) -> AlbumSyncService:
        """Create album sync service with mocked dependencies."""
        return AlbumSyncService(
            session=mock_session,
            spotify_client=mock_spotify_client,
        )

    @pytest.mark.asyncio
    async def test_sync_albums_no_artists(
        self, service: AlbumSyncService, mock_session: AsyncMock
    ) -> None:
        """Test syncing albums when no artists exist."""
        # Mock empty artist list
        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[])

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert albums == []
        assert stats["total_artists"] == 0
        assert stats["artists_processed"] == 0
        assert stats["albums_created"] == 0

    @pytest.mark.asyncio
    async def test_sync_albums_artist_without_spotify_uri(
        self, service: AlbumSyncService, mock_session: AsyncMock
    ) -> None:
        """Test that artists without Spotify URI are skipped."""
        # Create artist without Spotify URI
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=None,
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert albums == []
        assert stats["total_artists"] == 1
        assert stats["artists_processed"] == 0  # Artist skipped

    @pytest.mark.asyncio
    async def test_sync_albums_creates_new_albums(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test that new albums are created."""
        # Create artist with Spotify URI
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        # Mock Spotify API response
        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    "name": "Test Album",
                    "release_date": "2024-01-15",
                    "album_type": "album",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.album_repo.add = AsyncMock()

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert len(albums) == 1
        assert albums[0].title == "Test Album"
        assert albums[0].release_year == 2024
        assert stats["albums_created"] == 1
        assert stats["albums_updated"] == 0

    @pytest.mark.asyncio
    async def test_sync_albums_updates_existing_albums(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test that existing albums are updated."""
        artist_id = ArtistId.generate()
        artist = Artist(
            id=artist_id,
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        # Create existing album
        existing_album = Album(
            id=AlbumId.generate(),
            title="Old Title",
            artist_id=artist_id,
            release_year=2023,
            spotify_uri=SpotifyUri.from_string("spotify:album:album123"),
        )

        # Mock Spotify API response with updated title
        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    "name": "New Title",
                    "release_date": "2024",
                    "album_type": "album",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=existing_album)
        service.album_repo.update = AsyncMock()

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert len(albums) == 1
        assert albums[0].title == "New Title"
        assert albums[0].release_year == 2024
        assert stats["albums_created"] == 0
        assert stats["albums_updated"] == 1

    @pytest.mark.asyncio
    async def test_sync_albums_handles_api_errors(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test graceful error handling when Spotify API fails."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        # Mock Spotify API to raise error
        mock_spotify_client.get_artist_albums = AsyncMock(
            side_effect=Exception("API error")
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert albums == []
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_sync_albums_for_single_artist(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test syncing albums for a single artist."""
        artist_id = ArtistId.generate()
        artist = Artist(
            id=artist_id,
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album1",
                    "name": "Album One",
                    "release_date": "2024",
                },
                {
                    "id": "album2",
                    "name": "Album Two",
                    "release_date": "2023",
                },
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.get_by_id = AsyncMock(return_value=artist)

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.album_repo.add = AsyncMock()

        albums, stats = await service.sync_albums_for_artist(artist_id, "test_token")

        assert len(albums) == 2
        assert stats["albums_created"] == 2

    @pytest.mark.asyncio
    async def test_sync_albums_for_artist_not_found(
        self, service: AlbumSyncService, mock_session: AsyncMock
    ) -> None:
        """Test error when artist not found."""
        artist_id = ArtistId.generate()

        service.artist_repo = AsyncMock()
        service.artist_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Artist not found"):
            await service.sync_albums_for_artist(artist_id, "test_token")

    @pytest.mark.asyncio
    async def test_sync_albums_for_artist_no_spotify_uri(
        self, service: AlbumSyncService, mock_session: AsyncMock
    ) -> None:
        """Test error when artist has no Spotify URI."""
        artist_id = ArtistId.generate()
        artist = Artist(
            id=artist_id,
            name="Test Artist",
            spotify_uri=None,
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.get_by_id = AsyncMock(return_value=artist)

        with pytest.raises(ValueError, match="has no Spotify URI"):
            await service.sync_albums_for_artist(artist_id, "test_token")

    @pytest.mark.asyncio
    async def test_parse_release_year_full_date(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test parsing release year from full date format (YYYY-MM-DD)."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    "name": "Test Album",
                    "release_date": "2024-06-15",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.album_repo.add = AsyncMock()

        albums, _ = await service.sync_albums_for_followed_artists("test_token")

        assert albums[0].release_year == 2024

    @pytest.mark.asyncio
    async def test_parse_release_year_month_only(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test parsing release year from month format (YYYY-MM)."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    "name": "Test Album",
                    "release_date": "2023-11",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.album_repo.add = AsyncMock()

        albums, _ = await service.sync_albums_for_followed_artists("test_token")

        assert albums[0].release_year == 2023

    @pytest.mark.asyncio
    async def test_parse_release_year_year_only(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test parsing release year from year-only format (YYYY)."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    "name": "Test Album",
                    "release_date": "1999",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        service.album_repo = AsyncMock()
        service.album_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.album_repo.add = AsyncMock()

        albums, _ = await service.sync_albums_for_followed_artists("test_token")

        assert albums[0].release_year == 1999

    @pytest.mark.asyncio
    async def test_invalid_album_data_missing_id(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test handling of album data with missing ID."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "name": "Test Album",  # Missing 'id'
                    "release_date": "2024",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert albums == []
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_invalid_album_data_missing_name(
        self,
        service: AlbumSyncService,
        mock_session: AsyncMock,
        mock_spotify_client: AsyncMock,
    ) -> None:
        """Test handling of album data with missing name."""
        artist = Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:1234abc"),
        )

        mock_spotify_client.get_artist_albums = AsyncMock(
            return_value=[
                {
                    "id": "album123",
                    # Missing 'name'
                    "release_date": "2024",
                }
            ]
        )

        service.artist_repo = AsyncMock()
        service.artist_repo.list_all = AsyncMock(return_value=[artist])

        albums, stats = await service.sync_albums_for_followed_artists("test_token")

        assert albums == []
        assert stats["errors"] == 1
