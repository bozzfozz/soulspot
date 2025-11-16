"""Album completeness service for detecting missing tracks."""

import logging
from typing import Any

from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


class AlbumCompletenessInfo:
    """Information about album completeness."""

    def __init__(
        self,
        album_id: str,
        album_title: str,
        artist_name: str,
        expected_track_count: int,
        actual_track_count: int,
        missing_track_numbers: list[int],
        source: str,
    ):
        """Initialize album completeness info."""
        self.album_id = album_id
        self.album_title = album_title
        self.artist_name = artist_name
        self.expected_track_count = expected_track_count
        self.actual_track_count = actual_track_count
        self.missing_track_numbers = missing_track_numbers
        self.source = source
        self.completeness_percent = (
            (actual_track_count / expected_track_count * 100)
            if expected_track_count > 0
            else 0.0
        )

    def is_complete(self) -> bool:
        """Check if album is complete."""
        return self.actual_track_count >= self.expected_track_count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "album_id": self.album_id,
            "album_title": self.album_title,
            "artist_name": self.artist_name,
            "expected_track_count": self.expected_track_count,
            "actual_track_count": self.actual_track_count,
            "missing_track_count": len(self.missing_track_numbers),
            "missing_track_numbers": self.missing_track_numbers,
            "completeness_percent": round(self.completeness_percent, 2),
            "is_complete": self.is_complete(),
            "source": self.source,
        }


class AlbumCompletenessService:
    """Service for checking album completeness."""

    def __init__(
        self,
        spotify_client: SpotifyClient | None = None,
        musicbrainz_client: MusicBrainzClient | None = None,
    ) -> None:
        """Initialize album completeness service.

        Args:
            spotify_client: Spotify client for album metadata
            musicbrainz_client: MusicBrainz client for album metadata
        """
        self.spotify_client = spotify_client
        self.musicbrainz_client = musicbrainz_client

    async def get_expected_track_count_from_spotify(
        self, spotify_uri: str, access_token: str
    ) -> int | None:
        """Get expected track count from Spotify.

        Args:
            spotify_uri: Spotify album URI
            access_token: Spotify access token

        Returns:
            Expected track count or None if not found
        """
        if not self.spotify_client:
            return None

        try:
            # Extract album ID from URI (spotify:album:XXXX)
            album_id = spotify_uri.split(":")[-1] if ":" in spotify_uri else spotify_uri

            # Get album details from Spotify API
            client = await self.spotify_client._get_client()
            response = await client.get(
                f"{self.spotify_client.API_BASE_URL}/albums/{album_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()

            album_data = response.json()
            total_tracks: int = album_data.get("total_tracks", 0)

            logger.info(
                f"Found {total_tracks} tracks for Spotify album {album_id}",
                extra={"album_id": album_id, "track_count": total_tracks},
            )

            return total_tracks

        except Exception as e:
            logger.warning(
                f"Failed to get track count from Spotify: {e}",
                extra={"spotify_uri": spotify_uri, "error": str(e)},
            )
            return None

    async def get_expected_track_count_from_musicbrainz(
        self, musicbrainz_id: str
    ) -> int | None:
        """Get expected track count from MusicBrainz.

        Args:
            musicbrainz_id: MusicBrainz release ID

        Returns:
            Expected track count or None if not found
        """
        if not self.musicbrainz_client:
            return None

        try:
            release_data = await self.musicbrainz_client.lookup_release(musicbrainz_id)

            if not release_data:
                return None

            # Count tracks across all media in the release
            total_tracks = 0
            media_list = release_data.get("media", [])

            for media in media_list:
                track_count = media.get("track-count", 0)
                total_tracks += track_count

            logger.info(
                f"Found {total_tracks} tracks for MusicBrainz release {musicbrainz_id}",
                extra={"musicbrainz_id": musicbrainz_id, "track_count": total_tracks},
            )

            return total_tracks

        except Exception as e:
            logger.warning(
                f"Failed to get track count from MusicBrainz: {e}",
                extra={"musicbrainz_id": musicbrainz_id, "error": str(e)},
            )
            return None

    def detect_missing_track_numbers(
        self, local_track_numbers: list[int], expected_track_count: int
    ) -> list[int]:
        """Detect missing track numbers.

        Args:
            local_track_numbers: List of track numbers present locally
            expected_track_count: Expected total track count

        Returns:
            List of missing track numbers
        """
        if expected_track_count <= 0:
            return []

        expected_numbers = set(range(1, expected_track_count + 1))
        present_numbers = set(local_track_numbers)
        missing_numbers = sorted(expected_numbers - present_numbers)

        return missing_numbers
