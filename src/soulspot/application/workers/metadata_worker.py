"""Metadata enrichment worker for background metadata processing."""

from typing import TYPE_CHECKING, Any

# Hey future me - TYPE_CHECKING lazy import pattern to break circular dependency:
# use_cases/__init__.py → queue_album_downloads → workers.job_queue
# workers/__init__.py → metadata_worker → use_cases/__init__.py
# By importing in TYPE_CHECKING block, mypy sees the types but runtime doesn't execute the import.
if TYPE_CHECKING:
    pass

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

    # Hey future me, metadata enrichment needs THREE repos (track, artist, album) because we enrich all
    # three levels of the music hierarchy! MusicBrainz client is the external dependency - it has STRICT
    # rate limits (1 request per second) so don't spam it! The use case handles rate limiting internally.
    # Same pattern as other workers - inject deps, create use case, don't auto-register.
    # NOTE: Lazy import in __init__ to break circular dependency (use_cases ↔ workers).
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
        # Lazy import to break circular dependency: use_cases → workers.job_queue → metadata_worker → use_cases
        from soulspot.application.use_cases.enrich_metadata import EnrichMetadataUseCase

        self._job_queue = job_queue
        self._use_case = EnrichMetadataUseCase(
            musicbrainz_client=musicbrainz_client,
            track_repository=track_repository,
            artist_repository=artist_repository,
            album_repository=album_repository,
        )

    # Yo, register to handle METADATA_ENRICHMENT jobs. MusicBrainz rate limiting means these jobs run SLOW
    # (max 1 per second!). If you have 1000 tracks to enrich, expect 15+ minutes! Don't register this worker
    # too early or you'll hit MusicBrainz before you're ready and waste quota on failed requests.
    def register(self) -> None:
        """Register handler with job queue."""
        self._job_queue.register_handler(
            JobType.METADATA_ENRICHMENT, self._handle_metadata_job
        )

    # Listen up future me, this handler calls MusicBrainz API to enrich track/artist/album metadata! The
    # force_refresh flag bypasses cache and re-fetches from MB (use sparingly!). The enrich_artist/enrich_album
    # flags let you skip parts (maybe you only want track metadata). IMPORTANT: If MusicBrainz returns errors
    # (track not found, API down, rate limit hit), we raise Exception which triggers RETRY. Max retries is 3
    # so we don't spam MB forever. The enriched_fields list in result tells you what actually changed (genres,
    # release_date, artwork_url, etc). This can take 1-3 seconds per track due to rate limiting!
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

    # Hey, queue a single track for metadata enrichment. force_refresh=True bypasses cache - only use if
    # you KNOW the cached data is wrong or outdated (don't waste MusicBrainz quota!). The enrich_artist and
    # enrich_album flags default True because users usually want complete metadata, but you can skip them
    # for performance (artist/album lookups are extra API calls). max_retries=3 because MusicBrainz can be
    # flaky (timeouts, temporary errors). Returns job_id for tracking.
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

    # Yo, batch enrichment for multiple tracks - loops and calls enqueue_metadata_enrichment for each. This
    # creates LOTS of jobs if you pass hundreds of track_ids! MusicBrainz rate limit means they'll queue up
    # and process slowly (1 per second). For 1000 tracks, expect 15+ minutes! Consider showing progress in
    # UI or users will think it's broken. Returns job_ids in same order as track_ids. Don't use force_refresh
    # for batch operations or you'll hammer MusicBrainz unnecessarily!
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
