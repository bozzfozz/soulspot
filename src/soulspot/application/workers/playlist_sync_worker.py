"""Playlist sync worker for background playlist synchronization."""

import logging
from typing import Any

from soulspot.application.use_cases import ImportSpotifyPlaylistUseCase
from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IPlaylistRepository,
    ISpotifyClient,
    ITrackRepository,
)

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

    # Yo, register this worker to handle PLAYLIST_SYNC jobs. Call after app startup when everything is ready.
    # If you register too early, jobs might fail because Spotify client isn't configured or DB isn't migrated!
    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(
            JobType.PLAYLIST_SYNC, self._handle_playlist_sync_job
        )

    # Listen up future me, this handler fetches a WHOLE playlist from Spotify and imports ALL tracks! For
    # huge playlists (1000+ tracks), this can take MINUTES and hit Spotify rate limits. The access_token
    # MUST be valid - if it's expired, job fails immediately. The fetch_all_tracks flag controls pagination -
    # True means fetch every track (slow!), False might fetch only first 100 (faster but incomplete). IMPORTANT:
    # We DON'T fail the job if some tracks fail to import! We log warnings but return success with error list.
    # This is because partial sync is better than no sync - maybe track #500 is broken on Spotify, don't fail the whole thing!
    async def _handle_playlist_sync_job(self, job: Job) -> Any:
        """Handle a playlist sync job.

        Args:
            job: Job to process

        Returns:
            Sync result
        """
        # Extract payload
        playlist_id = job.payload.get("playlist_id")
        access_token = job.payload.get("access_token")
        fetch_all_tracks = job.payload.get("fetch_all_tracks", True)

        if not playlist_id:
            raise ValueError("Missing playlist_id in job payload")
        if not access_token:
            raise ValueError("Missing access_token in job payload")

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

    # Hey, this is the PUBLIC API for queueing a single playlist sync. The access_token is passed as payload
    # (NOT in job metadata) because tokens are specific to this sync operation. fetch_all_tracks defaults True
    # because users expect full sync! max_retries is 2 (not 3 like downloads) because playlist sync is less
    # critical - if it fails twice, user can manually retry. Don't set max_retries too high or you'll spam
    # Spotify API and get rate-limited! Returns job_id for tracking progress.
    async def enqueue_playlist_sync(
        self,
        playlist_id: str,
        access_token: str,
        fetch_all_tracks: bool = True,
        max_retries: int = 2,
    ) -> str:
        """Enqueue a playlist sync job.

        Args:
            playlist_id: Spotify playlist ID
            access_token: Spotify access token
            fetch_all_tracks: Whether to fetch all tracks
            max_retries: Maximum retry attempts

        Returns:
            Job ID
        """
        return await self._job_queue.enqueue(
            job_type=JobType.PLAYLIST_SYNC,
            payload={
                "playlist_id": playlist_id,
                "access_token": access_token,
                "fetch_all_tracks": fetch_all_tracks,
            },
            max_retries=max_retries,
        )

    # Yo, this is for "sync all my playlists" feature - queues multiple playlists in one call. It loops and
    # calls enqueue_playlist_sync for each one - simple! But CAREFUL: if you pass 100 playlist_ids, you're
    # creating 100 jobs that all need the same access_token. If token expires before jobs run, they ALL fail!
    # Consider checking token expiry first and refreshing if needed. The jobs run in parallel (job queue handles
    # concurrency), but Spotify rate limits might throttle them. Returns list of job_ids in same order as input.
    async def enqueue_batch_sync(
        self,
        playlist_ids: list[str],
        access_token: str,
        fetch_all_tracks: bool = True,
        max_retries: int = 2,
    ) -> list[str]:
        """Enqueue multiple playlist sync jobs.

        Args:
            playlist_ids: Spotify playlist IDs
            access_token: Spotify access token
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
