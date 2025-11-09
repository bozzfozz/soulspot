"""Domain ports (interfaces) for dependency inversion."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from soulspot.domain.entities import Album, Artist, Download, Playlist, Track
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    DownloadId,
    PlaylistId,
    TrackId,
)


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
    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Artist | None:
        """Get an artist by MusicBrainz ID."""
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
    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Album | None:
        """Get an album by MusicBrainz ID."""
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
    async def get_by_spotify_uri(self, spotify_uri: Any) -> Track | None:
        """Get a track by Spotify URI."""
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
    async def get_by_spotify_uri(self, spotify_uri: Any) -> Playlist | None:
        """Get a playlist by Spotify URI."""
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
    async def add_track(self, playlist_id: PlaylistId, track_id: TrackId) -> None:
        """Add a track to a playlist."""
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


# External Integration Ports


class ISlskdClient(ABC):
    """Port for slskd HTTP client operations."""

    @abstractmethod
    async def search(self, query: str, timeout: int = 30) -> list[dict[str, Any]]:
        """
        Search for files on the Soulseek network.

        Args:
            query: Search query string
            timeout: Search timeout in seconds

        Returns:
            List of search results with file information
        """
        pass

    @abstractmethod
    async def download(self, username: str, filename: str) -> str:
        """
        Start a download from a user.

        Args:
            username: Username of the file owner
            filename: Full path to the file to download

        Returns:
            Download ID
        """
        pass

    @abstractmethod
    async def get_download_status(self, download_id: str) -> dict[str, Any]:
        """
        Get the status of a download.

        Args:
            download_id: Download ID

        Returns:
            Download status information
        """
        pass

    @abstractmethod
    async def list_downloads(self) -> list[dict[str, Any]]:
        """
        List all downloads.

        Returns:
            List of downloads with status information
        """
        pass

    @abstractmethod
    async def cancel_download(self, download_id: str) -> None:
        """
        Cancel a download.

        Args:
            download_id: Download ID
        """
        pass


class ISpotifyClient(ABC):
    """Port for Spotify API client operations with OAuth PKCE."""

    @abstractmethod
    async def get_authorization_url(self, state: str, code_verifier: str) -> str:
        """
        Generate Spotify OAuth authorization URL.

        Args:
            state: State parameter for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            Authorization URL
        """
        pass

    @abstractmethod
    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            code_verifier: PKCE code verifier

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Token response with new access_token and expires_in
        """
        pass

    @abstractmethod
    async def get_playlist(self, playlist_id: str, access_token: str) -> dict[str, Any]:
        """
        Get playlist details.

        Args:
            playlist_id: Spotify playlist ID
            access_token: OAuth access token

        Returns:
            Playlist information including tracks
        """
        pass

    @abstractmethod
    async def get_track(self, track_id: str, access_token: str) -> dict[str, Any]:
        """
        Get track details.

        Args:
            track_id: Spotify track ID
            access_token: OAuth access token

        Returns:
            Track information
        """
        pass

    @abstractmethod
    async def search_track(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """
        Search for tracks.

        Args:
            query: Search query
            access_token: OAuth access token
            limit: Maximum number of results

        Returns:
            Search results
        """
        pass


class IMusicBrainzClient(ABC):
    """Port for MusicBrainz API client operations."""

    @abstractmethod
    async def lookup_recording_by_isrc(self, isrc: str) -> dict[str, Any] | None:
        """
        Lookup a recording by ISRC code.

        Args:
            isrc: International Standard Recording Code

        Returns:
            Recording information or None if not found
        """
        pass

    @abstractmethod
    async def search_recording(
        self, artist: str, title: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search for recordings by artist and title.

        Args:
            artist: Artist name
            title: Track title
            limit: Maximum number of results

        Returns:
            List of recording matches
        """
        pass

    @abstractmethod
    async def lookup_release(self, release_id: str) -> dict[str, Any] | None:
        """
        Lookup a release (album) by MusicBrainz ID.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            Release information or None if not found
        """
        pass

    @abstractmethod
    async def lookup_artist(self, artist_id: str) -> dict[str, Any] | None:
        """
        Lookup an artist by MusicBrainz ID.

        Args:
            artist_id: MusicBrainz artist ID

        Returns:
            Artist information or None if not found
        """
        pass
