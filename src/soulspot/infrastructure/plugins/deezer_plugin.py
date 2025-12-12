"""
Deezer Plugin Stub - Future Implementation.

Hey future me – das ist ein STUB für das Deezer Plugin!
Implementiere hier die Deezer API Konvertierung zu SoulSpot DTOs.

Deezer API Besonderheiten:
- Public API ohne OAuth für Metadaten (BASIC mode)
- OAuth für User-Library Zugriff (PRO mode)
- Rate Limit: ~50 requests/5 seconds
- ISRC verfügbar bei Tracks (gut für Cross-Service Matching!)
- Kostenlos, keine Premium-Einschränkungen

Implementierungs-Priorität:
1. get_artist, get_album, get_track (Metadaten)
2. search (für Discovery)
3. OAuth für User-Playlists (wenn benötigt)
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


class DeezerPlugin(IMusicServicePlugin):
    """
    Deezer plugin stub - converts Deezer API data to standard DTOs.

    Hey future me – implementiere hier die Deezer API Integration!
    """

    @property
    def service_type(self) -> ServiceType:
        """Return Deezer service type."""
        return ServiceType.DEEZER

    @property
    def auth_type(self) -> AuthType:
        """Deezer can work without auth (public API)."""
        return AuthType.API_KEY

    @property
    def display_name(self) -> str:
        """Return human-readable service name."""
        return "Deezer"

    # =========================================================================
    # AUTHENTICATION (Stub)
    # =========================================================================

    async def get_auth_url(self, state: str | None = None) -> str:
        """Get Deezer OAuth URL (for PRO mode)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def handle_callback(self, code: str, state: str | None = None) -> AuthStatus:
        """Handle OAuth callback."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_auth_status(self) -> AuthStatus:
        """Get auth status."""
        return AuthStatus(
            is_authenticated=False,
            service=ServiceType.DEEZER,
        )

    async def logout(self) -> None:
        """Logout (no-op for public API)."""
        pass

    # =========================================================================
    # USER PROFILE (Stub)
    # =========================================================================

    async def get_current_user(self) -> UserProfileDTO:
        """Get current user (requires OAuth)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # SEARCH (Stub)
    # =========================================================================

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResultDTO:
        """Search Deezer."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # ARTISTS (Stub)
    # =========================================================================

    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Get artist by Deezer ID."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[AlbumDTO]:
        """Get artist's albums."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_artist_top_tracks(
        self, artist_id: str, market: str | None = None
    ) -> list[TrackDTO]:
        """Get artist's top tracks."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_followed_artists(
        self, limit: int = 50, after: str | None = None
    ) -> PaginatedResponse[ArtistDTO]:
        """Get followed artists (requires OAuth)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # ALBUMS (Stub)
    # =========================================================================

    async def get_album(self, album_id: str) -> AlbumDTO:
        """Get album by Deezer ID."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get album tracks."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # TRACKS (Stub)
    # =========================================================================

    async def get_track(self, track_id: str) -> TrackDTO:
        """Get track by Deezer ID."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_tracks(self, track_ids: list[str]) -> list[TrackDTO]:
        """Get multiple tracks."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # PLAYLISTS (Stub)
    # =========================================================================

    async def get_playlist(self, playlist_id: str) -> PlaylistDTO:
        """Get playlist by Deezer ID."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get playlist tracks."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[PlaylistDTO]:
        """Get user playlists (requires OAuth)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    # =========================================================================
    # LIBRARY (Stub)
    # =========================================================================

    async def get_saved_tracks(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get saved tracks (requires OAuth)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )

    async def get_saved_albums(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """Get saved albums (requires OAuth)."""
        raise PluginError(
            message="Deezer plugin not implemented yet",
            service=ServiceType.DEEZER,
            error_code="not_implemented",
        )


# Export
__all__ = ["DeezerPlugin"]
