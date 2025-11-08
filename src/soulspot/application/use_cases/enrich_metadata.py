"""Enrich metadata use case."""

from dataclasses import dataclass
from datetime import datetime

from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IMusicBrainzClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import AlbumId, ArtistId, TrackId


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

    async def _enrich_track_metadata(
        self,
        track: Track,
        force_refresh: bool,
    ) -> tuple[dict[str, any] | None, list[str]]:
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
                recording = await self._musicbrainz_client.lookup_recording_by_isrc(track.isrc)
                if recording:
                    enriched_fields.append("musicbrainz_lookup_by_isrc")
            except Exception:
                pass  # Fall back to search

        # Fall back to search if ISRC lookup failed
        if not recording:
            try:
                artist = track.artist_names[0] if track.artist_names else ""
                results = await self._musicbrainz_client.search_recording(
                    artist=artist,
                    title=track.title,
                    limit=5,
                )
                if results:
                    recording = results[0]  # Take first result
                    enriched_fields.append("musicbrainz_search")
            except Exception:
                return None, enriched_fields

        if recording:
            # Update track with MusicBrainz data
            track.musicbrainz_id = recording.get("id")

            # Update duration if not set or more accurate
            mb_length = recording.get("length")
            if mb_length and (not track.duration_ms or abs(track.duration_ms - mb_length) > 2000):
                track.duration_ms = mb_length
                enriched_fields.append("duration_ms")

            # Update ISRC if found
            isrc_list = recording.get("isrc-list", [])
            if isrc_list and not track.isrc:
                track.isrc = isrc_list[0]
                enriched_fields.append("isrc")

            track.updated_at = datetime.utcnow()

        return recording, enriched_fields

    async def _enrich_artist_metadata(
        self,
        recording: dict[str, any],
        track: Track,
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
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    await self._artist_repository.add(artist)
                    enriched_fields.append("artist_created")
            except Exception:
                pass

        return artist, enriched_fields

    async def _enrich_album_metadata(
        self,
        recording: dict[str, any],
        track: Track,
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
                    release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

                    # Get artist ID (should already exist from track enrichment)
                    artist_credit = mb_release.get("artist-credit", [{}])[0]
                    artist_mbid = artist_credit.get("artist", {}).get("id")
                    artist = None
                    if artist_mbid:
                        artist = await self._artist_repository.get_by_musicbrainz_id(artist_mbid)

                    if artist:
                        album = Album(
                            id=AlbumId.generate(),
                            title=mb_release["title"],
                            artist_id=artist.id,
                            release_year=release_year,
                            musicbrainz_id=release_mbid,
                            total_tracks=mb_release.get("track-count"),
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        await self._album_repository.add(album)
                        enriched_fields.append("album_created")
            except Exception:
                pass

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
            recording, track_fields = await self._enrich_track_metadata(track, request.force_refresh)
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
                artist, artist_fields = await self._enrich_artist_metadata(recording, track)
                all_enriched_fields.extend(artist_fields)
            except Exception as e:
                errors.append(f"Failed to enrich artist: {e}")

        # 4. Enrich album metadata
        album = None
        if request.enrich_album and recording:
            try:
                album, album_fields = await self._enrich_album_metadata(recording, track)
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
