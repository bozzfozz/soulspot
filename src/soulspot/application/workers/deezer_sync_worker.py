# Hey future me - dieser Worker führt den Deezer Auto-Sync automatisch aus!
#
# Das Pattern ist identisch zu SpotifySyncWorker:
# 1. Endlosschleife mit konfigurierbarem Intervall
# 2. Settings aus DB lesen (AppSettingsService)
# 3. In-memory Tracking wann letzter Sync war
# 4. Sync ausführen wenn: enabled UND cooldown abgelaufen
#
# WICHTIGER UNTERSCHIED zu Spotify:
# - Deezer hat KEINE token_refresh Logik - Tokens sind langlebig (ca. 90 Tage)
# - Deezer public API braucht keinen Token (Charts, New Releases)
# - Nur User-Daten (Favorites, Playlists) brauchen Token
#
# Worker synct:
# - Charts (public - no auth needed)
# - New Releases (public - no auth needed)
# - Followed Artists (USER - auth needed)
# - User Playlists (USER - auth needed)
# - Saved Albums (USER - auth needed)
# - Saved Tracks (USER - auth needed)
"""Background worker for automatic Deezer data synchronization."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.application.cache.deezer_charts_cache import DeezerChartsCache
    from soulspot.config import Settings
    from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


class DeezerSyncWorker:
    """Background worker that automatically syncs data from Deezer.

    Runs every `check_interval_seconds` and executes enabled syncs when their
    cooldown has expired.

    PUBLIC Syncs (no auth required):
    - Charts (tracks, albums, artists)
    - New Releases

    USER Syncs (auth required):
    - Followed Artists
    - User Playlists
    - Saved Albums
    - Saved Tracks

    Settings are read from database (app_settings table) and can be changed
    at runtime without restarting the worker.

    Hey future me - unlike Spotify, Deezer tokens are LONG-LIVED (~90 days).
    No automatic refresh needed. If token expires, user must re-auth.
    """

    def __init__(
        self,
        db: "Database",
        settings: "Settings",
        check_interval_seconds: int = 60,  # Check every minute
    ) -> None:
        """Initialize Deezer sync worker.

        Args:
            db: Database instance for creating sessions
            settings: Application settings
            check_interval_seconds: How often to check if syncs are due

        Note: No token_manager parameter unlike Spotify - Deezer tokens are
        managed via deezer_sessions table and checked per request.
        """
        self.db = db
        self.settings = settings
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Hey future me - Charts werden IN-MEMORY gecacht, NICHT in die DB geschrieben!
        # Das verhindert Vermischung von Browse-Content mit User's Library.
        from soulspot.application.cache.deezer_charts_cache import DeezerChartsCache
        self._charts_cache = DeezerChartsCache()

        # Hey future me - diese Timestamps tracken wann der letzte erfolgreiche Sync war.
        # Sie sind in-memory, d.h. beim Neustart werden alle Syncs sofort ausgeführt.
        self._last_sync: dict[str, datetime | None] = {
            # Public syncs (no auth)
            "charts": None,
            "new_releases": None,
            # User syncs (auth required)
            "artists": None,
            "playlists": None,
            "saved_albums": None,
            "saved_tracks": None,
        }

        # Track sync stats for monitoring
        self._sync_stats: dict[str, dict[str, Any]] = {
            "charts": {"count": 0, "last_result": None, "last_error": None},
            "new_releases": {"count": 0, "last_result": None, "last_error": None},
            "artists": {"count": 0, "last_result": None, "last_error": None},
            "playlists": {"count": 0, "last_result": None, "last_error": None},
            "saved_albums": {"count": 0, "last_result": None, "last_error": None},
            "saved_tracks": {"count": 0, "last_result": None, "last_error": None},
        }

    async def start(self) -> None:
        """Start the Deezer sync worker.

        Creates a background task that runs the sync loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("Deezer sync worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        from soulspot.infrastructure.observability.log_messages import LogMessages

        logger.info(
            LogMessages.worker_started(
                worker="Deezer Sync", interval=self.check_interval_seconds
            )
        )

    async def stop(self) -> None:
        """Stop the Deezer sync worker.

        Cancels the background task and waits for cleanup.
        Safe to call multiple times (idempotent).
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Deezer sync worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop - checks and runs syncs periodically.

        Hey future me - diese Loop läuft EWIG bis stop() aufgerufen wird!
        """
        # Wait a bit on startup to let other services initialize
        await asyncio.sleep(35)  # Slightly offset from Spotify worker

        logger.info("Deezer sync worker entering main loop")

        while self._running:
            try:
                await self._check_and_run_syncs()
            except Exception as e:
                # Don't crash the loop on errors - log and continue
                logger.error(f"Error in Deezer sync worker loop: {e}", exc_info=True)

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                # Worker is being stopped
                break

    async def _check_and_run_syncs(self) -> None:
        """Check settings and run any due syncs.

        Hey future me - PUBLIC syncs (charts, new_releases) run even without auth.
        USER syncs only run if we have a valid Deezer token.
        """
        async with self.db.session_scope() as session:
            try:
                from soulspot.application.services.app_settings_service import (
                    AppSettingsService,
                )

                settings_service = AppSettingsService(session)

                # Check master toggle first
                auto_sync_enabled = await settings_service.get_bool(
                    "deezer.auto_sync_enabled", default=True
                )

                if not auto_sync_enabled:
                    logger.debug("Deezer auto-sync is disabled, skipping")
                    return

                # Check if provider is enabled
                provider_mode = await settings_service.get_string(
                    "deezer.provider_mode", default="basic"
                )
                if provider_mode == "off":
                    logger.debug("Deezer provider is disabled, skipping sync")
                    return

                # Get interval settings
                # Hey future me - charts/releases can update less frequently than user data
                charts_interval = await settings_service.get_int(
                    "deezer.charts_sync_interval_minutes", default=60
                )
                releases_interval = await settings_service.get_int(
                    "deezer.new_releases_sync_interval_minutes", default=60
                )
                user_sync_interval = await settings_service.get_int(
                    "deezer.user_sync_interval_minutes", default=10
                )

                now = datetime.now(UTC)

                # =========================================================
                # PUBLIC SYNCS - No auth required!
                # =========================================================

                # Charts sync (public API)
                if await settings_service.get_bool(
                    "deezer.auto_sync_charts", default=True
                ) and self._is_sync_due("charts", charts_interval, now):
                    await self._run_charts_sync(session, now)

                # New Releases sync (public API)
                if await settings_service.get_bool(
                    "deezer.auto_sync_new_releases", default=True
                ) and self._is_sync_due("new_releases", releases_interval, now):
                    await self._run_new_releases_sync(session, now)

                # =========================================================
                # USER SYNCS - Auth required!
                # =========================================================

                # Check if we have a valid Deezer token
                access_token = await self._get_deezer_token(session)
                if not access_token:
                    logger.debug(
                        "No valid Deezer token for user syncs, skipping user data"
                    )
                else:
                    # Followed Artists sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_artists", default=True
                    ) and self._is_sync_due("artists", user_sync_interval, now):
                        await self._run_artists_sync(session, access_token, now)

                    # User Playlists sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_playlists", default=True
                    ) and self._is_sync_due("playlists", user_sync_interval, now):
                        await self._run_playlists_sync(session, access_token, now)

                    # Saved Albums sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_saved_albums", default=True
                    ) and self._is_sync_due("saved_albums", user_sync_interval, now):
                        await self._run_saved_albums_sync(session, access_token, now)

                    # Saved Tracks sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_saved_tracks", default=True
                    ) and self._is_sync_due("saved_tracks", user_sync_interval, now):
                        await self._run_saved_tracks_sync(session, access_token, now)

                # Commit any changes
                await session.commit()

            except Exception as e:
                logger.error(f"Error in Deezer sync cycle: {e}", exc_info=True)
                await session.rollback()

    async def _get_deezer_token(self, session: Any) -> str | None:
        """Get a valid Deezer access token.

        Hey future me - Deezer tokens are stored in deezer_sessions table.
        Unlike Spotify, there's no refresh mechanism - tokens are long-lived.
        If expired, user must re-authenticate.

        Returns:
            Access token if available, None otherwise
        """
        try:
            from soulspot.infrastructure.persistence.repositories import (
                DeezerSessionRepository,
            )

            repo = DeezerSessionRepository(session)

            # Get any valid session (for background worker, we use any available)
            # Hey future me - for multi-user, you'd need to iterate all sessions!
            # This implementation uses a single-user assumption.
            sessions = await repo.get_all_active()
            if sessions:
                # Return the first valid token
                return sessions[0].access_token
            return None

        except Exception as e:
            logger.warning(f"Failed to get Deezer token: {e}")
            return None

    def _is_sync_due(
        self, sync_type: str, interval_minutes: int, now: datetime
    ) -> bool:
        """Check if a sync is due based on its cooldown interval."""
        last_sync = self._last_sync.get(sync_type)

        if last_sync is None:
            return True

        cooldown = timedelta(minutes=interval_minutes)
        return (now - last_sync) >= cooldown

    # =========================================================================
    # PUBLIC SYNC METHODS
    # =========================================================================

    async def _run_charts_sync(self, session: Any, now: datetime) -> None:
        """Run charts sync to IN-MEMORY CACHE (public API - no auth needed).
        
        Hey future me - WICHTIG: Charts werden NICHT in die DB geschrieben!
        Sie werden nur im _charts_cache gehalten. Das verhindert Vermischung
        von Browse-Content mit User's Library.
        
        Wir nutzen ChartsService (nicht DeezerSyncService) direkt und
        speichern das Ergebnis im Cache.
        """
        logger.info("Starting automatic Deezer charts sync (in-memory cache)...")

        try:
            from soulspot.application.services.charts_service import ChartsService
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            # Hey future me - charts don't need auth token!
            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=None,  # No auth for public API
            )

            # Use ChartsService directly - it returns ChartsResult, not DB writes!
            charts_service = ChartsService(
                spotify_plugin=None,  # No Spotify for public charts
                deezer_plugin=deezer_plugin,
            )

            # Fetch all chart types and store in cache
            tracks_result = await charts_service.get_chart_tracks(
                limit=50, enabled_providers=["deezer"]
            )
            albums_result = await charts_service.get_chart_albums(
                limit=50, enabled_providers=["deezer"]
            )
            artists_result = await charts_service.get_chart_artists(
                limit=50, enabled_providers=["deezer"]
            )
            
            # Update the in-memory cache (NO DB writes!)
            self._charts_cache.update_all(
                tracks=tracks_result,
                albums=albums_result,
                artists=artists_result,
            )

            result = {
                "cached": True,
                "tracks": len(tracks_result.tracks),
                "albums": len(albums_result.albums),
                "artists": len(artists_result.artists),
            }

            # Update tracking
            self._last_sync["charts"] = now
            self._sync_stats["charts"]["count"] += 1
            self._sync_stats["charts"]["last_result"] = result
            self._sync_stats["charts"]["last_error"] = None

            logger.info(
                f"Deezer charts cached: {result['tracks']} tracks, "
                f"{result['albums']} albums, {result['artists']} artists"
            )

        except Exception as e:
            self._sync_stats["charts"]["last_error"] = str(e)
            logger.error(f"Deezer charts sync failed: {e}", exc_info=True)

    async def _run_new_releases_sync(self, session: Any, now: datetime) -> None:
        """Run new releases sync (public API - no auth needed)."""
        logger.info("Starting automatic Deezer new releases sync...")

        try:
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=None,
            )

            sync_service = DeezerSyncService(
                session=session,
                deezer_plugin=deezer_plugin,
            )

            result = await sync_service.sync_new_releases()

            # Update tracking
            self._last_sync["new_releases"] = now
            self._sync_stats["new_releases"]["count"] += 1
            self._sync_stats["new_releases"]["last_result"] = result
            self._sync_stats["new_releases"]["last_error"] = None

            logger.info(f"Deezer new releases sync completed: {result}")

        except Exception as e:
            self._sync_stats["new_releases"]["last_error"] = str(e)
            logger.error(f"Deezer new releases sync failed: {e}", exc_info=True)

    # =========================================================================
    # USER SYNC METHODS (Auth required)
    # =========================================================================

    async def _run_artists_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run followed artists sync."""
        logger.info("Starting automatic Deezer artists sync...")

        try:
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=access_token,
            )

            sync_service = DeezerSyncService(
                session=session,
                deezer_plugin=deezer_plugin,
            )

            result = await sync_service.sync_followed_artists(force=False)

            self._last_sync["artists"] = now
            self._sync_stats["artists"]["count"] += 1
            self._sync_stats["artists"]["last_result"] = result
            self._sync_stats["artists"]["last_error"] = None

            logger.info(f"Deezer artists sync completed: {result}")

        except Exception as e:
            self._sync_stats["artists"]["last_error"] = str(e)
            logger.error(f"Deezer artists sync failed: {e}", exc_info=True)

    async def _run_playlists_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run user playlists sync."""
        logger.info("Starting automatic Deezer playlists sync...")

        try:
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=access_token,
            )

            sync_service = DeezerSyncService(
                session=session,
                deezer_plugin=deezer_plugin,
            )

            result = await sync_service.sync_user_playlists(force=False)

            self._last_sync["playlists"] = now
            self._sync_stats["playlists"]["count"] += 1
            self._sync_stats["playlists"]["last_result"] = result
            self._sync_stats["playlists"]["last_error"] = None

            logger.info(f"Deezer playlists sync completed: {result}")

        except Exception as e:
            self._sync_stats["playlists"]["last_error"] = str(e)
            logger.error(f"Deezer playlists sync failed: {e}", exc_info=True)

    async def _run_saved_albums_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run saved albums sync."""
        logger.info("Starting automatic Deezer saved albums sync...")

        try:
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=access_token,
            )

            sync_service = DeezerSyncService(
                session=session,
                deezer_plugin=deezer_plugin,
            )

            result = await sync_service.sync_saved_albums(force=False)

            self._last_sync["saved_albums"] = now
            self._sync_stats["saved_albums"]["count"] += 1
            self._sync_stats["saved_albums"]["last_result"] = result
            self._sync_stats["saved_albums"]["last_error"] = None

            logger.info(f"Deezer saved albums sync completed: {result}")

        except Exception as e:
            self._sync_stats["saved_albums"]["last_error"] = str(e)
            logger.error(f"Deezer saved albums sync failed: {e}", exc_info=True)

    async def _run_saved_tracks_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run saved tracks sync."""
        logger.info("Starting automatic Deezer saved tracks sync...")

        try:
            from soulspot.application.services.deezer_sync_service import (
                DeezerSyncService,
            )
            from soulspot.infrastructure.integrations.deezer_client import (
                DeezerClient,
            )
            from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

            deezer_client = DeezerClient()
            deezer_plugin = DeezerPlugin(
                client=deezer_client,
                access_token=access_token,
            )

            sync_service = DeezerSyncService(
                session=session,
                deezer_plugin=deezer_plugin,
            )

            result = await sync_service.sync_saved_tracks(force=False)

            self._last_sync["saved_tracks"] = now
            self._sync_stats["saved_tracks"]["count"] += 1
            self._sync_stats["saved_tracks"]["last_result"] = result
            self._sync_stats["saved_tracks"]["last_error"] = None

            logger.info(f"Deezer saved tracks sync completed: {result}")

        except Exception as e:
            self._sync_stats["saved_tracks"]["last_error"] = str(e)
            logger.error(f"Deezer saved tracks sync failed: {e}", exc_info=True)

    # =========================================================================
    # STATUS & MONITORING
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get worker status and sync statistics.

        Returns:
            Dict with running state, last syncs, and stats per sync type
        """
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "last_syncs": {
                k: v.isoformat() if v else None for k, v in self._last_sync.items()
            },
            "sync_stats": self._sync_stats,
            "charts_cache_stats": self._charts_cache.get_stats(),
        }

    def get_cached_charts(self) -> "DeezerChartsCache":
        """Get the in-memory charts cache.
        
        Hey future me - das ist der Zugriffspunkt für die API!
        Die Charts-Route ruft diese Methode auf um gecachte Charts zu bekommen.
        
        Returns:
            DeezerChartsCache instance with cached chart data
        """
        from soulspot.application.cache.deezer_charts_cache import DeezerChartsCache
        return self._charts_cache

    async def force_charts_sync(self) -> dict[str, Any]:
        """Force immediate charts sync (for manual refresh button).
        
        Returns:
            Sync result with counts
        """
        logger.info("Force charts sync requested...")
        async with self.db.session_scope() as session:
            await self._run_charts_sync(session, datetime.now(UTC))
        return self._charts_cache.get_stats()

    def reset_sync_time(self, sync_type: str) -> bool:
        """Reset last sync time to force immediate resync.

        Args:
            sync_type: Type of sync to reset

        Returns:
            True if reset, False if invalid type
        """
        if sync_type in self._last_sync:
            self._last_sync[sync_type] = None
            logger.info(f"Reset Deezer sync timer for: {sync_type}")
            return True
        return False
