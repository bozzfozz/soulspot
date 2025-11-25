# Spotify API Songs Roadmap

> **Version:** 1.0  
> **Last Updated:** 2025-11-25  
> **Status:** Living Document

---

## Übersicht

Diese Dokumentation bietet einen umfassenden Überblick über die Spotify API Songs/Tracks Integration in SoulSpot:
- Was wurde bereits implementiert?
- Was können wir aktuell machen?
- Was fehlt noch?

---

## Inhaltsverzeichnis

1. [Status-Matrix](#1-status-matrix)
2. [Implementierte Features](#2-implementierte-features)
3. [Aktuelle Möglichkeiten](#3-aktuelle-möglichkeiten)
4. [Fehlende Features](#4-fehlende-features)
5. [Priorisierte Roadmap](#5-priorisierte-roadmap)
6. [Technische Details](#6-technische-details)
7. [Weiterführende Dokumentation](#7-weiterführende-dokumentation)

---

## 1. Status-Matrix

### Spotify Tracks API Integration

| Feature | Status | Priorität | Beschreibung |
|---------|--------|-----------|--------------|
| **Single Track Fetch** | ✅ Implementiert | P0 | `GET /tracks/{id}` |
| **Track Search** | ✅ Implementiert | P0 | `GET /search?type=track` |
| **Batch Track Fetch** | ⏳ Geplant | P1 | `GET /tracks?ids=` (bis 50 IDs) |
| **Audio Features (Single)** | ⏳ Geplant | P2 | `GET /audio-features/{id}` |
| **Audio Features (Batch)** | ⏳ Geplant | P2 | `GET /audio-features?ids=` (bis 100) |
| **Audio Analysis** | ⏳ Optional | P3 | `GET /audio-analysis/{id}` |
| **Album Tracks** | ⏳ Geplant | P1 | `GET /albums/{id}/tracks` |
| **Artist Top Tracks** | ⏳ Geplant | P2 | `GET /artists/{id}/top-tracks` |

### Track-Datenmodell

| Feld | Status | Gespeichert | Verwendung |
|------|--------|-------------|------------|
| `spotify_id` (via URI) | ✅ | `spotify_uri` | Identifikation |
| `name`/`title` | ✅ | `title` | Anzeige, Suche |
| `duration_ms` | ✅ | `duration_ms` | Anzeige, Matching |
| `track_number` | ✅ | `track_number` | Album-Zuordnung |
| `disc_number` | ✅ | `disc_number` | Multi-Disc Alben |
| `explicit` | ❌ | - | Noch nicht gespeichert |
| `isrc` | ✅ | `isrc` | Deduplication |
| `popularity` | ❌ | - | Noch nicht gespeichert |
| `preview_url` | ❌ | - | Noch nicht gespeichert |
| `artists` | ✅ (FK) | `artist_id` | Relation zu Artist |
| `album` | ✅ (FK) | `album_id` | Relation zu Album |
| `musicbrainz_id` | ✅ | `musicbrainz_id` | Cross-Source Matching |
| `audio_features` | ❌ | - | Noch nicht implementiert |
| `raw_spotify_json` | ❌ | - | Noch nicht gespeichert |

### Playlist & Track Sync

| Feature | Status | Beschreibung |
|---------|--------|--------------|
| Playlist Import | ✅ | Playlist mit allen Tracks importieren |
| Playlist Sync | ✅ | Playlist mit Spotify aktualisieren |
| Sync All Playlists | ✅ | Alle Playlists synchronisieren |
| Playlist Library Sync | ✅ | User-Playlists Übersicht |
| Track Pagination | ✅ | Automatische Pagination für große Playlists |
| Missing Tracks Detection | ✅ | Tracks ohne lokale Datei erkennen |

---

## 2. Implementierte Features

### 2.1 SpotifyClient (HTTP Client)

**Datei:** `src/soulspot/infrastructure/integrations/spotify_client.py`

```python
# Implementierte Methoden:
async def get_track(track_id: str, access_token: str) -> dict
async def search_track(query: str, access_token: str, limit: int = 20) -> dict
async def get_playlist(playlist_id: str, access_token: str) -> dict
async def get_user_playlists(access_token: str, limit: int = 50, offset: int = 0) -> dict
async def get_artist_albums(artist_id: str, access_token: str, limit: int = 50) -> list
async def get_followed_artists(access_token: str, limit: int = 50, after: str | None = None) -> dict
```

### 2.2 Track API Endpoints

**Datei:** `src/soulspot/api/routers/tracks.py`

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/tracks/{track_id}` | GET | Track-Details abrufen |
| `/api/tracks/search` | GET | Tracks in Spotify suchen |
| `/api/tracks/{track_id}/download` | POST | Track-Download starten |
| `/api/tracks/{track_id}/enrich` | POST | Metadaten anreichern |
| `/api/tracks/{track_id}/metadata` | PATCH | Metadaten manuell bearbeiten |

### 2.3 Playlist API Endpoints

**Datei:** `src/soulspot/api/routers/playlists.py`

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/playlists/import` | POST | Spotify Playlist importieren |
| `/api/playlists/sync-library` | POST | User-Playlist-Bibliothek synchronisieren |
| `/api/playlists/` | GET | Alle Playlists auflisten |
| `/api/playlists/{id}` | GET | Playlist-Details abrufen |
| `/api/playlists/{id}/sync` | POST | Einzelne Playlist synchronisieren |
| `/api/playlists/sync-all` | POST | Alle Playlists synchronisieren |
| `/api/playlists/{id}/missing-tracks` | GET | Fehlende Tracks identifizieren |
| `/api/playlists/{id}/download-missing` | POST | Fehlende Tracks zum Download vormerken |
| `/api/playlists/{id}/export/m3u` | GET | Als M3U exportieren |
| `/api/playlists/{id}/export/csv` | GET | Als CSV exportieren |
| `/api/playlists/{id}/export/json` | GET | Als JSON exportieren |

### 2.4 OAuth & Authentifizierung

**Status:** ✅ Vollständig implementiert

- OAuth 2.0 mit PKCE Flow
- Automatische Token-Refresh
- Session-basierte Token-Verwaltung
- Scopes: `playlist-read-private`, `playlist-read-collaborative`, `user-library-read`, `user-read-private`, `user-follow-read`

### 2.5 Track-Datenbank

**Schema (TrackModel):**

```python
class TrackModel(Base):
    id: str  # UUID
    title: str
    artist_id: str  # FK zu Artist
    album_id: str | None  # FK zu Album
    duration_ms: int | None
    track_number: int | None
    disc_number: int | None
    spotify_uri: str | None
    musicbrainz_id: str | None
    isrc: str | None
    genre: str | None
    file_path: str | None
    file_hash: str | None
    file_size: int | None
    audio_bitrate: int | None
    audio_format: str | None
    audio_sample_rate: int | None
    is_broken: bool
    last_scanned_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

---

## 3. Aktuelle Möglichkeiten

### Was können wir jetzt machen?

#### ✅ Playlists synchronisieren
```bash
# Playlist importieren (URL oder ID)
POST /api/playlists/import?playlist_id=https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl

# Alle User-Playlists holen
POST /api/playlists/sync-library
```

#### ✅ Tracks suchen
```bash
# In Spotify nach Tracks suchen
GET /api/tracks/search?query=Bohemian%20Rhapsody&limit=20&access_token=...
```

#### ✅ Einzelne Tracks abrufen
```bash
# Track-Details aus lokaler DB
GET /api/tracks/{track_id}
```

#### ✅ Tracks herunterladen
```bash
# Download starten
POST /api/tracks/{track_id}/download?quality=best
```

#### ✅ Metadaten anreichern
```bash
# Von MusicBrainz anreichern
POST /api/tracks/{track_id}/enrich?force_refresh=false
```

#### ✅ Metadaten bearbeiten
```bash
# Manuell bearbeiten (schreibt auch ID3-Tags)
PATCH /api/tracks/{track_id}/metadata
{
  "title": "New Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "genre": "Rock",
  "year": 2023
}
```

#### ✅ Fehlende Tracks erkennen
```bash
# Tracks ohne lokale Datei finden
GET /api/playlists/{playlist_id}/missing-tracks
```

---

## 4. Fehlende Features

### 4.1 SpotifyClient Erweiterungen (Priorität: HOCH)

| Feature | Spotify Endpoint | Priorität | Aufwand |
|---------|------------------|-----------|---------|
| **Batch Track Fetch** | `GET /v1/tracks?ids=` | P1 | Klein |
| **Get Album** | `GET /v1/albums/{id}` | P1 | Klein |
| **Batch Album Fetch** | `GET /v1/albums?ids=` | P1 | Klein |
| **Get Album Tracks** | `GET /v1/albums/{id}/tracks` | P1 | Klein |
| **Get Artist** | `GET /v1/artists/{id}` | P1 | Klein |
| **Artist Top Tracks** | `GET /v1/artists/{id}/top-tracks` | P2 | Klein |

### 4.2 Audio Features Integration (Priorität: MITTEL)

| Feature | Beschreibung | Aufwand |
|---------|--------------|---------|
| **Audio Features Fetch** | Danceability, Energy, Tempo, etc. | Mittel |
| **DB Schema Erweiterung** | `audio_features` JSONB Spalte | Klein |
| **UI Integration** | Audio Features in Track-Ansicht | Mittel |
| **Filter nach Audio Features** | Playlists nach BPM, Energy filtern | Groß |

### 4.3 Datenmodell Erweiterungen (Priorität: MITTEL)

| Feld | Beschreibung | Status |
|------|--------------|--------|
| `explicit` | Explizit-Flag | ❌ Fehlt |
| `popularity` | Beliebtheit (0-100) | ❌ Fehlt |
| `preview_url` | 30s Preview URL | ❌ Fehlt |
| `available_markets` | Verfügbarkeit | ❌ Fehlt |
| `raw_spotify_json` | Komplettes API Response | ❌ Fehlt |
| `last_synced_at` | Letzte Spotify-Sync | ❌ Fehlt |

### 4.4 Sync-Strategien (Priorität: HOCH)

| Feature | Beschreibung | Status |
|---------|--------------|--------|
| **Inkrementeller Sync** | Nur geänderte Tracks aktualisieren | ❌ Fehlt |
| **Snapshot ID Check** | Playlist-Änderung vor Sync prüfen | ❌ Fehlt |
| **Rate Limit Handling** | 429 mit Retry-After behandeln | ⏳ Teilweise |
| **Batch Operations** | Effiziente Bulk-Requests | ⏳ Teilweise |

### 4.5 Deduplication (Priorität: MITTEL)

| Feature | Beschreibung | Status |
|---------|--------------|--------|
| **ISRC-basierte Dedup** | Duplikate via ISRC erkennen | ✅ Grundlage vorhanden |
| **Fuzzy Matching** | Name+Artist+Duration Matching | ✅ In Advanced Search |
| **Match Confidence** | Vertrauensscore speichern | ❌ Fehlt |
| **match_key Generation** | Normalisierter Matching-Key | ❌ Fehlt |

### 4.6 UI/UX Features (Priorität: NIEDRIG)

| Feature | Beschreibung | Status |
|---------|--------------|--------|
| **Preview Player** | 30s Preview abspielen | ❌ Fehlt |
| **Spotify Link** | Direktlink zu Spotify | ⏳ Teilweise |
| **Popularity Display** | Beliebtheit anzeigen | ❌ Fehlt |
| **Audio Features Visualisierung** | Radar-Chart für Features | ❌ Fehlt |

---

## 5. Priorisierte Roadmap

### Phase 1: SpotifyClient Erweiterungen (2-3 Wochen)

**Ziel:** Vollständige Spotify API Abdeckung für Tracks, Albums und Artists

| Task | Priorität | Aufwand | Status |
|------|-----------|---------|--------|
| `get_tracks(ids)` - Batch Tracks | P0 | Klein | 📋 |
| `get_album(id)` - Album Details | P0 | Klein | 📋 |
| `get_albums(ids)` - Batch Albums | P1 | Klein | 📋 |
| `get_album_tracks(id)` - Album Tracklist | P1 | Klein | 📋 |
| `get_artist(id)` - Artist Details | P1 | Klein | 📋 |
| `get_artist_top_tracks(id)` - Top Tracks | P2 | Klein | 📋 |

**Akzeptanzkriterien:**
- [ ] Alle neuen Methoden in `SpotifyClient` implementiert
- [ ] Rate Limiting mit `Retry-After` Header
- [ ] Unit Tests für alle neuen Methoden
- [ ] Dokumentation aktualisiert

### Phase 2: Datenmodell Erweiterungen (1-2 Wochen)

**Ziel:** Vollständige Spotify-Metadaten speichern

| Task | Priorität | Aufwand | Status |
|------|-----------|---------|--------|
| Track-Schema erweitern | P1 | Klein | 📋 |
| Alembic Migration erstellen | P1 | Klein | 📋 |
| Repository-Methoden erweitern | P1 | Klein | 📋 |
| `raw_spotify_json` für alle Entitäten | P1 | Klein | 📋 |

**Neue Felder:**
```python
# TrackModel Erweiterungen
explicit: bool | None
popularity: int | None  # 0-100
preview_url: str | None
available_markets: list[str] | None  # JSON
raw_spotify_json: dict | None  # JSONB
last_synced_at: datetime | None
```

### Phase 3: Audio Features (2-3 Wochen)

**Ziel:** Audio Features von Spotify abrufen und nutzen

| Task | Priorität | Aufwand | Status |
|------|-----------|---------|--------|
| `get_audio_features(id)` | P2 | Klein | 📋 |
| `get_audio_features_batch(ids)` | P2 | Klein | 📋 |
| DB Schema für Audio Features | P2 | Klein | 📋 |
| Sync bei Playlist Import | P2 | Mittel | 📋 |
| API Endpoint für Audio Features | P2 | Klein | 📋 |

**Schema:**
```python
# Als JSONB Spalte oder separate Tabelle
audio_features = {
    "danceability": 0.735,
    "energy": 0.578,
    "key": 5,
    "loudness": -11.84,
    "mode": 0,
    "speechiness": 0.0461,
    "acousticness": 0.514,
    "instrumentalness": 0.0902,
    "liveness": 0.159,
    "valence": 0.624,
    "tempo": 98.002,
    "time_signature": 4
}
```

### Phase 4: Optimierungen (2-4 Wochen)

**Ziel:** Performance und Effizienz verbessern

| Task | Priorität | Aufwand | Status |
|------|-----------|---------|--------|
| Batch-Sync für Playlists | P1 | Mittel | 📋 |
| Snapshot ID für Change Detection | P1 | Klein | 📋 |
| Inkrementeller Track-Sync | P2 | Mittel | 📋 |
| Cache für häufige API-Calls | P2 | Mittel | 📋 |
| Rate Limit Dashboard | P3 | Klein | 📋 |

---

## 6. Technische Details

### 6.1 Batch API Nutzung

Spotify unterstützt effiziente Batch-Requests:

```python
# Bis zu 50 Tracks pro Request
tracks = await spotify_client.get_tracks(
    ids="id1,id2,id3,...",
    access_token=token
)

# Bis zu 100 Audio Features pro Request
features = await spotify_client.get_audio_features_batch(
    ids="id1,id2,id3,...",
    access_token=token
)

# Bis zu 20 Albums pro Request
albums = await spotify_client.get_albums(
    ids="id1,id2,id3,...",
    access_token=token
)
```

### 6.2 Rate Limiting Best Practices

```python
async def handle_rate_limit(response: httpx.Response) -> None:
    """Handle Spotify rate limiting with Retry-After header."""
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        logger.warning(f"Rate limited. Retrying after {retry_after}s")
        await asyncio.sleep(retry_after)
```

### 6.3 ISRC Deduplication

```python
async def find_track_by_isrc(isrc: str) -> Track | None:
    """Find existing track by ISRC for deduplication."""
    return await track_repository.get_by_isrc(isrc)

async def should_import_track(track_data: dict) -> bool:
    """Check if track should be imported or is already present."""
    isrc = track_data.get("external_ids", {}).get("isrc")
    if isrc:
        existing = await find_track_by_isrc(isrc)
        if existing:
            logger.info(f"Track already exists: {existing.title}")
            return False
    return True
```

### 6.4 Empfohlene API Endpoints

```python
# SpotifyClient Erweiterungen (empfohlen)
class SpotifyClient:
    # Tracks
    async def get_tracks(self, ids: str, access_token: str) -> dict:
        """Batch fetch up to 50 tracks."""
        
    async def get_audio_features(self, track_id: str, access_token: str) -> dict:
        """Get audio features for a single track."""
        
    async def get_audio_features_batch(self, ids: str, access_token: str) -> dict:
        """Batch fetch audio features for up to 100 tracks."""
    
    # Albums
    async def get_album(self, album_id: str, access_token: str) -> dict:
        """Get album details."""
        
    async def get_albums(self, ids: str, access_token: str) -> dict:
        """Batch fetch up to 20 albums."""
        
    async def get_album_tracks(
        self, album_id: str, access_token: str, limit: int = 50, offset: int = 0
    ) -> dict:
        """Get paginated album tracks."""
    
    # Artists
    async def get_artist(self, artist_id: str, access_token: str) -> dict:
        """Get artist details."""
        
    async def get_artist_top_tracks(
        self, artist_id: str, market: str, access_token: str
    ) -> dict:
        """Get artist's top tracks for a market."""
```

---

## 7. Weiterführende Dokumentation

### Interne Dokumentation

- [Spotify Tracks API](spotify-tracks.md) - Detaillierte Track-Feld Referenz
- [Spotify Artist API](spotify-artist-api.md) - Artist Integration
- [Spotify Album API](spotify-album-api.md) - Album Integration
- [Spotify Metadata Reference](spotify-metadata-reference.md) - Vollständige Feld-Referenz
- [Backend Roadmap](../development/backend-roadmap.md) - Entwicklungsplan
- [Advanced Search API](advanced-search-api.md) - Such- und Matching-Funktionen

### Externe Ressourcen

- [Spotify Web API Reference](https://developer.spotify.com/documentation/web-api)
- [Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)
- [Get Several Tracks](https://developer.spotify.com/documentation/web-api/reference/get-several-tracks)
- [Get Audio Features](https://developer.spotify.com/documentation/web-api/reference/get-audio-features)
- [Get Several Audio Features](https://developer.spotify.com/documentation/web-api/reference/get-several-audio-features)

---

## Changelog

| Datum | Version | Änderungen |
|-------|---------|------------|
| 2025-11-25 | 1.0 | Initiale Dokumentation erstellt |

---

**Ende der Spotify API Songs Roadmap**
