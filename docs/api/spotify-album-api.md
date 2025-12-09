# ⚠️ DEPRECATED - Spotify Album API Integration

> **Status:** ❌ DEPRECATED  
> **Replaced By:** [library-management-api.md](./library-management-api.md)  
> **Date Deprecated:** 9. Dezember 2025  
> **Reason:** No dedicated `albums.py` router exists. Album functionality is implemented in `library.py` (35 endpoints) and managed via library management features.

**DO NOT USE THIS FILE. See [library-management-api.md](./library-management-api.md) for current album management API.**

---

<details>
<summary>Original Content (Archived)</summary>

# Spotify Album API Integration

> **Version:** 1.0  
> **Last Updated:** 2025-11-25  
> **Status:** Dokumentation / Referenz für zukünftige Implementation

---

## Übersicht

Diese Dokumentation beschreibt die Spotify Album API und wie sie in SoulSpot integriert werden kann, um Album-Metadaten zu synchronisieren, zu speichern und für Deduplication zu nutzen.

---

## Relevante Spotify-Endpoints (Album-bezogen)

### Primäre Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/v1/albums/{id}` | GET | Vollständiges Albumobjekt inkl. paginierter Track-Liste |
| `/v1/albums?ids={ids}` | GET | Batch-Fetch bis zu 20 Album-IDs für effiziente Abfragen |
| `/v1/albums/{id}/tracks` | GET | Nur Trackliste (paginiert, für Alben mit 50+ Tracks) |
| `/v1/artists/{id}/albums` | GET | Alle Alben eines Artists (optional für Discography-Sync) |

### Rate Limiting

- **429 Too Many Requests:** Retry-After Header beachten
- **Empfohlene Concurrency:** Moderat (2-5 parallele Requests)
- **Batch-Requests bevorzugen:** Reduziert API-Calls signifikant

---

## Empfohlene DB-Felder für Album-Entität

### Minimal erforderliche Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `spotify_id` | `TEXT UNIQUE NOT NULL` | Spotify Album ID |
| `name` / `title` | `TEXT NOT NULL` | Albumtitel |
| `album_type` | `TEXT` | `album`, `single`, `compilation` |
| `release_date` | `TEXT` | Original-Format von Spotify |
| `release_date_precision` | `TEXT` | `year`, `month`, `day` |
| `total_tracks` | `INTEGER` | Gesamtzahl der Tracks |
| `images` | `JSONB` | Array: `[{url, height, width}, ...]` |
| `artists` | `JSONB` | Array: `[{spotify_id, name}, ...]` |
| `external_ids` | `JSONB` | `{upc: "..."}` - kritisch für Dedup! |
| `label` | `TEXT` | Plattenlabel |
| `last_synced_at` | `TIMESTAMPTZ` | Zeitpunkt der letzten Synchronisation |

</details>
| `raw_json` | `JSONB` | Komplettes API-Response für spätere Nutzung |

### Optionale Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `popularity` | `SMALLINT` | Album-Beliebtheit (0-100) |
| `available_markets` | `TEXT[]` | Länder, in denen Album verfügbar ist |
| `href` | `TEXT` | Spotify API URL |
| `external_urls.spotify` | `TEXT` | Spotify Web Player URL |
| `copyrights` | `JSONB` | Array: `[{text, type}, ...]` |
| `album_group` | `TEXT` | Von Artist-Albums-Endpoint: `appears_on` |
| `genres` | `TEXT[]` | Selten auf Album-Level (meist auf Artist) |

---

## DB-Schema (PostgreSQL)

```sql
CREATE TABLE albums (
    id SERIAL PRIMARY KEY,
    spotify_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    album_type TEXT,
    release_date TEXT,
    release_date_precision TEXT,
    total_tracks INTEGER,
    images JSONB,
    artists JSONB,  -- [{spotify_id, name}, ...]
    external_ids JSONB,  -- {upc: "..."}
    label TEXT,
    popularity SMALLINT,
    available_markets TEXT[],
    copyrights JSONB,
    href TEXT,
    external_url TEXT,
    raw JSONB,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX ix_albums_spotify_id ON albums(spotify_id);
CREATE INDEX ix_albums_name_lower ON albums(LOWER(name));
CREATE INDEX ix_albums_popularity ON albums(popularity);
CREATE INDEX ix_albums_last_synced_at ON albums(last_synced_at);

-- Optional: GIN-Index für JSON-Felder wenn häufig durchsucht
CREATE INDEX ix_albums_external_ids ON albums USING GIN(external_ids);
```

### Optionale Relationstabellen

```sql
-- Für normalisierte Artist-Album-Beziehungen
CREATE TABLE album_artists (
    album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    artist_spotify_id TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    position INTEGER DEFAULT 0,  -- Reihenfolge der Artists
    PRIMARY KEY (album_id, artist_spotify_id)
);

-- Für Album-Track-Beziehungen (wenn Tracks separat gespeichert)
CREATE TABLE album_tracks (
    album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    track_spotify_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    duration_ms INTEGER,
    PRIMARY KEY (album_id, track_spotify_id)
);
```

---

## Mapping: Spotify API → Datenbank

| Spotify API Feld | DB Feld | Hinweise |
|------------------|---------|----------|
| `id` | `spotify_id` | Primärer Identifier |
| `name` | `name` | Albumtitel |
| `album_type` | `album_type` | `album`, `single`, `compilation` |
| `release_date` | `release_date` | String speichern, nicht parsen! |
| `release_date_precision` | `release_date_precision` | Für korrektes Parsen |
| `total_tracks` | `total_tracks` | Gesamtzahl |
| `images` | `images` | JSONB Array direkt speichern |
| `artists` | `artists` | JSONB oder Relations-Tabelle |
| `external_ids.upc` | `external_ids` | JSONB mit UPC |
| `label` | `label` | Plattenlabel |
| `popularity` | `popularity` | 0-100 Score |
| `external_urls.spotify` | `external_url` | Web Player Link |
| *(gesamte Response)* | `raw` | Für zukünftige Felder |

---

## Beispiel: Spotify Album JSON Response

```json
{
  "album_type": "album",
  "artists": [
    {
      "id": "1Xyo4u8uXC1ZmMpatF05PJ",
      "name": "The Weeknd"
    }
  ],
  "available_markets": ["DE", "US", "GB"],
  "copyrights": [
    {
      "text": "© 2024 XO",
      "type": "C"
    },
    {
      "text": "℗ 2024 XO",
      "type": "P"
    }
  ],
  "external_ids": {
    "upc": "602435327891"
  },
  "external_urls": {
    "spotify": "https://open.spotify.com/album/5T8EDUDqKcs6OSOwEsfqG7"
  },
  "href": "https://api.spotify.com/v1/albums/5T8EDUDqKcs6OSOwEsfqG7",
  "id": "5T8EDUDqKcs6OSOwEsfqG7",
  "images": [
    {
      "height": 640,
      "url": "https://i.scdn.co/image/ab67616d0000b273...",
      "width": 640
    },
    {
      "height": 300,
      "url": "https://i.scdn.co/image/ab67616d00001e02...",
      "width": 300
    },
    {
      "height": 64,
      "url": "https://i.scdn.co/image/ab67616d00004851...",
      "width": 64
    }
  ],
  "name": "Dawn FM",
  "label": "XO / Republic Records",
  "popularity": 87,
  "release_date": "2022-01-07",
  "release_date_precision": "day",
  "total_tracks": 16,
  "tracks": {
    "href": "https://api.spotify.com/v1/albums/5T8EDUDqKcs6OSOwEsfqG7/tracks?offset=0&limit=50",
    "items": [
      {
        "id": "2LBqCSwhJGcFQeTHMVGwy3",
        "name": "Dawn FM",
        "track_number": 1,
        "duration_ms": 92626
      }
    ],
    "limit": 50,
    "next": null,
    "offset": 0,
    "total": 16
  }
}
```

---

## Sync-Strategie

### Authentifizierung

- **Client Credentials Flow:** Ausreichend für öffentliche Metadaten
- Kein User-Login erforderlich für Album-Daten

### Batch-Fetching (Empfohlen)

```python
# Effizient: Bis zu 20 Alben pro Request
album_ids = ["id1", "id2", "id3", ...]
chunks = [album_ids[i:i+20] for i in range(0, len(album_ids), 20)]

for chunk in chunks:
    ids_param = ",".join(chunk)
    response = await client.get(f"/v1/albums?ids={ids_param}")
    # Verarbeite albums_response["albums"]
```

### Track-Fetching-Entscheidung

```python
# Für jedes Album entscheiden:
if need_track_relations:
    if album["total_tracks"] <= 50:
        # Tracks sind bereits in album["tracks"]["items"]
        tracks = album["tracks"]["items"]
    else:
        # Pagination erforderlich für große Alben
        tracks = await fetch_all_album_tracks(album_id)
```

### Raw JSON Persistierung

```python
# IMMER das komplette Response speichern!
album_model.raw = spotify_response

# Ermöglicht spätere Feature-Erweiterung ohne Re-Fetch
# Beispiel: Später "genres" hinzufügen ohne API-Call
```

---

## Deduplication-Strategie

### Primär: UPC (Universal Product Code)

```python
def find_duplicate_by_upc(album_data: dict) -> Album | None:
    upc = album_data.get("external_ids", {}).get("upc")
    if upc:
        return await album_repo.find_by_upc(upc)
    return None
```

**Vorteile:**
- Weltweit eindeutig pro Release
- Identifiziert gleiche Alben in verschiedenen Märkten
- Erkennt Deluxe/Standard-Editionen als unterschiedlich

### Fallback: Fuzzy Matching

```python
def find_duplicate_fuzzy(album_data: dict) -> Album | None:
    """Fallback wenn kein UPC vorhanden."""
    title_normalized = normalize(album_data["name"])
    artist_name = album_data["artists"][0]["name"]
    release_year = album_data["release_date"][:4]
    
    candidates = await album_repo.find_by_artist_and_year(
        artist_name, release_year
    )
    
    for candidate in candidates:
        if fuzzy_match(candidate.title, title_normalized) > 0.85:
            return candidate
    
    return None
```

### Editions-Handling

```text
Problem: "Album (Deluxe)" vs "Album" vs "Album (Remastered)"

Lösungsansätze:
1. UPC unterscheidet korrekt → verschiedene Releases
2. UI zeigt alle Editionen gruppiert an
3. User kann "Primary Edition" markieren
4. Download prüft ob bereits eine Edition vorhanden
```

---

## Release Date Parsing

### Wichtig: Precision beachten!

```python
def parse_release_date(date_str: str, precision: str) -> date:
    """
    Parse Spotify release date mit korrekter Precision.
    
    precision="year"  → "2022"       → 2022-01-01
    precision="month" → "2022-03"    → 2022-03-01
    precision="day"   → "2022-03-15" → 2022-03-15
    """
    match precision:
        case "year":
            return date(int(date_str), 1, 1)
        case "month":
            year, month = date_str.split("-")
            return date(int(year), int(month), 1)
        case "day":
            return date.fromisoformat(date_str)
        case _:
            # Fallback: Versuche ISO-Format
            return date.fromisoformat(date_str)
```

### Speicherempfehlung

```sql
-- Speichere Original-String + Precision
release_date TEXT,           -- "2022-03-15" oder "2022"
release_date_precision TEXT, -- "day", "month", "year"

-- NICHT: release_date DATE → verliert Precision-Info!
```

---

## Verwendung in SoulSpot

### Album-Seiten

- Zeige Images, Release Date, Label
- Liste Tracks (wenn gefetcht)
- Link zu Spotify Web Player
- Zeige Copyright-Informationen

### Kandidaten-Generierung (Downloads)

```python
def prioritize_download_candidates(albums: list[Album]) -> list[Album]:
    """Nutze Popularity für Download-Priorisierung."""
    return sorted(
        albums,
        key=lambda a: (a.popularity or 0),
        reverse=True
    )
```

### Dedup-Logik vor Download

```python
async def should_download_album(album_data: dict) -> bool:
    """Prüfe ob Album bereits vorhanden (über UPC/ISRC)."""
    # 1. Prüfe UPC
    if existing := await find_by_upc(album_data):
        logger.info(f"Album bereits vorhanden: {existing.title}")
        return False
    
    # 2. Prüfe existierende Tracks via ISRC
    tracks = album_data.get("tracks", {}).get("items", [])
    for track in tracks:
        isrc = track.get("external_ids", {}).get("isrc")
        if isrc and await track_exists_by_isrc(isrc):
            logger.info(f"Track bereits vorhanden: {track['name']}")
            # Entscheide: Skip oder partial download?
    
    return True
```

### UI: Editionen-Anzeige

```html
<!-- Zeige mehrere Editionen gruppiert -->
<div class="album-editions">
  <h3>Dawn FM</h3>
  <ul>
    <li>Standard Edition (2022) ✓ Downloaded</li>
    <li>Deluxe Edition (2022) - 3 bonus tracks</li>
    <li>Alternate World (2022) - Different artwork</li>
  </ul>
  <span class="hint">Gleicher UPC = Duplikat erkannt</span>
</div>
```

---

## Rate Limiting & Error Handling

### 429 Too Many Requests

```python
async def spotify_request_with_retry(url: str) -> dict:
    """Request mit automatischem Retry bei Rate Limit."""
    max_retries = 3
    
    for attempt in range(max_retries):
        response = await client.get(url)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            continue
        
        response.raise_for_status()
        return response.json()
    
    raise SpotifyRateLimitError("Max retries exceeded")
```

### Batch-Job-Empfehlungen

```python
# Moderate Concurrency
CONCURRENT_REQUESTS = 3
DELAY_BETWEEN_BATCHES = 0.5  # Sekunden

async def sync_all_albums(album_ids: list[str]):
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    
    async def fetch_with_limit(ids_chunk: list[str]):
        async with semaphore:
            result = await spotify_client.get_albums(ids_chunk)
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)
            return result
    
    chunks = [album_ids[i:i+20] for i in range(0, len(album_ids), 20)]
    results = await asyncio.gather(*[fetch_with_limit(c) for c in chunks])
    return [album for batch in results for album in batch]
```

---

## Images-Handling

### Spotify liefert 3 Größen

```python
def get_best_image(images: list[dict], target_width: int = 300) -> str | None:
    """Wähle passende Bildgröße."""
    if not images:
        return None
    
    # Spotify sortiert nach Größe (größtes zuerst)
    # Typische Größen: 640, 300, 64
    for img in images:
        if img.get("width", 0) >= target_width:
            return img["url"]
    
    # Fallback: Größtes verfügbares
    return images[0]["url"] if images else None
```

### CDN-Caching (Optional)

```python
# Option 1: Direkt Spotify CDN URLs nutzen (empfohlen)
image_url = album["images"][0]["url"]
# URLs sind stabil und cachebar

# Option 2: Proxy/Cache auf eigenem CDN
# Nur wenn Offline-Support oder Bandwidth-Kontrolle nötig
```

---

## Weiterführende Dokumentation

- [Spotify Web API Reference](https://developer.spotify.com/documentation/web-api)
- [Album Object](https://developer.spotify.com/documentation/web-api/reference/get-an-album)
- [Get Several Albums](https://developer.spotify.com/documentation/web-api/reference/get-multiple-albums)
- [Get Album Tracks](https://developer.spotify.com/documentation/web-api/reference/get-an-albums-tracks)
- [Get Artist's Albums](https://developer.spotify.com/documentation/web-api/reference/get-an-artists-albums)

---

## Implementation Checklist

Diese Checklist kann für die zukünftige Implementation verwendet werden:

- [ ] `AlbumModel` erweitern (spotify_id, album_type, release_date, etc.)
- [ ] Alembic Migration erstellen
- [ ] `Album` Domain Entity erweitern
- [ ] `ISpotifyClient` Port erweitern (get_album, get_albums, get_album_tracks)
- [ ] `SpotifyClient` Implementation
- [ ] `AlbumRepository` erweitern (find_by_spotify_id, find_by_upc)
- [ ] AlbumSyncService erstellen
- [ ] Deduplication-Service implementieren
- [ ] Unit Tests schreiben
- [ ] Integration Tests schreiben

---

*Diese Dokumentation dient als Referenz für die zukünftige Implementation der Spotify Album API Integration in SoulSpot.*
