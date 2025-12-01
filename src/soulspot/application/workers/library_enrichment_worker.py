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
        from soulspot.application.services.token_manager import DatabaseTokenManager
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

        payload = job.payload
        triggered_by = payload.get("triggered_by", "manual")

        logger.info(f"Starting enrichment job {job.id} (triggered_by={triggered_by})")

        async with self.db.session_scope() as session:
            try:
                # Get valid Spotify access token
                # Hey - we need a token to call Spotify API for search!
                token_manager = DatabaseTokenManager(session)
                access_token = await token_manager.get_valid_token()

                if not access_token:
                    logger.warning("No valid Spotify token available for enrichment")
                    return {
                        "success": False,
                        "error": "No valid Spotify token. Please re-authenticate.",
                    }

                # Create Spotify client and enrichment service
                spotify_client = SpotifyClient(self.settings)
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
