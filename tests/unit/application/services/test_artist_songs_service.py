"""Unit tests for artist songs service."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.artist_songs_service import ArtistSongsService
from soulspot.domain.entities import Artist, Track
from soulspot.domain.value_objects import ArtistId, SpotifyUri, TrackId


class TestArtistSongsService:
    """Test ArtistSongsService."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_spotify_client(self) -> AsyncMock:
        """Create a mock Spotify client."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self, mock_session: AsyncMock, mock_spotify_client: AsyncMock
    ) -> ArtistSongsService:
        """Create service with mocked dependencies."""
        return ArtistSongsService(
            session=mock_session,
            spotify_client=mock_spotify_client,
        )

    @pytest.fixture
    def mock_artist(self) -> Artist:
        """Create a mock artist entity."""
        return Artist(
            id=ArtistId.generate(),
            name="Test Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:123abc"),
        )

    @pytest.fixture
    def mock_spotify_tracks(self) -> list[dict]:
        """Create mock Spotify top tracks response."""
        return [
            {
                "id": "track1",
                "name": "Hit Song 1",
                "duration_ms": 200000,
                "track_number": 1,
                "disc_number": 1,
                "album": {"album_type": "single", "name": "Single 1"},
                "external_ids": {"isrc": "USRC12345678"},
            },
            {
                "id": "track2",
                "name": "Hit Song 2",
                "duration_ms": 180000,
                "track_number": 1,
                "disc_number": 1,
                "album": {"album_type": "album", "name": "Album 1"},
                "external_ids": {"isrc": "USRC12345679"},
            },
            {
                "id": "track3",
                "name": "Hit Song 3",
                "duration_ms": 220000,
                "track_number": 1,
                "disc_number": 1,
                "album": {"album_type": "single", "name": "Single 2"},
                "external_ids": {},
            },
        ]

    @pytest.mark.asyncio
    async def test_sync_artist_songs_success(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
        mock_spotify_tracks: list[dict],
    ) -> None:
        """Test successful sync of artist songs."""
        # Setup mocks
        service.artist_repo.get_by_id = AsyncMock(return_value=mock_artist)
        service.spotify_client.get_artist_top_tracks = AsyncMock(
            return_value=mock_spotify_tracks
        )
        service.track_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.track_repo.add = AsyncMock()

        # Execute
        tracks, stats = await service.sync_artist_songs(
            artist_id=mock_artist.id,
            access_token="test_token",
            market="US",
        )

        # Verify
        assert stats["total_fetched"] == 3
        assert stats["created"] == 3
        assert stats["updated"] == 0
        assert stats["errors"] == 0
        assert len(tracks) == 3

        # Verify Spotify API was called with correct params
        service.spotify_client.get_artist_top_tracks.assert_called_once_with(
            artist_id="123abc",
            access_token="test_token",
            market="US",
        )

    @pytest.mark.asyncio
    async def test_sync_artist_songs_updates_existing(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test that existing tracks are updated, not created."""
        existing_track = Track(
            id=TrackId.generate(),
            title="Old Title",
            artist_id=mock_artist.id,
            duration_ms=100000,
            spotify_uri=SpotifyUri.from_string("spotify:track:track1"),
        )

        spotify_track = {
            "id": "track1",
            "name": "New Title",  # Updated title
            "duration_ms": 200000,  # Updated duration
            "track_number": 1,
            "disc_number": 1,
            "album": {"album_type": "single"},
            "external_ids": {},
        }

        # Setup mocks
        service.artist_repo.get_by_id = AsyncMock(return_value=mock_artist)
        service.spotify_client.get_artist_top_tracks = AsyncMock(
            return_value=[spotify_track]
        )
        service.track_repo.get_by_spotify_uri = AsyncMock(return_value=existing_track)
        service.track_repo.update = AsyncMock()

        # Execute
        tracks, stats = await service.sync_artist_songs(
            artist_id=mock_artist.id,
            access_token="test_token",
        )

        # Verify
        assert stats["total_fetched"] == 1
        assert stats["created"] == 0
        assert stats["updated"] == 1
        assert existing_track.title == "New Title"
        assert existing_track.duration_ms == 200000
        service.track_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_artist_songs_artist_not_found(
        self,
        service: ArtistSongsService,
    ) -> None:
        """Test sync fails when artist not found."""
        service.artist_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Artist not found"):
            await service.sync_artist_songs(
                artist_id=ArtistId.generate(),
                access_token="test_token",
            )

    @pytest.mark.asyncio
    async def test_sync_artist_songs_no_spotify_uri(
        self,
        service: ArtistSongsService,
    ) -> None:
        """Test sync fails when artist has no Spotify URI."""
        artist_without_uri = Artist(
            id=ArtistId.generate(),
            name="Local Artist",
            spotify_uri=None,
        )
        service.artist_repo.get_by_id = AsyncMock(return_value=artist_without_uri)

        with pytest.raises(ValueError, match="no Spotify URI"):
            await service.sync_artist_songs(
                artist_id=artist_without_uri.id,
                access_token="test_token",
            )

    @pytest.mark.asyncio
    async def test_get_artist_singles(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test getting singles for an artist."""
        mock_tracks = [
            Track(
                id=TrackId.generate(),
                title="Single 1",
                artist_id=mock_artist.id,
                album_id=None,
            ),
            Track(
                id=TrackId.generate(),
                title="Single 2",
                artist_id=mock_artist.id,
                album_id=None,
            ),
        ]
        service.track_repo.get_singles_by_artist = AsyncMock(return_value=mock_tracks)

        result = await service.get_artist_singles(mock_artist.id)

        assert len(result) == 2
        service.track_repo.get_singles_by_artist.assert_called_once_with(mock_artist.id)

    @pytest.mark.asyncio
    async def test_remove_song_success(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test removing a single song."""
        track_id = TrackId.generate()
        track = Track(
            id=track_id,
            title="Song to Delete",
            artist_id=mock_artist.id,
        )
        service.track_repo.get_by_id = AsyncMock(return_value=track)
        service.track_repo.delete = AsyncMock()

        result = await service.remove_song(track_id, mock_artist.id)

        assert result is True
        service.track_repo.delete.assert_called_once_with(track_id)

    @pytest.mark.asyncio
    async def test_remove_song_not_found(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test removing a song that doesn't exist."""
        track_id = TrackId.generate()
        service.track_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Track not found"):
            await service.remove_song(track_id, mock_artist.id)

    @pytest.mark.asyncio
    async def test_remove_song_wrong_artist(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test removing a song that belongs to different artist."""
        track_id = TrackId.generate()
        other_artist_id = ArtistId.generate()
        track = Track(
            id=track_id,
            title="Wrong Artist Song",
            artist_id=other_artist_id,  # Different artist
        )
        service.track_repo.get_by_id = AsyncMock(return_value=track)

        with pytest.raises(ValueError, match="does not belong to artist"):
            await service.remove_song(track_id, mock_artist.id)

    @pytest.mark.asyncio
    async def test_remove_all_artist_songs(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test removing all songs for an artist."""
        mock_tracks = [
            Track(id=TrackId.generate(), title="Song 1", artist_id=mock_artist.id),
            Track(id=TrackId.generate(), title="Song 2", artist_id=mock_artist.id),
            Track(id=TrackId.generate(), title="Song 3", artist_id=mock_artist.id),
        ]
        service.track_repo.get_singles_by_artist = AsyncMock(return_value=mock_tracks)
        service.track_repo.delete = AsyncMock()

        count = await service.remove_all_artist_songs(mock_artist.id)

        assert count == 3
        assert service.track_repo.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_all_artists_songs(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
        mock_spotify_tracks: list[dict],
    ) -> None:
        """Test bulk sync for all artists."""
        artists = [mock_artist]

        # Setup mocks
        service.artist_repo.list_all = AsyncMock(return_value=artists)
        service.artist_repo.get_by_id = AsyncMock(return_value=mock_artist)
        service.spotify_client.get_artist_top_tracks = AsyncMock(
            return_value=mock_spotify_tracks
        )
        service.track_repo.get_by_spotify_uri = AsyncMock(return_value=None)
        service.track_repo.add = AsyncMock()

        # Execute
        tracks, stats = await service.sync_all_artists_songs(
            access_token="test_token",
            market="US",
            limit=10,
        )

        # Verify
        assert stats["artists_processed"] == 1
        assert stats["total_fetched"] == 3
        assert stats["created"] == 3
        assert len(tracks) == 3
        service.artist_repo.list_all.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_process_track_with_invalid_data(
        self,
        service: ArtistSongsService,
        mock_artist: Artist,
    ) -> None:
        """Test processing track with missing required fields."""
        invalid_track = {"id": None, "name": None}  # Missing required fields

        track, was_created, is_single = await service._process_track(
            invalid_track, mock_artist.id
        )

        assert track is None
        assert was_created is False
        assert is_single is False
