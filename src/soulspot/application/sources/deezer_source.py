"""Deezer Import Source.

Hey future me - THIS WRAPS DEEZER PLUGIN!
Deezer has some public APIs (no auth needed for browse)
but requires auth for favorites/playlists.

The source:
- Checks if Deezer is enabled
- For favorites: checks authentication
- For browse: works without auth
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, PlaylistDTO, TrackDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

logger = logging.getLogger(__name__)


class DeezerImportSource:
    """Import source for Deezer.
    
    Hey future me - wraps DeezerPlugin for UnifiedLibraryManager!
    
    IMPORTANT: Deezer has public APIs that don't need auth!
    - Artist lookup, album search: NO AUTH
    - User favorites, playlists: AUTH REQUIRED
    
    Usage:
        source = DeezerImportSource(deezer_plugin)
        if source.is_available:
            artists = await source.import_artists()
    """
    
    def __init__(self, plugin: "DeezerPlugin | None") -> None:
        """Initialize with DeezerPlugin.
        
        Args:
            plugin: DeezerPlugin instance (can be None if not configured)
        """
        self._plugin = plugin
    
    @property
    def name(self) -> str:
        """Source name."""
        return "deezer"
    
    @property
    def is_available(self) -> bool:
        """True if Deezer plugin is configured.
        
        Note: Deezer public APIs work without auth.
        User favorites/playlists require auth.
        """
        if not self._plugin:
            return False
        # For artists import, we need user favorites (requires auth)
        from soulspot.domain.ports.plugin import PluginCapability
        return self._plugin.can_use(PluginCapability.USER_FAVORITE_ARTISTS)
    
    @property
    def is_available_for_browse(self) -> bool:
        """True if Deezer can be used for public browse (no auth needed)."""
        if not self._plugin:
            return False
        from soulspot.domain.ports.plugin import PluginCapability
        return self._plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES)
    
    async def import_artists(self) -> list["ArtistDTO"]:
        """Import favorite artists from Deezer.
        
        Requires user authentication!
        
        Returns:
            List of ArtistDTOs from Deezer favorites
        """
        if not self._plugin or not self.is_available:
            return []
        
        all_artists: list["ArtistDTO"] = []
        offset = 0
        
        while True:
            try:
                response = await self._plugin.get_favorite_artists(
                    limit=100,
                    offset=offset,
                )
                
                if not response.items:
                    break
                
                all_artists.extend(response.items)
                
                if response.next_offset:
                    offset = response.next_offset
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Deezer artist import failed: {e}")
                break
        
        logger.info(f"Imported {len(all_artists)} artists from Deezer")
        return all_artists
    
    async def import_albums_for_artist(
        self,
        artist_id: str,
        artist_name: str | None = None,
    ) -> list["AlbumDTO"]:
        """Import albums for a specific artist from Deezer.
        
        Hey future me - this can work with EITHER:
        - artist_id (direct Deezer ID)
        - artist_name (search by name, if no ID)
        
        Public API - no auth required!
        
        Args:
            artist_id: Deezer artist ID
            artist_name: Artist name for search fallback
        
        Returns:
            List of AlbumDTOs for this artist
        """
        if not self._plugin:
            return []
        
        # If no artist_id but have name, try to search first
        resolved_id = artist_id
        if not resolved_id and artist_name:
            try:
                search_result = await self._plugin.search_artists(
                    query=artist_name,
                    limit=1,
                )
                if search_result.items:
                    resolved_id = search_result.items[0].deezer_id
            except Exception as e:
                logger.debug(f"Deezer artist search failed for '{artist_name}': {e}")
                return []
        
        if not resolved_id:
            return []
        
        all_albums: list["AlbumDTO"] = []
        offset = 0
        
        while True:
            try:
                response = await self._plugin.get_artist_albums(
                    artist_id=resolved_id,
                    limit=100,
                    offset=offset,
                )
                
                if not response.items:
                    break
                
                all_albums.extend(response.items)
                
                if response.next_offset:
                    offset = response.next_offset
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Deezer album import failed for {resolved_id}: {e}")
                break
        
        return all_albums
    
    async def import_tracks_for_album(
        self,
        album_id: str,
    ) -> list["TrackDTO"]:
        """Import tracks for a specific album from Deezer.
        
        Public API - no auth required!
        
        Args:
            album_id: Deezer album ID
        
        Returns:
            List of TrackDTOs for this album
        """
        if not self._plugin:
            return []
        
        try:
            response = await self._plugin.get_album_tracks(
                album_id=album_id,
                limit=200,  # Most albums have < 200 tracks
            )
            return list(response.items) if response.items else []
        except Exception as e:
            logger.error(f"Deezer track import failed for album {album_id}: {e}")
            return []
    
    async def import_playlists(self) -> list["PlaylistDTO"]:
        """Import user playlists from Deezer.
        
        Requires user authentication!
        
        Returns:
            List of PlaylistDTOs
        """
        if not self._plugin or not self.is_available:
            return []
        
        from soulspot.domain.ports.plugin import PluginCapability
        if not self._plugin.can_use(PluginCapability.USER_PLAYLISTS):
            return []
        
        all_playlists: list["PlaylistDTO"] = []
        offset = 0
        
        while True:
            try:
                response = await self._plugin.get_user_playlists(
                    limit=100,
                    offset=offset,
                )
                
                if not response.items:
                    break
                
                all_playlists.extend(response.items)
                
                if response.next_offset:
                    offset = response.next_offset
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Deezer playlist import failed: {e}")
                break
        
        return all_playlists
