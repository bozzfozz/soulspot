# SoulSpot Data Standards - Das definitive Referenzdokument

## Überblick

Dieses Dokument definiert die **SoulSpot-internen Standards** für alle Daten. 
Jeder Plugin-Übersetzer muss externe Daten in diese Formate konvertieren.

---

## 1. Die SoulSpot-Datentypen (DTOs)

SoulSpot verwendet **Data Transfer Objects (DTOs)** als internes Standardformat:

| DTO | Zweck | Source |
|-----|-------|--------|
| `ArtistDTO` | Künstler-Daten | Plugins |
| `AlbumDTO` | Album-Daten | Plugins |
| `TrackDTO` | Track-Daten | Plugins |
| `PlaylistDTO` | Playlist-Daten | Plugins |
| `UserProfileDTO` | User-Profil | Plugins |
| `SearchResultDTO` | Suchergebnisse | Plugins |
| `PaginatedResponse[T]` | Paginierte Listen | Plugins |

---

## 2. SoulSpot-Feldstandards

### 2.1 ID-Felder (KRITISCH!)

Jeder DTO hat für JEDEN unterstützten Service ein eigenes ID-Feld:

```python
# Artist-Beispiel
ArtistDTO(
    # SoulSpot-interne UUID (nach Mapper-Durchlauf)
    internal_id: str | None = None,     # "550e8400-e29b-41d4-a716-446655440000"
    
    # Spotify IDs
    spotify_id: str | None = None,      # "4dpARuHxo51G3z768sgnrY" (nur ID)
    spotify_uri: str | None = None,     # "spotify:artist:4dpARuHxo51G3z768sgnrY" (voller URI)
    
    # Andere Services
    deezer_id: str | None = None,       # "12345"
    tidal_id: str | None = None,        # "7654321"
    musicbrainz_id: str | None = None,  # "f27ec8db-af05-4f36-916e-3d57f91ecf5e"
)
```

**Regeln:**
| Feld | Format | Wann setzen? |
|------|--------|--------------|
| `internal_id` | UUID-String | **NUR** vom `ProviderMappingService` |
| `spotify_id` | Nur ID-Teil | Plugin setzt bei Spotify-Daten |
| `spotify_uri` | `spotify:type:id` | Plugin setzt bei Spotify-Daten |
| `deezer_id` | String | Plugin setzt bei Deezer-Daten |
| `musicbrainz_id` | UUID | Plugin setzt bei MusicBrainz-Daten |

### 2.2 Pflichtfelder je DTO

#### ArtistDTO

```python
@dataclass
class ArtistDTO:
    # PFLICHT
    name: str                  # Künstlername
    source_service: str        # "spotify", "deezer", "tidal", "musicbrainz"
    
    # OPTIONAL - mindestens eine ID sollte gesetzt sein
    internal_id: str | None    # Von ProviderMappingService
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    tidal_id: str | None       
    musicbrainz_id: str | None 
    
    # OPTIONAL Metadaten
    image_url: str | None      # Profilbild-URL
    genres: list[str]          # ["rock", "alternative"]
    tags: list[str]            # User-definierte Tags
    popularity: int | None     # 0-100 (Spotify)
    followers: int | None      # Follower-Count
    disambiguation: str | None # MusicBrainz Unterscheidung
    external_urls: dict        # {"spotify": "https://..."}
```

#### AlbumDTO

```python
@dataclass
class AlbumDTO:
    # PFLICHT
    title: str                 # Album-Titel
    artist_name: str           # Primärer Künstler
    source_service: str        # "spotify", "deezer", etc.
    
    # OPTIONAL - mindestens eine ID sollte gesetzt sein
    internal_id: str | None    
    artist_internal_id: str | None  # Artist's SoulSpot UUID
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    artist_spotify_id: str | None   # Artist's Spotify ID
    artist_deezer_id: str | None    
    
    # OPTIONAL Metadaten
    release_date: str | None   # "YYYY-MM-DD" oder "YYYY"
    release_year: int | None   # Extrahiertes Jahr
    artwork_url: str | None    # Cover-Bild URL
    total_tracks: int | None   
    
    # Album-Typ (Lidarr-Style)
    album_type: str = "album"  # "album", "single", "ep", "compilation"
    primary_type: str = "Album"
    secondary_types: list[str] # ["Compilation", "Live"]
    
    # Nested Tracks (optional)
    tracks: list[TrackDTO]     # Meist leer, separat laden
```

#### TrackDTO

```python
@dataclass
class TrackDTO:
    # PFLICHT
    title: str                 # Track-Titel
    artist_name: str           # Primärer Künstler
    source_service: str        # "spotify", "deezer", etc.
    
    # IDs
    internal_id: str | None    
    spotify_id: str | None     
    spotify_uri: str | None    
    deezer_id: str | None      
    isrc: str | None           # KRITISCH für Cross-Service-Matching!
    
    # Artist-Referenzen
    internal_artist_id: str | None
    artist_spotify_id: str | None
    
    # Album-Referenzen (optional für Singles)
    internal_album_id: str | None
    album_name: str | None
    album_spotify_id: str | None
    
    # Metadaten
    duration_ms: int = 0       # Dauer in Millisekunden
    track_number: int | None   
    disc_number: int = 1       
    explicit: bool = False     
    popularity: int | None     # 0-100
    preview_url: str | None    # 30-Sekunden Preview
    
    # Nested Objects
    additional_artists: list[ArtistDTO]  # Features
    artists: list[ArtistDTO]   # Primary + Additional
    album: AlbumDTO | None     # Optional Album-Context
```

---

## 3. Plugin-Übersetzungsregeln

### 3.1 Spotify → SoulSpot

```python
# SpotifyPlugin._convert_artist()
def _convert_artist(self, raw: dict) -> ArtistDTO:
    """
    Spotify-Feldmapping:
    
    Spotify API          →  SoulSpot DTO
    ───────────────────────────────────────
    raw["name"]          →  name
    raw["id"]            →  spotify_id
    raw["uri"]           →  spotify_uri
    raw["images"][0-1]   →  image_url (320px preferred)
    raw["genres"]        →  genres
    raw["popularity"]    →  popularity
    raw["followers"]["total"] → followers
    raw["external_urls"] →  external_urls
    """
    return ArtistDTO(
        name=raw.get("name", "Unknown"),
        source_service="spotify",
        spotify_id=raw.get("id"),
        spotify_uri=raw.get("uri"),
        image_url=self._extract_image(raw, size=320),
        genres=raw.get("genres", []),
        popularity=raw.get("popularity"),
        followers=raw.get("followers", {}).get("total"),
        external_urls=raw.get("external_urls", {}),
    )
```

### 3.2 Deezer → SoulSpot

```python
# DeezerPlugin._convert_artist()
def _convert_artist(self, raw: dict) -> ArtistDTO:
    """
    Deezer-Feldmapping:
    
    Deezer API           →  SoulSpot DTO
    ───────────────────────────────────────
    raw["name"]          →  name
    raw["id"]            →  deezer_id (als String!)
    raw["picture_medium"] → image_url
    raw["nb_fan"]        →  followers
    raw["link"]          →  external_urls["deezer"]
    """
    return ArtistDTO(
        name=raw.get("name", "Unknown"),
        source_service="deezer",
        deezer_id=str(raw.get("id", "")),  # IMMER String!
        image_url=raw.get("picture_medium"),
        followers=raw.get("nb_fan"),
        external_urls={"deezer": raw.get("link", "")},
    )
```

### 3.3 Track-Mapping - ISRC ist KEY!

```python
# Der WICHTIGSTE Track-Identifier für Cross-Service-Matching
def _convert_track(self, raw: dict) -> TrackDTO:
    return TrackDTO(
        title=raw.get("name"),
        artist_name=raw.get("artists", [{}])[0].get("name"),
        source_service="spotify",
        
        spotify_id=raw.get("id"),
        spotify_uri=raw.get("uri"),
        
        # KRITISCH: ISRC für Deduplizierung!
        isrc=raw.get("external_ids", {}).get("isrc"),
        
        duration_ms=raw.get("duration_ms", 0),
        # ...
    )
```

---

## 4. Datenfluss-Übersicht

```
┌────────────────────────────────────────────────────────────────────┐
│                        EXTERNE APIs                                 │
│                                                                    │
│  Spotify: {"name": "...", "id": "...", "uri": "spotify:artist:..."} │
│  Deezer:  {"name": "...", "id": 12345, "picture_medium": "..."}     │
│  Tidal:   {"name": "...", "id": "...", "imageUrl": "..."}          │
└────────────────────────────────────────────────────────────────────┘
                               │
                               │ raw dict/JSON
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                         PLUGINS                                     │
│                    (ÜBERSETZER Layer)                              │
│                                                                    │
│  SpotifyPlugin._convert_artist(raw) → ArtistDTO                    │
│  DeezerPlugin._convert_artist(raw)  → ArtistDTO                    │
│  TidalPlugin._convert_artist(raw)   → ArtistDTO                    │
│                                                                    │
│  ALLE geben das GLEICHE Format zurück!                             │
└────────────────────────────────────────────────────────────────────┘
                               │
                               │ Standard DTOs
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                    SOULSPOT INTERNER STANDARD                       │
│                                                                    │
│  ArtistDTO:                                                        │
│    name: "The Beatles"                                             │
│    source_service: "spotify"                                       │
│    spotify_id: "3WrFJ7ztbogyGnTHbHJFl2"                            │
│    spotify_uri: "spotify:artist:3WrFJ7ztbogyGnTHbHJFl2"            │
│    deezer_id: None  (weil aus Spotify)                             │
│    image_url: "https://i.scdn.co/image/..."                        │
│    genres: ["british invasion", "rock"]                            │
│                                                                    │
│  → Alle Services verwenden DIESES Format!                          │
└────────────────────────────────────────────────────────────────────┘
                               │
                               │ Standard DTOs
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                   PROVIDER MAPPING SERVICE                          │
│                    (ID-Resolution Layer)                           │
│                                                                    │
│  map_artist_dto(dto) → dto mit internal_id                         │
│                                                                    │
│  Schaut in DB:                                                     │
│    1. spotify_uri vorhanden? → internal_id                         │
│    2. deezer_id vorhanden? → internal_id                           │
│    3. Name-Match? → internal_id                                    │
│                                                                    │
│  Output: Gleiches DTO aber mit internal_id wenn gefunden           │
└────────────────────────────────────────────────────────────────────┘
                               │
                               │ DTOs mit internal_id
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                   APPLICATION SERVICES                              │
│                    (Business Logic)                                 │
│                                                                    │
│  FollowedArtistsService.sync()                                     │
│  ChartsService.get_charts()                                        │
│  DiscoverService.get_related()                                     │
│                                                                    │
│  → Arbeiten NUR mit Standard DTOs                                  │
│  → Keine Service-spezifische Logik                                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Konvertierungs-Checkliste für neue Plugins

Wenn du einen neuen Service hinzufügst (z.B. Apple Music), stelle sicher:

### 5.1 Artist-Konvertierung
- [ ] `name` → Pflichtfeld
- [ ] `source_service` → "apple_music"
- [ ] `apple_music_id` → ID vom Service (als String!)
- [ ] `image_url` → Bild-URL extrahiert
- [ ] `genres` → Liste von Genres (falls verfügbar)
- [ ] `external_urls` → Link zum Profil

### 5.2 Track-Konvertierung
- [ ] `title` → Pflichtfeld
- [ ] `artist_name` → Primärer Künstler
- [ ] `source_service` → "apple_music"
- [ ] `apple_music_id` → Track-ID
- [ ] **`isrc`** → KRITISCH für Cross-Service-Matching!
- [ ] `duration_ms` → Dauer in Millisekunden
- [ ] `explicit` → Explicit-Flag
- [ ] `preview_url` → Preview-Link (falls verfügbar)

### 5.3 Album-Konvertierung
- [ ] `title` → Pflichtfeld
- [ ] `artist_name` → Pflichtfeld
- [ ] `source_service` → "apple_music"
- [ ] `album_type` → "album", "single", "ep", "compilation"
- [ ] `release_date` → ISO-Format "YYYY-MM-DD"
- [ ] `artwork_url` → Cover-Bild

---

## 6. Wichtige Konventionen

### 6.1 String-IDs überall!

```python
# ❌ FALSCH - Integer ID
deezer_id=raw["id"]  # Deezer gibt Integer!

# ✅ RICHTIG - String ID
deezer_id=str(raw.get("id", ""))
```

### 6.2 source_service ist Pflicht!

```python
# ❌ FALSCH - Woher kommen die Daten?
ArtistDTO(name="Beatles")

# ✅ RICHTIG - Quelle ist klar
ArtistDTO(name="Beatles", source_service="spotify")
```

### 6.3 Defensive Coding

```python
# ❌ FALSCH - Crash bei fehlenden Daten
image_url=raw["images"][0]["url"]

# ✅ RICHTIG - Defensive Extraktion
images = raw.get("images", [])
image_url = images[0].get("url") if images else None
```

### 6.4 Konsistente Bild-Größen

```python
# Standard: 320px für Thumbnails, 640px für große Ansichten
def _extract_image(self, raw: dict, size: int = 320) -> str | None:
    images = raw.get("images", [])
    if not images:
        return None
    
    # Finde Bild mit passender Größe
    for img in images:
        if img.get("width", 0) == size:
            return img.get("url")
    
    # Fallback: erstes Bild
    return images[0].get("url")
```

---

## 7. Quick Reference: Feld-Mapping

### Spotify → SoulSpot

| Spotify | SoulSpot DTO |
|---------|--------------|
| `id` | `spotify_id` |
| `uri` | `spotify_uri` |
| `name` | `name` / `title` |
| `images[].url` | `image_url` / `artwork_url` |
| `genres` | `genres` |
| `popularity` | `popularity` |
| `followers.total` | `followers` |
| `duration_ms` | `duration_ms` |
| `track_number` | `track_number` |
| `disc_number` | `disc_number` |
| `explicit` | `explicit` |
| `preview_url` | `preview_url` |
| `external_ids.isrc` | `isrc` |
| `release_date` | `release_date` |
| `album_type` | `album_type` |

### Deezer → SoulSpot

| Deezer | SoulSpot DTO |
|--------|--------------|
| `id` | `deezer_id` (als String!) |
| `name` / `title` | `name` / `title` |
| `picture_medium` | `image_url` |
| `cover_medium` | `artwork_url` |
| `nb_fan` | `followers` |
| `duration` | `duration_ms * 1000` (Deezer gibt Sekunden!) |
| `track_position` | `track_number` |
| `disk_number` | `disc_number` |
| `explicit_lyrics` | `explicit` |
| `preview` | `preview_url` |
| `isrc` | `isrc` |
| `release_date` | `release_date` |
| `record_type` | `album_type` |

---

*Stand: Nach Architektur-Review Session*
