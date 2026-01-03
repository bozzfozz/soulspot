# AI-Model: Copilot
"""Deduplication Checker - Import-Zeit Entity Matching.

Hey future me - dies ist der SCHNELLE Teil der Deduplizierung!

TIMING: Synchron, <50ms Latenz. Wird bei jedem Import aufgerufen.
Darf NICHT langsam sein - kein Batch-Processing, kein Full-Table-Scan!

VERANTWORTUNG:
- Entity-Matching beim Import (Artist, Album, Track)
- DTO-in-Entity Merging (Provider-IDs kombinieren)
- Match-Key Generation für schnelle Lookups

NICHT HIER (→ deduplication_housekeeping.py):
- Scheduled Cleanup Jobs
- Full-Library Duplicate Scan
- User-getriggerte Merge-Operationen
- Track-Datei Löschung

MATCHING PRIORITY:
1. MusicBrainz ID (MBID) - Universal Standard ✅
2. ISRC (für Tracks) - ISO Standard
3. Provider IDs (Spotify URI, Deezer ID)
4. Normalized Name (Fallback - Case-Insensitive)

MERGED AUS (Jan 2025):
- entity_deduplicator.py (494 LOC) - Komplette Migration

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                     DeduplicationChecker                         │
│  ┌─────────────┐                                                 │
│  │ Incoming    │  find_existing()     ┌──────────────────────┐  │
│  │ ArtistDTO   │ ──────────────────── │ Match Strategy       │  │
│  │ from Deezer │                      │ MBID → Spotify →     │  │
│  └─────────────┘                      │ Deezer → Name        │  │
│                                       └──────────┬───────────┘  │
│                                                  │              │
│  ┌─────────────┐   Repository Lookup             ▼              │
│  │ Existing    │ ◄────────────────── Fast lookup via           │
│  │ Artist      │                     indexed columns            │
│  │ (or None)   │                                                │
│  └──────┬──────┘                                                │
│         │                                                       │
│         │ merge_into_existing()                                 │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │ Merged      │  IDs combined:                                 │
│  │ Artist      │  spotify_id + deezer_id + mbid                │
│  │ Entity      │  Best metadata kept                           │
│  └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

Usage:
```python
checker = DeduplicationChecker(artist_repo, album_repo, track_repo)

# Bei Artist-Import
existing, was_found = await checker.find_existing_artist(dto)
if was_found:
    checker.merge_artist_dto(existing, dto, source="deezer")
else:
    # Create new artist
    artist = Artist.from_dto(dto)
```
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


class DeduplicationChecker:
    """Fast entity deduplication for import-time matching.
    
    Hey future me - this is CRITICAL for multi-source sync!
    Timing requirement: <50ms per lookup.
    
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
        """Initialize with repositories for fast lookups.
        
        Hey future me - repositories should have indexes on:
        - musicbrainz_id
        - spotify_uri
        - deezer_id
        - LOWER(name) for artists
        - isrc for tracks
        
        Args:
            artist_repo: Repository for artist lookups
            album_repo: Repository for album lookups
            track_repo: Repository for track lookups
        """
        self._artist_repo = artist_repo
        self._album_repo = album_repo
        self._track_repo = track_repo
    
    # =========================================================================
    # === ARTIST DEDUPLICATION ===
    # =========================================================================
    
    async def find_existing_artist(
        self,
        dto: "ArtistDTO",
    ) -> tuple["Artist | None", bool]:
        """Find existing artist matching the incoming DTO.
        
        Hey future me - Matching priority:
        1. MusicBrainz ID (most reliable, universal standard)
        2. Spotify URI (provider-specific but stable)
        3. Deezer ID (provider-specific but stable)
        4. Normalized name (fallback - risky for common names!)
        
        Args:
            dto: Incoming artist data from provider
        
        Returns:
            Tuple of (existing_artist_or_none, was_match_found)
            If match found: Returns existing artist (caller should merge)
            If no match: Returns None (caller should create new)
        """
        # 1. Try MusicBrainz ID (gold standard)
        if dto.musicbrainz_id:
            existing = await self._artist_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Artist match by MBID: {dto.name}")
                return existing, True
        
        # 2. Try Spotify URI (stable provider ID)
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing = await self._artist_repo.get_by_spotify_uri(
                    SpotifyUri.from_string(dto.spotify_uri)
                )
                if existing:
                    logger.debug(f"Artist match by Spotify URI: {dto.name}")
                    return existing, True
            except ValueError:
                # Invalid Spotify URI format
                pass
        
        # 3. Try Deezer ID (stable provider ID)
        if dto.deezer_id:
            existing = await self._artist_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Artist match by Deezer ID: {dto.name}")
                return existing, True
        
        # 4. Fallback: Name match (normalized, case-insensitive)
        # CAUTION: Many artists share names - be careful!
        if dto.name:
            existing = await self._artist_repo.get_by_name(dto.name)
            if existing:
                logger.debug(f"Artist potential match by name: {dto.name}")
                return existing, True
        
        # No match found
        return None, False
    
    def merge_artist_dto(
        self,
        existing: "Artist",
        incoming: "ArtistDTO",
        source: str,
    ) -> "Artist":
        """Merge incoming DTO data into existing artist entity.
        
        Hey future me - this PRESERVES existing data, only ADDS missing!
        We never overwrite existing IDs or metadata - only fill gaps.
        
        Merge rules:
        - Provider IDs: Add if missing, never overwrite
        - Image: Add if missing OR from "better" source
        - Metadata: Add if missing
        
        Args:
            existing: Existing artist entity to update
            incoming: New data from provider
            source: Source name ("spotify", "deezer", "musicbrainz")
        
        Returns:
            Modified existing artist (same object, mutated)
        """
        # Merge provider IDs (never overwrite existing!)
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
            except ValueError:
                pass  # Invalid URI, skip
        
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
        
        # Update primary_source if this is a "better" source
        # (Provider data is "better" than local for metadata)
        if not existing.primary_source and source in ("spotify", "deezer", "musicbrainz"):
            existing.primary_source = source
        
        # Merge genres if we have them and existing is empty
        if incoming.genres and not existing.genres:
            existing.genres = incoming.genres
        
        return existing
    
    # =========================================================================
    # === ALBUM DEDUPLICATION ===
    # =========================================================================
    
    async def find_existing_album(
        self,
        dto: "AlbumDTO",
        artist_id: str,
    ) -> tuple["Album | None", bool]:
        """Find existing album matching the incoming DTO.
        
        Hey future me - Matching priority:
        1. MusicBrainz Release Group ID
        2. Spotify URI
        3. Deezer ID
        4. Title + Artist combination (fuzzy fallback)
        
        Args:
            dto: Incoming album data from provider
            artist_id: Artist ID this album belongs to
        
        Returns:
            Tuple of (existing_album_or_none, was_match_found)
        """
        # 1. Try MusicBrainz ID
        if dto.musicbrainz_id:
            existing = await self._album_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Album match by MBID: {dto.title}")
                return existing, True
        
        # 2. Try Spotify URI
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing = await self._album_repo.get_by_spotify_uri(
                    SpotifyUri.from_string(dto.spotify_uri)
                )
                if existing:
                    logger.debug(f"Album match by Spotify URI: {dto.title}")
                    return existing, True
            except ValueError:
                pass
        
        # 3. Try Deezer ID
        if dto.deezer_id:
            existing = await self._album_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Album match by Deezer ID: {dto.title}")
                return existing, True
        
        # 4. Fallback: Title + Artist
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
    
    def merge_album_dto(
        self,
        existing: "Album",
        incoming: "AlbumDTO",
        source: str,
    ) -> "Album":
        """Merge incoming DTO data into existing album entity.
        
        Args:
            existing: Existing album entity to update
            incoming: New data from provider
            source: Source name
        
        Returns:
            Modified existing album (same object, mutated)
        """
        # Merge provider IDs
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
            except ValueError:
                pass
        
        if incoming.deezer_id and not existing.deezer_id:
            existing.deezer_id = incoming.deezer_id
        
        if incoming.musicbrainz_id and not existing.musicbrainz_id:
            existing.musicbrainz_id = incoming.musicbrainz_id
        
        # Merge cover image
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
        
        if incoming.label and not existing.label:
            existing.label = incoming.label
        
        return existing
    
    # =========================================================================
    # === TRACK DEDUPLICATION ===
    # =========================================================================
    
    async def find_existing_track(
        self,
        dto: "TrackDTO",
        album_id: str | None,
    ) -> tuple["Track | None", bool]:
        """Find existing track matching the incoming DTO.
        
        Hey future me - Matching priority:
        1. ISRC (ISO standard for recordings - BEST!)
        2. MusicBrainz Recording ID
        3. Spotify URI
        4. Deezer ID
        5. Title + Album combination (risky fallback)
        
        Args:
            dto: Incoming track data from provider
            album_id: Album ID this track belongs to (can be None for singles)
        
        Returns:
            Tuple of (existing_track_or_none, was_match_found)
        """
        # 1. ISRC is the gold standard for track matching
        if dto.isrc:
            existing = await self._track_repo.get_by_isrc(dto.isrc)
            if existing:
                logger.debug(f"Track match by ISRC: {dto.title}")
                return existing, True
        
        # 2. Try MusicBrainz Recording ID
        if dto.musicbrainz_id:
            existing = await self._track_repo.get_by_musicbrainz_id(dto.musicbrainz_id)
            if existing:
                logger.debug(f"Track match by MBID: {dto.title}")
                return existing, True
        
        # 3. Try Spotify URI
        if dto.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing = await self._track_repo.get_by_spotify_uri(
                    SpotifyUri.from_string(dto.spotify_uri)
                )
                if existing:
                    logger.debug(f"Track match by Spotify URI: {dto.title}")
                    return existing, True
            except ValueError:
                pass
        
        # 4. Try Deezer ID
        if dto.deezer_id:
            existing = await self._track_repo.get_by_deezer_id(dto.deezer_id)
            if existing:
                logger.debug(f"Track match by Deezer ID: {dto.title}")
                return existing, True
        
        # 5. Fallback: Title + Album (RISKY - many albums have same track names!)
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
    
    def merge_track_dto(
        self,
        existing: "Track",
        incoming: "TrackDTO",
        source: str,
    ) -> "Track":
        """Merge incoming DTO data into existing track entity.
        
        Args:
            existing: Existing track entity to update
            incoming: New data from provider
            source: Source name
        
        Returns:
            Modified existing track (same object, mutated)
        """
        # Merge provider IDs
        if incoming.spotify_uri and not existing.spotify_uri:
            from soulspot.domain.value_objects import SpotifyUri
            try:
                existing.spotify_uri = SpotifyUri.from_string(incoming.spotify_uri)
            except ValueError:
                pass
        
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
        
        if incoming.disc_number and not existing.disc_number:
            existing.disc_number = incoming.disc_number
        
        return existing
    
    # =========================================================================
    # === UTILITY METHODS ===
    # =========================================================================
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a name for matching.
        
        Hey future me - use this for name-based matching!
        - Lowercase
        - Remove special characters (keep letters, numbers, spaces)
        - Collapse whitespace
        - Strip leading/trailing
        
        This is a SIMPLE normalizer. For artist names with prefixes
        (DJ, The, MC), use normalize_artist_name() from value_objects.
        
        Args:
            name: Name to normalize
        
        Returns:
            Normalized name (lowercase, cleaned)
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
        
        Hey future me - use this for building dedup caches!
        
        Priority order:
        1. mbid:xxx (most reliable)
        2. isrc:xxx (for tracks)
        3. spotify:xxx
        4. deezer:xxx
        5. name:xxx (normalized, fallback)
        
        Args:
            mbid: MusicBrainz ID
            spotify_id: Spotify ID (not full URI!)
            deezer_id: Deezer ID
            isrc: ISRC code (for tracks)
            name: Entity name (fallback)
        
        Returns:
            Match key string like "mbid:abc123" or "name:pink floyd"
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
            return f"name:{DeduplicationChecker.normalize_name(name)}"
        return "unknown"
    
    @staticmethod
    def extract_spotify_id(spotify_uri: str | None) -> str | None:
        """Extract Spotify ID from URI.
        
        Args:
            spotify_uri: Full Spotify URI like "spotify:artist:abc123"
        
        Returns:
            Just the ID part "abc123" or None
        """
        if not spotify_uri:
            return None
        parts = spotify_uri.split(":")
        return parts[-1] if len(parts) >= 3 else None
