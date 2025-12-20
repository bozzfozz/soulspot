"""Image Provider Registry - Multi-Provider Fallback Management.

Hey future me - das ist die ZENTRALE Stelle für Multi-Provider Image-Lookup!

FLOW:
    ImageService / MetadataService
        │
        └─► ImageProviderRegistry.get_artist_image(...)
                │
                │   Providers in Priority-Reihenfolge:
                │   1. DeezerImageProvider (NO AUTH!) ← Default First
                │   2. SpotifyImageProvider (needs OAuth)
                │   3. CoverArtArchiveImageProvider (future)
                │
                ├─► DeezerImageProvider.get_artist_image()
                │       └─► Found? → Return ImageResult
                │       └─► Not found? → Next provider
                │
                └─► SpotifyImageProvider.get_artist_image()
                        └─► Found? → Return ImageResult
                        └─► Not found? → Return None

Der Registry probiert alle Provider durch bis einer ein Bild findet!
Priority ist konfigurierbar (niedrigere Zahl = höhere Priorität).

DEFAULT PRIORITY:
- Deezer: 1 (first, no auth needed!)
- Spotify: 2 (needs OAuth)
- MusicBrainz/CAA: 3 (future)

USAGE:
    registry = ImageProviderRegistry()
    registry.register(DeezerImageProvider(deezer_plugin), priority=1)
    registry.register(SpotifyImageProvider(spotify_plugin), priority=2)
    
    # Get image - tries all providers in order
    result = await registry.get_artist_image(
        artist_name="Radiohead",
        artist_ids={"spotify": "4Z8W4fKeB5YxbusRsdQVPb", "deezer": "399"}
    )
"""

import logging
from dataclasses import dataclass, field

from soulspot.domain.ports.image_provider import (
    IImageProvider,
    IImageProviderRegistry,
    ImageQuality,
    ImageResult,
    ProviderName,
)

logger = logging.getLogger(__name__)


@dataclass
class _ProviderEntry:
    """Internal entry for registered provider with priority."""
    provider: IImageProvider
    priority: int


class ImageProviderRegistry(IImageProviderRegistry):
    """Registry for managing image providers with fallback logic.
    
    Hey future me - das ist der MULTI-PROVIDER ORCHESTRATOR!
    
    Features:
    - Priority-based provider ordering
    - Automatic fallback to next provider on failure
    - Availability checking (skip unavailable providers)
    - Direct ID lookup + Search by name support
    
    Typical priority setup:
    - Deezer (1): No auth, always available
    - Spotify (2): Needs OAuth, may not be available
    - MusicBrainz (3): No auth, but slower and less coverage
    """
    
    def __init__(self) -> None:
        """Initialize empty registry."""
        self._providers: dict[ProviderName, _ProviderEntry] = {}
    
    def register(self, provider: IImageProvider, priority: int = 10) -> None:
        """Register a provider with given priority.
        
        Lower priority = checked first!
        
        Args:
            provider: The image provider implementation
            priority: Ordering priority (default 10)
            
        Example:
            registry.register(DeezerImageProvider(plugin), priority=1)  # First
            registry.register(SpotifyImageProvider(plugin), priority=2)  # Second
        """
        self._providers[provider.provider_name] = _ProviderEntry(
            provider=provider,
            priority=priority,
        )
        logger.info(
            "Registered image provider: %s (priority=%d, requires_auth=%s)",
            provider.provider_name,
            priority,
            provider.requires_auth,
        )
    
    def unregister(self, provider_name: ProviderName) -> bool:
        """Remove a provider from the registry.
        
        Args:
            provider_name: Name of provider to remove
            
        Returns:
            True if removed, False if not found
        """
        if provider_name in self._providers:
            del self._providers[provider_name]
            logger.info("Unregistered image provider: %s", provider_name)
            return True
        return False
    
    def _get_sorted_providers(self) -> list[IImageProvider]:
        """Get providers sorted by priority (lowest first)."""
        sorted_entries = sorted(
            self._providers.values(),
            key=lambda e: e.priority,
        )
        return [entry.provider for entry in sorted_entries]
    
    async def get_available_providers(self) -> list[IImageProvider]:
        """Get list of currently available providers, sorted by priority.
        
        Returns:
            List of providers where is_available() == True
        """
        available = []
        for provider in self._get_sorted_providers():
            if await provider.is_available():
                available.append(provider)
            else:
                logger.debug(
                    "Provider %s not available (requires_auth=%s)",
                    provider.provider_name,
                    provider.requires_auth,
                )
        return available
    
    async def get_artist_image(
        self,
        artist_name: str | None = None,
        artist_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image from best available provider.
        
        Tries providers in priority order:
        1. Direct ID lookup (if artist_ids provided)
        2. Search by name (if artist_name provided)
        
        Args:
            artist_name: Artist name for search
            artist_ids: Dict of provider → artist_id for direct lookup
            quality: Desired image quality
            
        Returns:
            ImageResult from first successful provider, or None
        """
        artist_ids = artist_ids or {}
        
        for provider in await self.get_available_providers():
            provider_name = provider.provider_name
            
            # Try direct ID lookup first (faster, more accurate)
            if provider_name in artist_ids:
                artist_id = artist_ids[provider_name]
                logger.debug(
                    "Trying %s direct lookup for artist ID: %s",
                    provider_name,
                    artist_id,
                )
                result = await provider.get_artist_image(artist_id, quality)
                if result:
                    logger.info(
                        "Found artist image via %s direct lookup: %s",
                        provider_name,
                        result.url[:50] + "..." if len(result.url) > 50 else result.url,
                    )
                    return result
            
            # Fallback to search by name
            if artist_name:
                logger.debug(
                    "Trying %s search for artist: '%s'",
                    provider_name,
                    artist_name,
                )
                search_result = await provider.search_artist_image(artist_name, quality)
                if search_result.found and search_result.best_match:
                    logger.info(
                        "Found artist image via %s search: %s",
                        provider_name,
                        search_result.best_match.url[:50] + "..."
                        if len(search_result.best_match.url) > 50
                        else search_result.best_match.url,
                    )
                    return search_result.best_match
        
        logger.debug(
            "No artist image found for: name=%s, ids=%s",
            artist_name,
            artist_ids,
        )
        return None
    
    async def get_album_image(
        self,
        album_title: str | None = None,
        artist_name: str | None = None,
        album_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image from best available provider.
        
        Tries providers in priority order:
        1. Direct ID lookup (if album_ids provided)
        2. Search by title/artist (if album_title provided)
        
        Args:
            album_title: Album title for search
            artist_name: Optional artist name for better search
            album_ids: Dict of provider → album_id for direct lookup
            quality: Desired image quality
            
        Returns:
            ImageResult from first successful provider, or None
        """
        album_ids = album_ids or {}
        
        for provider in await self.get_available_providers():
            provider_name = provider.provider_name
            
            # Try direct ID lookup first
            if provider_name in album_ids:
                album_id = album_ids[provider_name]
                logger.debug(
                    "Trying %s direct lookup for album ID: %s",
                    provider_name,
                    album_id,
                )
                result = await provider.get_album_image(album_id, quality)
                if result:
                    logger.info(
                        "Found album image via %s direct lookup",
                        provider_name,
                    )
                    return result
            
            # Fallback to search
            if album_title:
                logger.debug(
                    "Trying %s search for album: '%s' by '%s'",
                    provider_name,
                    album_title,
                    artist_name or "unknown",
                )
                search_result = await provider.search_album_image(
                    album_title,
                    artist_name,
                    quality,
                )
                if search_result.found and search_result.best_match:
                    logger.info(
                        "Found album image via %s search",
                        provider_name,
                    )
                    return search_result.best_match
        
        logger.debug(
            "No album image found for: title=%s, artist=%s, ids=%s",
            album_title,
            artist_name,
            album_ids,
        )
        return None
    
    # === Convenience Methods ===
    
    def get_provider(self, provider_name: ProviderName) -> IImageProvider | None:
        """Get a specific provider by name.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Provider instance or None if not registered
        """
        entry = self._providers.get(provider_name)
        return entry.provider if entry else None
    
    @property
    def registered_providers(self) -> list[ProviderName]:
        """Get list of registered provider names."""
        return list(self._providers.keys())
    
    def __len__(self) -> int:
        """Get number of registered providers."""
        return len(self._providers)
    
    def __contains__(self, provider_name: ProviderName) -> bool:
        """Check if provider is registered."""
        return provider_name in self._providers
