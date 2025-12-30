# Track Management

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-11-25  
**Related Docs:** [Download Management](./download-management.md) | [API Reference: Tracks](../03-api-reference/tracks.md)

---

## Overview

Track Management enables managing individual tracks: search, download, metadata display and editing. Search tracks on Spotify, download from Soulseek, and edit metadata in both database and files.

---

## Features

### Track Search

- **Spotify Search:** Search for tracks on Spotify
- **Flexible Queries:** Search by title, artist, album, or ISRC

---

### Track Download

- **Soulseek Download:** Download tracks from Soulseek
- **Quality Selection:** Choose preferred quality
- **Automatic Search:** Find best available source

**Quality Options:**
- **Best:** Highest available quality (FLAC preferred, then by bitrate/file size)
- **Good:** Minimum 256kbps or FLAC
- **Any:** First available audio file

⚠️ **Note:** `SearchAndDownloadTrackUseCase` uses `AdvancedSearchService` for intelligent file selection with fuzzy matching and quality scoring. FLAC files receive 1000-point bonus in ranking.

---

### Track Details

- **Complete Metadata:** Title, artist, album, genre, year, etc.
- **Technical Info:** Duration, file format, file path
- **IDs:** Spotify URI, MusicBrainz ID, ISRC

---

### Metadata Editing

- **Database Update:** Update metadata in SoulSpot
- **File Tags:** Modify ID3 tags in audio file
- **Allowed Fields:** Title, artist, album, genre, year, track number, disc number

---

## Usage (Web UI)

### Search Track

1. Navigate to **Tracks** or use search bar
2. Enter search term
3. Results loaded from Spotify
4. Click track for details

---

### Download Track

1. Open track details
2. Click **Download**
3. Select desired quality:
   - **Best:** Highest quality (FLAC preferred)
   - **Good:** Minimum 256kbps
   - **Any:** First available
4. Download added to queue

---

### Edit Metadata

1. Open track details
2. Click **Edit Metadata**
3. Change desired fields
4. Click **Save**
5. Changes saved to DB and file

---

## API Endpoints

### GET `/api/tracks/search`

Search for tracks on Spotify.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | - | Search term (required) |
| `limit` | int | 20 | Number of results (max 100) |
| `access_token` | string | - | Spotify access token (required) |

**Response:**
```json
{
  "tracks": [
    {
      "id": "spotify-track-id",
      "name": "Track Title",
      "artists": [
        {"name": "Artist Name"}
      ],
      "album": {"name": "Album Name"},
      "duration_ms": 240000,
      "uri": "spotify:track:xyz"
    }
  ],
  "total": 50,
  "query": "search term",
  "limit": 20
}
```

---

### GET `/api/tracks/{track_id}`

Get track details.

**Response:**
```json
{
  "id": "track-uuid",
  "title": "Track Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "album_artist": "Album Artist",
  "genre": "Electronic",
  "year": 2024,
  "artist_id": "artist-uuid",
  "album_id": "album-uuid",
  "duration_ms": 240000,
  "track_number": 5,
  "disc_number": 1,
  "spotify_uri": "spotify:track:xyz",
  "musicbrainz_id": "mbid-123",
  "isrc": "USRC12345678",
  "file_path": "/music/Artist/Album/track.flac",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T00:00:00Z"
}
```

---

### POST `/api/tracks/{track_id}/download`

Start track download.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quality` | string | "best" | Quality preference (best, good, any) |

**Response:**
```json
{
  "message": "Download started",
  "track_id": "track-uuid",
  "download_id": "download-uuid",
  "quality": "best",
  "status": "queued"
}
```

---

### PUT `/api/tracks/{track_id}/metadata`

Update track metadata.

**Request:**
```json
{
  "title": "New Title",
  "artist": "New Artist",
  "album": "New Album",
  "genre": "New Genre",
  "year": 2025,
  "track_number": 1,
  "disc_number": 1
}
```

**Response:**
```json
{
  "message": "Metadata updated successfully",
  "track_id": "track-uuid",
  "updated_fields": ["title", "artist", "year"]
}
```

---

## Quality Scoring

**FLAC Files:** +1000 bonus points  
**Bitrate:** Higher bitrate = higher score  
**File Size:** Larger file (same format) = higher score  
**Fuzzy Matching:** Filename similarity to query

---

## Related Documentation

- **[Download Management](./download-management.md)** - Queue management
- **[Metadata Enrichment](./metadata-enrichment.md)** - Multi-source enrichment
- **[API Reference: Tracks](../03-api-reference/tracks.md)** - Full endpoint documentation

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
