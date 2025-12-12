# Configuration Architecture

## Overview

SoulSpot uses a **database-first configuration** approach instead of traditional `.env` files.
All user-configurable settings (API credentials, OAuth tokens, preferences) are stored in the database
and can be changed via the Settings UI without app restart.

## Why Database Configuration?

1. **User-Friendly**: No manual file editing needed
2. **Hot Reload**: Settings take effect immediately without restart
3. **Secure**: Credentials stored in encrypted SQLite/PostgreSQL, not plain text files
4. **Portable**: Database backup includes all settings
5. **Single Source**: No confusion between `.env`, config files, and DB settings

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

## Storage Location

| Configuration Type | Storage Location | Example |
|-------------------|------------------|---------|
| **OAuth Credentials** | `app_settings` table | Spotify Client ID, Deezer App ID |
| **User OAuth Tokens** | Service-specific tables | `spotify_sessions`, `deezer_sessions` |
| **App Preferences** | `app_settings` table | Theme, sync intervals, log level |
| **Infrastructure** | Environment vars (optional) | DATABASE_URL (only if custom DB needed) |

## First-Time Setup

1. **Start the app** (Docker or local)
2. **Navigate to Settings** in the Web UI
3. **Enter credentials** for each service you want to use:
   - Spotify: Client ID, Client Secret from developer.spotify.com
   - Deezer: App ID, Secret from developers.deezer.com
   - slskd: URL and API Key or username/password
4. **Connect services** via OAuth buttons
5. **Start syncing!**

## Migration from .env

If you have an existing `.env` file, the settings will be imported automatically on first startup:

1. Environment variables are read at startup
2. Values are copied to `app_settings` table
3. Subsequent changes should be made via Settings UI
4. You can delete `.env` after successful migration

## Security Notes

- Credentials in `app_settings` should be encrypted at rest (planned feature)
- OAuth access tokens in `*_sessions` tables are sensitive
- The database file (`soulspot.db`) should have restricted permissions
- Consider encrypting the database for production use

## Environment Variables (Legacy/Override)

Some environment variables are still supported for infrastructure settings:

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | Custom database connection | `postgresql://user:pass@host/db` |
| `SECRET_KEY` | Encryption key | Random 32-char string |
| `DEBUG` | Enable debug mode | `true` / `false` |
| `LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING` |

**Note**: Service credentials (Spotify, Deezer, slskd) should be configured via UI, not environment variables.

## Database Tables

### app_settings
Dynamic key-value store for runtime configuration:
- `key`: Setting identifier (e.g., `spotify.client_id`)
- `value`: Setting value (stored as string)
- `value_type`: Type hint (`string`, `int`, `bool`, `json`)
- `category`: Grouping for UI (`spotify`, `deezer`, `general`)
- `description`: Human-readable description

### spotify_sessions
OAuth sessions for Spotify:
- `session_id`: Browser session identifier
- `access_token`: Spotify OAuth token
- `refresh_token`: Refresh token for renewal
- `token_expires_at`: Expiration timestamp

### deezer_sessions
OAuth sessions for Deezer:
- `session_id`: Browser session identifier
- `access_token`: Deezer OAuth token (long-lived)
- `deezer_user_id`: Linked Deezer account
- `deezer_username`: Display name

## Troubleshooting

### "Credentials not configured"
→ Navigate to Settings and enter the missing credentials

### "Settings not persisting"
→ Check database file permissions
→ Verify DATABASE_URL is correct

### "OAuth flow failing"
→ Ensure redirect URI in Settings matches what you registered with the service
