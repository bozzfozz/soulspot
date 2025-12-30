# Library Management

**Category:** Features  
**Last Updated:** 2025-11-25  
**Related Docs:** [Local Library Enrichment](./local-library-enrichment.md) | [Metadata Enrichment](./metadata-enrichment.md)

---

## Overview

Library Management provides tools for maintaining and managing your music library: scans, duplicate detection, broken file repair, and album completeness checking.

---

## Features

### Library Scan

**Discovers:**
- New files added manually
- Broken/corrupt audio files
- Duplicate files (hash-based + metadata-based)

**Endpoint:** `POST /api/library/scan`

---

### Duplicate Detection

- **Hash-Based:** Identifies exactly identical files
- **Metadata-Based:** Finds different versions of same track
- **Storage Analysis:** Shows disk space wasted by duplicates

**Endpoint:** `GET /api/library/duplicates`

---

### Broken Files

- **Detection:** Finds corrupt/incomplete/unreadable files
- **Re-Download:** Automatically re-download broken files
- **Status Tracking:** Monitor repair progress

**Endpoint:** `GET /api/library/broken-files`

---

### Album Completeness

- **Spotify Comparison:** Compare local albums with Spotify data
- **Missing Tracks:** Show which tracks missing from album
- **Bulk Download:** Download missing tracks in one step

**Endpoint:** `GET /api/library/albums/incomplete`

---

### Spotify Enrichment

After each scan, automatically enrich local files with Spotify metadata:

- **Automatic Matching:** Find Spotify URIs for local artists/albums
- **Artwork Download:** Fetch album covers + artist images
- **Genre Enrichment:** Add Spotify genres
- **Album Types:** Detect compilations, EPs, singles, live albums

**Enable:** Settings → Library → Auto-Enrich Local Library

**See:** [Local Library Enrichment](./local-library-enrichment.md)

---

### Statistics

- **Library Size:** Total size of all files
- **Track Count:** Number of tracks in database
- **Scan Status:** Scan progress percentage

---

## Usage (Web UI)

### Scan Library

1. Navigate to **Library** → **Scan**
2. Select path to scan
3. Click **Start Scan**
4. Monitor real-time progress
5. Review results after completion

---

### Clean Duplicates

1. Navigate to **Library** → **Duplicates**
2. Review duplicate groups
3. Select which copy to keep
4. Mark duplicates as "resolved"

---

### Repair Broken Files

1. Navigate to **Library** → **Broken Files**
2. Review broken file list
3. Click **Re-Download All** or select individual files
4. Download starts automatically

---

### Check Album Completeness

1. Navigate to **Library** → **Albums**
2. Filter by "Incomplete"
3. Click album for details
4. Start download of missing tracks

---

## API Endpoints

### POST `/api/library/scan`

Start library scan.

**Request:**
```json
{
  "scan_path": "/music/library"
}
```

**Response:**
```json
{
  "scan_id": "scan-uuid",
  "status": "running",
  "scan_path": "/music/library",
  "total_files": 0,
  "message": "Library scan started"
}
```

---

### GET `/api/library/scan/{scan_id}`

Get scan status.

**Response:**
```json
{
  "scan_id": "scan-uuid",
  "status": "running",
  "scan_path": "/music/library",
  "total_files": 1500,
  "scanned_files": 750,
  "broken_files": 5,
  "duplicate_files": 12,
  "progress_percent": 50.0
}
```

**Status Values:**
- `running` - Scan in progress
- `completed` - Scan finished
- `failed` - Scan failed

---

### GET `/api/library/duplicates`

Get all duplicate groups.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resolved` | bool | null | Filter by resolved status |

---

### GET `/api/library/broken-files`

Get list of broken files.

---

### POST `/api/library/broken-files/{file_id}/re-download`

Re-download single broken file.

---

### POST `/api/library/broken-files/re-download-all`

Re-download all broken files.

---

### GET `/api/library/albums/incomplete`

Get albums missing tracks.

---

### GET `/api/library/stats`

Get library statistics.

**Response:**
```json
{
  "total_tracks": 15000,
  "total_size_bytes": 52428800000,
  "broken_files": 5,
  "duplicate_files": 12,
  "incomplete_albums": 8
}
```

---

## Related Documentation

- **[Local Library Enrichment](./local-library-enrichment.md)** - Metadata enrichment
- **[Metadata Enrichment](./metadata-enrichment.md)** - Enrichment strategies
- **[Download Management](./download-management.md)** - Re-download broken files

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
