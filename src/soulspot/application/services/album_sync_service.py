# AI-Model: Copilot
"""Service for syncing albums from followed artists on Spotify.

Hey future me - this service handles syncing albums from artists the user follows on Spotify!
The flow is: User clicks "sync albums" → we fetch ALL followed artists from our DB → for each
artist, fetch their albums from Spotify → create/update Album entities in our DB. This is separate
from tracks (which would be a much heavier sync). Albums can be removed via the DELETE endpoint.

GOTCHA: Spotify's get_artist_albums has pagination (default 50, max 50 per call). Prolific artists
like Bob Dylan have 500+ releases! Handle pagination for those edge cases.
GOTCHA: We use spotify_uri as the unique key for albums, same as artists.
GOTCHA: "album" and "single" types from Spotify are both synced (singles count as mini-albums).
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Album
from soulspot.domain.value_objects import AlbumId, ArtistId, SpotifyUri
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
)

logger = logging.getLogger(__name__)


class AlbumSyncService:
    """Service for syncing albums from followed artists on Spotify.

    Hey future me - this service syncs albums from artists the user follows on Spotify.
    It first fetches all artists from our local DB (those were synced via FollowedArtistsService),
    then for each artist, fetches their albums from Spotify API and creates/updates them locally.

    The sync is:
    1. Fetch all artists from local DB
    2. For each artist with spotify_uri, fetch albums from Spotify
    3. Create new albums or update existing ones (matched by spotify_uri)
    4. Return sync statistics

    We DON'T sync tracks here - that's a much heavier operation and should be optional!
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
    ) -> None:
        """Initialize album sync service.

        Args:
            session: Database session for Album/Artist repositories
            spotify_client: Spotify client for API calls
        """
        self.artist_repo = ArtistRepository(session)
        self.album_repo = AlbumRepository(session)
        self.spotify_client = spotify_client

    # Hey future me, this is the MAIN sync method! Fetches all local artists, then for each one,
    # fetches their albums from Spotify and syncs to our DB. This can be slow for users with many
    # followed artists (100+ artists × 10+ albums each = 1000+ album records). Consider rate
    # limiting or background task for production. Returns sync stats for UI feedback.
    async def sync_albums_for_followed_artists(
        self, access_token: str
    ) -> tuple[list[Album], dict[str, Any]]:
        """Sync albums from all followed artists on Spotify.

        Fetches all artists from local DB, then for each artist fetches their albums
        from Spotify and creates/updates them in the local database.

        Args:
            access_token: Spotify OAuth access token

        Returns:
            Tuple of (list of synced Album entities, sync statistics dict)

        Raises:
            httpx.HTTPError: If Spotify API request fails
        """
        all_albums: list[Album] = []
        stats = {
            "total_artists": 0,
            "artists_processed": 0,
            "albums_fetched": 0,
            "albums_created": 0,
            "albums_updated": 0,
            "errors": 0,
        }

        # Fetch all artists from local DB (unlimited - we want ALL followed artists)
        # Hey future me - this fetches ALL local artists, not just 100! Using high limit
        # to get all artists synced via FollowedArtistsService. If you have 1000+ artists,
        # consider pagination or streaming approach to avoid memory issues.
        artists = await self.artist_repo.list_all(limit=10000, offset=0)
        stats["total_artists"] = len(artists)

        logger.info(f"Starting album sync for {len(artists)} local artists")

        for artist in artists:
            # Skip artists without Spotify URI (manually added artists)
            if not artist.spotify_uri:
                logger.debug(f"Skipping artist {artist.name} - no Spotify URI")
                continue

            try:
                albums = await self._sync_artist_albums(
                    artist_id=artist.id,
                    spotify_artist_id=artist.spotify_uri.resource_id,
                    access_token=access_token,
                    stats=stats,
                )
                all_albums.extend(albums)
                stats["artists_processed"] += 1
            except Exception as e:
                logger.error(f"Failed to sync albums for artist {artist.name}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Album sync complete: {stats['artists_processed']} artists processed, "
            f"{stats['albums_created']} albums created, {stats['albums_updated']} updated, "
            f"{stats['errors']} errors"
        )

        return all_albums, stats

    # Hey future me, this syncs albums for a SINGLE artist! Spotify's get_artist_albums returns
    # a list of album objects with: id, name, uri, release_date, album_type, images, etc.
    # We extract what we need and create/update Album entities. Pagination is handled by
    # SpotifyClient.get_artist_albums (default limit 50, should cover most artists).
    async def _sync_artist_albums(
        self,
        artist_id: ArtistId,
        spotify_artist_id: str,
        access_token: str,
        stats: dict[str, Any],
    ) -> list[Album]:
        """Sync albums for a single artist from Spotify.

        Args:
            artist_id: Local Artist ID (UUID)
            spotify_artist_id: Spotify artist ID (base62 string)
            access_token: Spotify OAuth access token
            stats: Shared stats dict to update

        Returns:
            List of synced Album entities
        """
        synced_albums: list[Album] = []

        # Fetch albums from Spotify (handles pagination internally)
        albums_data = await self.spotify_client.get_artist_albums(
            artist_id=spotify_artist_id,
            access_token=access_token,
            limit=50,  # Max allowed by Spotify API
        )

        for album_data in albums_data:
            try:
                album, was_created = await self._process_album_data(
                    album_data=album_data,
                    artist_id=artist_id,
                )
                synced_albums.append(album)
                stats["albums_fetched"] += 1
                if was_created:
                    stats["albums_created"] += 1
                else:
                    stats["albums_updated"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to process album {album_data.get('name', 'unknown')}: {e}"
                )
                stats["errors"] += 1

        return synced_albums

    # Hey future me, this processes a single album from Spotify API response! We use spotify_uri
    # as the unique key to prevent duplicates. If album exists, we update title/release_year if
    # changed. If new, we create it. Spotify album object has: id, name, uri, release_date,
    # album_type (album/single), images (list of artwork URLs), total_tracks, etc.
    async def _process_album_data(
        self,
        album_data: dict[str, Any],
        artist_id: ArtistId,
    ) -> tuple[Album, bool]:
        """Process a single album from Spotify API response.

        Args:
            album_data: Album data from Spotify API
            artist_id: Local Artist ID to associate album with

        Returns:
            Tuple of (Album entity, was_created boolean)

        Raises:
            ValueError: If album data is invalid
        """
        spotify_id = album_data.get("id")
        title = album_data.get("name")
        release_date = album_data.get("release_date", "")

        if not spotify_id or not title:
            raise ValueError(f"Invalid album data: missing id or name - {album_data}")

        spotify_uri = SpotifyUri.from_string(f"spotify:album:{spotify_id}")

        # Parse release year from date (YYYY, YYYY-MM, or YYYY-MM-DD format)
        # Hey future me - Spotify release_date can be just year (1999), month (1999-05),
        # or full date (1999-05-01). We only want the year. Some albums have no release date
        # at all (mainly weird compilations), so handle that gracefully!
        release_year: int | None = None
        if release_date:
            try:
                release_year = int(release_date[:4])
                # Validate year is reasonable (1900-2100 per Album entity validation)
                if release_year < 1900 or release_year > 2100:
                    release_year = None
            except (ValueError, IndexError):
                logger.warning(f"Could not parse release year from: {release_date}")

        # Check if album already exists
        existing_album = await self.album_repo.get_by_spotify_uri(spotify_uri)

        if existing_album:
            # Update existing album if anything changed
            needs_update = False
            if existing_album.title != title:
                existing_album.title = title
                needs_update = True
            if existing_album.release_year != release_year:
                existing_album.release_year = release_year
                needs_update = True

            if needs_update:
                await self.album_repo.update(existing_album)
                logger.debug(f"Updated album: {title}")
            return existing_album, False

        # Create new album
        new_album = Album(
            id=AlbumId.generate(),
            title=title,
            artist_id=artist_id,
            release_year=release_year,
            spotify_uri=spotify_uri,
            metadata_sources={"title": "spotify", "release_year": "spotify"},
        )

        await self.album_repo.add(new_album)
        logger.info(f"Created new album: {title}")

        return new_album, True

    # Hey future me, this syncs albums for a SINGLE artist by their local ID! Useful when user
    # clicks "sync albums" for one specific artist instead of all followed artists. Returns
    # just that artist's albums and stats.
    async def sync_albums_for_artist(
        self, artist_id: ArtistId, access_token: str
    ) -> tuple[list[Album], dict[str, Any]]:
        """Sync albums for a single artist from Spotify.

        Args:
            artist_id: Local Artist ID (UUID)
            access_token: Spotify OAuth access token

        Returns:
            Tuple of (list of synced Album entities, sync statistics dict)

        Raises:
            ValueError: If artist not found or has no Spotify URI
            httpx.HTTPError: If Spotify API request fails
        """
        stats = {
            "albums_fetched": 0,
            "albums_created": 0,
            "albums_updated": 0,
            "errors": 0,
        }

        # Get artist from local DB
        artist = await self.artist_repo.get_by_id(artist_id)
        if not artist:
            raise ValueError(f"Artist not found: {artist_id}")
        if not artist.spotify_uri:
            raise ValueError(f"Artist {artist.name} has no Spotify URI")

        albums = await self._sync_artist_albums(
            artist_id=artist.id,
            spotify_artist_id=artist.spotify_uri.resource_id,
            access_token=access_token,
            stats=stats,
        )

        logger.info(
            f"Synced {len(albums)} albums for artist {artist.name}: "
            f"{stats['albums_created']} created, {stats['albums_updated']} updated"
        )

        return albums, stats
