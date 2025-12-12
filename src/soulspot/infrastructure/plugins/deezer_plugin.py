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
- OAuth für User-Library Zugriff (PRO mode)
- Rate Limit: ~50 requests/5 seconds
- ISRC verfügbar bei Tracks (gut für Cross-Service Matching!)
- Kostenlos, keine Premium-Einschränkungen

Implementierte Features (NO AUTH!):
- search() - Suche nach Artists, Albums, Tracks
- get_artist(), get_album(), get_track() - Einzelne Ressourcen
- get_artist_albums() - Alle Alben eines Artists
- get_browse_new_releases() - Editorial + Chart Albums
- get_editorial_releases() - Kuratierte Neuerscheinungen
- get_chart_albums() - Top-Charts
- get_genres() - Genre-Liste

Noch nicht implementiert (benötigen OAuth):
- get_followed_artists() - Braucht OAuth
- get_saved_tracks/albums() - Braucht OAuth
- get_user_playlists() - Braucht OAuth
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
    """

    def __init__(self, client: DeezerClient | None = None) -> None:
        """
        Initialize Deezer plugin.

        Args:
            client: Optional DeezerClient instance. Creates new one if not provided.
        """
        self._client = client or DeezerClient()

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
                artists=artists,
                albums=albums,
                tracks=tracks,
                playlists=[],  # Deezer playlist search not implemented
                query=query,
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
        """Get artist's albums from Deezer.

        Hey future me – Deezer Artist-Albums braucht KEINE Auth!

        Args:
            artist_id: Deezer artist ID
            include_groups: Not used (Deezer returns all types)
            limit: Maximum albums to return
            offset: Pagination offset

        Returns:
            PaginatedResponse with artist's albums
        """
        try:
            deezer_albums = await self._client.get_artist_albums(
                int(artist_id), limit=limit
            )
            albums = [self._convert_album(a) for a in deezer_albums]

            return PaginatedResponse(
                items=albums,
                total=len(albums),
                limit=limit,
                offset=offset,
                has_more=False,  # Deezer returns all at once
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
        """Get followed artists (requires OAuth - NOT IMPLEMENTED)."""
        raise PluginError(
            message="Deezer followed artists requires OAuth (not implemented)",
            service=ServiceType.DEEZER,
            error_code="oauth_required",
        )

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
                has_more=False,
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
            spotify_id=None,  # No Spotify ID for Deezer artists
            name=deezer_artist.name,
            genres=[],  # Deezer doesn't return genres on artist object
            popularity=None,
            image_url=deezer_artist.picture_big or deezer_artist.picture_medium,
            external_url=deezer_artist.link,
            followers=deezer_artist.nb_fan,
            extra={
                "deezer_id": deezer_artist.id,
                "picture_small": deezer_artist.picture_small,
                "picture_medium": deezer_artist.picture_medium,
                "picture_big": deezer_artist.picture_big,
                "picture_xl": deezer_artist.picture_xl,
                "nb_album": deezer_artist.nb_album,
            },
        )

    def _convert_album(self, deezer_album: DeezerAlbum) -> AlbumDTO:
        """Convert DeezerAlbum to AlbumDTO.

        Hey future me – der zentrale Album-Konverter!
        Wird von allen Methoden genutzt die Alben zurückgeben.

        Args:
            deezer_album: DeezerAlbum dataclass from deezer_client

        Returns:
            Standard AlbumDTO
        """
        return AlbumDTO(
            id=str(deezer_album.id),
            name=deezer_album.title,
            artist_name=deezer_album.artist_name,
            artist_id=str(deezer_album.artist_id) if deezer_album.artist_id else None,
            release_date=deezer_album.release_date,
            total_tracks=deezer_album.nb_tracks or 0,
            album_type=deezer_album.record_type or "album",
            image_url=deezer_album.cover_big or deezer_album.cover_medium,
            external_url=deezer_album.link,
            service=ServiceType.DEEZER,
            extra={
                "deezer_id": deezer_album.id,
                "cover_small": deezer_album.cover_small,
                "cover_medium": deezer_album.cover_medium,
                "cover_big": deezer_album.cover_big,
                "cover_xl": deezer_album.cover_xl,
                "explicit": deezer_album.explicit_lyrics,
                "record_type": deezer_album.record_type,
                "upc": deezer_album.upc,
                "duration": deezer_album.duration,
            },
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
            id=str(deezer_track.id),
            name=deezer_track.title,
            artist_name=deezer_track.artist_name,
            artist_id=str(deezer_track.artist_id) if deezer_track.artist_id else None,
            album_name=deezer_track.album_title,
            album_id=str(deezer_track.album_id) if deezer_track.album_id else None,
            duration_ms=deezer_track.duration * 1000,  # Convert seconds to ms
            track_number=deezer_track.track_position,
            disc_number=deezer_track.disk_number,
            isrc=deezer_track.isrc,  # GOLD for cross-service matching!
            explicit=deezer_track.explicit_lyrics,
            service=ServiceType.DEEZER,
            extra={
                "deezer_id": deezer_track.id,
                "preview_url": deezer_track.preview,
            },
        )

    # Legacy alias for backwards compatibility
    def _convert_album_to_dto(self, deezer_album: DeezerAlbum) -> AlbumDTO:
        """Legacy alias - use _convert_album instead."""
        return self._convert_album(deezer_album)


# Export
__all__ = ["DeezerPlugin"]
