"""Background worker for automatic New Releases synchronization.

Hey future me - dieser Worker synct New Releases automatisch im Hintergrund!

Das Problem: NewReleasesService macht bei jedem Request API-Calls zu Spotify/Deezer.
Das ist langsam und verbraucht API-Quota. Dieser Worker cached die Ergebnisse.

Der Worker läuft in einer Endlosschleife und:
1. Prüft alle X Minuten ob ein Sync fällig ist (default: 30 min)
2. Liest die Settings aus der DB (AppSettingsService)
3. Ruft NewReleasesService.get_all_new_releases() auf
4. Speichert die Ergebnisse in einem In-Memory Cache
5. UI Route liest aus dem Cache statt live API zu callen

Cache-Strategie:
- In-Memory Cache (kein Redis/DB needed)
- TTL: 30 Minuten (configurable via app_settings)
- Fallback: Bei Cache-Miss wird live gefetcht
- Invalidation: Bei Manual-Sync oder Settings-Change

Fehlerbehandlung:
- Wenn Sync fehlschlägt: Loggen, alter Cache bleibt gültig
- Kein Crash der Loop!
- Bei Token-Fehler: Nur Spotify skipped, Deezer läuft weiter
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from soulspot.application.services.new_releases_service import (
    NewReleasesResult,
    NewReleasesService,
)

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager
    from soulspot.config import Settings
    from soulspot.infrastructure.persistence import Database

logger = logging.getLogger(__name__)


@dataclass
class NewReleasesCache:
    """In-memory cache for new releases data.
    
    Hey future me - das ist der Cache für gecachte New Releases!
    Enthält die Daten + Metadata wann sie gecacht wurden.
    """
    
    result: NewReleasesResult | None = None
    """The cached result from NewReleasesService."""
    
    cached_at: datetime | None = None
    """When the cache was last updated."""
    
    ttl_minutes: int = 30
    """Time-to-live in minutes before cache is considered stale."""
    
    is_valid: bool = False
    """Whether cache contains valid data."""
    
    sync_errors: list[str] = field(default_factory=list)
    """Errors from the last sync attempt."""
    
    def is_fresh(self) -> bool:
        """Check if cache is still fresh (not expired).
        
        Returns:
            True if cache is valid and not expired
        """
        if not self.is_valid or not self.cached_at or not self.result:
            return False
        
        age = datetime.now(UTC) - self.cached_at
        return age < timedelta(minutes=self.ttl_minutes)
    
    def get_age_seconds(self) -> int | None:
        """Get cache age in seconds.
        
        Returns:
            Seconds since cache was updated, or None if not cached
        """
        if not self.cached_at:
            return None
        
        age = datetime.now(UTC) - self.cached_at
        return int(age.total_seconds())
    
    def update(self, result: NewReleasesResult) -> None:
        """Update cache with new result.
        
        Args:
            result: Fresh result from NewReleasesService
        """
        self.result = result
        self.cached_at = datetime.now(UTC)
        self.is_valid = True
        self.sync_errors = list(result.errors.values()) if result.errors else []
    
    def invalidate(self) -> None:
        """Mark cache as invalid (forces refresh on next access)."""
        self.is_valid = False


class NewReleasesSyncWorker:
    """Background worker that automatically syncs New Releases from all providers.
    
    Hey future me - dieser Worker ist ähnlich wie SpotifySyncWorker aufgebaut!
    
    Er läuft alle X Minuten (default: 30) und:
    1. Checkt ob auto_sync_new_releases enabled ist (app_settings)
    2. Erstellt NewReleasesService mit allen verfügbaren Plugins
    3. Holt New Releases von allen Providern
    4. Cached die Ergebnisse
    
    Usage:
        worker = NewReleasesSyncWorker(db=db, token_manager=tm, settings=settings)
        await worker.start()
        
        # Get cached data (used by UI route)
        cached = worker.get_cached_releases()
        if cached.is_fresh():
            return cached.result  # Fast!
        
        # Force refresh
        await worker.force_sync()
    
    Settings (app_settings table):
    - new_releases.auto_sync_enabled: bool (default True)
    - new_releases.sync_interval_minutes: int (default 30)
    - new_releases.lookback_days: int (default 90)
    - new_releases.include_singles: bool (default True)
    - new_releases.include_compilations: bool (default True)
    """
    
    def __init__(
        self,
        db: "Database",
        token_manager: "DatabaseTokenManager",
        settings: "Settings",
        check_interval_seconds: int = 60,  # Check every minute
    ) -> None:
        """Initialize New Releases sync worker.
        
        Args:
            db: Database instance for creating sessions
            token_manager: DatabaseTokenManager for getting Spotify access tokens
            settings: Application settings
            check_interval_seconds: How often to check if sync is due
        """
        self.db = db
        self.token_manager = token_manager
        self.settings = settings
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None
        
        # Cache for new releases
        self._cache = NewReleasesCache()
        
        # Track last sync time (in-memory, resets on restart)
        self._last_sync: datetime | None = None
        
        # Track seen album keys to detect truly NEW releases
        # Hey future me - this set stores normalized keys (artist::album) of albums
        # we've already seen. On first sync after restart, we populate it without
        # sending notifications. After that, new albums trigger notifications!
        self._seen_album_keys: set[str] = set()
        self._first_sync_done: bool = False
        
        # Stats for monitoring
        self._sync_stats: dict[str, Any] = {
            "sync_count": 0,
            "last_result": None,
            "last_error": None,
            "last_duration_seconds": None,
            "new_albums_detected": 0,  # NEW: Track how many new albums found
        }
    
    async def start(self) -> None:
        """Start the New Releases sync worker.
        
        Creates a background task that runs the sync loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("New Releases sync worker is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="New Releases Sync",
                interval=self.check_interval_seconds
            )
        )
    
    async def stop(self) -> None:
        """Stop the New Releases sync worker.
        
        Cancels the background task and waits for cleanup.
        Safe to call multiple times (idempotent).
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("New Releases sync worker stopped")
    
    def get_status(self) -> dict[str, Any]:
        """Get current worker status.
        
        Returns:
            Status dict with running state, cache info, stats, and notification tracking
        """
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "first_sync_done": self._first_sync_done,
            "tracked_albums_count": len(self._seen_album_keys),
            "cache": {
                "is_valid": self._cache.is_valid,
                "is_fresh": self._cache.is_fresh(),
                "age_seconds": self._cache.get_age_seconds(),
                "album_count": len(self._cache.result.albums) if self._cache.result else 0,
                "source_counts": self._cache.result.source_counts if self._cache.result else {},
                "errors": self._cache.sync_errors,
            },
            "stats": self._sync_stats,
        }
    
    def get_cached_releases(self) -> NewReleasesCache:
        """Get the cached releases.
        
        UI route should call this instead of making fresh API calls.
        Check is_fresh() to see if cache is still valid.
        
        Returns:
            NewReleasesCache with result (may be stale or empty)
        """
        return self._cache
    
    async def force_sync(self) -> NewReleasesResult | None:
        """Force an immediate sync, bypassing cooldown.
        
        Use this for "Refresh" button in UI.
        
        Returns:
            Fresh NewReleasesResult, or None if sync failed
        """
        logger.info("Force sync requested for New Releases")
        return await self._do_sync(force=True)
    
    def invalidate_cache(self) -> None:
        """Invalidate the cache (forces refresh on next access).
        
        Use this when settings change that affect new releases.
        """
        self._cache.invalidate()
        logger.info("New Releases cache invalidated")
    
    async def _run_loop(self) -> None:
        """Main worker loop - checks and runs syncs periodically.
        
        Hey future me - diese Loop läuft EWIG bis stop() aufgerufen wird!
        Auf jedem Durchlauf:
        1. Hole Settings aus DB (ob Sync enabled, Intervall)
        2. Prüfe ob ein Sync fällig ist (Cooldown abgelaufen)
        3. Führe Sync aus wenn fällig
        4. Schlafe für check_interval_seconds
        5. Wiederhole
        
        Fehler crashen die Loop NICHT - nur loggen und weitermachen.
        """
        # Wait a bit on startup to let other services initialize
        # Token refresh worker should have time to refresh if needed
        await asyncio.sleep(45)
        
        logger.info("New Releases sync worker entering main loop")
        
        while self._running:
            try:
                await self._check_and_run_sync()
            except Exception as e:
                # Don't crash the worker - log and continue
                logger.exception(f"Error in New Releases sync loop: {e}")
                self._sync_stats["last_error"] = str(e)
            
            await asyncio.sleep(self.check_interval_seconds)
        
        logger.info("New Releases sync worker exited main loop")
    
    async def _check_and_run_sync(self) -> None:
        """Check if sync is due and run it if enabled.
        
        Hey future me - diese Methode prüft Settings und führt Sync aus.
        """
        async with self.db.session_scope() as session:
            try:
                from soulspot.application.services.app_settings_service import (
                    AppSettingsService,
                )
                
                settings_service = AppSettingsService(session)
                
                # Check if auto-sync is enabled
                auto_sync_enabled = await settings_service.get_bool(
                    "new_releases.auto_sync_enabled", default=True
                )
                
                if not auto_sync_enabled:
                    logger.debug("New Releases auto-sync is disabled, skipping")
                    return
                
                # Get sync interval
                sync_interval = await settings_service.get_int(
                    "new_releases.sync_interval_minutes", default=30
                )
                
                # Update cache TTL to match sync interval
                self._cache.ttl_minutes = sync_interval
                
                # Check if sync is due
                if self._is_sync_due(sync_interval):
                    await self._do_sync()
            
            except Exception as e:
                logger.error(f"Error checking New Releases sync: {e}", exc_info=True)
    
    def _is_sync_due(self, interval_minutes: int) -> bool:
        """Check if sync is due based on cooldown interval.
        
        Args:
            interval_minutes: Cooldown in minutes
        
        Returns:
            True if sync should run
        """
        if self._last_sync is None:
            # Never synced - do it now
            return True
        
        cooldown = timedelta(minutes=interval_minutes)
        return (datetime.now(UTC) - self._last_sync) >= cooldown
    
    async def _do_sync(self, force: bool = False) -> NewReleasesResult | None:
        """Execute the actual sync.
        
        Hey future me - das ist die eigentliche Sync-Logik!
        1. Holt Settings aus DB
        2. Erstellt Plugins mit Token
        3. Ruft NewReleasesService auf
        4. Updated Cache
        
        Args:
            force: If True, bypass cooldown check
        
        Returns:
            NewReleasesResult or None on failure
        """
        start_time = datetime.now(UTC)
        logger.info("Starting New Releases sync...")
        
        try:
            async with self.db.session_scope() as session:
                from soulspot.application.services.app_settings_service import (
                    AppSettingsService,
                )
                from soulspot.infrastructure.integrations.deezer_client import (
                    DeezerClient,
                )
                from soulspot.infrastructure.integrations.spotify_client import (
                    SpotifyClient,
                )
                from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
                from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
                
                settings_service = AppSettingsService(session)
                
                # Get sync settings
                lookback_days = await settings_service.get_int(
                    "new_releases.lookback_days", default=90
                )
                include_singles = await settings_service.get_bool(
                    "new_releases.include_singles", default=True
                )
                include_compilations = await settings_service.get_bool(
                    "new_releases.include_compilations", default=True
                )
                
                # Create plugins
                spotify_plugin: SpotifyPlugin | None = None
                deezer_plugin: DeezerPlugin | None = None
                
                # Check if Spotify is enabled and authenticated
                spotify_enabled = await settings_service.is_provider_enabled("spotify")
                if spotify_enabled:
                    access_token = await self.token_manager.get_token_for_background()
                    if access_token:
                        spotify_client = SpotifyClient(self.settings.spotify)
                        spotify_plugin = SpotifyPlugin(
                            client=spotify_client,
                            access_token=access_token
                        )
                        logger.debug("Spotify plugin ready for New Releases sync")
                    else:
                        logger.debug("Spotify token not available, skipping Spotify")
                
                # Check if Deezer is enabled (Deezer doesn't need auth for browse)
                deezer_enabled = await settings_service.is_provider_enabled("deezer")
                if deezer_enabled:
                    deezer_client = DeezerClient()
                    deezer_plugin = DeezerPlugin(client=deezer_client)
                    logger.debug("Deezer plugin ready for New Releases sync")
                
                # Create service and fetch releases
                service = NewReleasesService(
                    spotify_plugin=spotify_plugin,
                    deezer_plugin=deezer_plugin,
                )
                
                enabled_providers: list[str] = []
                if spotify_plugin:
                    enabled_providers.append("spotify")
                if deezer_plugin:
                    enabled_providers.append("deezer")
                
                result = await service.get_all_new_releases(
                    days=lookback_days,
                    include_singles=include_singles,
                    include_compilations=include_compilations,
                    enabled_providers=enabled_providers,
                )
                
                # Update cache
                self._cache.update(result)
                self._last_sync = datetime.now(UTC)
                
                # =========================================================
                # DETECT NEW ALBUMS AND SEND NOTIFICATION
                # =========================================================
                # Hey future me - this is where the magic happens!
                # On first sync, we just populate _seen_album_keys.
                # On subsequent syncs, we compare and notify about truly new albums.
                new_albums = await self._detect_and_notify_new_albums(
                    result, session, settings_service
                )
                
                # Update stats
                duration = (datetime.now(UTC) - start_time).total_seconds()
                self._sync_stats["sync_count"] += 1
                self._sync_stats["last_result"] = {
                    "album_count": len(result.albums),
                    "source_counts": result.source_counts,
                    "total_before_dedup": result.total_before_dedup,
                    "errors": result.errors,
                    "new_albums_detected": len(new_albums),
                }
                self._sync_stats["last_error"] = None
                self._sync_stats["last_duration_seconds"] = duration
                self._sync_stats["new_albums_detected"] = len(new_albums)
                
                logger.info(
                    f"New Releases sync completed: {len(result.albums)} albums "
                    f"({len(new_albums)} new) from {result.source_counts} in {duration:.1f}s"
                )
                
                return result
        
        except Exception as e:
            logger.exception(f"New Releases sync failed: {e}")
            self._sync_stats["last_error"] = str(e)
            self._sync_stats["last_duration_seconds"] = (
                datetime.now(UTC) - start_time
            ).total_seconds()
            return None
    
    async def _detect_and_notify_new_albums(
        self,
        result: NewReleasesResult,
        session: Any,
        settings_service: Any,
    ) -> list[dict[str, str]]:
        """Detect truly new albums and send notification if enabled.
        
        Hey future me - das ist die Notification-Logik!
        
        1. Auf erstem Sync: Populate _seen_album_keys ohne Notification
        2. Auf folgenden Syncs: Vergleiche und notifiziere über neue Albums
        3. Respektiere app_settings für enable/disable
        
        Args:
            result: NewReleasesResult from service
            session: DB session for notification service
            settings_service: AppSettingsService instance
        
        Returns:
            List of new album dicts (artist_name, album_name, release_date)
        """
        new_albums: list[dict[str, str]] = []
        current_keys: set[str] = set()
        
        # Build current album keys and detect new ones
        for album in result.albums:
            key = self._normalize_album_key(album.artist_name, album.title)
            current_keys.add(key)
            
            # Check if this is a new album (not seen before)
            if key not in self._seen_album_keys:
                new_albums.append({
                    "artist_name": album.artist_name,
                    "album_name": album.title,
                    "release_date": album.release_date or "",
                    "source": album.source_service,
                })
        
        # Update seen keys with current set
        self._seen_album_keys = current_keys
        
        # On first sync, don't send notifications (just learned the baseline)
        if not self._first_sync_done:
            self._first_sync_done = True
            logger.info(
                f"First New Releases sync - learned {len(current_keys)} albums "
                "(no notification)"
            )
            return []
        
        # No new albums = no notification
        if not new_albums:
            logger.debug("No new albums detected since last sync")
            return []
        
        # Check if notifications are enabled
        notifications_enabled = await settings_service.get_bool(
            "new_releases.notifications_enabled", default=True
        )
        
        if not notifications_enabled:
            logger.debug(
                f"Detected {len(new_albums)} new albums but notifications disabled"
            )
            return new_albums
        
        # Send notification!
        try:
            from soulspot.application.services.notification_service import (
                NotificationService,
            )
            
            notification_service = NotificationService(session)
            
            # Calculate source counts for new albums only
            new_source_counts: dict[str, int] = {}
            for album in new_albums:
                source = album.get("source", "unknown")
                new_source_counts[source] = new_source_counts.get(source, 0) + 1
            
            await notification_service.send_new_releases_detected_notification(
                new_albums=new_albums,
                total_count=len(new_albums),
                source_counts=new_source_counts,
            )
            
            logger.info(
                f"Sent notification for {len(new_albums)} new albums: "
                f"{new_source_counts}"
            )
        except Exception as e:
            logger.warning(f"Failed to send new releases notification: {e}")
        
        return new_albums
    
    @staticmethod
    def _normalize_album_key(artist: str, album: str) -> str:
        """Create normalized key for album tracking.
        
        Hey future me - gleiche Normalisierung wie in NewReleasesService!
        Damit matchen die Keys korrekt.
        """
        artist_norm = artist.lower().strip()
        album_norm = album.lower().strip()
        
        # Remove common suffixes
        for suffix in [
            "(deluxe)", "(deluxe edition)", "(expanded edition)",
            "(remastered)", "(remaster)", "- single", "(single)",
            "(ep)", "- ep"
        ]:
            album_norm = album_norm.replace(suffix, "").strip()
        
        return f"{artist_norm}::{album_norm}"


# Export
__all__ = ["NewReleasesSyncWorker", "NewReleasesCache"]
