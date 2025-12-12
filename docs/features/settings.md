# Settings

> **Version:** 1.2  
> **Last Updated:** 2025-11-30

---

## Übersicht

Die Settings-Verwaltung ermöglicht das Anzeigen und Konfigurieren der Anwendung. Die Einstellungen sind in Kategorien gruppiert:

- **Spotify Sync** - Auto-Sync Einstellungen (Runtime, DB-gespeichert) ⭐ NEU
- **Allgemein** - App-Name, Logging, Debug
- **Integrationen** - Spotify, slskd, MusicBrainz Credentials
- **Download** - Download-Queue Konfiguration
- **Darstellung** - Theme-Einstellungen
- **Erweitert** - API-Server, Circuit Breaker

> 💡 **Neu:** Spotify Sync Settings werden in der Datenbank gespeichert und können zur Laufzeit ohne Neustart geändert werden. Siehe [Spotify Sync](./spotify-sync.md) für Details.

---

## Einstellungs-Kategorien

### Allgemein (General)

| Einstellung | Beschreibung | Typ | Default |
|-------------|--------------|-----|---------|
| `app_name` | Name der Anwendung | string | "SoulSpot" |
| `log_level` | Logging-Level | string | "INFO" |
| `debug` | Debug-Modus aktivieren | boolean | false |

### Integrationen (Integration)

#### Spotify

| Einstellung | Beschreibung | Typ |
|-------------|--------------|-----|
| `spotify_client_id` | Spotify OAuth Client ID | string |
| `spotify_client_secret` | Spotify OAuth Client Secret | string (maskiert) |
| `spotify_redirect_uri` | OAuth Redirect URL | string |

#### slskd (Soulseek)

| Einstellung | Beschreibung | Typ |
|-------------|--------------|-----|
| `slskd_url` | URL zum slskd-Dienst | string |
| `slskd_username` | slskd Benutzername | string |
| `slskd_password` | slskd Passwort | string (maskiert) |
| `slskd_api_key` | slskd API Key (optional) | string (maskiert) |

#### MusicBrainz

| Einstellung | Beschreibung | Typ | Default |
|-------------|--------------|-----|---------|
| `musicbrainz_app_name` | App-Name für MusicBrainz API | string | "SoulSpot" |
| `musicbrainz_contact` | Kontakt-Email für MusicBrainz | string | "" |

### Download

| Einstellung | Beschreibung | Typ | Default | Bereich |
|-------------|--------------|-----|---------|---------|
| `max_concurrent_downloads` | Max. parallele Downloads | int | 5 | 1-10 |
| `default_max_retries` | Wiederholungsversuche bei Fehler | int | 3 | 1-10 |
| `enable_priority_queue` | Priorisierung aktivieren | boolean | true | - |

### Darstellung (Appearance)

| Einstellung | Beschreibung | Typ | Default |
|-------------|--------------|-----|---------|
| `theme` | UI-Theme | string | "auto" |

**Theme-Optionen:**
- `light`: Helles Theme
- `dark`: Dunkles Theme
- `auto`: Folgt dem System

### Erweitert (Advanced)

| Einstellung | Beschreibung | Typ | Default | Bereich |
|-------------|--------------|-----|---------|---------|
| `api_host` | API Server Host | string | "0.0.0.0" | - |
| `api_port` | API Server Port | int | 8765 | 1-65535 |
| `circuit_breaker_failure_threshold` | Fehler bis Circuit Break | int | 5 | 1+ |
| `circuit_breaker_timeout` | Circuit Breaker Timeout (Sek.) | float | 60.0 | 1.0+ |

---

## Nutzung über die Web-UI

### Einstellungen anzeigen

1. Navigiere zu **Settings**
2. Die Einstellungen sind in Tabs gruppiert
3. Sensible Werte (Passwörter, API-Keys) werden mit `***` maskiert

### Einstellungen ändern

> ⚠️ **Hinweis:** Die Bearbeitung von Einstellungen ist derzeit noch nicht vollständig implementiert. Änderungen über die UI werden akzeptiert, aber nicht persistent gespeichert.

**Aktuelle Empfehlung:**
Ändere Einstellungen über die `.env` Datei und starte die Anwendung neu.

---

## API-Endpunkte

### GET `/api/settings/`

Ruft alle aktuellen Einstellungen ab.

**Response:**
```json
{
  "general": {
    "app_name": "SoulSpot",
    "log_level": "INFO",
    "debug": false
  },
  "integration": {
    "spotify_client_id": "abc123...",
    "spotify_client_secret": "***",
    "spotify_redirect_uri": "http://localhost:8765/auth/callback",
    "slskd_url": "http://localhost:5030",
    "slskd_username": "user",
    "slskd_password": "***",
    "slskd_api_key": "***",
    "musicbrainz_app_name": "SoulSpot",
    "musicbrainz_contact": "contact@example.com"
  },
  "download": {
    "max_concurrent_downloads": 5,
    "default_max_retries": 3,
    "enable_priority_queue": true
  },
  "appearance": {
    "theme": "auto"
  },
  "advanced": {
    "api_host": "0.0.0.0",
    "api_port": 8765,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout": 60.0
  }
}
```

### POST `/api/settings/`

Aktualisiert Einstellungen.

> ⚠️ **Hinweis:** Dieser Endpoint akzeptiert Änderungen, speichert sie aber derzeit nicht persistent.

**Request:** Gleiche Struktur wie GET Response

**Response:**
```json
{
  "message": "Settings updated successfully",
  "note": "Settings will be applied on next application restart"
}
```

### POST `/api/settings/reset`

Setzt alle Einstellungen auf Standardwerte zurück.

> ⚠️ **Hinweis:** Dieser Endpoint ist derzeit ein Stub und führt keine tatsächliche Reset-Operation durch.

**Response:**
```json
{
  "message": "Settings reset to defaults",
  "note": "Please restart the application for changes to take effect"
}
```

### GET `/api/settings/defaults`

Ruft die Standardwerte aller Einstellungen ab.

**Response:**
```json
{
  "general": {
    "app_name": "SoulSpot",
    "log_level": "INFO",
    "debug": false
  },
  "integration": {
    "spotify_client_id": "",
    "spotify_client_secret": "",
    "spotify_redirect_uri": "http://localhost:8765/auth/callback",
    "slskd_url": "http://localhost:5030",
    "slskd_username": "admin",
    "slskd_password": "",
    "slskd_api_key": null,
    "musicbrainz_app_name": "SoulSpot",
    "musicbrainz_contact": ""
  },
  "download": {
    "max_concurrent_downloads": 5,
    "default_max_retries": 3,
    "enable_priority_queue": true
  },
  "appearance": {
    "theme": "auto"
  },
  "advanced": {
    "api_host": "0.0.0.0",
    "api_port": 8765,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout": 60.0
  }
}
```

---

## Spotify Database Statistics

Die Spotify Sync Sektion in Settings zeigt zwei Statistik-Bereiche:

### Image Storage (Festplatten-Statistiken)

Zeigt wie viele Bilder auf der Festplatte gespeichert sind:

| Statistik | Beschreibung |
|-----------|--------------|
| Artist Images | Anzahl und Größe der Artist-Bilder |
| Album Covers | Anzahl und Größe der Album-Cover |
| Playlist Covers | Anzahl und Größe der Playlist-Cover |
| Total | Gesamtanzahl und -größe aller Bilder |

### Synced Data (Datenbank-Statistiken)

Zeigt wie viele Entities aus Spotify in der Datenbank gespeichert sind:

| Statistik | Beschreibung | Kriterium |
|-----------|--------------|-----------|
| Artists | Anzahl Künstler aus Spotify | `spotify_uri IS NOT NULL` |
| Albums | Anzahl Alben aus Spotify | `spotify_uri IS NOT NULL` |
| Tracks | Anzahl Songs aus Spotify | `spotify_uri IS NOT NULL` |
| Playlists | Anzahl Playlists aus Spotify | `source = 'spotify'` |

**API-Endpunkt:** `GET /api/settings/spotify-sync/db-stats`

**Response:**
```json
{
  "artists_count": 125,
  "albums_count": 487,
  "tracks_count": 5234,
  "playlists_count": 12,
  "total_count": 5858
}
```

---

## Konfiguration über Umgebungsvariablen

Alle Einstellungen können über Umgebungsvariablen in der `.env` Datei konfiguriert werden:

### Beispiel `.env`

```env
# General
LOG_LEVEL=INFO
DEBUG=false

# Spotify OAuth
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8765/auth/callback

# slskd (Soulseek)
SLSKD_URL=http://localhost:5030
SLSKD_USERNAME=admin
SLSKD_PASSWORD=your_password
SLSKD_API_KEY=optional_api_key

# MusicBrainz
MUSICBRAINZ_APP_NAME=SoulSpot
MUSICBRAINZ_CONTACT=your@email.com

# Download
DOWNLOAD_MAX_CONCURRENT=5
DOWNLOAD_MAX_RETRIES=3

# API
API_HOST=0.0.0.0
API_PORT=8765

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60.0
```

---

## Circuit Breaker

Der Circuit Breaker schützt vor kaskadierten Fehlern bei externen APIs:

### Funktionsweise

1. **Closed (Normal)**: Anfragen werden normal durchgeführt
2. **Open (Blockiert)**: Nach X Fehlern werden Anfragen sofort abgelehnt
3. **Half-Open (Test)**: Nach Timeout wird eine Test-Anfrage durchgelassen

### Einstellungen

| Einstellung | Beschreibung | Empfehlung |
|-------------|--------------|------------|
| `failure_threshold` | Fehler bis Open | 5 für stabile APIs, 3 für instabile |
| `timeout` | Sekunden bis Half-Open | 60 für kritische, 300 für unkritische |

### Betroffene Services

- Spotify API
- MusicBrainz API
- Last.fm API (wenn konfiguriert)
- slskd API

---

## Sicherheitshinweise

### Sensible Daten

Folgende Werte sollten niemals exponiert werden:

- `spotify_client_secret`
- `slskd_password`
- `slskd_api_key`

Diese werden in der API-Response mit `***` maskiert.

### Produktionsempfehlungen

1. **HTTPS aktivieren**: Setze `secure_cookies=true` in Production
2. **Debug deaktivieren**: Setze `debug=false`
3. **Log-Level**: Verwende `INFO` oder `WARNING` in Production
4. **API-Host**: Beschränke auf `127.0.0.1` wenn nur lokal genutzt

---

## Troubleshooting

### Problem: Einstellungen werden nicht übernommen

**Lösung:**
1. Prüfe die `.env` Datei auf Syntaxfehler
2. Starte die Anwendung neu
3. Prüfe Container-Logs auf Fehler

### Problem: Spotify-Verbindung schlägt fehl

**Prüfe:**
1. `spotify_client_id` und `spotify_client_secret` sind korrekt
2. `spotify_redirect_uri` entspricht der Konfiguration im Spotify Developer Dashboard
3. Die App ist im Spotify Developer Dashboard freigegeben

### Problem: slskd-Verbindung schlägt fehl

**Prüfe:**
1. slskd-Container läuft (`docker ps`)
2. `slskd_url` ist erreichbar (z.B. `http://localhost:5030`)
3. Credentials sind korrekt

### Problem: MusicBrainz Rate-Limiting

**Lösung:**
1. Setze korrekten `musicbrainz_contact` (wird in User-Agent verwendet)
2. MusicBrainz erlaubt nur 1 Request/Sekunde
3. Bei Problemen: Warte einige Minuten

---

## Verwandte Features

- [Spotify Sync](./spotify-sync.md) - Auto-Sync Einstellungen ⭐ NEU
- [Authentication](../api/auth-api.md) - Spotify OAuth Konfiguration
- [Download Management](./download-management.md) - Download-Einstellungen
- [Metadata Enrichment](./metadata-enrichment.md) - MusicBrainz-Konfiguration
