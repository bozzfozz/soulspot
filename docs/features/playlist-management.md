# Playlist Management

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Übersicht

Das Playlist Management ermöglicht den Import, die Synchronisation und den Export von Spotify-Playlists. Du kannst einzelne Playlists oder deine gesamte Spotify-Bibliothek importieren und diese automatisch mit Spotify synchron halten.

---

## Features

### Playlist Import

Importiere einzelne Spotify-Playlists oder deine gesamte Playlist-Bibliothek:

1. **Einzelner Import**: Importiere eine Playlist per Spotify-URL oder ID
2. **Bibliotheks-Sync**: Importiere alle deine Spotify-Playlists auf einmal
3. **Automatische Track-Erfassung**: Alle Tracks werden mit Metadaten gespeichert

### Playlist Synchronisation

Halte deine importierten Playlists aktuell:

- **Einzelne Playlist syncen**: Update eine spezifische Playlist
- **Alle Playlists syncen**: Batch-Sync aller importierten Playlists
- **Delta-Sync**: Nur neue oder geänderte Tracks werden aktualisiert

### Playlist Export

Exportiere deine Playlists in verschiedene Formate:

- **M3U**: Standard-Playlist-Format für Mediaplayer
- **CSV**: Tabellarische Ansicht für Excel/Google Sheets
- **JSON**: Vollständige Daten für Entwickler/Backup

### Missing Tracks

Identifiziere und lade fehlende Tracks:

- Tracks ohne lokale Datei werden erkannt
- Batch-Download aller fehlenden Tracks möglich

---

## Nutzung über die Web-UI

### Playlist importieren

1. Navigiere zu **Playlists** im Hauptmenü
2. Klicke auf **Import Playlist**
3. Füge die Spotify-Playlist-URL oder ID ein
4. Klicke auf **Import**

**Akzeptierte Formate:**
- Spotify-URL: `https://open.spotify.com/playlist/2ZBCi09CSeWMBOoHZdN6Nl`
- Playlist-ID: `2ZBCi09CSeWMBOoHZdN6Nl`

### Bibliothek synchronisieren

1. Navigiere zu **Playlists**
2. Klicke auf **Sync Library**
3. Alle deine Spotify-Playlists werden importiert (nur Metadaten)
4. Wähle einzelne Playlists für den vollständigen Import mit Tracks

### Playlist exportieren

1. Öffne die gewünschte Playlist
2. Klicke auf das Export-Icon
3. Wähle das Format (M3U, CSV oder JSON)
4. Die Datei wird automatisch heruntergeladen

---

## API-Endpunkte

### POST `/api/playlists/import`

Importiert eine Spotify-Playlist.

**Query-Parameter:**
| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `playlist_id` | string | Spotify Playlist-ID oder URL |
| `fetch_all_tracks` | boolean | Alle Tracks abrufen (default: true) |

**Response:**
```json
{
  "message": "Playlist imported successfully",
  "playlist_id": "uuid-der-playlist",
  "playlist_name": "Meine Playlist",
  "tracks_imported": 42,
  "tracks_failed": 0,
  "errors": []
}
```

### POST `/api/playlists/sync-library`

Synchronisiert die gesamte Playlist-Bibliothek (nur Metadaten).

**Response:**
```json
{
  "message": "Playlist library synced successfully",
  "total_playlists": 15,
  "synced_count": 10,
  "updated_count": 5,
  "results": [...]
}
```

### GET `/api/playlists/`

Listet alle importierten Playlists auf.

**Query-Parameter:**
| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `skip` | int | 0 | Offset für Pagination |
| `limit` | int | 20 | Anzahl der Ergebnisse (max 100) |

### GET `/api/playlists/{playlist_id}`

Ruft Details einer Playlist ab.

**Response:**
```json
{
  "id": "uuid",
  "name": "Playlist Name",
  "description": "Beschreibung",
  "source": "spotify",
  "track_ids": ["track-uuid-1", "track-uuid-2"],
  "track_count": 42,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T00:00:00Z"
}
```

### POST `/api/playlists/{playlist_id}/sync`

Synchronisiert eine einzelne Playlist mit Spotify.

### POST `/api/playlists/sync-all`

Synchronisiert alle Playlists mit Spotify.

> ⚠️ **Achtung:** Diese Operation kann bei vielen Playlists lange dauern!

### GET `/api/playlists/{playlist_id}/export/m3u`

Exportiert die Playlist als M3U-Datei.

### GET `/api/playlists/{playlist_id}/export/csv`

Exportiert die Playlist als CSV-Datei.

### GET `/api/playlists/{playlist_id}/export/json`

Exportiert die Playlist als JSON.

### GET `/api/playlists/{playlist_id}/missing-tracks`

Gibt Tracks zurück, die in der Playlist sind, aber keine lokale Datei haben.

**Response:**
```json
{
  "playlist_id": "uuid",
  "playlist_name": "Meine Playlist",
  "missing_tracks": [...],
  "missing_count": 5,
  "total_tracks": 42
}
```

### POST `/api/playlists/{playlist_id}/download-missing`

Identifiziert fehlende Tracks zum Download.

---

## Workflow-Beispiel

### Vollständiger Import-Workflow

```mermaid
graph TD
    A[Spotify-URL kopieren] --> B[POST /playlists/import]
    B --> C{Erfolgreich?}
    C -->|Ja| D[Playlist in DB gespeichert]
    C -->|Nein| E[Fehler prüfen]
    D --> F[GET /playlists/{id}/missing-tracks]
    F --> G{Fehlende Tracks?}
    G -->|Ja| H[Downloads starten]
    G -->|Nein| I[Fertig]
```

---

## Troubleshooting

### Problem: Import schlägt fehl

**Mögliche Ursachen:**
1. **Keine gültige Spotify-Session**: Authentifiziere dich erneut unter `/auth`
2. **Playlist ist privat**: Die Playlist muss öffentlich sein oder dir gehören
3. **Ungültige URL/ID**: Prüfe das Format der Playlist-URL

### Problem: Tracks werden nicht importiert

**Mögliche Ursachen:**
1. **Rate-Limiting**: Spotify limitiert API-Aufrufe. Warte und versuche es erneut.
2. **Große Playlist**: Bei Playlists mit 1000+ Tracks kann der Import länger dauern.

### Problem: Export enthält keine Dateipfade

**Lösung:** M3U-Export funktioniert nur für Tracks mit heruntergeladenen Dateien. Lade fehlende Tracks zuerst herunter.

---

## Verwandte Features

- [Download Management](./download-management.md) - Für das Herunterladen der Tracks
- [Track Management](./track-management.md) - Für die Verwaltung einzelner Tracks
- [Authentication](../api/auth-api.md) - Für die Spotify-Verbindung
