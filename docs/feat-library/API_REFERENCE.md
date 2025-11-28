# Library API Reference

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr API](https://github.com/Lidarr/Lidarr) v1 Endpoints

---

## Overview

This document defines the REST API endpoints for SoulSpot's library management system. The API follows RESTful conventions and is inspired by Lidarr's v1 API structure.

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

All responses are JSON with consistent structure:

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

---

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
| `metadataProfileId` | integer | Filter by metadata profile |
| `tags` | string | Comma-separated tag IDs |
| `sort` | string | Sort field (name, added, albumCount, etc.) |
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
      "cleanName": "michaeljackson",
      "artistType": "Person",
      "status": "ended",
      "monitored": true,
      "monitorNewItems": "all",
      "path": "/music/Michael Jackson",
      "rootFolderPath": "/music",
      "qualityProfileId": 1,
      "metadataProfileId": 1,
      "overview": "Michael Joseph Jackson was an American singer...",
      "genres": ["Pop", "R&B", "Soul"],
      "images": [
        {"coverType": "poster", "url": "/images/artists/1/poster.jpg"}
      ],
      "ratings": {"value": 4.8, "votes": 15000},
      "tags": [1, 2],
      "added": "2024-01-15T10:30:00Z",
      "ended": true,
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

**Response:** Single artist object (same structure as list item)

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
  "tags": [1, 2],
  "addOptions": {
    "monitor": "all",
    "albumsToMonitor": [],
    "searchForMissingAlbums": true
  }
}
```

**Add Options:**

| Field | Type | Description |
|-------|------|-------------|
| `monitor` | string | "none", "specific", "all", "future" |
| `albumsToMonitor` | array | Album IDs to monitor (if monitor="specific") |
| `searchForMissingAlbums` | boolean | Trigger search after adding |

**Response:** Created artist object with ID

### Update Artist

```http
PUT /api/v1/artist/{id}
```

**Request Body:** Full artist object with updated fields

**Response:** Updated artist object

### Delete Artist

```http
DELETE /api/v1/artist/{id}
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `deleteFiles` | boolean | Delete files from disk (default: false) |
| `addImportListExclusion` | boolean | Add to exclusion list (default: false) |

**Response:** 204 No Content

### Refresh Artist

```http
POST /api/v1/artist/{id}/refresh
```

Re-fetch artist metadata from MusicBrainz.

**Response:** 202 Accepted

### Search Artist

```http
POST /api/v1/artist/{id}/search
```

Trigger search for missing albums.

**Response:** 202 Accepted

---

## Album Endpoints

### List Albums

```http
GET /api/v1/album
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Filter by artist ID |
| `albumIds` | string | Comma-separated album IDs |
| `foreignAlbumId` | string | MusicBrainz Release Group ID |
| `includeAllArtistAlbums` | boolean | Include all albums for artist |
| `monitored` | boolean | Filter by monitored status |
| `albumType` | string | Filter by album type |
| `sort` | string | Sort field |
| `order` | string | Sort order |
| `page` | integer | Page number |
| `perPage` | integer | Items per page |

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "artistId": 1,
      "foreignAlbumId": "6f5e7e10-5e4f-4e3a-9a1a-2b3c4d5e6f7a",
      "title": "Thriller",
      "overview": "Thriller is the sixth studio album...",
      "disambiguation": "",
      "albumType": "Album",
      "secondaryTypes": [],
      "monitored": true,
      "anyReleaseOk": true,
      "releaseDate": "1982-11-30T00:00:00Z",
      "genres": ["Pop", "R&B"],
      "media": [
        {"mediumNumber": 1, "mediumFormat": "CD"}
      ],
      "images": [
        {"coverType": "cover", "url": "/images/albums/1/cover.jpg"}
      ],
      "releases": [
        {
          "id": 1,
          "foreignReleaseId": "...",
          "title": "Thriller (US CD)",
          "trackCount": 9,
          "format": "CD",
          "country": ["US"],
          "monitored": true
        }
      ],
      "statistics": {
        "trackCount": 9,
        "trackFileCount": 9,
        "sizeOnDisk": 524288000,
        "percentOfTracks": 100.0
      },
      "grabbed": false
    }
  ],
  "meta": { ... }
}
```

### Get Album by ID

```http
GET /api/v1/album/{id}
```

### Update Album

```http
PUT /api/v1/album/{id}
```

### Bulk Monitor Albums

```http
PUT /api/v1/album/monitor
```

**Request Body:**

```json
{
  "albumIds": [1, 2, 3, 4, 5],
  "monitored": true
}
```

**Response:** Array of updated album objects

---

## Track Endpoints

### List Tracks

```http
GET /api/v1/track
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Filter by artist ID |
| `albumId` | integer | Filter by album ID |
| `albumReleaseId` | integer | Filter by specific release |
| `trackIds` | string | Comma-separated track IDs |

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "artistId": 1,
      "albumId": 1,
      "foreignTrackId": "...",
      "foreignRecordingId": "...",
      "trackFileId": 1,
      "albumReleaseId": 1,
      "absoluteTrackNumber": 1,
      "trackNumber": "1",
      "title": "Wanna Be Startin' Somethin'",
      "duration": 363000,
      "explicit": false,
      "mediumNumber": 1,
      "hasFile": true,
      "ratings": {"value": 4.5, "votes": 1000}
    }
  ],
  "meta": { ... }
}
```

---

## Track File Endpoints

### List Track Files

```http
GET /api/v1/trackFile
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Filter by artist ID |
| `albumId` | integer | Filter by album ID |
| `trackFileIds` | string | Comma-separated file IDs |
| `unmapped` | boolean | Only unmapped files |

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "artistId": 1,
      "albumId": 1,
      "trackIds": [1],
      "path": "/music/Michael Jackson/Thriller/01 - Wanna Be Startin' Somethin'.flac",
      "size": 52428800,
      "dateAdded": "2024-01-15T10:30:00Z",
      "quality": {
        "quality": {"id": 6, "name": "FLAC"},
        "revision": {"version": 1, "real": 0, "isRepack": false}
      },
      "qualityWeight": 600,
      "mediaInfo": {
        "audioChannels": 2,
        "audioBitrate": 1411,
        "audioCodec": "FLAC",
        "audioBits": 16,
        "audioSampleRate": 44100
      },
      "qualityCutoffNotMet": false
    }
  ],
  "meta": { ... }
}
```

### Get Track File by ID

```http
GET /api/v1/trackFile/{id}
```

### Update Track File

```http
PUT /api/v1/trackFile/{id}
```

### Delete Track File

```http
DELETE /api/v1/trackFile/{id}
```

### Bulk Delete Track Files

```http
DELETE /api/v1/trackFile/bulk
```

**Request Body:**

```json
{
  "trackFileIds": [1, 2, 3]
}
```

---

## Rename Endpoints

### Preview Rename

```http
GET /api/v1/rename
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Artist ID (required) |
| `albumId` | integer | Album ID (optional, for album-specific) |

**Response:**

```json
{
  "data": [
    {
      "artistId": 1,
      "albumId": 1,
      "trackNumbers": [1],
      "trackFileId": 1,
      "existingPath": "/music/Michael Jackson/Thriller/track01.flac",
      "newPath": "/music/Michael Jackson/Thriller/01 - Wanna Be Startin' Somethin'.flac"
    }
  ]
}
```

### Execute Rename

```http
POST /api/v1/rename
```

**Request Body:**

```json
{
  "artistId": 1,
  "files": [
    {"trackFileId": 1, "newPath": "..."}
  ]
}
```

---

## Retag Endpoints

### Preview Retag

```http
GET /api/v1/retag
```

Preview metadata tag changes for audio files.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `artistId` | integer | Artist ID (required) |
| `albumId` | integer | Album ID (optional) |

**Response:**

```json
{
  "data": [
    {
      "artistId": 1,
      "albumId": 1,
      "trackNumbers": [1],
      "trackFileId": 1,
      "path": "/music/...",
      "changes": [
        {"field": "Artist", "oldValue": "M. Jackson", "newValue": "Michael Jackson"},
        {"field": "Album", "oldValue": "Thriller 1982", "newValue": "Thriller"}
      ]
    }
  ]
}
```

### Execute Retag

```http
POST /api/v1/retag
```

**Request Body:**

```json
{
  "artistId": 1,
  "files": [1, 2, 3]
}
```

---

## Manual Import Endpoints

### Get Import Candidates

```http
GET /api/v1/manualimport
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `folder` | string | Path to scan for audio files |
| `downloadId` | string | Download client ID (optional) |
| `artistId` | integer | Pre-select artist |
| `filterExistingFiles` | boolean | Hide already imported files |
| `replaceExistingFiles` | boolean | Allow replacing existing |

**Response:**

```json
{
  "data": [
    {
      "id": "temp-1",
      "path": "/downloads/album/01-track.flac",
      "relativePath": "01-track.flac",
      "folderName": "album",
      "name": "01-track.flac",
      "size": 52428800,
      "quality": {"quality": {"id": 6, "name": "FLAC"}},
      "artist": null,
      "album": null,
      "albumReleaseId": null,
      "tracks": [],
      "rejections": [],
      "audioTags": {
        "artist": "Michael Jackson",
        "album": "Thriller",
        "title": "Wanna Be Startin' Somethin'",
        "trackNumber": "1",
        "year": 1982
      }
    }
  ]
}
```

### Execute Manual Import

```http
POST /api/v1/manualimport
```

**Request Body:**

```json
{
  "importMode": "move",
  "files": [
    {
      "path": "/downloads/album/01-track.flac",
      "artistId": 1,
      "albumId": 1,
      "albumReleaseId": 1,
      "trackIds": [1],
      "quality": {"quality": {"id": 6, "name": "FLAC"}},
      "disableReleaseSwitching": false
    }
  ]
}
```

**Import Modes:**
- `copy` — Copy files to library
- `move` — Move files to library
- `hardlink` — Create hard links (same filesystem)
- `hardlinkIfPossible` — Hardlink or copy

---

## Quality Profile Endpoints

### List Quality Profiles

```http
GET /api/v1/qualityprofile
```

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "Lossless",
      "upgradeAllowed": true,
      "cutoff": 6,
      "items": [
        {
          "id": 1000,
          "name": "Lossless",
          "quality": null,
          "items": [
            {"quality": {"id": 6, "name": "FLAC"}, "allowed": true},
            {"quality": {"id": 8, "name": "ALAC"}, "allowed": true}
          ],
          "allowed": true
        },
        {
          "quality": {"id": 3, "name": "MP3-320"},
          "items": [],
          "allowed": true
        }
      ],
      "minFormatScore": 0,
      "cutoffFormatScore": 0,
      "formatItems": []
    }
  ]
}
```

### Get Quality Profile

```http
GET /api/v1/qualityprofile/{id}
```

### Create Quality Profile

```http
POST /api/v1/qualityprofile
```

### Update Quality Profile

```http
PUT /api/v1/qualityprofile/{id}
```

### Delete Quality Profile

```http
DELETE /api/v1/qualityprofile/{id}
```

---

## Metadata Profile Endpoints

### List Metadata Profiles

```http
GET /api/v1/metadataprofile
```

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "Standard",
      "primaryAlbumTypes": [
        {"albumType": {"id": 1, "name": "Album"}, "allowed": true},
        {"albumType": {"id": 2, "name": "EP"}, "allowed": true},
        {"albumType": {"id": 3, "name": "Single"}, "allowed": false}
      ],
      "secondaryAlbumTypes": [
        {"albumType": {"id": 1, "name": "Compilation"}, "allowed": false},
        {"albumType": {"id": 2, "name": "Live"}, "allowed": false}
      ],
      "releaseStatuses": [
        {"releaseStatus": {"id": 1, "name": "Official"}, "allowed": true},
        {"releaseStatus": {"id": 2, "name": "Promotional"}, "allowed": false}
      ]
    }
  ]
}
```

### Create Metadata Profile

```http
POST /api/v1/metadataprofile
```

### Update Metadata Profile

```http
PUT /api/v1/metadataprofile/{id}
```

### Delete Metadata Profile

```http
DELETE /api/v1/metadataprofile/{id}
```

---

## Root Folder Endpoints

### List Root Folders

```http
GET /api/v1/rootfolder
```

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "path": "/music",
      "accessible": true,
      "freeSpace": 500000000000,
      "totalSpace": 1000000000000,
      "defaultMetadataProfileId": 1,
      "defaultQualityProfileId": 1,
      "defaultMonitorOption": "all",
      "defaultNewItemMonitorOption": "all",
      "defaultTags": []
    }
  ]
}
```

### Add Root Folder

```http
POST /api/v1/rootfolder
```

### Delete Root Folder

```http
DELETE /api/v1/rootfolder/{id}
```

---

## Tag Endpoints

### List Tags

```http
GET /api/v1/tag
```

**Response:**

```json
{
  "data": [
    {"id": 1, "label": "Favorites"},
    {"id": 2, "label": "To Review"},
    {"id": 3, "label": "Complete"}
  ]
}
```

### Create Tag

```http
POST /api/v1/tag
```

### Update Tag

```http
PUT /api/v1/tag/{id}
```

### Delete Tag

```http
DELETE /api/v1/tag/{id}
```

---

## Search Endpoints

### Lookup Artist

```http
GET /api/v1/artist/lookup
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `term` | string | Search term (name or MusicBrainz ID) |

**Response:**

```json
{
  "data": [
    {
      "foreignArtistId": "f27ec8db-af05-4f36-916e-3d57f91ecf5e",
      "artistName": "Michael Jackson",
      "overview": "...",
      "artistType": "Person",
      "disambiguation": "",
      "images": [...],
      "ratings": {...}
    }
  ]
}
```

### Lookup Album

```http
GET /api/v1/album/lookup
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `term` | string | Search term |
| `artistId` | integer | Filter by artist (optional) |

---

## Command Endpoints

### Get Running Commands

```http
GET /api/v1/command
```

### Execute Command

```http
POST /api/v1/command
```

**Available Commands:**

```json
// Refresh all artists
{"name": "RefreshArtist"}

// Refresh specific artist
{"name": "RefreshArtist", "artistId": 1}

// Search for missing albums
{"name": "MissingAlbumSearch"}

// Rescan artist folders
{"name": "RescanFolders"}

// Rename artist files
{"name": "RenameArtist", "artistIds": [1, 2, 3]}

// Retag artist files
{"name": "RetagArtist", "artistIds": [1, 2, 3]}

// Clean up library
{"name": "CleanUpRecycleBin"}

// Backup database
{"name": "Backup"}
```

### Get Command Status

```http
GET /api/v1/command/{id}
```

---

## Bulk Edit Endpoints

### Bulk Edit Artists

```http
PUT /api/v1/artist/editor
```

**Request Body:**

```json
{
  "artistIds": [1, 2, 3],
  "monitored": true,
  "qualityProfileId": 2,
  "metadataProfileId": 1,
  "rootFolderPath": "/music",
  "moveFiles": true,
  "tags": [1, 2],
  "applyTags": "add"
}
```

**Apply Tags Options:**
- `add` — Add to existing tags
- `remove` — Remove from tags
- `replace` — Replace all tags

### Bulk Delete Artists

```http
DELETE /api/v1/artist/editor
```

**Request Body:**

```json
{
  "artistIds": [1, 2, 3],
  "deleteFiles": false,
  "addImportListExclusion": true
}
```

---

## Python FastAPI Implementation Example

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

router = APIRouter(prefix="/api/v1", tags=["library"])

@router.get("/artist", response_model=PaginatedResponse[ArtistResponse])
async def list_artists(
    db: AsyncSession = Depends(get_db),
    mbId: Optional[str] = None,
    monitored: Optional[bool] = None,
    qualityProfileId: Optional[int] = None,
    metadataProfileId: Optional[int] = None,
    tags: Optional[str] = None,
    sort: str = "sortName",
    order: str = "asc",
    page: int = Query(1, ge=1),
    perPage: int = Query(25, ge=1, le=100),
):
    """
    # Hey future me – this endpoint can get heavy with lots of artists.
    # Make sure to use proper indexing and consider caching statistics.
    # The tags parameter is comma-separated for URL simplicity.
    """
    query = select(Artist)
    
    # Apply filters
    if mbId:
        query = query.where(Artist.foreign_artist_id == mbId)
    if monitored is not None:
        query = query.where(Artist.monitored == monitored)
    if qualityProfileId:
        query = query.where(Artist.quality_profile_id == qualityProfileId)
    if metadataProfileId:
        query = query.where(Artist.metadata_profile_id == metadataProfileId)
    if tags:
        tag_ids = [int(t) for t in tags.split(",")]
        # JSON array containment query depends on DB
        query = query.where(Artist.tags.contains(tag_ids))
    
    # Apply sorting
    sort_column = getattr(Artist, sort, Artist.sort_name)
    if order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)
    
    # Pagination
    offset = (page - 1) * perPage
    query = query.offset(offset).limit(perPage)
    
    result = await db.execute(query)
    artists = result.scalars().all()
    
    # Get total count
    count_query = select(func.count(Artist.id))
    # Apply same filters...
    total = await db.scalar(count_query)
    
    return {
        "data": [ArtistResponse.from_orm(a) for a in artists],
        "meta": {"total": total, "page": page, "perPage": perPage}
    }


@router.post("/artist", response_model=ArtistResponse, status_code=201)
async def add_artist(
    artist_data: ArtistCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a new artist to the library."""
    # Check if already exists
    existing = await db.scalar(
        select(Artist).where(Artist.foreign_artist_id == artist_data.foreignArtistId)
    )
    if existing:
        raise HTTPException(400, "Artist already exists in library")
    
    # Fetch metadata from MusicBrainz
    mb_data = await musicbrainz_service.get_artist(artist_data.foreignArtistId)
    
    # Create artist
    artist = Artist(
        foreign_artist_id=artist_data.foreignArtistId,
        artist_name=mb_data.name,
        sort_name=mb_data.sort_name,
        clean_name=slugify(mb_data.name),
        artist_type=mb_data.type,
        path=f"{artist_data.rootFolderPath}/{mb_data.name}",
        root_folder_path=artist_data.rootFolderPath,
        quality_profile_id=artist_data.qualityProfileId,
        metadata_profile_id=artist_data.metadataProfileId,
        monitored=artist_data.monitored,
        monitor_new_items=artist_data.monitorNewItems,
        overview=mb_data.overview,
        genres=mb_data.genres,
        images=mb_data.images,
        tags=artist_data.tags,
    )
    
    db.add(artist)
    await db.commit()
    await db.refresh(artist)
    
    # Fetch and add albums based on monitoring options
    if artist_data.addOptions.monitor != "none":
        await album_service.sync_albums_for_artist(artist, artist_data.addOptions)
    
    return ArtistResponse.from_orm(artist)
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
