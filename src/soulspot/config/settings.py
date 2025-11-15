"""Settings management with Pydantic and profile support."""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(str, Enum):
    """Deployment profile."""

    SIMPLE = "simple"  # SQLite, no queue, local filesystem
    STANDARD = "standard"  # PostgreSQL, Redis/Celery, optional S3


class DatabaseSettings(BaseSettings):
    """Database configuration."""

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
    )
    max_overflow: int = Field(
        default=10,
        description="Maximum connection pool overflow (PostgreSQL only)",
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
        return bool(self.api_key and self.api_key.strip() and self.api_secret and self.api_secret.strip())


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
    secure_cookies: bool = Field(
        default=False,
        description="Use secure cookies (requires HTTPS). Set to True in production.",
    )

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


class Settings(BaseSettings):
    """Main application settings."""

    # Application
    app_name: str = Field(
        default="SoulSpot Bridge",
        description="Application name",
    )
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
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

    # Security
    secret_key: str = Field(
        default="change-me-to-a-random-secret-key-in-production",
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_in_production(cls, v: str, info: ValidationInfo) -> str:
        """Validate secret key in production."""
        if (
            info.data.get("app_env") == "production"
            and v == "change-me-to-a-random-secret-key-in-production"
        ):
            raise ValueError("Secret key must be changed in production")
        return v

    def is_simple_profile(self) -> bool:
        """Check if using simple profile."""
        return self.profile == Profile.SIMPLE

    def is_standard_profile(self) -> bool:
        """Check if using standard profile."""
        return self.profile == Profile.STANDARD

    def ensure_directories(self) -> None:
        """Ensure all storage directories exist."""
        self.storage.download_path.mkdir(parents=True, exist_ok=True)
        self.storage.music_path.mkdir(parents=True, exist_ok=True)
        self.storage.artwork_path.mkdir(parents=True, exist_ok=True)
        self.storage.temp_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
