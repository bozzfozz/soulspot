# Spotify Playlist API Integration

> **Version:** 1.0  
> **Last Updated:** 2025-11-25  
> **Status:** Dokumentation / Referenz für zukünftige Implementation

---

## Übersicht

Diese Dokumentation beschreibt die Spotify Playlist API und wie sie in SoulSpot integriert werden kann, um Playlist-Metadaten und -Tracks zu synchronisieren, zu speichern und für Download-Queues zu nutzen.

---

## Relevante Spotify-Endpoints (Playlist-bezogen)

### Primäre Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/v1/playlists/{playlist_id}` | GET | Vollständiges Playlist-Objekt inkl. Metadaten |
| `/v1/playlists/{playlist_id}/tracks` | GET | Paginierte Liste der Playlist-Items (added_at, added_by, track) |
| `/v1/me/playlists` | GET | Listen der Playlists des aktuellen Users |
| `/v1/users/{user_id}/playlists` | GET | Listen der öffentlichen Playlists eines Users |
| `/v1/playlists/{playlist_id}/images` | GET | Playlist-Cover (falls getrennt abgerufen) |

### Modifikations-Endpoints (erfordern User OAuth)

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/v1/playlists/{playlist_id}` | PUT | Playlist-Details ändern (Name, Beschreibung, public/private) |
| `/v1/playlists/{playlist_id}/tracks` | POST | Tracks zur Playlist hinzufügen |
| `/v1/playlists/{playlist_id}/tracks` | PUT | Playlist-Tracks ersetzen oder neu ordnen |
| `/v1/playlists/{playlist_id}/tracks` | DELETE | Tracks aus Playlist entfernen |
| `/v1/users/{user_id}/playlists` | POST | Neue Playlist erstellen |

### Rate Limiting

- **429 Too Many Requests:** `Retry-After` Header beachten
- **Empfohlene Concurrency:** Moderat (2-5 parallele Requests)
- **Pagination:** Playlist-Tracks sind paginiert (max 100 Items pro Request)

---

## Auth & Scopes

### Öffentliche Playlists

- **Client Credentials Flow** reicht aus für öffentliche Playlist-Metadaten
- Kein User-Login erforderlich

### Private/Geschützte Playlists

User OAuth mit folgenden Scopes erforderlich:

| Scope | Beschreibung |
|-------|--------------|
| `playlist-read-private` | Lesen privater Playlists |
| `playlist-read-collaborative` | Lesen kollaborativer Playlists |
| `playlist-modify-public` | Öffentliche Playlists erstellen/ändern |
| `playlist-modify-private` | Private Playlists erstellen/ändern |

### Rate-Limits und Error Handling

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

---

## Empfohlene DB-Felder für Playlist-Entität

### Minimale Felder (Playlist)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `spotify_id` | `TEXT UNIQUE NOT NULL` | Spotify Playlist ID |
| `name` | `TEXT NOT NULL` | Playlist-Name |
| `description` | `TEXT NULL` | Playlist-Beschreibung (kann HTML enthalten) |
| `owner` | `JSONB` | Owner-Objekt: `{id, display_name}` |
| `public` | `BOOLEAN NULL` | Public oder private (null = unbekannt) |
| `collaborative` | `BOOLEAN` | Kollaborative Playlist |
| `followers_total` | `INTEGER` | `followers.total` - Anzahl Follower |
| `images` | `JSONB` | Cover-Images Array: `[{url, height, width}, ...]` |
| `snapshot_id` | `TEXT` | Wichtig für Incremental Sync / Change Detection |
| `tracks_total` | `INTEGER` | `tracks.total` - Gesamtzahl Tracks |
| `external_url` | `TEXT` | Spotify Web Player URL |
| `last_synced_at` | `TIMESTAMPTZ` | Zeitpunkt der letzten Synchronisation |
| `raw_json` | `JSONB` | Komplettes API-Response für spätere Nutzung |

### Optionale Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `href` | `TEXT` | Spotify API URL |
| `uri` | `TEXT` | Spotify URI (`spotify:playlist:...`) |
| `primary_color` | `TEXT` | Primärfarbe der Playlist (selten) |

---

## Playlist-Items / Tracks (wichtig zu speichern)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `playlist_id` | `FK` | Fremdschlüssel zu `playlists.id` |
| `position` | `INTEGER` | Position in der Playlist (0-basiert, explizit speichern!) |
| `added_at` | `TIMESTAMPTZ` | Wann zur Playlist hinzugefügt |
| `added_by` | `JSONB` | User-Objekt: `{id, display_name}` |
| `is_local` | `BOOLEAN` | Lokale Tracks (kein Spotify ID) |
| `track_spotify_id` | `TEXT NULL` | `track.id` (null bei lokalen Tracks oder gelöschten Tracks) |
| `track_raw` | `JSONB` | Embedded Track-Payload für Offline-Referenz |

### Wichtige Hinweise zu Playlist-Items

- **`track` kann `null` sein:** Gelöschte oder regional nicht verfügbare Tracks
- **Lokale Tracks:** `is_local: true` → kein Spotify ID vorhanden
- **Reihenfolge ist kritisch:** `position` muss exakt gespeichert werden
- **`added_by` bei kollaborativen Playlists:** Zeigt wer welchen Track hinzugefügt hat

---

## DB-Schema (PostgreSQL, kompakt)

### Playlists Tabelle

```sql
CREATE TABLE playlists (
    id SERIAL PRIMARY KEY,
    spotify_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    owner JSONB,  -- {id, display_name}
    public BOOLEAN,
    collaborative BOOLEAN DEFAULT FALSE,
    followers_total INTEGER DEFAULT 0,
    images JSONB,  -- [{url, height, width}, ...]
    snapshot_id TEXT,
    tracks_total INTEGER DEFAULT 0,
    external_url TEXT,
    raw JSONB,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX ix_playlists_spotify_id ON playlists(spotify_id);
CREATE INDEX ix_playlists_name_lower ON playlists(LOWER(name));
CREATE INDEX ix_playlists_owner ON playlists((owner->>'id'));
CREATE INDEX ix_playlists_snapshot_id ON playlists(snapshot_id);
CREATE INDEX ix_playlists_last_synced_at ON playlists(last_synced_at);
```

### Playlist-Items Tabelle

```sql
CREATE TABLE playlist_items (
    id SERIAL PRIMARY KEY,
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_at TIMESTAMPTZ,
    added_by JSONB,  -- {id, display_name}
    is_local BOOLEAN DEFAULT FALSE,
    track_spotify_id TEXT,
    track_raw JSONB,  -- Embedded track payload for reference
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX ix_playlist_items_playlist_id ON playlist_items(playlist_id);
CREATE INDEX ix_playlist_items_track_spotify_id ON playlist_items(track_spotify_id);
CREATE INDEX ix_playlist_items_position ON playlist_items(playlist_id, position);

-- Unique constraint: Ein Track kann nur einmal pro Position in einer Playlist sein
CREATE UNIQUE INDEX ix_playlist_items_unique_position ON playlist_items(playlist_id, position);

-- Alternativ: Wenn duplicate tracks in einer Playlist erlaubt sind
-- CREATE INDEX ix_playlist_items_added_at ON playlist_items(playlist_id, track_spotify_id, added_at);
```

---

## Mapping: Spotify API → Datenbank

### Playlist-Objekt Mapping

| Spotify API Feld | DB Feld | Hinweise |
|------------------|---------|----------|
| `id` | `spotify_id` | Primärer Identifier |
| `name` | `name` | Playlist-Titel |
| `description` | `description` | Kann HTML/Emojis enthalten |
| `owner.id` + `owner.display_name` | `owner` | JSONB speichern |
| `public` | `public` | Kann `null` sein |
| `collaborative` | `collaborative` | Boolean |
| `followers.total` | `followers_total` | Integer |
| `images` | `images` | JSONB Array direkt speichern |
| `snapshot_id` | `snapshot_id` | Für Change Detection |
| `tracks.total` | `tracks_total` | Gesamtzahl |
| `external_urls.spotify` | `external_url` | Web Player Link |
| *(gesamte Response)* | `raw` | Für zukünftige Felder |

### Playlist-Item Mapping

| Spotify API Feld | DB Feld | Hinweise |
|------------------|---------|----------|
| *(array index)* | `position` | Explizit speichern (0-basiert) |
| `added_at` | `added_at` | ISO 8601 Timestamp |
| `added_by.id` + `added_by.display_name` | `added_by` | JSONB |
| `is_local` | `is_local` | Boolean |
| `track.id` | `track_spotify_id` | Kann null sein |
| *(gesamtes track object)* | `track_raw` | Embedded Track für Referenz |

---

## Wichtige Besonderheiten & Edge Cases

### 1. snapshot_id für Change Detection

```python
async def should_sync_playlist(playlist_id: str, stored_snapshot: str) -> bool:
    """Prüfe ob Playlist geändert wurde via snapshot_id."""
    current = await spotify_client.get_playlist(playlist_id)
    return current["snapshot_id"] != stored_snapshot
```

- Jede Playlist hat eine eindeutige `snapshot_id`
- Ändert sich bei JEDER Modifikation (Tracks hinzufügen/entfernen/umsortieren)
- Nutze für cheap change detection: nur syncen wenn snapshot_id anders

### 2. Pagination für Track-Listen

```python
async def fetch_all_playlist_tracks(playlist_id: str, access_token: str) -> list:
    """Alle Tracks einer Playlist holen (mit Pagination)."""
    all_items = []
    offset = 0
    limit = 100  # Spotify max
    
    while True:
        response = await spotify_client.get_playlist_tracks(
            playlist_id, access_token, limit=limit, offset=offset
        )
        all_items.extend(response["items"])
        
        if response["next"] is None:
            break
        
        offset += limit
    
    return all_items
```

### 3. Lokale Tracks (is_local: true)

```python
def handle_playlist_item(item: dict) -> dict:
    """Verarbeite Playlist-Item inkl. lokaler Tracks."""
    if item.get("is_local"):
        # Kein Spotify ID vorhanden!
        return {
            "is_local": True,
            "track_spotify_id": None,
            "track_raw": item.get("track"),  # Enthält lokale Metadaten
            "name": item.get("track", {}).get("name", "Unknown"),
        }
    
    track = item.get("track")
    if track is None:
        # Track wurde gelöscht oder ist nicht verfügbar
        return {
            "is_local": False,
            "track_spotify_id": None,
            "track_raw": None,
            "unavailable": True,
        }
    
    return {
        "is_local": False,
        "track_spotify_id": track["id"],
        "track_raw": track,
    }
```

### 4. Gelöschte/Nicht verfügbare Tracks

- `track` object kann `null` sein (deleted track or unavailable in market)
- **Behalte** das `playlist_item`, markiere aber Track als fehlend
- Nutze `track_raw` um die letzte bekannte Info zu bewahren

### 5. Reihenfolge ist wichtig

```python
# WICHTIG: Position explizit speichern!
for index, item in enumerate(playlist_tracks["items"]):
    playlist_item = {
        "position": index,  # Nicht einfach weglassen!
        "added_at": item["added_at"],
        # ...
    }
```

### 6. Kollaborative Playlists

- Mehrere User können Tracks hinzufügen
- `added_by` zeigt wer welchen Track hinzugefügt hat
- Bei Sync: `added_by` mitführen für vollständige History

### 7. Followers (followers.total)

- Nützlich für Ranking/Popularität
- Kann aufwendig sein, häufig zu aktualisieren
- Empfehlung: nur bei explizitem Sync aktualisieren

### 8. Kein Webhook für Playlists

- Spotify hat KEINEN allgemeinen Webhook für Playlist-Änderungen
- Lösung: Polling oder User-initiated re-sync ("Sync Playlist" Button)

---

## Sync-Strategie

### Initial Import

```python
async def import_playlist(playlist_id: str, access_token: str) -> None:
    """Erstmaliger Import einer Playlist."""
    # 1. Playlist-Metadaten holen
    playlist = await spotify_client.get_playlist(playlist_id, access_token)
    
    # 2. Playlist in DB speichern
    stored_playlist = await playlist_repo.upsert({
        "spotify_id": playlist["id"],
        "name": playlist["name"],
        "description": playlist.get("description"),
        "owner": {
            "id": playlist["owner"]["id"],
            "display_name": playlist["owner"].get("display_name"),
        },
        "public": playlist.get("public"),
        "collaborative": playlist.get("collaborative", False),
        "followers_total": playlist.get("followers", {}).get("total", 0),
        "images": playlist.get("images", []),
        "snapshot_id": playlist["snapshot_id"],
        "tracks_total": playlist.get("tracks", {}).get("total", 0),
        "external_url": playlist.get("external_urls", {}).get("spotify"),
        "raw": playlist,
        "last_synced_at": utc_now(),
    })
    
    # 3. Tracks via Pagination holen
    all_tracks = await fetch_all_playlist_tracks(playlist_id, access_token)
    
    # 4. Playlist-Items upserten
    for position, item in enumerate(all_tracks):
        track = item.get("track")
        await playlist_item_repo.upsert({
            "playlist_id": stored_playlist.id,
            "position": position,
            "added_at": item.get("added_at"),
            "added_by": {
                "id": item.get("added_by", {}).get("id"),
                "display_name": item.get("added_by", {}).get("display_name"),
            },
            "is_local": item.get("is_local", False),
            "track_spotify_id": track["id"] if track else None,
            "track_raw": track,
        })
```

### Incremental Sync

```python
async def sync_playlist(playlist_id: str, access_token: str) -> SyncResult:
    """Inkrementeller Sync einer bereits importierten Playlist."""
    # 1. Stored Playlist laden
    stored = await playlist_repo.find_by_spotify_id(playlist_id)
    if not stored:
        raise PlaylistNotFoundError(playlist_id)
    
    # 2. Aktuelle Metadaten von Spotify holen
    current = await spotify_client.get_playlist(playlist_id, access_token)
    
    # 3. snapshot_id vergleichen
    if current["snapshot_id"] == stored.snapshot_id:
        logger.info(f"Playlist {playlist_id} unchanged (same snapshot_id)")
        return SyncResult(status="unchanged", tracks_added=0, tracks_removed=0)
    
    # 4. snapshot_id geändert → Full re-fetch der Tracks
    logger.info(f"Playlist {playlist_id} changed, re-fetching tracks...")
    
    # 5. Metadaten updaten
    await playlist_repo.update(stored.id, {
        "name": current["name"],
        "description": current.get("description"),
        "snapshot_id": current["snapshot_id"],
        "tracks_total": current.get("tracks", {}).get("total", 0),
        "followers_total": current.get("followers", {}).get("total", 0),
        "images": current.get("images", []),
        "raw": current,
        "last_synced_at": utc_now(),
    })
    
    # 6. Tracks re-fetchen und upserten (oder diff berechnen)
    new_tracks = await fetch_all_playlist_tracks(playlist_id, access_token)
    
    # Option A: Einfach - alle Items löschen und neu einfügen
    await playlist_item_repo.delete_by_playlist(stored.id)
    for position, item in enumerate(new_tracks):
        await playlist_item_repo.create(...)
    
    # Option B: Diff berechnen für granularere Updates
    # (komplexer, aber effizienter bei großen Playlists)
    
    return SyncResult(status="updated", tracks_added=len(new_tracks))
```

### On-Demand Sync

```python
# UI Button "Sync Playlist" → API Endpoint
@router.post("/playlists/{playlist_id}/sync")
async def sync_playlist_endpoint(playlist_id: str):
    """Sofortige Synchronisation einer Playlist."""
    result = await sync_playlist(playlist_id, access_token)
    return {"status": result.status, "details": result}
```

### Lightweight Sync (für große Playlists)

```python
async def lightweight_sync(playlist_id: str, access_token: str) -> bool:
    """Quick check ohne vollständigen Track-Fetch."""
    stored = await playlist_repo.find_by_spotify_id(playlist_id)
    current = await spotify_client.get_playlist(playlist_id, access_token)
    
    changed = current["snapshot_id"] != stored.snapshot_id
    
    if changed:
        # Nur Metadaten updaten, Tracks später
        await playlist_repo.update(stored.id, {
            "snapshot_id": current["snapshot_id"],
            "tracks_total": current["tracks"]["total"],
            "needs_full_sync": True,  # Flag für späteren Full Sync
        })
    
    return changed
```

---

## Beispiel JSON (Spotify Playlist Response)

### Playlist-Objekt

```json
{
  "id": "37i9dQZF1DXcBWIGoYBM5M",
  "name": "Today's Top Hits",
  "description": "The biggest songs in the world right now. Cover: Taylor Swift",
  "owner": {
    "id": "spotify",
    "display_name": "Spotify"
  },
  "public": true,
  "collaborative": false,
  "followers": {
    "total": 34520000
  },
  "images": [
    {
      "url": "https://i.scdn.co/image/ab67706f00000003...",
      "height": 640,
      "width": 640
    },
    {
      "url": "https://i.scdn.co/image/ab67706f00001002...",
      "height": 300,
      "width": 300
    }
  ],
  "tracks": {
    "href": "https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
    "total": 50
  },
  "snapshot_id": "MTYwMDU2NjA0MCwwMDAwMDAwMDFiZjEyMzQ1Njc4OTBhYmNkZWY=",
  "external_urls": {
    "spotify": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
  },
  "href": "https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M",
  "uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
}
```

### Playlist Track Item (einzelnes Element aus /playlists/{id}/tracks items)

```json
{
  "added_at": "2024-12-21T15:30:00Z",
  "added_by": {
    "id": "user123",
    "type": "user",
    "display_name": "Max Mustermann",
    "external_urls": {
      "spotify": "https://open.spotify.com/user/user123"
    }
  },
  "is_local": false,
  "track": {
    "id": "3n3Ppam7vgaVa1iaRUc9Lp",
    "name": "Mr. Brightside",
    "duration_ms": 222000,
    "explicit": false,
    "track_number": 1,
    "disc_number": 1,
    "artists": [
      {
        "id": "0gxyHStUsqpMadRV0Di1Qt",
        "name": "The Killers"
      }
    ],
    "album": {
      "id": "6TJmQnO44YE5BtTxH8pop1",
      "name": "Hot Fuss",
      "release_date": "2004-06-07",
      "images": [
        {
          "url": "https://i.scdn.co/image/ab67616d0000b273...",
          "height": 640,
          "width": 640
        }
      ]
    },
    "external_ids": {
      "isrc": "USHW30400001"
    },
    "external_urls": {
      "spotify": "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp"
    },
    "preview_url": "https://p.scdn.co/mp3-preview/...",
    "popularity": 78
  }
}
```

### Lokaler Track (is_local: true)

```json
{
  "added_at": "2024-01-15T10:00:00Z",
  "added_by": {
    "id": "user123",
    "display_name": "Max Mustermann"
  },
  "is_local": true,
  "track": {
    "id": null,
    "name": "My Local Recording",
    "duration_ms": 180000,
    "artists": [
      {
        "name": "Local Artist"
      }
    ],
    "album": {
      "name": "Local Album"
    },
    "uri": "spotify:local:Local+Artist:Local+Album:My+Local+Recording:180"
  }
}
```

### Nicht verfügbarer Track (track: null)

```json
{
  "added_at": "2023-06-01T12:00:00Z",
  "added_by": {
    "id": "user456",
    "display_name": "Jane Doe"
  },
  "is_local": false,
  "track": null
}
```

---

## Verwendung in SoulSpot

### Playlist-Seiten

- Zeige Playlist-Details: Name, Description, Owner, Cover Image
- Liste Tracks mit Position, Added At, Added By
- Zeige Followers-Count für Popularität
- Link zu Spotify Web Player

### Download-Queue Generation

```python
async def generate_download_queue(playlist_id: str) -> list[DownloadCandidate]:
    """Erzeuge Download-Kandidaten aus Playlist-Tracks."""
    items = await playlist_item_repo.find_by_playlist(playlist_id)
    candidates = []
    
    for item in items:
        # Skip lokale Tracks
        if item.is_local:
            logger.info(f"Skipping local track at position {item.position}")
            continue
        
        # Skip nicht verfügbare Tracks
        if item.track_spotify_id is None:
            logger.warning(f"Skipping unavailable track at position {item.position}")
            continue
        
        # Nutze ISRC für Matching
        track_raw = item.track_raw or {}
        isrc = track_raw.get("external_ids", {}).get("isrc")
        
        candidates.append(DownloadCandidate(
            track_spotify_id=item.track_spotify_id,
            isrc=isrc,
            name=track_raw.get("name"),
            artist=track_raw.get("artists", [{}])[0].get("name"),
            position=item.position,
        ))
    
    return candidates
```

### Playlist-Vergleich und Ähnlichkeit

```python
def compare_playlists(playlist_a: list[str], playlist_b: list[str]) -> float:
    """Berechne Ähnlichkeit basierend auf gemeinsamen Tracks."""
    set_a = set(playlist_a)  # track_spotify_ids
    set_b = set(playlist_b)
    
    intersection = set_a & set_b
    union = set_a | set_b
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)  # Jaccard Similarity
```

### Popularitäts-Tracking

```python
async def track_popularity_trend(playlist_id: str) -> None:
    """Speichere Followers-Trend für Analyse."""
    playlist = await playlist_repo.find_by_spotify_id(playlist_id)
    
    await popularity_history_repo.create({
        "playlist_id": playlist.id,
        "followers_total": playlist.followers_total,
        "tracks_total": playlist.tracks_total,
        "recorded_at": utc_now(),
    })
```

---

## Praktische Empfehlungen

### 1. Speichere raw_json und track_raw

```python
# IMMER das komplette Response speichern!
playlist_model.raw = spotify_response

# Ermöglicht spätere Feature-Erweiterung ohne Re-Fetch
# Beispiel: Später "primary_color" auswerten ohne API-Call
```

### 2. Nutze snapshot_id für cheap change detection

```python
# Effizient: Nur Metadaten holen, nicht alle Tracks
async def has_playlist_changed(playlist_id: str) -> bool:
    current = await spotify_client.get_playlist(playlist_id)
    stored = await playlist_repo.find_by_spotify_id(playlist_id)
    return current["snapshot_id"] != stored.snapshot_id
```

### 3. Preserve ordering strictly (position)

```python
# Position immer explizit speichern
# Nicht implizit aus Array-Index ableiten bei DB-Queries!
items = await session.execute(
    select(PlaylistItem)
    .where(PlaylistItem.playlist_id == playlist_id)
    .order_by(PlaylistItem.position)  # Explizit sortieren!
)
```

### 4. Markiere is_local items und null track objects

```python
# UI und Download-Jobs können diese behandeln/überspringen
if item.is_local:
    show_warning("Lokaler Track - kann nicht heruntergeladen werden")
elif item.track_spotify_id is None:
    show_warning("Track nicht mehr verfügbar auf Spotify")
```

### 5. Concurrency bei Updates

```python
# Nutze snapshot_id + last_synced_at für Conflict Detection
async def safe_update(playlist_id: str, new_data: dict) -> None:
    stored = await playlist_repo.find_by_spotify_id(playlist_id)
    
    # Optimistic Locking via snapshot_id
    if stored.snapshot_id != new_data.get("expected_snapshot_id"):
        raise ConcurrentModificationError(
            "Playlist wurde zwischenzeitlich geändert"
        )
    
    await playlist_repo.update(stored.id, new_data)
```

---

## Weiterführende Dokumentation

- [Spotify Web API Reference - Playlists](https://developer.spotify.com/documentation/web-api/reference/get-playlist)
- [Get Playlist](https://developer.spotify.com/documentation/web-api/reference/get-playlist)
- [Get Playlist Items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-tracks)
- [Get Current User's Playlists](https://developer.spotify.com/documentation/web-api/reference/get-a-list-of-current-users-playlists)
- [Add Items to Playlist](https://developer.spotify.com/documentation/web-api/reference/add-tracks-to-playlist)
- [Spotify Authorization Guide](https://developer.spotify.com/documentation/web-api/tutorials/code-flow)

---

## Implementation Checklist

Diese Checklist kann für die zukünftige Implementation verwendet werden:

- [ ] `PlaylistModel` erweitern (spotify_id, snapshot_id, owner, etc.)
- [ ] `PlaylistItemModel` erstellen (position, added_at, added_by, is_local, track_raw)
- [ ] Alembic Migration erstellen
- [ ] `Playlist` Domain Entity erweitern
- [ ] `PlaylistItem` Domain Entity erstellen
- [ ] `ISpotifyClient` Port erweitern (get_playlist_tracks, get_user_playlists pagination)
- [ ] `SpotifyClient` Implementation erweitern
- [ ] `PlaylistRepository` erweitern (find_by_spotify_id, find_by_snapshot_id)
- [ ] `PlaylistItemRepository` erstellen
- [ ] PlaylistSyncService erstellen
- [ ] Incremental Sync via snapshot_id implementieren
- [ ] Local Track Handling implementieren
- [ ] Unavailable Track Handling implementieren
- [ ] Unit Tests schreiben
- [ ] Integration Tests schreiben

---

*Diese Dokumentation dient als Referenz für die zukünftige Implementation der Spotify Playlist API Integration in SoulSpot.*
