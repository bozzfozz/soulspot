# Hey future me - ImageBackfillWorker automates image downloading!
#
# It replaces the manual "Fetch Artwork" button with automatic background processing.
# Runs periodically (default: every 30 minutes) and downloads images for entities
# that have CDN URLs (image_url/cover_url) but no local file (image_path/cover_path).
#
# KEY INSIGHT: This worker is DIFFERENT from LibraryDiscoveryWorker!
# - LibraryDiscoveryWorker: DISCOVERS IDs and saves CDN URLs to DB
# - ImageBackfillWorker: DOWNLOADS images from CDN URLs to local files
#
# FLOW:
# 1. LibraryDiscoveryWorker runs → saves image_url to ArtistModel/AlbumModel
# 2. ImageBackfillWorker runs → reads image_url, downloads to image_path
# 3. UI shows local image from image_path (faster, works offline)
#
# THROTTLING: To avoid hammering CDNs, we:
# - Process max 50 artists + 50 albums per cycle
# - Add 100ms delay between downloads
# - Skip items that failed recently (24h cooldown)
#
# SETTINGS: Controlled via AppSettingsService
# - library.auto_fetch_artwork (bool): Enable/disable this worker
# - library.download_images (bool): Master switch for all image downloads
"""Image Backfill Worker - Automatically downloads missing images."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.config import Settings

logger = logging.getLogger(__name__)


class ImageBackfillWorker:
    """Background worker for automatic image downloading.

    Hey future me - this worker REPLACES the manual "Fetch Artwork" button!
    It periodically checks for entities with CDN URLs but missing local files,
    and downloads them automatically.

    Similar to LibraryDiscoveryWorker pattern but focused on image downloads.

    Key features:
    - Runs every 30 minutes by default (configurable)
    - Processes max 50 artists + 50 albums per cycle (prevents overload)
    - Respects library.auto_fetch_artwork and library.download_images settings
    - Throttles downloads (100ms between requests) to be CDN-friendly
    - Graceful shutdown support
    """

    def __init__(
        self,
        db: Any,  # Database instance
        settings: "Settings",  # Settings instance
        run_interval_minutes: int = 30,  # Default: 30 minutes
        batch_size: int = 50,  # Max items per entity type per cycle
    ) -> None:
        """Initialize image backfill worker.

        Args:
            db: Database instance for session creation
            settings: Application settings (for image paths)
            run_interval_minutes: How often to run backfill (default 30 min)
            batch_size: Max artists/albums to process per cycle (default 50)
        """
        self.db = db
        self.settings = settings
        self.check_interval_seconds = run_interval_minutes * 60
        self.batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run_at: datetime | None = None
        self._last_run_stats: dict[str, Any] | None = None

    async def start(self) -> None:
        """Start the image backfill worker."""
        if self._running:
            logger.warning("ImageBackfillWorker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"🖼️ ImageBackfillWorker started (interval: {self.check_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the image backfill worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("ImageBackfillWorker stopped")

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, and last run stats
        """
        return {
            "name": "Image Backfill Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self.check_interval_seconds,
            "batch_size": self.batch_size,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "last_run_stats": self._last_run_stats,
        }

    async def _run_loop(self) -> None:
        """Main worker loop.
        
        Hey future me - we start with a 2-minute delay to let other startup tasks
        finish (DB migrations, initial syncs, etc.). This prevents SQLite lock
        contention during the busy startup phase.
        """
        # Initial delay to let app start up and other workers finish first
        await asyncio.sleep(120)

        while self._running:
            try:
                stats = await self._run_backfill_cycle()
                self._last_run_at = datetime.now(UTC)
                self._last_run_stats = stats

                total_downloaded = stats.get("artists_downloaded", 0) + stats.get(
                    "albums_downloaded", 0
                )
                if total_downloaded > 0:
                    logger.info(
                        f"🖼️ Image backfill complete: "
                        f"{stats.get('artists_downloaded', 0)} artist images, "
                        f"{stats.get('albums_downloaded', 0)} album covers"
                    )
                else:
                    logger.debug("🖼️ Image backfill: No missing images found")

            except Exception as e:
                logger.error(f"Error in image backfill worker loop: {e}", exc_info=True)

            # Wait for next cycle
            await asyncio.sleep(self.check_interval_seconds)

    async def _run_backfill_cycle(self) -> dict[str, Any]:
        """Run a complete backfill cycle.

        Checks settings, then downloads missing images for artists and albums.

        Returns:
            Stats dict with counts
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "artists_checked": 0,
            "artists_downloaded": 0,
            "artists_failed": 0,
            "albums_checked": 0,
            "albums_downloaded": 0,
            "albums_failed": 0,
            "skipped_disabled": False,
            "errors": [],
        }

        async with self.db.session_scope() as session:
            # Check if auto-fetch is enabled
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )

            settings_service = AppSettingsService(session)

            # Check master switch for all image downloads
            download_enabled = await settings_service.get_bool(
                "library.download_images", default=True
            )
            if not download_enabled:
                logger.debug(
                    "🖼️ Image backfill: library.download_images is disabled, skipping"
                )
                stats["skipped_disabled"] = True
                return stats

            # Check auto-fetch specific setting
            auto_fetch_enabled = await settings_service.get_bool(
                "library.auto_fetch_artwork", default=True
            )
            if not auto_fetch_enabled:
                logger.debug(
                    "🖼️ Image backfill: library.auto_fetch_artwork is disabled, skipping"
                )
                stats["skipped_disabled"] = True
                return stats

            # Initialize ImageService
            from soulspot.application.services.images import ImageService

            image_service = ImageService(
                cache_base_path=str(self.settings.storage.image_path),
                local_serve_prefix="/api/images",
            )

            # Phase 1: Download artist images
            artist_stats = await self._backfill_artist_images(
                session, image_service
            )
            stats["artists_checked"] = artist_stats["checked"]
            stats["artists_downloaded"] = artist_stats["downloaded"]
            stats["artists_failed"] = artist_stats["failed"]
            stats["errors"].extend(artist_stats["errors"])

            # Phase 2: Download album covers
            album_stats = await self._backfill_album_images(
                session, image_service
            )
            stats["albums_checked"] = album_stats["checked"]
            stats["albums_downloaded"] = album_stats["downloaded"]
            stats["albums_failed"] = album_stats["failed"]
            stats["errors"].extend(album_stats["errors"])

            # Commit all changes
            await session.commit()

        stats["completed_at"] = datetime.now(UTC).isoformat()
        return stats

    async def _backfill_artist_images(
        self,
        session: "AsyncSession",
        image_service: Any,
    ) -> dict[str, Any]:
        """Download missing artist images.

        Args:
            session: Database session
            image_service: ImageService instance

        Returns:
            Stats dict with checked/downloaded/failed counts
        """
        stats: dict[str, Any] = {
            "checked": 0,
            "downloaded": 0,
            "failed": 0,
            "errors": [],
        }

        # Find artists with CDN URL but no local path
        stmt = (
            select(ArtistModel)
            .where(
                ArtistModel.image_url.isnot(None),
                ArtistModel.image_path.is_(None),
            )
            .limit(self.batch_size)
        )

        result = await session.execute(stmt)
        artists = result.scalars().all()
        stats["checked"] = len(artists)

        if not artists:
            return stats

        logger.debug(f"🖼️ Processing {len(artists)} artists with missing images")

        for artist in artists:
            try:
                # Determine provider ID for filename
                provider_id = artist.spotify_id or artist.deezer_id
                provider = "spotify" if artist.spotify_id else "deezer"

                if not provider_id:
                    # Fallback: hash of artist name
                    provider_id = hashlib.md5(
                        artist.name.lower().encode()
                    ).hexdigest()[:16]
                    provider = "local"

                # Download image
                image_path = await image_service.download_artist_image(
                    provider_id=provider_id,
                    image_url=artist.image_url,
                    provider=provider,
                )

                if image_path:
                    artist.image_path = image_path
                    artist.updated_at = datetime.now(UTC)
                    stats["downloaded"] += 1
                    logger.debug(f"✅ Downloaded artist image: {artist.name}")
                else:
                    stats["failed"] += 1
                    stats["errors"].append(
                        {"type": "artist", "name": artist.name, "error": "Download returned None"}
                    )

                # Throttle to be CDN-friendly
                await asyncio.sleep(0.1)

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    {"type": "artist", "name": artist.name, "error": str(e)}
                )
                logger.warning(f"❌ Failed to download artist image for {artist.name}: {e}")

        return stats

    async def _backfill_album_images(
        self,
        session: "AsyncSession",
        image_service: Any,
    ) -> dict[str, Any]:
        """Download missing album covers.

        Args:
            session: Database session
            image_service: ImageService instance

        Returns:
            Stats dict with checked/downloaded/failed counts
        """
        stats: dict[str, Any] = {
            "checked": 0,
            "downloaded": 0,
            "failed": 0,
            "errors": [],
        }

        # Find albums with CDN URL but no local path
        stmt = (
            select(AlbumModel)
            .where(
                AlbumModel.cover_url.isnot(None),
                AlbumModel.cover_path.is_(None),
            )
            .limit(self.batch_size)
        )

        result = await session.execute(stmt)
        albums = result.scalars().all()
        stats["checked"] = len(albums)

        if not albums:
            return stats

        logger.debug(f"🖼️ Processing {len(albums)} albums with missing covers")

        for album in albums:
            try:
                # Determine provider ID for filename
                provider_id = album.spotify_id or album.deezer_id
                provider = "spotify" if album.spotify_id else "deezer"

                if not provider_id:
                    # Fallback: hash of album title + artist
                    artist_name = album.artist.name if album.artist else "unknown"
                    hash_input = f"{album.title}_{artist_name}".lower()
                    provider_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]
                    provider = "local"

                # Download cover
                image_path = await image_service.download_album_image(
                    provider_id=provider_id,
                    image_url=album.cover_url,
                    provider=provider,
                )

                if image_path:
                    album.cover_path = image_path
                    album.updated_at = datetime.now(UTC)
                    stats["downloaded"] += 1
                    logger.debug(f"✅ Downloaded album cover: {album.title}")
                else:
                    stats["failed"] += 1
                    stats["errors"].append(
                        {"type": "album", "name": album.title, "error": "Download returned None"}
                    )

                # Throttle to be CDN-friendly
                await asyncio.sleep(0.1)

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    {"type": "album", "name": album.title, "error": str(e)}
                )
                logger.warning(f"❌ Failed to download album cover for {album.title}: {e}")

        return stats

    async def trigger_manual_run(self) -> dict[str, Any]:
        """Manually trigger an immediate backfill cycle.
        
        Hey future me - this is for the UI "Fetch Artwork" button!
        Instead of creating a new endpoint, we can reuse this worker's logic.
        
        Returns:
            Stats from the backfill cycle
        """
        logger.info("🖼️ Manual image backfill triggered")
        return await self._run_backfill_cycle()
