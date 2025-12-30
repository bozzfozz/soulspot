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
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from soulspot.infrastructure.observability.logger_template import log_worker_health

if TYPE_CHECKING:
    # NOTE: DeezerChartsCache and DeezerNewReleasesCache removed
    # - Charts: showed generic browse content, feature removed
    # - New Releases: now handled by NewReleasesSyncWorker
    from soulspot.application.services.deezer_sync_service import DeezerSyncService
    from soulspot.application.services.images import ImageDownloadQueue, ImageService
    from soulspot.config import Settings
    from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


def _get_image_service() -> "ImageService":
    """Get ImageService with correct Docker cache path.

    Hey future me - THIS IS CRITICAL!
    ImageService() ohne Parameter nutzt default ./images (FALSCH in Docker!).
    Wir müssen den korrekten Pfad aus Settings holen.
    """
    from soulspot.application.services.images import ImageService
    from soulspot.config import get_settings

    settings = get_settings()
    return ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/api/images",
    )


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
        image_queue: "ImageDownloadQueue | None" = None,
    ) -> None:
        """Initialize Deezer sync worker.

        Args:
            db: Database instance for creating sessions
            settings: Application settings
            check_interval_seconds: How often to check if syncs are due
            image_queue: Queue for async image downloads (optional)

        Note: No token_manager parameter unlike Spotify - Deezer tokens are
        managed via deezer_sessions table and checked per request.

        REFACTORED (Jan 2025): Bekommt image_queue für async Bilder-Downloads!
        Images werden in Queue gestellt statt blockierend heruntergeladen.
        """
        self.db = db
        self.settings = settings
        self.check_interval_seconds = check_interval_seconds
        self._image_queue = image_queue
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Lifecycle tracking for health monitoring
        self._cycles_completed = 0
        self._errors_total = 0
        self._start_time = time.time()

        # NOTE: Charts and New Releases caches REMOVED!
        # - Charts were generic "trending" content, not user's personal music
        # - New Releases now handled by NewReleasesSyncWorker (shows only followed artists)
        # This worker now only syncs USER data: followed artists, playlists, saved items

        # Hey future me - diese Timestamps tracken wann der letzte erfolgreiche Sync war.
        # Sie sind in-memory, d.h. beim Neustart werden alle Syncs sofort ausgeführt.
        self._last_sync: dict[str, datetime | None] = {
            # NOTE: "charts" and "new_releases" removed - generic browse content
            # User syncs (auth required)
            "artists": None,
            "playlists": None,
            "saved_albums": None,
            "saved_tracks": None,
            # Gradual background syncs (auth required - needs followed artists first)
            "artist_albums": None,  # Gradual album sync for artists
            "album_tracks": None,  # Gradual track sync for albums
        }

        # Track sync stats for monitoring
        self._sync_stats: dict[str, dict[str, Any]] = {
            # NOTE: "charts" and "new_releases" removed - generic browse content
            "artists": {"count": 0, "last_result": None, "last_error": None},
            "playlists": {"count": 0, "last_result": None, "last_error": None},
            "saved_albums": {"count": 0, "last_result": None, "last_error": None},
            "saved_tracks": {"count": 0, "last_result": None, "last_error": None},
            "artist_albums": {
                "count": 0,
                "last_result": None,
                "last_error": None,
                "pending": 0,
            },
            "album_tracks": {
                "count": 0,
                "last_result": None,
                "last_error": None,
                "pending": 0,
            },
        }

    async def start(self) -> None:
        """Start the Deezer sync worker.

        Creates a background task that runs the sync loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("deezer_sync.already_running")
            return

        self._running = True
        self._start_time = time.time()  # Reset start time
        self._task = asyncio.create_task(self._run_loop())
        
        logger.info(
            "worker.started",
            extra={
                "worker": "deezer_sync",
                "check_interval_seconds": self.check_interval_seconds,
            },
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
        
        uptime = time.time() - self._start_time
        logger.info(
            "worker.stopped",
            extra={
                "worker": "deezer_sync",
                "cycles_completed": self._cycles_completed,
                "errors_total": self._errors_total,
                "uptime_seconds": round(uptime, 2),
            },
        )

    def _create_sync_service(
        self, session: Any, access_token: str | None, settings_service: Any
    ) -> "DeezerSyncService":
        """Create a DeezerSyncService instance with all dependencies.

        Hey future me - dieser Helper reduziert Code-Duplizierung!
        Jede _run_*_sync Methode braucht denselben Setup-Code:
        - DeezerClient erstellen
        - DeezerPlugin erstellen
        - ImageService erstellen
        - DeezerSyncService erstellen (mit allen deps inkl. image_queue!)

        REFACTORED (Jan 2025): image_queue wird jetzt durchgereicht für async Downloads!
        REFACTORED (Jan 2025): settings_service für persistente Sync-Status!

        Args:
            session: Database session for the sync
            access_token: Deezer OAuth token (None for public API calls)
            settings_service: AppSettingsService instance for persistent sync status

        Returns:
            Configured DeezerSyncService instance
        """
        from soulspot.application.services.deezer_sync_service import DeezerSyncService
        from soulspot.infrastructure.integrations.deezer_client import DeezerClient
        from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

        deezer_client = DeezerClient()
        deezer_plugin = DeezerPlugin(
            client=deezer_client,
            access_token=access_token,
        )
        image_service = _get_image_service()

        return DeezerSyncService(
            session=session,
            deezer_plugin=deezer_plugin,
            image_service=image_service,
            image_queue=self._image_queue,
            settings_service=settings_service,
        )

    async def _run_loop(self) -> None:
        """Main worker loop - checks and runs syncs periodically.

        Hey future me - diese Loop läuft EWIG bis stop() aufgerufen wird!
        """
        # Wait a bit on startup to let other services initialize
        await asyncio.sleep(35)  # Slightly offset from Spotify worker

        logger.info("deezer_sync.loop_started")

        while self._running:
            try:
                await self._check_and_run_syncs()
                self._cycles_completed += 1
                
                # Log health every 10 cycles
                if self._cycles_completed % 10 == 0:
                    log_worker_health(
                        logger=logger,
                        worker_name="deezer_sync",
                        cycles_completed=self._cycles_completed,
                        errors_total=self._errors_total,
                        uptime_seconds=time.time() - self._start_time,
                    )
                
            except Exception as e:
                self._errors_total += 1
                # Don't crash the loop on errors - log and continue
                logger.error(
                    "deezer_sync.loop_error",
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                        "cycle": self._cycles_completed,
                    },
                )

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
                    logger.debug("deezer_sync.skipped", extra={"reason": "auto_sync_disabled"})
                    return

                # Check if provider is enabled
                provider_mode = await settings_service.get_string(
                    "deezer.provider_mode", default="basic"
                )
                if provider_mode == "off":
                    logger.debug("deezer_sync.skipped", extra={"reason": "provider_disabled"})
                    return

                # Get interval settings
                # Hey future me - charts/releases can update less frequently than user data
                await settings_service.get_int(
                    "deezer.charts_sync_interval_minutes", default=60
                )
                await settings_service.get_int(
                    "deezer.new_releases_sync_interval_minutes", default=60
                )
                user_sync_interval = await settings_service.get_int(
                    "deezer.user_sync_interval_minutes", default=10
                )

                now = datetime.now(UTC)

                # NOTE: PUBLIC SYNCS (Charts, New Releases) REMOVED!
                # - Charts: showed random trending content, not personal music
                # - New Releases: now handled by NewReleasesSyncWorker
                # This worker now ONLY syncs USER data (requires auth)

                # =========================================================
                # USER SYNCS - Auth required!
                # =========================================================

                # Check if we have a valid Deezer token
                access_token = await self._get_deezer_token(session)
                if not access_token:
                    logger.debug(
                        "deezer_sync.skipped",
                        extra={
                            "reason": "no_token",
                            "action": "user_needs_to_authenticate",
                        },
                    )
                else:
                    # Followed Artists sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_artists", default=True
                    ) and self._is_sync_due("artists", user_sync_interval, now):
                        await self._run_artists_sync(
                            session, access_token, now, settings_service
                        )

                    # User Playlists sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_playlists", default=True
                    ) and self._is_sync_due("playlists", user_sync_interval, now):
                        await self._run_playlists_sync(
                            session, access_token, now, settings_service
                        )

                    # Saved Albums sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_saved_albums", default=True
                    ) and self._is_sync_due("saved_albums", user_sync_interval, now):
                        await self._run_saved_albums_sync(
                            session, access_token, now, settings_service
                        )

                    # Saved Tracks sync
                    if await settings_service.get_bool(
                        "deezer.auto_sync_saved_tracks", default=True
                    ) and self._is_sync_due("saved_tracks", user_sync_interval, now):
                        await self._run_saved_tracks_sync(
                            session, access_token, now, settings_service
                        )

                    # =========================================================
                    # GRADUAL BACKGROUND SYNCS
                    # Hey future me - these sync albums/tracks for followed artists
                    # gradually to avoid hitting API rate limits!
                    # =========================================================

                    # Gradual Artist Albums sync (like Spotify worker)
                    artist_albums_interval = await settings_service.get_int(
                        "deezer.artist_albums_sync_interval_minutes", default=2
                    )
                    artists_per_cycle = await settings_service.get_int(
                        "deezer.artist_albums_per_cycle", default=5
                    )
                    # Resync settings - how often to refresh existing artists
                    resync_enabled = await settings_service.get_bool(
                        "deezer.auto_resync_artist_albums", default=True
                    )
                    resync_hours = await settings_service.get_int(
                        "deezer.artist_albums_resync_hours", default=24
                    )
                    if await settings_service.get_bool(
                        "deezer.auto_sync_artist_albums", default=True
                    ) and self._is_sync_due(
                        "artist_albums", artist_albums_interval, now
                    ):
                        await self._run_artist_albums_sync(
                            session,
                            access_token,
                            now,
                            settings_service,
                            artists_per_cycle,
                            resync_hours,
                            resync_enabled,
                        )

                    # Gradual Album Tracks sync (load tracks for albums)
                    album_tracks_interval = await settings_service.get_int(
                        "deezer.album_tracks_sync_interval_minutes", default=2
                    )
                    albums_per_cycle = await settings_service.get_int(
                        "deezer.album_tracks_per_cycle", default=10
                    )
                    if await settings_service.get_bool(
                        "deezer.auto_sync_album_tracks", default=True
                    ) and self._is_sync_due("album_tracks", album_tracks_interval, now):
                        await self._run_album_tracks_sync(
                            session,
                            access_token,
                            now,
                            settings_service,
                            albums_per_cycle,
                        )

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

    # NOTE: PUBLIC SYNC METHODS REMOVED!
    # - _run_charts_sync() - Charts showed generic trending content, not personal music
    # - _run_new_releases_sync() - Now handled by NewReleasesSyncWorker
    # This worker now ONLY syncs USER data (requires auth)

    # =========================================================================
    # USER SYNC METHODS (Auth required)
    # =========================================================================

    async def _run_artists_sync(
        self, session: Any, access_token: str, now: datetime, settings_service: Any
    ) -> None:
        """Run followed artists sync."""
        operation_start = time.time()
        logger.info("deezer_sync.artists.started", extra={"scheduled_time": now.isoformat()})

        try:
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )
            result = await sync_service.sync_followed_artists(force=False)

            self._last_sync["artists"] = now
            self._sync_stats["artists"]["count"] += 1
            self._sync_stats["artists"]["last_result"] = result
            self._sync_stats["artists"]["last_error"] = None

            duration = time.time() - operation_start
            logger.info(
                "deezer_sync.artists.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "result": result,
                    "total_cycles": self._sync_stats["artists"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["artists"]["last_error"] = str(e)
            logger.error(
                "deezer_sync.artists.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )

    async def _run_playlists_sync(
        self, session: Any, access_token: str, now: datetime, settings_service: Any
    ) -> None:
        """Run user playlists sync."""
        operation_start = time.time()
        logger.info("deezer_sync.playlists.started", extra={"scheduled_time": now.isoformat()})

        try:
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )
            result = await sync_service.sync_user_playlists(force=False)

            self._last_sync["playlists"] = now
            self._sync_stats["playlists"]["count"] += 1
            self._sync_stats["playlists"]["last_result"] = result
            self._sync_stats["playlists"]["last_error"] = None

            duration = time.time() - operation_start
            logger.info(
                "deezer_sync.playlists.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "result": result,
                    "total_cycles": self._sync_stats["playlists"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["playlists"]["last_error"] = str(e)
            logger.error(
                "deezer_sync.playlists.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )

    async def _run_saved_albums_sync(
        self, session: Any, access_token: str, now: datetime, settings_service: Any
    ) -> None:
        """Run saved albums sync."""
        operation_start = time.time()
        logger.info("deezer_sync.saved_albums.started", extra={"scheduled_time": now.isoformat()})

        try:
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )
            result = await sync_service.sync_saved_albums(force=False)

            self._last_sync["saved_albums"] = now
            self._sync_stats["saved_albums"]["count"] += 1
            self._sync_stats["saved_albums"]["last_result"] = result
            self._sync_stats["saved_albums"]["last_error"] = None

            duration = time.time() - operation_start
            logger.info(
                "deezer_sync.saved_albums.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "result": result,
                    "total_cycles": self._sync_stats["saved_albums"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["saved_albums"]["last_error"] = str(e)
            logger.error(
                "deezer_sync.saved_albums.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )

    async def _run_saved_tracks_sync(
        self, session: Any, access_token: str, now: datetime, settings_service: Any
    ) -> None:
        """Run saved tracks sync."""
        operation_start = time.time()
        logger.info("deezer_sync.saved_tracks.started", extra={"scheduled_time": now.isoformat()})

        try:
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )
            result = await sync_service.sync_saved_tracks(force=False)

            self._last_sync["saved_tracks"] = now
            self._sync_stats["saved_tracks"]["count"] += 1
            self._sync_stats["saved_tracks"]["last_result"] = result
            self._sync_stats["saved_tracks"]["last_error"] = None

            duration = time.time() - operation_start
            logger.info(
                "deezer_sync.saved_tracks.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "result": result,
                    "total_cycles": self._sync_stats["saved_tracks"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["saved_tracks"]["last_error"] = str(e)
            logger.error(
                "deezer_sync.saved_tracks.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )

    # =========================================================================
    # GRADUAL BACKGROUND SYNCS (artist_albums, album_tracks)
    # Hey future me - these work exactly like the Spotify versions!
    # =========================================================================

    async def _run_artist_albums_sync(
        self,
        session: Any,
        access_token: str,
        now: datetime,
        settings_service: Any,
        artists_per_cycle: int = 5,
        resync_hours: int = 24,
        resync_enabled: bool = True,
    ) -> None:
        """Run gradual artist albums sync (initial + periodic resync).

        Hey future me - this is the GRADUAL background album sync for Deezer!
        Deezer's get_artist_albums() returns simplified albums WITHOUT tracks,
        just like Spotify. So we need to sync tracks separately.

        Unlike Spotify, Deezer albums don't need OAuth for fetching (only the
        followed artists list needs OAuth).

        NEW: Also resyncs existing artists periodically to catch new releases!

        Priority order:
        1. Artists that have NEVER been synced (albums_synced_at IS NULL)
        2. Artists that need RESYNC (albums_synced_at older than resync_hours)

        Args:
            session: Database session
            access_token: Deezer OAuth token (for getting artist IDs)
            now: Current timestamp
            settings_service: AppSettingsService for persistent sync status
            artists_per_cycle: How many artists to process (default 5)
            resync_hours: How many hours before resync is needed (default 24)
            resync_enabled: Whether to resync existing artists (default True)
        """
        operation_start = time.time()
        
        try:
            from soulspot.infrastructure.persistence.repositories import (
                SpotifyBrowseRepository,
            )

            repo = SpotifyBrowseRepository(session)

            # Hey future me - TWO-PHASE SYNC just like SpotifySyncWorker!
            # 1. First, get artists that have NEVER been synced (priority)
            # 2. Then, if resync enabled and space left, get artists needing RESYNC
            artists_to_sync: list[Any] = []

            # Phase 1: Get never-synced artists (highest priority)
            pending_artists = await repo.get_artists_pending_album_sync(
                limit=artists_per_cycle, source="deezer"
            )
            pending_count = await repo.count_artists_pending_album_sync(source="deezer")
            artists_to_sync.extend(pending_artists)

            # Phase 2: If resync enabled and we have room, add artists needing resync
            resync_count = 0
            if resync_enabled and len(artists_to_sync) < artists_per_cycle:
                remaining_slots = artists_per_cycle - len(artists_to_sync)
                resync_artists = await repo.get_artists_due_for_resync(
                    max_age_hours=resync_hours,
                    limit=remaining_slots,
                    source="deezer",
                )
                resync_count = await repo.count_artists_due_for_resync(
                    max_age_hours=resync_hours, source="deezer"
                )
                artists_to_sync.extend(resync_artists)

            if not artists_to_sync:
                logger.debug("No Deezer artists pending album sync or needing resync")
                self._sync_stats["artist_albums"]["pending"] = 0
                self._sync_stats["artist_albums"]["resync_pending"] = 0
                return

            # Log what we're doing
            new_count = len(pending_artists)
            resync_this_cycle = len(artists_to_sync) - new_count
            logger.info(
                f"Starting gradual Deezer artist albums sync: "
                f"{new_count} new + {resync_this_cycle} resync = {len(artists_to_sync)} artists "
                f"this cycle. Pending: {pending_count} new, {resync_count} resync"
            )

            # Set up sync service via helper (includes image_queue!)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            synced_count = 0
            total_albums = 0

            for artist in artists_to_sync:
                try:
                    # Sync albums for this artist
                    # Hey future me - artist.deezer_id is the Deezer ID from the model!
                    result = await sync_service.sync_artist_albums(
                        deezer_artist_id=artist.deezer_id,
                        force=True,
                    )

                    if result.get("albums_synced"):
                        synced_count += 1
                        total_albums += result.get("albums_synced", 0)
                        logger.debug(
                            f"Synced {result.get('albums_synced', 0)} albums for {artist.name}"
                        )

                    # Small delay between artists
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(
                        f"Failed to sync albums for Deezer artist {artist.name}: {e}"
                    )

            # Update tracking
            self._last_sync["artist_albums"] = now
            self._sync_stats["artist_albums"]["count"] += 1
            self._sync_stats["artist_albums"]["last_result"] = {
                "artists_synced": synced_count,
                "total_albums": total_albums,
                "new_artists": new_count,
                "resync_artists": resync_this_cycle,
            }
            self._sync_stats["artist_albums"]["last_error"] = None
            self._sync_stats["artist_albums"]["pending"] = pending_count
            self._sync_stats["artist_albums"]["resync_pending"] = resync_count

            logger.info(
                f"Gradual Deezer artist albums sync complete: {synced_count} artists, "
                f"{total_albums} albums. Still pending: {pending_count - synced_count}"
            )

        except Exception as e:
            self._sync_stats["artist_albums"]["last_error"] = str(e)
            logger.error(f"Deezer artist albums sync failed: {e}", exc_info=True)

    async def _run_album_tracks_sync(
        self,
        session: Any,
        access_token: str,
        now: datetime,
        settings_service: Any,
        albums_per_cycle: int = 10,
    ) -> None:
        """Run gradual album tracks sync (load tracks for albums that don't have them).

        Hey future me - this is the SECOND gradual background sync for Deezer!
        Deezer's get_artist_albums() returns simplified album objects WITHOUT tracks.
        This sync gradually fills in the tracks.

        IMPORTANT: Deezer get_album_tracks() is PUBLIC API - no OAuth needed!
        We still require access_token for consistency but could work without it.

        Args:
            session: Database session
            access_token: Deezer OAuth token (not actually needed for this call)
            now: Current timestamp
            settings_service: AppSettingsService for persistent sync status
            albums_per_cycle: How many albums to process (default 10)
        """
        try:
            from soulspot.infrastructure.persistence.repositories import (
                SpotifyBrowseRepository,
            )

            repo = SpotifyBrowseRepository(session)

            # Get Deezer albums that haven't had tracks synced
            pending_albums = await repo.get_albums_pending_track_sync(
                limit=albums_per_cycle, source="deezer"
            )
            pending_count = await repo.count_albums_pending_track_sync(source="deezer")

            if not pending_albums:
                logger.debug("No Deezer albums pending track sync")
                self._sync_stats["album_tracks"]["pending"] = 0
                return

            logger.info(
                f"Starting gradual Deezer album tracks sync: {len(pending_albums)} albums "
                f"this cycle. Total pending: {pending_count}"
            )

            # Set up sync service via helper (includes image_queue!)
            # Hey future me - access_token not really needed for get_album_tracks
            # but DeezerPlugin constructor accepts it
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            synced_count = 0
            total_tracks = 0

            for album in pending_albums:
                try:
                    # Sync tracks for this album
                    # Hey future me - album.deezer_id is the Deezer ID from the model!
                    result = await sync_service.sync_album_tracks(
                        deezer_album_id=album.deezer_id,
                        force=True,
                    )

                    if result.get("synced"):
                        synced_count += 1
                        total_tracks += result.get("tracks_synced", 0)
                        logger.debug(
                            f"Synced {result.get('tracks_synced', 0)} tracks for album "
                            f"'{album.title}'"
                        )
                    elif result.get("error"):
                        logger.warning(
                            f"Failed to sync tracks for Deezer album '{album.title}': "
                            f"{result.get('error')}"
                        )

                    # Small delay between albums
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(
                        f"Failed to sync tracks for Deezer album {album.title}: {e}"
                    )

            # Update tracking
            self._last_sync["album_tracks"] = now
            self._sync_stats["album_tracks"]["count"] += 1
            self._sync_stats["album_tracks"]["last_result"] = {
                "albums_synced": synced_count,
                "total_tracks": total_tracks,
            }
            self._sync_stats["album_tracks"]["last_error"] = None
            self._sync_stats["album_tracks"]["pending"] = pending_count - synced_count

            logger.info(
                f"Gradual Deezer album tracks sync complete: {synced_count} albums, "
                f"{total_tracks} tracks. Still pending: {pending_count - synced_count}"
            )

        except Exception as e:
            self._sync_stats["album_tracks"]["last_error"] = str(e)
            logger.error(f"Deezer album tracks sync failed: {e}", exc_info=True)

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
            # NOTE: charts_cache_stats and new_releases_cache_stats removed
            # - Charts: showed generic browse content, feature removed
            # - New Releases: now handled by NewReleasesSyncWorker
        }

    # NOTE: get_cached_charts() REMOVED - Charts feature removed
    # NOTE: get_cached_new_releases() REMOVED - use NewReleasesSyncWorker
    # NOTE: force_charts_sync() REMOVED - Charts feature removed
    # NOTE: force_new_releases_sync() REMOVED - use NewReleasesSyncWorker

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

    async def force_sync(self, sync_type: str | None = None) -> dict[str, Any]:
        """Force an immediate sync (bypass cooldown).

        Hey future me - this is the equivalent of SpotifySyncWorker.force_sync()!
        Allows manual triggering of syncs from the UI or API.

        Args:
            sync_type: Specific sync to run, or None for all.
                       Options: "artists", "playlists", "saved_albums",
                                "saved_tracks", "artist_albums", "album_tracks"
                       NOTE: "charts" and "new_releases" removed - generic browse content

        Returns:
            Dict with sync results for each type.
        """
        results: dict[str, Any] = {}

        async with self.db.session_scope() as session:
            try:
                now = datetime.now(UTC)

                # Get Deezer token for user syncs
                access_token = await self._get_deezer_token(session)

                # NOTE: PUBLIC SYNCS (charts, new_releases) REMOVED!
                if sync_type in ("charts", "new_releases"):
                    results[sync_type] = (
                        "feature removed - use NewReleasesSyncWorker for new releases"
                    )

                # USER SYNCS (auth required)
                if not access_token:
                    if sync_type in (
                        "artists",
                        "playlists",
                        "saved_albums",
                        "saved_tracks",
                        "artist_albums",
                        "album_tracks",
                    ):
                        return {
                            "error": "No valid Deezer token available for user syncs"
                        }
                else:
                    if sync_type is None or sync_type == "artists":
                        try:
                            await self._run_artists_sync(session, access_token, now)
                            results["artists"] = "success"
                        except Exception as e:
                            results["artists"] = f"error: {e}"

                    if sync_type is None or sync_type == "playlists":
                        try:
                            await self._run_playlists_sync(session, access_token, now)
                            results["playlists"] = "success"
                        except Exception as e:
                            results["playlists"] = f"error: {e}"

                    if sync_type is None or sync_type == "saved_albums":
                        try:
                            await self._run_saved_albums_sync(
                                session, access_token, now
                            )
                            results["saved_albums"] = "success"
                        except Exception as e:
                            results["saved_albums"] = f"error: {e}"

                    if sync_type is None or sync_type == "saved_tracks":
                        try:
                            await self._run_saved_tracks_sync(
                                session, access_token, now
                            )
                            results["saved_tracks"] = "success"
                        except Exception as e:
                            results["saved_tracks"] = f"error: {e}"

                    if sync_type is None or sync_type == "artist_albums":
                        try:
                            # Force sync a batch of pending/resync artists
                            await self._run_artist_albums_sync(
                                session, access_token, now, artists_per_cycle=10
                            )
                            results["artist_albums"] = "success"
                        except Exception as e:
                            results["artist_albums"] = f"error: {e}"

                    if sync_type is None or sync_type == "album_tracks":
                        try:
                            # Force sync a batch of pending albums
                            await self._run_album_tracks_sync(
                                session, access_token, now, albums_per_cycle=20
                            )
                            results["album_tracks"] = "success"
                        except Exception as e:
                            results["album_tracks"] = f"error: {e}"

                await session.commit()

            except Exception as e:
                await session.rollback()
                results["error"] = str(e)

        return results
