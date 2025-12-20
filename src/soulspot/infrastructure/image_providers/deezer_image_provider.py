"""Deezer Image Provider - IImageProvider implementation for Deezer.

Hey future me - dieser Provider wrapped DeezerClient für das Image-System!

WICHTIG:
- Deezer Public API braucht KEINE Auth für Bilder!
- Daher immer verfügbar (is_available() = True)
- Perfekt als Fallback wenn Spotify nicht authed

Deezer Bildgrößen:
- picture_small / cover_small: 56x56
- picture_medium / cover_medium: 250x250
- picture_big / cover_big: 500x500
- picture_xl / cover_xl: 1000x1000 (beste Qualität!)

FLOW:
    ImageProviderRegistry
        │
        └─► DeezerImageProvider.search_artist_image("Metallica")
                │
                └─► DeezerClient.search_artists("Metallica")
                        │
                        └─► DeezerArtist mit picture_xl
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
    from soulspot.infrastructure.integrations.deezer_client import DeezerClient

logger = logging.getLogger(__name__)


# Quality → Deezer size mapping
_QUALITY_TO_SIZE = {
    ImageQuality.THUMBNAIL: "small",    # 56x56
    ImageQuality.SMALL: "medium",       # 250x250
    ImageQuality.MEDIUM: "big",         # 500x500
    ImageQuality.LARGE: "xl",           # 1000x1000
    ImageQuality.ORIGINAL: "xl",        # 1000x1000 (best available)
}


class DeezerImageProvider(IImageProvider):
    """Deezer image provider using DeezerClient.
    
    Hey future me - dieser Provider:
    1. Wrapped DeezerClient für IImageProvider Interface
    2. Nutzt search_artists/search_albums für Suche
    3. KEINE Auth nötig! Immer verfügbar
    4. Deezer hat gute Bildqualität (bis 1000x1000)
    
    Priorität: 2 - nach Spotify, vor CAA
    """
    
    def __init__(self, deezer_client: DeezerClient) -> None:
        """Initialize with DeezerClient.
        
        Args:
            deezer_client: Initialized DeezerClient
        """
        self._client = deezer_client
        
    # === Properties ===
    
    @property
    def provider_name(self) -> ProviderName:
        """Deezer provider name."""
        return "deezer"
    
    @property
    def requires_auth(self) -> bool:
        """Deezer public API does NOT require authentication for images!"""
        return False
    
    # === Availability ===
    
    async def is_available(self) -> bool:
        """Deezer public API is always available.
        
        Hey future me - keine Auth nötig!
        Wir könnten hier einen Health-Check machen, aber das wäre zu langsam.
        """
        return True
    
    # === Helper: Get best image URL ===
    
    def _get_best_artist_image(
        self, 
        artist, 
        quality: ImageQuality,
    ) -> str | None:
        """Get the best artist image URL based on quality preference.
        
        Args:
            artist: DeezerArtist object
            quality: Desired quality
            
        Returns:
            Best available image URL or None
        """
        size = _QUALITY_TO_SIZE.get(quality, "big")
        
        # Try requested size first, then fallback to smaller
        url = getattr(artist, f"picture_{size}", None)
        if url:
            return url
            
        # Fallback chain: xl > big > medium > small
        for fallback in ["picture_xl", "picture_big", "picture_medium", "picture_small"]:
            url = getattr(artist, fallback, None)
            if url:
                return url
        
        return None
    
    def _get_best_album_image(
        self, 
        album, 
        quality: ImageQuality,
    ) -> str | None:
        """Get the best album image URL based on quality preference.
        
        Args:
            album: DeezerAlbum object
            quality: Desired quality
            
        Returns:
            Best available image URL or None
        """
        size = _QUALITY_TO_SIZE.get(quality, "big")
        
        # Try requested size first, then fallback to smaller
        url = getattr(album, f"cover_{size}", None)
        if url:
            return url
            
        # Fallback chain: xl > big > medium > small
        for fallback in ["cover_xl", "cover_big", "cover_medium", "cover_small"]:
            url = getattr(album, fallback, None)
            if url:
                return url
        
        return None
    
    # === Direct Lookup Methods (by ID) ===
    
    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image by Deezer ID.
        
        Args:
            artist_id: Deezer artist ID (as string, will be converted to int)
            quality: Desired image quality
            
        Returns:
            ImageResult with URL or None if not found
        """
        try:
            # Deezer IDs are integers
            deezer_id = int(artist_id)
            artist = await self._client.get_artist(deezer_id)
            
            if not artist:
                logger.debug("No Deezer artist found for ID %s", artist_id)
                return None
            
            url = self._get_best_artist_image(artist, quality)
            if not url:
                logger.debug(
                    "No image for Deezer artist %s (%s)",
                    artist_id, artist.name
                )
                return None
            
            return ImageResult(
                url=url,
                provider="deezer",
                quality=quality,
                entity_name=artist.name,
                entity_id=str(artist.id),
            )
            
        except ValueError as e:
            logger.warning("Invalid Deezer artist ID %s: %s", artist_id, e)
            return None
        except Exception as e:
            logger.warning(
                "Failed to get Deezer artist image for %s: %s",
                artist_id, e
            )
            return None
    
    async def get_album_image(
        self,
        album_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image by Deezer ID.
        
        Args:
            album_id: Deezer album ID (as string)
            quality: Desired image quality
            
        Returns:
            ImageResult with URL or None if not found
        """
        try:
            deezer_id = int(album_id)
            album = await self._client.get_album(deezer_id)
            
            if not album:
                logger.debug("No Deezer album found for ID %s", album_id)
                return None
            
            url = self._get_best_album_image(album, quality)
            if not url:
                logger.debug(
                    "No image for Deezer album %s (%s)",
                    album_id, album.title
                )
                return None
            
            return ImageResult(
                url=url,
                provider="deezer",
                quality=quality,
                entity_name=album.title,
                entity_id=str(album.id),
            )
            
        except ValueError as e:
            logger.warning("Invalid Deezer album ID %s: %s", album_id, e)
            return None
        except Exception as e:
            logger.warning(
                "Failed to get Deezer album image for %s: %s",
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
        
        Hey future me - Deezer Public API, keine Auth nötig!
        Perfekt als Fallback wenn Spotify nicht verfügbar.
        
        Args:
            artist_name: Artist name to search for
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best_match and alternatives
        """
        try:
            artists = await self._client.search_artists(
                query=artist_name,
                limit=5,
            )
            
            if not artists:
                logger.debug("No Deezer results for artist: %s", artist_name)
                return ImageSearchResult(matches=[], best_match=None)
            
            # Convert zu ImageResults
            matches: list[ImageResult] = []
            for artist in artists:
                url = self._get_best_artist_image(artist, quality)
                if url:
                    matches.append(ImageResult(
                        url=url,
                        provider="deezer",
                        quality=quality,
                        entity_name=artist.name,
                        entity_id=str(artist.id),
                    ))
            
            if not matches:
                logger.debug(
                    "No images in Deezer results for artist: %s",
                    artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            return ImageSearchResult(
                matches=matches,
                best_match=matches[0],
            )
            
        except Exception as e:
            logger.warning(
                "Failed to search Deezer artist image for %s: %s",
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
        
        Hey future me - Deezer ist TOP für Compilations (Bravo Hits etc.)!
        Sucht nach Album-Titel, optional mit Artist-Filter.
        
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
                query = f"{artist_name} - {album_title}"
            else:
                query = album_title
            
            albums = await self._client.search_albums(
                query=query,
                limit=5,
            )
            
            if not albums:
                logger.debug(
                    "No Deezer results for album: %s (artist: %s)",
                    album_title, artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            # Convert zu ImageResults
            matches: list[ImageResult] = []
            for album in albums:
                url = self._get_best_album_image(album, quality)
                if url:
                    matches.append(ImageResult(
                        url=url,
                        provider="deezer",
                        quality=quality,
                        entity_name=album.title,
                        entity_id=str(album.id),
                    ))
            
            if not matches:
                logger.debug(
                    "No images in Deezer results for album: %s",
                    album_title
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            return ImageSearchResult(
                matches=matches,
                best_match=matches[0],
            )
            
        except Exception as e:
            logger.warning(
                "Failed to search Deezer album image for %s: %s",
                album_title, e
            )
            return ImageSearchResult(matches=[], best_match=None)
