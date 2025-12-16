"""
Provider Mapping Service - Maps external service IDs to internal UUIDs.

Hey future me – REFACTORED für Clean Architecture!
Dieser Service nutzt jetzt Repositories statt direkte Model-Zugriffe.

Problem it solves:
- Plugins return DTOs with spotify_id, deezer_id, etc.
- SoulSpot services need internal UUIDs
- Without mapping, we'd have ID confusion everywhere

Usage Pattern:
1. Call plugin to get data → Plugin returns DTO with service IDs
2. Pass DTO through mapper → Mapper adds internal_id if entity exists in DB
3. Use mapped DTO in service → Now has both service_id AND internal_id

Clean Architecture:
- Application Layer: ProviderMappingService (orchestration)
- Domain Layer: Artist, Album, Track entities; ArtistId, AlbumId, TrackId value objects
- Infrastructure Layer: ArtistRepository, AlbumRepository, TrackRepository

Example:
    mapper = ProviderMappingService(session)
    
    # Artist lookup with internal ID resolution
    artist_dto = await spotify_plugin.get_artist("0TnOYISbd1XYRBk9myaseg")
    mapped_dto = await mapper.map_artist_dto(artist_dto)
    # mapped_dto.internal_id is now set if artist exists in DB

Key Principle:
- DTOs carry both external IDs (for API calls) AND internal IDs (for DB operations)
- Repositories handle ALL database access (no direct Model usage!)
- This service is pure orchestration - no business logic
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Album, Artist, ArtistSource, Track
from soulspot.domain.value_objects import AlbumId, ArtistId, SpotifyUri, TrackId
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, TrackDTO

logger = logging.getLogger(__name__)


class ProviderMappingService:
    """Maps external service IDs to internal UUIDs via Repositories.
    
    Hey future me – this is the SINGLE POINT for ID translation!
    All ID lookups and creations go through here.
    
    CLEAN ARCHITECTURE:
    - Uses Repositories, not direct Model access
    - Creates Domain Entities, not ORM Models
    - Returns UUIDs as strings for DTO compatibility
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session for repository access.
        
        Hey future me – wir erstellen Repositories hier statt sie zu injecten,
        weil dieser Service ein "Helper" ist, kein Full-Service mit eigener DI.
        Die Session wird durchgereicht, das ist der wichtige Teil.
        """
        self._session = session
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)

    # =========================================================================
    # ARTIST MAPPING
    # =========================================================================

    async def map_artist_dto(self, dto: ArtistDTO) -> ArtistDTO:
        """Add internal_id to ArtistDTO if artist exists in database.
        
        Hey future me – this does NOT create the artist, just adds the internal_id
        if we find a match. Use get_or_create_artist() to create if needed.
        
        Lookup order:
        1. spotify_uri (most reliable for Spotify data)
        2. deezer_id (for Deezer data)
        3. Name matching (fallback)
        
        Returns:
            Same DTO with internal_id set (or None if not found)
        """
        internal_id: str | None = None

        # Try Spotify URI first
        if not internal_id and dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
                artist = await self._artist_repo.get_by_spotify_uri(spotify_uri)
                if artist:
                    internal_id = str(artist.id.value)
            except ValueError:
                pass

        # Try Deezer ID
        if not internal_id and dto.deezer_id:
            artist = await self._artist_repo.get_by_deezer_id(dto.deezer_id)
            if artist:
                internal_id = str(artist.id.value)

        # Try name match as fallback
        if not internal_id and dto.name:
            artist = await self._artist_repo.get_by_name(dto.name)
            if artist:
                internal_id = str(artist.id.value)
                logger.debug(f"Matched artist '{dto.name}' by name to {internal_id}")

        dto.internal_id = internal_id
        return dto

    # Backwards compatibility alias
    async def map_artist(self, dto: ArtistDTO) -> ArtistDTO:
        """Alias for map_artist_dto (backwards compatibility)."""
        return await self.map_artist_dto(dto)

    async def get_or_create_artist(
        self,
        dto: ArtistDTO,
        source: str = "spotify",
    ) -> tuple[str, bool]:
        """Get existing artist UUID or create new one.
        
        Hey future me – this is the CREATE-IF-NOT-EXISTS pattern via Repository.
        Returns (internal_uuid, was_created).
        
        Args:
            dto: Artist data from plugin
            source: Source to use if creating ('local', 'spotify', 'deezer')
        
        Returns:
            Tuple of (internal UUID string, was_created boolean)
        """
        # First try to find existing
        mapped_dto = await self.map_artist_dto(dto)
        if mapped_dto.internal_id:
            return mapped_dto.internal_id, False

        # Not found - create new artist via Repository
        artist_source = self._parse_source(source)
        
        # Build SpotifyUri if we have spotify_id
        spotify_uri = None
        if dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
            except ValueError:
                pass
        elif dto.spotify_id:
            spotify_uri = SpotifyUri.from_string(f"spotify:artist:{dto.spotify_id}")

        new_artist = Artist(
            id=ArtistId.generate(),
            name=dto.name,
            source=artist_source,
            spotify_uri=spotify_uri,
            deezer_id=dto.deezer_id,
            tidal_id=dto.tidal_id,
            musicbrainz_id=dto.musicbrainz_id,
            artwork_url=dto.artwork_url,
            genres=dto.genres or [],
            tags=dto.tags or [],
            disambiguation=dto.disambiguation,
            popularity=dto.popularity,
            followers=dto.followers,
        )

        await self._artist_repo.add(new_artist)
        logger.info(f"Created new artist: {dto.name} ({source})")

        return str(new_artist.id.value), True

    # Backwards compatibility alias
    async def ensure_artist_exists(
        self,
        dto: ArtistDTO,
        source: str = "spotify",
    ) -> str:
        """Alias for get_or_create_artist (returns just UUID for backwards compat)."""
        uuid_str, _ = await self.get_or_create_artist(dto, source)
        return uuid_str

    async def get_artist_uuid_by_spotify_id(self, spotify_id: str) -> str | None:
        """Get internal UUID for a Spotify artist ID."""
        spotify_uri = SpotifyUri.from_string(f"spotify:artist:{spotify_id}")
        artist = await self._artist_repo.get_by_spotify_uri(spotify_uri)
        return str(artist.id.value) if artist else None

    async def get_artist_uuid_by_deezer_id(self, deezer_id: str) -> str | None:
        """Get internal UUID for a Deezer artist ID."""
        artist = await self._artist_repo.get_by_deezer_id(deezer_id)
        return str(artist.id.value) if artist else None

    # =========================================================================
    # ALBUM MAPPING
    # =========================================================================

    async def map_album_dto(self, dto: AlbumDTO) -> AlbumDTO:
        """Add internal_id to AlbumDTO if album exists in database.
        
        Lookup order:
        1. spotify_uri
        2. deezer_id
        
        Returns:
            Same DTO with internal_id set (or None if not found)
        """
        internal_id: str | None = None

        # Try Spotify URI first
        if not internal_id and dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
                album = await self._album_repo.get_by_spotify_uri(spotify_uri)
                if album:
                    internal_id = str(album.id.value)
            except ValueError:
                pass

        # Try Deezer ID
        if not internal_id and dto.deezer_id:
            album = await self._album_repo.get_by_deezer_id(dto.deezer_id)
            if album:
                internal_id = str(album.id.value)

        dto.internal_id = internal_id
        return dto

    # Backwards compatibility alias
    async def map_album(self, dto: AlbumDTO) -> AlbumDTO:
        """Alias for map_album_dto (backwards compatibility)."""
        return await self.map_album_dto(dto)

    async def get_or_create_album(
        self,
        dto: AlbumDTO,
        artist_internal_id: str,
        source: str = "spotify",
    ) -> tuple[str, bool]:
        """Get existing album UUID or create new one.
        
        Args:
            dto: Album data from plugin
            artist_internal_id: Internal UUID of the artist (must exist!)
            source: Source to use if creating
        
        Returns:
            Tuple of (internal UUID string, was_created boolean)
        """
        # First try to find existing
        mapped_dto = await self.map_album_dto(dto)
        if mapped_dto.internal_id:
            return mapped_dto.internal_id, False

        # Not found - create new album via Repository
        spotify_uri = None
        if dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
            except ValueError:
                pass
        elif dto.spotify_id:
            spotify_uri = SpotifyUri.from_string(f"spotify:album:{dto.spotify_id}")

        new_album = Album(
            id=AlbumId.generate(),
            title=dto.title,
            artist_id=ArtistId(artist_internal_id),
            source=self._parse_source(source),
            spotify_uri=spotify_uri,
            deezer_id=dto.deezer_id,
            tidal_id=dto.tidal_id,
            musicbrainz_id=dto.musicbrainz_id,
            artwork_url=dto.artwork_url,
            release_date=dto.release_date,
            release_year=dto.release_year,
            primary_type=dto.album_type or "album",
            secondary_types=dto.secondary_types or [],
            total_tracks=dto.total_tracks,
        )

        await self._album_repo.add(new_album)
        logger.info(f"Created new album: {dto.title} ({source})")

        return str(new_album.id.value), True

    # Backwards compatibility alias
    async def ensure_album_exists(
        self,
        dto: AlbumDTO,
        artist_internal_id: str,
        source: str = "spotify",
    ) -> str:
        """Alias for get_or_create_album (returns just UUID for backwards compat)."""
        uuid_str, _ = await self.get_or_create_album(dto, artist_internal_id, source)
        return uuid_str

    async def get_album_uuid_by_spotify_id(self, spotify_id: str) -> str | None:
        """Get internal UUID for a Spotify album ID."""
        spotify_uri = SpotifyUri.from_string(f"spotify:album:{spotify_id}")
        album = await self._album_repo.get_by_spotify_uri(spotify_uri)
        return str(album.id.value) if album else None

    async def get_album_uuid_by_deezer_id(self, deezer_id: str) -> str | None:
        """Get internal UUID for a Deezer album ID."""
        album = await self._album_repo.get_by_deezer_id(deezer_id)
        return str(album.id.value) if album else None

    # =========================================================================
    # TRACK MAPPING
    # =========================================================================

    async def map_track_dto(self, dto: TrackDTO) -> TrackDTO:
        """Add internal_id to TrackDTO if track exists in database.
        
        Lookup order:
        1. ISRC (international standard, best for matching)
        2. spotify_uri
        3. deezer_id
        
        Returns:
            Same DTO with internal_id set (or None if not found)
        """
        internal_id: str | None = None

        # ISRC is the BEST identifier
        if not internal_id and dto.isrc:
            track = await self._track_repo.get_by_isrc(dto.isrc)
            if track:
                internal_id = str(track.id.value)

        # Try Spotify URI
        if not internal_id and dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
                track = await self._track_repo.get_by_spotify_uri(spotify_uri)
                if track:
                    internal_id = str(track.id.value)
            except ValueError:
                pass

        # Try Deezer ID
        if not internal_id and dto.deezer_id:
            track = await self._track_repo.get_by_deezer_id(dto.deezer_id)
            if track:
                internal_id = str(track.id.value)

        dto.internal_id = internal_id
        return dto

    # Backwards compatibility alias
    async def map_track(self, dto: TrackDTO) -> TrackDTO:
        """Alias for map_track_dto (backwards compatibility)."""
        return await self.map_track_dto(dto)

    async def get_or_create_track(
        self,
        dto: TrackDTO,
        artist_internal_id: str,
        album_internal_id: str | None = None,
        source: str = "spotify",
    ) -> tuple[str, bool]:
        """Get existing track UUID or create new one.
        
        Args:
            dto: Track data from plugin
            artist_internal_id: Internal UUID of the artist (must exist!)
            album_internal_id: Internal UUID of the album (optional for singles)
            source: Source to use if creating
        
        Returns:
            Tuple of (internal UUID string, was_created boolean)
        """
        # First try to find existing
        mapped_dto = await self.map_track_dto(dto)
        if mapped_dto.internal_id:
            return mapped_dto.internal_id, False

        # Not found - create new track via Repository
        spotify_uri = None
        if dto.spotify_uri:
            try:
                spotify_uri = SpotifyUri.from_string(dto.spotify_uri)
            except ValueError:
                pass
        elif dto.spotify_id:
            spotify_uri = SpotifyUri.from_string(f"spotify:track:{dto.spotify_id}")

        new_track = Track(
            id=TrackId.generate(),
            title=dto.title,
            artist_id=ArtistId(artist_internal_id),
            album_id=AlbumId(album_internal_id) if album_internal_id else None,
            source=self._parse_source(source),
            spotify_uri=spotify_uri,
            deezer_id=dto.deezer_id,
            tidal_id=dto.tidal_id,
            musicbrainz_id=dto.musicbrainz_id,
            isrc=dto.isrc,
            duration_ms=dto.duration_ms,
            track_number=dto.track_number,
            disc_number=dto.disc_number,
            explicit=dto.explicit,
        )

        await self._track_repo.add(new_track)
        logger.info(f"Created new track: {dto.title} ({source})")

        return str(new_track.id.value), True

    # Backwards compatibility alias
    async def ensure_track_exists(
        self,
        dto: TrackDTO,
        artist_internal_id: str,
        album_internal_id: str | None = None,
        source: str = "spotify",
    ) -> str:
        """Alias for get_or_create_track (returns just UUID for backwards compat)."""
        uuid_str, _ = await self.get_or_create_track(dto, artist_internal_id, album_internal_id, source)
        return uuid_str

    async def get_track_uuid_by_isrc(self, isrc: str) -> str | None:
        """Get internal UUID for a track by ISRC."""
        track = await self._track_repo.get_by_isrc(isrc)
        return str(track.id.value) if track else None

    async def get_track_uuid_by_spotify_id(self, spotify_id: str) -> str | None:
        """Get internal UUID for a Spotify track ID."""
        spotify_uri = SpotifyUri.from_string(f"spotify:track:{spotify_id}")
        track = await self._track_repo.get_by_spotify_uri(spotify_uri)
        return str(track.id.value) if track else None

    # =========================================================================
    # BATCH MAPPING
    # =========================================================================

    async def map_artists_batch(self, dtos: list[ArtistDTO]) -> list[ArtistDTO]:
        """Map multiple artists at once."""
        for dto in dtos:
            await self.map_artist_dto(dto)
        return dtos

    async def map_albums_batch(self, dtos: list[AlbumDTO]) -> list[AlbumDTO]:
        """Map multiple albums at once."""
        for dto in dtos:
            await self.map_album_dto(dto)
        return dtos

    async def map_tracks_batch(self, dtos: list[TrackDTO]) -> list[TrackDTO]:
        """Map multiple tracks at once."""
        for dto in dtos:
            await self.map_track_dto(dto)
        return dtos

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _parse_source(source: str) -> ArtistSource:
        """Convert source string to ArtistSource enum.
        
        Hey future me – wir haben nur LOCAL, SPOTIFY, HYBRID.
        Deezer und Tidal werden als SPOTIFY behandelt (external service).
        """
        source_lower = source.lower()
        if source_lower == "local":
            return ArtistSource.LOCAL
        if source_lower in ("spotify", "deezer", "tidal"):
            return ArtistSource.SPOTIFY
        if source_lower == "hybrid":
            return ArtistSource.HYBRID
        return ArtistSource.SPOTIFY


# Export for easy imports
__all__ = ["ProviderMappingService"]
