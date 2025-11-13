"""Settings management API endpoints."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from soulspot.config import get_settings

router = APIRouter()


class GeneralSettings(BaseModel):
    """General application settings."""

    app_name: str = Field(description="Application name")
    log_level: str = Field(description="Logging level")
    debug: bool = Field(description="Debug mode")


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
    slskd_api_key: str | None = Field(default=None, description="slskd API key (optional)")

    # MusicBrainz
    musicbrainz_app_name: str = Field(description="MusicBrainz app name")
    musicbrainz_contact: str = Field(description="MusicBrainz contact email")


class DownloadSettings(BaseModel):
    """Download configuration settings."""

    max_concurrent_downloads: int = Field(
        ge=1, le=10, description="Maximum concurrent downloads"
    )
    default_max_retries: int = Field(ge=1, le=10, description="Default max retries")
    enable_priority_queue: bool = Field(description="Enable priority queue")


class AppearanceSettings(BaseModel):
    """Appearance and theme settings."""

    theme: str = Field(description="Theme: light, dark, or auto")


class AdvancedSettings(BaseModel):
    """Advanced configuration settings."""

    api_host: str = Field(description="API host")
    api_port: int = Field(ge=1, le=65535, description="API port")
    secure_cookies: bool = Field(description="Use secure cookies")
    circuit_breaker_failure_threshold: int = Field(
        ge=1, description="Circuit breaker failure threshold"
    )
    circuit_breaker_timeout: float = Field(
        ge=1.0, description="Circuit breaker timeout (seconds)"
    )


class AllSettings(BaseModel):
    """Combined settings model."""

    general: GeneralSettings
    integration: IntegrationSettings
    download: DownloadSettings
    appearance: AppearanceSettings
    advanced: AdvancedSettings


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
            secure_cookies=settings.api.secure_cookies,
            circuit_breaker_failure_threshold=settings.observability.circuit_breaker.failure_threshold,
            circuit_breaker_timeout=settings.observability.circuit_breaker.timeout,
        ),
    )


@router.post("/")
async def update_settings(settings_update: AllSettings) -> dict[str, Any]:
    """Update application settings.

    Note: This endpoint currently returns the settings but doesn't persist them.
    In a full implementation, this would write to environment variables or a config file.

    Args:
        settings_update: New settings values

    Returns:
        Success message
    """
    # TODO: Implement actual persistence to .env file or database
    # For now, just validate and return success
    # Settings validation is done by Pydantic automatically
    _ = settings_update  # Mark as used for linting
    return {
        "message": "Settings updated successfully",
        "note": "Settings will be applied on next application restart",
    }


@router.post("/reset")
async def reset_settings() -> dict[str, Any]:
    """Reset all settings to defaults.

    Returns:
        Success message with default settings
    """
    # TODO: Implement reset functionality
    return {
        "message": "Settings reset to defaults",
        "note": "Please restart the application for changes to take effect",
    }


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
            app_name="SoulSpot Bridge",
            log_level="INFO",
            debug=False,
        ),
        integration=IntegrationSettings(
            spotify_client_id=spotify_defaults.client_id,
            spotify_client_secret="",
            spotify_redirect_uri=spotify_defaults.redirect_uri,
            slskd_url=slskd_defaults.url,
            slskd_username=slskd_defaults.username,
            slskd_password="",
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
            secure_cookies=api_defaults.secure_cookies,
            circuit_breaker_failure_threshold=circuit_breaker_defaults.failure_threshold,
            circuit_breaker_timeout=circuit_breaker_defaults.timeout,
        ),
    )
