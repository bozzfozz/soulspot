# Auto-Import

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-12-12  
**Related Docs:** [Download Management](./download-management.md) | [Metadata Enrichment](./metadata-enrichment.md)

---

## Overview

Auto-Import Service is a background worker that monitors the downloads folder and automatically moves finished downloads to the organized music library with metadata enrichment and artwork.

**Workflow:**
```
1. Soulseek downloads tracks to /downloads
   ↓
2. Service waits 5s (file stability check)
   ↓
3. Post-processing pipeline:
   - Metadata enrichment
   - Artwork download
   - Dynamic naming
   ↓
4. Move to /music/Artist/Album/Track.ext
   ↓
5. Repeat every 60s
```

---

## Key Features

- **Automatic Monitoring:** Poll-based folder monitoring (configurable interval)
- **File Stability Check:** Waits until file stops being modified (prevents partial downloads)
- **Post-Processing Pipeline:** Metadata enrichment, artwork, dynamic naming
- **Multi-Format Support:** 10+ audio formats (MP3, FLAC, M4A, OGG, etc.)
- **Dynamic Naming Templates:** Runtime-configurable file names via Settings UI
- **Spotify Artwork Integration:** High-quality artwork from Spotify API
- **Safe File Handling:** Atomic moves, no data corruption

---

## Architecture

```
Auto-Import Worker (Background Service)
  ├─ 1. Poll /downloads every 60s
  ├─ 2. Find audio files (*.mp3, *.flac, *.m4a, etc.)
  ├─ 3. Check file stability (5s no modifications)
  ├─ 4. Run Post-Processing Pipeline:
  │    ├─ Metadata Enrichment (MusicBrainz, Spotify)
  │    ├─ Artwork Download (Spotify API)
  │    ├─ Dynamic Naming (DB templates)
  │    └─ Folder Structure Organization
  ├─ 5. Move to /music/{Artist}/{Album}/{Track}.{ext}
  └─ 6. Update DB repositories (Track, Artist, Album)
```

**Source:** `src/soulspot/application/services/auto_import.py`

---

## Configuration

### Environment Variables

```bash
# Storage Paths
SOULSPOT_DOWNLOAD_PATH=/mnt/downloads  # Soulseek downloads
SOULSPOT_MUSIC_PATH=/mnt/music        # Organized library

# Auto-Import Settings
AUTO_IMPORT_ENABLED=true              # Enable/disable
AUTO_IMPORT_POLL_INTERVAL=60          # Seconds between scans
AUTO_IMPORT_STABILITY_DELAY=5         # Seconds before processing

# Dynamic Naming (optional - configurable via Settings UI)
NAMING_FOLDER_TEMPLATE="{albumartist}/{album}"
NAMING_FILE_TEMPLATE="{tracknumber} - {title}"
```

---

### Service Initialization

```python
from soulspot.application.services.auto_import import AutoImportService

service = AutoImportService(
    settings=settings,
    track_repository=track_repo,
    artist_repository=artist_repo,
    album_repository=album_repo,
    poll_interval=60,  # Check every 60s
    post_processing_pipeline=pipeline,
    spotify_client=spotify,  # For artwork
    app_settings_service=app_settings  # For naming templates
)

await service.start()  # Start monitoring
await service.stop()   # Stop monitoring
```

---

## Supported Audio Formats

| Format | Extension | Quality | Notes |
|--------|-----------|---------|-------|
| MP3 | `.mp3` | 128-320 kbps | Most common |
| FLAC | `.flac` | Lossless | High-quality |
| M4A/AAC | `.m4a`, `.aac` | 128-256 kbps | Apple ecosystem |
| Ogg Vorbis | `.ogg` | 128-320 kbps | Open format |
| Opus | `.opus` | 64-256 kbps | Modern codec |
| WAV | `.wav` | Lossless | Uncompressed |
| WMA | `.wma` | 128-320 kbps | Windows Media |
| APE | `.ape` | Lossless | Monkey's Audio |
| ALAC | `.alac` | Lossless | Apple Lossless |

**Total:** 10 formats automatically recognized and processed.

---

## Post-Processing Pipeline

### 1. Metadata Enrichment

```
- Read existing ID3/Vorbis tags from file
- Fetch additional metadata from MusicBrainz/Spotify
- Merge both sources (conflict resolution)
- Write enhanced tags back to file
```

---

### 2. Artwork Download

```
- Spotify API: High-quality album cover (640x640)
- MusicBrainz/CoverArtArchive: Fallback
- Embed as cover art in audio file
- Save separate cover.jpg in album folder
```

---

### 3. Dynamic Naming

```
- Load templates from Settings DB (if available)
- Fallback to env var templates
- Token replacement: {artist}, {album}, {title}, {tracknumber}
- Safe filename cleaning (remove /, \, :, etc.)
```

**Example:**
```
Template: "{albumartist}/{album}/{tracknumber} - {title}"
Result:   "Pink Floyd/The Wall/01 - In The Flesh.mp3"
```

---

## Naming Template Tokens

| Token | Description | Example |
|-------|-------------|---------|
| `{artist}` | Track artist | "Pink Floyd" |
| `{albumartist}` | Album artist | "Pink Floyd" |
| `{album}` | Album title | "The Wall" |
| `{title}` | Track title | "In The Flesh?" |
| `{tracknumber}` | Track number (padded) | "01" |
| `{year}` | Release year | "1979" |
| `{genre}` | Genre | "Progressive Rock" |
| `{discnumber}` | Disc number | "1" |

**Configure:** Settings → Library → Naming Templates

---

## File Stability Check

**Problem:** Processing files during download causes corruption.

**Solution:** Wait until file stops being modified.

**Implementation:**
```python
async def _is_file_stable(self, file_path: Path) -> bool:
    """Check if file hasn't been modified in 5 seconds."""
    initial_mtime = file_path.stat().st_mtime
    await asyncio.sleep(5)
    current_mtime = file_path.stat().st_mtime
    return initial_mtime == current_mtime
```

---

## Workflow Example

```
1. Soulseek downloads: track.mp3 to /downloads/
   ↓
2. Auto-Import detects file (poll every 60s)
   ↓
3. Stability check (wait 5s, verify no changes)
   ↓
4. Read metadata from file
   ↓
5. Enrich with Spotify/MusicBrainz data
   ↓
6. Download album artwork
   ↓
7. Apply naming template
   ↓
8. Move to /music/Artist/Album/01 - Track.mp3
   ↓
9. Update database repositories
   ↓
10. Original file removed from /downloads
```

---

## Troubleshooting

### Files Not Being Imported

**Causes:**
1. **Auto-import disabled:** Check `AUTO_IMPORT_ENABLED=true`
2. **Wrong format:** Only 10 supported formats processed
3. **File still downloading:** Wait for stability check (5s)
4. **Permission error:** Check folder permissions

**Solution:** Check logs for "Auto-Import" entries.

---

### Files Imported to Wrong Location

**Causes:**
1. **Wrong naming template:** Check Settings → Naming Templates
2. **Missing metadata:** File has no artist/album tags
3. **Invalid characters:** Template contains forbidden characters

**Solution:** Review naming template tokens and metadata.

---

### Duplicate Files Created

**Causes:**
1. **File already exists:** Auto-import doesn't deduplicate
2. **Different metadata:** Same audio, different tags

**Solution:** Use Library Management → Duplicates feature.

---

## Related Documentation

- **[Download Management](./download-management.md)** - Queue and downloads
- **[Metadata Enrichment](./metadata-enrichment.md)** - Enrichment strategies
- **[Library Management](./library-management.md)** - Organize library
- **[Settings](./settings.md)** - Configure auto-import

---

**Last Validated:** 2025-12-12  
**Implementation Status:** ✅ Production-ready
