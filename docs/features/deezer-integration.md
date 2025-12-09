# Deezer Integration

> **⚠️ PLANNED (NOT DEPRECATED):** Deezer integration is planned but not yet implemented. This is design documentation for future implementation.  
> **Status:** Design/Specification Phase  
> **Implementation:** NOT STARTED

<details>
<summary><strong>📁 Design Documentation (Click to Expand)</strong></summary>

---

> **Version:** 1.0  
> **Last Updated:** 2025-12-05  
> **Status:** PLANNED (Design Phase)

---

## Übersicht

Die Deezer-Integration ermöglicht es, lokale Bibliothek-Einträge mit Metadaten und Artwork von Deezer anzureichern. **Deezer ist der ideale Fallback** wenn Spotify kein Match findet, besonders für:

- **Various Artists / Compilations** - Album-Suche funktioniert ohne Artist
- **Obscure Releases** - Deezer hat teilweise anderen Katalog als Spotify
- **Artwork-Enrichment** - Hochauflösende Cover (1000x1000px)

### Warum Deezer?

| Feature | Deezer | Spotify | Tidal |
|---------|--------|---------|-------|
| **Auth benötigt für Metadaten** | ❌ Nein! | ✅ Ja | ✅ Ja |
| **Artwork-Größe** | 1000x1000 | 640x640 | 1280x1280 |
| **ISRC verfügbar** | ✅ Ja | ✅ Ja | ✅ Ja |
| **Rate Limit** | 50/5s | 180/min | Variabel |
| **ToS für Enrichment** | ✅ Erlaubt | ⚠️ Eingeschränkt | ⚠️ Eingeschränkt |

---

## API-Client

### Installation

Keine zusätzliche Installation nötig! Der `DeezerClient` nutzt `httpx` (bereits im Projekt).

### Basis-Usage

```python
from soulspot.infrastructure.integrations import DeezerClient

# Client erstellen (keine Auth!)
client = DeezerClient()

# Album suchen
albums = await client.search_albums("Bravo Hits 100")
for album in albums:
    print(f"{album.title} - {album.artist_name}")
    print(f"Artwork: {album.cover_xl}")  # 1000x1000!

# Artist suchen
artists = await client.search_artists("Armin van Buuren")
artist = artists[0]
print(f"Bild: {artist.picture_xl}")

# Track mit ISRC holen (für exaktes Matching!)
track = await client.get_track_by_isrc("USQY51613007")
if track:
    print(f"{track.title} by {track.artist_name}")

# Nicht vergessen: Client schließen
await client.close()
```

### Convenience-Methoden für Enrichment

```python
# Artwork für Album finden (perfekt für Various Artists!)
artwork_url = await client.find_album_artwork(
    album_title="Bravo Hits 100",
    artist_name=None  # Bei Various Artists leer lassen
)

# Artist-Bild finden
image_url = await client.find_artist_image("Paul Elstak")
```

---

## Datenmodelle

### DeezerAlbum

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | `int` | Deezer Album ID |
| `title` | `str` | Album-Titel |
| `artist_name` | `str` | Artist-Name |
| `artist_id` | `int` | Deezer Artist ID |
| `cover_xl` | `str` | 1000x1000 Artwork URL |
| `cover_big` | `str` | 500x500 Artwork URL |
| `cover_medium` | `str` | 250x250 Artwork URL |
| `release_date` | `str` | Release-Datum (YYYY-MM-DD) |
| `nb_tracks` | `int` | Anzahl Tracks |
| `record_type` | `str` | album, ep, single, compile |
| `upc` | `str` | Universal Product Code |

### DeezerArtist

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | `int` | Deezer Artist ID |
| `name` | `str` | Artist-Name |
| `picture_xl` | `str` | 1000x1000 Bild URL |
| `nb_album` | `int` | Anzahl Alben |
| `nb_fan` | `int` | Anzahl Fans |

### DeezerTrack

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | `int` | Deezer Track ID |
| `title` | `str` | Track-Titel |
| `artist_name` | `str` | Artist-Name |
| `album_title` | `str` | Album-Titel |
| `isrc` | `str` | ISRC Code (für Matching!) |
| `duration` | `int` | Länge in Sekunden |
| `preview` | `str` | 30s Preview URL |

---

## Rate Limiting

Deezer erlaubt **50 Requests pro 5 Sekunden** pro IP-Adresse.

Der Client hat integriertes Rate Limiting:
- 100ms Pause zwischen Requests
- Lock für concurrent Requests

---

## Integration mit Library Enrichment

### Fallback-Kette

Das Enrichment-System nutzt Deezer als Fallback:

```
1. Spotify (wenn verbunden und Match gefunden)
   ↓ kein Match
2. Deezer (immer verfügbar, kein Auth)
   ↓ kein Match  
3. MusicBrainz/CoverArtArchive
   ↓ kein Match
4. Lokale cover.jpg
```

### Beispiel für Various Artists Enrichment

```python
# In local_library_enrichment_service.py

async def _enrich_compilation_album(self, album: Album) -> str | None:
    """Enrich Various Artists compilation with Deezer artwork."""
    
    # Spotify funktioniert oft nicht für Various Artists
    # → Direkt zu Deezer
    artwork_url = await self._deezer_client.find_album_artwork(
        album_title=album.title,
        artist_name=None  # Ignorieren bei Compilations
    )
    
    return artwork_url
```

---

## Konfiguration

Keine Konfiguration nötig! Deezer's Public API ist kostenlos und erfordert keine Credentials.

Optional kann in `.env` gesetzt werden:

```env
# Rate Limit Delay (optional, default 0.1s)
DEEZER_RATE_LIMIT_MS=100
```

---

## Bekannte Einschränkungen

1. **Kein Full-Length Streaming** - Nur 30s Previews
2. **Keine User-Playlists** - Erfordert OAuth (nicht implementiert)
3. **Katalog-Unterschiede** - Nicht alle Spotify-Alben sind auf Deezer
4. **Keine deutsche Lokalisierung** - Suchergebnisse sind international

---

## Vergleich der Artwork-Quellen

| Quelle | Größe | Qualität | Verfügbarkeit |
|--------|-------|----------|---------------|
| **Deezer** | 1000x1000 | Sehr gut | Immer (kein Auth) |
| **Spotify** | 640x640 | Gut | Nur mit Auth |
| **CoverArtArchive** | Variabel | Gut | Langsam (Rate Limit) |
| **Lokale Datei** | Variabel | Variabel | Wenn vorhanden |


---

## API-Referenz

### Suche
- `search_albums(query, limit=25)` - Sucht Alben auf Deezer
- `search_artists(query, limit=25)` - Sucht Artists auf Deezer
- `search_tracks(query, limit=25)` - Sucht Tracks auf Deezer

### Einzelabfragen
- `get_album(album_id)` - Holt Album-Details inkl. UPC
- `get_artist(artist_id)` - Holt Artist-Details
- `get_track(track_id)` - Holt Track-Details inkl. ISRC
- `get_album_tracks(album_id)` - Holt alle Tracks eines Albums

### ISRC/UPC Matching (neu!)
- `get_track_by_isrc(isrc)` - Holt Track direkt per ISRC (100% Matching!)
- `get_album_by_upc(upc)` - Holt Album direkt per UPC/Barcode
- `search_by_barcode(barcode)` - Vollständiges Album inkl. Tracklist per Barcode

### Convenience-Methoden
- `find_album_artwork(album_title, artist_name=None)` - Findet beste Artwork-URL
- `find_artist_image(artist_name)` - Findet beste Artist-Bild-URL

### Tracklist-Vergleich (neu!)
- `compare_tracklists(deezer_album_id, local_tracks)` - Vergleicht lokale mit Deezer-Tracklist
  - Findet fehlende/extra Tracks
  - Match-Rate Berechnung
  - Nützlich für Qualitätskontrolle

### Preview URLs (neu!)
- `get_track_preview_url(track_id)` - 30s Preview URL für einen Track
- `get_album_preview_urls(album_id)` - Preview URLs für alle Album-Tracks

---

## Neue Features (Dezember 2025)

### ISRC-basiertes Track-Matching
```python
# Direktes Matching über ISRC = 100% Trefferquote!
track = await client.get_track_by_isrc("USRC11900012")
if track:
    print(f"Exaktes Match: {track.title} by {track.artist_name}")
```

### UPC/Barcode-Suche
```python
# Barcode scannen und Album finden
result = await client.search_by_barcode("0602498654322")
if result["success"]:
    album = result["album"]
    print(f"Album: {album['title']} ({album['total_tracks']} Tracks)")
    print(f"Artwork XL: {result['artwork']['xl']}")
```

### Deezer-Only Modus (ohne Spotify)
```python
# Für Nutzer ohne Spotify-Account
service = LocalLibraryEnrichmentService(...)
stats = await service.enrich_batch_deezer_only()
# Nutzt nur Deezer API - kein Spotify OAuth nötig!
```

</details>

