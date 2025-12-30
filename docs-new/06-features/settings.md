# Settings

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-11-30  
**Related Docs:** [Configuration](../02-architecture/configuration.md) | [Spotify Sync](./spotify-sync.md)

---

## Overview

Settings management allows viewing and configuring the application. Settings are grouped into categories:

- **Spotify Sync** - Auto-sync settings (runtime, DB-stored) ⭐
- **General** - App name, logging, debug
- **Integrations** - Spotify, slskd, MusicBrainz credentials
- **Download** - Download queue configuration
- **Appearance** - Theme settings
- **Advanced** - API server, circuit breaker

💡 **Note:** Spotify Sync settings are stored in database and can be changed at runtime without restart. See [Spotify Sync](./spotify-sync.md) for details.

---

## Settings Categories

### General

| Setting | Description | Type | Default |
|---------|-------------|------|---------|
| `app_name` | Application name | string | "SoulSpot" |
| `log_level` | Logging level | string | "INFO" |
| `debug` | Enable debug mode | boolean | false |

---

### Integrations

#### Spotify

| Setting | Description | Type |
|---------|-------------|------|
| `spotify_client_id` | Spotify OAuth Client ID | string |
| `spotify_client_secret` | Spotify OAuth Client Secret | string (masked) |
| `spotify_redirect_uri` | OAuth Redirect URL | string |

---

#### slskd (Soulseek)

| Setting | Description | Type |
|---------|-------------|------|
| `slskd_url` | slskd service URL | string |
| `slskd_username` | slskd username | string |
| `slskd_password` | slskd password | string (masked) |
| `slskd_api_key` | slskd API key (optional) | string (masked) |

---

#### MusicBrainz

| Setting | Description | Type | Default |
|---------|-------------|------|---------|
| `musicbrainz_app_name` | App name for MusicBrainz API | string | "SoulSpot" |
| `musicbrainz_contact` | Contact email for MusicBrainz | string | "" |

---

### Download

| Setting | Description | Type | Default | Range |
|---------|-------------|------|---------|-------|
| `max_concurrent_downloads` | Max parallel downloads | int | 5 | 1-10 |
| `default_max_retries` | Retry attempts on failure | int | 3 | 1-10 |
| `enable_priority_queue` | Enable prioritization | boolean | true | - |

---

### Appearance

| Setting | Description | Type | Default |
|---------|-------------|------|---------|
| `theme` | UI theme | string | "auto" |

**Theme Options:**
- `light`: Light theme
- `dark`: Dark theme
- `auto`: Follow system

---

### Advanced

| Setting | Description | Type | Default | Range |
|---------|-------------|------|---------|-------|
| `api_host` | API server host | string | "0.0.0.0" | - |
| `api_port` | API server port | int | 8765 | 1-65535 |
| `circuit_breaker_failure_threshold` | Failures until circuit break | int | 5 | 1+ |
| `circuit_breaker_timeout` | Circuit breaker timeout (sec) | float | 60.0 | 1.0+ |

---

## Usage (Web UI)

### View Settings

1. Navigate to **Settings**
2. Settings grouped in tabs
3. Sensitive values (passwords, API keys) masked with `***`

---

### Change Settings

⚠️ **Note:** Editing settings via UI not fully implemented. Changes accepted but not persisted.

**Current Recommendation:**
Change settings via `.env` file and restart application.

---

## API Endpoints

### GET `/api/settings/`

Get all current settings.

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
    "spotify_redirect_uri": "http://localhost:8765/auth/callback",
    "slskd_url": "http://localhost:5030",
    "slskd_username": "user",
    "slskd_password": "***",
    "slskd_api_key": "***",
    "musicbrainz_app_name": "SoulSpot",
    "musicbrainz_contact": "contact@example.com"
  },
  "download": {
    "max_concurrent_downloads": 5,
    "default_max_retries": 3,
    "enable_priority_queue": true
  },
  "appearance": {
    "theme": "auto"
  },
  "advanced": {
    "api_host": "0.0.0.0",
    "api_port": 8765,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout": 60.0
  }
}
```

---

### POST `/api/settings/`

Update settings.

**Request:**
```json
{
  "general": {
    "log_level": "DEBUG"
  },
  "download": {
    "max_concurrent_downloads": 10
  }
}
```

**Response:**
```json
{
  "message": "Settings updated successfully",
  "updated_keys": ["general.log_level", "download.max_concurrent_downloads"]
}
```

---

## Related Documentation

- **[Configuration](../02-architecture/configuration.md)** - Configuration architecture
- **[Spotify Sync](./spotify-sync.md)** - Runtime sync settings

---

**Last Validated:** 2025-11-30  
**Implementation Status:** ✅ Production-ready
