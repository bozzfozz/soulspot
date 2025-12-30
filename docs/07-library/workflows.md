# Library Workflows

**Category:** Library Management  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Data Models](./data-models.md), [API Reference](./api-reference.md), [UI Patterns](./ui-patterns.md)

---

## Overview

Key workflows for managing a music library in SoulSpot. Each workflow includes user interactions, system processes, and API calls.

## 1. Add Artist Workflow

### User Flow

```
1. User clicks "Add Artist"
2. Search dialog appears (MusicBrainz search)
3. User types artist name
4. Select artist from search results
5. Configure options:
   - Root folder (e.g., /music)
   - Quality profile (e.g., Lossless)
   - Metadata profile (Standard)
   - Monitor option (All Albums, Future, Missing, etc.)
   - Tags (optional)
   - ☑ Search for missing albums
6. Click "Add Artist"
7. System creates artist in database
8. System fetches albums from MusicBrainz
9. System creates artist folder on disk
10. System applies monitoring settings
11. Optional: Trigger search for missing albums
```

### Monitor Options

| Option | Description | Albums Monitored |
|--------|-------------|------------------|
| **All Albums** | Monitor all current and future | All existing + new releases |
| **Future Albums** | Only new releases | None existing, all new |
| **Missing Albums** | Albums without files | Only incomplete |
| **Existing Albums** | Albums with some files | Only with files |
| **Latest Album** | Most recent release only | 1 album |
| **First Album** | Debut album only | 1 album |
| **None** | No automatic monitoring | None |

### API Sequence

```http
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
  "addOptions": {
    "monitor": "all",
    "searchForMissingAlbums": true
  }
}

# 3. System fetches albums from MusicBrainz
# 4. System applies monitoring based on addOptions.monitor
# 5. System triggers search if searchForMissingAlbums=true
```

## 2. Library Import Workflow

### Manual Import Flow

```
1. User has existing music files in folder (e.g., /downloads/music)
2. Click "Manual Import" button
3. Select folder to import
4. System scans folder for audio files
5. System analyzes each file:
   - Read metadata tags (ID3, FLAC, etc.)
   - Calculate file hash
   - Detect quality (format, bitrate)
6. System attempts to match files to library:
   - Match by MusicBrainz Recording ID (if present in tags)
   - Match by artist + album + track title
   - Fuzzy matching for close matches
7. User reviews import preview:
   - ✅ Green: Confident match
   - ⚠️ Yellow: Possible match (manual review)
   - ❌ Red: No match (skip or manual assignment)
8. User confirms import
9. System moves/copies files to library folders
10. System updates database with TrackFile records
11. Optional: System enriches metadata from MusicBrainz
```

### Import Matching Strategy

```python
# Priority order for matching:
1. MusicBrainz Recording ID (in file tags) → Exact match
2. Artist + Album + Track Title → Fuzzy match (>85% confidence)
3. ISRC (International Standard Recording Code) → Exact match
4. Fingerprinting (AcoustID) → Audio analysis match

# Match confidence levels:
- 100%: MusicBrainz ID or ISRC exact match
- 85-99%: Fuzzy text match with high similarity
- 70-84%: Possible match (requires manual review)
- <70%: No match (skip or manual assignment)
```

## 3. Album Monitoring Workflow

### Enable Monitoring

```
1. Navigate to artist or album view
2. Click monitoring toggle (☐ → ☑)
3. System marks album as monitored
4. Background worker checks for missing tracks
5. If missing tracks found:
   - System searches for downloads
   - Downloads are queued automatically
6. Monitoring status saved to database
```

### Bulk Monitoring (Album Studio)

```
1. Click "Album Studio" view
2. Grid displays all albums with monitoring checkboxes
3. Select multiple albums via checkboxes
4. Click "Monitor Selected" or "Unmonitor Selected"
5. System bulk updates monitored status
6. Background worker processes changes
```

## 4. Quality Upgrade Workflow

### Automatic Upgrade

```
1. New download becomes available (e.g., FLAC version of MP3-320 track)
2. System compares qualities:
   - Current file: MP3-320 (quality weight: 4)
   - New file: FLAC (quality weight: 6)
3. System checks quality profile:
   - upgrade_allowed: true
   - cutoff: 6 (FLAC)
4. New file meets cutoff → Trigger download
5. Download completes
6. System replaces old file with new file
7. Old file moved to recycle bin or deleted
8. Database updated with new TrackFile
```

### Quality Profile Check

```python
# Example quality profile evaluation:
profile = {
    "name": "Balanced",
    "upgrade_allowed": True,
    "cutoff": 6,  # FLAC quality tier
    "items": [
        {"quality_id": 6, "allowed": True},   # FLAC
        {"quality_id": 4, "allowed": True},   # MP3-320
        {"quality_id": 3, "allowed": True},   # MP3-256
        {"quality_id": 2, "allowed": False},  # MP3-192
    ]
}

# Check if download allowed:
is_allowed = profile.is_quality_allowed(new_quality_id=6)  # True

# Check if upgrade needed:
needs_upgrade = profile.get_quality_weight(6) > profile.get_quality_weight(4)  # True

# Check if cutoff met:
cutoff_met = profile.is_cutoff_met(current_quality_id=6)  # True (stop upgrading)
```

## 5. Library Organization Workflow

### Rename Files

```
1. Select tracks/albums/artists
2. Click "Organize" → "Rename Files"
3. System previews changes:
   - Old: /music/michael jackson/bad/01 - bad.mp3
   - New: /music/Michael Jackson/Bad (1987)/01 - Bad.mp3
4. User reviews and confirms
5. System renames files using naming templates
6. Database paths updated
7. Verification scan confirms all files accessible
```

### Naming Template Example

```
# Album folder template:
{Artist Name}/{Album Title} ({Release Year})

# Track file template:
{Track Number:00} - {Track Title}

# Multi-disc template:
{Medium:00}-{Track Number:00} - {Track Title}

# Result examples:
/music/Michael Jackson/Thriller (1982)/01 - Wanna Be Startin' Somethin'.flac
/music/Pink Floyd/The Wall (1979)/01-01 - In the Flesh.flac
```

## 6. Missing Track Detection Workflow

### Album Completeness Check

```
1. User views album details
2. System compares:
   - Expected tracks (from MusicBrainz): 12 tracks
   - Actual files: 10 tracks
3. System identifies missing tracks:
   - Track 5: "Human Nature"
   - Track 7: "P.Y.T."
4. UI displays missing tracks with ⚠️ warning
5. User can:
   - Search for missing tracks manually
   - Enable monitoring to auto-download
   - Mark as "not wanted" (skip)
```

### Gap Analysis

```
Expected: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
Actual:   [1, 2, 3, 4,    6,    8, 9, 10, 11, 12]
Missing:  [           5,       7                  ]

# Display in UI:
✅ Track 1-4: Complete
⚠️ Track 5: Missing
✅ Track 6: Complete
⚠️ Track 7: Missing
✅ Track 8-12: Complete
```

## Integration Points

### External Services

| Service | Workflow Usage |
|---------|----------------|
| **MusicBrainz** | Artist/album/track metadata, search, matching |
| **Spotify** | Alternative metadata source, artwork |
| **Soulseek (slskd)** | Download missing tracks |
| **Last.fm** | Tag enrichment, play counts |

### Background Workers

| Worker | Workflow Trigger |
|--------|------------------|
| **Library Scanner** | Detects new/changed files on disk |
| **Metadata Enricher** | Updates artist/album info from MusicBrainz |
| **Missing Track Checker** | Finds incomplete albums |
| **Quality Upgrader** | Searches for better quality versions |

## Related Documentation

- [Data Models](./data-models.md) - Entity structures
- [API Reference](./api-reference.md) - REST endpoints
- [UI Patterns](./ui-patterns.md) - User interface components
- [Quality Profiles](./quality-profiles.md) - Quality management system
