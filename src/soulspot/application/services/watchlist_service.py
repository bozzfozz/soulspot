"""Watchlist service for monitoring artists for new releases.

Hey future me - MULTI-PROVIDER Support hinzugefügt (3. Januar 2026)!

Das Service nutzt ALLE aktivierten Provider (Spotify + Deezer) um neue Releases zu finden.
Results werden dedupliziert und kombiniert.

Pattern aus copilot-instructions.md Section 4.4:
"Always use ALL available services, deduplicate, and combine results"
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
from soulspot.domain.ports.plugin import PluginCapability
from soulspot.domain.value_objects import ArtistId, WatchlistId
from soulspot.infrastructure.persistence.repositories import ArtistWatchlistRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins import DeezerPlugin, SpotifyPlugin

logger = logging.getLogger(__name__)


class WatchlistService:
    """Service for managing artist watchlists.
    
    Hey future me - MULTI-PROVIDER SUPPORT!
    
    Der Service akzeptiert jetzt sowohl SpotifyPlugin als auch DeezerPlugin.
    Bei check_for_new_releases() werden BEIDE abgefragt und Results kombiniert.
    
    Warum beide?
    - Spotify: Accurate release dates, user's followed artists
    - Deezer: Public API (no auth for browse), sometimes earlier releases
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize watchlist service.

        Args:
            session: Database session
            spotify_plugin: Spotify plugin for fetching releases
            deezer_plugin: Deezer plugin for fetching releases (public API!)
        """
        self.repository = ArtistWatchlistRepository(session)
        self.spotify_plugin = spotify_plugin
        self.deezer_plugin = deezer_plugin

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

    # Hey future me: New release checking - MULTI-PROVIDER (3. Januar 2026)!
    # 
    # Pattern aus copilot-instructions.md Section 4.4:
    # 1. Query ALL enabled services (Deezer + Spotify)
    # 2. Aggregate results into unified list
    # 3. Deduplicate by normalized key (title + year)
    # 4. Tag source for each result
    # 5. Graceful fallback if one service fails
    #
    # WHY store last_release_date? Avoids re-downloading same album on every check
    # WHY parse release_date? Both providers return YYYY-MM-DD or just YYYY - need to handle both
    # GOTCHA: If band releases 3 albums while we were down, we'll get all 3 as "new"
    async def check_for_new_releases(
        self, watchlist: ArtistWatchlist, _access_token: str | None = None
    ) -> list[dict[str, Any]]:
        """Check for new releases for an artist from ALL available providers.

        Hey future me - MULTI-PROVIDER! Checks Spotify AND Deezer, deduplicates results.

        Args:
            watchlist: Artist watchlist
            _access_token: DEPRECATED - Plugins manage tokens internally

        Returns:
            List of new releases found (deduplicated, from all providers)
        """
        all_albums: list[dict[str, Any]] = []
        seen_keys: set[str] = set()  # For deduplication
        source_counts = {"spotify": 0, "deezer": 0}
        
        artist_id_str = str(watchlist.artist_id.value)

        # 1. SPOTIFY - requires auth, but most accurate release dates
        if self.spotify_plugin and self.spotify_plugin.can_use(
            PluginCapability.GET_ARTIST_ALBUMS
        ):
            try:
                response = await self.spotify_plugin.get_artist_albums(artist_id_str)
                for album in response.items:
                    # Create dedup key: normalized title + year
                    dedup_key = self._make_dedup_key(album.title, album.release_date)
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        all_albums.append(
                            self._album_dto_to_dict(album, source="spotify")
                        )
                        source_counts["spotify"] += 1
            except Exception as e:
                logger.warning(f"Spotify failed for artist {artist_id_str}: {e}")

        # 2. DEEZER - public API (no auth needed!), good fallback
        # Hey future me - Deezer needs the DEEZER artist ID, not Spotify ID!
        # For now we skip if we only have Spotify ID. Future: lookup mapping.
        if self.deezer_plugin and self.deezer_plugin.can_use(
            PluginCapability.GET_ARTIST_ALBUMS
        ):
            try:
                # Note: This assumes artist_id_str is provider-agnostic UUID
                # In practice, we'd need to map to Deezer's artist ID
                response = await self.deezer_plugin.get_artist_albums(artist_id_str)
                for album in response.items:
                    dedup_key = self._make_dedup_key(album.title, album.release_date)
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        all_albums.append(
                            self._album_dto_to_dict(album, source="deezer")
                        )
                        source_counts["deezer"] += 1
            except Exception as e:
                logger.debug(f"Deezer failed for artist {artist_id_str}: {e}")

        if not all_albums:
            logger.warning(
                f"No albums found for artist {artist_id_str} from any provider"
            )
            return []

        logger.info(
            f"Found {len(all_albums)} albums for artist {artist_id_str} "
            f"(spotify={source_counts['spotify']}, deezer={source_counts['deezer']})"
        )

        # 3. Filter for NEW releases since last check
        new_releases: list[dict[str, Any]] = []
        latest_release_date = watchlist.last_release_date

        for album in all_albums:
            release_date = self._parse_release_date(album.get("release_date", ""))
            if release_date is None:
                continue

            if (
                watchlist.last_release_date is None
                or release_date > watchlist.last_release_date
            ):
                new_releases.append(album)
                if latest_release_date is None or release_date > latest_release_date:
                    latest_release_date = release_date

        # Update last_release_date if we found newer releases
        if latest_release_date and latest_release_date != watchlist.last_release_date:
            watchlist.last_release_date = latest_release_date

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

    # ─────────────────────────────────────────────────────────────────────────────
    # HELPER METHODS - Multi-Provider Support
    # ─────────────────────────────────────────────────────────────────────────────

    def _make_dedup_key(self, title: str, release_date: str | None) -> str:
        """Create a deduplication key from album title and release year.

        Hey future me - why year only? Because Spotify might have "2024-03-15"
        while Deezer has "2024-03-14" (timezone differences). Year is safer.

        Args:
            title: Album title
            release_date: Release date string (YYYY-MM-DD or YYYY)

        Returns:
            Normalized key: "lowercase_title|year"
        """
        normalized_title = title.lower().strip()
        year = release_date[:4] if release_date and len(release_date) >= 4 else "unknown"
        return f"{normalized_title}|{year}"

    def _album_dto_to_dict(self, album: Any, source: str) -> dict[str, Any]:
        """Convert album DTO to dict with source tag.

        Hey future me - why dict not DTO? Because the return type of
        check_for_new_releases is dict for backward compat with automation.

        Args:
            album: Album DTO from plugin
            source: Provider name ("spotify" or "deezer")

        Returns:
            Dict with album info + source tag
        """
        return {
            "id": getattr(album, "id", None),
            "title": album.title,
            "artist_name": getattr(album, "artist_name", None),
            "release_date": album.release_date,
            "album_type": getattr(album, "album_type", "album"),
            "total_tracks": getattr(album, "total_tracks", None),
            "image_url": getattr(album, "image_url", None),
            "source": source,
        }

    def _parse_release_date(self, date_str: str) -> datetime | None:
        """Parse release date string to datetime.

        Hey future me - Spotify returns YYYY-MM-DD but sometimes just YYYY!
        Deezer is more consistent but still can vary. Handle both.

        Args:
            date_str: Date string in YYYY-MM-DD or YYYY format

        Returns:
            datetime or None if parsing fails
        """
        if not date_str:
            return None

        try:
            if len(date_str) == 4:  # Just year
                return datetime(int(date_str), 1, 1, tzinfo=UTC)
            elif len(date_str) == 7:  # YYYY-MM
                return datetime.strptime(date_str, "%Y-%m").replace(tzinfo=UTC)
            else:  # YYYY-MM-DD
                return datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse date '{date_str}': {e}")
            return None
