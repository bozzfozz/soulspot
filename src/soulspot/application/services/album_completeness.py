"""Album completeness service for detecting missing tracks."""

import logging
from typing import Any

from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.plugins import SpotifyPlugin

logger = logging.getLogger(__name__)


# Hey future me, AlbumCompletenessInfo is a data holder for album gap analysis! Tells you WHICH tracks are
# missing and calculates percentage (e.g., "you have 10 of 12 tracks = 83.3% complete"). The missing_track_numbers
# list is the actual gap - [3, 7] means track 3 and 7 are missing. Source tells you where we got the track count
# from (spotify vs musicbrainz - useful for debugging mismatches). This is pure data, no business logic!
class AlbumCompletenessInfo:
    """Information about album completeness."""

    # Yo, constructor stores all the album gap details. expected vs actual is the key comparison. expected comes
    # from Spotify/MusicBrainz (what SHOULD exist), actual is what you have locally. missing_track_numbers is
    # computed elsewhere and passed in - this is just storage! The completeness_percent calculation is inline
    # (not a method) because it's simple math. Division by zero check prevents crash on weird edge cases.
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

    # Listen, simple boolean check - is album 100% complete? WHY >= not ==? Deluxe editions might have MORE
    # tracks than expected (bonus tracks). We consider that "complete" because you have everything plus extras!
    # If you want exact match only, change to == but that's probably too strict.
    def is_complete(self) -> bool:
        """Check if album is complete."""
        return self.actual_track_count >= self.expected_track_count

    # Hey future me, serialization to dict for JSON API responses. Rounds percentage to 2 decimals for readability
    # (83.33% not 83.33333333%). Includes both missing count (quick overview) and actual missing numbers (details).
    # The is_complete() call computes the boolean on the fly. Source field lets you know where count came from!
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


# Yo, AlbumCompletenessService is the gap finder - compares your collection against official tracklists!
# Uses TWO metadata sources (Spotify + MusicBrainz) because no single source has everything. Spotify is great
# for mainstream albums, MusicBrainz has obscure/old stuff. Both clients are optional - service degrades
# gracefully if one is missing. This is stateless - no caching, fetches fresh data every time!
# Hey future me – refactored to use SpotifyPlugin statt SpotifyClient! Plugin gibt DTOs zurück.
class AlbumCompletenessService:
    """Service for checking album completeness."""

    # Hey, constructor takes both metadata clients as optional dependencies. If you only have one, that's okay -
    # the service will use what's available. SpotifyPlugin hat Token bereits, MusicBrainz ist
    # anonymous (no auth). Good separation of concerns - service doesn't know HOW to authenticate!
    def __init__(
        self,
        spotify_plugin: SpotifyPlugin | None = None,
        musicbrainz_client: MusicBrainzClient | None = None,
    ) -> None:
        """Initialize album completeness service.

        Args:
            spotify_plugin: Spotify plugin for album metadata (returns DTOs)
            musicbrainz_client: MusicBrainz client for album metadata
        """
        self.spotify_plugin = spotify_plugin
        self.musicbrainz_client = musicbrainz_client

    # Hey future me: Album completeness checking - finds missing tracks from an album
    # WHY two sources (Spotify + MusicBrainz)? Spotify has newer stuff, MusicBrainz has obscure/old stuff
    # Example: Import "OK Computer" with 10 tracks, but album should have 12 - this finds the 2 missing
    # GOTCHA: Deluxe editions vs standard - Spotify might say 15 tracks, you have standard with 10
    # REFACTORED: Now uses SpotifyPlugin which returns AlbumDTO with total_tracks field!
    async def get_expected_track_count_from_spotify(
        self, spotify_uri: str, access_token: str | None = None
    ) -> int | None:
        """Get expected track count from Spotify.

        Args:
            spotify_uri: Spotify album URI
            access_token: DEPRECATED - Plugin manages token internally

        Returns:
            Expected track count or None if not found
        """
        if not self.spotify_plugin:
            return None

        try:
            # Extract album ID from Spotify URI
            # Handles both URI format (spotify:album:XXXX) and ID string
            album_id = spotify_uri.split(":")[-1] if ":" in spotify_uri else spotify_uri

            # Hey future me – Plugin gibt AlbumDTO zurück, nicht raw JSON!
            album = await self.spotify_plugin.get_album(album_id)
            total_tracks = album.total_tracks or 0

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

    # Hey future me: MusicBrainz track counting - sums across all media (discs)
    # WHY loop through media? Albums can be multi-disc - we need total across ALL discs
    # Example: "The Wall" has 2 discs with 13+13 tracks = 26 total
    # GOTCHA: Some releases have bonus DVDs counted as "media" - we count ALL tracks including those
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

    # Listen up, set math to find missing track numbers! Creates a set of expected (1 to N) and a set of what
    # you have, then subtract to find gaps. WHY sets not lists? Sets have O(1) lookup vs O(n) for lists - much
    # faster for large albums! The sorted() at the end makes output readable ([1, 3, 7] not [7, 1, 3]). Returns
    # empty list if expected_track_count is zero or negative (defensive). Simple and efficient algorithm!
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
