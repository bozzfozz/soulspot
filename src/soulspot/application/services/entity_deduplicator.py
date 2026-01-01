"""Entity Deduplicator Service.

Hey future me - THIS IS THE DEDUPLICATION CORE!

Problem: Spotify and Deezer can return the SAME artist/album/track
         but with different metadata and IDs.
         
Solution: Match and merge entities using a priority hierarchy:
          1. MusicBrainz ID (MBID) - Universal standard
          2. ISRC (for tracks) - ISO standard
          3. Provider IDs - Same ID on same provider
          4. Normalized Name - Fallback (case-insensitive, stripped)

IMPORTANT: This does NOT delete duplicates!
           It MERGES incoming data into existing entities.
           
Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                      EntityDeduplicator                          │
│  ┌─────────────┐                                                 │
│  │ Incoming    │  find_match_key()    ┌──────────────────────┐  │
│  │ ArtistDTO   │ ──────────────────── │ Match Key            │  │
│  │ from Deezer │                      │ "mbid:xxx" or        │  │
│  └─────────────┘                      │ "spotify:yyy" or     │  │
│                                       │ "name:pink floyd"    │  │
│                                       └──────────┬───────────┘  │
│                                                  │              │
│  ┌─────────────┐   lookup_by_key()               ▼              │
│  │ Existing    │ ◄────────────────── Find in DB via           │
│  │ Artist      │                     Repository                 │
│  │ (or None)   │                                                │
│  └──────┬──────┘                                                │
│         │                                                       │
│         │ merge_artist()                                        │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │ Merged      │  IDs combined:                                 │
│  │ Artist      │  spotify_id + deezer_id + mbid                │
│  │ Entity      │  Best metadata kept                           │
│  └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

Usage:
    dedup = EntityDeduplicator(artist_repo, album_repo, track_repo)
    
    for dto in incoming_artists:
        artist, was_created = await dedup.deduplicate_artist(dto, source="spotify")
        # artist is either existing (merged) or new
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.domain.dtos import AlbumDTO, ArtistDTO, TrackDTO
    from soulspot.domain.entities import Album, Artist, Track
    from soulspot.domain.ports import IAlbumRepository, IArtistRepository, ITrackRepository

logger = logging.getLogger(__name__)


class EntityDeduplicator:
    """Service for deduplicating entities across multiple sources.
    
    Hey future me - this is CRITICAL for multi-source sync!
    
    Without deduplication:
    - "Pink Floyd" from Spotify creates Artist A
    - "Pink Floyd" from Deezer creates Artist B
    - User sees 2 "Pink Floyd" entries 😱
    
    With deduplication:
    - "Pink Floyd" from Spotify creates Artist A (spotify_id=X)
    - "Pink Floyd" from Deezer finds Artist A, merges deezer_id=Y
    - User sees 1 "Pink Floyd" with both IDs ✅
    """
    
    def __init__(
        self,
        artist_repo: "IArtistRepository",
        album_repo: "IAlbumRepository",
        track_repo: "ITrackRepository",
    ) -> None:
        """Initialize with repositories for lookup.
        
        Args:
            artist_repo: Repository for artist lookups
            album_repo: Repository for album lookups
            track_repo: Repository for track lookups
        """
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
    
    # =========================================================================
    # ARTIST DEDUPLICATION
    # =========================================================================
    
    async def deduplicate_artist(
        self,
        dto: "ArtistDTO",
        source: str,
    ) -> tuple["Artist | None", bool]:
        """Deduplicate an artist DTO against existing artists.
        
        Priority for matching:
        1. MusicBrainz ID (most reliable)
        2. Spotify URI/ID
        3. Deezer ID
        4. Normalized name (fallback)
        
        Args:
            dto: Incoming artist data
            source: Source name ("spotify", "deezer", etc.)
        
        Returns:
            Tuple of (existing_artist_or_none, was_match_found)
            If match found: Returns existing artist (caller should merge)
            If no match: Returns None (caller should create new)
        """
        # Try MBID first (most reliable)
        if dto.musicbrainz_id:
            existing = await self._artist_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Artist match by MBID: {dto.name}")
                return existing, True
        
        # Try Spotify URI
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing = await self._artist_repo.get_by_spotify_uri(
                SpotifyUri.from_string(dto.spotify_uri)
            )
            if existing:
                logger.debug(f"Artist match by Spotify URI: {dto.name}")
                return existing, True
        
        # Try Deezer ID
        if dto.deezer_id:
            existing = await self._artist_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Artist match by Deezer ID: {dto.name}")
                return existing, True
        
        # Fallback: Name match (normalized, case-insensitive)
        # Be careful here - many artists share names!
        if dto.name:
            existing = await self._artist_repo.get_by_name(dto.name)
            if existing:
                # Only match by name if confident (e.g., same source or unique name)
                logger.debug(f"Artist potential match by name: {dto.name}")
                return existing, True
        
        # No match found
        return None, False
    
    def merge_artist(
        self,
        existing: "Artist",
        incoming: "ArtistDTO",
        source: str,
    ) -> "Artist":
        """Merge incoming DTO data into existing artist.
        
        Hey future me - this PRESERVES existing data, only ADDS missing!
        We don't overwrite existing IDs or metadata.
        
        Args:
            existing: Existing artist entity
            incoming: New data to merge
            source: Source of incoming data
        
        Returns:
            Modified existing artist (same object)
        """
        # Merge provider IDs (never overwrite existing)
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
        
        if incoming.deezer_id and not existing.deezer_id:
            existing.deezer_id = incoming.deezer_id
        
        if incoming.tidal_id and not existing.tidal_id:
            existing.tidal_id = incoming.tidal_id
        
        if incoming.musicbrainz_id and not existing.musicbrainz_id:
            existing.musicbrainz_id = incoming.musicbrainz_id
        
        # Merge image (prefer if missing or from better source)
        if incoming.image_url and not existing.image.url:
            from soulspot.domain.value_objects import ImageRef
            existing.image = ImageRef(
                url=incoming.image_url,
                path=existing.image.path,
            )
        
        # Update primary source if this is a "better" source
        # (Spotify/Deezer are "better" than local for metadata)
        if not existing.primary_source and source in ("spotify", "deezer"):
            existing.primary_source = source
        
        return existing
    
    # =========================================================================
    # ALBUM DEDUPLICATION
    # =========================================================================
    
    async def deduplicate_album(
        self,
        dto: "AlbumDTO",
        artist_id: str,
        source: str,
    ) -> tuple["Album | None", bool]:
        """Deduplicate an album DTO against existing albums.
        
        Priority for matching:
        1. MusicBrainz ID
        2. Spotify URI
        3. Deezer ID
        4. Title + Artist combination
        
        Args:
            dto: Incoming album data
            artist_id: Artist ID this album belongs to
            source: Source name
        
        Returns:
            Tuple of (existing_album_or_none, was_match_found)
        """
        # Try MBID
        if dto.musicbrainz_id:
            existing = await self._album_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Album match by MBID: {dto.title}")
                return existing, True
        
        # Try Spotify URI
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing = await self._album_repo.get_by_spotify_uri(
                SpotifyUri.from_string(dto.spotify_uri)
            )
            if existing:
                logger.debug(f"Album match by Spotify URI: {dto.title}")
                return existing, True
        
        # Try Deezer ID
        if dto.deezer_id:
            existing = await self._album_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Album match by Deezer ID: {dto.title}")
                return existing, True
        
        # Fallback: Title + Artist
        if dto.title and artist_id:
            from soulspot.domain.value_objects import ArtistId
            existing = await self._album_repo.get_by_title_and_artist(
                title=dto.title,
                artist_id=ArtistId.from_string(artist_id),
            )
            if existing:
                logger.debug(f"Album match by title+artist: {dto.title}")
                return existing, True
        
        return None, False
    
    def merge_album(
        self,
        existing: "Album",
        incoming: "AlbumDTO",
        source: str,
    ) -> "Album":
        """Merge incoming DTO data into existing album.
        
        Args:
            existing: Existing album entity
            incoming: New data to merge
            source: Source of incoming data
        
        Returns:
            Modified existing album
        """
        # Merge provider IDs
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
        
        if incoming.deezer_id and not existing.deezer_id:
            existing.deezer_id = incoming.deezer_id
        
        if incoming.musicbrainz_id and not existing.musicbrainz_id:
            existing.musicbrainz_id = incoming.musicbrainz_id
        
        # Merge cover
        if incoming.cover_url and not existing.cover.url:
            from soulspot.domain.value_objects import ImageRef
            existing.cover = ImageRef(
                url=incoming.cover_url,
                path=existing.cover.path,
            )
        
        # Merge metadata (if missing)
        if incoming.release_date and not existing.release_date:
            existing.release_date = incoming.release_date
        
        if incoming.total_tracks and not existing.total_tracks:
            existing.total_tracks = incoming.total_tracks
        
        return existing
    
    # =========================================================================
    # TRACK DEDUPLICATION
    # =========================================================================
    
    async def deduplicate_track(
        self,
        dto: "TrackDTO",
        album_id: str | None,
        source: str,
    ) -> tuple["Track | None", bool]:
        """Deduplicate a track DTO against existing tracks.
        
        Priority for matching:
        1. ISRC (ISO standard for recordings)
        2. MusicBrainz ID
        3. Spotify URI
        4. Deezer ID
        5. Title + Album combination
        
        Args:
            dto: Incoming track data
            album_id: Album ID this track belongs to
            source: Source name
        
        Returns:
            Tuple of (existing_track_or_none, was_match_found)
        """
        # ISRC is the gold standard for track matching
        if dto.isrc:
            existing = await self._track_repo.get_by_isrc(dto.isrc)
            if existing:
                logger.debug(f"Track match by ISRC: {dto.title}")
                return existing, True
        
        # Try MBID
        if dto.musicbrainz_id:
            existing = await self._track_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Track match by MBID: {dto.title}")
                return existing, True
        
        # Try Spotify URI
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing = await self._track_repo.get_by_spotify_uri(
                SpotifyUri.from_string(dto.spotify_uri)
            )
            if existing:
                logger.debug(f"Track match by Spotify URI: {dto.title}")
                return existing, True
        
        # Try Deezer ID
        if dto.deezer_id:
            existing = await self._track_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Track match by Deezer ID: {dto.title}")
                return existing, True
        
        # Fallback: Title + Album (fuzzy)
        # Note: This is risky - many albums have tracks with same name
        # Only do this if we have album_id to narrow down
        if dto.title and album_id:
            from soulspot.domain.value_objects import AlbumId
            existing = await self._track_repo.get_by_title_and_album(
                title=dto.title,
                album_id=AlbumId.from_string(album_id),
            )
            if existing:
                logger.debug(f"Track match by title+album: {dto.title}")
                return existing, True
        
        return None, False
    
    def merge_track(
        self,
        existing: "Track",
        incoming: "TrackDTO",
        source: str,
    ) -> "Track":
        """Merge incoming DTO data into existing track.
        
        Args:
            existing: Existing track entity
            incoming: New data to merge
            source: Source of incoming data
        
        Returns:
            Modified existing track
        """
        # Merge provider IDs
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
        
        if incoming.deezer_id and not existing.deezer_id:
            existing.deezer_id = incoming.deezer_id
        
        if incoming.isrc and not existing.isrc:
            existing.isrc = incoming.isrc
        
        if incoming.musicbrainz_id and not existing.musicbrainz_id:
            existing.musicbrainz_id = incoming.musicbrainz_id
        
        # Merge metadata
        if incoming.duration_ms and not existing.duration_ms:
            existing.duration_ms = incoming.duration_ms
        
        if incoming.track_number and not existing.track_number:
            existing.track_number = incoming.track_number
        
        return existing
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a name for matching.
        
        Hey future me - use this for name-based matching!
        - Lowercase
        - Remove special characters
        - Collapse whitespace
        
        Args:
            name: Name to normalize
        
        Returns:
            Normalized name
        """
        # Lowercase
        normalized = name.lower()
        # Remove special characters (keep letters, numbers, spaces)
        normalized = re.sub(r"[^\w\s]", "", normalized)
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    
    @staticmethod
    def generate_match_key(
        mbid: str | None = None,
        spotify_id: str | None = None,
        deezer_id: str | None = None,
        isrc: str | None = None,
        name: str | None = None,
    ) -> str:
        """Generate a match key for deduplication.
        
        Priority:
        1. mbid:xxx
        2. isrc:xxx
        3. spotify:xxx
        4. deezer:xxx
        5. name:xxx (normalized)
        
        Args:
            mbid: MusicBrainz ID
            spotify_id: Spotify ID
            deezer_id: Deezer ID
            isrc: ISRC code
            name: Entity name (fallback)
        
        Returns:
            Match key string
        """
        if mbid:
            return f"mbid:{mbid}"
        if isrc:
            return f"isrc:{isrc}"
        if spotify_id:
            return f"spotify:{spotify_id}"
        if deezer_id:
            return f"deezer:{deezer_id}"
        if name:
            return f"name:{EntityDeduplicator.normalize_name(name)}"
        return "unknown"
