# Library Management Documentation

**Category:** Library Management  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Features](../06-features/README.md), [API Reference](../01-api-reference/README.md), [Architecture](../02-architecture/README.md)

---

## Overview

Complete documentation for SoulSpot's Library Management system, inspired by Lidarr's proven patterns for music collection management. The library system handles comprehensive organization of Artists, Albums, and Tracks with support for quality profiles, metadata management, and bulk operations.

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Artist Management** | Add, edit, delete, monitor artists with MusicBrainz integration |
| **Album Management** | Track releases, editions, formats with monitoring controls |
| **Track Management** | Individual track handling with file mapping and metadata |
| **Quality Profiles** | Define preferred audio quality tiers and upgrade logic |
| **Organization** | Folder structure and file naming conventions |
| **Bulk Operations** | Mass edit, delete, organize across library |
| **Import/Export** | Manual import with preview, library export |

## 📚 Documentation Index

### Core Documentation

| Document | Description |
|----------|-------------|
| **[Data Models](./data-models.md)** | Artist, Album, Track, TrackFile entities and relationships |
| **[Workflows](./workflows.md)** | Key user workflows (add artist, import, monitoring, organization) |
| **[UI Patterns](./ui-patterns.md)** | Views, filters, sorting, bulk operations patterns |
| **[API Reference](./api-reference.md)** | REST endpoints for library operations |

### Integration & Configuration

| Document | Description |
|----------|-------------|
| **[Lidarr Integration](./lidarr-integration.md)** | Compatibility guide for existing Lidarr libraries |
| **[Quality Profiles](./quality-profiles.md)** | Audio quality tiers and upgrade system |
| **[Naming Conventions](./naming-conventions.md)** | File/folder naming tokens and formats |
| **[Artwork Implementation](./artwork-implementation.md)** | Spotify CDN artwork with fallback chain |

## 🚀 Quick Start

### Understanding the Data Model

```
Artist (1) ──────< Album (N) ──────< Track (N) ──────< TrackFile (1)
   │                  │                 │                   │
   │                  │                 │                   └── physical file
   │                  │                 └── individual song
   │                  └── release container
   └── music creator

Key Relationships:
- One Artist has many Albums (cascade delete)
- One Album belongs to one Artist
- One Album has many Tracks (cascade delete)
- One Track belongs to one Album
- One Track has optional TrackFile (physical file mapping)
```

### Key Entities

| Entity | Purpose | Identifier |
|--------|---------|------------|
| **Artist** | Music creator (solo/group) | MusicBrainz Artist ID (UUID) |
| **Album** | Release container | MusicBrainz Release Group ID (UUID) |
| **Track** | Individual song | MusicBrainz Recording ID (UUID) |
| **TrackFile** | Physical audio file | Internal ID + file path |

**⚠️ CRITICAL:** Always use MusicBrainz IDs (`foreign_artist_id`, `foreign_album_id`, `foreign_recording_id`) for external lookups, NOT internal database IDs.

### Profile System

| Profile Type | Purpose |
|--------------|---------|
| **Quality Profile** | Defines acceptable audio formats (FLAC, MP3, etc.) and upgrade thresholds |
| **Metadata Profile** | Controls which album types to include (Studio, EP, Single, Compilation) |

**Example Quality Profile:**

```
Audiophile Profile:
┌─────────────────────────────────────┐
│ Cutoff: FLAC (quality weight: 6)   │
├─────────────────────────────────────┤
│ ✅ FLAC (weight: 6)                 │
│ ✅ ALAC (weight: 5)                 │
│ ❌ MP3-320 (weight: 4) - rejected   │
│ ❌ MP3-256 (weight: 3) - rejected   │
└─────────────────────────────────────┘

Result: Only downloads FLAC/ALAC, upgrades MP3s automatically
```

## Common Workflows

### 1. Add Artist

```
User → Search MusicBrainz → Select Artist → Configure Options → Add
                                                   ↓
                              Root Folder: /music
                              Quality Profile: Lossless
                              Monitor: All Albums
                              Tags: [Classical]
                                                   ↓
System → Fetch Albums → Create Folder → Apply Monitoring → Search Missing
```

**See:** [Workflows - Add Artist](./workflows.md#1-add-artist-workflow)

### 2. Import Existing Library

```
User → Manual Import → Select Folder → System Scans
                                           ↓
                          Analyze Files (metadata, quality, hash)
                                           ↓
                          Match to Library (MusicBrainz ID, fuzzy match)
                                           ↓
User → Review Matches → Confirm → System Moves Files → Update Database
```

**See:** [Workflows - Library Import](./workflows.md#2-library-import-workflow)

### 3. Monitor Albums for Auto-Downloads

```
User → Enable Monitoring (☐ → ☑)
         ↓
System → Check Missing Tracks → Search for Downloads → Queue Automatically
```

**See:** [Workflows - Album Monitoring](./workflows.md#3-album-monitoring-workflow)

### 4. Quality Upgrades

```
New Download Available (FLAC) → System Compares Qualities → Check Profile
                                      ↓                           ↓
                         Current: MP3-320 (weight: 4)   Cutoff: FLAC (weight: 6)
                                      ↓
                         Upgrade Allowed? YES → Download → Replace File
```

**See:** [Workflows - Quality Upgrade](./workflows.md#4-quality-upgrade-workflow)

## Library Views

| View | Description | Best For |
|------|-------------|----------|
| **Table** | Detailed rows with sortable columns | Power users, bulk operations |
| **Poster** | Grid of album/artist artwork | Visual browsing, discovery |
| **Banner** | Wide banner images | Artist overview, featured artists |
| **Overview** | Compact list with descriptions | Quick scanning, mobile |

**See:** [UI Patterns - View Modes](./ui-patterns.md#view-modes)

## Integration Points

### External Services

| Service | Purpose | Used In |
|---------|---------|---------|
| **MusicBrainz** | Metadata (artist/album/track), search, matching | Add Artist, Import, Enrichment |
| **Spotify** | Alternative metadata, artwork URLs | Artwork fallback, metadata enrichment |
| **Soulseek (slskd)** | Download missing tracks | Auto-downloads, manual search |
| **Last.fm** | Tag enrichment, play counts | Metadata enrichment |

### Background Workers

| Worker | Trigger | Function |
|--------|---------|----------|
| **Library Scanner** | Scheduled/manual | Detects new/changed files on disk |
| **Metadata Enricher** | Scheduled/manual | Updates artist/album info from MusicBrainz |
| **Missing Track Checker** | Album monitoring enabled | Finds incomplete albums |
| **Quality Upgrader** | New downloads available | Searches for better quality versions |

## API Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/artist` | GET | List all artists with filtering/sorting |
| `/api/v1/artist/{id}` | GET/PUT/DELETE | Get/update/delete artist |
| `/api/v1/artist` | POST | Add new artist |
| `/api/v1/album` | GET | List albums with filtering |
| `/api/v1/album/{id}` | GET/PUT | Get/update album |
| `/api/v1/track` | GET | List tracks |
| `/api/v1/trackfile/{id}` | GET/DELETE | Get/delete track file |
| `/api/v1/library/stats` | GET | Library statistics |

**See:** [API Reference](./api-reference.md) for complete endpoint documentation

## File Organization

### Folder Structure

```
/music/
  ├── Artist Name/
  │   ├── Album Title (Release Year)/
  │   │   ├── 01 - Track Title.flac
  │   │   ├── 02 - Track Title.flac
  │   │   └── cover.jpg
  │   └── Album Title 2 (Year)/
  └── Artist Name 2/
```

### Naming Templates

**Album Folder:**
```
{Artist Name}/{Album Title} ({Release Year})

Example: Michael Jackson/Thriller (1982)
```

**Track Files:**
```
Standard: {Track Number:00} - {Track Title}
Multi-Disc: {Medium:00}-{Track Number:00} - {Track Title}
Various Artists: {Track Number:00} - {Artist Name} - {Track Title}

Examples:
01 - Wanna Be Startin' Somethin'.flac
01-01 - In the Flesh.flac  (Disc 1, Track 1)
03 - Queen - Bohemian Rhapsody.flac  (Various Artists)
```

**See:** [Naming Conventions](./naming-conventions.md) for complete token reference

## Lidarr Compatibility

SoulSpot is designed to be compatible with existing Lidarr libraries:

| Feature | Lidarr Compatibility |
|---------|---------------------|
| **Folder Structure** | ✅ Identical hierarchy |
| **Naming Tokens** | ✅ Same token system |
| **Multi-Disc Handling** | ✅ Prefix style (01-01) or subfolder style |
| **MusicBrainz IDs** | ✅ Required for matching |
| **Quality Profiles** | ✅ Borrowed Lidarr system |
| **cover.jpg** | ✅ Standard album artwork file |

**See:** [Lidarr Integration](./lidarr-integration.md) for compatibility checklist

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Artist not found in MusicBrainz** | Search by MBID directly, check spelling variations |
| **Import matching fails** | Ensure files have proper ID3 tags, use MusicBrainz Picard |
| **Quality upgrades not triggering** | Check quality profile allows upgrades, verify cutoff setting |
| **Files not moving during import** | Verify folder permissions, check disk space |
| **Album completeness incorrect** | Refresh album from MusicBrainz, check for deluxe editions |

## Related Documentation

- [Features Overview](../06-features/README.md) - All SoulSpot features
- [API Reference](../01-api-reference/README.md) - Complete API documentation
- [Architecture](../02-architecture/README.md) - System design patterns
- [User Guide](../04-user-guides/user-guide.md) - Getting started guide
