# Library Data Models

**Category:** Library Management  
**Status:** ✅ Active  
**Last Updated:** 2025-12-30  
**Related:** [Data Standards](../02-architecture/data-standards.md), [Data Layer Patterns](../02-architecture/data-layer-patterns.md), [API Reference](./api-reference.md)

---

## Overview

Core data models for SoulSpot's library management system, inspired by Lidarr's architecture and adapted for Python/SQLAlchemy. The library uses a hierarchical structure: **Artist → Album → Track → TrackFile**.

## Entity Relationship

```
Artist (1) ──────< Album (N) ──────< Track (N) ──────< TrackFile (1)
   │                  │                 │
   │                  │                 └── physical audio file
   │                  └── release container (with editions/formats)
   └── music creator (solo/group)

Key Relationships:
- Artist has many Albums (cascade delete)
- Album belongs to one Artist
- Album has many Tracks (cascade delete)
- Track belongs to one Album
- Track has optional TrackFile (physical file mapping)
```

## Core Models

### Artist Model

Primary entity representing a music creator (solo artist or group).

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key (auto-increment) |
| `foreign_artist_id` | String(36) | **MusicBrainz Artist ID** (UUID, unique, indexed) |
| `artist_name` | String(255) | Display name |
| `sort_name` | String(255) | Alphabetical sorting (e.g., "Jackson, Michael") |
| `clean_name` | String(255) | URL-safe name |
| `artist_type` | String(50) | Person, Group, Orchestra, Choir, Character, Other |
| `status` | String(20) | "continuing" or "ended" |
| `monitored` | Boolean | Enable automatic monitoring |
| `monitor_new_items` | String(10) | "all", "none", "new" |
| `path` | String(512) | File system folder path |
| `quality_profile_id` | Integer | FK to quality_profiles |
| `metadata_profile_id` | Integer | FK to metadata_profiles |
| `genres` | JSON | Array of genre strings |
| `images` | JSON | Array of image objects `[{type, url}, ...]` |
| `ratings` | JSON | `{value: 4.5, votes: 1000}` |
| `added` | DateTime | When added to library |

**Relationships:**
- `albums` → One-to-Many with Album (cascade delete)
- `quality_profile` → Many-to-One with QualityProfile
- `metadata_profile` → Many-to-One with MetadataProfile

**Python Model Pattern:**

```python
class Artist(Base):
    __tablename__ = "artists"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    foreign_artist_id = Column(String(36), unique=True, nullable=False, index=True)
    artist_name = Column(String(255), nullable=False)
    sort_name = Column(String(255), nullable=False, index=True)
    monitored = Column(Boolean, default=True)
    path = Column(String(512), nullable=True)
    quality_profile_id = Column(Integer, ForeignKey("quality_profiles.id"))
    genres = Column(JSON, default=list)
    
    # Relationships
    albums = relationship("Album", back_populates="artist", cascade="all, delete-orphan")
    quality_profile = relationship("QualityProfile")
```

### Album Model

Release container for tracks with support for multiple editions/formats.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `artist_id` | Integer | FK to artists (required) |
| `foreign_album_id` | String(36) | **MusicBrainz Release Group ID** |
| `title` | String(255) | Album title |
| `clean_title` | String(255) | Normalized title for matching |
| `album_type` | String(50) | Studio, EP, Single, Compilation, Live, Remix, etc. |
| `release_date` | Date | Original release date |
| `monitored` | Boolean | Enable automatic downloads |
| `overview` | Text | Album description/review |
| `genres` | JSON | Genre array (inherited from artist) |
| `images` | JSON | Cover art images |
| `releases` | JSON | Array of release editions `[{mbId, country, format}, ...]` |

**Relationships:**
- `artist` → Many-to-One with Artist
- `tracks` → One-to-Many with Track (cascade delete)

### Track Model

Individual song with optional file mapping.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `album_id` | Integer | FK to albums (required) |
| `foreign_recording_id` | String(36) | **MusicBrainz Recording ID** |
| `title` | String(255) | Track title |
| `track_number` | Integer | Position in album |
| `medium_number` | Integer | Disc number (for multi-disc albums) |
| `duration` | Integer | Length in seconds |
| `explicit` | Boolean | Parental advisory flag |
| `has_file` | Boolean | Whether physical file exists |
| `track_file_id` | Integer | FK to track_files (nullable) |

**Relationships:**
- `album` → Many-to-One with Album
- `track_file` → One-to-One with TrackFile (optional)

### TrackFile Model

Physical audio file on disk with quality and media info.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `track_id` | Integer | FK to tracks |
| `path` | String(512) | Absolute file path |
| `size` | BigInteger | File size in bytes |
| `quality` | JSON | `{format: "FLAC", bitrate: 1411, sampleRate: 44100}` |
| `media_info` | JSON | Codec details, channels, etc. |
| `date_added` | DateTime | Import timestamp |

## Identifiers

**Critical:** Always use MusicBrainz IDs for external lookups, NOT internal database IDs.

| Entity | Internal ID | External ID (MusicBrainz) |
|--------|-------------|---------------------------|
| Artist | `id` (auto-increment) | `foreign_artist_id` (UUID) |
| Album | `id` (auto-increment) | `foreign_album_id` (UUID) |
| Track | `id` (auto-increment) | `foreign_recording_id` (UUID) |

**Example:**
```python
# ❌ WRONG: Using internal ID for MusicBrainz lookup
mb_artist = musicbrainz.get_artist(artist.id)  # Internal ID won't work!

# ✅ RIGHT: Using foreign ID for external lookups
mb_artist = musicbrainz.get_artist(artist.foreign_artist_id)  # MusicBrainz UUID
```

## Statistics Pattern

Artists and Albums have computed statistics stored in JSON or via `@property`.

**Artist Statistics:**
```python
@property
def statistics(self) -> dict:
    return {
        "albumCount": len(self.albums),
        "trackCount": sum(len(a.tracks) for a in self.albums),
        "trackFileCount": sum(1 for a in self.albums for t in a.tracks if t.has_file),
        "sizeOnDisk": sum(t.track_file.size for a in self.albums for t in a.tracks if t.track_file)
    }
```

## Related Documentation

- [Library Workflows](./workflows.md) - Common library operations
- [API Reference](./api-reference.md) - REST endpoints for models
- [Lidarr Integration](./lidarr-integration.md) - Compatibility guide
- [Data Layer Patterns](../02-architecture/data-layer-patterns.md) - Repository patterns
