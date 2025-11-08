"""Playlist sync worker for background playlist synchronization."""

from typing import Any

from soulspot.application.use_cases import ImportSpotifyPlaylistUseCase
from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import IPlaylistRepository, ISpotifyClient, ITrackRepository


class PlaylistSyncWorker:
    """Worker for processing playlist sync jobs in the background.

    This worker:
    1. Monitors playlist sync queue
    2. Fetches playlist from Spotify
    3. Imports tracks into system
    4. Updates playlist metadata
    5. Handles periodic sync for active playlists
    """

    def __init__(
        self,
        job_queue: JobQueue,
        spotify_client: ISpotifyClient,
        playlist_repository: IPlaylistRepository,
        track_repository: ITrackRepository,
    ) -> None:
        """Initialize playlist sync worker.

        Args:
            job_queue: Job queue for background processing
            spotify_client: Client for Spotify API
            playlist_repository: Repository for playlist persistence
            track_repository: Repository for track persistence
        """
        self._job_queue = job_queue
        self._use_case = ImportSpotifyPlaylistUseCase(
            spotify_client=spotify_client,
            playlist_repository=playlist_repository,
            track_repository=track_repository,
        )

    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(JobType.PLAYLIST_SYNC, self._handle_playlist_sync_job)

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
        from soulspot.application.use_cases.import_spotify_playlist import ImportSpotifyPlaylistRequest

        request = ImportSpotifyPlaylistRequest(
            playlist_id=playlist_id,
            access_token=access_token,
            fetch_all_tracks=fetch_all_tracks,
        )

        response = await self._use_case.execute(request)

        # Check if sync had errors
        if response.tracks_failed > 0:
            # Log errors but don't fail the job
            print(f"Playlist sync warnings: {len(response.errors)} errors")

        return {
            "playlist_id": str(response.playlist.id),
            "playlist_name": response.playlist.name,
            "tracks_imported": response.tracks_imported,
            "tracks_failed": response.tracks_failed,
            "errors": response.errors,
        }

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
