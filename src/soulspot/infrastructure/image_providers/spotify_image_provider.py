"""Spotify Image Provider - IImageProvider implementation for Spotify.

Hey future me - dieser Provider wrapped SpotifyPlugin für das Image-System!

WICHTIG:
- Alle Spotify-Operations brauchen Auth (OAuth Token)
- SpotifyPlugin managed den Token intern
- is_available() prüft ob Token vorhanden

FLOW:
    ImageProviderRegistry
        │
        └─► SpotifyImageProvider.search_artist_image("Metallica")
                │
                └─► SpotifyPlugin.search_artist("Metallica")
                        │
                        └─► ArtistDTO mit image.url
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from soulspot.domain.ports.image_provider import (
    IImageProvider,
    ImageQuality,
    ImageResult,
    ImageSearchResult,
    ProviderName,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class SpotifyImageProvider(IImageProvider):
    """Spotify image provider using SpotifyPlugin.
    
    Hey future me - dieser Provider:
    1. Wrapped SpotifyPlugin für IImageProvider Interface
    2. Nutzt search_artist/search_album für Suche nach Namen
    3. Nutzt get_artist/get_album für ID-basierte Abfragen
    4. Alle Operationen brauchen Auth!
    
    Priorität: 1 (höchste) - Spotify hat beste Bildqualität
    """
    
    def __init__(self, spotify_plugin: SpotifyPlugin) -> None:
        """Initialize with SpotifyPlugin.
        
        Args:
            spotify_plugin: Initialized SpotifyPlugin with token
        """
        self._plugin = spotify_plugin
        
    # === Properties ===
    
    @property
    def provider_name(self) -> ProviderName:
        """Spotify provider name."""
        return "spotify"
    
    @property
    def requires_auth(self) -> bool:
        """Spotify requires OAuth authentication."""
        return True
    
    # === Availability ===
    
    async def is_available(self) -> bool:
        """Check if Spotify is available (has valid token).
        
        Hey future me - SpotifyPlugin.is_authenticated prüft:
        - Token vorhanden
        - Token nicht expired
        
        Wir machen KEINEN API-Call hier (zu langsam)!
        """
        return self._plugin.is_authenticated
    
    # === Direct Lookup Methods (by ID) ===
    
    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image by Spotify ID.
        
        Args:
            artist_id: Spotify artist ID (e.g., "1dfeR4HaWDbWqFHLkxsg1d")
            quality: Desired image quality (Spotify returns multiple sizes)
            
        Returns:
            ImageResult with URL or None if not found
        """
        try:
            artist_dto = await self._plugin.get_artist(artist_id)
            
            # ArtistDTO.image ist ImageRef
            if not artist_dto.image or not artist_dto.image.url:
                logger.debug(
                    "No image for Spotify artist %s (%s)",
                    artist_id, artist_dto.name
                )
                return None
            
            # Spotify gibt mehrere Größen, wir nutzen die aus DTO
            # (SpotifyPlugin wählt bereits die beste)
            return ImageResult(
                url=artist_dto.image.url,
                provider="spotify",
                width=artist_dto.image.width,
                height=artist_dto.image.height,
                quality=quality,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to get Spotify artist image for %s: %s",
                artist_id, e
            )
            return None
    
    async def get_album_image(
        self,
        album_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image by Spotify ID.
        
        Args:
            album_id: Spotify album ID
            quality: Desired image quality
            
        Returns:
            ImageResult with URL or None if not found
        """
        try:
            album_dto = await self._plugin.get_album(album_id)
            
            # AlbumDTO.image ist ImageRef
            if not album_dto.image or not album_dto.image.url:
                logger.debug(
                    "No image for Spotify album %s (%s)",
                    album_id, album_dto.title
                )
                return None
            
            return ImageResult(
                url=album_dto.image.url,
                provider="spotify",
                width=album_dto.image.width,
                height=album_dto.image.height,
                quality=quality,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to get Spotify album image for %s: %s",
                album_id, e
            )
            return None
    
    # === Search Methods (by name) ===
    
    async def search_artist_image(
        self,
        artist_name: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for artist image by name.
        
        Hey future me - sucht Spotify nach Artist und gibt beste Match zurück!
        Mehrere Ergebnisse werden als alternatives zurückgegeben.
        
        Args:
            artist_name: Artist name to search for
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best_match and alternatives
        """
        try:
            # Suche Spotify
            result = await self._plugin.search_artist(
                query=artist_name,
                limit=5,  # Top 5 für alternatives
            )
            
            if not result.items:
                logger.debug("No Spotify results for artist: %s", artist_name)
                return ImageSearchResult(matches=[], best_match=None)
            
            # Convert zu ImageResults
            matches: list[ImageResult] = []
            for artist_dto in result.items:
                if artist_dto.image and artist_dto.image.url:
                    matches.append(ImageResult(
                        url=artist_dto.image.url,
                        provider="spotify",
                        width=artist_dto.image.width,
                        height=artist_dto.image.height,
                        quality=quality,
                        entity_name=artist_dto.name,
                        entity_id=artist_dto.id,  # Spotify ID
                    ))
            
            if not matches:
                logger.debug(
                    "No images in Spotify results for artist: %s",
                    artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            # Bestes Match = erstes Ergebnis (Spotify sortiert nach Relevanz)
            return ImageSearchResult(
                matches=matches,
                best_match=matches[0],
            )
            
        except Exception as e:
            logger.warning(
                "Failed to search Spotify artist image for %s: %s",
                artist_name, e
            )
            return ImageSearchResult(matches=[], best_match=None)
    
    async def search_album_image(
        self,
        album_title: str,
        artist_name: str | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for album image by title and optionally artist.
        
        Args:
            album_title: Album title to search for
            artist_name: Optional artist name for better matching
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best_match and alternatives
        """
        try:
            # Build search query
            if artist_name:
                query = f"album:{album_title} artist:{artist_name}"
            else:
                query = f"album:{album_title}"
            
            # Suche Spotify
            result = await self._plugin.search_album(
                query=query,
                limit=5,
            )
            
            if not result.items:
                logger.debug(
                    "No Spotify results for album: %s (artist: %s)",
                    album_title, artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            # Convert zu ImageResults
            matches: list[ImageResult] = []
            for album_dto in result.items:
                if album_dto.image and album_dto.image.url:
                    matches.append(ImageResult(
                        url=album_dto.image.url,
                        provider="spotify",
                        width=album_dto.image.width,
                        height=album_dto.image.height,
                        quality=quality,
                        entity_name=album_dto.title,
                        entity_id=album_dto.id,
                    ))
            
            if not matches:
                logger.debug(
                    "No images in Spotify results for album: %s",
                    album_title
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            return ImageSearchResult(
                matches=matches,
                best_match=matches[0],
            )
            
        except Exception as e:
            logger.warning(
                "Failed to search Spotify album image for %s: %s",
                album_title, e
            )
            return ImageSearchResult(matches=[], best_match=None)
