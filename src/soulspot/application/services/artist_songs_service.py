# AI-Model: Copilot
"""Service for syncing and managing individual songs (singles) from followed artists.

Hey future me - this service handles syncing songs that are NOT part of albums from
artists the user follows on Spotify. It fetches "top tracks" from Spotify (most popular
songs) and stores them as tracks without album association. This is separate from
album sync - we're handling standalone singles/popular tracks here!

The flow is:
1. Get followed artists from DB (already synced via FollowedArtistsService)
2. For each artist, fetch their top tracks from Spotify API
3. Filter out tracks that are part of albums (we only want singles)
4. Create/update Track entities in our DB
5. Return sync statistics

GOTCHA: Spotify's "top tracks" endpoint returns the artist's most popular songs,
which may include album tracks. We filter these by checking if the track's album
type is "single" or if the album has only one track.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Track
from soulspot.domain.value_objects import ArtistId, SpotifyUri, TrackId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import (
    ArtistRepository,
    TrackRepository,
)

logger = logging.getLogger(__name__)


class ArtistSongsService:
    """Service for syncing individual songs from followed artists.

    This service syncs popular songs/singles from artists in the database.
    Unlike FollowedArtistsService which syncs artist metadata, this syncs
    the actual TRACKS (songs). Focuses on singles and popular tracks that
    aren't part of full albums, giving users quick access to hit songs.

    The spotify_client is optional - only required for sync operations.
    Read and delete operations work without it.
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient | None = None,
    ) -> None:
        """Initialize artist songs service.

        Args:
            session: Database session for repositories
            spotify_client: Spotify client for API calls (optional, only needed for sync)
        """
        self.session = session
        self.artist_repo = ArtistRepository(session)
        self.track_repo = TrackRepository(session)
        self._spotify_client = spotify_client

    @property
    def spotify_client(self) -> SpotifyClient:
        """Get Spotify client, raising error if not configured.

        Returns:
            SpotifyClient instance

        Raises:
            ValueError: If spotify_client was not provided during initialization
        """
        if self._spotify_client is None:
            raise ValueError(
                "SpotifyClient is required for this operation. "
                "Initialize ArtistSongsService with spotify_client parameter."
            )
        return self._spotify_client

    # Main sync method for syncing songs from a single artist.
    # Fetches top tracks from Spotify, filters for singles (non-album tracks),
    # and creates/updates them in DB. Returns the tracks plus stats.
    async def sync_artist_songs(
        self, artist_id: ArtistId, access_token: str, market: str = "US"
    ) -> tuple[list[Track], dict[str, Any]]:
        """Sync songs from a single artist.

        Fetches the artist's top tracks from Spotify and stores non-album
        tracks (singles) in the database. Existing tracks are updated,
        new ones are created.

        Args:
            artist_id: Artist ID to sync songs for
            access_token: Spotify OAuth access token
            market: ISO 3166-1 alpha-2 country code (e.g., "US", "DE")

        Returns:
            Tuple of (list of Track entities, sync statistics dict)

        Raises:
            ValueError: If artist not found in database
        """
        stats = {
            "total_fetched": 0,
            "singles_found": 0,
            "created": 0,
            "updated": 0,
            "skipped_album_tracks": 0,
            "errors": 0,
        }

        # Verify artist exists in our DB
        artist = await self.artist_repo.get_by_id(artist_id)
        if not artist:
            raise ValueError(f"Artist not found: {artist_id.value}")

        if not artist.spotify_uri:
            raise ValueError(f"Artist has no Spotify URI: {artist.name}")

        # Extract Spotify artist ID from URI (spotify:artist:xxxxx -> xxxxx)
        spotify_artist_id = str(artist.spotify_uri).split(":")[-1]

        synced_tracks: list[Track] = []

        try:
            # Fetch top tracks from Spotify
            top_tracks = await self.spotify_client.get_artist_top_tracks(
                artist_id=spotify_artist_id,
                access_token=access_token,
                market=market,
            )

            stats["total_fetched"] = len(top_tracks)
            logger.info(
                f"Fetched {len(top_tracks)} top tracks for artist {artist.name}"
            )

            for track_data in top_tracks:
                try:
                    track, was_created, is_single = await self._process_track(
                        track_data, artist_id
                    )
                    if track:
                        synced_tracks.append(track)
                        if is_single:
                            stats["singles_found"] += 1
                        if was_created:
                            stats["created"] += 1
                        else:
                            stats["updated"] += 1
                    else:
                        stats["skipped_album_tracks"] += 1
                except Exception as e:
                    logger.error(
                        f"Failed to process track {track_data.get('name', 'unknown')}: {e}"
                    )
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error fetching top tracks for artist {artist.name}: {e}")
            raise

        logger.info(
            f"Artist songs sync for {artist.name}: {stats['total_fetched']} fetched, "
            f"{stats['singles_found']} singles, {stats['created']} created, "
            f"{stats['updated']} updated, {stats['skipped_album_tracks']} skipped"
        )

        return synced_tracks, stats

    # Bulk sync operation for all followed artists in DB.
    # Iterates through artists and syncs their songs. Can take a while for
    # users following many artists. Consider adding progress callbacks for UI.
    async def sync_all_artists_songs(
        self, access_token: str, market: str = "US", limit: int = 100
    ) -> tuple[list[Track], dict[str, Any]]:
        """Sync songs from all followed artists in the database.

        Iterates through all artists in DB and syncs their top tracks.
        This is a bulk operation and may take time for many artists.

        Args:
            access_token: Spotify OAuth access token
            market: ISO 3166-1 alpha-2 country code
            limit: Maximum number of artists to process

        Returns:
            Tuple of (list of all synced Track entities, aggregate statistics)
        """
        aggregate_stats = {
            "artists_processed": 0,
            "total_fetched": 0,
            "singles_found": 0,
            "created": 0,
            "updated": 0,
            "skipped_album_tracks": 0,
            "errors": 0,
            "artist_errors": 0,
        }

        all_tracks: list[Track] = []

        # Get all artists from DB
        artists = await self.artist_repo.list_all(limit=limit)
        logger.info(f"Starting song sync for {len(artists)} artists")

        for artist in artists:
            try:
                tracks, stats = await self.sync_artist_songs(
                    artist_id=artist.id,
                    access_token=access_token,
                    market=market,
                )
                all_tracks.extend(tracks)
                aggregate_stats["artists_processed"] += 1
                aggregate_stats["total_fetched"] += stats["total_fetched"]
                aggregate_stats["singles_found"] += stats["singles_found"]
                aggregate_stats["created"] += stats["created"]
                aggregate_stats["updated"] += stats["updated"]
                aggregate_stats["skipped_album_tracks"] += stats["skipped_album_tracks"]
                aggregate_stats["errors"] += stats["errors"]
            except Exception as e:
                logger.error(f"Failed to sync songs for artist {artist.name}: {e}")
                aggregate_stats["artist_errors"] += 1

        logger.info(
            f"Bulk song sync complete: {aggregate_stats['artists_processed']} artists, "
            f"{aggregate_stats['created']} tracks created, "
            f"{aggregate_stats['updated']} tracks updated"
        )

        return all_tracks, aggregate_stats

    # Process a single track from Spotify API response.
    # Checks if it already exists (by spotify_uri), then creates or updates.
    # Returns (track, was_created, is_single) - is_single helps with stats.
    async def _process_track(
        self, track_data: dict[str, Any], artist_id: ArtistId
    ) -> tuple[Track | None, bool, bool]:
        """Process a single track from Spotify API response.

        Creates or updates a Track entity based on Spotify data.
        Stores ALL tracks (both singles and album tracks) to provide
        comprehensive artist song coverage.

        Args:
            track_data: Track data from Spotify API
            artist_id: Artist ID to associate track with

        Returns:
            Tuple of (Track entity or None, was_created boolean, is_single boolean)
        """
        spotify_track_id = track_data.get("id")
        track_name = track_data.get("name")
        duration_ms = track_data.get("duration_ms", 0)
        track_number = track_data.get("track_number")
        disc_number = track_data.get("disc_number", 1)

        if not spotify_track_id or not track_name:
            logger.warning(f"Invalid track data: missing id or name - {track_data}")
            return None, False, False

        spotify_uri = SpotifyUri.from_string(f"spotify:track:{spotify_track_id}")

        # Check album info to determine if this is a single
        album_data = track_data.get("album", {})
        album_type = album_data.get("album_type", "")
        # A track is considered a "single" if album_type is "single"
        is_single = album_type == "single"

        # Extract ISRC if available (from external_ids)
        external_ids = track_data.get("external_ids", {})
        isrc = external_ids.get("isrc")

        # Check if track already exists by Spotify URI
        existing_track = await self.track_repo.get_by_spotify_uri(spotify_uri)

        if existing_track:
            # Update existing track metadata if needed
            needs_update = False
            if existing_track.title != track_name:
                existing_track.title = track_name
                needs_update = True
            if existing_track.duration_ms != duration_ms:
                existing_track.duration_ms = duration_ms
                needs_update = True
            if existing_track.isrc != isrc and isrc:
                existing_track.isrc = isrc
                needs_update = True

            if needs_update:
                await self.track_repo.update(existing_track)
                logger.debug(f"Updated track: {track_name}")

            return existing_track, False, is_single

        # Create new track entity - store WITHOUT album association
        # so these show up as "singles" in our DB
        new_track = Track(
            id=TrackId.generate(),
            title=track_name,
            artist_id=artist_id,
            album_id=None,  # Store as single (no album)
            duration_ms=duration_ms,
            track_number=track_number,
            disc_number=disc_number,
            spotify_uri=spotify_uri,
            isrc=isrc,
        )

        await self.track_repo.add(new_track)
        logger.info(f"Created new track: {track_name}")

        return new_track, True, is_single

    # Get all singles (non-album tracks) for an artist from DB.
    # This is a READ operation that doesn't touch Spotify API.
    async def get_artist_singles(self, artist_id: ArtistId) -> list[Track]:
        """Get all singles (non-album tracks) for an artist from the database.

        Args:
            artist_id: Artist ID to get singles for

        Returns:
            List of Track entities without album association
        """
        return await self.track_repo.get_singles_by_artist(artist_id)

    # Remove a single track from DB.
    # Checks that the track exists and belongs to the given artist before deleting.
    async def remove_song(self, track_id: TrackId, artist_id: ArtistId) -> bool:
        """Remove a song from the database.

        Args:
            track_id: Track ID to remove
            artist_id: Artist ID (for validation)

        Returns:
            True if track was removed

        Raises:
            ValueError: If track not found or doesn't belong to artist
        """
        track = await self.track_repo.get_by_id(track_id)

        if not track:
            raise ValueError(f"Track not found: {track_id.value}")

        if track.artist_id != artist_id:
            raise ValueError(
                f"Track {track_id.value} does not belong to artist {artist_id.value}"
            )

        await self.track_repo.delete(track_id)
        logger.info(f"Removed track: {track.title} (id: {track_id.value})")

        return True

    # Bulk remove all singles for an artist. Use when user wants to
    # "clear" an artist's synced songs without deleting the artist itself.
    async def remove_all_artist_songs(self, artist_id: ArtistId) -> int:
        """Remove all singles (non-album tracks) for an artist.

        Args:
            artist_id: Artist ID to remove songs for

        Returns:
            Number of tracks removed
        """
        singles = await self.track_repo.get_singles_by_artist(artist_id)
        count = 0

        for track in singles:
            await self.track_repo.delete(track.id)
            count += 1

        logger.info(f"Removed {count} singles for artist {artist_id.value}")
        return count
