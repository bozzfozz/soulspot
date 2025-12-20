"""Deezer Image Provider - IImageProvider implementation for Deezer.

Hey future me - das ist der WRAPPER um DeezerPlugin für IImageProvider!

WICHTIG: Deezer braucht KEINE OAuth für Bilder!
requires_auth = False → Perfekt als Fallback wenn Spotify nicht verfügbar!

FLOW:
    ImageService/Registry
        │
        └─► DeezerImageProvider.get_artist_image(deezer_id)
                │
                └─► DeezerPlugin.get_artist(deezer_id)
                        │
                        └─► artist_dto.image.url → ImageResult

Deezer-Besonderheiten:
- Öffentliche API (keine Auth nötig!)
- Bilder in verschiedenen Größen: 56, 250, 500, 1000
- Nur numerische IDs (kein URI-Format wie Spotify)
"""

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
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

logger = logging.getLogger(__name__)


class DeezerImageProvider(IImageProvider):
    """Deezer implementation of IImageProvider.
    
    Hey future me - Deezer ist KOSTENLOS und braucht keine Auth!
    Perfekt als Fallback wenn Spotify OAuth fehlt.
    
    Deezer-Besonderheiten:
    - Öffentliche API (requires_auth = False!)
    - Bilder in verschiedenen Größen verfügbar
    - Numerische IDs (keine URIs)
    
    Quality Mapping (Deezer sizes):
    - THUMBNAIL → 56px (small)
    - SMALL → 250px (medium) 
    - MEDIUM → 500px (big)
    - LARGE → 1000px (xl)
    - ORIGINAL → 1000px
    """
    
    # Deezer image size suffixes
    SIZE_SUFFIXES = {
        ImageQuality.THUMBNAIL: "small",   # 56x56
        ImageQuality.SMALL: "medium",      # 250x250
        ImageQuality.MEDIUM: "big",        # 500x500
        ImageQuality.LARGE: "xl",          # 1000x1000
        ImageQuality.ORIGINAL: "xl",       # 1000x1000
    }
    
    def __init__(self, deezer_plugin: "DeezerPlugin") -> None:
        """Initialize with DeezerPlugin.
        
        Args:
            deezer_plugin: DeezerPlugin instance (no auth needed!)
        """
        self._plugin = deezer_plugin
    
    @property
    def provider_name(self) -> ProviderName:
        """Return provider name."""
        return "deezer"
    
    @property
    def requires_auth(self) -> bool:
        """Deezer does NOT require OAuth for images!"""
        return False
    
    async def is_available(self) -> bool:
        """Deezer is always available (no auth needed).
        
        Future me note:
        Could add rate limit check here if needed.
        """
        return True
    
    # === Direct Lookup Methods ===
    
    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image by Deezer ID.
        
        Args:
            artist_id: Deezer artist ID (numeric string, e.g., "27")
            quality: Desired image quality
            
        Returns:
            ImageResult with CDN URL, or None if not found
        """
        try:
            artist_dto = await self._plugin.get_artist(artist_id)
            
            if not artist_dto or not artist_dto.image.url:
                logger.debug("No image found for Deezer artist: %s", artist_id)
                return None
            
            # Adjust URL for requested quality
            url = self._adjust_image_url(artist_dto.image.url, quality)
            
            return ImageResult(
                url=url,
                provider="deezer",
                quality=quality,
            )
            
        except Exception as e:
            logger.warning("Error getting Deezer artist image for %s: %s", artist_id, e)
            return None
    
    async def get_album_image(
        self,
        album_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image by Deezer ID.
        
        Args:
            album_id: Deezer album ID (numeric string)
            quality: Desired image quality
            
        Returns:
            ImageResult with CDN URL, or None if not found
        """
        try:
            album_dto = await self._plugin.get_album(album_id)
            
            if not album_dto or not album_dto.cover.url:
                logger.debug("No cover found for Deezer album: %s", album_id)
                return None
            
            url = self._adjust_image_url(album_dto.cover.url, quality)
            
            return ImageResult(
                url=url,
                provider="deezer",
                quality=quality,
            )
            
        except Exception as e:
            logger.warning("Error getting Deezer album image for %s: %s", album_id, e)
            return None
    
    # === Search Methods ===
    
    async def search_artist_image(
        self,
        artist_name: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for artist image by name.
        
        Args:
            artist_name: Artist name to search
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best match and alternatives
        """
        result = ImageSearchResult(
            query=artist_name,
            provider="deezer",
        )
        
        try:
            search_result = await self._plugin.search_artists(
                query=artist_name,
                limit=5,
            )
            
            if not search_result.items:
                logger.debug("No Deezer artists found for: %s", artist_name)
                return result
            
            # Convert DTOs to ImageResults
            for i, artist_dto in enumerate(search_result.items):
                if not artist_dto.image.url:
                    continue
                
                image_result = ImageResult(
                    url=self._adjust_image_url(artist_dto.image.url, quality),
                    provider="deezer",
                    quality=quality,
                )
                
                if i == 0:
                    result.best_match = image_result
                else:
                    result.alternatives.append(image_result)
            
            return result
            
        except Exception as e:
            logger.warning("Error searching Deezer artist images for '%s': %s", artist_name, e)
            return result
    
    async def search_album_image(
        self,
        album_title: str,
        artist_name: str | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for album image by title and artist.
        
        Args:
            album_title: Album title to search
            artist_name: Optional artist name for better matching
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best match and alternatives
        """
        query = album_title
        if artist_name:
            query = f"{artist_name} {album_title}"
        
        result = ImageSearchResult(
            query=query,
            provider="deezer",
        )
        
        try:
            search_result = await self._plugin.search_albums(
                query=query,
                limit=5,
            )
            
            if not search_result.items:
                logger.debug("No Deezer albums found for: %s", query)
                return result
            
            # Find best match (prefer exact title match)
            album_title_lower = album_title.lower().strip()
            best_match_dto = None
            
            for album_dto in search_result.items:
                if album_dto.title.lower().strip() == album_title_lower:
                    best_match_dto = album_dto
                    break
            
            # Fallback to first result
            if not best_match_dto:
                best_match_dto = search_result.items[0]
            
            # Convert to ImageResults
            for album_dto in search_result.items:
                if not album_dto.cover.url:
                    continue
                
                image_result = ImageResult(
                    url=self._adjust_image_url(album_dto.cover.url, quality),
                    provider="deezer",
                    quality=quality,
                )
                
                if album_dto == best_match_dto:
                    result.best_match = image_result
                else:
                    result.alternatives.append(image_result)
            
            return result
            
        except Exception as e:
            logger.warning("Error searching Deezer album images for '%s': %s", query, e)
            return result
    
    # === Helper Methods ===
    
    def _adjust_image_url(
        self,
        url: str,
        quality: ImageQuality,
    ) -> str:
        """Adjust Deezer image URL for requested quality.
        
        Future me note:
        Deezer URLs look like:
        - https://e-cdns-images.dzcdn.net/images/artist/.../250x250-000000-80-0-0.jpg
        - https://api.deezer.com/artist/27/image?size=medium
        
        We can modify the size parameter or URL suffix to get different sizes.
        
        Size mapping:
        - small: 56x56
        - medium: 250x250
        - big: 500x500
        - xl: 1000x1000
        """
        size_suffix = self.SIZE_SUFFIXES.get(quality, "big")
        
        # Handle API-style URLs (?size=xxx)
        if "?size=" in url:
            # Replace size parameter
            import re
            return re.sub(r'\?size=\w+', f'?size={size_suffix}', url)
        
        # Handle CDN-style URLs (250x250 in path)
        # Try to replace common size patterns
        import re
        
        # Pattern: NNNxNNN (e.g., 250x250, 500x500)
        size_pixels = {
            "small": "56x56",
            "medium": "250x250",
            "big": "500x500",
            "xl": "1000x1000",
        }
        target_size = size_pixels.get(size_suffix, "500x500")
        
        # Replace any dimension pattern
        modified = re.sub(r'\d+x\d+', target_size, url)
        
        return modified
