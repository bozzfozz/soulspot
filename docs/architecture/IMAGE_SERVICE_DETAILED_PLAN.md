# SoulSpot ImageService - Architektur & Dokumentation

**Version:** 2.0 (Konsolidiert)  
**Status:** PHASE 2 ABGESCHLOSSEN ✅  
**Letzte Aktualisierung:** Januar 2025

---

## Übersicht

Der **ImageService** ist der zentrale Dienst für alle Bildoperationen in SoulSpot.

### Was ImageService macht

| Methode | Beschreibung | Aufrufer |
|---------|--------------|----------|
| `get_display_url()` | Beste URL für Anzeige (lokal > CDN > Placeholder) | Templates |
| `get_placeholder()` | Standard-Placeholder für Entity-Typ | Templates |
| `get_image()` | Vollständige Bild-Metadaten abrufen | Services |
| `download_and_cache()` | Bild herunterladen, zu WebP konvertieren, cachen | Sync-Services |
| `validate_image()` | Prüfen ob CDN-URL noch gültig ist | Batch-Jobs |
| `optimize_cache()` | Alte/verwaiste Bilder aufräumen | Cron-Jobs |

### Was ImageService NICHT macht

- ❌ URLs von Providern holen → Das machen **Plugins** (SpotifyPlugin, DeezerPlugin)
- ❌ Provider-spezifische Fallback-Logik → Das machen **Plugins**
- ❌ API-Authentifizierung → Das machen **Plugins**

---

## Architektur

### Schichten-Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                       PRESENTATION LAYER                         │
│                                                                  │
│   Templates (Jinja2)                                            │
│   ├── dashboard.html                                            │
│   ├── playlists.html                                            │
│   └── ...                                                       │
│                                                                  │
│   Ruft auf: get_display_url(source_url, local_path, entity_type)│
│   Bekommt:  "/artwork/local/artists/ab/abc.webp"               │
│             oder "https://i.scdn.co/image/abc" (CDN Fallback)   │
│             oder "/static/images/placeholder-artist.svg"        │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                              │ URL für <img src="...">
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│                                                                  │
│   ImageService                                                  │
│   ├── get_display_url()     ← Sync, für Templates               │
│   ├── get_image()           ← Async, ImageInfo zurückgeben      │
│   ├── download_and_cache()  ← Async, Download + WebP + Cache    │
│   ├── validate_image()      ← Async, HEAD request               │
│   └── optimize_cache()      ← Async, alte Bilder löschen        │
│                                                                  │
│   Intern:                                                       │
│   ├── _download_image()     ← HTTP GET via HttpClientPool       │
│   ├── _convert_to_webp()    ← PIL in Thread-Pool                │
│   ├── _save_to_cache()      ← Filesystem-Schreiben              │
│   └── _update_entity_image_path() ← DB Update                   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                              │ source_url vom Plugin
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     INFRASTRUCTURE LAYER                         │
│                                                                  │
│   Plugins (liefern nur URLs, kein Download!)                    │
│   ├── SpotifyPlugin.get_artist_details()                        │
│   │   └── ArtistDTO { name, image_url, ... }                   │
│   ├── DeezerPlugin.get_album_details()                          │
│   │   └── AlbumDTO { title, cover_url, ... }                   │
│   └── ...                                                       │
│                                                                  │
│   HttpClientPool (für Downloads)                                │
│   └── Shared httpx.AsyncClient mit Connection-Reuse             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Datenfluss: Bild herunterladen und anzeigen

### Schritt 1: Sync-Service holt Daten vom Plugin

```python
# SpotifySyncService oder DeezerSyncService
artist_dto = await spotify_plugin.get_artist_details(spotify_uri)

# artist_dto enthält:
# - name: "Radiohead"
# - image_url: "https://i.scdn.co/image/abc123..."  ← CDN URL!
# - spotify_uri: "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb"
```

**Plugin liefert die URL als Teil der Entity-Daten!**

### Schritt 2: Sync-Service ruft ImageService

```python
# Sync-Service entscheidet: Bild lokal cachen?
if settings.cache_images_locally:
    result = await image_service.download_and_cache(
        source_url=artist_dto.image_url,  # URL vom Plugin
        entity_type="artist",
        entity_id=artist.id,              # Interne UUID, nicht spotify_id!
    )
    
    if result.success:
        # artist.image_path ist jetzt gesetzt
        logger.info(f"Bild gecacht: {result.image_info.local_path}")
```

### Schritt 3: ImageService verarbeitet das Bild

```
ImageService.download_and_cache():
│
├── 1. Prüft: Schon gecacht und URL gleich?
│       JA  → Return SaveImageResult.success_cached()
│       NEIN → Weiter
│
├── 2. Download via HttpClientPool
│       GET https://i.scdn.co/image/abc123...
│       → bytes (JPEG, PNG, etc.)
│
├── 3. WebP-Konvertierung (PIL in Thread-Pool)
│       - Resize auf 300px (Artists) oder 500px (Albums)
│       - Konvertiere zu WebP (Quality 85)
│       → webp_bytes
│
├── 4. Speichern in Cache
│       /app/data/cache/images/artists/ab/abc123.webp
│       Sharding: erste 2 Zeichen der ID
│
├── 5. DB Update
│       UPDATE soulspot_artists 
│       SET image_url = 'https://...', 
│           image_path = 'artists/ab/abc123.webp'
│       WHERE id = 'abc123...'
│
└── 6. Return SaveImageResult.success_downloaded()
```

### Schritt 4: Template zeigt das Bild

```jinja2
{# In dashboard.html, playlists.html, etc. #}

<img src="{{ get_display_url(artist.image_url, artist.image_path, 'artist') }}"
     alt="{{ artist.name }}"
     loading="lazy">

{# get_display_url() prüft: #}
{# 1. artist.image_path existiert und Datei da? → /artwork/local/artists/ab/abc.webp #}
{# 2. artist.image_url vorhanden? → https://i.scdn.co/image/abc123 (CDN) #}
{# 3. Sonst → /static/images/placeholder-artist.svg #}
```

---

## Konfiguration

### Bild-Größen

```python
IMAGE_SIZES = {
    "artist": 300,    # Profilbilder, 300px reicht
    "album": 500,     # Cover braucht mehr Detail
    "playlist": 300,  # Grid-Thumbnails
    "track": 500,     # Nutzt Album-Cover
}

WEBP_QUALITY = 85  # Sweet spot für Qualität vs. Dateigröße
```

### Verzeichnis-Struktur

```
/app/data/cache/images/
├── artists/
│   ├── ab/
│   │   ├── abc123.webp
│   │   └── abd456.webp
│   ├── cd/
│   │   └── cde789.webp
│   └── ...
├── albums/
│   ├── 12/
│   │   └── 123abc.webp
│   └── ...
└── playlists/
    └── ...
```

**Sharding:** Erste 2 Zeichen der Entity-ID als Unterverzeichnis.
Verhindert zu viele Dateien in einem Ordner.

---

## API-Referenz

### get_display_url() - Sync

```python
def get_display_url(
    self,
    source_url: str | None,   # CDN URL (z.B. "https://i.scdn.co/...")
    local_path: str | None,   # Lokaler Pfad (z.B. "artists/ab/abc.webp")
    entity_type: EntityType = "album",  # Für Placeholder-Auswahl
) -> str:
    """Beste URL für Anzeige.
    
    Priorität:
    1. Lokaler Cache (wenn local_path gesetzt UND Datei existiert)
    2. CDN URL (wenn source_url gesetzt)
    3. Placeholder (nach entity_type)
    """
```

**Verwendung in Templates:**
```jinja2
<img src="{{ get_display_url(album.cover_url, album.cover_path, 'album') }}">
```

### download_and_cache() - Async

```python
async def download_and_cache(
    self,
    source_url: str,           # CDN URL zum Herunterladen
    entity_type: EntityType,   # "artist", "album", "playlist"
    entity_id: str,            # Interne UUID
    force_redownload: bool = False,  # Cache ignorieren
) -> SaveImageResult:
    """Bild herunterladen, zu WebP konvertieren, cachen.
    
    Returns:
        SaveImageResult mit:
        - success: True/False
        - image_info: ImageInfo mit display_url, local_path, etc.
        - error: Fehlermeldung wenn success=False
        - downloaded: True wenn neu heruntergeladen
        - cached_reused: True wenn Cache verwendet
    """
```

**Verwendung in Sync-Services:**
```python
result = await image_service.download_and_cache(
    source_url=artist_dto.image_url,
    entity_type="artist",
    entity_id=artist.id,
)
if not result.success:
    logger.warning(f"Bild-Download fehlgeschlagen: {result.error}")
```

### validate_image() - Async

```python
async def validate_image(self, source_url: str) -> bool:
    """Prüft ob CDN-URL noch gültig ist (HTTP HEAD).
    
    Sparsam verwenden - macht Netzwerk-Request!
    """
```

### optimize_cache() - Async

```python
async def optimize_cache(
    self,
    max_age_days: int = 90,  # Bilder älter als X Tage löschen
    dry_run: bool = True,    # Nur berichten, nicht löschen
) -> dict[str, int]:
    """Cache aufräumen.
    
    Returns:
        {
            "deleted_count": 42,
            "freed_bytes": 12345678,
            "orphaned_count": 5,
        }
    """
```

---

## Datentypen

### ImageInfo

```python
@dataclass(frozen=True)
class ImageInfo:
    entity_type: EntityType      # "artist", "album", etc.
    entity_id: str               # Interne UUID
    display_url: str             # Beste URL für Anzeige
    source_url: str | None       # Original CDN URL
    local_path: str | None       # Lokaler Cache-Pfad
    is_cached: bool              # Lokal gecacht?
    provider: ImageProvider | None  # "spotify", "deezer", etc.
    width: int | None = None     # Bildbreite (wenn bekannt)
    height: int | None = None    # Bildhöhe (wenn bekannt)
    needs_refresh: bool = False  # Cache veraltet?
```

### SaveImageResult

```python
@dataclass
class SaveImageResult:
    success: bool
    image_info: ImageInfo | None = None
    error: str | None = None
    downloaded: bool = False      # Neu heruntergeladen?
    cached_reused: bool = False   # Cache verwendet?
```

---

## Migration von ArtworkService

### ArtworkService ist DEPRECATED ⚠️

Die gesamte Funktionalität wurde in ImageService integriert.

**Vorher (ArtworkService):**
```python
artwork_service = ArtworkService(settings)
path = await artwork_service.download_artist_image(spotify_id, image_url)
```

**Nachher (ImageService):**
```python
from soulspot.application.services.images import ImageService

image_service = ImageService(session=session)
result = await image_service.download_and_cache(
    source_url=image_url,
    entity_type="artist",
    entity_id=artist.id,  # WICHTIG: Interne UUID, nicht spotify_id!
)
path = result.image_info.local_path if result.success else None
```

**Wichtige Unterschiede:**
1. **entity_id** = Interne UUID, nicht Provider-spezifische ID
2. **Alles in einem Call**: Download + WebP + Cache + DB Update
3. **Strukturierte Rückgabe**: SaveImageResult statt str | None

---

## Implementierungs-Status

### ✅ Phase 1.0 - Grundstruktur (FERTIG)
- [x] `ImageService` Klasse erstellt
- [x] `IImageService` Interface definiert
- [x] `ImageInfo`, `SaveImageResult` DTOs
- [x] `get_display_url()` implementiert
- [x] `get_placeholder()` implementiert
- [x] `get_image()` implementiert

### ✅ Phase 1.1 - Template-Integration (FERTIG)
- [x] `get_display_url` als globale Template-Funktion
- [x] Alle Templates migriert (18 Stellen!)
- [x] `library_duplicates.html` API-Feld-Fix

### ✅ Phase 2.0 - Download & Cache (FERTIG)
- [x] `download_and_cache()` implementiert
- [x] `_download_image()` via HttpClientPool
- [x] `_convert_to_webp()` via PIL in Thread-Pool
- [x] `_save_to_cache()` mit Sharding
- [x] `_update_entity_image_path()` DB Update
- [x] `validate_image()` implementiert
- [x] `optimize_cache()` implementiert
- [x] ArtworkService als DEPRECATED markiert

### ✅ Phase 3.0 - Sync-Service Migration (ABGESCHLOSSEN)
- [x] SpotifySyncService: ArtworkService → ImageService
- [x] SpotifySyncWorker: ArtworkService → ImageService
- [x] settings.py (trigger_spotify_sync): ArtworkService → ImageService
- [x] settings.py (image-stats endpoints): ArtworkService → ImageService
- [x] LocalLibraryEnrichmentService: ArtworkService → ImageService
- [x] library.py (apply_enrichment_candidate): ArtworkService → ImageService
- [x] enrichment_service.py: Kommentare aktualisiert
- [x] services/__init__.py: Exports aktualisiert
- [x] ImageDownloadErrorCode + ImageDownloadResult zu ImageService migriert
- [x] get_disk_usage() + get_image_count() zu ImageService hinzugefügt
- [x] download_*_image_with_result() Methoden hinzugefügt

### ⏳ Phase 3.1 - Cleanup (AUSSTEHEND)
- [ ] ArtworkService löschen
- [ ] Dokumentation aktualisieren (docs/architecture/SERVICE_REORGANIZATION.md)

---

## Dateien

| Datei | Beschreibung |
|-------|--------------|
| `src/soulspot/application/services/images/__init__.py` | Modul-Exports |
| `src/soulspot/application/services/images/image_service.py` | Implementierung |
| `src/soulspot/domain/ports/image_service.py` | Interface |
| `src/soulspot/application/services/artwork_service.py` | **DEPRECATED** - kann gelöscht werden |

---

## FAQ

### Warum fragt ImageService nicht direkt bei Plugins nach?

**Separation of Concerns:**
- Plugins sind für Provider-spezifische API-Kommunikation zuständig
- ImageService ist Provider-agnostisch und kennt nur URLs
- Sync-Services orchestrieren beides

### Warum WebP und nicht JPEG?

- ~30% kleinere Dateien bei gleicher Qualität
- Unterstützt Transparenz (wie PNG)
- Von allen modernen Browsern unterstützt

### Warum Sharding im Verzeichnis?

- Dateisysteme werden langsam bei >10.000 Dateien pro Verzeichnis
- `artists/ab/abc123.webp` statt `artists/abc123.webp`
- Erste 2 Zeichen der UUID als Unterverzeichnis

### Was passiert wenn Download fehlschlägt?

- `SaveImageResult.success = False`
- `SaveImageResult.error` enthält Fehlermeldung
- Entity behält die CDN-URL (image_url) ohne lokalen Pfad
- Template zeigt CDN-Bild als Fallback
