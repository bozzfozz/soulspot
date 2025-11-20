"""Settings management with Pydantic and profile support."""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(str, Enum):
    """Deployment profile."""

    SIMPLE = "simple"  # SQLite, no queue, local filesystem
    STANDARD = "standard"  # PostgreSQL, Redis/Celery, optional S3


class DatabaseSettings(BaseSettings):
    """Database configuration with enhanced connection pool tuning."""

    url: str = Field(
        default="sqlite+aiosqlite:///./soulspot.db",
        description="Database connection URL",
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL statements for debugging",
    )
    pool_size: int = Field(
        default=5,
        description="Database connection pool size (PostgreSQL only)",
        ge=1,
        le=50,
    )
    max_overflow: int = Field(
        default=10,
        description="Maximum connection pool overflow (PostgreSQL only)",
        ge=0,
        le=50,
    )
    pool_timeout: float = Field(
        default=30.0,
        description="Connection pool timeout in seconds",
        ge=1.0,
        le=300.0,
    )
    pool_recycle: int = Field(
        default=3600,
        description="Connection recycle time in seconds (prevents stale connections)",
        ge=300,
        le=7200,
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="Test connections before checkout to ensure they're alive",
    )

    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class SlskdSettings(BaseSettings):
    """slskd client configuration."""

    url: str = Field(
        default="http://localhost:5030",
        description="slskd base URL",
    )
    username: str = Field(
        default="admin",
        description="slskd username",
    )
    password: str = Field(
        default="changeme",
        description="slskd password",
    )
    api_key: str | None = Field(
        default=None,
        description="slskd API key (optional)",
    )

    model_config = SettingsConfigDict(env_prefix="SLSKD_")


class SpotifySettings(BaseSettings):
    """Spotify API configuration."""

    client_id: str = Field(
        default="",
        description="Spotify OAuth client ID",
    )
    client_secret: str = Field(
        default="",
        description="Spotify OAuth client secret",
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/spotify/callback",
        description="OAuth redirect URI",
    )

    model_config = SettingsConfigDict(env_prefix="SPOTIFY_")


class MusicBrainzSettings(BaseSettings):
    """MusicBrainz API configuration."""

    app_name: str = Field(
        default="SoulSpot-Bridge",
        description="Application name for MusicBrainz API",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Application version for MusicBrainz API",
    )
    contact: str = Field(
        default="",
        description="Contact email for MusicBrainz API",
    )

    model_config = SettingsConfigDict(env_prefix="MUSICBRAINZ_")


class LastfmSettings(BaseSettings):
    """Last.fm API configuration."""

    api_key: str = Field(
        default="",
        description="Last.fm API key",
    )
    api_secret: str = Field(
        default="",
        description="Last.fm API secret",
    )

    model_config = SettingsConfigDict(env_prefix="LASTFM_")

    def is_configured(self) -> bool:
        """Check if Last.fm credentials are configured.

        Returns:
            True if both API key and secret are provided, False otherwise
        """
        return bool(
            self.api_key
            and self.api_key.strip()
            and self.api_secret
            and self.api_secret.strip()
        )


class StorageSettings(BaseSettings):
    """File storage configuration."""

    download_path: Path = Field(
        default=Path("./downloads"),
        description="Directory for downloaded files",
    )
    music_path: Path = Field(
        default=Path("./music"),
        description="Directory for organized music files",
    )
    artwork_path: Path = Field(
        default=Path("./artwork"),
        description="Directory for album artwork",
    )
    temp_path: Path = Field(
        default=Path("./tmp"),
        description="Directory for temporary files",
    )

    @field_validator("download_path", "music_path", "artwork_path", "temp_path")
    @classmethod
    def ensure_path_is_absolute(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        return v.resolve()

    model_config = SettingsConfigDict(env_prefix="STORAGE_")


class APISettings(BaseSettings):
    """API server configuration."""

    host: str = Field(
        default="0.0.0.0",  # nosec B104 - binding to all interfaces is intentional for containerized deployment
        description="API host to bind to",
    )
    port: int = Field(
        default=8000,
        description="API port to bind to",
        ge=1,
        le=65535,
    )
    workers: int = Field(
        default=1,
        description="Number of worker processes",
        ge=1,
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:8000", "http://localhost:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS",
    )
    # Removed secure_cookies - not needed for local-only use
    # Cookies always use httponly for basic security

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = SettingsConfigDict(env_prefix="API_")


class CircuitBreakerSettings(BaseSettings):
    """Circuit breaker configuration for external services."""

    failure_threshold: int = Field(
        default=5,
        description="Number of failures before opening circuit",
        ge=1,
    )
    success_threshold: int = Field(
        default=2,
        description="Number of successes in HALF_OPEN before closing circuit",
        ge=1,
    )
    timeout: float = Field(
        default=60.0,
        description="Seconds to wait in OPEN state before trying HALF_OPEN",
        ge=1.0,
    )
    reset_timeout: float = Field(
        default=300.0,
        description="Seconds to wait before resetting failure counter in CLOSED state",
        ge=1.0,
    )

    model_config = SettingsConfigDict(env_prefix="CIRCUIT_BREAKER_")


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configuration."""

    # Logging
    log_json_format: bool = Field(
        default=False,
        description="Use JSON format for logs (recommended for production)",
    )

    # Health checks
    enable_dependency_health_checks: bool = Field(
        default=True,
        description="Enable health checks for external dependencies",
    )
    health_check_timeout: float = Field(
        default=5.0,
        description="Timeout for dependency health checks in seconds",
        ge=1.0,
        le=30.0,
    )

    # Circuit breaker
    circuit_breaker: CircuitBreakerSettings = Field(
        default_factory=CircuitBreakerSettings,
        description="Circuit breaker configuration",
    )

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_")


class DownloadSettings(BaseSettings):
    """Download queue and worker configuration."""

    max_concurrent_downloads: int = Field(
        default=3,
        description="Maximum number of concurrent downloads (1-3 recommended)",
        ge=1,
        le=10,
    )
    default_max_retries: int = Field(
        default=3,
        description="Default maximum retry attempts for failed downloads",
        ge=1,
        le=10,
    )
    enable_priority_queue: bool = Field(
        default=True,
        description="Enable priority-based download queue",
    )

    model_config = SettingsConfigDict(env_prefix="DOWNLOAD_")


class PostProcessingSettings(BaseSettings):
    """Post-processing pipeline configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable automatic post-processing after download",
    )
    artwork_enabled: bool = Field(
        default=True,
        description="Enable artwork download and embedding",
    )
    artwork_max_size: int = Field(
        default=1200,
        description="Maximum artwork dimension in pixels",
        ge=300,
        le=3000,
    )
    artwork_quality: int = Field(
        default=95,
        description="JPEG quality for artwork (1-100)",
        ge=1,
        le=100,
    )
    lyrics_enabled: bool = Field(
        default=True,
        description="Enable lyrics fetching and embedding",
    )
    id3_tagging_enabled: bool = Field(
        default=True,
        description="Enable ID3 tag writing",
    )
    file_renaming_enabled: bool = Field(
        default=True,
        description="Enable file renaming based on templates",
    )
    file_naming_template: str = Field(
        default="{Artist CleanName} - {Album Type} - {Release Year} - {Album CleanTitle}/{medium:02d}{track:02d} - {Track CleanTitle}",
        description="File naming template",
    )

    model_config = SettingsConfigDict(env_prefix="POSTPROCESSING_")


class Settings(BaseSettings):
    """Main application settings."""

    # Application
    app_name: str = Field(
        default="SoulSpot Bridge",
        description="Application name",
    )
    # Removed app_env - project is for local use only
    profile: Profile = Field(
        default=Profile.SIMPLE,
        description="Deployment profile (simple or standard)",
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    # Security (for local use - generate a random key)
    secret_key: str = Field(
        default="local-dev-secret-key-change-for-better-security",
        description="Secret key for cryptographic operations",
        min_length=32,
    )

    # Nested settings
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database configuration",
    )
    slskd: SlskdSettings = Field(
        default_factory=SlskdSettings,
        description="slskd configuration",
    )
    spotify: SpotifySettings = Field(
        default_factory=SpotifySettings,
        description="Spotify configuration",
    )
    musicbrainz: MusicBrainzSettings = Field(
        default_factory=MusicBrainzSettings,
        description="MusicBrainz configuration",
    )
    lastfm: LastfmSettings = Field(
        default_factory=LastfmSettings,
        description="Last.fm configuration",
    )
    storage: StorageSettings = Field(
        default_factory=StorageSettings,
        description="Storage configuration",
    )
    api: APISettings = Field(
        default_factory=APISettings,
        description="API configuration",
    )
    observability: ObservabilitySettings = Field(
        default_factory=ObservabilitySettings,
        description="Observability configuration",
    )
    download: DownloadSettings = Field(
        default_factory=DownloadSettings,
        description="Download queue configuration",
    )
    postprocessing: PostProcessingSettings = Field(
        default_factory=PostProcessingSettings,
        description="Post-processing pipeline configuration",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Removed production secret key validation - this is for local use only

    def is_simple_profile(self) -> bool:
        """Check if using simple profile."""
        return self.profile == Profile.SIMPLE

    def is_standard_profile(self) -> bool:
        """Check if using standard profile."""
        return self.profile == Profile.STANDARD

    def _get_sqlite_db_path(self) -> Path | None:
        """Extract database file path from SQLite URL.

        Returns:
            Path to the database file if using SQLite, None otherwise.
        """
        db_url = self.database.url
        if "sqlite" not in db_url:
            return None

        # Parse URL to extract path
        # Format: sqlite+aiosqlite:///path/to/db.db or sqlite:///path/to/db.db
        parsed = urlparse(db_url)
        if not parsed.path:
            return None

        # Remove leading slash for relative paths, keep for absolute paths
        path_str = parsed.path
        if (
            path_str.startswith("/")
            and not path_str.startswith("//")
            and (path_str.startswith("/./") or path_str.startswith("/../"))
        ):
            # Relative path with leading slash
            path_str = path_str[1:]  # Remove first slash

        return Path(path_str)

    def ensure_directories(self) -> None:
        """Ensure all storage directories exist, including database parent directory."""
        # Ensure storage directories exist
        self.storage.download_path.mkdir(parents=True, exist_ok=True)
        self.storage.music_path.mkdir(parents=True, exist_ok=True)
        self.storage.artwork_path.mkdir(parents=True, exist_ok=True)
        self.storage.temp_path.mkdir(parents=True, exist_ok=True)

        # Ensure database parent directory exists for SQLite
        db_path = self._get_sqlite_db_path()
        if db_path is not None:
            db_parent = db_path.parent
            if db_parent and str(db_parent) != ".":
                db_parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
