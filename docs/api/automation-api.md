# Automation API

> **Version:** 2.0  
> **Last Updated:** 2025-01-06  
> **Base Path:** `/api/automation`

---

## Overview

The Automation API provides endpoints for managing artist watchlists, discography tracking, followed artists synchronization, quality upgrades, and automation rules. This API enables automated music discovery and collection management.

---

## Sub-Modules

The Automation API is split into logical sub-modules:

| Module | Prefix | Description |
|--------|--------|-------------|
| [Watchlists](#watchlists) | `/watchlist` | Artist watchlist management |
| [Discography](#discography) | `/discography` | Album completeness tracking |
| [Quality Upgrades](#quality-upgrades) | `/quality-upgrades` | Audio quality improvement |
| [Followed Artists](#followed-artists) | `/followed-artists` | Spotify followed artists sync |
| [Filters](#filters) | `/filters` | Download filtering rules |
| [Rules](#rules) | `/rules` | Automation rule definitions |

---

## Watchlists

Watchlists monitor artists for new releases and can trigger automatic downloads.

### Create Watchlist

```http
POST /api/automation/watchlist
```

**Request Body:**
```json
{
  "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `artist_id` | string | required | Spotify URI or internal artist ID |
| `check_frequency_hours` | int | 24 | How often to check for new releases |
| `auto_download` | bool | true | Automatically queue new releases for download |
| `quality_profile` | string | "high" | Quality target: "low", "medium", "high" |

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
  "status": "active",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high",
  "created_at": "2025-01-06T10:30:00Z"
}
```

### List Watchlists

```http
GET /api/automation/watchlist?limit=100&offset=0&active_only=false
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Maximum results to return |
| `offset` | int | 0 | Pagination offset |
| `active_only` | bool | false | Filter to only active watchlists |

**Response:**
```json
{
  "watchlists": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
      "status": "active",
      "check_frequency_hours": 24,
      "auto_download": true,
      "quality_profile": "high",
      "last_checked_at": "2025-01-06T09:00:00Z",
      "total_releases_found": 12,
      "total_downloads_triggered": 8
    }
  ],
  "limit": 100,
  "offset": 0
}
```

### Get Watchlist

```http
GET /api/automation/watchlist/{watchlist_id}
```

### Update Watchlist

```http
PUT /api/automation/watchlist/{watchlist_id}
```

### Delete Watchlist

```http
DELETE /api/automation/watchlist/{watchlist_id}
```

### Pause/Resume Watchlist

```http
POST /api/automation/watchlist/{watchlist_id}/pause
POST /api/automation/watchlist/{watchlist_id}/resume
```

---

## Discography

Check and manage album completeness for artists in your library.

### Check Discography

```http
POST /api/automation/discography/check
```

**Request Body:**
```json
{
  "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb"
}
```

**Response:**
```json
{
  "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
  "artist_name": "Radiohead",
  "total_albums": 15,
  "owned_albums": 10,
  "missing_albums": 5,
  "completeness_percent": 66.7,
  "missing": [
    {
      "album_id": "spotify:album:xxx",
      "name": "In Rainbows",
      "release_date": "2007-10-10",
      "album_type": "album"
    }
  ]
}
```

**Note:** Uses pre-synced `spotify_albums` data from background sync. No live Spotify API call required.

### Get Missing Albums (All Artists)

```http
GET /api/automation/discography/missing?limit=10
```

Returns artists with incomplete discographies, sorted by number of missing albums.

**Response:**
```json
{
  "artists_with_missing_albums": [
    {
      "artist_id": "...",
      "artist_name": "Pink Floyd",
      "missing_count": 8,
      "completeness_percent": 45.0
    }
  ],
  "count": 10
}
```

---

## Quality Upgrades

Identify and manage tracks that could be upgraded to higher quality versions.

### Identify Upgrade Candidates

```http
POST /api/automation/quality-upgrades/identify
```

**Request Body:**
```json
{
  "quality_profile": "high",
  "min_improvement_score": 0.3,
  "limit": 100
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `quality_profile` | string | "high" | Target quality (FLAC/320kbps for "high") |
| `min_improvement_score` | float | 0.3 | Minimum improvement (0.0-1.0). 0.3 = 30% better |
| `limit` | int | 100 | Maximum candidates to return |

**Response:**
```json
{
  "candidates": [
    {
      "track_id": "...",
      "title": "Paranoid Android",
      "current_quality": "192kbps MP3",
      "target_quality": "FLAC",
      "improvement_score": 0.65
    }
  ],
  "count": 42,
  "quality_profile": "high",
  "min_improvement_score": 0.3
}
```

### Get Unprocessed Upgrades

```http
GET /api/automation/quality-upgrades/unprocessed?limit=100
```

Returns quality upgrade candidates that haven't been processed yet.

---

## Followed Artists

Synchronize followed artists from Spotify and create watchlists.

### Sync Followed Artists

```http
POST /api/automation/followed-artists/sync
```

**Requires:** Spotify OAuth authentication

Fetches all artists the user follows on Spotify and syncs them to the local database.

**Response (JSON):**
```json
{
  "total_fetched": 150,
  "created": 45,
  "updated": 105,
  "errors": 0,
  "artists": [
    {
      "id": "...",
      "name": "Radiohead",
      "image_url": "https://..."
    }
  ]
}
```

**HTMX Support:** If `HX-Request: true` header is present, returns HTML partial for in-page updates.

### Bulk Create Watchlists

```http
POST /api/automation/followed-artists/bulk-watchlist
```

**Request Body:**
```json
{
  "artist_ids": [
    "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
    "spotify:artist:2YZyLoL8N0Wb9xBt1NhZWg"
  ],
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

Creates watchlists for multiple artists at once. Useful after syncing followed artists.

---

## Filters

Manage download filters that determine which releases to skip.

### List Filters

```http
GET /api/automation/filters
```

### Create Filter

```http
POST /api/automation/filters
```

### Update Filter

```http
PUT /api/automation/filters/{filter_id}
```

### Delete Filter

```http
DELETE /api/automation/filters/{filter_id}
```

---

## Rules

Manage automation rules that define custom behaviors.

### List Rules

```http
GET /api/automation/rules
```

### Create Rule

```http
POST /api/automation/rules
```

### Update Rule

```http
PUT /api/automation/rules/{rule_id}
```

### Delete Rule

```http
DELETE /api/automation/rules/{rule_id}
```

---

## Error Responses

All endpoints return standard HTTP error codes:

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input (e.g., malformed artist ID) |
| 401 | Unauthorized - Spotify authentication required |
| 404 | Not Found - Resource doesn't exist |
| 500 | Server Error - Internal error |
| 503 | Service Unavailable - Provider disabled |

**Error Response Format:**
```json
{
  "detail": "Human-readable error message"
}
```

---

## Quality Profiles

| Profile | Description | Target Formats |
|---------|-------------|----------------|
| `low` | Minimum acceptable quality | 128kbps+, any format |
| `medium` | Standard quality | 256kbps+, MP3/AAC/OGG |
| `high` | High quality | 320kbps+ or FLAC |

---

## Related Documentation

- [Automation & Watchlists Feature](../features/automation-watchlists.md)
- [Followed Artists Feature](../features/followed-artists.md)
- [Album Completeness Feature](../features/album-completeness.md)
- [Download Management API](download-management.md)
