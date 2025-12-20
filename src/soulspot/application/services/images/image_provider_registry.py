"""Image Provider Registry - Manages multiple image providers with priority.

Hey future me - das ist das HERZ des Multi-Source Image Systems!

FUNKTION:
- Registriert alle Image Providers (Spotify, Deezer, CAA)
- Verwaltet Prioritäten (Spotify = 1, Deezer = 2, CAA = 3)
- Führt Fallback-Logik aus (nächster Provider wenn einer fehlschlägt)

FLOW:
    LocalLibraryEnrichmentService
        │
        └─► ImageProviderRegistry.get_artist_image("Metallica")
                │
                ├─► SpotifyImageProvider.is_available() → True?
                │       └─► search_artist_image("Metallica") → Result!
                │
                ├─► DeezerImageProvider.is_available() → True? (Fallback)
                │       └─► search_artist_image("Metallica") → Result!
                │
                └─► None (kein Provider hat Bild)

PRIORITÄTEN (default):
1. Spotify (beste Qualität, aber braucht Auth)
2. Deezer (gute Qualität, keine Auth!)
3. CAA (nur Albums, keine Artists)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from soulspot.domain.ports.image_provider import (
    IImageProvider,
    IImageProviderRegistry,
    ImageQuality,
    ImageResult,
    ProviderName,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ImageProviderRegistry(IImageProviderRegistry):
    """Registry that manages image providers with priority-based fallback.
    
    Hey future me - dieser Registry:
    1. Speichert alle registrierten Providers mit Priority
    2. Sortiert nach Priority (niedrigere Zahl = höhere Priorität)
    3. Führt Fallback aus (nächster Provider wenn einer fehlschlägt)
    4. Prüft is_available() bevor ein Provider genutzt wird
    
    Default Prioritäten:
    - Spotify: 1 (erste Wahl, beste Qualität)
    - Deezer: 2 (Fallback, keine Auth nötig)
    - CAA: 3 (nur Albums, letzter Fallback)
    """
    
    def __init__(self) -> None:
        """Initialize empty registry."""
        # List of (provider, priority) tuples, sorted by priority
        self._providers: list[tuple[IImageProvider, int]] = []
    
    # === Registration ===
    
    def register(self, provider: IImageProvider, priority: int = 10) -> None:
        """Register a provider with given priority.
        
        Lower priority number = checked first.
        
        Args:
            provider: The image provider implementation
            priority: Ordering priority (lower = higher priority)
        """
        # Check if already registered
        for existing, _ in self._providers:
            if existing.provider_name == provider.provider_name:
                logger.warning(
                    "Provider %s already registered, updating priority",
                    provider.provider_name
                )
                self._providers.remove((existing, _))
                break
        
        self._providers.append((provider, priority))
        # Sort by priority (lower = first)
        self._providers.sort(key=lambda x: x[1])
        
        logger.info(
            "Registered image provider: %s (priority=%d, requires_auth=%s)",
            provider.provider_name, priority, provider.requires_auth
        )
    
    def unregister(self, provider_name: ProviderName) -> bool:
        """Remove a provider from the registry.
        
        Args:
            provider_name: Name of provider to remove
            
        Returns:
            True if removed, False if not found
        """
        for provider, priority in self._providers:
            if provider.provider_name == provider_name:
                self._providers.remove((provider, priority))
                logger.info("Unregistered image provider: %s", provider_name)
                return True
        return False
    
    # === Availability ===
    
    async def get_available_providers(self) -> list[IImageProvider]:
        """Get list of currently available providers, sorted by priority.
        
        Checks is_available() for each provider.
        
        Returns:
            List of available providers
        """
        available = []
        for provider, _ in self._providers:
            try:
                if await provider.is_available():
                    available.append(provider)
            except Exception as e:
                logger.warning(
                    "Error checking availability for %s: %s",
                    provider.provider_name, e
                )
        return available
    
    # === Main Image Retrieval Methods ===
    
    async def get_artist_image(
        self,
        artist_name: str | None = None,
        artist_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image from best available provider.
        
        Hey future me - DAS ist die Methode die der EnrichmentService nutzt!
        
        Strategie:
        1. Wenn artist_ids vorhanden: Versuche Direct Lookup (schneller!)
        2. Wenn nicht gefunden: Versuche Search by Name
        3. Probiere Provider in Priority-Reihenfolge
        4. Return erstes erfolgreiches Ergebnis
        
        Args:
            artist_name: Artist name for search
            artist_ids: Dict of provider → artist_id for direct lookup
            quality: Desired image quality
            
        Returns:
            ImageResult from first successful provider, or None
        """
        artist_ids = artist_ids or {}
        
        # Try each provider in priority order
        for provider, priority in self._providers:
            try:
                # Check availability
                if not await provider.is_available():
                    logger.debug(
                        "Skipping %s (not available) for artist: %s",
                        provider.provider_name, artist_name
                    )
                    continue
                
                # Strategy 1: Direct lookup by ID (if available)
                provider_id = artist_ids.get(provider.provider_name)  # type: ignore[arg-type]
                if provider_id:
                    result = await provider.get_artist_image(provider_id, quality)
                    if result:
                        logger.info(
                            "Found artist image via ID lookup: %s (provider=%s, id=%s)",
                            artist_name, provider.provider_name, provider_id
                        )
                        return result
                
                # Strategy 2: Search by name
                if artist_name:
                    search_result = await provider.search_artist_image(
                        artist_name, quality
                    )
                    if search_result.best_match:
                        logger.info(
                            "Found artist image via search: %s (provider=%s)",
                            artist_name, provider.provider_name
                        )
                        return search_result.best_match
                
                # This provider didn't have an image, try next
                logger.debug(
                    "No image from %s for artist: %s",
                    provider.provider_name, artist_name
                )
                
            except Exception as e:
                logger.warning(
                    "Error getting artist image from %s for %s: %s",
                    provider.provider_name, artist_name, e
                )
                continue
        
        # No provider had an image
        logger.debug("No image found for artist: %s", artist_name)
        return None
    
    async def get_album_image(
        self,
        album_title: str | None = None,
        artist_name: str | None = None,
        album_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image from best available provider.
        
        Same logic as get_artist_image but for albums.
        
        Args:
            album_title: Album title for search
            artist_name: Optional artist name for better matching
            album_ids: Dict of provider → album_id for direct lookup
            quality: Desired image quality
            
        Returns:
            ImageResult from first successful provider, or None
        """
        album_ids = album_ids or {}
        
        # Try each provider in priority order
        for provider, priority in self._providers:
            try:
                # Check availability
                if not await provider.is_available():
                    logger.debug(
                        "Skipping %s (not available) for album: %s",
                        provider.provider_name, album_title
                    )
                    continue
                
                # Strategy 1: Direct lookup by ID
                provider_id = album_ids.get(provider.provider_name)  # type: ignore[arg-type]
                if provider_id:
                    result = await provider.get_album_image(provider_id, quality)
                    if result:
                        logger.info(
                            "Found album image via ID lookup: %s (provider=%s, id=%s)",
                            album_title, provider.provider_name, provider_id
                        )
                        return result
                
                # Strategy 2: Search by title + artist
                if album_title:
                    search_result = await provider.search_album_image(
                        album_title, artist_name, quality
                    )
                    if search_result.best_match:
                        logger.info(
                            "Found album image via search: %s - %s (provider=%s)",
                            artist_name, album_title, provider.provider_name
                        )
                        return search_result.best_match
                
                logger.debug(
                    "No image from %s for album: %s",
                    provider.provider_name, album_title
                )
                
            except Exception as e:
                logger.warning(
                    "Error getting album image from %s for %s: %s",
                    provider.provider_name, album_title, e
                )
                continue
        
        logger.debug("No image found for album: %s", album_title)
        return None
    
    # === Convenience Methods ===
    
    def get_registered_providers(self) -> list[tuple[ProviderName, int, bool]]:
        """Get info about registered providers.
        
        Returns:
            List of (name, priority, requires_auth) tuples
        """
        return [
            (p.provider_name, prio, p.requires_auth)
            for p, prio in self._providers
        ]
    
    def __len__(self) -> int:
        """Number of registered providers."""
        return len(self._providers)
    
    def __repr__(self) -> str:
        providers_str = ", ".join(
            f"{p.provider_name}(p={prio})"
            for p, prio in self._providers
        )
        return f"ImageProviderRegistry([{providers_str}])"
