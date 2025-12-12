"""
Spotify Plugin - Converts Spotify API data to SoulSpot Standard Format.

Hey future me – das ist DER erste richtige Plugin!
SpotifyPlugin wrappet den existierenden SpotifyClient und konvertiert
ALLE API-Responses zu unseren Standard-DTOs.

Architektur:
- SpotifyClient: Low-Level HTTP Client (bleibt unverändert, gibt dict zurück)
- SpotifyPlugin: High-Level Plugin (konvertiert zu DTOs)

Warum zwei Klassen?
1. SpotifyClient ist getestet und stabil - nicht anfassen
2. SpotifyPlugin kümmert sich um Konvertierung
3. Wenn Spotify API ändert, nur SpotifyClient anpassen
4. Wenn DTO-Format ändert, nur SpotifyPlugin anpassen

Verwendung:
    plugin = SpotifyPlugin(spotify_client, token_manager)
    artist = await plugin.get_artist("4dpARuHxo51G3z768sgnrY")
    # artist ist jetzt ArtistDTO, nicht dict!
"""

import logging
from typing import Any

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
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


class SpotifyPlugin(IMusicServicePlugin):
    """
    Spotify plugin that converts API responses to standard DTOs.

    Hey future me – das ist der Adapter zwischen Spotify API und SoulSpot!
    Alle Methoden geben DTOs zurück, nie rohe dicts.
    """

    # Hey future me – wir speichern access_token als Attribut!
    # Der Token wird von außen gesetzt (TokenManager/Service) und hier genutzt.
    # Das Plugin verwaltet Tokens NICHT selbst - das macht der TokenManager.
    def __init__(
        self,
        client: SpotifyClient,
        access_token: str | None = None,
    ) -> None:
        """
        Initialize Spotify plugin.

        Args:
            client: Low-level SpotifyClient for HTTP calls
            access_token: OAuth access token (can be set later via set_token)
        """
        self._client = client
        self._access_token = access_token

    # =========================================================================
    # PLUGIN INTERFACE PROPERTIES
    # =========================================================================

    @property
    def service_type(self) -> ServiceType:
        """Return Spotify service type."""
        return ServiceType.SPOTIFY

    @property
    def auth_type(self) -> AuthType:
        """Return OAuth PKCE auth type."""
        return AuthType.OAUTH_PKCE

    @property
    def display_name(self) -> str:
        """Return human-readable service name."""
        return "Spotify"

    # =========================================================================
    # TOKEN MANAGEMENT
    # =========================================================================

    def set_token(self, access_token: str) -> None:
        """
        Set the OAuth access token.

        Hey future me – call this nach Token-Refresh oder Auth-Callback!
        Das Plugin cached den Token, aber validiert ihn nicht.

        Args:
            access_token: Fresh OAuth access token
        """
        self._access_token = access_token

    def _ensure_token(self) -> str:
        """
        Ensure we have an access token.

        Hey future me – wirft PluginError wenn kein Token!
        Besser als cryptische 401 Errors von Spotify.

        Returns:
            Access token string

        Raises:
            PluginError: If no token is set
        """
        if not self._access_token:
            raise PluginError(
                message="Not authenticated. Please connect your Spotify account.",
                service=ServiceType.SPOTIFY,
                error_code="no_token",
                recoverable=True,
            )
        return self._access_token

    # =========================================================================
    # AUTHENTICATION METHODS
    # =========================================================================

    async def get_auth_url(self, state: str | None = None) -> str:
        """
        Get Spotify OAuth authorization URL.

        Args:
            state: CSRF protection state (will be generated if not provided)

        Returns:
            Full authorization URL to redirect user to
        """
        import secrets

        if state is None:
            state = secrets.token_urlsafe(32)

        code_verifier = SpotifyClient.generate_code_verifier()
        # Hey future me – code_verifier muss gespeichert werden!
        # Der caller muss das tun (TokenManager/AuthService).
        # Wir geben nur die URL zurück.

        try:
            url = await self._client.get_authorization_url(state, code_verifier)
            return url
        except Exception as e:
            raise PluginError(
                message=f"Failed to generate auth URL: {e!s}",
                service=ServiceType.SPOTIFY,
                error_code="auth_url_error",
                original_error=e,
            ) from e

    async def handle_callback(self, code: str, state: str | None = None) -> AuthStatus:
        """
        Handle OAuth callback (code exchange).

        Hey future me – das wird vom AuthRouter aufgerufen nach Spotify-Redirect!
        Der code_verifier muss separat übergeben werden (nicht im Interface).

        Args:
            code: Authorization code from callback
            state: State for verification (not used here, verified by caller)

        Returns:
            AuthStatus with authentication details

        Raises:
            PluginError: If callback handling fails
        """
        # Hey future me – der volle OAuth Flow braucht den code_verifier!
        # Das Interface erlaubt das nicht, also muss der Caller
        # SpotifyClient.exchange_code() direkt nutzen.
        # Diese Methode ist nur für Interface-Kompatibilität.
        raise PluginError(
            message="Use SpotifyClient.exchange_code() directly with code_verifier",
            service=ServiceType.SPOTIFY,
            error_code="not_implemented",
        )

    async def get_auth_status(self) -> AuthStatus:
        """
        Get current authentication status.

        Hey future me – checkt ob Token gesetzt ist und holt User-Info!
        Gibt AuthStatus mit is_authenticated=False wenn kein Token.
        """
        if not self._access_token:
            return AuthStatus(
                is_authenticated=False,
                service=ServiceType.SPOTIFY,
            )

        try:
            user = await self.get_current_user()
            return AuthStatus(
                is_authenticated=True,
                service=ServiceType.SPOTIFY,
                user_id=user.spotify_id,
                display_name=user.display_name,
            )
        except PluginError:
            return AuthStatus(
                is_authenticated=False,
                service=ServiceType.SPOTIFY,
            )

    async def logout(self) -> None:
        """
        Clear authentication tokens.

        Hey future me – löscht nur lokalen Token, nicht Spotify-Session!
        """
        self._access_token = None

    # =========================================================================
    # CONVERSION HELPERS
    # =========================================================================

    def _convert_artist(self, data: dict[str, Any]) -> ArtistDTO:
        """
        Convert Spotify artist JSON to ArtistDTO.

        Hey future me – das ist DER zentrale Artist-Konverter!
        Wird von allen Methoden genutzt die Artists zurückgeben.
        """
        # Pick medium-sized image (usually 320px)
        image_url = None
        images = data.get("images", [])
        if images:
            # Prefer medium size, fallback to first
            if len(images) >= 2:
                image_url = images[1].get("url")
            else:
                image_url = images[0].get("url")

        return ArtistDTO(
            name=data.get("name", "Unknown Artist"),
            source_service="spotify",
            spotify_id=data.get("id"),
            spotify_uri=data.get("uri"),
            image_url=image_url,
            genres=data.get("genres", []),
            popularity=data.get("popularity"),
            followers=data.get("followers", {}).get("total"),
            external_urls=data.get("external_urls", {}),
        )

    def _convert_album(
        self, data: dict[str, Any], include_tracks: bool = False
    ) -> AlbumDTO:
        """
        Convert Spotify album JSON to AlbumDTO.

        Hey future me – Spotify album_type ist "album", "single", "compilation".
        Wir mappen das auf primary_type + secondary_types.
        """
        # Extract artist name (first artist)
        artists = data.get("artists", [])
        artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
        artist_spotify_id = artists[0].get("id") if artists else None

        # Pick best artwork (first is usually highest quality)
        artwork_url = None
        images = data.get("images", [])
        if images:
            artwork_url = images[0].get("url")

        # Map Spotify album_type to our types
        spotify_type = data.get("album_type", "album")
        primary_type = "Album"
        secondary_types: list[str] = []

        if spotify_type == "single":
            primary_type = "Single"
        elif spotify_type == "compilation":
            primary_type = "Album"
            secondary_types = ["Compilation"]
        elif spotify_type == "ep":
            primary_type = "EP"

        # Parse release year from release_date
        release_date = data.get("release_date", "")
        release_year = None
        if release_date:
            try:
                release_year = int(release_date[:4])
            except (ValueError, IndexError):
                pass

        album = AlbumDTO(
            title=data.get("name", "Unknown Album"),
            artist_name=artist_name,
            source_service="spotify",
            spotify_id=data.get("id"),
            spotify_uri=data.get("uri"),
            artist_spotify_id=artist_spotify_id,
            release_date=release_date,
            release_year=release_year,
            artwork_url=artwork_url,
            total_tracks=data.get("total_tracks"),
            album_type=spotify_type,
            primary_type=primary_type,
            secondary_types=secondary_types,
            genres=data.get("genres", []),
            label=data.get("label"),
            upc=data.get("external_ids", {}).get("upc"),
            external_urls=data.get("external_urls", {}),
        )

        # Include tracks if requested and available
        if include_tracks and "tracks" in data:
            tracks_data = data.get("tracks", {})
            items = tracks_data.get("items", [])
            album.tracks = [
                self._convert_track(t, album_data=data) for t in items if t
            ]

        return album

    def _convert_track(
        self, data: dict[str, Any], album_data: dict[str, Any] | None = None
    ) -> TrackDTO:
        """
        Convert Spotify track JSON to TrackDTO.

        Hey future me – Spotify simplified tracks (in Album) haben kein Album!
        Daher der album_data Parameter für Context aus dem Parent.

        Args:
            data: Track JSON from Spotify API
            album_data: Optional album JSON for context (for tracks in album)
        """
        # Extract primary artist
        artists = data.get("artists", [])
        artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
        artist_spotify_id = artists[0].get("id") if artists else None

        # Album info (from track or parent album_data)
        album = data.get("album") or album_data
        album_name = None
        album_spotify_id = None
        if album:
            album_name = album.get("name")
            album_spotify_id = album.get("id")

        # Extract ISRC (THE universal track identifier!)
        isrc = data.get("external_ids", {}).get("isrc")

        # Additional artists (features)
        additional_artists: list[ArtistDTO] = []
        if len(artists) > 1:
            for artist in artists[1:]:
                additional_artists.append(
                    ArtistDTO(
                        name=artist.get("name", "Unknown Artist"),
                        source_service="spotify",
                        spotify_id=artist.get("id"),
                        spotify_uri=artist.get("uri"),
                    )
                )

        return TrackDTO(
            title=data.get("name", "Unknown Track"),
            artist_name=artist_name,
            source_service="spotify",
            spotify_id=data.get("id"),
            spotify_uri=data.get("uri"),
            isrc=isrc,
            artist_spotify_id=artist_spotify_id,
            album_name=album_name,
            album_spotify_id=album_spotify_id,
            duration_ms=data.get("duration_ms", 0),
            track_number=data.get("track_number"),
            disc_number=data.get("disc_number", 1),
            explicit=data.get("explicit", False),
            popularity=data.get("popularity"),
            preview_url=data.get("preview_url"),
            external_urls=data.get("external_urls", {}),
            additional_artists=additional_artists,
        )

    def _convert_playlist(
        self, data: dict[str, Any], include_tracks: bool = False
    ) -> PlaylistDTO:
        """
        Convert Spotify playlist JSON to PlaylistDTO.
        """
        # Pick first image for cover
        cover_url = None
        images = data.get("images", [])
        if images:
            cover_url = images[0].get("url")

        # Owner info
        owner = data.get("owner", {})
        owner_name = owner.get("display_name") or owner.get("id")
        owner_id = owner.get("id")

        playlist = PlaylistDTO(
            name=data.get("name", "Unknown Playlist"),
            source_service="spotify",
            spotify_id=data.get("id"),
            spotify_uri=data.get("uri"),
            description=data.get("description"),
            cover_url=cover_url,
            is_public=data.get("public", True),
            is_collaborative=data.get("collaborative", False),
            total_tracks=data.get("tracks", {}).get("total"),
            owner_name=owner_name,
            owner_id=owner_id,
            snapshot_id=data.get("snapshot_id"),
            external_urls=data.get("external_urls", {}),
        )

        # Include tracks if requested
        if include_tracks and "tracks" in data:
            tracks_data = data.get("tracks", {})
            items = tracks_data.get("items", [])
            playlist.tracks = [
                self._convert_track(item.get("track", {}))
                for item in items
                if item and item.get("track")
            ]

        return playlist

    # =========================================================================
    # USER PROFILE
    # =========================================================================

    async def get_current_user(self) -> UserProfileDTO:
        """
        Get the current authenticated user's profile.
        """
        token = self._ensure_token()

        try:
            client = await self._client._get_client()
            response = await client.get(
                f"{self._client.API_BASE_URL}/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            # Pick best image
            image_url = None
            images = data.get("images", [])
            if images:
                image_url = images[0].get("url")

            return UserProfileDTO(
                display_name=data.get("display_name") or data.get("id", "Unknown"),
                source_service="spotify",
                spotify_id=data.get("id"),
                email=data.get("email"),
                country=data.get("country"),
                image_url=image_url,
                product=data.get("product"),
                external_urls=data.get("external_urls", {}),
            )
        except Exception as e:
            raise PluginError(
                message=f"Failed to get user profile: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # SEARCH
    # =========================================================================

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResultDTO:
        """
        Search for artists, albums, tracks, and playlists.
        """
        token = self._ensure_token()

        if types is None:
            types = ["artist", "album", "track", "playlist"]

        try:
            client = await self._client._get_client()
            params: dict[str, Any] = {
                "q": query,
                "type": ",".join(types),
                "limit": min(limit, 50),
                "offset": offset,
            }

            response = await client.get(
                f"{self._client.API_BASE_URL}/search",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            result = SearchResultDTO(
                query=query,
                source_service="spotify",
                offset=offset,
                limit=limit,
            )

            # Convert artists
            if "artists" in data:
                artists_data = data["artists"]
                result.artists = [
                    self._convert_artist(a) for a in artists_data.get("items", []) if a
                ]
                result.total_artists = artists_data.get("total", 0)

            # Convert albums
            if "albums" in data:
                albums_data = data["albums"]
                result.albums = [
                    self._convert_album(a) for a in albums_data.get("items", []) if a
                ]
                result.total_albums = albums_data.get("total", 0)

            # Convert tracks
            if "tracks" in data:
                tracks_data = data["tracks"]
                result.tracks = [
                    self._convert_track(t) for t in tracks_data.get("items", []) if t
                ]
                result.total_tracks = tracks_data.get("total", 0)

            # Convert playlists
            if "playlists" in data:
                playlists_data = data["playlists"]
                result.playlists = [
                    self._convert_playlist(p)
                    for p in playlists_data.get("items", [])
                    if p
                ]
                result.total_playlists = playlists_data.get("total", 0)

            return result

        except PluginError:
            raise
        except Exception as e:
            raise PluginError(
                message=f"Search failed: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # ARTISTS
    # =========================================================================

    async def get_artist(self, artist_id: str) -> ArtistDTO:
        """Get an artist by Spotify ID."""
        token = self._ensure_token()

        try:
            data = await self._client.get_artist(artist_id, token)
            return self._convert_artist(data)
        except Exception as e:
            raise PluginError(
                message=f"Failed to get artist {artist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_artist_albums(
        self,
        artist_id: str,
        include_groups: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[AlbumDTO]:
        """Get an artist's albums."""
        token = self._ensure_token()

        try:
            # SpotifyClient.get_artist_albums returns list directly
            # We need to use the raw endpoint for proper pagination
            client = await self._client._get_client()

            params: dict[str, Any] = {
                "limit": min(limit, 50),
                "offset": offset,
            }

            if include_groups:
                params["include_groups"] = ",".join(include_groups)
            else:
                params["include_groups"] = "album,single,compilation"

            response = await client.get(
                f"{self._client.API_BASE_URL}/artists/{artist_id}/albums",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            items = [
                self._convert_album(a) for a in data.get("items", []) if a
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except PluginError:
            raise
        except Exception as e:
            raise PluginError(
                message=f"Failed to get albums for artist {artist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_artist_top_tracks(
        self, artist_id: str, market: str | None = None
    ) -> list[TrackDTO]:
        """Get an artist's top tracks."""
        token = self._ensure_token()

        try:
            data = await self._client.get_artist_top_tracks(
                artist_id, token, market or "US"
            )
            return [self._convert_track(t) for t in data if t]
        except Exception as e:
            raise PluginError(
                message=f"Failed to get top tracks for artist {artist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_followed_artists(
        self, limit: int = 50, after: str | None = None
    ) -> PaginatedResponse[ArtistDTO]:
        """Get artists followed by the current user."""
        token = self._ensure_token()

        try:
            data = await self._client.get_followed_artists(token, limit, after)

            artists_data = data.get("artists", {})
            items = [
                self._convert_artist(a) for a in artists_data.get("items", []) if a
            ]
            total = artists_data.get("total", len(items))

            # Spotify uses cursor pagination (after), not offset
            cursors = artists_data.get("cursors", {})
            next_cursor = cursors.get("after")

            return PaginatedResponse(
                items=items,
                total=total,
                offset=0,  # Cursor-based, so offset is not meaningful
                limit=limit,
                next_offset=1 if next_cursor else None,  # Signal there's more
            )

        except Exception as e:
            raise PluginError(
                message=f"Failed to get followed artists: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # ALBUMS
    # =========================================================================

    async def get_album(self, album_id: str) -> AlbumDTO:
        """Get an album by Spotify ID."""
        token = self._ensure_token()

        try:
            data = await self._client.get_album(album_id, token)
            return self._convert_album(data, include_tracks=True)
        except Exception as e:
            raise PluginError(
                message=f"Failed to get album {album_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get tracks from an album."""
        token = self._ensure_token()

        try:
            data = await self._client.get_album_tracks(album_id, token, limit, offset)

            items = [
                self._convert_track(t) for t in data.get("items", []) if t
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except Exception as e:
            raise PluginError(
                message=f"Failed to get tracks for album {album_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # TRACKS
    # =========================================================================

    async def get_track(self, track_id: str) -> TrackDTO:
        """Get a track by Spotify ID."""
        token = self._ensure_token()

        try:
            data = await self._client.get_track(track_id, token)
            return self._convert_track(data)
        except Exception as e:
            raise PluginError(
                message=f"Failed to get track {track_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_tracks(self, track_ids: list[str]) -> list[TrackDTO]:
        """Get multiple tracks by IDs (batch request)."""
        token = self._ensure_token()

        if not track_ids:
            return []

        try:
            client = await self._client._get_client()

            # Spotify allows max 50 tracks per request
            results: list[TrackDTO] = []
            for i in range(0, len(track_ids), 50):
                chunk = track_ids[i : i + 50]
                ids_param = ",".join(chunk)

                response = await client.get(
                    f"{self._client.API_BASE_URL}/tracks",
                    params={"ids": ids_param},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                data = response.json()

                tracks = data.get("tracks", [])
                results.extend([
                    self._convert_track(t) for t in tracks if t
                ])

            return results

        except PluginError:
            raise
        except Exception as e:
            raise PluginError(
                message=f"Failed to get tracks: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # PLAYLISTS
    # =========================================================================

    async def get_playlist(self, playlist_id: str) -> PlaylistDTO:
        """Get a playlist by Spotify ID."""
        token = self._ensure_token()

        try:
            data = await self._client.get_playlist(playlist_id, token)
            return self._convert_playlist(data, include_tracks=True)
        except Exception as e:
            raise PluginError(
                message=f"Failed to get playlist {playlist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get tracks from a playlist."""
        token = self._ensure_token()

        try:
            client = await self._client._get_client()

            response = await client.get(
                f"{self._client.API_BASE_URL}/playlists/{playlist_id}/tracks",
                params={"limit": min(limit, 100), "offset": offset},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            items = [
                self._convert_track(item.get("track", {}))
                for item in data.get("items", [])
                if item and item.get("track")
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except PluginError:
            raise
        except Exception as e:
            raise PluginError(
                message=f"Failed to get tracks for playlist {playlist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[PlaylistDTO]:
        """Get playlists owned or followed by the current user."""
        token = self._ensure_token()

        try:
            data = await self._client.get_user_playlists(token, limit, offset)

            items = [
                self._convert_playlist(p) for p in data.get("items", []) if p
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except Exception as e:
            raise PluginError(
                message=f"Failed to get user playlists: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # LIBRARY (SAVED ITEMS)
    # =========================================================================

    async def get_saved_tracks(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[TrackDTO]:
        """Get user's saved/liked tracks."""
        token = self._ensure_token()

        try:
            data = await self._client.get_saved_tracks(token, limit, offset)

            # Saved tracks have {added_at, track} structure
            items = [
                self._convert_track(item.get("track", {}))
                for item in data.get("items", [])
                if item and item.get("track")
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except Exception as e:
            raise PluginError(
                message=f"Failed to get saved tracks: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_saved_albums(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse[AlbumDTO]:
        """Get user's saved albums."""
        token = self._ensure_token()

        try:
            data = await self._client.get_saved_albums(token, limit, offset)

            # Saved albums have {added_at, album} structure
            items = [
                self._convert_album(item.get("album", {}))
                for item in data.get("items", [])
                if item and item.get("album")
            ]
            total = data.get("total", len(items))
            next_url = data.get("next")
            next_offset = offset + len(items) if next_url else None

            return PaginatedResponse(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                next_offset=next_offset,
            )

        except Exception as e:
            raise PluginError(
                message=f"Failed to get saved albums: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # BATCH OPERATIONS (nicht im Interface, aber nützlich!)
    # =========================================================================

    async def get_several_artists(self, artist_ids: list[str]) -> list[ArtistDTO]:
        """
        Get multiple artists by IDs (batch request, max 50).

        Hey future me – das ist der PERFORMANCE-BOOSTER für Playlist-Imports!
        Statt 100 einzelne Requests → 2 Batch-Requests.

        Args:
            artist_ids: List of Spotify artist IDs (max 50 per call)

        Returns:
            List of ArtistDTOs
        """
        token = self._ensure_token()

        if not artist_ids:
            return []

        try:
            data = await self._client.get_several_artists(artist_ids, token)
            return [self._convert_artist(a) for a in data if a]
        except Exception as e:
            raise PluginError(
                message=f"Failed to get artists batch: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def get_several_albums(self, album_ids: list[str]) -> list[AlbumDTO]:
        """
        Get multiple albums by IDs (batch request, max 20).

        Args:
            album_ids: List of Spotify album IDs (max 20 per call)

        Returns:
            List of AlbumDTOs
        """
        token = self._ensure_token()

        if not album_ids:
            return []

        try:
            data = await self._client.get_albums(album_ids, token)
            return [self._convert_album(a) for a in data if a]
        except Exception as e:
            raise PluginError(
                message=f"Failed to get albums batch: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # RELATED ARTISTS (Discovery Feature)
    # =========================================================================

    async def get_related_artists(self, artist_id: str) -> list[ArtistDTO]:
        """
        Get artists similar to a given artist.

        Hey future me – super nützlich für "Fans Also Like" Feature!
        Spotify gibt bis zu 20 ähnliche Artists zurück.

        Args:
            artist_id: Spotify artist ID

        Returns:
            List of related ArtistDTOs (up to 20)
        """
        token = self._ensure_token()

        try:
            data = await self._client.get_related_artists(artist_id, token)
            return [self._convert_artist(a) for a in data if a]
        except Exception as e:
            raise PluginError(
                message=f"Failed to get related artists for {artist_id}: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    # =========================================================================
    # FOLLOW/UNFOLLOW ARTISTS
    # =========================================================================

    async def follow_artists(self, artist_ids: list[str]) -> None:
        """
        Follow one or more artists on Spotify.

        Hey future me – nach dem Follow erscheint Artist in get_followed_artists()!

        Args:
            artist_ids: List of Spotify artist IDs to follow (max 50)
        """
        token = self._ensure_token()

        if not artist_ids:
            return

        try:
            await self._client.follow_artist(artist_ids, token)
        except Exception as e:
            raise PluginError(
                message=f"Failed to follow artists: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def unfollow_artists(self, artist_ids: list[str]) -> None:
        """
        Unfollow one or more artists on Spotify.

        Args:
            artist_ids: List of Spotify artist IDs to unfollow (max 50)
        """
        token = self._ensure_token()

        if not artist_ids:
            return

        try:
            await self._client.unfollow_artist(artist_ids, token)
        except Exception as e:
            raise PluginError(
                message=f"Failed to unfollow artists: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e

    async def check_following_artists(self, artist_ids: list[str]) -> dict[str, bool]:
        """
        Check if user follows specific artists.

        Hey future me – nutze das für "Following"/"Follow" Button-State!

        Args:
            artist_ids: List of Spotify artist IDs to check (max 50)

        Returns:
            Dict mapping artist_id -> is_following (True/False)
        """
        token = self._ensure_token()

        if not artist_ids:
            return {}

        try:
            results = await self._client.check_if_following_artists(artist_ids, token)
            return dict(zip(artist_ids, results))
        except Exception as e:
            raise PluginError(
                message=f"Failed to check following status: {e!s}",
                service=ServiceType.SPOTIFY,
                original_error=e,
            ) from e


# Export
__all__ = ["SpotifyPlugin"]
