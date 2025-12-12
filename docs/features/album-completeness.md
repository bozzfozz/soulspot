# Album Completeness Detection

> **Version:** 1.0  
> **Status:** ✅ Active  
> **Last Updated:** 2025-12-12  
> **Service:** `src/soulspot/application/services/album_completeness.py`

---

## Overview

Das Album Completeness Feature erkennt unvollständige Alben in deiner Bibliothek, indem es die Anzahl der lokal vorhandenen Tracks mit der offiziellen Tracklist aus externen Metadatenquellen (Spotify, MusicBrainz) vergleicht.

**Beispiel:**
- Du hast "OK Computer" von Radiohead mit 10 Tracks importiert
- Die offizielle Tracklist hat 12 Tracks
- → Album ist **83.3% vollständig**, Tracks 3 und 7 fehlen

---

## Key Features

- **Multi-Source Verification**: Nutzt sowohl Spotify als auch MusicBrainz für maximale Abdeckung
- **Gap Analysis**: Zeigt exakt welche Track-Nummern fehlen (nicht nur Anzahl)
- **Deluxe Edition Detection**: Behandelt Alben mit mehr Tracks als erwartet als "vollständig"
- **Percentage Calculation**: Klare Prozentangabe für UX (z.B. "75% vollständig")
- **Graceful Degradation**: Funktioniert auch wenn nur eine Metadatenquelle verfügbar ist

---

## Use Cases

### 1. Unvollständige Downloads finden
Nach einem Batch-Import prüfen, welche Alben noch Tracks fehlen:

```python
from soulspot.application.services.album_completeness import AlbumCompletenessService

service = AlbumCompletenessService(
    spotify_client=spotify,
    musicbrainz_client=musicbrainz
)

# Album prüfen
result = await service.check_album_completeness(
    album_id="local_album_id_123",
    local_tracks=[1, 2, 3, 5, 6, 7, 9, 10]  # Track 4 und 8 fehlen
)

print(f"Vollständigkeit: {result.completeness_percent}%")
print(f"Fehlende Tracks: {result.missing_track_numbers}")
# Output: Vollständigkeit: 80.0%
#         Fehlende Tracks: [4, 8]
```

### 2. Standard vs Deluxe Edition Handling
Wenn du die Deluxe Edition (15 Tracks) hast, aber Spotify nur die Standard Edition (12 Tracks) kennt:

```python
result = await service.check_album_completeness(
    album_id="deluxe_album_id",
    local_tracks=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # 15 Tracks
)

print(result.is_complete())  # True - mehr Tracks als erwartet ist OK
print(result.expected_track_count)  # 12 (aus Spotify)
print(result.actual_track_count)  # 15 (deine lokale Sammlung)
```

### 3. Batch-Analyse für Bibliothek
Alle unvollständigen Alben in der Bibliothek finden:

```python
incomplete_albums = []
for album in my_album_collection:
    result = await service.check_album_completeness(
        album_id=album.id,
        local_tracks=album.track_numbers
    )
    if not result.is_complete():
        incomplete_albums.append(result)

# Sortiere nach Vollständigkeit (niedrigste zuerst)
incomplete_albums.sort(key=lambda x: x.completeness_percent)
for album in incomplete_albums:
    print(f"{album.album_title}: {album.completeness_percent}% - {album.missing_track_count} Tracks fehlen")
```

---

## API Integration

### Data Model: AlbumCompletenessInfo

```python
class AlbumCompletenessInfo:
    album_id: str                    # Lokale Album-ID
    album_title: str                 # Album-Titel
    artist_name: str                 # Künstlername
    expected_track_count: int        # Anzahl Tracks laut Metadatenquelle
    actual_track_count: int          # Anzahl lokal vorhandener Tracks
    missing_track_numbers: list[int] # Liste der fehlenden Track-Nummern
    source: str                      # Metadatenquelle ("spotify" oder "musicbrainz")
    completeness_percent: float      # Vollständigkeit in % (berechnet)

    def is_complete() -> bool:       # True wenn actual >= expected
    def to_dict() -> dict[str, Any]: # Serialisierung für JSON API
```

**JSON Response Beispiel:**
```json
{
  "album_id": "abc123",
  "album_title": "OK Computer",
  "artist_name": "Radiohead",
  "expected_track_count": 12,
  "actual_track_count": 10,
  "missing_track_count": 2,
  "missing_track_numbers": [3, 7],
  "completeness_percent": 83.33,
  "is_complete": false,
  "source": "spotify"
}
```

---

## Multi-Source Strategy

### 1. Spotify (Primary)
**Vorteile:**
- Aktuelle und mainstream Alben (ab ~1990)
- Schnelle API-Response
- Zuverlässige Track-Nummerierung

**Nachteile:**
- Regionale Verfügbarkeit variiert
- Alte/Obscure Alben fehlen oft
- Benötigt OAuth-Token

**Verwendung:**
```python
service = AlbumCompletenessService(spotify_client=spotify)
result = await service.check_album_completeness(album_id, local_tracks)
if result.source == "spotify":
    print("Daten aus Spotify API")
```

### 2. MusicBrainz (Fallback)
**Vorteile:**
- Umfangreiche Datenbank (alte/obscure Alben)
- Keine Authentifizierung nötig
- Community-gepflegte Daten

**Nachteile:**
- Rate-Limiting (1 Request/Sekunde)
- Manchmal veraltete/fehlerhafte Daten
- Langsamer als Spotify

**Verwendung:**
```python
service = AlbumCompletenessService(musicbrainz_client=musicbrainz)
result = await service.check_album_completeness(album_id, local_tracks)
if result.source == "musicbrainz":
    print("Daten aus MusicBrainz")
```

### 3. Combined Mode (Empfohlen)
Nutzt beide Quellen für maximale Coverage:

```python
service = AlbumCompletenessService(
    spotify_client=spotify,
    musicbrainz_client=musicbrainz
)
# Versucht zuerst Spotify, dann MusicBrainz Fallback
result = await service.check_album_completeness(album_id, local_tracks)
```

---

## Configuration

### Environment Variables
```bash
# Spotify API (optional, aber empfohlen)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret

# MusicBrainz (optional, keine Auth nötig)
MUSICBRAINZ_RATE_LIMIT=1.0  # Sekunden zwischen Requests
```

### Service Initialization
```python
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

# Mit beiden Quellen (empfohlen)
spotify = SpotifyClient(client_id=..., client_secret=...)
musicbrainz = MusicBrainzClient()
service = AlbumCompletenessService(spotify, musicbrainz)

# Nur Spotify
service = AlbumCompletenessService(spotify_client=spotify)

# Nur MusicBrainz (wenn kein Spotify-Token verfügbar)
service = AlbumCompletenessService(musicbrainz_client=musicbrainz)
```

---

## Edge Cases & Gotchas

### 1. Deluxe Edition Detection
**Problem:** Du hast 15 Tracks, Spotify sagt 12 Tracks  
**Lösung:** `is_complete()` gibt `True` zurück wenn `actual >= expected`

**Warum?** Bonus Tracks bedeuten "Album + Extras", nicht "unvollständig".

### 2. Track Number Gaps
**Problem:** Album hat Tracks [1, 2, 4, 5, 6] - Track 3 wurde gelöscht  
**Lösung:** `missing_track_numbers` zeigt `[3]`, auch wenn lokal nur 5 Tracks

### 3. Multi-Disc Albums
**Problem:** 2-Disc Album mit 30 Tracks, aber Track-Nummern 1-15 und 1-15  
**Status:** 🚧 **Known Issue** - Derzeit keine Disc-Normalisierung

**Workaround:** Nutze MusicBrainz mit MBID für Multi-Disc Detection

### 4. Different Editions
**Problem:** Du hast US Edition (10 Tracks), Spotify kennt UK Edition (12 Tracks)  
**Status:** Service kann nicht unterscheiden zwischen "unvollständig" und "andere Edition"

**Hinweis:** `source` field zeigt, welche Metadatenquelle verwendet wurde

---

## Performance Considerations

### API Rate Limits
- **Spotify:** ~180 requests/minute (OAuth Token)
- **MusicBrainz:** 1 request/second (enforced by library)

### Batch Processing
Für große Bibliotheken (>100 Alben) empfohlen:

```python
import asyncio

# Batch-Check mit Rate-Limiting
async def check_all_albums(album_ids):
    results = []
    for album_id in album_ids:
        result = await service.check_album_completeness(album_id, local_tracks)
        results.append(result)
        await asyncio.sleep(0.1)  # Gentle rate-limiting
    return results
```

### Caching Strategy
Metadaten-Results cachen um wiederholte API-Calls zu vermeiden:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_track_count(album_id: str) -> int:
    # Cache für 1 Stunde
    return service.get_official_track_count(album_id)
```

---

## Integration Examples

### With Library Scanner
```python
from soulspot.application.services.library_scanner import LibraryScanner

# Nach Library-Scan unvollständige Alben finden
scanner = LibraryScanner(...)
scan_result = await scanner.scan_directory("/music")

completeness_service = AlbumCompletenessService(spotify, musicbrainz)
for album in scan_result.albums:
    result = await completeness_service.check_album_completeness(
        album_id=album.id,
        local_tracks=album.track_numbers
    )
    if not result.is_complete():
        print(f"⚠️ {album.title}: {result.missing_track_count} Tracks fehlen")
```

### With Download Management
```python
# Fehlende Tracks automatisch in Download-Queue einreihen
if not result.is_complete():
    for track_number in result.missing_track_numbers:
        track = await get_track_metadata(album_id, track_number)
        await download_queue.add(track)
```

---

## Related Features

- **[Library Management](./library-management.md)** - Library-Scan und Import
- **[Download Management](./download-management.md)** - Fehlende Tracks automatisch herunterladen
- **[Metadata Enrichment](./metadata-enrichment.md)** - Metadaten-Quellen und Synchronisierung

---

## Troubleshooting

### "No metadata source available"
**Problem:** Weder Spotify noch MusicBrainz Client verfügbar  
**Lösung:** Mindestens einen Client im Service-Constructor übergeben

### "Expected track count is 0"
**Problem:** Metadatenquelle hat kein Album mit dieser ID gefunden  
**Lösung:** Prüfe ob `album_id` korrekt ist, versuche andere Quelle

### "Completeness shows >100%"
**Ursache:** Deluxe Edition mit Bonus Tracks  
**Status:** Expected behavior - `is_complete()` gibt `True` zurück

### Spotify API Rate Limit
**Problem:** "429 Too Many Requests"  
**Lösung:** Batch-Processing mit Delays (siehe Performance Section)

### MusicBrainz 503 Error
**Problem:** Rate-Limit überschritten (>1 req/sec)  
**Lösung:** Client nutzt automatisch Rate-Limiter, Problem sollte selten auftreten

---

**Version:** 1.0 · **Status:** Active · **Service:** `album_completeness.py`
