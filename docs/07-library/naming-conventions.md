# Naming Conventions

**Category:** Library Management  
**Status:** 🚧 Draft  
**Last Updated:** 2025-11-28  
**Related Docs:** [Lidarr Integration](./lidarr-integration.md) | [Auto-Import](../06-features/auto-import.md)

---

## Overview

Defines naming conventions for organizing music files on disk. A well-structured naming system enables:

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
| `{Artist MbId}` | MusicBrainz Artist ID | `f27ec8db-af05...` |
| `{Artist Genre}` | Primary genre | `Pop` |

---

### Album Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Album Title}` | Album title | `Thriller` |
| `{Album CleanTitle}` | URL-safe title | `thriller` |
| `{Album Type}` | Album type | `Album`, `EP`, `Single` |
| `{Release Year}` | Release year | `1982` |
| `{Release Date}` | Full date | `1982-11-30` |
| `{Original Year}` | Original release year | `1982` |

---

### Track Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Track Title}` | Track title | `Billie Jean` |
| `{Track CleanTitle}` | URL-safe title | `billiejean` |
| `{Track Number}` | Track number (padded) | `05` |
| `{Track Number:0}` | Track number (no padding) | `5` |
| `{Track Number:00}` | Track number (2 digits) | `05` |

---

### Disc Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Medium}` | Disc number | `1` |
| `{Medium:0}` | Disc number (no padding) | `1` |
| `{Medium:00}` | Disc number (2 digits) | `01` |
| `{Medium Format}` | Disc format | `CD`, `Vinyl` |

---

### Quality Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{Quality Full}` | Full quality name | `FLAC` |
| `{MediaInfo AudioCodec}` | Audio codec | `FLAC`, `MP3` |
| `{MediaInfo AudioBitrate}` | Bitrate | `320`, `1411` |
| `{MediaInfo AudioBitsPerSample}` | Bit depth | `16`, `24` |
| `{MediaInfo AudioSampleRate}` | Sample rate | `44100`, `96000` |

---

## Standard Naming Formats

### Artist Folder

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

---

### Album Folder

**Recommended:**
```
{Album Title} ({Release Year})
```

**Examples:**
```
Thriller (1982)
Abbey Road (1969)
```

**With Quality:**
```
{Album Title} ({Release Year}) [{Quality Full}]
```

**Examples:**
```
Thriller (1982) [FLAC]
Abbey Road (1969) [320kbps]
```

---

### Track Files

**Standard (Single Disc):**
```
{Track Number:00} - {Track Title}
Example: 05 - Billie Jean.flac
```

**Multi-Disc:**
```
{Medium:00}-{Track Number:00} - {Track Title}
Example: 02-05 - Birthday.flac
```

**Various Artists:**
```
{Track Number:00} - {Artist Name} - {Track Title}
Example: 01 - Phil Collins - You Can't Hurry Love.flac
```

---

## Configuration

### SoulSpot Settings

```bash
# Folder templates
NAMING_FOLDER_TEMPLATE="{albumartist}/{album}"

# File templates
NAMING_FILE_TEMPLATE="{tracknumber} - {title}"
NAMING_FILE_TEMPLATE_MULTICD="{discnumber}-{tracknumber} - {title}"
```

---

### Runtime Configuration

Settings can be changed via Settings UI:

1. Navigate to **Settings** → **Library**
2. Edit **Folder Template**
3. Edit **File Template**
4. Click **Save**

Changes take effect for new imports immediately (no restart needed).

---

## Template Examples

### Minimal

```
Folder: {albumartist}/{album}
File:   {tracknumber} - {title}

Result:
/music/Michael Jackson/Thriller/05 - Billie Jean.flac
```

---

### With Year

```
Folder: {albumartist}/{album} ({year})
File:   {tracknumber} - {title}

Result:
/music/Michael Jackson/Thriller (1982)/05 - Billie Jean.flac
```

---

### With Quality

```
Folder: {albumartist}/{album} ({year}) [{quality}]
File:   {tracknumber} - {title}

Result:
/music/Michael Jackson/Thriller (1982) [FLAC]/05 - Billie Jean.flac
```

---

### Multi-Disc with Artist

```
Folder: {albumartist}/{album} ({year})
File:   {discnumber}-{tracknumber} - {artist} - {title}

Result:
/music/Various Artists/Now That's What I Call Music! (1983)/01-01 - Phil Collins - You Can't Hurry Love.flac
```

---

## Safe Filename Cleaning

Forbidden characters automatically removed/replaced:

| Character | Replacement |
|-----------|-------------|
| `/` | `_` |
| `\` | `_` |
| `:` | `-` |
| `*` | `` |
| `?` | `` |
| `"` | `'` |
| `<` | `(` |
| `>` | `)` |
| `|` | `-` |

**Example:**
```
Input:  What's Going On?
Output: What's Going On
```

---

## Related Documentation

- **[Lidarr Integration](./lidarr-integration.md)** - Lidarr compatibility
- **[Auto-Import](../06-features/auto-import.md)** - Dynamic naming in action

---

**Last Validated:** 2025-11-28  
**Implementation Status:** 🚧 Draft
