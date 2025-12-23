"""Settings management with Pydantic and profile support."""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Hey future me, Profile enum controls deployment complexity! SIMPLE = SQLite + in-memory queue
# (good for local dev, single user). STANDARD = PostgreSQL + Redis/Celery (production). Profile
# affects which features are available and which defaults are used. Code can check profile with
# settings.is_simple_profile() or settings.is_standard_profile(). Don't add more profiles without
# thinking hard - it multiplies testing matrix! Two is already painful enough to maintain.
class Profile(str, Enum):
    """Deployment profile."""

    SIMPLE = "simple"  # SQLite, no queue, local filesystem
    STANDARD = "standard"  # PostgreSQL, Redis/Celery, optional S3


# Yo, DatabaseSettings is a NESTED Pydantic model! It groups all DB-related config together.
# Env vars are prefixed with DATABASE_ (e.g., DATABASE_URL, DATABASE_POOL_SIZE). pool_* settings
# only apply to PostgreSQL - SQLite ignores them! The pool_pre_ping=True is CRITICAL to prevent
# stale connections (MySQL closes idle conns after 8h, breaks app without pre-ping). pool_recycle
# refreshes connections every hour to avoid this. Don't lower pool_size below 5 unless you want
# "connection pool exhausted" errors under load! Each async request needs its own connection.
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


# Listen future me, SlskdSettings configures the slskd (Soulseek daemon) HTTP client! You need EITHER
# api_key OR username+password for auth. api_key is preferred (more secure, doesn't expire). The URL
# should point to your slskd instance (usually http://localhost:5030 in dev, could be remote in prod).
# If slskd is down/unreachable, downloads fail but app stays up. Check slskd health in /ready endpoint.
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


# Hey, SpotifySettings stores OAuth PKCE credentials for Spotify API! You get client_id and
# client_secret from Spotify Developer Dashboard. redirect_uri MUST match what you registered in
# Spotify dashboard exactly (including http vs https, trailing slash, port)! OAuth will fail with
# cryptic "redirect_uri mismatch" if they don't match. Default redirect_uri assumes local dev on
# port 8000. For production, override with your actual domain. These are NOT the same as user tokens!
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
        default="http://localhost:8000/api/auth/callback",
        description="OAuth redirect URI",
    )

    model_config = SettingsConfigDict(env_prefix="SPOTIFY_")


# Yo future me, MusicBrainz requires a User-Agent with app_name, app_version, and contact email!
# They'll ban your IP if you don't set a proper User-Agent (or use a generic Python one). contact
# should be a real email so they can reach you if your app misbehaves (excessive requests, etc).
# MusicBrainz has strict rate limits (1 req/sec) enforced by our circuit breaker. DON'T abuse this
# API or you'll get blocked for the entire community! Be a good citizen and respect rate limits.
class MusicBrainzSettings(BaseSettings):
    """MusicBrainz API configuration."""

    app_name: str = Field(
        default="SoulSpot",
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


# Hey, Last.fm is OPTIONAL! The is_configured() method checks if credentials are actually set
# (not just empty strings). Code should check lastfm.is_configured() before attempting API calls.
# If not configured, features gracefully degrade (skip Last.fm tags, just use MusicBrainz). Get
# api_key and api_secret from Last.fm API account (https://www.last.fm/api/account/create). Both
# are required - missing either means Last.fm is disabled. Empty/whitespace-only values = not configured!
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

    # Hey future me, this checks if Last.fm is actually configured or just using placeholder values.
    # We need BOTH api_key AND api_secret to be non-empty (after stripping whitespace). If either
    # is missing/empty, Last.fm features should be disabled gracefully. The bool() wrapper isn't
    # strictly needed (the and chain returns truthy/falsy) but makes intent clearer. Use this in
    # conditional feature enabling - don't try Last.fm API calls if this returns False!
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


# NOTE: DeezerSettings was removed! Deezer OAuth credentials are stored in the database
# via app_settings table, not in environment variables. This allows users to configure
# Deezer OAuth via Settings UI without app restart. User tokens are stored in deezer_sessions.
# See: alembic/versions/ss30015uuv63_add_deezer_sessions_table.py for schema.


# Listen up future me, StorageSettings has a CRITICAL validator ensure_path_is_absolute! All paths
# are automatically resolved to absolute paths (./downloads becomes /home/user/app/downloads). This
# prevents bugs when working directory changes! The validator runs on ALL four path fields. Paths
# default to current directory subdirectories (./downloads, ./music, etc) but you should override
# these in production to permanent storage locations. The app auto-creates these dirs at startup
# via settings.ensure_directories(). DON'T use relative paths anywhere else in the code!
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
    image_path: Path = Field(
        default=Path("./images"),
        description="Directory for cached images (artist/album artwork)",
    )
    temp_path: Path = Field(
        default=Path("./tmp"),
        description="Directory for temporary files",
    )

    # Yo, this Pydantic validator runs AUTOMATICALLY on field assignment! @field_validator decorator
    # marks it as validator for ALL four path fields. The @classmethod is REQUIRED (Pydantic needs
    # it). v.resolve() converts relative paths to absolute (e.g., "./downloads" becomes
    # "/home/user/app/downloads"). This prevents bugs where relative paths break when working
    # directory changes! Without this, Path("./music") might point to /tmp/music when running
    # tests but /app/music in production. ALWAYS use absolute paths for file operations!
    @field_validator("download_path", "music_path", "image_path", "temp_path")
    @classmethod
    def ensure_path_is_absolute(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        return v.resolve()

    model_config = SettingsConfigDict(env_prefix="STORAGE_")


# Hey future me, APISettings configures the FastAPI server! host="0.0.0.0" means bind to ALL network
# interfaces (needed for Docker containers). For local dev, "127.0.0.1" is safer but won't work in
# containers. cors_origins can be comma-separated string OR list (validator handles both). The
# parse_cors_origins validator converts "http://a.com,http://b.com" to ["http://a.com", "http://b.com"].
# secure_cookies should be True in production (requires HTTPS) but False for local dev (breaks on HTTP)!
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
        description="Use secure flag for cookies (requires HTTPS). Enable in production.",
    )
    session_cookie_name: str = Field(
        default="session_id",
        description="Name of the session cookie",
    )
    session_max_age: int = Field(
        default=3600,
        description="Session cookie max age in seconds",
        ge=60,
        le=86400,
    )
    gzip_minimum_size: int = Field(
        default=1000,
        description="Minimum response size in bytes for GZip compression",
        ge=100,
        le=10000,
    )

    # Yo, this validator handles CORS origins from ENV vars! Env vars are always strings, so we need
    # to parse "http://a,http://b" into a list. If it's already a list (programmatic config), pass
    # through unchanged. The strip() removes accidental whitespace from "http://a.com, http://b.com".
    # This runs BEFORE Pydantic validates the list type. If someone sets API__CORS_ORIGINS="http://a,b",
    # this converts it to ["http://a", "b"]. mode="before" means run before Pydantic's own parsing!
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = SettingsConfigDict(env_prefix="API_")


# Listen future me, CircuitBreakerSettings configures the circuit breaker pattern for external APIs!
# After failure_threshold consecutive failures, circuit OPENS (stops calling API, fails fast). After
# timeout seconds in OPEN state, circuit goes HALF_OPEN (tries one request). If success_threshold
# consecutive successes in HALF_OPEN, circuit CLOSES (back to normal). If any failure in HALF_OPEN,
# back to OPEN! This prevents cascading failures when external APIs are down. reset_timeout clears
# failure counter in CLOSED state after 5min of no failures. Tune these based on API reliability!
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


# Hey, ObservabilitySettings groups all monitoring/logging config! log_json_format=True enables
# structured JSON logging (good for production log aggregators like ELK, Datadog). Set False for
# human-readable dev logs. enable_dependency_health_checks controls whether /ready endpoint checks
# external services (DB, slskd, Spotify, MusicBrainz). Disable this if health checks are too slow
# or you don't care about external service status. circuit_breaker settings are nested here too!
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
    shutdown_timeout: float = Field(
        default=5.0,
        description="Timeout for graceful shutdown of background tasks in seconds",
        ge=1.0,
        le=30.0,
    )

    # Circuit breaker
    circuit_breaker: CircuitBreakerSettings = Field(
        default_factory=CircuitBreakerSettings,
        description="Circuit breaker configuration",
    )

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_")


# Yo future me, DownloadSettings configures the job queue and download workers! max_concurrent_downloads
# limits parallel downloads (Soulseek servers often throttle/ban if you download too many at once).
# 1-3 is recommended range - higher = faster but more likely to get banned. default_max_retries is
# how many times we retry failed downloads before giving up. enable_priority_queue=True means P0
# downloads (priority=0) are processed before P1/P2. If False, FIFO order. Don't set max_concurrent
# too high or you'll saturate network bandwidth and downloads will slow down from congestion!
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
    num_workers: int = Field(
        default=3,
        description="Number of job queue worker threads",
        ge=1,
        le=10,
    )

    model_config = SettingsConfigDict(env_prefix="DOWNLOAD_")


# Hey future me, NamingSettings configures Lidarr-style file and folder naming! This mirrors Lidarr's
# Media Management > Track Naming settings. The format strings use tokens like {Artist Name}, {Album Title},
# {track:00} that get replaced with actual metadata. Default formats match Lidarr defaults and work with
# Plex/Jellyfin/Navidrome. colon_replacement is crucial for Windows compatibility (colons illegal in
# filenames). multi_disc_style controls whether multi-disc albums use prefixes (01-01 - Track.flac) or
# subfolders (Disc 1/01 - Track.flac). These settings affect both library scanning and file organization!
class NamingSettings(BaseSettings):
    """Lidarr-style file and folder naming configuration."""

    # Artist folder format
    artist_folder_format: str = Field(
        default="{Artist Name}",
        description="Format for artist folder names (e.g., '{Artist Name}')",
    )

    # Album folder format
    album_folder_format: str = Field(
        default="{Album Title} ({Release Year})",
        description="Format for album folder names (e.g., '{Album Title} ({Release Year})')",
    )

    # Standard track format (single disc albums)
    standard_track_format: str = Field(
        default="{track:00} - {Track Title}",
        description="Format for track filenames on single-disc albums",
    )

    # Multi-disc track format
    multi_disc_track_format: str = Field(
        default="{medium:00}-{track:00} - {Track Title}",
        description="Format for track filenames on multi-disc albums",
    )

    # Various Artists compilation format
    various_artist_track_format: str = Field(
        default="{track:00} - {Artist Name} - {Track Title}",
        description="Format for track filenames on Various Artists compilations",
    )

    # Multi-disc handling style: "prefix" or "subfolder"
    multi_disc_style: str = Field(
        default="prefix",
        description="How to handle multi-disc albums: 'prefix' (01-01 - Track.flac) or 'subfolder' (Disc 1/01 - Track.flac)",
    )

    # Disc subfolder format (for subfolder style)
    multi_disc_folder_format: str = Field(
        default="Disc {medium}",
        description="Format for disc subfolders when multi_disc_style is 'subfolder'",
    )

    # Character replacement
    replace_illegal_characters: bool = Field(
        default=True,
        description="Replace illegal characters in filenames for cross-platform compatibility",
    )

    # Colon replacement: "" (delete), "-", " -" (default), " - "
    colon_replacement: str = Field(
        default=" -",
        description="What to replace colons with in filenames: '' (delete), '-', ' -' (default), ' - '",
    )

    model_config = SettingsConfigDict(env_prefix="NAMING_")


# Hey, PostProcessingSettings controls what happens AFTER a file is downloaded! enabled=True means
# run the full pipeline (fetch artwork, embed lyrics, write ID3 tags, rename files). You can disable
# individual steps (artwork_enabled, lyrics_enabled, etc) while keeping others. artwork_max_size and
# artwork_quality control image resizing (big artwork = big file size). file_naming_template uses
# special placeholders like {Artist CleanName} and {Track CleanTitle} - see docs for full list. If
# pipeline is disabled, files just sit in downloads/ with original slskd filenames (usually garbage)!
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
    auto_import_poll_interval: int = Field(
        default=60,
        description="Auto-import service polling interval in seconds",
        ge=10,
        le=600,
    )

    model_config = SettingsConfigDict(env_prefix="POSTPROCESSING_")


# Listen up future me, Settings is the TOP-LEVEL config class! All other *Settings classes are nested
# inside this one. Pydantic loads config from .env file (env_file=".env") and environment variables.
# The env_nested_delimiter="__" means DATABASE_URL becomes database.url (double underscore = nesting).
# case_sensitive=False means database_url, DATABASE_URL, Database_Url all work. extra="ignore" means
# unknown env vars don't cause errors. This class is a SINGLETON via @lru_cache on get_settings()!
# DON'T instantiate Settings() directly - always use get_settings() to get the cached singleton.
class Settings(BaseSettings):
    """Main application settings."""

    # Application
    app_name: str = Field(
        default="SoulSpot",
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
    # NOTE: No deezer field! Deezer OAuth credentials stored in DB (app_settings).
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
    naming: NamingSettings = Field(
        default_factory=NamingSettings,
        description="Lidarr-style naming configuration for files and folders",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        # .env file is optional - all settings have sensible defaults
        env_ignore_empty=True,
    )

    # Removed production secret key validation - this is for local use only

    # Hey, these profile helper methods are for feature flags! Use `if settings.is_simple_profile():`
    # instead of `if settings.profile == Profile.SIMPLE` - cleaner and more explicit. Code can check
    # profile to enable/disable features (e.g., Redis queue only in STANDARD, in-memory in SIMPLE).
    def is_simple_profile(self) -> bool:
        """Check if using simple profile."""
        return self.profile == Profile.SIMPLE

    # Yo, same as is_simple_profile but for STANDARD! These could be properties instead of methods
    # but methods are more explicit (verb names make intent clearer). Don't add more profiles
    # without adding corresponding helper methods here!
    def is_standard_profile(self) -> bool:
        """Check if using standard profile."""
        return self.profile == Profile.STANDARD

    # Listen future me, this parses DATABASE_URL to extract the SQLite file path! It's PRIVATE (leading
    # underscore) because it's internal implementation detail. Returns None for non-SQLite databases
    # (PostgreSQL, MySQL). The parsing logic handles both sqlite:/// and sqlite+aiosqlite:/// formats.
    # The path manipulation removes leading slash for relative paths but keeps it for absolute paths.
    # This is used by ensure_directories() to create parent directories before SQLAlchemy tries to
    # access the file. DON'T call this repeatedly - it's called once at startup!
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

    # Hey, this creates ALL storage directories at app startup! Called from lifespan() before any file
    # operations. Uses mkdir(parents=True, exist_ok=True) so it's idempotent (safe to call multiple
    # times). Also creates DB parent directory for SQLite (otherwise SQLAlchemy fails with "directory
    # not found"). If this fails (permission denied, disk full), app won't start - better than failing
    # later during first download! The exists_ok=True means no error if directories already exist.
    def ensure_directories(self) -> None:
        """Ensure all storage directories exist, including database parent directory."""
        import logging
        logger = logging.getLogger(__name__)

        # Ensure storage directories exist with logging
        for name, path in [
            ("Downloads", self.storage.download_path),
            ("Music", self.storage.music_path),
            ("Images", self.storage.image_path),
            ("Temp", self.storage.temp_path),
        ]:
            existed = path.exists()
            path.mkdir(parents=True, exist_ok=True)
            status = "exists" if existed else "created"
            logger.info("Storage path %s: %s (%s)", name, path, status)

        # Ensure database parent directory exists for SQLite
        db_path = self._get_sqlite_db_path()
        if db_path is not None:
            db_parent = db_path.parent
            if db_parent and str(db_parent) != ".":
                existed = db_parent.exists()
                db_parent.mkdir(parents=True, exist_ok=True)
                status = "exists" if existed else "created"
                logger.info("Database directory: %s (%s)", db_parent, status)


# Listen up future me, @lru_cache makes this a SINGLETON! First call creates Settings by reading .env
# and environment variables, subsequent calls return THE SAME INSTANCE. This is efficient (only parse
# .env once) but means settings changes require app restart! Each process/worker gets its own singleton
# (lru_cache is per-process, not shared across gunicorn workers). For tests, you might need to clear
# the cache with get_settings.cache_clear() to force re-reading. ALWAYS use get_settings() instead of
# Settings() directly to get the singleton! The maxsize is unbounded (default) since we only cache one.
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
