"""Spotify Image Provider - IImageProvider implementation for Spotify.

Hey future me - das ist der WRAPPER um SpotifyPlugin für IImageProvider!

FLOW:
    ImageService/Registry
        │
        └─► SpotifyImageProvider.get_artist_image(spotify_id)
                │
                └─► SpotifyPlugin.get_artist(spotify_id)
                        │
                        └─► artist_dto.image.url → ImageResult

Der Provider WRAPPED den Plugin und übersetzt zu ImageResult DTOs.
So bleibt die Domain sauber von Plugin-Implementierungsdetails!

WICHTIG: Spotify braucht IMMER OAuth für Bilder!
requires_auth = True
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
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class SpotifyImageProvider(IImageProvider):
    """Spotify implementation of IImageProvider.

    Hey future me - wrapped SpotifyPlugin für einheitlichen Zugriff!

    Spotify-Besonderheiten:
    - IMMER OAuth erforderlich (auch für öffentliche Daten)
    - Bilder in verschiedenen Größen verfügbar (64, 300, 640)
    - URI Format: spotify:artist:ID oder spotify:album:ID

    Quality Mapping:
    - THUMBNAIL → 64px
    - SMALL → 64px
    - MEDIUM → 300px (default)
    - LARGE → 640px
    - ORIGINAL → 640px (Spotify max)
    """

    # Spotify image sizes
    SIZE_MAP = {
        ImageQuality.THUMBNAIL: 64,
        ImageQuality.SMALL: 64,
        ImageQuality.MEDIUM: 300,
        ImageQuality.LARGE: 640,
        ImageQuality.ORIGINAL: 640,
    }

    def __init__(self, spotify_plugin: "SpotifyPlugin") -> None:
        """Initialize with SpotifyPlugin.

        Args:
            spotify_plugin: Authenticated SpotifyPlugin instance
        """
        self._plugin = spotify_plugin

    @property
    def provider_name(self) -> ProviderName:
        """Return provider name."""
        return "spotify"

    @property
    def requires_auth(self) -> bool:
        """Spotify ALWAYS requires OAuth."""
        return True

    async def is_available(self) -> bool:
        """Check if Spotify is available (authenticated).

        Future me note:
        Uses plugin.is_authenticated for quick check (no API call).
        """
        return self._plugin.is_authenticated

    # === Direct Lookup Methods ===

    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image by Spotify ID.

        Args:
            artist_id: Spotify artist ID (e.g., "4Z8W4fKeB5YxbusRsdQVPb")
            quality: Desired image quality

        Returns:
            ImageResult with CDN URL, or None if not found
        """
        if not await self.is_available():
            logger.debug("Spotify not available for artist image lookup")
            return None

        try:
            artist_dto = await self._plugin.get_artist(artist_id)

            if not artist_dto or not artist_dto.image.url:
                logger.debug("No image found for Spotify artist: %s", artist_id)
                return None

            # Select best size based on quality
            url = self._select_best_image_url(
                artist_dto.image.url,
                quality,
            )

            return ImageResult(
                url=url,
                provider="spotify",
                quality=quality,
            )

        except Exception as e:
            logger.warning(
                "Error getting Spotify artist image for %s: %s", artist_id, e
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
            ImageResult with CDN URL, or None if not found
        """
        if not await self.is_available():
            logger.debug("Spotify not available for album image lookup")
            return None

        try:
            album_dto = await self._plugin.get_album(album_id)

            if not album_dto or not album_dto.cover.url:
                logger.debug("No cover found for Spotify album: %s", album_id)
                return None

            url = self._select_best_image_url(
                album_dto.cover.url,
                quality,
            )

            return ImageResult(
                url=url,
                provider="spotify",
                quality=quality,
            )

        except Exception as e:
            logger.warning("Error getting Spotify album image for %s: %s", album_id, e)
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
            provider="spotify",
        )

        if not await self.is_available():
            logger.debug("Spotify not available for artist search")
            return result

        try:
            # SpotifyPlugin hat search_artist() (Singular!)
            search_result = await self._plugin.search_artist(
                query=artist_name,
                limit=5,
            )

            if not search_result.items:
                logger.debug("No Spotify artists found for: %s", artist_name)
                return result

            # Convert DTOs to ImageResults
            for i, artist_dto in enumerate(search_result.items):
                if not artist_dto.image.url:
                    continue

                image_result = ImageResult(
                    url=self._select_best_image_url(artist_dto.image.url, quality),
                    provider="spotify",
                    quality=quality,
                )

                if i == 0:
                    result.best_match = image_result
                else:
                    result.alternatives.append(image_result)

            return result

        except Exception as e:
            logger.warning(
                "Error searching Spotify artist images for '%s': %s", artist_name, e
            )
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
            provider="spotify",
        )

        if not await self.is_available():
            logger.debug("Spotify not available for album search")
            return result

        try:
            # SpotifyPlugin hat search_album() (Singular!)
            search_result = await self._plugin.search_album(
                query=query,
                limit=5,
            )

            if not search_result.items:
                logger.debug("No Spotify albums found for: %s", query)
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
            for _i, album_dto in enumerate(search_result.items):
                if not album_dto.cover.url:
                    continue

                image_result = ImageResult(
                    url=self._select_best_image_url(album_dto.cover.url, quality),
                    provider="spotify",
                    quality=quality,
                )

                if album_dto == best_match_dto:
                    result.best_match = image_result
                else:
                    result.alternatives.append(image_result)

            return result

        except Exception as e:
            logger.warning(
                "Error searching Spotify album images for '%s': %s", query, e
            )
            return result

    # === Helper Methods ===

    def _select_best_image_url(
        self,
        default_url: str,
        quality: ImageQuality,
    ) -> str:
        """Select best image URL based on quality preference.

        Future me note:
        Spotify URLs typically look like:
        https://i.scdn.co/image/ab6761610000e5eb...

        The size is encoded in the URL path (e.g., "e5eb" = 640px).
        For now we just return the default URL - Spotify usually gives
        the 640px version which is good for most uses.

        TODO: Parse Spotify images array if we get access to it.
        """
        # For now, return default URL
        # Spotify's API returns the largest available image
        return default_url
