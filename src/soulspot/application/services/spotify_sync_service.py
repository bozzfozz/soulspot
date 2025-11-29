# Hey future me - this service handles AUTO-SYNC of Spotify data to our database!
# The key difference from FollowedArtistsService: this syncs to SEPARATE tables
# (spotify_artists, spotify_albums, spotify_tracks) NOT the local library tables.
# It also has DIFF-SYNC logic: compares Spotify with DB and removes unfollowed artists.
# Auto-sync triggers on page load with cooldown (no button needed).
#
# What syncs where:
# - Followed Artists → spotify_artists table (auto-sync every 5 min)
# - User Playlists → playlists table (auto-sync every 10 min)
# - Liked Songs → playlists table (special playlist with is_liked_songs=True)
# - Saved Albums → spotify_albums table (is_saved=True flag)
#
# Image Download:
# - When download_images setting is True, we download and store images locally
# - Stored in artwork/spotify/{artists|albums|playlists}/{id}.webp
# - The _path columns store the relative path, _url columns keep the CDN URL
"""Service for automatic Spotify data synchronization with diff logic."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.models import ensure_utc_aware
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

if TYPE_CHECKING:
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.spotify_image_service import SpotifyImageService

logger = logging.getLogger(__name__)


class SpotifySyncService:
    """Service for auto-syncing Spotify data with diff logic.

    This service handles:
    1. Auto-sync followed artists on page load (with cooldown)
    2. Auto-sync user playlists (with cooldown)
    3. Auto-sync Liked Songs (special playlist)
    4. Auto-sync Saved Albums (albums the user explicitly saved)
    5. Diff-sync: add new follows, remove unfollows from DB
    6. Lazy-load artist albums when user navigates to artist page
    7. Lazy-load album tracks when user navigates to album page
    8. Download and store images locally (optional)

    All Spotify data goes to spotify_* tables or playlists table,
    NOT local library tables!
    """

    # Cooldown in minutes before re-syncing (avoid hammering Spotify API)
    ARTISTS_SYNC_COOLDOWN = 5
    PLAYLISTS_SYNC_COOLDOWN = 10
    ALBUMS_SYNC_COOLDOWN = 15
    TRACKS_SYNC_COOLDOWN = 60

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
        image_service: "SpotifyImageService | None" = None,
        settings_service: "AppSettingsService | None" = None,
    ) -> None:
        """Initialize sync service.

        Args:
            session: Database session
            spotify_client: Spotify client for API calls
            image_service: Optional image service for downloading images
            settings_service: Optional settings service for sync config
        """
        self.repo = SpotifyBrowseRepository(session)
        self.spotify_client = spotify_client
        self.session = session
        self._image_service = image_service
        self._settings_service = settings_service

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
            "skipped_disabled": False,
        }

        try:
            # Check if artists sync is enabled
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_artists_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Artists sync is disabled in settings")
                return stats

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

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Add new artists
            for artist_data in spotify_artists:
                if artist_data["id"] in to_add:
                    await self._upsert_artist(
                        artist_data, download_images=should_download_images
                    )

            # Update existing artists (in case name/image changed)
            for artist_data in spotify_artists:
                if artist_data["id"] in unchanged:
                    await self._upsert_artist(
                        artist_data, download_images=should_download_images
                    )

            # Remove unfollowed artists (CASCADE deletes albums/tracks)
            if to_remove:
                # Check if we should remove unfollowed artists
                should_remove = True
                if self._settings_service:
                    should_remove = (
                        await self._settings_service.should_remove_unfollowed_artists()
                    )

                if should_remove:
                    # Clean up images before deleting artists
                    if self._image_service:
                        for spotify_id in to_remove:
                            await self._image_service.delete_image_async(
                                f"spotify/artists/{spotify_id}.webp"
                            )

                    removed_count = await self.repo.delete_artists(to_remove)
                    logger.info(f"Removed {removed_count} unfollowed artists from DB")
                else:
                    stats["removed"] = 0  # Didn't actually remove

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="followed_artists",
                status="idle",
                items_synced=len(spotify_artists),
                items_added=len(to_add),
                items_removed=stats["removed"],
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

    async def _upsert_artist(
        self, artist_data: dict[str, Any], download_images: bool = False
    ) -> None:
        """Insert or update a Spotify artist in DB.

        Args:
            artist_data: Artist data from Spotify API
            download_images: Whether to download profile image locally
        """
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

        # Download image if enabled
        image_path = None
        if download_images and image_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_artist_by_id(spotify_id)
            existing_url = existing.image_url if existing else None
            existing_path = existing.image_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, image_url, existing_path
            ):
                image_path = await self._image_service.download_artist_image(
                    spotify_id, image_url
                )
            elif existing_path:
                image_path = existing_path  # Keep existing path

        await self.repo.upsert_artist(
            spotify_id=spotify_id,
            name=name,
            image_url=image_url,
            image_path=image_path,
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
            # Hey future me - use ensure_utc_aware() because SQLite returns naive datetimes!
            if not force and artist.albums_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.ALBUMS_SYNC_COOLDOWN)
                if datetime.now(UTC) < ensure_utc_aware(artist.albums_synced_at) + cooldown:
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
            # Hey future me - use ensure_utc_aware() because SQLite returns naive datetimes!
            if not force and album.tracks_synced_at:
                from datetime import timedelta

                cooldown = timedelta(minutes=self.TRACKS_SYNC_COOLDOWN)
                if datetime.now(UTC) < ensure_utc_aware(album.tracks_synced_at) + cooldown:
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

    # =========================================================================
    # USER PLAYLISTS SYNC
    # =========================================================================
    # Hey future me - this syncs playlists from Spotify to our playlists table!
    # Playlists are different from artists/albums:
    # - They go to the PLAYLISTS table (not a separate spotify_playlists table)
    # - They have source='SPOTIFY' to distinguish from manual playlists
    # - The spotify_uri column identifies them uniquely
    # =========================================================================

    async def sync_user_playlists(
        self, access_token: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's playlists from Spotify with diff logic.

        Similar to artists sync but for playlists. Called on page load.
        Checks settings to see if playlist sync is enabled.

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
            "skipped_disabled": False,
        }

        try:
            # Check if playlist sync is enabled
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_playlists_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Playlist sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("user_playlists"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_spotify_playlists()
                logger.debug("Skipping user playlists sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="running",
            )
            await self.session.commit()

            # Fetch all playlists from Spotify
            spotify_playlists = await self._fetch_all_user_playlists(access_token)
            spotify_uris = {f"spotify:playlist:{p['id']}" for p in spotify_playlists}

            # Get existing Spotify playlist URIs from DB
            db_uris = await self.repo.get_spotify_playlist_uris()

            # Diff calculation
            to_add = spotify_uris - db_uris
            to_remove = db_uris - spotify_uris
            unchanged = spotify_uris & db_uris

            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)
            stats["unchanged"] = len(unchanged)
            stats["total"] = len(spotify_uris)

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Add new playlists
            for playlist_data in spotify_playlists:
                spotify_uri = f"spotify:playlist:{playlist_data['id']}"
                if spotify_uri in to_add or spotify_uri in unchanged:
                    await self._upsert_playlist(
                        playlist_data, download_images=should_download_images
                    )

            # Remove playlists that no longer exist on Spotify
            should_remove = True
            if to_remove:
                if self._settings_service:
                    should_remove = await self._settings_service.should_remove_unfollowed_playlists()

                if should_remove:
                    removed_count = await self.repo.delete_playlists_by_uris(to_remove)
                    logger.info(
                        f"Removed {removed_count} deleted Spotify playlists from DB"
                    )

                    # Cleanup orphaned images
                    if self._image_service:
                        for uri in to_remove:
                            playlist_id = uri.replace("spotify:playlist:", "")
                            await self._image_service.delete_image_async(
                                f"spotify/playlists/{playlist_id}.webp"
                            )
            else:
                should_remove = False  # No playlists to remove

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="idle",
                items_synced=len(spotify_playlists),
                items_added=len(to_add),
                items_removed=len(to_remove) if should_remove else 0,
                cooldown_minutes=self.PLAYLISTS_SYNC_COOLDOWN,
            )

            await self.session.commit()
            stats["synced"] = True

            logger.info(
                f"User playlists sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} removed"
            )

        except Exception as e:
            logger.error(f"Error syncing user playlists: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="user_playlists",
                status="error",
                error_message=str(e),
            )
            await self.session.commit()

        return stats

    async def _fetch_all_user_playlists(
        self, access_token: str
    ) -> list[dict[str, Any]]:
        """Fetch all user playlists from Spotify (handles pagination)."""
        all_playlists: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_client.get_user_playlists(
                access_token=access_token,
                limit=limit,
                offset=offset,
            )

            items = response.get("items", [])
            if not items:
                break

            all_playlists.extend(items)

            # Check if there are more pages
            if response.get("next") is None:
                break

            offset += limit

        return all_playlists

    async def _upsert_playlist(
        self,
        playlist_data: dict[str, Any],
        download_images: bool = False,
    ) -> None:
        """Insert or update a Spotify playlist in DB.

        Args:
            playlist_data: Playlist data from Spotify API
            download_images: Whether to download cover image locally
        """
        spotify_id = playlist_data["id"]
        spotify_uri = f"spotify:playlist:{spotify_id}"
        name = playlist_data.get("name", "Unknown")
        description = playlist_data.get("description", "")
        images = playlist_data.get("images", [])

        # Get cover URL (first/largest image)
        cover_url = None
        if images:
            cover_url = images[0].get("url")

        # Download image if enabled
        cover_path = None
        if download_images and cover_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_playlist_by_uri(spotify_uri)
            existing_url = existing.cover_url if existing else None
            existing_path = existing.cover_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, cover_url, existing_path
            ):
                cover_path = await self._image_service.download_playlist_image(
                    spotify_id, cover_url
                )
            elif existing_path:
                cover_path = existing_path  # Keep existing path

        await self.repo.upsert_playlist(
            spotify_uri=spotify_uri,
            name=name,
            description=description,
            cover_url=cover_url,
            cover_path=cover_path,
            source="SPOTIFY",
        )

    # =========================================================================
    # LIKED SONGS SYNC
    # =========================================================================
    # Hey future me - "Liked Songs" is a SPECIAL playlist!
    # - It's not a real Spotify playlist (no playlist ID)
    # - We create a local playlist with is_liked_songs=True
    # - Tracks come from GET /me/tracks endpoint
    # =========================================================================

    async def sync_liked_songs(
        self, access_token: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's Liked Songs from Spotify.

        Creates/updates a special playlist with is_liked_songs=True.
        This playlist doesn't have a Spotify URI since "Liked Songs"
        isn't a real playlist on Spotify.

        Args:
            access_token: Spotify OAuth access token
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
            "skipped_disabled": False,
        }

        try:
            # Check if Liked Songs sync is enabled
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_liked_songs_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Liked Songs sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("liked_songs"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_liked_songs_tracks()
                logger.debug("Skipping Liked Songs sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="running",
            )
            await self.session.commit()

            # Fetch all liked songs from Spotify
            liked_tracks = await self._fetch_all_liked_songs(access_token)
            stats["total"] = len(liked_tracks)

            # Ensure the Liked Songs playlist exists
            liked_playlist = await self.repo.get_or_create_liked_songs_playlist()

            # Sync tracks to playlist
            # Hey - we replace all tracks because Spotify doesn't give us diff info
            added_count = await self.repo.sync_liked_songs_tracks(
                playlist_id=liked_playlist.id,
                tracks=liked_tracks,
            )
            stats["added"] = added_count

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="idle",
                items_synced=len(liked_tracks),
                items_added=added_count,
                cooldown_minutes=self.PLAYLISTS_SYNC_COOLDOWN,
            )

            await self.session.commit()
            stats["synced"] = True

            logger.info(f"Liked Songs sync complete: {stats['total']} tracks")

        except Exception as e:
            logger.error(f"Error syncing Liked Songs: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="liked_songs",
                status="error",
                error_message=str(e),
            )
            await self.session.commit()

        return stats

    async def _fetch_all_liked_songs(self, access_token: str) -> list[dict[str, Any]]:
        """Fetch all liked songs from Spotify (handles pagination).

        Returns list of track data with added_at timestamp.
        """
        all_tracks: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_client.get_saved_tracks(
                access_token=access_token,
                limit=limit,
                offset=offset,
            )

            items = response.get("items", [])
            if not items:
                break

            # Extract track data with added_at
            for item in items:
                track_data = item.get("track", {})
                track_data["added_at"] = item.get("added_at")
                all_tracks.append(track_data)

            # Check if there are more pages
            if response.get("next") is None:
                break

            offset += limit

        return all_tracks

    # =========================================================================
    # SAVED ALBUMS SYNC
    # =========================================================================
    # Hey future me - "Saved Albums" are albums the user explicitly saved!
    # Different from artist albums which come from followed artists.
    # We set is_saved=True on these albums in spotify_albums table.
    # This requires ensuring the artist exists first (create if not followed).
    # =========================================================================

    async def sync_saved_albums(
        self, access_token: str, force: bool = False
    ) -> dict[str, Any]:
        """Sync user's Saved Albums from Spotify.

        Saved albums are albums the user explicitly saved to their library.
        These get is_saved=True flag so they persist even if artist is unfollowed.

        Args:
            access_token: Spotify OAuth access token
            force: Skip cooldown check

        Returns:
            Dict with sync stats
        """
        stats: dict[str, Any] = {
            "synced": False,
            "total": 0,
            "added": 0,
            "removed": 0,
            "error": None,
            "skipped_cooldown": False,
            "skipped_disabled": False,
        }

        try:
            # Check if Saved Albums sync is enabled
            if (
                self._settings_service
                and not await self._settings_service.is_spotify_saved_albums_sync_enabled()
            ):
                stats["skipped_disabled"] = True
                logger.debug("Saved Albums sync is disabled in settings")
                return stats

            # Check cooldown
            if not force and not await self.repo.should_sync("saved_albums"):
                stats["skipped_cooldown"] = True
                stats["total"] = await self.repo.count_saved_albums()
                logger.debug("Skipping Saved Albums sync (cooldown)")
                return stats

            # Mark sync as running
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="running",
            )
            await self.session.commit()

            # Fetch all saved albums from Spotify
            saved_albums = await self._fetch_all_saved_albums(access_token)
            spotify_album_ids = {a["album"]["id"] for a in saved_albums}

            # Get existing saved album IDs from DB
            db_saved_ids = await self.repo.get_saved_album_ids()

            # Diff calculation
            to_add = spotify_album_ids - db_saved_ids
            to_remove = db_saved_ids - spotify_album_ids

            stats["total"] = len(spotify_album_ids)
            stats["added"] = len(to_add)
            stats["removed"] = len(to_remove)

            # Check if image download is enabled
            should_download_images = False
            if self._settings_service and self._image_service:
                should_download_images = (
                    await self._settings_service.should_download_images()
                )

            # Process saved albums
            for item in saved_albums:
                album_data = item["album"]

                # Ensure artist exists (create minimal entry if not followed)
                artists = album_data.get("artists", [])
                if artists:
                    artist_data = artists[0]  # Primary artist
                    await self._ensure_artist_exists(artist_data)
                    artist_id = artist_data["id"]
                else:
                    continue  # Skip albums without artists

                # Upsert album with is_saved=True
                await self._upsert_saved_album(
                    album_data,
                    artist_id,
                    download_images=should_download_images,
                )

            # Remove is_saved flag from albums no longer saved
            if to_remove:
                await self.repo.unmark_albums_as_saved(to_remove)
                logger.info(f"Unmarked {len(to_remove)} albums as no longer saved")

            # Update sync status
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="idle",
                items_synced=len(saved_albums),
                items_added=len(to_add),
                items_removed=len(to_remove),
                cooldown_minutes=self.ALBUMS_SYNC_COOLDOWN,
            )

            await self.session.commit()
            stats["synced"] = True

            logger.info(
                f"Saved Albums sync complete: {stats['total']} total, "
                f"+{stats['added']} added, -{stats['removed']} unmarked"
            )

        except Exception as e:
            logger.error(f"Error syncing Saved Albums: {e}")
            stats["error"] = str(e)
            await self.repo.update_sync_status(
                sync_type="saved_albums",
                status="error",
                error_message=str(e),
            )
            await self.session.commit()

        return stats

    async def _fetch_all_saved_albums(self, access_token: str) -> list[dict[str, Any]]:
        """Fetch all saved albums from Spotify (handles pagination).

        Returns list of items with album data and added_at timestamp.
        """
        all_albums: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            response = await self.spotify_client.get_saved_albums(
                access_token=access_token,
                limit=limit,
                offset=offset,
            )

            items = response.get("items", [])
            if not items:
                break

            all_albums.extend(items)

            # Check if there are more pages
            if response.get("next") is None:
                break

            offset += limit

        return all_albums

    async def _ensure_artist_exists(self, artist_data: dict[str, Any]) -> None:
        """Ensure an artist exists in DB (create minimal entry if not).

        Called when syncing saved albums where the artist might not be followed.
        Creates a minimal artist entry without full metadata.

        Args:
            artist_data: Minimal artist data from album (id, name)
        """
        spotify_id = artist_data["id"]

        # Check if artist exists
        existing = await self.repo.get_artist_by_id(spotify_id)
        if existing:
            return  # Artist exists, nothing to do

        # Create minimal artist entry
        name = artist_data.get("name", "Unknown")
        await self.repo.upsert_artist(
            spotify_id=spotify_id,
            name=name,
            image_url=None,
            genres=[],
            popularity=None,
            follower_count=None,
        )
        logger.debug(f"Created minimal artist entry for: {name} ({spotify_id})")

    async def _upsert_saved_album(
        self,
        album_data: dict[str, Any],
        artist_id: str,
        download_images: bool = False,
    ) -> None:
        """Insert or update a saved album in DB with is_saved=True.

        Args:
            album_data: Album data from Spotify API
            artist_id: Spotify artist ID
            download_images: Whether to download cover image locally
        """
        spotify_id = album_data["id"]
        name = album_data.get("name", "Unknown")
        images = album_data.get("images", [])
        release_date = album_data.get("release_date")
        release_date_precision = album_data.get("release_date_precision")
        album_type = album_data.get("album_type", "album")
        total_tracks = album_data.get("total_tracks", 0)

        # Get cover URL
        image_url = None
        if images:
            image_url = images[0].get("url")

        # Download image if enabled
        image_path = None
        if download_images and image_url and self._image_service:
            # Check if image changed before downloading
            existing = await self.repo.get_album_by_id(spotify_id)
            existing_url = existing.image_url if existing else None
            existing_path = existing.image_path if existing else None

            if await self._image_service.should_redownload(
                existing_url, image_url, existing_path
            ):
                image_path = await self._image_service.download_album_image(
                    spotify_id, image_url
                )
            elif existing_path:
                image_path = existing_path

        await self.repo.upsert_album(
            spotify_id=spotify_id,
            artist_id=artist_id,
            name=name,
            image_url=image_url,
            image_path=image_path,
            release_date=release_date,
            release_date_precision=release_date_precision,
            album_type=album_type,
            total_tracks=total_tracks,
            is_saved=True,
        )

    # =========================================================================
    # IMAGE DOWNLOAD INTEGRATION
    # =========================================================================

    async def _download_artist_image_if_needed(
        self,
        spotify_id: str,
        new_url: str | None,
        existing_url: str | None = None,
        existing_path: str | None = None,
    ) -> str | None:
        """Download artist image if enabled and needed.

        Args:
            spotify_id: Spotify artist ID
            new_url: New image URL from Spotify
            existing_url: Previously stored URL (for comparison)
            existing_path: Previously stored local path

        Returns:
            Local path to image, or None if not downloaded
        """
        if not self._image_service or not self._settings_service:
            return None

        should_download = await self._settings_service.should_download_images()
        if not should_download:
            return existing_path  # Keep existing path if any

        if not new_url:
            return None

        if await self._image_service.should_redownload(
            existing_url, new_url, existing_path
        ):
            return await self._image_service.download_artist_image(spotify_id, new_url)

        return existing_path

    # =========================================================================
    # FULL SYNC (ALL ENABLED SYNCS)
    # =========================================================================

    async def run_full_sync(
        self, access_token: str, force: bool = False
    ) -> dict[str, Any]:
        """Run all enabled sync operations.

        Convenience method to run artists, playlists, liked songs, and saved albums
        sync in sequence. Checks settings for each sync type.

        Args:
            access_token: Spotify OAuth access token
            force: Skip cooldown checks

        Returns:
            Dict with results from each sync operation
        """
        results: dict[str, Any] = {
            "artists": None,
            "playlists": None,
            "liked_songs": None,
            "saved_albums": None,
        }

        # Artists sync
        results["artists"] = await self.sync_followed_artists(access_token, force=force)

        # Playlists sync
        results["playlists"] = await self.sync_user_playlists(access_token, force=force)

        # Liked Songs sync
        results["liked_songs"] = await self.sync_liked_songs(access_token, force=force)

        # Saved Albums sync
        results["saved_albums"] = await self.sync_saved_albums(
            access_token, force=force
        )

        return results
