"""Multi-source metadata enrichment use case."""

import logging
from dataclasses import dataclass
from typing import Any

from soulspot.application.services.metadata_merger import MetadataMerger
from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Album, Artist, Track
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    ILastfmClient,
    IMusicBrainzClient,
    ISpotifyClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import TrackId

logger = logging.getLogger(__name__)


@dataclass
class EnrichMetadataMultiSourceRequest:
    """Request to enrich track metadata from multiple sources."""

    track_id: TrackId
    force_refresh: bool = False
    enrich_artist: bool = True
    enrich_album: bool = True
    use_spotify: bool = True
    use_musicbrainz: bool = True
    use_lastfm: bool = True
    spotify_access_token: str | None = None
    manual_overrides: dict[str, Any] | None = None


@dataclass
class EnrichMetadataMultiSourceResponse:
    """Response from multi-source metadata enrichment."""

    track: Track
    artist: Artist | None
    album: Album | None
    enriched_fields: list[str]
    sources_used: list[str]
    errors: list[str]


class EnrichMetadataMultiSourceUseCase(
    UseCase[EnrichMetadataMultiSourceRequest, EnrichMetadataMultiSourceResponse]
):
    """Use case for enriching track metadata from multiple sources with authority hierarchy.

    This use case:
    1. Retrieves track from repository
    2. Fetches metadata from multiple sources (Spotify, MusicBrainz, Last.fm)
    3. Merges metadata using authority hierarchy: Manual > MusicBrainz > Spotify > Last.fm
    4. Optionally enriches artist and album information
    5. Updates entities in repository
    """

    def __init__(
        self,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
        musicbrainz_client: IMusicBrainzClient,
        lastfm_client: ILastfmClient | None = None,
        spotify_client: ISpotifyClient | None = None,
        metadata_merger: MetadataMerger | None = None,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
            album_repository: Repository for album persistence
            musicbrainz_client: Client for MusicBrainz API operations
            lastfm_client: Optional client for Last.fm API operations (None if not configured)
            spotify_client: Optional client for Spotify API operations
            metadata_merger: Optional metadata merger service
        """
        self._track_repository = track_repository
        self._artist_repository = artist_repository
        self._album_repository = album_repository
        self._musicbrainz_client = musicbrainz_client
        self._lastfm_client = lastfm_client
        self._spotify_client = spotify_client
        self._metadata_merger = metadata_merger or MetadataMerger()

    async def _fetch_musicbrainz_metadata(
        self, track: Track, artist: Artist | None
    ) -> dict[str, Any] | None:
        """Fetch metadata from MusicBrainz."""
        try:
            # Try ISRC lookup first
            if track.isrc:
                recording = await self._musicbrainz_client.lookup_recording_by_isrc(
                    track.isrc
                )
                if recording:
                    return recording

            # Fall back to search
            if artist:
                results = await self._musicbrainz_client.search_recording(
                    artist=artist.name, title=track.title, limit=1
                )
                if results:
                    return results[0]

            return None
        except Exception as e:
            logger.warning("MusicBrainz metadata fetch failed: %s", e)
            return None

    async def _fetch_spotify_metadata(
        self, track: Track, access_token: str
    ) -> dict[str, Any] | None:
        """Fetch metadata from Spotify."""
        if not self._spotify_client:
            return None

        try:
            if track.spotify_uri:
                track_id = track.spotify_uri.value.split(":")[-1]
                return await self._spotify_client.get_track(track_id, access_token)

            # Fall back to search
            query = f"track:{track.title}"
            results = await self._spotify_client.search_track(
                query, access_token, limit=1
            )
            if results and "tracks" in results and results["tracks"]["items"]:
                return dict(results["tracks"]["items"][0])

            return None
        except Exception as e:
            logger.warning("Spotify metadata fetch failed: %s", e)
            return None

    async def _fetch_lastfm_metadata(
        self, track: Track, artist: Artist | None
    ) -> dict[str, Any] | None:
        """Fetch metadata from Last.fm."""
        if not self._lastfm_client:
            return None
        try:
            artist_name = artist.name if artist else ""
            return await self._lastfm_client.get_track_info(
                artist=artist_name,
                track=track.title,
                mbid=track.musicbrainz_id,
            )
        except Exception as e:
            logger.warning("Last.fm metadata fetch failed: %s", e)
            return None

    async def execute(
        self, request: EnrichMetadataMultiSourceRequest
    ) -> EnrichMetadataMultiSourceResponse:
        """Execute the multi-source metadata enrichment use case.

        Args:
            request: Request containing track ID and enrichment options

        Returns:
            Response with enriched entities and statistics
        """
        errors: list[str] = []
        sources_used: list[str] = []
        enriched_fields: list[str] = []

        # 1. Retrieve track
        track = await self._track_repository.get_by_id(request.track_id)
        if not track:
            return EnrichMetadataMultiSourceResponse(
                track=None,  # type: ignore
                artist=None,
                album=None,
                enriched_fields=[],
                sources_used=[],
                errors=[f"Track not found: {request.track_id}"],
            )

        # 2. Get artist for context
        artist = None
        if request.enrich_artist:
            try:
                artist = await self._artist_repository.get_by_id(track.artist_id)
            except Exception as e:
                errors.append(f"Failed to fetch artist: {e}")

        # 3. Fetch metadata from sources
        spotify_data = None
        musicbrainz_data = None
        lastfm_data = None

        if request.use_musicbrainz:
            musicbrainz_data = await self._fetch_musicbrainz_metadata(track, artist)
            if musicbrainz_data:
                sources_used.append("MusicBrainz")
                enriched_fields.append("musicbrainz_data_fetched")

        if request.use_spotify and request.spotify_access_token:
            spotify_data = await self._fetch_spotify_metadata(
                track, request.spotify_access_token
            )
            if spotify_data:
                sources_used.append("Spotify")
                enriched_fields.append("spotify_data_fetched")

        if request.use_lastfm:
            lastfm_data = await self._fetch_lastfm_metadata(track, artist)
            if lastfm_data:
                sources_used.append("Last.fm")
                enriched_fields.append("lastfm_data_fetched")

        # 4. Merge track metadata
        try:
            track = self._metadata_merger.merge_track_metadata(
                track=track,
                spotify_data=spotify_data,
                musicbrainz_data=musicbrainz_data,
                lastfm_data=lastfm_data,
                manual_overrides=request.manual_overrides,
            )
            await self._track_repository.update(track)
            enriched_fields.append("track_metadata_merged")
        except Exception as e:
            errors.append(f"Failed to merge track metadata: {e}")

        # 5. Enrich artist metadata
        if artist and request.enrich_artist:
            try:
                # Fetch artist-specific data
                mb_artist_data = None
                if musicbrainz_data and "artist-credit" in musicbrainz_data:
                    artist_mbid = (
                        musicbrainz_data["artist-credit"][0].get("artist", {}).get("id")
                    )
                    if artist_mbid:
                        mb_artist_data = await self._musicbrainz_client.lookup_artist(
                            artist_mbid
                        )

                spotify_artist_data = None
                if (
                    spotify_data
                    and "artists" in spotify_data
                    and spotify_data["artists"]
                ):
                    # Use first artist
                    spotify_artist_data = spotify_data["artists"][0]

                lastfm_artist_data = None
                if self._lastfm_client and artist.musicbrainz_id:
                    lastfm_artist_data = await self._lastfm_client.get_artist_info(
                        artist=artist.name, mbid=artist.musicbrainz_id
                    )

                artist = self._metadata_merger.merge_artist_metadata(
                    artist=artist,
                    spotify_data=spotify_artist_data,
                    musicbrainz_data=mb_artist_data,
                    lastfm_data=lastfm_artist_data,
                    manual_overrides=request.manual_overrides,
                )
                await self._artist_repository.update(artist)
                enriched_fields.append("artist_metadata_merged")
            except Exception as e:
                errors.append(f"Failed to enrich artist metadata: {e}")

        # 6. Enrich album metadata
        album = None
        if track.album_id and request.enrich_album:
            try:
                album = await self._album_repository.get_by_id(track.album_id)
                if album:
                    # Fetch album-specific data
                    mb_album_data = None
                    if album.musicbrainz_id:
                        mb_album_data = await self._musicbrainz_client.lookup_release(
                            album.musicbrainz_id
                        )

                    spotify_album_data = None
                    if spotify_data and "album" in spotify_data:
                        spotify_album_data = spotify_data["album"]

                    lastfm_album_data = None
                    if self._lastfm_client and artist and album.musicbrainz_id:
                        lastfm_album_data = await self._lastfm_client.get_album_info(
                            artist=artist.name,
                            album=album.title,
                            mbid=album.musicbrainz_id,
                        )

                    album = self._metadata_merger.merge_album_metadata(
                        album=album,
                        spotify_data=spotify_album_data,
                        musicbrainz_data=mb_album_data,
                        lastfm_data=lastfm_album_data,
                        manual_overrides=request.manual_overrides,
                    )
                    await self._album_repository.update(album)
                    enriched_fields.append("album_metadata_merged")
            except Exception as e:
                errors.append(f"Failed to enrich album metadata: {e}")

        return EnrichMetadataMultiSourceResponse(
            track=track,
            artist=artist,
            album=album,
            enriched_fields=enriched_fields,
            sources_used=sources_used,
            errors=errors,
        )
