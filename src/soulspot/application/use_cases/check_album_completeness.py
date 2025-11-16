"""Use case for checking album completeness."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.album_completeness import (
    AlbumCompletenessInfo,
    AlbumCompletenessService,
)
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)

logger = logging.getLogger(__name__)


class CheckAlbumCompletenessUseCase:
    """Use case for checking album completeness."""

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient | None = None,
        musicbrainz_client: MusicBrainzClient | None = None,
        access_token: str | None = None,
    ) -> None:
        """Initialize use case.

        Args:
            session: Database session
            spotify_client: Spotify client for album metadata
            musicbrainz_client: MusicBrainz client for album metadata
            access_token: Spotify access token
        """
        self.session = session
        self.service = AlbumCompletenessService(spotify_client, musicbrainz_client)
        self.access_token = access_token

    async def execute(
        self, incomplete_only: bool = True, min_track_count: int = 3
    ) -> list[dict[str, Any]]:
        """Check completeness of all albums.

        Args:
            incomplete_only: Only return incomplete albums
            min_track_count: Minimum track count to consider (filters out singles)

        Returns:
            List of album completeness information
        """
        logger.info(
            "Starting album completeness check",
            extra={
                "incomplete_only": incomplete_only,
                "min_track_count": min_track_count,
            },
        )

        # Fetch all albums with their artists
        stmt = (
            select(AlbumModel, ArtistModel)
            .join(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
            .order_by(ArtistModel.name, AlbumModel.title)
        )
        result = await self.session.execute(stmt)
        albums_with_artists = result.all()

        completeness_results: list[dict[str, Any]] = []

        for album_model, artist_model in albums_with_artists:
            try:
                # Get local tracks for this album
                tracks_stmt = select(TrackModel).where(
                    TrackModel.album_id == album_model.id
                )
                tracks_result = await self.session.execute(tracks_stmt)
                local_tracks = tracks_result.scalars().all()

                # Extract track numbers
                local_track_numbers = [
                    track.track_number
                    for track in local_tracks
                    if track.track_number is not None
                ]

                actual_count = len(local_tracks)
                expected_count = 0
                source = "unknown"

                # Try to get expected track count from Spotify
                if album_model.spotify_uri and self.access_token:
                    spotify_count = (
                        await self.service.get_expected_track_count_from_spotify(
                            album_model.spotify_uri, self.access_token
                        )
                    )
                    if spotify_count:
                        expected_count = spotify_count
                        source = "spotify"

                # Fallback to MusicBrainz if Spotify didn't work
                if expected_count == 0 and album_model.musicbrainz_id:
                    mb_count = (
                        await self.service.get_expected_track_count_from_musicbrainz(
                            album_model.musicbrainz_id
                        )
                    )
                    if mb_count:
                        expected_count = mb_count
                        source = "musicbrainz"

                # Skip if we couldn't determine expected count or album is too small
                if expected_count == 0 or expected_count < min_track_count:
                    continue

                # Detect missing track numbers
                missing_numbers = self.service.detect_missing_track_numbers(
                    local_track_numbers, expected_count
                )

                # Create completeness info
                completeness_info = AlbumCompletenessInfo(
                    album_id=album_model.id,
                    album_title=album_model.title,
                    artist_name=artist_model.name,
                    expected_track_count=expected_count,
                    actual_track_count=actual_count,
                    missing_track_numbers=missing_numbers,
                    source=source,
                )

                # Filter incomplete if requested
                if incomplete_only and completeness_info.is_complete():
                    continue

                completeness_results.append(completeness_info.to_dict())

            except Exception as e:
                logger.error(
                    f"Failed to check completeness for album {album_model.title}: {e}",
                    extra={
                        "album_id": album_model.id,
                        "album_title": album_model.title,
                        "error": str(e),
                    },
                )
                continue

        logger.info(
            f"Album completeness check complete: found {len(completeness_results)} albums",
            extra={"album_count": len(completeness_results)},
        )

        return completeness_results

    async def check_single_album(self, album_id: str) -> dict[str, Any] | None:
        """Check completeness of a single album.

        Args:
            album_id: Album ID to check

        Returns:
            Album completeness information or None if not found
        """
        # Fetch album with artist
        stmt = (
            select(AlbumModel, ArtistModel)
            .join(ArtistModel, AlbumModel.artist_id == ArtistModel.id)
            .where(AlbumModel.id == album_id)
        )
        result = await self.session.execute(stmt)
        album_data = result.first()

        if not album_data:
            logger.warning(f"Album not found: {album_id}", extra={"album_id": album_id})
            return None

        album_model, artist_model = album_data

        # Get local tracks
        tracks_stmt = select(TrackModel).where(TrackModel.album_id == album_model.id)
        tracks_result = await self.session.execute(tracks_stmt)
        local_tracks = tracks_result.scalars().all()

        # Extract track numbers
        local_track_numbers = [
            track.track_number
            for track in local_tracks
            if track.track_number is not None
        ]

        actual_count = len(local_tracks)
        expected_count = 0
        source = "unknown"

        # Try Spotify
        if album_model.spotify_uri and self.access_token:
            spotify_count = await self.service.get_expected_track_count_from_spotify(
                album_model.spotify_uri, self.access_token
            )
            if spotify_count:
                expected_count = spotify_count
                source = "spotify"

        # Fallback to MusicBrainz
        if expected_count == 0 and album_model.musicbrainz_id:
            mb_count = await self.service.get_expected_track_count_from_musicbrainz(
                album_model.musicbrainz_id
            )
            if mb_count:
                expected_count = mb_count
                source = "musicbrainz"

        if expected_count == 0:
            logger.warning(
                f"Could not determine expected track count for album {album_id}",
                extra={"album_id": album_id},
            )
            return None

        # Detect missing tracks
        missing_numbers = self.service.detect_missing_track_numbers(
            local_track_numbers, expected_count
        )

        completeness_info = AlbumCompletenessInfo(
            album_id=album_model.id,
            album_title=album_model.title,
            artist_name=artist_model.name,
            expected_track_count=expected_count,
            actual_track_count=actual_count,
            missing_track_numbers=missing_numbers,
            source=source,
        )

        return completeness_info.to_dict()
