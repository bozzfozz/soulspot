# Browse API

> **Version:** 1.0  
> **Last Updated:** 2025-01-16

---

## Overview

The Browse API provides endpoints for discovering new music without requiring Spotify authentication. It uses the **DeezerPlugin** to offer new releases, charts, and genre browsing.

---

## Architecture

```
Route (/browse/new-releases)
    ↓
DeezerPlugin (dependency injection)
    ↓
DeezerClient (HTTP calls)
    ↓
Deezer Public API (no OAuth!)
```

---

## Key Features

- **No authentication required** - Works for all users immediately
- **Plugin architecture** - Uses DeezerPlugin for clean separation
- **Multiple sources** - Aggregates from Deezer editorial + charts
- **New releases** - Fresh album releases from around the world
- **Compilation filtering** - Option to exclude compilation albums
- **Future extensibility** - Can add Spotify when user is authenticated

---

## Endpoints

### GET `/browse/new-releases`

Fetch new album releases from Deezer (no auth required).

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of releases to fetch (10-100) |
| `include_compilations` | boolean | true | Include compilation albums |

#### Response

Returns HTML page with album grid. Each album includes:
- Album cover artwork
- Title and artist name
- Release date
- Track count
- Record type (album, single, EP, compilation)
- Explicit content indicator
- Link to Deezer

#### Example Request

```http
GET /browse/new-releases?limit=50&include_compilations=false
```

#### Data Source

Uses `DeezerClient.get_browse_new_releases()` which combines:
1. **Editorial Releases** - Curated picks from Deezer's editorial team
2. **Chart Albums** - Top charting albums globally

Results are deduplicated and sorted by relevance.

---

## Album Data Structure

Each album in the response contains:

```json
{
  "deezer_id": 123456789,
  "title": "Album Title",
  "artist_name": "Artist Name",
  "artist_id": 987654,
  "release_date": "2025-01-15",
  "total_tracks": 12,
  "record_type": "album",
  "cover_small": "https://...",
  "cover_medium": "https://...",
  "cover_big": "https://...",
  "cover_xl": "https://...",
  "link": "https://www.deezer.com/album/123456789",
  "explicit": false
}
```

---

## Record Types

| Type | Description |
|------|-------------|
| `album` | Full-length album |
| `single` | Single track release |
| `ep` | Extended play (typically 4-6 tracks) |
| `compile` | Compilation/collection |

---

## Error Handling

If the Deezer API is unavailable, the page displays an error message:

```html
<div class="alert alert-warning">
    <i class="bi bi-exclamation-triangle"></i> Failed to fetch new releases: [error message]
</div>
```

---

## Rate Limits

Deezer API rate limits:
- **No authentication required**
- **50 requests per 5 seconds** per IP
- The client includes automatic rate limiting

---

## Future Enhancements

Planned additions:
1. **Spotify New Releases** - When user is authenticated with Spotify
2. **Genre filtering** - Browse by specific genre
3. **Regional charts** - Country-specific new releases
4. **Personalized recommendations** - Based on listening history
5. **Download queue integration** - One-click add to download queue

---

## Related Endpoints

- `GET /spotify/discover` - Similar artists (requires Spotify auth)
- `GET /search` - Search across all sources
- `GET /downloads` - Download queue management
