"""ImportSource Protocol and Registry.

Hey future me - THIS IS THE CORE ABSTRACTION!

The ImportSource Protocol defines what any import source must provide:
- Artists (followed/liked)
- Albums (saved/for artist)
- Tracks (liked/for album)
- Playlists (user playlists)

The ImportSourceRegistry manages all sources and provides:
- Registration of new sources
- Filtering by availability (enabled + authenticated)
- Unified import from all sources

ARCHITECTURE:
```
┌─────────────────────────────────────────────────────────┐
│                 ImportSourceRegistry                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │ LocalSource │ │SpotifySource│ │DeezerSource │ ...    │
│  │ (files)     │ │ (API)       │ │ (API)       │        │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘        │
│         │               │               │               │
│         └───────────────┼───────────────┘               │
│                         ▼                               │
│              import_from_all_sources()                  │
│                         │                               │
│                         ▼                               │
│                  ImportResult                           │
│         (artists, albums, tracks, errors)               │
└─────────────────────────────────────────────────────────┘
```

Usage:
    registry = ImportSourceRegistry()
    registry.register(SpotifyImportSource(plugin))
    registry.register(DeezerImportSource(plugin))
    
    result = await registry.import_from_all_sources()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, PlaylistDTO, TrackDTO

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result from importing entities from a source.
    
    Hey future me - this aggregates results from one or multiple sources!
    The errors list captures per-source or per-entity errors without
    failing the entire import.
    """
    artists: list["ArtistDTO"] = field(default_factory=list)
    albums: list["AlbumDTO"] = field(default_factory=list)
    tracks: list["TrackDTO"] = field(default_factory=list)
    playlists: list["PlaylistDTO"] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    # Stats
    source_name: str = ""
    
    def merge(self, other: "ImportResult") -> "ImportResult":
        """Merge another result into this one.
        
        Hey future me - used when aggregating from multiple sources!
        """
        return ImportResult(
            artists=self.artists + other.artists,
            albums=self.albums + other.albums,
            tracks=self.tracks + other.tracks,
            playlists=self.playlists + other.playlists,
            errors=self.errors + other.errors,
            source_name=f"{self.source_name},{other.source_name}" if self.source_name else other.source_name,
        )


@runtime_checkable
class ImportSource(Protocol):
    """Protocol for import sources (Spotify, Deezer, Local, etc.).
    
    Hey future me - this is the ABSTRACTION!
    Any import source must implement these methods.
    
    Properties:
        name: Unique identifier for the source
        is_available: True if source can be used (enabled + authenticated)
    
    Methods:
        import_artists: Get all followed/liked artists
        import_albums_for_artist: Get albums for a specific artist
        import_tracks_for_album: Get tracks for a specific album
        import_playlists: Get user playlists
    """
    
    @property
    def name(self) -> str:
        """Unique name for this source (e.g., 'spotify', 'deezer')."""
        ...
    
    @property
    def is_available(self) -> bool:
        """True if source is enabled AND authenticated (if required)."""
        ...
    
    async def import_artists(self) -> list["ArtistDTO"]:
        """Import all followed/liked artists from this source.
        
        Returns:
            List of ArtistDTOs from this source
        """
        ...
    
    async def import_albums_for_artist(
        self, 
        artist_id: str,
        artist_name: str | None = None,
    ) -> list["AlbumDTO"]:
        """Import all albums for a specific artist.
        
        Args:
            artist_id: Provider-specific artist ID
            artist_name: Artist name (for search fallback)
        
        Returns:
            List of AlbumDTOs for this artist
        """
        ...
    
    async def import_tracks_for_album(
        self,
        album_id: str,
    ) -> list["TrackDTO"]:
        """Import all tracks for a specific album.
        
        Args:
            album_id: Provider-specific album ID
        
        Returns:
            List of TrackDTOs for this album
        """
        ...
    
    async def import_playlists(self) -> list["PlaylistDTO"]:
        """Import user playlists from this source.
        
        Returns:
            List of PlaylistDTOs
        """
        ...


class ImportSourceRegistry:
    """Registry for import sources.
    
    Hey future me - this manages ALL import sources!
    Register sources at startup, then use import_from_all_sources()
    to get unified data from all enabled sources.
    
    Usage:
        registry = ImportSourceRegistry()
        registry.register(SpotifyImportSource(spotify_plugin))
        registry.register(DeezerImportSource(deezer_plugin))
        
        result = await registry.import_from_all_sources()
    """
    
    def __init__(self) -> None:
        """Initialize empty registry."""
        self._sources: dict[str, ImportSource] = {}
    
    def register(self, source: ImportSource) -> None:
        """Register an import source.
        
        Args:
            source: ImportSource implementation to register
        """
        self._sources[source.name] = source
        logger.debug(f"Registered import source: {source.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister an import source.
        
        Args:
            name: Name of source to remove
        """
        if name in self._sources:
            del self._sources[name]
            logger.debug(f"Unregistered import source: {name}")
    
    def get(self, name: str) -> ImportSource | None:
        """Get a specific source by name.
        
        Args:
            name: Source name (e.g., 'spotify')
        
        Returns:
            ImportSource if found, None otherwise
        """
        return self._sources.get(name)
    
    def get_available_sources(self) -> list[ImportSource]:
        """Get all sources that are currently available.
        
        Returns:
            List of enabled + authenticated sources
        """
        return [s for s in self._sources.values() if s.is_available]
    
    async def import_artists_from_all(self) -> ImportResult:
        """Import artists from all available sources.
        
        Hey future me - this is the UNIFIED import!
        Aggregates artists from Spotify + Deezer + any other source.
        
        Returns:
            Combined ImportResult with artists from all sources
        """
        result = ImportResult()
        
        for source in self.get_available_sources():
            try:
                logger.info(f"Importing artists from {source.name}...")
                artists = await source.import_artists()
                source_result = ImportResult(
                    artists=artists,
                    source_name=source.name,
                )
                result = result.merge(source_result)
                logger.info(f"Imported {len(artists)} artists from {source.name}")
            except Exception as e:
                error_msg = f"{source.name}: {e!s}"
                result.errors.append(error_msg)
                logger.warning(f"Artist import failed for {source.name}: {e}")
        
        return result
    
    async def import_from_all_sources(self) -> ImportResult:
        """Import everything from all available sources.
        
        This imports:
        - Artists (followed/liked)
        - Playlists (user playlists)
        
        Albums and tracks are typically fetched on-demand per artist/album,
        not in bulk import.
        
        Returns:
            Combined ImportResult from all sources
        """
        result = ImportResult()
        
        # Import artists from all sources
        artists_result = await self.import_artists_from_all()
        result = result.merge(artists_result)
        
        # Import playlists from all sources
        for source in self.get_available_sources():
            try:
                playlists = await source.import_playlists()
                result.playlists.extend(playlists)
                logger.info(f"Imported {len(playlists)} playlists from {source.name}")
            except Exception as e:
                result.errors.append(f"{source.name} playlists: {e!s}")
                logger.warning(f"Playlist import failed for {source.name}: {e}")
        
        return result
