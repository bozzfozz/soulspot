"""New Releases Service - Multi-Provider Orchestration.

Hey future me - DAS ist der zentrale Service für Multi-Provider New Releases!
Er orchestriert ALLE verfügbaren Plugins (Spotify, Deezer, Tidal, etc.) und
aggregiert deren New Releases zu einer deduplizierten Liste.

Architektur:
    UI Route → NewReleasesService → [SpotifyPlugin, DeezerPlugin, TidalPlugin]
                    ↓
            Aggregate & Deduplicate
                    ↓
            Sorted AlbumDTOs

Warum ein Service?
1. Plugins sind stateless - sie wissen nichts voneinander
2. Service orchestriert und dedupliziert
3. UI bleibt clean - ruft nur Service auf
4. Erweiterbar für neue Provider (Tidal, Qobuz, etc.)

Deduplication Strategy:
1. ISRC (International Standard Recording Code) - wenn verfügbar
2. Normalized (artist_name::album_title) - als Fallback
3. Source tracking - welcher Provider lieferte zuerst
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from soulspot.domain.dtos import AlbumDTO
from soulspot.domain.ports.plugin import PluginCapability

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


@dataclass
class NewReleasesResult:
    """Result container for multi-provider new releases.
    
    Hey future me - das ist das Ergebnis vom Service!
    Enthält alle Releases + Metadata über die Quellen.
    """
    
    albums: list[AlbumDTO]
    """Aggregated, deduplicated album list sorted by release_date."""
    
    source_counts: dict[str, int]
    """How many albums came from each source (spotify: 10, deezer: 5, etc.)."""
    
    total_before_dedup: int
    """Total albums before deduplication (for metrics)."""
    
    errors: dict[str, str]
    """Errors per source (spotify: "Auth failed", etc.)."""


class NewReleasesService:
    """Service that aggregates new releases from all music providers.
    
    Hey future me - nutze diesen Service in der UI Route!
    Er kümmert sich um:
    - Parallele API-Calls zu allen Plugins
    - Deduplication via ISRC oder artist::title
    - Fehlerbehandlung (ein Plugin fail = andere laufen weiter)
    - Sortierung nach Release-Datum
    
    Usage:
        service = NewReleasesService(
            spotify_plugin=spotify,
            deezer_plugin=deezer,
            settings_service=settings
        )
        result = await service.get_all_new_releases(days=90)
        # result.albums = [AlbumDTO, AlbumDTO, ...]
    """
    
    def __init__(
        self,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
        # Future: tidal_plugin, qobuz_plugin, etc.
    ) -> None:
        """Initialize with available plugins.
        
        Args:
            spotify_plugin: SpotifyPlugin instance (optional)
            deezer_plugin: DeezerPlugin instance (optional)
        """
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin
    
    async def get_all_new_releases(
        self,
        days: int = 90,
        include_singles: bool = True,
        include_compilations: bool = True,
        enabled_providers: list[str] | None = None,
    ) -> NewReleasesResult:
        """Get new releases from ALL enabled providers.
        
        Hey future me - das ist DIE zentrale Methode!
        Ruft alle Plugins parallel auf, aggregiert und dedupliziert.
        
        Args:
            days: Look back period in days (default 90)
            include_singles: Include singles/EPs
            include_compilations: Include compilation albums
            enabled_providers: List of enabled providers ["spotify", "deezer"]
                              If None, all available plugins are queried.
        
        Returns:
            NewReleasesResult with aggregated albums and metadata
        """
        all_albums: list[AlbumDTO] = []
        source_counts: dict[str, int] = {}
        errors: dict[str, str] = {}
        total_before_dedup = 0
        
        # Determine which providers to query
        if enabled_providers is None:
            enabled_providers = []
            if self._spotify:
                enabled_providers.append("spotify")
            if self._deezer:
                enabled_providers.append("deezer")
        
        logger.info(f"NewReleasesService: Querying providers: {enabled_providers}")
        
        # Create tasks for parallel execution
        tasks: list[tuple[str, asyncio.Task[list[AlbumDTO]]]] = []
        
        # Spotify task
        if "spotify" in enabled_providers and self._spotify:
            if self._spotify.can_use(PluginCapability.BROWSE_NEW_RELEASES):
                task = asyncio.create_task(
                    self._spotify.get_new_releases(
                        days=days,
                        include_singles=include_singles,
                        include_compilations=include_compilations,
                    )
                )
                tasks.append(("spotify", task))
            else:
                logger.debug("NewReleasesService: Spotify skipped (not authenticated or capability unavailable)")
                errors["spotify"] = "Not authenticated"
        
        # Deezer task
        if "deezer" in enabled_providers and self._deezer:
            if self._deezer.can_use(PluginCapability.BROWSE_NEW_RELEASES):
                task = asyncio.create_task(
                    self._get_deezer_releases(
                        days=days,
                        include_singles=include_singles,
                        include_compilations=include_compilations,
                    )
                )
                tasks.append(("deezer", task))
            else:
                logger.debug("NewReleasesService: Deezer skipped (capability unavailable)")
        
        # Wait for all tasks
        for provider, task in tasks:
            try:
                albums = await task
                source_counts[provider] = len(albums)
                total_before_dedup += len(albums)
                all_albums.extend(albums)
                logger.info(f"NewReleasesService: Got {len(albums)} from {provider}")
            except Exception as e:
                errors[provider] = str(e)
                source_counts[provider] = 0
                logger.warning(f"NewReleasesService: {provider} failed: {e}")
        
        # Deduplicate
        deduped_albums = self._deduplicate_albums(all_albums)
        
        # Sort by release date (newest first)
        deduped_albums.sort(
            key=lambda a: a.release_date or "1900-01-01",
            reverse=True
        )
        
        logger.info(
            f"NewReleasesService: Total {total_before_dedup} → {len(deduped_albums)} after dedup"
        )
        
        return NewReleasesResult(
            albums=deduped_albums,
            source_counts=source_counts,
            total_before_dedup=total_before_dedup,
            errors=errors,
        )
    
    async def _get_deezer_releases(
        self,
        days: int,
        include_singles: bool,
        include_compilations: bool,
    ) -> list[AlbumDTO]:
        """Get new releases from Deezer and convert to AlbumDTOs.
        
        Hey future me - Deezer Plugin gibt dict zurück, wir brauchen AlbumDTOs!
        """
        if not self._deezer:
            return []
        
        result = await self._deezer.get_browse_new_releases(
            limit=100,
            include_compilations=include_compilations,
        )
        
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown Deezer error"))
        
        albums: list[AlbumDTO] = []
        for album_data in result.get("albums", []):
            # Filter singles if not wanted
            record_type = album_data.get("record_type", "album")
            if not include_singles and record_type in ("single", "ep"):
                continue
            
            albums.append(AlbumDTO(
                title=album_data.get("title", ""),
                artist_name=album_data.get("artist_name", ""),
                source_service="deezer",
                deezer_id=str(album_data.get("deezer_id") or album_data.get("id", "")),
                artist_deezer_id=str(album_data.get("artist_id", "")) if album_data.get("artist_id") else None,
                release_date=album_data.get("release_date"),
                total_tracks=album_data.get("total_tracks") or album_data.get("nb_tracks") or 0,
                album_type=record_type,
                artwork_url=album_data.get("cover_big") or album_data.get("cover_medium"),
                external_urls={"deezer": album_data.get("link", "")},
            ))
        
        return albums
    
    def _deduplicate_albums(self, albums: list[AlbumDTO]) -> list[AlbumDTO]:
        """Deduplicate albums by ISRC or normalized artist::title.
        
        Hey future me - deduplication strategy:
        1. ISRC (if available) - most reliable cross-service match
        2. Normalized (artist_name::album_title) - fallback for albums without ISRC
        
        First-seen wins: if Spotify delivers before Deezer, Spotify version is kept.
        """
        seen_isrcs: set[str] = set()
        seen_keys: set[str] = set()
        deduped: list[AlbumDTO] = []
        
        for album in albums:
            # Try ISRC first (most reliable)
            if album.upc:  # UPC is album-level unique identifier
                if album.upc in seen_isrcs:
                    continue
                seen_isrcs.add(album.upc)
            
            # Fallback to normalized key
            key = self._normalize_key(album.artist_name, album.title)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            deduped.append(album)
        
        return deduped
    
    @staticmethod
    def _normalize_key(artist: str, album: str) -> str:
        """Create normalized key for deduplication.
        
        Hey future me - einfache Normalisierung:
        - Lowercase
        - Strip whitespace
        - Remove common variations ("(Deluxe)", "- Single", etc.)
        
        Could be improved with fuzzy matching but simple works 95% of the time.
        """
        artist_norm = artist.lower().strip()
        album_norm = album.lower().strip()
        
        # Remove common suffixes that differ between services
        for suffix in [
            "(deluxe)", "(deluxe edition)", "(expanded edition)",
            "(remastered)", "(remaster)", "- single", "(single)",
            "(ep)", "- ep"
        ]:
            album_norm = album_norm.replace(suffix, "").strip()
        
        return f"{artist_norm}::{album_norm}"


# Export
__all__ = ["NewReleasesService", "NewReleasesResult"]
