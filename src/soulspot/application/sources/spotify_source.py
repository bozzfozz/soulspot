"""Spotify Import Source.

Hey future me - THIS WRAPS SPOTIFY PLUGIN!
Instead of calling SpotifyPlugin directly in workers,
we go through this ImportSource abstraction.

The source:
- Checks if Spotify is enabled + authenticated
- Wraps plugin calls with error handling
- Converts responses to standard DTOs
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, PlaylistDTO, TrackDTO
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class SpotifyImportSource:
    """Import source for Spotify.
    
    Hey future me - wraps SpotifyPlugin for UnifiedLibraryManager!
    
    Usage:
        source = SpotifyImportSource(spotify_plugin)
        if source.is_available:
            artists = await source.import_artists()
    """
    
    def __init__(self, plugin: "SpotifyPlugin | None") -> None:
        """Initialize with SpotifyPlugin.
        
        Args:
            plugin: SpotifyPlugin instance (can be None if not configured)
        """
        self._plugin = plugin
    
    @property
    def name(self) -> str:
        """Source name."""
        return "spotify"
    
    @property
    def is_available(self) -> bool:
        """True if Spotify plugin is configured AND authenticated."""
        if not self._plugin:
            return False
        # Check if plugin has valid authentication
        from soulspot.domain.ports.plugin import PluginCapability
        return self._plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS)
    
    async def import_artists(self) -> list["ArtistDTO"]:
        """Import followed artists from Spotify.
        
        Handles pagination automatically via SpotifyPlugin.
        
        Returns:
            List of ArtistDTOs from Spotify
        """
        if not self._plugin or not self.is_available:
            return []
        
        all_artists: list["ArtistDTO"] = []
        after_cursor: str | None = None
        
        while True:
            try:
                response = await self._plugin.get_followed_artists(
                    limit=50,
                    after=after_cursor,
                )
                
                if not response.items:
                    break
                
                all_artists.extend(response.items)
                
                # Get next cursor for pagination
                if response.next_offset and response.items:
                    after_cursor = response.items[-1].spotify_id
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Spotify artist import failed: {e}")
                break
        
        logger.info(f"Imported {len(all_artists)} artists from Spotify")
        return all_artists
    
    async def import_albums_for_artist(
        self,
        artist_id: str,
        artist_name: str | None = None,
    ) -> list["AlbumDTO"]:
        """Import albums for a specific artist from Spotify.
        
        Args:
            artist_id: Spotify artist ID
            artist_name: Not used for Spotify (has direct ID lookup)
        
        Returns:
            List of AlbumDTOs for this artist
        """
        if not self._plugin:
            return []
        
        from soulspot.domain.ports.plugin import PluginCapability
        if not self._plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
            return []
        
        all_albums: list["AlbumDTO"] = []
        offset = 0
        
        while True:
            try:
                response = await self._plugin.get_artist_albums(
                    artist_id=artist_id,
                    limit=50,
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
                logger.error(f"Spotify album import failed for {artist_id}: {e}")
                break
        
        return all_albums
    
    async def import_tracks_for_album(
        self,
        album_id: str,
    ) -> list["TrackDTO"]:
        """Import tracks for a specific album from Spotify.
        
        Args:
            album_id: Spotify album ID
        
        Returns:
            List of TrackDTOs for this album
        """
        if not self._plugin:
            return []
        
        from soulspot.domain.ports.plugin import PluginCapability
        if not self._plugin.can_use(PluginCapability.GET_ALBUM_TRACKS):
            return []
        
        try:
            response = await self._plugin.get_album_tracks(
                album_id=album_id,
                limit=50,
            )
            return list(response.items) if response.items else []
        except Exception as e:
            logger.error(f"Spotify track import failed for album {album_id}: {e}")
            return []
    
    async def import_playlists(self) -> list["PlaylistDTO"]:
        """Import user playlists from Spotify.
        
        Returns:
            List of PlaylistDTOs
        """
        if not self._plugin:
            return []
        
        from soulspot.domain.ports.plugin import PluginCapability
        if not self._plugin.can_use(PluginCapability.USER_PLAYLISTS):
            return []
        
        all_playlists: list["PlaylistDTO"] = []
        offset = 0
        
        while True:
            try:
                response = await self._plugin.get_user_playlists(
                    limit=50,
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
                logger.error(f"Spotify playlist import failed: {e}")
                break
        
        return all_playlists
