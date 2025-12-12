# Spotify Plugin Refactoring - Architecture Documentation

**Status:** ✅ COMPLETED (January 2025)  
**Erstellt:** 10. Dezember 2025  
**Abgeschlossen:** Januar 2025  
**Ziel:** Alle Spotify-spezifischen Komponenten ins Plugin verschieben

---

## ✅ Migration Complete

**Was wurde implementiert:**

1. **SpotifyPlugin** (`infrastructure/plugins/spotify_plugin.py`)
   - Implementiert `IMusicServicePlugin` Interface
   - Wraps `SpotifyClient` für alle API-Aufrufe
   - Gibt typisierte DTOs zurück: `ArtistDTO`, `AlbumDTO`, `TrackDTO`
   - Pagination via `PaginatedResponse[T]`

2. **Alle Komponenten migriert:**
   - ✅ API Routers: Verwenden jetzt `SpotifyPlugin` via `get_spotify_plugin()`
   - ✅ Use Cases: Arbeiten mit `IMusicServicePlugin` Interface
   - ✅ Application Services: `LocalLibraryEnrichmentService` etc.
   - ✅ Workers: Erstellen `SpotifyPlugin` pro Job mit Token

3. **SpotifyClient Verbleib:**
   - Bleibt NUR für OAuth (TokenManager, AuthDependencies)
   - Alle Business-Logik geht über SpotifyPlugin

**Architektur nach Migration:**
```
API Router 
    → Depends(get_spotify_plugin)
        → SpotifyPlugin (DTOs)
            → SpotifyClient (raw HTTP)
                → Spotify API
```

**Hinweis:** Der Rest dieses Dokuments ist historische Planungsdokumentation.

---

## Problem Statement (HISTORISCH)

**AKTUELL (FALSCH):**
```
Spotify-Logik ist über 3 Schichten verteilt:

Application Layer:
  ├── services/spotify_sync_service.py (1248 Zeilen!)
  ├── services/spotify_image_service.py (740 Zeilen)
  ├── cache/spotify_cache.py (186 Zeilen)
  ├── workers/spotify_sync_worker.py
  └── use_cases/import_spotify_playlist.py

API Layer:
  ├── routers/search.py (Spotify-hardcoded endpoints)
  └── routers/artists.py (follow/unfollow Spotify)

Plugins Layer:
  └── spotify_plugin.py (nur Interface-Implementierung)

❌ PROBLEM: Spotify-Code ist ÜBERALL statt im Plugin!
```

**SOLL (RICHTIG):**
```
Plugins Layer:
  ├── spotify_plugin.py (Hauptklasse - PUBLIC Interface)
  └── spotify/
      ├── __init__.py (Nothing exported - all PRIVATE!)
      ├── _sync_service.py (Spotify-Sync-Logik)
      ├── _image_service.py (Bild-Downloads)
      └── _cache.py (Spotify-API-Cache)

Infrastructure Layer:
  ├── auth/spotify_token_manager.py (OAuth - bleibt hier)
  └── integrations/spotify_client.py (HTTP Client - bleibt hier)

Application Layer:
  └── workers/streaming_sync_worker.py (GENERISCH - verwendet Plugin-Interface)

✅ LÖSUNG: Alle Spotify-Logik im Plugin gekapselt!
```

---

## Warum ist das wichtig?

### 1. **Service-Agnostik**
Wenn Tidal/Deezer hinzugefügt werden, dürfen wir NICHT für jeden Service neue Application-Services erstellen:

```python
# ❌ FALSCH (aktueller Zustand):
application/services/
  ├── spotify_sync_service.py
  ├── tidal_sync_service.py  # Duplikation!
  ├── deezer_sync_service.py # Noch mehr Duplikation!

# ✅ RICHTIG (Ziel):
plugins/
  ├── spotify_plugin.py (enthält alle Spotify-Logik)
  ├── tidal_plugin.py   (enthält alle Tidal-Logik)
  └── deezer_plugin.py  (enthält alle Deezer-Logik)

application/workers/
  └── streaming_sync_worker.py  # EINS für ALLE Services!
```

### 2. **Klare Grenzen**
- **Plugin = Service-spezifische Logik** (wie genau Spotify synced)
- **Application = Generische Orchestrierung** (wann synced wird, Error-Handling)
- **Infrastructure = Technische Details** (HTTP, OAuth, Database)

### 3. **Testbarkeit**
```python
# Aktuell: Spotify-Logic überall verstreut
test_spotify_sync_service.py
test_spotify_image_service.py
test_spotify_cache.py
test_spotify_sync_worker.py
test_search_routes.py

# Nach Refactoring: Alles an einem Ort
test_spotify_plugin.py  # Testet ALLES in einem Modul
```

---

## Migration Plan (Schritt-für-Schritt)

### Phase 1: Plugin-Struktur erstellen

**Schritt 1.1: Package erstellen**
```bash
mkdir -p src/soulspot/plugins/spotify
touch src/soulspot/plugins/spotify/__init__.py
```

**Schritt 1.2: `__init__.py` mit PRIVATE-Marker**
```python
# src/soulspot/plugins/spotify/__init__.py
"""Spotify plugin internal modules.

PRIVATE: These modules are ONLY used internally by SpotifyPlugin.
Do NOT import from outside plugins/spotify_plugin.py!

Why private (_prefix)?
- Implementation details may change without notice
- Breaking changes don't affect other modules
- Clear boundary: Public interface is SpotifyPlugin class only
"""

__all__: list[str] = []  # Nothing exported - all internal!
```

---

### Phase 2: Services migrieren (VEREINFACHT!)

#### 2.1 `_sync_service.py` (370 Zeilen statt 1248!)

**Was macht es:**
- Sync followed artists (mit Diff-Logik: add new, remove unfollowed)
- Sync user playlists (owned + followed)
- Sync saved albums
- Pagination-Handling (Spotify gibt max 50 Items pro Page)

**Was macht es NICHT (delegiert):**
- Image Downloads → `_image_service.py`
- Caching → `_cache.py`
- Database Operations → `SpotifyBrowseRepository` (Infrastructure)

**Datei:** `src/soulspot/plugins/spotify/_sync_service.py`

```python
"""Spotify sync service - INTERNAL to SpotifyPlugin.

SIMPLIFIED version: 370 lines (old: 1248 lines)
- Removed complex error tracking
- Removed helper methods
- Focus on core sync operations
"""

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

logger = logging.getLogger(__name__)


class SpotifySyncService:
    """Internal service for Spotify data synchronization.
    
    PRIVATE: Only used by SpotifyPlugin. Do NOT import elsewhere!
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        image_service: "SpotifyImageService | None" = None,
    ) -> None:
        self._client = spotify_client
        self._image_service = image_service

    async def sync_followed_artists(
        self,
        access_token: str,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Sync user's followed artists.
        
        1. Fetch all from Spotify (paginated)
        2. Get current DB state
        3. Diff: Add new, remove unfollowed
        4. Trigger image downloads
        """
        repo = SpotifyBrowseRepository(session)
        
        # Fetch from API (handles pagination)
        spotify_artists = await self._fetch_all_followed_artists(access_token)
        spotify_ids = {artist["id"] for artist in spotify_artists}
        
        # Get current DB state
        db_artists = await repo.get_all_followed_artists()
        db_ids = {artist.spotify_id for artist in db_artists}
        
        # Diff logic
        to_add = spotify_ids - db_ids
        to_remove = db_ids - spotify_ids
        
        added_count = 0
        removed_count = 0
        errors = []
        
        # Add new follows
        for artist_data in spotify_artists:
            if artist_data["id"] in to_add:
                try:
                    await repo.upsert_artist(artist_data)
                    added_count += 1
                    
                    # Trigger image download (async)
                    if self._image_service and artist_data.get("images"):
                        await self._image_service.download_artist_image(
                            artist_id=artist_data["id"],
                            image_url=artist_data["images"][0]["url"],
                        )
                except Exception as e:
                    logger.warning(f"Failed to add artist: {e}")
                    errors.append(str(e))
        
        # Remove unfollows
        for artist_id in to_remove:
            try:
                await repo.delete_artist(artist_id)
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove artist: {e}")
                errors.append(str(e))
        
        await session.commit()
        
        return {
            "added": added_count,
            "removed": removed_count,
            "total": len(spotify_ids),
            "errors": errors,
        }

    async def _fetch_all_followed_artists(self, access_token: str) -> list[dict]:
        """Fetch ALL followed artists (handles pagination)."""
        all_artists = []
        after = None
        
        while True:
            response = await self._client.get_followed_artists(
                access_token=access_token,
                limit=50,
                after=after,
            )
            
            artists = response.get("artists", {}).get("items", [])
            all_artists.extend(artists)
            
            # Pagination cursor
            cursors = response.get("artists", {}).get("cursors", {})
            after = cursors.get("after")
            if not after:
                break  # No more pages
        
        return all_artists

    # sync_user_playlists(), sync_saved_albums() analog...
```

---

#### 2.2 `_image_service.py` (200 Zeilen statt 740!)

**Was macht es:**
- Download von Spotify CDN
- Resize (Artists: 300px, Albums: 500px, Playlists: 300px)
- WebP Conversion (kleinere Files, gute Qualität)
- Speichern: `artwork/spotify/{type}/{id}.webp`

**Datei:** `src/soulspot/plugins/spotify/_image_service.py`

```python
"""Spotify image service - INTERNAL to SpotifyPlugin.

SIMPLIFIED: 200 lines (old: 740 lines)
- Removed complex error tracking (12 error codes → try/except)
- Removed URL change detection
- Removed cleanup logic
- Focus on download → resize → save
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Literal

import httpx
from PIL import Image as PILImage

from soulspot.config import Settings

logger = logging.getLogger(__name__)

IMAGE_SIZES = {"artists": 300, "albums": 500, "playlists": 300}
WEBP_QUALITY = 85

ImageType = Literal["artists", "albums", "playlists"]


class SpotifyImageService:
    """Internal service for Spotify image downloads.
    
    PRIVATE: Only used by SpotifyPlugin.
    """

    def __init__(self, settings: Settings) -> None:
        self._artwork_base = settings.storage.artwork_path
        self._spotify_path = self._artwork_base / "spotify"
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Ensure directories exist
        for image_type in IMAGE_SIZES:
            (self._spotify_path / image_type).mkdir(parents=True, exist_ok=True)

    async def download_artist_image(
        self, artist_id: str, image_url: str
    ) -> str | None:
        """Download and save artist image.
        
        Returns: Relative path (e.g., "spotify/artists/{id}.webp") or None
        """
        return await self._download_and_save("artists", artist_id, image_url)

    async def _download_and_save(
        self, image_type: ImageType, entity_id: str, image_url: str
    ) -> str | None:
        try:
            # Download
            response = await self._http_client.get(image_url)
            response.raise_for_status()
            
            # Process (resize + WebP)
            target_size = IMAGE_SIZES[image_type]
            processed = await self._process_image(response.content, target_size)
            if not processed:
                return None
            
            # Save
            file_path = self._spotify_path / image_type / f"{entity_id}.webp"
            file_path.write_bytes(processed)
            
            return f"spotify/{image_type}/{entity_id}.webp"
        except Exception as e:
            logger.warning(f"Image download failed: {e}")
            return None

    async def _process_image(self, image_bytes: bytes, target_size: int) -> bytes | None:
        try:
            img = PILImage.open(BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((target_size, target_size), PILImage.Resampling.LANCZOS)
            
            output = BytesIO()
            img.save(output, format="WEBP", quality=WEBP_QUALITY)
            return output.getvalue()
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return None
```

---

#### 2.3 `_cache.py` (160 Zeilen statt 186!)

**Was macht es:**
- In-Memory Cache für Spotify API Responses
- TTL-based Expiration (Tracks: 24h, Playlists: 1h, Search: 30min)
- Thread-safe mit `asyncio.Lock`

**Datei:** `src/soulspot/plugins/spotify/_cache.py`

```python
"""Spotify cache - INTERNAL to SpotifyPlugin.

SIMPLIFIED: Direct dict-based cache (no base class overhead)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# TTL values
TTL_TRACK = 86400   # 24 hours (metadata stable)
TTL_ARTIST = 43200  # 12 hours
TTL_ALBUM = 43200   # 12 hours
TTL_PLAYLIST = 3600 # 1 hour (dynamic content)
TTL_SEARCH = 1800   # 30 minutes


class SpotifyCache:
    """In-memory cache for Spotify API responses.
    
    PRIVATE: Only used by SpotifyPlugin.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[Any, datetime]] = {}  # key → (value, expires_at)
        self._lock = asyncio.Lock()

    async def get_track(self, track_id: str) -> dict | None:
        return await self._get(f"track:{track_id}")

    async def set_track(self, track_id: str, track_data: dict) -> None:
        await self._set(f"track:{track_id}", track_data, TTL_TRACK)

    async def _get(self, key: str) -> Any | None:
        async with self._lock:
            if key not in self._cache:
                return None
            
            value, expires_at = self._cache[key]
            now = datetime.now(timezone.utc)
            
            if now >= expires_at:
                del self._cache[key]  # Expired
                return None
            
            return value

    async def _set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        async with self._lock:
            self._cache[key] = (value, expires_at)
```

---

### Phase 3: `SpotifyPlugin` aktualisieren

**Datei:** `src/soulspot/plugins/spotify_plugin.py`

**Änderungen im `__init__`:**
```python
from soulspot.config import Settings  # ← NEU (für image service)
from soulspot.plugins.spotify._cache import SpotifyCache
from soulspot.plugins.spotify._image_service import SpotifyImageService
from soulspot.plugins.spotify._sync_service import SpotifySyncService

class SpotifyPlugin(IStreamingServicePlugin):
    def __init__(
        self,
        settings: SpotifySettings,
        token_manager: SpotifyTokenManager,
        app_settings: Settings,  # ← NEU!
    ) -> None:
        self._settings = settings
        self._client = SpotifyClient(settings)
        self._token_manager = token_manager

        # PRIVATE: Internal services
        self._cache = SpotifyCache()
        self._image_service = SpotifyImageService(app_settings)
        self._sync_service = SpotifySyncService(
            spotify_client=self._client,
            image_service=self._image_service,
        )
```

---

### Phase 4: `lifecycle.py` aktualisieren

**Datei:** `src/soulspot/infrastructure/lifecycle.py`

**Änderung bei Plugin-Registrierung:**
```python
# Vorher:
spotify_plugin = SpotifyPlugin(
    settings=settings.spotify,
    token_manager=spotify_token_manager,
)

# Nachher:
spotify_plugin = SpotifyPlugin(
    settings=settings.spotify,
    token_manager=spotify_token_manager,
    app_settings=settings,  # ← NEU (für image service paths)
)
```

---

### Phase 5: Generischer `StreamingSyncWorker` (Optional)

**Problem:** Aktueller `SpotifySyncWorker` ist Spotify-hardcoded.

**Lösung:** Generischer Worker, der PluginRegistry verwendet:

**Datei:** `src/soulspot/application/workers/streaming_sync_worker.py` (NEU)

```python
"""Generic sync worker for ANY streaming service."""

import logging
from soulspot.application.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)


class StreamingSyncWorker:
    """Generic sync worker using PluginRegistry.
    
    Works with Spotify, Tidal, Deezer - ANY registered service!
    """

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        service_types: list[str] = ["spotify"],  # Konfigurierbar
        check_interval_seconds: int = 60,
    ):
        self._registry = plugin_registry
        self._service_types = service_types
        self._check_interval = check_interval_seconds

    async def sync_all_services(self, session_id: str):
        """Sync across all configured services."""
        results = {}
        
        for service_type in self._service_types:
            plugin = self._registry.get(service_type)
            if not plugin:
                logger.warning(f"Service '{service_type}' not registered")
                continue
            
            try:
                # Generic interface method!
                result = await plugin.sync_user_playlists(session_id)
                results[service_type] = result
            except Exception as e:
                logger.error(f"Sync failed for {service_type}: {e}")
                results[service_type] = {"error": str(e)}
        
        return results
```

**In `lifecycle.py` verwenden:**
```python
# Vorher:
spotify_sync_worker = SpotifySyncWorker(...)

# Nachher:
streaming_sync_worker = StreamingSyncWorker(
    plugin_registry=plugin_registry,
    service_types=["spotify"],  # Later: ["spotify", "tidal", "deezer"]
    check_interval_seconds=60,
)
```

---

## Vorher/Nachher Vergleich

### Code-Reduktion

| Komponente | Vorher (Zeilen) | Nachher (Zeilen) | Einsparung |
|------------|----------------|------------------|------------|
| `spotify_sync_service.py` | 1248 | 370 | **70%** |
| `spotify_image_service.py` | 740 | 200 | **73%** |
| `spotify_cache.py` | 186 | 160 | **14%** |
| **GESAMT** | **2174** | **730** | **66%** |

### Architektur

**VORHER:**
```
application/services/
  ├── spotify_sync_service.py    ❌ Spotify-hardcoded
  ├── spotify_image_service.py   ❌ Spotify-hardcoded
  └── ...

application/workers/
  └── spotify_sync_worker.py     ❌ Spotify-hardcoded

api/routers/
  └── search.py                  ❌ Spotify-hardcoded routes

plugins/
  └── spotify_plugin.py          ⚠️ Nur Interface, keine Logik
```

**NACHHER:**
```
plugins/
  ├── spotify_plugin.py          ✅ Alle Spotify-Logik hier!
  └── spotify/
      ├── _sync_service.py       ✅ PRIVATE
      ├── _image_service.py      ✅ PRIVATE
      └── _cache.py              ✅ PRIVATE

application/workers/
  └── streaming_sync_worker.py   ✅ GENERISCH (alle Services)

api/routers/
  └── streaming.py               ✅ Service-agnostic
```

---

## Testen der Migration

### 1. Syntax-Check
```bash
# Alle neuen Files prüfen
python -m py_compile src/soulspot/plugins/spotify/_sync_service.py
python -m py_compile src/soulspot/plugins/spotify/_image_service.py
python -m py_compile src/soulspot/plugins/spotify/_cache.py
python -m py_compile src/soulspot/plugins/spotify_plugin.py
```

### 2. Import-Check
```python
# In Python REPL
import sys
sys.path.insert(0, "src")

from soulspot.plugins.spotify_plugin import SpotifyPlugin
from soulspot.plugins.spotify._sync_service import SpotifySyncService  # Should work
from soulspot.application.workers.streaming_sync_worker import StreamingSyncWorker

print("✅ All imports successful")
```

### 3. Integration Test
```python
# Test Plugin mit internen Services
from soulspot.config import get_settings
from soulspot.infrastructure.auth.spotify_token_manager import SpotifyTokenManager
from soulspot.plugins.spotify_plugin import SpotifyPlugin

settings = get_settings()
token_manager = SpotifyTokenManager(settings.spotify)
plugin = SpotifyPlugin(
    settings=settings.spotify,
    token_manager=token_manager,
    app_settings=settings,
)

# Check internal services initialized
assert plugin._cache is not None
assert plugin._image_service is not None
assert plugin._sync_service is not None
print("✅ Plugin initialization successful")
```

---

## Rollback Plan (falls Probleme)

**Option 1: Alte Services behalten**
- Neue Files erstellen (koexistieren)
- Alte Services als `@deprecated` markieren
- Migration schrittweise

**Option 2: Feature Flag**
```python
# settings.py
ENABLE_PLUGIN_REFACTORING = os.getenv("ENABLE_PLUGIN_REFACTORING", "false") == "true"

# lifecycle.py
if ENABLE_PLUGIN_REFACTORING:
    plugin = SpotifyPlugin(...)  # Neue Version
else:
    plugin = SpotifyPluginLegacy(...)  # Alte Version
```

---

## Nächste Schritte (nach Implementation)

1. **Alte Services deprecaten:**
   ```python
   # application/services/spotify_sync_service.py
   import warnings
   
   class SpotifySyncService:
       def __init__(self, *args, **kwargs):
           warnings.warn(
               "SpotifySyncService is deprecated. Use SpotifyPlugin directly.",
               DeprecationWarning,
               stacklevel=2,
           )
   ```

2. **Alte API Routes redirecten:**
   ```python
   # api/routers/search.py
   @router.get("/spotify/artists", deprecated=True)
   async def search_spotify_artists_old(...):
       # Redirect to new endpoint
       return RedirectResponse("/api/streaming/spotify/search/artists")
   ```

3. **Tidal/Deezer Plugins erstellen:**
   ```
   plugins/
     ├── tidal_plugin.py
     ├── tidal/
     │   ├── _sync_service.py
     │   └── _cache.py
     └── deezer_plugin.py
   ```

---

## Zusammenfassung

### Was wird erreicht?
✅ **Klare Grenzen:** Plugin = Service-Logik, Application = Orchestrierung  
✅ **66% weniger Code:** Simplified services (2174 → 730 Zeilen)  
✅ **Multi-Service Ready:** Tidal/Deezer folgen gleichem Pattern  
✅ **Bessere Testbarkeit:** Alles in einem Modul  
✅ **Keine Breaking Changes:** Migration schrittweise möglich  

### Was bleibt wo?
- **Infrastructure:** `spotify_client.py`, `spotify_token_manager.py` (HTTP/OAuth)
- **Plugins:** Alle Spotify-spezifische Business-Logik
- **Application:** Nur noch generische Worker/Services

### Implementierungszeit
- Phase 1-4: **~60 Minuten** (Files erstellen, Code migrieren)
- Phase 5 (optional): **+30 Minuten** (Generic Worker)
- Testing: **+20 Minuten**
- **TOTAL: ~2 Stunden**

---

**Ready to implement?** Dieser Plan ist die Grundlage für die Code-Migration nach dem VSCode Crash.
