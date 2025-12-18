"""Image Service Port (Interface).

Future me note:
This defines the CONTRACT for image operations in SoulSpot.
The actual implementation is in application/services/images/image_service.py

Why is this here (in domain/ports)?
- Clean Architecture: Domain defines interfaces, Infrastructure implements
- Dependency Inversion: Services depend on this interface, not concrete implementation
- Testing: Easy to mock for unit tests

Usage:
    from soulspot.domain.ports.image_service import IImageService, ImageInfo
    
    class MyService:
        def __init__(self, image_service: IImageService):
            self.image_service = image_service
        
        async def process_artist(self, artist_id: str):
            info = await self.image_service.get_image("artist", artist_id)
            ...
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol


# === Type Definitions ===

EntityType = Literal["artist", "album", "playlist", "track"]
ImageProvider = Literal["spotify", "deezer", "tidal", "musicbrainz", "caa", "local"]


class ImageSize(Enum):
    """Standard image sizes.
    
    Future me note:
    Phase 2 will use these for thumbnail generation.
    For now they're just for tracking what we have.
    """
    UNKNOWN = "unknown"
    SMALL = "small"      # ~64x64
    MEDIUM = "medium"    # ~300x300
    LARGE = "large"      # ~640x640
    ORIGINAL = "original"


# === Data Transfer Objects ===

@dataclass(frozen=True)
class ImageInfo:
    """Complete information about an entity's image.
    
    This is immutable (frozen) - it's a snapshot at query time.
    """
    entity_type: EntityType
    entity_id: str
    
    # URLs
    display_url: str           # Best URL for frontend
    source_url: str | None     # Original CDN URL
    
    # Local cache
    local_path: str | None
    is_cached: bool
    
    # Provider
    provider: ImageProvider | None
    
    # Dimensions (if known)
    width: int | None = None
    height: int | None = None
    
    # Status
    needs_refresh: bool = False
    
    # Timestamps
    fetched_at: datetime | None = None
    last_verified_at: datetime | None = None


@dataclass
class SaveImageResult:
    """Result of a save_image() operation."""
    success: bool
    image_info: ImageInfo | None = None
    error: str | None = None
    
    # What happened
    downloaded: bool = False
    cached_reused: bool = False
    deduplicated: bool = False
    
    @classmethod
    def failure(cls, error: str) -> SaveImageResult:
        return cls(success=False, error=error)
    
    @classmethod
    def success_cached(cls, image_info: ImageInfo) -> SaveImageResult:
        return cls(success=True, image_info=image_info, cached_reused=True)
    
    @classmethod
    def success_downloaded(cls, image_info: ImageInfo) -> SaveImageResult:
        return cls(success=True, image_info=image_info, downloaded=True)


# === Service Interface ===

class IImageService(Protocol):
    """Image Service Port (Interface).
    
    Future me note:
    All ImageService implementations must follow this protocol.
    This enables:
    - Dependency injection
    - Easy mocking for tests
    - Alternative implementations (S3-based, etc.)
    
    NOTE: Downloads are part of this interface now!
    ImageService handles: URL resolution + downloading + WebP conversion + caching
    Plugins only provide URLs, they don't download.
    """
    
    def get_display_url(
        self,
        source_url: str | None,
        local_path: str | None,
        entity_type: EntityType = "album",
    ) -> str:
        """Get best display URL for an image (sync method for templates).
        
        Priority: local > CDN > placeholder
        
        Args:
            source_url: CDN URL from provider
            local_path: Local cache path
            entity_type: For choosing placeholder
            
        Returns:
            URL string to display
        """
        ...
    
    def get_placeholder(self, entity_type: EntityType = "album") -> str:
        """Get placeholder URL for an entity type."""
        ...
    
    def get_best_image(
        self,
        entity_type: EntityType,
        provider_ids: dict[str, str | None],
        fallback_url: str | None = None,
    ) -> str:
        """Get the best available cached image from multiple providers.
        
        Checks cached images in priority order (spotify > deezer > tidal > musicbrainz).
        Use this when an entity has IDs from multiple providers.
        
        Args:
            entity_type: "artist", "album", or "playlist"
            provider_ids: Dict of provider → ID, e.g.:
                {"spotify": "abc123", "deezer": "456", "musicbrainz": None}
            fallback_url: CDN URL to use if no cached image found
            
        Returns:
            Best available URL (local cache > fallback > placeholder)
        """
        ...
    
    def find_cached_image(
        self,
        entity_type: EntityType,
        provider_ids: dict[str, str | None],
    ) -> str | None:
        """Find the best cached image path (without fallback).
        
        Like get_best_image() but returns None if no cache exists.
        
        Args:
            entity_type: "artist", "album", or "playlist"
            provider_ids: Dict of provider → ID
            
        Returns:
            Relative path like "artists/spotify/abc.webp" or None
        """
        ...
    
    async def get_image(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> ImageInfo | None:
        """Get complete image info for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity's internal ID
            
        Returns:
            ImageInfo or None if not found
        """
        ...
    
    async def download_and_cache(
        self,
        source_url: str,
        entity_type: EntityType,
        entity_id: str,
        force_redownload: bool = False,
    ) -> SaveImageResult:
        """Download image from CDN, convert to WebP, and cache locally.
        
        This is THE method for downloading images. Called by sync services
        after getting URL from plugins.
        
        Args:
            source_url: CDN URL to download from
            entity_type: Type of entity
            entity_id: Entity's internal ID
            force_redownload: Re-download even if cached
            
        Returns:
            SaveImageResult with status and path
        """
        ...
    
    async def validate_image(self, source_url: str) -> bool:
        """Check if image URL is still valid (HTTP HEAD request).
        
        Use sparingly - makes network request!
        
        Args:
            source_url: CDN URL to validate
            
        Returns:
            True if URL returns 200 OK
        """
        ...
    
    async def optimize_cache(
        self,
        max_age_days: int = 90,
        dry_run: bool = True,
    ) -> dict[str, int]:
        """Clean up old/orphaned cached images.
        
        Args:
            max_age_days: Delete images older than this
            dry_run: If True, just report what would be deleted
            
        Returns:
            Stats: {deleted_count, freed_bytes, orphaned_count}
        """
        ...

    # =========================================================================
    # COMPATIBILITY METHODS (for migration from ArtworkService)
    # =========================================================================

    async def should_redownload(
        self,
        existing_url: str | None,
        new_url: str | None,
        existing_path: str | None,
    ) -> bool:
        """Check if image should be re-downloaded (URL changed or no local cache).
        
        Compatibility method for migration from ArtworkService.
        
        Args:
            existing_url: URL stored in DB
            new_url: New URL from provider
            existing_path: Local cache path stored in DB
            
        Returns:
            True if should re-download
        """
        ...

    async def delete_cached_image(self, relative_path: str | None) -> bool:
        """Delete a cached image file.
        
        Compatibility method for migration from ArtworkService.
        Just deletes the file - does NOT update DB.
        
        Args:
            relative_path: Relative path (e.g., "artists/ab/abc123.webp")
            
        Returns:
            True if deleted, False if not found or error
        """
        ...

    # Alias for backward compatibility
    delete_image_async = delete_cached_image

    # =========================================================================
    # Provider-ID Download Methods (for Sync-Service migration)
    # =========================================================================
    # These methods accept provider IDs (e.g., Spotify ID, Deezer ID) and return
    # paths without updating the database. The caller handles DB updates.
    # 
    # Path structure: {entity_type}s/{provider}/{provider_id}.webp
    # Examples:
    #   - artists/spotify/1dfeR4HaWDbWqFHLkxsg1d.webp
    #   - albums/deezer/123456.webp
    #   - artists/musicbrainz/abc-def-ghi.webp

    async def download_artist_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download artist image by provider ID.
        
        Migration bridge for Sync-Services.
        Downloads + converts to WebP, returns path only.
        Does NOT update database.
        
        Args:
            provider_id: External provider ID (e.g., Spotify ID, Deezer ID)
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")
            
        Returns:
            Relative path like "artists/spotify/abc123.webp" or None
        """
        ...

    async def download_album_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download album image by provider ID.
        
        Migration bridge for Sync-Services.
        
        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")
        """
        ...

    async def download_playlist_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download playlist image by provider ID.
        
        Migration bridge for Sync-Services.
        
        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal")
        """
        ...


# === Re-exports for convenience ===

__all__ = [
    "EntityType",
    "ImageProvider",
    "ImageSize",
    "ImageInfo",
    "SaveImageResult",
    "IImageService",
]

