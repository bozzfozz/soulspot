"""Multi-Provider Charts Service.

Hey future me - dieser Service aggregiert Charts von ALLEN Providern!

Das Problem: Es gibt keine zentrale Charts-Seite die mehrere Services kombiniert.
Diese Lösung: Kombiniere Deezer Charts + Spotify Top 50 + (future) für reichhaltigere Charts.

Architecture:
    ChartsService
        ↓
    [SpotifyPlugin, DeezerPlugin]
        ↓
    Aggregate & Deduplicate
        ↓
    ChartsResult

Features:
1. Chart Tracks - Top tracks from all services
2. Chart Albums - Top albums from all services
3. Chart Artists - Top artists from all services
4. Editorial Picks - Curated content from services

WICHTIG: Deezer Charts brauchen KEINE Auth! 
Spotify braucht Auth für personalisierte Charts, aber nicht für globale Top 50.

Usage:
    service = ChartsService(
        spotify_plugin=spotify_plugin,
        deezer_plugin=deezer_plugin,
    )
    
    # Get combined chart tracks
    result = await service.get_chart_tracks(limit=50)
    
    # Get combined chart albums
    result = await service.get_chart_albums(limit=50)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, TrackDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


@dataclass
class ChartTrack:
    """A track from charts with metadata from multiple sources.
    
    Hey future me - follows TrackDTO naming conventions!
    Uses `artwork_url` (not `image_url`) for consistency with AlbumDTO.
    """
    
    title: str
    artist_name: str
    album_name: str | None = None
    spotify_id: str | None = None
    deezer_id: str | None = None
    isrc: str | None = None
    duration_ms: int = 0
    preview_url: str | None = None
    artwork_url: str | None = None  # Album artwork (consistent with AlbumDTO)
    popularity: int = 0
    source_service: str = "unknown"
    chart_position: int | None = None
    external_urls: dict[str, str] = field(default_factory=dict)


@dataclass
class ChartAlbum:
    """An album from charts with metadata from multiple sources.
    
    Hey future me - follows AlbumDTO naming conventions!
    Uses `artwork_url` (not `image_url`) for cover art.
    """
    
    title: str
    artist_name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    upc: str | None = None
    release_date: str | None = None
    total_tracks: int = 0
    artwork_url: str | None = None  # Consistent with AlbumDTO
    source_service: str = "unknown"
    chart_position: int | None = None
    external_urls: dict[str, str] = field(default_factory=dict)


@dataclass
class ChartArtist:
    """An artist from charts with metadata from multiple sources."""
    
    name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    image_url: str | None = None
    genres: list[str] = field(default_factory=list)
    popularity: int = 0
    source_service: str = "unknown"
    chart_position: int | None = None
    external_urls: dict[str, str] = field(default_factory=dict)


@dataclass
class ChartsResult:
    """Result from charts operations."""
    
    tracks: list[ChartTrack] = field(default_factory=list)
    albums: list[ChartAlbum] = field(default_factory=list)
    artists: list[ChartArtist] = field(default_factory=list)
    
    source_counts: dict[str, int] = field(default_factory=dict)
    """How many items came from each source before dedup."""
    
    total_before_dedup: int = 0
    """Total items before deduplication."""
    
    errors: dict[str, str] = field(default_factory=dict)
    """Errors from each provider (provider_name -> error_message)."""


class ChartsService:
    """Multi-Provider Charts Service.
    
    Hey future me - dieser Service ist analog zu NewReleasesService aufgebaut!
    Aggregiert Charts von mehreren Services.
    
    Deezer Features (NO AUTH!):
    - get_chart_tracks() - Top 100 tracks
    - get_chart_albums() - Top 100 albums
    - get_chart_artists() - Top 100 artists
    - get_editorial_releases() - Editorial picks
    
    Spotify Features (AUTH NEEDED):
    - Global Top 50 playlist
    - New Releases
    """
    
    def __init__(
        self,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize service with available plugins.
        
        Args:
            spotify_plugin: SpotifyPlugin instance (optional)
            deezer_plugin: DeezerPlugin instance (optional, NO AUTH NEEDED for charts!)
        """
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin
    
    async def get_chart_tracks(
        self,
        limit: int = 50,
        enabled_providers: list[str] | None = None,
    ) -> ChartsResult:
        """Get top chart tracks from all providers.
        
        Hey future me - Deezer Charts sind FREE, keine Auth nötig!
        
        Args:
            limit: Maximum tracks to return
            enabled_providers: List of enabled providers ["spotify", "deezer"]
        
        Returns:
            ChartsResult with chart tracks from all sources
        """
        providers = enabled_providers or ["spotify", "deezer"]
        tasks: list[asyncio.Task[list[tuple[ChartTrack, str]]]] = []
        
        # Deezer Chart Tracks (NO AUTH!)
        if "deezer" in providers and self._deezer:
            tasks.append(
                asyncio.create_task(
                    self._fetch_deezer_chart_tracks(limit),
                    name="deezer_tracks"
                )
            )
        
        # Spotify: We'd need a playlist fetch for Top 50 (future enhancement)
        # For now, skip Spotify chart tracks
        
        # Wait for all tasks
        all_tracks: list[tuple[ChartTrack, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task, result in zip(tasks, results, strict=False):
                task_name = task.get_name()
                source = task_name.split("_")[0]
                
                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"ChartsService: {source} tracks failed: {result}")
                else:
                    for track, src in result:
                        all_tracks.append((track, src))
                        source_counts[src] = source_counts.get(src, 0) + 1
        
        # Deduplicate by ISRC then by artist|title
        total_before = len(all_tracks)
        deduped = self._deduplicate_tracks(all_tracks)
        
        return ChartsResult(
            tracks=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
        )
    
    async def get_chart_albums(
        self,
        limit: int = 50,
        enabled_providers: list[str] | None = None,
    ) -> ChartsResult:
        """Get top chart albums from all providers.
        
        Args:
            limit: Maximum albums to return
            enabled_providers: List of enabled providers
        
        Returns:
            ChartsResult with chart albums from all sources
        """
        providers = enabled_providers or ["spotify", "deezer"]
        tasks: list[asyncio.Task[list[tuple[ChartAlbum, str]]]] = []
        
        # Deezer Chart Albums (NO AUTH!)
        if "deezer" in providers and self._deezer:
            tasks.append(
                asyncio.create_task(
                    self._fetch_deezer_chart_albums(limit),
                    name="deezer_albums"
                )
            )
        
        # Wait for all tasks
        all_albums: list[tuple[ChartAlbum, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task, result in zip(tasks, results, strict=False):
                task_name = task.get_name()
                source = task_name.split("_")[0]
                
                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"ChartsService: {source} albums failed: {result}")
                else:
                    for album, src in result:
                        all_albums.append((album, src))
                        source_counts[src] = source_counts.get(src, 0) + 1
        
        # Deduplicate
        total_before = len(all_albums)
        deduped = self._deduplicate_albums(all_albums)
        
        return ChartsResult(
            albums=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
        )
    
    async def get_chart_artists(
        self,
        limit: int = 50,
        enabled_providers: list[str] | None = None,
    ) -> ChartsResult:
        """Get top chart artists from all providers.
        
        Args:
            limit: Maximum artists to return
            enabled_providers: List of enabled providers
        
        Returns:
            ChartsResult with chart artists from all sources
        """
        providers = enabled_providers or ["spotify", "deezer"]
        tasks: list[asyncio.Task[list[tuple[ChartArtist, str]]]] = []
        
        # Deezer Chart Artists (NO AUTH!)
        if "deezer" in providers and self._deezer:
            tasks.append(
                asyncio.create_task(
                    self._fetch_deezer_chart_artists(limit),
                    name="deezer_artists"
                )
            )
        
        # Wait for all tasks
        all_artists: list[tuple[ChartArtist, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task, result in zip(tasks, results, strict=False):
                task_name = task.get_name()
                source = task_name.split("_")[0]
                
                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"ChartsService: {source} artists failed: {result}")
                else:
                    for artist, src in result:
                        all_artists.append((artist, src))
                        source_counts[src] = source_counts.get(src, 0) + 1
        
        # Deduplicate
        total_before = len(all_artists)
        deduped = self._deduplicate_artists(all_artists)
        
        return ChartsResult(
            artists=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
        )
    
    async def get_editorial_picks(
        self,
        limit: int = 50,
        enabled_providers: list[str] | None = None,
    ) -> ChartsResult:
        """Get editorial/curated picks from all providers.
        
        Hey future me - das sind handverlesene Empfehlungen der Services!
        Deezer "Editorial Releases" sind oft hochwertige neue Releases.
        
        Args:
            limit: Maximum items to return
            enabled_providers: List of enabled providers
        
        Returns:
            ChartsResult with editorial albums
        """
        providers = enabled_providers or ["spotify", "deezer"]
        tasks: list[asyncio.Task[list[tuple[ChartAlbum, str]]]] = []
        
        # Deezer Editorial (NO AUTH!)
        if "deezer" in providers and self._deezer:
            tasks.append(
                asyncio.create_task(
                    self._fetch_deezer_editorial(limit),
                    name="deezer_editorial"
                )
            )
        
        # Wait for all tasks
        all_albums: list[tuple[ChartAlbum, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task, result in zip(tasks, results, strict=False):
                task_name = task.get_name()
                source = task_name.split("_")[0]
                
                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"ChartsService: {source} editorial failed: {result}")
                else:
                    for album, src in result:
                        all_albums.append((album, src))
                        source_counts[src] = source_counts.get(src, 0) + 1
        
        # Deduplicate
        total_before = len(all_albums)
        deduped = self._deduplicate_albums(all_albums)
        
        return ChartsResult(
            albums=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
        )
    
    # =========================================================================
    # DEEZER FETCHERS
    # =========================================================================
    
    async def _fetch_deezer_chart_tracks(
        self,
        limit: int,
    ) -> list[tuple[ChartTrack, str]]:
        """Fetch chart tracks from Deezer."""
        if not self._deezer:
            return []
        
        try:
            track_dtos = await self._deezer.get_chart_tracks(limit)
            
            result: list[tuple[ChartTrack, str]] = []
            for position, dto in enumerate(track_dtos, 1):
                chart_track = ChartTrack(
                    title=dto.title,
                    artist_name=dto.artist_name or "Unknown",
                    album_name=dto.album_name,
                    deezer_id=dto.deezer_id,
                    isrc=dto.isrc,
                    duration_ms=dto.duration_ms,
                    preview_url=dto.preview_url,
                    artwork_url=dto.artwork_url,
                    source_service="deezer",
                    chart_position=position,
                    external_urls=dto.external_urls or {},
                )
                result.append((chart_track, "deezer"))
            
            return result
        
        except Exception as e:
            logger.warning(f"Deezer chart tracks failed: {e}")
            raise
    
    async def _fetch_deezer_chart_albums(
        self,
        limit: int,
    ) -> list[tuple[ChartAlbum, str]]:
        """Fetch chart albums from Deezer."""
        if not self._deezer:
            return []
        
        try:
            album_dtos = await self._deezer.get_chart_albums(limit)
            
            result: list[tuple[ChartAlbum, str]] = []
            for position, dto in enumerate(album_dtos, 1):
                chart_album = ChartAlbum(
                    title=dto.title,
                    artist_name=dto.artist_name or "Unknown",
                    deezer_id=dto.deezer_id,
                    upc=dto.upc,
                    release_date=dto.release_date,
                    total_tracks=dto.total_tracks or 0,
                    artwork_url=dto.artwork_url,
                    source_service="deezer",
                    chart_position=position,
                    external_urls=dto.external_urls or {},
                )
                result.append((chart_album, "deezer"))
            
            return result
        
        except Exception as e:
            logger.warning(f"Deezer chart albums failed: {e}")
            raise
    
    async def _fetch_deezer_chart_artists(
        self,
        limit: int,
    ) -> list[tuple[ChartArtist, str]]:
        """Fetch chart artists from Deezer."""
        if not self._deezer:
            return []
        
        try:
            artist_dtos = await self._deezer.get_chart_artists(limit)
            
            result: list[tuple[ChartArtist, str]] = []
            for position, dto in enumerate(artist_dtos, 1):
                chart_artist = ChartArtist(
                    name=dto.name,
                    deezer_id=dto.deezer_id,
                    artwork_url=dto.artwork_url,
                    source_service="deezer",
                    chart_position=position,
                    external_urls=dto.external_urls or {},
                )
                result.append((chart_artist, "deezer"))
            
            return result
        
        except Exception as e:
            logger.warning(f"Deezer chart artists failed: {e}")
            raise
    
    async def _fetch_deezer_editorial(
        self,
        limit: int,
    ) -> list[tuple[ChartAlbum, str]]:
        """Fetch editorial releases from Deezer."""
        if not self._deezer:
            return []
        
        try:
            album_dtos = await self._deezer.get_editorial_releases(limit)
            
            result: list[tuple[ChartAlbum, str]] = []
            for dto in album_dtos:
                chart_album = ChartAlbum(
                    title=dto.title,
                    artist_name=dto.artist_name or "Unknown",
                    deezer_id=dto.deezer_id,
                    upc=dto.upc,
                    release_date=dto.release_date,
                    total_tracks=dto.total_tracks or 0,
                    artwork_url=dto.artwork_url,
                    source_service="deezer",
                    external_urls=dto.external_urls or {},
                )
                result.append((chart_album, "deezer"))
            
            return result
        
        except Exception as e:
            logger.warning(f"Deezer editorial failed: {e}")
            raise
    
    # =========================================================================
    # DEDUPLICATION
    # =========================================================================
    
    def _deduplicate_tracks(
        self,
        tracks: list[tuple[ChartTrack, str]],
    ) -> list[ChartTrack]:
        """Deduplicate tracks by ISRC then by artist|title."""
        seen_isrcs: set[str] = set()
        seen_keys: set[str] = set()
        result: list[ChartTrack] = []
        
        for track, source in tracks:
            # Try ISRC first
            if track.isrc:
                if track.isrc in seen_isrcs:
                    continue
                seen_isrcs.add(track.isrc)
            
            # Fallback to normalized key
            key = f"{track.artist_name.lower().strip()}|{track.title.lower().strip()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            result.append(track)
        
        return result
    
    def _deduplicate_albums(
        self,
        albums: list[tuple[ChartAlbum, str]],
    ) -> list[ChartAlbum]:
        """Deduplicate albums by UPC then by artist|title."""
        seen_upcs: set[str] = set()
        seen_keys: set[str] = set()
        result: list[ChartAlbum] = []
        
        for album, source in albums:
            # Try UPC first
            if album.upc:
                if album.upc in seen_upcs:
                    continue
                seen_upcs.add(album.upc)
            
            # Fallback to normalized key
            key = f"{album.artist_name.lower().strip()}|{album.title.lower().strip()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            result.append(album)
        
        return result
    
    def _deduplicate_artists(
        self,
        artists: list[tuple[ChartArtist, str]],
    ) -> list[ChartArtist]:
        """Deduplicate artists by normalized name."""
        seen_names: set[str] = set()
        result: list[ChartArtist] = []
        
        for artist, source in artists:
            key = artist.name.lower().strip()
            if key in seen_names:
                continue
            seen_names.add(key)
            
            result.append(artist)
        
        return result


# Export
__all__ = [
    "ChartsService",
    "ChartsResult",
    "ChartTrack",
    "ChartAlbum",
    "ChartArtist",
]
