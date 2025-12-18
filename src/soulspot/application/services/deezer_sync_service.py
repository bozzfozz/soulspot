# Hey future me - NEUER SERVICE für Deezer Sync!
# Das ist Phase 2 des Service Separation Plans.
#
# Dieser Service synct Deezer-Daten zur Datenbank:
# - Charts (Top Tracks, Albums, Artists)
# - New Releases (Editorial + Charts)
# - Artist Albums (Fallback wenn Spotify nicht auth)
# - Artist Top Tracks
#
# WICHTIG: Deezer braucht KEINE OAuth für die meisten Operationen!
# Das macht diesen Service perfekt als Fallback wenn Spotify nicht verbunden.
#
# Was dieser Service macht:
# - sync_charts() → Charts in DB speichern
# - sync_new_releases() → New Releases in DB speichern
# - sync_artist_albums() → Artist Discographie synken
# - sync_artist_top_tracks() → Top Tracks eines Artists synken
#
# Was dieser Service NICHT macht:
# - User Library (Favorites, Playlists) - das braucht OAuth
# - ViewModels erstellen (das macht LibraryViewService)
"""Deezer Sync Service - Syncs Deezer data to database."""

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.persistence.models import ensure_utc_aware
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

if TYPE_CHECKING:
    from soulspot.application.services.images import ImageService
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

logger = logging.getLogger(__name__)


class DeezerSyncService:
    """Service für Deezer-Daten Synchronisation.
    
    Hey future me - das ist der DEEZER Sync Service nach Clean Architecture!
    
    Dieser Service:
    1. Holt Daten von Deezer via DeezerPlugin
    2. Konvertiert zu DB-Modellen
    3. Speichert in unified soulspot_* Tabellen mit source='deezer'
    
    KEINE OAuth nötig für:
    - Charts (get_chart_tracks, get_chart_albums)
    - New Releases (get_browse_new_releases, get_editorial_releases)
    - Artist Lookup (get_artist, get_artist_albums)
    
    OAuth NUR für:
    - User Library (Favorites, Playlists)
    """
    
    # Cooldown in Minuten bevor neu gesynct wird
    CHARTS_SYNC_COOLDOWN = 60  # Charts ändern sich nicht so schnell
    NEW_RELEASES_SYNC_COOLDOWN = 60
    ARTIST_ALBUMS_SYNC_COOLDOWN = 120  # 2 Stunden
    TRACKS_SYNC_COOLDOWN = 30  # 30 Minuten für Album-Tracks
    
    def __init__(
        self,
        session: AsyncSession,
        deezer_plugin: "DeezerPlugin",
        image_service: "ImageService | None" = None,
    ) -> None:
        """Initialize Deezer sync service.
        
        Hey future me - DeezerPlugin braucht KEINE OAuth für sync!
        Alle Sync-Methoden hier nutzen die Public API.
        
        Args:
            session: Database session
            deezer_plugin: DeezerPlugin für API calls
            image_service: ImageService für Bilder-Downloads (optional)
        """
        self._session = session
        self._plugin = deezer_plugin
        self._image_service = image_service
        
        # Repositories für DB-Zugriff
        self._artist_repo = ArtistRepository(session)
        self._album_repo = AlbumRepository(session)
        self._track_repo = TrackRepository(session)
        
        # Cache für Sync-Status
        self._last_sync_times: dict[str, datetime] = {}
    
    # =========================================================================
    # SYNC STATUS HELPERS
    # =========================================================================
    
    def _should_sync(self, sync_type: str, cooldown_minutes: int) -> bool:
        """Check if sync should run based on cooldown.
        
        Hey future me - das verhindert API-Spam!
        Wir synken nicht jedes Mal, sondern respektieren Cooldowns.
        """
        last_sync = self._last_sync_times.get(sync_type)
        if not last_sync:
            return True
        
        now = datetime.now(UTC)
        elapsed_minutes = (now - last_sync).total_seconds() / 60
        return elapsed_minutes >= cooldown_minutes
    
    def _mark_synced(self, sync_type: str) -> None:
        """Mark sync as completed."""
        self._last_sync_times[sync_type] = datetime.now(UTC)
    
    # =========================================================================
    # CHARTS SYNC (DEPRECATED - Use in-memory cache!)
    # =========================================================================
    
    async def sync_charts(
        self, 
        limit: int = 50,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer charts to database.
        
        ⚠️ DEPRECATED: Charts should NOT be written to DB!
        Use DeezerSyncWorker._charts_cache (in-memory) instead.
        
        Hey future me - Diese Methode NICHT mehr verwenden!
        Charts dürfen nicht in soulspot_* Tabellen geschrieben werden,
        weil sie dann mit der User Library vermischt werden.
        
        Stattdessen: DeezerSyncWorker.get_cached_charts() nutzen.
        
        Returns:
            Dict with deprecated warning
        """
        import warnings
        warnings.warn(
            "DeezerSyncService.sync_charts() is deprecated. "
            "Charts use in-memory cache now via DeezerSyncWorker. "
            "Use ChartsService for live data.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        logger.warning(
            "sync_charts() DEPRECATED! Charts should use in-memory cache, "
            "not database. Use DeezerSyncWorker.get_cached_charts()."
        )
        
        return {
            "deprecated": True,
            "reason": "Charts use in-memory cache now, not DB",
            "alternative": "DeezerSyncWorker.get_cached_charts() or ChartsService",
        }
    
    # =========================================================================
    # NEW RELEASES SYNC (DEPRECATED - Use in-memory cache!)
    # =========================================================================
    
    async def sync_new_releases(
        self,
        limit: int = 50,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer new releases to database.
        
        ⚠️ DEPRECATED: New Releases should NOT be written to DB!
        Use DeezerSyncWorker._new_releases_cache (in-memory) instead.
        
        Hey future me - Diese Methode NICHT mehr verwenden!
        New Releases dürfen nicht in soulspot_* Tabellen geschrieben werden,
        weil sie dann mit der User Library vermischt werden.
        
        User's Library sollte NUR enthalten:
        - Followed Artists (und deren Alben via sync_artist_albums)
        - Liked Songs
        - Saved Albums
        - User Playlists
        
        New Releases sind Browse-Content, nicht persönliche Library!
        
        Stattdessen: DeezerSyncWorker.get_cached_new_releases() nutzen.
        
        Returns:
            Dict with deprecated warning
        """
        import warnings
        warnings.warn(
            "DeezerSyncService.sync_new_releases() is deprecated. "
            "New Releases use in-memory cache now via DeezerSyncWorker. "
            "Use DeezerSyncWorker.get_cached_new_releases() for live data.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        logger.warning(
            "sync_new_releases() DEPRECATED! New Releases should use in-memory cache, "
            "not database. Use DeezerSyncWorker.get_cached_new_releases()."
        )
        
        return {
            "deprecated": True,
            "reason": "New Releases use in-memory cache now, not DB",
            "alternative": "DeezerSyncWorker.get_cached_new_releases()",
        }
    
    # =========================================================================
    # ARTIST ALBUMS SYNC (FALLBACK für Spotify!)
    # =========================================================================
    
    async def sync_artist_albums(
        self,
        deezer_artist_id: str,
        limit: int = 50,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync artist albums from Deezer to database.
        
        Hey future me - DAS IST DER FALLBACK wenn Spotify nicht auth!
        Deezer braucht keine OAuth für Artist Albums.
        
        Args:
            deezer_artist_id: Deezer artist ID
            limit: Max albums to sync
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        cache_key = f"artist_albums_{deezer_artist_id}"
        if not force and not self._should_sync(cache_key, self.ARTIST_ALBUMS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
                "next_sync_in_minutes": self.ARTIST_ALBUMS_SYNC_COOLDOWN,
            }
        
        result = {
            "albums_synced": 0,
            "errors": [],
        }
        
        try:
            # Get albums from Deezer
            albums = await self._plugin.get_artist_albums(deezer_artist_id, limit=limit)
            
            # Step 1: Ensure artist exists and get artist_id
            # We need artist_id to link albums properly
            artist_id: str | None = None
            
            if albums and albums[0]:
                # Get artist_id from first album DTO
                artist_id = await self._ensure_artist_exists(albums[0], is_chart=False)
            
            if not artist_id:
                logger.warning(
                    f"DeezerSyncService: Cannot sync albums for artist {deezer_artist_id} - no artist_id"
                )
                return {"albums_synced": 0, "error": "artist_not_found"}
            
            # Step 2: Sync albums with artist relationship
            for album_dto in albums:
                try:
                    await self._save_album_with_artist(album_dto, artist_id, is_chart=False)
                    result["albums_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Album {album_dto.title}: {e}")
            
            # Step 3: Mark artist's albums as synced
            # Hey future me - this is CRITICAL for the gradual background sync!
            # Without this, the same artist would be re-synced every cycle.
            await self._update_artist_albums_synced_at(deezer_artist_id)
            
            await self._session.commit()
            self._mark_synced(cache_key)
            
            logger.info(
                f"DeezerSyncService: Artist {deezer_artist_id} albums synced - "
                f"{result['albums_synced']} albums"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Artist albums sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def sync_artist_top_tracks(
        self,
        deezer_artist_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Sync artist top tracks from Deezer to database.
        
        Args:
            deezer_artist_id: Deezer artist ID
            limit: Max tracks to sync
            
        Returns:
            Sync result with counts
        """
        result = {
            "tracks_synced": 0,
            "errors": [],
        }
        
        try:
            top_tracks = await self._plugin.get_artist_top_tracks(
                deezer_artist_id, limit=limit
            )
            
            # Step 1: Ensure artist exists and get artist_id
            artist_id: str | None = None
            
            if top_tracks and top_tracks[0]:
                # Get artist_id from first track DTO
                artist_id = await self._ensure_artist_exists(top_tracks[0], is_chart=False)
            
            if not artist_id:
                logger.warning(
                    f"DeezerSyncService: Cannot sync tracks for artist {deezer_artist_id} - no artist_id"
                )
                return {"tracks_synced": 0, "error": "artist_not_found"}
            
            # Step 2: Sync tracks with artist relationship
            for track_dto in top_tracks:
                try:
                    await self._save_track_with_artist(track_dto, artist_id, is_chart=False)
                    result["tracks_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Track {track_dto.title}: {e}")
            
            await self._session.commit()
            
            logger.info(
                f"DeezerSyncService: Artist {deezer_artist_id} top tracks synced - "
                f"{result['tracks_synced']} tracks"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Artist top tracks sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    # =========================================================================
    # RELATED ARTISTS SYNC (Discovery Feature!) - NO AUTH REQUIRED!
    # =========================================================================
    
    async def sync_related_artists(
        self,
        deezer_artist_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync related artists for a specific artist from Deezer.
        
        Hey future me - das ist ein DISCOVERY Feature!
        KEIN OAuth nötig - Deezer Related Artists sind public!
        
        Use Case:
        - "Artists You Might Like" auf Artist-Detail-Seite
        - Discovery Recommendations
        - "Fans Also Like" Section
        
        Args:
            deezer_artist_id: Deezer artist ID
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        cache_key = f"related_artists_{deezer_artist_id}"
        if not force and not self._should_sync(cache_key, self.CHARTS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "synced": False,
            "artists_synced": 0,
            "errors": [],
        }
        
        try:
            # Get related artists from Deezer (NO OAuth needed!)
            related_artists = await self._plugin.get_related_artists(deezer_artist_id)
            
            for artist_dto in related_artists:
                try:
                    await self._save_artist_from_dto(artist_dto, is_related=True)
                    result["artists_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Artist {artist_dto.name}: {e}")
            
            # TODO: Store the relationship (artist_id -> related_artist_id)
            # This requires a new table: artist_relations
            # For now, we just cache the related artists in DB
            
            await self._session.commit()
            self._mark_synced(cache_key)
            
            result["synced"] = True
            logger.info(
                f"DeezerSyncService: Related artists for {deezer_artist_id} synced - "
                f"{result['artists_synced']} artists"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Related artists sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    # =========================================================================
    # DB SAVE HELPERS
    # =========================================================================
    # Hey future me - diese Methoden speichern DTOs in der unified Library!
    # Alle Einträge bekommen source='deezer' für spätere Filterung.
    
    async def _save_artist_from_dto(
        self,
        artist_dto: Any,
        is_chart: bool = False,
        is_related: bool = False,
    ) -> None:
        """Save artist DTO to database.
        
        Hey future me - hier speichern wir in soulspot_artists!
        source='deezer' markiert, dass es von Deezer kommt.
        
        Note: is_chart and is_related parameters are kept for API compatibility
        but not stored in database (fields don't exist in ArtistModel).
        """
        from soulspot.infrastructure.persistence.models import ArtistModel
        
        # Check if artist exists (by deezer_id or name)
        existing = await self._artist_repo.get_by_deezer_id(artist_dto.deezer_id)
        
        # Hey future me - DTO.image ist ImageRef, Model.image_url ist DB-Spalte
        dto_image_url = artist_dto.image.url if artist_dto.image else None
        deezer_id = artist_dto.deezer_id
        
        if existing:
            # Update existing
            existing.name = artist_dto.name
            existing.image_url = dto_image_url or existing.image_url
            
            # Download artist image if URL changed (Deezer provider)
            if self._image_service and deezer_id and dto_image_url:
                if await self._image_service.should_redownload(
                    existing.image_url, dto_image_url, existing.image_path
                ):
                    image_path = await self._image_service.download_artist_image(
                        deezer_id, dto_image_url, provider="deezer"
                    )
                    if image_path:
                        existing.image_path = image_path
            # Note: is_chart and is_related flags are not stored in model
        else:
            # Create new - Download artist image for new artist (Deezer provider)
            image_path = None
            if self._image_service and deezer_id and dto_image_url:
                image_path = await self._image_service.download_artist_image(
                    deezer_id, dto_image_url, provider="deezer"
                )
            
            new_artist = ArtistModel(
                name=artist_dto.name,
                deezer_id=artist_dto.deezer_id,
                image_url=dto_image_url,
                image_path=image_path,
                source="deezer",
            )
            self._session.add(new_artist)
    
    async def _ensure_artist_exists(
        self,
        artist_dto: Any,
        is_chart: bool = False,
    ) -> str | None:
        """Ensure artist exists in database and return its internal ID.
        
        CRITICAL FIX (Dec 2025): Prevents duplicate artists by checking name first!
        - First checks for existing artist by deezer_id
        - Then checks for existing artist by NAME (prevents Spotify/Deezer duplicates)
        - Only creates NEW artist if neither exists
        - Updates source to "hybrid" if artist exists from other provider
        
        Args:
            artist_dto: Artist DTO from plugin (must have: name, deezer_id, and optionally artwork_url, genres, tags)
            is_chart: Whether this is from charts
            
        Returns:
            Internal artist ID (UUID) or None if creation failed
        """
        from soulspot.domain.entities import Artist, ArtistSource
        from soulspot.infrastructure.persistence.models import ArtistModel
        from sqlalchemy import func, select
        
        try:
            # Extract artist data from DTO (handle both ArtistDTO and Album/TrackDTO)
            artist_name = getattr(artist_dto, 'name', None) or getattr(artist_dto, 'artist_name', None)
            deezer_id = getattr(artist_dto, 'deezer_id', None) or getattr(artist_dto, 'artist_deezer_id', None)
            # Hey future me - DTOs nutzen jetzt ImageRef! ArtistDTO.image.url statt .artwork_url
            # Fallback auf alte Attribute für Backwards-Compat mit gemischten DTOs
            image_attr = getattr(artist_dto, 'image', None)
            artwork_url = getattr(image_attr, 'url', None) if image_attr else None
            genres = getattr(artist_dto, 'genres', None)
            tags = getattr(artist_dto, 'tags', None)
            
            if not artist_name or not deezer_id:
                logger.warning(f"Cannot ensure artist exists - missing name or deezer_id")
                return None
            
            # STEP 1: Check if artist exists by deezer_id
            existing_model = None
            if deezer_id:
                existing_model = await self._artist_repo.get_by_deezer_id(deezer_id)
            
            # STEP 2: If not found by deezer_id, check by NAME (prevent duplicates!)
            # CRITICAL FIX: Case-insensitive + whitespace normalization!
            if not existing_model:
                normalized_name = artist_name.strip().lower()
                stmt = select(ArtistModel).where(func.lower(func.trim(ArtistModel.name)) == normalized_name)
                result = await self._session.execute(stmt)
                # Use first() instead of scalar_one_or_none() to handle existing duplicates gracefully
                existing_model = result.scalars().first()
            
            if existing_model:
                # Update existing artist - add deezer_id if missing
                if not existing_model.deezer_id:
                    existing_model.deezer_id = deezer_id
                
                # Update source to "hybrid" if it was only from one provider before
                if existing_model.source == "spotify":
                    existing_model.source = "hybrid"
                elif existing_model.source == "local":
                    existing_model.source = "hybrid"
                # If already "deezer" or "hybrid", keep as is
                
                existing_model.name = artist_name
                existing_model.image_url = artwork_url or existing_model.image_url
                if genres:
                    existing_model.genres = json.dumps(genres)
                if tags:
                    existing_model.tags = json.dumps(tags)
                
                # Download artist image if URL changed (Deezer provider)
                if self._image_service and deezer_id and artwork_url:
                    if await self._image_service.should_redownload(
                        existing_model.image_url, artwork_url, existing_model.image_path
                    ):
                        image_path = await self._image_service.download_artist_image(
                            deezer_id, artwork_url, provider="deezer"
                        )
                        if image_path:
                            existing_model.image_path = image_path
                
                return str(existing_model.id)
            else:
                # Create new artist with proper domain entity
                import uuid
                artist_id = str(uuid.uuid4())
                
                # Download artist image for new artist (Deezer provider)
                image_path = None
                if self._image_service and deezer_id and artwork_url:
                    image_path = await self._image_service.download_artist_image(
                        deezer_id, artwork_url, provider="deezer"
                    )
                
                new_artist = ArtistModel(
                    id=artist_id,
                    name=artist_name,
                    deezer_id=deezer_id,
                    image_url=artwork_url,
                    image_path=image_path,
                    source="deezer",  # Source field in model accepts string
                    genres=json.dumps(genres) if genres else None,
                    tags=json.dumps(tags) if tags else None,
                )
                self._session.add(new_artist)
                await self._session.flush()  # Get the ID immediately
                return artist_id
                
        except Exception as e:
            logger.error(f"Failed to ensure artist exists: {e}")
            return None

    async def _update_artist_albums_synced_at(self, deezer_artist_id: str) -> None:
        """Update artist's albums_synced_at timestamp after album sync.

        Hey future me - this is CRITICAL for the gradual background sync!
        Without this, the worker can't track which artists have been synced.

        Args:
            deezer_artist_id: Deezer artist ID
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import ArtistModel

        deezer_uri = f"deezer:artist:{deezer_artist_id}"

        try:
            stmt = (
                update(ArtistModel)
                .where(ArtistModel.deezer_uri == deezer_uri)
                .values(albums_synced_at=datetime.now(UTC))
            )
            await self._session.execute(stmt)
            logger.debug(f"Updated albums_synced_at for Deezer artist {deezer_artist_id}")
        except Exception as e:
            logger.warning(f"Failed to update albums_synced_at: {e}")

    async def _update_album_tracks_synced_at(self, deezer_album_id: str) -> None:
        """Update album's tracks_synced_at timestamp after track sync.

        Hey future me - this is CRITICAL for the gradual background sync!
        Without this, the worker can't track which albums have had tracks synced.

        Args:
            deezer_album_id: Deezer album ID
        """
        from sqlalchemy import update

        from soulspot.infrastructure.persistence.models import AlbumModel

        deezer_uri = f"deezer:album:{deezer_album_id}"

        try:
            stmt = (
                update(AlbumModel)
                .where(AlbumModel.deezer_uri == deezer_uri)
                .values(tracks_synced_at=datetime.now(UTC))
            )
            await self._session.execute(stmt)
            logger.debug(f"Updated tracks_synced_at for Deezer album {deezer_album_id}")
        except Exception as e:
            logger.warning(f"Failed to update tracks_synced_at: {e}")
    
    async def _save_album_with_artist(
        self,
        album_dto: Any,
        artist_id: str,
        is_chart: bool = False,
    ) -> None:
        """Save album DTO with artist relationship.
        
        CRITICAL FIX (Dec 2025): This method properly links album to artist.
        
        Args:
            album_dto: Album DTO from plugin
            artist_id: Internal artist ID to link to
            is_chart: Whether this is from charts
        """
        from soulspot.infrastructure.persistence.models import AlbumModel
        import uuid
        
        try:
            # Hey future me - AlbumDTO.cover ist ImageRef!
            dto_cover_url = album_dto.cover.url if album_dto.cover else None
            
            # Check if album exists (by deezer_id)
            existing = None
            if album_dto.deezer_id:
                existing = await self._album_repo.get_by_deezer_id(album_dto.deezer_id)
            
            if existing:
                # Update existing - Model.cover_url ist DB-Spalte
                existing.title = album_dto.title
                existing.cover_url = dto_cover_url or existing.cover_url
                
                # Download album cover if URL changed (Deezer provider)
                if self._image_service and album_dto.deezer_id and dto_cover_url:
                    if await self._image_service.should_redownload(
                        existing.cover_url, dto_cover_url, existing.cover_path
                    ):
                        cover_path = await self._image_service.download_album_image(
                            album_dto.deezer_id, dto_cover_url, provider="deezer"
                        )
                        if cover_path:
                            existing.cover_path = cover_path
            else:
                # Download album cover for new album (Deezer provider)
                cover_path = None
                if self._image_service and album_dto.deezer_id and dto_cover_url:
                    cover_path = await self._image_service.download_album_image(
                        album_dto.deezer_id, dto_cover_url, provider="deezer"
                    )
                
                # Create new with artist relationship
                new_album = AlbumModel(
                    id=str(uuid.uuid4()),
                    title=album_dto.title,
                    artist_id=artist_id,  # CRITICAL: Link to artist
                    deezer_id=album_dto.deezer_id,
                    cover_url=dto_cover_url,
                    cover_path=cover_path,
                    release_date=album_dto.release_date,
                    total_tracks=album_dto.total_tracks,
                    primary_type=album_dto.primary_type or "Album",
                    source="deezer",
                )
                self._session.add(new_album)
                
        except Exception as e:
            logger.error(f"Failed to save album '{album_dto.title}': {e}")
    
    async def _save_track_with_artist(
        self,
        track_dto: Any,
        artist_id: str,
        is_chart: bool = False,
    ) -> None:
        """Save track DTO with artist relationship.
        
        CRITICAL FIX (Dec 2025): This method properly links track to artist.
        
        Args:
            track_dto: Track DTO from plugin
            artist_id: Internal artist ID to link to
            is_chart: Whether this is from charts
        """
        from soulspot.infrastructure.persistence.models import TrackModel
        import uuid
        
        try:
            # Check if track exists (by deezer_id or ISRC)
            existing = None
            if track_dto.deezer_id:
                existing = await self._track_repo.get_by_deezer_id(track_dto.deezer_id)
            if not existing and track_dto.isrc:
                existing = await self._track_repo.get_by_isrc(track_dto.isrc)
            
            if existing:
                # Update existing
                existing.title = track_dto.title
                existing.deezer_id = track_dto.deezer_id or existing.deezer_id
                existing.isrc = track_dto.isrc or existing.isrc
            else:
                # Create new with artist relationship
                new_track = TrackModel(
                    id=str(uuid.uuid4()),
                    title=track_dto.title,
                    artist_id=artist_id,  # CRITICAL: Link to artist
                    deezer_id=track_dto.deezer_id,
                    isrc=track_dto.isrc,
                    duration_ms=track_dto.duration_ms or 0,
                    track_number=track_dto.track_number,
                    disc_number=track_dto.disc_number or 1,
                    explicit=track_dto.explicit or False,
                    source="deezer",
                )
                self._session.add(new_track)
                
        except Exception as e:
            logger.error(f"Failed to save track '{track_dto.title}': {e}")
    
    async def _save_album_from_dto(
        self,
        album_dto: Any,
        is_chart: bool = False,
        is_new_release: bool = False,
        is_saved: bool = False,
    ) -> None:
        """Save album DTO to database.
        
        Hey future me - hier speichern wir in soulspot_albums!
        source='deezer' markiert, dass es von Deezer kommt.
        AlbumDTO.cover ist ImageRef! Model.cover_url ist DB-Spalte.
        
        Note: is_chart, is_new_release, is_saved parameters are kept for API compatibility
        but not stored in database (fields don't exist in AlbumModel).
        AlbumModel uses 'title' field, not 'name'.
        """
        from soulspot.infrastructure.persistence.models import AlbumModel
        
        # Hey future me - AlbumDTO.cover ist ImageRef!
        dto_cover_url = album_dto.cover.url if album_dto.cover else None
        
        # Check if album exists (by deezer_id)
        existing = await self._album_repo.get_by_deezer_id(album_dto.deezer_id)
        
        if existing:
            # Update existing - use 'title' not 'name'
            existing.title = album_dto.title
            existing.cover_url = dto_cover_url or existing.cover_url
            # Note: is_chart, is_new_release, is_saved flags are not stored in model
            if is_saved:
                existing.is_saved = is_saved  # This field DOES exist
        else:
            # Create new - need artist_id which is not in DTO
            # Skip creation if we can't link to an artist
            # This needs to be handled by the caller
            logger.warning(
                f"Cannot create album '{album_dto.title}' without artist_id - "
                "caller must handle artist relationship"
            )
            # Note: This will be handled properly by sync methods that have artist context
    
    async def _save_track_from_dto(
        self,
        track_dto: Any,
        is_chart: bool = False,
        is_top_track: bool = False,
        is_saved: bool = False,
    ) -> None:
        """Save track DTO to database.
        
        Hey future me - hier speichern wir in soulspot_tracks!
        source='deezer' markiert, dass es von Deezer kommt.
        ISRC ist wichtig für Cross-Service Matching!
        
        Note: is_chart, is_top_track, is_saved parameters are kept for API compatibility
        but not stored in database (fields don't exist in TrackModel).
        """
        from soulspot.infrastructure.persistence.models import TrackModel
        
        # Check if track exists (by deezer_id or ISRC)
        existing = None
        if track_dto.deezer_id:
            existing = await self._track_repo.get_by_deezer_id(track_dto.deezer_id)
        if not existing and track_dto.isrc:
            existing = await self._track_repo.get_by_isrc(track_dto.isrc)
        
        if existing:
            # Update existing
            existing.title = track_dto.title
            existing.deezer_id = track_dto.deezer_id or existing.deezer_id
            existing.isrc = track_dto.isrc or existing.isrc
            # Note: is_chart, is_top_track, is_saved flags are not stored in model
        else:
            # Create new - need artist_id and possibly album_id which are not in DTO
            # Skip creation if we can't link to an artist
            # This needs to be handled by the caller
            logger.warning(
                f"Cannot create track '{track_dto.title}' without artist_id - "
                "caller must handle artist relationship"
            )
            # Note: This will be handled properly by sync methods that have artist context

    # =========================================================================
    # USER LIBRARY SYNC (BRAUCHT OAuth!)
    # =========================================================================
    # Hey future me - diese Methoden brauchen Deezer OAuth!
    # Sie synken User-spezifische Daten (Favorites, Playlists).
    # Wenn kein OAuth Token vorhanden, werden sie übersprungen.
    
    async def sync_followed_artists(
        self,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer followed artists to database.
        
        Hey future me - das ist wie SpotifySyncService.sync_followed_artists()!
        BRAUCHT Deezer OAuth um die gefolgten Artists zu holen.
        
        Args:
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        if not self._plugin.is_authenticated:
            return {
                "skipped": True,
                "reason": "not_authenticated",
                "message": "Deezer OAuth required for followed artists",
            }
        
        if not force and not self._should_sync("followed_artists", self.CHARTS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "artists_synced": 0,
            "errors": [],
        }
        
        try:
            # Get followed artists from Deezer (requires OAuth!)
            paginated = await self._plugin.get_followed_artists(limit=100)
            
            for artist_dto in paginated.items:
                try:
                    await self._save_artist_from_dto(artist_dto)
                    result["artists_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Artist {artist_dto.name}: {e}")
            
            await self._session.commit()
            self._mark_synced("followed_artists")
            
            logger.info(
                f"DeezerSyncService: Followed artists synced - "
                f"{result['artists_synced']} artists"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Followed artists sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def sync_user_playlists(
        self,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer user playlists to database.
        
        Hey future me - das ist wie SpotifySyncService.sync_user_playlists()!
        BRAUCHT Deezer OAuth um die User-Playlists zu holen.
        
        Args:
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        if not self._plugin.is_authenticated:
            return {
                "skipped": True,
                "reason": "not_authenticated",
                "message": "Deezer OAuth required for user playlists",
            }
        
        if not force and not self._should_sync("user_playlists", self.CHARTS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "playlists_synced": 0,
            "errors": [],
        }
        
        try:
            # Get user playlists from Deezer (requires OAuth!)
            paginated = await self._plugin.get_user_playlists(limit=50)
            
            for playlist_dto in paginated.items:
                try:
                    await self._save_playlist_from_dto(playlist_dto)
                    result["playlists_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Playlist {playlist_dto.name}: {e}")
            
            await self._session.commit()
            self._mark_synced("user_playlists")
            
            logger.info(
                f"DeezerSyncService: User playlists synced - "
                f"{result['playlists_synced']} playlists"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: User playlists sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def sync_saved_albums(
        self,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer saved albums to database.
        
        Hey future me - BRAUCHT Deezer OAuth!
        
        Args:
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        if not self._plugin.is_authenticated:
            return {
                "skipped": True,
                "reason": "not_authenticated",
                "message": "Deezer OAuth required for saved albums",
            }
        
        if not force and not self._should_sync("saved_albums", self.ALBUMS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "albums_synced": 0,
            "errors": [],
        }
        
        try:
            # Get saved albums from Deezer (requires OAuth!)
            paginated = await self._plugin.get_saved_albums(limit=50)
            
            # Step 1: Build artist_id mapping
            artist_id_map: dict[str, str] = {}
            
            for album_dto in paginated.items:
                if album_dto.artist_deezer_id and album_dto.artist_deezer_id not in artist_id_map:
                    artist_id = await self._ensure_artist_exists(album_dto, is_chart=False)
                    if artist_id:
                        artist_id_map[album_dto.artist_deezer_id] = artist_id
            
            # Step 2: Sync albums with artist relationships
            for album_dto in paginated.items:
                try:
                    artist_id = artist_id_map.get(album_dto.artist_deezer_id or "")
                    if artist_id:
                        await self._save_album_with_artist(album_dto, artist_id, is_chart=False)
                        result["albums_synced"] += 1
                    else:
                        logger.warning(
                            f"DeezerSyncService: Saved album '{album_dto.title}' skipped - no artist_id"
                        )
                except Exception as e:
                    result["errors"].append(f"Album {album_dto.title}: {e}")
            
            await self._session.commit()
            self._mark_synced("saved_albums")
            
            logger.info(
                f"DeezerSyncService: Saved albums synced - "
                f"{result['albums_synced']} albums"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Saved albums sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _save_playlist_from_dto(
        self,
        playlist_dto: Any,
    ) -> None:
        """Save playlist DTO to database.
        
        Hey future me - Playlists speichern wir in der playlists Tabelle!
        source='DEEZER' markiert, dass es von Deezer kommt.
        PlaylistDTO.cover ist ImageRef! Model.cover_url ist DB-Spalte.
        """
        from soulspot.infrastructure.persistence.models import PlaylistModel
        from soulspot.infrastructure.persistence.repositories import PlaylistRepository
        
        playlist_repo = PlaylistRepository(self._session)
        
        # Hey future me - PlaylistDTO.cover ist ImageRef!
        dto_cover_url = playlist_dto.cover.url if playlist_dto.cover else None
        
        # Check if playlist exists (by deezer_id)
        # TODO: Implement get_by_deezer_id for PlaylistRepository
        # For now, just create new
        new_playlist = PlaylistModel(
            name=playlist_dto.name,
            description=playlist_dto.description,
            deezer_id=playlist_dto.deezer_id,
            cover_url=dto_cover_url,
            owner=playlist_dto.owner_name,
            track_count=playlist_dto.total_tracks,
            source="DEEZER",
        )
        self._session.add(new_playlist)

    # =========================================================================
    # SAVED TRACKS SYNC (equivalent zu Spotify's sync_liked_songs)
    # =========================================================================
    
    async def sync_saved_tracks(
        self,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync Deezer saved tracks (favorites) to database.
        
        Hey future me - das ist das Deezer-Equivalent zu Spotify's sync_liked_songs()!
        BRAUCHT Deezer OAuth um die User-Favoriten zu holen.
        
        Args:
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        if not self._plugin.is_authenticated:
            return {
                "skipped": True,
                "reason": "not_authenticated",
                "message": "Deezer OAuth required for saved tracks",
            }
        
        if not force and not self._should_sync("saved_tracks", self.TRACKS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "tracks_synced": 0,
            "errors": [],
        }
        
        try:
            # Get saved tracks from Deezer (requires OAuth!)
            paginated = await self._plugin.get_saved_tracks(limit=100)
            
            # Step 1: Build artist_id mapping
            artist_id_map: dict[str, str] = {}
            
            for track_dto in paginated.items:
                if track_dto.artist_deezer_id and track_dto.artist_deezer_id not in artist_id_map:
                    artist_id = await self._ensure_artist_exists(track_dto, is_chart=False)
                    if artist_id:
                        artist_id_map[track_dto.artist_deezer_id] = artist_id
            
            # Step 2: Sync tracks with artist relationships
            for track_dto in paginated.items:
                try:
                    artist_id = artist_id_map.get(track_dto.artist_deezer_id or "")
                    if artist_id:
                        await self._save_track_with_artist(track_dto, artist_id, is_chart=False)
                        result["tracks_synced"] += 1
                    else:
                        logger.warning(
                            f"DeezerSyncService: Saved track '{track_dto.title}' skipped - no artist_id"
                        )
                except Exception as e:
                    result["errors"].append(f"Track {track_dto.title}: {e}")
            
            await self._session.commit()
            self._mark_synced("saved_tracks")
            
            logger.info(
                f"DeezerSyncService: Saved tracks synced - "
                f"{result['tracks_synced']} tracks"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Saved tracks sync failed: {e}")
            result["error"] = str(e)
        
        return result
    
    # =========================================================================
    # ALBUM TRACKS SYNC (equivalent zu Spotify's sync_album_tracks)
    # =========================================================================
    
    async def sync_album_tracks(
        self,
        deezer_album_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync album tracks from Deezer to database.
        
        Hey future me - das ist das Deezer-Equivalent zu Spotify's sync_album_tracks()!
        KEIN OAuth nötig - Album-Tracks sind public!
        
        Args:
            deezer_album_id: Deezer album ID
            force: Skip cooldown check
            
        Returns:
            Sync result with counts
        """
        cache_key = f"album_tracks_{deezer_album_id}"
        if not force and not self._should_sync(cache_key, self.TRACKS_SYNC_COOLDOWN):
            return {
                "skipped": True,
                "reason": "cooldown",
            }
        
        result = {
            "synced": False,
            "tracks_synced": 0,
            "errors": [],
        }
        
        try:
            # Get album tracks from Deezer (NO OAuth needed!)
            tracks = await self._plugin.get_album_tracks(deezer_album_id, limit=100)
            
            # Step 1: Get artist_id (all tracks in same album should have same artist)
            artist_id: str | None = None
            
            if tracks and tracks[0]:
                artist_id = await self._ensure_artist_exists(tracks[0], is_chart=False)
            
            if not artist_id:
                logger.warning(
                    f"DeezerSyncService: Cannot sync tracks for album {deezer_album_id} - no artist_id"
                )
                return {"synced": False, "tracks_synced": 0, "error": "artist_not_found"}
            
            # Step 2: Sync tracks with artist relationship
            for track_dto in tracks:
                try:
                    await self._save_track_with_artist(track_dto, artist_id, is_chart=False)
                    result["tracks_synced"] += 1
                except Exception as e:
                    result["errors"].append(f"Track {track_dto.title}: {e}")
            
            # Step 3: Mark album tracks as synced
            # Hey future me - this is CRITICAL for the gradual background sync!
            await self._update_album_tracks_synced_at(deezer_album_id)
            
            await self._session.commit()
            self._mark_synced(cache_key)
            
            result["synced"] = True
            logger.info(
                f"DeezerSyncService: Album {deezer_album_id} tracks synced - "
                f"{result['tracks_synced']} tracks"
            )
            
        except Exception as e:
            logger.error(f"DeezerSyncService: Album tracks sync failed: {e}")
            result["error"] = str(e)
        
        return result
