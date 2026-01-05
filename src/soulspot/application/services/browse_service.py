# Hey future me – this is the UNIFIED browse service for ALL discovery & new release operations!
# Merged from discover_service.py + new_releases_service.py
# These operations are logically related: both discover new music for the user.
# The split was artificial – now we have one clean service for all browse/discovery needs.
"""
BrowseService: Unified service for music discovery and new releases.

This service aggregates data from multiple providers (Spotify, Deezer, Tidal, etc.)
to provide comprehensive browse/discovery functionality:

1. **New Releases** - Latest albums from followed artists
2. **Related Artists** - "Fans Also Like" recommendations
3. **Discovery Suggestions** - Artist recommendations based on listening history

Split from:
- discover_service.py (565 LOC) - Related artists, discovery suggestions
- new_releases_service.py (275 LOC) - New releases aggregation

Architecture:
```
UI Route → BrowseService → [SpotifyPlugin, DeezerPlugin, ...]
                ↓
        Aggregate & Deduplicate
                ↓
        Sorted Results (AlbumDTO, DiscoveredArtist)
```

Multi-Provider Strategy:
1. Query ALL enabled providers in parallel
2. Aggregate results
3. Deduplicate by ISRC/UPC (albums) or normalized name (artists)
4. Track source counts for analytics
5. Handle partial failures gracefully (one provider fail = others continue)

Performance: All provider calls are async and parallelized via asyncio.gather()
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from soulspot.domain.dtos import AlbumDTO
from soulspot.domain.ports.plugin import PluginCapability

if TYPE_CHECKING:
    from soulspot.domain.dtos import ArtistDTO
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DiscoveredArtist:
    """A discovered artist with metadata from multiple sources.

    Hey future me – an artist can come from multiple services!
    source_service shows the PRIMARY source (who found it first).
    We merge IDs from both services when deduplicating.
    """

    name: str
    spotify_id: str | None = None
    deezer_id: str | None = None
    image_url: str | None = None
    genres: list[str] = field(default_factory=list)
    popularity: int = 0
    source_service: str = "unknown"
    based_on: str | None = None  # Which artist this was discovered from
    external_urls: dict[str, str] = field(default_factory=dict)


@dataclass
class BrowseResult:
    """Result container for browse/discovery operations.

    Works for both artist discovery and new releases.
    Contains metadata about sources and deduplication.
    """

    # For artist discovery
    artists: list[DiscoveredArtist] = field(default_factory=list)

    # For new releases
    albums: list[AlbumDTO] = field(default_factory=list)

    source_counts: dict[str, int] = field(default_factory=dict)
    """How many items came from each source before dedup."""

    total_before_dedup: int = 0
    """Total items before deduplication."""

    errors: dict[str, str] = field(default_factory=dict)
    """Errors per provider (provider_name -> error_message)."""

    based_on_count: int = 0
    """Number of source artists used (for discovery suggestions)."""


# Backward compatibility aliases
DiscoverResult = BrowseResult
NewReleasesResult = BrowseResult


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class BrowseService:
    """Unified service for music discovery and new releases.

    Hey future me – use this service for ALL browse/discovery operations!
    Handles:
    - New releases from followed artists
    - Related artists ("Fans Also Like")
    - Discovery suggestions based on listening history

    All methods aggregate from multiple providers and deduplicate results.

    Usage:
        service = BrowseService(spotify_plugin=spotify, deezer_plugin=deezer)

        # New releases
        result = await service.get_new_releases(days=90)

        # Related artists
        result = await service.get_related_artists(spotify_id="xxx")

        # Discovery suggestions
        result = await service.get_discovery_suggestions(source_artists=artists)
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

    # ───────────────────────────────────────────────────────────────────────────
    # NEW RELEASES
    # ───────────────────────────────────────────────────────────────────────────

    async def get_new_releases(
        self,
        days: int = 90,
        include_singles: bool = True,
        include_compilations: bool = True,
        enabled_providers: list[str] | None = None,
    ) -> BrowseResult:
        """Get new releases from ALL enabled providers.

        Hey future me – this aggregates new releases from followed artists!
        Each provider returns releases from artists the user follows there.

        Args:
            days: Look back period in days (default 90)
            include_singles: Include singles/EPs
            include_compilations: Include compilation albums
            enabled_providers: List of providers ["spotify", "deezer"]

        Returns:
            BrowseResult with aggregated albums
        """
        all_albums: list[AlbumDTO] = []
        source_counts: dict[str, int] = {}
        errors: dict[str, str] = {}

        # Determine which providers to query
        if enabled_providers is None:
            enabled_providers = []
            if self._spotify:
                enabled_providers.append("spotify")
            if self._deezer:
                enabled_providers.append("deezer")

        logger.info(f"BrowseService: Querying new releases from: {enabled_providers}")

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
                logger.debug("BrowseService: Spotify skipped (not authenticated)")
                errors["spotify"] = "Not authenticated"

        # Deezer task
        if "deezer" in enabled_providers and self._deezer:
            if self._deezer.is_authenticated:
                task = asyncio.create_task(
                    self._deezer.get_new_releases(
                        days=days,
                        include_singles=include_singles,
                        include_compilations=include_compilations,
                    )
                )
                tasks.append(("deezer", task))
            else:
                logger.debug("BrowseService: Deezer skipped (not authenticated)")
                errors["deezer"] = "Not authenticated"

        # Wait for all tasks
        for provider, task in tasks:
            try:
                albums = await task
                source_counts[provider] = len(albums)
                all_albums.extend(albums)
                logger.info(f"BrowseService: Got {len(albums)} releases from {provider}")
            except Exception as e:
                errors[provider] = str(e)
                source_counts[provider] = 0
                logger.warning(f"BrowseService: {provider} new releases failed: {e}")

        # Deduplicate
        total_before = len(all_albums)
        deduped_albums = self._deduplicate_albums(all_albums)

        # Sort by release date (newest first)
        deduped_albums.sort(key=lambda a: a.release_date or "1900-01-01", reverse=True)

        logger.info(
            f"BrowseService: New releases {total_before} → {len(deduped_albums)} after dedup"
        )

        return BrowseResult(
            albums=deduped_albums,
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
        )

    # ───────────────────────────────────────────────────────────────────────────
    # RELATED ARTISTS
    # ───────────────────────────────────────────────────────────────────────────

    async def get_related_artists(
        self,
        spotify_id: str | None = None,
        deezer_id: str | None = None,
        artist_name: str | None = None,
        limit: int = 20,
        enabled_providers: list[str] | None = None,
    ) -> BrowseResult:
        """Get artists similar to a specific artist from all providers.

        Hey future me – this is for "Fans Also Like" sections!

        Strategy:
        1. If spotify_id → Spotify Related Artists
        2. If deezer_id → Deezer Related Artists
        3. If only name → Search on each service, then get related
        4. Deduplicate and merge

        Args:
            spotify_id: Spotify artist ID
            deezer_id: Deezer artist ID
            artist_name: Artist name (for search if no ID)
            limit: Maximum artists to return
            enabled_providers: List of enabled providers

        Returns:
            BrowseResult with related artists
        """
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
                source = task_name.split("_")[0]

                if isinstance(result, Exception):
                    errors[source] = str(result)
                    logger.warning(f"BrowseService: {source} related failed: {result}")
                else:
                    for artist, src in result:
                        all_artists.append((artist, src))
                        source_counts[src] = source_counts.get(src, 0) + 1

        # Deduplicate
        total_before = len(all_artists)
        deduped = self._deduplicate_artists(all_artists)

        return BrowseResult(
            artists=deduped[:limit],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
            based_on_count=1,
        )

    # ───────────────────────────────────────────────────────────────────────────
    # DISCOVERY SUGGESTIONS
    # ───────────────────────────────────────────────────────────────────────────

    async def get_discovery_suggestions(
        self,
        source_artists: list["ArtistDTO"],
        max_suggestions: int = 50,
        max_per_artist: int = 5,
        enabled_providers: list[str] | None = None,
        exclude_artist_ids: set[str] | None = None,
    ) -> BrowseResult:
        """Get discovery suggestions based on a list of followed artists.

        Hey future me – this is for the Discovery Page!

        Strategy:
        1. For each source_artist: get related artists from all providers
        2. Aggregate all suggestions
        3. Deduplicate
        4. Score by frequency (artists recommended by multiple sources rank higher)
        5. Filter out already followed artists

        Args:
            source_artists: List of artists to base suggestions on
            max_suggestions: Maximum suggestions to return
            max_per_artist: Maximum suggestions per source artist
            enabled_providers: List of enabled providers
            exclude_artist_ids: Artist IDs to exclude (e.g., already followed)

        Returns:
            BrowseResult with aggregated suggestions
        """
        providers = enabled_providers or ["spotify", "deezer"]
        exclude_ids = exclude_artist_ids or set()

        all_artists: list[tuple[DiscoveredArtist, str]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}

        # Limit source artists to avoid too many API calls
        source_artists = source_artists[:20]

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

        return BrowseResult(
            artists=deduped[:max_suggestions],
            source_counts=source_counts,
            total_before_dedup=total_before,
            errors=errors,
            based_on_count=len(source_artists),
        )

    # ───────────────────────────────────────────────────────────────────────────
    # BACKWARD COMPATIBILITY ALIASES
    # ───────────────────────────────────────────────────────────────────────────

    async def discover_similar_artists(
        self,
        seed_artist_name: str,
        seed_artist_spotify_id: str | None = None,
        seed_artist_deezer_id: str | None = None,
        limit: int = 20,
        enabled_providers: list[str] | None = None,
    ) -> BrowseResult:
        """Alias for get_related_artists() - backward compatibility.

        Hey future me – ui.py expects this method name!
        """
        return await self.get_related_artists(
            spotify_id=seed_artist_spotify_id,
            deezer_id=seed_artist_deezer_id,
            artist_name=seed_artist_name,
            limit=limit,
            enabled_providers=enabled_providers,
        )

    async def get_all_new_releases(
        self,
        days: int = 90,
        include_singles: bool = True,
        include_compilations: bool = True,
        enabled_providers: list[str] | None = None,
    ) -> BrowseResult:
        """Alias for get_new_releases() - backward compatibility."""
        return await self.get_new_releases(
            days=days,
            include_singles=include_singles,
            include_compilations=include_compilations,
            enabled_providers=enabled_providers,
        )

    async def get_new_releases_for_library_artists(
        self,
        library_artists: list["ArtistDTO"],
        days: int = 30,
        include_singles: bool = True,
        include_compilations: bool = True,
    ) -> BrowseResult:
        """Get new releases for artists in the user's LOCAL library.

        Hey future me - PERSONAL New Releases from DB artists!
        Unlike get_new_releases() which uses "followed" artists from provider APIs,
        this method uses artists the user has added to their LOCAL library.

        Strategy:
        1. For each library artist with spotify_id → Get recent albums via Spotify
        2. For each library artist with deezer_id → Get recent albums via Deezer
        3. Aggregate, deduplicate, sort by release date
        4. NO OAuth needed for Deezer artist lookup!

        This allows Personal New Releases EVEN WITHOUT any provider login!
        Artists in library have deezer_id from enrichment → fetch their releases.

        Args:
            library_artists: List of ArtistDTO from database (with spotify_id/deezer_id)
            days: Look back period in days (default 30)
            include_singles: Include singles/EPs
            include_compilations: Include compilation albums

        Returns:
            BrowseResult with aggregated albums from library artists
        """
        from datetime import UTC, datetime, timedelta

        all_albums: list[AlbumDTO] = []
        source_counts: dict[str, int] = {"spotify": 0, "deezer": 0}
        errors: dict[str, str] = {}
        seen_ids: set[str] = set()

        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        logger.info(
            f"BrowseService: Checking new releases for {len(library_artists)} library artists (last {days} days)"
        )

        # Batch process artists - limit to avoid API overload
        max_artists = min(len(library_artists), 50)  # Cap at 50 artists per request
        processed = 0

        for artist in library_artists[:max_artists]:
            albums_found = 0

            # Try Spotify first (if we have spotify_id AND plugin available AND authenticated)
            if artist.spotify_id and self._spotify and self._spotify.is_authenticated:
                try:
                    albums = await self._spotify.get_artist_albums(
                        artist_id=artist.spotify_id,
                        limit=10,  # Recent albums only
                    )
                    for album in albums:
                        # Skip duplicates
                        album_key = album.spotify_id or album.isrc or f"{artist.name}::{album.title}"
                        if album_key in seen_ids:
                            continue

                        # Filter by type
                        album_type = (album.album_type or "album").lower()
                        if album_type in ("single", "ep") and not include_singles:
                            continue
                        if album_type == "compilation" and not include_compilations:
                            continue

                        # Filter by date
                        if album.release_date and album.release_date >= cutoff_str:
                            seen_ids.add(album_key)
                            if not album.source_service:
                                album.source_service = "spotify"
                            all_albums.append(album)
                            albums_found += 1
                            source_counts["spotify"] += 1

                except Exception as e:
                    logger.debug(f"Spotify albums fetch failed for {artist.name}: {e}")

            # Try Deezer (if we have deezer_id AND plugin available - NO AUTH NEEDED!)
            if artist.deezer_id and self._deezer:
                try:
                    albums_response = await self._deezer.get_artist_albums(
                        artist_id=artist.deezer_id,
                        limit=10,  # Recent albums only
                    )
                    for album in albums_response.items:
                        # Skip duplicates (check both deezer_id and name::title)
                        album_key = album.deezer_id or f"{artist.name}::{album.title}"
                        if album_key in seen_ids:
                            continue

                        # Also check if same album exists from Spotify
                        spotify_key = album.spotify_id or album.isrc
                        if spotify_key and spotify_key in seen_ids:
                            continue

                        # Filter by type
                        album_type = (album.album_type or "album").lower()
                        if album_type in ("single", "ep") and not include_singles:
                            continue
                        if album_type == "compilation" and not include_compilations:
                            continue

                        # Filter by date
                        if album.release_date and album.release_date >= cutoff_str:
                            seen_ids.add(album_key)
                            if album.deezer_id:
                                seen_ids.add(album.deezer_id)
                            if not album.source_service:
                                album.source_service = "deezer"
                            all_albums.append(album)
                            albums_found += 1
                            source_counts["deezer"] += 1

                except Exception as e:
                    logger.debug(f"Deezer albums fetch failed for {artist.name}: {e}")

            processed += 1
            if albums_found > 0:
                logger.debug(f"Found {albums_found} new releases for {artist.name}")

        # Sort by release date (newest first)
        all_albums.sort(key=lambda a: a.release_date or "1900-01-01", reverse=True)

        logger.info(
            f"BrowseService: Found {len(all_albums)} total new releases from "
            f"{processed} library artists (spotify={source_counts['spotify']}, deezer={source_counts['deezer']})"
        )

        return BrowseResult(
            albums=all_albums,
            source_counts=source_counts,
            total_before_dedup=len(all_albums),  # Already deduped during collection
            errors=errors,
        )

    # ───────────────────────────────────────────────────────────────────────────
    # PRIVATE: PROVIDER FETCHERS
    # ───────────────────────────────────────────────────────────────────────────

    async def _fetch_spotify_related(
        self,
        artist_id: str,
        limit: int,
        based_on: str | None = None,
    ) -> list[tuple[DiscoveredArtist, str]]:
        """Fetch related artists from Spotify."""
        if not self._spotify:
            return []

        try:
            related_dtos = await self._spotify.get_related_artists(artist_id)
            if limit:
                related_dtos = related_dtos[:limit]

            result: list[tuple[DiscoveredArtist, str]] = []
            for dto in related_dtos:
                artist = DiscoveredArtist(
                    name=dto.name,
                    spotify_id=dto.spotify_id,
                    deezer_id=None,
                    image_url=dto.image.url if dto.image else None,
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
        """Fetch related artists from Deezer."""
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
                    image_url=dto.image.url if dto.image else None,
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
        """Find Deezer artist ID by name search."""
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

    # ───────────────────────────────────────────────────────────────────────────
    # PRIVATE: DEDUPLICATION
    # ───────────────────────────────────────────────────────────────────────────

    def _deduplicate_albums(self, albums: list[AlbumDTO]) -> list[AlbumDTO]:
        """Deduplicate albums by UPC or normalized artist::title.

        Hey future me – deduplication strategy:
        1. UPC (if available) - most reliable cross-service match
        2. Normalized (artist_name::album_title) - fallback
        First-seen wins.
        """
        seen_upcs: set[str] = set()
        seen_keys: set[str] = set()
        deduped: list[AlbumDTO] = []

        for album in albums:
            # Try UPC first
            if album.upc:
                if album.upc in seen_upcs:
                    continue
                seen_upcs.add(album.upc)

            # Fallback to normalized key
            key = self._normalize_album_key(album.artist_name, album.title)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            deduped.append(album)

        return deduped

    def _deduplicate_artists(
        self,
        artists: list[tuple[DiscoveredArtist, str]],
    ) -> list[DiscoveredArtist]:
        """Deduplicate artists by normalized name."""
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
                existing.external_urls.update(artist.external_urls)

        result = list(seen_names.values())
        result.sort(key=lambda a: a.popularity, reverse=True)

        return result

    def _deduplicate_artists_with_scoring(
        self,
        artists: list[tuple[DiscoveredArtist, str]],
    ) -> list[DiscoveredArtist]:
        """Deduplicate artists with frequency scoring.

        Artists recommended by MULTIPLE sources rank higher.
        """
        name_counts: dict[str, int] = {}
        seen_artists: dict[str, DiscoveredArtist] = {}

        for artist, _source in artists:
            key = artist.name.lower().strip()
            name_counts[key] = name_counts.get(key, 0) + 1

            if key not in seen_artists:
                seen_artists[key] = artist
            else:
                existing = seen_artists[key]
                if not existing.spotify_id and artist.spotify_id:
                    existing.spotify_id = artist.spotify_id
                if not existing.deezer_id and artist.deezer_id:
                    existing.deezer_id = artist.deezer_id
                if not existing.image_url and artist.image_url:
                    existing.image_url = artist.image_url
                existing.external_urls.update(artist.external_urls)

        result = list(seen_artists.values())
        result.sort(
            key=lambda a: (name_counts.get(a.name.lower().strip(), 0), a.popularity),
            reverse=True,
        )

        return result

    @staticmethod
    def _normalize_album_key(artist: str, album: str) -> str:
        """Create normalized key for album deduplication."""
        artist_norm = artist.lower().strip()
        album_norm = album.lower().strip()

        # Remove common suffixes that differ between services
        for suffix in [
            "(deluxe)",
            "(deluxe edition)",
            "(expanded edition)",
            "(remastered)",
            "(remaster)",
            "- single",
            "(single)",
            "(ep)",
            "- ep",
        ]:
            album_norm = album_norm.replace(suffix, "").strip()

        return f"{artist_norm}::{album_norm}"


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY - STANDALONE CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

# These aliases allow existing code to continue working


class DiscoverService(BrowseService):
    """Backward compatibility alias for BrowseService.

    ⚠️ DEPRECATED: Use BrowseService instead.
    """

    pass


class NewReleasesService(BrowseService):
    """Backward compatibility alias for BrowseService.

    ⚠️ DEPRECATED: Use BrowseService instead.
    """

    pass


# Export
__all__ = [
    "BrowseService",
    "BrowseResult",
    "DiscoveredArtist",
    # Backward compatibility
    "DiscoverService",
    "DiscoverResult",
    "NewReleasesService",
    "NewReleasesResult",
]
