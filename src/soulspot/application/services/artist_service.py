# AI-Model: Copilot
"""Unified Artist Domain Service - Single source for ALL artist operations.

Hey future me - dies ist DER Service für alle Artist-Operationen!

MERGED aus (Jan 2025):
- followed_artists_service.py (1408 LOC) - Spotify/Deezer Sync
- artist_songs_service.py (566 LOC) - Top Tracks
- discography_service.py (266 LOC) - Discography Completeness

Pattern: Aggregate Root Service (DDD)
Lidarr-Vorbild: ArtistService + RefreshArtistService kombiniert

MULTI-PROVIDER SUPPORT:
- Spotify is PRIMARY (requires OAuth for most operations)
- Deezer is FALLBACK (NO AUTH NEEDED for public API!)
- All providers are aggregated into unified library

SECTIONS:
- === SYNC OPERATIONS === (from followed_artists_service)
- === ALBUM OPERATIONS === (from followed_artists_service)
- === TOP TRACKS === (from artist_songs_service)
- === DISCOGRAPHY === (from discography_service)
- === CRUD === (read/delete operations)
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Artist
from soulspot.domain.exceptions import (
    BusinessRuleViolation,
    ConfigurationError,
    EntityNotFoundError,
    ValidationError,
)
from soulspot.domain.value_objects import ArtistId, SpotifyUri
from soulspot.infrastructure.observability.log_messages import LogMessages
from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel
from soulspot.infrastructure.persistence.repositories import ArtistRepository

if TYPE_CHECKING:
    from soulspot.domain.dtos import ArtistDTO, TrackDTO
    from soulspot.domain.entities import Track
    from soulspot.domain.value_objects import TrackId
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _normalize_album_key(artist_name: str, title: str, release_year: int | None) -> str:
    """Create normalized key for album deduplication.

    Hey future me - this is CRITICAL for cross-service deduplication!
    Same album from Spotify and Deezer have different IDs but same:
    - Artist name (case-insensitive, stripped)
    - Album title (case-insensitive, stripped)
    - Release year (optional, helps distinguish remastered versions)

    Examples:
    - "pink floyd|the dark side of the moon|1973"
    - "aurora|all my demons greeting me as a friend|2016"

    GOTCHA: Different versions (remastered, deluxe) may have same name!
    We include release_year to help, but it's not perfect.
    """
    artist = (artist_name or "").strip().lower()
    album = (title or "").strip().lower()
    year = str(release_year) if release_year else "unknown"
    return f"{artist}|{album}|{year}"


# =============================================================================
# DATA CLASSES (from discography_service)
# =============================================================================


@dataclass
class DiscographyInfo:
    """Information about artist discography completeness.

    Hey future me - this was DiscographyService.DiscographyInfo,
    now lives here as a unified response type.
    """

    artist_id: str
    artist_name: str
    total_albums: int
    owned_albums: int
    missing_albums: list[dict[str, Any]]

    @property
    def completeness_percent(self) -> float:
        """Calculate completeness percentage."""
        return (
            (self.owned_albums / self.total_albums * 100)
            if self.total_albums > 0
            else 0.0
        )

    def is_complete(self) -> bool:
        """Check if discography is complete."""
        return self.owned_albums >= self.total_albums

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artist_id": self.artist_id,
            "artist_name": self.artist_name,
            "total_albums": self.total_albums,
            "owned_albums": self.owned_albums,
            "missing_albums_count": len(self.missing_albums),
            "missing_albums": self.missing_albums,
            "completeness_percent": round(self.completeness_percent, 2),
            "is_complete": self.is_complete(),
        }


# =============================================================================
# MAIN SERVICE CLASS
# =============================================================================


class ArtistService:
    """Unified Artist Domain Service.

    Hey future me - this is the SINGLE source for ALL artist operations!

    MERGED FROM:
    - FollowedArtistsService (sync followed artists from Spotify/Deezer)
    - ArtistSongsService (sync top tracks/singles)
    - DiscographyService (check discography completeness)

    MULTI-PROVIDER (Nov 2025):
    - Spotify: Primary for authenticated operations
    - Deezer: Fallback (NO AUTH NEEDED for public API!)

    Constructor takes BOTH plugins as OPTIONAL:
    - BOTH plugins: Full capability (Spotify primary, Deezer fallback)
    - Spotify only: Standard Spotify-only mode
    - Deezer only: Public API mode (no OAuth needed!)
    - Neither: Will fail on sync operations (but constructor succeeds)

    Args:
        session: Database session for Artist repository
        spotify_plugin: Optional SpotifyPlugin for API calls (handles auth internally)
        deezer_plugin: Optional DeezerPlugin for fallback (NO AUTH!)
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize unified artist service.

        Hey future me - plugins are OPTIONAL! Service works with any combination.
        """
        from soulspot.application.services.provider_mapping_service import (
            ProviderMappingService,
        )
        from soulspot.infrastructure.persistence.repositories import TrackRepository

        self._session = session
        self.artist_repo = ArtistRepository(session)
        self.track_repo = TrackRepository(session)
        self._spotify_plugin = spotify_plugin
        self._deezer_plugin = deezer_plugin
        self._mapping_service = ProviderMappingService(session)

    @property
    def spotify_plugin(self) -> "SpotifyPlugin":
        """Get Spotify plugin, raising error if not configured.

        Returns:
            SpotifyPlugin instance

        Raises:
            ConfigurationError: If spotify_plugin was not provided
        """
        if self._spotify_plugin is None:
            raise ConfigurationError(
                "SpotifyPlugin is required for this operation. "
                "Initialize ArtistService with spotify_plugin parameter."
            )
        return self._spotify_plugin

    @property
    def session(self) -> AsyncSession:
        """Get the database session."""
        return self._session

    # =========================================================================
    # === SYNC OPERATIONS (from followed_artists_service) ===
    # =========================================================================

    async def sync_followed_artists_spotify(
        self,
        auto_sync_discography: bool = True,
    ) -> tuple[list[Artist], dict[str, int]]:
        """Fetch all followed artists from Spotify and sync to database.

        Hey future me - SPOTIFY-specific sync method!
        Use sync_followed_artists_all_providers() for multi-provider sync.

        AUTO-DISCOGRAPHY (Jan 2025):
        New artists automatically get their discography synced (albums + tracks)
        so they're immediately useful in the library.

        Args:
            auto_sync_discography: If True, sync discography for newly created artists

        Returns:
            Tuple of (list of Artist entities, sync statistics dict)

        Raises:
            ValidationError: If spotify_plugin is not configured
        """
        if not self._spotify_plugin:
            raise ValidationError(
                "Spotify plugin required for followed artists sync. "
                "Use sync_artist_albums() for album-only sync via Deezer."
            )

        all_artists: list[Artist] = []
        newly_created_artists: list[Artist] = []
        after_cursor: str | None = None
        page = 1
        stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "discography_synced": 0,
            "source": "spotify",
        }

        while True:
            try:
                response = await self._spotify_plugin.get_followed_artists(
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

                for artist_dto in items:
                    try:
                        artist, was_created = await self._process_artist_dto(
                            artist_dto, source="spotify"
                        )
                        all_artists.append(artist)
                        stats["total_fetched"] += 1
                        if was_created:
                            stats["created"] += 1
                            newly_created_artists.append(artist)
                        else:
                            stats["updated"] += 1
                            # Check if existing artist has 0 albums → add to sync queue
                            from soulspot.infrastructure.persistence.repositories import (
                                AlbumRepository,
                            )

                            album_repo = AlbumRepository(self._session)
                            album_count = await album_repo.count_for_artist(artist.id)
                            if album_count == 0:
                                logger.info(
                                    f"🔄 Existing artist '{artist.name}' has 0 albums - "
                                    "adding to discography sync queue"
                                )
                                newly_created_artists.append(artist)
                                stats["albums_missing"] = (
                                    stats.get("albums_missing", 0) + 1
                                )
                    except Exception as e:
                        logger.error(
                            LogMessages.sync_failed(
                                sync_type="artist_processing",
                                reason=f"Failed to process artist {artist_dto.name}",
                                hint="Check database constraints and artist data",
                            ).format(),
                            exc_info=e,
                        )
                        stats["errors"] += 1

                if response.next_offset and items:
                    after_cursor = items[-1].spotify_id
                else:
                    break

                page += 1

            except Exception as e:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="followed_artists_pagination",
                        reason=f"Error fetching page {page}",
                        hint="Returning partial results",
                    ).format(),
                    exc_info=e,
                )
                break

        logger.info(
            f"Followed artists sync complete: {stats['total_fetched']} fetched, "
            f"{stats['created']} created, {stats['updated']} updated"
        )

        # AUTO-DISCOGRAPHY SYNC for new artists
        if auto_sync_discography and newly_created_artists:
            logger.info(
                f"🎵 Starting auto-discography sync for {len(newly_created_artists)} artists..."
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

        return all_artists, stats

    async def sync_followed_artists_all_providers(
        self,
    ) -> tuple[list[Artist], dict[str, Any]]:
        """Sync followed artists from ALL providers to unified library.

        Hey future me - this is the MULTI-PROVIDER version!
        Aggregates followed artists from Spotify AND Deezer (both require OAuth).

        Returns:
            Tuple of (list of all Artist entities, aggregated stats by provider)
        """
        from soulspot.domain.ports.plugin import PluginCapability

        all_artists: list[Artist] = []
        seen_names: set[str] = set()
        aggregate_stats: dict[str, Any] = {
            "providers": {},
            "total_fetched": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_errors": 0,
        }

        # 1. Sync from Spotify
        if self._spotify_plugin and self._spotify_plugin.can_use(
            PluginCapability.USER_FOLLOWED_ARTISTS
        ):
            try:
                spotify_artists, spotify_stats = (
                    await self.sync_followed_artists_spotify()
                )
                aggregate_stats["providers"]["spotify"] = spotify_stats
                aggregate_stats["total_fetched"] += spotify_stats["total_fetched"]
                aggregate_stats["total_created"] += spotify_stats["created"]
                aggregate_stats["total_updated"] += spotify_stats["updated"]
                aggregate_stats["total_errors"] += spotify_stats["errors"]

                for artist in spotify_artists:
                    seen_names.add(artist.name.lower().strip())
                    all_artists.append(artist)

            except Exception as e:
                logger.warning(f"Spotify followed artists sync failed: {e}")
                aggregate_stats["providers"]["spotify"] = {"error": str(e)}
        else:
            aggregate_stats["providers"]["spotify"] = {"skipped": "not_authenticated"}

        # 2. Sync from Deezer
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

            except Exception as e:
                logger.warning(f"Deezer followed artists sync failed: {e}")
                aggregate_stats["providers"]["deezer"] = {"error": str(e)}
        else:
            aggregate_stats["providers"]["deezer"] = {"skipped": "not_authenticated"}

        logger.info(
            f"Multi-provider sync complete: {aggregate_stats['total_fetched']} total"
        )

        return all_artists, aggregate_stats

    async def _sync_deezer_followed_artists(
        self,
        seen_names: set[str] | None = None,
        auto_sync_discography: bool = True,
    ) -> tuple[list[Artist], dict[str, int]]:
        """Sync followed artists from Deezer to unified library.

        Hey future me - Deezer requires OAuth for favorite artists!
        """
        if not self._deezer_plugin:
            return [], {"total_fetched": 0, "created": 0, "updated": 0, "errors": 0}

        all_artists: list[Artist] = []
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
                        name_key = artist_dto.name.lower().strip()
                        if name_key in seen_names:
                            stats["skipped_duplicate"] += 1
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
                            newly_created_artists.append(artist)
                        else:
                            stats["updated"] += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process Deezer artist {artist_dto.name}: {e}"
                        )
                        stats["errors"] += 1

                if response.next_offset:
                    after_cursor = str(response.next_offset)
                else:
                    break

            except Exception as e:
                logger.error(f"Deezer followed artists fetch failed: {e}")
                break

        # AUTO-DISCOGRAPHY SYNC for new Deezer artists
        if auto_sync_discography and newly_created_artists:
            logger.info(
                f"🎵 Starting auto-discography for {len(newly_created_artists)} Deezer artists..."
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
                        f"{disco_stats['albums_added']} albums"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Auto-discography failed for {artist.name}: {e}")

        return all_artists, stats

    async def _merge_deezer_to_existing(self, artist_dto: "ArtistDTO") -> None:
        """Merge Deezer artist data into existing library entry."""
        from soulspot.domain.entities import ArtistSource

        if not artist_dto.deezer_id:
            return

        existing = await self.artist_repo.get_by_name(artist_dto.name)
        if not existing:
            return

        if not existing.deezer_id:
            existing.deezer_id = artist_dto.deezer_id
            if existing.spotify_uri:
                existing.source = ArtistSource.HYBRID
            await self.artist_repo.update(existing)
            logger.debug(
                f"Merged Deezer ID {artist_dto.deezer_id} to existing artist {existing.name}"
            )

    async def _process_artist_dto(
        self, artist_dto: "ArtistDTO", source: str = "spotify"
    ) -> tuple[Artist, bool]:
        """Process a single artist from SpotifyPlugin or DeezerPlugin.

        Args:
            artist_dto: ArtistDTO from plugin
            source: "spotify" or "deezer"

        Returns:
            Tuple of (Artist entity, was_created boolean)
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

        # Use ProviderMappingService to lookup/create
        internal_id, was_created = await self._mapping_service.get_or_create_artist(
            artist_dto, source=source
        )

        artist = await self.artist_repo.get_by_id(ArtistId(internal_id))
        if not artist:
            raise EntityNotFoundError(f"Artist not found after create: {internal_id}")

        # Update existing artist if not newly created
        if not was_created:
            needs_update = False
            name = artist_dto.name
            genres = artist_dto.genres or []
            image_url = artist_dto.image.url

            # Add service-specific ID if missing
            if source == "spotify" and artist_dto.spotify_uri:
                spotify_uri = SpotifyUri.from_string(
                    artist_dto.spotify_uri or f"spotify:artist:{artist_dto.spotify_id}"
                )
                if not artist.spotify_uri:
                    artist.spotify_uri = spotify_uri
                    needs_update = True
            elif source == "deezer" and artist_dto.deezer_id:
                if not artist.deezer_id:
                    artist.deezer_id = artist_dto.deezer_id
                    needs_update = True

            if artist.name != name:
                artist.update_name(name)
                needs_update = True
            if artist.genres != genres and genres:
                artist.genres = genres
                artist.metadata_sources["genres"] = source
                needs_update = True
            if artist.image.url != image_url and image_url:
                from soulspot.domain.value_objects import ImageRef

                artist.image = ImageRef(url=image_url)
                artist.metadata_sources["image"] = source
                needs_update = True

            if artist.source == ArtistSource.LOCAL:
                artist.source = ArtistSource.HYBRID
                needs_update = True

            if needs_update:
                await self.artist_repo.update(artist)

        return artist, was_created

    async def preview_followed_artists(self, limit: int = 50) -> list["ArtistDTO"]:
        """Get a preview of followed artists without syncing to database.

        Args:
            limit: Max artists to fetch (1-50)

        Returns:
            List of ArtistDTOs from Spotify
        """
        if not self._spotify_plugin:
            raise ValidationError("Spotify plugin required for preview")

        response = await self._spotify_plugin.get_followed_artists(limit=min(limit, 50))
        return response.items

    # =========================================================================
    # === ALBUM OPERATIONS (from followed_artists_service) ===
    # =========================================================================

    async def sync_artist_albums(
        self,
        artist_id: str,
    ) -> dict[str, int]:
        """Sync albums for an artist with MULTI-PROVIDER support.

        MULTI-PROVIDER:
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!)

        Args:
            artist_id: Our internal artist ID

        Returns:
            Dict with sync stats (total, added, skipped, source)
        """
        from soulspot.domain.ports.plugin import PluginCapability
        from soulspot.infrastructure.persistence.repositories import AlbumRepository

        stats: dict[str, int | str] = {"total": 0, "added": 0, "skipped": 0, "source": "none"}

        artist = await self.artist_repo.get(artist_id)
        if not artist:
            logger.warning(f"Artist not found: {artist_id}")
            return stats  # type: ignore[return-value]

        spotify_artist_id = artist.spotify_id
        albums_dtos = []
        source = "none"

        # 1. Try Spotify first
        if spotify_artist_id and self._spotify_plugin:
            try:
                if self._spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
                    response = await self._spotify_plugin.get_artist_albums(
                        artist_id=spotify_artist_id, limit=50
                    )
                    albums_dtos = response.items
                    source = "spotify"
            except Exception as e:
                logger.warning(f"Spotify album fetch failed for {artist.name}: {e}")

        # 2. Fallback to Deezer
        if not albums_dtos and self._deezer_plugin and artist.name:
            try:
                albums_dtos = await self._fetch_albums_from_deezer(
                    artist_name=artist.name, deezer_artist_id=artist.deezer_id
                )
                if albums_dtos:
                    source = "deezer"
            except Exception as e:
                logger.warning(f"Deezer fallback failed for {artist.name}: {e}")

        if not albums_dtos:
            return stats  # type: ignore[return-value]

        stats["source"] = source
        album_repo = AlbumRepository(self._session)
        seen_keys: set[str] = set()

        for album_dto in albums_dtos:
            stats["total"] += 1

            norm_key = _normalize_album_key(
                album_dto.artist_name or artist.name,
                album_dto.title,
                album_dto.release_year,
            )

            if norm_key in seen_keys:
                stats["skipped"] += 1
                continue
            seen_keys.add(norm_key)

            # Check if album exists
            spotify_uri: SpotifyUri | None = None
            if album_dto.spotify_id:
                spotify_uri = SpotifyUri.from_string(
                    album_dto.spotify_uri or f"spotify:album:{album_dto.spotify_id}"
                )
                existing = await album_repo.get_by_spotify_uri(spotify_uri)
                if existing:
                    stats["skipped"] += 1
                    continue

            # Check by title+artist
            existing_by_title = await album_repo.get_by_title_and_artist(
                title=album_dto.title, artist_id=artist.id
            )
            if existing_by_title:
                stats["skipped"] += 1
                continue

            # Create new album
            album_id, was_created = await self._mapping_service.get_or_create_album(
                album_dto, artist_internal_id=str(artist.id.value), source=source
            )

            if was_created:
                stats["added"] += 1

        logger.info(f"Synced {stats['added']} new albums for {artist.name}")
        return stats  # type: ignore[return-value]

    async def _fetch_albums_from_deezer(
        self,
        artist_name: str,
        deezer_artist_id: str | None = None,
    ) -> list:
        """Fetch artist albums from Deezer WITH PAGINATION."""
        if not self._deezer_plugin:
            return []

        try:
            resolved_deezer_id = deezer_artist_id

            if not resolved_deezer_id:
                search_result = await self._deezer_plugin.search_artists(
                    query=artist_name, limit=5
                )
                if not search_result.items:
                    return []
                resolved_deezer_id = search_result.items[0].deezer_id
                if not resolved_deezer_id:
                    return []

            all_albums: list = []
            offset = 0
            page_limit = 100

            for _ in range(10):  # Max 10 pages
                response = await self._deezer_plugin.get_artist_albums(
                    artist_id=resolved_deezer_id, limit=page_limit, offset=offset
                )
                all_albums.extend(response.items or [])
                if response.next_offset is None:
                    break
                offset = response.next_offset

            return all_albums

        except Exception as e:
            logger.warning(f"Deezer albums lookup failed: {e}")
            return []

    async def sync_artist_discography_complete(
        self,
        artist_id: str,
        include_tracks: bool = True,
    ) -> dict[str, Any]:
        """Sync complete discography for an artist: Albums AND Tracks.

        MULTI-PROVIDER:
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!)

        Args:
            artist_id: Our internal artist ID
            include_tracks: Whether to also sync tracks (default: True)

        Returns:
            Dict with sync stats
        """
        from uuid import uuid4

        from soulspot.domain.entities import Album, Track
        from soulspot.domain.ports.plugin import PluginCapability
        from soulspot.domain.value_objects import AlbumId, ImageRef, TrackId
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            TrackRepository,
        )

        stats: dict[str, Any] = {
            "albums_total": 0,
            "albums_added": 0,
            "albums_skipped": 0,
            "albums_with_track_errors": 0,
            "tracks_total": 0,
            "tracks_added": 0,
            "tracks_skipped": 0,
            "track_fetch_errors": [],
            "source": "none",
        }

        artist = await self.artist_repo.get(artist_id)
        if not artist:
            logger.warning(f"Artist not found: {artist_id}")
            return stats

        spotify_artist_id = artist.spotify_id
        albums_dtos: list[Any] = []
        source = "none"

        # 1. Try Spotify WITH PAGINATION
        if spotify_artist_id and self._spotify_plugin:
            try:
                if self._spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
                    offset = 0
                    for _ in range(10):
                        response = await self._spotify_plugin.get_artist_albums(
                            artist_id=spotify_artist_id, limit=50, offset=offset
                        )
                        albums_dtos.extend(response.items)
                        if response.next_offset is None:
                            break
                        offset = response.next_offset

                    if albums_dtos:
                        source = "spotify"
            except Exception as e:
                logger.warning(f"Spotify album fetch failed: {e}")

        # 2. Fallback to Deezer
        if not albums_dtos and self._deezer_plugin and artist.name:
            try:
                albums_dtos = await self._fetch_albums_from_deezer(
                    artist_name=artist.name, deezer_artist_id=artist.deezer_id
                )
                if albums_dtos:
                    source = "deezer"
            except Exception as e:
                logger.warning(f"Deezer album fetch failed: {e}")

        if not albums_dtos:
            return stats

        stats["source"] = source
        album_repo = AlbumRepository(self._session)
        track_repo = TrackRepository(self._session)
        seen_album_keys: set[str] = set()
        seen_track_keys: set[str] = set()

        for album_dto in albums_dtos:
            stats["albums_total"] += 1

            norm_key = _normalize_album_key(
                album_dto.artist_name or artist.name,
                album_dto.title,
                album_dto.release_year,
            )

            if norm_key in seen_album_keys:
                stats["albums_skipped"] += 1
                continue
            seen_album_keys.add(norm_key)

            # Check if album exists
            existing_album = None

            if album_dto.deezer_id:
                existing_album = await album_repo.get_by_deezer_id(album_dto.deezer_id)

            if not existing_album and album_dto.spotify_uri:
                try:
                    spotify_uri = SpotifyUri.from_string(album_dto.spotify_uri)
                    existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
                except ValueError:
                    pass
            elif not existing_album and album_dto.spotify_id:
                try:
                    spotify_uri = SpotifyUri.from_string(
                        f"spotify:album:{album_dto.spotify_id}"
                    )
                    existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
                except ValueError:
                    pass

            if not existing_album:
                existing_album = await album_repo.get_by_title_and_artist(
                    title=album_dto.title, artist_id=artist.id
                )

            if existing_album:
                album_id = existing_album.id
                stats["albums_skipped"] += 1
            else:
                # Create new album
                spotify_uri = None
                if album_dto.spotify_uri:
                    spotify_uri = SpotifyUri.from_string(album_dto.spotify_uri)
                elif album_dto.spotify_id:
                    spotify_uri = SpotifyUri.from_string(
                        f"spotify:album:{album_dto.spotify_id}"
                    )

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
                    cover=ImageRef(
                        url=album_dto.cover.url if album_dto.cover else None
                    ),
                    primary_type=(album_dto.album_type or "album").title(),
                )
                await album_repo.add(album)
                album_id = album.id
                stats["albums_added"] += 1

            # Fetch tracks if enabled
            if include_tracks:
                try:
                    track_dtos = await self._fetch_album_tracks(
                        album_dto, source, spotify_artist_id, artist.deezer_id
                    )

                    if not track_dtos:
                        album_type_lower = (album_dto.album_type or "").lower()
                        if album_type_lower not in ("compilation", "various"):
                            stats["albums_with_track_errors"] += 1
                            stats["track_fetch_errors"].append(
                                (album_dto.title, "No tracks returned")
                            )
                        continue

                except Exception as track_error:
                    logger.exception(f"Track fetch failed for {album_dto.title}")
                    stats["albums_with_track_errors"] += 1
                    stats["track_fetch_errors"].append(
                        (album_dto.title, str(track_error))
                    )
                    continue

                for track_dto in track_dtos:
                    stats["tracks_total"] += 1

                    track_key = f"{album_dto.title.lower()}|{track_dto.title.lower()}|{track_dto.track_number or 0}"
                    if track_key in seen_track_keys:
                        stats["tracks_skipped"] += 1
                        continue
                    seen_track_keys.add(track_key)

                    # Check if track exists
                    existing_track = None
                    if track_dto.isrc:
                        existing_track = await track_repo.get_by_isrc(track_dto.isrc)
                    if not existing_track:
                        existing_track = await track_repo.get_by_title_and_album(
                            title=track_dto.title, album_id=album_id
                        )

                    if existing_track:
                        stats["tracks_skipped"] += 1
                        continue

                    # Create new track
                    spotify_track_uri = None
                    if track_dto.spotify_uri:
                        spotify_track_uri = SpotifyUri.from_string(track_dto.spotify_uri)
                    elif track_dto.spotify_id:
                        spotify_track_uri = SpotifyUri.from_string(
                            f"spotify:track:{track_dto.spotify_id}"
                        )

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
            f"✅ Discography sync for {artist.name}: "
            f"{stats['albums_added']} albums, {stats['tracks_added']} tracks"
        )

        return stats

    async def _fetch_album_tracks(
        self,
        album_dto: Any,
        source: str,
        spotify_artist_id: str | None,
        deezer_artist_id: str | None,
    ) -> list[Any]:
        """Fetch tracks for an album from the appropriate provider."""
        from soulspot.domain.ports.plugin import PluginCapability

        try:
            if source == "spotify" and self._spotify_plugin and album_dto.spotify_id:
                if self._spotify_plugin.can_use(PluginCapability.GET_ALBUM_TRACKS):
                    response = await self._spotify_plugin.get_album_tracks(
                        album_id=album_dto.spotify_id, limit=50
                    )
                    return response.items if hasattr(response, "items") else []
            elif source == "deezer" and self._deezer_plugin and album_dto.deezer_id:
                response = await self._deezer_plugin.get_album_tracks(
                    album_id=album_dto.deezer_id
                )
                return response.items if hasattr(response, "items") else []
        except Exception as e:
            logger.warning(f"Failed to fetch tracks for {album_dto.title}: {e}")

        return []

    # =========================================================================
    # === TOP TRACKS (from artist_songs_service) ===
    # =========================================================================

    async def sync_artist_top_tracks(
        self, artist_id: ArtistId, market: str = "US"
    ) -> tuple[list["Track"], dict[str, int]]:
        """Sync top tracks (singles) from an artist with MULTI-PROVIDER fallback.

        MULTI-PROVIDER:
        1. Try Spotify first (if authenticated)
        2. Fall back to Deezer (NO AUTH NEEDED!)

        Args:
            artist_id: Artist ID to sync songs for
            market: ISO 3166-1 alpha-2 country code

        Returns:
            Tuple of (list of Track entities, sync statistics dict)
        """
        from soulspot.domain.entities import Track
        from soulspot.domain.ports.plugin import PluginCapability
        from soulspot.domain.value_objects import TrackId

        stats: dict[str, int | str] = {
            "total_fetched": 0,
            "singles_found": 0,
            "created": 0,
            "updated": 0,
            "skipped_album_tracks": 0,
            "errors": 0,
            "source": "none",
        }

        artist = await self.artist_repo.get_by_id(artist_id)
        if not artist:
            raise EntityNotFoundError(f"Artist not found: {artist_id.value}")

        spotify_artist_id = artist.spotify_id
        synced_tracks: list[Track] = []
        track_dtos: list["TrackDTO"] = []
        source = "none"

        # 1. Try Spotify first
        if spotify_artist_id and self._spotify_plugin:
            try:
                if self._spotify_plugin.can_use(PluginCapability.GET_ARTIST_TOP_TRACKS):
                    track_dtos = await self._spotify_plugin.get_artist_top_tracks(
                        artist_id=spotify_artist_id, market=market
                    )
                    source = "spotify"
            except Exception as e:
                logger.warning(f"Spotify top tracks failed for {artist.name}: {e}")

        # 2. Fallback to Deezer
        if not track_dtos and self._deezer_plugin and artist.name:
            try:
                track_dtos = await self._fetch_top_tracks_from_deezer(artist.name)
                if track_dtos:
                    source = "deezer"
            except Exception as e:
                logger.warning(f"Deezer fallback failed for {artist.name}: {e}")

        if not track_dtos:
            return synced_tracks, stats  # type: ignore[return-value]

        stats["total_fetched"] = len(track_dtos)
        stats["source"] = source

        for track_dto in track_dtos:
            try:
                track, was_created, is_single = await self._process_top_track_dto(
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
                logger.error(f"Failed to process track {track_dto.title}: {e}")
                stats["errors"] += 1

        return synced_tracks, stats  # type: ignore[return-value]

    async def _fetch_top_tracks_from_deezer(self, artist_name: str) -> list["TrackDTO"]:
        """Fetch artist top tracks from Deezer as fallback."""
        if not self._deezer_plugin:
            return []

        try:
            search_result = await self._deezer_plugin.search_artists(
                query=artist_name, limit=5
            )
            if not search_result.items:
                return []

            deezer_artist_id = search_result.items[0].deezer_id
            if not deezer_artist_id:
                return []

            return await self._deezer_plugin.get_artist_top_tracks(
                artist_id=deezer_artist_id
            )

        except Exception as e:
            logger.warning(f"Deezer top tracks lookup failed: {e}")
            return []

    async def _process_top_track_dto(
        self, track_dto: "TrackDTO", artist_id: ArtistId, source: str = "spotify"
    ) -> tuple["Track | None", bool, bool]:
        """Process a single track from SpotifyPlugin or DeezerPlugin.

        Returns:
            Tuple of (Track entity or None, was_created, is_single)
        """
        from soulspot.domain.entities import Track
        from soulspot.domain.value_objects import TrackId

        track_id = track_dto.spotify_id or track_dto.deezer_id
        if not track_id or not track_dto.title:
            return None, False, False

        spotify_uri: SpotifyUri | None = None
        if track_dto.spotify_id:
            spotify_uri = SpotifyUri.from_string(
                track_dto.spotify_uri or f"spotify:track:{track_dto.spotify_id}"
            )

        is_single = (
            track_dto.album_spotify_id is None and track_dto.album_deezer_id is None
        )
        isrc = track_dto.isrc

        # Check if track exists
        existing_track = None

        if spotify_uri:
            existing_track = await self.track_repo.get_by_spotify_uri(spotify_uri)

        if not existing_track and isrc:
            existing_track = await self.track_repo.get_by_isrc(isrc)

        if not existing_track:
            artist = await self.artist_repo.get_by_id(artist_id)
            if artist and artist.name:
                existing_track = await self.track_repo.get_by_title_and_artist(
                    title=track_dto.title, artist_name=artist.name
                )

        if existing_track:
            # Update existing track
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

            return existing_track, False, is_single

        # Create new track
        internal_id, was_created = await self._mapping_service.get_or_create_track(
            track_dto,
            artist_internal_id=str(artist_id.value),
            album_internal_id=None,
            source=source,
        )

        new_track = await self.track_repo.get_by_id(TrackId(internal_id))
        if not new_track:
            raise EntityNotFoundError(f"Track not found after creation: {internal_id}")

        return new_track, True, is_single

    async def sync_all_artists_top_tracks(
        self, market: str = "US", limit: int = 100
    ) -> tuple[list["Track"], dict[str, int]]:
        """Sync top tracks from all followed artists.

        Args:
            market: ISO 3166-1 alpha-2 country code
            limit: Maximum number of artists to process

        Returns:
            Tuple of (list of all synced Track entities, aggregate statistics)
        """
        from soulspot.domain.entities import Track

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
        artists = await self.artist_repo.list_all(limit=limit)

        for artist in artists:
            try:
                tracks, stats = await self.sync_artist_top_tracks(
                    artist_id=artist.id, market=market
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
                logger.error(f"Failed to sync songs for artist {artist.name}: {e}")
                aggregate_stats["artist_errors"] += 1

        return all_tracks, aggregate_stats

    # =========================================================================
    # === DISCOGRAPHY (from discography_service) ===
    # =========================================================================

    async def check_discography(
        self,
        artist_id: ArtistId,
        access_token: str = "",  # Kept for API compatibility, not used
    ) -> DiscographyInfo:
        """Check discography completeness for an artist.

        Uses unified soulspot_albums table after table consolidation.
        Compares owned albums (downloaded) with known albums from Spotify.

        Args:
            artist_id: Artist ID (local soulspot_artists.id)
            access_token: Kept for API compatibility (not used)

        Returns:
            Discography information
        """
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self._session.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist:
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name="Unknown",
                total_albums=0,
                owned_albums=0,
                missing_albums=[],
            )

        # Get owned albums
        stmt_owned = select(AlbumModel).where(
            AlbumModel.artist_id == str(artist_id.value),
            AlbumModel.source.in_(["local", "hybrid"]),
        )
        result = await self._session.execute(stmt_owned)
        owned_albums = result.scalars().all()
        owned_spotify_uris = {
            album.spotify_uri for album in owned_albums if album.spotify_uri
        }

        spotify_artist_id = (
            artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None
        )
        if not spotify_artist_id:
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),
                owned_albums=len(owned_albums),
                missing_albums=[],
            )

        if not artist.albums_synced_at:
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),
                owned_albums=len(owned_albums),
                missing_albums=[],
            )

        # Get all known Spotify albums
        stmt_spotify = select(AlbumModel).where(
            AlbumModel.artist_id == str(artist_id.value),
            AlbumModel.source == "spotify",
        )
        result = await self._session.execute(stmt_spotify)
        all_spotify_albums = list(result.scalars().all())

        # Find missing albums
        missing_albums = []
        for album in all_spotify_albums:
            if album.spotify_uri not in owned_spotify_uris:
                spotify_id = (
                    album.spotify_uri.split(":")[-1] if album.spotify_uri else album.id
                )
                missing_albums.append(
                    {
                        "name": album.title,
                        "spotify_uri": album.spotify_uri,
                        "spotify_id": spotify_id,
                        "release_date": album.release_date or "",
                        "total_tracks": album.total_tracks or 0,
                        "album_type": album.primary_type,
                        "image_url": album.cover_url,
                    }
                )

        return DiscographyInfo(
            artist_id=str(artist_id.value),
            artist_name=artist.name,
            total_albums=len(all_spotify_albums),
            owned_albums=len(owned_albums),
            missing_albums=missing_albums,
        )

    async def get_missing_albums_for_all_artists(
        self, access_token: str = "", limit: int = 10
    ) -> list[DiscographyInfo]:
        """Get missing albums for all artists in the library.

        Args:
            access_token: Kept for API compatibility (not used)
            limit: Maximum number of artists to check

        Returns:
            List of discography information for artists with missing albums
        """
        stmt = select(ArtistModel).limit(limit)
        result = await self._session.execute(stmt)
        artists = result.scalars().all()

        discography_infos = []
        for artist in artists:
            try:
                artist_id = ArtistId.from_string(artist.id)
                info = await self.check_discography(artist_id, access_token)
                if not info.is_complete():
                    discography_infos.append(info)
            except Exception as e:
                logger.error(f"Failed to check discography for {artist.id}: {e}")
                continue

        return discography_infos

    # =========================================================================
    # === CRUD OPERATIONS ===
    # =========================================================================

    async def get_artist_singles(self, artist_id: ArtistId) -> list["Track"]:
        """Get all singles (non-album tracks) for an artist.

        Args:
            artist_id: Artist ID to get singles for

        Returns:
            List of Track entities without album association
        """
        return await self.track_repo.get_singles_by_artist(artist_id)

    async def remove_track(self, track_id: "TrackId", artist_id: ArtistId) -> bool:
        """Remove a track from the database.

        Args:
            track_id: Track ID to remove
            artist_id: Artist ID (for validation)

        Returns:
            True if track was removed
        """
        from soulspot.domain.value_objects import TrackId

        track = await self.track_repo.get_by_id(track_id)

        if not track:
            raise EntityNotFoundError(f"Track not found: {track_id.value}")

        if track.artist_id != artist_id:
            raise BusinessRuleViolation(
                f"Track {track_id.value} does not belong to artist {artist_id.value}"
            )

        await self.track_repo.delete(track_id)
        logger.info(f"Removed track: {track.title}")

        return True

    async def remove_all_artist_tracks(self, artist_id: ArtistId) -> int:
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
