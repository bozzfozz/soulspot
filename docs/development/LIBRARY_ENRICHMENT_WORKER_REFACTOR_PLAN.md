# LibraryEnrichmentWorker Refactor Plan

## 🎉 STATUS: ABGESCHLOSSEN (Jan 2025)

Alle Phasen wurden erfolgreich implementiert:
- ✅ Phase 1: Alle 3 ImageProvider erstellt
- ✅ Phase 2: ImageProviderRegistry erstellt  
- ✅ Phase 3: LocalLibraryEnrichmentService refactored
- ✅ Phase 4: LibraryEnrichmentWorker aktualisiert

### Implementierte Dateien:
| Datei | LOC | Status |
|-------|-----|--------|
| `infrastructure/image_providers/__init__.py` | ~15 | ✅ |
| `infrastructure/image_providers/spotify_image_provider.py` | ~200 | ✅ |
| `infrastructure/image_providers/deezer_image_provider.py` | ~190 | ✅ |
| `infrastructure/image_providers/caa_image_provider.py` | ~210 | ✅ |
| `application/services/images/image_provider_registry.py` | ~185 | ✅ |

### Architektur-Entscheidung:
- **LibraryDiscoveryWorker** bleibt für ID-Discovery (5 Phasen)
- **ImageService** bleibt für On-Demand Image-Download
- **ImageProviderRegistry** liefert Multi-Source Fallback für URLs
- **LibraryEnrichmentWorker** (DEPRECATED) nutzt jetzt Registry

---

## 🎯 Ziel

Den `LibraryEnrichmentWorker` umbauen, damit er den **Multi-Source ImageService** nutzt und Bilder von **allen verfügbaren Providern** (Spotify, Deezer, MusicBrainz/CAA) holt.

## 📊 Aktueller Stand (IST)

```
LibraryEnrichmentWorker
        │
        ▼
LocalLibraryEnrichmentService
        │
        ├── SpotifyPlugin.search_artist() → ArtistDTO mit image.url
        │
        └── ImageService.download_artist_image(spotify_id, url, "spotify")
                │
                └── Speichert: /config/images/artists/spotify/{id}.webp
```

**Probleme:**
1. ❌ Nur Spotify als Bildquelle
2. ❌ Wenn Spotify kein Bild hat → kein Bild
3. ❌ Deezer/MusicBrainz/CoverArtArchive werden ignoriert
4. ❌ Multi-Source Provider-System wird nicht genutzt

## 🚀 Ziel-Architektur (SOLL)

```
LibraryEnrichmentWorker
        │
        ▼
LocalLibraryEnrichmentService (refactored)
        │
        ├── 1. IImageProviderRegistry.get_available_providers()
        │       └── Returns: [SpotifyImageProvider, DeezerImageProvider, CAAImageProvider]
        │
        ├── 2. For each Artist/Album without image:
        │       └── IImageProviderRegistry.get_best_image_for_artist(name)
        │               │
        │               ├── SpotifyImageProvider.search_artist_image(name)
        │               ├── DeezerImageProvider.search_artist_image(name)
        │               └── CAAImageProvider.search_artist_image(name)
        │
        └── 3. ImageService.download_and_cache(best_url, entity_type, entity_id)
                │
                └── Speichert: /config/images/{type}s/{provider}/{id}.webp
```

## 📋 Aufgaben (Reihenfolge)

### Phase 1: IImageProvider Implementierungen (3 Aufgaben)

#### Task 1.1: SpotifyImageProvider erstellen
```python
# src/soulspot/infrastructure/image_providers/spotify_image_provider.py

class SpotifyImageProvider(IImageProvider):
    """Spotify image provider using SpotifyPlugin."""
    
    def __init__(self, spotify_plugin: SpotifyPlugin):
        self._plugin = spotify_plugin
    
    @property
    def provider_name(self) -> ProviderName:
        return "spotify"
    
    @property
    def requires_auth(self) -> bool:
        return True
    
    async def is_available(self) -> bool:
        return self._plugin.is_authenticated
    
    async def get_artist_image(self, artist_id: str, quality: ImageQuality) -> ImageResult | None:
        artist_dto = await self._plugin.get_artist(artist_id)
        if artist_dto and artist_dto.image.url:
            return ImageResult(
                url=artist_dto.image.url,
                provider="spotify",
                quality=quality,
            )
        return None
    
    async def search_artist_image(self, artist_name: str, quality: ImageQuality) -> ImageSearchResult:
        # Use plugin's search
        results = await self._plugin.search_artist(artist_name, limit=1)
        ...
```

**Abhängigkeiten:** SpotifyPlugin existiert bereits ✅

#### Task 1.2: DeezerImageProvider erstellen
```python
# src/soulspot/infrastructure/image_providers/deezer_image_provider.py

class DeezerImageProvider(IImageProvider):
    """Deezer image provider using DeezerClient."""
    
    def __init__(self, deezer_client: DeezerClient):
        self._client = deezer_client
    
    @property
    def provider_name(self) -> ProviderName:
        return "deezer"
    
    @property
    def requires_auth(self) -> bool:
        return False  # Deezer public API!
    
    async def is_available(self) -> bool:
        return True  # Always available (public API)
    
    async def search_artist_image(self, artist_name: str, quality: ImageQuality) -> ImageSearchResult:
        # Deezer search returns image URLs
        ...
```

**Abhängigkeiten:** DeezerClient existiert bereits ✅

#### Task 1.3: CoverArtArchiveImageProvider erstellen
```python
# src/soulspot/infrastructure/image_providers/caa_image_provider.py

class CoverArtArchiveImageProvider(IImageProvider):
    """Cover Art Archive provider for album images."""
    
    def __init__(self, musicbrainz_client: MusicBrainzClient, caa_client: CoverArtArchiveClient):
        self._mb_client = musicbrainz_client
        self._caa_client = caa_client
    
    @property
    def provider_name(self) -> ProviderName:
        return "caa"
    
    @property
    def requires_auth(self) -> bool:
        return False
    
    async def search_album_image(self, album_title: str, artist_name: str, quality: ImageQuality) -> ImageSearchResult:
        # 1. Search MusicBrainz for release-group
        # 2. Get cover from CAA
        ...
```

**Abhängigkeiten:** MusicBrainzClient, CoverArtArchiveClient existieren ✅

### Phase 2: ImageProviderRegistry erstellen (1 Aufgabe)

#### Task 2.1: Registry implementieren
```python
# src/soulspot/application/services/images/image_provider_registry.py

class ImageProviderRegistry(IImageProviderRegistry):
    """Registry that manages image providers with priority."""
    
    def __init__(self, session: AsyncSession, settings: Settings):
        self._providers: list[tuple[IImageProvider, int]] = []
        self._session = session
        self._settings = settings
    
    def register(self, provider: IImageProvider, priority: int = 10) -> None:
        self._providers.append((provider, priority))
        # Sort by priority (lower = higher priority)
        self._providers.sort(key=lambda x: x[1])
    
    async def get_best_image_for_artist(
        self, 
        artist_name: str,
        preferred_provider: ProviderName | None = None,
    ) -> ImageSearchResult:
        """Try all providers in priority order until we find an image."""
        for provider, _ in self._providers:
            if not await provider.is_available():
                continue
            
            result = await provider.search_artist_image(artist_name, ImageQuality.MEDIUM)
            if result.best_match:
                return result
        
        return ImageSearchResult(matches=[], best_match=None)
```

### Phase 3: LocalLibraryEnrichmentService refactoren (2 Aufgaben)

#### Task 3.1: Registry als Dependency hinzufügen
```python
# src/soulspot/application/services/local_library_enrichment_service.py

class LocalLibraryEnrichmentService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        image_service: ImageService,
        image_provider_registry: IImageProviderRegistry,  # NEU!
        spotify_plugin: SpotifyPlugin | None = None,  # Jetzt optional
    ):
        self._session = session
        self._settings = settings
        self._image_service = image_service
        self._provider_registry = image_provider_registry  # NEU!
        self._spotify_plugin = spotify_plugin
```

#### Task 3.2: enrich_batch() umbauen
```python
async def _enrich_artist_images(self, artists: list[Artist], stats: dict) -> None:
    """Fetch images for artists from all providers."""
    
    for artist in artists:
        # Try all providers in priority order
        result = await self._provider_registry.get_best_image_for_artist(
            artist_name=artist.name,
        )
        
        if result.best_match:
            # Download via ImageService
            save_result = await self._image_service.download_and_cache(
                source_url=result.best_match.url,
                entity_type="artist",
                entity_id=str(artist.id.value),
            )
            
            if save_result.success:
                # Update artist model
                artist.image_url = result.best_match.url
                artist.image_path = save_result.image_info.local_path
                stats["images_downloaded"] += 1
```

### Phase 4: Worker + Dependencies anpassen (2 Aufgaben)

#### Task 4.1: LibraryEnrichmentWorker aktualisieren
```python
# src/soulspot/application/workers/library_enrichment_worker.py

async def _handle_enrichment_job(self, job: Job) -> dict[str, Any]:
    # Create all providers
    spotify_provider = SpotifyImageProvider(spotify_plugin)
    deezer_provider = DeezerImageProvider(deezer_client)
    caa_provider = CoverArtArchiveImageProvider(mb_client, caa_client)
    
    # Create registry with priority
    registry = ImageProviderRegistry(session, self.settings)
    registry.register(spotify_provider, priority=1)   # Spotify first
    registry.register(deezer_provider, priority=2)    # Deezer second
    registry.register(caa_provider, priority=3)       # CAA last
    
    # Create service with registry
    service = LocalLibraryEnrichmentService(
        session=session,
        settings=self.settings,
        image_service=image_service,
        image_provider_registry=registry,
        spotify_plugin=spotify_plugin,
    )
    
    return await service.enrich_batch()
```

#### Task 4.2: Dependencies in api/dependencies.py hinzufügen
```python
def get_image_provider_registry(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    spotify_plugin: SpotifyPlugin | None = Depends(get_spotify_plugin_optional),
    deezer_client: DeezerClient = Depends(get_deezer_client),
) -> IImageProviderRegistry:
    """Create ImageProviderRegistry with all available providers."""
    registry = ImageProviderRegistry(session, settings)
    
    if spotify_plugin and spotify_plugin.is_authenticated:
        registry.register(SpotifyImageProvider(spotify_plugin), priority=1)
    
    registry.register(DeezerImageProvider(deezer_client), priority=2)
    registry.register(CoverArtArchiveImageProvider(...), priority=3)
    
    return registry
```

## 📁 Neue Dateien

```
src/soulspot/
├── infrastructure/
│   └── image_providers/           # NEU!
│       ├── __init__.py
│       ├── spotify_image_provider.py
│       ├── deezer_image_provider.py
│       └── caa_image_provider.py
└── application/
    └── services/
        └── images/
            └── image_provider_registry.py  # NEU!
```

## 🔄 Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `local_library_enrichment_service.py` | + IImageProviderRegistry Dependency |
| `library_enrichment_worker.py` | + Registry Setup + Provider Creation |
| `api/dependencies.py` | + get_image_provider_registry() |
| `domain/ports/__init__.py` | + Export IImageProviderRegistry |

## ✅ Akzeptanzkriterien

1. **Spotify + Deezer + CAA werden nacheinander geprüft**
2. **Wenn Spotify kein Bild hat → Deezer wird gefragt**
3. **Für Albums: CAA wird als Fallback genutzt**
4. **Settings respektieren**: `spotify.download_images`, Provider Modes
5. **Bilder in `/config/images/{type}s/{provider}/{id}.webp`**
6. **Logging zeigt welcher Provider das Bild lieferte**

## 📊 Vorher/Nachher

| Szenario | VORHER | NACHHER |
|----------|--------|---------|
| Artist hat Spotify-Bild | ✅ | ✅ |
| Artist hat nur Deezer-Bild | ❌ kein Bild | ✅ Deezer-Bild |
| Album hat nur CAA-Bild | ❌ kein Bild | ✅ CAA-Bild |
| Kein Provider hat Bild | Placeholder | Placeholder (unchanged) |
| Spotify nicht authed | ❌ komplett fehlschlag | ✅ Deezer/CAA noch verfügbar |

## 🚨 Risiken

1. **Breaking Change für LocalLibraryEnrichmentService**
   - Mitigation: Optional parameter mit default `None`
   
2. **Circular Imports**
   - Mitigation: Infrastructure → Domain Richtung beibehalten
   
3. **Rate Limiting bei mehreren Providern**
   - Mitigation: Each provider handles own rate limiting

## 📅 Zeitaufwand-Schätzung

| Phase | Aufgaben | Geschätzt | Tatsächlich |
|-------|----------|-----------|-------------|
| Phase 1 | 3 Provider Implementierungen | 2-3h | ✅ ~2h |
| Phase 2 | Registry | 1h | ✅ ~30min |
| Phase 3 | Service Refactor | 2h | ✅ ~1h |
| Phase 4 | Worker + Dependencies | 1h | ✅ ~30min |
| Testing | Manual Docker Tests | 1h | ⏳ Pending |
| **Total** | | **7-8h** | **~4h** |

## 🎬 Nächster Schritt

**✅ ALLE IMPLEMENTIERUNG ABGESCHLOSSEN**

Die folgenden Schritte sind noch offen:
1. ⏳ Live-Test in Docker-Umgebung
2. ⏳ Verify Bilder werden korrekt geladen
3. ⏳ Edge-Cases testen (Spotify nicht verbunden, etc.)

---

## Anhang: Code-Referenzen

### Neue Provider-Initialisierung (library_enrichment_worker.py)

```python
# Build the ImageProviderRegistry with all available providers
image_registry = ImageProviderRegistry()

# Register providers based on availability
# Priority: Spotify (1) → Deezer (2) → CoverArtArchive (3)
if spotify_plugin:
    image_registry.register(SpotifyImageProvider(spotify_plugin), priority=1)

# Deezer is always available (no auth required)
image_registry.register(DeezerImageProvider(), priority=2)

# CoverArtArchive is always available (no auth required, albums only)
image_registry.register(CoverArtArchiveImageProvider(), priority=3)

service = LocalLibraryEnrichmentService(
    session=session,
    spotify_plugin=spotify_plugin,
    settings=self.settings,
    image_provider_registry=image_registry,
)
```

### Usage in LocalLibraryEnrichmentService

```python
# Try registry first for multi-provider fallback
artwork_url = await self._get_artist_image_via_registry(
    artist_name=artist.name,
    spotify_uri=artist.spotify_uri.value,
)

if not artwork_url:
    # Fallback to direct Spotify plugin call (legacy behavior)
    ...
```
