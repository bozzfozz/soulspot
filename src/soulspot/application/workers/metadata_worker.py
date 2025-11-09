"""Metadata enrichment worker for background metadata processing."""

from typing import Any

from soulspot.application.use_cases import EnrichMetadataUseCase
from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IMusicBrainzClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import TrackId


class MetadataWorker:
    """Worker for processing metadata enrichment jobs in the background.

    This worker:
    1. Monitors metadata enrichment queue
    2. Fetches metadata from MusicBrainz
    3. Enriches track, artist, and album information
    4. Updates entities in repository
    5. Handles rate limiting for MusicBrainz API
    """

    def __init__(
        self,
        job_queue: JobQueue,
        musicbrainz_client: IMusicBrainzClient,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
    ) -> None:
        """Initialize metadata worker.

        Args:
            job_queue: Job queue for background processing
            musicbrainz_client: Client for MusicBrainz API
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
            album_repository: Repository for album persistence
        """
        self._job_queue = job_queue
        self._use_case = EnrichMetadataUseCase(
            musicbrainz_client=musicbrainz_client,
            track_repository=track_repository,
            artist_repository=artist_repository,
            album_repository=album_repository,
        )

    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(
            JobType.METADATA_ENRICHMENT, self._handle_metadata_job
        )

    async def _handle_metadata_job(self, job: Job) -> Any:
        """Handle a metadata enrichment job.

        Args:
            job: Job to process

        Returns:
            Enrichment result
        """
        # Extract payload
        track_id_str = job.payload.get("track_id")
        if not track_id_str:
            raise ValueError("Missing track_id in job payload")

        track_id = TrackId(track_id_str)
        force_refresh = job.payload.get("force_refresh", False)
        enrich_artist = job.payload.get("enrich_artist", True)
        enrich_album = job.payload.get("enrich_album", True)

        # Execute use case
        from soulspot.application.use_cases.enrich_metadata import EnrichMetadataRequest

        request = EnrichMetadataRequest(
            track_id=track_id,
            force_refresh=force_refresh,
            enrich_artist=enrich_artist,
            enrich_album=enrich_album,
        )

        response = await self._use_case.execute(request)

        # Check if enrichment had errors
        if response.errors:
            # Raise first error to trigger retry
            raise Exception("; ".join(response.errors))

        return {
            "track_id": str(track_id),
            "artist_id": str(response.artist.id) if response.artist else None,
            "album_id": str(response.album.id) if response.album else None,
            "enriched_fields": response.enriched_fields,
        }

    async def enqueue_metadata_enrichment(
        self,
        track_id: TrackId,
        force_refresh: bool = False,
        enrich_artist: bool = True,
        enrich_album: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Enqueue a metadata enrichment job.

        Args:
            track_id: Track to enrich
            force_refresh: Force refresh even if metadata exists
            enrich_artist: Whether to enrich artist information
            enrich_album: Whether to enrich album information
            max_retries: Maximum retry attempts

        Returns:
            Job ID
        """
        return await self._job_queue.enqueue(
            job_type=JobType.METADATA_ENRICHMENT,
            payload={
                "track_id": str(track_id),
                "force_refresh": force_refresh,
                "enrich_artist": enrich_artist,
                "enrich_album": enrich_album,
            },
            max_retries=max_retries,
        )

    async def enqueue_batch_enrichment(
        self,
        track_ids: list[TrackId],
        force_refresh: bool = False,
        enrich_artist: bool = True,
        enrich_album: bool = True,
        max_retries: int = 3,
    ) -> list[str]:
        """Enqueue multiple metadata enrichment jobs.

        Args:
            track_ids: Tracks to enrich
            force_refresh: Force refresh even if metadata exists
            enrich_artist: Whether to enrich artist information
            enrich_album: Whether to enrich album information
            max_retries: Maximum retry attempts

        Returns:
            List of job IDs
        """
        job_ids = []
        for track_id in track_ids:
            job_id = await self.enqueue_metadata_enrichment(
                track_id=track_id,
                force_refresh=force_refresh,
                enrich_artist=enrich_artist,
                enrich_album=enrich_album,
                max_retries=max_retries,
            )
            job_ids.append(job_id)
        return job_ids
