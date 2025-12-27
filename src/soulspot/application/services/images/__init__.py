# Future me note:
# This module is the CENTRAL place for all image-related logic.
#
# REFACTORED (Dec 2025):
# - Added failed_markers.py for FAILED|reason|timestamp handling
# - Added repair.py for batch repair operations (from ImageRepairService)
# - ImageRepairService is now DEPRECATED - use ImageService instead
#
# Clean Architecture: DTOs are defined in domain/ports/image_service.py
# and re-exported here for convenience. This keeps:
# - Single Source of Truth: DTOs defined ONCE in domain layer
# - Convenient imports: from soulspot.application.services.images import ImageService, ImageInfo
#
# What ImageService does:
#   - get_display_url(): Sync method for templates (local > CDN > placeholder)
#   - download_and_cache(): Download from CDN, convert to WebP, cache locally
#   - validate_image(): Check if CDN URL is still valid
#   - optimize_cache(): Clean up old/orphaned cached images
#   - repair_artist_images(): Batch fix artists with missing images (NEW!)
#   - repair_album_images(): Batch fix albums with missing covers (NEW!)
#
# What Plugins do (NOT ImageService):
#   - Provide image URLs (spotify_plugin.get_artist() → ArtistDTO.image_url)
#   - Provider-specific fallback logic (DeezerPlugin searches if Spotify fails)
#
# See docs/architecture/IMAGE_SERVICE_DETAILED_PLAN.md for full roadmap.

"""SoulSpot Image Services Module.

Central module for all image-related operations:
- ImageService: Download, cache, convert, display images

Usage:
    from soulspot.application.services.images import ImageService, ImageInfo

    # Via dependency injection
    image_service = ImageService(session=session)

    # Get display URL (sync - for templates)
    url = image_service.get_display_url(
        source_url="https://i.scdn.co/image/abc123",
        local_path="artists/ab/abc123.webp",
        entity_type="artist"
    )

    # Download and cache (async - for sync services)
    result = await image_service.download_and_cache(
        source_url="https://i.scdn.co/image/abc123",
        entity_type="artist",
        entity_id="abc123",
    )

    # Batch repair (async - for background jobs)
    stats = await image_service.repair_artist_images(limit=50)
"""

# FAILED marker utilities (shared by repair operations)
from soulspot.application.services.images.failed_markers import (
    FAILED_RETRY_HOURS,
    FailedMarkerReason,
    classify_error,
    guess_provider_from_url,
    make_failed_marker,
    parse_failed_marker,
    should_retry_failed,
)

# Provider Registry (Multi-Source Image System)
from soulspot.application.services.images.image_provider_registry import (
    ImageProviderRegistry,
)

# Implementation
from soulspot.application.services.images.image_service import (
    IMAGE_SIZES,
    WEBP_QUALITY,
    ImageDownloadErrorCode,
    ImageDownloadResult,
    ImageService,
)

# Batch repair operations (extracted from deprecated ImageRepairService)
from soulspot.application.services.images.repair import (
    repair_album_images,
    repair_artist_images,
)

# Clean Architecture: Import DTOs from Domain Port (Single Source of Truth)
from soulspot.domain.ports.image_service import (
    EntityType,
    IImageService,
    ImageInfo,
    ImageProvider,
    ImageSize,
    SaveImageResult,
)

__all__ = [
    # DTOs from Domain Port
    "EntityType",
    "ImageInfo",
    "ImageProvider",
    "ImageSize",
    "IImageService",
    "SaveImageResult",
    # Implementation-specific
    "ImageService",
    "ImageDownloadErrorCode",
    "ImageDownloadResult",
    "IMAGE_SIZES",
    "WEBP_QUALITY",
    # Multi-Source Provider Registry
    "ImageProviderRegistry",
    # FAILED marker utilities
    "FailedMarkerReason",
    "FAILED_RETRY_HOURS",
    "make_failed_marker",
    "parse_failed_marker",
    "should_retry_failed",
    "classify_error",
    "guess_provider_from_url",
    # Batch repair operations
    "repair_artist_images",
    "repair_album_images",
]
