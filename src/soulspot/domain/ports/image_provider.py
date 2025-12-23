"""Image Provider Interface - Abstraction for image sources.

Hey future me - das ist das PORT (Interface) für Bild-Quellen!

PROBLEM VORHER:
- ImageService hatte Plugin-Code direkt
- SpotifySyncService hatte Plugin-Code direkt
- MetadataService hatte Plugin-Code direkt
- Überall verstreuter Plugin-Code!

LÖSUNG JETZT:
- IImageProvider ist das einheitliche Interface
- SpotifyImageProvider, DeezerImageProvider, etc. implementieren es
- Services sprechen NUR mit dem Interface
- Clean Architecture: Domain kennt keine Infrastructure!

FLOW:
    ImageService / MetadataService / SyncServices
        │
        └─► IImageProvider.get_artist_image(artist_id)
                │
                ├─► SpotifyImageProvider (implementiert IImageProvider)
                │       └─► SpotifyPlugin.get_artist()
                ├─► DeezerImageProvider
                │       └─► DeezerPlugin.get_artist()
                └─► CoverArtArchiveImageProvider
                        └─► MusicBrainz API

Der Service weiß NICHT welcher Provider - nur das Interface!

Implementierungen:
- infrastructure/providers/spotify_image_provider.py
- infrastructure/providers/deezer_image_provider.py
- infrastructure/providers/coverartarchive_image_provider.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

# === Type Definitions ===

ProviderName = Literal["spotify", "deezer", "tidal", "musicbrainz", "coverartarchive", "local"]


class ImageQuality(Enum):
    """Image quality/size hints.

    Future me note:
    Some providers return multiple sizes. This helps choose the right one.
    """
    THUMBNAIL = "thumbnail"  # ~64px - for lists
    SMALL = "small"          # ~160px - for grids
    MEDIUM = "medium"        # ~300px - default UI
    LARGE = "large"          # ~640px - detail pages
    ORIGINAL = "original"    # Full resolution


# === Result DTOs ===

@dataclass(frozen=True)
class ImageResult:
    """Result of an image lookup.

    Future me note:
    Immutable (frozen) - represents a snapshot of what the provider returned.
    url is the CDN URL, not a local path!
    """
    url: str
    provider: ProviderName
    width: int | None = None
    height: int | None = None
    quality: ImageQuality = ImageQuality.MEDIUM

    @property
    def is_high_res(self) -> bool:
        """Check if this is a high-resolution image."""
        if self.width and self.height:
            return min(self.width, self.height) >= 500
        return self.quality in (ImageQuality.LARGE, ImageQuality.ORIGINAL)


@dataclass
class ImageSearchResult:
    """Result of an image search (may have multiple matches).

    Future me note:
    When searching by name, we might get multiple candidates.
    best_match is our recommendation, alternatives are fallbacks.
    """
    best_match: ImageResult | None = None
    alternatives: list[ImageResult] = field(default_factory=list)
    query: str = ""  # Original search query
    provider: ProviderName = "spotify"

    @property
    def found(self) -> bool:
        """Check if any image was found."""
        return self.best_match is not None


# === Provider Interface ===

class IImageProvider(ABC):
    """Interface for image providers.

    Future me note:
    This abstraction lets ImageService/MetadataService ask for images
    WITHOUT knowing which provider it's talking to!

    Implementierungen müssen diese Methoden implementieren:
    - get_artist_image() - By provider-specific ID
    - get_album_image() - By provider-specific ID
    - search_artist_image() - By name (fuzzy)
    - search_album_image() - By title/artist (fuzzy)

    Jede Implementierung wrapped einen Plugin:
    - SpotifyImageProvider → SpotifyPlugin
    - DeezerImageProvider → DeezerPlugin
    - CoverArtArchiveImageProvider → MusicBrainz/CAA API

    WICHTIG: Methoden sind async weil sie HTTP-Calls machen!
    """

    @property
    @abstractmethod
    def provider_name(self) -> ProviderName:
        """Name of this provider (spotify, deezer, etc.).

        Used for:
        - Cache path organization (artists/spotify/...)
        - Logging and debugging
        - Provider priority ordering
        """
        ...

    @property
    @abstractmethod
    def requires_auth(self) -> bool:
        """Whether this provider requires authentication.

        Future me note:
        - Spotify: True (needs OAuth)
        - Deezer: False (public API for images!)
        - CoverArtArchive: False
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is currently available.

        Future me note:
        Checks:
        - Auth status (if requires_auth)
        - Rate limit status
        - Network connectivity

        Use this before trying to fetch images!
        """
        ...

    # === Direct Lookup Methods (by ID) ===

    @abstractmethod
    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get image URL for an artist by provider-specific ID.

        Args:
            artist_id: Provider-specific artist ID (e.g., Spotify ID, Deezer ID)
            quality: Desired image quality

        Returns:
            ImageResult with URL, or None if not found

        Example:
            result = await provider.get_artist_image("1dfeR4HaWDbWqFHLkxsg1d")
            if result:
                print(f"Found: {result.url} from {result.provider}")
        """
        ...

    @abstractmethod
    async def get_album_image(
        self,
        album_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get image URL for an album by provider-specific ID.

        Args:
            album_id: Provider-specific album ID
            quality: Desired image quality

        Returns:
            ImageResult with URL, or None if not found
        """
        ...

    # === Search Methods (by name) ===

    @abstractmethod
    async def search_artist_image(
        self,
        artist_name: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for artist image by name.

        Future me note:
        This is for when you don't have the provider ID!
        Uses fuzzy matching to find best match.

        Args:
            artist_name: Artist name to search for
            quality: Desired image quality

        Returns:
            ImageSearchResult with best_match and alternatives
        """
        ...

    @abstractmethod
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
        ...


# === Provider Registry ===

class IImageProviderRegistry(ABC):
    """Registry for managing multiple image providers.

    Future me note:
    This handles:
    - Provider priority ordering
    - Fallback logic (try Spotify, then Deezer, then CAA)
    - Availability checking

    ImageService uses this to get images from the best available provider.
    """

    @abstractmethod
    def register(self, provider: IImageProvider, priority: int = 10) -> None:
        """Register a provider with given priority.

        Lower priority number = checked first.
        Default priority 10 allows inserting before (1-9) or after (11+).

        Args:
            provider: The image provider implementation
            priority: Ordering priority (lower = higher priority)
        """
        ...

    @abstractmethod
    def unregister(self, provider_name: ProviderName) -> bool:
        """Remove a provider from the registry.

        Args:
            provider_name: Name of provider to remove

        Returns:
            True if removed, False if not found
        """
        ...

    @abstractmethod
    async def get_available_providers(self) -> list[IImageProvider]:
        """Get list of currently available providers, sorted by priority.

        Returns:
            List of available providers (is_available() == True)
        """
        ...

    @abstractmethod
    async def get_artist_image(
        self,
        artist_name: str | None = None,
        artist_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get artist image from best available provider.

        Future me note:
        This is THE method for getting artist images!
        It tries providers in priority order:
        1. First try direct ID lookup (if artist_ids provided)
        2. Then try search by name (if artist_name provided)
        3. Return first successful result

        Args:
            artist_name: Artist name for search
            artist_ids: Dict of provider → artist_id for direct lookup
            quality: Desired image quality

        Returns:
            ImageResult from first successful provider, or None

        Example:
            result = await registry.get_artist_image(
                artist_name="Radiohead",
                artist_ids={
                    "spotify": "4Z8W4fKeB5YxbusRsdQVPb",
                    "deezer": "399"
                }
            )
        """
        ...

    @abstractmethod
    async def get_album_image(
        self,
        album_title: str | None = None,
        artist_name: str | None = None,
        album_ids: dict[ProviderName, str] | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image from best available provider.

        Same logic as get_artist_image but for albums.
        """
        ...


# === Exports ===

__all__ = [
    # Types
    "ProviderName",
    "ImageQuality",
    # DTOs
    "ImageResult",
    "ImageSearchResult",
    # Interfaces
    "IImageProvider",
    "IImageProviderRegistry",
]
