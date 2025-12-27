# AI-Model: Copilot
"""Service for syncing and managing followed artists from MULTIPLE PROVIDERS.

MULTI-PROVIDER SUPPORT (Nov 2025):
- sync_followed_artists() - NOW MULTI-PROVIDER! Spotify + Deezer (both require OAuth)
- sync_artist_albums() - Multi-provider with Deezer fallback (Deezer NO AUTH!)
- When Spotify fails for album fetch, we try Deezer automatically
- This ensures artist albums work even without Spotify OAuth!

FOLLOWED ARTISTS FROM ALL PROVIDERS → UNIFIED LIBRARY:
- Spotify followed artists → soulspot_artists (source='spotify' or 'hybrid')
- Deezer favorite artists → soulspot_artists (source='deezer' or 'hybrid')
- All providers are aggregated into the unified library!

DEDUPLICATION STRATEGY:
- Artists are deduplicated by:
  1. Service-specific ID (spotify_uri, deezer_id)
  2. Name (case-insensitive fallback)
- Albums are deduplicated by:
  1. SpotifyUri (for Spotify albums ONLY - SpotifyUri validates "spotify:" prefix!)
  2. title + artist_name (cross-service, case-insensitive)
- Cross-service deduplication by: normalized(artist_name + title)
- This prevents duplicates when same artist/album comes from different providers
"""

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Artist
from soulspot.domain.exceptions import EntityNotFoundError, ValidationError
from soulspot.domain.value_objects import ArtistId, SpotifyUri
from soulspot.infrastructure.observability.log_messages import LogMessages
from soulspot.infrastructure.persistence.repositories import ArtistRepository

if TYPE_CHECKING:
    from typing import Any

    from soulspot.domain.dtos import ArtistDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


def _normalize_album_key(artist_name: str, title: str, release_year: int | None) -> str:
    """Create normalized key for album deduplication.

    Hey future me - this is CRITICAL for cross-service deduplication!
    Same album from Spotify and Deezer have different IDs but same:
    - Artist name (case-insensitive, stripped)
    - Album title (case-insensitive, stripped)
    - Release year (optional, helps distinguish remastered versions)

    Examples:
    - "Pink Floyd|The Dark Side of the Moon|1973"
    - "aurora|all my demons greeting me as a friend|2016"

    GOTCHA: Different versions (remastered, deluxe) may have same name!
    We include release_year to help, but it's not perfect.
    """
    artist = (artist_name or "").strip().lower()
    album = (title or "").strip().lower()
    year = str(release_year) if release_year else "unknown"
    return f"{artist}|{album}|{year}"


class FollowedArtistsService:
    """Service for syncing followed artists from MULTIPLE PROVIDERS.

    Hey future me - REFACTORED for MULTI-PROVIDER support!
    Now syncs followed artists from Spotify AND Deezer to unified library.

    MULTI-PROVIDER (Nov 2025):
    - sync_followed_artists() - Spotify followed artists (requires OAuth)
    - sync_followed_artists_all_providers() - ALL providers aggregated!
    - _sync_deezer_followed_artists() - Deezer favorite artists (requires OAuth)
    - sync_artist_albums() - Multi-provider with Deezer fallback (Deezer NO AUTH!)

    All followed artists from any provider land in the unified soulspot_artists table
    with appropriate source field ('spotify', 'deezer', 'hybrid').

    Cross-provider deduplication ensures same artist followed on multiple services
    gets merged into single library entry with all service IDs.

    GOTCHA: Spotify uses cursor-based pagination (after param) NOT offset!
    Deezer uses index-based pagination. Each plugin handles its own pagination.
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize followed artists service.

        Hey future me - refactored to use SpotifyPlugin WITH Deezer fallback!
        The plugin handles token management internally, no more access_token juggling.

        MULTI-SERVICE PATTERN (Dec 2025):
        Both plugins are now OPTIONAL! The service works with:
        - BOTH plugins: Full capability (Spotify primary, Deezer fallback)
        - Spotify only: Standard Spotify-only mode
        - Deezer only: Public API mode (no OAuth needed!)
        - Neither: Will fail on sync operations (but constructor succeeds)

        PROVIDER MAPPING SERVICE (Nov 2025):
        Wir nutzen jetzt den zentralen ProviderMappingService für ID-Mapping.
        Statt manuell ArtistId.generate() zu machen, nutzt der MappingService
        konsistente Lookup-Logik und erstellt IDs nur wenn nötig.

        Args:
            session: Database session for Artist repository
            spotify_plugin: Optional SpotifyPlugin for API calls (handles auth internally)
            deezer_plugin: Optional DeezerPlugin for fallback artist albums (NO AUTH!)
        """
        from soulspot.application.services.provider_mapping_service import (
            ProviderMappingService,
        )

        self._session = session
        self.artist_repo = ArtistRepository(session)
        self.spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin
        self._mapping_service = ProviderMappingService(session)

    # Hey future me, this is the SPOTIFY-specific followed artists sync!
    # REFACTORED to use SpotifyPlugin! Now named _sync_spotify_followed_artists
    # for symmetry with _sync_deezer_followed_artists.
    # It fetches ALL followed artists from Spotify (handling pagination automatically via
    # PaginatedResponse) and creates/updates Artist entities in DB. Returns list of Artists
    # for UI to display. The sync operation is idempotent - safe to call multiple times.
    # The plugin handles auth internally - no more access_token parameter needed!
    # Progress is logged. Commits are caller's responsibility (service doesn't commit).
    #
    # AUTO-DISCOGRAPHY (Jan 2025):
    # If auto_sync_discography=True, we also sync discography for all NEWLY CREATED artists.
    # This means new artists get their albums + tracks immediately, not after 6h wait.
    async def _sync_spotify_followed_artists(
        self,
        auto_sync_discography: bool = True,
    ) -> tuple[list[Artist], dict[str, int]]:
        """Fetch all followed artists from Spotify and sync to database.

        Hey future me - SPOTIFY-specific sync method!
        This is symmetric with _sync_deezer_followed_artists().
        Use sync_followed_artists_all_providers() for multi-provider sync.

        IMPORTANT: This method REQUIRES spotify_plugin to be set!
        If you need album sync without Spotify, use sync_artist_albums()
        which falls back to Deezer.
        
        AUTO-DISCOGRAPHY (Jan 2025):
        New artists automatically get their discography synced (albums + tracks)
        so they're immediately useful in the library. Set auto_sync_discography=False
        to disable this (e.g., for bulk imports where LibraryDiscoveryWorker will handle it).

        Args:
            auto_sync_discography: If True, sync discography for newly created artists

        Returns:
            Tuple of (list of Artist entities, sync statistics dict)

        Raises:
            PluginError: If Spotify API request fails
            ValidationError: If spotify_plugin is not configured
        """
        # Hey future me - early validation! _sync_spotify_followed_artists needs Spotify OAuth
        if not self.spotify_plugin:
            raise ValidationError(
                "Spotify plugin required for followed artists sync. "
                "Use sync_artist_albums() for album-only sync via Deezer."
            )

        all_artists: list[Artist] = []
        # Hey future me - track newly created artists for auto-discography sync!
        newly_created_artists: list[Artist] = []
        after_cursor: str | None = None
        page = 1
        stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "discography_synced": 0,  # Track how many got auto-discography
            "source": "spotify",  # Track which provider was used
        }

        # Listen, Spotify pagination loop using SpotifyPlugin!
        # Plugin returns PaginatedResponse with items (ArtistDTOs) and pagination info.
        # We keep fetching until there are no more items.
        while True:
            try:
                # SpotifyPlugin.get_followed_artists returns PaginatedResponse[ArtistDTO]
                response = await self.spotify_plugin.get_followed_artists(
                    limit=50,
                    after=after_cursor,
                )

                items = response.items
                if not items:
                    logger.info("No more followed artists to fetch")
                    break

                logger.info(
                    f"Fetched page {page} with {len(items)} followed artists from Spotify"
                )

                # Process each artist from plugin response (already converted to ArtistDTO!)
                for artist_dto in items:
                    try:
                        artist, was_created = await self._process_artist_dto(
                            artist_dto, source="spotify"
                        )
                        all_artists.append(artist)
                        stats["total_fetched"] += 1
                        if was_created:
                            stats["created"] += 1
                            # Hey future me - track new artists for auto-discography!
                            newly_created_artists.append(artist)
                        else:
                            stats["updated"] += 1
                    except Exception as e:
                        logger.error(
                            LogMessages.sync_failed(
                                sync_type="artist_processing",
                                reason=f"Failed to process artist {artist_dto.name}",
                                hint="Check database constraints and artist data validity",
                            ).format(),
                            exc_info=e,
                        )
                        stats["errors"] += 1

                # Check for next page - get last artist's spotify_id as cursor
                if response.next_offset and items:
                    after_cursor = items[-1].spotify_id
                else:
                    logger.info("Reached end of followed artists (no more pages)")
                    break

                page += 1

            except Exception as e:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="followed_artists_pagination",
                        reason=f"Error fetching followed artists page {page}",
                        hint="Returning partial results - check Spotify API status",
                    ).format(),
                    exc_info=e,
                )
                # Return partial results if pagination fails mid-sync
                break

        logger.info(
            f"Followed artists sync complete: {stats['total_fetched']} fetched, "
            f"{stats['created']} created, {stats['updated']} updated, {stats['errors']} errors"
        )

        # Hey future me - AUTO-DISCOGRAPHY SYNC for new artists!
        # This ensures new artists get their albums + tracks immediately.
        # Without this, users would wait 6h for LibraryDiscoveryWorker.
        if auto_sync_discography and newly_created_artists:
            logger.info(
                f"🎵 Starting auto-discography sync for {len(newly_created_artists)} new artists..."
            )
            for artist in newly_created_artists:
                try:
                    disco_stats = await self.sync_artist_discography_complete(
                        artist_id=str(artist.id.value),
                        include_tracks=True,
                    )
                    stats["discography_synced"] += 1
                    logger.info(
                        f"✅ Auto-synced discography for {artist.name}: "
                        f"{disco_stats['albums_added']} albums, {disco_stats['tracks_added']} tracks"
                    )
                except Exception as e:
                    # Log but continue - one failure shouldn't stop others
                    logger.warning(
                        f"⚠️ Auto-discography sync failed for {artist.name}: {e}"
                    )

            logger.info(
                f"Auto-discography sync complete: {stats['discography_synced']}/{len(newly_created_artists)} artists"
            )

        return all_artists, stats

    # Hey future me - MULTI-PROVIDER Followed Artists Sync!
    # This syncs followed artists from ALL enabled providers (Spotify + Deezer) to
    # the unified library. Each provider requires its own OAuth authentication.
    # Artists from different providers are MERGED into the same library entry if
    # they match by name or MusicBrainz ID.
    async def sync_followed_artists_all_providers(
        self,
    ) -> tuple[list[Artist], dict[str, Any]]:
        """Sync followed artists from ALL providers to unified library.

        Hey future me - this is the MULTI-PROVIDER version!
        Aggregates followed artists from Spotify AND Deezer (both require OAuth).
        Each artist is deduplicated across providers.

        The unified library gets artists with source='spotify', 'deezer', or 'hybrid'
        depending on where the artist was followed.

        Returns:
            Tuple of (list of all Artist entities, aggregated stats by provider)
        """
        from soulspot.domain.ports.plugin import PluginCapability

        all_artists: list[Artist] = []
        seen_names: set[str] = set()  # For cross-provider deduplication
        aggregate_stats: dict[str, Any] = {
            "providers": {},
            "total_fetched": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_errors": 0,
        }

        # 1. Sync from Spotify (if plugin available AND authenticated)
        # Hey future me - spotify_plugin can be None if user isn't logged in!
        if self.spotify_plugin and self.spotify_plugin.can_use(
            PluginCapability.USER_FOLLOWED_ARTISTS
        ):
            try:
                spotify_artists, spotify_stats = await self._sync_spotify_followed_artists()
                aggregate_stats["providers"]["spotify"] = spotify_stats
                aggregate_stats["total_fetched"] += spotify_stats["total_fetched"]
                aggregate_stats["total_created"] += spotify_stats["created"]
                aggregate_stats["total_updated"] += spotify_stats["updated"]
                aggregate_stats["total_errors"] += spotify_stats["errors"]

                # Track names for deduplication
                for artist in spotify_artists:
                    seen_names.add(artist.name.lower().strip())
                    all_artists.append(artist)

                logger.info(
                    f"Spotify followed artists sync: {spotify_stats['total_fetched']} fetched"
                )
            except Exception as e:
                logger.warning(f"Spotify followed artists sync failed: {e}")
                aggregate_stats["providers"]["spotify"] = {"error": str(e)}
        else:
            logger.debug("Skipping Spotify - not authenticated")
            aggregate_stats["providers"]["spotify"] = {"skipped": "not_authenticated"}

        # 2. Sync from Deezer (if authenticated)
        if self._deezer_plugin and self._deezer_plugin.can_use(
            PluginCapability.USER_FOLLOWED_ARTISTS
        ):
            try:
                deezer_artists, deezer_stats = await self._sync_deezer_followed_artists(
                    seen_names=seen_names
                )
                aggregate_stats["providers"]["deezer"] = deezer_stats
                aggregate_stats["total_fetched"] += deezer_stats["total_fetched"]
                aggregate_stats["total_created"] += deezer_stats["created"]
                aggregate_stats["total_updated"] += deezer_stats["updated"]
                aggregate_stats["total_errors"] += deezer_stats["errors"]

                all_artists.extend(deezer_artists)

                logger.info(
                    f"Deezer followed artists sync: {deezer_stats['total_fetched']} fetched"
                )
            except Exception as e:
                logger.warning(f"Deezer followed artists sync failed: {e}")
                aggregate_stats["providers"]["deezer"] = {"error": str(e)}
        else:
            logger.debug("Skipping Deezer - not authenticated or not available")
            aggregate_stats["providers"]["deezer"] = {"skipped": "not_authenticated"}

        logger.info(
            f"Multi-provider sync complete: {aggregate_stats['total_fetched']} total, "
            f"{aggregate_stats['total_created']} created, {aggregate_stats['total_updated']} updated"
        )

        return all_artists, aggregate_stats

    # Hey future me - Deezer-specific followed artists sync!
    # Deezer calls them "favorite artists" but it's the same concept.
    # This is separate from Spotify because Deezer has different pagination.
    async def _sync_deezer_followed_artists(
        self, seen_names: set[str] | None = None, auto_sync_discography: bool = True,
    ) -> tuple[list[Artist], dict[str, int]]:
        """Sync followed artists from Deezer to unified library.

        Hey future me - Deezer requires OAuth for favorite artists!
        This is NOT the same as the public artist lookup (which is free).

        Args:
            seen_names: Set of artist names already synced (for dedup)
            auto_sync_discography: If True, sync discography for newly created artists

        Returns:
            Tuple of (list of Artist entities, sync stats)
        """
        if not self._deezer_plugin:
            return [], {"total_fetched": 0, "created": 0, "updated": 0, "errors": 0}

        all_artists: list[Artist] = []
        # Hey future me - track newly created artists for auto-discography!
        newly_created_artists: list[Artist] = []
        seen_names = seen_names or set()
        after_cursor: str | None = None
        stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "skipped_duplicate": 0,
            "errors": 0,
            "discography_synced": 0,
            "source": "deezer",
        }

        while True:
            try:
                response = await self._deezer_plugin.get_followed_artists(
                    limit=50,
                    after=after_cursor,
                )

                items = response.items
                if not items:
                    break

                for artist_dto in items:
                    try:
                        # Cross-provider deduplication by name
                        name_key = artist_dto.name.lower().strip()
                        if name_key in seen_names:
                            stats["skipped_duplicate"] += 1
                            # Try to merge - add deezer_id to existing artist
                            await self._merge_deezer_to_existing(artist_dto)
                            continue

                        seen_names.add(name_key)
                        artist, was_created = await self._process_artist_dto(
                            artist_dto, source="deezer"
                        )
                        all_artists.append(artist)
                        stats["total_fetched"] += 1
                        if was_created:
                            stats["created"] += 1
                            # Hey future me - track new artists for auto-discography!
                            newly_created_artists.append(artist)
                        else:
                            stats["updated"] += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process Deezer artist {artist_dto.name}: {e}"
                        )
                        stats["errors"] += 1

                # Deezer uses index-based pagination
                if response.next_offset:
                    after_cursor = str(response.next_offset)
                else:
                    break

            except Exception as e:
                logger.error(f"Deezer followed artists fetch failed: {e}")
                break

        # Hey future me - AUTO-DISCOGRAPHY SYNC for new Deezer artists!
        if auto_sync_discography and newly_created_artists:
            logger.info(
                f"🎵 Starting auto-discography sync for {len(newly_created_artists)} new Deezer artists..."
            )
            for artist in newly_created_artists:
                try:
                    disco_stats = await self.sync_artist_discography_complete(
                        artist_id=str(artist.id.value),
                        include_tracks=True,
                    )
                    stats["discography_synced"] += 1
                    logger.info(
                        f"✅ Auto-synced discography for {artist.name}: "
                        f"{disco_stats['albums_added']} albums, {disco_stats['tracks_added']} tracks"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Auto-discography sync failed for {artist.name}: {e}"
                    )

            logger.info(
                f"Deezer auto-discography sync complete: {stats['discography_synced']}/{len(newly_created_artists)} artists"
            )

        return all_artists, stats

    # Hey future me - merge Deezer data into existing artist!
    # When same artist is followed on both Spotify AND Deezer, we don't create
    # duplicate - we ADD the deezer_id to the existing artist record.
    async def _merge_deezer_to_existing(self, artist_dto: "ArtistDTO") -> None:
        """Merge Deezer artist data into existing library entry.

        When user follows same artist on multiple providers, we add the
        service-specific IDs to the existing record instead of creating duplicate.

        Args:
            artist_dto: ArtistDTO from Deezer with deezer_id
        """
        from soulspot.domain.entities import ArtistSource

        if not artist_dto.deezer_id:
            return

        # Find existing artist by name
        existing = await self.artist_repo.get_by_name(artist_dto.name)
        if not existing:
            return

        # Add deezer_id if not already set
        if not existing.deezer_id:
            existing.deezer_id = artist_dto.deezer_id

            # If already has spotify_uri, upgrade to hybrid
            if existing.spotify_uri:
                existing.source = ArtistSource.HYBRID

            await self.artist_repo.update(existing)
            logger.debug(
                f"Merged Deezer ID {artist_dto.deezer_id} to existing artist {existing.name}"
            )

    # Yo future me, REFACTORED to process ArtistDTO from SpotifyPlugin!
    # This processes a single artist DTO and creates/updates the Artist entity in DB.
    # We use spotify_uri as unique identifier (better than name since artists can share names).
    # If artist exists, we update the name, genres, image_url AND source.
    # Source is now CRITICAL for unified Music Manager:
    # - If artist exists with source='local', upgrade to source='hybrid' (local + Spotify/Deezer)
    # - If artist doesn't exist, create with source='spotify' or 'deezer'
    # The DTO already has: name, spotify_id/deezer_id, spotify_uri, image_url, genres.
    # Returns tuple (artist, was_created) so caller can track stats properly.
    #
    # MULTI-PROVIDER (Nov 2025):
    # Now handles both Spotify and Deezer DTOs. The source parameter determines
    # which provider the artist came from. Deduplication works across providers.
    #
    # REFACTORED (Nov 2025):
    # Now uses ProviderMappingService for ID lookup. The mapping service does:
    # 1. Lookup by spotify_uri, deezer_id, or name
    # 2. Create new artist if not found
    # Business logic (source upgrade, metadata merge) stays HERE.
    async def _process_artist_dto(
        self, artist_dto: "ArtistDTO", source: str = "spotify"
    ) -> tuple[Artist, bool]:
        """Process a single artist from SpotifyPlugin or DeezerPlugin (ArtistDTO).

        Hey future me - REFACTORED to use ProviderMappingService!
        The mapping service handles ID lookup and creation.
        This method handles the business logic: source upgrade, metadata merge.

        Args:
            artist_dto: ArtistDTO from plugin
            source: "spotify" or "deezer" - determines source field and ID handling

        Returns:
            Tuple of (Artist entity, was_created boolean)

        Raises:
            ValueError: If artist data is invalid (missing required fields)
        """
        from soulspot.domain.entities import ArtistSource

        # Validate based on source
        if source == "spotify":
            if not artist_dto.spotify_id or not artist_dto.name:
                raise ValidationError(
                    "Invalid Spotify artist DTO: missing spotify_id or name"
                )
        elif source == "deezer":
            if not artist_dto.deezer_id or not artist_dto.name:
                raise ValidationError(
                    "Invalid Deezer artist DTO: missing deezer_id or name"
                )
        else:
            raise ValidationError(f"Unknown source: {source}")

        # STEP 1: Use ProviderMappingService to lookup/create
        # This handles: spotify_uri lookup, deezer_id lookup, name fallback, creation
        internal_id, was_created = await self._mapping_service.get_or_create_artist(
            artist_dto, source=source
        )

        # STEP 2: Get the full Artist entity
        artist = await self.artist_repo.get_by_id(ArtistId(internal_id))
        if not artist:
            # Should not happen, but handle gracefully
            raise EntityNotFoundError(f"Artist not found after create: {internal_id}")

        # STEP 3: Business Logic - Update existing artist if not newly created
        if not was_created:
            needs_update = False
            name = artist_dto.name
            genres = artist_dto.genres or []
            # DTO now uses ImageRef, extract URL
            image_url = artist_dto.image.url

            # Add service-specific ID if missing (merge across providers)
            if source == "spotify" and artist_dto.spotify_uri:
                spotify_uri = SpotifyUri.from_string(
                    artist_dto.spotify_uri or f"spotify:artist:{artist_dto.spotify_id}"
                )
                if not artist.spotify_uri:
                    artist.spotify_uri = spotify_uri
                    needs_update = True
                    logger.info(f"Added spotify_uri to artist '{name}'")
            elif source == "deezer" and artist_dto.deezer_id:
                if not artist.deezer_id:
                    artist.deezer_id = artist_dto.deezer_id
                    needs_update = True
                    logger.info(f"Added deezer_id to artist '{name}'")

            if artist.name != name:
                artist.update_name(name)
                needs_update = True
            if artist.genres != genres and genres:
                artist.genres = genres
                artist.metadata_sources["genres"] = source
                needs_update = True
            # Entity now uses ImageRef for image
            if artist.image.url != image_url and image_url:
                from soulspot.domain.value_objects import ImageRef

                artist.image = ImageRef(url=image_url)
                artist.metadata_sources["image"] = source
                needs_update = True

            # Hey future me - UPGRADE source if artist was local-only!
            if artist.source == ArtistSource.LOCAL:
                artist.source = ArtistSource.HYBRID
                needs_update = True
                logger.info(
                    f"Upgraded artist '{name}' from LOCAL to HYBRID (local + {source})"
                )

            if needs_update:
                await self.artist_repo.update(artist)
                logger.debug(f"Updated artist: {name} (source: {source})")

        return artist, was_created

    async def sync_artist_albums(
        self,
        artist_id: str,
    ) -> dict[str, int]:
        """Sync albums for an artist into unified albums table with MULTI-PROVIDER support.

        Hey future me - REFACTORED with DEEZER FALLBACK!
        This syncs albums into soulspot_albums table (unified)!
        Unlike SpotifySyncService which uses separate spotify_albums table, this method
        puts albums directly into the unified music library so they appear alongside
        local albums. This is key for the Music Manager concept!

        MULTI-PROVIDER (Nov 2025):
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!) when Spotify fails
        3. Deezer albums are searched by artist name, then fetched

        WHY fallback?
        - Users without Spotify OAuth can still see artist discographies
        - Deezer's public API is reliable for artist album lookups

        No more access_token param - plugin handles auth internally.

        Args:
            artist_id: Our internal artist ID (not Spotify ID)

        Returns:
            Dict with sync stats (total, added, skipped, source)
        """
        from soulspot.domain.ports.plugin import PluginCapability
        from soulspot.infrastructure.persistence.repositories import AlbumRepository

        stats: dict[str, int | str] = {
            "total": 0,
            "added": 0,
            "skipped": 0,
            "source": "none",
        }

        # Get artist by ID
        artist = await self.artist_repo.get(artist_id)
        if not artist:
            logger.warning(
                LogMessages.file_operation_failed(
                    operation="artist_lookup",
                    path=str(artist_id),
                    reason="Artist not found",
                    hint="Sync followed artists first to populate artist data",
                ).format()
            )
            return stats  # type: ignore[return-value]

        # Use spotify_id property (extracts ID from SpotifyUri value object)
        spotify_artist_id = artist.spotify_id

        albums_dtos = []
        source = "none"

        # 1. Try Spotify first (if we have spotify_plugin, spotify_uri AND auth)
        # Hey future me - spotify_plugin can be None if user isn't logged in!
        if spotify_artist_id and self.spotify_plugin:
            try:
                if self.spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
                    response = await self.spotify_plugin.get_artist_albums(
                        artist_id=spotify_artist_id,
                        limit=50,
                    )
                    albums_dtos = response.items
                    source = "spotify"
                    logger.debug(
                        f"Fetched {len(albums_dtos)} albums from Spotify for {artist.name}"
                    )
            except Exception as e:
                logger.warning(
                    f"Spotify album fetch failed for {artist.name}: {e}. "
                    "Trying Deezer fallback..."
                )

        # 2. Fallback to Deezer (NO AUTH NEEDED!)
        # Hey future me - SMART LOOKUP! Pass the stored deezer_id if we have it,
        # so we don't need to search by name every time. This is the "Übersetzer"!
        if not albums_dtos and self._deezer_plugin and artist.name:
            try:
                albums_dtos = await self._fetch_albums_from_deezer(
                    artist_name=artist.name,
                    deezer_artist_id=artist.deezer_id,  # Pass stored ID!
                )
                if albums_dtos:
                    source = "deezer"
                    logger.info(
                        f"Fetched {len(albums_dtos)} albums from Deezer fallback "
                        f"for {artist.name} (deezer_id={artist.deezer_id})"
                    )
            except Exception as e:
                logger.warning(f"Deezer fallback also failed for {artist.name}: {e}")

        if not albums_dtos:
            logger.warning(
                LogMessages.sync_failed(
                    sync_type="artist_albums_fetch",
                    reason=f"No albums found for artist {artist.name}",
                    hint="Neither Spotify nor Deezer returned albums",
                ).format()
            )
            return stats  # type: ignore[return-value]

        stats["source"] = source
        album_repo = AlbumRepository(self._session)

        # Track seen albums by normalized key to avoid duplicates
        # Hey future me - CROSS-SERVICE DEDUPLICATION!
        # The same album from Spotify and Deezer have DIFFERENT IDs but SAME:
        # - Artist name + Album title + Release year
        # We normalize (lowercase, strip whitespace) to match fuzzy
        seen_keys: set[str] = set()

        # Process each album (now AlbumDTO from either source!)
        for album_dto in albums_dtos:
            stats["total"] += 1

            # Create normalized key for deduplication
            # Format: "artist_name|album_title|release_year"
            norm_key = _normalize_album_key(
                album_dto.artist_name or artist.name,
                album_dto.title,
                album_dto.release_year,
            )

            # Skip if we've already seen this album (by normalized key)
            if norm_key in seen_keys:
                stats["skipped"] += 1
                logger.debug(f"Skipping duplicate (by key): {album_dto.title}")
                continue
            seen_keys.add(norm_key)

            # Handle Spotify vs Deezer albums differently
            # Hey future me - Deezer albums DON'T have Spotify URIs!
            # SpotifyUri validates "spotify:" prefix, so we can't create pseudo-URIs.
            spotify_uri: SpotifyUri | None = None

            if album_dto.spotify_id:
                # Spotify album - create proper SpotifyUri
                spotify_uri = SpotifyUri.from_string(
                    album_dto.spotify_uri or f"spotify:album:{album_dto.spotify_id}"
                )
                # Check if album already exists by Spotify URI
                existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
                if existing_album:
                    stats["skipped"] += 1
                    continue
            # For Deezer albums: NO SpotifyUri, skip URI-based dedup check

            # Additional check: Search by title + artist to catch cross-service duplicates
            # Hey future me - this catches albums that exist with different source URI
            existing_by_title = await album_repo.get_by_title_and_artist(
                title=album_dto.title,
                artist_id=artist.id,
            )
            if existing_by_title:
                stats["skipped"] += 1
                logger.debug(f"Skipping duplicate (by title/artist): {album_dto.title}")
                continue

            # Create new album using ProviderMappingService
            # Hey future me - REFACTORED to use central ID generation
            album_id, was_created = await self._mapping_service.get_or_create_album(
                album_dto,
                artist_internal_id=str(artist.id.value),
                source=source,
            )

            if was_created:
                stats["added"] += 1
                logger.debug(
                    f"Added album: {album_dto.title} ({album_dto.release_year}) "
                    f"source={source}"
                )
            else:
                stats["skipped"] += 1

        logger.info(
            f"Synced {stats['added']} new albums for {artist.name} "
            f"({stats['skipped']} already existed, source={source})"
        )
        return stats  # type: ignore[return-value]

    async def _fetch_albums_from_deezer(
        self,
        artist_name: str,
        deezer_artist_id: str | None = None,
    ) -> list:
        """Fetch artist albums from Deezer as fallback.

        Hey future me - Deezer uses different artist IDs!
        Strategy:
        1. If we HAVE deezer_id → use it directly (FASTER, MORE ACCURATE!)
        2. If NO deezer_id → Search Deezer for the artist by name (fallback)
        3. Fetch albums using the resolved Deezer artist ID

        NO AUTH NEEDED for any of this!

        Args:
            artist_name: Artist name to search on Deezer (fallback)
            deezer_artist_id: Deezer artist ID if we have it (preferred!)

        Returns:
            list[AlbumDTO] from Deezer
        """
        if not self._deezer_plugin:
            return []

        try:
            # SMART LOOKUP: Use stored deezer_id if available!
            # Hey future me - this is the "Übersetzer" - we TRANSLATE our stored ID
            # to the correct Deezer API call, instead of searching by name every time!
            resolved_deezer_id = deezer_artist_id

            if not resolved_deezer_id:
                # Fallback: Search for artist on Deezer by name
                logger.debug(f"No Deezer ID stored for '{artist_name}', searching...")
                search_result = await self._deezer_plugin.search_artists(
                    query=artist_name, limit=5
                )

                if not search_result.items:
                    logger.debug(f"No Deezer artist found for '{artist_name}'")
                    return []

                # Take the first match (usually best result)
                deezer_artist = search_result.items[0]
                resolved_deezer_id = deezer_artist.deezer_id

                if not resolved_deezer_id:
                    return []

                logger.debug(
                    f"Mapped artist '{artist_name}' to Deezer ID {resolved_deezer_id} "
                    f"({deezer_artist.name})"
                )
            else:
                logger.debug(
                    f"Using stored Deezer ID {resolved_deezer_id} for '{artist_name}'"
                )

            # Fetch albums from Deezer (NO AUTH NEEDED!)
            albums_response = await self._deezer_plugin.get_artist_albums(
                artist_id=resolved_deezer_id,
                limit=50,
            )

            return albums_response.items if albums_response.items else []

        except Exception as e:
            logger.warning(f"Deezer artist albums lookup failed: {e}")
            return []

    async def sync_artist_discography_complete(
        self,
        artist_id: str,
        include_tracks: bool = True,
    ) -> dict[str, Any]:
        """Sync complete discography for an artist: Albums AND Tracks.

        Hey future me - THIS IS THE COMPLETE SYNC METHOD!
        Fetches Albums from providers AND for each Album fetches ALL Tracks.
        Everything gets stored in DB so the UI can load from DB only.

        MULTI-PROVIDER (Dec 2025):
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!)

        Flow:
        1. Get artist from DB
        2. Fetch all albums from provider(s)
        3. For each album: fetch tracks from provider
        4. Store albums in soulspot_albums
        5. Store tracks in soulspot_tracks with album_id FK

        Args:
            artist_id: Our internal artist ID
            include_tracks: Whether to also sync tracks (default: True)

        Returns:
            Dict with sync stats:
            - albums_total, albums_added, albums_skipped
            - tracks_total, tracks_added, tracks_skipped
            - source: "spotify", "deezer", or "none"
        """
        from uuid import uuid4

        from soulspot.domain.entities import Album, Track
        from soulspot.domain.ports.plugin import PluginCapability
        from soulspot.domain.value_objects import AlbumId, ArtistId, ImageRef, TrackId
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            TrackRepository,
        )

        stats: dict[str, Any] = {
            "albums_total": 0,
            "albums_added": 0,
            "albums_skipped": 0,
            "tracks_total": 0,
            "tracks_added": 0,
            "tracks_skipped": 0,
            "source": "none",
        }

        # Get artist
        artist = await self.artist_repo.get(artist_id)
        if not artist:
            logger.warning(f"Artist not found: {artist_id}")
            return stats

        spotify_artist_id = artist.spotify_id
        albums_dtos: list[Any] = []
        source = "none"

        # 1. Try Spotify first
        if spotify_artist_id and self.spotify_plugin:
            try:
                if self.spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
                    response = await self.spotify_plugin.get_artist_albums(
                        artist_id=spotify_artist_id,
                        limit=50,
                    )
                    albums_dtos = response.items
                    source = "spotify"
                    logger.info(f"Fetched {len(albums_dtos)} albums from Spotify for {artist.name}")
            except Exception as e:
                logger.warning(f"Spotify album fetch failed for {artist.name}: {e}")

        # 2. Fallback to Deezer
        if not albums_dtos and self._deezer_plugin and artist.name:
            try:
                albums_dtos = await self._fetch_albums_from_deezer(
                    artist_name=artist.name,
                    deezer_artist_id=artist.deezer_id,
                )
                if albums_dtos:
                    source = "deezer"
                    logger.info(f"Fetched {len(albums_dtos)} albums from Deezer for {artist.name}")
            except Exception as e:
                logger.warning(f"Deezer album fetch failed for {artist.name}: {e}")

        if not albums_dtos:
            logger.warning(f"No albums found for artist {artist.name}")
            return stats

        stats["source"] = source
        album_repo = AlbumRepository(self._session)
        track_repo = TrackRepository(self._session)

        # Track seen albums and tracks to avoid duplicates
        seen_album_keys: set[str] = set()
        seen_track_keys: set[str] = set()

        for album_dto in albums_dtos:
            stats["albums_total"] += 1

            # Normalize album key for deduplication
            norm_key = _normalize_album_key(
                album_dto.artist_name or artist.name,
                album_dto.title,
                album_dto.release_year,
            )

            if norm_key in seen_album_keys:
                stats["albums_skipped"] += 1
                continue
            seen_album_keys.add(norm_key)

            # Check if album already exists
            # Hey future me - CRITICAL: Check by deezer_id FIRST if available!
            # This prevents UNIQUE constraint errors when album was already synced.
            existing_album = None

            # 1. Check by Deezer ID (most specific)
            if album_dto.deezer_id:
                existing_album = await album_repo.get_by_deezer_id(album_dto.deezer_id)

            # 2. Check by Spotify URI
            if not existing_album and album_dto.spotify_uri:
                try:
                    spotify_uri = SpotifyUri.from_string(album_dto.spotify_uri)
                    existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
                except ValueError:
                    pass
            elif not existing_album and album_dto.spotify_id:
                try:
                    spotify_uri = SpotifyUri.from_string(f"spotify:album:{album_dto.spotify_id}")
                    existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
                except ValueError:
                    pass

            # 3. Fallback to title+artist (least specific)
            if not existing_album:
                existing_album = await album_repo.get_by_title_and_artist(
                    title=album_dto.title,
                    artist_id=artist.id,
                )

            if existing_album:
                # Album exists - use its ID for track linking
                album_id = existing_album.id
                stats["albums_skipped"] += 1
            else:
                # Create new album
                spotify_uri = None
                if album_dto.spotify_uri:
                    spotify_uri = SpotifyUri.from_string(album_dto.spotify_uri)
                elif album_dto.spotify_id:
                    spotify_uri = SpotifyUri.from_string(f"spotify:album:{album_dto.spotify_id}")

                album = Album(
                    id=AlbumId(str(uuid4())),
                    title=album_dto.title,
                    artist_id=artist.id,
                    source=source,
                    release_year=album_dto.release_year,
                    release_date=album_dto.release_date,
                    spotify_uri=spotify_uri,
                    deezer_id=album_dto.deezer_id,
                    total_tracks=album_dto.total_tracks,
                    cover=ImageRef(url=album_dto.cover.url if album_dto.cover else None),
                    primary_type=(album_dto.album_type or "album").title(),
                )
                await album_repo.add(album)
                album_id = album.id
                stats["albums_added"] += 1
                logger.debug(f"Added album: {album_dto.title}")

            # Now fetch tracks for this album (if enabled)
            if include_tracks:
                track_dtos = await self._fetch_album_tracks(
                    album_dto, source, spotify_artist_id, artist.deezer_id
                )

                for track_dto in track_dtos:
                    stats["tracks_total"] += 1

                    # Normalize track key for deduplication
                    track_key = f"{album_dto.title.lower()}|{track_dto.title.lower()}|{track_dto.track_number or 0}"

                    if track_key in seen_track_keys:
                        stats["tracks_skipped"] += 1
                        continue
                    seen_track_keys.add(track_key)

                    # Check if track exists (by ISRC or title+album)
                    existing_track = None
                    if track_dto.isrc:
                        existing_track = await track_repo.get_by_isrc(track_dto.isrc)

                    if not existing_track:
                        existing_track = await track_repo.get_by_title_and_album(
                            title=track_dto.title,
                            album_id=album_id,
                        )

                    if existing_track:
                        stats["tracks_skipped"] += 1
                        continue

                    # Create new track
                    spotify_track_uri = None
                    if track_dto.spotify_uri:
                        spotify_track_uri = SpotifyUri.from_string(track_dto.spotify_uri)
                    elif track_dto.spotify_id:
                        spotify_track_uri = SpotifyUri.from_string(f"spotify:track:{track_dto.spotify_id}")

                    track = Track(
                        id=TrackId(str(uuid4())),
                        title=track_dto.title,
                        artist_id=artist.id,
                        album_id=album_id,
                        duration_ms=track_dto.duration_ms or 0,
                        track_number=track_dto.track_number,
                        disc_number=track_dto.disc_number or 1,
                        spotify_uri=spotify_track_uri,
                        deezer_id=track_dto.deezer_id,
                        isrc=track_dto.isrc,
                    )
                    await track_repo.add(track)
                    stats["tracks_added"] += 1

        logger.info(
            f"Complete discography sync for {artist.name}: "
            f"Albums {stats['albums_added']}/{stats['albums_total']}, "
            f"Tracks {stats['tracks_added']}/{stats['tracks_total']} (source={source})"
        )
        return stats

    async def _fetch_album_tracks(
        self,
        album_dto: Any,
        source: str,
        spotify_artist_id: str | None,
        deezer_artist_id: str | None,
    ) -> list[Any]:
        """Fetch tracks for an album from the appropriate provider.

        Hey future me - this is a helper for sync_artist_discography_complete!
        Uses the same provider that gave us the album.
        Both Spotify and Deezer return PaginatedResponse with .items!
        """
        from soulspot.domain.ports.plugin import PluginCapability

        try:
            if source == "spotify" and self.spotify_plugin and album_dto.spotify_id:
                if self.spotify_plugin.can_use(PluginCapability.GET_ALBUM_TRACKS):
                    response = await self.spotify_plugin.get_album_tracks(
                        album_id=album_dto.spotify_id,
                        limit=50,
                    )
                    # PaginatedResponse has .items
                    return response.items if hasattr(response, 'items') else []
            elif source == "deezer" and self._deezer_plugin and album_dto.deezer_id:
                # Deezer also returns PaginatedResponse!
                response = await self._deezer_plugin.get_album_tracks(
                    album_id=album_dto.deezer_id,
                )
                return response.items if hasattr(response, 'items') else []
        except Exception as e:
            logger.warning(f"Failed to fetch tracks for album {album_dto.title}: {e}")

        return []

    # Hey future me, REFACTORED to use SpotifyPlugin!
    # This is a simple utility to get a preview of followed artists WITHOUT syncing to DB!
    # Useful for "show me who I follow on Spotify" without persisting data.
    # Returns list of ArtistDTOs for quick display.
    async def preview_followed_artists(self, limit: int = 50) -> list["ArtistDTO"]:
        """Get a preview of followed artists without syncing to database.

        Hey future me - refactored to use SpotifyPlugin!
        No more access_token param - plugin handles auth internally.
        Returns ArtistDTOs instead of raw Spotify JSON.

        IMPORTANT: Requires spotify_plugin to be configured!

        Args:
            limit: Max artists to fetch (1-50)

        Returns:
            List of ArtistDTOs from Spotify

        Raises:
            ValidationError: If spotify_plugin is not configured
        """
        if not self.spotify_plugin:
            raise ValidationError(
                "Spotify plugin required for preview_followed_artists"
            )

        response = await self.spotify_plugin.get_followed_artists(
            limit=min(limit, 50),
        )
        return response.items
