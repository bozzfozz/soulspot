"""Application services - Token management and business logic services."""

from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.application.services.auto_import import AutoImportService
from soulspot.application.services.charts_service import (
    ChartAlbum,
    ChartArtist,
    ChartsResult,
    ChartsService,
    ChartTrack,
)
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
    AuthUrlResult as DeezerAuthUrlResult,
    TokenResult as DeezerTokenResult,
)
from soulspot.application.services.deezer_sync_service import DeezerSyncService
from soulspot.application.services.discover_service import (
    DiscoveredArtist,
    DiscoverResult,
    DiscoverService,
)
from soulspot.application.services.library_view_service import LibraryViewService
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
from soulspot.application.services.artwork_service import (
    ArtworkService,
    ImageDownloadErrorCode,
    ImageDownloadResult,
)
from soulspot.application.services.token_manager import TokenManager

__all__ = [
    "AggregatedSyncResult",
    "AlbumAnalysisResult",
    "AppSettingsService",
    "AuthUrlResult",
    "AutoImportService",
    "ChartAlbum",
    "ChartArtist",
    "ChartsResult",
    "ChartsService",
    "ChartTrack",
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
    "LibraryViewService",
    "NewReleasesResult",
    "NewReleasesService",
    "ProviderMappingService",
    "ProviderSyncOrchestrator",
    "Session",
    "SessionStore",
    "SlskdCredentials",
    "SpotifyAuthService",
    "SpotifyCredentials",
    "ArtworkService",
    "TokenManager",
    "TokenResult",
]
