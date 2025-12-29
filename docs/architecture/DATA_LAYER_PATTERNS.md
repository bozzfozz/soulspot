# SoulSpot Data Layer Patterns

## Quick Reference für häufige Operationen

Dieses Dokument zeigt konkrete Beispiele, wie du verschiedene Daten-Operationen korrekt implementierst.

---

## 1. Neuen Service-Endpunkt hinzufügen

### Schritt 1: Route (API Layer)

```python
# src/soulspot/api/routers/artists.py

from fastapi import APIRouter, Depends
from soulspot.api.dependencies import get_artist_service
from soulspot.application.services.artist_service import ArtistService

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/{artist_id}")
async def get_artist(
    artist_id: str,
    service: ArtistService = Depends(get_artist_service),  # ← Service injiziert!
):
    """
    Hey future me - Routes sind DÜNN!
    Nur HTTP-Handling, keine Business Logic.
    """
    return await service.get_artist_by_id(artist_id)
```

### Schritt 2: Service (Application Layer)

```python
# src/soulspot/application/services/artist_service.py

from soulspot.domain.dtos import ArtistDTO
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.persistence.repositories import ArtistRepository


class ArtistService:
    """
    Hey future me - Services orchestrieren Plugins und Repos!
    Sie enthalten die Business Logic.
    """
    
    def __init__(
        self,
        spotify_plugin: SpotifyPlugin,
        artist_repo: ArtistRepository,
    ):
        self._spotify = spotify_plugin
        self._repo = artist_repo

    async def get_artist_by_id(self, spotify_id: str) -> ArtistDTO:
        # 1. Erst in DB schauen (cached)
        existing = await self._repo.get_by_spotify_uri(
            f"spotify:artist:{spotify_id}"
        )
        
        if existing:
            # Konvertiere Entity zu DTO für API Response
            return ArtistDTO(
                name=existing.name,
                source_service="database",
                spotify_uri=str(existing.spotify_uri),
                spotify_id=spotify_id,
                image_url=existing.image_url,
            )
        
        # 2. Nicht in DB - hole von Spotify
        return await self._spotify.get_artist(spotify_id)
```

### Schritt 3: Dependency (API Layer)

```python
# src/soulspot/api/dependencies.py

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.artist_service import ArtistService
from soulspot.infrastructure.plugins import SpotifyPlugin
from soulspot.infrastructure.persistence.repositories import ArtistRepository


async def get_artist_service(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
) -> ArtistService:
    """Factory für ArtistService mit allen Dependencies."""
    return ArtistService(
        spotify_plugin=spotify_plugin,
        artist_repo=ArtistRepository(session),
    )
```

---

## 2. Neue Plugin-Methode hinzufügen

### Beispiel: `get_chart_tracks()` in DeezerPlugin

```python
# src/soulspot/infrastructure/plugins/deezer_plugin.py

async def get_chart_tracks(self, limit: int = 50) -> list[TrackDTO]:
    """
    Get current chart tracks from Deezer.
    
    Hey future me - Client gibt raw dict, wir konvertieren zu DTOs!
    Die Konvertierung passiert HIER im Plugin, nicht im Client.
    """
    # 1. Raw API Call über Client
    raw_data = await self._client.get_chart_tracks(limit=limit)
    
    # 2. Konvertiere zu DTOs
    tracks: list[TrackDTO] = []
    for item in raw_data.get("tracks", {}).get("data", []):
        tracks.append(self._convert_track(item))  # ← _convert_track, nicht _convert_track_to_dto!
    
    return tracks


def _convert_track(self, data: dict) -> TrackDTO:
    """
    Convert raw Deezer API track to TrackDTO.
    
    Hey future me - ALLE Konvertierungen hier!
    Checke welche Felder die API liefert und mappe sie korrekt.
    """
    album_data = data.get("album", {})
    artist_data = data.get("artist", {})
    
    return TrackDTO(
        title=data.get("title", "Unknown"),
        artist_name=artist_data.get("name", "Unknown Artist"),
        source_service="deezer",
        
        # Deezer-spezifische ID
        deezer_id=str(data.get("id", "")),
        
        # Album-Referenz (wenn vorhanden)
        album_name=album_data.get("title"),
        album_deezer_id=str(album_data.get("id", "")) if album_data.get("id") else None,
        
        # Artist-Referenz
        artist_deezer_id=str(artist_data.get("id", "")) if artist_data.get("id") else None,
        
        # Track-Metadaten
        duration_ms=(data.get("duration", 0)) * 1000,  # Deezer gibt Sekunden!
        explicit=data.get("explicit_lyrics", False),
        preview_url=data.get("preview"),
    )
```

---

## 3. Neue Repository-Methode hinzufügen

### ⚠️ WICHTIG: Interface UND Implementation aktualisieren!

### Schritt 1: Interface (Domain Port)

```python
# src/soulspot/domain/ports/__init__.py

class IArtistRepository(ABC):
    # ... existing methods ...
    
    @abstractmethod
    async def get_by_deezer_id(self, deezer_id: str) -> Artist | None:
        """Get an artist by Deezer ID.
        
        Hey future me - Multi-Service Lookup für Deduplikation!
        Checke zuerst ob Artist schon existiert bevor du neuen erstellst.
        """
        pass
```

### Schritt 2: Implementation (Infrastructure)

```python
# src/soulspot/infrastructure/persistence/repositories.py

class ArtistRepository(IArtistRepository):
    # ... existing methods ...
    
    async def get_by_deezer_id(self, deezer_id: str) -> Artist | None:
        """Get an artist by Deezer ID."""
        result = await self._session.execute(
            select(ArtistModel).where(ArtistModel.deezer_id == deezer_id)
        )
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_entity(model)  # ← Model → Entity Konvertierung!
    
    def _to_entity(self, model: ArtistModel) -> Artist:
        """Convert ORM Model to Domain Entity.
        
        Hey future me - das ist die Model→Entity Brücke!
        """
        return Artist(
            id=ArtistId(model.id),
            name=model.name,
            spotify_uri=SpotifyUri(model.spotify_uri) if model.spotify_uri else None,
            deezer_id=model.deezer_id,
            musicbrainz_id=model.musicbrainz_id,
            image_url=model.image_url,
            # ... weitere Felder
        )
```

---

## 4. spotify_id aus verschiedenen Kontexten extrahieren

### Aus Entity (Domain)

```python
# Entity hat NUR spotify_uri
artist: Artist = await repo.get_by_id(artist_id)

# Extrahiere ID
if artist.spotify_uri:
    spotify_id = str(artist.spotify_uri).split(":")[-1]
```

### Aus Model (ORM)

```python
# Model hat spotify_uri Column + spotify_id Property
artist_model: ArtistModel = result.scalar_one()

# Option 1: Property nutzen (wenn definiert)
spotify_id = artist_model.spotify_id  # ← @property im Model

# Option 2: Manuell extrahieren (immer sicher)
spotify_id = artist_model.spotify_uri.split(":")[-1] if artist_model.spotify_uri else None
```

### Aus DTO

```python
# DTO hat BEIDE Felder
artist_dto: ArtistDTO = await plugin.get_artist("xyz")

# Direkt nutzen
spotify_id = artist_dto.spotify_id      # ← Schon extrahiert
spotify_uri = artist_dto.spotify_uri    # ← Voller URI
```

### In Jinja2 Templates

```html
<!-- artist ist ein Model oder DTO -->
{% if artist.spotify_uri %}
    <a href="https://open.spotify.com/artist/{{ artist.spotify_uri.split(':')[-1] }}">
        Auf Spotify öffnen
    </a>
{% endif %}

<!-- Wenn Model spotify_id Property hat -->
{% if artist.spotify_id %}
    <a href="https://open.spotify.com/artist/{{ artist.spotify_id }}">
        Auf Spotify öffnen
    </a>
{% endif %}
```

---

## 5. Multi-Provider Aggregation Pattern

```python
# src/soulspot/application/services/charts_service.py

async def get_aggregated_chart_tracks(self) -> list[TrackDTO]:
    """
    Get chart tracks from ALL enabled providers.
    
    Hey future me - DAS ist das Multi-Provider Pattern!
    1. Query ALLE aktiven Provider
    2. Aggregiere Ergebnisse
    3. Dedupliziere (ISRC ist der Key!)
    """
    all_tracks: list[TrackDTO] = []
    seen_isrcs: set[str] = set()
    
    # 1. Deezer (kein Auth nötig für Charts)
    if self._deezer_plugin.can_use(PluginCapability.BROWSE_CHARTS):
        try:
            deezer_tracks = await self._deezer_plugin.get_chart_tracks()
            for track in deezer_tracks:
                # Dedupliziere via ISRC
                if track.isrc and track.isrc in seen_isrcs:
                    continue
                if track.isrc:
                    seen_isrcs.add(track.isrc)
                all_tracks.append(track)
        except PluginError as e:
            logger.warning(f"Deezer charts failed: {e}")
    
    # 2. Spotify (Auth required)
    if self._spotify_plugin.can_use(PluginCapability.BROWSE_CHARTS):
        try:
            spotify_tracks = await self._spotify_plugin.get_chart_tracks()
            for track in spotify_tracks:
                if track.isrc and track.isrc in seen_isrcs:
                    continue
                if track.isrc:
                    seen_isrcs.add(track.isrc)
                all_tracks.append(track)
        except PluginError as e:
            logger.warning(f"Spotify charts failed: {e}")
    
    return all_tracks
```

---

## 6. Häufige Fehler-Fixes

### AttributeError: 'XModel' has no attribute 'spotify_id'

```python
# ❌ FEHLER
artist_model = await session.get(ArtistModel, id)
print(artist_model.spotify_id)  # AttributeError!

# ✅ FIX 1: Property in Model hinzufügen
# In models.py:
@property
def spotify_id(self) -> str | None:
    if not self.spotify_uri:
        return None
    return self.spotify_uri.split(":")[-1]

# ✅ FIX 2: Manuell extrahieren
spotify_id = artist_model.spotify_uri.split(":")[-1] if artist_model.spotify_uri else None
```

### TypeError: 'NoneType' object is not subscriptable

```python
# ❌ FEHLER
spotify_id = artist.spotify_uri.split(":")[-1]  # Crash wenn None!

# ✅ FIX: None-Check
spotify_id = artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None

# ✅ NOCH BESSER: Walrus Operator (Python 3.8+)
spotify_id = uri.split(":")[-1] if (uri := artist.spotify_uri) else None
```

### Plugin gibt raw dict statt DTO

```python
# ❌ FEHLER (im Plugin)
async def get_artist(self, artist_id: str):
    return await self._client.get_artist(artist_id)  # raw dict!

# ✅ FIX: Konvertiere zu DTO
async def get_artist(self, artist_id: str) -> ArtistDTO:
    raw = await self._client.get_artist(artist_id)
    return self._convert_artist(raw)
```

---

## 5. Track-Persistenz von Providern (NEU!)

### ⚠️ WICHTIG: Einheitliches Pattern für alle Provider!

**IMMER `TrackRepository.upsert_from_provider()` nutzen!**

Diese Methode ist die **einzige korrekte Art**, Tracks von externen Providern
(Spotify, Deezer, Tidal) zu persistieren.

### Warum?

1. **Einheitliche Deduplication**: ISRC → Provider-ID → title+album
2. **Konsistente album_id**: IMMER interne UUIDs, nie Provider-IDs
3. **Clean Architecture**: Services → Repository → ORM (nicht Services → ORM direkt)
4. **Multi-Provider-Ready**: Tracks bekommen `source="hybrid"` wenn mehrere Provider-IDs

### Korrekte Verwendung

```python
# src/soulspot/application/services/deezer_sync_service.py

async def _save_track_with_artist(
    self,
    track_dto: TrackDTO,
    artist_id: str,  # ← Interne UUID!
    album_id: str | None,  # ← Interne UUID!
) -> None:
    """
    Hey future me - nutze TrackRepository.upsert_from_provider()!
    Niemals ORM direkt (TrackModel) verwenden.
    """
    await self._track_repo.upsert_from_provider(
        title=track_dto.title,
        artist_id=artist_id,  # Internal UUID (from ProviderMappingService)
        album_id=album_id,  # Internal UUID (from AlbumRepository lookup)
        source="deezer",
        duration_ms=track_dto.duration_ms or 0,
        track_number=track_dto.track_number or 1,
        disc_number=track_dto.disc_number or 1,
        explicit=track_dto.explicit or False,
        isrc=track_dto.isrc,  # KRITISCH für Deduplication!
        deezer_id=track_dto.deezer_id,
        preview_url=track_dto.preview_url,
    )
```

### ❌ FALSCH: Direktes ORM

```python
# ❌ NIEMALS SO!
from soulspot.infrastructure.persistence.models import TrackModel

track = TrackModel(
    title=dto.title,
    artist_id=artist_id,
    album_id=album_id,  # Was ist das - Spotify-ID oder UUID??
    deezer_id=dto.deezer_id,
)
self._session.add(track)
```

### ❌ DEPRECATED: SpotifyBrowseRepository.upsert_track()

```python
# ❌ DEPRECATED - nicht für neue Features!
await self.repo.upsert_track(
    spotify_id=track.id,
    album_id=album.id,  # Spotify-ID! Verwirrend!
    name=track.title,
)

# ✅ STATTDESSEN:
# 1. Album-UUID nachschlagen
album = await album_repo.get_by_spotify_uri(f"spotify:album:{album.id}")
# 2. TrackRepository nutzen
await track_repo.upsert_from_provider(
    title=track.title,
    artist_id=str(album.artist_id.value),  # UUID!
    album_id=str(album.id.value),  # UUID!
    source="spotify",
    spotify_uri=f"spotify:track:{track.id}",
    ...
)
```

---

## Quick Checklist für neue Features

- [ ] Route ruft Service auf (nicht Client/Repo direkt)
- [ ] Service gibt DTOs zurück
- [ ] Plugin konvertiert raw → DTO
- [ ] Repository-Methode auch im Interface (Port) definiert
- [ ] spotify_uri in DB, spotify_id nur als Property
- [ ] Multi-Provider nutzt `can_use()` für Capability-Check
- [ ] Error Handling mit `PluginError` für Plugin-Fehler
- [ ] **Track-Persistenz via `TrackRepository.upsert_from_provider()` (NEU!)**
- [ ] **artist_id/album_id sind IMMER interne UUIDs**

