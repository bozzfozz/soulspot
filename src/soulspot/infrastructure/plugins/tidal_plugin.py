"""
Tidal Plugin Stub - Future Implementation.

Hey future me – das ist ein STUB für das Tidal Plugin!
Implementiere hier die Tidal API Konvertierung zu SoulSpot DTOs.

Tidal API Besonderheiten:
- OAuth 2.0 mit Device Code Flow (wie Spotify)
- API Key erforderlich (Tidal Developer Account)
- HiFi/Master quality metadata verfügbar
- MQA (Master Quality Authenticated) Tags
- ISRC verfügbar

Implementierungs-Priorität:
1. OAuth Setup (Device Code Flow)
2. get_artist, get_album, get_track
3. search
4. User Library (Favorites)
"""

from soulspot.domain.dtos import (
    AlbumDTO,
    ArtistDTO,
    PaginatedResponse,
    PlaylistDTO,
    SearchResultDTO,
    TrackDTO,
    UserProfileDTO,
)
from soulspot.domain.ports.plugin import (
    AuthStatus,
    AuthType,
    IMusicServicePlugin,
    PluginError,
    ServiceType,
)


class TidalPlugin(IMusicServicePlugin):
    """
    Tidal plugin stub - converts Tidal API data to standard DTOs.

    Hey future me – implementiere hier die Tidal API Integration!
    """

    @property
    def service_type(self) -> ServiceType:
        """Return Tidal service type."""
        return ServiceType.TIDAL

    @property
    def auth_type(self) -> AuthType:
        """Tidal uses OAuth PKCE."""
        return AuthType.OAUTH_PKCE

    @property
    def display_name(self) -> str:
        """Return human-readable service name."""
        return "Tidal"

    # =========================================================================
    # AUTHENTICATION (Stub)
    # =========================================================================

    async def get_auth_url(self, _state: str | None = None) -> str:
        """Get Tidal OAuth URL."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def handle_callback(self, _code: str, _state: str | None = None) -> AuthStatus:
        """Handle OAuth callback."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_auth_status(self) -> AuthStatus:
        """Get auth status."""
        return AuthStatus(
            is_authenticated=False,
            service=ServiceType.TIDAL,
        )

    async def logout(self) -> None:
        """Logout."""
        pass

    # =========================================================================
    # USER PROFILE (Stub)
    # =========================================================================

    async def get_current_user(self) -> UserProfileDTO:
        """Get current user."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # SEARCH (Stub)
    # =========================================================================

    async def search(
        self,
        _query: str,
        _types: list[str] | None = None,
        _limit: int = 20,
        _offset: int = 0,
    ) -> SearchResultDTO:
        """Search Tidal."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # ARTISTS (Stub)
    # =========================================================================

    async def get_artist(self, _artist_id: str) -> ArtistDTO:
        """Get artist by Tidal ID."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_artist_albums(
        self,
        _artist_id: str,
        _include_groups: list[str] | None = None,
        _limit: int = 50,
        _offset: int = 0,
    ) -> PaginatedResponse[AlbumDTO]:
        """Get artist's albums."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_artist_top_tracks(
        self, _artist_id: str, _market: str | None = None
    ) -> list[TrackDTO]:
        """Get artist's top tracks."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_followed_artists(
        self, _limit: int = 50, _after: str | None = None
    ) -> PaginatedResponse[ArtistDTO]:
        """Get followed artists."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # ALBUMS (Stub)
    # =========================================================================

    async def get_album(self, _album_id: str) -> AlbumDTO:
        """Get album by Tidal ID."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_album_tracks(
        self, _album_id: str, _limit: int = 50, _offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get album tracks."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # TRACKS (Stub)
    # =========================================================================

    async def get_track(self, _track_id: str) -> TrackDTO:
        """Get track by Tidal ID."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_tracks(self, _track_ids: list[str]) -> list[TrackDTO]:
        """Get multiple tracks."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # PLAYLISTS (Stub)
    # =========================================================================

    async def get_playlist(self, _playlist_id: str) -> PlaylistDTO:
        """Get playlist by Tidal ID."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_playlist_tracks(
        self, _playlist_id: str, _limit: int = 100, _offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get playlist tracks."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_user_playlists(
        self, _limit: int = 50, _offset: int = 0
    ) -> PaginatedResponse[PlaylistDTO]:
        """Get user playlists."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    # =========================================================================
    # LIBRARY (Stub)
    # =========================================================================

    async def get_saved_tracks(
        self, _limit: int = 50, _offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get saved tracks."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )

    async def get_saved_albums(
        self, _limit: int = 50, _offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """Get saved albums."""
        raise PluginError(
            message="Tidal plugin not implemented yet",
            service=ServiceType.TIDAL,
            error_code="not_implemented",
        )


# Export
__all__ = ["TidalPlugin"]
