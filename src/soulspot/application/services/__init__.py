"""Application services - Token management and business logic services."""

from soulspot.application.services.app_settings_service import AppSettingsService
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
from soulspot.application.services.provider_mapping_service import (
    ProviderMappingService,
)
from soulspot.application.services.session_store import Session, SessionStore
from soulspot.application.services.spotify_auth_service import (
    AuthUrlResult,
    SpotifyAuthService,
    TokenResult,
)
from soulspot.application.services.spotify_image_service import (
    ImageDownloadErrorCode,
    ImageDownloadResult,
    SpotifyImageService,
)
from soulspot.application.services.token_manager import TokenManager

__all__ = [
    "AlbumAnalysisResult",
    "AppSettingsService",
    "AuthUrlResult",
    "AutoImportService",
    "CompilationAnalyzerService",
    "CredentialsService",
    "DeezerCredentials",
    "ImageDownloadErrorCode",
    "ImageDownloadResult",
    "ProviderMappingService",
    "Session",
    "SessionStore",
    "SlskdCredentials",
    "SpotifyAuthService",
    "SpotifyCredentials",
    "SpotifyImageService",
    "TokenManager",
    "TokenResult",
]
