# Hey future me - NEUER SERVICE nach Architecture Standard!
# Dieser Service liefert ViewModels für Template-Rendering.
# Routes rufen diesen Service auf und bekommen FERTIGE ViewModels.
# KEINE Model-Details in Routes!
#
# Warum separater Service?
# - Single Responsibility: ViewModels ≠ Sync Logic
# - SpotifySyncService war 1839 Zeilen (God Class!)
# - Klare Trennung: Sync Services synken, View Services rendern
#
# Was dieser Service macht:
# - get_album_detail_view() → AlbumDetailView für Album-Detail-Seite
# - get_artist_detail_view() → ArtistDetailView für Artist-Detail-Seite
# - get_track_list_view() → TrackListView für Track-Listen
#
# Was dieser Service NICHT macht:
# - Sync von Daten (das machen die *SyncServices)
# - DB-Queries direkt (das machen Repositories)
# - API-Calls (das machen Plugins)
"""Library View Service - ViewModels für Template-Rendering."""

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.dtos import AlbumDetailView, TrackView
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

if TYPE_CHECKING:
    from soulspot.application.services.spotify_sync_service import SpotifySyncService

logger = logging.getLogger(__name__)


class LibraryViewService:
    """Service für Template-ready ViewModels.
    
    Hey future me - das ist der VIEW SERVICE nach Clean Architecture!
    
    Dieser Service:
    1. Holt Daten aus DB via Repositories
    2. Triggert Sync-on-demand (optional)
    3. Konvertiert Models zu ViewModels
    4. Gibt ViewModels an Routes zurück
    
    Routes wissen NICHTS über Models - nur ViewModels!
    
    Beispiel Route:
        @router.get("/albums/{album_id}")
        async def album_detail(service: LibraryViewService = Depends(...)):
            view = await service.get_album_detail_view(artist_id, album_id)
            return templates.TemplateResponse("album.html", view)
    
    Die Route braucht NICHT wissen ob Model.title oder Model.name heißt!
    """
    
    def __init__(
        self,
        session: AsyncSession,
        spotify_sync: "SpotifySyncService | None" = None,
    ) -> None:
        """Initialize Library View Service.
        
        Hey future me - SpotifySyncService ist OPTIONAL!
        Wenn vorhanden, können wir Sync-on-demand triggern.
        Wenn nicht, zeigen wir nur cached Daten.
        
        Args:
            session: Database session
            spotify_sync: Optional SpotifySyncService für Sync-on-demand
        """
        self._session = session
        self._spotify_sync = spotify_sync
        
        # Repository für DB-Zugriff
        self._repo = SpotifyBrowseRepository(session)
    
    # =========================================================================
    # ALBUM VIEWS
    # =========================================================================
    
    async def get_album_detail_view(
        self, artist_id: str, album_id: str, auto_sync: bool = True
    ) -> AlbumDetailView | None:
        """Get album detail as a ViewModel for template rendering.
        
        Hey future me - das ist die RICHTIGE Methode nach Architecture Standard!
        Routes rufen DIESE Methode auf und bekommen ein fertiges ViewModel zurück.
        Die Route muss NICHTS über Models oder DB-Attribute wissen.
        
        Flow:
        1. Get artist from DB (for breadcrumb)
        2. Get album from DB
        3. Auto-sync tracks from Spotify (with cooldown) - OPTIONAL
        4. Get tracks from DB
        5. Convert everything to AlbumDetailView
        
        Args:
            artist_id: Spotify artist ID
            album_id: Spotify album ID
            auto_sync: Whether to auto-sync tracks (default: True)
            
        Returns:
            AlbumDetailView or None if album not found
        """
        # Get artist (optional - für Breadcrumb)
        artist_model = await self._repo.get_artist_by_id(artist_id)
        artist_spotify_id = artist_model.spotify_id if artist_model else None
        artist_name = artist_model.name if artist_model else None
        
        # Get album
        album_model = await self._repo.get_album_by_id(album_id)
        if not album_model:
            return None
        
        # Auto-sync tracks (with error handling) - only if sync service available
        synced = False
        sync_error = None
        
        if auto_sync and self._spotify_sync:
            try:
                sync_result = await self._spotify_sync.sync_album_tracks(album_id)
                synced = sync_result.get("synced", False)
                if sync_result.get("error"):
                    sync_error = sync_result["error"]
            except Exception as e:
                sync_error = str(e)
                logger.warning(f"Track sync failed for album {album_id}: {e}")
        
        # Get tracks from DB
        track_models = await self._repo.get_tracks_by_album(album_id, limit=100)
        
        # Convert tracks to TrackView
        track_views = self._convert_tracks_to_views(track_models)
        
        # Sort by disc, then track number
        track_views.sort(key=lambda t: (t.disc_number, t.track_number))
        
        # Calculate total duration string
        total_duration_ms = sum(t.duration_ms for t in track_views)
        total_duration_str = self._format_total_duration(total_duration_ms)
        
        return AlbumDetailView(
            spotify_id=album_model.spotify_id,
            title=album_model.name,
            artwork_url=album_model.artwork_url,
            release_date=album_model.release_date,
            album_type=album_model.album_type or "album",
            total_tracks=album_model.total_tracks or len(track_views),
            artist_spotify_id=artist_spotify_id,
            artist_name=artist_name,
            tracks=track_views,
            track_count=len(track_views),
            total_duration_str=total_duration_str,
            synced=synced,
            sync_error=sync_error,
        )
    
    # =========================================================================
    # CONVERSION HELPERS
    # =========================================================================
    # Hey future me - diese Methoden konvertieren Models zu ViewModels!
    # Sie verstecken die Model-Details (z.B. "title" vs "name").
    
    def _convert_tracks_to_views(self, track_models: list[Any]) -> list[TrackView]:
        """Convert TrackModels to TrackViews.
        
        Hey future me - hier passiert die Model→ViewModel Konvertierung!
        TrackModel hat "title", TrackView hat "name" (für Template).
        """
        track_views: list[TrackView] = []
        
        for track in track_models:
            duration_ms = track.duration_ms or 0
            
            # Format duration as "M:SS"
            duration_str = self._format_duration(duration_ms)
            
            track_views.append(TrackView(
                spotify_id=track.spotify_id,
                title=track.title,  # Model has "title", ViewModel uses "title" (standardized)
                track_number=track.track_number or 1,
                disc_number=track.disc_number or 1,
                duration_ms=duration_ms,
                duration_str=duration_str,
                explicit=track.explicit or False,
                preview_url=track.preview_url,
                isrc=track.isrc,
                is_downloaded=self._check_if_downloaded(track),
            ))
        
        return track_views
    
    def _check_if_downloaded(self, track: Any) -> bool:
        """Check if track is downloaded (linked to local track).
        
        Hey future me - TODO: Echte Logik implementieren!
        Aktuell ist das ein Stub. Später prüfen wir:
        - Hat der Track eine local_track_id?
        - Existiert die Datei noch?
        """
        # TODO: Implement proper download check
        # For now, just check if there's a local_track_id attribute
        local_id = getattr(track, "local_track_id", None)
        return local_id is not None
    
    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        """Format duration in milliseconds as "M:SS"."""
        duration_sec = duration_ms // 1000
        duration_min = duration_sec // 60
        duration_sec_rem = duration_sec % 60
        return f"{duration_min}:{duration_sec_rem:02d}"
    
    @staticmethod
    def _format_total_duration(total_ms: int) -> str:
        """Format total duration as "X min Y sec"."""
        total_min = total_ms // 60000
        total_sec = (total_ms % 60000) // 1000
        return f"{total_min} min {total_sec} sec"
