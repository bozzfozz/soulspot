# Spotify Artist API Roadmap

> **⚠️ DEPRECATED:** This roadmap is outdated. Artist API is fully implemented. See **docs/api/spotify-artist-api.md** for complete API reference (9 endpoints).

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

> **Version:** 1.0  
> **Last Updated:** 2025-11-25  
> **Status:** ~~Active~~ ROADMAP FORMAT OUTDATED

---

## Übersicht

Diese Dokumentation beschreibt, welche **Spotify Web API Artist-Endpunkte** wir bereits nutzen, welche Features wir daraus gebaut haben, und welche zusätzlichen Möglichkeiten noch existieren.

---

## 🟢 Genutzte Spotify Artist API Endpunkte

### 1. Get User's Followed Artists
**Spotify Endpoint:** `GET /me/following?type=artist`

| Status | ✅ Implementiert |
|--------|-----------------|
| **SoulSpot Methode** | `SpotifyClient.get_followed_artists()` |
| **Datei** | `src/soulspot/infrastructure/integrations/spotify_client.py` |
| **OAuth Scope** | `user-follow-read` |

**Was wir daraus gebaut haben:**

| Feature | Beschreibung |
|---------|--------------|
| Followed Artists Sync | Alle gefolgten Künstler von Spotify importieren |
| Bulk-Watchlist-Erstellung | Watchlists für viele Artists auf einmal erstellen |
| Artist-Datenbank | Speicherung von Name, Genres, Bildern in lokaler DB |

**API Response-Felder die wir nutzen:**
- `artists.items[].id` - Spotify Artist ID
- `artists.items[].name` - Artist Name
- `artists.items[].genres` - Genre-Liste
- `artists.items[].images` - Profilbilder
- `artists.items[].uri` - Spotify URI
- `artists.cursors.after` - Pagination-Cursor

---

### 2. Get Artist's Albums
**Spotify Endpoint:** `GET /artists/{id}/albums`

| Status | ✅ Implementiert |
|--------|-----------------|
| **SoulSpot Methode** | `SpotifyClient.get_artist_albums()` |
| **Datei** | `src/soulspot/infrastructure/integrations/spotify_client.py` |
| **OAuth Scope** | Kein spezieller Scope nötig |

**Was wir daraus gebaut haben:**

| Feature | Beschreibung |
|---------|--------------|
| Discographie-Check | Vergleich unserer Bibliothek mit Spotify-Discographie |
| Neue Releases erkennen | Watchlists prüfen auf neue Alben/Singles |
| Missing Albums | Fehlende Alben identifizieren |

**API Response-Felder die wir nutzen:**
- `items[].id` - Album ID
- `items[].name` - Album Name
- `items[].album_type` - album, single, compilation
- `items[].release_date` - Erscheinungsdatum
- `items[].images` - Coverbilder

**Parameter die wir setzen:**
- `include_groups=album,single` (ohne appears_on, compilation)
- `limit=50` (max pro Request)

---

## 🟠 Nicht genutzte Spotify Artist API Endpunkte

### 1. Get Artist
**Spotify Endpoint:** `GET /artists/{id}`

| Status | ❌ Nicht implementiert |
|--------|------------------------|
| **Nutzen** | Detaillierte Artist-Infos abrufen |
| **Schwierigkeit** | ⭐ Einfach |

**Verfügbare Daten:**
- `followers.total` - Anzahl Follower
- `popularity` - Popularitäts-Score (0-100)
- `genres` - Genre-Liste (aktueller als bei followed artists)
- `images` - Profilbilder in verschiedenen Auflösungen
- `external_urls` - Links zu Spotify

**Mögliche Features:**
| Feature | Beschreibung |
|---------|--------------|
| Artist Popularity Score | Popularität anzeigen für Sortierung/Filter |
| Follower Count | "10M Followers" Badge im UI |
| Aktuelle Genre-Tags | Genres vom aktuellen Artist-Profil |

---

### 2. Get Several Artists
**Spotify Endpoint:** `GET /artists?ids={ids}`

| Status | ❌ Nicht implementiert |
|--------|------------------------|
| **Nutzen** | Mehrere Artists auf einmal abrufen |
| **Schwierigkeit** | ⭐ Einfach |

**Mögliche Features:**
| Feature | Beschreibung |
|---------|--------------|
| Batch-Updates | Viele Artists auf einmal aktualisieren (max 50 IDs) |
| Performance | Weniger API-Calls beim Refresh |
| Bulk-Import | Schnelleres Importieren von Playlist-Artists |

---

### 3. Get Artist's Top Tracks
**Spotify Endpoint:** `GET /artists/{id}/top-tracks`

| Status | ❌ Nicht implementiert |
|--------|------------------------|
| **Nutzen** | Die beliebtesten Songs eines Artists |
| **Schwierigkeit** | ⭐ Einfach |

**Verfügbare Daten:**
- `tracks[]` - Liste der Top 10 Tracks
- `tracks[].popularity` - Track-Popularität
- `tracks[].preview_url` - 30-Sekunden Vorschau

**Mögliche Features:**
| Feature | Beschreibung |
|---------|--------------|
| "Top Tracks" Ansicht | Die besten Songs eines Artists anzeigen |
| Smart Download | Automatisch die Top Tracks downloaden |
| Vorschau-Player | 30s Preview vor dem Download |
| Prioritized Downloads | Beliebte Songs zuerst herunterladen |

---

### 4. Get Artist's Related Artists
**Spotify Endpoint:** `GET /artists/{id}/related-artists`

| Status | ❌ Nicht implementiert |
|--------|------------------------|
| **Nutzen** | Ähnliche Künstler finden |
| **Schwierigkeit** | ⭐⭐ Mittel |

**Verfügbare Daten:**
- `artists[]` - Liste von 20 ähnlichen Artists
- Vollständige Artist-Objekte (Name, Genres, Bilder, etc.)

**Mögliche Features:**
| Feature | Beschreibung |
|---------|--------------|
| "Similar Artists" | "Wenn dir X gefällt, probier auch Y" |
| Artist Discovery | Neue Musik entdecken basierend auf Favoriten |
| Auto-Watchlist | Ähnliche Artists automatisch zur Watchlist hinzufügen |
| Genre-Exploration | Durch verwandte Artists neue Genres erkunden |

---

### 5. Search for Artists
**Spotify Endpoint:** `GET /search?type=artist`

| Status | ⚠️ Indirekt (nur Tracks) |
|--------|--------------------------|
| **Nutzen** | Artists auf Spotify suchen |
| **Schwierigkeit** | ⭐ Einfach |

**Aktuell:** Wir haben `search_track()` implementiert, aber nicht `search_artist()`.

**Mögliche Features:**
| Feature | Beschreibung |
|---------|--------------|
| Artist-Suche | Direkt nach Artists suchen |
| Add to Watchlist | Gefundene Artists zur Watchlist hinzufügen |
| Quick-Import | Artist finden und sofort Discographie downloaden |

---

## 🔵 Feature-Ideen basierend auf Spotify API

### Kurzfristig (Einfach zu implementieren)

| Feature | Spotify Endpoint | Aufwand |
|---------|------------------|---------|
| Artist-Details anzeigen | `GET /artists/{id}` | ⭐ 2h |
| Top Tracks laden | `GET /artists/{id}/top-tracks` | ⭐ 2h |
| Artist-Suche | `GET /search?type=artist` | ⭐ 2h |
| Batch Artist-Update | `GET /artists?ids={ids}` | ⭐ 3h |

### Mittelfristig (Neue Features)

| Feature | Spotify Endpoint | Aufwand |
|---------|------------------|---------|
| Related Artists | `GET /artists/{id}/related-artists` | ⭐⭐ 4h |
| Artist Discovery Page | Mehrere Endpoints | ⭐⭐ 1 Tag |
| Popularity-basierte Sortierung | `GET /artists/{id}` | ⭐⭐ 4h |
| Smart Download (Top Tracks first) | `GET /artists/{id}/top-tracks` | ⭐⭐ 6h |

### Langfristig (Komplexe Features)

| Feature | Spotify Endpoint | Aufwand |
|---------|------------------|---------|
| Genre-Netzwerk | Related Artists + Genres | ⭐⭐⭐ 2-3 Tage |
| Auto-Discovery | Related + Top Tracks | ⭐⭐⭐ 2-3 Tage |
| Trend-Analyse | Popularity über Zeit | ⭐⭐⭐ 3-5 Tage |

---

## Implementierungs-Priorität

### Prio 1: Artist Details (`GET /artists/{id}`)

**Vorgeschlagene Methoden-Signatur:**
```python
# Hinzufügen in SpotifyClient (spotify_client.py)
async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
    """Get detailed artist information including popularity and followers.
    
    Returns:
        dict with keys: id, name, genres, popularity, followers, images, external_urls
    """
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/artists/{artist_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(dict[str, Any], response.json())
```
**Begründung:** Gibt uns Popularity-Score und Follower-Count für bessere UI.

### Prio 2: Top Tracks (`GET /artists/{id}/top-tracks`)

**Vorgeschlagene Methoden-Signatur:**
```python
# Hinzufügen in SpotifyClient (spotify_client.py)
async def get_artist_top_tracks(
    self, artist_id: str, access_token: str, market: str = "DE"
) -> list[dict[str, Any]]:
    """Get artist's top 10 tracks by popularity.
    
    Args:
        artist_id: Spotify artist ID
        access_token: OAuth access token
        market: ISO 3166-1 alpha-2 country code (default: DE)
    
    Returns:
        List of track objects with keys: id, name, popularity, preview_url, album
    """
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/artists/{artist_id}/top-tracks",
        params={"market": market},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(list[dict[str, Any]], response.json().get("tracks", []))
```
**Begründung:** Sehr nützlich für "Smart Downloads" und Track-Vorschau.

### Prio 3: Related Artists (`GET /artists/{id}/related-artists`)

**Vorgeschlagene Methoden-Signatur:**
```python
# Hinzufügen in SpotifyClient (spotify_client.py)
async def get_related_artists(self, artist_id: str, access_token: str) -> list[dict[str, Any]]:
    """Get up to 20 artists similar to the given artist.
    
    Args:
        artist_id: Spotify artist ID
        access_token: OAuth access token
    
    Returns:
        List of artist objects with keys: id, name, genres, popularity, images
    """
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/artists/{artist_id}/related-artists",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return cast(list[dict[str, Any]], response.json().get("artists", []))
```
**Begründung:** Ermöglicht Artist Discovery und Empfehlungen.

---

## Verwandte Dokumentation

- [Followed Artists](./followed-artists.md) - Followed Artists Sync Feature
- [Automation & Watchlists](./automation-watchlists.md) - Watchlist System
- [Spotify Web API Docs](https://developer.spotify.com/documentation/web-api/reference/#category-artists) - Offizielle Spotify Docs

---

## Changelog

### 2025-11-25 - Spotify API Focus

- Dokumentation überarbeitet: Fokus auf Spotify Web API Artist Endpoints
- Auflistung genutzter vs. nicht genutzter Endpoints
- Feature-Ideen basierend auf verfügbaren API-Daten
