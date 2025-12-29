# Stats API

> **Version:** 2.0  
> **Last Updated:** 2025-01-06  
> **Base Path:** `/api/stats`

---

## Overview

The Stats API provides dashboard statistics and trend data. It powers the stat cards on the main dashboard, showing current counts and trend indicators (↑/↓) for key metrics.

---

## Endpoints

### Get Dashboard Stats with Trends

```http
GET /api/stats/trends
```

Returns current counts for all major metrics plus trend data showing changes since yesterday/last week.

**Response:**
```json
{
  "playlists": 45,
  "tracks": 1250,
  "tracks_downloaded": 980,
  "downloads_completed": 850,
  "downloads_failed": 12,
  "queue_size": 25,
  "active_downloads": 3,
  "spotify_artists": 120,
  "spotify_albums": 450,
  "spotify_tracks": 3200,
  "trends": {
    "downloads_today": {
      "current": 15,
      "previous": 8,
      "change": 7,
      "change_percent": 87.5,
      "direction": "up",
      "period": "today"
    },
    "downloads_week": {
      "current": 85,
      "previous": 62,
      "change": 23,
      "change_percent": 37.1,
      "direction": "up",
      "period": "week"
    },
    "playlists_new": {
      "current": 3,
      "previous": 0,
      "change": 3,
      "change_percent": 100.0,
      "direction": "up",
      "period": "week"
    },
    "failed": {
      "current": 12,
      "previous": 0,
      "change": 12,
      "change_percent": 0.0,
      "direction": "up",
      "period": "total"
    }
  },
  "last_updated": "2025-01-06T10:30:00+00:00"
}
```

---

## Response Schema

### StatsWithTrends

| Field | Type | Description |
|-------|------|-------------|
| `playlists` | int | Total playlists in database |
| `tracks` | int | Total distinct tracks across all playlists |
| `tracks_downloaded` | int | Tracks that have local files |
| `downloads_completed` | int | Total completed downloads (cumulative) |
| `downloads_failed` | int | Failed downloads needing attention |
| `queue_size` | int | Pending/queued downloads |
| `active_downloads` | int | Currently downloading |
| `spotify_artists` | int | Synced Spotify artists |
| `spotify_albums` | int | Synced Spotify albums |
| `spotify_tracks` | int | Synced Spotify tracks |
| `trends` | object | Trend data for key metrics (optional) |
| `last_updated` | string | ISO timestamp of stats snapshot |

### TrendData

| Field | Type | Description |
|-------|------|-------------|
| `current` | int | Current value |
| `previous` | int | Value from comparison period |
| `change` | int | Absolute change (current - previous) |
| `change_percent` | float | Percentage change |
| `direction` | string | `"up"`, `"down"`, or `"stable"` |
| `period` | string | Comparison period (e.g., `"today"`, `"week"`) |

---

## Trend Calculations

### Downloads Today
- **Current:** Downloads completed since midnight (UTC)
- **Previous:** Downloads completed yesterday (24h period)
- **Period:** `"today"`

### Downloads Week
- **Current:** Downloads completed in last 7 days
- **Previous:** Downloads completed in previous 7 days (days 8-14 ago)
- **Period:** `"week"`

### Playlists New
- **Current:** Playlists created in last 7 days
- **Previous:** Not tracked (always 0)
- **Period:** `"week"`

### Failed
- **Current:** Total failed downloads
- **Direction:** `"up"` means more failures (bad), `"down"` means fewer (good)
- **Period:** `"total"`

---

## Dashboard Integration

The stats endpoint is designed for dashboard stat cards:

```html
<div class="stat-card">
  <h3>Downloads</h3>
  <div class="stat-value">{{ stats.downloads_completed }}</div>
  <div class="stat-trend {{ stats.trends.downloads_today.direction }}">
    {{ '+' if stats.trends.downloads_today.change > 0 else '' }}
    {{ stats.trends.downloads_today.change }} heute
    {% if stats.trends.downloads_today.direction == 'up' %}↑{% elif stats.trends.downloads_today.direction == 'down' %}↓{% endif %}
  </div>
</div>
```

**Styling by Direction:**
- `up` → Green (more downloads = good)
- `down` → Red (fewer downloads = concerning)
- `stable` → Gray (no change)

**Exception:** For `failed` trend, the color logic is inverted:
- `up` → Red (more failures = bad)
- `down` → Green (fewer failures = good)

---

## Data Sources

The Stats API aggregates data from:

| Metric | Source |
|--------|--------|
| Playlists | `PlaylistModel` table |
| Tracks | `PlaylistItemModel` (distinct tracks) |
| Downloads | `DownloadModel` table |
| Provider data | `ProviderBrowseRepository` (Spotify/Deezer/Tidal) |

---

## Performance Notes

This endpoint performs several database queries:
- 8 COUNT queries for current stats
- 4 COUNT queries for trend calculations

For large databases, consider caching responses with a short TTL (e.g., 60 seconds).

---

## Related Documentation

- [Dashboard Feature](../features/README.md)
- [Download Management API](download-management.md)
- [Library Management API](library-management-api.md)
