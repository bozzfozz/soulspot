# AI-Model: Copilot
# Spotify Followed Artists Feature

## Overview

The Spotify Followed Artists feature allows users to sync all artists they follow on Spotify and bulk-create watchlists for automatic album and track downloads. This implements the core requirement: "Zugriff auf alle auf Spotify gefolgt Artist, wo wir Artist auswählen können zim folgen und alle verfügbaren Songs und Alben herunterladen bzw neue kommende Songs und Alben herunterladen"

## Features

### User Workflow

1. **Sync Followed Artists**: Click "Sync from Spotify" to fetch all followed artists
2. **Browse Artists**: View synced artists with their genres in a responsive grid
3. **Select Artists**: Use checkboxes to select which artists to watch
4. **Create Watchlists**: Bulk-create watchlists for automatic downloads
5. **Automatic Downloads**: New releases are automatically downloaded based on watchlist settings

## Access

**URL**: `/ui/automation/followed-artists`

**Requirements**:
- Active Spotify OAuth session
- `user-follow-read` permission granted

## API Endpoints

### POST /api/automation/followed-artists/sync

Syncs all followed artists from Spotify to local database.

**Response (JSON)**:
```json
{
  "total_fetched": 42,
  "created": 15,
  "updated": 27,
  "errors": 0,
  "artists": [...]
}
```

### POST /api/automation/followed-artists/watchlists/bulk

Creates watchlists for multiple artists at once.

**Request**:
```json
{
  "artist_ids": ["uuid1", "uuid2"],
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

**Response**:
```json
{
  "total_requested": 10,
  "created": 8,
  "failed": 2,
  "failed_artists": ["uuid-x"]
}
```

### GET /api/automation/followed-artists/preview

Quick preview of followed artists without syncing to database (max 50).

## Known Limitations

⚠️ **Genres not persisted**: Artist genres are displayed in UI but not stored in database due to missing columns in `artists` table. This requires a future database migration.

## Troubleshooting

### 403 Forbidden Error
**Cause**: Missing `user-follow-read` OAuth scope  
**Solution**: Re-authorize via Spotify login

### No Artists Synced
**Cause**: Not following any artists on Spotify  
**Solution**: Follow artists on Spotify first

## Related Features

- [Artist Watchlists](./artist-watchlists.md)
- [Automation Workflows](./automation-workflows.md)
