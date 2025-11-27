# Hey future me - this service handles AUTO-SYNC of Spotify data to our database!
# The key difference from FollowedArtistsService: this syncs to SEPARATE tables
# (spotify_artists, spotify_albums, spotify_tracks) NOT the local library tables.
# It also has DIFF-SYNC logic: compares Spotify with DB and removes unfollowed artists.
# Auto-sync triggers on page load with cooldown (no button needed).
"""Service for automatic Spotify data synchronization with diff logic."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

logger = logging.getLogger(__name__)


class SpotifySyncService:
    """Service for auto-syncing Spotify data with diff logic.

    This service handles:
    1. Auto-sync followed artists on page load (with cooldown)
    2. Diff-sync: add new follows, remove unfollows from DB
    3. Lazy-load artist albums when user navigates to artist page
    4. Lazy-load album tracks when user navigates to album page

    All data goes to spotify_* tables, NOT local library tables!
    """

    # Cooldown in minutes before re-syncing (avoid hammering Spotify API)
    ARTISTS_SYNC_COOLDOWN = 5
    ALBUMS_SYNC_COOLDOWN = 15
    TRACKS_SYNC_COOLDOWN = 60

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
    ) -> None:
        """Initialize sync service.

        Args:
            session: Database session
            spotify_client: Spotify client for API calls
        """
        self.repo = SpotifyBrowseRepository(session)
        self.spotify_client = spotify_client
        self.session = session

    # =========================================================================
    # FOLLOWED ARTISTS SYNC
    # =========================================================================

    async def sync_followed_artists(
        self, access_token: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync followed artists from Spotify with diff logic.

        This is the MAIN auto-sync method! Called on page load.
        - Checks cooldown first (skip if recently synced)
        - Fetches all followed artists from Spotify (paginated)
        - Compares with DB: adds new, removes unfollowed
        - Returns stats for UI display

        Args:
            access_token: Spotify OAuth access token
            force: Skip cooldown check

        Returns:
            Dict with sync stats (added, removed, total, etc.)
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "removed": 0,
            "unchanged": 0,
            "error": None,
            "skipped_cooldown": False,
        }

        try:
            # Check cooldown
            if not force and not await self.repo.should_sync("followed_artists"):
                stats["skipped_cooldown"] = True
                existing_count = await self.repo.count_artists()
                stats["total"] = existing_count
                logger.debug("Skipping followed artists sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="running",
            )
            await self.session.commit()

            # Fetch all followed artists from Spotify
            spotify_artists = await self._fetch_all_followed_artists(access_token)
            spotify_ids = {a["id"] for a in spotify_artists}

            # Get existing artist IDs from DB
            db_ids = await self.repo.get_all_artist_ids()

            # Diff calculation
            to_add = spotify_ids - db_ids
            to_remove = db_ids - spotify_ids
            unchanged = spotify_ids & db_ids

            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)
            stats["unchanged"] = len(unchanged)
            stats["total"] = len(spotify_ids)

            # Add new artists
            for artist_data in spotify_artists:
                if artist_data["id"] in to_add:
                    await self._upsert_artist(artist_data)

            # Update existing artists (in case name/image changed)
            for artist_data in spotify_artists:
                if artist_data["id"] in unchanged:
                    await self._upsert_artist(artist_data)

            # Remove unfollowed artists (CASCADE deletes albums/tracks)
            if to_remove:
                removed_count = await self.repo.delete_artists(to_remove)
                logger.info(f"Removed {removed_count} unfollowed artists from DB")

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="idle",
                items_synced=len(spotify_artists),
                items_added=len(to_add),
                items_removed=len(to_remove),
                cooldown_minutes=self.ARTISTS_SYNC_COOLDOWN,
            )

            await self.session.commit()
            stats["synced"] = True

            logger.info(
                f"Followed artists sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} removed"
            )

        except Exception as e:
            logger.error(f"Error syncing followed artists: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="error",
                error_message=str(e),
            )
            await self.session.commit()

        return stats

    async def _fetch_all_followed_artists(
        self, access_token: str
    ) -> list[dict[str, Any]]:
        """Fetch all followed artists from Spotify (handles pagination).

        Spotify uses cursor-based pagination. We loop until no more pages.
        """
        all_artists: list[dict[str, Any]] = []
        after_cursor: str | None = None

        while True:
            response = await self.spotify_client.get_followed_artists(
                access_token=access_token,
                limit=50,
                after=after_cursor,
            )

            artists_data = response.get("artists", {})
            items = artists_data.get("items", [])

            if not items:
                break

            all_artists.extend(items)

            cursors = artists_data.get("cursors", {})
            after_cursor = cursors.get("after")

            if not after_cursor:
                break

        return all_artists

    async def _upsert_artist(self, artist_data: dict[str, Any]) -> None:
        """Insert or update a Spotify artist in DB."""
        spotify_id = artist_data["id"]
        name = artist_data.get("name", "Unknown")
        genres = artist_data.get("genres", [])
        images = artist_data.get("images", [])
        popularity = artist_data.get("popularity")
        followers = artist_data.get("followers", {})
        follower_count = followers.get("total")

        # Pick medium-sized image (index 1) or first available
        image_url = None
        if images:
            preferred = images[1] if len(images) > 1 else images[0]
            image_url = preferred.get("url")

        await self.repo.upsert_artist(
            spotify_id=spotify_id,
            name=name,
            image_url=image_url,
            genres=genres,
            popularity=popularity,
            follower_count=follower_count,
        )

    # =========================================================================
    # ARTIST ALBUMS SYNC
    # =========================================================================

    async def sync_artist_albums(
        self, access_token: str, artist_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync albums for a specific artist from Spotify.

        Called when user navigates to artist detail page.
        Lazy-loads albums only when needed.

        Args:
            access_token: Spotify OAuth access token
            artist_id: Spotify artist ID
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "error": None,
            "skipped_cooldown": False,
        }

        try:
            # Check if artist exists
            artist = await self.repo.get_artist_by_id(artist_id)
            if not artist:
                stats["error"] = f"Artist {artist_id} not found"
                return stats

            # Check cooldown based on albums_synced_at
            if not force and artist.albums_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.ALBUMS_SYNC_COOLDOWN)
                if datetime.now(UTC) < artist.albums_synced_at + cooldown:
                    stats["skipped_cooldown"] = True
                    stats["total"] = await self.repo.count_albums_by_artist(artist_id)
                    return stats

            # Fetch albums from Spotify
            albums = await self._fetch_artist_albums(access_token, artist_id)

            for album_data in albums:
                await self._upsert_album(album_data, artist_id)
                stats["added"] += 1

            stats["total"] = len(albums)

            # Mark albums as synced
            await self.repo.set_albums_synced(artist_id)
            await self.session.commit()

            stats["synced"] = True
            logger.info(f"Synced {len(albums)} albums for artist {artist_id}")

        except Exception as e:
            logger.error(f"Error syncing albums for artist {artist_id}: {e}")
            stats["error"] = str(e)

        return stats

    async def _fetch_artist_albums(
        self, access_token: str, artist_id: str
    ) -> list[dict[str, Any]]:
        """Fetch all albums for an artist from Spotify.

        Note: The spotify_client.get_artist_albums method returns a list directly
        with a default limit of 50 albums.
        """
        # The client method already handles include_groups and returns a list
        albums = await self.spotify_client.get_artist_albums(
            artist_id=artist_id,
            access_token=access_token,
            limit=50,
        )
        return albums

    async def _upsert_album(self, album_data: dict[str, Any], artist_id: str) -> None:
        """Insert or update a Spotify album in DB."""
        spotify_id = album_data["id"]
        name = album_data.get("name", "Unknown")
        images = album_data.get("images", [])
        release_date = album_data.get("release_date")
        release_date_precision = album_data.get("release_date_precision")
        album_type = album_data.get("album_type", "album")
        total_tracks = album_data.get("total_tracks", 0)

        image_url = None
        if images:
            preferred = images[0]  # Largest image for album covers
            image_url = preferred.get("url")

        await self.repo.upsert_album(
            spotify_id=spotify_id,
            artist_id=artist_id,
            name=name,
            image_url=image_url,
            release_date=release_date,
            release_date_precision=release_date_precision,
            album_type=album_type,
            total_tracks=total_tracks,
        )

    # =========================================================================
    # ALBUM TRACKS SYNC
    # =========================================================================

    async def sync_album_tracks(
        self, access_token: str, album_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync tracks for a specific album from Spotify.

        Called when user navigates to album detail page.

        Args:
            access_token: Spotify OAuth access token
            album_id: Spotify album ID
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "error": None,
            "skipped_cooldown": False,
        }

        try:
            # Check if album exists
            album = await self.repo.get_album_by_id(album_id)
            if not album:
                stats["error"] = f"Album {album_id} not found"
                return stats

            # Check cooldown
            if not force and album.tracks_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.TRACKS_SYNC_COOLDOWN)
                if datetime.now(UTC) < album.tracks_synced_at + cooldown:
                    stats["skipped_cooldown"] = True
                    stats["total"] = await self.repo.count_tracks_by_album(album_id)
                    return stats

            # Fetch album with tracks from Spotify
            album_data = await self.spotify_client.get_album(
                access_token=access_token,
                album_id=album_id,
            )

            tracks = album_data.get("tracks", {}).get("items", [])

            for track_data in tracks:
                await self._upsert_track(track_data, album_id)
                stats["added"] += 1

            stats["total"] = len(tracks)

            # Mark tracks as synced
            await self.repo.set_tracks_synced(album_id)
            await self.session.commit()

            stats["synced"] = True
            logger.info(f"Synced {len(tracks)} tracks for album {album_id}")

        except Exception as e:
            logger.error(f"Error syncing tracks for album {album_id}: {e}")
            stats["error"] = str(e)

        return stats

    async def _upsert_track(self, track_data: dict[str, Any], album_id: str) -> None:
        """Insert or update a Spotify track in DB."""
        spotify_id = track_data["id"]
        name = track_data.get("name", "Unknown")
        track_number = track_data.get("track_number", 1)
        disc_number = track_data.get("disc_number", 1)
        duration_ms = track_data.get("duration_ms", 0)
        explicit = track_data.get("explicit", False)
        preview_url = track_data.get("preview_url")

        # ISRC from external_ids
        external_ids = track_data.get("external_ids", {})
        isrc = external_ids.get("isrc")

        await self.repo.upsert_track(
            spotify_id=spotify_id,
            album_id=album_id,
            name=name,
            track_number=track_number,
            disc_number=disc_number,
            duration_ms=duration_ms,
            explicit=explicit,
            preview_url=preview_url,
            isrc=isrc,
        )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_artists(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """Get followed artists from DB."""
        return await self.repo.get_all_artists(limit=limit, offset=offset)

    async def get_artist(self, spotify_id: str) -> Any | None:
        """Get a single artist from DB."""
        return await self.repo.get_artist_by_id(spotify_id)

    async def get_artist_albums(
        self, artist_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get albums for an artist from DB."""
        return await self.repo.get_albums_by_artist(
            artist_id=artist_id, limit=limit, offset=offset
        )

    async def get_album(self, spotify_id: str) -> Any | None:
        """Get a single album from DB."""
        return await self.repo.get_album_by_id(spotify_id)

    async def get_album_tracks(
        self, album_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get tracks for an album from DB."""
        return await self.repo.get_tracks_by_album(
            album_id=album_id, limit=limit, offset=offset
        )

    async def get_sync_status(self, sync_type: str) -> Any | None:
        """Get sync status for display."""
        return await self.repo.get_sync_status(sync_type)

    async def count_artists(self) -> int:
        """Get total artist count."""
        return await self.repo.count_artists()
