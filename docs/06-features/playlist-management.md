# Playlist Management

**Category:** Features  
**Last Updated:** 2025-11-25  
**Related Docs:** [Spotify Sync](./spotify-sync.md) | [API Reference: Playlists](../03-api-reference/playlists.md)

---

## Overview

Playlist Management enables import, synchronization, and export of Spotify playlists. Import individual playlists or your entire Spotify library and keep them in sync automatically.

---

## Features

### Playlist Import

**Two Import Modes:**

1. **Single Playlist Import**
   - Import by Spotify URL or ID
   - Fetches all tracks with metadata
   - Creates local playlist copy

2. **Library Sync**
   - Imports all your Spotify playlists
   - Batch operation for entire library
   - Metadata only (fetch tracks later)

**Endpoint:** `POST /api/playlists/import`

---

### Playlist Synchronization

**Keep playlists up-to-date:**

- **Single Playlist Sync:** Update specific playlist
- **Batch Sync:** Update all imported playlists
- **Delta Sync:** Only new/changed tracks updated

**Endpoints:**
- `POST /api/playlists/{playlist_id}/sync` - Single playlist
- `POST /api/playlists/sync-all` - All playlists

---

### Playlist Export

**Export Formats:**

| Format | Use Case | Endpoint |
|--------|----------|----------|
| **M3U** | Media players (VLC, Foobar2000) | `GET /api/playlists/{id}/export/m3u` |
| **CSV** | Excel/Google Sheets analysis | `GET /api/playlists/{id}/export/csv` |
| **JSON** | Developers, backup | `GET /api/playlists/{id}/export/json` |

**M3U Example:**
```
#EXTM3U
#EXTINF:234,Artist - Track Title
/path/to/file.mp3
#EXTINF:187,Another Artist - Another Track
/path/to/another.mp3
```

---

### Missing Tracks Detection

**Identify tracks without local files:**

```json
GET /api/playlists/{id}/missing-tracks

Response:
{
  "playlist_id": "uuid",
  "playlist_name": "My Playlist",
  "missing_tracks": [...],
  "missing_count": 5,
  "total_tracks": 42
}
```

**Use Case:** Batch download missing tracks from playlist.

**Endpoint:** `POST /api/playlists/{id}/download-missing`

---

## Usage (Web UI)

### Import Playlist

1. Navigate to **Playlists** page
2. Click **Import Playlist** button
3. Paste Spotify playlist URL or ID
4. Click **Import**

**Accepted Formats:**
- Full URL: `https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl`
- Playlist ID: `2ZBCi09CSeWMBOoHZdN6Nl`

---

### Sync Library

1. Navigate to **Playlists** page
2. Click **Sync Library** button
3. All Spotify playlists imported (metadata only)
4. Select individual playlists for full track import

---

### Export Playlist

1. Open desired playlist
2. Click **Export** icon
3. Select format (M3U, CSV, JSON)
4. File downloads automatically

---

## API Endpoints

### POST `/api/playlists/import`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `playlist_id` | string | Spotify playlist ID or URL |
| `fetch_all_tracks` | boolean | Fetch all tracks (default: true) |

**Response:**
```json
{
  "message": "Playlist imported successfully",
  "playlist_id": "uuid",
  "playlist_name": "My Playlist",
  "tracks_imported": 42,
  "tracks_failed": 0,
  "errors": []
}
```

---

### POST `/api/playlists/sync-library`

**Response:**
```json
{
  "message": "Playlist library synced successfully",
  "total_playlists": 15,
  "synced_count": 10,
  "updated_count": 5,
  "results": [...]
}
```

---

### GET `/api/playlists/`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 20 | Results per page (max 100) |

---

### GET `/api/playlists/{playlist_id}`

**Response:**
```json
{
  "id": "uuid",
  "name": "Playlist Name",
  "description": "Description",
  "source": "spotify",
  "track_ids": ["track-uuid-1", "track-uuid-2"],
  "track_count": 42,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T00:00:00Z"
}
```

---

### POST `/api/playlists/{playlist_id}/sync`

Sync single playlist with Spotify (delta update).

---

### POST `/api/playlists/sync-all`

Sync all playlists with Spotify.

⚠️ **Warning:** May take long time with many playlists!

---

### Export Endpoints

- `GET /api/playlists/{id}/export/m3u` - M3U format
- `GET /api/playlists/{id}/export/csv` - CSV format
- `GET /api/playlists/{id}/export/json` - JSON format

---

### GET `/api/playlists/{playlist_id}/missing-tracks`

Returns tracks in playlist without local files.

---

### POST `/api/playlists/{playlist_id}/download-missing`

Identifies missing tracks for download queue.

---

## Workflow Example

```
1. Copy Spotify playlist URL
   ↓
2. POST /api/playlists/import (with URL)
   ↓
3. Playlist saved to database
   ↓
4. GET /api/playlists/{id}/missing-tracks
   ↓
5. POST /api/playlists/{id}/download-missing (if needed)
   ↓
6. Download tracks via Download Manager
   ↓
7. Export as M3U for media player
```

---

## Troubleshooting

### Import Fails

**Causes:**
1. **No Spotify session** - Authenticate at `/settings?tab=spotify`
2. **Private playlist** - Must be public or owned by you
3. **Invalid URL/ID** - Check format

---

### Tracks Not Imported

**Causes:**
1. **Rate limiting** - Spotify API limits, wait and retry
2. **Large playlist** - 1000+ tracks may take time

---

### Export Missing File Paths

**Solution:** M3U export only works for downloaded tracks. Download missing tracks first.

---

## Related Documentation

- **[Download Management](./download-management.md)** - Track downloading
- **[Track Management](./track-management.md)** - Individual track management
- **[Authentication](./authentication.md)** - Spotify connection

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
