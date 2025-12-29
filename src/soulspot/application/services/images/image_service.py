"""SoulSpot Image Service - Central Image Operations.

Future me note:
This is THE one and only place for image business logic in SoulSpot.

What this service does:
1. get_display_url() - Sync method for templates (local > CDN > placeholder)
2. get_image() - Async method to get full image info for an entity
3. get_placeholder() - Get placeholder URL for entity type
4. validate_image() - Check if image URL is still valid (HEAD request)
5. optimize_cache() - Clean up old/unused cached images

What this service does NOT do (handled by Infrastructure):
- ❌ HTTP Downloads → Plugins (SpotifyPlugin, DeezerPlugin) do this
- ❌ Fallback Search → Plugins handle their own fallback logic
- ❌ WebP Conversion → ImageProcessor helper in Infrastructure

Why it exists:
Before this, every service had its own image logic:
- ui.py: model.cover_url or model.image_url or placeholder
- sync services: if dto.image_url: model.image_url = dto.image_url
- artwork_service: Downloading (now deprecated, logic moves to plugins)

Now: One service for URL resolution + validation + cache management!

Architecture (Layered):
- Presentation: Templates use get_display_url()
- Application: ImageService orchestrates
- Infrastructure: Plugins download, ImageProcessor converts

This service is STATELESS (no instance variables beyond config).
All state is in database (via repositories) or filesystem (cache).
Thread-safe by design (asyncio compatible).

See: docs/architecture/IMAGE_SERVICE_DETAILED_PLAN.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

# Clean Architecture: Import DTOs from Domain Port (Single Source of Truth)
from soulspot.domain.ports.image_service import (
    EntityType,
    ImageInfo,
    ImageProvider,
    SaveImageResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


# === Default Placeholders ===

DEFAULT_PLACEHOLDERS: dict[EntityType, str] = {
    "artist": "/static/images/placeholder-artist.svg",
    "album": "/static/images/placeholder-album.svg",
    "playlist": "/static/images/placeholder-playlist.svg",
    "track": "/static/images/placeholder-album.svg",  # Tracks use album placeholder
}

GENERIC_PLACEHOLDER = "/static/images/placeholder.svg"


# === Error Handling for Downloads ===


class ImageDownloadErrorCode(Enum):
    """Error codes for image download failures.

    Future me note:
    Use these to categorize download failures for error reporting.
    LocalLibraryEnrichmentService uses this for batch job tracking.
    """

    NO_URL = "NO_URL"
    HTTP_404 = "HTTP_404"  # Image not found on CDN
    HTTP_403 = "HTTP_403"  # Access forbidden (rate limit or auth issue)
    HTTP_500 = "HTTP_500"  # Server error
    HTTP_OTHER = "HTTP_OTHER"  # Other HTTP status codes
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION = "NETWORK_CONNECTION"
    NETWORK_OTHER = "NETWORK_OTHER"
    INVALID_IMAGE = "INVALID_IMAGE"  # Can't parse as image
    PROCESSING_ERROR = "PROCESSING_ERROR"  # PIL/resize error
    DISK_WRITE_ERROR = "DISK_WRITE_ERROR"
    WEBP_CONVERSION_ERROR = "WEBP_CONVERSION_ERROR"  # WebP conversion failed
    UNKNOWN = "UNKNOWN"


@dataclass
class ImageDownloadResult:
    """Result of an image download operation.

    Future me note:
    Use this for batch operations where you need to track WHY downloads failed.
    success=True means image was saved, success=False includes error details.
    """

    success: bool
    path: str | None = None  # Relative path if successful
    error_code: ImageDownloadErrorCode | None = None
    error_message: str | None = None
    url: str | None = None  # Original URL attempted

    @classmethod
    def ok(cls, path: str) -> ImageDownloadResult:
        """Create successful result."""
        return cls(success=True, path=path)

    @classmethod
    def error(
        cls, code: ImageDownloadErrorCode, message: str, url: str | None = None
    ) -> ImageDownloadResult:
        """Create error result with details."""
        return cls(
            success=False,
            error_code=code,
            error_message=message,
            url=url,
        )


# === Service Implementation ===

# Image size configuration (from ArtworkService)
IMAGE_SIZES: dict[EntityType, int] = {
    "artist": 300,  # Profile pics, 300px is enough
    "album": 500,  # Cover art needs detail
    "playlist": 300,  # Grid thumbnails
    "track": 500,  # Uses album cover
}

WEBP_QUALITY = 85  # Sweet spot for quality vs file size


@dataclass
class ImageService:
    """Central Image Service Implementation.

    Future me note:
    This is the SINGLE source of truth for all image operations in SoulSpot!

    Responsibilities:
    - get_display_url(): Sync method for templates (local > CDN > placeholder)
    - get_image(): Get full image info for entity
    - download_and_cache(): Download from URL, convert to WebP, cache locally
    - validate_image(): Check if CDN URL is still valid
    - optimize_cache(): Clean up old/orphaned images

    What this does NOT do (Plugins handle it):
    - Fetching URLs from providers (SpotifyPlugin, DeezerPlugin do that)
    - Provider-specific fallback logic (Plugins handle their own fallbacks)

    Thread-safe: Uses no shared mutable state.
    """

    # Dependencies (injected)
    session: AsyncSession | None = None  # DB session (optional for sync methods)

    # Configuration
    # Hey future me - default ist für lokale Dev, Docker überschreibt via dependency injection!
    cache_base_path: str = field(default="./images")
    local_serve_prefix: str = field(default="/api/images")

    # === Public Sync Methods (for templates) ===

    def get_display_url(
        self,
        source_url: str | None,
        local_path: str | None,
        entity_type: EntityType = "album",
    ) -> str:
        """Get the best display URL for an image.

        Future me note:
        This is the workhorse method - called from every template!
        It's intentionally SYNC so Jinja2 can call it directly.

        Priority:
        1. Local cache path (if exists and file is there)
        2. CDN URL (Spotify, Deezer, etc.)
        3. Entity-specific placeholder
        4. Generic placeholder

        Args:
            source_url: CDN URL (e.g., "https://i.scdn.co/image/...")
            local_path: Local path (e.g., "artists/abc123.jpg")
            entity_type: For choosing the right placeholder

        Returns:
            URL string to display the image
        """
        # Priority 1: Local cache (if path provided AND file exists)
        if local_path:
            full_path = Path(self.cache_base_path) / local_path
            if full_path.exists():
                return f"{self.local_serve_prefix}/{local_path}"
            else:
                logger.debug(
                    "Local path provided but file missing: %s (entity_type=%s)",
                    local_path,
                    entity_type,
                )

        # Priority 2: CDN URL (Spotify, Deezer, etc.)
        if source_url:
            return source_url

        # Priority 3: Entity-specific placeholder
        return DEFAULT_PLACEHOLDERS.get(entity_type, GENERIC_PLACEHOLDER)

    def get_placeholder(self, entity_type: EntityType = "album") -> str:
        """Get placeholder image URL for an entity type.

        Future me note:
        Simple helper, but useful when you KNOW there's no image.
        """
        return DEFAULT_PLACEHOLDERS.get(entity_type, GENERIC_PLACEHOLDER)

    # Provider priority for multi-source entities
    # Higher priority = checked first
    PROVIDER_PRIORITY: ClassVar[list[str]] = [
        "spotify",  # Best quality, most consistent
        "deezer",  # Good quality
        "tidal",  # Good quality
        "musicbrainz",  # Community-sourced, variable quality
    ]

    def get_best_image(
        self,
        entity_type: EntityType,
        provider_ids: dict[str, str | None],
        fallback_url: str | None = None,
    ) -> str:
        """Get the best available cached image from multiple providers.

        Future me note:
        This is THE method for templates when an entity has multiple provider IDs!

        Use case: A local library track matched to both Spotify AND Deezer.
        We want to show the BEST available image, checking in priority order.

        Args:
            entity_type: "artist", "album", or "playlist"
            provider_ids: Dict of provider → ID, e.g.:
                {"spotify": "abc123", "deezer": "456", "musicbrainz": None}
            fallback_url: CDN URL to use if no cached image found

        Returns:
            Best available URL (local cache > fallback > placeholder)

        Example:
            >>> image_service.get_best_image(
            ...     entity_type="artist",
            ...     provider_ids={
            ...         "spotify": "1dfeR4HaWDbWqFHLkxsg1d",
            ...         "deezer": "123456",
            ...         "musicbrainz": "abc-def-ghi"
            ...     },
            ...     fallback_url="https://i.scdn.co/image/..."
            ... )
            "/artwork/local/artists/spotify/1dfeR4HaWDbWqFHLkxsg1d.webp"
        """
        # Check cached images in priority order
        for provider in self.PROVIDER_PRIORITY:
            provider_id = provider_ids.get(provider)
            if not provider_id:
                continue

            # Build path: {entity_type}s/{provider}/{provider_id}.webp
            relative_path = f"{entity_type}s/{provider}/{provider_id}.webp"
            full_path = Path(self.cache_base_path) / relative_path

            if full_path.exists():
                logger.debug(
                    "Found best image for %s from %s: %s",
                    entity_type,
                    provider,
                    relative_path,
                )
                return f"{self.local_serve_prefix}/{relative_path}"

        # No cached image found - use fallback URL if provided
        if fallback_url:
            return fallback_url

        # Last resort: placeholder
        return DEFAULT_PLACEHOLDERS.get(entity_type, GENERIC_PLACEHOLDER)

    def find_cached_image(
        self,
        entity_type: EntityType,
        provider_ids: dict[str, str | None],
    ) -> str | None:
        """Find the best cached image path (without fallback to CDN/placeholder).

        Future me note:
        Like get_best_image() but returns None if no cache exists.
        Useful for checking "do we have ANY local image?"

        Args:
            entity_type: "artist", "album", or "playlist"
            provider_ids: Dict of provider → ID

        Returns:
            Relative path like "artists/spotify/abc.webp" or None
        """
        for provider in self.PROVIDER_PRIORITY:
            provider_id = provider_ids.get(provider)
            if not provider_id:
                continue

            relative_path = f"{entity_type}s/{provider}/{provider_id}.webp"
            full_path = Path(self.cache_base_path) / relative_path

            if full_path.exists():
                return relative_path

        return None

    # === Public Async Methods (for services) ===

    async def get_image(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> ImageInfo | None:
        """Get complete image information for an entity.

        Future me note:
        Phase 1: This queries the entity's repository to get URL/path.
        Phase 2: This will also check the ImageMetadata table.

        Args:
            entity_type: Type of entity
            entity_id: Entity's internal ID

        Returns:
            ImageInfo or None if entity not found
        """
        if not self.session:
            logger.error("get_image() called without session - returning None")
            return None

        # Phase 1: Direct entity lookup
        # Future: Add caching layer here

        if entity_type == "artist":
            return await self._get_artist_image(entity_id)
        elif entity_type == "album":
            return await self._get_album_image(entity_id)
        elif entity_type == "playlist":
            return await self._get_playlist_image(entity_id)
        elif entity_type == "track":
            # Tracks use their album's image
            return await self._get_track_image(entity_id)

        logger.warning("Unknown entity_type: %s", entity_type)
        return None

    # === Private Helper Methods ===

    async def _get_artist_image(self, entity_id: str) -> ImageInfo | None:
        """Get image info for an artist.

        Future me note:
        This queries ArtistModel directly. In Phase 2, we'll also
        check the ImageMetadata table for more details.
        """
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import ArtistModel

        stmt = select(ArtistModel).where(ArtistModel.id == entity_id)
        result = await self.session.execute(stmt)  # type: ignore[union-attr]
        model = result.scalar_one_or_none()

        if not model:
            return None

        display_url = self.get_display_url(
            source_url=model.image_url,
            local_path=model.image_path,
            entity_type="artist",
        )

        return ImageInfo(
            entity_type="artist",
            entity_id=entity_id,
            display_url=display_url,
            source_url=model.image_url,
            local_path=model.image_path,
            is_cached=bool(model.image_path),
            provider=self._guess_provider(model.image_url),
        )

    async def _get_album_image(self, entity_id: str) -> ImageInfo | None:
        """Get image info for an album."""
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import AlbumModel

        stmt = select(AlbumModel).where(AlbumModel.id == entity_id)
        result = await self.session.execute(stmt)  # type: ignore[union-attr]
        model = result.scalar_one_or_none()

        if not model:
            return None

        display_url = self.get_display_url(
            source_url=model.cover_url, local_path=model.cover_path, entity_type="album"
        )

        return ImageInfo(
            entity_type="album",
            entity_id=entity_id,
            display_url=display_url,
            source_url=model.cover_url,
            local_path=model.cover_path,
            is_cached=bool(model.cover_path),
            provider=self._guess_provider(model.cover_url),
        )

    async def _get_playlist_image(self, entity_id: str) -> ImageInfo | None:
        """Get image info for a playlist."""
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import PlaylistModel

        stmt = select(PlaylistModel).where(PlaylistModel.id == entity_id)
        result = await self.session.execute(stmt)  # type: ignore[union-attr]
        model = result.scalar_one_or_none()

        if not model:
            return None

        display_url = self.get_display_url(
            source_url=model.cover_url,
            local_path=model.cover_path,
            entity_type="playlist",
        )

        return ImageInfo(
            entity_type="playlist",
            entity_id=entity_id,
            display_url=display_url,
            source_url=model.cover_url,
            local_path=model.cover_path,
            is_cached=bool(model.cover_path),
            provider=self._guess_provider(model.cover_url),
        )

    async def _get_track_image(self, entity_id: str) -> ImageInfo | None:
        """Get image info for a track (uses album's image)."""
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = select(TrackModel).where(TrackModel.id == entity_id)
        result = await self.session.execute(stmt)  # type: ignore[union-attr]
        track = result.scalar_one_or_none()

        if not track or not track.album_id:
            return None

        return await self._get_album_image(track.album_id)

    def _guess_provider(self, url: str | None) -> ImageProvider | None:
        """Guess the provider from a CDN URL.

        Future me note:
        This is a heuristic - not 100% accurate but good enough.
        """
        if not url:
            return None

        url_lower = url.lower()

        if "scdn.co" in url_lower or "spotify" in url_lower:
            return "spotify"
        elif "dzcdn.net" in url_lower or "deezer" in url_lower:
            return "deezer"
        elif "tidal" in url_lower:
            return "tidal"
        elif "coverartarchive" in url_lower or "musicbrainz" in url_lower:
            return "caa"
        elif url_lower.startswith("/") or url_lower.startswith("file://"):
            return "local"

        return None

    # =========================================================================
    # DOWNLOAD & CACHE METHODS (integrated from ArtworkService)
    # =========================================================================

    async def download_and_cache(
        self,
        source_url: str,
        entity_type: EntityType,
        entity_id: str,
        force_redownload: bool = False,
    ) -> SaveImageResult:
        """Download image from CDN, convert to WebP, and cache locally.

        Future me note:
        This is THE method for downloading images! Called by sync services
        after getting URL from plugins.

        Flow:
        1. Check if already cached (skip if not force_redownload)
        2. Download from CDN via HttpClientPool
        3. Convert to WebP (resize + optimize)
        4. Save to local cache
        5. Update entity in DB with local_path

        Args:
            source_url: CDN URL to download from
            entity_type: Type of entity (artist, album, etc.)
            entity_id: Entity's internal ID
            force_redownload: Re-download even if cached

        Returns:
            SaveImageResult with status and path
        """
        if not source_url:
            return SaveImageResult.failure("No source URL provided")

        # Check if already cached
        if not force_redownload:
            existing = await self.get_image(entity_type, entity_id)
            if existing and existing.is_cached and existing.source_url == source_url:
                return SaveImageResult.success_cached(existing)

        # Download and process
        try:
            image_data = await self._download_image(source_url)
            if not image_data:
                return SaveImageResult.failure(
                    f"Failed to download image from {source_url}"
                )

            # Convert to WebP
            target_size = IMAGE_SIZES.get(entity_type, 300)
            webp_data = await self._convert_to_webp(image_data, target_size)
            if not webp_data:
                return SaveImageResult.failure("Failed to convert image to WebP")

            # Save to cache
            local_path = await self._save_to_cache(webp_data, entity_type, entity_id)

            # Update entity in DB
            await self._update_entity_image_path(
                entity_type, entity_id, source_url, local_path
            )

            # Build result
            image_info = ImageInfo(
                entity_type=entity_type,
                entity_id=entity_id,
                display_url=f"{self.local_serve_prefix}/{local_path}",
                source_url=source_url,
                local_path=local_path,
                is_cached=True,
                provider=self._guess_provider(source_url),
            )

            return SaveImageResult.success_downloaded(image_info)

        except Exception as e:
            logger.exception(
                "Error in download_and_cache for %s/%s", entity_type, entity_id
            )
            return SaveImageResult.failure(str(e))

    async def _download_image(self, url: str) -> bytes | None:
        """Download image from URL using HttpClientPool.

        Future me note:
        Uses shared HttpClientPool for connection reuse!
        """
        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            return response.content

        except Exception as e:
            logger.warning("Error downloading image from %s: %s", url, e)
            return None

    async def _convert_to_webp(
        self,
        image_data: bytes,
        target_size: int,
    ) -> bytes | None:
        """Convert image to WebP format with resize.

        Future me note:
        Runs PIL in thread pool because it's CPU-bound!
        """
        import asyncio
        from io import BytesIO

        try:
            from PIL import Image as PILImage
        except ImportError:
            logger.error("Pillow not installed - cannot convert images")
            return None

        def _process_sync() -> bytes:
            """Sync processing (runs in thread pool)."""
            with PILImage.open(BytesIO(image_data)) as img:
                # Convert to RGB if necessary
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                # Resize maintaining aspect ratio
                img.thumbnail((target_size, target_size), PILImage.Resampling.LANCZOS)

                # Save as WebP
                output = BytesIO()
                img.save(output, format="WEBP", quality=WEBP_QUALITY, method=6)
                return output.getvalue()

        try:
            return await asyncio.to_thread(_process_sync)
        except Exception as e:
            logger.warning("Error converting image to WebP: %s", e)
            return None

    async def _save_to_cache(
        self,
        image_data: bytes,
        entity_type: EntityType,
        entity_id: str,
    ) -> str:
        """Save image data to local cache.

        Returns relative path for DB storage.
        """
        import asyncio

        # Build path: {entity_type}s/{id[:2]}/{id}.webp
        # Sharding by first 2 chars prevents too many files in one dir
        subdir = entity_id[:2] if len(entity_id) >= 2 else "00"
        relative_path = f"{entity_type}s/{subdir}/{entity_id}.webp"

        full_path = Path(self.cache_base_path) / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(full_path.write_bytes, image_data)

        logger.debug(
            "Saved image to cache: %s (%d bytes)", relative_path, len(image_data)
        )
        return relative_path

    async def _update_entity_image_path(
        self,
        entity_type: EntityType,
        entity_id: str,
        source_url: str,
        local_path: str,
    ) -> None:
        """Update entity's image URL and path in database."""
        if not self.session:
            logger.warning("No session - cannot update entity image path")
            return

        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import (
            AlbumModel,
            ArtistModel,
            PlaylistModel,
        )

        model_map: dict[EntityType, tuple[type, str, str]] = {
            "artist": (ArtistModel, "image_url", "image_path"),
            "album": (AlbumModel, "cover_url", "cover_path"),
            "playlist": (PlaylistModel, "cover_url", "cover_path"),
        }

        if entity_type not in model_map:
            return

        model_class, url_col, path_col = model_map[entity_type]

        stmt = (
            update(model_class)
            .where(model_class.id == entity_id)
            .values(**{url_col: source_url, path_col: local_path})
        )
        await self.session.execute(stmt)

    # =========================================================================
    # VALIDATION & CACHE MANAGEMENT
    # =========================================================================

    async def validate_image(self, source_url: str) -> bool:
        """Check if image URL is still valid (HTTP HEAD request).

        Future me note:
        Use sparingly - makes network request!
        Good for batch validation of stale images.

        Args:
            source_url: CDN URL to validate

        Returns:
            True if URL returns 200 OK
        """
        if not source_url:
            return False

        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.head(
                source_url, follow_redirects=True, timeout=10.0
            )
            return response.status_code == 200

        except Exception as e:
            logger.debug("Image validation failed for %s: %s", source_url, e)
            return False

    async def optimize_cache(
        self,
        max_age_days: int = 90,
        dry_run: bool = True,
    ) -> dict[str, int]:
        """Clean up old/orphaned cached images.

        Future me note:
        Call this periodically (e.g., weekly cron) to free disk space.

        Removes images that:
        - Haven't been modified in max_age_days
        - Are orphaned (file exists but no entity references it)

        Args:
            max_age_days: Delete images older than this
            dry_run: If True, just report what would be deleted

        Returns:
            Stats dict: {deleted_count, freed_bytes, orphaned_count}
        """
        from datetime import timedelta

        cache_path = Path(self.cache_base_path)
        if not cache_path.exists():
            return {"deleted_count": 0, "freed_bytes": 0, "orphaned_count": 0}

        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

        deleted_count = 0
        freed_bytes = 0
        orphaned_count = 0

        # Walk cache directory
        for file_path in cache_path.rglob("*.webp"):
            try:
                stat = file_path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

                if mtime < cutoff:
                    size = stat.st_size

                    if not dry_run:
                        file_path.unlink()
                        logger.info("Deleted old image: %s (%d bytes)", file_path, size)

                    deleted_count += 1
                    freed_bytes += size

            except Exception as e:
                logger.warning("Error checking cache file %s: %s", file_path, e)

        result = {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "orphaned_count": orphaned_count,  # TODO: Check DB for orphans
        }

        logger.info(
            "Cache optimization %s: %d files, %d bytes",
            "would delete" if dry_run else "deleted",
            deleted_count,
            freed_bytes,
        )

        return result

    # =========================================================================
    # SMART IMAGE LOGIC (Phase 1 - Local-First Strategy)
    # =========================================================================
    #
    # Hey future me - these methods implement the "Local-First" image strategy!
    # Core principle: If we have a local file, we're DONE. Don't re-download.
    #
    # Decision tree:
    # 1. has_local_image(path) → YES? → SKIP (no work needed)
    # 2. has CDN URL? → YES? → DOWNLOAD from CDN
    # 3. has provider_id? → YES? → API LOOKUP then download
    # 4. Nothing? → SKIP (can't get image)

    def has_local_image(self, entity_path: str | None) -> bool:
        """Check if local image file exists (FAST - sync, no DB query).

        Hey future me - this is THE primary check for "do we need to download?"
        Call this BEFORE any download decision. It's intentionally SYNC
        so it can be used in tight loops without async overhead.

        Args:
            entity_path: The image_path or cover_path from DB
                        (e.g., "artists/spotify/abc123.webp")

        Returns:
            True if file exists on disk, False otherwise

        Examples:
            >>> service.has_local_image("artists/spotify/abc.webp")
            True  # File exists
            >>> service.has_local_image(None)
            False  # No path
            >>> service.has_local_image("FAILED:HTTP_404:2025-01-01")
            False  # Failed marker, not a real file
        """
        if not entity_path:
            return False

        # Skip FAILED markers (they start with "FAILED")
        if entity_path.startswith("FAILED"):
            return False

        full_path = Path(self.cache_base_path) / entity_path
        return full_path.exists()

    def should_download(
        self,
        existing_path: str | None,
        cdn_url: str | None = None,
    ) -> bool:
        """Simplified download decision: Local exists? No. Has URL? Yes.

        Hey future me - this REPLACES the old should_redownload() logic!
        Key insight: We don't care about URL changes if we have a local file.
        CDN URLs change (token refresh, CDN migration) but the IMAGE is the same.

        Args:
            existing_path: Current image_path/cover_path from DB
            cdn_url: CDN URL available for download (optional)

        Returns:
            True if should download from CDN

        Examples:
            >>> service.should_download("artists/spotify/abc.webp", "https://...")
            False  # Has local file, skip download
            >>> service.should_download(None, "https://...")
            True   # No local file, download needed
            >>> service.should_download(None, None)
            False  # No URL, can't download
        """
        # Rule 1: Local file exists → don't download
        if self.has_local_image(existing_path):
            return False

        # Rule 2: Have CDN URL → download, No URL → can't download
        return bool(cdn_url)

    def needs_image_work(
        self,
        entity_path: str | None,
        cdn_url: str | None,
        provider_id: str | None = None,
    ) -> tuple[bool, str]:
        """Determine if entity needs image work and what kind.

        Hey future me - use this for batch operations to categorize work!
        Returns both a boolean AND the type of work needed.

        Args:
            entity_path: Current image_path/cover_path from DB
            cdn_url: CDN URL (if available)
            provider_id: Provider ID for API lookup (if no CDN URL)

        Returns:
            (needs_work, work_type) tuple where work_type is:
            - "none": No work needed (has local image)
            - "download": Has CDN URL, just download it
            - "lookup": No CDN URL but has provider ID, need API lookup first
            - "skip": No CDN URL and no provider ID, can't get image

        Examples:
            >>> service.needs_image_work("artists/x.webp", "https://...", "abc")
            (False, "none")  # Already have local image
            >>> service.needs_image_work(None, "https://...", "abc")
            (True, "download")  # Have URL, just download
            >>> service.needs_image_work(None, None, "abc")
            (True, "lookup")  # Need API lookup first
            >>> service.needs_image_work(None, None, None)
            (False, "skip")  # Can't get image
        """
        # Priority 1: Already have local image
        if self.has_local_image(entity_path):
            return (False, "none")

        # Priority 2: Have CDN URL → download directly
        if cdn_url:
            return (True, "download")

        # Priority 3: Have provider ID → need API lookup
        if provider_id:
            return (True, "lookup")

        # Priority 4: Nothing to work with
        return (False, "skip")

    # =========================================================================
    # COMPATIBILITY METHODS (for migration from ArtworkService)
    # =========================================================================

    async def should_redownload(
        self,
        existing_url: str | None,
        new_url: str | None,
        existing_path: str | None,
    ) -> bool:
        """Check if image should be re-downloaded.

        ⚠️ DEPRECATED: Use should_download() instead!

        Hey future me - this is kept for backward compatibility only.
        The new should_download() is simpler and ignores URL changes
        (which is correct - we don't need to re-download if local exists).

        This wrapper delegates to should_download() but is async to
        maintain the old signature for existing callers.

        Args:
            existing_url: URL stored in DB (IGNORED in new logic)
            new_url: New URL from provider
            existing_path: Local cache path stored in DB

        Returns:
            True if should re-download
        """
        # Delegate to new simplified logic
        # Note: existing_url is intentionally ignored now
        return self.should_download(existing_path, new_url)

    async def delete_cached_image(self, relative_path: str | None) -> bool:
        """Delete a cached image file.

        Future me note:
        This is a COMPATIBILITY method for migration from ArtworkService.
        Just deletes the file - does NOT update DB.

        Args:
            relative_path: Relative path (e.g., "artists/ab/abc123.webp")

        Returns:
            True if deleted, False if not found or error
        """
        if not relative_path:
            return False

        try:
            full_path = Path(self.cache_base_path) / relative_path
            if full_path.exists():
                full_path.unlink()
                logger.debug("Deleted cached image: %s", relative_path)
                return True
            return False
        except Exception as e:
            logger.warning("Error deleting cached image %s: %s", relative_path, e)
            return False

    # Alias for backward compatibility with ArtworkService
    delete_image_async = delete_cached_image

    # =========================================================================
    # PROVIDER-ID DOWNLOAD METHODS (for Sync-Services migration)
    # =========================================================================
    #
    # Hey future me - these methods are for the Sync-Service migration!
    # The problem: SpotifySyncService uses spotify_id, but ImageService
    # expects internal UUID. These methods bridge that gap by:
    # 1. Accepting provider ID (e.g., spotify_id, deezer_id)
    # 2. Downloading and converting to WebP
    # 3. Returning ONLY the relative path (no DB update!)
    #
    # The caller (Sync-Service) is responsible for:
    # - Passing the path to the repository's upsert method
    # - The repository handles mapping provider_id → internal record
    #
    # Path structure: {entity_type}s/{provider}/{provider_id}.webp
    # Example: artists/spotify/1dfeR4HaWDbWqFHLkxsg1d.webp
    #          artists/deezer/123456.webp
    #          albums/musicbrainz/abc-def-123.webp
    #
    # This keeps the existing flow intact while using ImageService internals.

    async def download_artist_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download artist image by provider ID (e.g., Spotify ID, Deezer ID).

        Future me note:
        This is a MIGRATION BRIDGE for Sync-Services.
        Downloads + converts to WebP, returns path only.
        Does NOT update database - caller passes path to repo.

        Args:
            provider_id: External provider ID (e.g., Spotify ID, Deezer ID)
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")

        Returns:
            Relative path like "artists/spotify/abc123.webp" or None
        """
        return await self._download_for_provider(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="artist",
            provider=provider,
        )

    async def download_album_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download album image by provider ID.

        Future me note:
        Same as download_artist_image but for albums.

        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")
        """
        return await self._download_for_provider(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="album",
            provider=provider,
        )

    async def download_playlist_image(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> str | None:
        """Download playlist image by provider ID.

        Future me note:
        Same as download_artist_image but for playlists.

        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal")
        """
        return await self._download_for_provider(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="playlist",
            provider=provider,
        )

    async def _download_for_provider(
        self,
        provider_id: str,
        image_url: str | None,
        entity_type: str,
        provider: str = "spotify",
    ) -> str | None:
        """Internal method to download image for provider ID.

        Future me note:
        This is the actual implementation behind the provider-ID methods.
        Uses a provider subdirectory to keep images organized by source.

        Path structure: {entity_type}s/{provider}/{provider_id}.webp

        Examples:
            - artists/spotify/1dfeR4HaWDbWqFHLkxsg1d.webp
            - albums/deezer/123456.webp
            - artists/musicbrainz/abc-def-ghi.webp

        Args:
            provider_id: External ID (Spotify ID, Deezer ID, etc.)
            image_url: URL to fetch
            entity_type: "artist", "album", or "playlist"
            provider: Provider name for subdirectory

        Returns:
            Relative path or None if failed
        """
        if not image_url or not provider_id:
            return None

        # Sanitize provider name (lowercase, no special chars)
        safe_provider = provider.lower().replace(" ", "_")

        try:
            # Fetch image data (BUG FIX: was _fetch_image, now _download_image)
            image_data = await self._download_image(image_url)
            if not image_data:
                return None

            # Convert to WebP (BUG FIX: added await, added target_size)
            target_size = IMAGE_SIZES.get(entity_type, 300)  # type: ignore[arg-type]
            webp_data = await self._convert_to_webp(image_data, target_size)
            if not webp_data:
                logger.warning(
                    "WebP conversion failed for %s %s (%s)",
                    entity_type,
                    provider_id,
                    safe_provider,
                )
                return None

            # Build path: {entity_type}s/{provider}/{provider_id}.webp
            # Example: artists/spotify/1dfeR4HaWDbWqFHLkxsg1d.webp
            #          albums/deezer/123456.webp
            relative_path = f"{entity_type}s/{safe_provider}/{provider_id}.webp"
            full_path = Path(self.cache_base_path) / relative_path

            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            full_path.write_bytes(webp_data)
            logger.debug(
                "Downloaded %s image for %s:%s → %s",
                entity_type,
                safe_provider,
                provider_id,
                relative_path,
            )
            return relative_path

        except Exception as e:
            logger.error(
                "Error downloading %s image for %s:%s: %s",
                entity_type,
                safe_provider,
                provider_id,
                e,
            )
            return None

    # =========================================================================
    # PROVIDER-ID DOWNLOAD METHODS WITH RESULT (for batch operations)
    # =========================================================================
    #
    # Hey future me - these are for LocalLibraryEnrichmentService batch jobs!
    # Unlike the simple download methods above, these return ImageDownloadResult
    # with detailed error information for tracking batch job failures.

    async def download_artist_image_with_result(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> ImageDownloadResult:
        """Download artist image with detailed error tracking.

        Future me note:
        Use this instead of download_artist_image() when you need to know
        WHY an image download failed (for error reporting in batch jobs).

        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")
        """
        return await self._download_for_provider_with_result(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="artist",
            provider=provider,
        )

    async def download_album_image_with_result(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> ImageDownloadResult:
        """Download album image with detailed error tracking.

        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal", "musicbrainz")
        """
        return await self._download_for_provider_with_result(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="album",
            provider=provider,
        )

    async def download_playlist_image_with_result(
        self, provider_id: str, image_url: str | None, provider: str = "spotify"
    ) -> ImageDownloadResult:
        """Download playlist image with detailed error tracking.

        Args:
            provider_id: External provider ID
            image_url: URL to download from
            provider: Provider name ("spotify", "deezer", "tidal")
        """
        return await self._download_for_provider_with_result(
            provider_id=provider_id,
            image_url=image_url,
            entity_type="playlist",
            provider=provider,
        )

    async def _download_for_provider_with_result(
        self,
        provider_id: str,
        image_url: str | None,
        entity_type: str,
        provider: str = "spotify",
    ) -> ImageDownloadResult:
        """Download image with detailed error result.

        Future me note:
        This provides detailed error tracking for batch operations.
        Same logic as _download_for_provider but returns ImageDownloadResult.

        Args:
            provider_id: External ID
            image_url: URL to fetch
            entity_type: "artist", "album", or "playlist"
            provider: Provider name for subdirectory
        """
        if not image_url:
            return ImageDownloadResult.error(
                ImageDownloadErrorCode.NO_URL,
                "No image URL provided",
                None,
            )

        if not provider_id:
            return ImageDownloadResult.error(
                ImageDownloadErrorCode.UNKNOWN,
                "No provider ID provided",
                image_url,
            )

        # Sanitize provider name
        safe_provider = provider.lower().replace(" ", "_")

        try:
            # Fetch image data with error tracking (BUG FIX: was _fetch_image)
            image_data = await self._download_image(image_url)
            if not image_data:
                return ImageDownloadResult.error(
                    ImageDownloadErrorCode.NETWORK_OTHER,
                    "Failed to fetch image data",
                    image_url,
                )

            # Convert to WebP (BUG FIX: added await, added target_size)
            target_size = IMAGE_SIZES.get(entity_type, 300)  # type: ignore[arg-type]
            webp_data = await self._convert_to_webp(image_data, target_size)
            if not webp_data:
                return ImageDownloadResult.error(
                    ImageDownloadErrorCode.WEBP_CONVERSION_ERROR,
                    "WebP conversion failed",
                    image_url,
                )

            # Build path: {entity_type}s/{provider}/{provider_id}.webp
            relative_path = f"{entity_type}s/{safe_provider}/{provider_id}.webp"
            full_path = Path(self.cache_base_path) / relative_path

            # Ensure directory exists and write
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_bytes(webp_data)
            except OSError as e:
                return ImageDownloadResult.error(
                    ImageDownloadErrorCode.DISK_WRITE_ERROR,
                    f"Failed to write file: {e}",
                    image_url,
                )

            logger.debug(
                "Downloaded %s image for %s:%s → %s",
                entity_type,
                safe_provider,
                provider_id,
                relative_path,
            )
            return ImageDownloadResult.ok(relative_path)

        except Exception as e:
            logger.error(
                "Error downloading %s image for %s:%s: %s",
                entity_type,
                safe_provider,
                provider_id,
                e,
            )
            return ImageDownloadResult.error(
                ImageDownloadErrorCode.UNKNOWN,
                str(e),
                image_url,
            )

    # =========================================================================
    # STATISTICS METHODS (for settings UI)
    # =========================================================================

    def get_disk_usage(self) -> dict[str, int]:
        """Get disk usage statistics for cached images.

        Future me note:
        This is for the Settings UI to show storage used per category.

        Returns:
            Dict with 'artists', 'albums', 'playlists', 'total' byte counts.
        """
        usage: dict[str, int] = {}
        total = 0

        cache_path = Path(self.cache_base_path)
        logger.info(
            "📊 Image Stats - Cache path: %s (exists: %s)",
            cache_path,
            cache_path.exists(),
        )

        if not cache_path.exists():
            logger.warning("⚠️ Image cache directory does not exist: %s", cache_path)
            return {"artists": 0, "albums": 0, "playlists": 0, "total": 0}

        for category in ("artists", "albums", "playlists"):
            category_path = cache_path / category
            if category_path.exists():
                cat_bytes = sum(
                    f.stat().st_size for f in category_path.rglob("*") if f.is_file()
                )
                usage[category] = cat_bytes
                total += cat_bytes
                logger.debug(
                    "📊 %s: %d bytes from %d files",
                    category,
                    cat_bytes,
                    sum(1 for f in category_path.rglob("*") if f.is_file()),
                )
            else:
                usage[category] = 0
                logger.debug("📊 %s directory does not exist", category)

        usage["total"] = total
        logger.info(
            "📊 Image Stats Total: %d bytes across %d files",
            total,
            sum(1 for f in cache_path.rglob("*") if f.is_file()),
        )
        return usage

    def get_image_count(self) -> dict[str, int]:
        """Get count of cached images per category.

        Future me note:
        For Settings UI alongside disk usage.

        Returns:
            Dict with 'artists', 'albums', 'playlists', 'total' counts.
        """
        counts: dict[str, int] = {}
        total = 0

        cache_path = Path(self.cache_base_path)
        if not cache_path.exists():
            return {"artists": 0, "albums": 0, "playlists": 0, "total": 0}

        for category in ("artists", "albums", "playlists"):
            category_path = cache_path / category
            if category_path.exists():
                cat_count = sum(1 for f in category_path.rglob("*") if f.is_file())
                counts[category] = cat_count
                total += cat_count
            else:
                counts[category] = 0

        counts["total"] = total
        return counts
