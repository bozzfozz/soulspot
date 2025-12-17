"""Artwork Service - Download and manage UI artwork locally (NOT for ID3 embedding).

Hey future me - this service handles LOCAL STORAGE of images for UI display!
RENAMED Jan 2025: From SpotifyImageService → ArtworkService for clarity.

IMPORTANT DISTINCTION:
- ArtworkService (this file) = UI images stored in artwork/ folder (WebP, for browser display)
- MetadataService (postprocessing/) = ID3/FLAC tag embedding (for audio file metadata)

Both handle "cover artwork" but for DIFFERENT purposes:
- ArtworkService: Display images in web UI (local storage, fast loading)
- MetadataService: Embed artwork into audio files (ID3v2 APIC tag)

Why local storage?
1. Offline access - Images work without Spotify connection
2. Fast loading - No CDN latency, images served from disk
3. URL change detection - Compare image_url vs stored; re-download if changed
4. Cleanup on delete - Remove images when entity is removed from DB

MULTI-PROVIDER FALLBACK (Nov 2025):
- Primary: Spotify CDN (if URL available)
- Fallback: Deezer CDN (NO AUTH NEEDED - just search by name!)
- Fallback 2: CoverArtArchive (for albums with MusicBrainz ID)

Image sizes (per user specification):
- Artists: 300x300px (profile images, smaller is fine)
- Albums: 500x500px (cover art, needs more detail)
- Playlists: 300x300px (grid thumbnails)

Format: WebP (30% smaller than JPEG, supported everywhere now)

Storage structure:
  artwork/
    spotify/
      artists/
        {spotify_id}.webp
      albums/
        {spotify_id}.webp
      playlists/
        {playlist_id}.webp
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Literal, TYPE_CHECKING

import httpx
from PIL import Image as PILImage

from soulspot.config import Settings

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

logger = logging.getLogger(__name__)

# Hey future me - these sizes are user-specified, not arbitrary!
# Artists: Profile pics shown in lists, 300px is plenty
# Albums: Main cover art, needs detail for album view, 500px
# Playlists: Shown in sidebar/lists like artists, 300px
IMAGE_SIZES: dict[str, int] = {
    "artists": 300,
    "albums": 500,
    "playlists": 300,
}

# WebP quality - 85 is sweet spot for visual quality vs file size
WEBP_QUALITY = 85


# =============================================================================
# ERROR TRACKING (Jan 2025)
# Hey future me - structured error tracking for better debugging!
# Each error has a code and human-readable message.
# =============================================================================


class ImageDownloadErrorCode(Enum):
    """Error codes for image download failures."""

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
    UNKNOWN = "UNKNOWN"


@dataclass
class ImageDownloadResult:
    """Result of an image download operation.

    Hey future me - use this to track success/failure with detailed error info!
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


ImageType = Literal["artists", "albums", "playlists"]


class ArtworkService:
    """Service for downloading and managing UI artwork locally.

    Hey future me - this is the RENAMED SpotifyImageService (Jan 2025)!
    Now called ArtworkService because:
    1. It handles artwork for UI display (not ID3 embedding)
    2. It supports multiple sources (Spotify, Deezer, CoverArtArchive)
    3. Clearer separation from MetadataService (postprocessing/)

    Downloads images from CDNs, resizes them, converts to WebP,
    and stores locally for offline access and fast loading.

    Usage:
        service = ArtworkService(settings)
        path = await service.download_artist_image("0OdUWJ0sBjDrqHygGUXeCF", "https://i.scdn.co/...")
        # Returns: "spotify/artists/0OdUWJ0sBjDrqHygGUXeCF.webp"
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize with app settings.

        Args:
            settings: Application settings with storage paths.
        """
        self._settings = settings
        self._artwork_base = settings.storage.artwork_path
        self._spotify_path = self._artwork_base / "spotify"

        # Ensure directories exist
        for image_type in IMAGE_SIZES:
            (self._spotify_path / image_type).mkdir(parents=True, exist_ok=True)

    def _get_image_path(self, image_type: ImageType, entity_id: str) -> Path:
        """Get full filesystem path for an image.

        Args:
            image_type: Type of image ('artists', 'albums', 'playlists').
            entity_id: Spotify ID or playlist UUID.

        Returns:
            Full Path object for the image file.
        """
        return self._spotify_path / image_type / f"{entity_id}.webp"

    def _get_relative_path(self, image_type: ImageType, entity_id: str) -> str:
        """Get relative path (stored in DB) for an image.

        The relative path is stored in DB to avoid issues when base path changes.

        Args:
            image_type: Type of image.
            entity_id: Spotify ID or playlist UUID.

        Returns:
            Relative path string (e.g., "spotify/artists/abc123.webp").
        """
        return f"spotify/{image_type}/{entity_id}.webp"

    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path (from DB) to absolute filesystem path.

        Used when serving images or checking existence.

        Args:
            relative_path: Path stored in DB (e.g., "spotify/artists/abc123.webp").

        Returns:
            Full filesystem path.
        """
        return self._artwork_base / relative_path

    async def _download_and_process_image(
        self,
        url: str,
        target_size: int,
    ) -> bytes | None:
        """Download image from URL and process it.

        Downloads from CDN, resizes to target size (maintaining aspect ratio),
        and converts to WebP format.
        NOW USES HttpClientPool for connection reuse!

        Args:
            url: CDN URL.
            target_size: Target size in pixels (square).

        Returns:
            Processed WebP image bytes, or None if download failed.
        """
        if not url:
            return None

        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Process with Pillow
            # Hey - we run PIL in thread pool because it's CPU-bound and would block async
            image_data = await asyncio.to_thread(
                self._process_image_sync, response.content, target_size
            )
            return image_data

        except Exception as e:
            logger.warning(f"Error downloading/processing image from {url}: {e}")
            return None

    async def _download_and_process_image_with_result(
        self,
        url: str | None,
        target_size: int,
    ) -> tuple[bytes | None, ImageDownloadResult]:
        """Download and process image with detailed error tracking.

        Hey future me - this is the NEW version that returns structured errors!
        Use this for enrichment batch jobs where you want to track why things failed.

        Args:
            url: CDN URL (can be None).
            target_size: Target size in pixels (square).

        Returns:
            Tuple of (image_bytes or None, ImageDownloadResult with error details)
        """
        if not url:
            return None, ImageDownloadResult.error(
                ImageDownloadErrorCode.NO_URL,
                "No image URL provided",
                url,
            )

        try:
            from soulspot.infrastructure.integrations.http_pool import HttpClientPool

            client = await HttpClientPool.get_client()
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Process with Pillow
            try:
                image_data = await asyncio.to_thread(
                    self._process_image_sync, response.content, target_size
                )
                # Return success placeholder - actual path will be set by caller
                return image_data, ImageDownloadResult(success=True, url=url)
            except Exception as e:
                return None, ImageDownloadResult.error(
                    ImageDownloadErrorCode.PROCESSING_ERROR,
                    f"Image processing failed: {str(e)}",
                    url,
                )

        except httpx.HTTPStatusError as e:
            # Handle HTTP errors with specific codes
            status = e.response.status_code
            if status == 404:
                return None, ImageDownloadResult.error(
                    ImageDownloadErrorCode.HTTP_404,
                    "Image not found (404) - CDN may have removed or changed the image",
                    url,
                )
            elif status == 403:
                return None, ImageDownloadResult.error(
                    ImageDownloadErrorCode.HTTP_403,
                    "Access forbidden (403) - Rate limit or authentication issue",
                    url,
                )
            elif status >= 500:
                return None, ImageDownloadResult.error(
                    ImageDownloadErrorCode.HTTP_500,
                    f"Server error ({status}) - Try again later",
                    url,
                )
            else:
                return None, ImageDownloadResult.error(
                    ImageDownloadErrorCode.HTTP_OTHER,
                    f"HTTP error {status} downloading image",
                    url,
                )

        except httpx.TimeoutException:
            return None, ImageDownloadResult.error(
                ImageDownloadErrorCode.NETWORK_TIMEOUT,
                "Download timed out - CDN may be slow or unreachable",
                url,
            )

        except httpx.ConnectError:
            return None, ImageDownloadResult.error(
                ImageDownloadErrorCode.NETWORK_CONNECTION,
                "Connection failed - Check network connectivity",
                url,
            )

        except httpx.RequestError as e:
            return None, ImageDownloadResult.error(
                ImageDownloadErrorCode.NETWORK_OTHER,
                f"Network error: {str(e)}",
                url,
            )

        except Exception as e:
            logger.exception(f"Unexpected error downloading image from {url}: {e}")
            return None, ImageDownloadResult.error(
                ImageDownloadErrorCode.UNKNOWN,
                f"Unexpected error: {str(e)}",
                url,
            )

    def _process_image_sync(self, image_bytes: bytes, target_size: int) -> bytes:
        """Process image synchronously (runs in thread pool).

        Resizes to target size and converts to WebP.

        Args:
            image_bytes: Raw image data from download.
            target_size: Target size in pixels.

        Returns:
            Processed WebP image bytes.
        """
        with PILImage.open(BytesIO(image_bytes)) as img:
            # Convert to RGB if necessary (some images are RGBA or palette-based)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # Resize maintaining aspect ratio, fit in square
            # Hey - LANCZOS is the highest quality resampling filter
            img.thumbnail((target_size, target_size), PILImage.Resampling.LANCZOS)

            # Save as WebP
            output = BytesIO()
            img.save(output, format="WEBP", quality=WEBP_QUALITY, method=6)
            return output.getvalue()

    async def download_artist_image(
        self,
        spotify_id: str,
        image_url: str | None,
    ) -> str | None:
        """Download and save artist profile image.

        Args:
            spotify_id: Spotify artist ID.
            image_url: CDN URL for the image.

        Returns:
            Relative path to saved image (for DB storage), or None if failed.
        """
        if not image_url:
            logger.debug(f"No image URL for artist {spotify_id}")
            return None

        target_size = IMAGE_SIZES["artists"]
        image_data = await self._download_and_process_image(image_url, target_size)

        if not image_data:
            return None

        # Save to disk
        file_path = self._get_image_path("artists", spotify_id)
        await asyncio.to_thread(file_path.write_bytes, image_data)

        relative_path = self._get_relative_path("artists", spotify_id)
        logger.debug(f"Saved artist image: {relative_path} ({len(image_data)} bytes)")
        return relative_path

    async def download_album_image(
        self,
        spotify_id: str,
        image_url: str | None,
    ) -> str | None:
        """Download and save album cover image.

        Args:
            spotify_id: Spotify album ID.
            image_url: CDN URL for the cover.

        Returns:
            Relative path to saved image, or None if failed.
        """
        if not image_url:
            logger.debug(f"No image URL for album {spotify_id}")
            return None

        target_size = IMAGE_SIZES["albums"]
        image_data = await self._download_and_process_image(image_url, target_size)

        if not image_data:
            return None

        # Save to disk
        file_path = self._get_image_path("albums", spotify_id)
        await asyncio.to_thread(file_path.write_bytes, image_data)

        relative_path = self._get_relative_path("albums", spotify_id)
        logger.debug(f"Saved album image: {relative_path} ({len(image_data)} bytes)")
        return relative_path

    async def download_playlist_image(
        self,
        playlist_id: str,
        cover_url: str | None,
    ) -> str | None:
        """Download and save playlist cover image.

        Note: playlist_id can be Spotify URI or internal UUID.

        Args:
            playlist_id: Playlist ID (Spotify URI or internal).
            cover_url: CDN URL for the cover.

        Returns:
            Relative path to saved image, or None if failed.
        """
        if not cover_url:
            logger.debug(f"No cover URL for playlist {playlist_id}")
            return None

        target_size = IMAGE_SIZES["playlists"]
        image_data = await self._download_and_process_image(cover_url, target_size)

        if not image_data:
            return None

        # Save to disk - sanitize playlist_id in case it contains special chars
        safe_id = playlist_id.replace(":", "_").replace("/", "_")
        file_path = self._get_image_path("playlists", safe_id)
        await asyncio.to_thread(file_path.write_bytes, image_data)

        relative_path = self._get_relative_path("playlists", safe_id)
        logger.debug(f"Saved playlist image: {relative_path} ({len(image_data)} bytes)")
        return relative_path

    # =========================================================================
    # DETAILED ERROR TRACKING METHODS (Jan 2025)
    # Hey future me - use these for batch enrichment where you need to know
    # WHY something failed! Returns ImageDownloadResult with error details.
    # =========================================================================

    async def download_artist_image_with_result(
        self,
        spotify_id: str,
        image_url: str | None,
    ) -> ImageDownloadResult:
        """Download artist image with detailed error tracking.

        Hey future me - use this instead of download_artist_image() when you need
        to know WHY an image download failed (for error reporting in batch jobs)!

        Args:
            spotify_id: Spotify artist ID.
            image_url: CDN URL for the image.

        Returns:
            ImageDownloadResult with success/failure details.
        """
        target_size = IMAGE_SIZES["artists"]
        image_data, result = await self._download_and_process_image_with_result(
            image_url, target_size
        )

        if not result.success or not image_data:
            return result

        # Save to disk
        try:
            file_path = self._get_image_path("artists", spotify_id)
            await asyncio.to_thread(file_path.write_bytes, image_data)

            relative_path = self._get_relative_path("artists", spotify_id)
            logger.debug(
                f"Saved artist image: {relative_path} ({len(image_data)} bytes)"
            )
            return ImageDownloadResult.ok(relative_path)

        except OSError as e:
            from soulspot.infrastructure.observability.error_formatting import format_oserror_message
            msg = format_oserror_message(
                e, "save artist image", file_path, {"url": image_url, "size": f"{len(image_data)} bytes"}
            )
            logger.error(msg, exc_info=True)
            return ImageDownloadResult.error(
                ImageDownloadErrorCode.DISK_WRITE_ERROR,
                msg,
                image_url,
            )

    async def download_album_image_with_result(
        self,
        spotify_id: str,
        image_url: str | None,
    ) -> ImageDownloadResult:
        """Download album image with detailed error tracking.

        Args:
            spotify_id: Spotify album ID.
            image_url: CDN URL for the cover.

        Returns:
            ImageDownloadResult with success/failure details.
        """
        target_size = IMAGE_SIZES["albums"]
        image_data, result = await self._download_and_process_image_with_result(
            image_url, target_size
        )

        if not result.success or not image_data:
            return result

        # Save to disk
        try:
            file_path = self._get_image_path("albums", spotify_id)
            await asyncio.to_thread(file_path.write_bytes, image_data)

            relative_path = self._get_relative_path("albums", spotify_id)
            logger.debug(
                f"Saved album image: {relative_path} ({len(image_data)} bytes)"
            )
            return ImageDownloadResult.ok(relative_path)

        except OSError as e:
            from soulspot.infrastructure.observability.error_formatting import format_oserror_message
            msg = format_oserror_message(
                e, "save album image", file_path, {"url": image_url, "size": f"{len(image_data)} bytes"}
            )
            logger.error(msg, exc_info=True)
            return ImageDownloadResult.error(
                ImageDownloadErrorCode.DISK_WRITE_ERROR,
                msg,
                image_url,
            )

    def delete_image(self, relative_path: str | None) -> bool:
        """Delete an image file from disk.

        Call this when an entity is removed from DB (unfollowed artist, etc.).

        Args:
            relative_path: Relative path stored in DB, or None.

        Returns:
            True if deleted, False if not found or error.
        """
        if not relative_path:
            return False

        try:
            file_path = self.get_absolute_path(relative_path)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted image: {relative_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Error deleting image {relative_path}: {e}")
            return False

    async def delete_image_async(self, relative_path: str | None) -> bool:
        """Delete an image file asynchronously.

        Args:
            relative_path: Relative path stored in DB.

        Returns:
            True if deleted, False otherwise.
        """
        return await asyncio.to_thread(self.delete_image, relative_path)

    def image_exists(self, relative_path: str | None) -> bool:
        """Check if an image exists on disk.

        Args:
            relative_path: Relative path stored in DB.

        Returns:
            True if file exists.
        """
        if not relative_path:
            return False
        file_path = self.get_absolute_path(relative_path)
        return file_path.exists()

    async def should_redownload(
        self,
        stored_url: str | None,
        new_url: str | None,
        stored_path: str | None,
    ) -> bool:
        """Check if image should be re-downloaded.

        Re-download if:
        1. URL changed (source service updated the image)
        2. File doesn't exist (was deleted or first sync)
        3. New URL but no stored URL (new image added)

        Args:
            stored_url: Previously stored image_url from DB.
            new_url: Current image_url from API.
            stored_path: Stored image_path from DB.

        Returns:
            True if image should be downloaded.
        """
        # No new URL, nothing to download
        if not new_url:
            return False

        # URL changed - re-download
        if stored_url != new_url:
            logger.debug(f"Image URL changed: {stored_url} -> {new_url}")
            return True

        # File doesn't exist - download
        if not stored_path or not self.image_exists(stored_path):
            logger.debug(f"Image file missing: {stored_path}")
            return True

        return False

    def get_disk_usage(self) -> dict[str, int]:
        """Get disk usage statistics for artwork images.

        Returns dict with bytes used per category and total.

        Returns:
            Dict with 'artists', 'albums', 'playlists', 'total' byte counts.
        """
        usage: dict[str, int] = {}
        total = 0

        for image_type in IMAGE_SIZES:
            type_path = self._spotify_path / image_type
            if type_path.exists():
                type_bytes = sum(f.stat().st_size for f in type_path.glob("*.webp"))
                usage[image_type] = type_bytes
                total += type_bytes
            else:
                usage[image_type] = 0

        usage["total"] = total
        return usage

    async def get_disk_usage_async(self) -> dict[str, int]:
        """Get disk usage statistics asynchronously.

        Returns:
            Dict with byte counts per category.
        """
        return await asyncio.to_thread(self.get_disk_usage)

    def get_image_count(self) -> dict[str, int]:
        """Get count of images per category.

        Returns:
            Dict with 'artists', 'albums', 'playlists', 'total' counts.
        """
        counts: dict[str, int] = {}
        total = 0

        for image_type in IMAGE_SIZES:
            type_path = self._spotify_path / image_type
            if type_path.exists():
                count = len(list(type_path.glob("*.webp")))
                counts[image_type] = count
                total += count
            else:
                counts[image_type] = 0

        counts["total"] = total
        return counts

    async def cleanup_orphaned_images(
        self,
        valid_artist_ids: set[str],
        valid_album_ids: set[str],
        valid_playlist_ids: set[str],
    ) -> dict[str, int]:
        """Remove images that no longer have corresponding DB entities.

        Call this periodically or after bulk deletions to free disk space.

        Args:
            valid_artist_ids: Set of artist IDs still in DB.
            valid_album_ids: Set of album IDs still in DB.
            valid_playlist_ids: Set of playlist IDs still in DB.

        Returns:
            Dict with count of deleted images per category.
        """
        deleted: dict[str, int] = {"artists": 0, "albums": 0, "playlists": 0}

        # Check artists
        artists_path = self._spotify_path / "artists"
        if artists_path.exists():
            for img_file in artists_path.glob("*.webp"):
                spotify_id = img_file.stem
                if spotify_id not in valid_artist_ids:
                    await asyncio.to_thread(img_file.unlink)
                    deleted["artists"] += 1
                    logger.debug(f"Deleted orphaned artist image: {spotify_id}")

        # Check albums
        albums_path = self._spotify_path / "albums"
        if albums_path.exists():
            for img_file in albums_path.glob("*.webp"):
                spotify_id = img_file.stem
                if spotify_id not in valid_album_ids:
                    await asyncio.to_thread(img_file.unlink)
                    deleted["albums"] += 1
                    logger.debug(f"Deleted orphaned album image: {spotify_id}")

        # Check playlists
        playlists_path = self._spotify_path / "playlists"
        if playlists_path.exists():
            for img_file in playlists_path.glob("*.webp"):
                playlist_id = img_file.stem
                if playlist_id not in valid_playlist_ids:
                    await asyncio.to_thread(img_file.unlink)
                    deleted["playlists"] += 1
                    logger.debug(f"Deleted orphaned playlist image: {playlist_id}")

        total_deleted = sum(deleted.values())
        if total_deleted > 0:
            logger.info(
                f"Cleaned up {total_deleted} orphaned artwork images: {deleted}"
            )

        return deleted

    # =========================================================================
    # MULTI-PROVIDER FALLBACK METHODS (Nov 2025)
    # Hey future me - these methods try primary source first, then fall back!
    # Deezer CDN is FREE (no auth needed), perfect for when Spotify URLs fail.
    # =========================================================================

    async def download_artist_image_with_fallback(
        self,
        spotify_id: str,
        artist_name: str,
        spotify_image_url: str | None = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> ImageDownloadResult:
        """Download artist image with Deezer fallback.

        Hey future me - dieser Methode nutzt MULTI-PROVIDER für Bilder!
        Fallback-Kette: Spotify URL → Deezer (nach Name suchen) → Fail

        Deezer advantage: NO AUTH NEEDED for artist search!

        Args:
            spotify_id: Spotify artist ID (for file naming)
            artist_name: Artist name (for Deezer search fallback)
            spotify_image_url: Spotify CDN URL (optional)
            deezer_plugin: DeezerPlugin instance for fallback (optional)

        Returns:
            ImageDownloadResult with success/failure details
        """
        # 1. Try Spotify URL first
        if spotify_image_url:
            result = await self.download_artist_image_with_result(
                spotify_id, spotify_image_url
            )
            if result.success:
                return result
            logger.debug(
                f"Spotify image failed for {artist_name}, trying Deezer fallback: "
                f"{result.error_message}"
            )

        # 2. Try Deezer fallback (NO AUTH NEEDED!)
        if deezer_plugin and artist_name:
            try:
                deezer_url = await self._get_deezer_artist_image_url(
                    deezer_plugin, artist_name
                )
                if deezer_url:
                    target_size = IMAGE_SIZES["artists"]
                    image_data, dl_result = await self._download_and_process_image_with_result(
                        deezer_url, target_size
                    )

                    if image_data and dl_result.success:
                        # Save with Spotify ID (our primary key)
                        try:
                            file_path = self._get_image_path("artists", spotify_id)
                            await asyncio.to_thread(file_path.write_bytes, image_data)
                            relative_path = self._get_relative_path("artists", spotify_id)
                            logger.info(
                                f"Saved artist image from Deezer fallback: "
                                f"{artist_name} → {relative_path}"
                            )
                            return ImageDownloadResult.ok(relative_path)
                        except OSError as e:
                            logger.error(f"Failed to save Deezer artist image: {e}")

            except Exception as e:
                logger.debug(f"Deezer artist image fallback failed: {e}")

        # All sources failed
        return ImageDownloadResult.error(
            ImageDownloadErrorCode.NO_URL,
            f"No image found for artist '{artist_name}' from Spotify or Deezer",
            spotify_image_url,
        )

    async def download_album_image_with_fallback(
        self,
        spotify_id: str,
        album_title: str,
        artist_name: str,
        spotify_image_url: str | None = None,
        deezer_plugin: "DeezerPlugin | None" = None,
        musicbrainz_id: str | None = None,
    ) -> ImageDownloadResult:
        """Download album image with Deezer and CoverArtArchive fallback.

        Hey future me - dieser Methode nutzt MULTI-PROVIDER für Album-Cover!
        Fallback-Kette: Spotify URL → Deezer (search) → CoverArtArchive → Fail

        Args:
            spotify_id: Spotify album ID (for file naming)
            album_title: Album title (for Deezer search)
            artist_name: Artist name (for Deezer search)
            spotify_image_url: Spotify CDN URL (optional)
            deezer_plugin: DeezerPlugin instance for fallback (optional)
            musicbrainz_id: MusicBrainz release ID for CoverArtArchive (optional)

        Returns:
            ImageDownloadResult with success/failure details
        """
        # 1. Try Spotify URL first
        if spotify_image_url:
            result = await self.download_album_image_with_result(
                spotify_id, spotify_image_url
            )
            if result.success:
                return result
            logger.debug(
                f"Spotify album image failed for '{album_title}', trying fallbacks: "
                f"{result.error_message}"
            )

        # 2. Try Deezer fallback (NO AUTH NEEDED!)
        if deezer_plugin and album_title and artist_name:
            try:
                deezer_url = await self._get_deezer_album_image_url(
                    deezer_plugin, album_title, artist_name
                )
                if deezer_url:
                    target_size = IMAGE_SIZES["albums"]
                    image_data, dl_result = await self._download_and_process_image_with_result(
                        deezer_url, target_size
                    )

                    if image_data and dl_result.success:
                        try:
                            file_path = self._get_image_path("albums", spotify_id)
                            await asyncio.to_thread(file_path.write_bytes, image_data)
                            relative_path = self._get_relative_path("albums", spotify_id)
                            logger.info(
                                f"Saved album image from Deezer fallback: "
                                f"'{album_title}' by {artist_name} → {relative_path}"
                            )
                            return ImageDownloadResult.ok(relative_path)
                        except OSError as e:
                            logger.error(f"Failed to save Deezer album image: {e}")

            except Exception as e:
                logger.debug(f"Deezer album image fallback failed: {e}")

        # 3. Try CoverArtArchive fallback (if we have MusicBrainz ID)
        if musicbrainz_id:
            try:
                caa_url = f"https://coverartarchive.org/release/{musicbrainz_id}/front"
                target_size = IMAGE_SIZES["albums"]
                image_data, dl_result = await self._download_and_process_image_with_result(
                    caa_url, target_size
                )

                if image_data and dl_result.success:
                    try:
                        file_path = self._get_image_path("albums", spotify_id)
                        await asyncio.to_thread(file_path.write_bytes, image_data)
                        relative_path = self._get_relative_path("albums", spotify_id)
                        logger.info(
                            f"Saved album image from CoverArtArchive fallback: "
                            f"'{album_title}' → {relative_path}"
                        )
                        return ImageDownloadResult.ok(relative_path)
                    except OSError as e:
                        logger.error(f"Failed to save CoverArtArchive album image: {e}")

            except Exception as e:
                logger.debug(f"CoverArtArchive fallback failed: {e}")

        # All sources failed
        return ImageDownloadResult.error(
            ImageDownloadErrorCode.NO_URL,
            f"No image found for album '{album_title}' from Spotify, Deezer, or CoverArtArchive",
            spotify_image_url,
        )

    async def _get_deezer_artist_image_url(
        self,
        deezer_plugin: "DeezerPlugin",
        artist_name: str,
    ) -> str | None:
        """Search Deezer for an artist and get their image URL.

        Hey future me - Deezer search is FREE, no auth needed!
        We search by name and take the first matching result's picture.

        Args:
            deezer_plugin: DeezerPlugin instance
            artist_name: Artist name to search for

        Returns:
            Deezer CDN image URL or None
        """
        try:
            search_result = await deezer_plugin.search_artists(
                query=artist_name, limit=3
            )

            if not search_result.items:
                logger.debug(f"No Deezer artist found for '{artist_name}'")
                return None

            # Take the first match
            artist_dto = search_result.items[0]

            # ArtistDTO.image is ImageRef with .url property
            if artist_dto.image.url:
                logger.debug(
                    f"Found Deezer image for '{artist_name}': {artist_dto.image.url[:50]}..."
                )
                return artist_dto.image.url

            return None

        except Exception as e:
            logger.debug(f"Deezer artist search failed for '{artist_name}': {e}")
            return None

    async def _get_deezer_album_image_url(
        self,
        deezer_plugin: "DeezerPlugin",
        album_title: str,
        artist_name: str,
    ) -> str | None:
        """Search Deezer for an album and get its cover URL.

        Hey future me - Deezer album search is FREE, no auth needed!
        Search query combines artist + album for better matching.

        Args:
            deezer_plugin: DeezerPlugin instance
            album_title: Album title to search for
            artist_name: Artist name for better matching

        Returns:
            Deezer CDN cover URL or None
        """
        try:
            # Combine artist and album for better search
            search_query = f"{artist_name} {album_title}"
            search_result = await deezer_plugin.search_albums(
                query=search_query, limit=5
            )

            if not search_result.items:
                logger.debug(f"No Deezer album found for '{album_title}' by {artist_name}")
                return None

            # Find best match (prefer exact title match)
            best_match = None
            album_title_lower = album_title.lower().strip()
            artist_name_lower = artist_name.lower().strip()

            for album_dto in search_result.items:
                if (
                    album_dto.title.lower().strip() == album_title_lower
                    and album_dto.artist_name
                    and album_dto.artist_name.lower().strip() == artist_name_lower
                ):
                    best_match = album_dto
                    break

            # Fallback to first result if no exact match
            if not best_match:
                best_match = search_result.items[0]

            # AlbumDTO.cover is ImageRef with .url property
            if best_match.cover.url:
                logger.debug(
                    f"Found Deezer cover for '{album_title}': "
                    f"{best_match.cover.url[:50]}..."
                )
                return best_match.cover.url

            return None

        except Exception as e:
            logger.debug(
                f"Deezer album search failed for '{album_title}' by {artist_name}: {e}"
            )
            return None
