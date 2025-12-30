# Hey future me - dieser Worker führt den Spotify Auto-Sync automatisch aus!
#
# Das Problem: Wir haben SpotifySyncService mit allen Sync-Methoden, aber nichts
# das diese periodisch aufruft. Dieser Worker macht genau das.
#
# Der Worker läuft in einer Endlosschleife und:
# 1. Prüft alle X Sekunden ob ein Sync fällig ist
# 2. Liest die Settings aus der DB (AppSettingsService)
# 3. Trackt wann der letzte Sync für jeden Typ war (in-memory)
# 4. Führt den Sync aus wenn: enabled UND cooldown abgelaufen
#
# Cooldown-Logik:
# - Jeder Sync-Typ (artists, playlists, liked, albums) hat eigenen Cooldown
# - Default: artists=5min, playlists=10min
# - Cooldown wird nach erfolgreichem Sync zurückgesetzt
#
# Fehlerbehandlung:
# - Wenn Sync fehlschlägt: Loggen und beim nächsten Durchlauf nochmal versuchen
# - Kein Crash der Loop!
# - Bei Token-Fehler (401): Worker läuft weiter, aber skippt Syncs bis Token wieder da ist
#
# UPDATE (Nov 2025): Now uses session_scope context manager instead of async generator
# to fix "GC cleaning up non-checked-in connection" errors.
"""Background worker for automatic Spotify data synchronization."""

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from soulspot.infrastructure.observability import log_worker_health

if TYPE_CHECKING:
    from soulspot.application.services.images import ImageDownloadQueue, ImageService
    from soulspot.application.services.token_manager import DatabaseTokenManager
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


class SpotifySyncWorker:
    """Background worker that automatically syncs data from Spotify.

    Runs every `check_interval_seconds` and executes enabled syncs when their
    cooldown has expired. Syncs include:
    - Followed Artists
    - User Playlists
    - Liked Songs
    - Saved Albums

    Settings are read from database (app_settings table) and can be changed
    at runtime without restarting the worker.

    On sync failure:
    - Logs error and continues (no crash loop)
    - Retries on next check cycle
    - If auth fails (401), skips sync until token is refreshed
    """

    def __init__(
        self,
        db: "Database",
        token_manager: "DatabaseTokenManager",
        settings: "Settings",
        check_interval_seconds: int = 60,  # Check every minute
        image_queue: "ImageDownloadQueue | None" = None,
    ) -> None:
        """Initialize Spotify sync worker.

        Args:
            db: Database instance for creating sessions
            token_manager: DatabaseTokenManager for getting access tokens
            settings: Application settings (for SpotifyClient config)
            check_interval_seconds: How often to check if syncs are due
            image_queue: Optional queue for async image downloads
        """
        self.db = db
        self.token_manager = token_manager
        self.settings = settings
        self.check_interval_seconds = check_interval_seconds
        self._image_queue = image_queue
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Hey future me - diese Timestamps tracken wann der letzte erfolgreiche Sync war.
        # Sie sind in-memory, d.h. beim Neustart werden alle Syncs sofort ausgeführt.
        # Das ist gewollt - nach einem Restart wollen wir einen Fresh Sync.
        self._last_sync: dict[str, datetime | None] = {
            "artists": None,
            "playlists": None,
            "liked_songs": None,
            "saved_albums": None,
            "artist_albums": None,  # Gradual background album sync
            "album_tracks": None,  # Gradual background track sync for albums
        }

        # Hey future me - RATE LIMIT COOLDOWN!
        # Wenn wir einen 429 Error bekommen, setzen wir diesen Timestamp.
        # Alle Syncs werden dann bis zu diesem Zeitpunkt pausiert.
        # Das verhindert den "infinite 429 loop" bei heavy rate limiting.
        # Backoff: 5 min → 10 min → 20 min (exponentiell, max 60 min)
        self._rate_limit_until: datetime | None = None
        self._rate_limit_backoff_minutes: int = 5  # Initial backoff

        # Track sync stats for monitoring
        self._sync_stats: dict[str, dict[str, Any]] = {
            "artists": {"count": 0, "last_result": None, "last_error": None},
            "playlists": {"count": 0, "last_result": None, "last_error": None},
            "liked_songs": {"count": 0, "last_result": None, "last_error": None},
            "saved_albums": {"count": 0, "last_result": None, "last_error": None},
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

        # Worker lifecycle tracking for health logging
        self._cycles_completed: int = 0
        self._errors_total: int = 0
        self._start_time: float = time.time()

    def _is_rate_limited(self) -> bool:
        """Check if we're currently in rate limit cooldown.

        Hey future me - diese Methode prüft ob wir noch im Rate Limit Cooldown sind.
        Wenn ja, sollten KEINE Syncs ausgeführt werden!
        """
        if self._rate_limit_until is None:
            return False

        now = datetime.now(UTC)
        if now >= self._rate_limit_until:
            # Cooldown expired - reset
            self._rate_limit_until = None
            self._rate_limit_backoff_minutes = 5  # Reset backoff
            logger.info("Spotify rate limit cooldown expired, resuming syncs")
            return False

        # Still in cooldown
        remaining = self._rate_limit_until - now
        logger.debug(
            f"Rate limited for {remaining.total_seconds():.0f}s more "
            f"(until {self._rate_limit_until.isoformat()})"
        )
        return True

    def _set_rate_limit_cooldown(self, retry_after_seconds: int | None = None) -> None:
        """Set rate limit cooldown after receiving 429.

        Hey future me - EXPONENTIELLES BACKOFF!
        5 min → 10 min → 20 min → 40 min → 60 min (max)

        Wenn Spotify Retry-After header sendet, nutze das als Minimum.
        """
        now = datetime.now(UTC)

        # Use retry_after if provided, otherwise use backoff
        if retry_after_seconds and retry_after_seconds > 0:
            # Spotify told us how long to wait
            cooldown_seconds = max(
                retry_after_seconds, self._rate_limit_backoff_minutes * 60
            )
        else:
            # Use exponential backoff
            cooldown_seconds = self._rate_limit_backoff_minutes * 60

        self._rate_limit_until = now + timedelta(seconds=cooldown_seconds)

        # Increase backoff for next time (exponential, max 60 min)
        self._rate_limit_backoff_minutes = min(
            self._rate_limit_backoff_minutes * 2,
            60,  # Max 60 minutes
        )

        logger.warning(
            f"Spotify rate limited! Pausing all syncs for {cooldown_seconds}s "
            f"(until {self._rate_limit_until.isoformat()}). "
            f"Next backoff will be {self._rate_limit_backoff_minutes} minutes."
        )

    def _reset_rate_limit_on_success(self) -> None:
        """Reset rate limit backoff after successful sync.

        Hey future me - nach einem erfolgreichen Sync setzen wir den Backoff zurück.
        Das bedeutet: Wenn wir einmal rate limited werden und dann wieder
        erfolgreich syncen, startet der nächste Backoff wieder bei 5 Minuten.
        """
        if self._rate_limit_backoff_minutes > 5:
            logger.info("Successful sync - resetting rate limit backoff to 5 minutes")
            self._rate_limit_backoff_minutes = 5

    def _create_sync_service(
        self, session: Any, access_token: str, settings_service: Any
    ) -> Any:
        """Create SpotifySyncService with all dependencies.

        Hey future me - ZENTRALE Factory für SpotifySyncService!
        Alle _run_*_sync Methoden nutzen diese Helper-Methode.
        So wird image_queue korrekt an ALLE Service-Instanzen übergeben.

        Args:
            session: Database session
            access_token: Spotify access token
            settings_service: AppSettingsService instance

        Returns:
            SpotifySyncService instance
        """
        from soulspot.application.services.spotify_sync_service import (
            SpotifySyncService,
        )
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
        from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

        spotify_client = SpotifyClient(self.settings.spotify)
        spotify_plugin = SpotifyPlugin(client=spotify_client, access_token=access_token)
        image_service = _get_image_service()

        return SpotifySyncService(
            session=session,
            spotify_plugin=spotify_plugin,
            image_service=image_service,
            image_queue=self._image_queue,
            settings_service=settings_service,
        )

    async def start(self) -> None:
        """Start the Spotify sync worker.

        Creates a background task that runs the sync loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("spotify_sync.already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "worker.started",
            extra={
                "worker": "spotify_sync",
                "check_interval_seconds": self.check_interval_seconds,
            },
        )

    async def stop(self) -> None:
        """Stop the Spotify sync worker.

        Cancels the background task and waits for cleanup.
        Safe to call multiple times (idempotent).
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info(
            "worker.stopped",
            extra={
                "worker": "spotify_sync",
                "cycles_completed": self._cycles_completed,
                "errors_total": self._errors_total,
                "uptime_seconds": int(time.time() - self._start_time),
            },
        )

    async def _run_loop(self) -> None:
        """Main worker loop - checks and runs syncs periodically.

        Hey future me - diese Loop laeuft EWIG bis stop() aufgerufen wird!
        Auf jedem Durchlauf:
        1. Hole Settings aus DB (welche Syncs enabled, Intervalle)
        2. Pruefe ob ein Sync faellig ist (Cooldown abgelaufen)
        3. Fuehre faellige Syncs aus
        4. Schlafe fuer check_interval_seconds
        """
        logger.info("spotify_sync.main_loop.entered")

        while self._running:
            try:
                await self._check_and_run_syncs()
                self._cycles_completed += 1

                # Log health every 10 cycles
                if self._cycles_completed % 10 == 0:
                    log_worker_health(
                        logger,
                        "spotify_sync",
                        self._cycles_completed,
                        self._errors_total,
                        time.time() - self._start_time,
                    )

            except Exception as e:
                # Do not crash the loop on errors - log and continue
                self._errors_total += 1
                logger.error(
                    "spotify_sync.cycle.failed",
                    extra={"error_type": type(e).__name__},
                    exc_info=True,
                )

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                # Worker is being stopped
                break

    async def _check_and_run_syncs(self) -> None:
        """Check settings and run any due syncs.

        Hey future me - diese Methode wird alle check_interval_seconds aufgerufen.
        Sie holt die aktuellen Settings aus der DB (damit Runtime-Aenderungen wirken)
        und fuehrt alle faelligen Syncs aus.

        UPDATE (Nov 2025): Now uses session_scope context manager instead of
        async generator to fix GC cleaning up non-checked-in connection errors.

        UPDATE (Dez 2025): Added rate limit cooldown check!
        If rate limited, we skip ALL syncs until cooldown expires.
        """
        # Hey future me - RATE LIMIT CHECK FIRST!
        # If in cooldown, do not try to sync.
        if self._is_rate_limited():
            logger.debug("spotify_sync.skipped", extra={"reason": "rate_limited"})
            return

        # Get a fresh DB session for this cycle using session_scope context manager
        # Hey future me - using session_scope ensures proper connection cleanup!
        async with self.db.session_scope() as session:
            try:
                # Import here to avoid circular imports
                from soulspot.application.services.app_settings_service import (
                    AppSettingsService,
                )

                settings_service = AppSettingsService(session)

                # Check master toggle first
                auto_sync_enabled = await settings_service.get_bool(
                    "spotify.auto_sync_enabled", default=True
                )

                if not auto_sync_enabled:
                    logger.debug(
                        "spotify_sync.skipped", extra={"reason": "auto_sync_disabled"}
                    )
                    return

                # Get access token - if not available, skip this cycle
                access_token = await self.token_manager.get_token_for_background()
                if not access_token:
                    logger.warning(
                        "spotify_sync.skipped",
                        extra={
                            "reason": "no_token",
                            "action": "user_needs_to_authenticate",
                        },
                    )
                    return

                # Get interval settings
                artists_interval = await settings_service.get_int(
                    "spotify.artists_sync_interval_minutes", default=5
                )
                playlists_interval = await settings_service.get_int(
                    "spotify.playlists_sync_interval_minutes", default=10
                )

                # Check which syncs are enabled and due
                now = datetime.now(UTC)

                # Artists sync
                if await settings_service.get_bool(
                    "spotify.auto_sync_artists", default=True
                ) and self._is_sync_due("artists", artists_interval, now):
                    await self._run_artists_sync(session, access_token, now)

                # Playlists sync
                if await settings_service.get_bool(
                    "spotify.auto_sync_playlists", default=True
                ) and self._is_sync_due("playlists", playlists_interval, now):
                    await self._run_playlists_sync(session, access_token, now)

                # Liked Songs sync (uses playlists interval)
                if await settings_service.get_bool(
                    "spotify.auto_sync_liked_songs", default=True
                ) and self._is_sync_due("liked_songs", playlists_interval, now):
                    await self._run_liked_songs_sync(session, access_token, now)

                # Saved Albums sync (uses playlists interval)
                if await settings_service.get_bool(
                    "spotify.auto_sync_saved_albums", default=True
                ) and self._is_sync_due("saved_albums", playlists_interval, now):
                    await self._run_saved_albums_sync(session, access_token, now)

                # Gradual Artist Albums sync - loads albums for a few artists per cycle
                # Hey future me - this syncs albums gradually to avoid API rate limits!
                # Default: 5 artists per cycle, every 2 minutes = ~150 artists/hour
                # NEW: Also resyncs existing artists to catch new releases!
                artist_albums_interval = await settings_service.get_int(
                    "spotify.artist_albums_sync_interval_minutes", default=2
                )
                artists_per_cycle = await settings_service.get_int(
                    "spotify.artist_albums_per_cycle", default=5
                )
                # Resync settings - how often to refresh existing artists
                resync_enabled = await settings_service.get_bool(
                    "spotify.auto_resync_artist_albums", default=True
                )
                resync_hours = await settings_service.get_int(
                    "spotify.artist_albums_resync_hours", default=24
                )
                if await settings_service.get_bool(
                    "spotify.auto_sync_artist_albums", default=True
                ) and self._is_sync_due("artist_albums", artist_albums_interval, now):
                    await self._run_artist_albums_sync(
                        session,
                        access_token,
                        now,
                        artists_per_cycle,
                        resync_hours,
                        resync_enabled,
                    )

                # Gradual Album Tracks sync - loads tracks for albums that don't have them
                # Hey future me - this is the SECOND gradual sync!
                # When we sync artist albums, Spotify only returns simplified album objects
                # WITHOUT tracks. This sync gradually fills in the tracks for those albums.
                # Default: 10 albums per cycle, every 2 minutes = ~300 albums/hour
                album_tracks_interval = await settings_service.get_int(
                    "spotify.album_tracks_sync_interval_minutes", default=2
                )
                albums_per_cycle = await settings_service.get_int(
                    "spotify.album_tracks_per_cycle", default=10
                )
                if await settings_service.get_bool(
                    "spotify.auto_sync_album_tracks", default=True
                ) and self._is_sync_due("album_tracks", album_tracks_interval, now):
                    await self._run_album_tracks_sync(
                        session,
                        access_token,
                        now,
                        albums_per_cycle,
                    )

                # Commit any changes
                await session.commit()

                # Hey future me - successful sync cycle means we're not rate limited!
                # Reset the backoff so next rate limit starts at 5 minutes again.
                self._reset_rate_limit_on_success()

            except Exception as e:
                # Check if this is a rate limit error
                error_str = str(e).lower()
                if (
                    "429" in error_str
                    or "rate limit" in error_str
                    or "too many requests" in error_str
                ):
                    # Extract retry-after if present in the error message
                    retry_after = None
                    if "retry after" in error_str or "retry-after" in error_str:
                        # Try to extract number from error message
                        import re

                        match = re.search(r"retry[- ]?after[:\s]*(\d+)", error_str)
                        if match:
                            retry_after = int(match.group(1))

                    # Set rate limit cooldown
                    self._set_rate_limit_cooldown(retry_after)
                else:
                    logger.error(f"Error in sync cycle: {e}", exc_info=True)
                await session.rollback()

    def _is_sync_due(
        self, sync_type: str, interval_minutes: int, now: datetime
    ) -> bool:
        """Check if a sync is due based on its cooldown interval.

        Args:
            sync_type: Type of sync (artists, playlists, etc.)
            interval_minutes: Cooldown in minutes
            now: Current time

        Returns:
            True if sync should run, False otherwise
        """
        last_sync = self._last_sync.get(sync_type)

        if last_sync is None:
            # Never synced - do it now
            return True

        # Check if cooldown has expired
        cooldown = timedelta(minutes=interval_minutes)
        return (now - last_sync) >= cooldown

    async def _run_artists_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run artists sync and update tracking.

        Hey future me - nutzt jetzt _create_sync_service() Helper!
        Das stellt sicher dass image_queue korrekt übergeben wird.
        """
        operation_start = time.time()
        logger.info("spotify_sync.artists.started", extra={"scheduled_time": now.isoformat()})

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )

            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            result = await sync_service.sync_followed_artists(force=False)

            # Update tracking
            self._last_sync["artists"] = now
            self._sync_stats["artists"]["count"] += 1
            self._sync_stats["artists"]["last_result"] = result
            self._sync_stats["artists"]["last_error"] = None

            duration = time.time() - operation_start
            synced = result.get("synced", 0) if result else 0
            removed = result.get("removed", 0) if result else 0
            
            logger.info(
                "spotify_sync.artists.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "synced": synced,
                    "removed": removed,
                    "total_cycles": self._sync_stats["artists"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["artists"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.artists.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _run_playlists_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run playlists sync and update tracking."""
        operation_start = time.time()
        logger.info("spotify_sync.playlists.started", extra={"scheduled_time": now.isoformat()})

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )

            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            result = await sync_service.sync_user_playlists(force=False)

            self._last_sync["playlists"] = now
            self._sync_stats["playlists"]["count"] += 1
            self._sync_stats["playlists"]["last_result"] = result
            self._sync_stats["playlists"]["last_error"] = None

            duration = time.time() - operation_start
            synced = result.get("synced", 0) if result else 0
            removed = result.get("removed", 0) if result else 0
            
            logger.info(
                "spotify_sync.playlists.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "synced": synced,
                    "removed": removed,
                    "total_cycles": self._sync_stats["playlists"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["playlists"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.playlists.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _run_liked_songs_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run liked songs sync and update tracking."""
        operation_start = time.time()
        logger.info("spotify_sync.liked_songs.started", extra={"scheduled_time": now.isoformat()})

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )

            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            result = await sync_service.sync_liked_songs(force=False)

            self._last_sync["liked_songs"] = now
            self._sync_stats["liked_songs"]["count"] += 1
            self._sync_stats["liked_songs"]["last_result"] = result
            self._sync_stats["liked_songs"]["last_error"] = None

            duration = time.time() - operation_start
            track_count = result.get("track_count", 0) if result else 0
            
            logger.info(
                "spotify_sync.liked_songs.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "track_count": track_count,
                    "total_cycles": self._sync_stats["liked_songs"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["liked_songs"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.liked_songs.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _run_saved_albums_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run saved albums sync and update tracking."""
        operation_start = time.time()
        logger.info("spotify_sync.saved_albums.started", extra={"scheduled_time": now.isoformat()})

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )

            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            result = await sync_service.sync_saved_albums(force=False)

            self._last_sync["saved_albums"] = now
            self._sync_stats["saved_albums"]["count"] += 1
            self._sync_stats["saved_albums"]["last_result"] = result
            self._sync_stats["saved_albums"]["last_error"] = None

            duration = time.time() - operation_start
            synced = result.get("synced", 0) if result else 0
            
            logger.info(
                "spotify_sync.saved_albums.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "synced": synced,
                    "total_cycles": self._sync_stats["saved_albums"]["count"],
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["saved_albums"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.saved_albums.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _run_artist_albums_sync(
        self,
        session: Any,
        access_token: str,
        now: datetime,
        artists_per_cycle: int = 5,
        resync_hours: int = 24,
        resync_enabled: bool = True,
    ) -> None:
        """Run gradual artist albums sync (initial + periodic resync).

        Hey future me - this is the GRADUAL background album sync!
        Instead of syncing all 358+ artists at once (would hit API limits),
        we sync a few artists per cycle. With default settings:
        - 5 artists per cycle
        - Every 2 minutes
        - = 150 artists/hour
        - = All 358 artists done in ~2.5 hours

        This runs AFTER the initial artist sync, gradually filling in albums
        for artists that haven't had their albums synced yet.

        NEW (Dec 2025): Also resyncs existing artists periodically!
        If resync_enabled=True, we'll also include artists whose albums_synced_at
        is older than resync_hours. This ensures New Releases stay fresh
        without requiring manual page visits.

        Priority order:
        1. Artists that have NEVER been synced (albums_synced_at IS NULL)
        2. Artists that need RESYNC (albums_synced_at older than resync_hours)

        Args:
            session: Database session
            access_token: Spotify OAuth token
            now: Current timestamp
            artists_per_cycle: How many artists to process (default 5)
            resync_hours: How many hours before resync is needed (default 24)
            resync_enabled: Whether to resync existing artists (default True)
        """
        operation_start = time.time()
        
        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.infrastructure.persistence.repositories import (
                SpotifyBrowseRepository,
            )

            repo = SpotifyBrowseRepository(session)

            # Hey future me - TWO-PHASE SYNC:
            # 1. First, get artists that have NEVER been synced (priority)
            # 2. Then, if resync enabled and space left, get artists needing RESYNC
            artists_to_sync: list[Any] = []

            # Phase 1: Get never-synced artists (highest priority)
            # Hey future me - explicit source="spotify" for clarity!
            pending_artists = await repo.get_artists_pending_album_sync(
                limit=artists_per_cycle, source="spotify"
            )
            pending_count = await repo.count_artists_pending_album_sync(
                source="spotify"
            )
            artists_to_sync.extend(pending_artists)

            # Phase 2: If resync enabled and we have room, add artists needing resync
            resync_count = 0
            if resync_enabled and len(artists_to_sync) < artists_per_cycle:
                remaining_slots = artists_per_cycle - len(artists_to_sync)
                resync_artists = await repo.get_artists_due_for_resync(
                    max_age_hours=resync_hours,
                    limit=remaining_slots,
                    source="spotify",
                )
                resync_count = await repo.count_artists_due_for_resync(
                    max_age_hours=resync_hours, source="spotify"
                )
                artists_to_sync.extend(resync_artists)

            if not artists_to_sync:
                # All artists have been synced and none need resync
                logger.debug(
                    "spotify_sync.artist_albums.skipped",
                    extra={
                        "reason": "no_artists_pending",
                        "pending_count": 0,
                        "resync_count": 0,
                    },
                )
                self._sync_stats["artist_albums"]["pending"] = 0
                self._sync_stats["artist_albums"]["resync_pending"] = 0
                return

            # Log what we're doing
            new_count = len(pending_artists)
            resync_this_cycle = len(artists_to_sync) - new_count
            logger.info(
                "spotify_sync.artist_albums.started",
                extra={
                    "scheduled_time": now.isoformat(),
                    "new_artists": new_count,
                    "resync_artists": resync_this_cycle,
                    "total_this_cycle": len(artists_to_sync),
                    "pending_new": pending_count,
                    "pending_resync": resync_count,
                },
            )

            # Set up services
            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            synced_count = 0
            total_albums = 0

            for artist in artists_to_sync:
                try:
                    # Sync albums for this artist
                    result = await sync_service.sync_artist_albums(
                        artist_id=artist.spotify_id,
                        force=True,  # Skip cooldown since we're doing gradual sync
                    )

                    if result.get("synced"):
                        synced_count += 1
                        total_albums += result.get("total", 0)
                        logger.debug(
                            "spotify_sync.artist_albums.artist_synced",
                            extra={
                                "artist_name": artist.name,
                                "artist_id": artist.spotify_id,
                                "albums_count": result.get("total", 0),
                            },
                        )

                    # Small delay between artists to be nice to the API
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(
                        "spotify_sync.artist_albums.artist_failed",
                        extra={
                            "artist_name": artist.name,
                            "artist_id": artist.spotify_id,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )
                    # Continue with next artist, don't fail the whole batch

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

            duration = time.time() - operation_start
            logger.info(
                "spotify_sync.artist_albums.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "artists_synced": synced_count,
                    "total_albums": total_albums,
                    "new_artists": new_count,
                    "resync_artists": resync_this_cycle,
                    "pending_new": pending_count,
                    "pending_resync": resync_count,
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["artist_albums"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.artist_albums.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def _run_album_tracks_sync(
        self,
        session: Any,
        access_token: str,
        now: datetime,
        albums_per_cycle: int = 10,
    ) -> None:
        """Run gradual album tracks sync (load tracks for albums that don't have them).

        Hey future me - this is the SECOND gradual background sync!
        When we sync artist albums via get_artist_albums(), Spotify only returns
        simplified album objects WITHOUT tracks (no track list, just basic album info).

        This sync gradually fills in the tracks for albums where tracks_synced_at IS NULL.
        With default settings:
        - 10 albums per cycle
        - Every 2 minutes
        - = 300 albums/hour
        - = All albums done in a few hours (depending on how many artists)

        Why 10 per cycle?
        - get_album() returns full album with tracks in ONE call
        - So 10 albums = 10 API calls
        - Spotify rate limit is ~30 calls/second, but we're being nice with delays
        - 10 per cycle with 0.5s delay = 5 seconds per cycle max

        Args:
            session: Database session
            access_token: Spotify OAuth token
            now: Current timestamp
            albums_per_cycle: How many albums to process (default 10)
        """
        operation_start = time.time()
        
        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.infrastructure.persistence.repositories import (
                SpotifyBrowseRepository,
            )

            repo = SpotifyBrowseRepository(session)

            # Get albums that have never had tracks synced
            # Hey future me - explicit source="spotify" for clarity!
            pending_albums = await repo.get_albums_pending_track_sync(
                limit=albums_per_cycle, source="spotify"
            )
            pending_count = await repo.count_albums_pending_track_sync(source="spotify")

            if not pending_albums:
                # All albums have been synced
                logger.debug(
                    "spotify_sync.album_tracks.skipped",
                    extra={"reason": "no_albums_pending", "pending_count": 0},
                )
                self._sync_stats["album_tracks"]["pending"] = 0
                return

            logger.info(
                "spotify_sync.album_tracks.started",
                extra={
                    "scheduled_time": now.isoformat(),
                    "albums_this_cycle": len(pending_albums),
                    "total_pending": pending_count,
                },
            )

            # Set up services
            settings_service = AppSettingsService(session)
            sync_service = self._create_sync_service(
                session, access_token, settings_service
            )

            synced_count = 0
            total_tracks = 0

            for idx, album in enumerate(pending_albums, 1):
                try:
                    # Get artist name for logging (eager loaded by repository)
                    artist_name = album.artist.name if album.artist else "Unknown Artist"
                    
                    # Sync tracks for this album
                    # Hey future me - album.spotify_id is the Spotify ID from the model!
                    result = await sync_service.sync_album_tracks(
                        album_id=album.spotify_id,
                        force=True,  # Skip cooldown since we're doing gradual sync
                    )

                    if result.get("synced"):
                        synced_count += 1
                        total_tracks += result.get("total", 0)
                        logger.info(
                            f"🎵 [{idx}/{len(pending_albums)}] {artist_name} - {album.title} "
                            f"({result.get('total', 0)} tracks)"
                        )
                    elif result.get("error"):
                        logger.warning(
                            f"⚠️ [{idx}/{len(pending_albums)}] {artist_name} - {album.title}: "
                            f"{result.get('error')}"
                        )

                    # Small delay between albums to be nice to the API
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(
                        f"❌ [{idx}/{len(pending_albums)}] {artist_name} - {album.title}: "
                        f"{type(e).__name__}: {e}"
                    )
                    # Continue with next album, don't fail the whole batch

            # Update tracking
            self._last_sync["album_tracks"] = now
            self._sync_stats["album_tracks"]["count"] += 1
            self._sync_stats["album_tracks"]["last_result"] = {
                "albums_synced": synced_count,
                "total_tracks": total_tracks,
            }
            self._sync_stats["album_tracks"]["last_error"] = None
            self._sync_stats["album_tracks"]["pending"] = pending_count - synced_count

            duration = time.time() - operation_start
            logger.info(
                "spotify_sync.album_tracks.completed",
                extra={
                    "duration_seconds": round(duration, 2),
                    "albums_synced": synced_count,
                    "total_tracks": total_tracks,
                    "pending_remaining": pending_count - synced_count,
                },
            )

        except Exception as e:
            duration = time.time() - operation_start
            self._sync_stats["album_tracks"]["last_error"] = str(e)
            logger.error(
                "spotify_sync.album_tracks.failed",
                exc_info=True,
                extra={
                    "duration_seconds": round(duration, 2),
                    "error_type": type(e).__name__,
                },
            )
            raise

    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get current worker status and stats.

        Returns dict with running state, last sync times, and sync stats.
        Useful for monitoring/debugging.
        """
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "last_sync": {
                sync_type: ts.isoformat() if ts else None
                for sync_type, ts in self._last_sync.items()
            },
            "stats": self._sync_stats,
        }

    async def force_sync(self, sync_type: str | None = None) -> dict[str, Any]:
        """Force an immediate sync (bypass cooldown).

        Args:
            sync_type: Specific sync to run, or None for all.

        Returns:
            Dict with sync results.

        Hey future me - this method uses db.session_scope() context manager just like
        _check_and_run_syncs(). The old code called self._get_db_session() which didn't
        exist, causing AttributeError. Now we properly use the context manager pattern
        to ensure connections are returned to the pool.
        """
        results: dict[str, Any] = {}

        # Hey future me - use session_scope context manager for proper connection cleanup!
        # This is the same pattern used in _check_and_run_syncs().
        async with self.db.session_scope() as session:
            try:
                # Get access token
                access_token = await self.token_manager.get_token_for_background()
                if not access_token:
                    return {"error": "No valid Spotify token available"}

                now = datetime.now(UTC)

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

                if sync_type is None or sync_type == "liked":
                    try:
                        await self._run_liked_songs_sync(session, access_token, now)
                        results["liked_songs"] = "success"
                    except Exception as e:
                        results["liked_songs"] = f"error: {e}"

                if sync_type is None or sync_type == "albums":
                    try:
                        await self._run_saved_albums_sync(session, access_token, now)
                        results["saved_albums"] = "success"
                    except Exception as e:
                        results["saved_albums"] = f"error: {e}"

                if sync_type is None or sync_type == "artist_albums":
                    try:
                        # Force sync a batch of pending artists
                        await self._run_artist_albums_sync(
                            session, access_token, now, artists_per_cycle=10
                        )
                        results["artist_albums"] = "success"
                    except Exception as e:
                        results["artist_albums"] = f"error: {e}"

                if sync_type is None or sync_type == "album_tracks":
                    try:
                        # Force sync a batch of pending albums (load tracks)
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
