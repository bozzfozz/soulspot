# Hey future me - this worker handles LIBRARY_SPOTIFY_ENRICHMENT jobs!
# It enriches local library items (artists, albums) with Spotify metadata.
# Triggered automatically after library scans (if auto_enrichment_enabled)
# or manually via API. Uses LocalLibraryEnrichmentService.
#
# ⚠️ DEPRECATED (2025.1): This worker is deprecated in favor of LibraryDiscoveryWorker!
# LibraryDiscoveryWorker provides:
# - Automatic 6-hourly execution (no manual triggering needed)
# - 5-phase discovery: Artist IDs → Discography → Ownership → Album IDs → Track IDs
# - Multi-provider support (Deezer first, Spotify enhancement)
# - Manual trigger via API: POST /api/library/discovery/trigger
# This worker will be removed in a future version.
"""Library Spotify enrichment worker for background enrichment jobs.

.. deprecated:: 2025.1
    Use LibraryDiscoveryWorker instead. This entire class will be removed in a future version.
"""

import logging
import warnings
from typing import TYPE_CHECKING, Any

from soulspot.application.workers.job_queue import Job, JobQueue, JobType
from soulspot.config import Settings

if TYPE_CHECKING:
    from soulspot.infrastructure.persistence.database import Database

logger = logging.getLogger(__name__)


class LibraryEnrichmentWorker:
    """Worker for processing library Spotify enrichment jobs.

    .. deprecated:: 2025.1
        Use LibraryDiscoveryWorker instead. This class will be removed in a future version.
        LibraryDiscoveryWorker provides automatic 6-hourly enrichment with 5 phases.

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
        warnings.warn(
            "LibraryEnrichmentWorker is deprecated. Use LibraryDiscoveryWorker instead. "
            "Manual trigger: POST /api/library/discovery/trigger",
            DeprecationWarning,
            stacklevel=2,
        )
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

        Hey future me - wir nutzen jetzt SpotifyPlugin statt SpotifyClient!
        Das Plugin managed Token intern, daher kein access_token Parameter mehr.

        Called by JobQueue when a LIBRARY_SPOTIFY_ENRICHMENT job is ready.

        Args:
            job: The job to process

        Returns:
            Enrichment statistics dict
        """
        from soulspot.application.services.local_library_enrichment_service import (
            LocalLibraryEnrichmentService,
        )
        from soulspot.application.services.images.image_provider_registry import (
            ImageProviderRegistry,
        )
        from soulspot.infrastructure.image_providers import (
            CoverArtArchiveImageProvider,
            DeezerImageProvider,
            SpotifyImageProvider,
        )
        from soulspot.infrastructure.integrations.deezer_client import DeezerClient
        from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
        from soulspot.infrastructure.persistence.repositories import (
            SpotifyTokenRepository,
        )
        from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

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

                # Hey future me - Spotify token is OPTIONAL now!
                # We can still enrich using Deezer/CoverArtArchive even without Spotify.
                access_token = token_model.access_token if token_model else None
                spotify_plugin: SpotifyPlugin | None = None

                if access_token:
                    # Hey future me - SpotifyPlugin erstellen mit Token!
                    # Das Plugin managed den Token intern.
                    spotify_client = SpotifyClient(self.settings.spotify)
                    spotify_plugin = SpotifyPlugin(client=spotify_client, access_token=access_token)
                else:
                    logger.info(
                        "No Spotify token available - will use Deezer/CoverArtArchive only for images"
                    )

                # Hey future me - Build the ImageProviderRegistry with all available providers!
                # This enables multi-source fallback: Spotify → Deezer → CoverArtArchive
                # Each provider is registered with a priority (lower = higher priority)
                image_registry = ImageProviderRegistry()

                # Register providers based on availability
                # Priority: Spotify (1) → Deezer (2) → CoverArtArchive (3)
                if spotify_plugin:
                    image_registry.register(SpotifyImageProvider(spotify_plugin), priority=1)

                # Deezer is always available (no auth required)
                # Hey future me - DeezerImageProvider wraps DeezerClient (public API, no auth).
                deezer_client = DeezerClient()
                image_registry.register(DeezerImageProvider(deezer_client), priority=2)

                # CoverArtArchive is always available (no auth required, albums only)
                image_registry.register(CoverArtArchiveImageProvider(), priority=3)

                logger.debug(
                    f"ImageProviderRegistry configured with {len(image_registry.get_available_providers())} providers"
                )

                service = LocalLibraryEnrichmentService(
                    session=session,
                    spotify_plugin=spotify_plugin,
                    settings=self.settings,
                    image_provider_registry=image_registry,
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
                logger.error(f"Enrichment job {job.id} failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                }
