"""Background workers for automation features."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.automation_workflow_service import (
    AutomationWorkflowService,
)
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.entities import AutomationTrigger
from soulspot.infrastructure.plugins import SpotifyPlugin

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

logger = logging.getLogger(__name__)


class WatchlistWorker:
    """Background worker for checking artist watchlists for new releases."""

    # Hey future me: This worker uses DatabaseTokenManager to get Spotify access token!
    # If token is invalid (is_valid=False), worker skips work gracefully and logs warning.
    # UI shows warning banner when token invalid → user re-authenticates → worker resumes.
    # The token_manager is injected via set_token_manager() after worker construction.
    # REFACTORED (Dec 2025): Now uses SpotifyPlugin instead of SpotifyClient!
    # FIX (Dec 2025): Changed to session_factory to prevent concurrent session errors
    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession]
        spotify_plugin: SpotifyPlugin,
        check_interval_seconds: int = 3600,  # Default: 1 hour
    ) -> None:
        """Initialize watchlist worker.

        Args:
            session_factory: Factory for creating database sessions
            spotify_plugin: SpotifyPlugin for fetching releases (handles token via set_token)
            check_interval_seconds: How often to check watchlists
        """
        self.session_factory = session_factory
        self.spotify_plugin = spotify_plugin
        self.check_interval_seconds = check_interval_seconds
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
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="Watchlist",
                interval=self.check_interval_seconds
            )
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
                logger.error(f"Error in watchlist worker loop: {e}", exc_info=True)

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    # Hey future me: Watchlist worker - background daemon that checks for new releases
    #
    # OPTIMIZATION (Nov 2025): Now uses pre-synced spotify_albums instead of API calls!
    # The Artist Albums Background Sync keeps spotify_albums fresh. We just query locally.
    # This reduces API calls from N (one per artist per check) to 0 for most checks.
    #
    # Flow:
    # 1. Get due watchlists
    # 2. For each watchlist, get local artist's spotify_uri
    # 3. Check if albums are synced (albums_synced_at not null)
    # 4. If synced: query spotify_albums for new albums since last_checked_at
    # 5. If not synced: trigger album sync for this artist (or skip)
    # 6. Process new releases as before
    #
    # TOKEN HANDLING: SpotifyPlugin.set_token() is called with token from token_manager!
    # FIX (Dec 2025): Creates new session scope to prevent concurrent session errors
    async def _check_watchlists(self) -> None:
        """Check all due watchlists for new releases using pre-synced album data."""
        # Create new session for this operation
        async with self.session_factory() as session:
            try:
                # Import repositories here to avoid circular deps
                from soulspot.infrastructure.persistence.repositories import (
                    ArtistRepository,
                    SpotifyBrowseRepository,
                )

                # Get access token and set on SpotifyPlugin
                access_token = None
                if self._token_manager:
                    access_token = await self._token_manager.get_token_for_background()

                if not access_token:
                    logger.warning(
                        "No valid Spotify token available - skipping watchlist check. "
                        "User needs to re-authenticate via UI."
                    )
                    return

                # Set token on SpotifyPlugin before any API calls!
                self.spotify_plugin.set_token(access_token)

                # Create services with this session
                watchlist_service = WatchlistService(session, self.spotify_plugin)
                workflow_service = AutomationWorkflowService(session)

                # Get watchlists that need checking
                watchlists = await watchlist_service.list_due_for_check(limit=100)

                if not watchlists:
                    logger.debug("No watchlists due for checking")
                    return

                logger.info(f"Checking {len(watchlists)} watchlists for new releases")

                # Set up repositories with this session
                artist_repo = ArtistRepository(session)
                spotify_repo = SpotifyBrowseRepository(session)

                for watchlist in watchlists:
                    try:
                        logger.debug(f"Checking watchlist for artist {watchlist.artist_id}")

                        # Step 1: Get local artist to find spotify_uri
                        local_artist = await artist_repo.get_by_id(watchlist.artist_id)
                        if not local_artist:
                            logger.warning(
                                f"Local artist {watchlist.artist_id} not found, skipping"
                            )
                            continue

                        if not local_artist.spotify_uri:
                            logger.warning(
                                f"Artist {local_artist.name} has no Spotify URI, skipping"
                            )
                            continue

                        # Extract Spotify ID from URI (spotify:artist:XXXXX)
                        spotify_artist_id = str(local_artist.spotify_uri).split(":")[-1]

                        # Step 2: Check if albums are synced for this artist
                        sync_status = await spotify_repo.get_artist_albums_sync_status(
                            spotify_artist_id
                        )

                        if not sync_status["albums_synced"]:
                            # Albums not synced yet - trigger sync and skip this check
                            # The Background Sync will catch up, we'll find new releases next cycle
                            logger.info(
                                f"Albums not yet synced for {local_artist.name}, "
                                "will be handled by background sync"
                            )
                            # Just update last_checked_at so we don't spam logs
                            watchlist.update_check(releases_found=0, downloads_triggered=0)
                            await watchlist_service.repository.update(watchlist)
                            await session.commit()
                            continue

                        # Step 3: Get new albums since last check from LOCAL data
                        # Hey future me - this is the KEY optimization! No API call here!
                        new_album_models = await spotify_repo.get_new_albums_since(
                            artist_id=spotify_artist_id,
                            since_date=watchlist.last_checked_at,
                        )

                        # Convert to the expected format
                        new_releases: list[dict[str, Any]] = []
                        for album in new_album_models:
                            new_releases.append(
                                {
                                    "album_id": album.spotify_uri,
                                    "album_name": album.title,
                                    "album_type": album.primary_type,
                                    "release_date": album.release_date,
                                    "total_tracks": album.total_tracks,
                                    "images": [{"url": album.cover_url}]
                                    if album.cover_url
                                    else [],
                                }
                            )

                        logger.info(
                            f"Found {len(new_releases)} new releases for {local_artist.name} "
                            f"(total albums in DB: {sync_status['album_count']})"
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
                                await workflow_service.trigger_workflow(
                                    trigger=AutomationTrigger.NEW_RELEASE,
                                    context=context,
                                )
                                downloads_triggered += 1

                        # Update check time and stats
                        watchlist.update_check(
                            releases_found=len(new_releases),
                            downloads_triggered=downloads_triggered,
                        )
                        await watchlist_service.repository.update(watchlist)
                        await session.commit()

                    except Exception as e:
                        logger.error(
                            f"Error checking watchlist {watchlist.id}: {e}",
                            exc_info=True,
                        )
                        await session.rollback()

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
    # REFACTORED (Dec 2025): DiscographyService now uses LOCAL spotify_albums data!
    # No SpotifyClient needed anymore - we query pre-synced data from DB.
    #
    # TOKEN HANDLING (2025 update):
    # Uses DatabaseTokenManager.get_token_for_background() - same pattern as WatchlistWorker.
    # Graceful degradation: skips work when token invalid, resumes after user re-authenticates.
    # FIX (Dec 2025): Changed to session_factory to prevent concurrent session errors
    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession]
        check_interval_seconds: int = 86400,  # Default: 24 hours
    ) -> None:
        """Initialize discography worker.

        Args:
            session_factory: Factory for creating database sessions
            check_interval_seconds: How often to check discography
        """
        self.session_factory = session_factory
        self.check_interval_seconds = check_interval_seconds
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
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="Discography",
                interval=self.check_interval_seconds
            )
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
                logger.error(f"Error in discography worker loop: {e}", exc_info=True)

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
        # Create new session for this operation
        async with self.session_factory() as session:
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

                # Create services with this session
                discography_service = DiscographyService(session)
                workflow_service = AutomationWorkflowService(session)

                # Get watchlist repository instance
                watchlist_repo = ArtistWatchlistRepository(session)

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
                        discography_info = await discography_service.check_discography(
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
                            await workflow_service.trigger_workflow(
                                trigger=AutomationTrigger.MISSING_ALBUM,
                                context={
                                    "artist_id": str(watchlist.artist_id.value),
                                    "missing_albums": discography_info.missing_albums,
                                    "quality_profile": watchlist.quality_profile,
                                },
                            )

                    except Exception as e:
                        logger.error(
                            f"Error checking discography for artist {watchlist.artist_id}: {e}",
                            exc_info=True,
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
    # FIX (Dec 2025): Changed to session_factory to prevent concurrent session errors
    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession]
        check_interval_seconds: int = 86400,  # Default: 24 hours
    ) -> None:
        """Initialize quality upgrade worker.

        Args:
            session_factory: Factory for creating database sessions
            check_interval_seconds: How often to check for upgrades
        """
        self.session_factory = session_factory
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the quality upgrade worker."""
        if self._running:
            logger.warning("Quality upgrade worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="Quality Upgrade",
                interval=self.check_interval_seconds
            )
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
                logger.error(f"Error in quality upgrade worker loop: {e}", exc_info=True)

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
        # Create new session for this operation
        async with self.session_factory() as session:
            try:
                logger.info("Identifying quality upgrade opportunities")

                # Hey - import repository to get tracks
                from soulspot.infrastructure.persistence.repositories import TrackRepository

                # Create services with this session
                quality_service = QualityUpgradeService(session)
                workflow_service = AutomationWorkflowService(session)

                track_repo = TrackRepository(session)

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
                            quality_service, "identify_upgrade_opportunities"
                        ):
                            logger.debug(
                                "Quality upgrade identification not yet implemented - skipping"
                            )
                            continue

                        candidates = (
                            await quality_service.identify_upgrade_opportunities(
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
                                await workflow_service.trigger_workflow(
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
                        logger.error(f"Error checking upgrade for track {track.id}: {e}", exc_info=True)
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
    # WatchlistWorker gets token_manager for background token access (and SpotifyPlugin).
    # DiscographyWorker gets token_manager but now uses LOCAL data only (no SpotifyClient needed!).
    # QualityUpgradeWorker doesn't need it (scans local library, no Spotify API calls).
    #
    # REFACTORED (Dec 2025): Uses SpotifyPlugin instead of SpotifyClient!
    # FIX (Dec 2025): Changed to session_factory to prevent concurrent session errors
    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession]
        spotify_plugin: SpotifyPlugin,
        watchlist_interval: int = 3600,
        discography_interval: int = 86400,
        quality_interval: int = 86400,
        token_manager: "DatabaseTokenManager | None" = None,
    ) -> None:
        """Initialize automation worker manager.

        Args:
            session_factory: Factory for creating database sessions
            spotify_plugin: SpotifyPlugin for API calls (token set via set_token before operations)
            watchlist_interval: Watchlist check interval in seconds
            discography_interval: Discography check interval in seconds
            quality_interval: Quality upgrade check interval in seconds
            token_manager: Database-backed token manager for Spotify access
        """
        self.watchlist_worker = WatchlistWorker(
            session_factory, spotify_plugin, watchlist_interval
        )
        # DiscographyWorker no longer needs SpotifyClient - uses LOCAL data!
        self.discography_worker = DiscographyWorker(
            session_factory, discography_interval
        )
        self.quality_worker = QualityUpgradeWorker(session_factory, quality_interval)

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
