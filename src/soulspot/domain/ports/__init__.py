"""Domain ports (interfaces) for dependency inversion."""

from abc import ABC, abstractmethod
from typing import Optional

from soulspot.domain.entities import Album, Artist, Download, Playlist, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, DownloadId, PlaylistId, TrackId


class IArtistRepository(ABC):
    """Repository interface for Artist entities."""

    @abstractmethod
    async def add(self, artist: Artist) -> None:
        """Add a new artist."""
        pass

    @abstractmethod
    async def get_by_id(self, artist_id: ArtistId) -> Artist | None:
        """Get an artist by ID."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Artist | None:
        """Get an artist by name."""
        pass

    @abstractmethod
    async def update(self, artist: Artist) -> None:
        """Update an existing artist."""
        pass

    @abstractmethod
    async def delete(self, artist_id: ArtistId) -> None:
        """Delete an artist."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        """List all artists with pagination."""
        pass


class IAlbumRepository(ABC):
    """Repository interface for Album entities."""

    @abstractmethod
    async def add(self, album: Album) -> None:
        """Add a new album."""
        pass

    @abstractmethod
    async def get_by_id(self, album_id: AlbumId) -> Album | None:
        """Get an album by ID."""
        pass

    @abstractmethod
    async def get_by_artist(self, artist_id: ArtistId) -> list[Album]:
        """Get all albums by an artist."""
        pass

    @abstractmethod
    async def update(self, album: Album) -> None:
        """Update an existing album."""
        pass

    @abstractmethod
    async def delete(self, album_id: AlbumId) -> None:
        """Delete an album."""
        pass


class ITrackRepository(ABC):
    """Repository interface for Track entities."""

    @abstractmethod
    async def add(self, track: Track) -> None:
        """Add a new track."""
        pass

    @abstractmethod
    async def get_by_id(self, track_id: TrackId) -> Track | None:
        """Get a track by ID."""
        pass

    @abstractmethod
    async def get_by_album(self, album_id: AlbumId) -> list[Track]:
        """Get all tracks in an album."""
        pass

    @abstractmethod
    async def get_by_artist(self, artist_id: ArtistId) -> list[Track]:
        """Get all tracks by an artist."""
        pass

    @abstractmethod
    async def update(self, track: Track) -> None:
        """Update an existing track."""
        pass

    @abstractmethod
    async def delete(self, track_id: TrackId) -> None:
        """Delete a track."""
        pass


class IPlaylistRepository(ABC):
    """Repository interface for Playlist entities."""

    @abstractmethod
    async def add(self, playlist: Playlist) -> None:
        """Add a new playlist."""
        pass

    @abstractmethod
    async def get_by_id(self, playlist_id: PlaylistId) -> Playlist | None:
        """Get a playlist by ID."""
        pass

    @abstractmethod
    async def update(self, playlist: Playlist) -> None:
        """Update an existing playlist."""
        pass

    @abstractmethod
    async def delete(self, playlist_id: PlaylistId) -> None:
        """Delete a playlist."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Playlist]:
        """List all playlists with pagination."""
        pass


class IDownloadRepository(ABC):
    """Repository interface for Download entities."""

    @abstractmethod
    async def add(self, download: Download) -> None:
        """Add a new download."""
        pass

    @abstractmethod
    async def get_by_id(self, download_id: DownloadId) -> Download | None:
        """Get a download by ID."""
        pass

    @abstractmethod
    async def get_by_track(self, track_id: TrackId) -> Download | None:
        """Get a download by track ID."""
        pass

    @abstractmethod
    async def update(self, download: Download) -> None:
        """Update an existing download."""
        pass

    @abstractmethod
    async def delete(self, download_id: DownloadId) -> None:
        """Delete a download."""
        pass

    @abstractmethod
    async def list_active(self) -> list[Download]:
        """List all active downloads (not finished)."""
        pass
