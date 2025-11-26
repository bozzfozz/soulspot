"""Unit tests for album repository."""


import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from soulspot.domain.entities import Album, Artist
from soulspot.domain.value_objects import AlbumId, ArtistId, SpotifyUri
from soulspot.infrastructure.persistence.models import Base
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
)


@pytest.fixture(scope="function")
async def async_session():
    """Create an async test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create tables with checkfirst to avoid duplicate index errors
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True)
        )

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()
        await session.close()

    await engine.dispose()


@pytest.fixture
async def artist(async_session: AsyncSession) -> Artist:
    """Create a test artist."""
    repo = ArtistRepository(async_session)
    artist = Artist(
        id=ArtistId.generate(),
        name="Test Artist",
        spotify_uri=SpotifyUri.from_string("spotify:artist:test123"),
    )
    await repo.add(artist)
    await async_session.commit()
    return artist


class TestAlbumRepository:
    """Test album repository functionality."""

    @pytest.mark.asyncio
    async def test_add_and_get_by_id(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test adding and retrieving an album by ID."""
        repo = AlbumRepository(async_session)

        album = Album(
            id=AlbumId.generate(),
            title="Test Album",
            artist_id=artist.id,
            release_year=2024,
            spotify_uri=SpotifyUri.from_string("spotify:album:album123"),
        )

        await repo.add(album)
        await async_session.commit()

        retrieved = await repo.get_by_id(album.id)

        assert retrieved is not None
        assert retrieved.title == "Test Album"
        assert retrieved.release_year == 2024
        assert str(retrieved.artist_id.value) == str(artist.id.value)

    @pytest.mark.asyncio
    async def test_get_by_spotify_uri(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test retrieving an album by Spotify URI."""
        repo = AlbumRepository(async_session)

        spotify_uri = SpotifyUri.from_string("spotify:album:unique123")
        album = Album(
            id=AlbumId.generate(),
            title="Unique Album",
            artist_id=artist.id,
            spotify_uri=spotify_uri,
        )

        await repo.add(album)
        await async_session.commit()

        retrieved = await repo.get_by_spotify_uri(spotify_uri)

        assert retrieved is not None
        assert retrieved.title == "Unique Album"
        assert str(retrieved.spotify_uri) == str(spotify_uri)

    @pytest.mark.asyncio
    async def test_get_by_spotify_uri_not_found(
        self, async_session: AsyncSession
    ) -> None:
        """Test get_by_spotify_uri returns None when not found."""
        repo = AlbumRepository(async_session)

        spotify_uri = SpotifyUri.from_string("spotify:album:nonexistent")
        retrieved = await repo.get_by_spotify_uri(spotify_uri)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_all(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test listing all albums."""
        repo = AlbumRepository(async_session)

        # Add multiple albums
        for i in range(5):
            album = Album(
                id=AlbumId.generate(),
                title=f"Album {i}",
                artist_id=artist.id,
                release_year=2020 + i,
                spotify_uri=SpotifyUri.from_string(f"spotify:album:list{i}"),
            )
            await repo.add(album)

        await async_session.commit()

        albums = await repo.list_all()

        assert len(albums) == 5

    @pytest.mark.asyncio
    async def test_list_all_with_pagination(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test listing albums with pagination."""
        repo = AlbumRepository(async_session)

        # Add 10 albums
        for i in range(10):
            album = Album(
                id=AlbumId.generate(),
                title=f"Album {i:02d}",  # Zero-padded for consistent ordering
                artist_id=artist.id,
                spotify_uri=SpotifyUri.from_string(f"spotify:album:page{i}"),
            )
            await repo.add(album)

        await async_session.commit()

        # Test first page
        page1 = await repo.list_all(limit=5, offset=0)
        assert len(page1) == 5

        # Test second page
        page2 = await repo.list_all(limit=5, offset=5)
        assert len(page2) == 5

        # Ensure no overlap
        page1_ids = {str(a.id.value) for a in page1}
        page2_ids = {str(a.id.value) for a in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_count_all(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test counting all albums."""
        repo = AlbumRepository(async_session)

        # Initially empty
        assert await repo.count_all() == 0

        # Add albums
        for i in range(3):
            album = Album(
                id=AlbumId.generate(),
                title=f"Album {i}",
                artist_id=artist.id,
                spotify_uri=SpotifyUri.from_string(f"spotify:album:count{i}"),
            )
            await repo.add(album)

        await async_session.commit()

        assert await repo.count_all() == 3

    @pytest.mark.asyncio
    async def test_update_album(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test updating an album."""
        repo = AlbumRepository(async_session)

        album = Album(
            id=AlbumId.generate(),
            title="Original Title",
            artist_id=artist.id,
            release_year=2023,
            spotify_uri=SpotifyUri.from_string("spotify:album:update123"),
        )

        await repo.add(album)
        await async_session.commit()

        # Update title and year
        album.title = "Updated Title"
        album.release_year = 2024
        await repo.update(album)
        await async_session.commit()

        retrieved = await repo.get_by_id(album.id)

        assert retrieved is not None
        assert retrieved.title == "Updated Title"
        assert retrieved.release_year == 2024

    @pytest.mark.asyncio
    async def test_delete_album(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test deleting an album."""
        repo = AlbumRepository(async_session)

        album = Album(
            id=AlbumId.generate(),
            title="To Be Deleted",
            artist_id=artist.id,
            spotify_uri=SpotifyUri.from_string("spotify:album:delete123"),
        )

        await repo.add(album)
        await async_session.commit()

        # Verify it exists
        assert await repo.get_by_id(album.id) is not None

        # Delete it
        await repo.delete(album.id)
        await async_session.commit()

        # Verify it's gone
        assert await repo.get_by_id(album.id) is None

    @pytest.mark.asyncio
    async def test_get_by_artist(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test getting albums by artist."""
        repo = AlbumRepository(async_session)
        artist_repo = ArtistRepository(async_session)

        # Create another artist
        other_artist = Artist(
            id=ArtistId.generate(),
            name="Other Artist",
            spotify_uri=SpotifyUri.from_string("spotify:artist:other456"),
        )
        await artist_repo.add(other_artist)

        # Add albums for both artists
        for i in range(3):
            album = Album(
                id=AlbumId.generate(),
                title=f"Test Artist Album {i}",
                artist_id=artist.id,
                spotify_uri=SpotifyUri.from_string(f"spotify:album:ta{i}"),
            )
            await repo.add(album)

        for i in range(2):
            album = Album(
                id=AlbumId.generate(),
                title=f"Other Artist Album {i}",
                artist_id=other_artist.id,
                spotify_uri=SpotifyUri.from_string(f"spotify:album:oa{i}"),
            )
            await repo.add(album)

        await async_session.commit()

        # Get albums for first artist
        albums = await repo.get_by_artist(artist.id)
        assert len(albums) == 3

        # Get albums for second artist
        other_albums = await repo.get_by_artist(other_artist.id)
        assert len(other_albums) == 2

    @pytest.mark.asyncio
    async def test_album_without_spotify_uri(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test creating album without Spotify URI (manual entry)."""
        repo = AlbumRepository(async_session)

        album = Album(
            id=AlbumId.generate(),
            title="Manual Album",
            artist_id=artist.id,
            release_year=2020,
            spotify_uri=None,  # No Spotify URI
        )

        await repo.add(album)
        await async_session.commit()

        retrieved = await repo.get_by_id(album.id)

        assert retrieved is not None
        assert retrieved.title == "Manual Album"
        assert retrieved.spotify_uri is None

    @pytest.mark.asyncio
    async def test_album_without_release_year(
        self, async_session: AsyncSession, artist: Artist
    ) -> None:
        """Test creating album without release year."""
        repo = AlbumRepository(async_session)

        album = Album(
            id=AlbumId.generate(),
            title="Unknown Year Album",
            artist_id=artist.id,
            release_year=None,
            spotify_uri=SpotifyUri.from_string("spotify:album:noyear"),
        )

        await repo.add(album)
        await async_session.commit()

        retrieved = await repo.get_by_id(album.id)

        assert retrieved is not None
        assert retrieved.release_year is None
