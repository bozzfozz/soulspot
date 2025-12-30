# Configuration Architecture

> **Database-First Configuration: No `.env` Files for Credentials**

## Overview

SoulSpot uses a **database-first configuration** approach. All user-configurable settings (API credentials, OAuth tokens, preferences) are stored in the database and can be changed via the Settings UI without app restart.

**Key Principle**: Configuration lives in the database, not in `.env` files.

---

## Why Database Configuration?

| Benefit | Explanation |
|---------|-------------|
| **User-Friendly** | No manual file editing needed |
| **Hot Reload** | Settings take effect immediately without restart |
| **Secure** | Credentials in encrypted DB, not plain text files |
| **Portable** | Database backup includes all settings |
| **Single Source** | No confusion between `.env`, config files, and DB |

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Settings UI                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Spotify    │  │   Deezer    │  │   slskd     │             │
│  │  Client ID  │  │   App ID    │  │   URL       │             │
│  │  Secret     │  │   Secret    │  │   API Key   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      app_settings Table                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ key                      │ value        │ category       │   │
│  ├──────────────────────────┼──────────────┼────────────────┤   │
│  │ spotify.client_id        │ abc123...    │ spotify        │   │
│  │ spotify.client_secret    │ xyz789...    │ spotify        │   │
│  │ deezer.app_id            │ 456...       │ deezer         │   │
│  │ deezer.secret            │ qwe...       │ deezer         │   │
│  │ slskd.url                │ http://...   │ slskd          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Storage Location

| Configuration Type | Storage Location | Example |
|-------------------|------------------|---------|
| **OAuth Credentials** | `app_settings` table | Spotify Client ID, Deezer App ID |
| **User OAuth Tokens** | Service-specific tables | `spotify_sessions`, `deezer_sessions` |
| **App Preferences** | `app_settings` table | Theme, sync intervals, log level |
| **Infrastructure** | Environment vars (optional) | DATABASE_URL (only if custom DB) |

---

## First-Time Setup

1. **Start the app** (Docker or local)
2. **Navigate to Settings** in the Web UI
3. **Enter credentials** for each service:
   - **Spotify**: Client ID + Secret from [developer.spotify.com](https://developer.spotify.com/dashboard)
   - **Deezer**: App ID + Secret from [developers.deezer.com](https://developers.deezer.com/myapps)
   - **slskd**: URL + API Key or username/password
4. **Connect services** via OAuth buttons
5. **Start syncing!**

---

## Migration from .env (Legacy)

If you have an existing `.env` file:

1. Environment variables are read at startup
2. Values are copied to `app_settings` table
3. Subsequent changes should be made via Settings UI
4. You can delete `.env` after successful migration

**Note**: `.env` is for backwards compatibility only. New installations should configure via UI.

---

## Security Notes

- ✅ Credentials in `app_settings` should be encrypted at rest (planned feature)
- ✅ OAuth access tokens in `*_sessions` tables are sensitive
- ✅ Database file (`soulspot.db`) should have restricted permissions (600)
- ✅ Consider encrypting the database for production use
- ❌ Never commit `.env` or database files to version control

---

## Environment Variables (Legacy/Override)

Some environment variables are still supported for infrastructure settings:

| Variable | Purpose | Example | Required |
|----------|---------|---------|----------|
| `DATABASE_URL` | Custom database connection | `postgresql://user:pass@host/db` | No (defaults to SQLite) |
| `SECRET_KEY` | Encryption key | Random 32-char string | No (generated if missing) |
| `DEBUG` | Enable debug mode | `true` / `false` | No (defaults to `false`) |
| `LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING` | No (defaults to `INFO`) |

**Important**: Service credentials (Spotify, Deezer, slskd) should be configured via UI, NOT environment variables.

---

## Database Tables

### app_settings

Dynamic key-value store for runtime configuration:

| Column | Type | Description |
|--------|------|-------------|
| `key` | String | Setting identifier (e.g., `spotify.client_id`) |
| `value` | String | Setting value (stored as string) |
| `value_type` | String | Type hint (`string`, `int`, `bool`, `json`) |
| `category` | String | Grouping for UI (`spotify`, `deezer`, `general`) |
| `description` | String | Human-readable description |

**Example Rows**:
```sql
INSERT INTO app_settings (key, value, value_type, category, description) VALUES
  ('spotify.client_id', 'abc123...', 'string', 'spotify', 'Spotify OAuth Client ID'),
  ('spotify.client_secret', 'xyz789...', 'string', 'spotify', 'Spotify OAuth Client Secret'),
  ('deezer.app_id', '456...', 'string', 'deezer', 'Deezer Application ID'),
  ('auto_import.enabled', 'true', 'bool', 'general', 'Enable auto-import from download folder');
```

### spotify_sessions

OAuth sessions for Spotify:

| Column | Type | Description |
|--------|------|-------------|
| `session_id` | String | Browser session identifier (cookie) |
| `access_token` | String | Spotify OAuth access token |
| `refresh_token` | String | Refresh token for renewal |
| `token_expires_at` | DateTime | Token expiration timestamp |

**Lifecycle**:
1. User clicks "Connect Spotify" in Settings
2. OAuth flow redirects to Spotify
3. Callback saves tokens in `spotify_sessions`
4. Background worker refreshes tokens before expiration

### deezer_sessions

OAuth sessions for Deezer:

| Column | Type | Description |
|--------|------|-------------|
| `session_id` | String | Browser session identifier (cookie) |
| `access_token` | String | Deezer OAuth token (long-lived, no refresh) |
| `deezer_user_id` | String | Linked Deezer account ID |
| `deezer_username` | String | Display name |

**Difference from Spotify**:
- Deezer tokens are **long-lived** (no expiration)
- No refresh token needed
- Token stored once during OAuth flow

---

## Code Patterns

### Accessing Credentials (Service Layer)

Use `AppSettingsService` for accessing settings:

```python
from soulspot.application.services.app_settings_service import AppSettingsService
from fastapi import Depends

async def my_endpoint(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
):
    # Get Spotify credentials (DB-first)
    client_id = await settings_service.get_string("spotify.client_id")
    client_secret = await settings_service.get_string("spotify.client_secret")
    
    # Get slskd URL
    slskd_url = await settings_service.get_string("slskd.url")
    
    # Get boolean setting
    auto_import = await settings_service.get_bool("auto_import.enabled")
    
    # Get JSON setting
    metadata_prefs = await settings_service.get_json("metadata.preferences")
```

**Code Reference**: `src/soulspot/application/services/app_settings_service.py` (lines 1-200+)

### Saving Credentials (Settings UI)

```python
# Save Spotify credentials to database
await settings_service.set_string(
    "spotify.client_id",
    client_id,
    category="spotify",
    description="Spotify OAuth Client ID"
)

await settings_service.set_string(
    "spotify.client_secret",
    client_secret,
    category="spotify",
    description="Spotify OAuth Client Secret"
)
```

**Code Reference**: `src/soulspot/api/routers/settings.py` (lines 200-400)

### Checking Provider Availability

```python
from soulspot.application.services.app_settings_service import AppSettingsService

# Check if provider is enabled
if await settings_service.is_provider_enabled("spotify"):
    # Provider mode is "basic" or "pro" (not "off")
    ...

# Get provider mode
mode = await settings_service.get_provider_mode("deezer")
# Returns: "off", "basic", or "pro"
```

**Provider Modes**:
- `off`: Disabled completely
- `basic`: Enabled with basic features (metadata/browse)
- `pro`: Full features enabled

### OAuth Token Management

**Spotify Token Pattern**:
```python
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

# Check if user is authenticated
if not spotify_plugin.is_authenticated:
    return {"error": "not_authenticated"}

# Get auth status (validates token)
auth_status = await spotify_plugin.get_auth_status()
if not auth_status.is_authenticated:
    return {"error": "token_expired"}

# Make API call (token auto-refreshed if needed)
artist = await spotify_plugin.get_artist("abc123")
```

**Deezer Token Pattern**:
```python
from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

# Check if user is authenticated
if not deezer_plugin.is_authenticated:
    return {"error": "not_authenticated"}

# Deezer tokens don't expire, so is_authenticated is sufficient
# No need for get_auth_status()

# Make API call
artist = await deezer_plugin.get_artist("123456")
```

---

## Provider Configuration Workflow

### 1. Spotify Setup

```
User Flow:
1. Settings → Spotify → Enter Client ID + Secret
2. Click "Connect Spotify"
3. Redirect to Spotify OAuth
4. Callback saves tokens in spotify_sessions
5. Background worker starts token refresh loop

Database Changes:
- app_settings: spotify.client_id, spotify.client_secret
- spotify_sessions: access_token, refresh_token, expires_at
```

### 2. Deezer Setup

```
User Flow:
1. Settings → Deezer → Enter App ID + Secret
2. Click "Connect Deezer"
3. Redirect to Deezer OAuth
4. Callback saves token in deezer_sessions
5. Token is long-lived (no refresh needed)

Database Changes:
- app_settings: deezer.app_id, deezer.secret
- deezer_sessions: access_token, deezer_user_id, deezer_username
```

### 3. slskd Setup

```
User Flow:
1. Settings → slskd → Enter URL + API Key
2. (Optional) Test connection
3. Save settings

Database Changes:
- app_settings: slskd.url, slskd.api_key
```

---

## Summary

**Configuration Storage**:
```
┌────────────────────────────────────────────┐
│ What                  │ Where              │
├───────────────────────┼────────────────────┤
│ OAuth Credentials     │ app_settings       │
│ OAuth Tokens          │ *_sessions tables  │
│ App Preferences       │ app_settings       │
│ Infrastructure        │ ENV vars (optional)│
└────────────────────────────────────────────┘
```

**Key Principles**:
1. **Database-First**: All config in DB, not `.env`
2. **UI-Driven**: Users configure via Settings page
3. **Hot Reload**: Changes take effect immediately
4. **Secure**: Tokens in DB, encrypted at rest (planned)
5. **Portable**: Backup DB = backup all settings

**Migration Path**:
```
Legacy: .env file → ENV vars → Settings UI
Modern: Settings UI → Database → Application
```

---

## See Also

- [Settings API Reference](../03-api-reference/settings.md) - Settings management endpoints
- [Auth Patterns](./auth-patterns.md) - OAuth flow documentation
- [Core Philosophy](./core-philosophy.md) - Autonomy principle
- `src/soulspot/application/services/app_settings_service.py` - Settings service implementation

---

**Document Status**: Migrated from `docs/architecture/CONFIGURATION.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/application/services/app_settings_service.py` - Settings service
- `src/soulspot/api/routers/settings.py` - Settings API (lines 77-1916)
- `src/soulspot/infrastructure/persistence/models.py` - `app_settings`, `*_sessions` tables
- `src/soulspot/infrastructure/plugins/spotify_plugin.py` - OAuth token management
