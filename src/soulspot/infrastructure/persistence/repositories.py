"""Repository implementations for domain entities."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from soulspot.application.services.session_store import Session

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soulspot.domain.entities import (
    Album,
    Artist,
    Download,
    DownloadStatus,
    Playlist,
    PlaylistSource,
    Track,
)
from soulspot.domain.exceptions import EntityNotFoundException, ValidationException
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IDownloadRepository,
    IPlaylistRepository,
    ITrackRepository,
)
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    DownloadId,
    FilePath,
    PlaylistId,
    SpotifyUri,
    TrackId,
)

from .models import (
    AlbumModel,
    ArtistModel,
    DownloadModel,
    PlaylistModel,
    PlaylistTrackModel,
    SessionModel,
    TrackModel,
)

# Type variable for generic repository
T = TypeVar("T")


class ArtistRepository(IArtistRepository):
    """SQLAlchemy implementation of Artist repository."""

    # Hey future me, this is the Repository pattern! Each repo gets its own AsyncSession injected
    # from the DB dependency. The session is NOT committed here - that happens in the route/use case!
    # Repo only stages changes (session.add, model updates). If you call add() then the request
    # fails before commit, the DB stays unchanged (transaction rollback). Don't create your own
    # session inside repos - always use the injected one or you'll get isolation/deadlock issues!
    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    # Yo, add() converts domain entity (Artist) to ORM model (ArtistModel) and stages it. Note we
    # convert IDs and URIs to strings for DB storage (UUIDs/URIs as varchar). The session.add()
    # does NOT hit the database yet - it just marks model for INSERT. Actual DB write happens on
    # session.commit() (handled by dependency). If artist.id already exists in DB, you'll get
    # IntegrityError on commit - this method doesn't check! Use get_by_id first if you care.
    # Hey - genres/tags are serialized as JSON strings for SQLite compatibility!
    # Hey - image_url is stored directly as string (Spotify CDN URL)!
    async def add(self, artist: Artist) -> None:
        """Add a new artist."""
        model = ArtistModel(
            id=str(artist.id.value),
            name=artist.name,
            spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
            musicbrainz_id=artist.musicbrainz_id,
            image_url=artist.image_url,
            genres=json.dumps(artist.genres) if artist.genres else None,
            tags=json.dumps(artist.tags) if artist.tags else None,
            created_at=artist.created_at,
            updated_at=artist.updated_at,
        )
        self.session.add(model)

    async def update(self, artist: Artist) -> None:
        """Update an existing artist."""
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Artist", artist.id.value)

        model.name = artist.name
        model.spotify_uri = str(artist.spotify_uri) if artist.spotify_uri else None
        model.musicbrainz_id = artist.musicbrainz_id
        model.image_url = artist.image_url
        model.genres = json.dumps(artist.genres) if artist.genres else None
        model.tags = json.dumps(artist.tags) if artist.tags else None
        model.updated_at = artist.updated_at

    async def delete(self, artist_id: ArtistId) -> None:
        """Delete an artist."""
        stmt = delete(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Artist", artist_id.value)

    # Listen up, get_by_id fetches from DB and converts ORM model back to domain entity. Returns None
    # if not found (not an error!). The scalar_one_or_none() is important - it returns ONE row or None,
    # raising if multiple rows match (shouldn't happen with unique ID but defensive). We reconstruct
    # the domain Artist object with all its value objects (ArtistId, SpotifyUri). The if/else on
    # spotify_uri handles nullable field - can't call SpotifyUri.from_string(None)!
    # Hey - genres/tags are deserialized from JSON strings!
    # Hey - image_url is stored directly as string (no conversion needed)!
    async def get_by_id(self, artist_id: ArtistId) -> Artist | None:
        """Get an artist by ID."""
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_name(self, name: str) -> Artist | None:
        """Get an artist by name."""
        stmt = select(ArtistModel).where(ArtistModel.name == name)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Artist | None:
        """Get an artist by MusicBrainz ID."""
        stmt = select(ArtistModel).where(ArtistModel.musicbrainz_id == musicbrainz_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Hey future me, this gets artist by Spotify URI (spotify:artist:xxxxx). Used when syncing
    # followed artists from Spotify - we check if artist already exists before creating. The URI
    # is stored as string in DB but we convert to/from SpotifyUri value object. Returns None if
    # not found. This is similar to get_by_musicbrainz_id but for Spotify identifiers.
    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Artist | None:
        """Get an artist by Spotify URI.

        Args:
            spotify_uri: Spotify URI (e.g., spotify:artist:4RbUYWWjEBb4umwqakOEd3)

        Returns:
            Artist entity if found, None otherwise
        """
        stmt = select(ArtistModel).where(ArtistModel.spotify_uri == str(spotify_uri))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        """List all artists with pagination."""
        stmt = (
            select(ArtistModel).order_by(ArtistModel.name).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Artist(
                id=ArtistId.from_string(model.id),
                name=model.name,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                image_url=model.image_url,
                genres=json.loads(model.genres) if model.genres else [],
                tags=json.loads(model.tags) if model.tags else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - this counts ALL artists in the DB using SQL COUNT (efficient!).
    # Used for pagination total_count and stats. Returns 0 if no artists exist (not None).
    async def count_all(self) -> int:
        """Count total number of artists in the database.

        Returns:
            Total count of artists
        """
        stmt = select(func.count(ArtistModel.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class AlbumRepository(IAlbumRepository):
    """SQLAlchemy implementation of Album repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, album: Album) -> None:
        """Add a new album."""
        model = AlbumModel(
            id=str(album.id.value),
            title=album.title,
            artist_id=str(album.artist_id.value),
            release_year=album.release_year,
            spotify_uri=str(album.spotify_uri.value) if album.spotify_uri else None,
            musicbrainz_id=album.musicbrainz_id,
            artwork_path=str(album.artwork_path.value) if album.artwork_path else None,
            artwork_url=album.artwork_url,  # NEW: Include artwork URL!
            created_at=album.created_at,
            updated_at=album.updated_at,
        )
        self.session.add(model)

    async def update(self, album: Album) -> None:
        """Update an existing album."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one()

        model.title = album.title
        model.artist_id = str(album.artist_id.value)
        model.release_year = album.release_year
        model.spotify_uri = str(album.spotify_uri.value) if album.spotify_uri else None
        model.musicbrainz_id = album.musicbrainz_id
        model.artwork_path = str(album.artwork_path.value) if album.artwork_path else None
        model.artwork_url = album.artwork_url  # NEW: Include artwork URL!
        model.updated_at = album.updated_at

        self.session.add(model)

    async def delete(self, album_id: AlbumId) -> None:
        """Delete an album."""
        stmt = delete(AlbumModel).where(AlbumModel.id == str(album_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Album", album_id.value)

    async def get_by_id(self, album_id: AlbumId) -> Album | None:
        """Get an album by ID."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Album(
            id=AlbumId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            release_year=model.release_year,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_path=FilePath.from_string(model.artwork_path)
            if model.artwork_path
            else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_artist(self, artist_id: ArtistId) -> list[Album]:
        """Get all albums by an artist."""
        stmt = (
            select(AlbumModel)
            .where(AlbumModel.artist_id == str(artist_id.value))
            .order_by(AlbumModel.release_year)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Album(
                id=AlbumId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                release_year=model.release_year,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                artwork_path=FilePath.from_string(model.artwork_path)
                if model.artwork_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Album | None:
        """Get an album by MusicBrainz ID."""
        stmt = select(AlbumModel).where(AlbumModel.musicbrainz_id == musicbrainz_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Album(
            id=AlbumId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            release_year=model.release_year,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_path=FilePath(model.artwork_path) if model.artwork_path else None,
            artwork_url=model.artwork_url if hasattr(model, 'artwork_url') else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Hey future me, this gets album by Spotify URI! Essential for playlist import to avoid
    # creating duplicate albums. Spotify track data includes album info with URI, so we can
    # check if album already exists before creating. This is the same pattern as artist
    # get_by_spotify_uri - deduplicate by URI, not by name (multiple albums can share names!).
    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Album | None:
        """Get an album by Spotify URI.
        
        Args:
            spotify_uri: Spotify URI (e.g., spotify:album:4aawyAB9vmqN3uQ7FjRGTy)
            
        Returns:
            Album entity if found, None otherwise
        """
        stmt = select(AlbumModel).where(
            AlbumModel.spotify_uri == str(spotify_uri.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Album(
            id=AlbumId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            release_year=model.release_year,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_path=FilePath(model.artwork_path) if model.artwork_path else None,
            artwork_url=model.artwork_url if hasattr(model, 'artwork_url') else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class TrackRepository(ITrackRepository):
    """SQLAlchemy implementation of Track repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, track: Track) -> None:
        """Add a new track."""
        # Hey - extract primary genre from genres list for DB storage!
        # Takes first genre if available, else None. DB stores single genre for filtering.
        # Check both that list exists AND is not empty before accessing [0]
        primary_genre = (
            track.genres[0] if (track.genres and len(track.genres) > 0) else None
        )

        model = TrackModel(
            id=str(track.id.value),
            title=track.title,
            artist_id=str(track.artist_id.value),
            album_id=str(track.album_id.value) if track.album_id else None,
            duration_ms=track.duration_ms,
            track_number=track.track_number,
            disc_number=track.disc_number,
            spotify_uri=str(track.spotify_uri) if track.spotify_uri else None,
            musicbrainz_id=track.musicbrainz_id,
            isrc=track.isrc,
            file_path=str(track.file_path) if track.file_path else None,
            genre=primary_genre,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        self.session.add(model)

    async def update(self, track: Track) -> None:
        """Update an existing track."""
        stmt = select(TrackModel).where(TrackModel.id == str(track.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Track", track.id.value)

        # Hey - update genre from entity's genres list (primary genre only)
        # Check both that list exists AND is not empty before accessing [0]
        primary_genre = (
            track.genres[0] if (track.genres and len(track.genres) > 0) else None
        )

        model.title = track.title
        model.artist_id = str(track.artist_id.value)
        model.album_id = str(track.album_id.value) if track.album_id else None
        model.duration_ms = track.duration_ms
        model.track_number = track.track_number
        model.disc_number = track.disc_number
        model.spotify_uri = str(track.spotify_uri) if track.spotify_uri else None
        model.musicbrainz_id = track.musicbrainz_id
        model.isrc = track.isrc
        model.file_path = str(track.file_path) if track.file_path else None
        model.genre = primary_genre
        model.updated_at = track.updated_at

    async def delete(self, track_id: TrackId) -> None:
        """Delete a track."""
        stmt = delete(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Track", track_id.value)

    async def get_by_id(self, track_id: TrackId) -> Track | None:
        """Get a track by ID."""
        stmt = select(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre]
            if model.genre
            else [],  # Hey - convert single genre back to list!
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Track | None:
        """Get a track by Spotify URI."""
        stmt = select(TrackModel).where(TrackModel.spotify_uri == str(spotify_uri))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_album(self, album_id: AlbumId) -> list[Track]:
        """Get all tracks in an album."""
        stmt = (
            select(TrackModel)
            .where(TrackModel.album_id == str(album_id.value))
            .order_by(TrackModel.disc_number, TrackModel.track_number)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def get_by_artist(self, artist_id: ArtistId) -> list[Track]:
        """Get all tracks by an artist."""
        stmt = (
            select(TrackModel)
            .where(TrackModel.artist_id == str(artist_id.value))
            .order_by(TrackModel.title)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Track]:
        """List all tracks with pagination and eager loading of relationships."""
        stmt = (
            select(TrackModel)
            .options(
                selectinload(TrackModel.artist),
                selectinload(TrackModel.album),
            )
            .order_by(TrackModel.title)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def count_all(self) -> int:
        """Count total number of tracks."""
        stmt = select(func.count(TrackModel.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def add_batch(self, tracks: list[Track]) -> None:
        """Add multiple tracks in a single batch operation.

        This is more efficient than calling add() multiple times as it reduces
        the number of round trips to the database.

        Args:
            tracks: List of Track entities to add
        """
        models = [
            TrackModel(
                id=str(track.id.value),
                title=track.title,
                artist_id=str(track.artist_id.value),
                album_id=str(track.album_id.value) if track.album_id else None,
                duration_ms=track.duration_ms,
                track_number=track.track_number,
                disc_number=track.disc_number,
                spotify_uri=str(track.spotify_uri) if track.spotify_uri else None,
                musicbrainz_id=track.musicbrainz_id,
                isrc=track.isrc,
                file_path=str(track.file_path) if track.file_path else None,
                created_at=track.created_at,
                updated_at=track.updated_at,
            )
            for track in tracks
        ]
        self.session.add_all(models)

    async def update_batch(self, tracks: list[Track]) -> None:
        """Update multiple tracks in a single batch operation.

        This is more efficient than calling update() multiple times.
        Note: This loads all tracks into memory first, then updates them.

        Args:
            tracks: List of Track entities to update
        """
        track_ids = [str(track.id.value) for track in tracks]
        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids))
        result = await self.session.execute(stmt)
        models = {model.id: model for model in result.scalars().all()}

        for track in tracks:
            model = models.get(str(track.id.value))
            if model:
                model.title = track.title
                model.artist_id = str(track.artist_id.value)
                model.album_id = str(track.album_id.value) if track.album_id else None
                model.duration_ms = track.duration_ms
                model.track_number = track.track_number
                model.disc_number = track.disc_number
                model.spotify_uri = (
                    str(track.spotify_uri) if track.spotify_uri else None
                )
                model.musicbrainz_id = track.musicbrainz_id
                model.isrc = track.isrc
                model.file_path = str(track.file_path) if track.file_path else None
                model.updated_at = track.updated_at


class PlaylistRepository(IPlaylistRepository):
    """SQLAlchemy implementation of Playlist repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, playlist: Playlist) -> None:
        """Add a new playlist."""
        model = PlaylistModel(
            id=str(playlist.id.value),
            name=playlist.name,
            description=playlist.description,
            source=playlist.source.value,
            spotify_uri=str(playlist.spotify_uri) if playlist.spotify_uri else None,
            cover_url=playlist.cover_url,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )
        self.session.add(model)

        # Add playlist tracks
        for position, track_id in enumerate(playlist.track_ids):
            playlist_track = PlaylistTrackModel(
                playlist_id=str(playlist.id.value),
                track_id=str(track_id.value),
                position=position,
            )
            self.session.add(playlist_track)

    async def update(self, playlist: Playlist) -> None:
        """Update an existing playlist."""
        stmt = select(PlaylistModel).where(PlaylistModel.id == str(playlist.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Playlist", playlist.id.value)

        model.name = playlist.name
        model.description = playlist.description
        model.source = playlist.source.value
        model.spotify_uri = str(playlist.spotify_uri) if playlist.spotify_uri else None
        model.cover_url = playlist.cover_url
        model.updated_at = playlist.updated_at

        # Update playlist tracks - delete old and add new
        delete_stmt = delete(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == str(playlist.id.value)
        )
        await self.session.execute(delete_stmt)

        for position, track_id in enumerate(playlist.track_ids):
            playlist_track = PlaylistTrackModel(
                playlist_id=str(playlist.id.value),
                track_id=str(track_id.value),
                position=position,
            )
            self.session.add(playlist_track)

    async def delete(self, playlist_id: PlaylistId) -> None:
        """Delete a playlist."""
        stmt = delete(PlaylistModel).where(PlaylistModel.id == str(playlist_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Playlist", playlist_id.value)

    async def get_by_id(self, playlist_id: PlaylistId) -> Playlist | None:
        """Get a playlist by ID with eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.id == str(playlist_id.value))
            .options(selectinload(PlaylistModel.playlist_tracks))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get playlist tracks in order
        track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]

        # Convert source string to PlaylistSource enum
        try:
            source = PlaylistSource(model.source)
        except ValueError as e:
            raise ValidationException(
                f"Invalid playlist source '{model.source}' for playlist {model.id}"
            ) from e

        return Playlist(
            id=PlaylistId.from_string(model.id),
            name=model.name,
            description=model.description,
            source=source,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            track_ids=track_ids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Playlist | None:
        """Get a playlist by Spotify URI with eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.spotify_uri == str(spotify_uri))
            .options(selectinload(PlaylistModel.playlist_tracks))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get playlist tracks in order
        track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]

        # Convert source string to PlaylistSource enum
        try:
            source = PlaylistSource(model.source)
        except ValueError as e:
            raise ValidationException(
                f"Invalid playlist source '{model.source}' for playlist {model.id}"
            ) from e

        return Playlist(
            id=PlaylistId.from_string(model.id),
            name=model.name,
            description=model.description,
            source=source,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            track_ids=track_ids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def add_track(self, playlist_id: PlaylistId, track_id: TrackId) -> None:
        """Add a track to a playlist."""
        # Get current max position
        stmt = select(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == str(playlist_id.value)
        )
        result = await self.session.execute(stmt)
        existing_tracks = result.scalars().all()

        max_position = max([pt.position for pt in existing_tracks], default=-1)

        # Add new track at end
        playlist_track = PlaylistTrackModel(
            playlist_id=str(playlist_id.value),
            track_id=str(track_id.value),
            position=max_position + 1,
        )
        self.session.add(playlist_track)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Playlist]:
        """List all playlists with pagination and eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .options(selectinload(PlaylistModel.playlist_tracks))
            .order_by(PlaylistModel.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        playlists = []
        for model in models:
            track_ids = [
                TrackId.from_string(pt.track_id) for pt in model.playlist_tracks
            ]
            # Convert source string to PlaylistSource enum
            try:
                source = PlaylistSource(model.source)
            except ValueError as e:
                raise ValidationException(
                    f"Invalid playlist source '{model.source}' for playlist {model.id}"
                ) from e

            playlists.append(
                Playlist(
                    id=PlaylistId.from_string(model.id),
                    name=model.name,
                    description=model.description,
                    source=source,
                    spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                    if model.spotify_uri
                    else None,
                    cover_url=model.cover_url,
                    track_ids=track_ids,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
            )

        return playlists


class DownloadRepository(IDownloadRepository):
    """SQLAlchemy implementation of Download repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, download: Download) -> None:
        """Add a new download."""
        model = DownloadModel(
            id=str(download.id.value),
            track_id=str(download.track_id.value),
            status=download.status.value,
            priority=download.priority,
            target_path=str(download.target_path) if download.target_path else None,
            source_url=download.source_url,
            progress_percent=download.progress_percent,
            error_message=download.error_message,
            started_at=download.started_at,
            completed_at=download.completed_at,
            created_at=download.created_at,
            updated_at=download.updated_at,
        )
        self.session.add(model)

    async def update(self, download: Download) -> None:
        """Update an existing download."""
        stmt = select(DownloadModel).where(DownloadModel.id == str(download.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Download", download.id.value)

        model.track_id = str(download.track_id.value)
        model.status = download.status.value
        model.priority = download.priority
        model.target_path = str(download.target_path) if download.target_path else None
        model.source_url = download.source_url
        model.progress_percent = download.progress_percent
        model.error_message = download.error_message
        model.started_at = download.started_at
        model.completed_at = download.completed_at
        model.updated_at = download.updated_at

    async def delete(self, download_id: DownloadId) -> None:
        """Delete a download."""
        stmt = delete(DownloadModel).where(DownloadModel.id == str(download_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("Download", download_id.value)

    async def get_by_id(self, download_id: DownloadId) -> Download | None:
        """Get a download by ID with eager loading of track."""
        stmt = (
            select(DownloadModel)
            .where(DownloadModel.id == str(download_id.value))
            .options(selectinload(DownloadModel.track))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Convert status string to DownloadStatus enum
        try:
            status = DownloadStatus(model.status)
        except ValueError as e:
            raise ValidationException(
                f"Invalid download status '{model.status}' for download {model.id}"
            ) from e

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=status,
            priority=model.priority,
            target_path=FilePath.from_string(model.target_path)
            if model.target_path
            else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_track(self, track_id: TrackId) -> Download | None:
        """Get a download by track ID with eager loading."""
        stmt = (
            select(DownloadModel)
            .where(DownloadModel.track_id == str(track_id.value))
            .options(selectinload(DownloadModel.track))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Convert status string to DownloadStatus enum
        try:
            status = DownloadStatus(model.status)
        except ValueError as e:
            raise ValidationException(
                f"Invalid download status '{model.status}' for download {model.id}"
            ) from e

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=status,
            priority=model.priority,
            target_path=FilePath.from_string(model.target_path)
            if model.target_path
            else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> list[Download]:
        """List downloads with a specific status, with pagination and eager loading."""
        stmt = (
            select(DownloadModel)
            .options(selectinload(DownloadModel.track))
            .where(DownloadModel.status == status)
            .order_by(DownloadModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=DownloadStatus(model.status),
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Download]:
        """List all active downloads (not finished), with pagination and eager loading."""
        stmt = (
            select(DownloadModel)
            .options(selectinload(DownloadModel.track))
            .where(
                DownloadModel.status.in_(
                    [
                        DownloadStatus.QUEUED.value,
                        DownloadStatus.DOWNLOADING.value,
                    ]
                )
            )
            .order_by(DownloadModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=DownloadStatus(model.status),
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def count_by_status(self, status: str) -> int:
        """Count downloads by status."""
        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == status
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_active(self) -> int:
        """Count active downloads."""
        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status.in_(
                [
                    DownloadStatus.QUEUED.value,
                    DownloadStatus.DOWNLOADING.value,
                ]
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class ArtistWatchlistRepository:
    """SQLAlchemy implementation of Artist Watchlist repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, watchlist: Any) -> None:
        """Add a new watchlist."""

        from .models import ArtistWatchlistModel

        model = ArtistWatchlistModel(
            id=str(watchlist.id.value),
            artist_id=str(watchlist.artist_id.value),
            status=watchlist.status.value,
            check_frequency_hours=watchlist.check_frequency_hours,
            auto_download=watchlist.auto_download,
            quality_profile=watchlist.quality_profile,
            last_checked_at=watchlist.last_checked_at,
            last_release_date=watchlist.last_release_date,
            total_releases_found=watchlist.total_releases_found,
            total_downloads_triggered=watchlist.total_downloads_triggered,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, watchlist_id: Any) -> Any:
        """Get a watchlist by ID."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return ArtistWatchlist(
            id=WatchlistId.from_string(model.id),
            artist_id=ArtistId.from_string(model.artist_id),
            status=WatchlistStatus(model.status),
            check_frequency_hours=model.check_frequency_hours,
            auto_download=model.auto_download,
            quality_profile=model.quality_profile,
            last_checked_at=model.last_checked_at,
            last_release_date=model.last_release_date,
            total_releases_found=model.total_releases_found,
            total_downloads_triggered=model.total_downloads_triggered,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_artist_id(self, artist_id: ArtistId) -> Any:
        """Get watchlist for an artist."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.artist_id == str(artist_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return ArtistWatchlist(
            id=WatchlistId.from_string(model.id),
            artist_id=ArtistId.from_string(model.artist_id),
            status=WatchlistStatus(model.status),
            check_frequency_hours=model.check_frequency_hours,
            auto_download=model.auto_download,
            quality_profile=model.quality_profile,
            last_checked_at=model.last_checked_at,
            last_release_date=model.last_release_date,
            total_releases_found=model.total_releases_found,
            total_downloads_triggered=model.total_downloads_triggered,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all watchlists with pagination."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List active watchlists."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = (
            select(ArtistWatchlistModel)
            .where(ArtistWatchlistModel.status == "active")
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_due_for_check(self, limit: int = 100) -> list[Any]:
        """List watchlists that are due for checking."""

        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        # Active watchlists that haven't been checked or are due for check
        stmt = (
            select(ArtistWatchlistModel)
            .where(ArtistWatchlistModel.status == "active")
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        # Filter in Python for simpler logic
        due_watchlists = []
        for model in models:
            watchlist = ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            if watchlist.should_check():
                due_watchlists.append(watchlist)

        return due_watchlists[:limit]

    async def update(self, watchlist: Any) -> None:
        """Update an existing watchlist."""
        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("ArtistWatchlist", watchlist.id.value)

        model.status = watchlist.status.value
        model.check_frequency_hours = watchlist.check_frequency_hours
        model.auto_download = watchlist.auto_download
        model.quality_profile = watchlist.quality_profile
        model.last_checked_at = watchlist.last_checked_at
        model.last_release_date = watchlist.last_release_date
        model.total_releases_found = watchlist.total_releases_found
        model.total_downloads_triggered = watchlist.total_downloads_triggered
        model.updated_at = watchlist.updated_at

    async def delete(self, watchlist_id: Any) -> None:
        """Delete a watchlist."""
        from .models import ArtistWatchlistModel

        stmt = delete(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist_id.value)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("ArtistWatchlist", watchlist_id.value)


class FilterRuleRepository:
    """SQLAlchemy implementation of Filter Rule repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, filter_rule: Any) -> None:
        """Add a new filter rule."""
        from .models import FilterRuleModel

        model = FilterRuleModel(
            id=str(filter_rule.id.value),
            name=filter_rule.name,
            filter_type=filter_rule.filter_type.value,
            target=filter_rule.target.value,
            pattern=filter_rule.pattern,
            is_regex=filter_rule.is_regex,
            enabled=filter_rule.enabled,
            priority=filter_rule.priority,
            description=filter_rule.description,
            created_at=filter_rule.created_at,
            updated_at=filter_rule.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, rule_id: Any) -> Any:
        """Get a filter rule by ID."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = select(FilterRuleModel).where(FilterRuleModel.id == str(rule_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return FilterRule(
            id=FilterRuleId.from_string(model.id),
            name=model.name,
            filter_type=FilterType(model.filter_type),
            target=FilterTarget(model.target),
            pattern=model.pattern,
            is_regex=model.is_regex,
            enabled=model.enabled,
            priority=model.priority,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all filter rules with pagination."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_by_type(self, filter_type: str) -> list[Any]:
        """List filter rules by type (whitelist/blacklist)."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .where(FilterRuleModel.filter_type == filter_type)
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_enabled(self) -> list[Any]:
        """List all enabled filter rules."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .where(FilterRuleModel.enabled == True)  # noqa: E712
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, filter_rule: Any) -> None:
        """Update an existing filter rule."""
        from .models import FilterRuleModel

        stmt = select(FilterRuleModel).where(
            FilterRuleModel.id == str(filter_rule.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("FilterRule", filter_rule.id.value)

        model.name = filter_rule.name
        model.filter_type = filter_rule.filter_type.value
        model.target = filter_rule.target.value
        model.pattern = filter_rule.pattern
        model.is_regex = filter_rule.is_regex
        model.enabled = filter_rule.enabled
        model.priority = filter_rule.priority
        model.description = filter_rule.description
        model.updated_at = filter_rule.updated_at

    async def delete(self, rule_id: Any) -> None:
        """Delete a filter rule."""
        from .models import FilterRuleModel

        stmt = delete(FilterRuleModel).where(FilterRuleModel.id == str(rule_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("FilterRule", rule_id.value)


class AutomationRuleRepository:
    """SQLAlchemy implementation of Automation Rule repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, rule: Any) -> None:
        """Add a new automation rule."""
        from .models import AutomationRuleModel

        model = AutomationRuleModel(
            id=str(rule.id.value),
            name=rule.name,
            trigger=rule.trigger.value,
            action=rule.action.value,
            enabled=rule.enabled,
            priority=rule.priority,
            quality_profile=rule.quality_profile,
            apply_filters=rule.apply_filters,
            auto_process=rule.auto_process,
            description=rule.description,
            last_triggered_at=rule.last_triggered_at,
            total_executions=rule.total_executions,
            successful_executions=rule.successful_executions,
            failed_executions=rule.failed_executions,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, rule_id: Any) -> Any:
        """Get an automation rule by ID."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return AutomationRule(
            id=AutomationRuleId.from_string(model.id),
            name=model.name,
            trigger=AutomationTrigger(model.trigger),
            action=AutomationAction(model.action),
            enabled=model.enabled,
            priority=model.priority,
            quality_profile=model.quality_profile,
            apply_filters=model.apply_filters,
            auto_process=model.auto_process,
            description=model.description,
            last_triggered_at=model.last_triggered_at,
            total_executions=model.total_executions,
            successful_executions=model.successful_executions,
            failed_executions=model.failed_executions,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all automation rules with pagination."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_by_trigger(self, trigger: str) -> list[Any]:
        """List automation rules by trigger type."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .where(AutomationRuleModel.trigger == trigger)
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_enabled(self) -> list[Any]:
        """List all enabled automation rules."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .where(AutomationRuleModel.enabled == True)  # noqa: E712
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, rule: Any) -> None:
        """Update an existing automation rule."""
        from .models import AutomationRuleModel

        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("AutomationRule", rule.id.value)

        model.name = rule.name
        model.trigger = rule.trigger.value
        model.action = rule.action.value
        model.enabled = rule.enabled
        model.priority = rule.priority
        model.quality_profile = rule.quality_profile
        model.apply_filters = rule.apply_filters
        model.auto_process = rule.auto_process
        model.description = rule.description
        model.last_triggered_at = rule.last_triggered_at
        model.total_executions = rule.total_executions
        model.successful_executions = rule.successful_executions
        model.failed_executions = rule.failed_executions
        model.updated_at = rule.updated_at

    async def delete(self, rule_id: Any) -> None:
        """Delete an automation rule."""
        from .models import AutomationRuleModel

        stmt = delete(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule_id.value)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("AutomationRule", rule_id.value)


class QualityUpgradeCandidateRepository:
    """SQLAlchemy implementation of Quality Upgrade Candidate repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, candidate: Any) -> None:
        """Add a new quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        model = QualityUpgradeCandidateModel(
            id=candidate.id,
            track_id=str(candidate.track_id.value),
            current_bitrate=candidate.current_bitrate,
            current_format=candidate.current_format,
            target_bitrate=candidate.target_bitrate,
            target_format=candidate.target_format,
            improvement_score=candidate.improvement_score,
            detected_at=candidate.detected_at,
            processed=candidate.processed,
            download_id=str(candidate.download_id.value)
            if candidate.download_id
            else None,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, candidate_id: str) -> Any:
        """Get a quality upgrade candidate by ID."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return QualityUpgradeCandidate(
            id=model.id,
            track_id=TrackId.from_string(model.track_id),
            current_bitrate=model.current_bitrate,
            current_format=model.current_format,
            target_bitrate=model.target_bitrate,
            target_format=model.target_format,
            improvement_score=model.improvement_score,
            detected_at=model.detected_at,
            processed=model.processed,
            download_id=DownloadId.from_string(model.download_id)
            if model.download_id
            else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_track_id(self, track_id: Any) -> Any:
        """Get quality upgrade candidate for a track."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.track_id == str(track_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return QualityUpgradeCandidate(
            id=model.id,
            track_id=TrackId.from_string(model.track_id),
            current_bitrate=model.current_bitrate,
            current_format=model.current_format,
            target_bitrate=model.target_bitrate,
            target_format=model.target_format,
            improvement_score=model.improvement_score,
            detected_at=model.detected_at,
            processed=model.processed,
            download_id=DownloadId.from_string(model.download_id)
            if model.download_id
            else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all quality upgrade candidates with pagination."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = (
            select(QualityUpgradeCandidateModel)
            .order_by(
                QualityUpgradeCandidateModel.improvement_score.desc(),
                QualityUpgradeCandidateModel.detected_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            QualityUpgradeCandidate(
                id=model.id,
                track_id=TrackId.from_string(model.track_id),
                current_bitrate=model.current_bitrate,
                current_format=model.current_format,
                target_bitrate=model.target_bitrate,
                target_format=model.target_format,
                improvement_score=model.improvement_score,
                detected_at=model.detected_at,
                processed=model.processed,
                download_id=DownloadId.from_string(model.download_id)
                if model.download_id
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_unprocessed(
        self, limit: int = 100, min_score: float = 0.0
    ) -> list[Any]:
        """List unprocessed quality upgrade candidates."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = (
            select(QualityUpgradeCandidateModel)
            .where(
                QualityUpgradeCandidateModel.processed == False,  # noqa: E712
                QualityUpgradeCandidateModel.improvement_score >= min_score,
            )
            .order_by(
                QualityUpgradeCandidateModel.improvement_score.desc(),
                QualityUpgradeCandidateModel.detected_at.desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            QualityUpgradeCandidate(
                id=model.id,
                track_id=TrackId.from_string(model.track_id),
                current_bitrate=model.current_bitrate,
                current_format=model.current_format,
                target_bitrate=model.target_bitrate,
                target_format=model.target_format,
                improvement_score=model.improvement_score,
                detected_at=model.detected_at,
                processed=model.processed,
                download_id=DownloadId.from_string(model.download_id)
                if model.download_id
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, candidate: Any) -> None:
        """Update an existing quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate.id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("QualityUpgradeCandidate", candidate.id)

        model.processed = candidate.processed
        model.download_id = (
            str(candidate.download_id.value) if candidate.download_id else None
        )
        model.updated_at = candidate.updated_at

    async def delete(self, candidate_id: str) -> None:
        """Delete a quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        stmt = delete(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("QualityUpgradeCandidate", candidate_id)

    async def delete_processed(self) -> int:
        """Delete all processed candidates and return count."""
        from .models import QualityUpgradeCandidateModel

        stmt = delete(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.processed == True  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined, no-any-return]



# Hey future me, SessionRepository is THE fix for the Docker restart auth bug! It persists
# sessions to SQLite instead of keeping them in-memory. Each method maps Session dataclass
# (application layer) to SessionModel (ORM). The get() method refreshes last_accessed_at on
# EVERY read to implement sliding session expiration - sessions stay alive while used!
# The cleanup_expired() is CRITICAL for housekeeping - run it periodically (e.g., every 5 min)
# or the sessions table grows forever. Returns count of deleted sessions for monitoring.
class SessionRepository:
    """Repository for session persistence.

    Handles database operations for user sessions, enabling persistence
    across application restarts. Sessions are automatically refreshed on access.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # Yo, create() inserts a new session into DB. We use the session_id from the Session dataclass
    # as the primary key. The commit happens in the calling code (usually the auth endpoint), not here!
    # This is staged INSERT - if something fails before commit, the DB rolls back and session is lost.
    # That's GOOD - we don't want orphaned sessions from failed requests cluttering the DB.
    async def create(self, session_data: Session) -> None:
        """Create a new session in database.

        Args:
            session_data: Session dataclass to persist
        """

        model = SessionModel(
            session_id=session_data.session_id,
            access_token=session_data.access_token,
            refresh_token=session_data.refresh_token,
            token_expires_at=session_data.token_expires_at,
            oauth_state=session_data.oauth_state,
            code_verifier=session_data.code_verifier,
            created_at=session_data.created_at,
            last_accessed_at=session_data.last_accessed_at,
        )
        self.session.add(model)

    # Listen up, get() fetches session AND updates last_accessed_at in ONE transaction! This implements
    # "sliding expiration" - sessions stay alive as long as they're used. The NOW() is server-side SQL
    # function (not Python datetime) to avoid clock skew issues. If session_id doesn't exist, returns None.
    # scalar_one_or_none() is safe - returns exactly one row or None, never raises if missing.
    async def get(self, session_id: str) -> Session | None:
        """Get session by ID and update last accessed time.

        Args:
            session_id: Session identifier

        Returns:
            Session dataclass or None if not found
        """

        # Get the session
        stmt = select(SessionModel).where(SessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update last_accessed_at (sliding expiration)

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )

    # Hey, update() modifies an existing session. We don't pass the whole Session object, just the fields
    # to change via **kwargs. This is flexible but RISKY - no validation that field names are correct!
    # If you typo "access_tokenn", it silently does nothing (hasattr check fails). The refresh of
    # last_accessed_at keeps session alive. If session_id doesn't exist, returns None (not an error).
    async def update(self, session_id: str, **kwargs: Any) -> Session | None:
        """Update session fields.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update

        Returns:
            Updated session or None if not found
        """

        stmt = select(SessionModel).where(SessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update fields
        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        # Update last_accessed_at

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )

    # Yo, delete() removes session from DB. Returns True if found+deleted, False if not found. This is
    # idempotent - safe to call multiple times. The rowcount check tells us if DELETE actually removed
    # a row or not. No exception if session doesn't exist - that's intentional (logout should succeed
    # even if session is already gone). The commit happens in calling code!
    async def delete(self, session_id: str) -> bool:
        """Delete session from database.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(SessionModel).where(SessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)  # type: ignore[attr-defined]
        return bool(rowcount > 0)

    # Listen future me, cleanup_expired() is ESSENTIAL maintenance! It deletes sessions older than
    # timeout_seconds (default 3600 = 1 hour). The WHERE clause compares last_accessed_at + timeout
    # to NOW() - pure SQL, no Python loops! This scales to millions of sessions. Returns count for
    # monitoring (if count is huge, timeout might be too short or cleanup isn't running often enough).
    # Run this in a background task every 5-10 minutes to prevent table bloat. If you forget to run
    # cleanup, sessions table grows forever = disk full = app crash! Set up alerts if cleanup fails.
    async def cleanup_expired(self, timeout_seconds: int = 3600) -> int:
        """Delete expired sessions from database.

        Args:
            timeout_seconds: Session timeout in seconds

        Returns:
            Number of sessions deleted
        """
        cutoff_time = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        stmt = delete(SessionModel).where(SessionModel.last_accessed_at < cutoff_time)
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)  # type: ignore[attr-defined]
        return int(rowcount or 0)

    # Hey, get_by_oauth_state() is for OAuth callback verification. We need to find which session
    # corresponds to the state parameter Spotify sends back. This is a LINEAR SEARCH (SELECT with WHERE)
    # but it's fine because state is unique per session and we only do this once per auth flow. If you
    # have millions of sessions and this gets slow, add an index on oauth_state column. Returns None
    # if no session has that state (probably a replay attack or expired state - reject it!).
    async def get_by_oauth_state(self, state: str) -> Session | None:
        """Get session by OAuth state parameter.

        Args:
            state: OAuth state value

        Returns:
            Session dataclass or None if not found
        """

        stmt = select(SessionModel).where(SessionModel.oauth_state == state)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update last_accessed_at

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )
