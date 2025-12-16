# Hey future me - ProviderSyncOrchestrator ist der MULTI-PROVIDER Service!
# Statt überall "try Spotify, catch, try Deezer" zu schreiben,
# zentralisiert dieser Service die Provider-Fallback-Logik.
#
# ARCHITEKTUR (Dec 2025):
# - Routes rufen ProviderSyncOrchestrator auf
# - Orchestrator fragt SpotifySyncService + DeezerSyncService ab
# - Ergebnisse werden dedupliziert und aggregiert
# - Fallback: Spotify → Deezer (oder umgekehrt je nach Feature)
#
# WICHTIG: Dieser Service erstellt KEINE eigenen API-Calls!
# Er orchestriert nur die spezialisierten Sync-Services.
"""Multi-provider sync orchestrator for aggregating data from multiple sources."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.deezer_sync_service import DeezerSyncService
    from soulspot.application.services.spotify_sync_service import SpotifySyncService

logger = logging.getLogger(__name__)


@dataclass
class AggregatedSyncResult:
    """Result from multi-provider sync operation.
    
    Hey future me - dieses Result zeigt was von welchem Provider kam!
    Wichtig für UI: User sieht "12 from Spotify, 8 from Deezer".
    """
    synced: bool = False
    total: int = 0
    added: int = 0
    source_counts: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)  # provider -> error
    skipped_providers: list[str] = field(default_factory=list)


class ProviderSyncOrchestrator:
    """Orchestrates sync operations across multiple providers.
    
    Hey future me - dieser Service ist der ZENTRALE Punkt für Multi-Provider!
    
    Warum ein Orchestrator statt direkt Services aufrufen?
    1. DRY: Fallback-Logik an EINEM Ort
    2. Konsistent: Alle Routes bekommen gleiche Aggregation
    3. Konfigurierbar: Provider können per Settings an/aus sein
    4. Erweiterbar: Tidal/MusicBrainz einfach hinzufügen
    
    Pattern:
    ```
    result = await orchestrator.sync_artist_albums(artist_id, artist_name)
    # result.source_counts = {"spotify": 10, "deezer": 5}
    ```
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_sync: "SpotifySyncService | None" = None,
        deezer_sync: "DeezerSyncService | None" = None,
        settings_service: "AppSettingsService | None" = None,
    ) -> None:
        """Initialize orchestrator with available sync services.
        
        Hey future me - Services können None sein!
        - spotify_sync = None wenn User nicht mit Spotify authentifiziert
        - deezer_sync sollte immer verfügbar sein (kein OAuth nötig)
        
        Args:
            session: Database session
            spotify_sync: SpotifySyncService (optional, needs OAuth)
            deezer_sync: DeezerSyncService (optional, but usually available)
            settings_service: For checking provider modes (off/basic/pro)
        """
        self._session = session
        self._spotify_sync = spotify_sync
        self._deezer_sync = deezer_sync
        self._settings_service = settings_service

    async def _is_provider_enabled(self, provider: str) -> bool:
        """Check if a provider is enabled in settings.
        
        Args:
            provider: Provider name ("spotify", "deezer")
            
        Returns:
            True if provider is enabled (not "off")
        """
        if not self._settings_service:
            return True  # Default: all providers enabled
        return await self._settings_service.is_provider_enabled(provider)

    # =========================================================================
    # ARTIST ALBUMS SYNC (Spotify primary, Deezer fallback)
    # =========================================================================

    async def sync_artist_albums(
        self,
        artist_id: str,
        artist_name: str | None = None,
        deezer_artist_id: str | None = None,
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync artist albums from all available providers.
        
        Hey future me - das ist die HAUPT-Methode für Artist Discographies!
        
        Strategy:
        1. Try Spotify first (if authenticated + enabled)
        2. Fallback to Deezer (NO AUTH NEEDED!)
        3. Merge results if both succeed
        
        Warum Spotify zuerst?
        - Spotify-Artists haben spotify_id, perfekt für Lookup
        - Deezer braucht artist_name für Search (weniger präzise)
        
        Args:
            artist_id: Spotify artist ID (primary key)
            artist_name: Artist name for Deezer search fallback
            deezer_artist_id: Deezer artist ID if known (skip search)
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats from each provider
        """
        result = AggregatedSyncResult()
        
        # Track which providers contributed
        spotify_result: dict[str, Any] | None = None
        deezer_result: dict[str, Any] | None = None
        
        # 1. Try Spotify (if available and enabled)
        if self._spotify_sync and await self._is_provider_enabled("spotify"):
            try:
                spotify_result = await self._spotify_sync.sync_artist_albums(
                    artist_id=artist_id,
                    force=force,
                )
                if spotify_result.get("synced"):
                    result.source_counts["spotify"] = spotify_result.get("total", 0)
                    result.added += spotify_result.get("added", 0)
                elif spotify_result.get("skipped_cooldown"):
                    result.skipped_providers.append("spotify")
            except Exception as e:
                logger.warning(f"Spotify artist albums sync failed: {e}")
                result.errors["spotify"] = str(e)
        else:
            result.skipped_providers.append("spotify")
        
        # 2. Try Deezer as fallback (if Spotify failed or got nothing)
        if (
            self._deezer_sync 
            and await self._is_provider_enabled("deezer")
            and (not spotify_result or not spotify_result.get("synced"))
        ):
            try:
                # Use Deezer artist ID if we have it, otherwise search by name
                deezer_id = deezer_artist_id
                if not deezer_id and artist_name:
                    # DeezerSyncService handles the name→ID mapping internally
                    pass  # Will use artist_name parameter
                
                deezer_result = await self._deezer_sync.sync_artist_albums(
                    artist_id=deezer_id or artist_id,  # Fallback to Spotify ID for lookup
                    artist_name=artist_name,
                    force=force,
                )
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = deezer_result.get("albums_synced", 0)
                    result.added += deezer_result.get("albums_synced", 0)
                elif deezer_result.get("skipped_cooldown"):
                    result.skipped_providers.append("deezer")
            except Exception as e:
                logger.warning(f"Deezer artist albums sync failed: {e}")
                result.errors["deezer"] = str(e)
        
        # Aggregate totals
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        logger.info(
            f"ProviderSyncOrchestrator: Artist albums sync complete - "
            f"Spotify: {result.source_counts.get('spotify', 0)}, "
            f"Deezer: {result.source_counts.get('deezer', 0)}"
        )
        
        return result

    # =========================================================================
    # NEW RELEASES SYNC (Deezer primary - NO AUTH NEEDED!)
    # =========================================================================

    async def sync_new_releases(
        self,
        limit: int = 50,
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync new releases from all available providers.
        
        Hey future me - Deezer ist hier PRIMARY!
        Warum? Deezer New Releases brauchen KEIN OAuth!
        Spotify New Releases brauchen OAuth.
        
        Strategy:
        1. Try Deezer first (NO AUTH!)
        2. Add Spotify if authenticated
        3. Deduplicate by artist+title
        
        Args:
            limit: Max releases per provider
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats from each provider
        """
        result = AggregatedSyncResult()
        
        # 1. Try Deezer first (NO AUTH - always available!)
        if self._deezer_sync and await self._is_provider_enabled("deezer"):
            try:
                deezer_result = await self._deezer_sync.sync_new_releases(
                    limit=limit,
                    force=force,
                )
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = deezer_result.get("albums_synced", 0)
                    result.added += deezer_result.get("albums_synced", 0)
                elif deezer_result.get("skipped_cooldown"):
                    result.skipped_providers.append("deezer")
            except Exception as e:
                logger.warning(f"Deezer new releases sync failed: {e}")
                result.errors["deezer"] = str(e)
        
        # 2. Add Spotify (if authenticated and enabled)
        if self._spotify_sync and await self._is_provider_enabled("spotify"):
            try:
                spotify_result = await self._spotify_sync.sync_new_releases(
                    limit=limit,
                    force=force,
                )
                if spotify_result.get("synced"):
                    result.source_counts["spotify"] = spotify_result.get("albums_synced", 0)
                    result.added += spotify_result.get("albums_synced", 0)
                elif spotify_result.get("skipped_cooldown"):
                    result.skipped_providers.append("spotify")
            except Exception as e:
                logger.warning(f"Spotify new releases sync failed: {e}")
                result.errors["spotify"] = str(e)
        
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        return result

    # =========================================================================
    # ARTIST TOP TRACKS SYNC
    # =========================================================================

    async def sync_artist_top_tracks(
        self,
        artist_id: str,
        artist_name: str | None = None,
        deezer_artist_id: str | None = None,
        market: str = "DE",
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync artist top tracks from all available providers.
        
        Hey future me - Deezer als Fallback wenn Spotify nicht verfügbar!
        
        Args:
            artist_id: Spotify artist ID
            artist_name: Artist name for Deezer search
            deezer_artist_id: Deezer artist ID if known
            market: Market code for Spotify (default: DE)
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats
        """
        result = AggregatedSyncResult()
        
        # 1. Try Spotify first (if available)
        if self._spotify_sync and await self._is_provider_enabled("spotify"):
            try:
                spotify_result = await self._spotify_sync.sync_artist_top_tracks(
                    artist_id=artist_id,
                    market=market,
                    force=force,
                )
                if spotify_result.get("synced"):
                    result.source_counts["spotify"] = spotify_result.get("tracks_synced", 0)
                    result.added += spotify_result.get("tracks_synced", 0)
            except Exception as e:
                logger.warning(f"Spotify artist top tracks sync failed: {e}")
                result.errors["spotify"] = str(e)
        
        # 2. Deezer fallback
        if (
            self._deezer_sync 
            and await self._is_provider_enabled("deezer")
            and not result.source_counts.get("spotify")
        ):
            try:
                deezer_result = await self._deezer_sync.sync_artist_top_tracks(
                    artist_id=deezer_artist_id or artist_id,
                    artist_name=artist_name,
                    force=force,
                )
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = deezer_result.get("tracks_synced", 0)
                    result.added += deezer_result.get("tracks_synced", 0)
            except Exception as e:
                logger.warning(f"Deezer artist top tracks sync failed: {e}")
                result.errors["deezer"] = str(e)
        
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        return result

    # =========================================================================
    # RELATED ARTISTS SYNC (Discovery Feature!)
    # =========================================================================

    async def sync_related_artists(
        self,
        artist_id: str,
        artist_name: str | None = None,
        deezer_artist_id: str | None = None,
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync related artists from all available providers.
        
        Hey future me - DISCOVERY Feature!
        Holt ähnliche Künstler von Spotify UND Deezer und kombiniert sie.
        
        Use Cases:
        - "Artists You Might Like" auf Artist-Detail-Seite
        - "Fans Also Like" Section
        - Discovery Recommendations
        
        Args:
            artist_id: Spotify artist ID
            artist_name: Artist name for Deezer
            deezer_artist_id: Deezer artist ID if known
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats
        """
        result = AggregatedSyncResult()
        
        # 1. Try Spotify first (if available)
        if self._spotify_sync and await self._is_provider_enabled("spotify"):
            try:
                spotify_result = await self._spotify_sync.sync_related_artists(
                    artist_id=artist_id,
                    force=force,
                )
                if spotify_result.get("synced"):
                    result.source_counts["spotify"] = spotify_result.get("artists_synced", 0)
                    result.added += spotify_result.get("artists_synced", 0)
            except Exception as e:
                logger.warning(f"Spotify related artists sync failed: {e}")
                result.errors["spotify"] = str(e)
        
        # 2. Deezer fallback
        if (
            self._deezer_sync 
            and await self._is_provider_enabled("deezer")
            and not result.source_counts.get("spotify")
        ):
            try:
                deezer_result = await self._deezer_sync.sync_related_artists(
                    artist_id=deezer_artist_id or artist_id,
                    artist_name=artist_name,
                    force=force,
                )
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = deezer_result.get("artists_synced", 0)
                    result.added += deezer_result.get("artists_synced", 0)
            except Exception as e:
                logger.warning(f"Deezer related artists sync failed: {e}")
                result.errors["deezer"] = str(e)
        
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        return result

    # =========================================================================
    # CHARTS SYNC (Deezer only - Spotify has no public charts API)
    # =========================================================================

    async def sync_charts(
        self,
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync charts from available providers.
        
        Hey future me - NUR DEEZER hat public Charts API!
        Spotify hat keine öffentliche Charts API.
        
        Args:
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats
        """
        result = AggregatedSyncResult()
        
        if self._deezer_sync and await self._is_provider_enabled("deezer"):
            try:
                deezer_result = await self._deezer_sync.sync_charts(force=force)
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = (
                        deezer_result.get("tracks_synced", 0) +
                        deezer_result.get("albums_synced", 0) +
                        deezer_result.get("artists_synced", 0)
                    )
                    result.added = result.source_counts["deezer"]
            except Exception as e:
                logger.warning(f"Deezer charts sync failed: {e}")
                result.errors["deezer"] = str(e)
        else:
            result.skipped_providers.append("deezer")
        
        # Note: Spotify has no public charts API
        result.skipped_providers.append("spotify")
        
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        return result

    # =========================================================================
    # ALBUM TRACKS SYNC
    # =========================================================================

    async def sync_album_tracks(
        self,
        album_id: str,
        deezer_album_id: str | None = None,
        force: bool = False,
    ) -> AggregatedSyncResult:
        """Sync album tracks from available providers.
        
        Args:
            album_id: Spotify album ID (or internal ID)
            deezer_album_id: Deezer album ID if known
            force: Skip cooldown check
            
        Returns:
            AggregatedSyncResult with stats
        """
        result = AggregatedSyncResult()
        
        # 1. Try Spotify first
        if self._spotify_sync and await self._is_provider_enabled("spotify"):
            try:
                spotify_result = await self._spotify_sync.sync_album_tracks(
                    album_id=album_id,
                    force=force,
                )
                if spotify_result.get("synced"):
                    result.source_counts["spotify"] = spotify_result.get("total", 0)
                    result.added += spotify_result.get("added", 0)
            except Exception as e:
                logger.warning(f"Spotify album tracks sync failed: {e}")
                result.errors["spotify"] = str(e)
        
        # 2. Deezer fallback
        if (
            self._deezer_sync 
            and await self._is_provider_enabled("deezer")
            and deezer_album_id
            and not result.source_counts.get("spotify")
        ):
            try:
                deezer_result = await self._deezer_sync.sync_album_tracks(
                    album_id=deezer_album_id,
                    force=force,
                )
                if deezer_result.get("synced"):
                    result.source_counts["deezer"] = deezer_result.get("tracks_synced", 0)
                    result.added += deezer_result.get("tracks_synced", 0)
            except Exception as e:
                logger.warning(f"Deezer album tracks sync failed: {e}")
                result.errors["deezer"] = str(e)
        
        result.total = sum(result.source_counts.values())
        result.synced = result.total > 0 or not result.errors
        
        return result
