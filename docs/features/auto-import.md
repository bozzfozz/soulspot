# Auto-Import Service

> **Version:** 1.0  
> **Status:** ✅ Active  
> **Last Updated:** 2025-12-12  
> **Service:** `src/soulspot/application/services/auto_import.py`

---

## Overview

Der Auto-Import Service ist ein Background-Worker, der den Downloads-Ordner überwacht und fertig heruntergeladene Musikdateien automatisch in die organisierte Musikbibliothek verschiebt.

**Workflow:**
1. 📥 Soulseek lädt Tracks nach `/downloads` herunter
2. ⏱️ Service wartet 5 Sekunden (File Stability Check)
3. 🔍 Post-Processing Pipeline: Metadaten, Artwork, Naming
4. 📂 Verschiebt Datei nach `/music/Artist/Album/Track.mp3`
5. 🔄 Wiederholt alle 60 Sekunden

---

## Key Features

- **Automatic Monitoring**: Poll-based Überwachung des Download-Ordners (konfigurierbar)
- **File Stability Check**: Wartet bis Datei nicht mehr modifiziert wird (verhindert Partial Downloads)
- **Post-Processing Pipeline**: Integriertes Metadata Enrichment, Artwork Download, Dynamic Naming
- **Multi-Format Support**: Unterstützt 10+ Audio-Formate (MP3, FLAC, M4A, OGG, etc.)
- **Dynamic Naming Templates**: Runtime-konfigurierbare Dateinamen via Settings UI
- **Spotify Artwork Integration**: High-Quality Artwork direkt von Spotify API
- **Safe File Handling**: Atomic moves, keine Datenkorruption

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Auto-Import Worker                         │
│                                                              │
│  1. Poll /downloads every 60s                               │
│  2. Find audio files (*.mp3, *.flac, *.m4a, etc.)          │
│  3. Check file stability (5s no modifications)              │
│  4. Run Post-Processing Pipeline:                           │
│     ├─ Metadata Enrichment (MusicBrainz, Spotify)          │
│     ├─ Artwork Download (Spotify API)                       │
│     ├─ Dynamic Naming (DB templates)                        │
│     └─ Folder Structure Organization                        │
│  5. Move to /music/{Artist}/{Album}/{Track}.{ext}          │
│  6. Update DB repositories (Track, Artist, Album)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# Storage Paths
SOULSPOT_DOWNLOAD_PATH=/mnt/downloads  # Where Soulseek downloads to
SOULSPOT_MUSIC_PATH=/mnt/music        # Organized music library

# Auto-Import Settings
AUTO_IMPORT_ENABLED=true              # Enable/disable auto-import
AUTO_IMPORT_POLL_INTERVAL=60          # Seconds between directory scans
AUTO_IMPORT_STABILITY_DELAY=5         # Seconds to wait before processing file

# Dynamic Naming (optional - can be configured via Settings UI)
NAMING_FOLDER_TEMPLATE="{albumartist}/{album}"
NAMING_FILE_TEMPLATE="{tracknumber} - {title}"
```

### Service Initialization

```python
from soulspot.application.services.auto_import import AutoImportService
from soulspot.config import Settings

settings = Settings()
service = AutoImportService(
    settings=settings,
    track_repository=track_repo,
    artist_repository=artist_repo,
    album_repository=album_repo,
    poll_interval=60,  # Check every 60 seconds
    post_processing_pipeline=pipeline,  # Optional custom pipeline
    spotify_client=spotify,  # For Spotify artwork
    app_settings_service=app_settings  # For dynamic naming templates
)

# Start monitoring (background task)
await service.start()

# Stop monitoring
await service.stop()
```

---

## Supported Audio Formats

Der Service unterstützt folgende Audio-Formate automatisch:

| Format | Extension | Common Quality | Notes |
|--------|-----------|----------------|-------|
| MP3 | `.mp3` | 128-320 kbps | Most common format |
| FLAC | `.flac` | Lossless | High-quality lossless |
| M4A/AAC | `.m4a`, `.aac` | 128-256 kbps | Apple ecosystem |
| Ogg Vorbis | `.ogg` | 128-320 kbps | Open format |
| Opus | `.opus` | 64-256 kbps | Modern codec |
| WAV | `.wav` | Lossless | Uncompressed |
| WMA | `.wma` | 128-320 kbps | Windows Media |
| APE | `.ape` | Lossless | Monkey's Audio |
| ALAC | `.alac` | Lossless | Apple Lossless |

**Total:** 10 Formate automatisch erkannt und verarbeitet.

---

## Post-Processing Pipeline Integration

### What Happens During Processing?

#### 1. Metadata Enrichment
```python
# Liest bestehende ID3/Vorbis Tags aus Datei
# Fetcht zusätzliche Metadaten von MusicBrainz/Spotify
# Merged beide Quellen (Conflict Resolution)
# Schreibt erweiterte Tags zurück in Datei
```

#### 2. Artwork Download
```python
# Spotify API: High-Quality Album Cover (640x640)
# MusicBrainz/CoverArtArchive: Fallback
# Einbettung als Cover Art in Audio-Datei
# Separate cover.jpg im Album-Ordner
```

#### 3. Dynamic Naming
```python
# Templates aus Settings DB laden (falls app_settings_service vorhanden)
# Fallback zu Env-Var Templates
# Token-Ersetzung: {artist}, {album}, {title}, {tracknumber}, etc.
# Safe Filename Cleaning (/, \, :, etc. entfernen)
```

**Beispiel Naming:**
```
Template: "{albumartist}/{album}/{tracknumber} - {title}"
Input: "Radiohead - OK Computer - 01 - Airbag.mp3"
Output: "/music/Radiohead/OK Computer/01 - Airbag.mp3"
```

### Custom Pipeline Configuration

```python
from soulspot.application.services.postprocessing.pipeline import PostProcessingPipeline

# Custom pipeline with specific settings
pipeline = PostProcessingPipeline(
    settings=settings,
    artist_repository=artist_repo,
    album_repository=album_repo,
    spotify_client=spotify,  # Enable Spotify artwork
    app_settings_service=app_settings,  # Enable dynamic naming
    enable_metadata_enrichment=True,
    enable_artwork_download=True,
    enable_dynamic_naming=True
)

service = AutoImportService(
    settings=settings,
    track_repository=track_repo,
    artist_repository=artist_repo,
    album_repository=album_repo,
    post_processing_pipeline=pipeline  # Use custom pipeline
)
```

---

## File Stability Detection

### Why 5 Second Wait?

**Problem:** Soulseek schreibt Dateien schrittweise (Download während Transfer)

**Ohne Stability Check:**
```
❌ File detected → Immediate move → Partial file → Corrupted!
```

**Mit Stability Check:**
```
✅ File detected → Wait 5s → No modification → Safe to move
```

### How It Works

```python
async def _is_file_stable(self, file_path: Path) -> bool:
    """Check if file hasn't been modified in last 5 seconds."""
    try:
        mtime = file_path.stat().st_mtime
        age = time.time() - mtime
        return age >= 5.0  # File stable for 5+ seconds
    except OSError:
        return False  # File disappeared or inaccessible
```

**Konfigurierbar via Constructor:**
```python
service = AutoImportService(
    ...,
    stability_delay=10  # Wait 10 seconds instead of 5
)
```

---

## Dynamic Naming Templates

### What Are Naming Templates?

Naming Templates definieren, wie Dateien und Ordner organisiert werden.

**Folder Template:** Ordnerstruktur unter `/music`  
**File Template:** Dateiname für jeden Track

### Available Tokens

| Token | Example | Description |
|-------|---------|-------------|
| `{artist}` | Radiohead | Track artist (can differ from album artist) |
| `{albumartist}` | Radiohead | Album artist (consistent for whole album) |
| `{album}` | OK Computer | Album title |
| `{title}` | Airbag | Track title |
| `{tracknumber}` | 01 | Track number (zero-padded) |
| `{year}` | 1997 | Release year |
| `{genre}` | Alternative Rock | Genre tag |
| `{discnumber}` | 1 | Disc number (multi-disc albums) |

### Configuration Modes

#### 1. Static (Environment Variables)
```bash
NAMING_FOLDER_TEMPLATE="{albumartist}/{album}"
NAMING_FILE_TEMPLATE="{tracknumber} - {title}"
```

**Result:** `/music/Radiohead/OK Computer/01 - Airbag.mp3`

#### 2. Dynamic (Settings UI - Preferred)
```python
# Pass app_settings_service to enable runtime configuration
service = AutoImportService(
    ...,
    app_settings_service=app_settings  # Enables DB-driven templates
)

# Templates can be changed via Settings UI without restart!
```

**Result:** Templates werden aus `settings` DB-Table geladen

### Custom Template Examples

#### Classic Structure
```
Folder: "{albumartist}/{album}"
File: "{tracknumber} - {title}"
Result: /music/Pink Floyd/The Wall/01 - In The Flesh.mp3
```

#### Year-Organized
```
Folder: "{albumartist}/{year} - {album}"
File: "{tracknumber}. {title}"
Result: /music/Pink Floyd/1979 - The Wall/01. In The Flesh.mp3
```

#### Genre-Organized
```
Folder: "{genre}/{albumartist}/{album}"
File: "{title}"
Result: /music/Rock/Pink Floyd/The Wall/In The Flesh.mp3
```

#### Multi-Disc Support
```
Folder: "{albumartist}/{album}/Disc {discnumber}"
File: "{tracknumber} - {title}"
Result: /music/Pink Floyd/The Wall/Disc 1/01 - In The Flesh.mp3
```

---

## Integration with Spotify Client

### Why Spotify Integration?

**High-Quality Artwork:**
- Spotify API liefert 640x640 Cover Art
- Bessere Qualität als MusicBrainz (oft 500x500)
- Aktuellere Covers für neue Releases

### Usage

```python
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

spotify = SpotifyClient(
    client_id=settings.spotify.client_id,
    client_secret=settings.spotify.client_secret
)

service = AutoImportService(
    ...,
    spotify_client=spotify  # Enable Spotify artwork downloads
)
```

**Fallback Strategy:**
```
1. Try Spotify API (if client provided and authenticated)
2. Fall back to MusicBrainz/CoverArtArchive
3. If all fail, no artwork (file still imported)
```

---

## Background Worker Lifecycle

### Start/Stop Management

```python
# Start auto-import worker
await service.start()
# → Begins polling loop in background

# Check if running
if service.is_running():
    print("Auto-import active")

# Stop worker gracefully
await service.stop()
# → Finishes current file processing, then exits
```

### Integration with FastAPI

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start auto-import worker
    await auto_import_service.start()
    yield
    # Shutdown: Stop auto-import worker
    await auto_import_service.stop()

app = FastAPI(lifespan=lifespan)
```

### Worker State Persistence

```python
# Worker maintains in-memory state during runtime
# On restart, resumes from current state (no DB persistence needed)
# Uses repositories to update Track/Artist/Album entities
```

---

## Error Handling

### Common Issues

#### 1. Permission Denied
**Symptom:** Cannot move file from `/downloads` to `/music`  
**Cause:** Insufficient file permissions  
**Solution:**
```bash
# Fix permissions
chmod -R 755 /mnt/downloads /mnt/music
chown -R $USER:$USER /mnt/downloads /mnt/music
```

#### 2. Duplicate Files
**Symptom:** File already exists in `/music`  
**Behavior:** Skips import, logs warning, continues  
**Prevention:** Enable duplicate detection in Library Management

#### 3. Corrupted Files
**Symptom:** Audio file cannot be read (invalid format)  
**Behavior:** Logs error, moves to `/downloads/failed/`, continues  
**Recovery:** Manual review of `/downloads/failed/` folder

#### 4. Metadata Fetch Failure
**Symptom:** Cannot fetch MusicBrainz/Spotify metadata  
**Behavior:** Imports file with basic tags from audio file, logs warning  
**Impact:** File still organized, but metadata incomplete

#### 5. Artwork Download Failure
**Symptom:** Cannot download album artwork  
**Behavior:** Imports file without artwork, logs warning  
**Impact:** Playback works, but no cover art displayed

---

## Performance Considerations

### Poll Interval Tuning

**Default:** 60 seconds

**Lower Interval (faster detection):**
```python
service = AutoImportService(..., poll_interval=30)  # 30 seconds
# Pros: Faster imports
# Cons: More CPU usage, more directory scans
```

**Higher Interval (resource-saving):**
```python
service = AutoImportService(..., poll_interval=120)  # 2 minutes
# Pros: Less CPU usage
# Cons: Slower imports
```

### Batch Processing

For large download queues:

```python
# Service automatically processes all ready files in single scan
# No need for manual batch configuration
# Each file processed sequentially to avoid race conditions
```

### Disk I/O Optimization

```python
# Atomic file moves (shutil.move) ensure no corruption
# Moves within same filesystem are instant (no copy)
# Cross-filesystem moves trigger copy+delete (slower)
```

**Best Practice:** Mount `/downloads` and `/music` on same filesystem

---

## Monitoring & Logging

### Log Messages

```python
# Successful import
logger.info(f"[AUTO-IMPORT] Imported: {filename} → {destination}")

# File stability check
logger.debug(f"[AUTO-IMPORT] Waiting for file stability: {filename}")

# Skipped file (duplicate)
logger.warning(f"[AUTO-IMPORT] Skipped duplicate: {filename}")

# Failed import
logger.error(f"[AUTO-IMPORT] Failed to import {filename}: {error}")
```

### Metrics Integration

```python
# Service can report stats via /api/stats endpoint
total_imported_files = service.get_imported_count()
failed_files = service.get_failed_count()
current_status = service.is_running()
```

---

## Related Features

- **[Download Management](./download-management.md)** - Soulseek Download Queue
- **[Library Management](./library-management.md)** - Library Scan & Organization
- **[Metadata Enrichment](./metadata-enrichment.md)** - Metadata Sources
- **[Settings](./settings.md)** - Dynamic Naming Templates Configuration

---

## Troubleshooting

### Worker Not Starting
**Symptoms:** Auto-import never processes files  
**Check:**
```python
# 1. Verify worker is running
await service.start()
assert service.is_running()

# 2. Check logs for startup errors
tail -f /var/log/soulspot/auto-import.log

# 3. Verify paths exist
assert Path(settings.storage.download_path).exists()
assert Path(settings.storage.music_path).exists()
```

### Files Not Moving
**Symptoms:** Files stay in `/downloads` forever  
**Causes:**
1. File not stable (still downloading) → Wait 5s+ after download complete
2. Unsupported format → Check `_audio_extensions` list
3. Permission error → Check file permissions (`chmod 644`)
4. Duplicate file → Check library for existing file

### Incorrect Naming
**Symptoms:** Files organized with wrong structure  
**Check:**
```bash
# 1. Verify templates
echo $NAMING_FOLDER_TEMPLATE
echo $NAMING_FILE_TEMPLATE

# 2. Check Settings UI (if using dynamic naming)
curl http://localhost:8765/api/settings/naming

# 3. Verify metadata in audio file
ffprobe /mnt/downloads/file.mp3
```

### Missing Artwork
**Symptoms:** Files imported without cover art  
**Causes:**
1. Spotify client not configured → Pass `spotify_client` to service
2. API rate limit → Wait 1 minute, artwork fetch resumes
3. Album not in Spotify/MusicBrainz → Manual artwork add required

---

**Version:** 1.0 · **Status:** Active · **Service:** `auto_import.py`
