# Followed Artists

**Category:** Features  
**Last Updated:** 2025-11-25  
**Related Docs:** [Spotify Sync](./spotify-sync.md) | [Automation Watchlists](./automation-watchlists.md)

---

## Overview

Followed Artists feature provides access to all artists you follow on Spotify. Sync artists and create watchlists in bulk to automatically download all albums and new releases.

---

## Features

### Artist Synchronization

- **Full Sync:** Import all followed artists from Spotify
- **Pagination:** Automatic handling for 100+ artists
- **Genre Tags:** Genres imported from Spotify

**Endpoint:** `POST /api/automation/followed-artists/sync`

---

### Bulk Watchlist Creation

- **Multi-Select:** Select multiple artists simultaneously
- **Unified Settings:** All watchlists with same configuration
- **Fast Setup:** Create hundreds of watchlists in seconds

**Endpoint:** `POST /api/automation/followed-artists/watchlists/bulk`

---

### Preview Mode

- **Quick Preview:** Shows up to 50 artists without database storage
- **OAuth Test:** Verifies `user-follow-read` permission works

**Endpoint:** `GET /api/automation/followed-artists/preview`

---

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| Spotify Session | Active OAuth connection |
| OAuth Scope | `user-follow-read` permission |
| Followed Artists | At least one artist followed on Spotify |

---

## Usage (Web UI)

### Sync Artists

1. Navigate to **Automation** → **Followed Artists**
2. Click **Sync from Spotify**
3. Wait for all artists to load
4. Artists displayed in grid view

---

### Create Watchlists

1. After sync: Select artists via checkbox
2. Or click **Select All** for all artists
3. Configure watchlist settings:
   - **Check Interval:** e.g., every 24 hours
   - **Auto-Download:** Automatic download?
   - **Quality Profile:** high, medium, low
4. Click **Create Watchlists**

---

### Preview Without Sync

1. Navigate to **Automation** → **Followed Artists**
2. Click **Preview** instead of **Sync**
3. First 50 artists displayed (no database storage)

---

## API Endpoints

### POST `/api/automation/followed-artists/sync`

Sync all followed artists from Spotify to local database.

**Response (JSON):**
```json
{
  "total_fetched": 150,
  "created": 100,
  "updated": 50,
  "errors": 0,
  "artists": [
    {
      "id": "artist-uuid",
      "name": "Artist Name",
      "spotify_uri": "spotify:artist:xyz",
      "image_url": "https://...",
      "genres": ["electronic", "synthwave"]
    }
  ]
}
```

**Response (HTMX):**
With `HX-Request: true` header, returns HTML partial.

---

### POST `/api/automation/followed-artists/watchlists/bulk`

Create watchlists for multiple artists simultaneously.

**Request:**
```json
{
  "artist_ids": ["uuid1", "uuid2", "uuid3"],
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

**Response:**
```json
{
  "total_requested": 10,
  "created": 8,
  "failed": 2,
  "failed_artists": ["uuid-x", "uuid-y"]
}
```

---

### GET `/api/automation/followed-artists/preview`

Quick preview without database synchronization.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max artists (1-50) |

**Response:** Raw Spotify API response with artist data.

---

## Workflow Example

```
1. Connect Spotify account
   ↓
2. Open /followed-artists page
   ↓
3. Click "Sync from Spotify"
   ↓
4. Artists loaded → Display in grid
   ↓
5. Select artists (checkboxes)
   ↓
6. Configure watchlist settings
   ↓
7. Click "Create Watchlists"
   ↓
8. Watchlists created → Auto-download enabled
```

---

## Troubleshooting

### "403 Forbidden" Error

**Cause:** Missing `user-follow-read` OAuth scope

**Solution:**
1. Disconnect Spotify in Settings
2. Reconnect (re-authorize)
3. Ensure scope granted

---

### No Artists Found

**Causes:**
1. **Not following anyone:** Follow artists on Spotify first
2. **Token expired:** Reconnect account
3. **API error:** Check logs for details

---

### Watchlist Creation Fails

**Causes:**
1. **Duplicate watchlist:** Artist already has watchlist
2. **Invalid settings:** Check configuration values
3. **Database error:** Check logs

---

## Related Documentation

- **[Spotify Sync](./spotify-sync.md)** - Artist sync background worker
- **[Automation Watchlists](./automation-watchlists.md)** - Watchlist management
- **[Authentication](./authentication.md)** - OAuth setup

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
