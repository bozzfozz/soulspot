"""Playlist sync worker for background playlist synchronization."""

import logging
from typing import TYPE_CHECKING, Any

from soulspot.application.use_cases import ImportSpotifyPlaylistUseCase
from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IPlaylistRepository,
    ISpotifyClient,
    ITrackRepository,
)

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

logger = logging.getLogger(__name__)


class PlaylistSyncWorker:
    """Worker for processing playlist sync jobs in the background.

    This worker:
    1. Monitors playlist sync queue
    2. Fetches playlist from Spotify
    3. Imports tracks into system
    4. Updates playlist metadata
    5. Handles periodic sync for active playlists
    """

    # Hey future me, same pattern as DownloadWorker - inject dependencies and create the use case here.
    # We need MORE repos than DownloadWorker (playlist, track, artist, album) because playlist import touches
    # all four entities! Don't register in __init__, let caller control when worker starts consuming jobs.
    def __init__(
        self,
        job_queue: JobQueue,
        spotify_client: ISpotifyClient,
        playlist_repository: IPlaylistRepository,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
    ) -> None:
        """Initialize playlist sync worker.

        Args:
            job_queue: Job queue for background processing
            spotify_client: Client for Spotify API
            playlist_repository: Repository for playlist persistence
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
            album_repository: Repository for album persistence
        """
        self._job_queue = job_queue
        self._use_case = ImportSpotifyPlaylistUseCase(
            spotify_client=spotify_client,
            playlist_repository=playlist_repository,
            track_repository=track_repository,
            artist_repository=artist_repository,
            album_repository=album_repository,
        )
        # Hey future me - token_manager wird via set_token_manager() gesetzt nach Construction!
        # So vermeiden wir zirkuläre Dependencies und Worker können erstellt werden
        # bevor app.state.db_token_manager bereit ist.
        self._token_manager: "DatabaseTokenManager | None" = None

    def set_token_manager(self, token_manager: "DatabaseTokenManager") -> None:
        """Set the token manager for getting Spotify access tokens.

        Called during app startup after DatabaseTokenManager is initialized.
        This allows the worker to get fresh tokens automatically instead of
        relying on tokens passed in job payload.

        Args:
            token_manager: Database-backed token manager
        """
        self._token_manager = token_manager

    # Yo, register this worker to handle PLAYLIST_SYNC jobs. Call after app startup when everything is ready.
    # If you register too early, jobs might fail because Spotify client isn't configured or DB isn't migrated!
    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(
            JobType.PLAYLIST_SYNC, self._handle_playlist_sync_job
        )

    # Listen up future me, this handler fetches a WHOLE playlist from Spotify and imports ALL tracks! For
    # huge playlists (1000+ tracks), this can take MINUTES and hit Spotify rate limits. We now use
    # DatabaseTokenManager to get fresh tokens automatically - no more expired tokens in job payload!
    # The fetch_all_tracks flag controls pagination - True means fetch every track (slow!), False might
    # fetch only first 100 (faster but incomplete). IMPORTANT: We DON'T fail the job if some tracks fail
    # to import! We log warnings but return success with error list. Partial sync is better than no sync.
    async def _handle_playlist_sync_job(self, job: Job) -> Any:
        """Handle a playlist sync job.

        Args:
            job: Job to process

        Returns:
            Sync result
        """
        # Extract payload
        playlist_id = job.payload.get("playlist_id")
        fetch_all_tracks = job.payload.get("fetch_all_tracks", True)

        if not playlist_id:
            raise ValueError("Missing playlist_id in job payload")

        # Get access token from TokenManager (preferred) or fall back to payload
        access_token = None
        if self._token_manager:
            token = await self._token_manager.get_valid_token()
            if token:
                access_token = token.access_token

        # Fall back to payload for backwards compatibility
        if not access_token:
            access_token = job.payload.get("access_token")

        if not access_token:
            raise ValueError(
                "No valid Spotify token available. "
                "Either set token_manager or provide access_token in payload."
            )

        # Execute use case
        from soulspot.application.use_cases.import_spotify_playlist import (
            ImportSpotifyPlaylistRequest,
        )

        request = ImportSpotifyPlaylistRequest(
            playlist_id=playlist_id,
            access_token=access_token,
            fetch_all_tracks=fetch_all_tracks,
        )

        response = await self._use_case.execute(request)

        # Check if sync had errors
        if response.tracks_failed > 0:
            # Log errors but don't fail the job
            logger.warning(
                "Playlist sync completed with %d errors: %s",
                len(response.errors),
                response.errors,
            )

        return {
            "playlist_id": str(response.playlist.id),
            "playlist_name": response.playlist.name,
            "tracks_imported": response.tracks_imported,
            "tracks_failed": response.tracks_failed,
            "errors": response.errors,
        }

    # Hey, this is the PUBLIC API for queueing a single playlist sync. With TokenManager, access_token
    # is now OPTIONAL - the worker will get a fresh token automatically! If you still pass access_token,
    # it's used as fallback for backwards compatibility. fetch_all_tracks defaults True because users
    # expect full sync! max_retries is 2 (not 3 like downloads) because playlist sync is less critical.
    async def enqueue_playlist_sync(
        self,
        playlist_id: str,
        access_token: str | None = None,
        fetch_all_tracks: bool = True,
        max_retries: int = 2,
    ) -> str:
        """Enqueue a playlist sync job.

        Args:
            playlist_id: Spotify playlist ID
            access_token: Optional Spotify access token (uses TokenManager if not provided)
            fetch_all_tracks: Whether to fetch all tracks
            max_retries: Maximum retry attempts

        Returns:
            Job ID
        """
        payload: dict[str, Any] = {
            "playlist_id": playlist_id,
            "fetch_all_tracks": fetch_all_tracks,
        }
        # Only include access_token if provided (for backwards compatibility)
        if access_token:
            payload["access_token"] = access_token

        return await self._job_queue.enqueue(
            job_type=JobType.PLAYLIST_SYNC,
            payload=payload,
            max_retries=max_retries,
        )

    # Yo, this is for "sync all my playlists" feature - queues multiple playlists in one call. With
    # TokenManager, we don't need to worry about token expiry anymore - each job gets a fresh token!
    # The jobs run in parallel (job queue handles concurrency), but Spotify rate limits might throttle them.
    async def enqueue_batch_sync(
        self,
        playlist_ids: list[str],
        access_token: str | None = None,
        fetch_all_tracks: bool = True,
        max_retries: int = 2,
    ) -> list[str]:
        """Enqueue multiple playlist sync jobs.

        Args:
            playlist_ids: Spotify playlist IDs
            access_token: Optional Spotify access token (uses TokenManager if not provided)
            fetch_all_tracks: Whether to fetch all tracks
            max_retries: Maximum retry attempts

        Returns:
            List of job IDs
        """
        job_ids = []
        for playlist_id in playlist_ids:
            job_id = await self.enqueue_playlist_sync(
                playlist_id=playlist_id,
                access_token=access_token,
                fetch_all_tracks=fetch_all_tracks,
                max_retries=max_retries,
            )
            job_ids.append(job_id)
        return job_ids

    def get_status(self) -> dict[str, Any]:
        """Get current worker status for monitoring/UI.

        Hey future me - diese Methode ist für den Worker-Status-Indicator.
        Gibt Infos zurück die das Frontend braucht.
        """
        return {
            "name": "Playlist Sync",
            "running": True,  # Worker is always "running" when registered
            "status": "idle",
            "has_token_manager": self._token_manager is not None,
        }
