# Library Data Models

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr](https://github.com/Lidarr/Lidarr) Data Models

---

## Overview

This document defines the core data models for SoulSpot's library management system. Models are inspired by Lidarr's architecture and adapted for Python/SQLAlchemy.

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Artist      │       │      Album      │       │      Track      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │──┐    │ id              │──┐    │ id              │
│ foreign_id (MB) │  │    │ artist_id    ───┼──┘    │ album_id     ───┼──┐
│ name            │  │    │ foreign_id (MB) │       │ foreign_id (MB) │  │
│ sort_name       │  │    │ title           │       │ title           │  │
│ artist_type     │  │    │ album_type      │       │ track_number    │  │
│ status          │  └───>│ release_date    │       │ duration        │  │
│ monitored       │       │ monitored       │       │ explicit        │  │
│ path            │       │ overview        │       │ has_file        │  │
│ quality_profile │       │ genres[]        │       │ track_file_id ──┼──┼──┐
│ metadata_profile│       │ images[]        │       └─────────────────┘  │  │
│ overview        │       │ releases[]      │                            │  │
│ genres[]        │       │ statistics      │<───────────────────────────┘  │
│ images[]        │       └─────────────────┘                               │
│ tags[]          │                                                         │
│ statistics      │       ┌─────────────────┐                               │
└─────────────────┘       │    TrackFile    │<──────────────────────────────┘
                          ├─────────────────┤
                          │ id              │
                          │ track_id        │
                          │ path            │
                          │ size            │
                          │ quality         │
                          │ date_added      │
                          │ media_info      │
                          └─────────────────┘
```

---

## Core Models

### Artist

The primary entity representing a music creator (solo artist or group).

#### TypeScript Interface (Lidarr Reference)

```typescript
interface Artist {
  id: number;
  foreignArtistId: string;        // MusicBrainz Artist ID
  artistName: string;
  sortName: string;               // For alphabetical sorting
  cleanName: string;              // URL-safe name
  artistType?: string;            // "Person", "Group", "Orchestra", etc.
  status: ArtistStatus;           // "continuing", "ended"
  monitored: boolean;
  monitorNewItems: MonitorNewItems; // "all", "none", "new"
  path: string;                   // File system path
  rootFolderPath: string;
  qualityProfileId: number;
  metadataProfileId: number;
  overview?: string;              // Biography/description
  disambiguation?: string;        // To distinguish similar names
  genres: string[];
  images: Image[];                // Poster, Banner, Fanart
  links: Link[];                  // External links (website, social)
  ratings: Ratings;
  tags: number[];
  added: string;                  // ISO date when added to library
  ended?: boolean;
  statistics: ArtistStatistics;
  nextAlbum?: Album;
  lastAlbum?: Album;
}

type ArtistStatus = "continuing" | "ended";
type MonitorNewItems = "all" | "none" | "new";
```

#### Python Model (SoulSpot)

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Artist(Base):
    """
    # Hey future me – this is the main artist entity. MusicBrainz ID is the
    # foreign_artist_id, NOT our internal id. Don't confuse them when doing
    # API lookups. The path is the actual folder on disk, root_folder_path
    # is the parent container (e.g., /music/).
    """
    __tablename__ = "artists"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    foreign_artist_id = Column(String(36), unique=True, nullable=False, index=True)  # MusicBrainz UUID
    
    # Names
    artist_name = Column(String(255), nullable=False)
    sort_name = Column(String(255), nullable=False, index=True)
    clean_name = Column(String(255), nullable=False)  # URL-safe
    disambiguation = Column(String(255), nullable=True)
    
    # Classification
    artist_type = Column(String(50), nullable=True)  # Person, Group, Orchestra, Choir, Character, Other
    status = Column(String(20), default="continuing")  # continuing, ended
    
    # Monitoring
    monitored = Column(Boolean, default=True)
    monitor_new_items = Column(String(10), default="all")  # all, none, new
    
    # Paths
    path = Column(String(512), nullable=True)
    root_folder_path = Column(String(512), nullable=True)
    
    # Profiles
    quality_profile_id = Column(Integer, ForeignKey("quality_profiles.id"), nullable=True)
    metadata_profile_id = Column(Integer, ForeignKey("metadata_profiles.id"), nullable=True)
    
    # Metadata
    overview = Column(Text, nullable=True)
    genres = Column(JSON, default=list)
    images = Column(JSON, default=list)  # [{type: "poster", url: "..."}, ...]
    links = Column(JSON, default=list)   # [{type: "website", url: "..."}, ...]
    ratings = Column(JSON, default=dict) # {value: 4.5, votes: 1000}
    tags = Column(JSON, default=list)    # [1, 2, 3] tag IDs
    
    # Timestamps
    added = Column(DateTime, default=datetime.utcnow)
    ended = Column(Boolean, default=False)
    
    # Relationships
    albums = relationship("Album", back_populates="artist", cascade="all, delete-orphan")
    quality_profile = relationship("QualityProfile")
    metadata_profile = relationship("MetadataProfile")
    
    @property
    def statistics(self) -> dict:
        """
        # Computed statistics – don't cache this, recalculate on demand or
        # use a separate stats table if performance becomes an issue.
        """
        return {
            "album_count": len(self.albums),
            "track_count": sum(len(a.tracks) for a in self.albums),
            "track_file_count": sum(1 for a in self.albums for t in a.tracks if t.has_file),
            "size_on_disk": sum(t.track_file.size for a in self.albums for t in a.tracks if t.track_file),
        }
```

---

### Album

Represents a music release (album, EP, single, etc.).

#### TypeScript Interface (Lidarr Reference)

```typescript
interface Album {
  id: number;
  artistId: number;
  foreignAlbumId: string;         // MusicBrainz Release Group ID
  title: string;
  overview?: string;
  disambiguation?: string;
  albumType: AlbumType;
  secondaryTypes: string[];       // ["Compilation", "Live", etc.]
  monitored: boolean;
  anyReleaseOk: boolean;          // Accept any release edition
  releaseDate?: string;
  genres: string[];
  media: Medium[];                // CD, Vinyl, Digital, etc.
  images: MediaCover[];
  links: Link[];
  releases: AlbumRelease[];
  statistics: AlbumStatistics;
  grabbed: boolean;               // Currently being downloaded
}

type AlbumType = 
  | "Album" 
  | "EP" 
  | "Single" 
  | "Broadcast" 
  | "Other";

interface Medium {
  mediumNumber: number;
  mediumName?: string;
  mediumFormat?: string;          // "CD", "Vinyl", "Digital Media"
}

interface AlbumRelease {
  id: number;
  albumId: number;
  foreignReleaseId: string;       // MusicBrainz Release ID
  title: string;
  status: string;
  duration: number;
  trackCount: number;
  media: Medium[];
  mediumCount: number;
  disambiguation?: string;
  country: string[];
  label: string[];
  format: string;
  monitored: boolean;
}
```

#### Python Model (SoulSpot)

```python
class Album(Base):
    """
    # Hey future me – albums can have multiple releases (editions, remasters).
    # The foreign_album_id is the MusicBrainz Release Group ID, NOT the individual
    # release ID. Each AlbumRelease has its own foreign_release_id.
    # album_type is the primary type, secondary_types is for stuff like "Live" or "Compilation".
    """
    __tablename__ = "albums"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False, index=True)
    foreign_album_id = Column(String(36), unique=True, nullable=False, index=True)  # MusicBrainz Release Group UUID
    
    # Basic Info
    title = Column(String(255), nullable=False)
    overview = Column(Text, nullable=True)
    disambiguation = Column(String(255), nullable=True)
    
    # Classification
    album_type = Column(String(50), default="Album")  # Album, EP, Single, Broadcast, Other
    secondary_types = Column(JSON, default=list)      # ["Compilation", "Live", "Remix", "Soundtrack"]
    
    # Monitoring
    monitored = Column(Boolean, default=True)
    any_release_ok = Column(Boolean, default=True)    # Accept any release edition
    
    # Release Info
    release_date = Column(DateTime, nullable=True)
    genres = Column(JSON, default=list)
    
    # Media
    media = Column(JSON, default=list)    # [{mediumNumber: 1, mediumFormat: "CD"}, ...]
    images = Column(JSON, default=list)   # [{coverType: "cover", url: "..."}, ...]
    links = Column(JSON, default=list)
    
    # Status
    grabbed = Column(Boolean, default=False)  # Currently downloading
    
    # Timestamps
    added = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album", cascade="all, delete-orphan")
    releases = relationship("AlbumRelease", back_populates="album", cascade="all, delete-orphan")
    
    @property
    def statistics(self) -> dict:
        """Computed album statistics."""
        total_tracks = len(self.tracks)
        tracks_with_files = sum(1 for t in self.tracks if t.has_file)
        return {
            "track_count": total_tracks,
            "track_file_count": tracks_with_files,
            "total_track_count": total_tracks,
            "size_on_disk": sum(t.track_file.size for t in self.tracks if t.track_file),
            "percent_of_tracks": (tracks_with_files / total_tracks * 100) if total_tracks > 0 else 0,
        }


class AlbumRelease(Base):
    """
    # Hey future me – this is for different editions of the same album.
    # E.g., "Dark Side of the Moon" has UK vinyl release, US CD release, 
    # Japanese deluxe edition, etc. Each is a separate AlbumRelease.
    """
    __tablename__ = "album_releases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False, index=True)
    foreign_release_id = Column(String(36), unique=True, nullable=False, index=True)  # MusicBrainz Release UUID
    
    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=True)    # Official, Promotional, Bootleg
    duration = Column(Integer, default=0)          # Total duration in ms
    track_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=1)
    
    media = Column(JSON, default=list)             # [{mediumNumber, mediumFormat, mediumName}]
    disambiguation = Column(String(255), nullable=True)
    country = Column(JSON, default=list)           # ["US", "UK", "JP"]
    label = Column(JSON, default=list)             # ["Columbia", "Sony"]
    format = Column(String(100), nullable=True)    # "CD", "Vinyl", "Digital"
    
    monitored = Column(Boolean, default=False)
    
    # Relationships
    album = relationship("Album", back_populates="releases")
```

---

### Track

Individual song/recording within an album.

#### TypeScript Interface (Lidarr Reference)

```typescript
interface Track {
  id: number;
  artistId: number;
  albumId: number;
  foreignTrackId: string;         // MusicBrainz Track ID
  foreignRecordingId: string;     // MusicBrainz Recording ID
  trackFileId?: number;
  albumReleaseId: number;
  
  absoluteTrackNumber: number;
  trackNumber: string;            // Can be "1", "A1", etc.
  title: string;
  duration: number;               // Milliseconds
  explicit: boolean;
  mediumNumber: number;
  
  hasFile: boolean;
  ratings: Ratings;
  
  // Navigation
  artist?: Artist;
  trackFile?: TrackFile;
}
```

#### Python Model (SoulSpot)

```python
class Track(Base):
    """
    # Hey future me – track_number is a STRING because vinyl can have "A1", "B2" etc.
    # Use absolute_track_number for sorting. foreign_track_id is from MusicBrainz.
    # has_file is a computed property, check if track_file_id is not None.
    """
    __tablename__ = "tracks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False, index=True)
    album_release_id = Column(Integer, ForeignKey("album_releases.id"), nullable=True)
    track_file_id = Column(Integer, ForeignKey("track_files.id"), nullable=True)
    
    # MusicBrainz IDs
    foreign_track_id = Column(String(36), nullable=True, index=True)
    foreign_recording_id = Column(String(36), nullable=True, index=True)
    
    # Track Info
    title = Column(String(255), nullable=False)
    track_number = Column(String(10), nullable=False)  # "1", "A1", "2-05"
    absolute_track_number = Column(Integer, nullable=False)
    medium_number = Column(Integer, default=1)
    
    # Audio Info
    duration = Column(Integer, default=0)  # Milliseconds
    explicit = Column(Boolean, default=False)
    
    # Metadata
    ratings = Column(JSON, default=dict)
    
    # Relationships
    artist = relationship("Artist")
    album = relationship("Album", back_populates="tracks")
    album_release = relationship("AlbumRelease")
    track_file = relationship("TrackFile", back_populates="track")
    
    @property
    def has_file(self) -> bool:
        return self.track_file_id is not None
```

---

### TrackFile

Physical audio file on disk.

#### TypeScript Interface (Lidarr Reference)

```typescript
interface TrackFile {
  id: number;
  artistId: number;
  albumId: number;
  trackIds: number[];
  
  path: string;
  size: number;                   // Bytes
  dateAdded: string;
  
  quality: Quality;
  qualityWeight: number;
  
  mediaInfo?: MediaInfo;
  
  qualityCutoffNotMet: boolean;
}

interface Quality {
  quality: {
    id: number;
    name: string;                 // "FLAC", "MP3-320", etc.
  };
  revision: {
    version: number;
    real: number;
    isRepack: boolean;
  };
}

interface MediaInfo {
  audioChannels: number;
  audioBitrate: number;
  audioCodec: string;
  audioBits: number;
  audioSampleRate: number;
}
```

#### Python Model (SoulSpot)

```python
class TrackFile(Base):
    """
    # Hey future me – this represents the actual file on disk. One TrackFile
    # can technically map to multiple tracks (rare, but possible for compilations).
    # quality_cutoff_not_met means we should upgrade this file if a better version appears.
    """
    __tablename__ = "track_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False, index=True)
    
    # File Info
    path = Column(String(1024), nullable=False, unique=True)
    size = Column(BigInteger, default=0)  # Bytes
    date_added = Column(DateTime, default=datetime.utcnow)
    
    # Quality
    quality = Column(JSON, nullable=False)  # {quality: {id, name}, revision: {...}}
    quality_weight = Column(Integer, default=0)
    quality_cutoff_not_met = Column(Boolean, default=False)
    
    # Media Info (from audio file analysis)
    media_info = Column(JSON, nullable=True)  # {audioChannels, audioBitrate, audioCodec, ...}
    
    # Relationships
    track = relationship("Track", back_populates="track_file", uselist=False)
    
    @property
    def audio_codec(self) -> str:
        return self.media_info.get("audioCodec", "Unknown") if self.media_info else "Unknown"
    
    @property
    def bitrate(self) -> int:
        return self.media_info.get("audioBitrate", 0) if self.media_info else 0
```

---

## Profile Models

### Quality Profile

Defines acceptable audio quality levels and upgrade thresholds.

```python
class QualityProfile(Base):
    """
    # Hey future me – cutoff is the quality level at which we stop upgrading.
    # If cutoff is "FLAC" and we have MP3-320, we'll upgrade. If we have FLAC, we won't.
    # items is ordered list of qualities with their allowed/preferred status.
    """
    __tablename__ = "quality_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    
    upgrade_allowed = Column(Boolean, default=True)
    cutoff = Column(Integer, nullable=False)  # Quality ID at which to stop upgrading
    
    # Ordered list of quality items
    # [{quality: {id, name}, allowed: true, items: []}, ...]
    items = Column(JSON, nullable=False)
    
    # Optional: custom format scores
    format_items = Column(JSON, default=list)
    min_format_score = Column(Integer, default=0)
    cutoff_format_score = Column(Integer, default=0)


class Quality(Base):
    """Pre-defined quality definitions."""
    __tablename__ = "qualities"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    weight = Column(Integer, nullable=False)  # For sorting/comparison
    
    # Known qualities:
    # 0: Unknown
    # 1: MP3-192
    # 2: MP3-256  
    # 3: MP3-320
    # 4: AAC-256
    # 5: AAC-320
    # 6: FLAC
    # 7: FLAC 24bit
    # 8: ALAC
    # 9: WAV
    # 10: APE
    # 11: WavPack
```

### Metadata Profile

Controls which album types to include in monitoring.

```python
class MetadataProfile(Base):
    """
    # Hey future me – this controls what types of albums we care about.
    # Some users only want Studio albums, others want everything including bootlegs.
    """
    __tablename__ = "metadata_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    
    # Primary types to include
    primary_album_types = Column(JSON, nullable=False)  # [{albumType: {id, name}, allowed: true}]
    
    # Secondary types to include  
    secondary_album_types = Column(JSON, nullable=False)  # [{albumType: {id, name}, allowed: true}]
    
    # Release statuses to include
    release_statuses = Column(JSON, nullable=False)  # [{releaseStatus: {id, name}, allowed: true}]
```

---

## Statistics Models

### ArtistStatistics

```python
@dataclass
class ArtistStatistics:
    """Computed statistics for an artist."""
    album_count: int = 0
    track_count: int = 0
    track_file_count: int = 0
    total_track_count: int = 0
    size_on_disk: int = 0  # Bytes
    percent_of_tracks: float = 0.0
```

### AlbumStatistics

```python
@dataclass
class AlbumStatistics:
    """Computed statistics for an album."""
    track_count: int = 0
    track_file_count: int = 0
    total_track_count: int = 0
    size_on_disk: int = 0  # Bytes
    percent_of_tracks: float = 0.0
```

---

## Supporting Models

### Image

```python
@dataclass
class Image:
    """Image metadata for posters, banners, etc."""
    cover_type: str  # "poster", "banner", "fanart", "cover"
    url: str
    remote_url: str = ""
    
# Stored as JSON in parent entity
```

### Link

```python
@dataclass
class Link:
    """External link (website, social media, etc.)."""
    url: str
    name: str
    
# Stored as JSON in parent entity
```

### Ratings

```python
@dataclass
class Ratings:
    """Rating information from external sources."""
    value: float = 0.0  # 0-5 or 0-10
    votes: int = 0
    
# Stored as JSON in parent entity
```

---

## Enums

```python
from enum import Enum

class ArtistStatus(str, Enum):
    CONTINUING = "continuing"
    ENDED = "ended"

class MonitorNewItems(str, Enum):
    ALL = "all"
    NONE = "none"
    NEW = "new"

class AlbumType(str, Enum):
    ALBUM = "Album"
    EP = "EP"
    SINGLE = "Single"
    BROADCAST = "Broadcast"
    OTHER = "Other"

class SecondaryAlbumType(str, Enum):
    COMPILATION = "Compilation"
    LIVE = "Live"
    REMIX = "Remix"
    SOUNDTRACK = "Soundtrack"
    INTERVIEW = "Interview"
    AUDIOBOOK = "Audiobook"
    DJ_MIX = "DJ-mix"
    MIXTAPE = "Mixtape/Street"
    DEMO = "Demo"
    SPOKENWORD = "Spokenword"

class ReleaseStatus(str, Enum):
    OFFICIAL = "Official"
    PROMOTIONAL = "Promotional"
    BOOTLEG = "Bootleg"
    PSEUDO_RELEASE = "Pseudo-Release"

class MediumFormat(str, Enum):
    CD = "CD"
    VINYL = "Vinyl"
    DIGITAL = "Digital Media"
    CASSETTE = "Cassette"
    DVD = "DVD"
    BLU_RAY = "Blu-ray"
    SACD = "SACD"
    OTHER = "Other"
```

---

## Database Schema

### Alembic Migration Example

```python
"""Initial library schema

Revision ID: xxxx
Create Date: 2025-11-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Artists
    op.create_table(
        'artists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('foreign_artist_id', sa.String(36), nullable=False, unique=True),
        sa.Column('artist_name', sa.String(255), nullable=False),
        sa.Column('sort_name', sa.String(255), nullable=False),
        sa.Column('clean_name', sa.String(255), nullable=False),
        sa.Column('disambiguation', sa.String(255)),
        sa.Column('artist_type', sa.String(50)),
        sa.Column('status', sa.String(20), default='continuing'),
        sa.Column('monitored', sa.Boolean(), default=True),
        sa.Column('monitor_new_items', sa.String(10), default='all'),
        sa.Column('path', sa.String(512)),
        sa.Column('root_folder_path', sa.String(512)),
        sa.Column('quality_profile_id', sa.Integer()),
        sa.Column('metadata_profile_id', sa.Integer()),
        sa.Column('overview', sa.Text()),
        sa.Column('genres', sa.JSON(), default=[]),
        sa.Column('images', sa.JSON(), default=[]),
        sa.Column('links', sa.JSON(), default=[]),
        sa.Column('ratings', sa.JSON(), default={}),
        sa.Column('tags', sa.JSON(), default=[]),
        sa.Column('added', sa.DateTime()),
        sa.Column('ended', sa.Boolean(), default=False),
    )
    op.create_index('ix_artists_foreign_artist_id', 'artists', ['foreign_artist_id'])
    op.create_index('ix_artists_sort_name', 'artists', ['sort_name'])
    
    # Albums
    op.create_table(
        'albums',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id'), nullable=False),
        sa.Column('foreign_album_id', sa.String(36), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('overview', sa.Text()),
        sa.Column('disambiguation', sa.String(255)),
        sa.Column('album_type', sa.String(50), default='Album'),
        sa.Column('secondary_types', sa.JSON(), default=[]),
        sa.Column('monitored', sa.Boolean(), default=True),
        sa.Column('any_release_ok', sa.Boolean(), default=True),
        sa.Column('release_date', sa.DateTime()),
        sa.Column('genres', sa.JSON(), default=[]),
        sa.Column('media', sa.JSON(), default=[]),
        sa.Column('images', sa.JSON(), default=[]),
        sa.Column('links', sa.JSON(), default=[]),
        sa.Column('grabbed', sa.Boolean(), default=False),
        sa.Column('added', sa.DateTime()),
    )
    op.create_index('ix_albums_artist_id', 'albums', ['artist_id'])
    op.create_index('ix_albums_foreign_album_id', 'albums', ['foreign_album_id'])
    
    # Tracks
    op.create_table(
        'tracks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id'), nullable=False),
        sa.Column('album_id', sa.Integer(), sa.ForeignKey('albums.id'), nullable=False),
        sa.Column('album_release_id', sa.Integer()),
        sa.Column('track_file_id', sa.Integer()),
        sa.Column('foreign_track_id', sa.String(36)),
        sa.Column('foreign_recording_id', sa.String(36)),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('track_number', sa.String(10), nullable=False),
        sa.Column('absolute_track_number', sa.Integer(), nullable=False),
        sa.Column('medium_number', sa.Integer(), default=1),
        sa.Column('duration', sa.Integer(), default=0),
        sa.Column('explicit', sa.Boolean(), default=False),
        sa.Column('ratings', sa.JSON(), default={}),
    )
    op.create_index('ix_tracks_album_id', 'tracks', ['album_id'])
    op.create_index('ix_tracks_artist_id', 'tracks', ['artist_id'])
    
    # Track Files
    op.create_table(
        'track_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id'), nullable=False),
        sa.Column('album_id', sa.Integer(), sa.ForeignKey('albums.id'), nullable=False),
        sa.Column('path', sa.String(1024), nullable=False, unique=True),
        sa.Column('size', sa.BigInteger(), default=0),
        sa.Column('date_added', sa.DateTime()),
        sa.Column('quality', sa.JSON(), nullable=False),
        sa.Column('quality_weight', sa.Integer(), default=0),
        sa.Column('quality_cutoff_not_met', sa.Boolean(), default=False),
        sa.Column('media_info', sa.JSON()),
    )

def downgrade():
    op.drop_table('track_files')
    op.drop_table('tracks')
    op.drop_table('albums')
    op.drop_table('artists')
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
