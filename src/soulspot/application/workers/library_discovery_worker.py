# Hey future me - LibraryDiscoveryWorker is the SUPERWORKER for library maintenance!
# It combines ALL enrichment + discography fetch into one coordinated background job.
#
# KEY INSIGHT: Deezer's public API needs NO OAuth! So we can:
# 1. Search by artist/album/track → get deezer_id
# 2. Fetch artist albums → get complete discography
# 3. Store in artist_discography table → UI shows "Missing Albums"
#
# PHASES (Dec 2025):
# Phase 1: Artist ID Discovery (deezer_id, spotify_uri)
# Phase 2: Artist Discography Fetch (complete album list)
# Phase 3: Update is_owned flags (compare library vs discography)
# Phase 4: Album ID Discovery (deezer_id, spotify_uri)
# Phase 5: Track ID Discovery via ISRC (deezer_id, spotify_uri)
#
# MULTI-SOURCE SUPPORT:
# - Uses EXISTING AppSettingsService.is_provider_enabled() for ON/OFF check
# - Uses SpotifyTokenRepository for OAuth token check (Spotify needs auth)
# - Deezer FIRST (no OAuth needed) for all operations
# - Spotify as ENHANCEMENT if enabled AND user has OAuth token
# - Merge results, deduplicate by title + album_type
# - Track source in artist_discography.source
#
# AVAILABILITY CHECK PATTERN:
# 1. is_provider_enabled("deezer") → True if mode != "off"
# 2. is_provider_enabled("spotify") → True if mode != "off"
# 3. SpotifyTokenRepository.get_active_token() → check OAuth exists
#
# DEPRECATES: LocalLibraryEnrichmentService for artist/album/track ID discovery!
# This worker does NOT trigger downloads - just discovery. User decides what to get.
"""Library Discovery Worker - Unified enrichment and discography fetching."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class LibraryDiscoveryWorker:
    """Background worker for library enrichment and discography discovery.

    Hey future me - this is the SUPERWORKER that REPLACES LocalLibraryEnrichmentService
    for all ID discovery operations!

    5 Phases:
    1. Artist ID Discovery: Find deezer_id/spotify_uri for local artists
    2. Discography Fetch: Get complete album lists from providers
    3. Ownership Update: Update is_owned flags by comparing with library
    4. Album ID Discovery: Find deezer_id/spotify_uri for local albums
    5. Track ID Discovery: Find deezer_id/spotify_uri via ISRC lookup

    MULTI-SOURCE STRATEGY using EXISTING availability patterns:
    - AppSettingsService.is_provider_enabled() for ON/OFF
    - SpotifyTokenRepository for OAuth token availability
    - Deezer FIRST (no OAuth!) for all operations
    - Spotify ENHANCEMENT if enabled AND OAuth token exists
    - Results are merged and deduplicated
    - Each entity gets IDs from BOTH services if available

    Key design decisions:
    - Uses Deezer FIRST (no OAuth needed!) for all operations
    - Spotify as fallback/enhancement IF provider enabled AND OAuth token available
    - Does NOT trigger downloads - just populates IDs and discography
    - Runs periodically (default: every 6 hours)

    DEPRECATED by this worker:
    - LocalLibraryEnrichmentService.enrich_batch()
    - LocalLibraryEnrichmentService.enrich_batch_deezer_only()
    - LocalLibraryEnrichmentService.enrich_tracks_by_isrc()
    - LibraryEnrichmentWorker (can be removed)
    """

    def __init__(
        self,
        db: Any,  # Database instance
        settings: Any,  # Settings instance
        run_interval_hours: int = 6,  # Default: 6 hours
    ) -> None:
        """Initialize discovery worker.

        Hey future me - we accept db (Database) and settings (Settings) objects
        because that's the pattern used by other workers (SpotifySyncWorker,
        DeezerSyncWorker, etc.). This makes lifecycle.py cleaner.

        Args:
            db: Database instance for session creation
            settings: Application settings
            run_interval_hours: How often to run discovery (default 6h)
        """
        self.db = db
        self.settings = settings
        self.check_interval_seconds = run_interval_hours * 3600  # Convert to seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run_at: datetime | None = None
        self._last_run_stats: dict[str, Any] | None = None

    async def start(self) -> None:
        """Start the discovery worker."""
        if self._running:
            logger.warning("LibraryDiscoveryWorker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"🔍 LibraryDiscoveryWorker started (interval: {self.check_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the discovery worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("LibraryDiscoveryWorker stopped")

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI.

        Returns:
            Dict with running state, config, and last run stats
        """
        return {
            "name": "Library Discovery Worker",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "check_interval_seconds": self.check_interval_seconds,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "last_run_stats": self._last_run_stats,
        }

    async def _run_loop(self) -> None:
        """Main worker loop."""
        # Initial delay to let app start up
        await asyncio.sleep(30)

        while self._running:
            try:
                stats = await self._run_discovery_cycle()
                self._last_run_at = datetime.now(UTC)
                self._last_run_stats = stats

                logger.info(
                    f"🔍 Discovery cycle complete: "
                    f"{stats.get('artists_enriched', 0)} artists enriched, "
                    f"{stats.get('albums_discovered', 0)} albums discovered"
                )
            except Exception as e:
                logger.error(f"Error in discovery worker loop: {e}", exc_info=True)

            # Wait for next cycle
            await asyncio.sleep(self.check_interval_seconds)

    async def _run_discovery_cycle(self) -> dict[str, Any]:
        """Run a complete discovery cycle.

        Executes all phases:
        1. Enrich artists without provider IDs (search Deezer/Spotify)
        2. Fetch discography for enriched artists
        3. Update is_owned flags
        4. Enrich albums without provider IDs (search Deezer/Spotify)
        5. Enrich tracks without provider IDs (via ISRC lookup)

        Returns:
            Stats dict with counts for each phase
        """
        stats: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "phase1_artist_enrichment": {},
            "phase2_discography": {},
            "phase3_ownership": {},
            "phase4_album_enrichment": {},
            "phase5_track_enrichment": {},
            "artists_enriched": 0,
            "albums_discovered": 0,
            "albums_enriched": 0,
            "tracks_enriched": 0,
            "errors": [],
        }

        async with self.db.session_scope() as session:
            try:
                # Phase 1: Enrich artists without provider IDs
                phase1_stats = await self._phase1_enrich_artists(session)
                stats["phase1_artist_enrichment"] = phase1_stats
                stats["artists_enriched"] = phase1_stats.get(
                    "deezer_enriched", 0
                ) + phase1_stats.get("spotify_enriched", 0)

                # Phase 2: Fetch discography for artists with IDs
                phase2_stats = await self._phase2_fetch_discography(session)
                stats["phase2_discography"] = phase2_stats
                stats["albums_discovered"] = phase2_stats.get(
                    "deezer_albums_added", 0
                ) + phase2_stats.get("spotify_albums_added", 0)

                # Phase 3: Update is_owned flags
                phase3_stats = await self._phase3_update_ownership(session)
                stats["phase3_ownership"] = phase3_stats

                # Phase 4: Enrich albums without provider IDs
                phase4_stats = await self._phase4_enrich_albums(session)
                stats["phase4_album_enrichment"] = phase4_stats
                stats["albums_enriched"] = phase4_stats.get(
                    "deezer_enriched", 0
                ) + phase4_stats.get("spotify_enriched", 0)

                # Phase 5: Enrich tracks via ISRC lookup
                phase5_stats = await self._phase5_enrich_tracks(session)
                stats["phase5_track_enrichment"] = phase5_stats
                stats["tracks_enriched"] = phase5_stats.get(
                    "deezer_enriched", 0
                ) + phase5_stats.get("spotify_enriched", 0)

                # Commit all changes
                await session.commit()

            except Exception as e:
                logger.error(f"Discovery cycle failed: {e}", exc_info=True)
                stats["errors"].append(str(e))
                await session.rollback()

        stats["completed_at"] = datetime.now(UTC).isoformat()
        return stats

    async def _initialize_plugins(
        self,
        session: AsyncSession,
    ) -> tuple[DeezerPlugin | None, SpotifyPlugin | None, list[str]]:
        """Initialize available plugins based on provider settings and OAuth status.

        Hey future me - this centralizes plugin initialization logic!
        Uses the proper patterns:
        1. AppSettingsService.is_provider_enabled() - check if provider is ON
        2. SpotifyTokenRepository - check if OAuth token exists (Spotify needs auth)

        Returns:
            Tuple of (deezer_plugin, spotify_plugin, sources_used list)
        """
        from soulspot.application.services.app_settings_service import (
            AppSettingsService,
        )
        from soulspot.config import get_settings
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )
        from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
        from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

        sources_used: list[str] = []
        app_settings = AppSettingsService(session)

        # === DEEZER (check if provider is enabled - no OAuth needed!) ===
        deezer_plugin = None
        if await app_settings.is_provider_enabled("deezer"):
            deezer_plugin = DeezerPlugin()
            sources_used.append("deezer")
        else:
            logger.debug("Deezer provider is disabled in settings")

        # === SPOTIFY (check if provider is enabled AND has OAuth) ===
        spotify_plugin = None
        if await app_settings.is_provider_enabled("spotify"):
            # Check if we have an OAuth token
            token_repo = SpotifyTokenRepository(session)
            token_model = await token_repo.get_active_token()

            if token_model and token_model.access_token:
                try:
                    settings = get_settings()
                    spotify_client = SpotifyClient(settings.spotify)
                    spotify_plugin = SpotifyPlugin(
                        client=spotify_client,
                        access_token=token_model.access_token,
                    )
                    sources_used.append("spotify")
                except Exception as e:
                    logger.warning(f"Spotify plugin init failed: {e}")
            else:
                logger.debug("Spotify enabled but no OAuth token available")
        else:
            logger.debug("Spotify provider is disabled in settings")

        return deezer_plugin, spotify_plugin, sources_used

    async def _phase1_enrich_artists(self, session: AsyncSession) -> dict[str, Any]:
        """Phase 1: Find provider IDs for artists without them.

        Hey future me - MULTI-SOURCE ENRICHMENT using EXISTING availability functions!
        Uses _initialize_plugins() which checks:
        1. AppSettingsService.is_provider_enabled() for provider ON/OFF status
        2. SpotifyTokenRepository for OAuth token (Spotify requires auth)

        Each source adds its own ID, so artist can have BOTH deezer_id AND spotify_uri.

        Returns:
            Stats dict with processed/enriched/failed counts per source
        """
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        stats = {
            "processed": 0,
            "deezer_enriched": 0,
            "spotify_enriched": 0,
            "already_enriched": 0,
            "failed": 0,
            "errors": [],
            "sources_used": [],
        }

        artist_repo = ArtistRepository(session)

        # Get artists without deezer_id (limit to batch size)
        artists = await artist_repo.get_unenriched(limit=50)

        if not artists:
            logger.debug("No unenriched artists found")
            return stats

        # Initialize plugins using centralized helper
        deezer_plugin, spotify_plugin, sources_used = await self._initialize_plugins(
            session
        )
        stats["sources_used"] = sources_used

        # Log which sources we're using
        if deezer_plugin and spotify_plugin:
            logger.info(
                f"Phase 1: Enriching {len(artists)} artists via Deezer + Spotify"
            )
        elif deezer_plugin:
            logger.info(f"Phase 1: Enriching {len(artists)} artists via Deezer only")
        elif spotify_plugin:
            logger.info(f"Phase 1: Enriching {len(artists)} artists via Spotify only")
        else:
            logger.warning("Phase 1: No providers available for enrichment!")
            return stats

        for artist in artists:
            stats["processed"] += 1

            # Skip if already has BOTH IDs
            if artist.deezer_id and artist.spotify_uri:
                stats["already_enriched"] += 1
                continue

            try:
                # === DEEZER (if available and artist missing deezer_id) ===
                if deezer_plugin and not artist.deezer_id:
                    search_result = await deezer_plugin.search_artists(
                        artist.name, limit=5
                    )

                    if search_result.items and search_result.items[0].deezer_id:
                        best_match = search_result.items[0]
                        await artist_repo.update_deezer_id(
                            artist_id=artist.id,
                            deezer_id=best_match.deezer_id,
                        )
                        stats["deezer_enriched"] += 1
                        logger.debug(
                            f"Deezer enriched '{artist.name}' → deezer_id={best_match.deezer_id}"
                        )

                    # Rate limit
                    await asyncio.sleep(0.05)

                # === SPOTIFY (if available and artist missing spotify_uri) ===
                if spotify_plugin and not artist.spotify_uri:
                    try:
                        spotify_result = await spotify_plugin.search_artists(
                            artist.name, limit=5
                        )

                        if spotify_result.items and spotify_result.items[0].spotify_uri:
                            best_match = spotify_result.items[0]
                            await artist_repo.update_spotify_uri(
                                artist_id=artist.id,
                                spotify_uri=best_match.spotify_uri,
                            )
                            stats["spotify_enriched"] += 1
                            logger.debug(
                                f"Spotify enriched '{artist.name}' → spotify_uri={best_match.spotify_uri}"
                            )

                        # Rate limit
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        # Don't fail entire artist if Spotify fails
                        logger.debug(f"Spotify search failed for '{artist.name}': {e}")

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    {
                        "artist": artist.name,
                        "error": str(e),
                    }
                )
                logger.warning(f"Failed to enrich artist '{artist.name}': {e}")

        return stats

    async def _phase2_fetch_discography(self, session: AsyncSession) -> dict[str, Any]:
        """Phase 2: Fetch complete discography for enriched artists.

        Hey future me - MULTI-SOURCE DISCOGRAPHY using EXISTING availability functions!
        Uses _initialize_plugins() which checks:
        1. AppSettingsService.is_provider_enabled() for provider ON/OFF status
        2. SpotifyTokenRepository for OAuth token (Spotify requires auth)

        Results are MERGED and DEDUPLICATED:
        - If album found on both services, entry has BOTH deezer_id and spotify_uri
        - upsert() handles deduplication by (artist_id, title, album_type)

        Returns:
            Stats dict with artists_processed/albums_added counts per source
        """
        from soulspot.domain.entities import ArtistDiscography
        from soulspot.domain.value_objects import AlbumId, SpotifyUri
        from soulspot.infrastructure.persistence.repositories import (
            ArtistDiscographyRepository,
            ArtistRepository,
        )

        stats = {
            "artists_processed": 0,
            "artists_skipped": 0,
            "deezer_albums_added": 0,
            "spotify_albums_added": 0,
            "albums_merged": 0,
            "errors": [],
            "sources_used": [],
        }

        artist_repo = ArtistRepository(session)
        discography_repo = ArtistDiscographyRepository(session)

        # Get artists with deezer_id that haven't been synced recently
        artists = await artist_repo.get_with_deezer_id_needing_discography_sync(
            limit=20
        )

        if not artists:
            logger.debug("No artists need discography sync")
            return stats

        # Initialize plugins using centralized helper
        deezer_plugin, spotify_plugin, sources_used = await self._initialize_plugins(
            session
        )
        stats["sources_used"] = sources_used

        # Log which sources we're using
        if deezer_plugin and spotify_plugin:
            logger.info(
                f"Phase 2: Fetching discography for {len(artists)} artists via Deezer + Spotify"
            )
        elif deezer_plugin:
            logger.info(
                f"Phase 2: Fetching discography for {len(artists)} artists via Deezer only"
            )
        elif spotify_plugin:
            logger.info(
                f"Phase 2: Fetching discography for {len(artists)} artists via Spotify only"
            )
        else:
            logger.warning("Phase 2: No providers available for discography fetch!")
            return stats

        for artist in artists:
            stats["artists_processed"] += 1

            if not artist.deezer_id and not artist.spotify_uri:
                stats["artists_skipped"] += 1
                continue

            try:
                # === DEEZER DISCOGRAPHY (if available and artist has deezer_id) ===
                if deezer_plugin and artist.deezer_id:
                    albums_response = await deezer_plugin.get_artist_albums(
                        artist_id=artist.deezer_id,
                        limit=100,
                    )

                    for album_dto in albums_response.items:
                        album_type = (album_dto.album_type or "album").lower()

                        entry = ArtistDiscography(
                            id=AlbumId(str(uuid4())),
                            artist_id=artist.id,
                            title=album_dto.title,
                            album_type=album_type,
                            deezer_id=album_dto.deezer_id,
                            release_date=album_dto.release_date,
                            total_tracks=album_dto.total_tracks,
                            cover_url=album_dto.cover.url if album_dto.cover else None,
                            source="deezer",
                        )

                        await discography_repo.upsert(entry)
                        stats["deezer_albums_added"] += 1

                    await asyncio.sleep(0.1)

                # === SPOTIFY DISCOGRAPHY (if available and artist has spotify_uri) ===
                if spotify_plugin and artist.spotify_uri:
                    try:
                        # Use spotify_id property (extracts ID from SpotifyUri value object)
                        spotify_id = artist.spotify_id

                        spotify_response = await spotify_plugin.get_artist_albums(
                            artist_id=spotify_id,
                            limit=50,
                        )

                        for album_dto in spotify_response.items:
                            album_type = (album_dto.album_type or "album").lower()

                            # Create entry with Spotify data
                            # upsert() will MERGE with existing Deezer entry if same title+type
                            entry = ArtistDiscography(
                                id=AlbumId(str(uuid4())),
                                artist_id=artist.id,
                                title=album_dto.title,
                                album_type=album_type,
                                spotify_uri=SpotifyUri(album_dto.spotify_uri)
                                if album_dto.spotify_uri
                                else None,
                                release_date=album_dto.release_date,
                                total_tracks=album_dto.total_tracks,
                                cover_url=album_dto.cover.url
                                if album_dto.cover
                                else None,
                                source="spotify",
                            )

                            await discography_repo.upsert(entry)
                            stats["spotify_albums_added"] += 1

                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.debug(
                            f"Spotify discography failed for '{artist.name}': {e}"
                        )

                # Update artist's discography sync timestamp
                await artist_repo.update_albums_synced_at(artist.id)

            except Exception as e:
                stats["errors"].append(
                    {
                        "artist": artist.name,
                        "error": str(e),
                    }
                )
                logger.warning(f"Failed to fetch discography for '{artist.name}': {e}")

        return stats

    async def _phase3_update_ownership(self, session: AsyncSession) -> dict[str, Any]:
        """Phase 3: Update is_owned flags in artist_discography.

        Hey future me - this compares discography with actual library!
        For each artist, we check which discovered albums the user actually owns.

        Returns:
            Stats dict with artists_processed/entries_updated counts
        """
        from soulspot.infrastructure.persistence.repositories import (
            ArtistDiscographyRepository,
            ArtistRepository,
        )

        stats = {
            "artists_processed": 0,
            "entries_updated": 0,
            "errors": [],
        }

        artist_repo = ArtistRepository(session)
        discography_repo = ArtistDiscographyRepository(session)

        # Get all artists that have discography entries
        # For now, we process all - could optimize to only process recently synced
        artists = await artist_repo.get_with_discography(limit=100)

        if not artists:
            logger.debug("No artists with discography to update")
            return stats

        logger.info(f"Phase 3: Updating ownership for {len(artists)} artists")

        for artist in artists:
            stats["artists_processed"] += 1

            try:
                updated = await discography_repo.update_is_owned_for_artist(artist.id)
                stats["entries_updated"] += updated

            except Exception as e:
                stats["errors"].append(
                    {
                        "artist": artist.name,
                        "error": str(e),
                    }
                )
                logger.warning(f"Failed to update ownership for '{artist.name}': {e}")

        return stats

    async def _phase4_enrich_albums(self, session: AsyncSession) -> dict[str, Any]:
        """Phase 4: Find provider IDs for albums without them.

        Hey future me - ALBUM ID DISCOVERY!
        Similar to Phase 1 but for albums instead of artists.
        Uses album title + artist name to search Deezer/Spotify.

        Returns:
            Stats dict with processed/enriched/failed counts per source
        """
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            ArtistRepository,
        )

        stats = {
            "processed": 0,
            "deezer_enriched": 0,
            "spotify_enriched": 0,
            "already_enriched": 0,
            "failed": 0,
            "errors": [],
            "sources_used": [],
        }

        album_repo = AlbumRepository(session)
        artist_repo = ArtistRepository(session)

        # Get albums without deezer_id (local files without provider IDs)
        albums = await album_repo.get_albums_without_deezer_id(limit=50)

        if not albums:
            logger.debug("No albums need ID discovery")
            return stats

        # Initialize plugins
        deezer_plugin, spotify_plugin, sources_used = await self._initialize_plugins(
            session
        )
        stats["sources_used"] = sources_used

        if not deezer_plugin and not spotify_plugin:
            logger.warning("Phase 4: No providers available for album enrichment!")
            return stats

        logger.info(
            f"Phase 4: Enriching {len(albums)} albums via {', '.join(sources_used)}"
        )

        for album in albums:
            stats["processed"] += 1

            # Skip if already has BOTH IDs
            if album.deezer_id and album.spotify_uri:
                stats["already_enriched"] += 1
                continue

            # Get artist name for search
            artist = await artist_repo.get_by_id(album.artist_id)
            artist_name = artist.name if artist else ""

            try:
                # === DEEZER (if available and album missing deezer_id) ===
                if deezer_plugin and not album.deezer_id:
                    search_query = f"{artist_name} {album.title}"
                    search_result = await deezer_plugin.search_albums(
                        search_query, limit=5
                    )

                    if search_result.items and search_result.items[0].deezer_id:
                        best_match = search_result.items[0]

                        # Check if deezer_id already exists on another album (avoid duplicates)
                        existing = await album_repo.get_by_deezer_id(
                            best_match.deezer_id
                        )
                        if existing and existing.id != album.id:
                            logger.debug(
                                f"Deezer ID {best_match.deezer_id} already assigned to album "
                                f"'{existing.title}', skipping duplicate for '{album.title}'"
                            )
                        else:
                            await album_repo.update_deezer_id(
                                album_id=album.id,
                                deezer_id=best_match.deezer_id,
                            )
                            # Hey future me - SET PRIMARY_TYPE from Deezer's album_type!
                            # This is critical for Album/EP/Single classification.
                            # Deezer uses: album, ep, single, compile
                            if best_match.album_type:
                                await album_repo.update_primary_type(
                                    album_id=album.id,
                                    primary_type=best_match.album_type,
                                )
                                logger.debug(
                                    f"Set primary_type='{best_match.album_type}' for album '{album.title}'"
                                )
                            stats["deezer_enriched"] += 1
                            logger.debug(
                                f"Deezer enriched album '{album.title}' → deezer_id={best_match.deezer_id}"
                            )

                    await asyncio.sleep(0.05)

                # === SPOTIFY (if available and album missing spotify_uri) ===
                if spotify_plugin and not album.spotify_uri:
                    try:
                        search_query = f"{artist_name} {album.title}"
                        spotify_result = await spotify_plugin.search_album(
                            search_query, limit=5
                        )

                        if spotify_result.items and spotify_result.items[0].spotify_uri:
                            best_match = spotify_result.items[0]

                            # Check if spotify_uri already exists on another album (avoid duplicates)
                            existing = await album_repo.get_by_spotify_uri(
                                str(best_match.spotify_uri)
                            )
                            if existing and existing.id != album.id:
                                logger.debug(
                                    f"Spotify URI {best_match.spotify_uri} already assigned to album "
                                    f"'{existing.title}', skipping duplicate for '{album.title}'"
                                )
                            else:
                                await album_repo.update_spotify_uri(
                                    album_id=album.id,
                                    spotify_uri=str(best_match.spotify_uri),
                                )
                                # Hey future me - SET PRIMARY_TYPE from Spotify's album_type!
                                # Only set if not already set by Deezer (Deezer is processed first).
                                # Spotify uses: album, single, compilation
                                if best_match.album_type and not album.deezer_id:
                                    await album_repo.update_primary_type(
                                        album_id=album.id,
                                        primary_type=best_match.album_type,
                                    )
                                    logger.debug(
                                        f"Set primary_type='{best_match.album_type}' for album '{album.title}'"
                                    )
                                stats["spotify_enriched"] += 1
                                logger.debug(
                                    f"Spotify enriched album '{album.title}' → spotify_uri={best_match.spotify_uri}"
                                )

                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.debug(
                            f"Spotify search failed for album '{album.title}': {e}"
                        )

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    {
                        "album": album.title,
                        "error": str(e),
                    }
                )
                logger.warning(f"Failed to enrich album '{album.title}': {e}")

        # === PHASE 4B: Update primary_type for albums that already have IDs ===
        # Hey future me - this is for albums that got IDs before we added primary_type!
        # We fetch the album data from Deezer/Spotify and extract the album_type.
        albums_needing_type = await album_repo.get_albums_without_primary_type(
            limit=100
        )

        if albums_needing_type and (deezer_plugin or spotify_plugin):
            logger.info(
                f"Phase 4B: Updating primary_type for {len(albums_needing_type)} albums with existing IDs"
            )
            stats["primary_type_updated"] = 0

            for album in albums_needing_type:
                try:
                    # Try Deezer first (if album has deezer_id)
                    if album.deezer_id and deezer_plugin:
                        try:
                            album_details = await deezer_plugin.get_album(
                                str(album.deezer_id)
                            )
                            if album_details and album_details.album_type:
                                await album_repo.update_primary_type(
                                    album_id=album.id,
                                    primary_type=album_details.album_type,
                                )
                                stats["primary_type_updated"] += 1
                                logger.debug(
                                    f"Updated primary_type='{album_details.album_type}' for album '{album.title}' via Deezer"
                                )
                                continue  # Skip Spotify if Deezer worked
                        except Exception as e:
                            logger.debug(
                                f"Deezer album fetch failed for '{album.title}': {e}"
                            )

                    # Fallback to Spotify (if album has spotify_uri)
                    if album.spotify_uri and spotify_plugin:
                        try:
                            album_details = await spotify_plugin.get_album(
                                str(album.spotify_uri)
                            )
                            if album_details and album_details.album_type:
                                await album_repo.update_primary_type(
                                    album_id=album.id,
                                    primary_type=album_details.album_type,
                                )
                                stats["primary_type_updated"] += 1
                                logger.debug(
                                    f"Updated primary_type='{album_details.album_type}' for album '{album.title}' via Spotify"
                                )
                        except Exception as e:
                            logger.debug(
                                f"Spotify album fetch failed for '{album.title}': {e}"
                            )

                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.debug(
                        f"Failed to update primary_type for album '{album.title}': {e}"
                    )

        return stats

    async def _phase5_enrich_tracks(self, session: AsyncSession) -> dict[str, Any]:
        """Phase 5: Find provider IDs for tracks via ISRC lookup.

        Hey future me - TRACK ID DISCOVERY via ISRC!
        ISRC is the UNIVERSAL music identifier. If a track has an ISRC,
        we can look it up on ANY service with 100% accuracy.

        Much more reliable than title/artist fuzzy matching!

        Returns:
            Stats dict with processed/enriched/failed counts per source
        """
        from soulspot.infrastructure.persistence.repositories import TrackRepository

        stats = {
            "processed": 0,
            "deezer_enriched": 0,
            "spotify_enriched": 0,
            "already_enriched": 0,
            "failed": 0,
            "no_isrc": 0,
            "errors": [],
            "sources_used": [],
        }

        track_repo = TrackRepository(session)

        # Get tracks with ISRC but without deezer_id
        tracks = await track_repo.get_tracks_without_deezer_id_with_isrc(limit=100)

        if not tracks:
            logger.debug("No tracks need ID discovery via ISRC")
            return stats

        # Initialize plugins
        deezer_plugin, spotify_plugin, sources_used = await self._initialize_plugins(
            session
        )
        stats["sources_used"] = sources_used

        if not deezer_plugin and not spotify_plugin:
            logger.warning("Phase 5: No providers available for track enrichment!")
            return stats

        logger.info(
            f"Phase 5: Enriching {len(tracks)} tracks via ISRC lookup using {', '.join(sources_used)}"
        )

        for track in tracks:
            stats["processed"] += 1

            # This shouldn't happen (query filters for ISRC) but just in case
            if not track.isrc:
                stats["no_isrc"] += 1
                continue

            try:
                # === DEEZER (if available and track missing deezer_id) ===
                if deezer_plugin and not track.deezer_id:
                    # Deezer ISRC lookup - direct API call!
                    deezer_track = await deezer_plugin.get_track_by_isrc(track.isrc)

                    if deezer_track and deezer_track.deezer_id:
                        await track_repo.update_deezer_id(
                            track_id=track.id,
                            deezer_id=deezer_track.deezer_id,
                        )
                        stats["deezer_enriched"] += 1
                        logger.debug(
                            f"Deezer enriched track '{track.title}' via ISRC → deezer_id={deezer_track.deezer_id}"
                        )

                    await asyncio.sleep(0.05)

                # === SPOTIFY (if available and track missing spotify_uri) ===
                if spotify_plugin and not track.spotify_uri:
                    try:
                        # Spotify ISRC search via track search with ISRC filter
                        spotify_result = await spotify_plugin.search_track(
                            f"isrc:{track.isrc}", limit=1
                        )

                        if spotify_result.items and spotify_result.items[0].spotify_uri:
                            best_match = spotify_result.items[0]
                            await track_repo.update_spotify_uri(
                                track_id=track.id,
                                spotify_uri=str(best_match.spotify_uri),
                            )
                            stats["spotify_enriched"] += 1
                            logger.debug(
                                f"Spotify enriched track '{track.title}' via ISRC → spotify_uri={best_match.spotify_uri}"
                            )

                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.debug(
                            f"Spotify ISRC search failed for track '{track.title}': {e}"
                        )

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    {
                        "track": track.title,
                        "isrc": track.isrc,
                        "error": str(e),
                    }
                )
                logger.warning(f"Failed to enrich track '{track.title}' via ISRC: {e}")

        return stats

    async def run_once(self) -> dict[str, Any]:
        """Run a single discovery cycle manually.

        Hey future me - this is for manual triggering from API/UI!
        Returns the same stats as the background loop.
        """
        logger.info("🔍 Running manual discovery cycle")
        stats = await self._run_discovery_cycle()
        self._last_run_at = datetime.now(UTC)
        self._last_run_stats = stats
        return stats
