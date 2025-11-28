# Library Management Workflows

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr Workflows](https://github.com/Lidarr/Lidarr)

---

## Overview

This document defines the key workflows for managing a music library in SoulSpot. Each workflow includes user interactions, system processes, and API calls.

---

## 1. Add Artist Workflow

### User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      ADD ARTIST WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User clicks "Add Artist"                                       │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Search Dialog   │  ← Type artist name                        │
│  │ (MusicBrainz)   │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Select Artist   │  ← Pick from search results                │
│  │ from Results    │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │            ADD ARTIST OPTIONS               │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ Root Folder:    [/music       ▼]   │    │                │
│  │  │ Quality Profile: [Lossless    ▼]   │    │                │
│  │  │ Metadata Profile: [Standard   ▼]   │    │                │
│  │  │ Monitor:         [All Albums  ▼]   │    │                │
│  │  │ Tags:            [+ Add Tag     ]   │    │                │
│  │  │                                     │    │                │
│  │  │ ☑ Search for missing albums         │    │                │
│  │  │ ☐ Start monitoring only             │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  [Cancel]                    [Add Artist]    │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Create Artist   │  → POST /api/v1/artist                     │
│  │ in Database     │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ├──────────────────────────────────┐                   │
│          │                                  │                   │
│          ▼                                  ▼                   │
│  ┌─────────────────┐              ┌─────────────────┐           │
│  │ Fetch Albums    │              │ Create Artist   │           │
│  │ from MusicBrainz│              │ Folder on Disk  │           │
│  └───────┬─────────┘              └─────────────────┘           │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Apply Monitor   │  ← Based on monitor option                 │
│  │ Settings        │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Trigger Search  │  ← If "Search for missing" enabled         │
│  │ for Albums      │                                            │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Monitor Options

| Option | Description | Albums Monitored |
|--------|-------------|------------------|
| All Albums | Monitor all current and future | All existing + new |
| Future Albums | Only monitor new releases | None existing, all new |
| Missing Albums | Albums without files | Only incomplete |
| Existing Albums | Albums with some files | Only with files |
| Latest Album | Most recent release only | 1 album |
| First Album | Debut album only | 1 album |
| None | No automatic monitoring | None |

### API Sequence

```python
# 1. Search MusicBrainz
GET /api/v1/artist/lookup?term=michael+jackson

# 2. Add artist with options
POST /api/v1/artist
{
  "foreignArtistId": "f27ec8db-af05-4f36-916e-3d57f91ecf5e",
  "artistName": "Michael Jackson",
  "rootFolderPath": "/music",
  "qualityProfileId": 1,
  "metadataProfileId": 1,
  "monitored": true,
  "monitorNewItems": "all",
  "tags": [],
  "addOptions": {
    "monitor": "all",
    "searchForMissingAlbums": true
  }
}

# 3. System fetches albums from MusicBrainz
# 4. System applies monitoring based on addOptions.monitor
# 5. System triggers search if searchForMissingAlbums=true
```

---

## 2. Library Import Workflow

### Manual Import Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    LIBRARY IMPORT WORKFLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User has existing music files in a folder                      │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Manual Import   │  ← Click "Manual Import" button            │
│  │ Dialog          │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Select Folder   │  ← Browse to /downloads/music              │
│  │ to Import       │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Scan Folder     │  → Identify audio files                    │
│  │ for Audio Files │  → Read existing tags                      │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │          MANUAL IMPORT PREVIEW              │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ File                 │ Artist │ Album│    │                │
│  │  ├─────────────────────────────────────┤    │                │
│  │  │ 01-track.flac        │ [▼]    │ [▼]  │    │                │
│  │  │ 02-track.flac        │ [▼]    │ [▼]  │    │                │
│  │  │ 03-track.flac        │ [▼]    │ [▼]  │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  Import Mode: [Move ▼]                       │                │
│  │                                              │                │
│  │  [Cancel]                    [Import]        │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          │  User assigns artists/albums to files                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Execute Import  │  → Move/Copy files to library              │
│  │                 │  → Rename per naming config                │
│  │                 │  → Update database                         │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Import Preview Response

```json
{
  "data": [
    {
      "id": "temp-1",
      "path": "/downloads/album/01-track.flac",
      "name": "01-track.flac",
      "size": 52428800,
      "quality": {"quality": {"id": 6, "name": "FLAC"}},
      "artist": {
        "id": 1,
        "artistName": "Michael Jackson"
      },
      "album": {
        "id": 1,
        "title": "Thriller"
      },
      "tracks": [
        {"id": 1, "title": "Wanna Be Startin' Somethin'"}
      ],
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

### Import Modes

| Mode | Description | Source Files |
|------|-------------|--------------|
| Move | Move files to library | Deleted from source |
| Copy | Copy files to library | Remain in source |
| Hardlink | Create hardlinks | Shared storage, same disk |
| Hardlink/Copy | Try hardlink, fallback to copy | Best effort |

---

## 3. Organize & Rename Workflow

### Rename Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORGANIZE & RENAME WORKFLOW                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User wants to reorganize files to match naming config          │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Artist Page     │  ← View artist details                     │
│  │ or Album Page   │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Click "Organize"│  ← Or "Rename Files"                       │
│  │ Button          │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Fetch Preview   │  → GET /api/v1/rename?artistId=1           │
│  │                 │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │            RENAME PREVIEW                   │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ Current Path → New Path              │    │                │
│  │  ├─────────────────────────────────────┤    │                │
│  │  │ ☑ /music/MJ/Thriller/track1.flac    │    │                │
│  │  │   → /music/Michael Jackson/Thriller │    │                │
│  │  │      (1982)/01 - Wanna Be...flac    │    │                │
│  │  │                                     │    │                │
│  │  │ ☑ /music/MJ/Thriller/track2.flac    │    │                │
│  │  │   → /music/Michael Jackson/Thriller │    │                │
│  │  │      (1982)/02 - Baby Be Mine.flac  │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  [Cancel]              [Organize Selected]   │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Execute Rename  │  → POST /api/v1/rename                     │
│  │                 │  → Move files                              │
│  │                 │  → Update database paths                   │
│  │                 │  → Clean empty folders                     │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Rename API

```python
# 1. Get rename preview
GET /api/v1/rename?artistId=1&albumId=1

# Response
{
  "data": [
    {
      "artistId": 1,
      "albumId": 1,
      "trackNumbers": [1],
      "trackFileId": 1,
      "existingPath": "/music/MJ/Thriller/track1.flac",
      "newPath": "/music/Michael Jackson/Thriller (1982)/01 - Wanna Be Startin' Somethin'.flac"
    }
  ]
}

# 2. Execute rename
POST /api/v1/rename
{
  "artistId": 1,
  "files": [
    {"trackFileId": 1, "newPath": "..."}
  ]
}
```

---

## 4. Album Studio Workflow

### Bulk Monitoring Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALBUM STUDIO WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User needs to manage monitoring for multiple albums            │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Navigate to     │                                            │
│  │ "Album Studio"  │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ALBUM STUDIO                         │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │ Filters: [Monitored ▼] [Quality ▼] [Tags ▼]       │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  │                                                         │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │ Michael Jackson                [Monitor All] [None]│  │    │
│  │  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐             │  │    │
│  │  │  │ ☑  │ │ ☑  │ │ ☐  │ │ ☑  │ │ ☐  │             │  │    │
│  │  │  │1979│ │1982│ │1987│ │1991│ │1995│             │  │    │
│  │  │  │ OTW│ │Thrl│ │Bad │ │Dngr│ │Hist│             │  │    │
│  │  │  └────┘ └────┘ └────┘ └────┘ └────┘             │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  │                                                         │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │ The Beatles                    [Monitor All] [None]│  │    │
│  │  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐             │  │    │
│  │  │  │ ☑  │ │ ☑  │ │ ☑  │ │ ☑  │ │ ☑  │             │  │    │
│  │  │  │1963│ │1965│ │1966│ │1967│ │1969│             │  │    │
│  │  │  │PPM │ │Help│ │Rvlv│ │SP  │ │AR  │             │  │    │
│  │  │  └────┘ └────┘ └────┘ └────┘ └────┘             │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  │                                                         │    │
│  │  [Cancel Changes]              [Save Changes (5)]       │    │
│  └─────────────────────────────────────────────────────────┘    │
│          │                                                      │
│          │  User clicks albums to toggle monitoring             │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Save Changes    │  → PUT /api/v1/album/monitor               │
│  │                 │                                            │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Album Studio API

```python
# Bulk update monitoring
PUT /api/v1/album/monitor
{
  "albumIds": [1, 2, 5, 8, 12],
  "monitored": true
}

# Response
{
  "data": [
    {"id": 1, "title": "Off the Wall", "monitored": true},
    {"id": 2, "title": "Thriller", "monitored": true},
    ...
  ]
}
```

---

## 5. Bulk Edit Workflow

### Artist Bulk Editor

```
┌─────────────────────────────────────────────────────────────────┐
│                    BULK EDIT WORKFLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User selects multiple artists in library                       │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Selection Mode  │  ← Check boxes on artist rows              │
│  │ (Multi-select)  │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Bulk Action Bar │  ← Appears when items selected             │
│  │ [5 Selected]    │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Click "Edit"    │                                            │
│  │                 │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │            BULK EDIT DIALOG                 │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ Quality Profile: [No Change ▼]      │    │                │
│  │  │ Metadata Profile: [No Change ▼]     │    │                │
│  │  │ Root Folder:      [No Change ▼]     │    │                │
│  │  │ Monitored:        [No Change ▼]     │    │                │
│  │  │                                     │    │                │
│  │  │ Tags:                               │    │                │
│  │  │   Apply Mode: [Add ▼]               │    │                │
│  │  │   [Favorites] [Rock] [+ Add]        │    │                │
│  │  │                                     │    │                │
│  │  │ ☐ Move Files (if changing folder)   │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  [Cancel]                    [Apply to 5]    │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Apply Changes   │  → PUT /api/v1/artist/editor               │
│  │                 │                                            │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Bulk Edit API

```python
# Bulk edit artists
PUT /api/v1/artist/editor
{
  "artistIds": [1, 2, 3, 4, 5],
  "monitored": true,
  "qualityProfileId": 2,
  "tags": [1, 2],
  "applyTags": "add",
  "moveFiles": false
}

# applyTags options:
# - "add": Add tags to existing
# - "remove": Remove tags from existing
# - "replace": Replace all tags
```

---

## 6. Retag Files Workflow

### Update Audio File Metadata

```
┌─────────────────────────────────────────────────────────────────┐
│                    RETAG FILES WORKFLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Files have incorrect/missing metadata tags                     │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Artist/Album    │                                            │
│  │ Details Page    │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Click "Retag"   │  ← From action menu                        │
│  │                 │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Fetch Preview   │  → GET /api/v1/retag?artistId=1            │
│  │                 │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │            RETAG PREVIEW                    │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ File: 01 - Track.flac                │    │                │
│  │  │                                     │    │                │
│  │  │ Field      │ Current    │ New       │    │                │
│  │  ├────────────┼────────────┼───────────┤    │                │
│  │  │ Artist     │ M. Jackson │ Michael   │    │                │
│  │  │            │            │ Jackson   │    │                │
│  │  │ Album      │ thriller   │ Thriller  │    │                │
│  │  │ Year       │ (empty)    │ 1982      │    │                │
│  │  │ Track #    │ 1          │ 1         │    │                │
│  │  │ Genre      │ (empty)    │ Pop       │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  [Cancel]                    [Apply Tags]    │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Execute Retag   │  → POST /api/v1/retag                      │
│  │                 │  → Write tags to files                     │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Retag API

```python
# 1. Preview tag changes
GET /api/v1/retag?artistId=1&albumId=1

# Response
{
  "data": [
    {
      "artistId": 1,
      "albumId": 1,
      "trackFileId": 1,
      "path": "/music/.../01 - Track.flac",
      "changes": [
        {"field": "Artist", "oldValue": "M. Jackson", "newValue": "Michael Jackson"},
        {"field": "Album", "oldValue": "thriller", "newValue": "Thriller"},
        {"field": "Year", "oldValue": "", "newValue": "1982"}
      ]
    }
  ]
}

# 2. Execute retag
POST /api/v1/retag
{
  "artistId": 1,
  "files": [1, 2, 3]
}
```

---

## 7. Search & Download Workflow

### Automatic Search

```
┌─────────────────────────────────────────────────────────────────┐
│                 SEARCH & DOWNLOAD WORKFLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Album is monitored but missing files                           │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────────────────────────────────────┐            │
│  │             TRIGGER SEARCH                      │            │
│  │                                                 │            │
│  │  Automatic:                                     │            │
│  │  • New album added with search enabled          │            │
│  │  • Scheduled missing album search task          │            │
│  │  • RSS sync finds new release                   │            │
│  │                                                 │            │
│  │  Manual:                                        │            │
│  │  • User clicks "Search" on album                │            │
│  │  • User triggers "Search All Missing"           │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────┐            │
│  │            BUILD SEARCH QUERY                   │            │
│  │                                                 │            │
│  │  Artist: Michael Jackson                        │            │
│  │  Album: Thriller                                │            │
│  │  Year: 1982                                     │            │
│  │  Quality: FLAC preferred                        │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────┐            │
│  │           SEARCH SOULSEEK (slskd)               │            │
│  │                                                 │            │
│  │  → Query slskd API for results                  │            │
│  │  → Filter by allowed qualities                  │            │
│  │  → Score results by preference                  │            │
│  │  → Select best match                            │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────┐            │
│  │            QUALITY DECISION                     │            │
│  │                                                 │            │
│  │  Is quality allowed? ─No──► Skip result         │            │
│  │         │Yes                                    │            │
│  │         ▼                                       │            │
│  │  Is upgrade needed? ─No──► Use if no file       │            │
│  │         │Yes                                    │            │
│  │         ▼                                       │            │
│  │  Queue download                                 │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────┐            │
│  │           DOWNLOAD & IMPORT                     │            │
│  │                                                 │            │
│  │  → Download via slskd                           │            │
│  │  → Monitor download progress                    │            │
│  │  → On completion, trigger import                │            │
│  │  → Move to library, rename, update DB           │            │
│  └─────────────────────────────────────────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Search API Commands

```python
# Search for specific album
POST /api/v1/command
{
  "name": "AlbumSearch",
  "albumIds": [1]
}

# Search for all missing albums
POST /api/v1/command
{
  "name": "MissingAlbumSearch"
}

# Search for all albums by artist
POST /api/v1/command
{
  "name": "ArtistSearch",
  "artistId": 1
}
```

---

## 8. Delete Artist/Album Workflow

### Delete with Options

```
┌─────────────────────────────────────────────────────────────────┐
│                    DELETE WORKFLOW                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User wants to remove an artist or album                        │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Click Delete    │  ← From action menu or detail page         │
│  │                 │                                            │
│  └───────┬─────────┘                                            │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────┐                │
│  │            DELETE CONFIRMATION              │                │
│  │  ┌─────────────────────────────────────┐    │                │
│  │  │ Are you sure you want to delete     │    │                │
│  │  │ "Michael Jackson"?                  │    │                │
│  │  │                                     │    │                │
│  │  │ 12 albums, 147 tracks               │    │                │
│  │  │ 2.1 GB on disk                      │    │                │
│  │  │                                     │    │                │
│  │  │ ☐ Delete files from disk            │    │                │
│  │  │ ☑ Add to import exclusion list      │    │                │
│  │  │                                     │    │                │
│  │  │ ⚠ This action cannot be undone      │    │                │
│  │  └─────────────────────────────────────┘    │                │
│  │                                              │                │
│  │  [Cancel]                    [Delete]        │                │
│  └──────────────────────────────────────────────┘                │
│          │                                                      │
│          ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Execute Delete  │  → DELETE /api/v1/artist/{id}              │
│  │                 │  → Optionally delete files                 │
│  │                 │  → Add to exclusion list                   │
│  └─────────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Delete API

```python
# Delete artist
DELETE /api/v1/artist/1?deleteFiles=false&addImportListExclusion=true

# Delete album
DELETE /api/v1/album/1?deleteFiles=true

# Bulk delete
DELETE /api/v1/artist/editor
{
  "artistIds": [1, 2, 3],
  "deleteFiles": false,
  "addImportListExclusion": true
}
```

---

## Python Service Implementation

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class AddArtistOptions:
    """
    # Hey future me – these options mirror Lidarr's addOptions object.
    # The monitor field controls which albums get monitored initially.
    # The searchForMissingAlbums triggers an immediate search job.
    """
    monitor: str = "all"  # all, future, missing, existing, latest, first, none
    albums_to_monitor: list[int] = None
    search_for_missing_albums: bool = True


class ArtistService:
    """Service for artist management workflows."""

    async def add_artist(
        self,
        foreign_artist_id: str,
        root_folder_path: str,
        quality_profile_id: int,
        metadata_profile_id: int,
        monitored: bool = True,
        tags: list[int] = None,
        options: AddArtistOptions = None,
    ) -> Artist:
        """
        Add a new artist to the library.

        This is the main entry point for the Add Artist workflow.
        """
        options = options or AddArtistOptions()

        # 1. Check if artist already exists
        existing = await self.repo.get_by_foreign_id(foreign_artist_id)
        if existing:
            raise ArtistExistsError(f"Artist {foreign_artist_id} already in library")

        # 2. Fetch artist info from MusicBrainz
        mb_artist = await self.musicbrainz.get_artist(foreign_artist_id)

        # 3. Create artist record
        artist = Artist(
            foreign_artist_id=foreign_artist_id,
            artist_name=mb_artist.name,
            sort_name=mb_artist.sort_name,
            clean_name=slugify(mb_artist.name),
            artist_type=mb_artist.type,
            status=mb_artist.status,
            path=f"{root_folder_path}/{mb_artist.name}",
            root_folder_path=root_folder_path,
            quality_profile_id=quality_profile_id,
            metadata_profile_id=metadata_profile_id,
            monitored=monitored,
            overview=mb_artist.overview,
            genres=mb_artist.genres,
            images=mb_artist.images,
            tags=tags or [],
        )

        await self.repo.create(artist)

        # 4. Create artist folder
        await self.file_system.create_directory(artist.path)

        # 5. Fetch and create albums
        albums = await self._sync_albums(artist, options)

        # 6. Trigger search if requested
        if options.search_for_missing_albums:
            await self.command_service.execute(
                "MissingAlbumSearch",
                artist_id=artist.id,
            )

        return artist

    async def _sync_albums(
        self,
        artist: Artist,
        options: AddArtistOptions,
    ) -> list[Album]:
        """Sync albums from MusicBrainz and apply monitoring options."""
        mb_albums = await self.musicbrainz.get_albums(artist.foreign_artist_id)

        albums = []
        for mb_album in mb_albums:
            # Check against metadata profile
            if not self._matches_metadata_profile(mb_album, artist.metadata_profile):
                continue

            album = Album(
                artist_id=artist.id,
                foreign_album_id=mb_album.id,
                title=mb_album.title,
                release_date=mb_album.release_date,
                album_type=mb_album.type,
                monitored=self._should_monitor(mb_album, options),
                # ... other fields
            )
            albums.append(album)

        await self.album_repo.bulk_create(albums)
        return albums

    def _should_monitor(self, album, options: AddArtistOptions) -> bool:
        """Determine if album should be monitored based on options."""
        match options.monitor:
            case "all":
                return True
            case "none":
                return False
            case "future":
                return album.release_date > datetime.now()
            case "latest":
                return album.is_latest
            case "first":
                return album.is_first
            case "specific":
                return album.id in (options.albums_to_monitor or [])
            case _:
                return True
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
