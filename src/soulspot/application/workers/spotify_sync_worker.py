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
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager
    from soulspot.config import Settings
    from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


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
    ) -> None:
        """Initialize Spotify sync worker.

        Args:
            db: Database instance for creating sessions
            token_manager: DatabaseTokenManager for getting access tokens
            settings: Application settings (for SpotifyImageService)
            check_interval_seconds: How often to check if syncs are due
        """
        self.db = db
        self.token_manager = token_manager
        self.settings = settings
        self.check_interval_seconds = check_interval_seconds
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
        }

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
        }

    async def start(self) -> None:
        """Start the Spotify sync worker.

        Creates a background task that runs the sync loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("Spotify sync worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Spotify sync worker started (checking every {self.check_interval_seconds}s)"
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
        logger.info("Spotify sync worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop - checks and runs syncs periodically.

        Hey future me - diese Loop läuft EWIG bis stop() aufgerufen wird!
        Auf jedem Durchlauf:
        1. Hole Settings aus DB (welche Syncs enabled, Intervalle)
        2. Prüfe ob ein Sync fällig ist (Cooldown abgelaufen)
        3. Führe fällige Syncs aus
        4. Schlafe für check_interval_seconds
        5. Wiederhole

        Fehler crashen die Loop NICHT - nur loggen und weitermachen.
        """
        # Wait a bit on startup to let other services initialize
        # Especially the token refresh worker should have time to refresh if needed
        await asyncio.sleep(30)

        logger.info("Spotify sync worker entering main loop")

        while self._running:
            try:
                await self._check_and_run_syncs()
            except Exception as e:
                # Don't crash the loop on errors - log and continue
                logger.error(f"Error in Spotify sync worker loop: {e}", exc_info=True)

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                # Worker is being stopped
                break

    async def _check_and_run_syncs(self) -> None:
        """Check settings and run any due syncs.

        Hey future me - diese Methode wird alle check_interval_seconds aufgerufen.
        Sie holt die aktuellen Settings aus der DB (damit Runtime-Änderungen wirken)
        und führt alle fälligen Syncs aus.

        UPDATE (Nov 2025): Now uses session_scope context manager instead of
        async generator to fix "GC cleaning up non-checked-in connection" errors.
        """
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
                    logger.debug("Spotify auto-sync is disabled, skipping")
                    return

                # Get access token - if not available, skip this cycle
                access_token = await self.token_manager.get_token_for_background()
                if not access_token:
                    logger.warning(
                        "No valid Spotify token available, skipping sync cycle"
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
                now = datetime.utcnow()

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

                # Commit any changes
                await session.commit()

            except Exception as e:
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

        Hey future me - diese Methode instantiiert den SpotifySyncService
        mit allen nötigen Dependencies und führt den Sync aus.
        """
        logger.info("Starting automatic artists sync...")

        try:
            # Import and instantiate services
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.services.spotify_image_service import (
                SpotifyImageService,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )

            spotify_client = SpotifyClient(self.settings.spotify)
            image_service = SpotifyImageService(self.settings)
            settings_service = AppSettingsService(session)

            sync_service = SpotifySyncService(
                spotify_client=spotify_client,
                session=session,
                image_service=image_service,
                settings_service=settings_service,
            )

            result = await sync_service.sync_followed_artists(access_token, force=False)

            # Update tracking
            self._last_sync["artists"] = now
            self._sync_stats["artists"]["count"] += 1
            self._sync_stats["artists"]["last_result"] = result
            self._sync_stats["artists"]["last_error"] = None

            synced = result.get("synced", 0) if result else 0
            removed = result.get("removed", 0) if result else 0
            logger.info(f"Artists sync complete: {synced} synced, {removed} removed")

        except Exception as e:
            self._sync_stats["artists"]["last_error"] = str(e)
            logger.error(f"Artists sync failed: {e}", exc_info=True)
            raise

    async def _run_playlists_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run playlists sync and update tracking."""
        logger.info("Starting automatic playlists sync...")

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.services.spotify_image_service import (
                SpotifyImageService,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )

            spotify_client = SpotifyClient(self.settings.spotify)
            image_service = SpotifyImageService(self.settings)
            settings_service = AppSettingsService(session)

            sync_service = SpotifySyncService(
                spotify_client=spotify_client,
                session=session,
                image_service=image_service,
                settings_service=settings_service,
            )

            result = await sync_service.sync_user_playlists(access_token, force=False)

            self._last_sync["playlists"] = now
            self._sync_stats["playlists"]["count"] += 1
            self._sync_stats["playlists"]["last_result"] = result
            self._sync_stats["playlists"]["last_error"] = None

            synced = result.get("synced", 0) if result else 0
            removed = result.get("removed", 0) if result else 0
            logger.info(f"Playlists sync complete: {synced} synced, {removed} removed")

        except Exception as e:
            self._sync_stats["playlists"]["last_error"] = str(e)
            logger.error(f"Playlists sync failed: {e}", exc_info=True)
            raise

    async def _run_liked_songs_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run liked songs sync and update tracking."""
        logger.info("Starting automatic liked songs sync...")

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.services.spotify_image_service import (
                SpotifyImageService,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )

            spotify_client = SpotifyClient(self.settings.spotify)
            image_service = SpotifyImageService(self.settings)
            settings_service = AppSettingsService(session)

            sync_service = SpotifySyncService(
                spotify_client=spotify_client,
                session=session,
                image_service=image_service,
                settings_service=settings_service,
            )

            result = await sync_service.sync_liked_songs(access_token, force=False)

            self._last_sync["liked_songs"] = now
            self._sync_stats["liked_songs"]["count"] += 1
            self._sync_stats["liked_songs"]["last_result"] = result
            self._sync_stats["liked_songs"]["last_error"] = None

            track_count = result.get("track_count", 0) if result else 0
            logger.info(f"Liked songs sync complete: {track_count} tracks")

        except Exception as e:
            self._sync_stats["liked_songs"]["last_error"] = str(e)
            logger.error(f"Liked songs sync failed: {e}", exc_info=True)
            raise

    async def _run_saved_albums_sync(
        self, session: Any, access_token: str, now: datetime
    ) -> None:
        """Run saved albums sync and update tracking."""
        logger.info("Starting automatic saved albums sync...")

        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.services.spotify_image_service import (
                SpotifyImageService,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
            )

            spotify_client = SpotifyClient(self.settings.spotify)
            image_service = SpotifyImageService(self.settings)
            settings_service = AppSettingsService(session)

            sync_service = SpotifySyncService(
                spotify_client=spotify_client,
                session=session,
                image_service=image_service,
                settings_service=settings_service,
            )

            result = await sync_service.sync_saved_albums(access_token, force=False)

            self._last_sync["saved_albums"] = now
            self._sync_stats["saved_albums"]["count"] += 1
            self._sync_stats["saved_albums"]["last_result"] = result
            self._sync_stats["saved_albums"]["last_error"] = None

            synced = result.get("synced", 0) if result else 0
            logger.info(f"Saved albums sync complete: {synced} synced")

        except Exception as e:
            self._sync_stats["saved_albums"]["last_error"] = str(e)
            logger.error(f"Saved albums sync failed: {e}", exc_info=True)
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
        try:
            from soulspot.application.services.app_settings_service import (
                AppSettingsService,
            )
            from soulspot.application.services.spotify_image_service import (
                SpotifyImageService,
            )
            from soulspot.application.services.spotify_sync_service import (
                SpotifySyncService,
            )
            from soulspot.infrastructure.integrations.spotify_client import (
                SpotifyClient,
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
            pending_artists = await repo.get_artists_pending_album_sync(
                limit=artists_per_cycle
            )
            pending_count = await repo.count_artists_pending_album_sync()
            artists_to_sync.extend(pending_artists)

            # Phase 2: If resync enabled and we have room, add artists needing resync
            resync_count = 0
            if resync_enabled and len(artists_to_sync) < artists_per_cycle:
                remaining_slots = artists_per_cycle - len(artists_to_sync)
                resync_artists = await repo.get_artists_due_for_resync(
                    max_age_hours=resync_hours,
                    limit=remaining_slots,
                )
                resync_count = await repo.count_artists_due_for_resync(
                    max_age_hours=resync_hours
                )
                artists_to_sync.extend(resync_artists)

            if not artists_to_sync:
                # All artists have been synced and none need resync
                logger.debug("No artists pending album sync or needing resync")
                self._sync_stats["artist_albums"]["pending"] = 0
                self._sync_stats["artist_albums"]["resync_pending"] = 0
                return

            # Log what we're doing
            new_count = len(pending_artists)
            resync_this_cycle = len(artists_to_sync) - new_count
            logger.info(
                f"Starting gradual artist albums sync: "
                f"{new_count} new + {resync_this_cycle} resync = {len(artists_to_sync)} artists "
                f"this cycle. Pending: {pending_count} new, {resync_count} resync"
            )

            # Set up services
            spotify_client = SpotifyClient(self.settings.spotify)
            image_service = SpotifyImageService(self.settings)
            settings_service = AppSettingsService(session)

            sync_service = SpotifySyncService(
                spotify_client=spotify_client,
                session=session,
                image_service=image_service,
                settings_service=settings_service,
            )

            synced_count = 0
            total_albums = 0

            for artist in artists_to_sync:
                try:
                    # Sync albums for this artist
                    result = await sync_service.sync_artist_albums(
                        access_token=access_token,
                        artist_id=artist.spotify_id,
                        force=True,  # Skip cooldown since we're doing gradual sync
                    )

                    if result.get("synced"):
                        synced_count += 1
                        total_albums += result.get("total", 0)
                        logger.debug(
                            f"Synced {result.get('total', 0)} albums for {artist.name}"
                        )

                    # Small delay between artists to be nice to the API
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(
                        f"Failed to sync albums for artist {artist.name}: {e}"
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

            logger.info(
                f"Gradual artist albums sync complete: {synced_count} artists, "
                f"{total_albums} albums. Still pending: {pending_count} new, {resync_count} resync"
            )

        except Exception as e:
            self._sync_stats["artist_albums"]["last_error"] = str(e)
            logger.error(f"Artist albums sync failed: {e}", exc_info=True)
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

                now = datetime.utcnow()

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

                await session.commit()

            except Exception as e:
                await session.rollback()
                results["error"] = str(e)

        return results
