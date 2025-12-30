# Library API Reference

**Category:** Library Management  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Data Models](./data-models.md), [Workflows](./workflows.md), [API Overview](../01-api-reference/README.md)

---

## Overview

REST API endpoints for SoulSpot's library management system. The API follows RESTful conventions and is inspired by Lidarr's v1 API structure.

### Base URL

```
/api/v1
```

### Authentication

All endpoints require authentication via API key or session token.

```http
X-Api-Key: your-api-key-here
```

### Response Format

```json
{
  "data": { ... },
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 25
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "ARTIST_NOT_FOUND",
    "message": "Artist with ID 123 not found",
    "details": { ... }
  }
}
```

## Artist Endpoints

### List All Artists

```http
GET /api/v1/artist
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `mbId` | string | Filter by MusicBrainz Artist ID |
| `monitored` | boolean | Filter by monitored status |
| `qualityProfileId` | integer | Filter by quality profile |
| `tags` | string | Comma-separated tag IDs |
| `sort` | string | Sort field (name, added, albumCount) |
| `order` | string | Sort order (asc, desc) |
| `page` | integer | Page number (default: 1) |
| `perPage` | integer | Items per page (default: 25, max: 100) |

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "foreignArtistId": "f27ec8db-af05-4f36-916e-3d57f91ecf5e",
      "artistName": "Michael Jackson",
      "sortName": "Jackson, Michael",
      "artistType": "Person",
      "status": "ended",
      "monitored": true,
      "path": "/music/Michael Jackson",
      "qualityProfileId": 1,
      "genres": ["Pop", "R&B", "Soul"],
      "images": [{"coverType": "poster", "url": "/images/artists/1/poster.jpg"}],
      "ratings": {"value": 4.8, "votes": 15000},
      "statistics": {
        "albumCount": 12,
        "trackCount": 147,
        "trackFileCount": 142,
        "sizeOnDisk": 2147483648
      }
    }
  ],
  "meta": {
    "total": 250,
    "page": 1,
    "perPage": 25
  }
}
```

### Get Artist by ID

```http
GET /api/v1/artist/{id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Artist ID |

**Response:** Single artist object

### Add Artist

```http
POST /api/v1/artist
```

**Request Body:**

```json
{
  "foreignArtistId": "f27ec8db-af05-4f36-916e-3d57f91ecf5e",
  "artistName": "Michael Jackson",
  "rootFolderPath": "/music",
  "qualityProfileId": 1,
  "metadataProfileId": 1,
  "monitored": true,
  "monitorNewItems": "all",
  "addOptions": {
    "monitor": "all",
    "searchForMissingAlbums": true
  }
}
```

**Response:** Created artist object with `id`

### Update Artist

```http
PUT /api/v1/artist/{id}
```

**Request Body:** Partial artist object (only changed fields)

**Response:** Updated artist object

### Delete Artist

```http
DELETE /api/v1/artist/{id}?deleteFiles=true
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `deleteFiles` | boolean | Delete files from disk (default: false) |
| `addImportListExclusion` | boolean | Add to exclusion list (default: false) |

**Response:** `204 No Content`

## Album Endpoints

### List Albums

```http
GET /api/v1/album
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Filter by artist ID |
| `foreignAlbumId` | string | MusicBrainz Release Group ID |
| `monitored` | boolean | Filter by monitored status |
| `albumType` | string | Studio, EP, Single, etc. |

**Response:** Array of album objects with statistics

### Get Album by ID

```http
GET /api/v1/album/{id}
```

**Response:** Single album object with tracks

### Update Album

```http
PUT /api/v1/album/{id}
```

**Common Update:** Toggle monitoring

```json
{
  "monitored": true
}
```

**Response:** Updated album object

### Bulk Update Albums

```http
PUT /api/v1/album/bulk
```

**Request Body:**

```json
{
  "albumIds": [1, 2, 3],
  "changes": {
    "monitored": true
  }
}
```

**Response:** Array of updated albums

## Track Endpoints

### List Tracks

```http
GET /api/v1/track
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `albumId` | integer | Filter by album ID |
| `hasFile` | boolean | Filter by file availability |

**Response:** Array of track objects

### Get Track by ID

```http
GET /api/v1/track/{id}
```

**Response:** Single track object with file details

## TrackFile Endpoints

### Get TrackFile by ID

```http
GET /api/v1/trackfile/{id}
```

**Response:**

```json
{
  "id": 1,
  "trackId": 100,
  "path": "/music/Michael Jackson/Thriller (1982)/01 - Wanna Be Startin' Somethin'.flac",
  "size": 35567890,
  "quality": {
    "format": "FLAC",
    "bitrate": 1411,
    "sampleRate": 44100,
    "bitsPerSample": 16
  },
  "mediaInfo": {
    "audioChannels": 2,
    "audioCodec": "FLAC",
    "audioBitrate": "1411kbps"
  },
  "dateAdded": "2024-01-15T10:30:00Z"
}
```

### Delete TrackFile

```http
DELETE /api/v1/trackfile/{id}
```

**Response:** `204 No Content`

## Search Endpoints

### Search for Artist

```http
GET /api/v1/artist/lookup?term=michael+jackson
```

**Response:** Array of MusicBrainz artist search results

### Search for Album

```http
GET /api/v1/album/lookup?term=thriller&artistId=1
```

**Response:** Array of MusicBrainz album search results

## Statistics Endpoints

### Get Library Statistics

```http
GET /api/v1/library/stats
```

**Response:**

```json
{
  "artists": {
    "total": 250,
    "monitored": 200,
    "unmonitored": 50
  },
  "albums": {
    "total": 1500,
    "monitored": 1200,
    "studio": 800,
    "ep": 300,
    "single": 400
  },
  "tracks": {
    "total": 15000,
    "withFiles": 14500,
    "missing": 500
  },
  "storage": {
    "totalBytes": 536870912000,
    "usedBytes": 429496729600,
    "freeBytes": 107374182400
  }
}
```

## Batch Operations

### Bulk Delete Artists

```http
DELETE /api/v1/artist/bulk
```

**Request Body:**

```json
{
  "artistIds": [1, 2, 3],
  "deleteFiles": true,
  "addImportListExclusion": false
}
```

**Response:** Summary of deleted items

### Bulk Monitor/Unmonitor

```http
POST /api/v1/artist/bulk/monitor
```

**Request Body:**

```json
{
  "artistIds": [1, 2, 3],
  "monitored": true
}
```

**Response:** Array of updated artists

## Related Documentation

- [Data Models](./data-models.md) - Entity structures
- [Workflows](./workflows.md) - Common operations
- [API Overview](../01-api-reference/README.md) - Full API documentation
- [Authentication](../06-features/authentication.md) - API authentication
