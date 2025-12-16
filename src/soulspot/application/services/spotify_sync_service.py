# Hey future me - REFACTORED to use SpotifyPlugin instead of raw SpotifyClient!
# The plugin handles token management internally, no more access_token parameter juggling.
# This service handles AUTO-SYNC of Spotify data to our database!
#
# REFACTORED (Dec 2025):
# - Removed get_album_detail_view() → Use LibraryViewService instead!
# - Removed Deezer fallback → Use DeezerSyncService for Deezer operations!
# - This service is now PURE SPOTIFY sync only
#
# What syncs where:
# - Followed Artists → spotify_artists table (auto-sync every 5 min)
#                    → ALSO soulspot_artists table (unified library!) with source='spotify'
# - User Playlists → playlists table (auto-sync every 10 min)
# - Liked Songs → playlists table (special playlist with is_liked_songs=True)
# - Saved Albums → spotify_albums table (is_saved=True flag)
#
# For ViewModels: Use LibraryViewService.get_album_detail_view()
# For Deezer: Use DeezerSyncService
# For Multi-Provider: Use ProviderSyncOrchestrator (Phase 3)
"""Service for automatic Spotify data synchronization with diff logic."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.persistence.models import ensure_utc_aware
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

if TYPE_CHECKING:
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.artwork_service import ArtworkService
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class SpotifySyncService:
    """Service for auto-syncing Spotify data with diff logic.

    Hey future me - REFACTORED to use SpotifyPlugin instead of raw SpotifyClient!
    The plugin handles token management internally, no more access_token parameter.
    All methods that used to take access_token now just work - plugin has the token!

    This service handles:
    1. Auto-sync followed artists on page load (with cooldown)
    2. Auto-sync user playlists (with cooldown)
    3. Auto-sync Liked Songs (special playlist)
    4. Auto-sync Saved Albums (albums the user explicitly saved)
    5. Diff-sync: add new follows, remove unfollows from DB
    6. Lazy-load artist albums when user navigates to artist page
    7. Lazy-load album tracks when user navigates to album page
    8. Download and store images locally (optional)

    All Spotify data goes to spotify_* tables or playlists table,
    NOT local library tables!
    """

    # Cooldown in minutes before re-syncing (avoid hammering Spotify API)
    ARTISTS_SYNC_COOLDOWN = 5
    PLAYLISTS_SYNC_COOLDOWN = 10
    ALBUMS_SYNC_COOLDOWN = 15
    TRACKS_SYNC_COOLDOWN = 60

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
        image_service: "ArtworkService | None" = None,
        settings_service: "AppSettingsService | None" = None,
    ) -> None:
        """Initialize sync service.

        Hey future me - refactored to use SpotifyPlugin!
        The plugin handles token management internally, no more access_token juggling.
        
        NOTE (Dec 2025): Deezer fallback removed!
        - Use DeezerSyncService for Deezer operations
        - Use ProviderSyncOrchestrator for multi-provider aggregation (Phase 3)

        Args:
            session: Database session
            spotify_plugin: SpotifyPlugin for API calls (handles auth internally)
            image_service: Optional image service for downloading images
            settings_service: Optional settings service for sync config
        """
        # Hey future me - ProviderMappingService zentralisiert das ID-Mapping!
        # Statt überall SpotifyUri.from_string() + ArtistId.generate() zu machen,
        # nutzen wir jetzt den MappingService für einheitliche UUID-Vergabe.
        from soulspot.application.services.provider_mapping_service import (
            ProviderMappingService,
        )

        self.repo = SpotifyBrowseRepository(session)
        self.spotify_plugin = spotify_plugin
        self._session = session
        self._image_service = image_service
        self._settings_service = settings_service
        self._mapping_service = ProviderMappingService(session)

    # =========================================================================
    # FOLLOWED ARTISTS SYNC
    # =========================================================================

    async def sync_followed_artists(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Sync followed artists from Spotify with diff logic.

        Hey future me - refactored to use SpotifyPlugin!
        No more access_token param - plugin handles auth internally.

        This is the MAIN auto-sync method! Called on page load.
        - First checks if Spotify provider is enabled at all (provider mode)
        - Checks cooldown next (skip if recently synced)
        - Fetches all followed artists from Spotify (paginated)
        - Compares with DB: adds new, removes unfollowed
        - Returns stats for UI display

        Args:
            force: Skip cooldown check

        Returns:
            Dict with sync stats (added, removed, total, etc.)
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "removed": 0,
            "unchanged": 0,
            "error": None,
            "skipped_cooldown": False,
            "skipped_disabled": False,
            "skipped_provider_disabled": False,
            "skipped_not_authenticated": False,
        }

        try:
            # Hey future me - PROVIDER LEVEL CHECK FIRST!
            # If Spotify provider is disabled in Settings, skip ALL Spotify operations.
            if self._settings_service and not await self._settings_service.is_provider_enabled("spotify"):
                stats["skipped_provider_disabled"] = True
                logger.debug("Spotify provider is disabled, skipping artists sync")
                return stats

            # Hey future me - AUTH CHECK USING can_use() - checks capability + auth!
            # If user is not authenticated with Spotify, skip operations that need auth.
            from soulspot.domain.ports.plugin import PluginCapability
            if not self.spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
                stats["skipped_not_authenticated"] = True
                logger.debug("Spotify not authenticated, skipping artists sync")
                return stats

            # Check if artists sync is enabled (feature-level)
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_artists_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Artists sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("followed_artists"):
                stats["skipped_cooldown"] = True
                existing_count = await self.repo.count_artists()
                stats["total"] = existing_count
                logger.debug("Skipping followed artists sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="running",
            )
            await self._session.commit()

            # Fetch all followed artists from Spotify
            spotify_artists = await self._fetch_all_followed_artists()
            spotify_ids = {a.spotify_id for a in spotify_artists if a.spotify_id}

            # Get existing artist IDs from DB
            db_ids = await self.repo.get_all_artist_ids()

            # Diff calculation
            to_add = spotify_ids - db_ids
            to_remove = db_ids - spotify_ids
            unchanged = spotify_ids & db_ids

            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)
            stats["unchanged"] = len(unchanged)
            stats["total"] = len(spotify_ids)

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Add new artists
            for artist_dto in spotify_artists:
                if artist_dto.spotify_id and artist_dto.spotify_id in to_add:
                    await self._upsert_artist_from_dto(
                        artist_dto, download_images=should_download_images
                    )

            # Update existing artists (in case name/image changed)
            for artist_dto in spotify_artists:
                if artist_dto.spotify_id and artist_dto.spotify_id in unchanged:
                    await self._upsert_artist_from_dto(
                        artist_dto, download_images=should_download_images
                    )

            # Remove unfollowed artists (CASCADE deletes albums/tracks)
            # Hey future me - track should_remove for unified library sync later
            should_remove = False
            if to_remove:
                # Check if we should remove unfollowed artists
                should_remove = True
                if self._settings_service:
                    should_remove = (
                        await self._settings_service.should_remove_unfollowed_artists()
                    )

                if should_remove:
                    # Clean up images before deleting artists
                    if self._image_service:
                        for spotify_id in to_remove:
                            await self._image_service.delete_image_async(
                                f"spotify/artists/{spotify_id}.webp"
                            )

                    removed_count = await self.repo.delete_artists(to_remove)
                    logger.info(f"Removed {removed_count} unfollowed artists from DB")
                else:
                    stats["removed"] = 0  # Didn't actually remove

            # UNIFIED LIBRARY SYNC: Also sync to soulspot_artists table!
            # This makes followed artists appear on /library/artists page.
            try:
                library_stats = await self._sync_to_unified_library(
                    spotify_artists, 
                    removed_ids=to_remove if should_remove else None
                )
                logger.info(
                    f"Unified library sync: {library_stats['created']} created, "
                    f"{library_stats['updated']} updated, "
                    f"{library_stats['downgraded']} downgraded"
                )
                stats["library_created"] = library_stats["created"]
                stats["library_updated"] = library_stats["updated"]
            except Exception as lib_error:
                logger.warning(f"Unified library sync failed (non-blocking): {lib_error}")
                # Don't fail the whole sync if library sync fails

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="idle",
                items_synced=len(spotify_artists),
                items_added=len(to_add),
                items_removed=stats["removed"],
                cooldown_minutes=self.ARTISTS_SYNC_COOLDOWN,
            )

            await self._session.commit()
            stats["synced"] = True

            logger.info(
                f"Followed artists sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} removed"
            )

        except Exception as e:
            logger.error(f"Error syncing followed artists: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="error",
                error_message=str(e),
            )
            await self._session.commit()

        return stats

    async def _fetch_all_followed_artists(
        self,
    ) -> list[Any]:
        """Fetch all followed artists from Spotify (handles pagination).

        Hey future me - refactored to use SpotifyPlugin!
        Returns list of ArtistDTOs instead of raw dicts.
        Spotify uses cursor-based pagination. We loop until no more pages.
        """
        from soulspot.domain.dtos import ArtistDTO

        all_artists: list[ArtistDTO] = []
        after_cursor: str | None = None

        while True:
            response = await self.spotify_plugin.get_followed_artists(
                limit=50,
                after=after_cursor,
            )

            items = response.items
            if not items:
                break

            all_artists.extend(items)

            # Get cursor for next page from last artist's spotify_id
            if response.next_offset and items:
                after_cursor = items[-1].spotify_id
            else:
                break

        return all_artists

    async def _upsert_artist_from_dto(
        self, artist_dto: Any, download_images: bool = False
    ) -> None:
        """Insert or update a Spotify artist in DB from ArtistDTO.

        Hey future me - this is the DTO version of _upsert_artist!
        Accepts ArtistDTO from SpotifyPlugin instead of raw dict.
        The image_url comes directly from DTO (plugin already selects best image).

        Args:
            artist_dto: ArtistDTO from SpotifyPlugin
            download_images: Whether to download profile image locally
        """
        from soulspot.domain.dtos import ArtistDTO

        if not isinstance(artist_dto, ArtistDTO):
            logger.warning(f"Expected ArtistDTO, got {type(artist_dto)}")
            return

        spotify_id = artist_dto.spotify_id
        if not spotify_id:
            logger.warning("ArtistDTO missing spotify_id, skipping")
            return

        name = artist_dto.name or "Unknown"
        genres = artist_dto.genres or []
        image_url = artist_dto.image_url  # Plugin already selects best image
        popularity = artist_dto.popularity
        follower_count = artist_dto.followers

        # Download image if enabled
        image_path = None
        if download_images and image_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_artist_by_id(spotify_id)
            existing_url = existing.image_url if existing else None
            existing_path = existing.image_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, image_url, existing_path
            ):
                image_path = await self._image_service.download_artist_image(
                    spotify_id, image_url
                )
            elif existing_path:
                image_path = existing_path  # Keep existing path

        await self.repo.upsert_artist(
            spotify_id=spotify_id,
            name=name,
            image_url=image_url,
            image_path=image_path,
            genres=genres,
            popularity=popularity,
            follower_count=follower_count,
        )

    # Hey future me - UNIFIED LIBRARY SYNC mit ProviderMappingService!
    # Statt manuell SpotifyUri.from_string() + ArtistId.generate() zu machen,
    # nutzen wir jetzt den zentralen MappingService für konsistente UUID-Vergabe.
    # Das DTO bekommt die internal_id gesetzt und wir können sie direkt nutzen.
    async def _sync_to_unified_library(
        self, artist_dtos: list[Any], removed_ids: set[str] | None = None
    ) -> dict[str, int]:
        """Sync followed artists to unified library (soulspot_artists).

        Hey future me - REFACTORED to use ProviderMappingService!
        Der MappingService kümmert sich um:
        1. Lookup existierender Artists (by spotify_id, name, oder isrc)
        2. Erstellen neuer Artists mit UUID falls nicht vorhanden
        3. Setzen von dto.internal_id mit der SoulSpot UUID

        Wir nutzen dann diese internal_id statt manuell IDs zu generieren.

        Args:
            artist_dtos: List of ArtistDTOs from Spotify that were synced
            removed_ids: Set of Spotify IDs that were unfollowed (for source downgrade)

        Returns:
            Dict with counts: created, updated, downgraded
        """
        from soulspot.domain.entities import ArtistSource
        from soulspot.domain.value_objects import ArtistId, SpotifyUri
        from soulspot.infrastructure.persistence.repositories import ArtistRepository

        stats = {"created": 0, "updated": 0, "downgraded": 0}
        artist_repo = ArtistRepository(self._session)

        for dto in artist_dtos:
            if not dto.spotify_id or not dto.name:
                continue

            # ZENTRAL: ProviderMappingService mappt DTO auf interne UUID
            # Erstellt Artist falls nicht vorhanden und setzt dto.internal_id
            mapped_dto = await self._mapping_service.map_artist_dto(dto)

            spotify_uri = SpotifyUri.from_string(
                dto.spotify_uri or f"spotify:artist:{dto.spotify_id}"
            )

            # Nutze internal_id um existierenden Artist zu holen
            if mapped_dto.internal_id:
                existing = await artist_repo.get_by_id(ArtistId(mapped_dto.internal_id))
            else:
                existing = await artist_repo.get_by_spotify_uri(spotify_uri)

            if existing:
                # Artist exists - check if we need to update source or metadata
                needs_update = False

                # If existing source is 'local', upgrade to 'hybrid'
                if existing.source == ArtistSource.LOCAL:
                    existing.source = ArtistSource.HYBRID
                    needs_update = True
                elif existing.source == ArtistSource.SPOTIFY:
                    # Already marked as Spotify source, just update metadata
                    pass

                # Update metadata from Spotify if available
                if dto.image_url and existing.image_url != dto.image_url:
                    existing.image_url = dto.image_url
                    needs_update = True
                if dto.genres and existing.genres != dto.genres:
                    existing.genres = dto.genres
                    needs_update = True

                if needs_update:
                    await artist_repo.update(existing)
                    stats["updated"] += 1
            else:
                # Artist wurde bereits vom MappingService erstellt
                # Wir müssen nur noch source auf SPOTIFY setzen
                if mapped_dto.internal_id:
                    new_artist = await artist_repo.get_by_id(ArtistId(mapped_dto.internal_id))
                    if new_artist and new_artist.source != ArtistSource.SPOTIFY:
                        new_artist.source = ArtistSource.SPOTIFY
                        await artist_repo.update(new_artist)
                stats["created"] += 1

        # Handle unfollowed artists - downgrade from 'spotify'/'hybrid' if needed
        if removed_ids:
            for spotify_id in removed_ids:
                spotify_uri = SpotifyUri.from_string(f"spotify:artist:{spotify_id}")
                existing = await artist_repo.get_by_spotify_uri(spotify_uri)

                if existing:
                    if existing.source == ArtistSource.HYBRID:
                        # Has local files - downgrade to 'local'
                        existing.source = ArtistSource.LOCAL
                        await artist_repo.update(existing)
                        stats["downgraded"] += 1
                    elif existing.source == ArtistSource.SPOTIFY:
                        # Only Spotify - can delete OR keep as 'local' orphan
                        # For now we keep (user might want the metadata)
                        existing.source = ArtistSource.LOCAL
                        await artist_repo.update(existing)
                        stats["downgraded"] += 1

        return stats

    # =========================================================================
    # ARTIST ALBUMS SYNC
    # =========================================================================

    async def sync_artist_albums(
        self, artist_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync albums for a specific artist with MULTI-PROVIDER support.

        Hey future me - refactored for SpotifyPlugin with Deezer fallback!
        No more access_token - plugin manages auth internally.
        Called when user navigates to artist detail page.
        Lazy-loads albums only when needed.
        
        MULTI-PROVIDER (Nov 2025):
        - Tries Spotify first (if authenticated)
        - Falls back to Deezer (NO AUTH NEEDED!) when Spotify fails
        - This ensures artist albums work even without Spotify OAuth!

        Args:
            artist_id: Spotify artist ID
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "error": None,
            "skipped_cooldown": False,
            "source": "none",  # Track which provider was used
        }

        try:
            # Check if artist exists
            artist = await self.repo.get_artist_by_id(artist_id)
            if not artist:
                stats["error"] = f"Artist {artist_id} not found"
                return stats

            # Check cooldown based on albums_synced_at
            # Hey future me - use ensure_utc_aware() because SQLite returns naive datetimes!
            if not force and artist.albums_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.ALBUMS_SYNC_COOLDOWN)
                if (
                    datetime.now(UTC)
                    < ensure_utc_aware(artist.albums_synced_at) + cooldown
                ):
                    stats["skipped_cooldown"] = True
                    stats["total"] = await self.repo.count_albums_by_artist(artist_id)
                    return stats

            # Fetch albums with multi-provider fallback
            # Pass artist name for Deezer search fallback
            artist_name = artist.name if hasattr(artist, 'name') else None
            album_dtos = await self._fetch_artist_albums(artist_id, artist_name)

            for album_dto in album_dtos:
                await self._upsert_album_from_dto(album_dto, artist_id)
                stats["added"] += 1

            stats["total"] = len(album_dtos)
            
            # Track source for stats/debugging
            if album_dtos:
                stats["source"] = getattr(album_dtos[0], 'source_service', 'unknown')

            # Mark albums as synced
            await self.repo.set_albums_synced(artist_id)
            await self._session.commit()

            stats["synced"] = True
            logger.info(
                f"Synced {len(album_dtos)} albums for artist {artist_id} "
                f"(source: {stats['source']})"
            )

        except Exception as e:
            logger.error(f"Error syncing albums for artist {artist_id}: {e}")
            stats["error"] = str(e)

        return stats

    async def _fetch_artist_albums(
        self, artist_id: str, artist_name: str | None = None
    ) -> list[Any]:
        """Fetch all albums for an artist with MULTI-PROVIDER FALLBACK.

        Hey future me - MULTI-PROVIDER SUPPORT (Nov 2025)!
        
        Priority order:
        1. Spotify (if authenticated) - preferred for Spotify-sourced artists
        2. Deezer (NO AUTH NEEDED!) - fallback when Spotify unavailable
        
        WHY Deezer fallback?
        - Deezer's public API doesn't require OAuth for artist albums!
        - Users without Spotify OAuth can still browse artist discographies
        - Better UX: "show me albums" works regardless of auth state
        
        GOTCHA: Deezer uses different artist IDs!
        - For Spotify artists, we search by artist name on Deezer
        - Then fetch albums for the matched Deezer artist
        - This is slightly less accurate but works for 95%+ of cases

        Args:
            artist_id: Spotify artist ID (primary)
            artist_name: Artist name for Deezer search fallback

        Returns:
            list[AlbumDTO] from Spotify or Deezer
        """
        from soulspot.domain.ports.plugin import PluginCapability

        albums: list[Any] = []
        source_used = "none"

        # 1. Try Spotify first (if authenticated)
        try:
            if self.spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
                response = await self.spotify_plugin.get_artist_albums(
                    artist_id=artist_id,
                    limit=50,
                )
                if response.items:
                    albums = response.items
                    source_used = "spotify"
                    logger.info(
                        f"Fetched {len(albums)} albums for artist {artist_id} from Spotify"
                    )
        except Exception as e:
            logger.warning(
                f"Spotify artist albums failed for {artist_id}: {e}. "
                "Will try Deezer fallback."
            )

        # NOTE: Deezer fallback removed (Dec 2025) - use DeezerSyncService directly!
        # For multi-provider aggregation, use ProviderSyncOrchestrator (Phase 3)

        if not albums:
            logger.warning(
                f"No albums found for artist {artist_id} from Spotify"
            )
        else:
            logger.debug(f"Artist albums source: {source_used}")

        return albums

    async def _upsert_album_from_dto(self, album_dto: Any, artist_id: str) -> None:
        """Insert or update an album in DB from AlbumDTO (Spotify or Deezer).

        Hey future me - supports BOTH Spotify AND Deezer albums!
        
        DEDUPLICATION STRATEGY:
        - For Spotify albums: Use spotify_id as unique identifier
        - For Deezer albums: Use deezer_id as unique identifier
        - We prefix Deezer IDs with "deezer:" to avoid collisions
        
        WHY this works:
        - Same album from Spotify = same spotify_id = upsert (no duplicate)
        - Same album from Deezer = same deezer_id = upsert (no duplicate)
        - Different source for same album = different IDs = could be duplicate!
        
        TODO: Consider ISRC matching for cross-service deduplication
        """
        from soulspot.domain.dtos import AlbumDTO

        if not isinstance(album_dto, AlbumDTO):
            logger.warning(f"Expected AlbumDTO, got {type(album_dto)}")
            return

        # Determine unique ID based on source
        # Spotify albums have spotify_id, Deezer albums have deezer_id
        unique_id = album_dto.spotify_id
        if not unique_id and album_dto.deezer_id:
            # Use Deezer ID with prefix to avoid collisions
            unique_id = f"deezer:{album_dto.deezer_id}"
        
        if not unique_id:
            logger.warning("AlbumDTO missing both spotify_id and deezer_id, skipping")
            return

        name = album_dto.title or "Unknown"
        image_url = album_dto.artwork_url
        release_date = album_dto.release_date
        # AlbumDTO doesn't have release_date_precision, default to 'day'
        release_date_precision = "day" if release_date else None
        album_type = album_dto.album_type or "album"
        total_tracks = album_dto.total_tracks or 0

        await self.repo.upsert_album(
            spotify_id=unique_id,  # Can be spotify ID or "deezer:ID"
            artist_id=artist_id,
            name=name,
            image_url=image_url,
            release_date=release_date,
            release_date_precision=release_date_precision,
            album_type=album_type,
            total_tracks=total_tracks,
        )

    # =========================================================================
    # ARTIST TOP TRACKS SYNC (für Konsistenz mit DeezerSyncService)
    # =========================================================================

    async def sync_artist_top_tracks(
        self,
        artist_id: str,
        market: str = "DE",
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync top tracks for a specific artist from Spotify.
        
        Hey future me - das ist die KONSISTENTE Methode wie DeezerSyncService!
        BRAUCHT Spotify OAuth um Top Tracks zu holen.
        
        Args:
            artist_id: Spotify artist ID
            market: Market code (default: DE)
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        cache_key = f"artist_top_tracks_{artist_id}"
        stats: dict[str, Any] = {
            "synced": False,
            "tracks_synced": 0,
            "error": None,
            "skipped_cooldown": False,
        }
        
        # Check cooldown (use TRACKS_SYNC_COOLDOWN for consistency)
        sync_status = await self.repo.get_sync_status(cache_key)
        if not force and sync_status:
            last_sync = sync_status.last_sync_at
            if last_sync:
                last_sync = ensure_utc_aware(last_sync)
                elapsed = (datetime.now(UTC) - last_sync).total_seconds() / 60
                if elapsed < self.TRACKS_SYNC_COOLDOWN:
                    stats["skipped_cooldown"] = True
                    return stats
        
        try:
            # Get top tracks from Spotify
            tracks = await self.spotify_plugin.get_artist_top_tracks(
                artist_id, market=market
            )
            
            for track_dto in tracks:
                try:
                    # Save track to DB
                    await self.repo.upsert_track(
                        spotify_id=track_dto.spotify_id or "",
                        album_id=track_dto.album_id or "",
                        name=track_dto.name,
                        duration_ms=track_dto.duration_ms,
                        track_number=track_dto.track_number or 1,
                        disc_number=track_dto.disc_number or 1,
                        explicit=track_dto.explicit,
                        preview_url=track_dto.preview_url,
                        isrc=track_dto.isrc,
                    )
                    stats["tracks_synced"] += 1
                except Exception as e:
                    logger.warning(f"Failed to save track {track_dto.name}: {e}")
            
            # Update sync status
            await self.repo.update_sync_status(cache_key)
            await self._session.commit()
            
            stats["synced"] = True
            logger.info(
                f"SpotifySyncService: Artist {artist_id} top tracks synced - "
                f"{stats['tracks_synced']} tracks"
            )
            
        except Exception as e:
            logger.error(f"SpotifySyncService: Artist top tracks sync failed: {e}")
            stats["error"] = str(e)
        
        return stats

    # =========================================================================
    # RELATED ARTISTS SYNC (Discovery Feature!)
    # =========================================================================

    async def sync_related_artists(
        self,
        artist_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync related artists for a specific artist from Spotify.
        
        Hey future me - das ist ein DISCOVERY Feature!
        Holt ähnliche Künstler und speichert sie als "related" in DB.
        BRAUCHT Spotify OAuth.
        
        Use Case:
        - "Artists You Might Like" auf Artist-Detail-Seite
        - Discovery Recommendations
        - "Fans Also Like" Section
        
        Args:
            artist_id: Spotify artist ID
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        cache_key = f"related_artists_{artist_id}"
        stats: dict[str, Any] = {
            "synced": False,
            "artists_synced": 0,
            "error": None,
            "skipped_cooldown": False,
        }
        
        # Check cooldown
        sync_status = await self.repo.get_sync_status(cache_key)
        if not force and sync_status:
            last_sync = sync_status.last_sync_at
            if last_sync:
                last_sync = ensure_utc_aware(last_sync)
                elapsed = (datetime.now(UTC) - last_sync).total_seconds() / 60
                if elapsed < self.ARTISTS_SYNC_COOLDOWN:
                    stats["skipped_cooldown"] = True
                    return stats
        
        try:
            # Get related artists from Spotify
            related_artists = await self.spotify_plugin.get_related_artists(artist_id)
            
            for artist_dto in related_artists:
                try:
                    # Save artist to DB
                    await self.repo.upsert_artist(
                        spotify_id=artist_dto.spotify_id or "",
                        name=artist_dto.name,
                        image_url=artist_dto.image_url,
                    )
                    stats["artists_synced"] += 1
                except Exception as e:
                    logger.warning(f"Failed to save related artist {artist_dto.name}: {e}")
            
            # TODO: Store the relationship (artist_id -> related_artist_id)
            # This requires a new table: artist_relations
            # For now, we just cache the related artists in DB
            
            # Update sync status
            await self.repo.update_sync_status(cache_key)
            await self._session.commit()
            
            stats["synced"] = True
            logger.info(
                f"SpotifySyncService: Related artists for {artist_id} synced - "
                f"{stats['artists_synced']} artists"
            )
            
        except Exception as e:
            logger.error(f"SpotifySyncService: Related artists sync failed: {e}")
            stats["error"] = str(e)
        
        return stats

    # =========================================================================
    # NEW RELEASES SYNC
    # =========================================================================

    async def sync_new_releases(
        self,
        limit: int = 50,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Spotify new releases to database.
        
        Hey future me - das ist die KONSISTENTE Methode wie DeezerSyncService!
        BRAUCHT Spotify OAuth um New Releases zu holen.
        
        Args:
            limit: Max albums to sync
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        stats: dict[str, Any] = {
            "synced": False,
            "albums_synced": 0,
            "error": None,
            "skipped_cooldown": False,
        }
        
        # Check cooldown
        sync_status = await self.repo.get_sync_status("new_releases")
        if not force and sync_status:
            last_sync = sync_status.last_sync_at
            if last_sync:
                last_sync = ensure_utc_aware(last_sync)
                elapsed = (datetime.now(UTC) - last_sync).total_seconds() / 60
                if elapsed < self.ALBUMS_SYNC_COOLDOWN:
                    stats["skipped_cooldown"] = True
                    return stats
        
        try:
            # Get new releases from Spotify
            albums = await self.spotify_plugin.get_new_releases(limit=limit)
            
            for album_dto in albums:
                try:
                    # Save album to DB
                    await self.repo.upsert_album(
                        spotify_id=album_dto.spotify_id or "",
                        artist_id=album_dto.artist_id or "",
                        name=album_dto.title,
                        image_url=album_dto.image_url,
                        release_date=album_dto.release_date,
                        album_type=album_dto.album_type or "album",
                        total_tracks=album_dto.total_tracks,
                    )
                    stats["albums_synced"] += 1
                except Exception as e:
                    logger.warning(f"Failed to save album {album_dto.title}: {e}")
            
            # Update sync status
            await self.repo.update_sync_status("new_releases")
            await self._session.commit()
            
            stats["synced"] = True
            logger.info(f"SpotifySyncService: New releases synced - {stats['albums_synced']} albums")
            
        except Exception as e:
            logger.error(f"SpotifySyncService: New releases sync failed: {e}")
            stats["error"] = str(e)
        
        return stats

    # =========================================================================
    # ALBUM TRACKS SYNC
    # =========================================================================

    async def sync_album_tracks(
        self, album_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync tracks for a specific album from Spotify.

        Hey future me - refactored for SpotifyPlugin!
        No more access_token - plugin manages auth internally.
        Called when user navigates to album detail page.

        Args:
            album_id: Spotify album ID
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "error": None,
            "skipped_cooldown": False,
        }

        try:
            # Check if album exists
            album = await self.repo.get_album_by_id(album_id)
            if not album:
                stats["error"] = f"Album {album_id} not found"
                return stats

            # Check cooldown
            # Hey future me - use ensure_utc_aware() because SQLite returns naive datetimes!
            if not force and album.tracks_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.TRACKS_SYNC_COOLDOWN)
                if (
                    datetime.now(UTC)
                    < ensure_utc_aware(album.tracks_synced_at) + cooldown
                ):
                    stats["skipped_cooldown"] = True
                    stats["total"] = await self.repo.count_tracks_by_album(album_id)
                    return stats

            # Fetch album with tracks from Spotify using plugin
            album_dto = await self.spotify_plugin.get_album(album_id=album_id)

            if not album_dto:
                stats["error"] = f"Album {album_id} not found on Spotify"
                return stats

            # Album DTO contains tracks list
            track_dtos = album_dto.tracks if hasattr(album_dto, 'tracks') and album_dto.tracks else []

            for track_dto in track_dtos:
                await self._upsert_track_from_dto(track_dto, album_id)
                stats["added"] += 1

            stats["total"] = len(track_dtos)

            # Mark tracks as synced
            await self.repo.set_tracks_synced(album_id)
            await self._session.commit()

            stats["synced"] = True
            logger.info(f"Synced {len(track_dtos)} tracks for album {album_id}")

        except Exception as e:
            logger.error(f"Error syncing tracks for album {album_id}: {e}")
            stats["error"] = str(e)

        return stats

    async def _upsert_track_from_dto(self, track_dto: Any, album_id: str) -> None:
        """Insert or update a Spotify track in DB from TrackDTO.

        Hey future me - DTO version of _upsert_track!
        TrackDTO has spotify_id (not id) and isrc directly on object.
        """
        from soulspot.domain.dtos import TrackDTO

        if not isinstance(track_dto, TrackDTO):
            logger.warning(f"Expected TrackDTO, got {type(track_dto)}")
            return

        spotify_id = track_dto.spotify_id
        if not spotify_id:
            logger.warning("TrackDTO missing spotify_id, skipping")
            return

        name = track_dto.title or "Unknown"
        track_number = track_dto.track_number or 1
        disc_number = track_dto.disc_number or 1
        duration_ms = track_dto.duration_ms or 0
        explicit = track_dto.explicit or False
        preview_url = track_dto.preview_url
        isrc = track_dto.isrc

        await self.repo.upsert_track(
            spotify_id=spotify_id,
            album_id=album_id,
            name=name,
            track_number=track_number,
            disc_number=disc_number,
            duration_ms=duration_ms,
            explicit=explicit,
            preview_url=preview_url,
            isrc=isrc,
        )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_artists(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """Get followed artists from DB."""
        return await self.repo.get_all_artists(limit=limit, offset=offset)

    async def get_artist(self, spotify_id: str) -> Any | None:
        """Get a single artist from DB."""
        return await self.repo.get_artist_by_id(spotify_id)

    async def get_artist_albums(
        self, artist_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get albums for an artist from DB."""
        return await self.repo.get_albums_by_artist(
            artist_id=artist_id, limit=limit, offset=offset
        )

    async def get_album(self, spotify_id: str) -> Any | None:
        """Get a single album from DB."""
        return await self.repo.get_album_by_id(spotify_id)

    async def get_album_tracks(
        self, album_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get tracks for an album from DB."""
        return await self.repo.get_tracks_by_album(
            album_id=album_id, limit=limit, offset=offset
        )

    # NOTE: get_album_detail_view() moved to LibraryViewService (Dec 2025)
    # Use LibraryViewService.get_album_detail_view() for ViewModels!

    async def get_sync_status(self, sync_type: str) -> Any | None:
        """Get sync status for display."""
        return await self.repo.get_sync_status(sync_type)

    async def count_artists(self) -> int:
        """Get total artist count."""
        return await self.repo.count_artists()

    # =========================================================================
    # USER PLAYLISTS SYNC
    # =========================================================================
    # Hey future me - this syncs playlists from Spotify to our playlists table!
    # Playlists are different from artists/albums:
    # - They go to the PLAYLISTS table (not a separate spotify_playlists table)
    # - They have source='SPOTIFY' to distinguish from manual playlists
    # - The spotify_uri column identifies them uniquely
    # =========================================================================

    async def sync_user_playlists(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's playlists from Spotify with diff logic.

        Hey future me - refactored for SpotifyPlugin!
        No more access_token - plugin manages auth internally.
        Similar to artists sync but for playlists. Called on page load.
        Checks settings to see if playlist sync is enabled.

        Args:
            force: Skip cooldown check

        Returns:
            Dict with sync stats (added, removed, total, etc.)
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "removed": 0,
            "unchanged": 0,
            "error": None,
            "skipped_cooldown": False,
            "skipped_disabled": False,
            "skipped_provider_disabled": False,
            "skipped_not_authenticated": False,
        }

        try:
            # Hey future me - PROVIDER LEVEL CHECK FIRST!
            if self._settings_service and not await self._settings_service.is_provider_enabled("spotify"):
                stats["skipped_provider_disabled"] = True
                logger.debug("Spotify provider is disabled, skipping playlists sync")
                return stats

            # Hey future me - AUTH CHECK USING can_use() - checks capability + auth!
            from soulspot.domain.ports.plugin import PluginCapability
            if not self.spotify_plugin.can_use(PluginCapability.USER_PLAYLISTS):
                stats["skipped_not_authenticated"] = True
                logger.debug("Spotify not authenticated, skipping playlists sync")
                return stats

            # Check if playlist sync is enabled (feature-level)
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_playlists_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Playlist sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("user_playlists"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_spotify_playlists()
                logger.debug("Skipping user playlists sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="running",
            )
            await self._session.commit()

            # Fetch all playlists from Spotify
            spotify_playlists = await self._fetch_all_user_playlists()
            spotify_uris = {f"spotify:playlist:{p.spotify_id}" for p in spotify_playlists if p.spotify_id}

            # Get existing Spotify playlist URIs from DB
            db_uris = await self.repo.get_spotify_playlist_uris()

            # Diff calculation
            to_add = spotify_uris - db_uris
            to_remove = db_uris - spotify_uris
            unchanged = spotify_uris & db_uris

            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)
            stats["unchanged"] = len(unchanged)
            stats["total"] = len(spotify_uris)

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Add new playlists
            for playlist_dto in spotify_playlists:
                if playlist_dto.spotify_id:
                    spotify_uri = f"spotify:playlist:{playlist_dto.spotify_id}"
                    if spotify_uri in to_add or spotify_uri in unchanged:
                        await self._upsert_playlist_from_dto(
                            playlist_dto, download_images=should_download_images
                        )

            # Remove playlists that no longer exist on Spotify
            should_remove = True
            if to_remove:
                if self._settings_service:
                    should_remove = await self._settings_service.should_remove_unfollowed_playlists()

                if should_remove:
                    removed_count = await self.repo.delete_playlists_by_uris(to_remove)
                    logger.info(
                        f"Removed {removed_count} deleted Spotify playlists from DB"
                    )

                    # Cleanup orphaned images
                    if self._image_service:
                        for uri in to_remove:
                            playlist_id = uri.replace("spotify:playlist:", "")
                            await self._image_service.delete_image_async(
                                f"spotify/playlists/{playlist_id}.webp"
                            )
            else:
                should_remove = False  # No playlists to remove

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="idle",
                items_synced=len(spotify_playlists),
                items_added=len(to_add),
                items_removed=len(to_remove) if should_remove else 0,
                cooldown_minutes=self.PLAYLISTS_SYNC_COOLDOWN,
            )

            await self._session.commit()
            stats["synced"] = True

            logger.info(
                f"User playlists sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} removed"
            )

        except Exception as e:
            logger.error(f"Error syncing user playlists: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="error",
                error_message=str(e),
            )
            await self._session.commit()

        return stats

    async def _fetch_all_user_playlists(
        self,
    ) -> list[Any]:
        """Fetch all user playlists from Spotify using SpotifyPlugin.

        Hey future me - returns PlaylistDTOs now!
        Plugin handles pagination and auth internally.
        """
        from soulspot.domain.dtos import PlaylistDTO

        all_playlists: list[PlaylistDTO] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_plugin.get_user_playlists(
                limit=limit,
                offset=offset,
            )

            items = response.items if response.items else []
            if not items:
                break

            all_playlists.extend(items)

            # Check if there are more pages
            if response.next_offset is None:
                break

            offset = response.next_offset

        return all_playlists

    async def _upsert_playlist_from_dto(
        self,
        playlist_dto: Any,
        download_images: bool = False,
    ) -> None:
        """Insert or update a Spotify playlist in DB from PlaylistDTO.

        Hey future me - DTO version of _upsert_playlist!
        PlaylistDTO has spotify_id, artwork_url (not images array).

        Args:
            playlist_dto: PlaylistDTO from SpotifyPlugin
            download_images: Whether to download cover image locally
        """
        from soulspot.domain.dtos import PlaylistDTO

        if not isinstance(playlist_dto, PlaylistDTO):
            logger.warning(f"Expected PlaylistDTO, got {type(playlist_dto)}")
            return

        spotify_id = playlist_dto.spotify_id
        if not spotify_id:
            logger.warning("PlaylistDTO missing spotify_id, skipping")
            return

        spotify_uri = f"spotify:playlist:{spotify_id}"
        name = playlist_dto.name or "Unknown"
        description = playlist_dto.description or ""
        cover_url = playlist_dto.cover_url

        # Download image if enabled
        cover_path = None
        if download_images and cover_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_playlist_by_uri(spotify_uri)
            existing_url = existing.cover_url if existing else None
            existing_path = existing.cover_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, cover_url, existing_path
            ):
                cover_path = await self._image_service.download_playlist_image(
                    spotify_id, cover_url
                )
            elif existing_path:
                cover_path = existing_path  # Keep existing path

        await self.repo.upsert_playlist(
            spotify_uri=spotify_uri,
            name=name,
            description=description,
            cover_url=cover_url,
            cover_path=cover_path,
            source="SPOTIFY",
        )

    # =========================================================================
    # LIKED SONGS SYNC
    # =========================================================================
    # Hey future me - "Liked Songs" is a SPECIAL playlist!
    # - It's not a real Spotify playlist (no playlist ID)
    # - We create a local playlist with is_liked_songs=True
    # - Tracks come from GET /me/tracks endpoint
    # =========================================================================

    async def sync_liked_songs(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's Liked Songs from Spotify.

        Hey future me - refactored for SpotifyPlugin!
        No more access_token - plugin manages auth internally.
        Creates/updates a special playlist with is_liked_songs=True.
        This playlist doesn't have a Spotify URI since "Liked Songs"
        isn't a real playlist on Spotify.

        Args:
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "error": None,
            "skipped_cooldown": False,
            "skipped_disabled": False,
            "skipped_provider_disabled": False,
            "skipped_not_authenticated": False,
        }

        try:
            # Hey future me - PROVIDER LEVEL CHECK FIRST!
            if self._settings_service and not await self._settings_service.is_provider_enabled("spotify"):
                stats["skipped_provider_disabled"] = True
                logger.debug("Spotify provider is disabled, skipping Liked Songs sync")
                return stats

            # Hey future me - AUTH CHECK USING can_use() - checks capability + auth!
            from soulspot.domain.ports.plugin import PluginCapability
            if not self.spotify_plugin.can_use(PluginCapability.USER_SAVED_TRACKS):
                stats["skipped_not_authenticated"] = True
                logger.debug("Spotify not authenticated, skipping Liked Songs sync")
                return stats

            # Check if Liked Songs sync is enabled (feature-level)
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_liked_songs_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Liked Songs sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("liked_songs"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_liked_songs_tracks()
                logger.debug("Skipping Liked Songs sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="running",
            )
            await self._session.commit()

            # Fetch all liked songs from Spotify
            liked_tracks = await self._fetch_all_liked_songs()
            stats["total"] = len(liked_tracks)

            # Ensure the Liked Songs playlist exists
            liked_playlist = await self.repo.get_or_create_liked_songs_playlist()

            # Sync tracks to playlist
            # Hey - we replace all tracks because Spotify doesn't give us diff info
            added_count = await self.repo.sync_liked_songs_tracks(
                playlist_id=liked_playlist.id,
                tracks=liked_tracks,
            )
            stats["added"] = added_count

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="idle",
                items_synced=len(liked_tracks),
                items_added=added_count,
                cooldown_minutes=self.PLAYLISTS_SYNC_COOLDOWN,
            )

            await self._session.commit()
            stats["synced"] = True

            logger.info(f"Liked Songs sync complete: {stats['total']} tracks")

        except Exception as e:
            from soulspot.infrastructure.observability.log_messages import LogMessages
            logger.error(
                LogMessages.sync_failed(
                    entity="Liked Songs",
                    source="Spotify",
                    error=str(e),
                    hint="Check if liked tracks have valid album/artist data in Spotify"
                ),
                exc_info=True
            )
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="error",
                error_message=str(e),
            )
            await self._session.commit()

        return stats

    async def _fetch_all_liked_songs(self) -> list[dict[str, Any]]:
        """Fetch all liked songs from Spotify using SpotifyPlugin.

        Hey future me - returns TrackDTOs converted to dicts for compatibility!
        The repo.sync_liked_songs_tracks expects dict format still.
        We convert TrackDTOs to dicts with added_at field.

        Returns list of track data with added_at timestamp.
        """

        all_tracks: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_plugin.get_saved_tracks(
                limit=limit,
                offset=offset,
            )

            items = response.items if response.items else []
            if not items:
                break

            # Convert TrackDTOs to dict format expected by repo
            for track_dto in items:
                track_dict = {
                    "id": track_dto.spotify_id,
                    "name": track_dto.title,
                    "duration_ms": track_dto.duration_ms,
                    "explicit": track_dto.explicit,
                    "preview_url": track_dto.preview_url,
                    "isrc": track_dto.isrc,
                    "track_number": track_dto.track_number,
                    "disc_number": track_dto.disc_number,
                    # added_at is not on DTO, use current time
                    "added_at": None,
                }
                # Include artists info if available
                if track_dto.artists:
                    track_dict["artists"] = [
                        {"id": a.spotify_id, "name": a.name}
                        for a in track_dto.artists
                    ]
                # Include album info if available
                if track_dto.album:
                    track_dict["album"] = {
                        "id": track_dto.album.spotify_id,
                        "name": track_dto.album.title,
                        "images": [{"url": track_dto.album.artwork_url}]
                        if track_dto.album.artwork_url
                        else [],
                    }
                all_tracks.append(track_dict)

            # Check if there are more pages
            if response.next_offset is None:
                break

            offset = response.next_offset

        return all_tracks

    # =========================================================================
    # SAVED ALBUMS SYNC
    # =========================================================================
    # Hey future me - "Saved Albums" are albums the user explicitly saved!
    # Different from artist albums which come from followed artists.
    # We set is_saved=True on these albums in spotify_albums table.
    # This requires ensuring the artist exists first (create if not followed).
    # =========================================================================

    async def sync_saved_albums(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's Saved Albums from Spotify.

        Hey future me - refactored for SpotifyPlugin!
        No more access_token - plugin manages auth internally.
        Saved albums are albums the user explicitly saved to their library.
        These get is_saved=True flag so they persist even if artist is unfollowed.

        Args:
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "removed": 0,
            "error": None,
            "skipped_cooldown": False,
            "skipped_disabled": False,
            "skipped_provider_disabled": False,
            "skipped_not_authenticated": False,
        }

        try:
            # Hey future me - PROVIDER LEVEL CHECK FIRST!
            if self._settings_service and not await self._settings_service.is_provider_enabled("spotify"):
                stats["skipped_provider_disabled"] = True
                logger.debug("Spotify provider is disabled, skipping Saved Albums sync")
                return stats

            # Hey future me - AUTH CHECK USING can_use() - checks capability + auth!
            from soulspot.domain.ports.plugin import PluginCapability
            if not self.spotify_plugin.can_use(PluginCapability.USER_SAVED_ALBUMS):
                stats["skipped_not_authenticated"] = True
                logger.debug("Spotify not authenticated, skipping Saved Albums sync")
                return stats

            # Check if Saved Albums sync is enabled (feature-level)
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_saved_albums_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Saved Albums sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("saved_albums"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_saved_albums()
                logger.debug("Skipping Saved Albums sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="running",
            )
            await self._session.commit()

            # Fetch all saved albums from Spotify
            saved_albums = await self._fetch_all_saved_albums()
            spotify_album_ids = {a.spotify_id for a in saved_albums if a.spotify_id}

            # Get existing saved album IDs from DB
            db_saved_ids = await self.repo.get_saved_album_ids()

            # Diff calculation
            to_add = spotify_album_ids - db_saved_ids
            to_remove = db_saved_ids - spotify_album_ids

            stats["total"] = len(spotify_album_ids)
            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Process saved albums (now using AlbumDTOs)
            for album_dto in saved_albums:
                if not album_dto.spotify_id:
                    continue

                # Ensure artist exists (create minimal entry if not followed)
                # AlbumDTO has artist_name and artist_spotify_id, not an artists list
                if album_dto.artist_spotify_id and album_dto.artist_name:
                    # Create a minimal ArtistDTO for the artist
                    from soulspot.domain.dtos import ArtistDTO
                    
                    primary_artist = ArtistDTO(
                        name=album_dto.artist_name,
                        source_service=album_dto.source_service,
                        spotify_id=album_dto.artist_spotify_id,
                    )
                    await self._ensure_artist_exists_from_dto(primary_artist)
                    artist_id = album_dto.artist_spotify_id
                else:
                    continue  # Skip albums without artist info

                # Upsert album with is_saved=True
                await self._upsert_saved_album_from_dto(
                    album_dto,
                    artist_id,
                    download_images=should_download_images,
                )

            # Remove is_saved flag from albums no longer saved
            if to_remove:
                await self.repo.unmark_albums_as_saved(to_remove)
                logger.info(f"Unmarked {len(to_remove)} albums as no longer saved")

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="idle",
                items_synced=len(saved_albums),
                items_added=len(to_add),
                items_removed=len(to_remove),
                cooldown_minutes=self.ALBUMS_SYNC_COOLDOWN,
            )

            await self._session.commit()
            stats["synced"] = True

            logger.info(
                f"Saved Albums sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} unmarked"
            )

        except Exception as e:
            logger.error(f"Error syncing Saved Albums: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="error",
                error_message=str(e),
            )
            await self._session.commit()

        return stats

    async def _fetch_all_saved_albums(self) -> list[Any]:
        """Fetch all saved albums from Spotify using SpotifyPlugin.

        Hey future me - returns AlbumDTOs now!
        Plugin handles pagination and auth internally.

        Returns list of AlbumDTOs.
        """
        from soulspot.domain.dtos import AlbumDTO

        all_albums: list[AlbumDTO] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_plugin.get_saved_albums(
                limit=limit,
                offset=offset,
            )

            items = response.items if response.items else []
            if not items:
                break

            all_albums.extend(items)

            # Check if there are more pages
            if response.next_offset is None:
                break

            offset = response.next_offset

        return all_albums

    async def _ensure_artist_exists_from_dto(self, artist_dto: Any) -> None:
        """Ensure an artist exists in DB from ArtistDTO (create minimal entry if not).

        Hey future me - DTO version of _ensure_artist_exists!
        Called when syncing saved albums where the artist might not be followed.
        Creates a minimal artist entry without full metadata.

        Args:
            artist_dto: ArtistDTO with at least spotify_id and name
        """
        from soulspot.domain.dtos import ArtistDTO

        if not isinstance(artist_dto, ArtistDTO):
            logger.warning(f"Expected ArtistDTO, got {type(artist_dto)}")
            return

        spotify_id = artist_dto.spotify_id
        if not spotify_id:
            return

        # Check if artist exists
        existing = await self.repo.get_artist_by_id(spotify_id)
        if existing:
            return  # Artist exists, nothing to do

        # Create minimal artist entry
        name = artist_dto.name or "Unknown"
        await self.repo.upsert_artist(
            spotify_id=spotify_id,
            name=name,
            image_url=artist_dto.image_url,
            genres=artist_dto.genres or [],
            popularity=artist_dto.popularity,
            follower_count=artist_dto.followers,
        )
        logger.debug(f"Created minimal artist entry for: {name} ({spotify_id})")

    async def _upsert_saved_album_from_dto(
        self,
        album_dto: Any,
        artist_id: str,
        download_images: bool = False,
    ) -> None:
        """Insert or update a saved album in DB from AlbumDTO with is_saved=True.

        Hey future me - DTO version of _upsert_saved_album!
        AlbumDTO has artwork_url directly.

        Args:
            album_dto: AlbumDTO from SpotifyPlugin
            artist_id: Spotify artist ID
            download_images: Whether to download cover image locally
        """
        from soulspot.domain.dtos import AlbumDTO

        if not isinstance(album_dto, AlbumDTO):
            logger.warning(f"Expected AlbumDTO, got {type(album_dto)}")
            return

        spotify_id = album_dto.spotify_id
        if not spotify_id:
            return

        name = album_dto.title or "Unknown"
        image_url = album_dto.artwork_url
        release_date = album_dto.release_date
        release_date_precision = "day" if release_date else None
        album_type = album_dto.album_type or "album"
        total_tracks = album_dto.total_tracks or 0

        # Download image if enabled
        image_path = None
        if download_images and image_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_album_by_id(spotify_id)
            existing_url = existing.image_url if existing else None
            existing_path = existing.image_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, image_url, existing_path
            ):
                image_path = await self._image_service.download_album_image(
                    spotify_id, image_url
                )
            elif existing_path:
                image_path = existing_path

        await self.repo.upsert_album(
            spotify_id=spotify_id,
            artist_id=artist_id,
            name=name,
            image_url=image_url,
            image_path=image_path,
            release_date=release_date,
            release_date_precision=release_date_precision,
            album_type=album_type,
            total_tracks=total_tracks,
            is_saved=True,
        )

    # =========================================================================
    # IMAGE DOWNLOAD INTEGRATION
    # =========================================================================

    async def _download_artist_image_if_needed(
        self,
        spotify_id: str,
        new_url: str | None,
        existing_url: str | None = None,
        existing_path: str | None = None,
    ) -> str | None:
        """Download artist image if enabled and needed.

        Args:
            spotify_id: Spotify artist ID
            new_url: New image URL from Spotify
            existing_url: Previously stored URL (for comparison)
            existing_path: Previously stored local path

        Returns:
            Local path to image, or None if not downloaded
        """
        if not self._image_service or not self._settings_service:
            return None

        should_download = await self._settings_service.should_download_images()
        if not should_download:
            return existing_path  # Keep existing path if any

        if not new_url:
            return None

        if await self._image_service.should_redownload(
            existing_url, new_url, existing_path
        ):
            return await self._image_service.download_artist_image(spotify_id, new_url)

        return existing_path

    # =========================================================================
    # FULL SYNC (ALL ENABLED SYNCS)
    # =========================================================================

    async def run_full_sync(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Run all enabled sync operations.

        Hey future me - refactored for SpotifyPlugin!
        No more access_token - plugin manages auth internally.
        Convenience method to run artists, playlists, liked songs, and saved albums
        sync in sequence. Checks settings for each sync type.

        Args:
            force: Skip cooldown checks

        Returns:
            Dict with results from each sync operation
        """
        results: dict[str, Any] = {
            "artists": None,
            "playlists": None,
            "liked_songs": None,
            "saved_albums": None,
        }

        # Artists sync
        results["artists"] = await self.sync_followed_artists(force=force)

        # Playlists sync
        results["playlists"] = await self.sync_user_playlists(force=force)

        # Liked Songs sync
        results["liked_songs"] = await self.sync_liked_songs(force=force)

        # Saved Albums sync
        results["saved_albums"] = await self.sync_saved_albums(force=force)

        return results
