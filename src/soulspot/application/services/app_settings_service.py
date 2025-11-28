"""App Settings Service - Dynamic Runtime Configuration.

Hey future me - this service provides runtime configuration that can be changed
via Settings UI without restarting the app. Unlike env vars in config/settings.py,
these settings are stored in the DB and read on-demand.

Use cases:
- Toggle Spotify auto-sync on/off
- Change sync intervals
- Enable/disable image downloading
- Feature flags

Pattern: Simple key-value store with type coercion.
- Keys are dot-notation strings: 'spotify.auto_sync_enabled'
- Values are stored as strings, converted to proper types on read
- Categories group related settings for UI display

The service caches settings in memory with a TTL to avoid constant DB hits,
while still allowing real-time changes from the Settings page.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.persistence.models import AppSettingsModel

logger = logging.getLogger(__name__)


# Hey future me - cache timeout is short (30s) because we want Settings UI changes
# to take effect quickly, but we also don't want to hit DB on every sync check
CACHE_TTL_SECONDS = 30


class AppSettingsService:
    """Service for managing dynamic application settings.

    Settings are stored in DB and can be changed at runtime without restart.
    Provides typed access with automatic conversion from string storage.

    Usage:
        settings_service = AppSettingsService(session)
        auto_sync = await settings_service.get_bool('spotify.auto_sync_enabled', default=True)
        interval = await settings_service.get_int('spotify.artists_sync_interval_minutes', default=5)
        await settings_service.set('spotify.auto_sync_enabled', False)
    """

    # Class-level cache to share across instances within same process
    # Hey future me - this is intentionally simple. If you need distributed caching, use Redis.
    _cache: dict[str, tuple[Any, datetime]] = {}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with async DB session.

        Args:
            session: SQLAlchemy async session for DB operations.
        """
        self._session = session

    def _get_from_cache(self, key: str) -> tuple[Any, bool]:
        """Get value from cache if not expired.

        Args:
            key: Setting key.

        Returns:
            Tuple of (value, cache_hit). If cache miss or expired, returns (None, False).
        """
        if key in self._cache:
            value, cached_at = self._cache[key]
            if datetime.utcnow() - cached_at < timedelta(seconds=CACHE_TTL_SECONDS):
                return value, True
            # Expired, remove from cache
            del self._cache[key]
        return None, False

    def _set_cache(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp.

        Args:
            key: Setting key.
            value: Parsed value to cache.
        """
        self._cache[key] = (value, datetime.utcnow())

    def invalidate_cache(self, key: str | None = None) -> None:
        """Invalidate cache for specific key or all keys.

        Call this after updating settings to ensure fresh reads.

        Args:
            key: Specific key to invalidate, or None to clear all cache.
        """
        if key is None:
            self._cache.clear()
            logger.debug("Cleared all app settings cache")
        elif key in self._cache:
            del self._cache[key]
            logger.debug(f"Invalidated cache for: {key}")

    async def get_raw(self, key: str) -> AppSettingsModel | None:
        """Get raw setting model from DB.

        Args:
            key: Setting key (e.g., 'spotify.auto_sync_enabled').

        Returns:
            AppSettingsModel or None if not found.
        """
        stmt = select(AppSettingsModel).where(AppSettingsModel.key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_string(self, key: str, default: str | None = None) -> str | None:
        """Get setting value as string.

        Args:
            key: Setting key.
            default: Default value if setting not found.

        Returns:
            Setting value as string, or default.
        """
        # Check cache first
        cached_value, cache_hit = self._get_from_cache(key)
        if cache_hit:
            return cached_value

        setting = await self.get_raw(key)
        value = setting.value if setting else default

        self._set_cache(key, value)
        return value

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get setting value as boolean.

        Interprets 'true', '1', 'yes' as True (case-insensitive).
        Everything else is False.

        Args:
            key: Setting key.
            default: Default value if setting not found.

        Returns:
            Setting value as boolean.
        """
        # Check cache first
        cached_value, cache_hit = self._get_from_cache(key)
        if cache_hit:
            return cached_value

        setting = await self.get_raw(key)
        if setting is None or setting.value is None:
            value = default
        else:
            value = setting.value.lower() in ("true", "1", "yes")

        self._set_cache(key, value)
        return value

    async def get_int(self, key: str, default: int = 0) -> int:
        """Get setting value as integer.

        Args:
            key: Setting key.
            default: Default value if setting not found or invalid.

        Returns:
            Setting value as integer.
        """
        # Check cache first
        cached_value, cache_hit = self._get_from_cache(key)
        if cache_hit:
            return cached_value

        setting = await self.get_raw(key)
        if setting is None or setting.value is None:
            value = default
        else:
            try:
                value = int(setting.value)
            except ValueError:
                logger.warning(f"Invalid integer value for {key}: {setting.value}")
                value = default

        self._set_cache(key, value)
        return value

    async def get_json(self, key: str, default: Any = None) -> Any:
        """Get setting value as parsed JSON.

        Args:
            key: Setting key.
            default: Default value if setting not found or invalid JSON.

        Returns:
            Parsed JSON value (dict, list, etc.).
        """
        # Check cache first
        cached_value, cache_hit = self._get_from_cache(key)
        if cache_hit:
            return cached_value

        setting = await self.get_raw(key)
        if setting is None or setting.value is None:
            value = default
        else:
            try:
                value = json.loads(setting.value)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON value for {key}: {setting.value}")
                value = default

        self._set_cache(key, value)
        return value

    async def set(
        self,
        key: str,
        value: Any,
        value_type: str = "string",
        category: str = "general",
        description: str | None = None,
    ) -> AppSettingsModel:
        """Set a setting value (insert or update).

        Automatically converts value to string for storage.
        Invalidates cache for this key.

        Args:
            key: Setting key.
            value: Value to store (will be converted to string).
            value_type: Type hint ('string', 'boolean', 'integer', 'json').
            category: Category for UI grouping.
            description: Human-readable description.

        Returns:
            Updated or created AppSettingsModel.
        """
        # Convert value to string for storage
        if value_type == "json" and not isinstance(value, str):
            str_value = json.dumps(value)
        elif value_type == "boolean":
            str_value = "true" if value else "false"
        else:
            str_value = str(value) if value is not None else None

        # Upsert pattern
        setting = await self.get_raw(key)
        if setting is None:
            setting = AppSettingsModel(
                key=key,
                value=str_value,
                value_type=value_type,
                category=category,
                description=description,
            )
            self._session.add(setting)
        else:
            setting.value = str_value
            if value_type != "string":  # Only update if explicitly set
                setting.value_type = value_type
            if description:
                setting.description = description

        await self._session.flush()

        # Invalidate cache
        self.invalidate_cache(key)

        logger.debug(f"Set app setting: {key} = {str_value}")
        return setting

    async def delete(self, key: str) -> bool:
        """Delete a setting.

        Args:
            key: Setting key to delete.

        Returns:
            True if deleted, False if not found.
        """
        setting = await self.get_raw(key)
        if setting:
            await self._session.delete(setting)
            await self._session.flush()
            self.invalidate_cache(key)
            logger.debug(f"Deleted app setting: {key}")
            return True
        return False

    async def get_by_category(self, category: str) -> list[AppSettingsModel]:
        """Get all settings in a category.

        Useful for Settings UI to display all Spotify settings at once.

        Args:
            category: Category name (e.g., 'spotify').

        Returns:
            List of settings in that category.
        """
        stmt = (
            select(AppSettingsModel)
            .where(AppSettingsModel.category == category)
            .order_by(AppSettingsModel.key)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self) -> list[AppSettingsModel]:
        """Get all settings.

        Returns:
            List of all app settings.
        """
        stmt = select(AppSettingsModel).order_by(
            AppSettingsModel.category, AppSettingsModel.key
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # SPOTIFY-SPECIFIC CONVENIENCE METHODS
    # =========================================================================
    # Hey future me - these are shortcuts for common Spotify settings.
    # They use the generic get_* methods under the hood, just with nicer names.
    # =========================================================================

    async def is_spotify_auto_sync_enabled(self) -> bool:
        """Check if Spotify auto-sync is globally enabled.

        This is the master switch - if False, no sync happens at all.
        """
        return await self.get_bool("spotify.auto_sync_enabled", default=True)

    async def is_spotify_artists_sync_enabled(self) -> bool:
        """Check if followed artists auto-sync is enabled."""
        if not await self.is_spotify_auto_sync_enabled():
            return False
        return await self.get_bool("spotify.auto_sync_artists", default=True)

    async def is_spotify_playlists_sync_enabled(self) -> bool:
        """Check if playlists auto-sync is enabled."""
        if not await self.is_spotify_auto_sync_enabled():
            return False
        return await self.get_bool("spotify.auto_sync_playlists", default=True)

    async def is_spotify_liked_songs_sync_enabled(self) -> bool:
        """Check if Liked Songs sync is enabled."""
        if not await self.is_spotify_auto_sync_enabled():
            return False
        return await self.get_bool("spotify.auto_sync_liked_songs", default=True)

    async def is_spotify_saved_albums_sync_enabled(self) -> bool:
        """Check if Saved Albums sync is enabled."""
        if not await self.is_spotify_auto_sync_enabled():
            return False
        return await self.get_bool("spotify.auto_sync_saved_albums", default=True)

    async def get_artists_sync_interval(self) -> int:
        """Get cooldown between artist sync runs in minutes."""
        return await self.get_int("spotify.artists_sync_interval_minutes", default=5)

    async def get_playlists_sync_interval(self) -> int:
        """Get cooldown between playlist sync runs in minutes."""
        return await self.get_int("spotify.playlists_sync_interval_minutes", default=10)

    async def should_download_images(self) -> bool:
        """Check if image downloading is enabled."""
        return await self.get_bool("spotify.download_images", default=True)

    async def should_remove_unfollowed_artists(self) -> bool:
        """Check if unfollowed artists should be removed from DB."""
        return await self.get_bool("spotify.remove_unfollowed_artists", default=True)

    async def should_remove_unfollowed_playlists(self) -> bool:
        """Check if deleted playlists should be removed from DB."""
        return await self.get_bool("spotify.remove_unfollowed_playlists", default=False)

    async def get_spotify_settings_summary(self) -> dict[str, Any]:
        """Get summary of all Spotify sync settings for UI display.

        Returns a dict with all settings, useful for Settings page.
        """
        return {
            "auto_sync_enabled": await self.get_bool(
                "spotify.auto_sync_enabled", default=True
            ),
            "auto_sync_artists": await self.get_bool(
                "spotify.auto_sync_artists", default=True
            ),
            "auto_sync_playlists": await self.get_bool(
                "spotify.auto_sync_playlists", default=True
            ),
            "auto_sync_liked_songs": await self.get_bool(
                "spotify.auto_sync_liked_songs", default=True
            ),
            "auto_sync_saved_albums": await self.get_bool(
                "spotify.auto_sync_saved_albums", default=True
            ),
            "artists_sync_interval_minutes": await self.get_int(
                "spotify.artists_sync_interval_minutes", default=5
            ),
            "playlists_sync_interval_minutes": await self.get_int(
                "spotify.playlists_sync_interval_minutes", default=10
            ),
            "download_images": await self.get_bool(
                "spotify.download_images", default=True
            ),
            "remove_unfollowed_artists": await self.get_bool(
                "spotify.remove_unfollowed_artists", default=True
            ),
            "remove_unfollowed_playlists": await self.get_bool(
                "spotify.remove_unfollowed_playlists", default=False
            ),
        }

    # =========================================================================
    # AUTOMATION WORKER SETTINGS
    # =========================================================================
    # Hey future me - diese Settings steuern die Automation Workers!
    # WICHTIG: Alle sind default=False (opt-in) für sicheren Rollout.
    # User müssen Automation explizit in Settings aktivieren.
    # =========================================================================

    async def is_watchlist_automation_enabled(self) -> bool:
        """Check if Watchlist Worker (new release detection) is enabled.

        Default is FALSE - user must explicitly enable in Settings.
        When enabled, worker checks followed artists for new releases.
        """
        return await self.get_bool("automation.watchlist_enabled", default=False)

    async def get_watchlist_interval_seconds(self) -> int:
        """Get interval for watchlist checks in seconds.

        Default is 3600 (1 hour) - how often to check for new releases.
        """
        return await self.get_int("automation.watchlist_interval_seconds", default=3600)

    async def is_discography_automation_enabled(self) -> bool:
        """Check if Discography Worker (completeness check) is enabled.

        Default is FALSE. When enabled, worker scans for missing albums
        in artist discographies and can trigger auto-downloads.
        """
        return await self.get_bool("automation.discography_enabled", default=False)

    async def get_discography_interval_seconds(self) -> int:
        """Get interval for discography checks in seconds.

        Default is 86400 (24 hours) - discographies change slowly.
        """
        return await self.get_int(
            "automation.discography_interval_seconds", default=86400
        )

    async def is_quality_upgrade_enabled(self) -> bool:
        """Check if Quality Upgrade Worker is enabled.

        Default is FALSE. When enabled, worker scans library for tracks
        that could be upgraded to better quality (e.g., MP3 -> FLAC).
        """
        return await self.get_bool("automation.quality_upgrade_enabled", default=False)

    async def get_quality_upgrade_interval_seconds(self) -> int:
        """Get interval for quality upgrade scans in seconds.

        Default is 86400 (24 hours) - quality opportunities don't change often.
        """
        return await self.get_int(
            "automation.quality_upgrade_interval_seconds", default=86400
        )

    async def get_quality_upgrade_min_score(self) -> int:
        """Get minimum improvement score to trigger quality upgrade.

        Score 0-100. Higher = bigger improvement needed.
        Default 20 = significant upgrade (e.g., 128kbps MP3 -> FLAC).
        """
        return await self.get_int("automation.quality_upgrade_min_score", default=20)

    async def is_cleanup_automation_enabled(self) -> bool:
        """Check if Cleanup Worker is enabled.

        Default is FALSE. When enabled, worker identifies orphaned files
        and stale DB entries. Does NOT auto-delete, just marks for review.
        """
        return await self.get_bool("automation.cleanup_enabled", default=False)

    async def get_cleanup_interval_seconds(self) -> int:
        """Get interval for cleanup scans in seconds.

        Default is 86400 (24 hours).
        """
        return await self.get_int("automation.cleanup_interval_seconds", default=86400)

    async def is_duplicate_detection_enabled(self) -> bool:
        """Check if Duplicate Detector Worker is enabled.

        Default is FALSE. When enabled, worker scans library for potential
        duplicate tracks using metadata matching. Stores candidates for
        manual review in duplicate_candidates table.
        """
        return await self.get_bool(
            "automation.duplicate_detection_enabled", default=False
        )

    async def get_duplicate_detection_interval_seconds(self) -> int:
        """Get interval for duplicate detection scans in seconds.

        Default is 86400 (24 hours).
        """
        return await self.get_int(
            "automation.duplicate_detection_interval_seconds", default=86400
        )

    async def get_automation_settings_summary(self) -> dict[str, Any]:
        """Get summary of all automation settings for UI display.

        Returns a dict with all automation settings for the Settings page.
        """
        return {
            # Watchlist (New Release Detection)
            "watchlist_enabled": await self.get_bool(
                "automation.watchlist_enabled", default=False
            ),
            "watchlist_interval_seconds": await self.get_int(
                "automation.watchlist_interval_seconds", default=3600
            ),
            # Discography Completeness
            "discography_enabled": await self.get_bool(
                "automation.discography_enabled", default=False
            ),
            "discography_interval_seconds": await self.get_int(
                "automation.discography_interval_seconds", default=86400
            ),
            # Quality Upgrade
            "quality_upgrade_enabled": await self.get_bool(
                "automation.quality_upgrade_enabled", default=False
            ),
            "quality_upgrade_interval_seconds": await self.get_int(
                "automation.quality_upgrade_interval_seconds", default=86400
            ),
            "quality_upgrade_min_score": await self.get_int(
                "automation.quality_upgrade_min_score", default=20
            ),
            # Cleanup
            "cleanup_enabled": await self.get_bool(
                "automation.cleanup_enabled", default=False
            ),
            "cleanup_interval_seconds": await self.get_int(
                "automation.cleanup_interval_seconds", default=86400
            ),
            # Duplicate Detection
            "duplicate_detection_enabled": await self.get_bool(
                "automation.duplicate_detection_enabled", default=False
            ),
            "duplicate_detection_interval_seconds": await self.get_int(
                "automation.duplicate_detection_interval_seconds", default=86400
            ),
        }

    # =========================================================================
    # LIBRARY NAMING SETTINGS
    # =========================================================================
    # Hey future me - these settings control how files/folders are named!
    # Defaults match Lidarr's recommended format for compatibility.
    # IMPORTANT: Only NEW downloads use these - existing files unchanged unless
    # user triggers manual batch-rename.
    #
    # Available template variables (Lidarr-compatible):
    # - {Artist Name}, {Artist CleanName}
    # - {Album Title}, {Album CleanTitle}, {Album Type}, {Release Year}
    # - {Track Title}, {Track CleanTitle}
    # - {Track Number}, {Track Number:00} (with zero-padding)
    # - {Medium}, {Medium:00} (disc number for multi-disc)
    # =========================================================================

    # Supported template variables for validation
    NAMING_VARIABLES: set[str] = {
        # Artist variables
        "Artist Name",
        "Artist CleanName",
        # Album variables
        "Album Title",
        "Album CleanTitle",
        "Album Type",
        "Release Year",
        # Track variables
        "Track Title",
        "Track CleanTitle",
        "Track Number",
        "Track Number:00",
        # Multi-disc variables
        "Medium",
        "Medium:00",
        # Legacy variables (for backward compatibility)
        "artist",
        "album",
        "title",
        "track",
        "track:02d",
        "year",
        "disc",
    }

    def validate_naming_template(self, template: str) -> tuple[bool, list[str]]:
        """Validate a naming template for invalid variables.

        Checks that all {variable} placeholders in the template are in
        the NAMING_VARIABLES set. Returns validation result and list of
        invalid variables found.

        Args:
            template: Template string like "{Artist Name}/{Album Title}"

        Returns:
            Tuple of (is_valid, invalid_variables).
            is_valid is True if all variables are valid.
            invalid_variables is list of unknown variable names.

        Example:
            >>> validate_naming_template("{Artist Name} - {Invalid}")
            (False, ["Invalid"])
        """
        import re

        # Find all {variable} patterns, including those with :format specifiers
        # Pattern matches {Var Name} or {var:format}
        pattern = r"\{([^}]+)\}"
        found_vars = re.findall(pattern, template)

        invalid = []
        for var in found_vars:
            # Check if variable (with or without format spec) is valid
            if var not in self.NAMING_VARIABLES:
                # Also check base name without format spec (e.g., "track" from "track:02d")
                base_var = var.split(":")[0]
                if base_var not in self.NAMING_VARIABLES and var not in self.NAMING_VARIABLES:
                    invalid.append(var)

        return (len(invalid) == 0, invalid)

    async def get_artist_folder_format(self) -> str:
        """Get template for artist folder names.

        Default: '{Artist Name}' - matches Lidarr standard.
        """
        return await self.get_string(
            "naming.artist_folder_format", default="{Artist Name}"
        ) or "{Artist Name}"

    async def get_album_folder_format(self) -> str:
        """Get template for album folder names.

        Default: '{Album Title} ({Release Year})' - matches Lidarr standard.
        """
        return await self.get_string(
            "naming.album_folder_format", default="{Album Title} ({Release Year})"
        ) or "{Album Title} ({Release Year})"

    async def get_standard_track_format(self) -> str:
        """Get template for single-disc track filenames.

        Default: '{Track Number:00} - {Track Title}' - matches Lidarr standard.
        """
        return await self.get_string(
            "naming.standard_track_format", default="{Track Number:00} - {Track Title}"
        ) or "{Track Number:00} - {Track Title}"

    async def get_multi_disc_track_format(self) -> str:
        """Get template for multi-disc track filenames.

        Default: '{Medium:00}-{Track Number:00} - {Track Title}'
        Adds disc number prefix for multi-disc albums.
        """
        return await self.get_string(
            "naming.multi_disc_track_format",
            default="{Medium:00}-{Track Number:00} - {Track Title}",
        ) or "{Medium:00}-{Track Number:00} - {Track Title}"

    async def is_rename_tracks_enabled(self) -> bool:
        """Check if automatic file renaming on import is enabled.

        Default: True - files are renamed according to template.
        """
        return await self.get_bool("naming.rename_tracks", default=True)

    async def should_replace_illegal_characters(self) -> bool:
        """Check if illegal filename characters should be replaced.

        Default: True - characters like : ? * are replaced.
        """
        return await self.get_bool("naming.replace_illegal_characters", default=True)

    async def should_create_artist_folder(self) -> bool:
        """Check if artist folders should be created automatically.

        Default: True - creates {Artist Name}/ folder if missing.
        """
        return await self.get_bool("naming.create_artist_folder", default=True)

    async def should_create_album_folder(self) -> bool:
        """Check if album folders should be created automatically.

        Default: True - creates {Album Title}/ subfolder if missing.
        """
        return await self.get_bool("naming.create_album_folder", default=True)

    async def get_colon_replacement(self) -> str:
        """Get replacement string for colon character in filenames.

        Default: ' -' (space dash) - Lidarr standard.
        """
        return await self.get_string("naming.colon_replacement", default=" -") or " -"

    async def get_slash_replacement(self) -> str:
        """Get replacement string for slash character in filenames.

        Default: '-' (dash).
        """
        return await self.get_string("naming.slash_replacement", default="-") or "-"

    async def get_naming_settings_summary(self) -> dict[str, Any]:
        """Get summary of all naming settings for UI display.

        Returns a dict with all naming settings for the Settings page.
        Includes template formats and behavior toggles.
        """
        return {
            # Template formats
            "artist_folder_format": await self.get_artist_folder_format(),
            "album_folder_format": await self.get_album_folder_format(),
            "standard_track_format": await self.get_standard_track_format(),
            "multi_disc_track_format": await self.get_multi_disc_track_format(),
            # Behavior toggles
            "rename_tracks": await self.is_rename_tracks_enabled(),
            "replace_illegal_characters": await self.should_replace_illegal_characters(),
            "create_artist_folder": await self.should_create_artist_folder(),
            "create_album_folder": await self.should_create_album_folder(),
            # Character replacements
            "colon_replacement": await self.get_colon_replacement(),
            "slash_replacement": await self.get_slash_replacement(),
        }
