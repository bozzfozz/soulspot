"""Application services - Token management and business logic services."""

from soulspot.application.services.app_settings_service import AppSettingsService

# Hey future me - ArtistService is THE unified service for ALL artist operations!
# Merged from: followed_artists_service, artist_songs_service, discography_service
# See: artist_service.py docstring for full list of merged methods.
from soulspot.application.services.artist_service import ArtistService, DiscographyInfo

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

# Hey future me - BrowseService is THE unified service for all browse/discovery operations!
# Merged from: discover_service.py + new_releases_service.py
# Backward compatible aliases: DiscoverService, NewReleasesService
from soulspot.application.services.browse_service import (
    BrowseResult,
    BrowseService,
    DiscoveredArtist,
    # Backward compatibility aliases
    DiscoverResult,
    DiscoverService,
    NewReleasesResult,
    NewReleasesService,
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

# Hey future me - Deduplication is split into two services for performance reasons:
# - DeduplicationChecker: Fast import-time matching (<50ms required)
# - DeduplicationHousekeepingService: Async scheduled cleanup (can take minutes)
# Old services (entity_deduplicator.py, library_merge_service.py, duplicate_service.py)
# are deprecated - use these new consolidated services instead.
from soulspot.application.services.deduplication_checker import DeduplicationChecker
from soulspot.application.services.deduplication_housekeeping import (
    DeduplicationHousekeepingService,
    DuplicateCounts,
    DuplicateGroup,
    MergeResult,
)

# Hey future me - Library Services are now in services/library/ subpackage!
# Phase 6 of SERVICE_CONSOLIDATION_PLAN reorganized library services for better organization.
# Import from library/ for new code, old imports still work for backward compatibility.
from soulspot.application.services.library import (
    LibraryScannerService,
    LibraryCleanupService,
    LibraryViewService,
    # AutoImportService already imported above
    # CompilationAnalyzerService already imported above
)

# Hey future me - Provider Services are now in services/providers/ subpackage!
# Phase 7 of SERVICE_CONSOLIDATION_PLAN reorganized provider services for better organization.
# Import from providers/ for new code, old imports still work for backward compatibility.
from soulspot.application.services.providers import (
    ProviderMappingService,
    ProviderSyncOrchestrator,
    AggregatedSyncResult,
    # SpotifySyncService, DeezerSyncService imported separately below for compatibility
)

# Hey future me - Session Services are now in services/sessions/ subpackage!
# Phase 8 of SERVICE_CONSOLIDATION_PLAN reorganized session services for better organization.
# Import from sessions/ for new code, old imports still work for backward compatibility.
from soulspot.application.services.sessions import (
    Session,
    SessionStore,
    TokenManager,
    TokenInfo,
    TokenStatus,
)

# Hey future me - MusicBrainzEnrichmentService handles disambiguation enrichment!
# Replaces enrich_disambiguation_batch from LocalLibraryEnrichmentService (deprecated).
from soulspot.application.services.musicbrainz_enrichment_service import (
    MusicBrainzEnrichmentService,
)
from soulspot.application.services.spotify_auth_service import (
    AuthUrlResult,
    SpotifyAuthService,
    TokenResult,
)

# ArtworkService is DEPRECATED and can be deleted
# All functionality has been migrated to ImageService

__all__ = [
    "AggregatedSyncResult",
    "AlbumAnalysisResult",
    "AppSettingsService",
    "ArtistService",
    "AuthUrlResult",
    "AutoFetchService",
    "AutoImportService",
    "BrowseResult",
    "BrowseService",
    "CompilationAnalyzerService",
    "CredentialsService",
    "DeezerAuthService",
    "DeezerAuthUrlResult",
    "DeezerCredentials",
    "DeezerSyncService",
    "DeezerTokenResult",
    "DiscographyInfo",
    "DiscoveredArtist",
    "DiscoverResult",
    "DiscoverService",
    "DeduplicationChecker",
    "DeduplicationHousekeepingService",
    "DuplicateCounts",
    "DuplicateGroup",
    "ImageDownloadErrorCode",
    "ImageDownloadResult",
    "ImageInfo",
    "ImageService",
    # Library Services (Phase 6)
    "LibraryScannerService",
    "LibraryCleanupService",
    "LibraryViewService",
    "MergeResult",
    "MusicBrainzEnrichmentService",
    "NewReleasesResult",
    "NewReleasesService",
    "ProviderMappingService",
    "ProviderSyncOrchestrator",
    "SaveImageResult",
    # Session Services (Phase 8)
    "Session",
    "SessionStore",
    "TokenManager",
    "TokenInfo",
    "TokenStatus",
    "SlskdCredentials",
    "SpotifyAuthService",
    "SpotifyCredentials",
    "TokenResult",
]
