# Hey future me - this worker handles LIBRARY_SPOTIFY_ENRICHMENT jobs!
# It enriches local library items (artists, albums) with Spotify metadata.
# Triggered automatically after library scans (if auto_enrichment_enabled)
# or manually via API. Uses LocalLibraryEnrichmentService.
"""Library Spotify enrichment worker for background enrichment jobs."""

import logging
from typing import TYPE_CHECKING, Any

from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.config import Settings

if TYPE_CHECKING:
    from soulspot.infrastructure.persistence.database import Database

logger = logging.getLogger(__name__)


class LibraryEnrichmentWorker:
    """Worker for processing library Spotify enrichment jobs.

    This worker:
    1. Receives LIBRARY_SPOTIFY_ENRICHMENT jobs from JobQueue
    2. Gets valid Spotify access token
    3. Creates LocalLibraryEnrichmentService
    4. Runs batch enrichment for unenriched items

    Enrichment matches local library items (artists, albums) with Spotify
    and adds metadata like images, genres, and Spotify URIs.
    """

    def __init__(
        self,
        job_queue: JobQueue,
        db: "Database",
        settings: Settings,
    ) -> None:
        """Initialize worker.

        Args:
            job_queue: Job queue for background processing
            db: Database instance for creating sessions
            settings: Application settings
        """
        self._job_queue = job_queue
        self.db = db
        self.settings = settings

    def register(self) -> None:
        """Register handler with job queue.

        Call this AFTER app is fully initialized!
        """
        self._job_queue.register_handler(
            JobType.LIBRARY_SPOTIFY_ENRICHMENT, self._handle_enrichment_job
        )

    async def _handle_enrichment_job(self, job: Job) -> dict[str, Any]:
        """Handle a library enrichment job.

        Called by JobQueue when a LIBRARY_SPOTIFY_ENRICHMENT job is ready.

        Args:
            job: The job to process

        Returns:
            Enrichment statistics dict
        """
        from soulspot.application.services.local_library_enrichment_service import (
            LocalLibraryEnrichmentService,
        )
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )

        payload = job.payload
        triggered_by = payload.get("triggered_by", "manual")

        logger.info(f"Starting enrichment job {job.id} (triggered_by={triggered_by})")

        async with self.db.session_scope() as session:
            try:
                # Get valid Spotify access token directly from repository
                # Hey future me - using SpotifyTokenRepository is simpler than DatabaseTokenManager
                # for cases where we already have a session. DatabaseTokenManager needs a session_scope
                # factory which is more complex to set up in a worker context.
                token_repo = SpotifyTokenRepository(session)
                token_model = await token_repo.get_active_token()

                if not token_model or not token_model.access_token:
                    logger.warning("No valid Spotify token available for enrichment")
                    return {
                        "success": False,
                        "error": "No valid Spotify token. Please re-authenticate.",
                    }

                access_token = token_model.access_token

                # Create Spotify client and enrichment service
                spotify_client = SpotifyClient(self.settings.spotify)
                service = LocalLibraryEnrichmentService(
                    session=session,
                    spotify_client=spotify_client,
                    settings=self.settings,
                    access_token=access_token,
                )

                # Run batch enrichment
                stats = await service.enrich_batch()

                logger.info(
                    f"Enrichment job {job.id} complete: "
                    f"{stats['artists_enriched']} artists, "
                    f"{stats['albums_enriched']} albums enriched"
                )

                return stats

            except Exception as e:
                logger.error(f"Enrichment job {job.id} failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                }
