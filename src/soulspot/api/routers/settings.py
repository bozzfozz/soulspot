"""Settings management API endpoints."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from soulspot.config import get_settings

router = APIRouter()


# Hey future me, these are Pydantic schemas for settings API! They group related settings (general, integration,
# download, appearance, advanced) for the UI. IMPORTANT: These are READ-ONLY views! Changing values here doesn't
# update the actual app config (which comes from env vars at startup). If you want dynamic config, you'd need
# to implement a config update mechanism with validation and app reload/restart. These schemas are also used
# for validation if you ever add PUT/PATCH endpoints to update settings at runtime.


class GeneralSettings(BaseModel):
    """General application settings."""

    app_name: str = Field(description="Application name")
    log_level: str = Field(description="Logging level")
    debug: bool = Field(description="Debug mode")


# Yo, external service credentials! SECURITY CRITICAL: Never log these, never return actual values in API
# responses! The GET endpoint below masks these with "***". slskd_api_key is optional because you can auth
# with username/password OR API key. The redirect_uri for Spotify must exactly match what's configured in
# Spotify Developer Dashboard or OAuth will fail! If these are wrong, integration endpoints will blow up with
# 401/403 errors. Store these in .env file, NEVER commit to git!
class IntegrationSettings(BaseModel):
    """Integration settings for external services."""

    # Spotify
    spotify_client_id: str = Field(description="Spotify client ID")
    spotify_client_secret: str = Field(description="Spotify client secret")
    spotify_redirect_uri: str = Field(description="Spotify redirect URI")

    # slskd
    slskd_url: str = Field(description="slskd URL")
    slskd_username: str = Field(description="slskd username")
    slskd_password: str = Field(description="slskd password")
    slskd_api_key: str | None = Field(
        default=None, description="slskd API key (optional)"
    )

    # MusicBrainz
    musicbrainz_app_name: str = Field(description="MusicBrainz app name")
    musicbrainz_contact: str = Field(description="MusicBrainz contact email")


# Hey, download worker configuration! max_concurrent_downloads is resource-limited (1-10 range) because
# running 50 simultaneous downloads would kill network/disk. Default is probably 3-5 (check config). If
# downloads are slow, increasing this helps IF your bottleneck is parallelism not bandwidth. default_max_retries
# is how many times we retry failed downloads before giving up. enable_priority_queue toggles whether priority
# field is used (if false, all downloads are FIFO regardless of priority). These affect runtime behavior!
class DownloadSettings(BaseModel):
    """Download configuration settings."""

    max_concurrent_downloads: int = Field(
        ge=1, le=10, description="Maximum concurrent downloads"
    )
    default_max_retries: int = Field(ge=1, le=10, description="Default max retries")
    enable_priority_queue: bool = Field(description="Enable priority queue")


# Yo, just theme settings for now! "light", "dark", or "auto" (follows system preference). This is client-side
# only - server doesn't care about theme. Future expansion: font size, compact mode, color customization, etc.
# Could also add dashboard layout preferences here (default widget sizes, grid spacing, etc).
class AppearanceSettings(BaseModel):
    """Appearance and theme settings."""

    theme: str = Field(description="Theme: light, dark, or auto")


# Listen, "advanced" means "don't touch unless you know what you're doing"! api_host/port determine where
# the server listens - changing these requires restart. Circuit breaker settings are for fault tolerance -
# if external API (Spotify/MusicBrainz/slskd) fails N times (failure_threshold), we stop calling it for X
# seconds (timeout) to avoid hammering a dead service. Prevents cascading failures. The 1-65535 port range
# is full TCP port range. Note secure_cookies was removed - see comment, this is local-only app!
class AdvancedSettings(BaseModel):
    """Advanced configuration settings."""

    api_host: str = Field(description="API host")
    api_port: int = Field(ge=1, le=65535, description="API port")
    # Removed secure_cookies - not needed for local-only use
    circuit_breaker_failure_threshold: int = Field(
        ge=1, description="Circuit breaker failure threshold"
    )
    circuit_breaker_timeout: float = Field(
        ge=1.0, description="Circuit breaker timeout (seconds)"
    )


# Hey, container for all settings groups! This is what GET /settings returns - one object with nested
# sections. Makes UI easier - you can render tabs for each category. Pydantic validates the whole tree,
# so if any setting is invalid/missing, the endpoint will 500. These match the actual Settings dataclass
# from soulspot.config - keep them in sync or you'll get validation errors!
class AllSettings(BaseModel):
    """Combined settings model."""

    general: GeneralSettings
    integration: IntegrationSettings
    download: DownloadSettings
    appearance: AppearanceSettings
    advanced: AdvancedSettings


# Hey future me, this endpoint exposes ALL settings to the UI - but we MASK secrets! Notice the "***"
# for passwords and API keys - NEVER return actual secrets in API responses or they'll leak in browser
# devtools, logs, error tracking, etc. The settings come from get_settings() which loads from env vars
# at startup. These are READ-ONLY in runtime - changing them here won't affect running app! For that,
# you'd need hot-reload or restart. The appearance.theme default is "auto" - actual theme is client-side.
@router.get("/")
async def get_all_settings() -> AllSettings:
    """Get all current settings.

    Returns:
        All application settings grouped by category
    """
    settings = get_settings()

    return AllSettings(
        general=GeneralSettings(
            app_name=settings.app_name,
            log_level=settings.log_level,
            debug=settings.debug,
        ),
        integration=IntegrationSettings(
            spotify_client_id=settings.spotify.client_id,
            spotify_client_secret="***" if settings.spotify.client_secret else "",
            spotify_redirect_uri=settings.spotify.redirect_uri,
            slskd_url=settings.slskd.url,
            slskd_username=settings.slskd.username,
            slskd_password="***" if settings.slskd.password else "",
            slskd_api_key="***" if settings.slskd.api_key else None,
            musicbrainz_app_name=settings.musicbrainz.app_name,
            musicbrainz_contact=settings.musicbrainz.contact,
        ),
        download=DownloadSettings(
            max_concurrent_downloads=settings.download.max_concurrent_downloads,
            default_max_retries=settings.download.default_max_retries,
            enable_priority_queue=settings.download.enable_priority_queue,
        ),
        appearance=AppearanceSettings(
            theme="auto",  # Default to auto, will be overridden by client preference
        ),
        advanced=AdvancedSettings(
            api_host=settings.api.host,
            api_port=settings.api.port,
            circuit_breaker_failure_threshold=settings.observability.circuit_breaker.failure_threshold,
            circuit_breaker_timeout=settings.observability.circuit_breaker.timeout,
        ),
    )


# Yo future me, this endpoint is a TODO stub! It ACCEPTS settings but DOESN'T SAVE THEM. If you actually
# implement this, you have three options: 1) Write to .env file (fragile, needs file permissions), 2) Save
# to DB config table (persistent, multi-instance safe), 3) External config service (enterprise!). IMPORTANT:
# Some settings require restart (port changes, DB URL), others can hot-reload (log level, timeouts). Don't
# let users think settings apply immediately when they don't - the "restart" note is critical! Also validate
# carefully - bad settings (port 0, invalid URLs) can brick the app!
@router.post("/")
async def update_settings(settings_update: AllSettings) -> dict[str, Any]:
    """Update application settings.

    Note: This endpoint currently returns the settings but doesn't persist them.
    In a full implementation, this would:
    - Write to .env file (requires dotenv manipulation library)
    - Store in database (config table)
    - Apply hot-reload for non-critical settings
    - Require restart for critical settings (ports, auth keys)

    Args:
        settings_update: New settings values

    Returns:
        Success message

    Raises:
        HTTPException: If settings validation fails
    """
    # TODO: Implement actual persistence
    # Options:
    # 1. Write to .env file using python-dotenv set_key()
    # 2. Store in database config table with key-value pairs
    # 3. Use external config service (Consul, etcd)
    # For now, just validate and return success
    # Settings validation is done by Pydantic automatically
    _ = settings_update  # Mark as used for linting
    return {
        "message": "Settings updated successfully",
        "note": "Settings will be applied on next application restart",
    }


# Listen up, reset is also a TODO stub - it SAYS it resets but doesn't actually do anything! Implementing
# this is DANGEROUS - you could delete user's API keys, break integrations, lose custom config. Add a
# "are you sure?" modal in UI! The reset should: 1) Clear DB config rows, 2) Delete .env overrides (not
# the whole .env!), 3) Reload defaults. BUT don't touch database URL or secrets that would lock users out!
# Maybe have "safe reset" (just UI prefs) vs "full reset" (everything). Restart is REQUIRED after reset.
@router.post("/reset")
async def reset_settings() -> dict[str, Any]:
    """Reset all settings to defaults.

    Returns settings to factory defaults by reloading from default Settings() instances.

    Implementation needed:
    - Clear any database-stored settings
    - Remove custom .env overrides
    - Reset in-memory configuration
    - Trigger configuration reload

    Returns:
        Success message with default settings

    Raises:
        HTTPException: If reset operation fails
    """
    # TODO: Implement reset functionality
    # Steps:
    # 1. Delete custom settings from database/file
    # 2. Reload Settings() with defaults
    # 3. Clear any cached configuration
    # 4. Return default settings object
    return {
        "message": "Settings reset to defaults",
        "note": "Please restart the application for changes to take effect",
    }


# Hey, this returns the HARDCODED defaults from the Settings models, not what's currently in use! These
# are the values you get if .env is empty. Useful for UI to show "what's the default for this field?" or
# "reset this one field to default". Notice we return empty strings for secrets, NOT actual defaults from
# Settings classes - we don't want to accidentally leak example secrets or expose hardcoded test values.
# This is safe to call without auth since it's just public defaults.
@router.get("/defaults")
async def get_default_settings() -> AllSettings:
    """Get default settings values.

    Returns:
        Default settings for all categories
    """
    from soulspot.config.settings import (
        APISettings,
        CircuitBreakerSettings,
        MusicBrainzSettings,
        SlskdSettings,
        SpotifySettings,
    )
    from soulspot.config.settings import (
        DownloadSettings as DownloadSettingsModel,
    )

    # Create default instances
    spotify_defaults = SpotifySettings()
    slskd_defaults = SlskdSettings()
    musicbrainz_defaults = MusicBrainzSettings()
    download_defaults = DownloadSettingsModel()
    api_defaults = APISettings()
    circuit_breaker_defaults = CircuitBreakerSettings()

    return AllSettings(
        general=GeneralSettings(
            app_name="SoulSpot",
            log_level="INFO",
            debug=False,
        ),
        integration=IntegrationSettings(
            spotify_client_id=spotify_defaults.client_id,
            spotify_client_secret="",  # nosec B106 - empty string default, not a password
            spotify_redirect_uri=spotify_defaults.redirect_uri,
            slskd_url=slskd_defaults.url,
            slskd_username=slskd_defaults.username,
            slskd_password="",  # nosec B106 - empty string default, not a password
            slskd_api_key=slskd_defaults.api_key,
            musicbrainz_app_name=musicbrainz_defaults.app_name,
            musicbrainz_contact=musicbrainz_defaults.contact,
        ),
        download=DownloadSettings(
            max_concurrent_downloads=download_defaults.max_concurrent_downloads,
            default_max_retries=download_defaults.default_max_retries,
            enable_priority_queue=download_defaults.enable_priority_queue,
        ),
        appearance=AppearanceSettings(
            theme="auto",
        ),
        advanced=AdvancedSettings(
            api_host=api_defaults.host,
            api_port=api_defaults.port,
            circuit_breaker_failure_threshold=circuit_breaker_defaults.failure_threshold,
            circuit_breaker_timeout=circuit_breaker_defaults.timeout,
        ),
    )
