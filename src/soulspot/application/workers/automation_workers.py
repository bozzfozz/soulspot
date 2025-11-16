"""Background workers for automation features."""

import asyncio
import logging

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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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
        self, watchlist: any, new_releases: list[dict]
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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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

    async def start_all(self) -> None:
        """Start all automation workers."""
        await self.watchlist_worker.start()
        await self.discography_worker.start()
        await self.quality_worker.start()
        logger.info("All automation workers started")

    async def stop_all(self) -> None:
        """Stop all automation workers."""
        await self.watchlist_worker.stop()
        await self.discography_worker.stop()
        await self.quality_worker.stop()
        logger.info("All automation workers stopped")

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
