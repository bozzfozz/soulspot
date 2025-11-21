"""Watchlist service for monitoring artists for new releases."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
from soulspot.domain.value_objects import ArtistId, WatchlistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import ArtistWatchlistRepository

logger = logging.getLogger(__name__)


class WatchlistService:
    """Service for managing artist watchlists."""

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient | None = None,
    ) -> None:
        """Initialize watchlist service.

        Args:
            session: Database session
            spotify_client: Spotify client for fetching releases
        """
        self.repository = ArtistWatchlistRepository(session)
        self.spotify_client = spotify_client

    # Hey future me: Watchlist service - monitors artists for new releases
    # WHY watchlist? User wants to auto-download new albums from favorite artists
    # Example: Watch "Tool" - when new album drops, automatically trigger download workflow
    # GOTCHA: Needs Spotify access token - these expire! Must refresh tokens or workflows fail
    async def create_watchlist(
        self,
        artist_id: ArtistId,
        check_frequency_hours: int = 24,
        auto_download: bool = True,
        quality_profile: str = "high",
    ) -> ArtistWatchlist:
        """Create a new artist watchlist.

        Args:
            artist_id: Artist ID to watch
            check_frequency_hours: How often to check for new releases
            auto_download: Whether to automatically download new releases
            quality_profile: Quality preference (low, medium, high, lossless)

        Returns:
            Created watchlist
        """
        watchlist = ArtistWatchlist(
            id=WatchlistId.generate(),
            artist_id=artist_id,
            status=WatchlistStatus.ACTIVE,
            check_frequency_hours=check_frequency_hours,
            auto_download=auto_download,
            quality_profile=quality_profile,
            last_checked_at=None,
            last_release_date=None,
            total_releases_found=0,
            total_downloads_triggered=0,
        )
        await self.repository.add(watchlist)
        logger.info(f"Created watchlist for artist {artist_id}")
        return watchlist

    # Yo simple getters - repository delegation methods
    # These are thin wrappers around repository - service layer orchestration
    async def get_watchlist(self, watchlist_id: WatchlistId) -> ArtistWatchlist | None:
        """Get watchlist by ID."""
        result: ArtistWatchlist | None = await self.repository.get_by_id(watchlist_id)
        return result

    async def get_by_artist(self, artist_id: ArtistId) -> ArtistWatchlist | None:
        """Get watchlist for an artist."""
        result: ArtistWatchlist | None = await self.repository.get_by_artist_id(
            artist_id
        )
        return result

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[ArtistWatchlist]:
        """List all watchlists."""
        return await self.repository.list_all(limit, offset)

    async def list_active(
        self, limit: int = 100, offset: int = 0
    ) -> list[ArtistWatchlist]:
        """List active watchlists."""
        return await self.repository.list_active(limit, offset)

    async def list_due_for_check(self, limit: int = 100) -> list[ArtistWatchlist]:
        """List watchlists that need checking."""
        return await self.repository.list_due_for_check(limit)

    # Hey, pause/resume/delete controls - domain entity methods + persist
    # WHY entity methods? Business logic (state transitions, validations) in entity
    # Service just orchestrates: fetch, call entity method, save
    async def pause_watchlist(self, watchlist_id: WatchlistId) -> None:
        """Pause a watchlist."""
        watchlist = await self.repository.get_by_id(watchlist_id)
        if watchlist:
            watchlist.pause()
            await self.repository.update(watchlist)
            logger.info(f"Paused watchlist {watchlist_id}")

    async def resume_watchlist(self, watchlist_id: WatchlistId) -> None:
        """Resume a watchlist."""
        watchlist = await self.repository.get_by_id(watchlist_id)
        if watchlist:
            watchlist.resume()
            await self.repository.update(watchlist)
            logger.info(f"Resumed watchlist {watchlist_id}")

    async def delete_watchlist(self, watchlist_id: WatchlistId) -> None:
        """Delete a watchlist."""
        await self.repository.delete(watchlist_id)
        logger.info(f"Deleted watchlist {watchlist_id}")

    # Hey future me: New release checking - compares Spotify albums against last known release date
    # WHY store last_release_date? Avoids re-downloading same album on every check
    # WHY parse release_date? Spotify returns YYYY-MM-DD or just YYYY - need to handle both
    # GOTCHA: Spotify returns albums in reverse chronological order - newest first
    # If band releases 3 albums while we were down, we'll get all 3 as "new"
    async def check_for_new_releases(
        self, watchlist: ArtistWatchlist, access_token: str
    ) -> list[dict[str, Any]]:
        """Check for new releases for an artist.

        Args:
            watchlist: Artist watchlist
            access_token: Spotify access token

        Returns:
            List of new releases found
        """
        if not self.spotify_client:
            logger.warning("Spotify client not available for release checking")
            return []

        try:
            # Get artist's albums from Spotify
            artist_spotify_id = str(watchlist.artist_id.value)
            albums = await self.spotify_client.get_artist_albums(
                artist_spotify_id, access_token
            )

            # Filter for new releases since last check
            new_releases = []
            for album in albums:
                release_date_str = album.get("release_date", "")
                if not release_date_str:
                    continue

                try:
                    # Parse release date (format: YYYY-MM-DD or YYYY)
                    if len(release_date_str) == 4:  # Year only
                        release_date_str += "-01-01"
                    release_date = datetime.fromisoformat(release_date_str).replace(
                        tzinfo=UTC
                    )

                    # Check if this is a new release
                    if (
                        watchlist.last_release_date is None
                        or release_date > watchlist.last_release_date
                    ):
                        new_releases.append(album)
                        if (
                            watchlist.last_release_date is None
                            or release_date > watchlist.last_release_date
                        ):
                            watchlist.last_release_date = release_date

                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Failed to parse release date '{release_date_str}': {e}"
                    )
                    continue

            # Update watchlist statistics
            watchlist.update_check(
                releases_found=len(new_releases),
                downloads_triggered=len(new_releases) if watchlist.auto_download else 0,
            )
            await self.repository.update(watchlist)

            logger.info(
                f"Found {len(new_releases)} new releases for watchlist {watchlist.id}"
            )
            return new_releases

        except Exception as e:
            logger.error(f"Failed to check for new releases: {e}")
            return []
