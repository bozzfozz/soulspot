# SoulSpot - Service Layer Reorganization Plan

## Status: IMAGE SERVICE MIGRATION COMPLETE ✅

### Completed (January 2025):
- ✅ `images/` folder created with ImageService (Phase 1)
- ✅ Interface defined in `domain/ports/image_service.py`
- ✅ Exports added to `services/__init__.py`
- ✅ **FULL ArtworkService → ImageService migration (Phase 3)**
- ✅ SpotifySyncService migrated to ImageService
- ✅ SpotifySyncWorker migrated to ImageService
- ✅ LocalLibraryEnrichmentService migrated to ImageService
- ✅ EnrichmentService migrated to ImageService
- ✅ settings.py endpoints migrated to ImageService
- ✅ library.py endpoints migrated to ImageService
- ✅ `artwork_service.py` marked as DEPRECATED (can be deleted)

### Next Steps:
- [ ] Delete `artwork_service.py` (no more consumers)
- [ ] Full reorganization (optional, ~7-8h)

### Usage (New Code):
```python
from soulspot.application.services.images import (
    ImageService,
    ImageDownloadErrorCode,
    ImageDownloadResult,
)

# For templates
image_service = ImageService()
url = image_service.get_display_url(source_url, local_path, "artist")

# For downloads (provider-based)
path = await image_service.download_artist_image(spotify_id, url)

# For batch operations with error tracking
result = await image_service.download_artist_image_with_result(id, url)
if result.success:
    print(f"Saved to: {result.path}")
else:
    print(f"Error: {result.error_code} - {result.error_message}")
```

---

## Problem

Der `application/services` Ordner hat **43 Dateien** - zu viele lose Dateien!

```
services/
├── __init__.py
├── advanced_search.py
├── album_completeness.py
├── album_sync_service.py
├── app_settings_service.py
├── artist_songs_service.py
├── artwork_service.py
├── auto_import.py
├── automation_workflow_service.py
├── batch_processor.py
├── charts_service.py
├── ... (43 files total!)
```

## Lösung: Feature-basierte Ordnerstruktur

```
services/
├── __init__.py                    # Re-exports für Abwärtskompatibilität
│
├── core/                          # Kern-Services (immer benötigt)
│   ├── __init__.py
│   ├── settings_service.py        # app_settings_service.py
│   ├── credentials_service.py
│   ├── session_store.py
│   └── token_manager.py
│
├── sync/                          # Provider-Sync (Spotify, Deezer, etc.)
│   ├── __init__.py
│   ├── spotify/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # spotify_auth_service.py
│   │   ├── sync_service.py        # spotify_sync_service.py
│   │   └── session_service.py
│   ├── deezer/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # deezer_auth_service.py
│   │   └── sync_service.py        # deezer_sync_service.py
│   └── orchestrator.py            # provider_sync_orchestrator.py
│
├── images/                        # Bild-Handling (NEU!)
│   ├── __init__.py
│   ├── image_service.py           # Zentraler Service
│   ├── downloader.py              # Download-Logik
│   ├── cache.py                   # Cache-Management
│   └── artwork_service.py         # Legacy (deprecated)
│
├── library/                       # Lokale Bibliothek
│   ├── __init__.py
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── scanner_service.py     # library_scanner_service.py
│   │   ├── file_discovery.py      # file_discovery_service.py
│   │   └── scanner.py             # library_scanner.py
│   ├── view_service.py            # library_view_service.py
│   ├── cleanup_service.py         # library_cleanup_service.py
│   └── enrichment_service.py      # local_library_enrichment_service.py
│
├── automation/                    # Automatisierung
│   ├── __init__.py
│   ├── watchlist_service.py
│   ├── filter_service.py
│   ├── workflow_service.py        # automation_workflow_service.py
│   ├── auto_import.py
│   └── quality_upgrade_service.py
│
├── downloads/                     # Download-Management
│   ├── __init__.py
│   ├── manager_service.py         # download_manager_service.py
│   ├── batch_processor.py
│   └── postprocessing/            # Bleibt ein Unterordner
│       ├── __init__.py
│       ├── metadata_service.py
│       └── ...
│
├── discovery/                     # Musik-Entdeckung
│   ├── __init__.py
│   ├── discover_service.py
│   ├── new_releases_service.py
│   ├── charts_service.py
│   └── advanced_search.py
│
├── metadata/                      # Metadaten-Handling
│   ├── __init__.py
│   ├── enrichment_service.py      # enrichment_service.py
│   ├── discography_service.py
│   ├── album_completeness.py
│   ├── duplicate_service.py
│   ├── metadata_merger.py
│   └── compilation_analyzer.py
│
├── artists/                       # Artist-spezifisch
│   ├── __init__.py
│   ├── songs_service.py           # artist_songs_service.py
│   └── followed_service.py        # followed_artists_service.py
│
├── playlists/                     # Playlist-spezifisch
│   ├── __init__.py
│   └── playlist_service.py
│
└── stats/                         # Statistiken
    ├── __init__.py
    └── stats_service.py
```

## Kategorisierung der 43 Dateien

| Kategorie | Dateien | Ordner |
|-----------|---------|--------|
| **Core** | `app_settings_service`, `credentials_service`, `session_store`, `token_manager` | `core/` |
| **Sync** | `spotify_*`, `deezer_*`, `album_sync_service`, `provider_*` | `sync/` |
| **Images** | `artwork_service` + NEU | `images/` |
| **Library** | `library_*`, `file_discovery`, `local_library_enrichment` | `library/` |
| **Automation** | `auto_import`, `watchlist`, `filter`, `quality_upgrade`, `automation_workflow` | `automation/` |
| **Downloads** | `download_manager`, `batch_processor`, `postprocessing/` | `downloads/` |
| **Discovery** | `discover_service`, `new_releases`, `charts`, `advanced_search` | `discovery/` |
| **Metadata** | `enrichment`, `discography`, `album_completeness`, `duplicate`, `metadata_merger`, `compilation_analyzer` | `metadata/` |
| **Artists** | `artist_songs`, `followed_artists` | `artists/` |
| **Playlists** | `playlist_service` | `playlists/` |
| **Stats** | `stats_service`, `notification_service` | `stats/` |
| **Unused?** | `widget_template_registry` | ENTFERNEN? |

## Migration Strategy

### Phase 1: Erstelle neue Ordnerstruktur (OHNE Code zu verschieben) ✅

```bash
mkdir -p src/soulspot/application/services/{core,sync/spotify,sync/deezer,images,library/scanner,automation,downloads,discovery,metadata,artists,playlists,stats}
```

### Phase 2: Erstelle __init__.py mit Re-Exports ✅

```python
# services/__init__.py - ABWÄRTSKOMPATIBILITÄT!

# Legacy imports (für bestehenden Code) - ENTFERNT (Jan 2025)
# from .artwork_service import ArtworkService  # DELETED - use ImageService!

# New structure imports
from .images import ImageService, ImageDownloadErrorCode, ImageDownloadResult
# ... etc
```

### Phase 3: ArtworkService → ImageService Migration ✅ COMPLETED

All consumers have been migrated:
- SpotifySyncService
- SpotifySyncWorker
- LocalLibraryEnrichmentService
- EnrichmentService
- settings.py endpoints
- library.py endpoints

```python
# VORHER (DEPRECATED)
from soulspot.application.services.artwork_service import ArtworkService
artwork_service = ArtworkService(settings)
path = await artwork_service.download_artist_image(spotify_id, url)

# NACHHER (USE THIS)
from soulspot.application.services.images import ImageService
image_service = ImageService()
path = await image_service.download_artist_image(spotify_id, url)
```

### Phase 4: Delete artwork_service.py ⏳

The file is marked for deletion - no more consumers.

## Aufwand

| Phase | Aufwand | Risiko |
|-------|---------|--------|
| Ordner erstellen | 10 min | Keins |
| __init__.py mit Re-Exports | 1h | Niedrig |
| Dateien verschieben | 2-3h | Mittel (Imports!) |
| Import-Updates | 2-3h | Mittel |
| Tests anpassen | 1h | Niedrig |

**Total: ~7-8 Stunden**

## Vorteile

1. **Navigierbarkeit**: Feature-basiert statt alphabetisch
2. **Wartbarkeit**: Zusammengehöriges zusammen
3. **Skalierbarkeit**: Neue Features → Neuer Ordner
4. **Onboarding**: Einfacher zu verstehen

## Aktueller Stand (Januar 2025)

Die Quick-Win Option wurde erfolgreich umgesetzt:

```
services/
├── images/                        ✅ IMPLEMENTIERT
│   ├── __init__.py               # Exports: ImageService, ImageDownloadResult, etc.
│   └── image_service.py          # ~1200 Zeilen: Download, Cache, WebP, Stats
├── artwork_service.py             🚨 ZUM LÖSCHEN MARKIERT (keine Consumers mehr!)
├── ... (rest bleibt)
```

### ImageService Features:
- `get_display_url()` - Für Templates (sync)
- `download_artist/album/playlist_image()` - Provider-ID basiert
- `download_*_with_result()` - Mit detailliertem Error-Tracking
- `should_redownload()` - URL-Change Detection
- `get_disk_usage()` / `get_image_count()` - Statistiken
- WebP-Konvertierung, Sharding, Cache-Optimierung

### Vollständige Reorganisation (optional)

Sollen wir die vollständige Reorganisation (~7-8h) durchführen?

- [ ] JA - Bessere Struktur ist es wert
- [x] TEILWEISE - Images-Ordner wurde erstellt, weitere Optional

