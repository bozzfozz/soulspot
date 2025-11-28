"""Background workers for automation features."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.automation_workflow_service import (
    AutomationWorkflowService,
)
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.entities import AutomationTrigger
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

logger = logging.getLogger(__name__)


class WatchlistWorker:
    """Background worker for checking artist watchlists for new releases."""

    # Hey future me: This worker uses DatabaseTokenManager to get Spotify access token!
    # If token is invalid (is_valid=False), worker skips work gracefully and logs warning.
    # UI shows warning banner when token invalid → user re-authenticates → worker resumes.
    # The token_manager is injected via set_token_manager() after worker construction.
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
        # Hey - token_manager is set via set_token_manager() after construction
        # This avoids circular dependencies and allows workers to be created before app.state is ready
        self._token_manager: DatabaseTokenManager | None = None

    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
        """Set the token manager for getting Spotify access tokens.

        Called during app startup after DatabaseTokenManager is initialized.

        Args:
            token_manager: Database-backed token manager
        """
        self._token_manager = token_manager

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

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, and check statistics
        """
        return {
            "name": "Watchlist Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self.check_interval_seconds,
            "has_token_manager": self._token_manager is not None,
        }

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
    #
    # TOKEN HANDLING (2025 update):
    # Uses DatabaseTokenManager.get_token_for_background() to get valid access token.
    # If token invalid (user revoked, refresh failed), skips work and logs warning.
    # UI shows red banner to user → user re-authenticates → worker resumes automatically.
    # This is GRACEFUL DEGRADATION - no crashes, just paused automation until re-auth.
    async def _check_watchlists(self) -> None:
        """Check all due watchlists for new releases."""
        try:
            # Hey - get access token from DatabaseTokenManager!
            # This is the CRITICAL integration point for background token management.
            access_token = None
            if self._token_manager:
                access_token = await self._token_manager.get_token_for_background()

            if not access_token:
                # Token invalid or missing - skip this cycle gracefully
                # UI warning banner shows "Spotify-Verbindung unterbrochen"
                logger.warning(
                    "No valid Spotify token available - skipping watchlist check. "
                    "User needs to re-authenticate via UI."
                )
                return

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

                    # Hey future me - jetzt holen wir ECHTE Releases von Spotify!
                    # get_artist_albums() gibt albums+singles zurück (include_groups in client).
                    # Wir filtern nach release_date > last_checked_at für "neue" Releases.
                    logger.info(
                        f"Fetching albums from Spotify for artist {watchlist.artist_id}"
                    )

                    # Fetch artist albums from Spotify API
                    all_albums = await self.spotify_client.get_artist_albums(
                        artist_id=str(watchlist.artist_id.value),
                        access_token=access_token,
                        limit=50,  # Get more to catch all recent releases
                    )

                    # Filter for NEW releases (released after last check)
                    new_releases: list[dict[str, Any]] = []
                    for album in all_albums:
                        release_date_str = album.get("release_date", "")
                        if not release_date_str:
                            continue

                        # Parse release date (can be YYYY, YYYY-MM, or YYYY-MM-DD)
                        try:
                            if len(release_date_str) == 4:  # YYYY
                                release_date = datetime(
                                    int(release_date_str), 1, 1, tzinfo=UTC
                                )
                            elif len(release_date_str) == 7:  # YYYY-MM
                                parts = release_date_str.split("-")
                                release_date = datetime(
                                    int(parts[0]), int(parts[1]), 1, tzinfo=UTC
                                )
                            else:  # YYYY-MM-DD
                                parts = release_date_str.split("-")
                                release_date = datetime(
                                    int(parts[0]),
                                    int(parts[1]),
                                    int(parts[2]),
                                    tzinfo=UTC,
                                )
                        except (ValueError, IndexError):
                            logger.warning(
                                f"Could not parse release date: {release_date_str}"
                            )
                            continue

                        # Check if this is a NEW release (after last check)
                        if (
                            watchlist.last_checked_at is None
                            or release_date > watchlist.last_checked_at
                        ):
                            new_releases.append(
                                {
                                    "album_id": album.get("id"),
                                    "album_name": album.get("name"),
                                    "album_type": album.get("album_type"),
                                    "release_date": release_date_str,
                                    "total_tracks": album.get("total_tracks", 0),
                                    "images": album.get("images", []),
                                }
                            )

                    logger.info(
                        f"Found {len(new_releases)} new releases for artist {watchlist.artist_id} "
                        f"(total albums checked: {len(all_albums)})"
                    )

                    # Trigger automation workflows for new releases if auto_download is enabled
                    downloads_triggered = 0
                    if new_releases and watchlist.auto_download:
                        for release in new_releases:
                            context = {
                                "artist_id": str(watchlist.artist_id.value),
                                "watchlist_id": str(watchlist.id.value),
                                "release_info": release,
                                "quality_profile": watchlist.quality_profile,
                            }
                            # Trigger the automation workflow
                            await self.workflow_service.trigger_workflow(
                                trigger=AutomationTrigger.NEW_RELEASE,
                                context=context,
                            )
                            downloads_triggered += 1

                    # Update check time and stats
                    watchlist.update_check(
                        releases_found=len(new_releases),
                        downloads_triggered=downloads_triggered,
                    )
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
    #
    # TOKEN HANDLING (2025 update):
    # Uses DatabaseTokenManager.get_token_for_background() - same pattern as WatchlistWorker.
    # Graceful degradation: skips work when token invalid, resumes after user re-authenticates.
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
        # Hey - token_manager is set via set_token_manager() after construction
        self._token_manager: DatabaseTokenManager | None = None

    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
        """Set the token manager for getting Spotify access tokens.

        Called during app startup after DatabaseTokenManager is initialized.

        Args:
            token_manager: Database-backed token manager
        """
        self._token_manager = token_manager

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

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, and check statistics
        """
        return {
            "name": "Discography Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self.check_interval_seconds,
            "has_token_manager": self._token_manager is not None,
        }

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._check_discographies()
            except Exception as e:
                logger.error(f"Error in discography worker loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Yo, discography check implementation - queries active watchlists and checks for missing albums
    # WHY check discographies? Auto-download missing albums when artists release new stuff
    # WHY active watchlists only? Don't waste API calls on paused/disabled artists
    #
    # TOKEN HANDLING (2025 update):
    # Gets token from DatabaseTokenManager at start of each cycle.
    # If no valid token, entire check is skipped (graceful degradation).
    # UI warning banner tells user to re-authenticate → worker resumes automatically.
    async def _check_discographies(self) -> None:
        """Check discography completeness for all artists.

        Implementation:
        1. Query all artists with active watchlists
        2. For each artist, fetch complete discography from Spotify
        3. Compare with local library to identify missing albums
        4. Trigger automation workflows for missing albums if auto_download enabled
        """
        try:
            logger.info("Checking artist discographies")

            # Hey - get access token from DatabaseTokenManager FIRST!
            # If no token, skip entire cycle (graceful degradation)
            access_token = None
            if self._token_manager:
                access_token = await self._token_manager.get_token_for_background()

            if not access_token:
                # Token invalid or missing - skip this cycle gracefully
                # UI warning banner shows "Spotify-Verbindung unterbrochen"
                logger.warning(
                    "No valid Spotify token available - skipping discography check. "
                    "User needs to re-authenticate via UI."
                )
                return

            # Hey - import repository here to avoid circular deps
            from soulspot.infrastructure.persistence.repositories import (
                ArtistWatchlistRepository,
            )

            # Get watchlist repository instance
            watchlist_repo = ArtistWatchlistRepository(self.session)

            # Get all active watchlists
            active_watchlists = await watchlist_repo.list_active(limit=100)

            if not active_watchlists:
                logger.debug("No active watchlists to check")
                return

            logger.info(f"Checking discographies for {len(active_watchlists)} artists")

            # Check each artist's discography
            for watchlist in active_watchlists:
                try:
                    # Skip if auto_download is disabled
                    if not watchlist.auto_download:
                        logger.debug(
                            f"Skipping artist {watchlist.artist_id} - auto_download disabled"
                        )
                        continue

                    # Hey - we have access_token from token_manager above!
                    # Token is refreshed automatically by TokenRefreshWorker.

                    # Check discography using service
                    discography_info = await self.discography_service.check_discography(
                        artist_id=watchlist.artist_id, access_token=access_token
                    )

                    # If missing albums found and auto_download enabled, trigger automation
                    if discography_info.missing_albums and watchlist.auto_download:
                        logger.info(
                            f"Found {len(discography_info.missing_albums)} missing albums "
                            f"for artist {watchlist.artist_id}"
                        )

                        # Hey - trigger automation workflow for missing albums
                        # The workflow service handles creating downloads, applying filters, etc
                        await self.workflow_service.trigger_workflow(
                            trigger=AutomationTrigger.MISSING_ALBUM,
                            context={
                                "artist_id": str(watchlist.artist_id.value),
                                "missing_albums": discography_info.missing_albums,
                                "quality_profile": watchlist.quality_profile,
                            },
                        )

                except Exception as e:
                    logger.error(
                        f"Error checking discography for artist {watchlist.artist_id}: {e}"
                    )
                    continue  # Continue with next artist on error

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

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, and check statistics
        """
        return {
            "name": "Quality Upgrade Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self.check_interval_seconds,
        }

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._identify_upgrades()
            except Exception as e:
                logger.error(f"Error in quality upgrade worker loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Hey future me: Quality upgrade identification - finds tracks that could be upgraded to better quality
    # WHY do this? User has 192kbps MP3, but FLAC or 320kbps available - automatic upgrade improves library
    # WHY complicated? Need to avoid false upgrades (downsampled FLAC worse than good MP3, different masters, etc)
    # GOTCHA: This scans entire library - expensive operation! Run infrequently (daily not hourly)
    async def _identify_upgrades(self) -> None:
        """Identify quality upgrade opportunities.

        Implementation:
        1. Scan library for tracks with lower quality files
        2. Search for higher quality alternatives
        3. Calculate improvement score based on bitrate/format
        4. Create upgrade candidates for tracks meeting threshold
        5. Trigger automation workflows for approved upgrades
        """
        try:
            logger.info("Identifying quality upgrade opportunities")

            # Hey - import repository to get tracks
            from soulspot.infrastructure.persistence.repositories import TrackRepository

            track_repo = TrackRepository(self.session)

            # Get all tracks from library (paginated to avoid memory issues)
            # In production, might want to add filters like "bitrate < 320" or "format = mp3"
            all_tracks = await track_repo.list_all()

            if not all_tracks:
                logger.debug("No tracks in library to check for upgrades")
                return

            logger.info(
                f"Scanning {len(all_tracks)} tracks for quality upgrade opportunities"
            )

            upgrade_candidates_found = 0

            # Check each track for upgrade opportunities
            for track in all_tracks:
                try:
                    # Skip tracks without audio files (not downloaded yet)
                    if not track.file_path or not track.is_downloaded():
                        continue

                    # Use quality service to identify upgrade opportunities
                    # This checks bitrate, format, and calculates improvement score
                    # Hey - method will be implemented in QualityUpgradeService later
                    # For now, skip if method doesn't exist yet (graceful degradation)
                    if not hasattr(
                        self.quality_service, "identify_upgrade_opportunities"
                    ):
                        logger.debug(
                            "Quality upgrade identification not yet implemented - skipping"
                        )
                        continue

                    candidates = (
                        await self.quality_service.identify_upgrade_opportunities(
                            track_id=track.id
                        )
                    )

                    # Process each candidate
                    for candidate in candidates:
                        # Hey - only trigger automation if improvement score meets threshold
                        # Score > 20 means significant upgrade (MP3 -> FLAC, 128kbps -> 320kbps)
                        # Score < 20 means marginal (256kbps -> 320kbps) - maybe not worth bandwidth
                        improvement_threshold = 20.0

                        if candidate.improvement_score >= improvement_threshold:
                            logger.info(
                                f"Found upgrade opportunity for track {track.id}: "
                                f"{candidate.current_format}@{candidate.current_bitrate}kbps -> "
                                f"{candidate.target_format}@{candidate.target_bitrate}kbps "
                                f"(score: {candidate.improvement_score})"
                            )

                            # Trigger automation workflow for quality upgrade
                            # Hey - quality upgrade automation will be completed with real search logic
                            await self.workflow_service.trigger_workflow(
                                trigger=AutomationTrigger.QUALITY_UPGRADE,
                                context={
                                    "track_id": str(track.id.value),
                                    "current_quality": f"{candidate.current_format}@{candidate.current_bitrate}kbps",
                                    "target_quality": f"{candidate.target_format}@{candidate.target_bitrate}kbps",
                                    "improvement_score": candidate.improvement_score,
                                },
                            )
                            upgrade_candidates_found += 1

                except Exception as e:
                    logger.error(f"Error checking upgrade for track {track.id}: {e}")
                    continue  # Continue with next track on error

            logger.info(
                f"Quality upgrade scan complete - found {upgrade_candidates_found} candidates"
            )

        except Exception as e:
            logger.error(f"Error in quality upgrade identification: {e}", exc_info=True)


class AutomationWorkerManager:
    """Manager for all automation background workers."""

    # Yo, the manager class - starts/stops all three workers as a unit
    # WHY manager? So you can start/stop all automation with one call instead of managing three workers
    # GOTCHA: All workers share same DB session - concurrent access could cause conflicts if not careful
    # The interval params let you tune each worker independently (watchlist hourly, others daily)
    #
    # TOKEN HANDLING (2025 update):
    # Manager now accepts token_manager param and injects it into workers that need Spotify access.
    # WatchlistWorker and DiscographyWorker get token_manager for background token access.
    # QualityUpgradeWorker doesn't need it (scans local library, no Spotify API calls).
    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
        watchlist_interval: int = 3600,
        discography_interval: int = 86400,
        quality_interval: int = 86400,
        token_manager: "DatabaseTokenManager | None" = None,
    ) -> None:
        """Initialize automation worker manager.

        Args:
            session: Database session
            spotify_client: Spotify client
            watchlist_interval: Watchlist check interval in seconds
            discography_interval: Discography check interval in seconds
            quality_interval: Quality upgrade check interval in seconds
            token_manager: Database-backed token manager for Spotify access
        """
        self.watchlist_worker = WatchlistWorker(
            session, spotify_client, watchlist_interval
        )
        self.discography_worker = DiscographyWorker(
            session, spotify_client, discography_interval
        )
        self.quality_worker = QualityUpgradeWorker(session, quality_interval)

        # Hey - inject token_manager into workers that need Spotify access!
        # This is the critical connection between token storage and background work.
        if token_manager:
            self.watchlist_worker.set_token_manager(token_manager)
            self.discography_worker.set_token_manager(token_manager)

    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
        """Set token manager for all workers that need Spotify access.

        Call this if token_manager wasn't available at construction time.

        Args:
            token_manager: Database-backed token manager
        """
        self.watchlist_worker.set_token_manager(token_manager)
        self.discography_worker.set_token_manager(token_manager)

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
        """Get simple running status of all workers.

        Returns:
            Dictionary mapping worker name to running status
        """
        return {
            "watchlist": self.watchlist_worker._running,
            "discography": self.discography_worker._running,
            "quality_upgrade": self.quality_worker._running,
        }

    def get_detailed_status(self) -> dict[str, dict[str, Any]]:
        """Get detailed status of all workers including config and stats.

        Hey future me - diese Methode gibt MEHR Details als get_status().
        Nützlich für die Worker-Status API und Debugging.

        Returns:
            Dictionary with detailed status for each worker
        """
        return {
            "watchlist": self.watchlist_worker.get_status(),
            "discography": self.discography_worker.get_status(),
            "quality_upgrade": self.quality_worker.get_status(),
        }
