# Spotify Albums API Roadmap

> **Version:** 1.1  
> **Last Updated:** 2025-11-26  
> **Status:** Phase 1 abgeschlossen (Core Album API implementiert)

---

## Übersicht

Diese Roadmap dokumentiert den aktuellen Stand der Spotify Album API Integration in SoulSpot, was bereits implementiert ist, was noch fehlt und die geplanten nächsten Schritte.

---

## 1. Was wurde schon implementiert?

### ✅ Domain Layer

#### Album Entity (`src/soulspot/domain/entities/__init__.py`)
- **AlbumId** Value Object für typsichere Album-IDs
- **Album** Dataclass mit folgenden Feldern:
  - `id`, `title`, `artist_id` (required)
  - `release_year`, `spotify_uri`, `musicbrainz_id` (optional)
  - `artwork_path`, `genres`, `tags`, `metadata_sources`
  - `created_at`, `updated_at` Timestamps
- Validierung (Titel nicht leer, Release-Jahr 1900-2100)
- Domain-Methode: `update_artwork()`

#### Repository Interface (`src/soulspot/domain/ports/__init__.py`)
- **IAlbumRepository** Port mit:
  - `add()`, `update()`, `delete()`
  - `get_by_id()`, `get_by_artist()`, `get_by_musicbrainz_id()`

### ✅ Infrastructure Layer

#### SpotifyClient (`src/soulspot/infrastructure/integrations/spotify_client.py`)
- **`get_artist_albums(artist_id, access_token, limit)`** ✅
  - Ruft alle Alben eines Künstlers ab
  - Unterstützt Pagination (limit 1-50)
  - Gibt `album` und `single` zurück (keine `appears_on`)

#### MusicBrainz Client
- **`lookup_release(release_id)`** ✅
  - Ruft Album-Metadaten über MusicBrainz ID ab

#### Last.fm Client
- **`get_album_info(artist, album, mbid)`** ✅
  - Ruft Album-Tags und Infos ab

### ✅ Application Layer

#### AlbumCompletenessService (`src/soulspot/application/services/album_completeness.py`)
- **`get_expected_track_count_from_spotify()`** ✅
  - Ruft erwartete Track-Anzahl eines Albums ab
- **`get_expected_track_count_from_musicbrainz()`** ✅
- **`detect_missing_track_numbers()`** ✅
  - Erkennt fehlende Tracks in einem Album

#### DiscographyService (`src/soulspot/application/services/discography_service.py`)
- **`check_discography_completeness()`** ✅
  - Vergleicht lokale Alben mit Spotify-Discography
  - Erkennt fehlende Alben

#### WatchlistService (`src/soulspot/application/services/watchlist_service.py`)
- **`check_new_releases()`** ✅
  - Überwacht Künstler-Alben auf neue Releases
  - Verwendet `get_artist_albums()` von Spotify

### ✅ API Layer

#### Library Router (`/api/library/`)
- `GET /incomplete-albums` - Liste unvollständiger Alben
- `GET /incomplete-albums/{album_id}` - Details zu einem Album

#### Automation Router (`/api/automation/`)
- Discography-Check Endpoints für Album-Vollständigkeit

### ✅ Web UI

- `/library/albums` - Album-Übersicht
- `/library/albums/{album_key}` - Album-Details

---

## 2. Was können wir schon machen?

### Album-Workflows (funktionierend)

| Feature | Status | Beschreibung |
|---------|--------|--------------|
| **Artist-Alben abrufen** | ✅ | Via `get_artist_albums()` |
| **Album-Vollständigkeit prüfen** | ✅ | Vergleich mit Spotify Track-Count |
| **Discography vergleichen** | ✅ | Erkennt fehlende Alben eines Künstlers |
| **Neue Releases erkennen** | ✅ | Watchlist prüft auf neue Alben |
| **Album-Artwork laden** | ⚠️ | Nur indirekt über Track/Playlist |
| **Album-Metadaten speichern** | ✅ | In Datenbank mit Spotify URI |

### Einschränkungen

1. **Kein direkter Album-Fetch** - Es gibt keine `get_album(album_id)` Methode
2. **Kein Batch-Album-Fetch** - `get_albums(ids)` fehlt (nur 1 Album pro Request)
3. **Keine Album-Suche** - `search_album()` nicht implementiert
4. **Kein Saved Albums** - `/me/albums` (User-Bibliothek) nicht verfügbar

---

## 3. Was fehlt noch?

### 🔴 Kritische Features (P0)

| Feature | Spotify Endpoint | Status | Aufwand |
|---------|------------------|--------|---------|
| **`get_album(id)`** | `GET /v1/albums/{id}` | ✅ Implementiert | Klein |
| **`get_albums(ids)`** | `GET /v1/albums?ids=` | ✅ Implementiert | Klein |
| **`get_album_tracks(id)`** | `GET /v1/albums/{id}/tracks` | ✅ Implementiert | Klein |

### 🟡 Wichtige Features (P1)

| Feature | Spotify Endpoint | Status | Aufwand |
|---------|------------------|--------|---------|
| **`search_album(query)`** | `GET /v1/search?type=album` | ❌ Fehlt | Mittel |
| **`get_saved_albums()`** | `GET /v1/me/albums` | ❌ Fehlt | Mittel |
| **Album-Sync-Service** | - | ❌ Fehlt | Groß |

### 🟢 Nice-to-have Features (P2)

| Feature | Spotify Endpoint | Status | Aufwand |
|---------|------------------|--------|---------|
| **`save_album(id)`** | `PUT /v1/me/albums` | ❌ Fehlt | Klein |
| **`remove_saved_album(id)`** | `DELETE /v1/me/albums` | ❌ Fehlt | Klein |
| **`check_album_saved(ids)`** | `GET /v1/me/albums/contains` | ❌ Fehlt | Klein |
| **`get_new_releases()`** | `GET /v1/browse/new-releases` | ❌ Fehlt | Mittel |

---

## 4. Implementation Roadmap

### Phase 1: Core Album API (1-2 Wochen)

#### 4.1.1 ISpotifyClient erweitern

```python
# Neue Methoden im Port hinzufügen
@abstractmethod
async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
    """Get single album by ID."""
    pass

@abstractmethod
async def get_albums(
    self, album_ids: list[str], access_token: str
) -> list[dict[str, Any]]:
    """Batch fetch up to 20 albums by IDs."""
    pass

@abstractmethod
async def get_album_tracks(
    self, album_id: str, access_token: str, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """Get album tracks with pagination."""
    pass
```

#### 4.1.2 SpotifyClient implementieren

```python
async def get_album(self, album_id: str, access_token: str) -> dict[str, Any]:
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/albums/{album_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(dict[str, Any], response.json())

async def get_albums(
    self, album_ids: list[str], access_token: str
) -> list[dict[str, Any]]:
    # Max 20 IDs pro Request
    album_ids = album_ids[:20]
    ids_param = ",".join(album_ids)
    
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/albums",
        params={"ids": ids_param},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    data = response.json()
    return cast(list[dict[str, Any]], data.get("albums", []))
```

### Phase 2: Album-Suche (1 Woche)

```python
async def search_albums(
    self, query: str, access_token: str, limit: int = 20
) -> dict[str, Any]:
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/search",
        params={"q": query, "type": "album", "limit": limit},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(dict[str, Any], response.json())
```

### Phase 3: User's Saved Albums (2 Wochen)

**Voraussetzung:** OAuth Scope `user-library-read` (bereits vorhanden)

```python
async def get_saved_albums(
    self, access_token: str, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/me/albums",
        params={"limit": limit, "offset": offset},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(dict[str, Any], response.json())
```

### Phase 4: Album-Sync-Service (3-4 Wochen)

- Sync User's Saved Albums mit lokaler DB
- Deduplication via UPC
- Artwork-Download
- Track-Mapping zu lokalen Dateien

---

## 5. DB-Schema Erweiterungen

### Notwendige Erweiterungen für AlbumModel

```python
# Neue Felder in der Alembic Migration
spotify_id = Column(String, unique=True, index=True)
album_type = Column(String)  # album, single, compilation
release_date = Column(String)  # Original Spotify Format
release_date_precision = Column(String)  # year, month, day
total_tracks = Column(Integer)
upc = Column(String, unique=True, index=True)  # Universal Product Code
label = Column(String)
popularity = Column(SmallInteger)
images_json = Column(Text)  # JSON Array der Bilder
raw_json = Column(Text)  # Komplette API Response
last_synced_at = Column(DateTime)
```

### Migration Checklist

- [ ] Alembic Migration erstellen
- [ ] AlbumModel erweitern
- [ ] Album Domain Entity erweitern
- [ ] AlbumRepository erweitern
- [ ] Unit Tests aktualisieren

---

## 6. Akzeptanzkriterien

### Phase 1: Core Album API
- [x] `get_album()` gibt vollständiges Album-Objekt zurück
- [x] `get_albums()` unterstützt Batch-Fetch bis 20 IDs
- [x] `get_album_tracks()` paginiert korrekt für große Alben
- [x] Unit Tests mit >80% Coverage
- [x] Integration Tests mit Mock-Spotify-Responses

### Phase 2: Album-Suche
- [ ] Suche findet Alben nach Titel und Künstler
- [ ] Fuzzy-Matching berücksichtigt Tippfehler
- [ ] UI zeigt Suchergebnisse mit Artwork

### Phase 3: Saved Albums
- [ ] Alle gespeicherten Alben werden abgerufen
- [ ] Pagination funktioniert korrekt
- [ ] Sync mit lokaler Bibliothek möglich

---

## 7. Referenzen

### Spotify API Dokumentation
- [Get Album](https://developer.spotify.com/documentation/web-api/reference/get-an-album)
- [Get Several Albums](https://developer.spotify.com/documentation/web-api/reference/get-multiple-albums)
- [Get Album Tracks](https://developer.spotify.com/documentation/web-api/reference/get-an-albums-tracks)
- [Search for Item (Albums)](https://developer.spotify.com/documentation/web-api/reference/search)
- [Get User's Saved Albums](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-albums)

### Interne Dokumentation
- [Spotify Album API Reference](../api/spotify-album-api.md) - Technische API Details
- [Backend Roadmap](../development/backend-roadmap.md) - Gesamtübersicht
- [Library Management](./library-management.md) - Album-Vollständigkeit

---

## 8. Zusammenfassung

| Kategorie | Status |
|-----------|--------|
| **Domain Layer** | ✅ Basis vorhanden |
| **Artist Albums** | ✅ Implementiert |
| **Single Album Fetch** | ✅ Implementiert |
| **Batch Album Fetch** | ✅ Implementiert |
| **Album Tracks** | ✅ Implementiert |
| **Album Search** | ❌ Fehlt |
| **Saved Albums** | ❌ Fehlt |
| **Album Sync** | ❌ Fehlt |

**Nächster Schritt:** Phase 2 - Album-Suche implementieren

---

*Diese Roadmap wird regelmäßig aktualisiert, um den aktuellen Entwicklungsstand widerzuspiegeln.*
