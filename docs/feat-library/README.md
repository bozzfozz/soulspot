# SoulSpot Library Management

## Document Information
- **Version**: 1.1
- **Last Updated**: 2025-12-01
- **Status**: Draft
- **Reference**: [Lidarr](https://github.com/Lidarr/Lidarr) Library Management Patterns

---

## Overview

This documentation describes the Library Management system for SoulSpot, inspired by Lidarr's proven patterns for music collection management. The library system handles comprehensive organization of Artists, Albums, and Tracks with support for quality profiles, metadata management, and bulk operations.

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

---

## 📚 Documentation Index

| Document | Description |
|----------|-------------|
| **[LIDARR_INTEGRATION.md](./LIDARR_INTEGRATION.md)** | 🆕 Complete guide for Lidarr library compatibility |
| **[DATA_MODELS.md](./DATA_MODELS.md)** | Artist, Album, Track data structures and relationships |
| **[API_REFERENCE.md](./API_REFERENCE.md)** | REST API endpoints for library operations |
| **[UI_PATTERNS.md](./UI_PATTERNS.md)** | Views, filters, sorting, and UI components |
| **[ARTWORK_IMPLEMENTATION.md](./ARTWORK_IMPLEMENTATION.md)** | Artwork handling from Spotify CDN with fallbacks |
| **[QUALITY_PROFILES.md](./QUALITY_PROFILES.md)** | Audio quality tiers and upgrade system |
| **[NAMING_CONVENTIONS.md](./NAMING_CONVENTIONS.md)** | File/folder naming tokens and formats |
| **[WORKFLOWS.md](./WORKFLOWS.md)** | Key user workflows and processes |

---

## 🚀 Quick Start

### 1. Understanding the Data Model

```
Artist (1) ──────< Album (N) ──────< Track (N)
   │                  │                 │
   │                  │                 │
   └── Statistics     └── Releases      └── TrackFile
       - albumCount       - editions        - path
       - trackCount       - formats         - quality
       - sizeOnDisk       - media           - size
```

### 2. Key Entities

| Entity | Purpose | Identifier |
|--------|---------|------------|
| **Artist** | Music creator (solo/group) | MusicBrainz Artist ID |
| **Album** | Release container | MusicBrainz Release Group ID |
| **Track** | Individual song | MusicBrainz Recording ID |
| **TrackFile** | Physical audio file | Internal ID + file path |

### 3. Profile System

- **Quality Profile**: Defines acceptable audio formats (FLAC, MP3, etc.) and upgrade thresholds
- **Metadata Profile**: Controls which album types to include (Studio, EP, Single, Compilation)

---

## Feature Highlights

### Artist Management

```python
# Add artist workflow
1. Search by name or MusicBrainz ID
2. Select matching result
3. Configure:
   - Root folder path
   - Quality profile
   - Metadata profile
   - Monitoring options
4. System fetches albums and tracks from MusicBrainz
```

**Monitoring Options:**
- `None` — Don't monitor any albums
- `Specific Albums` — Choose which albums to monitor
- `All Albums` — Monitor entire discography
- `Future Albums` — Only monitor new releases

### Album Management

**Album Types:**
- Studio Album
- EP
- Single
- Compilation
- Live
- Remix
- Soundtrack
- Other

**Release Tracking:**
- Multiple releases per album (editions, remasters)
- Format tracking (CD, Vinyl, Digital)
- Country/region releases

### Quality System

```
Quality Tiers (Example):
┌─────────────────────────────────────┐
│ 1. FLAC (Lossless)      ← Cutoff   │
│ 2. ALAC (Lossless)                 │
│ 3. MP3-320                         │
│ 4. MP3-256                         │
│ 5. MP3-192                         │
└─────────────────────────────────────┘

If current file is MP3-256, system will upgrade to FLAC when available.
```

### Library Views

| View | Description | Best For |
|------|-------------|----------|
| **Table** | Detailed rows with sortable columns | Power users, bulk operations |
| **Poster** | Grid of album/artist artwork | Visual browsing |
| **Banner** | Wide banner images | Artist overview |
| **Overview** | Compact list with descriptions | Quick scanning |

### Bulk Operations

- **Select Mode**: Toggle checkboxes for multi-select
- **Bulk Edit**: Change quality profile, tags, monitoring for multiple items
- **Bulk Delete**: Remove multiple items with file deletion option
- **Album Studio**: Quick album monitoring across entire library

---

## Integration Points

### External Services

| Service | Purpose | Integration |
|---------|---------|-------------|
| **MusicBrainz** | Artist/Album/Track metadata | API lookup |
| **CoverArtArchive** | Album artwork | Image fetching |
| **slskd (Soulseek)** | Music downloads | Download management |
| **Spotify** | Playlist sync | OAuth integration |

### SoulSpot-Specific Adaptations

| Lidarr Feature | SoulSpot Equivalent | Notes |
|----------------|---------------------|-------|
| Usenet/Torrent | slskd (Soulseek) | Different download source |
| Quality Profiles | Quality Profiles | Same concept |
| SignalR | WebSocket | Real-time updates |
| C#/.NET Backend | Python/FastAPI | Different stack |
| SQLite | SQLAlchemy | Same DB concept |

---

## Directory Structure

```
docs/feat-library/
├── README.md                    # This file (Overview)
├── LIDARR_INTEGRATION.md        # 🆕 Lidarr compatibility guide
├── DATA_MODELS.md               # Entity structures
├── API_REFERENCE.md             # REST endpoints
├── UI_PATTERNS.md               # View modes and components
├── ARTWORK_IMPLEMENTATION.md    # Artwork handling
├── QUALITY_PROFILES.md          # Quality system
├── NAMING_CONVENTIONS.md        # File/folder naming
└── WORKFLOWS.md                 # User workflows
```

---

## Related Documentation

- **[feat-ui/](../feat-ui/)** — UI Design System and Components
- **[api/](../api/)** — General API Documentation
- **[features/](../features/)** — Feature Specifications

---

**Status**: 📝 Draft — Awaiting Implementation  
**Last Updated**: 2025-12-01
