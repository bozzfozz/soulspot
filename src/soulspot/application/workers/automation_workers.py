"""Background workers for automation features."""

import asyncio
import contextlib
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.automation_workflow_service import (
    AutomationWorkflowService,
)
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.entities import AutomationTrigger
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


class WatchlistWorker:
    """Background worker for checking artist watchlists for new releases."""

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
        check_interval_seconds: int = 3600,  # Default: 1 hour
    ) -> None:
        """Initialize watchlist worker.

        Args:
            session: Database session
            spotify_client: Spotify client for fetching releases
            check_interval_seconds: How often to check watchlists
        """
        self.session = session
        self.spotify_client = spotify_client
        self.check_interval_seconds = check_interval_seconds
        self.watchlist_service = WatchlistService(session, spotify_client)
        self.workflow_service = AutomationWorkflowService(session)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the watchlist worker."""
        if self._running:
            logger.warning("Watchlist worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Watchlist worker started (check interval: {self.check_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the watchlist worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Watchlist worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._check_watchlists()
            except Exception as e:
                logger.error(f"Error in watchlist worker loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Hey future me: Watchlist worker - background daemon that polls Spotify for new releases
    # WHY check every hour? Balance between finding new releases quickly vs API rate limits
    # WHY separate worker? Long-running process, can't block main application
    # GOTCHA: If Spotify access token expires, worker silently fails until token refreshed
    # TODO: Add automatic token refresh or at least alert when token is stale
    async def _check_watchlists(self) -> None:
        """Check all due watchlists for new releases."""
        try:
            # Get watchlists that need checking
            watchlists = await self.watchlist_service.list_due_for_check(limit=100)

            if not watchlists:
                logger.debug("No watchlists due for checking")
                return

            logger.info(f"Checking {len(watchlists)} watchlists for new releases")

            for watchlist in watchlists:
                try:
                    # Check for new releases using Spotify API
                    logger.info(f"Checking watchlist for artist {watchlist.artist_id}")

                    # Get access token (this should be obtained from the session or config)
                    # For now, we'll skip if no spotify_client is available
                    if not self.spotify_client:
                        logger.warning(
                            "Spotify client not available, skipping release check"
                        )
                        watchlist.update_check(releases_found=0, downloads_triggered=0)
                        await self.watchlist_service.repository.update(watchlist)
                        await self.session.commit()
                        continue

                    # Note: In a real implementation, we'd need to get the access token
                    # from a secure location (e.g., service account or user session)
                    # For now, this will log an info message
                    logger.info(
                        f"Would check Spotify for new releases from artist {watchlist.artist_id}. "
                        "Integration requires valid access token."
                    )

                    # Trigger automation workflows for new releases if auto_download is enabled
                    if watchlist.auto_download:
                        context = {
                            "artist_id": str(watchlist.artist_id.value),
                            "watchlist_id": str(watchlist.id.value),
                            "quality_profile": watchlist.quality_profile,
                        }
                        # Trigger the automation workflow
                        await self.workflow_service.trigger_workflow(
                            trigger=AutomationTrigger.NEW_RELEASE,
                            context=context,
                        )

                    # Update check time
                    watchlist.update_check(releases_found=0, downloads_triggered=0)
                    await self.watchlist_service.repository.update(watchlist)
                    await self.session.commit()

                except Exception as e:
                    logger.error(
                        f"Error checking watchlist {watchlist.id}: {e}",
                        exc_info=True,
                    )
                    await self.session.rollback()

        except Exception as e:
            logger.error(f"Error in watchlist checking: {e}", exc_info=True)

    async def _trigger_automation(
        self, watchlist: Any, new_releases: list[dict[str, Any]]
    ) -> None:
        """Trigger automation workflows for new releases.

        Args:
            watchlist: Artist watchlist
            new_releases: List of new release information
        """
        for release in new_releases:
            context = {
                "artist_id": str(watchlist.artist_id.value),
                "watchlist_id": str(watchlist.id.value),
                "release_info": release,
                "quality_profile": watchlist.quality_profile,
            }

            await self.workflow_service.trigger_workflow(
                trigger=AutomationTrigger.NEW_RELEASE,
                context=context,
            )


class DiscographyWorker:
    """Background worker for checking artist discography completeness."""

    # Hey future me: Discography worker - the "complete your collection" automation
    # WHY 24h check interval? Artist discographies rarely change (few new albums per year)
    # This is more intensive than watchlist checking because we fetch ENTIRE discography
    # WHY Spotify client? MB doesn't have complete discographies for all artists
    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
        check_interval_seconds: int = 86400,  # Default: 24 hours
    ) -> None:
        """Initialize discography worker.

        Args:
            session: Database session
            spotify_client: Spotify client for fetching discography
            check_interval_seconds: How often to check discography
        """
        self.session = session
        self.spotify_client = spotify_client
        self.check_interval_seconds = check_interval_seconds
        self.discography_service = DiscographyService(session, spotify_client)
        self.workflow_service = AutomationWorkflowService(session)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the discography worker."""
        if self._running:
            logger.warning("Discography worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Discography worker started (check interval: {self.check_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the discography worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Discography worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._check_discographies()
            except Exception as e:
                logger.error(f"Error in discography worker loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Yo, discography check is STUBBED OUT (implementation needed)
    # WHY not implemented? This is complex - need to query Spotify for ALL albums, compare with local library,
    # detect missing albums (not just tracks), and queue downloads. Could hammer Spotify API hard if you
    # have 100+ artists with 10+ albums each. The TODO comments show the plan but needs careful implementation
    # with rate limiting, pagination, and error handling. Don't enable this worker until implemented!
    async def _check_discographies(self) -> None:
        """Check discography completeness for all artists.

        Implementation needed to:
        1. Query all artists with watchlists or auto-download enabled
        2. For each artist, fetch complete discography from Spotify
        3. Compare with local library to identify missing albums
        4. Trigger automation workflows for missing albums
        """
        try:
            # TODO: Get list of artists to check
            # Implementation steps:
            # 1. Query watchlist repository for active artists
            # 2. For each artist:
            #    - missing_albums = await self.discography_service.check_discography(artist_id, access_token)
            #    - if missing_albums and auto_download enabled:
            #        await self._trigger_automation(artist, missing_albums)
            logger.info("Checking artist discographies")

            # artists = await self._get_artists_to_check()
            # for artist in artists:
            #     missing_albums = await self.discography_service.check_discography(...)
            #     if missing_albums:
            #         await self._trigger_automation(artist, missing_albums)

        except Exception as e:
            logger.error(f"Error in discography checking: {e}", exc_info=True)


class QualityUpgradeWorker:
    """Background worker for detecting quality upgrade opportunities."""

    # Listen up future me: Quality upgrade worker - the "replace your 128kbps MP3s with FLAC" automation
    # WHY 24h check interval? Quality of existing files doesn't change, new sources might appear gradually
    # This scans LOCAL library (not external APIs) so less rate-limit concerns than other workers
    # GOTCHA: Comparing quality is subjective - bitrate alone doesn't tell full story (lossy vs lossless)
    def __init__(
        self,
        session: AsyncSession,
        check_interval_seconds: int = 86400,  # Default: 24 hours
    ) -> None:
        """Initialize quality upgrade worker.

        Args:
            session: Database session
            check_interval_seconds: How often to check for upgrades
        """
        self.session = session
        self.check_interval_seconds = check_interval_seconds
        self.quality_service = QualityUpgradeService(session)
        self.workflow_service = AutomationWorkflowService(session)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the quality upgrade worker."""
        if self._running:
            logger.warning("Quality upgrade worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Quality upgrade worker started (check interval: {self.check_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the quality upgrade worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Quality upgrade worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._identify_upgrades()
            except Exception as e:
                logger.error(f"Error in quality upgrade worker loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Hey future me: Quality upgrade identification is STUBBED (implementation needed)
    # WHY not implemented? This is complex - need to scan all files, extract bitrates/formats,
    # search Soulseek for better versions, calculate "improvement score" (320kbps->FLAC is worth it,
    # 256kbps->320kbps maybe not), and avoid downloading inferior "upgrades" (downsampled FLACs are a trap!).
    # Also need to handle edge cases like different masterings (2011 remaster might be louder but not "better").
    # The TODO shows the plan. Don't enable until implemented with proper quality heuristics!
    async def _identify_upgrades(self) -> None:
        """Identify quality upgrade opportunities.

        Implementation needed to:
        1. Scan library for tracks with lower quality files
        2. Search slskd for higher quality alternatives
        3. Calculate improvement score based on bitrate/format
        4. Create upgrade candidates for tracks meeting threshold
        5. Trigger automation workflows for approved upgrades
        """
        try:
            logger.info("Identifying quality upgrade opportunities")

            # TODO: Implement actual upgrade identification
            # Implementation steps:
            # 1. Get tracks from library with quality below target
            # 2. For each track:
            #    - candidates = await self.quality_service.identify_upgrade_opportunities(track_id)
            #    - if candidates meet improvement threshold:
            #        await self._trigger_automation(candidate)
            # candidates = await self.quality_service.identify_upgrade_opportunities(...)
            # for candidate in candidates:
            #     await self._trigger_automation(candidate)

        except Exception as e:
            logger.error(f"Error in quality upgrade identification: {e}", exc_info=True)


class AutomationWorkerManager:
    """Manager for all automation background workers."""

    # Yo, the manager class - starts/stops all three workers as a unit
    # WHY manager? So you can start/stop all automation with one call instead of managing three workers
    # GOTCHA: All workers share same DB session - concurrent access could cause conflicts if not careful
    # The interval params let you tune each worker independently (watchlist hourly, others daily)
    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
        watchlist_interval: int = 3600,
        discography_interval: int = 86400,
        quality_interval: int = 86400,
    ) -> None:
        """Initialize automation worker manager.

        Args:
            session: Database session
            spotify_client: Spotify client
            watchlist_interval: Watchlist check interval in seconds
            discography_interval: Discography check interval in seconds
            quality_interval: Quality upgrade check interval in seconds
        """
        self.watchlist_worker = WatchlistWorker(
            session, spotify_client, watchlist_interval
        )
        self.discography_worker = DiscographyWorker(
            session, spotify_client, discography_interval
        )
        self.quality_worker = QualityUpgradeWorker(session, quality_interval)

    # Hey future me: Start all three workers in parallel with asyncio.gather equivalents
    # Each worker.start() creates an async task that runs forever in background
    # WHY await each start()? To ensure all workers actually started before returning
    # GOTCHA: If any start() fails, others might already be running - no rollback!
    async def start_all(self) -> None:
        """Start all automation workers."""
        await self.watchlist_worker.start()
        await self.discography_worker.start()
        await self.quality_worker.start()
        logger.info("All automation workers started")

    # Listen, graceful shutdown - stop all workers and wait for their loops to exit
    # WHY await each stop()? To ensure tasks actually cancelled before app shutdown
    # Order doesn't matter - workers are independent. Stops are idempotent (safe to call twice).
    async def stop_all(self) -> None:
        """Stop all automation workers."""
        await self.watchlist_worker.stop()
        await self.discography_worker.stop()
        await self.quality_worker.stop()
        logger.info("All automation workers stopped")

    # Yo, health check helper - returns dict of running status for monitoring/dashboard
    # Accesses _running flags directly - not thread-safe but these are bool reads so low risk
    # Returns snapshot - status might change immediately after this returns!
    def get_status(self) -> dict[str, bool]:
        """Get status of all workers.

        Returns:
            Dictionary mapping worker name to running status
        """
        return {
            "watchlist": self.watchlist_worker._running,
            "discography": self.discography_worker._running,
            "quality_upgrade": self.quality_worker._running,
        }
