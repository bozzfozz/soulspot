# Hey future me - ImageBackfillWorker is a THIN WRAPPER around repair functions!
#
# REFACTORED (Dec 2025): Now uses modern repair functions directly from images/repair.py,
# not the deprecated ImageRepairService wrapper!
#
# What this worker does:
# - Runs periodically (default: every 30 minutes)
# - Checks settings (library.auto_fetch_artwork, library.download_images)
# - Calls repair_artist_images() and repair_album_images() directly
#
# What repair functions handle:
# - Finding entities with missing images
# - FAILED marker logic (24h retry)
# - API fallback (Deezer → Spotify → MusicBrainz)
# - Image downloading via ImageService
#
# This design avoids code duplication and ensures consistent behavior
# between manual repair (API) and automatic backfill (background).
"""Image Backfill Worker - Thin wrapper around repair functions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.config import Settings

logger = logging.getLogger(__name__)


class ImageBackfillWorker:
    """Background worker that delegates to ImageRepairService.

    Hey future me - this is now a THIN WRAPPER!
    All image download logic is in ImageRepairService.
    This worker just handles scheduling and settings checks.

    Key features:
    - Runs every 30 minutes by default (configurable)
    - Respects library.auto_fetch_artwork and library.download_images settings
    - Delegates to ImageRepairService for actual work
    - Graceful shutdown support
    """

    def __init__(
        self,
        db: Any,  # Database instance
        settings: Settings,  # Settings instance
        run_interval_minutes: int = 30,  # Default: 30 minutes
        batch_size: int = 100,  # Max items per entity type per cycle (increased from 50)
    ) -> None:
        """Initialize image backfill worker.

        Args:
            db: Database instance for session creation
            settings: Application settings (for image paths)
            run_interval_minutes: How often to run backfill (default 30 min)
            batch_size: Max artists/albums to process per cycle (default 100)
        """
        self.db = db
        self.settings = settings
        self.check_interval_seconds = run_interval_minutes * 60
        self.batch_size = batch_size
        self._running = False
        self._task: asyncio.Task[None] | None = None
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
        logger.info(
            "🖼️ ImageBackfillWorker: Waiting 2 minutes for startup to complete..."
        )
        await asyncio.sleep(120)
        logger.info("🖼️ ImageBackfillWorker: Starting main loop")

        while self._running:
            try:
                logger.info(
                    f"🖼️ ImageBackfillWorker: Starting backfill cycle (batch_size={self.batch_size})"
                )
                stats = await self._run_backfill_cycle()
                self._last_run_at = datetime.now(UTC)
                self._last_run_stats = stats

                total_repaired = stats.get("artists_repaired", 0) + stats.get(
                    "albums_repaired", 0
                )
                total_processed = stats.get("artists_processed", 0) + stats.get(
                    "albums_processed", 0
                )
                total_errors = len(stats.get("errors", []))

                logger.info("=" * 50)
                logger.info("🖼️ IMAGE BACKFILL CYCLE COMPLETE")
                logger.info("=" * 50)
                logger.info(
                    f"  ✅ Repaired: {total_repaired} (artists: {stats.get('artists_repaired', 0)}, albums: {stats.get('albums_repaired', 0)})"
                )
                logger.info(f"  📊 Processed: {total_processed}")
                logger.info(f"  ❌ Errors: {total_errors}")
                if stats.get("skipped_disabled"):
                    logger.info("  ⏭️ Skipped: Image downloads disabled in settings")
                logger.info(
                    f"  ⏱️ Next run in: {self.check_interval_seconds // 60} minutes"
                )
                logger.info("=" * 50)

            except Exception as e:
                logger.error(
                    f"💥 Error in image backfill worker loop: {e}", exc_info=True
                )

            # Wait for next cycle
            await asyncio.sleep(self.check_interval_seconds)

    async def _run_backfill_cycle(self) -> dict[str, Any]:
        """Run a complete backfill cycle using ImageRepairService.

        Hey future me - this delegates to ImageRepairService!
        No duplicate download logic here anymore.

        Returns:
            Stats dict with counts
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "artists_repaired": 0,
            "artists_processed": 0,
            "albums_repaired": 0,
            "albums_processed": 0,
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

            # Use modern repair functions directly (not deprecated wrapper!)
            # REFACTORED (Dec 2025): No more ImageRepairService wrapper!
            from soulspot.application.services.images import ImageService
            from soulspot.application.services.images.image_provider_registry import (
                ImageProviderRegistry,
            )
            from soulspot.application.services.images.repair import (
                repair_album_images,
                repair_artist_images,
            )
            from soulspot.infrastructure.plugins import DeezerPlugin
            from soulspot.infrastructure.providers.deezer_image_provider import (
                DeezerImageProvider,
            )

            image_service = ImageService(
                cache_base_path=str(self.settings.storage.image_path),
                local_serve_prefix="/api/images",
            )

            # Create ImageProviderRegistry with Deezer (no auth needed!)
            # Hey future me - DeezerImageProvider allows API fallback
            # when CDN URL is missing or invalid.
            # NOTE: register(provider, priority) - provider first, priority second!
            deezer_plugin = DeezerPlugin()
            deezer_provider = DeezerImageProvider(deezer_plugin)
            image_provider_registry = ImageProviderRegistry()
            image_provider_registry.register(deezer_provider, priority=2)

            # Phase 1: Repair artist images (modern function!)
            artist_result = await repair_artist_images(
                session=session,
                image_service=image_service,
                image_provider_registry=image_provider_registry,
                spotify_plugin=None,
                limit=self.batch_size,
            )
            stats["artists_processed"] = artist_result.get("processed", 0)
            stats["artists_repaired"] = artist_result.get("repaired", 0)
            stats["errors"].extend(artist_result.get("errors", []))

            # Phase 2: Repair album images (modern function!)
            album_result = await repair_album_images(
                session=session,
                image_service=image_service,
                image_provider_registry=image_provider_registry,
                limit=self.batch_size,
            )
            stats["albums_processed"] = album_result.get("processed", 0)
            stats["albums_repaired"] = album_result.get("repaired", 0)
            stats["errors"].extend(album_result.get("errors", []))

            # Commit all changes
            await session.commit()

        stats["completed_at"] = datetime.now(UTC).isoformat()
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


# Alias for new naming convention
ImageWorker = ImageBackfillWorker
