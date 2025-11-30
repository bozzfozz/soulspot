"""Settings management API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.config import get_settings

logger = logging.getLogger(__name__)

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
# devtools, logs, error tracking, etc. General/Integration/Advanced come from env vars (get_settings()).
# Download settings are NOW read from DB if set, with env as fallback - this allows runtime changes!
# UPDATE: General settings (log_level, debug, app_name) now ALSO come from DB with env fallback!
@router.get("/")
async def get_all_settings(
    db: AsyncSession = Depends(get_db_session),
) -> AllSettings:
    """Get all current settings.

    General settings (log_level, debug, app_name) are read from database (if set) with env as fallback.
    Download settings are read from database (if set) with env as fallback.
    Other settings are read directly from environment variables.

    Returns:
        All application settings grouped by category
    """
    settings = get_settings()
    settings_service = AppSettingsService(db)

    # General settings from DB (with env fallback) - allows runtime log level changes!
    general_summary = await settings_service.get_general_settings_summary(
        env_settings={
            "app_name": settings.app_name,
            "log_level": settings.log_level,
            "debug": settings.debug,
        }
    )

    # Download settings from DB (with env fallback)
    download_summary = await settings_service.get_download_settings_summary()

    return AllSettings(
        general=GeneralSettings(
            app_name=general_summary["app_name"],
            log_level=general_summary["log_level"],
            debug=general_summary["debug"],
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
            max_concurrent_downloads=download_summary["max_concurrent_downloads"],
            default_max_retries=download_summary["default_max_retries"],
            enable_priority_queue=download_summary["enable_priority_queue"],
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


# Hey future me - POST /settings/ now actually persists SOME settings to DB!
# Download settings are saved to DB (can be changed at runtime).
# General settings (log_level!) are ALSO saved to DB and applied immediately!
# Other settings (Integration, Advanced) are env-based and require restart.
# Log level change is INSTANT - no restart needed!
@router.post("/")
async def update_settings(
    settings_update: AllSettings,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update application settings.

    General settings (log_level, debug, app_name) are persisted to database.
    Log level changes take effect IMMEDIATELY without restart!
    Download settings are persisted to database and take effect immediately.
    Other settings (Integration, Advanced) are environment-based
    and require application restart to take effect.

    Args:
        settings_update: New settings values

    Returns:
        Success message with details about which settings are persisted

    Raises:
        HTTPException: If settings validation fails
    """
    settings_service = AppSettingsService(db)

    # Persist General settings to DB - log_level changes apply immediately!
    try:
        await settings_service.set_log_level(settings_update.general.log_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await settings_service.set(
        "general.debug",
        settings_update.general.debug,
        value_type="boolean",
        category="general",
    )
    await settings_service.set(
        "general.app_name",
        settings_update.general.app_name,
        value_type="string",
        category="general",
    )

    # Persist Download settings to DB (these take effect immediately)
    await settings_service.set(
        "download.max_concurrent_downloads",
        settings_update.download.max_concurrent_downloads,
        value_type="integer",
        category="download",
    )
    await settings_service.set(
        "download.default_max_retries",
        settings_update.download.default_max_retries,
        value_type="integer",
        category="download",
    )
    await settings_service.set(
        "download.enable_priority_queue",
        settings_update.download.enable_priority_queue,
        value_type="boolean",
        category="download",
    )

    await db.commit()

    logger.info(
        "Settings updated: log_level=%s, debug=%s",
        settings_update.general.log_level,
        settings_update.general.debug,
    )

    # Note: Integration and Advanced settings are env-based
    # They're validated by Pydantic but not persisted to DB
    return {
        "message": "Settings saved",
        "persisted": ["general", "download"],
        "immediate_effect": ["log_level", "download"],
        "requires_restart": ["integration", "advanced"],
        "note": "Log level and download settings take effect immediately. Integration and advanced settings require restart.",
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


# =============================================================================
# SPOTIFY SYNC SETTINGS (DYNAMIC, DB-STORED)
# =============================================================================
# Hey future me - these are DIFFERENT from the static IntegrationSettings above!
# These settings are stored in the app_settings table and can be changed at runtime
# without restarting the app. They control Spotify sync behavior.
# =============================================================================


class SpotifySyncSettings(BaseModel):
    """Spotify sync configuration - changeable at runtime.

    These settings control how SoulSpot syncs data from Spotify.
    They're stored in DB and can be toggled from Settings UI.
    """

    auto_sync_enabled: bool = Field(
        default=True, description="Master switch for all auto-sync"
    )
    auto_sync_artists: bool = Field(
        default=True, description="Auto-sync followed artists"
    )
    auto_sync_playlists: bool = Field(
        default=True, description="Auto-sync user playlists"
    )
    auto_sync_liked_songs: bool = Field(
        default=True, description="Auto-sync Liked Songs"
    )
    auto_sync_saved_albums: bool = Field(
        default=True, description="Auto-sync Saved Albums"
    )
    artists_sync_interval_minutes: int = Field(
        default=5, ge=1, le=60, description="Cooldown between artist syncs (minutes)"
    )
    playlists_sync_interval_minutes: int = Field(
        default=10, ge=1, le=60, description="Cooldown between playlist syncs (minutes)"
    )
    download_images: bool = Field(
        default=True, description="Download and store images locally"
    )
    remove_unfollowed_artists: bool = Field(
        default=True, description="Remove artists when unfollowed on Spotify"
    )
    remove_unfollowed_playlists: bool = Field(
        default=False, description="Remove playlists when deleted on Spotify"
    )


class SpotifyImageStats(BaseModel):
    """Disk usage statistics for Spotify images."""

    artists_bytes: int = Field(description="Bytes used by artist images")
    albums_bytes: int = Field(description="Bytes used by album covers")
    playlists_bytes: int = Field(description="Bytes used by playlist covers")
    total_bytes: int = Field(description="Total bytes used")
    artists_count: int = Field(description="Number of artist images")
    albums_count: int = Field(description="Number of album covers")
    playlists_count: int = Field(description="Number of playlist covers")
    total_count: int = Field(description="Total number of images")


class SpotifySyncSettingsResponse(BaseModel):
    """Response for Spotify sync settings with additional metadata."""

    settings: SpotifySyncSettings
    image_stats: SpotifyImageStats | None = Field(
        default=None, description="Image disk usage (if available)"
    )


@router.get("/spotify-sync")
async def get_spotify_sync_settings(
    db: AsyncSession = Depends(get_db_session),
) -> SpotifySyncSettingsResponse:
    """Get Spotify sync settings.

    Returns current sync configuration from database.
    These are runtime-editable settings, not env vars.

    Returns:
        Current Spotify sync settings and image statistics
    """
    settings_service = AppSettingsService(db)
    summary = await settings_service.get_spotify_settings_summary()

    # Get image stats if possible
    image_stats = None
    try:
        from soulspot.application.services.spotify_image_service import (
            SpotifyImageService,
        )

        app_settings = get_settings()
        image_service = SpotifyImageService(app_settings)

        disk_usage = image_service.get_disk_usage()
        image_count = image_service.get_image_count()

        image_stats = SpotifyImageStats(
            artists_bytes=disk_usage.get("artists", 0),
            albums_bytes=disk_usage.get("albums", 0),
            playlists_bytes=disk_usage.get("playlists", 0),
            total_bytes=disk_usage.get("total", 0),
            artists_count=image_count.get("artists", 0),
            albums_count=image_count.get("albums", 0),
            playlists_count=image_count.get("playlists", 0),
            total_count=image_count.get("total", 0),
        )
    except (OSError, ValueError) as e:
        # Hey future me - image stats are optional, don't fail the entire response if
        # SpotifyImageService can't access the disk or config is invalid.
        logger.debug("Could not fetch Spotify image stats: %s", e)

    return SpotifySyncSettingsResponse(
        settings=SpotifySyncSettings(**summary),
        image_stats=image_stats,
    )


@router.put("/spotify-sync")
async def update_spotify_sync_settings(
    settings_update: SpotifySyncSettings,
    db: AsyncSession = Depends(get_db_session),
) -> SpotifySyncSettings:
    """Update Spotify sync settings.

    These changes take effect immediately - no restart required!

    Args:
        settings_update: New settings values

    Returns:
        Updated settings
    """
    settings_service = AppSettingsService(db)

    # Update each setting
    await settings_service.set(
        "spotify.auto_sync_enabled",
        settings_update.auto_sync_enabled,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.auto_sync_artists",
        settings_update.auto_sync_artists,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.auto_sync_playlists",
        settings_update.auto_sync_playlists,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.auto_sync_liked_songs",
        settings_update.auto_sync_liked_songs,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.auto_sync_saved_albums",
        settings_update.auto_sync_saved_albums,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.artists_sync_interval_minutes",
        settings_update.artists_sync_interval_minutes,
        value_type="integer",
        category="spotify",
    )
    await settings_service.set(
        "spotify.playlists_sync_interval_minutes",
        settings_update.playlists_sync_interval_minutes,
        value_type="integer",
        category="spotify",
    )
    await settings_service.set(
        "spotify.download_images",
        settings_update.download_images,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.remove_unfollowed_artists",
        settings_update.remove_unfollowed_artists,
        value_type="boolean",
        category="spotify",
    )
    await settings_service.set(
        "spotify.remove_unfollowed_playlists",
        settings_update.remove_unfollowed_playlists,
        value_type="boolean",
        category="spotify",
    )

    await db.commit()

    return settings_update


@router.post("/spotify-sync/toggle/{setting_name}")
async def toggle_spotify_sync_setting(
    setting_name: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Toggle a boolean Spotify sync setting.

    Quick toggle for UI switches - flips current value.

    Args:
        setting_name: Name of the setting (e.g., "auto_sync_enabled")

    Returns:
        New setting value
    """
    # Map simple names to full setting keys
    key_mapping = {
        "auto_sync_enabled": "spotify.auto_sync_enabled",
        "auto_sync_artists": "spotify.auto_sync_artists",
        "auto_sync_playlists": "spotify.auto_sync_playlists",
        "auto_sync_liked_songs": "spotify.auto_sync_liked_songs",
        "auto_sync_saved_albums": "spotify.auto_sync_saved_albums",
        "download_images": "spotify.download_images",
        "remove_unfollowed_artists": "spotify.remove_unfollowed_artists",
        "remove_unfollowed_playlists": "spotify.remove_unfollowed_playlists",
    }

    setting_key = key_mapping.get(setting_name)
    if not setting_key:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting: {setting_name}. Valid settings: {list(key_mapping.keys())}",
        )

    settings_service = AppSettingsService(db)

    # Get current value and toggle
    current_value = await settings_service.get_bool(setting_key, default=True)
    new_value = not current_value

    await settings_service.set(
        setting_key,
        new_value,
        value_type="boolean",
        category="spotify",
    )
    await db.commit()

    return {
        "setting": setting_name,
        "old_value": current_value,
        "new_value": new_value,
    }


@router.get("/spotify-sync/image-stats")
async def get_spotify_image_stats() -> SpotifyImageStats:
    """Get disk usage statistics for Spotify images.

    Returns breakdown of storage used by artist, album, and playlist images.
    """
    from soulspot.application.services.spotify_image_service import SpotifyImageService

    app_settings = get_settings()
    image_service = SpotifyImageService(app_settings)

    disk_usage = image_service.get_disk_usage()
    image_count = image_service.get_image_count()

    return SpotifyImageStats(
        artists_bytes=disk_usage.get("artists", 0),
        albums_bytes=disk_usage.get("albums", 0),
        playlists_bytes=disk_usage.get("playlists", 0),
        total_bytes=disk_usage.get("total", 0),
        artists_count=image_count.get("artists", 0),
        albums_count=image_count.get("albums", 0),
        playlists_count=image_count.get("playlists", 0),
        total_count=image_count.get("total", 0),
    )


# Hey future me – dieser Endpoint ist ein Alias für image-stats, damit das JS von der
# Settings-Seite funktioniert. Der URL-Pfad /disk-usage ist intuitiver für UI-Entwickler.
@router.get("/spotify-sync/disk-usage")
async def get_spotify_disk_usage() -> SpotifyImageStats:
    """Alias for image-stats - get disk usage for Spotify images."""
    return await get_spotify_image_stats()


# =============================================================================
# SPOTIFY DATABASE STATS
# =============================================================================
# Hey future me - diese Stats zeigen wieviele Entities aus Spotify in der DB sind!
# Das ist ANDERS als Image Stats (die zählen Dateien auf der Festplatte).
# Hier zählen wir Artists/Albums/Tracks mit spotify_uri und Playlists mit source=spotify.
# =============================================================================


class SpotifyDbStats(BaseModel):
    """Database statistics for Spotify-synced entities."""

    artists_count: int = Field(description="Number of artists synced from Spotify")
    albums_count: int = Field(description="Number of albums synced from Spotify")
    tracks_count: int = Field(description="Number of tracks synced from Spotify")
    playlists_count: int = Field(description="Number of playlists synced from Spotify")
    total_count: int = Field(description="Total number of entities")


@router.get("/spotify-sync/db-stats")
async def get_spotify_db_stats(
    db: AsyncSession = Depends(get_db_session),
) -> SpotifyDbStats:
    """Get database statistics for Spotify-synced entities.

    Counts how many artists, albums, tracks, and playlists were synced from Spotify.
    This counts from BOTH:
    1. Local entities with Spotify URIs (enriched with Spotify data)
    2. Spotify browse tables (spotify_artists, spotify_albums, spotify_tracks from auto-sync)
    3. Liked Songs tracks (stored in soulspot_tracks with spotify_uri)

    Returns:
        Counts of each entity type from Spotify
    """
    from soulspot.infrastructure.persistence.repositories import (
        AlbumRepository,
        ArtistRepository,
        PlaylistRepository,
        SpotifyBrowseRepository,
        TrackRepository,
    )

    # Count local entities with Spotify URIs
    artist_repo = ArtistRepository(db)
    album_repo = AlbumRepository(db)
    track_repo = TrackRepository(db)
    playlist_repo = PlaylistRepository(db)

    local_artists_count = await artist_repo.count_with_spotify_uri()
    local_albums_count = await album_repo.count_with_spotify_uri()
    local_tracks_count = await track_repo.count_with_spotify_uri()
    local_playlists_count = await playlist_repo.count_by_source("spotify")

    # Count Spotify browse data (from auto-sync)
    spotify_repo = SpotifyBrowseRepository(db)
    spotify_artists_count = await spotify_repo.count_artists()
    spotify_albums_count = await spotify_repo.count_albums()
    spotify_tracks_count = await spotify_repo.count_tracks()
    
    # Count Liked Songs tracks (they're in soulspot_tracks but also need to be counted)
    # Hey future me - Liked Songs sync creates tracks in soulspot_tracks with spotify_uri.
    # The local_tracks_count above should already include them, but we also count 
    # from the Liked Songs playlist to ensure accuracy.
    liked_songs_count = await spotify_repo.count_liked_songs_tracks()

    # Combine: use the HIGHER count between local and spotify tables
    # local_tracks_count includes Liked Songs (after our fix) and manually added tracks
    # spotify_tracks_count is album tracks from lazy-loading
    # liked_songs_count ensures we count Liked Songs even if not yet in soulspot_tracks
    artists_count = max(local_artists_count, spotify_artists_count)
    albums_count = max(local_albums_count, spotify_albums_count)
    
    # For tracks: combine spotify_tracks (album tracks) + liked_songs OR local_tracks
    # Hey future me - we take max because after sync, liked songs go INTO soulspot_tracks
    # So local_tracks_count should equal liked_songs_count once sync completes
    tracks_count = max(local_tracks_count, spotify_tracks_count + liked_songs_count)
    playlists_count = local_playlists_count

    total = artists_count + albums_count + tracks_count + playlists_count

    return SpotifyDbStats(
        artists_count=artists_count,
        albums_count=albums_count,
        tracks_count=tracks_count,
        playlists_count=playlists_count,
        total_count=total,
    )


class SyncTriggerResponse(BaseModel):
    """Response for manual sync trigger."""

    success: bool = Field(description="Whether sync was started")
    message: str = Field(description="Status message")
    sync_type: str = Field(description="Type of sync triggered")


# Hey future me – dieser Endpoint triggert einen manuellen Sync. Er läuft synchron,
# d.h. er wartet auf den Sync bevor er zurückkehrt. Das ist für kleine Syncs OK,
# aber bei großen Bibliotheken könnte das ein Timeout geben. Dann müsste man das
# auf Background Tasks umstellen (FastAPI BackgroundTasks oder Celery).
# WICHTIG: Die sync_type Werte müssen mit dem JavaScript matchen!
@router.post("/spotify-sync/trigger/{sync_type}")
async def trigger_manual_sync(
    sync_type: str,
    db: AsyncSession = Depends(get_db_session),
) -> SyncTriggerResponse:
    """Trigger a manual Spotify sync.

    Runs the specified sync immediately, regardless of cooldown timers.

    Args:
        sync_type: Type of sync - 'artists', 'playlists', 'liked', 'albums', or 'all'

    Returns:
        Success status and message
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.spotify_image_service import SpotifyImageService
    from soulspot.application.services.spotify_sync_service import SpotifySyncService
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
    from soulspot.infrastructure.persistence.repositories import SpotifyTokenRepository

    valid_types = {"artists", "playlists", "liked", "albums", "all"}
    if sync_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sync type: {sync_type}. Valid types: {valid_types}",
        )

    app_settings = get_settings()

    # Get token from database using repository
    token_repo = SpotifyTokenRepository(db)
    token = await token_repo.get_active_token()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    spotify_client = SpotifyClient(app_settings.spotify)
    image_service = SpotifyImageService(app_settings)
    settings_service = AppSettingsService(db)

    sync_service = SpotifySyncService(
        session=db,
        spotify_client=spotify_client,
        image_service=image_service,
        settings_service=settings_service,
    )

    # Hey future me – das access_token holen wir aus dem gespeicherten Token.
    access_token = token.access_token

    try:
        if sync_type == "artists":
            result = await sync_service.sync_followed_artists(access_token, force=True)
            message = f"Artists synced: {result.get('synced', 0)} updated, {result.get('removed', 0)} removed"

        elif sync_type == "playlists":
            result = await sync_service.sync_user_playlists(access_token, force=True)
            message = f"Playlists synced: {result.get('synced', 0)} updated, {result.get('removed', 0)} removed"

        elif sync_type == "liked":
            result = await sync_service.sync_liked_songs(access_token, force=True)
            message = f"Liked Songs synced: {result.get('track_count', 0)} tracks"

        elif sync_type == "albums":
            result = await sync_service.sync_saved_albums(access_token, force=True)
            message = f"Saved Albums synced: {result.get('synced', 0)} updated"

        elif sync_type == "all":
            # Run all syncs
            results = await sync_service.run_full_sync(access_token, force=True)
            # Die Ergebnisse sind dicts mit details, extrahiere die Counts
            artists_count = (
                results.get("artists", {}).get("synced", 0)
                if results.get("artists")
                else 0
            )
            playlists_count = (
                results.get("playlists", {}).get("synced", 0)
                if results.get("playlists")
                else 0
            )
            albums_count = (
                results.get("saved_albums", {}).get("synced", 0)
                if results.get("saved_albums")
                else 0
            )
            message = f"Full sync complete: {artists_count} artists, {playlists_count} playlists, {albums_count} albums"

        await db.commit()

        return SyncTriggerResponse(
            success=True,
            message=message,
            sync_type=sync_type,
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}",
        ) from e


class SyncWorkerStatus(BaseModel):
    """Status information for the Spotify sync worker."""

    running: bool = Field(description="Whether the worker is currently running")
    check_interval_seconds: int = Field(
        description="How often the worker checks for due syncs"
    )
    last_sync: dict[str, str | None] = Field(
        description="Last sync time for each sync type"
    )
    stats: dict[str, dict[str, Any]] = Field(description="Sync statistics")


# Hey future me – dieser Endpoint gibt den Status des SpotifySyncWorkers zurück.
# Nützlich für Monitoring und Debugging. Zeigt an wann der letzte Sync war und
# ob es Fehler gab.
@router.get("/spotify-sync/worker-status")
async def get_spotify_sync_worker_status(
    request: Request,
) -> SyncWorkerStatus:
    """Get the status of the Spotify sync background worker.

    Returns information about:
    - Whether the worker is running
    - Last sync times for each type
    - Sync statistics and errors

    Returns:
        Worker status information
    """
    # Get worker from app state
    if not hasattr(request.app.state, "spotify_sync_worker"):
        raise HTTPException(
            status_code=503,
            detail="Spotify sync worker not initialized",
        )

    worker = request.app.state.spotify_sync_worker
    status = worker.get_status()

    return SyncWorkerStatus(
        running=status["running"],
        check_interval_seconds=status["check_interval_seconds"],
        last_sync=status["last_sync"],
        stats=status["stats"],
    )


# =====================================================
# Automation Settings Endpoints
# =====================================================


class AutomationSettings(BaseModel):
    """Automation settings for background workers.

    Hey future me – diese Settings kontrollieren die Automation-Worker!
    Alle Worker sind per Default DISABLED (opt-in) weil sie potenziell
    invasiv sind (löschen Dateien, starten Downloads automatisch).
    """

    # Watchlist Worker
    watchlist_enabled: bool = Field(
        default=False, description="Enable watchlist monitoring for new releases"
    )
    watchlist_interval_minutes: int = Field(
        default=60, ge=15, le=1440, description="Watchlist check interval in minutes"
    )

    # Discography Worker
    discography_enabled: bool = Field(
        default=False, description="Enable discography completion scanning"
    )
    discography_interval_hours: int = Field(
        default=24, ge=1, le=168, description="Discography scan interval in hours"
    )

    # Quality Upgrade Worker
    quality_upgrade_enabled: bool = Field(
        default=False, description="Enable quality upgrade detection"
    )
    quality_profile: str = Field(
        default="high", description="Target quality profile (medium, high, lossless)"
    )

    # Cleanup Worker
    cleanup_enabled: bool = Field(
        default=False, description="Enable auto-cleanup of temp files"
    )
    cleanup_retention_days: int = Field(
        default=7, ge=1, le=90, description="File retention period in days"
    )

    # Duplicate Detection Worker
    duplicate_detection_enabled: bool = Field(
        default=False, description="Enable duplicate track detection"
    )
    duplicate_scan_interval_hours: int = Field(
        default=168, ge=24, le=720, description="Duplicate scan interval in hours"
    )


class AutomationSettingsResponse(BaseModel):
    """Response wrapper for automation settings."""

    settings: AutomationSettings
    worker_status: dict[str, bool] | None = Field(
        default=None, description="Current worker running status"
    )


# Hey future me – dieser Endpoint gibt alle Automation Settings zurück.
# Die Settings kommen aus der DB via AppSettingsService.
@router.get("/automation")
async def get_automation_settings(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> AutomationSettingsResponse:
    """Get automation settings.

    Returns current automation configuration from database.
    These are runtime-editable settings for background workers.

    Returns:
        Current automation settings and worker status
    """
    settings_service = AppSettingsService(db)
    summary = await settings_service.get_automation_settings_summary()

    # Get worker status if available
    worker_status = None
    if hasattr(request.app.state, "automation_manager"):
        worker_status = request.app.state.automation_manager.get_status()

    return AutomationSettingsResponse(
        settings=AutomationSettings(**summary),
        worker_status=worker_status,
    )


# Hey future me – dieser Endpoint updated alle Automation Settings auf einmal.
# Die Changes werden sofort in der DB gespeichert und wirken sich auf die Worker aus.
@router.put("/automation")
async def update_automation_settings(
    settings_update: AutomationSettings,
    db: AsyncSession = Depends(get_db_session),
) -> AutomationSettings:
    """Update automation settings.

    These changes take effect immediately - no restart required!

    Args:
        settings_update: New settings values

    Returns:
        Updated settings
    """
    settings_service = AppSettingsService(db)

    # Update each setting
    await settings_service.set(
        "automation.watchlist_enabled",
        settings_update.watchlist_enabled,
        value_type="boolean",
        category="automation",
    )
    await settings_service.set(
        "automation.watchlist_interval_minutes",
        settings_update.watchlist_interval_minutes,
        value_type="integer",
        category="automation",
    )
    await settings_service.set(
        "automation.discography_enabled",
        settings_update.discography_enabled,
        value_type="boolean",
        category="automation",
    )
    await settings_service.set(
        "automation.discography_interval_hours",
        settings_update.discography_interval_hours,
        value_type="integer",
        category="automation",
    )
    await settings_service.set(
        "automation.quality_upgrade_enabled",
        settings_update.quality_upgrade_enabled,
        value_type="boolean",
        category="automation",
    )
    await settings_service.set(
        "automation.quality_profile",
        settings_update.quality_profile,
        value_type="string",
        category="automation",
    )
    await settings_service.set(
        "automation.cleanup_enabled",
        settings_update.cleanup_enabled,
        value_type="boolean",
        category="automation",
    )
    await settings_service.set(
        "automation.cleanup_retention_days",
        settings_update.cleanup_retention_days,
        value_type="integer",
        category="automation",
    )
    await settings_service.set(
        "automation.duplicate_detection_enabled",
        settings_update.duplicate_detection_enabled,
        value_type="boolean",
        category="automation",
    )
    await settings_service.set(
        "automation.duplicate_scan_interval_hours",
        settings_update.duplicate_scan_interval_hours,
        value_type="integer",
        category="automation",
    )

    await db.commit()

    return settings_update


# Hey future me – dieser Endpoint updated einzelne Automation Settings.
# Nützlich für Toggle-Buttons die nur einen Wert ändern.
@router.patch("/automation")
async def patch_automation_setting(
    setting_update: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update a single automation setting.

    Args:
        setting_update: Dict with setting name and new value

    Returns:
        Success message with updated value
    """
    settings_service = AppSettingsService(db)

    # Map setting names to their types
    setting_types = {
        "watchlist_enabled": "boolean",
        "watchlist_interval_minutes": "integer",
        "discography_enabled": "boolean",
        "discography_interval_hours": "integer",
        "quality_upgrade_enabled": "boolean",
        "quality_profile": "string",
        "cleanup_enabled": "boolean",
        "cleanup_retention_days": "integer",
        "duplicate_detection_enabled": "boolean",
        "duplicate_scan_interval_hours": "integer",
    }

    updated = {}
    for key, value in setting_update.items():
        if key in setting_types:
            await settings_service.set(
                f"automation.{key}",
                value,
                value_type=setting_types[key],
                category="automation",
            )
            updated[key] = value

    await db.commit()

    return {"message": "Setting updated", "updated": updated}


# =============================================================================
# LIBRARY NAMING SETTINGS
# =============================================================================
# Hey future me – diese Settings kontrollieren wie Dateien und Ordner benannt werden!
# WICHTIG: Diese Settings müssen mit Lidarr kompatibel sein, da beide Tools auf
# dieselbe Music Library zugreifen. Defaults sind Lidarr-Standard.
#
# Nur NEUE Downloads werden automatisch benannt. Bestehende Dateien bleiben
# unverändert, es sei denn User löst manuellen Batch-Rename aus.
# =============================================================================


class NamingSettings(BaseModel):
    """Library naming configuration for files and folders.

    These settings control how files and folders are named when importing
    music. Templates support variables like {Artist Name}, {Album Title}, etc.

    Defaults match Lidarr's recommended format for compatibility.
    """

    # Template formats
    artist_folder_format: str = Field(
        default="{Artist Name}",
        description="Template for artist folder names",
        examples=["{Artist Name}", "{Artist CleanName}"],
    )
    album_folder_format: str = Field(
        default="{Album Title} ({Release Year})",
        description="Template for album folder names",
        examples=["{Album Title} ({Release Year})", "{Album Title}"],
    )
    standard_track_format: str = Field(
        default="{Track Number:00} - {Track Title}",
        description="Template for single-disc track filenames",
        examples=["{Track Number:00} - {Track Title}", "{track:02d} {title}"],
    )
    multi_disc_track_format: str = Field(
        default="{Medium:00}-{Track Number:00} - {Track Title}",
        description="Template for multi-disc track filenames",
        examples=["{Medium:00}-{Track Number:00} - {Track Title}"],
    )

    # Behavior toggles
    rename_tracks: bool = Field(
        default=True,
        description="Enable automatic file renaming on import",
    )
    replace_illegal_characters: bool = Field(
        default=True,
        description="Replace characters not allowed in filenames",
    )
    create_artist_folder: bool = Field(
        default=True,
        description="Create artist folder if it doesn't exist",
    )
    create_album_folder: bool = Field(
        default=True,
        description="Create album folder if it doesn't exist",
    )

    # Character replacements
    colon_replacement: str = Field(
        default=" -",
        description="Replacement for colon character",
        max_length=10,
    )
    slash_replacement: str = Field(
        default="-",
        description="Replacement for slash character",
        max_length=10,
    )


class NamingValidationRequest(BaseModel):
    """Request to validate a naming template."""

    template: str = Field(description="Template string to validate")


class NamingValidationResponse(BaseModel):
    """Response from template validation."""

    valid: bool = Field(description="Whether template is valid")
    invalid_variables: list[str] = Field(
        default_factory=list,
        description="List of invalid variables found",
    )
    preview: str | None = Field(
        default=None,
        description="Preview of rendered template (if valid)",
    )


class NamingPreviewRequest(BaseModel):
    """Request to preview naming with sample data."""

    artist_folder_format: str = Field(default="{Artist Name}")
    album_folder_format: str = Field(default="{Album Title} ({Release Year})")
    standard_track_format: str = Field(default="{Track Number:00} - {Track Title}")


class NamingPreviewResponse(BaseModel):
    """Response with preview path."""

    full_path: str = Field(description="Full rendered path")
    artist_folder: str = Field(description="Rendered artist folder name")
    album_folder: str = Field(description="Rendered album folder name")
    track_filename: str = Field(description="Rendered track filename")


@router.get("/naming")
async def get_naming_settings(
    db: AsyncSession = Depends(get_db_session),
) -> NamingSettings:
    """Get library naming settings.

    Returns current file/folder naming configuration from database.
    These settings determine how imported music is organized.

    Returns:
        Current naming settings
    """
    settings_service = AppSettingsService(db)
    summary = await settings_service.get_naming_settings_summary()

    return NamingSettings(**summary)


@router.put("/naming")
async def update_naming_settings(
    settings_update: NamingSettings,
    db: AsyncSession = Depends(get_db_session),
) -> NamingSettings:
    """Update library naming settings.

    These changes take effect immediately for NEW imports.
    Existing files are NOT renamed automatically.

    Args:
        settings_update: New settings values

    Returns:
        Updated settings
    """
    settings_service = AppSettingsService(db)

    # Validate templates before saving
    for template_field in [
        "artist_folder_format",
        "album_folder_format",
        "standard_track_format",
        "multi_disc_track_format",
    ]:
        template_value = getattr(settings_update, template_field)
        is_valid, invalid_vars = settings_service.validate_naming_template(
            template_value
        )
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid template for {template_field}: unknown variables {invalid_vars}",
            )

    # Update each setting
    await settings_service.set(
        "naming.artist_folder_format",
        settings_update.artist_folder_format,
        value_type="string",
        category="naming",
    )
    await settings_service.set(
        "naming.album_folder_format",
        settings_update.album_folder_format,
        value_type="string",
        category="naming",
    )
    await settings_service.set(
        "naming.standard_track_format",
        settings_update.standard_track_format,
        value_type="string",
        category="naming",
    )
    await settings_service.set(
        "naming.multi_disc_track_format",
        settings_update.multi_disc_track_format,
        value_type="string",
        category="naming",
    )
    await settings_service.set(
        "naming.rename_tracks",
        settings_update.rename_tracks,
        value_type="boolean",
        category="naming",
    )
    await settings_service.set(
        "naming.replace_illegal_characters",
        settings_update.replace_illegal_characters,
        value_type="boolean",
        category="naming",
    )
    await settings_service.set(
        "naming.create_artist_folder",
        settings_update.create_artist_folder,
        value_type="boolean",
        category="naming",
    )
    await settings_service.set(
        "naming.create_album_folder",
        settings_update.create_album_folder,
        value_type="boolean",
        category="naming",
    )
    await settings_service.set(
        "naming.colon_replacement",
        settings_update.colon_replacement,
        value_type="string",
        category="naming",
    )
    await settings_service.set(
        "naming.slash_replacement",
        settings_update.slash_replacement,
        value_type="string",
        category="naming",
    )

    await db.commit()

    return settings_update


@router.post("/naming/validate")
async def validate_naming_template(
    request: NamingValidationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> NamingValidationResponse:
    """Validate a naming template.

    Checks that all {variable} placeholders are valid.
    Returns list of invalid variables if any found.

    Args:
        request: Template to validate

    Returns:
        Validation result with invalid variables if any
    """
    settings_service = AppSettingsService(db)
    is_valid, invalid_vars = settings_service.validate_naming_template(request.template)

    # Generate preview if valid
    preview = None
    if is_valid:
        # Sample data for preview
        sample_data = {
            "Artist Name": "Pink Floyd",
            "Artist CleanName": "Pink Floyd",
            "Album Title": "The Dark Side of the Moon",
            "Album CleanTitle": "The Dark Side of the Moon",
            "Album Type": "Album",
            "Release Year": "1973",
            "Track Title": "Speak to Me",
            "Track CleanTitle": "Speak to Me",
            "Track Number": "1",
            "Track Number:00": "01",
            "Medium": "1",
            "Medium:00": "01",
            # Legacy variables
            "artist": "Pink Floyd",
            "album": "The Dark Side of the Moon",
            "title": "Speak to Me",
            "track": "1",
            "track:02d": "01",
            "year": "1973",
            "disc": "1",
        }

        preview = request.template
        for var, value in sample_data.items():
            preview = preview.replace(f"{{{var}}}", value)

    return NamingValidationResponse(
        valid=is_valid,
        invalid_variables=invalid_vars,
        preview=preview,
    )


@router.post("/naming/preview")
async def preview_naming_format(
    request: NamingPreviewRequest,
) -> NamingPreviewResponse:
    """Preview how files will be named with current templates.

    Uses sample data to show what the full path would look like.

    Args:
        request: Templates to preview

    Returns:
        Full path preview with sample artist/album/track
    """
    # Sample data for preview
    sample = {
        "Artist Name": "Pink Floyd",
        "Artist CleanName": "Pink Floyd",
        "Album Title": "The Dark Side of the Moon",
        "Album CleanTitle": "The Dark Side of the Moon",
        "Album Type": "Album",
        "Release Year": "1973",
        "Track Title": "Speak to Me",
        "Track CleanTitle": "Speak to Me",
        "Track Number": "1",
        "Track Number:00": "01",
        "Medium": "1",
        "Medium:00": "01",
        # Legacy variables
        "artist": "Pink Floyd",
        "album": "The Dark Side of the Moon",
        "title": "Speak to Me",
        "track": "1",
        "track:02d": "01",
        "year": "1973",
        "disc": "1",
    }

    def render_template(template: str, data: dict[str, str]) -> str:
        result = template
        for var, value in data.items():
            result = result.replace(f"{{{var}}}", value)
        return result

    artist_folder = render_template(request.artist_folder_format, sample)
    album_folder = render_template(request.album_folder_format, sample)
    track_filename = render_template(request.standard_track_format, sample) + ".flac"

    full_path = f"/mnt/music/{artist_folder}/{album_folder}/{track_filename}"

    return NamingPreviewResponse(
        full_path=full_path,
        artist_folder=artist_folder,
        album_folder=album_folder,
        track_filename=track_filename,
    )


@router.get("/naming/variables")
async def get_naming_variables() -> dict[str, list[dict[str, str]]]:
    """Get list of available template variables.

    Returns all supported variables grouped by category.
    Useful for building template editors in UI.

    Returns:
        Variables grouped by category with descriptions
    """
    return {
        "artist": [
            {"variable": "{Artist Name}", "description": "Full artist name"},
            {
                "variable": "{Artist CleanName}",
                "description": "Sanitized artist name (no special chars)",
            },
        ],
        "album": [
            {"variable": "{Album Title}", "description": "Full album title"},
            {"variable": "{Album CleanTitle}", "description": "Sanitized album title"},
            {
                "variable": "{Album Type}",
                "description": "Album type (Album, Single, EP, Compilation)",
            },
            {"variable": "{Release Year}", "description": "Release year (4 digits)"},
        ],
        "track": [
            {"variable": "{Track Title}", "description": "Full track title"},
            {"variable": "{Track CleanTitle}", "description": "Sanitized track title"},
            {"variable": "{Track Number}", "description": "Track number"},
            {
                "variable": "{Track Number:00}",
                "description": "Track number zero-padded (01, 02, ...)",
            },
        ],
        "disc": [
            {"variable": "{Medium}", "description": "Disc number"},
            {"variable": "{Medium:00}", "description": "Disc number zero-padded"},
        ],
        "legacy": [
            {"variable": "{artist}", "description": "Artist name (legacy)"},
            {"variable": "{album}", "description": "Album title (legacy)"},
            {"variable": "{title}", "description": "Track title (legacy)"},
            {"variable": "{track}", "description": "Track number (legacy)"},
            {"variable": "{track:02d}", "description": "Track number padded (legacy)"},
            {"variable": "{year}", "description": "Release year (legacy)"},
            {"variable": "{disc}", "description": "Disc number (legacy)"},
        ],
    }


# =============================================================================
# LIBRARY ENRICHMENT SETTINGS
# =============================================================================
# Hey future me – dieser Endpoint kontrolliert das Auto-Enrichment der Local Library!
# Wenn enabled, wird nach jedem Library Scan automatisch Spotify nach Metadaten durchsucht.
# Super simpel - nur ein Boolean Toggle. Defaults, Batch Size etc. sind hardcoded in
# AppSettingsService weil der User damit nicht rumspielen muss.
# =============================================================================


class LibraryEnrichmentSettings(BaseModel):
    """Library enrichment configuration.

    Just a simple toggle - enrichment runs automatically after library scans.
    Advanced settings (batch size, rate limit, etc.) use sensible defaults.
    """

    auto_enrichment_enabled: bool = Field(
        default=True,
        description="Auto-enrich local library with Spotify metadata after scans",
    )


@router.get("/library/enrichment")
async def get_library_enrichment_settings(
    db: AsyncSession = Depends(get_db_session),
) -> LibraryEnrichmentSettings:
    """Get library enrichment settings.

    Returns current enrichment configuration from database.

    Returns:
        Current enrichment settings (just the auto toggle)
    """
    settings_service = AppSettingsService(db)
    enabled = await settings_service.is_library_auto_enrichment_enabled()

    return LibraryEnrichmentSettings(auto_enrichment_enabled=enabled)


@router.put("/library/enrichment")
async def update_library_enrichment_settings(
    settings_update: LibraryEnrichmentSettings,
    db: AsyncSession = Depends(get_db_session),
) -> LibraryEnrichmentSettings:
    """Update library enrichment settings.

    Toggle takes effect immediately - no restart required.

    Args:
        settings_update: New settings (just auto_enrichment_enabled)

    Returns:
        Updated settings
    """
    settings_service = AppSettingsService(db)

    await settings_service.set(
        "library.auto_enrichment_enabled",
        settings_update.auto_enrichment_enabled,
        value_type="boolean",
        category="library",
    )

    await db.commit()

    return settings_update
