"""
Deezer Plugin - Converts Deezer API data to SoulSpot Standard Format.

Hey future me – das ist das Deezer Plugin!
Es wrappet den DeezerClient und konvertiert API-Responses zu Standard-DTOs.

Das Plugin folgt demselben Pattern wie SpotifyPlugin:
- Client als Konstruktor-Parameter (DI-freundlich)
- Gibt DTOs zurück (nicht rohe dicts)
- Implementiert IMusicServicePlugin Interface
- Zentrale Konvertierungs-Methoden (_convert_*)

Deezer API Besonderheiten:
- Public API ohne OAuth für Metadaten (BASIC mode) - PERFEKT für Browse!
- OAuth für User-Library Zugriff (PRO mode) - JETZT IMPLEMENTIERT!
- Rate Limit: ~50 requests/5 seconds
- ISRC verfügbar bei Tracks (gut für Cross-Service Matching!)
- Kostenlos, keine Premium-Einschränkungen

✅ VOLLSTÄNDIG IMPLEMENTIERT:

Public API (NO AUTH needed!):
- search(), search_artists(), search_albums(), search_tracks()
- get_artist(), get_artist_albums(), get_artist_top_tracks()
- get_album(), get_album_tracks()
- get_track(), get_tracks(), get_several_*()
- get_browse_new_releases(), get_editorial_releases()
- get_chart_tracks(), get_chart_albums(), get_chart_artists()
- get_genres(), get_playlist(), get_playlist_tracks()

OAuth (requires auth):
- get_auth_url() - OAuth URL generieren
- handle_callback() - Code zu Token tauschen
- get_auth_status() - Auth-Status prüfen
- get_current_user() - User-Profil holen
- get_followed_artists() - Gefolgte Artists
- get_saved_tracks(), get_saved_albums() - User's Library
- get_user_playlists() - User's Playlists
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.domain.ports.plugin import CapabilityInfo

from soulspot.domain.dtos import (
    AlbumDTO,
    ArtistDTO,
    ImageRef,
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
from soulspot.infrastructure.integrations.deezer_client import (
    DeezerAlbum,
    DeezerArtist,
    DeezerClient,
    DeezerTrack,
)

logger = logging.getLogger(__name__)


class DeezerPlugin(IMusicServicePlugin):
    """
    Deezer plugin - converts Deezer API data to standard DTOs.

    Hey future me – das ist der Adapter zwischen Deezer API und SoulSpot!
    Das Besondere: Die meisten Methoden brauchen KEINE Auth (public API)!

    OAuth ist OPTIONAL und nur für User-Library nötig (Favorites, Playlists).
    Wenn OAuth nicht konfiguriert ist, funktionieren trotzdem:
    - Suche, Artist/Album/Track Lookup
    - Browse New Releases, Charts, Genres
    - ISRC Lookup (perfekt für Cross-Service Matching!)
    """

    def __init__(
        self,
        client: DeezerClient | None = None,
        access_token: str | None = None,
    ) -> None:
        """
        Initialize Deezer plugin.

        Args:
            client: Optional DeezerClient instance. Creates new one if not provided.
            access_token: Optional OAuth access token for user library access.
                          If not provided, only public API methods work.
        """
        self._client = client or DeezerClient()
        self._access_token = access_token

    # =========================================================================
    # QUICK AUTH CHECK
    # =========================================================================

    @property
    def is_authenticated(self) -> bool:
        """Check if we have an access token (quick check, no API call).

        Hey future me - use this for pre-flight checks before starting operations!
        Unlike get_auth_status(), this doesn't validate the token with Deezer.
        Token might be expired, but this tells you if auth was ever done.

        Important: Many Deezer features work WITHOUT auth (public API)!
        Use this to check if USER-SPECIFIC operations are available.

        Returns:
            True if an access token is set, False otherwise
        """
        return self._access_token is not None

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

    def get_capabilities(self) -> list["CapabilityInfo"]:
        """Get Deezer capabilities with auth requirements.

        Hey future me - Deezer is SPECIAL because most features work WITHOUT auth!
        Only user-specific features (favorites, playlists) need OAuth.

        Returns:
            List of capabilities with auth requirements
        """
        from soulspot.domain.ports.plugin import CapabilityInfo, PluginCapability

        return [
            # Public API - NO AUTH NEEDED! 🎉
            CapabilityInfo(PluginCapability.SEARCH_ARTISTS, requires_auth=False),
            CapabilityInfo(PluginCapability.SEARCH_ALBUMS, requires_auth=False),
            CapabilityInfo(PluginCapability.SEARCH_TRACKS, requires_auth=False),
            CapabilityInfo(PluginCapability.SEARCH_PLAYLISTS, requires_auth=False),
            CapabilityInfo(PluginCapability.BROWSE_NEW_RELEASES, requires_auth=False),
            CapabilityInfo(PluginCapability.BROWSE_GENRES, requires_auth=False),
            CapabilityInfo(PluginCapability.BROWSE_CHARTS, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_ARTIST, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_ALBUM, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_TRACK, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_PLAYLIST, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_ARTIST_ALBUMS, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_ARTIST_TOP_TRACKS, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_RELATED_ARTISTS, requires_auth=False),
            CapabilityInfo(PluginCapability.GET_ALBUM_TRACKS, requires_auth=False),
            # OAuth REQUIRED for user library
            CapabilityInfo(PluginCapability.USER_PROFILE, requires_auth=True),
            CapabilityInfo(PluginCapability.USER_FOLLOWED_ARTISTS, requires_auth=True),
            CapabilityInfo(PluginCapability.USER_SAVED_TRACKS, requires_auth=True),
            CapabilityInfo(PluginCapability.USER_SAVED_ALBUMS, requires_auth=True),
            CapabilityInfo(PluginCapability.USER_PLAYLISTS, requires_auth=True),
        ]

    # =========================================================================
    # AUTHENTICATION (OAuth - optional!)
    # =========================================================================

    async def get_auth_url(self, state: str | None = None) -> str:
        """Get Deezer OAuth URL.

        Hey future me - Deezer OAuth is simpler than Spotify!
        No PKCE needed, just redirect user to this URL.

        Args:
            state: CSRF protection state (recommended!)

        Returns:
            Authorization URL

        Raises:
            PluginError: If OAuth is not configured in DeezerClient settings
        """
        try:
            return self._client.get_authorization_url(state=state or "deezer-auth")
        except ValueError as e:
            raise PluginError(
                message=str(e),
                service=ServiceType.DEEZER,
                error_code="oauth_not_configured",
                original_error=e,
            ) from e

    async def handle_callback(self, code: str, state: str | None = None) -> AuthStatus:
        """Handle OAuth callback and exchange code for token.

        Hey future me - after user authorizes, Deezer redirects back with code.
        We exchange it for access_token (long-lived, no refresh needed!).

        Args:
            code: Authorization code from callback
            state: State for CSRF verification (should match get_auth_url)

        Returns:
            AuthStatus with authentication result
        """
        try:
            token_data = await self._client.exchange_code(code)
            access_token = token_data.get("access_token")

            if not access_token:
                return AuthStatus(
                    is_authenticated=False,
                    service=ServiceType.DEEZER,
                    error="No access token in response",
                )

            # Store token for later use
            self._access_token = access_token

            # Verify token by getting user profile
            try:
                user_data = await self._client.get_user_me(access_token)
                return AuthStatus(
                    is_authenticated=True,
                    service=ServiceType.DEEZER,
                    user_id=str(user_data.get("id", "")),
                    display_name=user_data.get("name"),
                    email=user_data.get("email"),
                    expires_at=None,  # Deezer tokens are long-lived
                )
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")
                # Token valid but couldn't get profile - still authenticated
                return AuthStatus(
                    is_authenticated=True,
                    service=ServiceType.DEEZER,
                )

        except ValueError as e:
            raise PluginError(
                message=str(e),
                service=ServiceType.DEEZER,
                error_code="oauth_not_configured",
                original_error=e,
            ) from e
        except Exception as e:
            logger.exception("Deezer OAuth callback failed")
            return AuthStatus(
                is_authenticated=False,
                service=ServiceType.DEEZER,
                error=str(e),
            )

    async def get_auth_status(self) -> AuthStatus:
        """Get current authentication status.

        Hey future me - Deezer tokens don't expire (with offline_access),
        but they CAN be revoked. We verify by hitting /user/me.
        """
        if not self._access_token:
            return AuthStatus(
                is_authenticated=False,
                service=ServiceType.DEEZER,
            )

        try:
            user_data = await self._client.get_user_me(self._access_token)
            return AuthStatus(
                is_authenticated=True,
                service=ServiceType.DEEZER,
                user_id=str(user_data.get("id", "")),
                display_name=user_data.get("name"),
                email=user_data.get("email"),
                expires_at=None,  # Long-lived token
            )
        except Exception:
            # Token invalid/revoked
            self._access_token = None
            return AuthStatus(
                is_authenticated=False,
                service=ServiceType.DEEZER,
                error="Token expired or revoked",
            )

    async def logout(self) -> None:
        """Clear access token (logout).

        Hey future me - Deezer doesn't have a logout endpoint.
        We just clear our stored token. User would need to revoke
        in Deezer settings if they want full revocation.
        """
        self._access_token = None

    # =========================================================================
    # USER PROFILE (requires OAuth)
    # =========================================================================

    def _ensure_authenticated(self) -> str:
        """Ensure user is authenticated and return access token.

        Hey future me - call this in methods that require OAuth!

        Returns:
            Access token

        Raises:
            PluginError: If not authenticated
        """
        if not self._access_token:
            raise PluginError(
                message="Deezer OAuth required. Please authenticate first.",
                service=ServiceType.DEEZER,
                error_code="oauth_required",
            )
        return self._access_token

    async def get_current_user(self) -> UserProfileDTO:
        """Get current user profile (requires OAuth).

        Returns:
            UserProfileDTO with user info

        Raises:
            PluginError: If not authenticated or request fails
        """
        token = self._ensure_authenticated()

        try:
            user_data = await self._client.get_user_me(token)
            return UserProfileDTO(
                display_name=user_data.get("name", ""),
                source_service="deezer",
                deezer_id=str(user_data.get("id", "")),
                email=user_data.get("email"),
                avatar=ImageRef.from_url(
                    user_data.get("picture_big") or user_data.get("picture")
                ),
                external_urls={"deezer": user_data.get("link", "")},
            )
        except Exception as e:
            logger.exception("Failed to get Deezer user profile")
            raise PluginError(
                message=f"Failed to get user profile: {e}",
                service=ServiceType.DEEZER,
                error_code="user_profile_error",
                original_error=e,
            ) from e

    # =========================================================================
    # SEARCH (Implemented - NO AUTH!)
    # =========================================================================

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResultDTO:
        """Search Deezer for artists, albums, and tracks.

        Hey future me – Deezer Search braucht KEINE Auth!
        Perfekt für Discovery ohne Spotify-Login.

        Args:
            query: Search query
            types: Types to search (artist, album, track). Defaults to all.
            limit: Results per type (max 25 per Deezer API)
            offset: Pagination offset

        Returns:
            SearchResultDTO with results from all requested types
        """
        if types is None:
            types = ["artist", "album", "track"]

        artists: list[ArtistDTO] = []
        albums: list[AlbumDTO] = []
        tracks: list[TrackDTO] = []

        try:
            # Deezer limit is 25 per request, we cap it
            deezer_limit = min(limit, 25)

            if "artist" in types:
                deezer_artists = await self._client.search_artists(
                    query, limit=deezer_limit
                )
                artists = [self._convert_artist(a) for a in deezer_artists]

            if "album" in types:
                deezer_albums = await self._client.search_albums(
                    query, limit=deezer_limit
                )
                albums = [self._convert_album(a) for a in deezer_albums]

            if "track" in types:
                deezer_tracks = await self._client.search_tracks(
                    query, limit=deezer_limit
                )
                tracks = [self._convert_track(t) for t in deezer_tracks]

            return SearchResultDTO(
                query=query,
                source_service="deezer",
                artists=artists,
                albums=albums,
                tracks=tracks,
                playlists=[],  # Deezer playlist search not implemented
            )

        except Exception as e:
            logger.error(f"DeezerPlugin search failed: {e}")
            raise PluginError(
                message=f"Search failed: {e!s}",
                service=ServiceType.DEEZER,
                error_code="search_error",
                original_error=e,
            ) from e

    # =========================================================================
    # ARTISTS (Implemented - NO AUTH!)
    # =========================================================================

    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Get artist by Deezer ID.

        Hey future me – Deezer Artist-Abruf braucht KEINE Auth!

        Args:
            artist_id: Deezer artist ID

        Returns:
            ArtistDTO with artist details
        """
        try:
            deezer_artist = await self._client.get_artist(int(artist_id))
            if not deezer_artist:
                raise PluginError(
                    message=f"Artist {artist_id} not found",
                    service=ServiceType.DEEZER,
                    error_code="not_found",
                )
            return self._convert_artist(deezer_artist)
        except PluginError:
            raise
        except Exception as e:
            logger.error(f"DeezerPlugin get_artist failed: {e}")
            raise PluginError(
                message=f"Failed to get artist: {e!s}",
                service=ServiceType.DEEZER,
                error_code="artist_error",
                original_error=e,
            ) from e

    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[AlbumDTO]:
        """Get artist's albums from Deezer WITH PAGINATION.

        Hey future me – Deezer Artist-Albums braucht KEINE Auth!
        Deezer API supports pagination via 'index' parameter (offset).
        Response includes 'total' and 'next' for pagination info.

        Args:
            artist_id: Deezer artist ID
            include_groups: Not used (Deezer returns all types)
            limit: Maximum albums to return per page (max 100)
            offset: Pagination offset (index for Deezer API)

        Returns:
            PaginatedResponse with artist's albums and pagination info
        """
        try:
            # Client now returns dict with pagination info
            response_data = await self._client.get_artist_albums(
                int(artist_id), limit=limit, index=offset
            )

            # response_data has: 'data' (albums), 'total', 'next' (URL or None)
            albums = [self._convert_album(a) for a in response_data["data"]]
            total = response_data.get("total", len(albums))
            has_next = response_data.get("next") is not None

            # Calculate next_offset if there are more pages
            next_offset = offset + len(albums) if has_next else None

            return PaginatedResponse(
                items=albums,
                total=total,
                limit=limit,
                offset=offset,
                next_offset=next_offset,
            )
        except Exception as e:
            logger.error(f"DeezerPlugin get_artist_albums failed: {e}")
            raise PluginError(
                message=f"Failed to get artist albums: {e!s}",
                service=ServiceType.DEEZER,
                error_code="artist_albums_error",
                original_error=e,
            ) from e

    async def get_artist_top_tracks(
        self, artist_id: str, market: str | None = None
    ) -> list[TrackDTO]:
        """Get artist's top tracks from Deezer.

        Hey future me – Deezer Top-Tracks braucht KEINE Auth!

        Args:
            artist_id: Deezer artist ID
            market: Not used by Deezer

        Returns:
            List of top tracks
        """
        try:
            deezer_tracks = await self._client.get_artist_top_tracks(
                int(artist_id), limit=10
            )
            return [self._convert_track(t) for t in deezer_tracks]
        except Exception as e:
            logger.error(f"DeezerPlugin get_artist_top_tracks failed: {e}")
            raise PluginError(
                message=f"Failed to get artist top tracks: {e!s}",
                service=ServiceType.DEEZER,
                error_code="artist_top_tracks_error",
                original_error=e,
            ) from e

    async def get_followed_artists(
        self, limit: int = 50, after: str | None = None
    ) -> PaginatedResponse[ArtistDTO]:
        """Get user's followed artists (requires OAuth).

        Hey future me - Deezer calls them "favorite artists" but it's the same thing!

        Args:
            limit: Max artists to return (max 100)
            after: Pagination cursor (index for Deezer API)

        Returns:
            Paginated list of followed artists
        """
        token = self._ensure_authenticated()
        index = int(after) if after else 0

        try:
            data = await self._client.get_user_artists(
                access_token=token,
                limit=min(limit, 100),
                index=index,
            )

            artists = [
                ArtistDTO(
                    name=artist.get("name", "Unknown"),
                    source_service="deezer",
                    deezer_id=str(artist.get("id", "")),
                    image=ImageRef.from_url(
                        artist.get("picture_big") or artist.get("picture_medium")
                    ),
                    genres=[],
                    followers=artist.get("nb_fan"),
                    external_urls={"deezer": artist.get("link", "")},
                )
                for artist in data.get("data", [])
            ]

            total = data.get("total", len(artists))
            next_index = index + len(artists)
            has_more = next_index < total

            return PaginatedResponse(
                items=artists,
                total=total,
                limit=limit,
                offset=index,
                next_offset=next_index if has_more else None,
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Failed to get followed artists")
            raise PluginError(
                message=f"Failed to get followed artists: {e}",
                service=ServiceType.DEEZER,
                error_code="followed_artists_error",
                original_error=e,
            ) from e

    # =========================================================================
    # ALBUMS (Implemented - NO AUTH!)
    # =========================================================================

    async def get_album(self, album_id: str) -> AlbumDTO:
        """Get album by Deezer ID.

        Hey future me – Deezer Album-Abruf braucht KEINE Auth!

        Args:
            album_id: Deezer album ID

        Returns:
            AlbumDTO with album details
        """
        try:
            deezer_album = await self._client.get_album(int(album_id))
            if not deezer_album:
                raise PluginError(
                    message=f"Album {album_id} not found",
                    service=ServiceType.DEEZER,
                    error_code="not_found",
                )
            return self._convert_album(deezer_album)
        except PluginError:
            raise
        except Exception as e:
            logger.error(f"DeezerPlugin get_album failed: {e}")
            raise PluginError(
                message=f"Failed to get album: {e!s}",
                service=ServiceType.DEEZER,
                error_code="album_error",
                original_error=e,
            ) from e

    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get album tracks from Deezer.

        Hey future me – Deezer Album-Tracks braucht KEINE Auth!

        Args:
            album_id: Deezer album ID
            limit: Maximum tracks to return
            offset: Pagination offset

        Returns:
            PaginatedResponse with album tracks
        """
        try:
            deezer_tracks = await self._client.get_album_tracks(int(album_id))
            tracks = [self._convert_track(t) for t in deezer_tracks]

            return PaginatedResponse(
                items=tracks,
                total=len(tracks),
                limit=limit,
                offset=offset,
                next_offset=None,
            )
        except Exception as e:
            logger.error(f"DeezerPlugin get_album_tracks failed: {e}")
            raise PluginError(
                message=f"Failed to get album tracks: {e!s}",
                service=ServiceType.DEEZER,
                error_code="album_tracks_error",
                original_error=e,
            ) from e

    # =========================================================================
    # TRACKS (Implemented - NO AUTH!)
    # =========================================================================

    async def get_track(self, track_id: str) -> TrackDTO:
        """Get track by Deezer ID.

        Hey future me – Deezer Track-Abruf braucht KEINE Auth!

        Args:
            track_id: Deezer track ID

        Returns:
            TrackDTO with track details
        """
        try:
            deezer_track = await self._client.get_track(int(track_id))
            if not deezer_track:
                raise PluginError(
                    message=f"Track {track_id} not found",
                    service=ServiceType.DEEZER,
                    error_code="not_found",
                )
            return self._convert_track(deezer_track)
        except PluginError:
            raise
        except Exception as e:
            logger.error(f"DeezerPlugin get_track failed: {e}")
            raise PluginError(
                message=f"Failed to get track: {e!s}",
                service=ServiceType.DEEZER,
                error_code="track_error",
                original_error=e,
            ) from e

    async def get_tracks(self, track_ids: list[str]) -> list[TrackDTO]:
        """Get multiple tracks by Deezer IDs.

        Hey future me – Deezer hat keine Batch-API, also holen wir einzeln!

        Args:
            track_ids: List of Deezer track IDs

        Returns:
            List of TrackDTOs
        """
        tracks = []
        for track_id in track_ids:
            try:
                track = await self.get_track(track_id)
                tracks.append(track)
            except PluginError:
                # Skip tracks that fail, don't break the whole request
                logger.warning(f"Failed to get track {track_id}, skipping")
                continue
        return tracks

    # =========================================================================
    # BATCH OPERATIONS (Sequential - Deezer has no native batch API)
    # =========================================================================

    async def get_several_artists(self, artist_ids: list[str]) -> list[ArtistDTO]:
        """Get multiple artists by Deezer IDs.

        Hey future me – Deezer hat keine Batch-API wie Spotify!
        Wir holen Artists einzeln mit Rate-Limiting im Client.

        Args:
            artist_ids: List of Deezer artist IDs

        Returns:
            List of ArtistDTOs (failed lookups filtered out)
        """
        try:
            int_ids = [int(aid) for aid in artist_ids]
            deezer_artists = await self._client.get_several_artists(int_ids)
            return [self._convert_artist(a) for a in deezer_artists]
        except Exception as e:
            logger.error(f"DeezerPlugin get_several_artists failed: {e}")
            raise PluginError(
                message=f"Failed to get artists: {e!s}",
                service=ServiceType.DEEZER,
                error_code="batch_artists_error",
                original_error=e,
            ) from e

    async def get_albums(self, album_ids: list[str]) -> list[AlbumDTO]:
        """Get multiple albums by Deezer IDs (batch request).

        Hey future me – Interface-compliant alias for get_several_albums!
        Deezer hat keine echte Batch-API, wir holen einzeln mit Rate-Limiting.

        Args:
            album_ids: List of Deezer album IDs

        Returns:
            List of AlbumDTOs (failed lookups filtered out)
        """
        return await self.get_several_albums(album_ids)

    async def get_several_albums(self, album_ids: list[str]) -> list[AlbumDTO]:
        """Get multiple albums by Deezer IDs.

        Hey future me – Deezer hat keine Batch-API wie Spotify!
        Wir holen Albums einzeln mit Rate-Limiting im Client.

        Args:
            album_ids: List of Deezer album IDs

        Returns:
            List of AlbumDTOs (failed lookups filtered out)
        """
        try:
            int_ids = [int(aid) for aid in album_ids]
            deezer_albums = await self._client.get_several_albums(int_ids)
            return [self._convert_album(a) for a in deezer_albums]
        except Exception as e:
            logger.error(f"DeezerPlugin get_several_albums failed: {e}")
            raise PluginError(
                message=f"Failed to get albums: {e!s}",
                service=ServiceType.DEEZER,
                error_code="batch_albums_error",
                original_error=e,
            ) from e

    # =========================================================================
    # DISCOVERY FEATURES
    # =========================================================================

    async def get_related_artists(
        self, artist_id: str, limit: int = 20
    ) -> list[ArtistDTO]:
        """Get artists related to the given artist.

        Hey future me – Deezer's "fans also like" feature!
        Perfekt für Discovery ohne Spotify-Login.

        Args:
            artist_id: Deezer artist ID
            limit: Maximum results (max 100)

        Returns:
            List of related ArtistDTOs
        """
        try:
            deezer_artists = await self._client.get_related_artists(
                int(artist_id), limit=limit
            )
            return [self._convert_artist(a) for a in deezer_artists]
        except Exception as e:
            logger.error(f"DeezerPlugin get_related_artists failed: {e}")
            raise PluginError(
                message=f"Failed to get related artists: {e!s}",
                service=ServiceType.DEEZER,
                error_code="related_artists_error",
                original_error=e,
            ) from e

    # =========================================================================
    # SEARCH CONVENIENCE HELPERS
    # =========================================================================

    async def search_artists(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> PaginatedResponse[ArtistDTO]:
        """Search for artists on Deezer.

        Hey future me – Convenience-Wrapper um search() für nur Artists.

        Args:
            query: Search query
            limit: Maximum results (max 25 per Deezer API)
            offset: Pagination offset

        Returns:
            PaginatedResponse with artist results
        """
        try:
            deezer_artists = await self._client.search_artists(
                query, limit=min(limit, 25)
            )
            artists = [self._convert_artist(a) for a in deezer_artists]
            has_more = len(artists) >= limit

            return PaginatedResponse(
                items=artists,
                total=len(artists),
                limit=limit,
                offset=offset,
                next_offset=offset + len(artists) if has_more else None,
            )
        except Exception as e:
            logger.error(f"DeezerPlugin search_artists failed: {e}")
            raise PluginError(
                message=f"Artist search failed: {e!s}",
                service=ServiceType.DEEZER,
                error_code="search_artists_error",
                original_error=e,
            ) from e

    async def search_albums(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """Search for albums on Deezer.

        Hey future me – Convenience-Wrapper um search() für nur Albums.

        Args:
            query: Search query
            limit: Maximum results (max 25 per Deezer API)
            offset: Pagination offset

        Returns:
            PaginatedResponse with album results
        """
        try:
            deezer_albums = await self._client.search_albums(
                query, limit=min(limit, 25)
            )
            albums = [self._convert_album(a) for a in deezer_albums]
            has_more = len(albums) >= limit

            return PaginatedResponse(
                items=albums,
                total=len(albums),
                limit=limit,
                offset=offset,
                next_offset=offset + len(albums) if has_more else None,
            )
        except Exception as e:
            logger.error(f"DeezerPlugin search_albums failed: {e}")
            raise PluginError(
                message=f"Album search failed: {e!s}",
                service=ServiceType.DEEZER,
                error_code="search_albums_error",
                original_error=e,
            ) from e

    async def search_tracks(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Search for tracks on Deezer.

        Hey future me – Convenience-Wrapper um search() für nur Tracks.
        ISRC ist verfügbar für Cross-Service Matching!

        Args:
            query: Search query
            limit: Maximum results (max 25 per Deezer API)
            offset: Pagination offset

        Returns:
            PaginatedResponse with track results
        """
        try:
            deezer_tracks = await self._client.search_tracks(
                query, limit=min(limit, 25)
            )
            tracks = [self._convert_track(t) for t in deezer_tracks]
            has_more = len(tracks) >= limit

            return PaginatedResponse(
                items=tracks,
                total=len(tracks),
                limit=limit,
                offset=offset,
                next_offset=offset + len(tracks) if has_more else None,
            )
        except Exception as e:
            logger.error(f"DeezerPlugin search_tracks failed: {e}")
            raise PluginError(
                message=f"Track search failed: {e!s}",
                service=ServiceType.DEEZER,
                error_code="search_tracks_error",
                original_error=e,
            ) from e

    # =========================================================================
    # ISRC-BASED LOOKUP (Unique Deezer Feature!)
    # =========================================================================

    async def get_track_by_isrc(self, isrc: str) -> TrackDTO | None:
        """Get track by ISRC code.

        Hey future me – DAS IST GOLD FÜR CROSS-SERVICE MATCHING!
        ISRC (International Standard Recording Code) ist ein eindeutiger
        Identifier für Recordings. Wenn du einen Track in deiner lokalen
        Library hast und dessen ISRC kennst, kannst du ihn damit auf Deezer
        finden - egal wie der Titel geschrieben ist!

        Args:
            isrc: International Standard Recording Code (e.g., "USRC11700123")

        Returns:
            TrackDTO if found, None otherwise
        """
        try:
            deezer_track = await self._client.get_track_by_isrc(isrc)
            if not deezer_track:
                return None
            return self._convert_track(deezer_track)
        except Exception as e:
            logger.warning(f"DeezerPlugin get_track_by_isrc failed for {isrc}: {e}")
            return None

    # =========================================================================
    # PLAYLISTS (Stub - requires OAuth)
    # =========================================================================

    async def get_playlist(self, playlist_id: str) -> PlaylistDTO:
        """Get playlist by Deezer ID.

        Hey future me - public playlists can be fetched without auth!
        """
        try:
            response = await self._client._rate_limited_request(
                "GET", f"/playlist/{playlist_id}"
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise PluginError(
                    message=f"Playlist not found: {data['error'].get('message', 'Unknown')}",
                    service=ServiceType.DEEZER,
                    error_code="not_found",
                )

            return PlaylistDTO(
                name=data.get("title", ""),
                source_service="deezer",
                deezer_id=str(data.get("id", "")),
                description=data.get("description"),
                cover=ImageRef.from_url(
                    data.get("picture_big") or data.get("picture_medium")
                ),
                owner_id=str(data.get("creator", {}).get("id", "")),
                owner_name=data.get("creator", {}).get("name"),
                total_tracks=data.get("nb_tracks", 0),
                is_public=data.get("public", True),
                external_urls={"deezer": data.get("link", "")},
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get playlist {playlist_id}")
            raise PluginError(
                message=f"Failed to get playlist: {e}",
                service=ServiceType.DEEZER,
                error_code="playlist_error",
                original_error=e,
            ) from e

    async def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get playlist tracks (public playlists work without auth)."""
        try:
            response = await self._client._rate_limited_request(
                "GET",
                f"/playlist/{playlist_id}/tracks",
                params={"limit": min(limit, 100), "index": offset},
            )
            response.raise_for_status()
            data = response.json()

            tracks = [
                self._convert_track(
                    DeezerTrack(
                        id=track.get("id", 0),
                        title=track.get("title", ""),
                        artist_name=track.get("artist", {}).get("name", "Unknown"),
                        artist_id=track.get("artist", {}).get("id"),
                        album_title=track.get("album", {}).get("title", ""),
                        album_id=track.get("album", {}).get("id"),
                        duration=track.get("duration", 0),
                        track_position=track.get("track_position"),
                        disk_number=track.get("disk_number"),
                        isrc=track.get("isrc"),
                        preview=track.get("preview"),
                        explicit_lyrics=track.get("explicit_lyrics", False),
                    )
                )
                for track in data.get("data", [])
            ]

            total = data.get("total", len(tracks))
            has_more = (offset + len(tracks)) < total

            return PaginatedResponse(
                items=tracks,
                total=total,
                limit=limit,
                offset=offset,
                next_offset=offset + len(tracks) if has_more else None,
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get playlist tracks for {playlist_id}")
            raise PluginError(
                message=f"Failed to get playlist tracks: {e}",
                service=ServiceType.DEEZER,
                error_code="playlist_tracks_error",
                original_error=e,
            ) from e

    async def get_user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[PlaylistDTO]:
        """Get user's playlists (requires OAuth).

        Hey future me - this returns playlists owned by the user AND
        playlists they've added to their library!
        """
        token = self._ensure_authenticated()

        try:
            data = await self._client.get_user_playlists(
                access_token=token,
                limit=min(limit, 100),
                index=offset,
            )

            playlists = [
                PlaylistDTO(
                    name=pl.get("title", ""),
                    source_service="deezer",
                    deezer_id=str(pl.get("id", "")),
                    description=pl.get("description"),
                    cover=ImageRef.from_url(
                        pl.get("picture_big") or pl.get("picture_medium")
                    ),
                    owner_id=str(pl.get("creator", {}).get("id", "")),
                    owner_name=pl.get("creator", {}).get("name"),
                    total_tracks=pl.get("nb_tracks", 0),
                    is_public=pl.get("public", True),
                    external_urls={"deezer": pl.get("link", "")},
                )
                for pl in data.get("data", [])
            ]

            total = data.get("total", len(playlists))
            has_more = (offset + len(playlists)) < total

            return PaginatedResponse(
                items=playlists,
                total=total,
                limit=limit,
                offset=offset,
                next_offset=offset + len(playlists) if has_more else None,
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Failed to get user playlists")
            raise PluginError(
                message=f"Failed to get user playlists: {e}",
                service=ServiceType.DEEZER,
                error_code="user_playlists_error",
                original_error=e,
            ) from e

    # =========================================================================
    # LIBRARY (OAuth required)
    # =========================================================================

    async def get_saved_tracks(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get user's favorite/saved tracks (requires OAuth).

        Hey future me - Deezer calls them "favorites" (heart icon).
        """
        token = self._ensure_authenticated()

        try:
            data = await self._client.get_user_favorites(
                access_token=token,
                limit=min(limit, 100),
                index=offset,
            )

            tracks = [
                self._convert_track(
                    DeezerTrack(
                        id=track.get("id", 0),
                        title=track.get("title", ""),
                        artist_name=track.get("artist", {}).get("name", "Unknown"),
                        artist_id=track.get("artist", {}).get("id"),
                        album_title=track.get("album", {}).get("title", ""),
                        album_id=track.get("album", {}).get("id"),
                        duration=track.get("duration", 0),
                        track_position=track.get("track_position"),
                        disk_number=track.get("disk_number"),
                        isrc=track.get("isrc"),
                        preview=track.get("preview"),
                        explicit_lyrics=track.get("explicit_lyrics", False),
                    )
                )
                for track in data.get("data", [])
            ]

            total = data.get("total", len(tracks))
            has_more = (offset + len(tracks)) < total

            return PaginatedResponse(
                items=tracks,
                total=total,
                limit=limit,
                offset=offset,
                next_offset=offset + len(tracks) if has_more else None,
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Failed to get saved tracks")
            raise PluginError(
                message=f"Failed to get saved tracks: {e}",
                service=ServiceType.DEEZER,
                error_code="saved_tracks_error",
                original_error=e,
            ) from e

    async def get_saved_albums(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """Get user's saved albums (requires OAuth).

        Hey future me - returns albums user has added to their library.
        """
        token = self._ensure_authenticated()

        try:
            data = await self._client.get_user_albums(
                access_token=token,
                limit=min(limit, 100),
                index=offset,
            )

            albums = [
                AlbumDTO(
                    title=album.get("title", ""),
                    artist_name=album.get("artist", {}).get("name", "Unknown"),
                    source_service="deezer",
                    deezer_id=str(album.get("id", "")),
                    artist_deezer_id=str(album.get("artist", {}).get("id", "")),
                    cover=ImageRef.from_url(
                        album.get("cover_big")
                        or album.get("cover_medium")
                        or album.get("cover")
                    ),
                    release_date=album.get("release_date"),
                    total_tracks=album.get("nb_tracks", 0),
                    album_type=album.get("record_type", "album"),
                    external_urls={"deezer": album.get("link", "")},
                )
                for album in data.get("data", [])
            ]

            total = data.get("total", len(albums))
            has_more = (offset + len(albums)) < total

            return PaginatedResponse(
                items=albums,
                total=total,
                limit=limit,
                offset=offset,
                next_offset=offset + len(albums) if has_more else None,
            )

        except PluginError:
            raise
        except Exception as e:
            logger.exception("Failed to get saved albums")
            raise PluginError(
                message=f"Failed to get saved albums: {e}",
                service=ServiceType.DEEZER,
                error_code="saved_albums_error",
                original_error=e,
            ) from e

    # =========================================================================
    # BROWSE - NO AUTH REQUIRED! (Implemented)
    # =========================================================================

    async def get_browse_new_releases(
        self,
        limit: int = 50,
        include_compilations: bool = True,
    ) -> dict[str, Any]:
        """Get new album releases from Deezer.

        Hey future me – das ist DIE Hauptmethode für Browse ohne Auth!
        Kombiniert Editorial Releases + Chart Albums für gute Mischung.
        Perfekt als Fallback wenn Spotify nicht verbunden ist.

        Args:
            limit: Maximum albums to return (10-100)
            include_compilations: Whether to include compilation albums

        Returns:
            Dict with albums list and metadata:
            {
                "success": True,
                "source": "deezer",
                "total": 42,
                "albums": [...album dicts...]
            }
        """
        try:
            result = await self._client.get_browse_new_releases(
                limit=limit,
                include_compilations=include_compilations,
            )
            logger.debug(f"DeezerPlugin: Fetched {result.get('total', 0)} new releases")
            return result
        except Exception as e:
            logger.error(f"DeezerPlugin: get_browse_new_releases failed: {e}")
            return {
                "success": False,
                "source": "deezer",
                "error": str(e),
                "albums": [],
            }

    async def get_editorial_releases(self, limit: int = 50) -> list[AlbumDTO]:
        """Get editorial selection of new releases.

        Hey future me – das sind die kuratierten Neuerscheinungen von Deezer.
        Keine Auth nötig! Gut für Discovery-Features.

        Args:
            limit: Maximum albums to return

        Returns:
            List of AlbumDTO objects
        """
        try:
            deezer_albums = await self._client.get_editorial_releases(limit=limit)
            return [self._convert_album_to_dto(album) for album in deezer_albums]
        except Exception as e:
            logger.error(f"DeezerPlugin: get_editorial_releases failed: {e}")
            return []

    async def get_chart_tracks(self, limit: int = 50) -> list[TrackDTO]:
        """Get top chart tracks.

        Hey future me – das sind die aktuellen Chart-Tracks.
        Keine Auth nötig! Gut für "What's hot" Features.

        Args:
            limit: Maximum tracks to return

        Returns:
            List of TrackDTO objects
        """
        try:
            deezer_tracks = await self._client.get_chart_tracks(limit=limit)
            return [self._convert_track(track) for track in deezer_tracks]
        except Exception as e:
            logger.error(f"DeezerPlugin: get_chart_tracks failed: {e}")
            return []

    async def get_chart_albums(self, limit: int = 50) -> list[AlbumDTO]:
        """Get top chart albums.

        Hey future me – das sind die aktuellen Chart-Alben.
        Keine Auth nötig! Gut für "What's hot" Features.

        Args:
            limit: Maximum albums to return

        Returns:
            List of AlbumDTO objects
        """
        try:
            deezer_albums = await self._client.get_chart_albums(limit=limit)
            return [self._convert_album_to_dto(album) for album in deezer_albums]
        except Exception as e:
            logger.error(f"DeezerPlugin: get_chart_albums failed: {e}")
            return []

    async def get_chart_artists(self, limit: int = 50) -> list[ArtistDTO]:
        """Get top chart artists.

        Hey future me – das sind die aktuellen Chart-Artists.
        Keine Auth nötig! Gut für "What's hot" Features.

        Args:
            limit: Maximum artists to return

        Returns:
            List of ArtistDTO objects
        """
        try:
            deezer_artists = await self._client.get_chart_artists(limit=limit)
            return [self._convert_artist(artist) for artist in deezer_artists]
        except Exception as e:
            logger.error(f"DeezerPlugin: get_chart_artists failed: {e}")
            return []

    # =========================================================================
    # NEW RELEASES FROM FOLLOWED ARTISTS (Multi-Provider Feature)
    # =========================================================================

    async def get_new_releases(
        self,
        days: int = 90,
        include_singles: bool = True,
        include_compilations: bool = True,
    ) -> list[AlbumDTO]:
        """Get new album releases from followed artists.

        Hey future me - DAS ist die RICHTIGE Methode für New Releases!
        Zeigt NUR Releases von Artists denen du folgst, NICHT alle Editorial/Charts!

        Wie Spotify:
        1. Holt alle Followed Artists
        2. Für jeden Artist: Recent Albums holen
        3. Filtert nach Release-Datum

        WICHTIG: Braucht OAuth (User muss bei Deezer eingeloggt sein)!
        Wenn nicht authenticated, gibt leere Liste zurück mit Warning.

        Args:
            days: Look back period (default 90 days)
            include_singles: Include singles/EPs in results
            include_compilations: Include compilation albums

        Returns:
            List of AlbumDTOs from followed artists within timeframe
        """
        from datetime import UTC, datetime, timedelta

        # Check if authenticated - New Releases from followed needs OAuth!
        if not self.is_authenticated:
            logger.warning(
                "DeezerPlugin.get_new_releases() requires OAuth! "
                "User needs to connect Deezer to see releases from followed artists. "
                "Use get_browse_new_releases() for public editorial/charts."
            )
            return []

        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        try:
            # Step 1: Get all followed artists (paginated)
            all_artists: list[ArtistDTO] = []
            after: str | None = None

            while True:
                result = await self.get_followed_artists(limit=50, after=after)
                all_artists.extend(result.items)
                if result.next_offset is None:
                    break
                after = str(result.next_offset)

            logger.info(
                f"DeezerPlugin: Fetching new releases for {len(all_artists)} followed artists"
            )

            # Step 2: Get recent albums for each artist
            all_albums: list[AlbumDTO] = []
            seen_ids: set[str] = set()

            for artist in all_artists:
                if not artist.deezer_id:
                    continue

                try:
                    # Get artist albums
                    albums = await self.get_artist_albums(
                        artist_id=artist.deezer_id,
                        limit=20,  # Max 20 recent albums per artist
                    )

                    # Filter by release date and type
                    for album in albums:
                        # Skip duplicates
                        if album.deezer_id and album.deezer_id in seen_ids:
                            continue

                        # Filter by album type
                        album_type = (album.album_type or "album").lower()
                        if album_type == "single" and not include_singles:
                            continue
                        if album_type == "compilation" and not include_compilations:
                            continue

                        # Check release date
                        if album.release_date and album.release_date >= cutoff_str:
                            if album.deezer_id:
                                seen_ids.add(album.deezer_id)
                            # Ensure source is set
                            if not album.source_service:
                                album.source_service = "deezer"
                            all_albums.append(album)

                except Exception as e:
                    # Log error but continue with other artists
                    logger.warning(
                        f"DeezerPlugin: Failed to get albums for artist {artist.deezer_id}: {e}"
                    )
                    continue

            logger.info(
                f"DeezerPlugin: Found {len(all_albums)} new releases from "
                f"{len(all_artists)} followed artists (last {days} days)"
            )
            return all_albums

        except PluginError:
            raise
        except Exception as e:
            logger.exception(f"DeezerPlugin: get_new_releases failed: {e}")
            return []

    async def get_genres(self) -> list[dict[str, Any]]:
        """Get all available Deezer genres.

        Hey future me – alle Genre-Kategorien von Deezer.
        Keine Auth nötig! Gut für Browse-by-Genre Features.

        Returns:
            List of genre dicts with id, name, picture URLs
        """
        try:
            return await self._client.get_genres()
        except Exception as e:
            logger.error(f"DeezerPlugin: get_genres failed: {e}")
            return []

    # =========================================================================
    # HELPER METHODS - Conversion from Deezer dataclasses to DTOs
    # =========================================================================

    def _convert_artist(self, deezer_artist: DeezerArtist) -> ArtistDTO:
        """Convert DeezerArtist to ArtistDTO.

        Hey future me – der zentrale Artist-Konverter!
        Wird von allen Methoden genutzt die Artists zurückgeben.

        Args:
            deezer_artist: DeezerArtist dataclass from deezer_client

        Returns:
            Standard ArtistDTO
        """
        return ArtistDTO(
            name=deezer_artist.name,
            source_service="deezer",
            deezer_id=str(deezer_artist.id),
            genres=[],  # Deezer doesn't return genres on artist object
            popularity=None,
            image=ImageRef.from_url(
                deezer_artist.picture_big or deezer_artist.picture_medium
            ),
            followers=deezer_artist.nb_fan,
            external_urls={"deezer": deezer_artist.link or ""},
        )

    def _convert_album(self, deezer_album: DeezerAlbum) -> AlbumDTO:
        """Convert DeezerAlbum to AlbumDTO.

        Hey future me – der zentrale Album-Konverter!
        Wird von allen Methoden genutzt die Alben zurückgeben.

        WICHTIG: Konvertiert Deezer record_type zu standardisiertem primary_type:
        - "album" → "album"
        - "ep" → "ep"
        - "single" → "single"
        - "compile" → "album" (Deezer's "compile" is treated as regular album, not compilation)

        NOTE: Deezer's "compile" record_type does NOT reliably indicate compilation albums
        (various artists). True compilations should be detected by checking track-level
        artist diversity, not by record_type alone.

        Args:
            deezer_album: DeezerAlbum dataclass from deezer_client

        Returns:
            Standard AlbumDTO
        """
        # Normalize Deezer record_type to standard primary_type
        record_type = deezer_album.record_type or "album"
        primary_type = record_type
        secondary_types = []

        # Deezer uses "compile" as a record_type, OFFICIALLY meaning "compilation/collection"
        # BUT in practice, Deezer marks many regular artist albums as "compile" (API inconsistency).
        # Examples: "Drokz" albums are marked "compile" but are NOT various-artists compilations.
        #
        # TRADE-OFF DECISION: Treat "compile" as "album" to avoid hiding regular albums.
        # Side effect: TRUE compilations marked as "compile" won't be filterable via include_compilations.
        #
        # TODO: Implement smart compilation detection by checking track-level artist diversity
        # instead of relying on Deezer's unreliable record_type field.
        if record_type == "compile":
            primary_type = "album"
            # Don't automatically add "compilation" to secondary_types

        return AlbumDTO(
            title=deezer_album.title,
            artist_name=deezer_album.artist_name,
            source_service="deezer",
            deezer_id=str(deezer_album.id),
            artist_deezer_id=str(deezer_album.artist_id)
            if deezer_album.artist_id
            else None,
            release_date=deezer_album.release_date,
            total_tracks=deezer_album.nb_tracks or 0,
            album_type=primary_type,  # Use normalized value ("album" for "compile")
            primary_type=primary_type,  # Normalized value
            secondary_types=secondary_types,
            cover=ImageRef.from_url(
                deezer_album.cover_big or deezer_album.cover_medium
            ),
            upc=deezer_album.upc,
            external_urls={"deezer": deezer_album.link or ""},
        )

    def _convert_track(self, deezer_track: DeezerTrack) -> TrackDTO:
        """Convert DeezerTrack to TrackDTO.

        Hey future me – der zentrale Track-Konverter!
        Wichtig: ISRC ist verfügbar für Cross-Service Matching!

        Args:
            deezer_track: DeezerTrack dataclass from deezer_client

        Returns:
            Standard TrackDTO
        """
        return TrackDTO(
            title=deezer_track.title,
            artist_name=deezer_track.artist_name,
            source_service="deezer",
            deezer_id=str(deezer_track.id),
            artist_deezer_id=str(deezer_track.artist_id)
            if deezer_track.artist_id
            else None,
            album_name=deezer_track.album_title,
            album_deezer_id=str(deezer_track.album_id)
            if deezer_track.album_id
            else None,
            duration_ms=deezer_track.duration * 1000,  # Convert seconds to ms
            track_number=deezer_track.track_position,
            disc_number=deezer_track.disk_number or 1,
            isrc=deezer_track.isrc,  # GOLD for cross-service matching!
            explicit=deezer_track.explicit_lyrics or False,
        )

    # Legacy alias for backwards compatibility
    def _convert_album_to_dto(self, deezer_album: DeezerAlbum) -> AlbumDTO:
        """Legacy alias - use _convert_album instead."""
        return self._convert_album(deezer_album)


# Export
__all__ = ["DeezerPlugin"]
