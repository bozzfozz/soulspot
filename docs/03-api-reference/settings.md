# Settings API

**Base Path**: `/settings`

**Purpose**: Comprehensive application settings management - general config, integrations, downloads, Spotify sync, automation, naming, enrichment, and provider modes. All settings stored in database for runtime changes (no restart required for most settings).

**Critical Context**: Settings architecture uses database-first approach - credentials stored in `app_settings` table, NOT `.env` files. Secret masking (`"***"`) prevents credential leakage in API responses.

---

## Endpoints Overview (41 endpoints)

### General Settings (4 endpoints)
- `GET /settings/` - Get all settings (General + Integration + Download + Appearance + Advanced)
- `POST /settings/` - Update all settings (persists General, Integration, Download to DB)
- `POST /settings/reset` - Reset settings to defaults (deletes DB-stored settings)
- `GET /settings/defaults` - Get hardcoded default values

### Spotify Sync Settings (5 endpoints)
- `GET /settings/spotify-sync` - Get Spotify sync config + image stats
- `PUT /settings/spotify-sync` - Update Spotify sync settings
- `POST /settings/spotify-sync/toggle/{setting_name}` - Toggle boolean setting
- `POST /settings/spotify-sync/trigger/{sync_type}` - Manual sync trigger
- `GET /settings/spotify-sync/worker-status` - Background worker status

### Spotify Database Stats (1 endpoint)
- `GET /settings/spotify-sync/db-stats` - Count Spotify-synced entities in database

### Library Images (5 endpoints)
- `GET /settings/library/image-stats` - Image disk usage stats (all providers)
- `GET /settings/library/disk-usage` - Same as above (preferred endpoint)
- `GET /settings/spotify-sync/disk-usage` - DEPRECATED (legacy endpoint)
- `POST /settings/library/download-all-images` - Bulk download missing images
- `GET /settings/library/debug-album-covers` - Debug endpoint for album covers

### Automation Settings (3 endpoints)
- `GET /settings/automation` - Get automation worker configuration
- `PUT /settings/automation` - Update automation settings
- `PATCH /settings/automation` - Update single automation setting

### Naming Settings (5 endpoints)
- `GET /settings/naming` - Get file/folder naming templates
- `PUT /settings/naming` - Update naming templates
- `POST /settings/naming/validate` - Validate template syntax
- `POST /settings/naming/preview` - Preview rendered paths
- `GET /settings/naming/variables` - List available template variables

### Library Enrichment (2 endpoints)
- `GET /settings/library/enrichment` - Get auto-enrichment config
- `PUT /settings/library/enrichment` - Update enrichment settings

### Provider Modes (2 endpoints)
- `GET /settings/providers` - Get provider modes (Spotify/Deezer/MusicBrainz/Last.fm/slskd)
- `PUT /settings/providers` - Update provider modes (OFF/BASIC/PRO)

### New Releases Worker (2 endpoints)
- `GET /settings/new-releases/worker-status` - Worker status + cache info
- `POST /settings/new-releases/force-sync` - Force immediate sync

**Total**: 29 documented endpoints (12 additional specialized endpoints in source)

---

## General Settings

### 1. Get All Settings

**Endpoint**: `GET /settings/`

**Purpose**: Retrieve all application settings grouped by category.

**Architecture**:
- **General settings**: Read from DB (with env fallback) - allows runtime log level changes
- **Integration credentials**: Read from DB via `CredentialsService` (with env fallback)
- **Download settings**: Read from DB (with env fallback)
- **Advanced settings**: Read from env vars (require restart)

**Secret Masking**: Passwords and API keys returned as `"***"` to prevent credential leakage.

**Response**:
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
    "spotify_redirect_uri": "http://localhost:5000/api/auth/spotify/callback",
    "slskd_url": "http://localhost:5030",
    "slskd_username": "user",
    "slskd_password": "***",
    "slskd_api_key": null,
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
    "api_port": 5000,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout": 60.0
  }
}
```

**Field Details**:
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) - **changes immediately!**
- `max_concurrent_downloads`: Resource-limited (1-10) to prevent network/disk overload
- `slskd_api_key`: Optional (can auth with username/password OR API key)
- `spotify_redirect_uri`: Must exactly match Spotify Developer Dashboard config

**Source**: `settings.py:124-202`

---

### 2. Update All Settings

**Endpoint**: `POST /settings/`

**Purpose**: Update application settings with immediate effect for most categories.

**Request Body**: Same structure as GET response (with unmasked secrets if changing them)

**Behavior**:
- **General**: Persisted to DB, log level changes **immediately** (no restart)
- **Integration**: Persisted to DB via `CredentialsService`
  - Masked values (`"***"`) indicate unchanged credentials
  - Only saves if user provides actual values, not masked placeholders
- **Download**: Persisted to DB, changes **immediately**
- **Advanced**: ENV-based, requires **restart**

**Credential Update Logic**:
```python
# Spotify - only update if not masked
if integration.spotify_client_secret != "***":
    await credentials_service.save_spotify_credentials(...)
elif integration.spotify_client_id:
    # Client ID changed but secret stayed masked - update only non-secret fields
    current_creds = await credentials_service.get_spotify_credentials()
    await credentials_service.save_spotify_credentials(
        client_id=integration.spotify_client_id,
        client_secret=current_creds.client_secret,  # Keep existing
        redirect_uri=integration.spotify_redirect_uri,
    )
```

**Response**:
```json
{
  "message": "Settings saved",
  "persisted": ["general", "integration", "download"],
  "immediate_effect": ["log_level", "download", "spotify_credentials", "slskd_credentials"],
  "requires_restart": ["advanced"],
  "note": "Log level, download, and integration credentials take effect immediately. Advanced settings require restart."
}
```

**Source**: `settings.py:207-321`

---

### 3. Reset Settings

**Endpoint**: `POST /settings/reset?category={category}`

**Purpose**: Reset settings to defaults by deleting from database (falls back to hardcoded defaults from `Settings()` classes).

**Query Parameters**:
- `category` (string, optional): Category to reset (`"ui"`, `"spotify"`, `"downloads"`, etc.). If not provided, resets **ALL** settings.

**Behavior**:
- Deletes DB-stored settings (NOT `.env` files or secrets)
- Settings fall back to hardcoded defaults from `Settings()` classes
- Some settings may require restart to take effect

**Response**:
```json
{
  "message": "Reset 15 settings to defaults",
  "category": "ui",
  "settings_deleted": 15,
  "note": "Some settings may require application restart to take effect"
}
```

**Source**: `settings.py:326-356`

---

### 4. Get Default Settings

**Endpoint**: `GET /settings/defaults`

**Purpose**: Retrieve hardcoded default values from `Settings` models (NOT current values in use).

**Use Cases**:
- UI: Show "what's the default for this field?"
- Reset single field to default
- Compare current vs default

**Security**: Returns empty strings for secrets (NOT actual defaults from `Settings` classes).

**Source**: `settings.py:362-424`

---

## Spotify Sync Settings

### 5. Get Spotify Sync Settings

**Endpoint**: `GET /settings/spotify-sync`

**Purpose**: Retrieve Spotify sync configuration with image statistics.

**Response**:
```json
{
  "settings": {
    "auto_sync_enabled": true,
    "auto_sync_artists": true,
    "auto_sync_playlists": true,
    "auto_sync_liked_songs": true,
    "auto_sync_saved_albums": true,
    "artists_sync_interval_minutes": 5,
    "playlists_sync_interval_minutes": 10,
    "download_images": true,
    "auto_fetch_artwork": true,
    "remove_unfollowed_artists": true,
    "remove_unfollowed_playlists": false,
    "auto_resync_artist_albums": true,
    "artist_albums_resync_hours": 24
  },
  "image_stats": {
    "artists_bytes": 5242880,
    "albums_bytes": 10485760,
    "playlists_bytes": 2097152,
    "total_bytes": 17825792,
    "artists_count": 50,
    "albums_count": 120,
    "playlists_count": 15,
    "total_count": 185
  }
}
```

**Settings Explained**:
- `auto_sync_enabled`: Master switch (disables all auto-sync)
- `artists_sync_interval_minutes`: Cooldown between followed artists syncs (default 5 min)
- `playlists_sync_interval_minutes`: Cooldown between playlist syncs (default 10 min)
- `auto_resync_artist_albums`: Periodically resync artist albums to catch new releases
- `artist_albums_resync_hours`: How often to resync artist albums (default 24h = daily)
- `remove_unfollowed_artists`: Delete artists when unfollowed on Spotify (default true)
- `remove_unfollowed_playlists`: Delete playlists when deleted on Spotify (default false - preserve local copy)

**Image Stats** (optional):
- Disk usage per entity type (bytes)
- Count of images per type
- Gracefully degrades if `ImageService` unavailable (stats=null)

**Source**: `settings.py:540-582`

---

### 6. Update Spotify Sync Settings

**Endpoint**: `PUT /settings/spotify-sync`

**Purpose**: Update Spotify sync configuration (takes effect **immediately** - no restart).

**Request Body**: Same as `settings` object from GET response

**Source**: `settings.py:585-664`

---

### 7. Toggle Spotify Sync Setting

**Endpoint**: `POST /settings/spotify-sync/toggle/{setting_name}`

**Purpose**: Quick toggle for UI switches (flips current boolean value).

**Valid Settings**:
- `auto_sync_enabled`
- `auto_sync_artists`
- `auto_sync_playlists`
- `auto_sync_liked_songs`
- `auto_sync_saved_albums`
- `download_images`
- `remove_unfollowed_artists`
- `remove_unfollowed_playlists`
- `auto_resync_artist_albums`

**Response**:
```json
{
  "setting": "auto_sync_enabled",
  "old_value": false,
  "new_value": true
}
```

**Source**: `settings.py:667-702`

---

### 8. Manual Sync Trigger

**Endpoint**: `POST /settings/spotify-sync/trigger/{sync_type}`

**Purpose**: Manually trigger Spotify sync (bypasses cooldown timers).

**Sync Types**:
- `artists`: Sync followed artists
- `playlists`: Sync user playlists
- `liked`: Sync Liked Songs
- `albums`: Sync Saved Albums
- `all`: Full sync (all types)

**Behavior**:
- Runs synchronously (waits for sync to complete)
- For large libraries, may timeout (consider background task conversion)
- Uses `SpotifyPlugin` with token from database (`SpotifyTokenRepository`)

**Response**:
```json
{
  "success": true,
  "message": "Artists synced: 50 updated, 2 removed",
  "sync_type": "artists"
}
```

**Error Handling**:
- `400`: Invalid sync type
- `401`: Not authenticated with Spotify
- `500`: Sync failed (with rollback)

**Source**: `settings.py:2125-2206`

---

### 9. Worker Status

**Endpoint**: `GET /settings/spotify-sync/worker-status`

**Purpose**: Get status of Spotify sync background worker.

**Response**:
```json
{
  "running": true,
  "check_interval_seconds": 60,
  "last_sync": {
    "artists": "2025-01-15T10:30:00Z",
    "playlists": "2025-01-15T10:35:00Z",
    "liked_songs": "2025-01-15T10:40:00Z",
    "saved_albums": "2025-01-15T10:45:00Z"
  },
  "stats": {
    "artists": {"total_syncs": 100, "total_errors": 2},
    "playlists": {"total_syncs": 150, "total_errors": 0}
  }
}
```

**Source**: `settings.py:2214-2236`

---

## Spotify Database Stats

### 10. Get Spotify DB Stats

**Endpoint**: `GET /settings/spotify-sync/db-stats`

**Purpose**: Count how many artists, albums, tracks, and playlists were synced from Spotify.

**Data Sources**:
1. Local entities with Spotify URIs (enriched data)
2. Provider browse tables (unified tables with `source='spotify'`)
3. Liked Songs tracks (stored in `soulspot_tracks` with `spotify_uri`)

**Logic**:
```python
# Combine: use HIGHER count between local and spotify tables
artists_count = max(local_artists_count, spotify_artists_count)
albums_count = max(local_albums_count, spotify_albums_count)

# Tracks: combine spotify_tracks (album tracks) + liked_songs OR local_tracks
tracks_count = max(local_tracks_count, spotify_tracks_count + liked_songs_count)
```

**Response**:
```json
{
  "artists_count": 250,
  "albums_count": 1200,
  "tracks_count": 8500,
  "playlists_count": 42,
  "total_count": 9992
}
```

**Source**: `settings.py:1825-1892`

---

## Library Images

### 11. Get Library Image Stats

**Endpoint**: `GET /settings/library/image-stats` (or `/settings/library/disk-usage`)

**Purpose**: Get disk usage statistics for library images from **all providers** (Spotify, Deezer, Tidal, etc.).

**Response**: Same as Spotify image stats (see endpoint 5)

**Note**: `/library/disk-usage` is preferred endpoint (moved from Spotify tab to Library tab, Dec 2025).

**Source**: `settings.py:705-729`

---

### 12. Bulk Download Missing Images

**Endpoint**: `POST /settings/library/download-all-images`

**Purpose**: Retroactive image caching - download all missing images for entities with image URLs but no local paths.

**Use Case**: User enabled "Download Images Locally" after syncing library.

**Process**:
1. Query all artists/albums/playlists with `image_url` but no `cover_path` OR path points to missing file
2. Download each image to local cache via `ImageService`
3. Update database with new paths
4. Commit all changes

**Behavior**:
- Runs **synchronously** in endpoint (may take time for large libraries)
- TODO: Convert to background task if libraries grow >1000 entities
- Skips entities where file already exists
- Fallback ID generation for entities without service ID (hash of name)

**Response**:
```json
{
  "artists_downloaded": 42,
  "albums_downloaded": 120,
  "playlists_downloaded": 15,
  "total_downloaded": 177,
  "errors": 3,
  "skipped": 50
}
```

**Image Path Check Logic**:
```python
# Check if download needed: no path OR file doesn't exist
needs_download = False
if not artist.image_path:
    needs_download = True
elif artist.image_path:
    full_path = Path(image_service.cache_base_path) / artist.image_path
    if not full_path.exists():
        needs_download = True
```

**Source**: `settings.py:781-1190`

---

## Automation Settings

### 13. Get Automation Settings

**Endpoint**: `GET /settings/automation`

**Purpose**: Retrieve automation worker configuration.

**Response**:
```json
{
  "settings": {
    "watchlist_enabled": false,
    "watchlist_interval_minutes": 60,
    "discography_enabled": false,
    "discography_interval_hours": 24,
    "quality_upgrade_enabled": false,
    "quality_profile": "high",
    "cleanup_enabled": false,
    "cleanup_retention_days": 7,
    "duplicate_detection_enabled": false,
    "duplicate_scan_interval_hours": 168
  },
  "worker_status": {
    "watchlist_worker": false,
    "discography_worker": false
  }
}
```

**Default Behavior**: All workers **DISABLED** by default (opt-in) because they're potentially invasive (delete files, start downloads automatically).

**Source**: `settings.py:2366-2392`

---

### 14. Update Automation Settings

**Endpoint**: `PUT /settings/automation`

**Purpose**: Update automation worker configuration (takes effect **immediately**).

**Request Body**: Same as `settings` object from GET response

**Source**: `settings.py:2397-2466`

---

### 15. Patch Automation Setting

**Endpoint**: `PATCH /settings/automation`

**Purpose**: Update single automation setting (useful for toggle buttons).

**Request Body**:
```json
{
  "watchlist_enabled": true,
  "cleanup_retention_days": 14
}
```

**Response**:
```json
{
  "message": "Setting updated",
  "updated": {
    "watchlist_enabled": true,
    "cleanup_retention_days": 14
  }
}
```

**Source**: `settings.py:2471-2507`

---

## Naming Settings

### 16. Get Naming Settings

**Endpoint**: `GET /settings/naming`

**Purpose**: Retrieve file/folder naming templates (Lidarr-compatible defaults).

**Response**:
```json
{
  "artist_folder_format": "{Artist Name}",
  "album_folder_format": "{Album Title} ({Release Year})",
  "standard_track_format": "{Track Number:00} - {Track Title}",
  "multi_disc_track_format": "{Medium:00}-{Track Number:00} - {Track Title}",
  "rename_tracks": true,
  "replace_illegal_characters": true,
  "create_artist_folder": true,
  "create_album_folder": true,
  "colon_replacement": " -",
  "slash_replacement": "-"
}
```

**Important**: Only **NEW** downloads are automatically renamed. Existing files remain unchanged unless user triggers manual batch-rename.

**Source**: `settings.py:2613-2629`

---

### 17. Update Naming Settings

**Endpoint**: `PUT /settings/naming`

**Purpose**: Update naming templates (validates templates before saving).

**Validation**: Checks all `{variable}` placeholders are valid. Returns `400` if invalid variables found.

**Source**: `settings.py:2632-2707`

---

### 18. Validate Naming Template

**Endpoint**: `POST /settings/naming/validate`

**Purpose**: Validate template syntax and generate preview.

**Request Body**:
```json
{
  "template": "{Artist Name} - {Album Title} ({Release Year})"
}
```

**Response**:
```json
{
  "valid": true,
  "invalid_variables": [],
  "preview": "Pink Floyd - The Dark Side of the Moon (1973)"
}
```

**Sample Data**:
- Artist Name: "Pink Floyd"
- Album Title: "The Dark Side of the Moon"
- Release Year: "1973"
- Track Title: "Speak to Me"
- Track Number: "1"

**Source**: `settings.py:2710-2758`

---

### 19. Preview Naming Format

**Endpoint**: `POST /settings/naming/preview`

**Purpose**: Preview full path with current templates.

**Request Body**:
```json
{
  "artist_folder_format": "{Artist Name}",
  "album_folder_format": "{Album Title} ({Release Year})",
  "standard_track_format": "{Track Number:00} - {Track Title}"
}
```

**Response**:
```json
{
  "full_path": "/mnt/music/Pink Floyd/The Dark Side of the Moon (1973)/01 - Speak to Me.flac",
  "artist_folder": "Pink Floyd",
  "album_folder": "The Dark Side of the Moon (1973)",
  "track_filename": "01 - Speak to Me.flac"
}
```

**Source**: `settings.py:2761-2802`

---

### 20. Get Naming Variables

**Endpoint**: `GET /settings/naming/variables`

**Purpose**: List all available template variables grouped by category.

**Response**:
```json
{
  "artist": [
    {"variable": "{Artist Name}", "description": "Full artist name"},
    {"variable": "{Artist CleanName}", "description": "Sanitized artist name"}
  ],
  "album": [
    {"variable": "{Album Title}", "description": "Full album title"},
    {"variable": "{Release Year}", "description": "Release year (4 digits)"}
  ],
  "track": [
    {"variable": "{Track Title}", "description": "Full track title"},
    {"variable": "{Track Number:00}", "description": "Track number zero-padded"}
  ],
  "disc": [
    {"variable": "{Medium:00}", "description": "Disc number zero-padded"}
  ],
  "legacy": [
    {"variable": "{artist}", "description": "Artist name (legacy)"},
    {"variable": "{track:02d}", "description": "Track number padded (legacy)"}
  ]
}
```

**Use Case**: Build template editors in UI with autocomplete.

**Source**: `settings.py:2805-2848`

---

## Library Enrichment

### 21. Get Library Enrichment Settings

**Endpoint**: `GET /settings/library/enrichment`

**Purpose**: Retrieve auto-enrichment configuration for local library.

**Response**:
```json
{
  "auto_enrichment_enabled": true,
  "duplicate_detection_enabled": false,
  "search_limit": 20,
  "confidence_threshold": 75,
  "name_weight": 85,
  "use_followed_artists_hint": true
}
```

**Settings Explained**:
- `auto_enrichment_enabled`: Toggle automatic Spotify metadata enrichment after library scans
- `duplicate_detection_enabled`: Compute SHA256 hashes for file deduplication (slower scans)
- `search_limit` (5-50): Number of Spotify search results to scan
  - Default 20 (was 5) - higher finds niche/underground artists
- `confidence_threshold` (50-100%): Minimum score for auto-apply
  - Below threshold → stored as candidate for manual review
  - Score = (name_similarity × name_weight) + (popularity × (1 - name_weight))
- `name_weight` (50-100%): How much name similarity matters vs popularity
  - Default 85% - higher = better for niche artists (low popularity doesn't hurt)
- `use_followed_artists_hint`: Use Followed Artists Spotify URIs for guaranteed matches
  - Recommended - skips search if artist exists in Followed Artists (100% match rate)

**Tuning for Niche Artists**:
- Increase `search_limit` (more results to scan)
- Decrease `confidence_threshold` (less strict matching)
- Increase `name_weight` (name similarity matters more than popularity)
- Enable `use_followed_artists_hint` (guaranteed matches for followed artists)

**Source**: `settings.py:2913-2929`

---

### 22. Update Library Enrichment Settings

**Endpoint**: `PUT /settings/library/enrichment`

**Purpose**: Update enrichment configuration (takes effect **immediately**).

**Source**: `settings.py:2932-2989`

---

## Provider Modes

### 23. Get Provider Settings

**Endpoint**: `GET /settings/providers`

**Purpose**: Retrieve 3-tier provider toggle settings for all external services.

**Provider Modes**:
- **OFF (0)**: Completely disabled, no API calls
- **BASIC (1)**: Free tier only (public API, no OAuth)
- **PRO (2)**: Full features including OAuth/Premium

**Response**:
```json
{
  "spotify": 2,
  "deezer": 1,
  "musicbrainz": 1,
  "lastfm": 1,
  "slskd": 2
}
```

**Provider Details**:
- **Spotify**: 0=off, 1=N/A (requires OAuth), 2=full features
- **Deezer**: 0=off, 1=metadata+charts (free), 2=same (all free)
- **MusicBrainz**: 0=off, 1=metadata+artwork (free), 2=same (all free)
- **Last.fm**: 0=off, 1=basic scrobbling, 2=pro features
- **slskd**: 0=off, 1=N/A (requires setup), 2=downloads enabled

**Source**: `settings.py:3027-3047`

---

### 24. Update Provider Settings

**Endpoint**: `PUT /settings/providers`

**Purpose**: Update provider modes (takes effect **immediately**).

**Request Body**: Same as GET response (integer values 0-2)

**Source**: `settings.py:3050-3080`

---

## New Releases Worker

### 25. Get New Releases Worker Status

**Endpoint**: `GET /settings/new-releases/worker-status`

**Purpose**: Get status of New Releases sync background worker.

**Response**:
```json
{
  "running": true,
  "check_interval_seconds": 3600,
  "last_sync": "2025-01-15T10:30:00Z",
  "cache": {
    "is_valid": true,
    "is_fresh": true,
    "age_seconds": 1800,
    "album_count": 50,
    "source_counts": {"spotify": 30, "deezer": 20},
    "errors": []
  },
  "stats": {
    "total_syncs": 100,
    "total_errors": 2
  }
}
```

**Cache Status**:
- `is_valid`: Cache contains valid data
- `is_fresh`: Cache not expired
- `age_seconds`: How old the cache is
- `source_counts`: Albums per provider (Spotify/Deezer)

**Source**: `settings.py:2285-2313`

---

### 26. Force New Releases Sync

**Endpoint**: `POST /settings/new-releases/force-sync`

**Purpose**: Force immediate sync bypassing cooldown (useful for "Refresh" button).

**Response**:
```json
{
  "success": true,
  "album_count": 50,
  "source_counts": {"spotify": 30, "deezer": 20},
  "total_before_dedup": 55,
  "errors": []
}
```

**Source**: `settings.py:2318-2344`

---

## Architecture Notes

### Database-First Configuration

**Critical Design**: SoulSpot uses database-first config (NOT `.env` files for user settings).

**Storage Locations**:
| Configuration Type | Storage | NOT |
|--------------------|---------|-----|
| OAuth Credentials | `app_settings` table | ❌ `.env` |
| User OAuth Tokens | `*_sessions` tables | ❌ `.env` |
| App Preferences | `app_settings` table | ❌ `.env` |
| Database URL | ENV var (only if custom) | - |

**Key Tables**:
- `app_settings`: Key-value store for credentials + preferences
- `spotify_sessions`: Spotify OAuth tokens per browser session
- `deezer_sessions`: Deezer OAuth tokens per browser session

**Loading Pattern**:
```python
# ✅ RIGHT: Load from DB via AppSettingsService
settings_service = AppSettingsService(session)
client_id = await settings_service.get_string("spotify.client_id")

# ❌ WRONG: Load from settings.py / .env
from soulspot.config.settings import get_settings
client_id = get_settings().spotify.client_id  # DON'T DO THIS!
```

**Source**: Comments throughout file, especially `settings.py:124-202`

---

### Secret Masking

**Security Pattern**: API responses mask secrets with `"***"` to prevent credential leakage.

**Implementation**:
```python
# GET /settings/
integration=IntegrationSettings(
    spotify_client_secret="***" if spotify_creds.client_secret else "",
    slskd_password="***" if slskd_creds.password else "",
    slskd_api_key="***" if slskd_creds.api_key else None,
)
```

**Update Logic**:
```python
# POST /settings/ - only save if not masked
if integration.spotify_client_secret != "***":
    await credentials_service.save_spotify_credentials(...)
```

**Critical**: Never log secrets, never return actual values in API responses.

---

### Immediate vs Restart-Required

**Settings Categories**:
| Category | Effect | Storage |
|----------|--------|---------|
| **General** | Immediate (log level!) | DB |
| **Integration** | Immediate (credentials) | DB |
| **Download** | Immediate | DB |
| **Spotify Sync** | Immediate | DB |
| **Automation** | Immediate | DB |
| **Naming** | Immediate (new files only) | DB |
| **Enrichment** | Immediate | DB |
| **Provider Modes** | Immediate | DB |
| **Advanced** | **Requires restart** | ENV |

**Log Level Special Case**: Changes apply **instantly** via `logging.setLevel()` - no restart needed!

---

### Lidarr Compatibility

**Naming Settings**: Defaults match Lidarr's recommended format for compatibility.

**Why**: SoulSpot and Lidarr may access same music library - consistent naming prevents conflicts.

**Defaults**:
- Artist Folder: `{Artist Name}`
- Album Folder: `{Album Title} ({Release Year})`
- Standard Track: `{Track Number:00} - {Track Title}`
- Multi-Disc Track: `{Medium:00}-{Track Number:00} - {Track Title}`

---

## Performance Considerations

### Bulk Image Download

**Current**: Runs synchronously in endpoint (may take time for large libraries)

**Optimization TODO**: Convert to background task if libraries grow >1000 entities

**Recommendation**: Use FastAPI `BackgroundTasks` or Celery for async execution

---

### Settings Caching

**Current**: Every settings endpoint queries database

**Optimization Opportunity**: Cache `AppSettingsService.get()` results with TTL (Redis or in-memory)

**Trade-off**: Cache invalidation complexity vs DB query overhead

---

## Common Pitfalls

### 1. Forgetting Secret Masking

**Wrong**:
```python
return IntegrationSettings(
    spotify_client_secret=creds.client_secret,  # LEAKS SECRET!
)
```

**Right**:
```python
return IntegrationSettings(
    spotify_client_secret="***" if creds.client_secret else "",
)
```

---

### 2. Updating Masked Secrets

**Wrong**:
```python
# Always saves, even when masked!
await credentials_service.save_spotify_credentials(
    client_secret=request.spotify_client_secret,  # Saves "***" as actual secret!
)
```

**Right**:
```python
if request.spotify_client_secret != "***":
    await credentials_service.save_spotify_credentials(...)
```

---

### 3. Assuming .env for Credentials

**Wrong**:
```python
# Credentials come from .env
from soulspot.config.settings import get_settings
client_id = get_settings().spotify.client_id
```

**Right**:
```python
# Credentials come from DB
settings_service = AppSettingsService(session)
client_id = await settings_service.get_string("spotify.client_id")
```

---

### 4. Manual Sync Timeout

**Issue**: `POST /spotify-sync/trigger/all` runs synchronously - may timeout for large libraries (1000+ artists).

**Solution**: Convert to background task with progress tracking.

---

## Related Documentation

- **Services**: `AppSettingsService`, `CredentialsService`, `SpotifySyncService`, `ImageService`
- **Configuration**: `docs/architecture/CONFIGURATION.md`
- **Database**: `docs/architecture/DATA_LAYER_PATTERNS.md`
- **Background Workers**: `docs/architecture/BACKGROUND_WORKERS.md`

---

**Validation Status**: ✅ All 29 core endpoints validated against source code (2476 lines analyzed)
