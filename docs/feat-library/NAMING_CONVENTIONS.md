# File & Folder Naming Conventions

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-11-28
- **Status**: Draft
- **Reference**: [Lidarr Naming](https://github.com/Lidarr/Lidarr)

---

## Overview

This document defines the naming conventions for organizing music files on disk. A well-structured naming system enables:

1. **Consistency** — All files follow predictable patterns
2. **Compatibility** — Works with media servers (Plex, Jellyfin, Navidrome)
3. **Readability** — Easy to browse in file managers
4. **Metadata Preservation** — Important info encoded in filenames

---

## Naming Tokens

### Artist Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Artist Name}` | Artist name | `Michael Jackson` |
| `{Artist CleanName}` | URL-safe name | `michaeljackson` |
| `{Artist SortName}` | Sortable name | `Jackson, Michael` |
| `{Artist MbId}` | MusicBrainz Artist ID | `f27ec8db-af05-4f36-916e-3d57f91ecf5e` |
| `{Artist Disambiguation}` | Disambiguation | `US singer` |
| `{Artist Genre}` | Primary genre | `Pop` |

### Album Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Album Title}` | Album title | `Thriller` |
| `{Album CleanTitle}` | URL-safe title | `thriller` |
| `{Album SortTitle}` | Sortable title | `Thriller` |
| `{Album MbId}` | MusicBrainz Release Group ID | `6f5e7e10-5e4f-4e3a-9a1a-2b3c4d5e6f7a` |
| `{Album Type}` | Album type | `Album`, `EP`, `Single` |
| `{Album Disambiguation}` | Disambiguation | `Deluxe Edition` |
| `{Release Year}` | Release year | `1982` |
| `{Release Date}` | Full date | `1982-11-30` |
| `{Original Year}` | Original release year | `1982` |

### Track Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Track Title}` | Track title | `Billie Jean` |
| `{Track CleanTitle}` | URL-safe title | `billiejean` |
| `{Track Number}` | Track number (padded) | `05` |
| `{Track Number:0}` | Track number (no padding) | `5` |
| `{Track Number:00}` | Track number (2 digits) | `05` |
| `{Track Number:000}` | Track number (3 digits) | `005` |

### Medium/Disc Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Medium}` | Disc number | `1` |
| `{Medium:0}` | Disc number (no padding) | `1` |
| `{Medium:00}` | Disc number (2 digits) | `01` |
| `{Medium Format}` | Disc format | `CD`, `Vinyl`, `Digital` |
| `{Medium Name}` | Disc name | `Disc 1: The Early Years` |

### Quality Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Quality Full}` | Full quality name | `FLAC` |
| `{Quality Title}` | Quality title | `FLAC` |
| `{MediaInfo AudioCodec}` | Audio codec | `FLAC`, `MP3` |
| `{MediaInfo AudioBitrate}` | Bitrate | `320`, `1411` |
| `{MediaInfo AudioBitsPerSample}` | Bit depth | `16`, `24` |
| `{MediaInfo AudioSampleRate}` | Sample rate | `44100`, `96000` |

### Special Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{-Group}` | Release group suffix | `-PERFECT` |
| ` [{Preferred Words}]` | Matching preferred words | `[Remastered]` |
| `{Custom Format}` | Custom format score | `[Score: 50]` |

---

## Standard Naming Formats

### Artist Folder Format

**Recommended:**
```
{Artist Name}
```

**Examples:**
```
Michael Jackson
The Beatles
Beethoven
```

**With Disambiguation:**
```
{Artist Name} ({Artist Disambiguation})
```

**Examples:**
```
Michael Jackson
Genesis (UK band)
Queen (UK rock band)
```

### Album Folder Format

**Recommended:**
```
{Album Title} ({Release Year})
```

**Examples:**
```
Thriller (1982)
Abbey Road (1969)
Symphony No. 9 (1824)
```

**With Album Type:**
```
{Album Title} ({Release Year}) [{Album Type}]
```

**Examples:**
```
Thriller (1982) [Album]
Bad (Live) (1988) [Live]
Dangerous (1991) [Album]
```

**With Quality:**
```
{Album Title} ({Release Year}) [{Quality Full}]
```

**Examples:**
```
Thriller (1982) [FLAC]
Abbey Road (1969) [MP3-320]
```

### Track File Format

**Standard (Single Disc):**
```
{Track Number:00} - {Track Title}
```

**Examples:**
```
01 - Wanna Be Startin' Somethin'.flac
02 - Baby Be Mine.flac
05 - Billie Jean.flac
```

**Multi-Disc Albums:**
```
{Medium:00}-{Track Number:00} - {Track Title}
```

**Examples:**
```
01-01 - Come Together.flac
01-02 - Something.flac
02-01 - Here Comes the Sun.flac
02-02 - Because.flac
```

**With Artist (Compilations):**
```
{Track Number:00} - {Artist Name} - {Track Title}
```

**Examples:**
```
01 - Michael Jackson - Billie Jean.flac
02 - Prince - Kiss.flac
03 - Madonna - Like a Virgin.flac
```

---

## Full Path Examples

### Standard Library

```
/music
└── Michael Jackson
    ├── Off the Wall (1979)
    │   ├── 01 - Don't Stop 'til You Get Enough.flac
    │   ├── 02 - Rock with You.flac
    │   └── ...
    ├── Thriller (1982)
    │   ├── 01 - Wanna Be Startin' Somethin'.flac
    │   ├── 02 - Baby Be Mine.flac
    │   └── ...
    └── Bad (1987)
        ├── 01 - Bad.flac
        └── ...
```

### Multi-Disc Album

```
/music
└── The Beatles
    └── The White Album (1968)
        ├── 01-01 - Back in the U.S.S.R..flac
        ├── 01-02 - Dear Prudence.flac
        ├── ...
        ├── 02-01 - Birthday.flac
        ├── 02-02 - Yer Blues.flac
        └── ...
```

### With Quality Tags

```
/music
└── Michael Jackson
    └── Thriller (1982) [FLAC]
        ├── 01 - Wanna Be Startin' Somethin'.flac
        └── ...
```

### Various Artists / Compilations

```
/music
└── Various Artists
    └── Now That's What I Call Music! 1 (1983)
        ├── 01 - Phil Collins - You Can't Hurry Love.flac
        ├── 02 - Culture Club - Karma Chameleon.flac
        └── ...
```

---

## Naming Configuration

### Python Configuration Model

```python
from dataclasses import dataclass
from enum import Enum


class ColonReplacement(Enum):
    DELETE = ""
    DASH = " -"
    SPACE_DASH = " -"
    SPACE_DASH_SPACE = " - "


class MultiDiscStyle(Enum):
    PREFIX = "prefix"           # 01-01 - Track.flac
    SUBFOLDER = "subfolder"     # Disc 1/01 - Track.flac


@dataclass
class NamingConfig:
    """
    # Hey future me – these settings mirror Lidarr's naming config.
    # Be careful with colons (illegal on Windows) and watch out for
    # reserved characters in filenames across OS platforms.
    """
    # Rename files
    rename_tracks: bool = True

    # Replace illegal characters
    replace_illegal_characters: bool = True
    colon_replacement: ColonReplacement = ColonReplacement.SPACE_DASH_SPACE

    # Folder formats
    artist_folder_format: str = "{Artist Name}"
    album_folder_format: str = "{Album Title} ({Release Year})"

    # Track formats
    standard_track_format: str = "{Track Number:00} - {Track Title}"
    multi_disc_track_format: str = "{Medium:00}-{Track Number:00} - {Track Title}"

    # Various artists
    include_artist_name: bool = False
    various_artist_track_format: str = "{Track Number:00} - {Artist Name} - {Track Title}"

    # Multi-disc handling
    multi_disc_style: MultiDiscStyle = MultiDiscStyle.PREFIX
    multi_disc_folder_format: str = "Disc {Medium}"

    def get_track_format(self, is_multi_disc: bool, is_various_artists: bool) -> str:
        """Get the appropriate track format based on album type."""
        if is_various_artists:
            return self.various_artist_track_format
        if is_multi_disc:
            return self.multi_disc_track_format
        return self.standard_track_format
```

### Naming Service

```python
import re
from pathlib import Path


class NamingService:
    """
    # Hey future me – token replacement is regex-heavy. The ILLEGAL_CHARS
    # pattern handles Windows/Unix differences. Always sanitize AFTER
    # token replacement, not before!
    """

    ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    TOKEN_PATTERN = re.compile(r'\{([^}]+)\}')

    def __init__(self, config: NamingConfig):
        self.config = config

    def build_artist_path(self, artist: Artist, root_folder: str) -> Path:
        """Build the full path for an artist folder."""
        folder_name = self._format_string(self.config.artist_folder_format, artist=artist)
        folder_name = self._sanitize_filename(folder_name)
        return Path(root_folder) / folder_name

    def build_album_path(self, album: Album, artist_path: Path) -> Path:
        """Build the full path for an album folder."""
        folder_name = self._format_string(
            self.config.album_folder_format,
            album=album,
            artist=album.artist,
        )
        folder_name = self._sanitize_filename(folder_name)
        return artist_path / folder_name

    def build_track_filename(
        self,
        track: Track,
        track_file: TrackFile,
        is_multi_disc: bool = False,
        is_various_artists: bool = False,
    ) -> str:
        """Build the filename for a track file."""
        format_str = self.config.get_track_format(is_multi_disc, is_various_artists)

        filename = self._format_string(
            format_str,
            track=track,
            album=track.album,
            artist=track.artist,
            quality=track_file.quality,
        )
        filename = self._sanitize_filename(filename)

        # Add extension
        extension = Path(track_file.path).suffix
        return f"{filename}{extension}"

    def _format_string(self, format_str: str, **context) -> str:
        """Replace tokens in format string with actual values."""
        def replace_token(match):
            token = match.group(1)
            return self._get_token_value(token, context)

        return self.TOKEN_PATTERN.sub(replace_token, format_str)

    def _get_token_value(self, token: str, context: dict) -> str:
        """Get the value for a specific token."""
        # Handle padding modifiers
        padding = None
        if ":" in token:
            token, padding = token.split(":", 1)

        # Map tokens to values
        value = self._resolve_token(token, context)

        # Apply padding
        if padding is not None and isinstance(value, int):
            value = str(value).zfill(len(padding) + 1)

        return str(value)

    def _resolve_token(self, token: str, context: dict) -> str:
        """Resolve a token name to its value from context."""
        token_map = {
            # Artist tokens
            "Artist Name": lambda c: c.get("artist", {}).get("artist_name", "Unknown Artist"),
            "Artist CleanName": lambda c: c.get("artist", {}).get("clean_name", "unknownartist"),
            "Artist SortName": lambda c: c.get("artist", {}).get("sort_name", "Unknown Artist"),

            # Album tokens
            "Album Title": lambda c: c.get("album", {}).get("title", "Unknown Album"),
            "Album CleanTitle": lambda c: c.get("album", {}).get("clean_title", "unknownalbum"),
            "Album Type": lambda c: c.get("album", {}).get("album_type", "Album"),
            "Release Year": lambda c: self._get_year(c.get("album", {}).get("release_date")),
            "Release Date": lambda c: c.get("album", {}).get("release_date", ""),

            # Track tokens
            "Track Title": lambda c: c.get("track", {}).get("title", "Unknown Track"),
            "Track Number": lambda c: c.get("track", {}).get("track_number", 0),

            # Medium tokens
            "Medium": lambda c: c.get("track", {}).get("medium_number", 1),

            # Quality tokens
            "Quality Full": lambda c: c.get("quality", {}).get("name", "Unknown"),
        }

        resolver = token_map.get(token)
        if resolver:
            # Convert model objects to dicts if needed
            ctx = {}
            for key, val in context.items():
                if hasattr(val, "__dict__"):
                    ctx[key] = val.__dict__
                else:
                    ctx[key] = val
            return resolver(ctx)

        return f"{{{token}}}"  # Return unchanged if unknown

    def _get_year(self, date_str: str | None) -> str:
        """Extract year from a date string."""
        if not date_str:
            return "Unknown"
        return date_str[:4]

    def _sanitize_filename(self, filename: str) -> str:
        """Remove or replace illegal characters in filename."""
        if not self.config.replace_illegal_characters:
            return filename

        # Replace colons based on config
        filename = filename.replace(":", self.config.colon_replacement.value)

        # Remove other illegal characters
        filename = self.ILLEGAL_CHARS.sub("", filename)

        # Trim whitespace and dots from ends (Windows requirement)
        filename = filename.strip(" .")

        return filename
```

---

## Rename Preview & Execution

### Rename Service

```python
from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass
class RenamePreview:
    track_file_id: int
    artist_id: int
    album_id: int
    track_numbers: list[int]
    existing_path: str
    new_path: str
    needs_rename: bool


class RenameService:
    """
    # Hey future me – file operations are DANGEROUS. Always preview first,
    # and use atomic moves where possible. The preview should catch all
    # edge cases before any files are touched.
    """

    def __init__(self, naming_service: NamingService):
        self.naming = naming_service

    async def preview_rename(
        self,
        artist_id: int,
        album_id: int | None = None,
    ) -> list[RenamePreview]:
        """Generate rename previews for an artist or album."""
        previews = []

        artist = await self._get_artist(artist_id)
        albums = await self._get_albums(artist_id, album_id)

        for album in albums:
            is_multi_disc = self._is_multi_disc(album)
            is_various = self._is_various_artists(album)

            for track_file in album.track_files:
                new_path = self._calculate_new_path(
                    track_file,
                    artist,
                    album,
                    is_multi_disc,
                    is_various,
                )

                previews.append(RenamePreview(
                    track_file_id=track_file.id,
                    artist_id=artist.id,
                    album_id=album.id,
                    track_numbers=[t.track_number for t in track_file.tracks],
                    existing_path=track_file.path,
                    new_path=str(new_path),
                    needs_rename=track_file.path != str(new_path),
                ))

        return [p for p in previews if p.needs_rename]

    async def execute_rename(self, previews: list[RenamePreview]) -> RenameResult:
        """Execute file renames based on previews."""
        success = []
        failed = []

        for preview in previews:
            try:
                source = Path(preview.existing_path)
                target = Path(preview.new_path)

                # Create target directory if needed
                target.parent.mkdir(parents=True, exist_ok=True)

                # Perform the rename/move
                shutil.move(str(source), str(target))

                # Update database
                await self._update_track_file_path(preview.track_file_id, str(target))

                success.append(preview)

            except Exception as e:
                failed.append((preview, str(e)))

        return RenameResult(
            successful=len(success),
            failed=len(failed),
            failures=failed,
        )

    def _calculate_new_path(
        self,
        track_file: TrackFile,
        artist: Artist,
        album: Album,
        is_multi_disc: bool,
        is_various_artists: bool,
    ) -> Path:
        """Calculate the new path for a track file."""
        # Get the track (first one for multi-track files)
        track = track_file.tracks[0]

        # Build path components
        artist_path = self.naming.build_artist_path(artist, artist.root_folder_path)
        album_path = self.naming.build_album_path(album, artist_path)
        filename = self.naming.build_track_filename(
            track,
            track_file,
            is_multi_disc,
            is_various_artists,
        )

        return album_path / filename
```

---

## API Endpoints

### Get Naming Config

```http
GET /api/v1/config/naming
```

### Update Naming Config

```http
PUT /api/v1/config/naming
Content-Type: application/json

{
  "renameTrack": true,
  "replaceIllegalCharacters": true,
  "colonReplacementFormat": " - ",
  "artistFolderFormat": "{Artist Name}",
  "albumFolderFormat": "{Album Title} ({Release Year})",
  "standardTrackFormat": "{Track Number:00} - {Track Title}",
  "multiDiscTrackFormat": "{Medium:00}-{Track Number:00} - {Track Title}"
}
```

### Preview Naming

```http
GET /api/v1/config/naming/examples
```

Returns example paths based on current config:

```json
{
  "artistFolderExample": "Michael Jackson",
  "albumFolderExample": "Thriller (1982)",
  "trackExample": "01 - Wanna Be Startin' Somethin'.flac",
  "multiDiscTrackExample": "01-05 - Billie Jean.flac"
}
```

---

## Media Server Compatibility

### Plex

Plex prefers:
```
/music/{Artist}/{Album} ({Year})/01 - {Track}.flac
```

### Jellyfin / Emby

Jellyfin prefers:
```
/music/{Artist}/{Album}/01 - {Track}.flac
```

### Navidrome

Navidrome is flexible but benefits from:
```
/music/{Artist}/{Album} ({Year})/01 - {Track}.flac
```

### Recommended Universal Format

For maximum compatibility:

```python
NamingConfig(
    artist_folder_format="{Artist Name}",
    album_folder_format="{Album Title} ({Release Year})",
    standard_track_format="{Track Number:00} - {Track Title}",
    multi_disc_track_format="{Medium:00}-{Track Number:00} - {Track Title}",
)
```

---

## Character Handling

### Reserved Characters by OS

| OS | Reserved Characters |
|----|---------------------|
| Windows | `< > : " / \ | ? *` |
| macOS | `:` (shows as `/` in Finder) |
| Linux | `/` and `NUL` |

### Replacement Rules

```python
REPLACEMENTS = {
    ":": " -",     # Colon to space-dash
    "/": "-",      # Slash to dash
    "\\": "-",     # Backslash to dash
    "<": "",       # Remove
    ">": "",       # Remove
    '"': "'",      # Double to single quote
    "|": "-",      # Pipe to dash
    "?": "",       # Remove
    "*": "",       # Remove
}
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-28  
**Status**: Draft
