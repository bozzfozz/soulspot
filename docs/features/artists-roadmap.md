# Artists Roadmap

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Übersicht

Diese Dokumentation beschreibt den aktuellen Stand der Artists-Funktionalität in SoulSpot: Was wurde bereits implementiert, was können wir schon machen, und was fehlt noch?

---

## 🟢 Was wurde schon implementiert?

### Domain-Layer

| Komponente | Status | Beschreibung |
|------------|--------|--------------|
| `Artist` Entity | ✅ | Vollständige Domain-Entity mit ID, Name, Spotify URI, MusicBrainz ID, image_url, genres, tags |
| `ArtistId` Value Object | ✅ | UUID-basiertes Value Object für Artist-IDs |
| `SpotifyUri` Value Object | ✅ | Validiertes Value Object für Spotify URIs |
| `IArtistRepository` Port | ✅ | Interface für Artist-Datenzugriff (CRUD + Lookups) |

### Infrastruktur-Layer

| Komponente | Status | Beschreibung |
|------------|--------|--------------|
| `ArtistModel` (SQLAlchemy) | ✅ | ORM-Modell mit allen Feldern inkl. JSON-genres/tags |
| `ArtistRepository` | ✅ | SQLAlchemy-Implementierung mit allen CRUD-Operationen |
| DB-Migrationen | ✅ | Alle relevanten Migrationen vorhanden (genres, tags, image_url) |
| Indizes | ✅ | Performante Indizes auf name, spotify_uri, musicbrainz_id |

### API-Endpunkte

| Endpunkt | Methode | Status | Beschreibung |
|----------|---------|--------|--------------|
| `/api/automation/followed-artists/sync` | POST | ✅ | Synchronisiert alle gefolgten Artists von Spotify |
| `/api/automation/followed-artists/preview` | GET | ✅ | Schnelle Vorschau ohne DB-Speicherung |
| `/api/automation/followed-artists/watchlists/bulk` | POST | ✅ | Bulk-Erstellung von Watchlists |
| `/api/automation/watchlist` | POST | ✅ | Einzelne Watchlist erstellen |
| `/api/automation/watchlist` | GET | ✅ | Watchlists auflisten |
| `/api/automation/watchlist/{id}` | GET | ✅ | Watchlist-Details abrufen |
| `/api/automation/watchlist/{id}` | DELETE | ✅ | Watchlist löschen |
| `/api/automation/watchlist/{id}/check` | POST | ✅ | Manueller Release-Check |
| `/api/automation/discography/check` | POST | ✅ | Discographie-Vollständigkeit prüfen |
| `/api/automation/discography/missing` | GET | ✅ | Fehlende Alben aller Artists |

### Services

| Service | Status | Beschreibung |
|---------|--------|--------------|
| `FollowedArtistsService` | ✅ | Sync von Spotify-gefolgten Artists |
| `WatchlistService` | ✅ | CRUD für Artist-Watchlists |
| `DiscographyService` | ✅ | Discographie-Vollständigkeit prüfen |
| `SpotifyClient.get_followed_artists` | ✅ | API-Methode für gefolgte Artists |

### UI-Komponenten

| Komponente | Status | Beschreibung |
|------------|--------|--------------|
| Followed Artists Page | ✅ | `/automation/followed-artists` Seite |
| Artist-Grid | ✅ | Grid-Darstellung mit Bildern und Genres |
| Bulk-Watchlist-UI | ✅ | Mehrfachauswahl für Watchlist-Erstellung |
| HTMX-Partials | ✅ | `partials/followed_artists_list.html` |

### Watchlist-System

| Feature | Status | Beschreibung |
|---------|--------|--------------|
| `ArtistWatchlist` Entity | ✅ | Domain-Entity für Artist-Überwachung |
| `ArtistWatchlistModel` (DB) | ✅ | SQLAlchemy-Modell mit Status, Frequenz, Stats |
| `ArtistWatchlistRepository` | ✅ | Repository mit list_due_for_check() |
| Release-Detection | ✅ | Erkennung neuer Releases via Spotify API |
| Auto-Download | ✅ | Automatischer Download bei neuen Releases |

---

## 🔵 Was können wir schon machen?

### Artist-Synchronisation

1. **Gefolgte Artists von Spotify importieren**
   - Alle gefolgten Künstler werden automatisch abgerufen
   - Pagination für 100+ Artists unterstützt
   - Genres, Tags und Bilder werden mit-importiert
   - Neue Artists werden erstellt, existierende aktualisiert

2. **Preview ohne Speicherung**
   - Schneller Test der OAuth-Berechtigung
   - Vorschau auf bis zu 50 Artists
   - Keine Datenbank-Änderungen

### Watchlist-Management

1. **Bulk-Watchlist-Erstellung**
   - Mehrere Artists gleichzeitig auswählen
   - Einheitliche Settings (Frequenz, Auto-Download, Qualität)
   - Schnelle Einrichtung für hunderte Artists

2. **Individuelle Watchlist-Konfiguration**
   - Check-Frequenz (default: 24 Stunden)
   - Auto-Download an/aus
   - Qualitätsprofil (low, medium, high, lossless)

3. **Release-Überwachung**
   - Automatische Checks nach Zeitplan
   - Manueller Check per API-Aufruf
   - Statistiken zu gefundenen Releases und Downloads

### Discographie-Analyse

1. **Vollständigkeitsprüfung**
   - Vergleich mit Spotify-Discographie
   - Erkennung fehlender Alben/Singles
   - Pro-Artist oder für alle Artists

2. **Missing Albums Overview**
   - Übersicht aller Artists mit fehlenden Alben
   - Limitierte Abfrage zur Performance-Optimierung

---

## 🟠 Was fehlt noch?

### Artist-spezifische API-Endpunkte (Priorität: Hoch)

| Endpunkt | Beschreibung | Schwierigkeit |
|----------|--------------|---------------|
| `GET /api/artists` | Liste aller Artists mit Pagination | ⭐ Einfach |
| `GET /api/artists/{id}` | Artist-Details abrufen | ⭐ Einfach |
| `GET /api/artists/{id}/albums` | Alben eines Artists | ⭐ Einfach |
| `GET /api/artists/{id}/tracks` | Tracks eines Artists | ⭐ Einfach |
| `PUT /api/artists/{id}` | Artist-Daten aktualisieren | ⭐⭐ Mittel |
| `DELETE /api/artists/{id}` | Artist löschen (mit Cascade-Warnung) | ⭐⭐ Mittel |
| `GET /api/artists/search` | Artist-Suche (Name, Genre) | ⭐⭐ Mittel |

### Artist-UI-Erweiterungen (Priorität: Mittel)

| Feature | Beschreibung | Schwierigkeit |
|---------|--------------|---------------|
| Artist-Detailseite | `/artists/{id}` mit allen Infos | ⭐⭐ Mittel |
| Artist-Bibliothek | Grid/Liste aller lokalen Artists | ⭐⭐ Mittel |
| Genre-Filter | Filter nach Genre in Artist-Liste | ⭐⭐ Mittel |
| Artist-Statistiken | Tracks, Alben, Downloads pro Artist | ⭐⭐ Mittel |
| Artist-Timeline | Chronologische Ansicht der Releases | ⭐⭐⭐ Komplex |

### Artist-Metadaten-Enrichment (Priorität: Mittel)

| Feature | Beschreibung | Schwierigkeit |
|---------|--------------|---------------|
| MusicBrainz-Sync | Artist-Daten von MusicBrainz anreichern | ⭐⭐ Mittel |
| Last.fm-Tags | Genre-Tags von Last.fm importieren | ⭐⭐ Mittel |
| Discogs-Integration | Zusätzliche Metadaten von Discogs | ⭐⭐⭐ Komplex |
| Artist-Biographie | Bio-Text von verschiedenen Quellen | ⭐⭐⭐ Komplex |
| Ähnliche Artists | Related Artists Empfehlungen | ⭐⭐⭐ Komplex |

### Automatisierung (Priorität: Mittel)

| Feature | Beschreibung | Schwierigkeit |
|---------|--------------|---------------|
| Automatischer Artist-Sync | Regelmäßiger Sync gefolgter Artists | ⭐⭐ Mittel |
| Unfollow-Erkennung | Artists erkennen, denen nicht mehr gefolgt wird | ⭐ Einfach |
| Artist-Import aus Playlist | Artists aus Playlist-Tracks extrahieren | ⭐⭐ Mittel |
| Artist-Merge | Duplikate zusammenführen | ⭐⭐⭐ Komplex |

### Erweiterte Features (Priorität: Niedrig)

| Feature | Beschreibung | Schwierigkeit |
|---------|--------------|---------------|
| Artist-Kategorien | Benutzerdefinierte Kategorien/Tags | ⭐⭐ Mittel |
| Artist-Notizen | Persönliche Notizen zu Artists | ⭐ Einfach |
| Favoriten | Lieblings-Artists markieren | ⭐ Einfach |
| Artist-Export | Export der Artist-Bibliothek | ⭐⭐ Mittel |
| Statistik-Dashboard | Charts zu Artist-Aktivität | ⭐⭐⭐ Komplex |

---

## Technische Schulden

### Repository-Layer

| Item | Beschreibung | Priorität |
|------|--------------|-----------|
| `count_all()` fehlt | ArtistRepository hat keine count-Methode | ⭐⭐ Mittel |
| Batch-Operationen | `add_batch()` für Performance bei Bulk-Imports | ⭐⭐ Mittel |
| Search-Methode | `search_by_name()` mit LIKE/ILIKE | ⭐⭐ Mittel |

### Tests

| Item | Beschreibung | Priorität |
|------|--------------|-----------|
| Repository-Tests | Unit-Tests für ArtistRepository | ⭐⭐⭐ Hoch |
| API-Integrationstests | Tests für Followed-Artists-Endpoints | ⭐⭐⭐ Hoch |
| Service-Tests | Tests für FollowedArtistsService | ⭐⭐ Mittel |

### Performance

| Item | Beschreibung | Priorität |
|------|--------------|-----------|
| Caching | Artist-Daten cachen für schnellere Lookups | ⭐⭐ Mittel |
| Lazy Loading | Beziehungen (albums, tracks) lazy laden | ⭐⭐ Mittel |
| Bulk-Queries | N+1 Problem bei Artist-Listen vermeiden | ⭐⭐⭐ Hoch |

---

## Implementierungs-Empfehlungen

### Phase 1: Basis-API (1-2 Tage)

```
1. GET /api/artists - Liste aller Artists
2. GET /api/artists/{id} - Artist-Details
3. GET /api/artists/{id}/albums - Alben
4. GET /api/artists/{id}/tracks - Tracks
5. GET /api/artists/search?q= - Suche
```

### Phase 2: Artist-UI (2-3 Tage)

```
1. /artists - Artist-Bibliothek Übersicht
2. /artists/{id} - Artist-Detailseite
3. Genre-Filter und Sortierung
4. Artist-Statistiken Widget
```

### Phase 3: Metadaten-Enrichment (3-5 Tage)

```
1. MusicBrainz Artist-Lookup
2. Last.fm Tags-Integration
3. Automatisches Enrichment bei Import
4. Manueller Refresh per Button
```

### Phase 4: Erweiterte Features (ongoing)

```
1. Artist-Kategorien
2. Favoriten-System
3. Erweiterte Statistiken
4. Export-Funktionen
```

---

## Verwandte Dokumentation

- [Followed Artists](./followed-artists.md) - Detailed guide for followed artists feature
- [Automation & Watchlists](./automation-watchlists.md) - Watchlist system details
- [Metadata Enrichment](./metadata-enrichment.md) - Metadata sources and enrichment
- [Download Management](./download-management.md) - Download queue and processing

---

## Changelog

### 2025-11-25 - Initial Roadmap

- Erstellung der initialen Roadmap-Dokumentation
- Auflistung aller implementierten Features
- Definition der fehlenden Features und Priorisierung
