# Settings API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/settings.py`

---

## Overview

The Settings API provides comprehensive configuration management for SoulSpot. It exposes **24 endpoints** across multiple categories:

- **General Settings** - Application-wide configuration (log level, debug mode, app name)
- **Integration Settings** - External service credentials (Spotify, slskd, MusicBrainz)
- **Download Settings** - Download queue behavior (concurrency, retries, priority)
- **Appearance Settings** - UI theming
- **Advanced Settings** - Circuit breaker, API host/port

**Key Features:**
- ✅ **Runtime Changes:** General + Download settings persist to database and apply **immediately** (no restart required)
- 🔐 **Security:** Secrets (passwords, API keys) are **masked** (`***`) in GET responses
- 🔄 **Env Fallback:** DB settings override environment variables, with env as fallback
- 🎯 **Spotify Sync Configuration:** Dedicated endpoints for Spotify sync behavior (workers, triggers, stats)
- 🔧 **Automation Settings:** Configure automation workflows, discography sync, quality upgrades
- 📝 **Naming Patterns:** Customizable file naming templates with validation + preview
- 🎨 **Library Enrichment:** Configure MusicBrainz/Spotify metadata enrichment
- 🔌 **Provider Settings:** Enable/disable external data providers

---

## Table of Contents

1. [General Settings](#1-general-settings)
2. [Spotify Sync Settings](#2-spotify-sync-settings)
3. [Automation Settings](#3-automation-settings)
4. [Naming Pattern Settings](#4-naming-pattern-settings)
5. [Library Enrichment Settings](#5-library-enrichment-settings)
6. [Provider Settings](#6-provider-settings)
7. [Data Models](#7-data-models)
8. [Code Examples](#8-code-examples)

---

## 1. General Settings

### GET `/api/settings/`

**Purpose:** Retrieve all application settings grouped by category.

**Authentication:** None (local-only app)

**Response:**
```json
{
  "general": {
    "app_name": "SoulSpot",
    "log_level": "INFO",
    "debug": false
  },
  "integration": {
    "spotify_client_id": "abc123...",
    "spotify_client_secret": "***",
    "spotify_redirect_uri": "http://localhost:8000/api/auth/callback",
    "slskd_url": "http://localhost:5030",
    "slskd_username": "user",
    "slskd_password": "***",
    "slskd_api_key": "***",
    "musicbrainz_app_name": "SoulSpot",
    "musicbrainz_contact": "user@example.com"
  },
  "download": {
    "max_concurrent_downloads": 3,
    "default_max_retries": 5,
    "enable_priority_queue": true
  },
  "appearance": {
    "theme": "auto"
  },
  "advanced": {
    "api_host": "0.0.0.0",
    "api_port": 8000,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout": 60.0
  }
}
```

**Notes:**
- Secrets (`spotify_client_secret`, `slskd_password`, `slskd_api_key`) are **masked** as `"***"`
- General + Download settings come from **database** (with env fallback)
- Integration + Advanced settings are **environment-based** (read-only via API)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 122-182)
@router.get("/")
async def get_all_settings(
    db: AsyncSession = Depends(get_db_session),
) -> AllSettings:
    """Get all current settings."""
    ...
```

---

### POST `/api/settings/`

**Purpose:** Update application settings. **General + Download settings are persisted to database.**

**Request Body:**
```json
{
  "general": {
    "app_name": "SoulSpot",
    "log_level": "DEBUG",
    "debug": true
  },
  "download": {
    "max_concurrent_downloads": 5,
    "default_max_retries": 3,
    "enable_priority_queue": true
  },
  "integration": { ... },
  "appearance": { ... },
  "advanced": { ... }
}
```

**Response:**
```json
{
  "message": "Settings updated successfully",
  "persisted": {
    "general": ["log_level", "debug", "app_name"],
    "download": ["max_concurrent_downloads", "default_max_retries", "enable_priority_queue"]
  },
  "requires_restart": ["integration", "advanced"]
}
```

**Behavior:**
- **General settings** → Saved to DB, **log_level changes apply IMMEDIATELY** (no restart)
- **Download settings** → Saved to DB, apply immediately
- **Integration/Advanced** → Environment-based, require restart (changes via API are **ignored**)

**Errors:**
- `400 Bad Request` - Invalid log level (must be DEBUG/INFO/WARNING/ERROR/CRITICAL)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 189-274)
@router.post("/")
async def update_settings(
    settings_update: AllSettings,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update application settings."""
    ...
```

---

### POST `/api/settings/reset`

**Purpose:** Reset all settings to default values (delete from DB, use env defaults).

**Request Body:** None

**Response:**
```json
{
  "message": "Settings reset to defaults successfully"
}
```

**Behavior:**
- Deletes ALL settings from database
- Subsequent requests use environment variable defaults
- Log level reverts to env-configured level

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 276-309)
@router.post("/reset")
async def reset_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Reset all settings to default values."""
    ...
```

---

### GET `/api/settings/defaults`

**Purpose:** Get default values for all settings (from environment variables).

**Response:**
```json
{
  "general": {
    "app_name": "SoulSpot",
    "log_level": "INFO",
    "debug": false
  },
  "download": {
    "max_concurrent_downloads": 3,
    "default_max_retries": 5,
    "enable_priority_queue": true
  },
  ...
}
```

**Use Case:** Display default values in UI when user wants to reset individual settings.

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 311-450)
@router.get("/defaults")
async def get_default_settings(
    db: AsyncSession = Depends(get_db_session),
) -> AllSettings:
    """Get default settings from environment."""
    ...
```

---

## 2. Spotify Sync Settings

### GET `/api/settings/spotify-sync`

**Purpose:** Get Spotify sync configuration (worker behavior, sync intervals, image fetching).

**Response:**
```json
{
  "enabled": true,
  "sync_liked_songs": true,
  "sync_playlists": true,
  "sync_artists": true,
  "sync_albums": true,
  "fetch_artist_images": true,
  "fetch_album_images": true,
  "fetch_playlist_covers": true,
  "auto_sync_interval_minutes": 60,
  "worker_enabled": true,
  "last_sync": "2025-12-09T10:30:00Z"
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 452-499)
@router.get("/spotify-sync")
async def get_spotify_sync_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get Spotify sync settings."""
    ...
```

---

### PUT `/api/settings/spotify-sync`

**Purpose:** Update Spotify sync settings. **All changes persist to database and apply immediately.**

**Request Body:**
```json
{
  "sync_liked_songs": false,
  "sync_playlists": true,
  "auto_sync_interval_minutes": 120,
  "fetch_artist_images": true
}
```

**Response:**
```json
{
  "message": "Spotify sync settings updated successfully"
}
```

**Behavior:**
- Changes apply **immediately** to background workers
- Worker restart not required
- Validation: `auto_sync_interval_minutes` must be >= 5

**Errors:**
- `400 Bad Request` - Invalid interval (<5 minutes)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 501-596)
@router.put("/spotify-sync")
async def update_spotify_sync_settings(
    settings_update: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update Spotify sync settings."""
    ...
```

---

### POST `/api/settings/spotify-sync/toggle/{setting_name}`

**Purpose:** Quick toggle for boolean Spotify sync settings.

**Path Parameters:**
- `setting_name` - One of: `sync_liked_songs`, `sync_playlists`, `sync_artists`, `sync_albums`, `fetch_artist_images`, `fetch_album_images`, `fetch_playlist_covers`, `worker_enabled`

**Request Body:** None

**Response:**
```json
{
  "setting_name": "sync_liked_songs",
  "new_value": false
}
```

**Behavior:**
- Toggles boolean setting (true → false, false → true)
- Persists to database
- Changes apply immediately

**Errors:**
- `400 Bad Request` - Invalid setting name (not boolean or not in allowed list)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 598-652)
@router.post("/spotify-sync/toggle/{setting_name}")
async def toggle_spotify_sync_setting(
    setting_name: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Toggle a boolean Spotify sync setting."""
    ...
```

---

### GET `/api/settings/spotify-sync/image-stats`

**Purpose:** Get statistics about fetched Spotify images (artists, albums, playlists).

**Response:**
```json
{
  "total_artists": 150,
  "artists_with_images": 142,
  "total_albums": 320,
  "albums_with_images": 305,
  "total_playlists": 25,
  "playlists_with_covers": 23,
  "image_coverage_percent": 94.5
}
```

**Use Case:** Display image fetching progress in UI.

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 654-680)
@router.get("/spotify-sync/image-stats")
async def get_spotify_image_stats(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get statistics about Spotify images."""
    ...
```

---

### GET `/api/settings/spotify-sync/disk-usage`

**Purpose:** Get disk space usage for Spotify data (cached images, database size).

**Response:**
```json
{
  "database_size_mb": 45.2,
  "image_cache_size_mb": 128.7,
  "total_size_mb": 173.9
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 682-705)
@router.get("/spotify-sync/disk-usage")
async def get_spotify_disk_usage(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get disk usage for Spotify data."""
    ...
```

---

### GET `/api/settings/spotify-sync/db-stats`

**Purpose:** Get database statistics (total records, sync status, last updated timestamps).

**Response:**
```json
{
  "total_artists": 150,
  "total_albums": 320,
  "total_tracks": 1850,
  "total_playlists": 25,
  "last_full_sync": "2025-12-09T08:00:00Z",
  "pending_syncs": 3
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 707-788)
@router.get("/spotify-sync/db-stats")
async def get_spotify_db_stats(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get Spotify database statistics."""
    ...
```

---

### POST `/api/settings/spotify-sync/trigger/{sync_type}`

**Purpose:** Manually trigger a specific Spotify sync operation (bypass scheduled worker).

**Path Parameters:**
- `sync_type` - One of: `liked_songs`, `playlists`, `artists`, `albums`, `full` (all data types)

**Request Body:** None

**Response:**
```json
{
  "message": "Spotify sync triggered",
  "sync_type": "liked_songs",
  "job_id": "uuid-123..."
}
```

**Behavior:**
- Creates background job for sync operation
- Returns immediately (non-blocking)
- Check job status via `/api/workers/status` endpoint

**Errors:**
- `400 Bad Request` - Invalid sync_type
- `401 Unauthorized` - No Spotify session found (user not authenticated)
- `500 Internal Server Error` - Sync job failed to start

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 790-912)
@router.post("/spotify-sync/trigger/{sync_type}")
async def trigger_spotify_sync(
    sync_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Manually trigger a Spotify sync operation."""
    ...
```

---

### GET `/api/settings/spotify-sync/worker-status`

**Purpose:** Get status of background Spotify sync worker (running, paused, last sync time).

**Response:**
```json
{
  "worker_enabled": true,
  "worker_running": true,
  "last_run": "2025-12-09T10:00:00Z",
  "next_run": "2025-12-09T11:00:00Z",
  "current_job": {
    "type": "playlists",
    "progress": 45,
    "started_at": "2025-12-09T10:30:00Z"
  }
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 914-1009)
@router.get("/spotify-sync/worker-status")
async def get_spotify_worker_status(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get Spotify sync worker status."""
    ...
```

---

## 3. Automation Settings

### GET `/api/settings/automation`

**Purpose:** Get automation settings (discography sync, quality upgrades, watchlists).

**Response:**
```json
{
  "auto_discography_sync_enabled": true,
  "auto_quality_upgrade_enabled": true,
  "check_interval_hours": 24,
  "watchlist_check_interval_hours": 12
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1011-1038)
@router.get("/automation")
async def get_automation_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get automation settings."""
    ...
```

---

### PUT `/api/settings/automation`

**Purpose:** Update automation settings (full replacement).

**Request Body:**
```json
{
  "auto_discography_sync_enabled": true,
  "auto_quality_upgrade_enabled": false,
  "check_interval_hours": 48
}
```

**Response:**
```json
{
  "message": "Automation settings updated successfully"
}
```

**Behavior:**
- Replaces **all** automation settings
- Changes apply immediately to background workers

**Errors:**
- `400 Bad Request` - Invalid interval (must be > 0)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1040-1124)
@router.put("/automation")
async def update_automation_settings(
    settings_update: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update automation settings."""
    ...
```

---

### PATCH `/api/settings/automation`

**Purpose:** Partially update automation settings (only specified fields).

**Request Body:**
```json
{
  "auto_quality_upgrade_enabled": true
}
```

**Response:**
```json
{
  "message": "Automation settings updated successfully"
}
```

**Behavior:**
- Updates **only** specified fields
- Other settings remain unchanged
- Changes apply immediately

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1126-1280)
@router.patch("/automation")
async def patch_automation_settings(
    settings_update: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Partially update automation settings."""
    ...
```

---

## 4. Naming Pattern Settings

### GET `/api/settings/naming`

**Purpose:** Get file naming pattern templates.

**Response:**
```json
{
  "track_pattern": "{artist}/{album}/{track_number:02d} - {title}",
  "album_folder_pattern": "{artist}/{album}",
  "artist_folder_pattern": "{artist}",
  "compilation_pattern": "Compilations/{album}/{track_number:02d} - {title}"
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1282-1298)
@router.get("/naming")
async def get_naming_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get file naming pattern settings."""
    ...
```

---

### PUT `/api/settings/naming`

**Purpose:** Update file naming patterns.

**Request Body:**
```json
{
  "track_pattern": "{artist} - {title}",
  "album_folder_pattern": "{artist} - {album} ({year})"
}
```

**Response:**
```json
{
  "message": "Naming patterns updated successfully"
}
```

**Behavior:**
- Validates pattern syntax before saving
- Invalid patterns return `400 Bad Request`
- Changes apply to **new downloads only** (existing files not renamed)

**Errors:**
- `400 Bad Request` - Invalid pattern syntax (missing variables, syntax errors)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1300-1400)
@router.put("/naming")
async def update_naming_settings(
    settings_update: dict[str, str],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update file naming patterns."""
    ...
```

---

### POST `/api/settings/naming/validate`

**Purpose:** Validate a naming pattern without saving it.

**Request Body:**
```json
{
  "pattern": "{artist}/{album}/{track_number:02d} - {title}"
}
```

**Response (Valid):**
```json
{
  "valid": true,
  "message": "Pattern is valid"
}
```

**Response (Invalid):**
```json
{
  "valid": false,
  "message": "Missing required variable: {artist}",
  "errors": [
    "Variable 'artist' is required but not present"
  ]
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1402-1461)
@router.post("/naming/validate")
async def validate_naming_pattern(
    pattern_data: dict[str, str],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Validate a file naming pattern."""
    ...
```

---

### POST `/api/settings/naming/preview`

**Purpose:** Preview how a naming pattern will format a sample track.

**Request Body:**
```json
{
  "pattern": "{artist}/{album}/{track_number:02d} - {title}",
  "sample_data": {
    "artist": "Pink Floyd",
    "album": "The Wall",
    "title": "Comfortably Numb",
    "track_number": 6
  }
}
```

**Response:**
```json
{
  "formatted": "Pink Floyd/The Wall/06 - Comfortably Numb",
  "valid": true
}
```

**Use Case:** Show user live preview of naming pattern in settings UI.

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1463-1519)
@router.post("/naming/preview")
async def preview_naming_pattern(
    preview_data: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Preview a file naming pattern."""
    ...
```

---

### GET `/api/settings/naming/variables`

**Purpose:** Get list of available variables for naming patterns.

**Response:**
```json
{
  "track_variables": [
    {"name": "artist", "description": "Track artist name", "required": true},
    {"name": "title", "description": "Track title", "required": true},
    {"name": "album", "description": "Album name", "required": false},
    {"name": "track_number", "description": "Track number", "required": false, "format": "02d"},
    {"name": "year", "description": "Release year", "required": false}
  ],
  "album_variables": [
    {"name": "artist", "description": "Album artist name", "required": true},
    {"name": "album", "description": "Album name", "required": true},
    {"name": "year", "description": "Release year", "required": false}
  ]
}
```

**Use Case:** Display available variables in settings UI (with autocomplete).

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1521-1636)
@router.get("/naming/variables")
async def get_naming_variables(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get available naming pattern variables."""
    ...
```

---

## 5. Library Enrichment Settings

### GET `/api/settings/library/enrichment`

**Purpose:** Get library enrichment settings (MusicBrainz, Spotify metadata).

**Response:**
```json
{
  "auto_enrich_enabled": true,
  "use_musicbrainz": true,
  "use_spotify_metadata": true,
  "enrich_on_import": true,
  "batch_size": 50
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1638-1665)
@router.get("/library/enrichment")
async def get_library_enrichment_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get library enrichment settings."""
    ...
```

---

### PUT `/api/settings/library/enrichment`

**Purpose:** Update library enrichment settings.

**Request Body:**
```json
{
  "auto_enrich_enabled": true,
  "use_musicbrainz": true,
  "use_spotify_metadata": false,
  "batch_size": 100
}
```

**Response:**
```json
{
  "message": "Library enrichment settings updated successfully"
}
```

**Behavior:**
- Changes apply immediately
- `batch_size` affects performance (higher = faster but more memory)

**Errors:**
- `400 Bad Request` - Invalid batch_size (must be 1-1000)

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1667-1780)
@router.put("/library/enrichment")
async def update_library_enrichment_settings(
    settings_update: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update library enrichment settings."""
    ...
```

---

## 6. Provider Settings

### GET `/api/settings/providers`

**Purpose:** Get enabled/disabled status of external data providers.

**Response:**
```json
{
  "musicbrainz_enabled": true,
  "spotify_enabled": true,
  "soulseek_enabled": true,
  "coverartarchive_enabled": true
}
```

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1782-1804)
@router.get("/providers")
async def get_provider_settings(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """Get provider settings."""
    ...
```

---

### PUT `/api/settings/providers`

**Purpose:** Enable/disable external data providers.

**Request Body:**
```json
{
  "musicbrainz_enabled": true,
  "spotify_enabled": true,
  "soulseek_enabled": false
}
```

**Response:**
```json
{
  "message": "Provider settings updated successfully"
}
```

**Behavior:**
- Disabling a provider prevents API calls to that service
- Existing data from disabled provider remains in database
- Changes apply immediately

**Code Reference:**
```python
# src/soulspot/api/routers/settings.py (lines 1806-1837)
@router.put("/providers")
async def update_provider_settings(
    settings_update: dict[str, bool],
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update provider settings."""
    ...
```

---

## 7. Data Models

### AllSettings

```python
class AllSettings(BaseModel):
    """Combined settings model."""
    general: GeneralSettings
    integration: IntegrationSettings
    download: DownloadSettings
    appearance: AppearanceSettings
    advanced: AdvancedSettings
```

### GeneralSettings

```python
class GeneralSettings(BaseModel):
    """General application settings."""
    app_name: str = Field(description="Application name")
    log_level: str = Field(description="Logging level")  # DEBUG/INFO/WARNING/ERROR/CRITICAL
    debug: bool = Field(description="Debug mode")
```

### IntegrationSettings

```python
class IntegrationSettings(BaseModel):
    """Integration settings for external services."""
    # Spotify
    spotify_client_id: str
    spotify_client_secret: str  # Masked as "***" in GET responses
    spotify_redirect_uri: str

    # slskd
    slskd_url: str
    slskd_username: str
    slskd_password: str  # Masked as "***"
    slskd_api_key: str | None  # Masked as "***"

    # MusicBrainz
    musicbrainz_app_name: str
    musicbrainz_contact: str
```

### DownloadSettings

```python
class DownloadSettings(BaseModel):
    """Download configuration settings."""
    max_concurrent_downloads: int = Field(ge=1, le=10)
    default_max_retries: int = Field(ge=1, le=10)
    enable_priority_queue: bool
```

### AppearanceSettings

```python
class AppearanceSettings(BaseModel):
    """Appearance and theme settings."""
    theme: str  # "light" | "dark" | "auto"
```

### AdvancedSettings

```python
class AdvancedSettings(BaseModel):
    """Advanced configuration settings."""
    api_host: str
    api_port: int = Field(ge=1, le=65535)
    circuit_breaker_failure_threshold: int = Field(ge=1)
    circuit_breaker_timeout: float = Field(ge=1.0)
```

---

## 8. Code Examples

### Example 1: Get All Settings

```python
import httpx

async def get_settings():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/settings/")
        return response.json()

settings = await get_settings()
print(f"Log Level: {settings['general']['log_level']}")
print(f"Max Downloads: {settings['download']['max_concurrent_downloads']}")
```

### Example 2: Change Log Level (Immediate Effect)

```python
async def set_log_level(level: str):
    async with httpx.AsyncClient() as client:
        # Get current settings
        current = await client.get("http://localhost:8000/api/settings/")
        data = current.json()
        
        # Update log level
        data["general"]["log_level"] = level
        
        # Save (changes apply immediately!)
        response = await client.post("http://localhost:8000/api/settings/", json=data)
        return response.json()

result = await set_log_level("DEBUG")
print(result)  # {"message": "Settings updated successfully", ...}
```

### Example 3: Toggle Spotify Sync Feature

```python
async def toggle_artist_sync():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/settings/spotify-sync/toggle/sync_artists"
        )
        return response.json()

result = await toggle_artist_sync()
print(result)  # {"setting_name": "sync_artists", "new_value": false}
```

### Example 4: Trigger Manual Spotify Sync

```python
async def trigger_full_sync():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/settings/spotify-sync/trigger/full"
        )
        return response.json()

result = await trigger_full_sync()
print(result)  # {"message": "Spotify sync triggered", "job_id": "uuid-123..."}
```

### Example 5: Validate Naming Pattern

```python
async def validate_pattern(pattern: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/settings/naming/validate",
            json={"pattern": pattern}
        )
        return response.json()

result = await validate_pattern("{artist}/{album}/{title}")
print(result)  # {"valid": true, "message": "Pattern is valid"}
```

### Example 6: Preview Naming Pattern

```python
async def preview_pattern():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/settings/naming/preview",
            json={
                "pattern": "{artist}/{album}/{track_number:02d} - {title}",
                "sample_data": {
                    "artist": "Radiohead",
                    "album": "OK Computer",
                    "title": "Paranoid Android",
                    "track_number": 2
                }
            }
        )
        return response.json()

result = await preview_pattern()
print(result)  # {"formatted": "Radiohead/OK Computer/02 - Paranoid Android", "valid": true}
```

---

## Summary

**24 Endpoints** organized by category:

| Category | Endpoints | Key Features |
|----------|-----------|--------------|
| **General** | 4 | Get/Update/Reset/Defaults |
| **Spotify Sync** | 8 | Worker control, stats, manual triggers, image stats |
| **Automation** | 3 | Enable/disable auto-sync features |
| **Naming Patterns** | 5 | Validate/preview/update file naming templates |
| **Library Enrichment** | 2 | Configure MusicBrainz/Spotify metadata |
| **Providers** | 2 | Enable/disable external services |

**Critical Notes:**
- ✅ **Runtime Changes:** General + Download + Spotify Sync settings persist to DB and apply **immediately**
- 🔐 **Security:** Secrets are **masked** in GET responses
- 🔄 **Env Fallback:** DB settings override environment variables
- 🚫 **Read-Only:** Integration + Advanced settings are environment-based (changes via API ignored)
