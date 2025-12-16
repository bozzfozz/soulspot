# AI-Model: Copilot
"""Service for syncing and managing individual songs (singles) from followed artists.

Hey future me - REFACTORED to use SpotifyPlugin with DEEZER FALLBACK!
The plugin handles token management internally, no more access_token parameter juggling.

MULTI-PROVIDER SUPPORT (Nov 2025):
- Spotify is PRIMARY for top tracks (requires OAuth)
- Deezer is FALLBACK (NO AUTH NEEDED!)
- When Spotify fails/not authenticated, we try Deezer

This service handles syncing songs that are NOT part of albums from artists the user follows
on Spotify. It fetches "top tracks" from Spotify (most popular songs) and stores them as
tracks without album association.

The flow is:
1. Get followed artists from DB (already synced via FollowedArtistsService)
2. For each artist, fetch their top tracks from Spotify/Deezer API via Plugin
3. Plugin returns TrackDTOs (already converted from raw JSON!)
4. Filter out tracks that are part of albums (we only want singles)
5. Create/update Track entities in our DB
6. Return sync statistics

GOTCHA: Spotify's "top tracks" endpoint returns the artist's most popular songs,
which may include album tracks. We filter these by checking album_type in the DTO.
"""

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.observability.log_messages import LogMessages

from soulspot.domain.entities import Track
from soulspot.domain.exceptions import (
    ConfigurationError,
    EntityNotFoundError,
    BusinessRuleViolation,
)
from soulspot.domain.value_objects import ArtistId, SpotifyUri, TrackId
from soulspot.infrastructure.persistence.repositories import (
    ArtistRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.domain.dtos import TrackDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class ArtistSongsService:
    """Service for syncing individual songs from followed artists.

    Hey future me - REFACTORED to use SpotifyPlugin WITH Deezer fallback!
    This service syncs popular songs/singles from artists in the database.
    Unlike FollowedArtistsService which syncs artist metadata, this syncs
    the actual TRACKS (songs). Focuses on singles and popular tracks that
    aren't part of full albums, giving users quick access to hit songs.

    MULTI-PROVIDER (Nov 2025):
    - Spotify: Primary for top tracks (requires OAuth)
    - Deezer: Fallback (NO AUTH NEEDED for artist top tracks!)

    The spotify_plugin is optional - only required for sync operations.
    Read and delete operations work without it.
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize artist songs service.

        Hey future me - refactored with Deezer fallback!
        The plugin handles token management internally, no more access_token juggling.

        Args:
            session: Database session for repositories
            spotify_plugin: SpotifyPlugin for API calls (optional, only needed for sync)
            deezer_plugin: Optional DeezerPlugin for fallback top tracks (NO AUTH!)
        """
        self.session = session
        self.artist_repo = ArtistRepository(session)
        self.track_repo = TrackRepository(session)
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin
        
        # Hey future me - ProviderMappingService for centralized ID management!
        # Used for track creation from DTOs (Spotify/Deezer).
        from soulspot.application.services.provider_mapping_service import (
            ProviderMappingService,
        )
        self._mapping_service = ProviderMappingService(session)

    @property
    def spotify_plugin(self) -> "SpotifyPlugin":
        """Get Spotify plugin, raising error if not configured.

        Returns:
            SpotifyPlugin instance

        Raises:
            ValueError: If spotify_plugin was not provided during initialization
        """
        if self._spotify_plugin is None:
            raise ConfigurationError(
                "SpotifyPlugin is required for this operation. "
                "Initialize ArtistSongsService with spotify_plugin parameter."
            )
        return self._spotify_plugin

    # Main sync method for syncing songs from a single artist with MULTI-PROVIDER support.
    # Fetches top tracks from Spotify/Deezer (returns TrackDTOs), filters for singles,
    # and creates/updates them in DB. Returns the tracks plus stats.
    async def sync_artist_songs(
        self, artist_id: ArtistId, market: str = "US"
    ) -> tuple[list[Track], dict[str, int]]:
        """Sync songs from a single artist with MULTI-PROVIDER fallback.

        Hey future me - refactored with Deezer fallback!
        No more access_token param - plugin handles auth internally.
        
        MULTI-PROVIDER (Nov 2025):
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!) when Spotify fails

        Fetches the artist's top tracks and stores non-album
        tracks (singles) in the database. Existing tracks are updated,
        new ones are created.

        Args:
            artist_id: Artist ID to sync songs for
            market: ISO 3166-1 alpha-2 country code (e.g., "US", "DE")

        Returns:
            Tuple of (list of Track entities, sync statistics dict)

        Raises:
            ValueError: If artist not found in database
        """
        from soulspot.domain.ports.plugin import PluginCapability
        
        stats: dict[str, int | str] = {
            "total_fetched": 0,
            "singles_found": 0,
            "created": 0,
            "updated": 0,
            "skipped_album_tracks": 0,
            "errors": 0,
            "source": "none",
        }

        # Verify artist exists in our DB
        artist = await self.artist_repo.get_by_id(artist_id)
        if not artist:
            raise EntityNotFoundError(f"Artist not found: {artist_id.value}")

        # Extract Spotify artist ID from URI if available
        spotify_artist_id = None
        if artist.spotify_uri:
            spotify_artist_id = str(artist.spotify_uri).split(":")[-1]

        synced_tracks: list[Track] = []
        track_dtos: list["TrackDTO"] = []
        source = "none"

        # 1. Try Spotify first (if we have spotify_uri AND plugin is authenticated)
        if spotify_artist_id and self._spotify_plugin:
            try:
                if self._spotify_plugin.can_use(PluginCapability.GET_ARTIST_TOP_TRACKS):
                    track_dtos = await self._spotify_plugin.get_artist_top_tracks(
                        artist_id=spotify_artist_id,
                        market=market,
                    )
                    source = "spotify"
                    logger.debug(
                        f"Fetched {len(track_dtos)} top tracks from Spotify for {artist.name}"
                    )
            except Exception as e:
                logger.warning(
                    f"Spotify top tracks failed for {artist.name}: {e}. "
                    "Trying Deezer fallback..."
                )

        # 2. Fallback to Deezer (NO AUTH NEEDED!)
        if not track_dtos and self._deezer_plugin and artist.name:
            try:
                track_dtos = await self._fetch_top_tracks_from_deezer(artist.name)
                if track_dtos:
                    source = "deezer"
                    logger.info(
                        f"Fetched {len(track_dtos)} top tracks from Deezer for {artist.name}"
                    )
            except Exception as e:
                logger.warning(f"Deezer fallback also failed for {artist.name}: {e}")

        if not track_dtos:
            logger.warning(
                LogMessages.sync_failed(
                    sync_type="artist_top_tracks_fetch",
                    reason=f"No top tracks found for artist {artist.name}",
                    hint="Neither Spotify nor Deezer returned tracks"
                ).format()
            )
            return synced_tracks, stats  # type: ignore[return-value]

        stats["total_fetched"] = len(track_dtos)
        stats["source"] = source
        logger.info(
            f"Fetched {len(track_dtos)} top tracks for artist {artist.name} "
            f"(source: {source})"
        )

        for track_dto in track_dtos:
            try:
                track, was_created, is_single = await self._process_track_dto(
                    track_dto, artist_id, source=source
                )
                if track:
                    synced_tracks.append(track)
                    if is_single:
                        stats["singles_found"] += 1
                    if was_created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                else:
                    stats["skipped_album_tracks"] += 1
            except Exception as e:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="track_processing",
                        reason=f"Failed to process track {track_dto.title}",
                        hint="Check track data validity and database constraints"
                    ).format(),
                    exc_info=e
                )
                stats["errors"] += 1

        logger.info(
            f"Artist songs sync for {artist.name}: {stats['total_fetched']} fetched, "
            f"{stats['singles_found']} singles, {stats['created']} created, "
            f"{stats['updated']} updated, {stats['skipped_album_tracks']} skipped "
            f"(source: {source})"
        )

        return synced_tracks, stats  # type: ignore[return-value]

    async def _fetch_top_tracks_from_deezer(self, artist_name: str) -> list["TrackDTO"]:
        """Fetch artist top tracks from Deezer as fallback.

        Hey future me - Deezer uses different artist IDs!
        Strategy:
        1. Search Deezer for the artist by name
        2. Get the first match's Deezer ID
        3. Fetch top tracks using Deezer artist ID
        
        NO AUTH NEEDED for any of this!

        Args:
            artist_name: Artist name to search on Deezer

        Returns:
            list[TrackDTO] from Deezer
        """
        if not self._deezer_plugin:
            return []

        try:
            # Search for artist on Deezer
            search_result = await self._deezer_plugin.search_artists(
                query=artist_name, limit=5
            )

            if not search_result.items:
                logger.debug(f"No Deezer artist found for '{artist_name}'")
                return []

            # Take the first match
            deezer_artist = search_result.items[0]
            deezer_artist_id = deezer_artist.deezer_id

            if not deezer_artist_id:
                return []

            logger.debug(
                f"Mapped artist '{artist_name}' to Deezer ID {deezer_artist_id} "
                f"({deezer_artist.name})"
            )

            # Fetch top tracks from Deezer (NO AUTH NEEDED!)
            return await self._deezer_plugin.get_artist_top_tracks(
                artist_id=deezer_artist_id,
            )

        except Exception as e:
            logger.warning(f"Deezer artist top tracks lookup failed: {e}")
            return []

    # Bulk sync operation for all followed artists in DB using SpotifyPlugin.
    # Iterates through artists and syncs their songs. Can take a while for
    # users following many artists. Consider adding progress callbacks for UI.
    async def sync_all_artists_songs(
        self, market: str = "US", limit: int = 100
    ) -> tuple[list[Track], dict[str, int]]:
        """Sync songs from all followed artists in the database via SpotifyPlugin.

        Hey future me - refactored to use SpotifyPlugin!
        No more access_token param - plugin handles auth internally.

        Iterates through all artists in DB and syncs their top tracks.
        This is a bulk operation and may take time for many artists.

        Args:
            market: ISO 3166-1 alpha-2 country code
            limit: Maximum number of artists to process

        Returns:
            Tuple of (list of all synced Track entities, aggregate statistics)
        """
        aggregate_stats = {
            "artists_processed": 0,
            "total_fetched": 0,
            "singles_found": 0,
            "created": 0,
            "updated": 0,
            "skipped_album_tracks": 0,
            "errors": 0,
            "artist_errors": 0,
        }

        all_tracks: list[Track] = []

        # Get all artists from DB
        artists = await self.artist_repo.list_all(limit=limit)
        logger.info(f"Starting song sync for {len(artists)} artists")

        for artist in artists:
            try:
                tracks, stats = await self.sync_artist_songs(
                    artist_id=artist.id,
                    market=market,
                )
                all_tracks.extend(tracks)
                aggregate_stats["artists_processed"] += 1
                aggregate_stats["total_fetched"] += stats["total_fetched"]
                aggregate_stats["singles_found"] += stats["singles_found"]
                aggregate_stats["created"] += stats["created"]
                aggregate_stats["updated"] += stats["updated"]
                aggregate_stats["skipped_album_tracks"] += stats["skipped_album_tracks"]
                aggregate_stats["errors"] += stats["errors"]
            except Exception as e:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="artist_songs_bulk_sync",
                        reason=f"Failed to sync songs for artist {artist.name}",
                        hint="Check artist Spotify URI and API connectivity"
                    ).format(),
                    exc_info=e
                )
                aggregate_stats["artist_errors"] += 1

        logger.info(
            f"Bulk song sync complete: {aggregate_stats['artists_processed']} artists, "
            f"{aggregate_stats['created']} tracks created, "
            f"{aggregate_stats['updated']} tracks updated"
        )

        return all_tracks, aggregate_stats

    # Process a single track from SpotifyPlugin or DeezerPlugin (TrackDTO).
    # Checks if it already exists (by spotify_uri OR ISRC OR title+artist), then creates or updates.
    # Returns (track, was_created, is_single) - is_single helps with stats.
    #
    # MULTI-PROVIDER DEDUPLICATION (Nov 2025):
    # Deezer tracks have different IDs than Spotify! We use "deezer:track:123" prefix.
    # Check order: 1) Spotify URI 2) ISRC 3) Title+Artist (case-insensitive)
    async def _process_track_dto(
        self, track_dto: "TrackDTO", artist_id: ArtistId, source: str = "spotify"
    ) -> tuple[Track | None, bool, bool]:
        """Process a single track from SpotifyPlugin or DeezerPlugin (TrackDTO).

        Hey future me - refactored with MULTI-PROVIDER deduplication!
        Now handles both Spotify and Deezer tracks, with proper dedup to
        prevent duplicate entries when same track from different sources.

        DEDUPLICATION ORDER:
        1. Check by Spotify/Deezer URI (exact match)
        2. Check by ISRC (global standard identifier)
        3. Check by title+artist name (case-insensitive fallback)

        Args:
            track_dto: TrackDTO from SpotifyPlugin or DeezerPlugin
            artist_id: Artist ID to associate track with
            source: "spotify" or "deezer" - determines URI prefix

        Returns:
            Tuple of (Track entity or None, was_created boolean, is_single boolean)
        """
        # Deezer tracks have deezer_id instead of spotify_id
        track_id = track_dto.spotify_id or track_dto.deezer_id
        if not track_id or not track_dto.title:
            logger.warning(
                LogMessages.file_operation_failed(
                    operation="track_dto_validation",
                    path="<track_dto>",
                    reason="Invalid track DTO: missing id or title",
                    hint="Check API response format"
                ).format()
            )
            return None, False, False

        # Build URI with source prefix for cross-provider tracking
        # Spotify: "spotify:track:xxx", Deezer: "deezer:track:xxx"
        if source == "deezer" and track_dto.deezer_id:
            uri_string = f"deezer:track:{track_dto.deezer_id}"
        else:
            uri_string = track_dto.spotify_uri or f"spotify:track:{track_dto.spotify_id}"
        
        spotify_uri = SpotifyUri.from_string(uri_string)

        # Check if this is a single - no album reference means standalone single
        is_single = track_dto.album_spotify_id is None and track_dto.album_deezer_id is None

        # Extract ISRC from DTO
        isrc = track_dto.isrc

        # MULTI-PROVIDER DEDUPLICATION: Check in order of reliability
        existing_track = None
        
        # 1. Check by URI (exact match for same provider)
        existing_track = await self.track_repo.get_by_spotify_uri(spotify_uri)
        
        # 2. Check by ISRC (cross-provider dedup via global identifier)
        if not existing_track and isrc:
            existing_track = await self.track_repo.get_by_isrc(isrc)
            if existing_track:
                logger.debug(
                    f"Found existing track by ISRC: {track_dto.title} (ISRC: {isrc})"
                )
        
        # 3. Check by title + artist (case-insensitive, last resort)
        if not existing_track:
            artist = await self.artist_repo.get_by_id(artist_id)
            if artist and artist.name:
                existing_track = await self.track_repo.get_by_title_and_artist(
                    title=track_dto.title,
                    artist_name=artist.name,
                )
                if existing_track:
                    logger.debug(
                        f"Found existing track by title+artist: {track_dto.title} "
                        f"by {artist.name}"
                    )

        if existing_track:
            # Update existing track metadata if needed
            needs_update = False
            if existing_track.title != track_dto.title:
                existing_track.title = track_dto.title
                needs_update = True
            if existing_track.duration_ms != track_dto.duration_ms:
                existing_track.duration_ms = track_dto.duration_ms
                needs_update = True
            if existing_track.isrc != isrc and isrc:
                existing_track.isrc = isrc
                needs_update = True

            if needs_update:
                await self.track_repo.update(existing_track)
                logger.debug(f"Updated track: {track_dto.title}")

            return existing_track, False, is_single

        # Create new track using ProviderMappingService (centralized ID management)
        # Hey future me - REFACTORED! The mapping service handles get-or-create logic
        track_id, was_created = await self._mapping_service.get_or_create_track(
            track_dto,
            artist_internal_id=str(artist_id.value),
            album_internal_id=None,  # Store as single (no album)
            source="spotify" if track_dto.spotify_id else "deezer",
        )

        # Get the created track entity
        new_track = await self.track_repo.get_by_id(TrackId(track_id))
        if not new_track:
            raise EntityNotFoundError(f"Track not found after creation: {track_id}")

        logger.info(f"Created new track: {track_dto.title}")

        return new_track, True, is_single

    # Get all singles (non-album tracks) for an artist from DB.
    # This is a READ operation that doesn't touch Spotify API.
    async def get_artist_singles(self, artist_id: ArtistId) -> list[Track]:
        """Get all singles (non-album tracks) for an artist from the database.

        Args:
            artist_id: Artist ID to get singles for

        Returns:
            List of Track entities without album association
        """
        return await self.track_repo.get_singles_by_artist(artist_id)

    # Remove a single track from DB.
    # Checks that the track exists and belongs to the given artist before deleting.
    async def remove_song(self, track_id: TrackId, artist_id: ArtistId) -> bool:
        """Remove a song from the database.

        Args:
            track_id: Track ID to remove
            artist_id: Artist ID (for validation)

        Returns:
            True if track was removed

        Raises:
            ValueError: If track not found or doesn't belong to artist
        """
        track = await self.track_repo.get_by_id(track_id)

        if not track:
            raise EntityNotFoundError(f"Track not found: {track_id.value}")

        if track.artist_id != artist_id:
            raise BusinessRuleViolation(
                f"Track {track_id.value} does not belong to artist {artist_id.value}"
            )

        await self.track_repo.delete(track_id)
        logger.info(f"Removed track: {track.title} (id: {track_id.value})")

        return True

    # Bulk remove all singles for an artist. Use when user wants to
    # "clear" an artist's synced songs without deleting the artist itself.
    async def remove_all_artist_songs(self, artist_id: ArtistId) -> int:
        """Remove all singles (non-album tracks) for an artist.

        Args:
            artist_id: Artist ID to remove songs for

        Returns:
            Number of tracks removed
        """
        singles = await self.track_repo.get_singles_by_artist(artist_id)
        count = 0

        for track in singles:
            await self.track_repo.delete(track.id)
            count += 1

        logger.info(f"Removed {count} singles for artist {artist_id.value}")
        return count
