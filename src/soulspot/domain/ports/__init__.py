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


# Hey future me, IArtistRepository is a PORT (Hexagonal Architecture)! It's an INTERFACE (ABC) that
# defines the contract for artist data access. The actual implementation is in infrastructure layer
# (SQLAlchemy repository). Domain layer depends on this interface, not concrete implementation - this
# is DEPENDENCY INVERSION! Use this in service classes: `def __init__(self, artist_repo: IArtistRepository)`
# Tests can mock this easily. If you change this interface, ALL implementations must change too!
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
    async def get_by_spotify_uri(self, spotify_uri: Any) -> Artist | None:
        """Get an artist by Spotify URI."""
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

    @abstractmethod
    async def get_unenriched(self, limit: int = 50) -> list[Artist]:
        """Get artists that have local files but no Spotify enrichment yet.

        Returns artists where:
        - spotify_uri is NULL (not linked to Spotify yet)
        - Artist has at least one track with file_path (local file exists)
        - Artist name is NOT "Various Artists" etc (those can't be enriched)

        Args:
            limit: Maximum number of artists to return

        Returns:
            List of Artist entities needing enrichment
        """
        pass

    @abstractmethod
    async def count_unenriched(self) -> int:
        """Count artists that need enrichment."""
        pass

    @abstractmethod
    async def count_with_spotify_uri(self) -> int:
        """Count artists that have a Spotify URI (synced from Spotify).

        Returns:
            Count of artists with spotify_uri IS NOT NULL
        """
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
    async def get_by_spotify_uri(self, spotify_uri: Any) -> Album | None:
        """Get an album by Spotify URI."""
        pass

    @abstractmethod
    async def update(self, album: Album) -> None:
        """Update an existing album."""
        pass

    @abstractmethod
    async def delete(self, album_id: AlbumId) -> None:
        """Delete an album."""
        pass

    @abstractmethod
    async def get_unenriched(
        self, limit: int = 50, include_compilations: bool = True
    ) -> list[Album]:
        """Get albums that have local files but no Spotify enrichment yet.

        Returns albums where:
        - spotify_uri is NULL (not linked to Spotify yet)
        - Album has at least one track with file_path (local file exists)

        Args:
            limit: Maximum number of albums to return
            include_compilations: If False, exclude compilation albums

        Returns:
            List of Album entities needing enrichment
        """
        pass

    @abstractmethod
    async def count_unenriched(self, include_compilations: bool = True) -> int:
        """Count albums that need enrichment."""
        pass

    @abstractmethod
    async def count_with_spotify_uri(self) -> int:
        """Count albums that have a Spotify URI (synced from Spotify).

        Returns:
            Count of albums with spotify_uri IS NOT NULL
        """
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

    @abstractmethod
    async def get_by_isrc(self, isrc: str) -> Track | None:
        """Get a track by ISRC (International Standard Recording Code).

        ISRC is a globally unique identifier for recordings, making this
        the most reliable way to match downloaded files to tracks.

        Args:
            isrc: ISRC code (e.g., 'USRC11900012')

        Returns:
            Track entity or None if not found
        """
        pass

    @abstractmethod
    async def count_with_spotify_uri(self) -> int:
        """Count tracks that have a Spotify URI (synced from Spotify).

        Returns:
            Count of tracks with spotify_uri IS NOT NULL
        """
        pass

    @abstractmethod
    async def search_by_title_artist(
        self, title: str, artist_name: str | None = None, limit: int = 5
    ) -> list[Track]:
        """Search for tracks by title and optionally artist name.

        Used as fallback when ISRC is not available.

        Args:
            title: Track title to search for
            artist_name: Optional artist name to filter by
            limit: Maximum results to return

        Returns:
            List of matching Track entities
        """
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

    @abstractmethod
    async def count_by_source(self, source: str) -> int:
        """Count playlists by source (e.g., 'spotify', 'manual').

        Args:
            source: Source to filter by (case-insensitive)

        Returns:
            Count of playlists with matching source
        """
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

    @abstractmethod
    async def list_recent(self, limit: int = 5) -> list[Download]:
        """List recently completed or active downloads."""
        pass


# External Integration Ports


# Yo, ISlskdClient is the PORT for slskd integration! It abstracts HTTP client details away from
# domain logic. The domain says "I need to search Soulseek and download files" - it doesn't care if
# it's HTTP, gRPC, or mock client. Implementation is in infrastructure/integrations/slskd_client.py.
# All methods are async because HTTP calls are async. Return types are dict (JSON responses) - could
# be more strongly typed with Pydantic models but we keep it simple. Circuit breaker wraps this!
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


# Listen, ISpotifyClient is the PORT for Spotify OAuth + API! It handles OAuth PKCE flow AND API calls.
# The access_token parameter on most methods is the user's OAuth token (not client credentials). We
# use PKCE (Proof Key for Code Exchange) for security - code_verifier is generated per auth flow. The
# exchange_code and refresh_token methods return token dicts with access_token, refresh_token, expires_in.
# Actual implementation is in infrastructure/integrations/spotify_client.py with circuit breaker!
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
    async def get_user_playlists(
        self, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get current user's playlists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of playlists to return (max 50)
            offset: The index of the first playlist to return

        Returns:
            Paginated list of user's playlists with 'items', 'next', 'total' fields
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

    @abstractmethod
    async def get_followed_artists(
        self, access_token: str, limit: int = 50, after: str | None = None
    ) -> dict[str, Any]:
        """
        Get current user's followed artists.

        Args:
            access_token: OAuth access token
            limit: Maximum number of artists to return (max 50)
            after: The last artist ID retrieved from previous page (for pagination)

        Returns:
            Paginated response with 'artists' containing 'items', 'cursors', and 'total' fields
        """
        pass

    @abstractmethod
    async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
        """
        Get single album by ID.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token

        Returns:
            Album information including tracks, images, etc.
        """
        pass

    @abstractmethod
    async def get_albums(
        self, album_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """
        Batch fetch up to 20 albums by IDs.

        Args:
            album_ids: List of Spotify album IDs (max 20)
            access_token: OAuth access token

        Returns:
            List of album objects (nulls filtered out)
        """
        pass

    @abstractmethod
    async def get_album_tracks(
        self, album_id: str, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        Get album tracks with pagination.

        Args:
            album_id: Spotify album ID
            access_token: OAuth access token
            limit: Maximum number of tracks to return (max 50)
            offset: The index of the first track to return

        Returns:
            Paginated response with tracks
        """
        pass

    @abstractmethod
    async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
        """Get detailed artist information including popularity and followers."""
        pass

    @abstractmethod
    async def get_several_artists(
        self, artist_ids: list[str], access_token: str
    ) -> list[dict[str, Any]]:
        """Get details for multiple artists in a single request (up to 50)."""
        pass

    @abstractmethod
    async def get_artist_albums(
        self, artist_id: str, access_token: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get albums for an artist."""
        pass

    @abstractmethod
    async def get_artist_top_tracks(
        self, artist_id: str, access_token: str, market: str = "US"
    ) -> list[dict[str, Any]]:
        """Get artist's top 10 tracks by popularity."""
        pass

    @abstractmethod
    async def get_related_artists(
        self, artist_id: str, access_token: str
    ) -> list[dict[str, Any]]:
        """Get up to 20 artists similar to the given artist."""
        pass

    @abstractmethod
    async def search_artist(
        self, query: str, access_token: str, limit: int = 20
    ) -> dict[str, Any]:
        """Search for artists on Spotify."""
        pass

    # =========================================================================
    # USER FOLLOWS: FOLLOW/UNFOLLOW ARTISTS
    # =========================================================================
    # Hey future me - these endpoints let users manage their followed artists!
    # - follow_artist: Add artist(s) to user's followed artists (PUT /me/following)
    # - unfollow_artist: Remove artist(s) from followed (DELETE /me/following)
    # - check_if_following: Check if user follows specific artists (GET /me/following/contains)
    # IMPORTANT: Requires "user-follow-modify" scope for PUT/DELETE!
    # =========================================================================

    @abstractmethod
    async def follow_artist(
        self, artist_ids: list[str], access_token: str
    ) -> None:
        """Follow one or more artists on Spotify.

        Args:
            artist_ids: List of Spotify artist IDs to follow (max 50)
            access_token: OAuth access token with user-follow-modify scope

        Raises:
            httpx.HTTPError: If the request fails (403 if missing scope)
        """
        pass

    @abstractmethod
    async def unfollow_artist(
        self, artist_ids: list[str], access_token: str
    ) -> None:
        """Unfollow one or more artists on Spotify.

        Args:
            artist_ids: List of Spotify artist IDs to unfollow (max 50)
            access_token: OAuth access token with user-follow-modify scope

        Raises:
            httpx.HTTPError: If the request fails (403 if missing scope)
        """
        pass

    @abstractmethod
    async def check_if_following_artists(
        self, artist_ids: list[str], access_token: str
    ) -> list[bool]:
        """Check if user follows one or more artists.

        Args:
            artist_ids: List of Spotify artist IDs to check (max 50)
            access_token: OAuth access token with user-follow-read scope

        Returns:
            List of booleans in same order as artist_ids
            (True if following, False if not)

        Raises:
            httpx.HTTPError: If the request fails
        """
        pass


# Hey future me, IMusicBrainzClient is the PORT for MusicBrainz metadata API! MusicBrainz is our
# primary metadata source (free, open, high quality). ISRC (International Standard Recording Code)
# is the best way to match tracks - it's globally unique. The lookup methods return None if not found
# (not exception) - calling code should handle missing data gracefully. MusicBrainz has strict 1 req/sec
# rate limit enforced by circuit breaker! Actual implementation is in infrastructure/integrations/musicbrainz_client.py.
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


# Yo, ILastfmClient is the PORT for Last.fm API! Last.fm is OPTIONAL (check lastfm.is_configured()
# before using). It provides genre tags and popularity data. mbid parameter is MusicBrainz ID for
# more accurate matching. All methods return None if not found or if Last.fm is not configured. The
# actual implementation checks is_configured() and returns None early if credentials are missing. Useful
# for enriching metadata beyond what MusicBrainz provides!
class ILastfmClient(ABC):
    """Port for Last.fm API client operations."""

    @abstractmethod
    async def get_track_info(
        self, artist: str, track: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get track information including tags.

        Args:
            artist: Artist name
            track: Track title
            mbid: Optional MusicBrainz ID

        Returns:
            Track information or None if not found
        """
        pass

    @abstractmethod
    async def get_artist_info(
        self, artist: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get artist information including tags.

        Args:
            artist: Artist name
            mbid: Optional MusicBrainz ID

        Returns:
            Artist information or None if not found
        """
        pass

    @abstractmethod
    async def get_album_info(
        self, artist: str, album: str, mbid: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get album information including tags.

        Args:
            artist: Artist name
            album: Album title
            mbid: Optional MusicBrainz ID

        Returns:
            Album information or None if not found
        """
        pass


class IArtistWatchlistRepository(ABC):
    """Repository interface for ArtistWatchlist entities."""

    @abstractmethod
    async def add(self, watchlist: Any) -> None:
        """Add a new watchlist."""
        pass

    @abstractmethod
    async def get_by_id(self, watchlist_id: Any) -> Any:
        """Get a watchlist by ID."""
        pass

    @abstractmethod
    async def get_by_artist_id(self, artist_id: ArtistId) -> Any:
        """Get watchlist for an artist."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all watchlists with pagination."""
        pass

    @abstractmethod
    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List active watchlists."""
        pass

    @abstractmethod
    async def list_due_for_check(self, limit: int = 100) -> list[Any]:
        """List watchlists that are due for checking."""
        pass

    @abstractmethod
    async def update(self, watchlist: Any) -> None:
        """Update an existing watchlist."""
        pass

    @abstractmethod
    async def delete(self, watchlist_id: Any) -> None:
        """Delete a watchlist."""
        pass


class IFilterRuleRepository(ABC):
    """Repository interface for FilterRule entities."""

    @abstractmethod
    async def add(self, filter_rule: Any) -> None:
        """Add a new filter rule."""
        pass

    @abstractmethod
    async def get_by_id(self, rule_id: Any) -> Any:
        """Get a filter rule by ID."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all filter rules with pagination."""
        pass

    @abstractmethod
    async def list_by_type(self, filter_type: str) -> list[Any]:
        """List filter rules by type (whitelist/blacklist)."""
        pass

    @abstractmethod
    async def list_enabled(self) -> list[Any]:
        """List all enabled filter rules."""
        pass

    @abstractmethod
    async def update(self, filter_rule: Any) -> None:
        """Update an existing filter rule."""
        pass

    @abstractmethod
    async def delete(self, rule_id: Any) -> None:
        """Delete a filter rule."""
        pass


class IAutomationRuleRepository(ABC):
    """Repository interface for AutomationRule entities."""

    @abstractmethod
    async def add(self, rule: Any) -> None:
        """Add a new automation rule."""
        pass

    @abstractmethod
    async def get_by_id(self, rule_id: Any) -> Any:
        """Get an automation rule by ID."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all automation rules with pagination."""
        pass

    @abstractmethod
    async def list_by_trigger(self, trigger: str) -> list[Any]:
        """List automation rules by trigger type."""
        pass

    @abstractmethod
    async def list_enabled(self) -> list[Any]:
        """List all enabled automation rules."""
        pass

    @abstractmethod
    async def update(self, rule: Any) -> None:
        """Update an existing automation rule."""
        pass

    @abstractmethod
    async def delete(self, rule_id: Any) -> None:
        """Delete an automation rule."""
        pass


class IQualityUpgradeCandidateRepository(ABC):
    """Repository interface for QualityUpgradeCandidate entities."""

    @abstractmethod
    async def add(self, candidate: Any) -> None:
        """Add a new quality upgrade candidate."""
        pass

    @abstractmethod
    async def get_by_id(self, candidate_id: str) -> Any:
        """Get a candidate by ID."""
        pass

    @abstractmethod
    async def get_by_track_id(self, track_id: TrackId) -> Any:
        """Get upgrade candidate for a track."""
        pass

    @abstractmethod
    async def list_unprocessed(self, limit: int = 100) -> list[Any]:
        """List unprocessed upgrade candidates."""
        pass

    @abstractmethod
    async def list_by_improvement_score(
        self, min_score: float, limit: int = 100
    ) -> list[Any]:
        """List candidates by minimum improvement score."""
        pass

    @abstractmethod
    async def update(self, candidate: Any) -> None:
        """Update an existing candidate."""
        pass

    @abstractmethod
    async def delete(self, candidate_id: str) -> None:
        """Delete a candidate."""
        pass
