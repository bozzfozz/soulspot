"""Application services - Token management and business logic services."""

from soulspot.application.services.app_settings_service import AppSettingsService

# Hey future me - AutoFetchService centralizes all background auto-fetching!
# Replaces inline auto-fetch logic that was scattered across UI routes.
# Architecture: Routes → AutoFetchService → repair_artist_images() / repair_album_images()
from soulspot.application.services.auto_fetch_service import AutoFetchService
from soulspot.application.services.auto_import import AutoImportService
from soulspot.application.services.compilation_analyzer_service import (
    AlbumAnalysisResult,
    CompilationAnalyzerService,
)
from soulspot.application.services.credentials_service import (
    CredentialsService,
    DeezerCredentials,
    SlskdCredentials,
    SpotifyCredentials,
)
from soulspot.application.services.deezer_auth_service import (
    DeezerAuthService,
    DeezerAuthUrlResult,
    DeezerTokenResult,
)
from soulspot.application.services.deezer_sync_service import DeezerSyncService
from soulspot.application.services.discover_service import (
    DiscoveredArtist,
    DiscoverResult,
    DiscoverService,
)

# Hey future me – ImageService ist der NEUE zentrale Ort für Bildoperationen!
# Ersetzt nach und nach artwork_service.py (Legacy)
# Batch repair operations are now in images/repair.py:
#   from soulspot.application.services.images.repair import repair_artist_images, repair_album_images
# Siehe docs/architecture/IMAGE_SERVICE_DETAILED_PLAN.md
from soulspot.application.services.images import (
    ImageDownloadErrorCode,
    ImageDownloadResult,
    ImageInfo,
    ImageService,
    SaveImageResult,
)

# Hey future me - LibraryMergeService handles duplicate detection and merging!
# Replaces the duplicate/merge methods from LocalLibraryEnrichmentService (deprecated).
from soulspot.application.services.library_merge_service import LibraryMergeService
from soulspot.application.services.library_view_service import LibraryViewService

# Hey future me - MusicBrainzEnrichmentService handles disambiguation enrichment!
# Replaces enrich_disambiguation_batch from LocalLibraryEnrichmentService (deprecated).
from soulspot.application.services.musicbrainz_enrichment_service import (
    MusicBrainzEnrichmentService,
)
from soulspot.application.services.new_releases_service import (
    NewReleasesResult,
    NewReleasesService,
)
from soulspot.application.services.provider_mapping_service import (
    ProviderMappingService,
)
from soulspot.application.services.provider_sync_orchestrator import (
    AggregatedSyncResult,
    ProviderSyncOrchestrator,
)
from soulspot.application.services.session_store import Session, SessionStore
from soulspot.application.services.spotify_auth_service import (
    AuthUrlResult,
    SpotifyAuthService,
    TokenResult,
)
from soulspot.application.services.token_manager import TokenManager

# ArtworkService is DEPRECATED and can be deleted
# All functionality has been migrated to ImageService

__all__ = [
    "AggregatedSyncResult",
    "AlbumAnalysisResult",
    "AppSettingsService",
    "AuthUrlResult",
    "AutoFetchService",
    "AutoImportService",
    "CompilationAnalyzerService",
    "CredentialsService",
    "DeezerAuthService",
    "DeezerAuthUrlResult",
    "DeezerCredentials",
    "DeezerSyncService",
    "DeezerTokenResult",
    "DiscoveredArtist",
    "DiscoverResult",
    "DiscoverService",
    "ImageDownloadErrorCode",
    "ImageDownloadResult",
    "ImageInfo",
    "ImageService",
    "LibraryMergeService",
    "LibraryViewService",
    "MusicBrainzEnrichmentService",
    "NewReleasesResult",
    "NewReleasesService",
    "ProviderMappingService",
    "ProviderSyncOrchestrator",
    "SaveImageResult",
    "Session",
    "SessionStore",
    "SlskdCredentials",
    "SpotifyAuthService",
    "SpotifyCredentials",
    "TokenManager",
    "TokenResult",
]
