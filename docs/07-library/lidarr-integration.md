# Lidarr Integration Guide

**Category:** Library Management  
**Status:** ✅ Complete  
**Last Updated:** 2025-12-01  
**Related Docs:** [Naming Conventions](./naming-conventions.md) | [Quality Profiles](./quality-profiles.md)

---

## Overview

Comprehensive guidance for integrating SoulSpot with existing Lidarr-managed music libraries. Covers folder structures, naming conventions, metadata handling, and configuration settings for seamless compatibility.

---

## Why Lidarr Compatibility Matters

- **Preserve Existing Structure** — Users with Lidarr libraries shouldn't reorganize
- **Media Server Compatibility** — Plex, Jellyfin, Emby, Navidrome expect consistent structures
- **Metadata Integrity** — MusicBrainz IDs enable reliable matching and enrichment
- **Quality Management** — Standardized quality profiles ensure consistent audio quality

---

## Lidarr Folder Structure

### Hierarchy Overview

```
/music                              ← Root Folder
└── {Artist Name}                   ← Artist Folder
    └── {Album Title} ({Release Year})  ← Album Folder
        ├── 01 - {Track Title}.flac     ← Track Files
        ├── 02 - {Track Title}.flac
        ├── cover.jpg                    ← Album Artwork (optional)
        └── ...
```

---

### Real-World Example

```
/music
├── Michael Jackson
│   ├── Off the Wall (1979)
│   │   ├── 01 - Don't Stop 'til You Get Enough.flac
│   │   ├── 02 - Rock with You.flac
│   │   └── cover.jpg
│   ├── Thriller (1982)
│   │   ├── 01 - Wanna Be Startin' Somethin'.flac
│   │   ├── 02 - Baby Be Mine.flac
│   │   └── ...
│   └── Bad (1987)
│       └── ...
├── The Beatles
│   ├── Abbey Road (1969)
│   │   └── ...
│   └── The White Album (1968)      ← Multi-Disc Example
│       ├── 01-01 - Back in the U.S.S.R..flac
│       ├── 01-02 - Dear Prudence.flac
│       ├── 02-01 - Birthday.flac
│       └── ...
└── Various Artists
    └── Now That's What I Call Music! 1 (1983)
        ├── 01 - Phil Collins - You Can't Hurry Love.flac
        ├── 02 - Culture Club - Karma Chameleon.flac
        └── ...
```

---

## Naming Conventions

### Standard Formats

**Artist Folder:**
```
{Artist Name}
Example: Michael Jackson
```

**Album Folder:**
```
{Album Title} ({Release Year})
Example: Thriller (1982)
```

**Track Naming:**
```
Standard: {track:00} - {Track Title}
Example: 05 - Billie Jean.flac

Multi-Disc: {medium:00}-{track:00} - {Track Title}
Example: 02-05 - Birthday.flac

Various Artists: {track:00} - {Artist Name} - {Track Title}
Example: 01 - Phil Collins - You Can't Hurry Love.flac
```

---

## Multi-Disc Albums

### Prefix Style (Recommended)

Track numbers include disc prefix:

```
/music/The Beatles/The White Album (1968)/
├── 01-01 - Back in the U.S.S.R..flac
├── 01-02 - Dear Prudence.flac
├── 02-01 - Birthday.flac
└── 02-02 - Yer Blues.flac
```

**Format String:**
```
{medium:00}-{track:00} - {Track Title}
```

---

### Subfolder Style

Each disc in separate folder:

```
/music/The Beatles/The White Album (1968)/
├── Disc 1/
│   ├── 01 - Back in the U.S.S.R..flac
│   └── ...
└── Disc 2/
    ├── 01 - Birthday.flac
    └── ...
```

**Format String:**
```
Disc {medium:0}/{track:00} - {Track Title}
```

---

## Metadata Requirements

### MusicBrainz IDs

Critical for accurate matching:

- **Artist MBID** — Links to MusicBrainz artist
- **Release Group MBID** — Album identifier
- **Release MBID** — Specific edition
- **Recording MBID** — Track identifier

**Database Fields:**
```python
class ArtistModel:
    musicbrainz_id: str | None  # Artist MBID

class AlbumModel:
    musicbrainz_id: str | None  # Release Group MBID

class TrackModel:
    musicbrainz_id: str | None  # Recording MBID
```

---

## Quality Profiles

See: [Quality Profiles](./quality-profiles.md) for full details.

**Example Profile:**
```yaml
name: "Audiophile"
allowed: [FLAC, ALAC, WAV, 320kbps]
cutoff: FLAC
upgrade_allowed: true
```

---

## Configuration Sync

### SoulSpot Settings

```bash
# Lidarr-compatible paths
SOULSPOT_MUSIC_PATH=/music
NAMING_FOLDER_TEMPLATE="{albumartist}/{album}"
NAMING_FILE_TEMPLATE="{tracknumber} - {title}"

# Multi-disc handling
NAMING_FILE_TEMPLATE_MULTICD="{discnumber}-{tracknumber} - {title}"
```

---

## Compatibility Checklist

- [ ] Folder structure matches Lidarr hierarchy
- [ ] Artist/Album naming uses Lidarr format
- [ ] Track files include disc prefix for multi-disc
- [ ] MusicBrainz IDs stored for all entities
- [ ] Quality profiles match Lidarr definitions
- [ ] cover.jpg artwork in album folders

---

## Related Documentation

- **[Naming Conventions](./naming-conventions.md)** - Full token reference
- **[Quality Profiles](./quality-profiles.md)** - Quality management
- **[Artwork Implementation](./artwork-implementation.md)** - Artwork handling

---

**Last Validated:** 2025-12-01  
**Implementation Status:** ✅ Production-ready
