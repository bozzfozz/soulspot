"""Repository implementations for domain entities."""

from typing import TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Album, Artist, Download, Playlist, Track
from soulspot.domain.exceptions import EntityNotFoundException
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
    TrackModel,
)

# Type variable for generic repository
T = TypeVar("T")


class ArtistRepository(IArtistRepository):
    """SQLAlchemy implementation of Artist repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, artist: Artist) -> None:
        """Add a new artist."""
        model = ArtistModel(
            id=str(artist.id.value),
            name=artist.name,
            spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
            musicbrainz_id=artist.musicbrainz_id,
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
            raise EntityNotFoundException(f"Artist with id {artist.id.value} not found")

        model.name = artist.name
        model.spotify_uri = str(artist.spotify_uri) if artist.spotify_uri else None
        model.musicbrainz_id = artist.musicbrainz_id
        model.updated_at = artist.updated_at

    async def delete(self, artist_id: ArtistId) -> None:
        """Delete an artist."""
        stmt = delete(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise EntityNotFoundException(f"Artist with id {artist_id.value} not found")

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
            spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
            musicbrainz_id=model.musicbrainz_id,
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
            spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
            musicbrainz_id=model.musicbrainz_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self) -> list[Artist]:
        """List all artists."""
        stmt = select(ArtistModel).order_by(ArtistModel.name)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Artist(
                id=ArtistId.from_string(model.id),
                name=model.name,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
                musicbrainz_id=model.musicbrainz_id,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]


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
            spotify_uri=str(album.spotify_uri) if album.spotify_uri else None,
            musicbrainz_id=album.musicbrainz_id,
            artwork_path=str(album.artwork_path) if album.artwork_path else None,
            created_at=album.created_at,
            updated_at=album.updated_at,
        )
        self.session.add(model)

    async def update(self, album: Album) -> None:
        """Update an existing album."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException(f"Album with id {album.id.value} not found")

        model.title = album.title
        model.artist_id = str(album.artist_id.value)
        model.release_year = album.release_year
        model.spotify_uri = str(album.spotify_uri) if album.spotify_uri else None
        model.musicbrainz_id = album.musicbrainz_id
        model.artwork_path = str(album.artwork_path) if album.artwork_path else None
        model.updated_at = album.updated_at

    async def delete(self, album_id: AlbumId) -> None:
        """Delete an album."""
        stmt = delete(AlbumModel).where(AlbumModel.id == str(album_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise EntityNotFoundException(f"Album with id {album_id.value} not found")

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
            spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_path=FilePath(model.artwork_path) if model.artwork_path else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_artist(self, artist_id: ArtistId) -> list[Album]:
        """List all albums by an artist."""
        stmt = select(AlbumModel).where(AlbumModel.artist_id == str(artist_id.value)).order_by(AlbumModel.release_year)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Album(
                id=AlbumId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                release_year=model.release_year,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
                musicbrainz_id=model.musicbrainz_id,
                artwork_path=FilePath(model.artwork_path) if model.artwork_path else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]


class TrackRepository(ITrackRepository):
    """SQLAlchemy implementation of Track repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, track: Track) -> None:
        """Add a new track."""
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
            raise EntityNotFoundException(f"Track with id {track.id.value} not found")

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
        model.updated_at = track.updated_at

    async def delete(self, track_id: TrackId) -> None:
        """Delete a track."""
        stmt = delete(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise EntityNotFoundException(f"Track with id {track_id.value} not found")

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
            spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath(model.file_path) if model.file_path else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_album(self, album_id: AlbumId) -> list[Track]:
        """List all tracks in an album."""
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
                album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath(model.file_path) if model.file_path else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]


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
            raise EntityNotFoundException(f"Playlist with id {playlist.id.value} not found")

        model.name = playlist.name
        model.description = playlist.description
        model.source = playlist.source.value
        model.spotify_uri = str(playlist.spotify_uri) if playlist.spotify_uri else None
        model.updated_at = playlist.updated_at

        # Update playlist tracks - delete old and add new
        delete_stmt = delete(PlaylistTrackModel).where(PlaylistTrackModel.playlist_id == str(playlist.id.value))
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
        if result.rowcount == 0:
            raise EntityNotFoundException(f"Playlist with id {playlist_id.value} not found")

    async def get_by_id(self, playlist_id: PlaylistId) -> Playlist | None:
        """Get a playlist by ID."""
        stmt = select(PlaylistModel).where(PlaylistModel.id == str(playlist_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get playlist tracks in order
        track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]

        return Playlist(
            id=PlaylistId.from_string(model.id),
            name=model.name,
            description=model.description,
            source=model.source,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
            track_ids=track_ids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self) -> list[Playlist]:
        """List all playlists."""
        stmt = select(PlaylistModel).order_by(PlaylistModel.name)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        playlists = []
        for model in models:
            track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]
            playlists.append(
                Playlist(
                    id=PlaylistId.from_string(model.id),
                    name=model.name,
                    description=model.description,
                    source=model.source,
                    spotify_uri=SpotifyUri.from_string(model.spotify_uri) if model.spotify_uri else None,
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
            raise EntityNotFoundException(f"Download with id {download.id.value} not found")

        model.track_id = str(download.track_id.value)
        model.status = download.status.value
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
        if result.rowcount == 0:
            raise EntityNotFoundException(f"Download with id {download_id.value} not found")

    async def get_by_id(self, download_id: DownloadId) -> Download | None:
        """Get a download by ID."""
        stmt = select(DownloadModel).where(DownloadModel.id == str(download_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=model.status,
            target_path=FilePath(model.target_path) if model.target_path else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_track(self, track_id: TrackId) -> Download | None:
        """Get a download by track ID."""
        stmt = select(DownloadModel).where(DownloadModel.track_id == str(track_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=model.status,
            target_path=FilePath(model.target_path) if model.target_path else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_status(self, status: str) -> list[Download]:
        """List all downloads with a specific status."""
        stmt = select(DownloadModel).where(DownloadModel.status == status).order_by(DownloadModel.created_at)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=model.status,
                target_path=FilePath(model.target_path) if model.target_path else None,
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
