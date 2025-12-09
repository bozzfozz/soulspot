# Spotify Sync API

> **⚠️ DEPRECATED:** This API doc is superseded by **docs/api/settings-api.md** (Spotify Sync section covers all 8 sync endpoints). For architecture/worker details, see **docs/features/spotify-sync.md**.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

> **Version:** 1.1  
> **Last Updated:** 2025-01-15  
> **Base Path:** `/api/settings`  
> **Status:** ~~Active~~ SUPERSEDED by settings-api.md

---

## Übersicht

Die Spotify Sync API ermöglicht die Konfiguration und Steuerung der automatischen Synchronisation von Spotify-Daten. Die Einstellungen werden in der Datenbank gespeichert und können zur Laufzeit ohne Neustart geändert werden.

### Endpunkt-Übersicht

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/api/settings/spotify-sync` | Sync-Einstellungen abrufen |
| PATCH | `/api/settings/spotify-sync` | Sync-Einstellungen aktualisieren |
| GET | `/api/settings/spotify-sync/image-stats` | Bild-Statistiken abrufen |
| POST | `/api/settings/spotify-sync/trigger/{sync_type}` | Manuellen Sync starten |
| GET | `/api/settings/spotify-sync/worker-status` | Background Worker Status |

---

## Endpunkte

### Sync Settings abrufen

```http
GET /api/settings/spotify-sync
```

Ruft alle Spotify-Sync-Einstellungen inklusive Image-Statistiken ab.

#### Response

```json
{
  "settings": {
    "auto_sync_enabled": true,
    "auto_sync_artists": true,
    "auto_sync_playlists": true,
    "auto_sync_liked_songs": true,
    "auto_sync_saved_albums": true,
    "artists_sync_interval_minutes": 5,
    "playlists_sync_interval_minutes": 10,
    "download_images": true,
    "remove_unfollowed_artists": true,
    "remove_unfollowed_playlists": false
  },
  "image_stats": {
    "artists_bytes": 1258291,
    "albums_bytes": 8847200,
    "playlists_bytes": 314572,
    "total_bytes": 10420063,
    "artists_count": 42,
    "albums_count": 156,
    "playlists_count": 12,
    "total_count": 210
  }
}
```

#### Response Schema

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `settings` | `SpotifySyncSettings` | Sync-Einstellungen |
| `image_stats` | `SpotifyImageStats?` | Disk-Usage-Statistiken (optional) |

---

### Sync Settings aktualisieren

```http
PUT /api/settings/spotify-sync
```

Aktualisiert die Spotify-Sync-Einstellungen. Änderungen werden sofort wirksam.

#### Request Body

```json
{
  "auto_sync_enabled": true,
  "auto_sync_artists": true,
  "auto_sync_playlists": true,
  "auto_sync_liked_songs": false,
  "auto_sync_saved_albums": true,
  "artists_sync_interval_minutes": 10,
  "playlists_sync_interval_minutes": 15,
  "download_images": true,
  "remove_unfollowed_artists": true,
  "remove_unfollowed_playlists": false
}
```

#### Request Schema

| Feld | Typ | Required | Default | Beschreibung |
|------|-----|----------|---------|--------------|
| `auto_sync_enabled` | boolean | Ja | `true` | Master-Toggle für Auto-Sync |
| `auto_sync_artists` | boolean | Ja | `true` | Künstler-Sync aktivieren |
| `auto_sync_playlists` | boolean | Ja | `true` | Playlist-Sync aktivieren |
| `auto_sync_liked_songs` | boolean | Ja | `true` | Liked Songs-Sync aktivieren |
| `auto_sync_saved_albums` | boolean | Ja | `true` | Saved Albums-Sync aktivieren |
| `artists_sync_interval_minutes` | int | Ja | `5` | Cooldown Artist-Sync (1-60) |
| `playlists_sync_interval_minutes` | int | Ja | `10` | Cooldown Playlist-Sync (1-60) |
| `download_images` | boolean | Ja | `true` | Bilder lokal speichern |
| `remove_unfollowed_artists` | boolean | Ja | `true` | Entfolgte Künstler entfernen |
| `remove_unfollowed_playlists` | boolean | Ja | `false` | Gelöschte Playlists entfernen |

#### Response

Gibt die aktualisierten Settings zurück (gleiche Struktur wie Request).

---

### Einzelnes Setting togglen

```http
POST /api/settings/spotify-sync/toggle/{setting_name}
```

Toggled ein einzelnes Boolean-Setting (true → false, false → true).

#### URL-Parameter

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `setting_name` | string | Name des zu togglenden Settings |

**Gültige Werte für `setting_name`:**

| Wert | Beschreibung |
|------|--------------|
| `auto_sync_enabled` | Master-Toggle |
| `auto_sync_artists` | Artists-Sync |
| `auto_sync_playlists` | Playlists-Sync |
| `auto_sync_liked_songs` | Liked Songs-Sync |
| `auto_sync_saved_albums` | Saved Albums-Sync |
| `download_images` | Image-Download |
| `remove_unfollowed_artists` | Artists entfernen |
| `remove_unfollowed_playlists` | Playlists entfernen |

#### Response

```json
{
  "setting": "auto_sync_artists",
  "old_value": true,
  "new_value": false
}
```

#### Fehler

```json
{
  "detail": "Unknown setting: invalid_name. Valid settings: ['auto_sync_enabled', ...]"
}
```

---

### Disk Usage abrufen

```http
GET /api/settings/spotify-sync/disk-usage
```

Ruft Speicherstatistiken für lokal gespeicherte Spotify-Bilder ab.

#### Response

```json
{
  "artists_bytes": 1258291,
  "albums_bytes": 8847200,
  "playlists_bytes": 314572,
  "total_bytes": 10420063,
  "artists_count": 42,
  "albums_count": 156,
  "playlists_count": 12,
  "total_count": 210
}
```

#### Response Schema

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `artists_bytes` | int | Bytes für Künstler-Bilder |
| `albums_bytes` | int | Bytes für Album-Cover |
| `playlists_bytes` | int | Bytes für Playlist-Cover |
| `total_bytes` | int | Gesamte Bytes |
| `artists_count` | int | Anzahl Künstler-Bilder |
| `albums_count` | int | Anzahl Album-Cover |
| `playlists_count` | int | Anzahl Playlist-Cover |
| `total_count` | int | Gesamtanzahl Bilder |

---

### Manuellen Sync triggern

```http
POST /api/settings/spotify-sync/trigger/{sync_type}
```

Triggert einen manuellen Sync, unabhängig von Cooldown-Timern.

#### URL-Parameter

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `sync_type` | string | Art des Syncs |

**Gültige Werte für `sync_type`:**

| Wert | Beschreibung |
|------|--------------|
| `artists` | Nur Followed Artists synken |
| `playlists` | Nur Playlists synken |
| `liked` | Nur Liked Songs synken |
| `albums` | Nur Saved Albums synken |
| `all` | Alle Sync-Typen ausführen |

#### Response (Erfolg)

```json
{
  "success": true,
  "message": "Artists synced: 42 updated, 3 removed",
  "sync_type": "artists"
}
```

#### Response (Full Sync)

```json
{
  "success": true,
  "message": "Full sync complete: 42 artists, 15 playlists, 25 albums",
  "sync_type": "all"
}
```

#### Fehler: Nicht authentifiziert

**Status:** `401 Unauthorized`

```json
{
  "detail": "Not authenticated with Spotify. Please connect your account first."
}
```

#### Fehler: Ungültiger Sync-Typ

**Status:** `400 Bad Request`

```json
{
  "detail": "Invalid sync type: invalid. Valid types: {'artists', 'playlists', 'liked', 'albums', 'all'}"
}
```

#### Fehler: Sync fehlgeschlagen

**Status:** `500 Internal Server Error`

```json
{
  "detail": "Sync failed: Connection timeout to Spotify API"
}
```

---

### Worker-Status abfragen

```http
GET /api/settings/spotify-sync/worker-status
```

Gibt den aktuellen Status des Background Sync Workers zurück, inkl. letzter Sync-Zeiten und Statistiken.

#### Response (Erfolg)

```json
{
  "is_running": true,
  "check_interval_seconds": 60,
  "last_syncs": {
    "artists": "2024-01-15T14:30:00Z",
    "playlists": "2024-01-15T14:25:00Z",
    "liked": null,
    "albums": "2024-01-15T14:20:00Z"
  },
  "sync_stats": {
    "artists": {
      "last_result": "success",
      "items_synced": 42,
      "duration_seconds": 3.5
    },
    "playlists": {
      "last_result": "success",
      "items_synced": 15,
      "duration_seconds": 2.1
    }
  },
  "next_check_in_seconds": 45
}
```

#### Response Schema

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `is_running` | bool | Ob der Worker läuft |
| `check_interval_seconds` | int | Wie oft der Worker prüft (Standard: 60) |
| `last_syncs` | object | Letzte Sync-Zeit pro Typ (null = noch nie) |
| `sync_stats` | object | Statistiken pro Sync-Typ |
| `next_check_in_seconds` | int | Sekunden bis zur nächsten Prüfung |

#### Response (Worker nicht verfügbar)

Falls der Worker nicht initialisiert wurde:

```json
{
  "is_running": false,
  "check_interval_seconds": 0,
  "last_syncs": {},
  "sync_stats": {},
  "next_check_in_seconds": null
}
```

---

## Datenmodelle

### SpotifySyncSettings

```typescript
interface SpotifySyncSettings {
  auto_sync_enabled: boolean;        // Master-Toggle
  auto_sync_artists: boolean;        // Artists synken
  auto_sync_playlists: boolean;      // Playlists synken
  auto_sync_liked_songs: boolean;    // Liked Songs synken
  auto_sync_saved_albums: boolean;   // Saved Albums synken
  artists_sync_interval_minutes: number;   // Cooldown (1-60)
  playlists_sync_interval_minutes: number; // Cooldown (1-60)
  download_images: boolean;          // Bilder speichern
  remove_unfollowed_artists: boolean;   // Cleanup Artists
  remove_unfollowed_playlists: boolean; // Cleanup Playlists
}
```

### SpotifyImageStats

```typescript
interface SpotifyImageStats {
  artists_bytes: number;    // Bytes Artists
  albums_bytes: number;     // Bytes Albums
  playlists_bytes: number;  // Bytes Playlists
  total_bytes: number;      // Gesamt Bytes
  artists_count: number;    // Anzahl Artists
  albums_count: number;     // Anzahl Albums
  playlists_count: number;  // Anzahl Playlists
  total_count: number;      // Gesamt Anzahl
}
```

### SyncTriggerResponse

```typescript
interface SyncTriggerResponse {
  success: boolean;     // Sync erfolgreich gestartet
  message: string;      // Status-Nachricht
  sync_type: string;    // Art des Syncs
}
```

---

## Beispiele

### cURL: Settings abrufen

```bash
curl -X GET "http://localhost:8000/api/settings/spotify-sync" \
  -H "Accept: application/json"
```

### cURL: Settings aktualisieren

```bash
curl -X PUT "http://localhost:8000/api/settings/spotify-sync" \
  -H "Content-Type: application/json" \
  -d '{
    "auto_sync_enabled": true,
    "auto_sync_artists": true,
    "auto_sync_playlists": false,
    "auto_sync_liked_songs": true,
    "auto_sync_saved_albums": true,
    "artists_sync_interval_minutes": 15,
    "playlists_sync_interval_minutes": 30,
    "download_images": true,
    "remove_unfollowed_artists": true,
    "remove_unfollowed_playlists": false
  }'
```

### cURL: Setting togglen

```bash
curl -X POST "http://localhost:8000/api/settings/spotify-sync/toggle/auto_sync_artists" \
  -H "Accept: application/json"
```

### cURL: Manuellen Sync triggern

```bash
# Nur Artists
curl -X POST "http://localhost:8000/api/settings/spotify-sync/trigger/artists"

# Alles synken
curl -X POST "http://localhost:8000/api/settings/spotify-sync/trigger/all"
```

### JavaScript: Fetch API

```javascript
// Settings laden
const response = await fetch('/api/settings/spotify-sync');
const data = await response.json();
console.log(data.settings.auto_sync_enabled);

// Settings speichern
await fetch('/api/settings/spotify-sync', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    auto_sync_enabled: true,
    auto_sync_artists: true,
    // ... weitere Settings
  })
});

// Manuellen Sync triggern
const syncResponse = await fetch('/api/settings/spotify-sync/trigger/artists', {
  method: 'POST'
});
const result = await syncResponse.json();
console.log(result.message);
```

### Python: httpx

```python
import httpx

async with httpx.AsyncClient() as client:
    # Settings abrufen
    response = await client.get("http://localhost:8000/api/settings/spotify-sync")
    settings = response.json()
    
    # Settings aktualisieren
    await client.put(
        "http://localhost:8000/api/settings/spotify-sync",
        json={
            "auto_sync_enabled": True,
            "auto_sync_artists": True,
            "artists_sync_interval_minutes": 10,
            # ...
        }
    )
    
    # Sync triggern
    result = await client.post(
        "http://localhost:8000/api/settings/spotify-sync/trigger/all"
    )
    print(result.json()["message"])
```

---

## Verwandte Dokumentation

- [Spotify Sync Feature](../features/spotify-sync.md) - Feature-Dokumentation
- [Settings API](../features/settings.md) - Allgemeine Settings
- [Spotify Artist API](./spotify-artist-api.md) - Artist-Endpunkte
- [Spotify Playlist API](./spotify-playlist-api.md) - Playlist-Endpunkte
