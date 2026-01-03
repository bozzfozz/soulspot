"""DEPRECATED: Merged into browse_service.py (Jan 2025)

===============================================================================
⚠️ DEPRECATED - DO NOT USE - TO BE DELETED ⚠️
===============================================================================

This service has been merged into BrowseService:
    from soulspot.application.services.browse_service import BrowseService

Migrated methods:
    DiscoverService.get_related_artists() → BrowseService.get_related_artists()
    DiscoverService.get_discovery_suggestions() → BrowseService.get_discovery_suggestions()

Backward compatibility aliases in browse_service.py:
    DiscoverService = BrowseService
    DiscoverResult = BrowseResult

DELETE THIS FILE after confirming all callers are updated!
File marked for deletion: discover_service.py (565 LOC → browse_service.py)
===============================================================================

ORIGINAL DOCSTRING:
Multi-Provider Artist Discovery Service.

Hey future me - dieser Service aggregiert Artist Discovery von ALLEN Providern!

Das Problem: /spotify/discover zeigt nur Spotify's "Fans Also Like".
Diese Lösung: Kombiniere Spotify + Deezer + (future) für reichhaltigere Suggestions.

Architecture:
    DiscoverService
        ↓
    [SpotifyPlugin, DeezerPlugin]
        ↓
    Aggregate & Deduplicate
        ↓
    DiscoverResult

Features:
1. Related Artists - "Fans Also Like" von mehreren Services
2. Artist Discovery - Suggestions basierend auf gefolgten Artists
3. Deduplication - Gleiche Artists von verschiedenen Services werden gemerged

Deduplication Strategy:
- Primary: Spotify ID match (wenn Artist bei beiden existiert)
- Secondary: Normalized name match (lowercase, trimmed)
- Merge: Combine metadata from both sources

Usage:
    service = DiscoverService(
        spotify_plugin=spotify_plugin,
        deezer_plugin=deezer_plugin,
    )

    # Get related artists for a specific artist
    result = await service.get_related_artists(
        spotify_id="3WrFJ7ztbogyGnTHbHJFl2",
        deezer_id="1234567",
    )

    # Get discovery suggestions based on followed artists
    result = await service.get_discovery_suggestions(
        source_artists=followed_artists,
        max_suggestions=50,
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.domain.dtos import ArtistDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredArtist:
    """A discovered artist with metadata from multiple sources.

    Hey future me - ein Artist kann von mehreren Services kommen!
    source_service zeigt den PRIMARY source (wer ihn zuerst gefunden hat).
    """

    name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    image_url: str | None = None
    genres: list[str] = field(default_factory=list)
    popularity: int = 0
    source_service: str = "unknown"
    based_on: str | None = None  # Which artist this was discovered from

    # Additional metadata from multiple sources
    external_urls: dict[str, str] = field(default_factory=dict)


@dataclass
class DiscoverResult:
    """Result from discovery operations.

    Contains discovered artists and metadata about the operation.
    """

    artists: list[DiscoveredArtist] = field(default_factory=list)
    """Deduplicated list of discovered artists."""

    source_counts: dict[str, int] = field(default_factory=dict)
    """How many artists came from each source before dedup."""

    total_before_dedup: int = 0
    """Total artists before deduplication."""

    errors: dict[str, str] = field(default_factory=dict)
    """Errors from each provider (provider_name -> error_message)."""

    based_on_count: int = 0
    """Number of source artists used for discovery."""


class DiscoverService:
    """Multi-Provider Artist Discovery Service.

    Hey future me - dieser Service ist analog zu NewReleasesService aufgebaut!
    Orchestriert mehrere Plugins und dedupliziert die Ergebnisse.

    Features:
    1. get_related_artists() - Related artists für einen spezifischen Artist
    2. get_discovery_suggestions() - Suggestions basierend auf einer Liste von Artists

    Beide Methoden aggregieren von Spotify + Deezer und deduplizieren.
    """

    def __init__(
        self,
        spotify_plugin: "SpotifyPlugin | None" = None,
        deezer_plugin: "DeezerPlugin | None" = None,
    ) -> None:
        """Initialize service with available plugins.

        Args:
            spotify_plugin: SpotifyPlugin instance (optional, may be unauthenticated)
            deezer_plugin: DeezerPlugin instance (optional)
        """
        self._spotify = spotify_plugin
        self._deezer = deezer_plugin

    async def get_related_artists(
        self,
        spotify_id: str | None = None,
        deezer_id: str | None = None,
        artist_name: str | None = None,
        limit: int = 20,
        enabled_providers: list[str] | None = None,
    ) -> DiscoverResult:
        """Get artists similar to a specific artist from all providers.

        Hey future me - das ist für "Fans Also Like" Sections!

        Strategy:
        1. Wenn spotify_id vorhanden → Spotify Related Artists
        2. Wenn deezer_id vorhanden → Deezer Related Artists
        3. Wenn nur name → Suche Artist auf beiden Services, dann Related
        4. Dedupliziere und merge

        Args:
            spotify_id: Spotify artist ID
            deezer_id: Deezer artist ID
            artist_name: Artist name (for search if no ID)
            limit: Maximum artists to return
            enabled_providers: List of enabled providers ["spotify", "deezer"]

        Returns:
            DiscoverResult with related artists from all sources
        """
        from soulspot.domain.ports.plugin import PluginCapability

        providers = enabled_providers or ["spotify", "deezer"]
        tasks: list[asyncio.Task[list[tuple[DiscoveredArtist, str]]]] = []

        # Spotify Related Artists
        if (
            "spotify" in providers
            and self._spotify
            and spotify_id
            and self._spotify.can_use(PluginCapability.GET_RELATED_ARTISTS)
        ):
            tasks.append(
                asyncio.create_task(
                    self._fetch_spotify_related(spotify_id, limit),
                    name="spotify_related",
                )
            )

        # Deezer Related Artists
        if "deezer" in providers and self._deezer:
            deezer_artist_id = deezer_id

            # If no deezer_id, try to find by name search
            if not deezer_artist_id and artist_name:
                deezer_artist_id = await self._find_deezer_artist_id(artist_name)

            if deezer_artist_id:
                tasks.append(
                    asyncio.create_task(
                        self._fetch_deezer_related(deezer_artist_id, limit),
                        name="deezer_related",
                    )
                )

        # Wait for all tasks
        all_artists: list[tuple[DiscoveredArtist, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for task, result in zip(tasks, results, strict=False):
                task_name = task.get_name()
                source = task_name.split("_")[0]  # "spotify_related" -> "spotify"

                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"DiscoverService: {source} failed: {result}")
                else:
                    for artist, src in result:
                        all_artists.append((artist, src))
                        source_counts[src] = source_counts.get(src, 0) + 1

        # Deduplicate
        total_before = len(all_artists)
        deduped = self._deduplicate_artists(all_artists)

        return DiscoverResult(
            artists=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
            based_on_count=1,
        )

    async def get_discovery_suggestions(
        self,
        source_artists: list["ArtistDTO"],
        max_suggestions: int = 50,
        max_per_artist: int = 5,
        enabled_providers: list[str] | None = None,
        exclude_artist_ids: set[str] | None = None,
    ) -> DiscoverResult:
        """Get discovery suggestions based on a list of followed artists.

        Hey future me - das ist für die Discovery Page!

        Strategy:
        1. Für jeden source_artist: hole related artists von allen Providern
        2. Aggregiere alle Suggestions
        3. Dedupliziere
        4. Sortiere nach Häufigkeit (Artists die von mehreren Sources empfohlen werden = höher)
        5. Filtere bereits gefolgte Artists raus

        Args:
            source_artists: List of artists to base suggestions on
            max_suggestions: Maximum suggestions to return
            max_per_artist: Maximum suggestions per source artist
            enabled_providers: List of enabled providers
            exclude_artist_ids: Set of artist IDs to exclude (e.g., already followed)

        Returns:
            DiscoverResult with aggregated suggestions
        """
        from soulspot.domain.ports.plugin import PluginCapability

        providers = enabled_providers or ["spotify", "deezer"]
        exclude_ids = exclude_artist_ids or set()

        all_artists: list[tuple[DiscoveredArtist, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}

        # Limit source artists to avoid too many API calls
        source_artists = source_artists[:20]  # Max 20 base artists

        for source_artist in source_artists:
            tasks: list[asyncio.Task[list[tuple[DiscoveredArtist, str]]]] = []

            # Spotify
            if "spotify" in providers and self._spotify:
                spotify_id = source_artist.spotify_id
                if spotify_id and self._spotify.can_use(
                    PluginCapability.GET_RELATED_ARTISTS
                ):
                    tasks.append(
                        asyncio.create_task(
                            self._fetch_spotify_related(
                                spotify_id, max_per_artist, based_on=source_artist.name
                            ),
                            name="spotify_related",
                        )
                    )

            # Deezer
            if "deezer" in providers and self._deezer:
                deezer_id = source_artist.deezer_id

                # Try to find Deezer ID if not present
                if not deezer_id:
                    deezer_id = await self._find_deezer_artist_id(source_artist.name)

                if deezer_id:
                    tasks.append(
                        asyncio.create_task(
                            self._fetch_deezer_related(
                                deezer_id, max_per_artist, based_on=source_artist.name
                            ),
                            name="deezer_related",
                        )
                    )

            # Wait for this artist's related artists
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for task, result in zip(tasks, results, strict=False):
                    task_name = task.get_name()
                    source = task_name.split("_")[0]

                    if isinstance(result, Exception):
                        # Only log first error per provider
                        if source not in errors:
                            errors[source] = str(result)
                    else:
                        for artist, src in result:
                            # Skip excluded artists
                            if artist.spotify_id and artist.spotify_id in exclude_ids:
                                continue
                            if artist.deezer_id and artist.deezer_id in exclude_ids:
                                continue

                            all_artists.append((artist, src))
                            source_counts[src] = source_counts.get(src, 0) + 1

        # Deduplicate with frequency scoring
        total_before = len(all_artists)
        deduped = self._deduplicate_artists_with_scoring(all_artists)

        return DiscoverResult(
            artists=deduped[:max_suggestions],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
            based_on_count=len(source_artists),
        )

    async def _fetch_spotify_related(
        self,
        artist_id: str,
        limit: int,
        based_on: str | None = None,
    ) -> list[tuple[DiscoveredArtist, str]]:
        """Fetch related artists from Spotify.

        Returns list of (DiscoveredArtist, source) tuples.
        """
        if not self._spotify:
            return []

        try:
            # Hey future me - Spotify's get_related_artists doesn't take limit param!
            # It always returns up to 20 artists. We slice after.
            related_dtos = await self._spotify.get_related_artists(artist_id)
            if limit:
                related_dtos = related_dtos[:limit]

            result: list[tuple[DiscoveredArtist, str]] = []
            for dto in related_dtos:
                artist = DiscoveredArtist(
                    name=dto.name,
                    spotify_id=dto.spotify_id,
                    deezer_id=None,
                    # Hey future me - ArtistDTO.image ist ImageRef!
                    image_url=dto.image.url,
                    genres=dto.genres or [],
                    popularity=dto.popularity or 0,
                    source_service="spotify",
                    based_on=based_on,
                    external_urls=dto.external_urls or {},
                )
                result.append((artist, "spotify"))

            return result

        except Exception as e:
            logger.warning(f"Spotify related artists failed for {artist_id}: {e}")
            raise

    async def _fetch_deezer_related(
        self,
        artist_id: str,
        limit: int,
        based_on: str | None = None,
    ) -> list[tuple[DiscoveredArtist, str]]:
        """Fetch related artists from Deezer.

        Returns list of (DiscoveredArtist, source) tuples.
        """
        if not self._deezer:
            return []

        try:
            related_dtos = await self._deezer.get_related_artists(artist_id, limit)

            result: list[tuple[DiscoveredArtist, str]] = []
            for dto in related_dtos:
                artist = DiscoveredArtist(
                    name=dto.name,
                    spotify_id=None,
                    deezer_id=dto.deezer_id,
                    # Hey future me - ArtistDTO.image ist ImageRef!
                    image_url=dto.image.url,
                    genres=dto.genres or [],
                    popularity=dto.popularity or 0,
                    source_service="deezer",
                    based_on=based_on,
                    external_urls=dto.external_urls or {},
                )
                result.append((artist, "deezer"))

            return result

        except Exception as e:
            logger.warning(f"Deezer related artists failed for {artist_id}: {e}")
            raise

    async def _find_deezer_artist_id(self, artist_name: str) -> str | None:
        """Find Deezer artist ID by name search.

        Hey future me - Deezer hat andere IDs als Spotify!
        Diese Methode sucht einen Artist auf Deezer by Name.
        """
        if not self._deezer:
            return None

        try:
            search_result = await self._deezer.search_artists(artist_name, limit=5)

            if not search_result.items:
                return None

            # Take first exact or close match
            name_lower = artist_name.lower().strip()
            for dto in search_result.items:
                if dto.name.lower().strip() == name_lower:
                    return dto.deezer_id

            # Fallback to first result
            return search_result.items[0].deezer_id

        except Exception as e:
            logger.debug(f"Deezer artist search failed for '{artist_name}': {e}")
            return None

    def _deduplicate_artists(
        self,
        artists: list[tuple[DiscoveredArtist, str]],
    ) -> list[DiscoveredArtist]:
        """Deduplicate artists by name (simple version).

        Hey future me - hier werden Artists von verschiedenen Services gemerged!
        Primary key: normalized name (lowercase, trimmed)
        """
        seen_names: dict[str, DiscoveredArtist] = {}

        for artist, _source in artists:
            key = artist.name.lower().strip()

            if key not in seen_names:
                seen_names[key] = artist
            else:
                # Merge: keep first, but add IDs from second
                existing = seen_names[key]
                if not existing.spotify_id and artist.spotify_id:
                    existing.spotify_id = artist.spotify_id
                if not existing.deezer_id and artist.deezer_id:
                    existing.deezer_id = artist.deezer_id
                if not existing.image_url and artist.image_url:
                    existing.image_url = artist.image_url
                if not existing.genres and artist.genres:
                    existing.genres = artist.genres
                # Merge external_urls
                existing.external_urls.update(artist.external_urls)

        # Sort by popularity
        result = list(seen_names.values())
        result.sort(key=lambda a: a.popularity, reverse=True)

        return result

    def _deduplicate_artists_with_scoring(
        self,
        artists: list[tuple[DiscoveredArtist, str]],
    ) -> list[DiscoveredArtist]:
        """Deduplicate artists with frequency scoring.

        Hey future me - Artists die von MEHREREN Sources empfohlen werden
        bekommen einen höheren Score! Das sind oft die besten Suggestions.
        """
        # Count occurrences by name
        name_counts: dict[str, int] = {}
        seen_artists: dict[str, DiscoveredArtist] = {}

        for artist, _source in artists:
            key = artist.name.lower().strip()
            name_counts[key] = name_counts.get(key, 0) + 1

            if key not in seen_artists:
                seen_artists[key] = artist
            else:
                # Merge IDs
                existing = seen_artists[key]
                if not existing.spotify_id and artist.spotify_id:
                    existing.spotify_id = artist.spotify_id
                if not existing.deezer_id and artist.deezer_id:
                    existing.deezer_id = artist.deezer_id
                if not existing.image_url and artist.image_url:
                    existing.image_url = artist.image_url
                existing.external_urls.update(artist.external_urls)

        # Sort by frequency (recommendations count) then popularity
        result = list(seen_artists.values())
        result.sort(
            key=lambda a: (name_counts.get(a.name.lower().strip(), 0), a.popularity),
            reverse=True,
        )

        return result

    # =============================================================================
    # ALIAS FOR BACKWARD COMPATIBILITY (Dec 2025)
    # Hey future me - this method was expected by ui.py but didn't exist!
    # It's just an alias for get_related_artists with different parameter names.
    # =============================================================================

    async def discover_similar_artists(
        self,
        seed_artist_name: str,
        seed_artist_spotify_id: str | None = None,
        seed_artist_deezer_id: str | None = None,
        limit: int = 20,
        enabled_providers: list[str] | None = None,
    ) -> DiscoverResult:
        """Discover artists similar to a seed artist.

        Hey future me - this is an alias for get_related_artists()!
        The ui.py route expects this method name and parameter structure.

        Now supports BOTH Spotify ID AND Deezer ID for better multi-provider discovery!
        - If only deezer_id: Deezer can directly query related artists
        - If only spotify_id: Spotify can directly query, Deezer searches by name
        - If both: Best of both worlds

        Args:
            seed_artist_name: Name of the seed artist
            seed_artist_spotify_id: Optional Spotify ID of the seed artist
            seed_artist_deezer_id: Optional Deezer ID of the seed artist
            limit: Max artists to return
            enabled_providers: List of providers to use (["spotify", "deezer"])

        Returns:
            DiscoverResult with similar artists
        """
        return await self.get_related_artists(
            spotify_id=seed_artist_spotify_id,
            deezer_id=seed_artist_deezer_id,
            artist_name=seed_artist_name,
            limit=limit,
            enabled_providers=enabled_providers,
        )


# Export
__all__ = ["DiscoverService", "DiscoverResult", "DiscoveredArtist"]
