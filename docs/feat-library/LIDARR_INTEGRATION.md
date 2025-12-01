# Lidarr Library Integration Guide

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-12-01
- **Status**: Complete
- **Reference**: [Lidarr Wiki](https://wiki.servarr.com/lidarr), [Davo's Community Guide](https://wiki.servarr.com/lidarr/community-guide)

---

## Overview

This document provides comprehensive guidance for integrating SoulSpot with existing Lidarr-managed music libraries. It covers folder structures, naming conventions, metadata handling, and configuration settings to ensure seamless compatibility between the two systems.

### Why Lidarr Compatibility Matters

- **Preserve Existing Structure** — Users with Lidarr-managed libraries shouldn't need to reorganize
- **Media Server Compatibility** — Plex, Jellyfin, Emby, and Navidrome expect consistent structures
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

### Real-World Example

```
/music
├── Michael Jackson
│   ├── Off the Wall (1979)
│   │   ├── 01 - Don't Stop 'til You Get Enough.flac
│   │   ├── 02 - Rock with You.flac
│   │   ├── 03 - Working Day and Night.flac
│   │   └── cover.jpg
│   ├── Thriller (1982)
│   │   ├── 01 - Wanna Be Startin' Somethin'.flac
│   │   ├── 02 - Baby Be Mine.flac
│   │   ├── 03 - The Girl Is Mine.flac
│   │   ├── 04 - Thriller.flac
│   │   ├── 05 - Beat It.flac
│   │   └── ...
│   └── Bad (1987)
│       └── ...
├── The Beatles
│   ├── Abbey Road (1969)
│   │   └── ...
│   └── The White Album (1968)      ← Multi-Disc Example
│       ├── 01-01 - Back in the U.S.S.R..flac
│       ├── 01-02 - Dear Prudence.flac
│       ├── ...
│       ├── 02-01 - Birthday.flac
│       ├── 02-02 - Yer Blues.flac
│       └── ...
└── Various Artists
    └── Now That's What I Call Music! 1 (1983)
        ├── 01 - Phil Collins - You Can't Hurry Love.flac
        ├── 02 - Culture Club - Karma Chameleon.flac
        └── ...
```

---

## Naming Conventions

### Lidarr Naming Tokens

Lidarr uses a token-based system for flexible naming. Understanding these tokens is essential for SoulSpot compatibility.

#### Artist Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Artist Name}` | Full artist name | `Michael Jackson` |
| `{Artist CleanName}` | URL/filesystem-safe name | `michaeljackson` |
| `{Artist SortName}` | Sortable format | `Jackson, Michael` |
| `{Artist Disambiguation}` | Disambiguating info | `UK band` |

#### Album Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Album Title}` | Full album title | `Thriller` |
| `{Album CleanTitle}` | URL/filesystem-safe title | `thriller` |
| `{Album Type}` | Album classification | `Album`, `EP`, `Single` |
| `{Album Disambiguation}` | Edition info | `Deluxe Edition` |
| `{Release Year}` | 4-digit year | `1982` |
| `{Release Date}` | Full date | `1982-11-30` |
| `{Original Year}` | Original release year | `1982` |

#### Track Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Track Title}` | Track name | `Billie Jean` |
| `{track:00}` | Zero-padded track number | `05` |
| `{track:0}` | Non-padded track number | `5` |
| `{medium:00}` | Disc number (zero-padded) | `01` |
| `{medium:0}` | Disc number (non-padded) | `1` |

#### Quality Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Quality Full}` | Full quality description | `FLAC` |
| `{MediaInfo AudioCodec}` | Audio codec | `FLAC`, `MP3` |
| `{MediaInfo AudioBitrate}` | Bitrate in kbps | `320`, `1411` |
| `{MediaInfo AudioBitsPerSample}` | Bit depth | `16`, `24` |
| `{MediaInfo AudioSampleRate}` | Sample rate in Hz | `44100`, `96000` |

### Standard Naming Formats

#### Default Lidarr Folder Formats

```
Artist Folder Format:
{Artist Name}

Album Folder Format:
{Album Title} ({Release Year})

Album Folder with Disambiguation:
{Album Title} ({Release Year}) {(Album Disambiguation)}
```

#### Default Track Naming Formats

**Standard (Single Disc):**
```
{track:00} - {Track Title}
Example: 05 - Billie Jean.flac
```

**Multi-Disc Albums:**
```
{medium:00}-{track:00} - {Track Title}
Example: 02-05 - Birthday.flac
```

**Various Artists / Compilations:**
```
{track:00} - {Artist Name} - {Track Title}
Example: 01 - Phil Collins - You Can't Hurry Love.flac
```

**Full Path with Artist in Filename (Alternative):**
```
{Artist Name}_{Album Title}_{track:00}_{Track Title}
Example: Michael Jackson_Thriller_05_Billie Jean.flac
```

---

## Multi-Disc Album Handling

### Naming Strategies

Lidarr offers two primary approaches for multi-disc releases:

#### 1. Prefix Style (Recommended)

Track numbers include disc prefix:

```
/music/The Beatles/The White Album (1968)/
├── 01-01 - Back in the U.S.S.R..flac
├── 01-02 - Dear Prudence.flac
├── 01-17 - Revolution 1.flac
├── 02-01 - Birthday.flac
├── 02-02 - Yer Blues.flac
└── 02-13 - Good Night.flac
```

**Format String:**
```
{medium:00}-{track:00} - {Track Title}
```

#### 2. Subfolder Style

Each disc in separate folder:

```
/music/The Beatles/The White Album (1968)/
├── Disc 1/
│   ├── 01 - Back in the U.S.S.R..flac
│   ├── 02 - Dear Prudence.flac
│   └── ...
└── Disc 2/
    ├── 01 - Birthday.flac
    ├── 02 - Yer Blues.flac
    └── ...
```

**Disc Folder Format:**
```
Disc {medium}
or
CD {medium}
```

### SoulSpot Implementation

```python
from dataclasses import dataclass
from enum import Enum


class MultiDiscStyle(Enum):
    PREFIX = "prefix"           # 01-01 - Track.flac
    SUBFOLDER = "subfolder"     # Disc 1/01 - Track.flac


@dataclass
class LidarrNamingConfig:
    """
    # Hey future me – this config mirrors Lidarr's Media Management settings.
    # The multi_disc_style determines how we handle albums with multiple CDs.
    # PREFIX is more common and works better with most music players.
    """
    # Artist folder
    artist_folder_format: str = "{Artist Name}"
    
    # Album folder
    album_folder_format: str = "{Album Title} ({Release Year})"
    album_folder_with_disambiguation: str = "{Album Title} ({Release Year}) {(Album Disambiguation)}"
    
    # Track naming
    standard_track_format: str = "{track:00} - {Track Title}"
    multi_disc_track_format: str = "{medium:00}-{track:00} - {Track Title}"
    various_artist_format: str = "{track:00} - {Artist Name} - {Track Title}"
    
    # Multi-disc handling
    multi_disc_style: MultiDiscStyle = MultiDiscStyle.PREFIX
    multi_disc_folder_format: str = "Disc {medium}"
    
    # Special handling
    replace_illegal_characters: bool = True
    colon_replacement: str = " -"
```

---

## Special Character Handling

### Reserved Characters by OS

| OS | Reserved Characters |
|----|---------------------|
| **Windows** | `< > : " / \ | ? *` and `NUL` |
| **macOS** | `:` (displayed as `/` in Finder) |
| **Linux** | `/` and `NUL` |

### Lidarr Replacement Rules

| Original | Replacement | Notes |
|----------|-------------|-------|
| `:` | ` -` | Configurable (space-dash is default) |
| `/` | `-` | Slash to dash |
| `\` | `-` | Backslash to dash |
| `<` | (removed) | Less than |
| `>` | (removed) | Greater than |
| `"` | `'` | Double to single quote |
| `|` | `-` | Pipe to dash |
| `?` | (removed) | Question mark |
| `*` | (removed) | Asterisk |

### Colon Replacement Options

Lidarr provides configurable colon replacement:

```python
class ColonReplacement(Enum):
    DELETE = ""               # Remove colons entirely
    DASH = "-"               # Replace with dash
    SPACE_DASH = " -"        # Replace with space-dash (default)
    SPACE_DASH_SPACE = " - " # Replace with space-dash-space
```

**Example:**
```
Original:    "Re: Stacks"
DELETE:      "Re Stacks"
DASH:        "Re- Stacks"
SPACE_DASH:  "Re - Stacks"  (Lidarr default)
```

### Implementation

```python
import re
from pathlib import Path


class LidarrFileNameSanitizer:
    """
    # Hey future me – this handles illegal characters the way Lidarr does.
    # Windows is the most restrictive, so we sanitize for that.
    # The colon replacement is user-configurable in Lidarr settings.
    """
    
    ILLEGAL_CHARS_PATTERN = re.compile(r'[<>"/\\|?*\x00-\x1f]')
    
    def __init__(self, colon_replacement: str = " -"):
        self.colon_replacement = colon_replacement
    
    def sanitize(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility."""
        # Replace colons first (configurable)
        name = name.replace(":", self.colon_replacement)
        
        # Remove other illegal characters
        name = self.ILLEGAL_CHARS_PATTERN.sub("", name)
        
        # Trim whitespace and dots from ends (Windows requirement)
        name = name.strip(" .")
        
        # Handle empty result
        if not name:
            name = "Unknown"
        
        return name
    
    def sanitize_path_component(self, component: str) -> str:
        """Sanitize a single path component (folder or filename without extension)."""
        return self.sanitize(component)
    
    def sanitize_full_path(self, path: str) -> str:
        """Sanitize all components of a path."""
        path_obj = Path(path)
        sanitized_parts = [self.sanitize(part) for part in path_obj.parts]
        return str(Path(*sanitized_parts))
```

---

## Quality Profiles

### Lidarr Quality Tiers

Lidarr defines quality tiers for audio files, ordered by preference:

| ID | Name | Bitrate | Lossless | Weight |
|----|------|---------|----------|--------|
| 0 | Unknown | Variable | No | 1 |
| 1 | MP3-VBR | Variable | No | 200 |
| 2 | MP3-192 | 192 kbps | No | 300 |
| 3 | MP3-256 | 256 kbps | No | 400 |
| 4 | MP3-320 | 320 kbps | No | 500 |
| 5 | AAC-256 | 256 kbps | No | 450 |
| 6 | FLAC | Variable | Yes | 600 |
| 7 | FLAC 24-bit | Variable | Yes | 700 |
| 8 | ALAC | Variable | Yes | 600 |
| 9 | ALAC 24-bit | Variable | Yes | 700 |
| 10 | WAV | Uncompressed | Yes | 650 |
| 11 | OGG Vorbis Q10 | ~500 kbps | No | 550 |
| 12 | Opus 256 | 256 kbps | No | 475 |
| 13 | APE | Variable | Yes | 580 |
| 14 | WavPack | Variable | Yes | 590 |

### Preset Quality Profiles

#### Lossless Profile

Best quality, lossless audio only:

```json
{
  "name": "Lossless",
  "upgradeAllowed": true,
  "cutoff": 6,
  "items": [
    {
      "name": "Lossless",
      "items": [
        { "quality": { "id": 7, "name": "FLAC 24-bit" }, "allowed": true },
        { "quality": { "id": 6, "name": "FLAC" }, "allowed": true },
        { "quality": { "id": 9, "name": "ALAC 24-bit" }, "allowed": true },
        { "quality": { "id": 8, "name": "ALAC" }, "allowed": true }
      ],
      "allowed": true
    }
  ]
}
```

#### High Quality Profile

High bitrate lossy, smaller file sizes:

```json
{
  "name": "High Quality",
  "upgradeAllowed": true,
  "cutoff": 4,
  "items": [
    { "quality": { "id": 4, "name": "MP3-320" }, "allowed": true },
    { "quality": { "id": 5, "name": "AAC-256" }, "allowed": true },
    { "quality": { "id": 12, "name": "Opus 256" }, "allowed": true }
  ]
}
```

#### Standard Profile

Accept any quality, prefer better:

```json
{
  "name": "Standard",
  "upgradeAllowed": true,
  "cutoff": 4,
  "items": [
    { "quality": { "id": 7, "name": "FLAC 24-bit" }, "allowed": true },
    { "quality": { "id": 6, "name": "FLAC" }, "allowed": true },
    { "quality": { "id": 4, "name": "MP3-320" }, "allowed": true },
    { "quality": { "id": 3, "name": "MP3-256" }, "allowed": true },
    { "quality": { "id": 2, "name": "MP3-192" }, "allowed": true }
  ]
}
```

---

## Metadata Profiles

### Album Types

Lidarr tracks album types from MusicBrainz:

| Type | Description | Include by Default |
|------|-------------|-------------------|
| **Album** | Standard studio album | ✅ Yes |
| **EP** | Extended play | ✅ Yes |
| **Single** | Single release | ❌ No |
| **Broadcast** | Radio/TV broadcast | ❌ No |
| **Other** | Uncategorized releases | ❌ No |

### Secondary Album Types

| Type | Description | Include by Default |
|------|-------------|-------------------|
| **Compilation** | Best-of, greatest hits | ❌ No |
| **Live** | Live recordings | ❌ No |
| **Remix** | Remix albums | ❌ No |
| **Soundtrack** | Film/TV/Game soundtracks | ❌ No |
| **DJ-mix** | DJ mix compilations | ❌ No |
| **Mixtape/Street** | Mixtapes | ❌ No |
| **Demo** | Demo recordings | ❌ No |
| **Interview** | Interview content | ❌ No |

### Release Statuses

| Status | Description | Include by Default |
|--------|-------------|-------------------|
| **Official** | Official releases | ✅ Yes |
| **Promotional** | Promo releases | ❌ No |
| **Bootleg** | Unofficial recordings | ❌ No |
| **Pseudo-Release** | Special releases | ❌ No |

### Standard Metadata Profile

```python
from dataclasses import dataclass, field


@dataclass
class LidarrMetadataProfile:
    """
    # Hey future me – metadata profiles control what types of albums
    # Lidarr monitors. Most users only want official studio albums.
    # Enabling everything can flood the library with low-priority releases.
    """
    name: str = "Standard"
    
    # Primary album types to include
    primary_album_types: list[str] = field(default_factory=lambda: [
        "Album",
        "EP",
    ])
    
    # Secondary album types to include (usually empty for clean libraries)
    secondary_album_types: list[str] = field(default_factory=list)
    
    # Release statuses to include
    release_statuses: list[str] = field(default_factory=lambda: [
        "Official",
    ])
```

---

## MusicBrainz Integration

### Entity Relationships

```
┌─────────────────┐
│     Artist      │ ← MusicBrainz Artist ID (UUID)
├─────────────────┤
│ e.g., Michael   │
│     Jackson     │
└────────┬────────┘
         │
         │ has many
         ▼
┌─────────────────┐
│  Release Group  │ ← MusicBrainz Release Group ID (UUID)
├─────────────────┤    (Album concept)
│ e.g., Thriller  │
└────────┬────────┘
         │
         │ has many editions
         ▼
┌─────────────────┐
│    Release      │ ← MusicBrainz Release ID (UUID)
├─────────────────┤    (Specific edition/format)
│ e.g., Thriller  │
│ (US CD, 1982)   │
└────────┬────────┘
         │
         │ contains
         ▼
┌─────────────────┐
│     Track       │ ← Links to Recording
├─────────────────┤
│ Position on     │
│ this release    │
└────────┬────────┘
         │
         │ points to
         ▼
┌─────────────────┐
│   Recording     │ ← MusicBrainz Recording ID (UUID)
├─────────────────┤    (The actual performance)
│ e.g., Billie    │
│ Jean (1982)     │
└─────────────────┘
```

### MusicBrainz IDs in Audio Tags

Lidarr expects these ID3 tags for optimal matching:

| Tag | Standard | Description |
|-----|----------|-------------|
| `MUSICBRAINZ_ARTISTID` | ID3v2.4 / Vorbis | Artist UUID |
| `MUSICBRAINZ_ALBUMID` | ID3v2.4 / Vorbis | Release Group UUID |
| `MUSICBRAINZ_RELEASEGROUPID` | ID3v2.4 / Vorbis | Release Group UUID |
| `MUSICBRAINZ_ALBUMARTISTID` | ID3v2.4 / Vorbis | Album Artist UUID |
| `MUSICBRAINZ_TRACKID` | ID3v2.4 / Vorbis | Recording UUID |

### Import Priority

When importing files, Lidarr matches in this order:

1. **MusicBrainz Artist ID + Album ID** (most reliable)
2. **MusicBrainz Release ID**
3. **MusicBrainz Recording/Track ID**
4. **File/folder name + existing tags** (least reliable)

---

## SoulSpot Configuration for Lidarr Compatibility

### Settings Configuration

```python
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class SoulSpotLidarrConfig:
    """
    # Hey future me – this is the master config for Lidarr compatibility.
    # All settings should match your Lidarr installation's Media Management
    # settings. When in doubt, check Lidarr's settings and mirror them here.
    """
    
    # Root folder (must match Lidarr root folder)
    root_folder: Path = Path("/music")
    
    # Naming formats (should match Lidarr Media Management)
    artist_folder_format: str = "{Artist Name}"
    album_folder_format: str = "{Album Title} ({Release Year})"
    standard_track_format: str = "{track:00} - {Track Title}"
    multi_disc_track_format: str = "{medium:00}-{track:00} - {Track Title}"
    
    # Various Artists handling
    various_artist_track_format: str = "{track:00} - {Artist Name} - {Track Title}"
    
    # Special character handling
    replace_illegal_characters: bool = True
    colon_replacement: str = " -"
    
    # Multi-disc handling
    multi_disc_style: str = "prefix"  # "prefix" or "subfolder"
    multi_disc_folder_format: str = "Disc {medium}"
    
    # Quality settings
    preferred_quality: str = "FLAC"
    accept_qualities: list[str] = None
    
    # Metadata profile
    primary_album_types: list[str] = None
    release_statuses: list[str] = None
    
    def __post_init__(self):
        if self.accept_qualities is None:
            self.accept_qualities = ["FLAC", "FLAC 24-bit", "ALAC", "MP3-320"]
        if self.primary_album_types is None:
            self.primary_album_types = ["Album", "EP"]
        if self.release_statuses is None:
            self.release_statuses = ["Official"]
```

### Library Scanner Integration

The following example shows how to implement a scanner for Lidarr-organized libraries:

```python
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Type definitions for scanner results
@dataclass
class AlbumFolderInfo:
    title: str
    year: Optional[int]
    disambiguation: Optional[str]


@dataclass
class TrackFileInfo:
    track_number: int
    disc_number: int
    title: str
    extension: str
    artist: Optional[str] = None


@dataclass
class TrackInfo:
    title: str
    track_number: int
    disc_number: int
    path: Path


@dataclass
class AlbumInfo:
    title: str
    year: Optional[int]
    disambiguation: Optional[str]
    path: Path
    tracks: list[TrackInfo] = None
    
    def __post_init__(self):
        if self.tracks is None:
            self.tracks = []


@dataclass
class ArtistInfo:
    name: str
    path: Path
    albums: list[AlbumInfo] = None
    
    def __post_init__(self):
        if self.albums is None:
            self.albums = []


@dataclass
class LibraryScanResult:
    artists: list[ArtistInfo]


# Supported audio file extensions
AUDIO_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.ogg', '.opus', '.wav', '.ape', '.wv', '.alac'}


class LidarrLibraryScanner:
    """
    # Hey future me – this scanner reads an existing Lidarr library
    # and imports it into SoulSpot's database. It parses folder names
    # using Lidarr's naming conventions to extract metadata.
    """
    
    ARTIST_FOLDER_PATTERN = re.compile(r'^(.+)$')
    ALBUM_FOLDER_PATTERN = re.compile(r'^(.+?)\s*\((\d{4})\)(?:\s*\(([^)]+)\))?$')
    TRACK_FILE_PATTERN = re.compile(r'^(\d+)-?(\d+)?\s*-\s*(.+)\.(\w+)$')
    VARIOUS_ARTIST_TRACK_PATTERN = re.compile(r'^(\d+)\s*-\s*(.+?)\s*-\s*(.+)\.(\w+)$')
    
    def __init__(self, config: SoulSpotLidarrConfig):
        self.config = config
        self.sanitizer = LidarrFileNameSanitizer(config.colon_replacement)
    
    async def scan_library(self) -> LibraryScanResult:
        """Scan the Lidarr library and extract metadata."""
        artists = []
        
        for artist_path in self.config.root_folder.iterdir():
            if not artist_path.is_dir():
                continue
            
            artist_name = self._parse_artist_folder(artist_path.name)
            artist = ArtistInfo(name=artist_name, path=artist_path)
            
            for album_path in artist_path.iterdir():
                if not album_path.is_dir():
                    continue
                
                album_info = self._parse_album_folder(album_path.name)
                album = AlbumInfo(
                    title=album_info.title,
                    year=album_info.year,
                    disambiguation=album_info.disambiguation,
                    path=album_path,
                )
                
                for track_file in album_path.glob('**/*'):
                    if track_file.suffix.lower() not in AUDIO_EXTENSIONS:
                        continue
                    
                    track_info = self._parse_track_file(track_file.name)
                    track = TrackInfo(
                        title=track_info.title,
                        track_number=track_info.track_number,
                        disc_number=track_info.disc_number,
                        path=track_file,
                    )
                    album.tracks.append(track)
                
                artist.albums.append(album)
            
            artists.append(artist)
        
        return LibraryScanResult(artists=artists)
    
    def _parse_artist_folder(self, folder_name: str) -> str:
        """Extract artist name from folder."""
        match = self.ARTIST_FOLDER_PATTERN.match(folder_name)
        return match.group(1) if match else folder_name
    
    def _parse_album_folder(self, folder_name: str) -> AlbumFolderInfo:
        """Extract album info from folder name."""
        match = self.ALBUM_FOLDER_PATTERN.match(folder_name)
        if match:
            return AlbumFolderInfo(
                title=match.group(1),
                year=int(match.group(2)),
                disambiguation=match.group(3),
            )
        return AlbumFolderInfo(title=folder_name, year=None, disambiguation=None)
    
    def _parse_track_file(self, filename: str) -> TrackFileInfo:
        """Extract track info from filename."""
        # Try multi-disc format first
        match = self.TRACK_FILE_PATTERN.match(filename)
        if match:
            disc = int(match.group(2)) if match.group(2) else 1
            track = int(match.group(1))
            if match.group(2):  # Multi-disc format: DD-TT
                disc = int(match.group(1))
                track = int(match.group(2))
            return TrackFileInfo(
                track_number=track,
                disc_number=disc,
                title=match.group(3),
                extension=match.group(4),
            )
        
        # Try various artists format
        match = self.VARIOUS_ARTIST_TRACK_PATTERN.match(filename)
        if match:
            return TrackFileInfo(
                track_number=int(match.group(1)),
                disc_number=1,
                artist=match.group(2),
                title=match.group(3),
                extension=match.group(4),
            )
        
        # Fallback
        return TrackFileInfo(
            track_number=0,
            disc_number=1,
            title=Path(filename).stem,
            extension=Path(filename).suffix,
        )
```

---

## Media Server Compatibility

### Plex

Plex expects:
```
/music/{Artist}/{Album} ({Year})/01 - {Track}.flac
```

**Additional Plex Tips:**
- Add `cover.jpg` or `poster.jpg` to album folders for artwork
- Use Plex's Music agent (Plex Music) for metadata
- Enable "Prefer local metadata" for Lidarr-tagged files

### Jellyfin / Emby

Jellyfin/Emby expect:
```
/music/{Artist}/{Album}/01 - {Track}.flac
```

**Notes:**
- Year in album folder is optional but recommended
- Supports `folder.jpg` or `cover.jpg` for artwork
- Can read embedded artwork from FLAC/MP3

### Navidrome

Navidrome is flexible:
```
/music/{Artist}/{Album} ({Year})/01 - {Track}.flac
```

**Notes:**
- Reads tags directly from files
- Supports multiple artwork files (`cover.jpg`, `folder.jpg`, `front.jpg`)
- Works well with MusicBrainz-tagged files

### Recommended Universal Format

For maximum compatibility across all media servers:

```python
UNIVERSAL_FORMAT = {
    "artist_folder": "{Artist Name}",
    "album_folder": "{Album Title} ({Release Year})",
    "standard_track": "{track:00} - {Track Title}",
    "multi_disc_track": "{medium:00}-{track:00} - {Track Title}",
}
```

---

## Importing Existing Libraries

### Pre-Import Checklist

1. **Backup Your Library** — Always backup before making changes
2. **Check Lidarr Settings** — Note current Media Management configuration
3. **Verify MusicBrainz Tags** — Check if files have MB IDs (Picard, beets)
4. **Review Folder Structure** — Ensure consistent artist/album folders

### Import Process

The following example demonstrates the import workflow pattern:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LibraryImportError:
    """Error during library import."""
    artist_name: str
    error_message: str


@dataclass
class ImportResult:
    """Result of library import operation."""
    imported: int
    skipped: int
    errors: list[LibraryImportError]


async def import_lidarr_library(
    source_path: Path,
    config: SoulSpotLidarrConfig,
    artist_service: Any,  # Your ArtistService implementation
    album_service: Any,   # Your AlbumService implementation
    track_service: Any,   # Your TrackService implementation
) -> ImportResult:
    """
    # Hey future me – this imports an existing Lidarr library.
    # It reads the folder structure and file tags, then creates
    # corresponding entries in SoulSpot's database.
    # IMPORTANT: This does NOT move or modify any files!
    """
    scanner = LidarrLibraryScanner(config)
    scan_result = await scanner.scan_library()
    
    imported_artists = []
    skipped_items = []
    errors: list[LibraryImportError] = []
    
    for artist_info in scan_result.artists:
        try:
            # Create or find artist
            artist = await artist_service.find_or_create(
                name=artist_info.name,
                path=artist_info.path,
            )
            
            for album_info in artist_info.albums:
                # Create or find album
                album = await album_service.find_or_create(
                    artist_id=artist.id,
                    title=album_info.title,
                    release_year=album_info.year,
                    path=album_info.path,
                )
                
                for track_info in album_info.tracks:
                    # Create track entry
                    await track_service.create(
                        album_id=album.id,
                        title=track_info.title,
                        track_number=track_info.track_number,
                        disc_number=track_info.disc_number,
                        file_path=track_info.path,
                    )
            
            imported_artists.append(artist)
            
        except Exception as e:
            errors.append(LibraryImportError(artist_info.name, str(e)))
    
    return ImportResult(
        imported=len(imported_artists),
        skipped=len(skipped_items),
        errors=errors,
    )
```

### Post-Import Tasks

1. **Verify Import** — Check that all artists/albums appear in SoulSpot
2. **Refresh Metadata** — Trigger MusicBrainz metadata refresh
3. **Check Quality Profiles** — Ensure files match expected quality
4. **Test Media Servers** — Verify Plex/Jellyfin still work correctly

---

## Troubleshooting

### Common Issues

#### Files Not Matching

**Problem:** Lidarr can't match imported files to releases.

**Solutions:**
1. Tag files with MusicBrainz IDs using Picard or beets
2. Ensure folder names follow exact format: `{Album Title} ({Year})`
3. Check for special character issues

#### Multi-Disc Albums Confused

**Problem:** Disc 1 and Disc 2 tracks mixed up.

**Solutions:**
1. Use `{medium:00}-{track:00}` format consistently
2. Ensure disc numbers are correct in file tags
3. Verify MusicBrainz release matches actual disc count

#### Various Artists Not Grouped

**Problem:** Compilation tracks scattered across artist folders.

**Solutions:**
1. Use "Various Artists" as album artist
2. Place in `/music/Various Artists/{Compilation}/`
3. Include artist name in track filename

#### Quality Profile Mismatch

**Problem:** SoulSpot downloads different quality than Lidarr.

**Solutions:**
1. Sync quality profile settings between systems
2. Set same cutoff quality
3. Verify allowed quality list matches

---

## API Reference

### Naming Configuration Endpoint

```http
GET /api/v1/config/naming
```

**Response:**
```json
{
  "renameTrack": true,
  "replaceIllegalCharacters": true,
  "colonReplacementFormat": " -",
  "artistFolderFormat": "{Artist Name}",
  "albumFolderFormat": "{Album Title} ({Release Year})",
  "standardTrackFormat": "{track:00} - {Track Title}",
  "multiDiscTrackFormat": "{medium:00}-{track:00} - {Track Title}"
}
```

### Update Naming Configuration

```http
PUT /api/v1/config/naming
Content-Type: application/json

{
  "renameTrack": true,
  "replaceIllegalCharacters": true,
  "colonReplacementFormat": " -",
  "artistFolderFormat": "{Artist Name}",
  "albumFolderFormat": "{Album Title} ({Release Year})",
  "standardTrackFormat": "{track:00} - {Track Title}",
  "multiDiscTrackFormat": "{medium:00}-{track:00} - {Track Title}"
}
```

### Import Library Endpoint

```http
POST /api/v1/library/import
Content-Type: application/json

{
  "sourcePath": "/music",
  "scanMode": "full",
  "matchMode": "relaxed"
}
```

---

## References

- [Lidarr Official Documentation](https://wiki.servarr.com/lidarr)
- [Davo's Community Lidarr Guide](https://wiki.servarr.com/lidarr/community-guide)
- [Lidarr Quick Start Guide](https://wiki.servarr.com/lidarr/quick-start-guide)
- [MusicBrainz Database Schema](https://musicbrainz.org/doc/MusicBrainz_Database/Schema)
- [Picard MusicBrainz Tagger](https://picard.musicbrainz.org/)

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-01  
**Status**: Complete
