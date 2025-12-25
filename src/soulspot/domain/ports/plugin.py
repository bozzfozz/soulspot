"""
Music Service Plugin Interface for SoulSpot.

Hey future me – das ist das HERZSTÜCK der Plugin-Architektur!
Jeder Music Service (Spotify, Deezer, Tidal) implementiert dieses Interface.
Die Methoden geben IMMER Standard-DTOs zurück – NIE rohes JSON!

Warum ein gemeinsames Interface?
1. Application Services können beliebige Plugins nutzen (Dependency Injection)
2. Neue Services hinzufügen = nur neues Plugin schreiben
3. Einheitliches Error-Handling über PluginError
4. Testing: Mock-Plugins für Unit-Tests

Implementierungs-Checkliste für neue Plugins:
1. Implementiere IMusicServicePlugin
2. Konvertiere API-Responses zu DTOs (NICHT im Application Layer!)
3. Handle OAuth wenn nötig (get_auth_url, handle_callback)
4. Registriere Plugin im Plugin-Registry
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from soulspot.domain.dtos import (
    AlbumDTO,
    ArtistDTO,
    PaginatedResponse,
    PlaylistDTO,
    SearchResultDTO,
    TrackDTO,
    UserProfileDTO,
)


class ServiceType(str, Enum):
    """
    Supported music service types.

    Hey future me – jeder neue Service braucht einen Enum-Wert hier!
    Das hilft bei Type-Safety und UI-Dropdowns.
    """

    SPOTIFY = "spotify"
    DEEZER = "deezer"
    TIDAL = "tidal"
    MUSICBRAINZ = "musicbrainz"  # Metadata-only, no streaming


class AuthType(str, Enum):
    """
    Authentication types supported by plugins.

    Hey future me – nicht alle Services brauchen OAuth!
    - NONE: Public API ohne Auth (MusicBrainz)
    - API_KEY: Einfacher API-Key (Deezer public endpoints)
    - OAUTH_PKCE: Modern OAuth 2.0 mit PKCE (Spotify, Tidal)
    - OAUTH_IMPLICIT: Legacy OAuth (vermeiden wenn möglich)
    """

    NONE = "none"
    API_KEY = "api_key"
    OAUTH_PKCE = "oauth_pkce"
    OAUTH_IMPLICIT = "oauth_implicit"


class PluginCapability(str, Enum):
    """
    Feature capabilities that plugins can support.

    Hey future me - das ist die zentrale Liste aller Features!
    Plugins geben an welche Features sie supporten und ob Auth nötig ist.

    PUBLIC = Feature funktioniert ohne Auth
    AUTH_REQUIRED = Feature braucht OAuth Token
    """

    # Search capabilities (usually public)
    SEARCH_ARTISTS = "search_artists"
    SEARCH_ALBUMS = "search_albums"
    SEARCH_TRACKS = "search_tracks"
    SEARCH_PLAYLISTS = "search_playlists"

    # Browse capabilities (usually public)
    BROWSE_NEW_RELEASES = "browse_new_releases"
    BROWSE_FEATURED = "browse_featured"
    BROWSE_GENRES = "browse_genres"
    BROWSE_CHARTS = "browse_charts"

    # Entity lookup (usually public)
    GET_ARTIST = "get_artist"
    GET_ALBUM = "get_album"
    GET_TRACK = "get_track"
    GET_PLAYLIST = "get_playlist"
    GET_ARTIST_ALBUMS = "get_artist_albums"
    GET_ARTIST_TOP_TRACKS = "get_artist_top_tracks"
    GET_RELATED_ARTISTS = "get_related_artists"

    # User library (always requires auth)
    USER_PROFILE = "user_profile"
    USER_FOLLOWED_ARTISTS = "user_followed_artists"
    USER_SAVED_TRACKS = "user_saved_tracks"
    USER_SAVED_ALBUMS = "user_saved_albums"
    USER_PLAYLISTS = "user_playlists"

    # Actions (always requires auth)
    FOLLOW_ARTIST = "follow_artist"
    UNFOLLOW_ARTIST = "unfollow_artist"
    SAVE_TRACK = "save_track"
    REMOVE_TRACK = "remove_track"


@dataclass
class CapabilityInfo:
    """Information about a plugin capability."""

    capability: PluginCapability
    requires_auth: bool
    description: str | None = None


# Hey future me – PluginError ist die EINHEITLICHE Exception für alle Plugin-Fehler!
# Wrap service-spezifische Exceptions (SpotifyAPIError, etc.) in PluginError.
# Das ermöglicht einheitliches Error-Handling im Application Layer.
@dataclass
class PluginError(Exception):
    """
    Unified error class for all plugin operations.

    All service-specific exceptions should be wrapped in PluginError.
    """

    message: str
    service: ServiceType
    error_code: str | None = None  # Service-specific error code
    original_error: Exception | None = None  # Wrapped original exception
    recoverable: bool = False  # Can the operation be retried?

    def __str__(self) -> str:
        """Return human-readable error message."""
        base = f"[{self.service.value}] {self.message}"
        if self.error_code:
            base = f"{base} (code: {self.error_code})"
        return base


# Hey future me – AuthStatus zeigt den aktuellen Auth-Zustand eines Plugins!
# Plugins müssen ihren Auth-Status tracken und bei get_auth_status() zurückgeben.
@dataclass
class AuthStatus:
    """
    Authentication status for a plugin.
    """

    is_authenticated: bool
    service: ServiceType
    user_id: str | None = None  # Service-specific user ID
    display_name: str | None = None  # User's display name
    expires_at: int | None = None  # Token expiry timestamp (Unix)
    scopes: list[str] | None = None  # Granted OAuth scopes


class IMusicServicePlugin(ABC):
    """
    Abstract base class for all music service plugins.

    Hey future me – das ist DAS Interface, das alle Plugins implementieren müssen!
    Jede Methode gibt Standard-DTOs zurück, KEINE rohen API-Responses.

    Implementierungs-Tipps:
    1. __init__ sollte lightweight sein (keine API-Calls)
    2. Lazy-load OAuth tokens (nicht im Constructor)
    3. Handle Rate-Limiting intern (mit Retries + Backoff)
    4. Log Errors, aber raise PluginError nach außen
    """

    @property
    @abstractmethod
    def service_type(self) -> ServiceType:
        """
        Return the service type this plugin handles.

        Returns:
            ServiceType enum value (e.g., ServiceType.SPOTIFY)
        """
        ...

    @property
    @abstractmethod
    def auth_type(self) -> AuthType:
        """
        Return the authentication type required by this plugin.

        Returns:
            AuthType enum value
        """
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for the service.

        Returns:
            Display name (e.g., "Spotify", "Deezer")
        """
        ...

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Quick check if authentication tokens are available.

        Hey future me - this is a FAST synchronous check!
        Unlike get_auth_status(), this doesn't validate the token with the service.
        Token might be expired, but this tells you if auth was ever done.

        Use this for:
        - Pre-flight checks before starting operations
        - Deciding whether to show "connect" vs "disconnect" buttons
        - Quick auth state checks in UI

        Don't use this for:
        - Verifying token validity (use get_auth_status())
        - Knowing token expiry time

        Returns:
            True if an access token is set, False otherwise
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> list[CapabilityInfo]:
        """
        Get list of capabilities this plugin supports with auth requirements.

        Hey future me - das ist DER Weg zu wissen was funktioniert!
        Jedes Plugin gibt seine unterstützten Features zurück und ob Auth nötig ist.

        Beispiel Rückgabe:
        [
            CapabilityInfo(SEARCH_ARTISTS, requires_auth=False),
            CapabilityInfo(USER_FOLLOWED_ARTISTS, requires_auth=True),
        ]

        Use this for:
        - UI: Show/hide features based on auth status
        - Routes: Gracefully skip unavailable features
        - Aggregation: Know which service can contribute what

        Returns:
            List of CapabilityInfo with auth requirements
        """
        ...

    def can_use(self, capability: PluginCapability) -> bool:
        """
        Check if a capability can be used right now.

        Considers both:
        1. Does the plugin support this capability?
        2. If it requires auth, is the plugin authenticated?

        Args:
            capability: The capability to check

        Returns:
            True if the capability can be used, False otherwise
        """
        for cap_info in self.get_capabilities():
            if cap_info.capability == capability:
                if cap_info.requires_auth:
                    return self.is_authenticated
                return True
        return False

    # =========================================================================
    # AUTHENTICATION METHODS
    # =========================================================================

    @abstractmethod
    async def get_auth_url(self, state: str | None = None) -> str:
        """
        Get the OAuth authorization URL for user login.

        Hey future me – state ist für CSRF-Protection!
        Speichere den state-Wert und verifiziere ihn im Callback.

        Args:
            state: Optional CSRF protection state

        Returns:
            Full authorization URL to redirect user to

        Raises:
            PluginError: If auth URL cannot be generated
        """
        ...

    @abstractmethod
    async def handle_callback(self, code: str, state: str | None = None) -> AuthStatus:
        """
        Handle OAuth callback and exchange code for tokens.

        Hey future me – das ist der zweite Teil des OAuth-Flows!
        Nach User-Login kommt Callback mit code → exchange für tokens.

        Args:
            code: Authorization code from callback
            state: State parameter for verification

        Returns:
            AuthStatus with authentication details

        Raises:
            PluginError: If token exchange fails
        """
        ...

    @abstractmethod
    async def get_auth_status(self) -> AuthStatus:
        """
        Get current authentication status.

        Returns:
            Current AuthStatus

        Raises:
            PluginError: If status cannot be determined
        """
        ...

    @abstractmethod
    async def logout(self) -> None:
        """
        Clear authentication tokens and logout user.

        Hey future me – das löscht lokale Tokens, nicht die Spotify-Session!
        User muss sich bei Spotify selbst ausloggen wenn gewünscht.

        Raises:
            PluginError: If logout fails
        """
        ...

    # =========================================================================
    # USER PROFILE
    # =========================================================================

    @abstractmethod
    async def get_current_user(self) -> UserProfileDTO:
        """
        Get the current authenticated user's profile.

        Returns:
            UserProfileDTO with user information

        Raises:
            PluginError: If not authenticated or request fails
        """
        ...

    # =========================================================================
    # SEARCH
    # =========================================================================

    @abstractmethod
    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResultDTO:
        """
        Search for artists, albums, tracks, and playlists.

        Hey future me – types filtert Ergebnis-Typen!
        None = alles suchen, ["track", "artist"] = nur Tracks und Artists.

        Args:
            query: Search query string
            types: List of types to search ("artist", "album", "track", "playlist")
            limit: Maximum results per type (max 50)
            offset: Pagination offset

        Returns:
            SearchResultDTO with results

        Raises:
            PluginError: If search fails
        """
        ...

    # =========================================================================
    # ARTISTS
    # =========================================================================

    @abstractmethod
    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """
        Get an artist by service-specific ID.

        Args:
            artist_id: Service-specific artist ID

        Returns:
            ArtistDTO with artist information

        Raises:
            PluginError: If artist not found or request fails
        """
        ...

    @abstractmethod
    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[AlbumDTO]:
        """
        Get an artist's albums.

        Hey future me – include_groups filtert Album-Typen!
        ["album", "single"] = nur Studioalben und Singles
        ["compilation", "appears_on"] = Compilations und Features

        Args:
            artist_id: Service-specific artist ID
            include_groups: Filter by album type ("album", "single", "compilation", "appears_on")
            limit: Maximum results (max 50)
            offset: Pagination offset

        Returns:
            PaginatedResponse of AlbumDTOs

        Raises:
            PluginError: If request fails
        """
        ...

    @abstractmethod
    async def get_artist_top_tracks(
        self, artist_id: str, market: str | None = None
    ) -> list[TrackDTO]:
        """
        Get an artist's top tracks.

        Args:
            artist_id: Service-specific artist ID
            market: ISO 3166-1 alpha-2 country code (e.g., "US", "DE")

        Returns:
            List of top TrackDTOs (usually 10)

        Raises:
            PluginError: If request fails
        """
        ...

    @abstractmethod
    async def get_followed_artists(
        self, limit: int = 50, after: str | None = None
    ) -> PaginatedResponse[ArtistDTO]:
        """
        Get artists followed by the current user.

        Hey future me – Spotify nutzt Cursor-Pagination (after), nicht Offset!
        after ist die letzte artist_id der vorherigen Seite.

        Args:
            limit: Maximum results (max 50)
            after: Cursor for pagination (last artist ID)

        Returns:
            PaginatedResponse of ArtistDTOs

        Raises:
            PluginError: If not authenticated or request fails
        """
        ...

    # =========================================================================
    # ALBUMS
    # =========================================================================

    @abstractmethod
    async def get_album(self, album_id: str) -> AlbumDTO:
        """
        Get an album by service-specific ID.

        Args:
            album_id: Service-specific album ID

        Returns:
            AlbumDTO with album information (including tracks)

        Raises:
            PluginError: If album not found or request fails
        """
        ...

    @abstractmethod
    async def get_albums(self, album_ids: list[str]) -> list[AlbumDTO]:
        """
        Get multiple albums by IDs (batch request).

        Hey future me – Spotify erlaubt max 20 IDs pro Request!
        Plugin sollte automatisch chunken wenn nötig.

        Args:
            album_ids: List of service-specific album IDs

        Returns:
            List of AlbumDTOs

        Raises:
            PluginError: If request fails
        """
        ...

    @abstractmethod
    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """
        Get tracks from an album.

        Args:
            album_id: Service-specific album ID
            limit: Maximum results (max 50)
            offset: Pagination offset

        Returns:
            PaginatedResponse of TrackDTOs

        Raises:
            PluginError: If request fails
        """
        ...

    # =========================================================================
    # TRACKS
    # =========================================================================

    @abstractmethod
    async def get_track(self, track_id: str) -> TrackDTO:
        """
        Get a track by service-specific ID.

        Args:
            track_id: Service-specific track ID

        Returns:
            TrackDTO with track information

        Raises:
            PluginError: If track not found or request fails
        """
        ...

    @abstractmethod
    async def get_tracks(self, track_ids: list[str]) -> list[TrackDTO]:
        """
        Get multiple tracks by IDs (batch request).

        Hey future me – Spotify erlaubt max 50 IDs pro Request!
        Plugin sollte automatisch chunken wenn nötig.

        Args:
            track_ids: List of service-specific track IDs

        Returns:
            List of TrackDTOs

        Raises:
            PluginError: If request fails
        """
        ...

    # =========================================================================
    # PLAYLISTS
    # =========================================================================

    @abstractmethod
    async def get_playlist(self, playlist_id: str) -> PlaylistDTO:
        """
        Get a playlist by service-specific ID.

        Args:
            playlist_id: Service-specific playlist ID

        Returns:
            PlaylistDTO with playlist information

        Raises:
            PluginError: If playlist not found or request fails
        """
        ...

    @abstractmethod
    async def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """
        Get tracks from a playlist.

        Args:
            playlist_id: Service-specific playlist ID
            limit: Maximum results (max 100)
            offset: Pagination offset

        Returns:
            PaginatedResponse of TrackDTOs

        Raises:
            PluginError: If request fails
        """
        ...

    @abstractmethod
    async def get_user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[PlaylistDTO]:
        """
        Get playlists owned or followed by the current user.

        Args:
            limit: Maximum results (max 50)
            offset: Pagination offset

        Returns:
            PaginatedResponse of PlaylistDTOs

        Raises:
            PluginError: If not authenticated or request fails
        """
        ...

    # =========================================================================
    # LIBRARY (SAVED ITEMS)
    # =========================================================================

    @abstractmethod
    async def get_saved_tracks(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """
        Get user's saved/liked tracks.

        Args:
            limit: Maximum results (max 50)
            offset: Pagination offset

        Returns:
            PaginatedResponse of TrackDTOs

        Raises:
            PluginError: If not authenticated or request fails
        """
        ...

    @abstractmethod
    async def get_saved_albums(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """
        Get user's saved albums.

        Args:
            limit: Maximum results (max 50)
            offset: Pagination offset

        Returns:
            PaginatedResponse of AlbumDTOs

        Raises:
            PluginError: If not authenticated or request fails
        """
        ...


# Hey future me – IMetadataPlugin ist für Services die NUR Metadaten liefern (kein Streaming)!
# MusicBrainz, Discogs, etc. implementieren das statt IMusicServicePlugin.
class IMetadataPlugin(ABC):
    """
    Interface for metadata-only services (MusicBrainz, Discogs, etc.).

    These plugins provide metadata enrichment, not streaming/playlist features.
    """

    @property
    @abstractmethod
    def service_type(self) -> ServiceType:
        """Return the service type."""
        ...

    @abstractmethod
    async def search_artist(self, name: str, limit: int = 10) -> list[ArtistDTO]:
        """Search for artists by name."""
        ...

    @abstractmethod
    async def search_album(
        self, title: str, artist: str | None = None, limit: int = 10
    ) -> list[AlbumDTO]:
        """Search for albums by title and optionally artist."""
        ...

    @abstractmethod
    async def search_track_by_isrc(self, isrc: str) -> TrackDTO | None:
        """Find a track by ISRC (International Standard Recording Code)."""
        ...

    @abstractmethod
    async def get_artist_by_mbid(self, mbid: str) -> ArtistDTO | None:
        """Get artist by MusicBrainz ID."""
        ...

    @abstractmethod
    async def get_album_by_mbid(self, mbid: str) -> AlbumDTO | None:
        """Get album by MusicBrainz ID."""
        ...


# Export all interfaces and types
__all__ = [
    "ServiceType",
    "AuthType",
    "PluginError",
    "AuthStatus",
    "IMusicServicePlugin",
    "IMetadataPlugin",
]
