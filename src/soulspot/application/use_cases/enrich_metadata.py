"""Enrich metadata use case."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from rapidfuzz import fuzz

from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IMusicBrainzClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId

logger = logging.getLogger(__name__)


@dataclass
class EnrichMetadataRequest:
    """Request to enrich track metadata."""

    track_id: TrackId
    force_refresh: bool = False
    enrich_artist: bool = True
    enrich_album: bool = True


@dataclass
class EnrichMetadataResponse:
    """Response from enriching track metadata."""

    track: Track
    artist: Artist | None
    album: Album | None
    enriched_fields: list[str]
    errors: list[str]


class EnrichMetadataUseCase(UseCase[EnrichMetadataRequest, EnrichMetadataResponse]):
    """Use case for enriching track metadata from MusicBrainz.

    This use case:
    1. Retrieves track from repository
    2. Looks up recording in MusicBrainz (by ISRC or search)
    3. Enriches track with additional metadata
    4. Optionally enriches artist information
    5. Optionally enriches album information
    6. Updates entities in repository
    """

    # Hey future me: This is the metadata enrichment workhorse - ONE track from ONE source (MusicBrainz)
    # WHY MusicBrainz only? It's the canonical source with ISRCs, proper track lengths, etc.
    # For multi-source enrichment (Spotify + Last.fm + MusicBrainz), see EnrichMetadataMultiSourceUseCase
    # GOTCHA: We inject ALL three repositories even though we're only enriching one track
    # WHY? Because MB data includes artist + album info, we might create those too

    # Minimum confidence score to accept a match (0.0 - 1.0)
    # Hey future me: 0.75 is a balanced threshold - too low = false positives,
    # too high = misses good matches (live versions, remasters, etc.)
    MIN_CONFIDENCE_THRESHOLD: float = 0.75

    def __init__(
        self,
        musicbrainz_client: IMusicBrainzClient,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            musicbrainz_client: Client for MusicBrainz API operations
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
            album_repository: Repository for album persistence
        """
        self._musicbrainz_client = musicbrainz_client
        self._track_repository = track_repository
        self._artist_repository = artist_repository
        self._album_repository = album_repository

    # Hey future me: Confidence scoring to avoid false positive matches
    # WHY weighted average? Title matters more than artist for track matching
    # (same artist, wrong song = useless match)
    # WHY duration bonus? Duration is a strong signal - same title but 3min vs 7min = different track
    # GOTCHA: Duration can be None for both track and MB result, handle gracefully
    @staticmethod
    def _calculate_match_confidence(
        query_title: str,
        query_artist: str,
        result_title: str,
        result_artist: str,
        query_duration_ms: int | None = None,
        result_duration_ms: int | None = None,
    ) -> float:
        """Calculate confidence score for a metadata match.

        Uses fuzzy string matching on title and artist, with optional
        duration comparison as a tiebreaker.

        Args:
            query_title: Track title we're searching for
            query_artist: Artist name we're searching for
            result_title: Title from search result
            result_artist: Artist name from search result
            query_duration_ms: Optional duration of our track in milliseconds
            result_duration_ms: Optional duration of result in milliseconds

        Returns:
            Confidence score from 0.0 (no match) to 1.0 (perfect match)
        """
        # Normalize strings for better matching
        query_title_norm = query_title.lower().strip()
        result_title_norm = result_title.lower().strip()
        query_artist_norm = query_artist.lower().strip()
        result_artist_norm = result_artist.lower().strip()

        # Calculate fuzzy similarity scores (0-100)
        # Using token_sort_ratio for title (handles word order: "Love Me Do" vs "Do Love Me")
        # Using partial_ratio for artist (handles "The Beatles" vs "Beatles")
        title_score = fuzz.token_sort_ratio(query_title_norm, result_title_norm)
        artist_score = fuzz.partial_ratio(query_artist_norm, result_artist_norm)

        # Weighted average: title matters more (60%) than artist (40%)
        # because same artist + wrong track = useless
        base_confidence = (title_score * 0.6 + artist_score * 0.4) / 100.0

        # Duration bonus/penalty if both durations available
        # Similar duration = more likely correct match
        if query_duration_ms and result_duration_ms:
            duration_diff_ms = abs(query_duration_ms - result_duration_ms)
            if duration_diff_ms <= 1000:  # Within 1 second = excellent
                base_confidence = min(1.0, base_confidence + 0.05)
            elif duration_diff_ms <= 3000:  # Within 3 seconds = good
                base_confidence = min(1.0, base_confidence + 0.02)
            elif duration_diff_ms > 30000:  # More than 30 seconds = suspicious
                base_confidence = max(0.0, base_confidence - 0.1)

        return round(base_confidence, 3)

    # Hey future me: The ISRC lookup dance - this is the fastest and most accurate way to match tracks
    # WHY try ISRC first? It's a globally unique identifier - like a barcode for recordings
    # WHY abs(track.duration_ms - mb_length) > 2000? Radio edits vs album versions can differ by seconds
    # GOTCHA: Not all tracks have ISRCs (especially older/indie stuff), so we fall back to search
    async def _enrich_track_metadata(
        self,
        track: Track,
        force_refresh: bool,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Enrich track metadata from MusicBrainz.

        Args:
            track: Track entity to enrich
            force_refresh: Whether to force refresh even if metadata exists

        Returns:
            Tuple of (MusicBrainz recording data, list of enriched fields)
        """
        enriched_fields: list[str] = []

        # Skip if already enriched and not forcing refresh
        if track.musicbrainz_id and not force_refresh:
            return None, enriched_fields

        # Try to lookup by ISRC first (fastest and most accurate)
        recording = None
        if track.isrc:
            try:
                recording = await self._musicbrainz_client.lookup_recording_by_isrc(
                    track.isrc
                )
                if recording:
                    enriched_fields.append("musicbrainz_lookup_by_isrc")
            except Exception as e:
                logger.debug(
                    "MusicBrainz ISRC lookup failed for track %s: %s. Falling back to search.",
                    track.id.value,
                    e,
                )

        # Fall back to search if ISRC lookup failed
        # Hey future me: We now use confidence scoring to avoid false positives!
        # Previously just took first result - now we score ALL results and pick best above threshold
        if not recording:
            try:
                # Fetch artist name from repository
                artist_name = ""
                try:
                    artist = await self._artist_repository.get_by_id(track.artist_id)
                    if artist:
                        artist_name = artist.name
                except Exception as e:
                    # Log the error but continue with empty artist name
                    logger.warning(
                        "Failed to fetch artist for track %s: %s", track.id.value, e
                    )

                results = await self._musicbrainz_client.search_recording(
                    artist=artist_name,
                    title=track.title,
                    limit=5,
                )
                if results:
                    # Score all results and pick the best match above threshold
                    best_match = None
                    best_score = 0.0

                    for result in results:
                        result_title = result.get("title", "")
                        # Get artist from result (may be in different structures)
                        result_artist = ""
                        if result.get("artist-credit"):
                            artist_credit = result["artist-credit"]
                            if isinstance(artist_credit, list) and artist_credit:
                                result_artist = artist_credit[0].get("artist", {}).get(
                                    "name", ""
                                )
                            elif isinstance(artist_credit, str):
                                result_artist = artist_credit

                        result_duration = result.get("length")

                        score = self._calculate_match_confidence(
                            query_title=track.title,
                            query_artist=artist_name,
                            result_title=result_title,
                            result_artist=result_artist,
                            query_duration_ms=track.duration_ms,
                            result_duration_ms=result_duration,
                        )

                        logger.debug(
                            "Match score for '%s' by '%s': %.3f",
                            result_title,
                            result_artist,
                            score,
                        )

                        if score > best_score:
                            best_score = score
                            best_match = result

                    # Only accept if above threshold
                    if best_match and best_score >= self.MIN_CONFIDENCE_THRESHOLD:
                        recording = best_match
                        enriched_fields.append("musicbrainz_search")
                        enriched_fields.append(f"confidence_{best_score:.2f}")
                        logger.info(
                            "Matched track '%s' to MusicBrainz '%s' with confidence %.2f",
                            track.title,
                            best_match.get("title"),
                            best_score,
                        )
                    elif best_match:
                        logger.warning(
                            "Best MusicBrainz match for '%s' has low confidence %.2f "
                            "(threshold: %.2f), skipping",
                            track.title,
                            best_score,
                            self.MIN_CONFIDENCE_THRESHOLD,
                        )
            except httpx.HTTPError as e:
                logger.warning(
                    "Failed to search MusicBrainz for track %s: %s",
                    track.id,
                    e,
                    exc_info=True,
                )
                return None, enriched_fields

        if recording:
            # Update track with MusicBrainz data
            track.musicbrainz_id = recording.get("id")

            # Update duration if not set or more accurate
            mb_length = recording.get("length")
            if mb_length and (
                not track.duration_ms or abs(track.duration_ms - mb_length) > 2000
            ):
                track.duration_ms = mb_length
                enriched_fields.append("duration_ms")

            # Update ISRC if found
            isrc_list = recording.get("isrc-list", [])
            if isrc_list and not track.isrc:
                track.isrc = isrc_list[0]
                enriched_fields.append("isrc")

            track.updated_at = datetime.now(UTC)

        return recording, enriched_fields

    async def _enrich_artist_metadata(
        self,
        recording: dict[str, Any],
        _track: Track,
    ) -> tuple[Artist | None, list[str]]:
        """Enrich artist metadata from MusicBrainz.

        Args:
            recording: MusicBrainz recording data
            track: Track entity

        Returns:
            Tuple of (Artist entity, list of enriched fields)
        """
        enriched_fields: list[str] = []

        if not recording or not recording.get("artist-credit"):
            return None, enriched_fields

        # Get first artist from recording
        artist_credit = recording["artist-credit"][0]
        artist_data = artist_credit.get("artist", {})
        artist_mbid = artist_data.get("id")

        if not artist_mbid:
            return None, enriched_fields

        # Check if artist already exists
        artist = await self._artist_repository.get_by_musicbrainz_id(artist_mbid)

        if not artist:
            # Fetch full artist details
            try:
                mb_artist = await self._musicbrainz_client.lookup_artist(artist_mbid)
                if mb_artist:
                    artist = Artist(
                        id=ArtistId.generate(),
                        name=mb_artist["name"],
                        musicbrainz_id=artist_mbid,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    await self._artist_repository.add(artist)
                    enriched_fields.append("artist_created")
            except Exception as e:
                logger.debug(
                    "Failed to create artist from MusicBrainz ID %s: %s",
                    artist_mbid,
                    e,
                )

        return artist, enriched_fields

    async def _enrich_album_metadata(
        self,
        recording: dict[str, Any],
        _track: Track,
    ) -> tuple[Album | None, list[str]]:
        """Enrich album metadata from MusicBrainz.

        Args:
            recording: MusicBrainz recording data
            track: Track entity

        Returns:
            Tuple of (Album entity, list of enriched fields)
        """
        enriched_fields: list[str] = []

        if not recording or not recording.get("release-list"):
            return None, enriched_fields

        # Get first release (album)
        release = recording["release-list"][0]
        release_mbid = release.get("id")

        if not release_mbid:
            return None, enriched_fields

        # Check if album already exists
        album = await self._album_repository.get_by_musicbrainz_id(release_mbid)

        if not album:
            # Fetch full release details
            try:
                mb_release = await self._musicbrainz_client.lookup_release(release_mbid)
                if mb_release:
                    # Extract release year
                    release_date = mb_release.get("date", "")
                    release_year = (
                        int(release_date[:4])
                        if release_date and len(release_date) >= 4
                        else None
                    )

                    # Get artist ID (should already exist from track enrichment)
                    artist_credit = mb_release.get("artist-credit", [{}])[0]
                    artist_mbid = artist_credit.get("artist", {}).get("id")
                    artist = None
                    if artist_mbid:
                        artist = await self._artist_repository.get_by_musicbrainz_id(
                            artist_mbid
                        )

                    if artist:
                        album = Album(
                            id=AlbumId.generate(),
                            title=mb_release["title"],
                            artist_id=artist.id,
                            release_year=release_year,
                            musicbrainz_id=release_mbid,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                        await self._album_repository.add(album)
                        enriched_fields.append("album_created")
            except Exception as e:
                logger.debug(
                    "Failed to create album from MusicBrainz release %s: %s",
                    release_mbid,
                    e,
                )

        return album, enriched_fields

    async def execute(self, request: EnrichMetadataRequest) -> EnrichMetadataResponse:
        """Execute the enrich metadata use case.

        Args:
            request: Request containing track ID and enrichment options

        Returns:
            Response with enriched entities and statistics
        """
        errors: list[str] = []
        all_enriched_fields: list[str] = []

        # 1. Retrieve track
        track = await self._track_repository.get_by_id(request.track_id)
        if not track:
            return EnrichMetadataResponse(
                track=None,  # type: ignore
                artist=None,
                album=None,
                enriched_fields=[],
                errors=[f"Track not found: {request.track_id}"],
            )

        # 2. Enrich track metadata
        try:
            recording, track_fields = await self._enrich_track_metadata(
                track, request.force_refresh
            )
            all_enriched_fields.extend(track_fields)

            if recording:
                await self._track_repository.update(track)
        except Exception as e:
            errors.append(f"Failed to enrich track: {e}")
            recording = None

        # 3. Enrich artist metadata
        artist = None
        if request.enrich_artist and recording:
            try:
                artist, artist_fields = await self._enrich_artist_metadata(
                    recording, track
                )
                all_enriched_fields.extend(artist_fields)
            except Exception as e:
                errors.append(f"Failed to enrich artist: {e}")

        # 4. Enrich album metadata
        album = None
        if request.enrich_album and recording:
            try:
                album, album_fields = await self._enrich_album_metadata(
                    recording, track
                )
                all_enriched_fields.extend(album_fields)
            except Exception as e:
                errors.append(f"Failed to enrich album: {e}")

        return EnrichMetadataResponse(
            track=track,
            artist=artist,
            album=album,
            enriched_fields=all_enriched_fields,
            errors=errors,
        )
