"""
Universal ID Enrichment Service - Cross-Provider ID Discovery.

Hey future me - DIES IST DAS ZENTRALE ID-ANREICHERUNGS-SYSTEM!

Das Problem: Lokale Imports haben KEINE Provider-IDs (deezer_id, spotify_uri, etc.)
Die Lösung: Name-basierte Suche bei ALLEN verfügbaren Providern

Flow:
1. Find entities missing IDs (Artist ohne deezer_id, Album ohne spotify_uri, etc.)
2. Search by NAME at each provider: Deezer (no auth!), Spotify (if auth), etc.
3. Match results by name similarity + optional secondary criteria
4. Store ALL found IDs for future direct lookups

Benefits:
- Entities get ALL available IDs over time
- Future lookups use fast direct ID queries
- Works incrementally - each sync adds more IDs
- Graceful degradation - missing auth just skips that provider

Pattern: Entity has ID? → Direct lookup | No ID? → Name search → Store found ID

Auth Requirements:
- Deezer: NO AUTH NEEDED! Search/lookup are PUBLIC API 🎉
- Spotify: REQUIRES OAuth for ALL operations (including search)

We use can_use(PluginCapability) to check if a provider can handle a specific
operation. This is cleaner than checking is_authenticated directly.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from soulspot.domain.ports.plugin import PluginCapability

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.domain.entities import Album, Artist, Track
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


# Hey future me - EnrichmentResult trackt was gefunden/updated wurde
@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""
    
    entity_type: str  # "artist", "album", "track"
    entity_name: str
    
    # Provider IDs that were found and added
    deezer_id_found: bool = False
    spotify_id_found: bool = False
    musicbrainz_id_found: bool = False
    tidal_id_found: bool = False
    
    # Additional data enriched
    image_url_found: bool = False
    cover_url_found: bool = False
    isrc_found: bool = False
    
    # Errors encountered
    errors: list[str] = field(default_factory=list)


# Hey future me - BatchEnrichmentStats für Logging und Monitoring
@dataclass
class BatchEnrichmentStats:
    """Statistics for a batch enrichment run."""
    
    artists_processed: int = 0
    artists_enriched: int = 0
    albums_processed: int = 0
    albums_enriched: int = 0
    tracks_processed: int = 0
    tracks_enriched: int = 0
    
    # Per-provider stats
    deezer_lookups: int = 0
    deezer_matches: int = 0
    spotify_lookups: int = 0
    spotify_matches: int = 0
    
    errors: list[str] = field(default_factory=list)


class UniversalIdEnrichmentService:
    """
    Service for enriching entities with provider IDs via name-based search.
    
    Hey future me - THIS IS THE UNIFIED APPROACH!
    
    Statt in jedem Worker separat Name-Search zu implementieren,
    zentralisieren wir es hier. Jeder Worker ruft einfach:
    
        await enrichment_service.enrich_artist(artist)
        await enrichment_service.enrich_album(album)
        await enrichment_service.enrich_track(track)
    
    Oder für Batch-Verarbeitung:
    
        await enrichment_service.enrich_artists_missing_ids(batch_size=50)
        await enrichment_service.enrich_albums_missing_ids(batch_size=50)
    """
    
    def __init__(
        self,
        session: "AsyncSession",
        deezer_plugin: "DeezerPlugin | None" = None,
        spotify_plugin: "SpotifyPlugin | None" = None,
    ):
        """
        Initialize enrichment service.
        
        Hey future me - Plugins sind optional! Service funktioniert auch
        wenn nur Deezer verfügbar ist (no auth needed for Deezer!).
        
        Args:
            session: Database session for updates
            deezer_plugin: Deezer API client (no auth required!)
            spotify_plugin: Spotify API client (requires OAuth)
        """
        self._session = session
        self._deezer = deezer_plugin
        self._spotify = spotify_plugin
        
        # Rate limiting
        self._request_delay = 0.2  # 200ms between requests
    
    # ========================================================================
    # ARTIST ENRICHMENT
    # ========================================================================
    
    async def enrich_artist(self, artist: "Artist") -> EnrichmentResult:
        """
        Enrich a single artist with provider IDs.
        
        Hey future me - Das ist der UNIFIED PATTERN für Artist-Enrichment:
        
        1. Check existing IDs
        2. For each MISSING ID, search by name at that provider
        3. Match by name similarity (fuzzy match)
        4. Store found ID for future direct lookups
        
        Args:
            artist: Artist entity to enrich
            
        Returns:
            EnrichmentResult with details of what was found/updated
        """
        result = EnrichmentResult(entity_type="artist", entity_name=artist.name)
        
        # Deezer enrichment - SEARCH_ARTISTS requires NO auth! 🎉
        if not artist.deezer_id and self._deezer:
            if self._deezer.can_use(PluginCapability.SEARCH_ARTISTS):
                try:
                    found_id, image_url = await self._search_artist_on_deezer(artist.name)
                    if found_id:
                        artist.deezer_id = found_id
                        result.deezer_id_found = True
                        logger.debug(f"Found Deezer ID for artist '{artist.name}': {found_id}")
                        
                        # Bonus: Also get image if missing
                        if image_url and (not artist.image or not artist.image.url):
                            from soulspot.domain.value_objects import ImageRef
                            artist.image = ImageRef(
                                url=image_url,
                                path=artist.image.path if artist.image else None,
                            )
                            result.image_url_found = True
                            
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Deezer search failed: {e}")
                    logger.debug(f"Deezer artist search failed for '{artist.name}': {e}")
        
        # Spotify enrichment - SEARCH_ARTISTS requires OAuth
        if not artist.spotify_uri and self._spotify:
            if self._spotify.can_use(PluginCapability.SEARCH_ARTISTS):
                try:
                    found_uri, image_url = await self._search_artist_on_spotify(artist.name)
                    if found_uri:
                        from soulspot.domain.value_objects import SpotifyUri
                        artist.spotify_uri = SpotifyUri.from_string(found_uri)
                        result.spotify_id_found = True
                        logger.debug(f"Found Spotify URI for artist '{artist.name}': {found_uri}")
                        
                        # Bonus: Also get image if missing and Deezer didn't find one
                        if image_url and (not artist.image or not artist.image.url):
                            from soulspot.domain.value_objects import ImageRef
                            artist.image = ImageRef(
                                url=image_url,
                                path=artist.image.path if artist.image else None,
                            )
                            result.image_url_found = True
                            
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Spotify search failed: {e}")
                    logger.debug(f"Spotify artist search failed for '{artist.name}': {e}")
        
        return result
    
    async def _search_artist_on_deezer(self, name: str) -> tuple[str | None, str | None]:
        """
        Search for artist on Deezer by name.
        
        Returns:
            Tuple of (deezer_id, image_url) if found, else (None, None)
        """
        if not self._deezer:
            return None, None
            
        try:
            results = await self._deezer.search_artists(name, limit=1)
            if results and results.items:
                best_match = results.items[0]
                # Basic name match (could add fuzzy matching later)
                if self._names_match(name, best_match.name):
                    return best_match.deezer_id, best_match.image.url if best_match.image else None
        except Exception as e:
            logger.debug(f"Deezer artist search error: {e}")
        
        return None, None
    
    async def _search_artist_on_spotify(self, name: str) -> tuple[str | None, str | None]:
        """
        Search for artist on Spotify by name.
        
        Hey future me - SpotifyPlugin hat keine search_artists() Convenience-Methode!
        Wir nutzen die generische search() Methode mit types=["artist"].
        
        IMPORTANT: Caller should check can_use(SEARCH_ARTISTS) before calling!
        
        Returns:
            Tuple of (spotify_uri, image_url) if found, else (None, None)
        """
        if not self._spotify:
            return None, None
            
        try:
            # Use generic search with types filter
            results = await self._spotify.search(name, types=["artist"], limit=1)
            if results and results.artists:
                best_match = results.artists[0]
                if self._names_match(name, best_match.name):
                    return best_match.spotify_uri, best_match.image.url if best_match.image else None
        except Exception as e:
            logger.debug(f"Spotify artist search error: {e}")
        
        return None, None
    
    # ========================================================================
    # ALBUM ENRICHMENT
    # ========================================================================
    
    async def enrich_album(
        self, album: "Album", artist_name: str | None = None
    ) -> EnrichmentResult:
        """
        Enrich a single album with provider IDs.
        
        Args:
            album: Album entity to enrich
            artist_name: Artist name for better search results
            
        Returns:
            EnrichmentResult with details of what was found/updated
        """
        result = EnrichmentResult(entity_type="album", entity_name=album.title)
        
        # Build search query
        search_query = album.title
        if artist_name:
            search_query = f"{artist_name} {album.title}"
        
        # Deezer enrichment - SEARCH_ALBUMS requires NO auth! 🎉
        if not album.deezer_id and self._deezer:
            if self._deezer.can_use(PluginCapability.SEARCH_ALBUMS):
                try:
                    found_id, cover_url = await self._search_album_on_deezer(search_query)
                    if found_id:
                        album.deezer_id = found_id
                        result.deezer_id_found = True
                        logger.debug(f"Found Deezer ID for album '{album.title}': {found_id}")
                        
                        # Bonus: Also get cover if missing
                        if cover_url and (not album.cover or not album.cover.url):
                            from soulspot.domain.value_objects import ImageRef
                            album.cover = ImageRef(
                                url=cover_url,
                                path=album.cover.path if album.cover else None,
                            )
                            result.cover_url_found = True
                            
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Deezer search failed: {e}")
        
        # Spotify enrichment - SEARCH_ALBUMS requires OAuth
        if not album.spotify_uri and self._spotify:
            if self._spotify.can_use(PluginCapability.SEARCH_ALBUMS):
                try:
                    found_uri, cover_url = await self._search_album_on_spotify(search_query)
                    if found_uri:
                        from soulspot.domain.value_objects import SpotifyUri
                        album.spotify_uri = SpotifyUri.from_string(found_uri)
                        result.spotify_id_found = True
                        logger.debug(f"Found Spotify URI for album '{album.title}': {found_uri}")
                        
                        if cover_url and (not album.cover or not album.cover.url):
                            from soulspot.domain.value_objects import ImageRef
                            album.cover = ImageRef(
                                url=cover_url,
                                path=album.cover.path if album.cover else None,
                            )
                            result.cover_url_found = True
                            
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Spotify search failed: {e}")
        
        return result
    
    async def _search_album_on_deezer(self, query: str) -> tuple[str | None, str | None]:
        """Search for album on Deezer."""
        if not self._deezer:
            return None, None
            
        try:
            results = await self._deezer.search_albums(query, limit=1)
            if results and results.items:
                best_match = results.items[0]
                return best_match.deezer_id, best_match.cover.url if best_match.cover else None
        except Exception as e:
            logger.debug(f"Deezer album search error: {e}")
        
        return None, None
    
    async def _search_album_on_spotify(self, query: str) -> tuple[str | None, str | None]:
        """Search for album on Spotify.
        
        Hey future me - SpotifyPlugin hat keine search_albums() Convenience-Methode!
        Wir nutzen die generische search() Methode mit types=["album"].
        
        IMPORTANT: Caller should check can_use(SEARCH_ALBUMS) before calling!
        """
        if not self._spotify:
            return None, None
            
        try:
            # Use generic search with types filter
            results = await self._spotify.search(query, types=["album"], limit=1)
            if results and results.albums:
                best_match = results.albums[0]
                return best_match.spotify_uri, best_match.cover.url if best_match.cover else None
        except Exception as e:
            logger.debug(f"Spotify album search error: {e}")
        
        return None, None
    
    # ========================================================================
    # TRACK ENRICHMENT
    # ========================================================================
    
    async def enrich_track(
        self, track: "Track", artist_name: str | None = None
    ) -> EnrichmentResult:
        """
        Enrich a single track with provider IDs.
        
        Hey future me - Tracks sind BESONDERS wichtig weil ISRC universal ist!
        Wenn wir ISRC haben, können wir direkt auf allen Services suchen.
        
        Args:
            track: Track entity to enrich
            artist_name: Artist name for better search
            
        Returns:
            EnrichmentResult with details of what was found/updated
        """
        result = EnrichmentResult(entity_type="track", entity_name=track.title)
        
        # Build search query
        search_query = track.title
        if artist_name:
            search_query = f"{artist_name} {track.title}"
        
        # Deezer enrichment - SEARCH_TRACKS requires NO auth! 🎉
        if not track.deezer_id and self._deezer:
            if self._deezer.can_use(PluginCapability.SEARCH_TRACKS):
                try:
                    found_id, isrc = await self._search_track_on_deezer(
                        search_query, existing_isrc=track.isrc
                    )
                    if found_id:
                        track.deezer_id = found_id
                        result.deezer_id_found = True
                        logger.debug(f"Found Deezer ID for track '{track.title}': {found_id}")
                    
                        # Bonus: Also get ISRC if missing
                        if isrc and not track.isrc:
                            track.isrc = isrc
                            result.isrc_found = True
                        
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Deezer search failed: {e}")
        
        # Spotify enrichment - SEARCH_TRACKS requires OAuth
        if not track.spotify_uri and self._spotify:
            if self._spotify.can_use(PluginCapability.SEARCH_TRACKS):
                try:
                    found_uri, isrc = await self._search_track_on_spotify(
                        search_query, existing_isrc=track.isrc
                    )
                    if found_uri:
                        from soulspot.domain.value_objects import SpotifyUri
                        track.spotify_uri = SpotifyUri.from_string(found_uri)
                        result.spotify_id_found = True
                        logger.debug(f"Found Spotify URI for track '{track.title}': {found_uri}")
                        
                        if isrc and not track.isrc:
                            track.isrc = isrc
                            result.isrc_found = True
                        
                    await asyncio.sleep(self._request_delay)
                except Exception as e:
                    result.errors.append(f"Spotify search failed: {e}")
        
        return result
    
    async def _search_track_on_deezer(
        self, query: str, existing_isrc: str | None = None
    ) -> tuple[str | None, str | None]:
        """Search for track on Deezer.
        
        IMPORTANT: Caller should check can_use(SEARCH_TRACKS) before calling!
        """
        if not self._deezer:
            return None, None
            
        try:
            # If we have ISRC, try direct lookup first (more accurate)
            if existing_isrc:
                track = await self._deezer.get_track_by_isrc(existing_isrc)
                if track:
                    return track.deezer_id, track.isrc
            
            # Fallback to name search
            results = await self._deezer.search_tracks(query, limit=1)
            if results and results.items:
                best_match = results.items[0]
                return best_match.deezer_id, best_match.isrc
        except Exception as e:
            logger.debug(f"Deezer track search error: {e}")
        
        return None, None
    
    async def _search_track_on_spotify(
        self, query: str, existing_isrc: str | None = None
    ) -> tuple[str | None, str | None]:
        """Search for track on Spotify.
        
        Hey future me - SpotifyPlugin hat keine search_tracks() Convenience-Methode!
        Wir nutzen die generische search() Methode mit types=["track"].
        ISRC lookup wäre besser, aber Spotify API macht das kompliziert.
        
        IMPORTANT: Caller should check can_use(SEARCH_TRACKS) before calling!
        """
        if not self._spotify:
            return None, None
            
        try:
            # If we have ISRC, try isrc:XXXX search syntax
            search_query = f"isrc:{existing_isrc}" if existing_isrc else query
            
            # Use generic search with types filter
            results = await self._spotify.search(search_query, types=["track"], limit=1)
            if results and results.tracks:
                best_match = results.tracks[0]
                return best_match.spotify_uri, best_match.isrc
        except Exception as e:
            logger.debug(f"Spotify track search error: {e}")
        
        return None, None
    
    # ========================================================================
    # BATCH ENRICHMENT
    # ========================================================================
    
    async def enrich_entities_missing_ids(
        self, batch_size: int = 50
    ) -> BatchEnrichmentStats:
        """
        Batch enrich all entities missing provider IDs.
        
        Hey future me - DIES IST DER BATCH JOB für UnifiedLibraryWorker!
        
        Ruft alle drei enrich-Methoden auf:
        1. Artists ohne deezer_id/spotify_uri
        2. Albums ohne deezer_id/spotify_uri  
        3. Tracks ohne deezer_id/spotify_uri
        
        Args:
            batch_size: Number of entities to process per type
            
        Returns:
            BatchEnrichmentStats with processing stats
        """
        from soulspot.infrastructure.persistence.repositories import (
            AlbumRepository,
            ArtistRepository,
            TrackRepository,
        )
        
        stats = BatchEnrichmentStats()
        
        artist_repo = ArtistRepository(self._session)
        album_repo = AlbumRepository(self._session)
        track_repo = TrackRepository(self._session)
        
        # Enrich artists
        try:
            artists = await artist_repo.get_artists_missing_provider_ids(limit=batch_size)
            for artist in artists:
                stats.artists_processed += 1
                result = await self.enrich_artist(artist)
                if result.deezer_id_found or result.spotify_id_found:
                    stats.artists_enriched += 1
                    await artist_repo.update(artist)
                    
                if result.deezer_id_found:
                    stats.deezer_matches += 1
                if result.spotify_id_found:
                    stats.spotify_matches += 1
                    
            await self._session.commit()
        except Exception as e:
            stats.errors.append(f"Artist enrichment failed: {e}")
            logger.warning(f"Batch artist enrichment failed: {e}")
        
        # Enrich albums (with artist names for better search)
        try:
            albums = await album_repo.get_albums_missing_provider_ids(limit=batch_size)
            
            # Pre-fetch artist names
            artist_names: dict[str, str] = {}
            unique_artist_ids = {album.artist_id for album in albums}
            for aid in unique_artist_ids:
                try:
                    artist = await artist_repo.get_by_id(aid)
                    if artist:
                        artist_names[str(aid)] = artist.name
                except Exception:
                    pass
            
            for album in albums:
                stats.albums_processed += 1
                artist_name = artist_names.get(str(album.artist_id))
                result = await self.enrich_album(album, artist_name=artist_name)
                if result.deezer_id_found or result.spotify_id_found:
                    stats.albums_enriched += 1
                    await album_repo.update(album)
                    
                if result.deezer_id_found:
                    stats.deezer_matches += 1
                if result.spotify_id_found:
                    stats.spotify_matches += 1
                    
            await self._session.commit()
        except Exception as e:
            stats.errors.append(f"Album enrichment failed: {e}")
            logger.warning(f"Batch album enrichment failed: {e}")
        
        # Enrich tracks (with artist names for better search)
        try:
            tracks = await track_repo.get_tracks_missing_provider_ids(limit=batch_size)
            
            # Pre-fetch artist names
            artist_names = {}
            unique_artist_ids = {track.artist_id for track in tracks}
            for aid in unique_artist_ids:
                try:
                    artist = await artist_repo.get_by_id(aid)
                    if artist:
                        artist_names[str(aid)] = artist.name
                except Exception:
                    pass
            
            for track in tracks:
                stats.tracks_processed += 1
                artist_name = artist_names.get(str(track.artist_id))
                result = await self.enrich_track(track, artist_name=artist_name)
                if result.deezer_id_found or result.spotify_id_found:
                    stats.tracks_enriched += 1
                    await track_repo.update(track)
                    
                if result.deezer_id_found:
                    stats.deezer_matches += 1
                if result.spotify_id_found:
                    stats.spotify_matches += 1
                    
            await self._session.commit()
        except Exception as e:
            stats.errors.append(f"Track enrichment failed: {e}")
            logger.warning(f"Batch track enrichment failed: {e}")
        
        logger.info(
            f"🔗 ID Enrichment: "
            f"Artists: {stats.artists_enriched}/{stats.artists_processed}, "
            f"Albums: {stats.albums_enriched}/{stats.albums_processed}, "
            f"Tracks: {stats.tracks_enriched}/{stats.tracks_processed} "
            f"(Deezer: {stats.deezer_matches}, Spotify: {stats.spotify_matches})"
        )
        
        return stats
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Check if two names match (basic normalization).
        
        Hey future me - könnte später mit fuzzy matching erweitert werden!
        z.B. "The Beatles" matches "Beatles", "AC/DC" matches "ACDC" etc.
        """
        # Basic normalization: lowercase, strip whitespace
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Direct match
        if n1 == n2:
            return True
        
        # Remove common prefixes
        prefixes = ["the ", "a ", "an "]
        for prefix in prefixes:
            if n1.startswith(prefix):
                n1 = n1[len(prefix):]
            if n2.startswith(prefix):
                n2 = n2[len(prefix):]
        
        return n1 == n2
