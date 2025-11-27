# Hey future me - this worker proactively refreshes Spotify OAuth tokens!
# The key insight: Spotify access tokens expire after 1 hour. If we wait until
# a background worker (WatchlistWorker, etc.) needs the token and it's expired,
# the API call fails. Instead, we refresh tokens BEFORE they expire!
#
# This worker runs every 5 minutes (configurable) and checks if the token expires
# within 10 minutes. If so, it refreshes proactively. This means background workers
# always have a fresh token available.
#
# If refresh fails (user revoked access, network error), we mark the token as invalid
# which triggers the UI warning banner ("Spotify-Verbindung abgelaufen - Bitte anmelden").
# Background workers check for valid token and skip work gracefully (no crash loop).
"""Background worker for proactive Spotify token refresh."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

logger = logging.getLogger(__name__)


class TokenRefreshWorker:
    """Background worker that proactively refreshes Spotify OAuth tokens.

    Runs every `check_interval_seconds` (default 5 min) and refreshes tokens
    that expire within `refresh_threshold_minutes` (default 10 min).

    This ensures background workers (WatchlistWorker, DiscographyWorker, etc.)
    always have valid tokens available without needing to handle refresh logic.

    On refresh failure:
    - HTTP 401/403: Token marked invalid → UI shows warning banner
    - Network error: Logged, retry on next cycle (might be temporary)
    - Other errors: Token marked invalid → UI shows warning banner
    """

    def __init__(
        self,
        token_manager: "DatabaseTokenManager",
        check_interval_seconds: int = 300,  # 5 minutes
        refresh_threshold_minutes: int = 10,  # Refresh if expires within 10 min
    ) -> None:
        """Initialize token refresh worker.

        Args:
            token_manager: DatabaseTokenManager for token operations
            check_interval_seconds: How often to check for expiring tokens
            refresh_threshold_minutes: Refresh tokens expiring within this window
        """
        self.token_manager = token_manager
        self.check_interval_seconds = check_interval_seconds
        self.refresh_threshold_minutes = refresh_threshold_minutes
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the token refresh worker.

        Creates a background task that runs the refresh loop.
        Safe to call multiple times (idempotent).
        """
        if self._running:
            logger.warning("Token refresh worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Token refresh worker started (check every {self.check_interval_seconds}s, "
            f"refresh threshold {self.refresh_threshold_minutes} min)"
        )

    async def stop(self) -> None:
        """Stop the token refresh worker.

        Cancels the background task and waits for cleanup.
        Safe to call multiple times (idempotent).
        """
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Token refresh worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop - checks and refreshes tokens periodically.

        Hey future me - this loop runs FOREVER until stop() is called!
        On each iteration:
        1. Call token_manager.refresh_expiring_tokens()
        2. Sleep for check_interval_seconds
        3. Repeat

        Errors in refresh don't crash the loop - just log and continue.
        The loop only exits when self._running becomes False.
        """
        # Yo - wait a bit on startup to let other services initialize
        await asyncio.sleep(10)

        while self._running:
            try:
                # Check and refresh expiring tokens
                refreshed = await self.token_manager.refresh_expiring_tokens(
                    threshold_minutes=self.refresh_threshold_minutes
                )

                if refreshed:
                    logger.info("Token refreshed successfully by background worker")
                else:
                    logger.debug("No tokens needed refresh")

            except Exception as e:
                # Don't crash the loop on errors - log and continue
                logger.error(f"Error in token refresh worker: {e}", exc_info=True)

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                # Worker is being stopped
                break

    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._running

    async def force_refresh(self) -> bool:
        """Force an immediate token refresh (bypass threshold check).

        Useful for testing or when user explicitly requests refresh.

        Returns:
            True if refresh was performed, False otherwise
        """
        try:
            # Use a very large threshold to always trigger refresh
            return await self.token_manager.refresh_expiring_tokens(
                threshold_minutes=999999
            )
        except Exception as e:
            logger.error(f"Force refresh failed: {e}", exc_info=True)
            return False
