# Followed Artists

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Übersicht

Das Followed Artists Feature ermöglicht den Zugriff auf alle Künstler, denen du auf Spotify folgst. Du kannst diese Artists synchronisieren und mit einem Klick Watchlists erstellen, um automatisch alle Alben und neue Releases herunterzuladen.

---

## Features

### Artist-Synchronisation

- **Vollständiger Sync**: Alle gefolgten Künstler von Spotify importieren
- **Pagination**: Automatische Verarbeitung bei 100+ Artists
- **Genre-Tags**: Genres werden von Spotify mitimportiert

### Bulk-Watchlist-Erstellung

- **Mehrfachauswahl**: Wähle mehrere Artists gleichzeitig aus
- **Einheitliche Einstellungen**: Alle Watchlists mit gleichen Settings
- **Schnelle Einrichtung**: Hunderte Watchlists in Sekunden erstellen

### Preview-Modus

- **Schnelle Vorschau**: Zeigt bis zu 50 Artists ohne DB-Speicherung
- **OAuth-Test**: Prüft ob `user-follow-read` Berechtigung funktioniert

---

## Voraussetzungen

| Anforderung | Beschreibung |
|-------------|--------------|
| Spotify-Session | Aktive OAuth-Verbindung |
| OAuth-Scope | `user-follow-read` Berechtigung |
| Gefolgte Artists | Mindestens ein Künstler auf Spotify gefolgt |

---

## Nutzung über die Web-UI

### Artists synchronisieren

1. Navigiere zu **Automation** → **Followed Artists**
2. Klicke auf **Sync from Spotify**
3. Warte, bis alle Artists geladen sind
4. Die Artists werden in einem Grid angezeigt

### Watchlists erstellen

1. Nach dem Sync: Wähle Artists per Checkbox aus
2. Oder klicke auf **Select All** für alle Artists
3. Konfiguriere die Watchlist-Einstellungen:
   - **Check-Intervall**: z.B. alle 24 Stunden
   - **Auto-Download**: Automatisch herunterladen?
   - **Qualitätsprofil**: high, medium, low
4. Klicke auf **Create Watchlists**

### Preview ohne Sync

1. Navigiere zu **Automation** → **Followed Artists**
2. Klicke auf **Preview** statt **Sync**
3. Die ersten 50 Artists werden angezeigt (ohne DB-Speicherung)

---

## API-Endpunkte

### POST `/api/automation/followed-artists/sync`

Synchronisiert alle gefolgten Artists von Spotify zur lokalen Datenbank.

**Response (JSON):**
```json
{
  "total_fetched": 150,
  "created": 100,
  "updated": 50,
  "errors": 0,
  "artists": [
    {
      "id": "artist-uuid",
      "name": "Artist Name",
      "spotify_uri": "spotify:artist:xyz",
      "image_url": "https://...",
      "genres": ["electronic", "synthwave"]
    }
  ]
}
```

**Response (HTMX):**
Bei `HX-Request: true` Header wird ein HTML-Partial zurückgegeben.

### POST `/api/automation/followed-artists/watchlists/bulk`

Erstellt Watchlists für mehrere Artists gleichzeitig.

**Request:**
```json
{
  "artist_ids": ["uuid1", "uuid2", "uuid3"],
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

**Response:**
```json
{
  "total_requested": 10,
  "created": 8,
  "failed": 2,
  "failed_artists": ["uuid-x", "uuid-y"]
}
```

### GET `/api/automation/followed-artists/preview`

Schnelle Vorschau ohne Datenbank-Synchronisation.

**Query-Parameter:**
| Parameter | Typ | Default | Beschreibung |
|-----------|-----|---------|--------------|
| `limit` | int | 50 | Max. Artists (1-50) |

**Response:**
Rohe Spotify API Response mit Artist-Daten.

---

## Workflow-Beispiel

### Kompletter Setup-Flow

```mermaid
graph TD
    A[Spotify verbinden] --> B[/followed-artists öffnen]
    B --> C[Sync from Spotify klicken]
    C --> D{Artists gefunden?}
    D -->|Ja| E[Artists in Grid anzeigen]
    D -->|Nein| F[Fehler: 403 oder keine Artists]
    E --> G[Artists auswählen]
    G --> H[Watchlist-Settings konfigurieren]
    H --> I[Create Watchlists klicken]
    I --> J[Watchlists erstellt]
    J --> K[Background-Worker prüft auf neue Releases]
```

### Typische Nutzung

1. **Erstmalig**: Sync → Alle auswählen → Watchlists erstellen
2. **Neue Artists**: Sync → Neue Artists werden als "nicht in Watchlist" markiert → Auswählen → Watchlists erstellen
3. **Cleanup**: Nicht mehr gefolgte Artists werden automatisch erkannt

---

## Datenbank-Migration

Das Feature erfordert eine Migration für Genre/Tags-Unterstützung:

```bash
alembic upgrade head
```

**Migrationsdetails:**
- Fügt `genres` TEXT Spalte hinzu (JSON-Array)
- Fügt `tags` TEXT Spalte hinzu (JSON-Array)
- SQLite-kompatibel (TEXT statt nativem JSON-Typ)

---

## Troubleshooting

### Problem: 403 Forbidden Error

**Ursache:** Fehlende `user-follow-read` OAuth-Berechtigung

**Lösung:** 
1. Gehe zu `/auth/logout`
2. Verbinde Spotify erneut über `/auth/authorize`
3. Bestätige ALLE angeforderten Berechtigungen

### Problem: Keine Artists werden synchronisiert

**Ursache:** Du folgst keinen Künstlern auf Spotify

**Lösung:** 
1. Öffne Spotify
2. Folge einigen Künstlern
3. Versuche den Sync erneut

### Problem: Sync dauert sehr lange

**Ursache:** Sehr viele gefolgte Artists (100+)

**Info:** 
- Spotify paginiert mit max. 50 Artists pro Request
- Bei 500 Artists = 10 API-Aufrufe
- Jeder Aufruf kann 1-2 Sekunden dauern
- Normal bei großen Sammlungen

### Problem: Bulk-Watchlist-Erstellung schlägt teilweise fehl

**Ursache:** Watchlist existiert bereits für manche Artists

**Info:** Das ist normal - bereits existierende Watchlists werden übersprungen, nicht als Fehler gezählt.

---

## Best Practices

### Initiale Einrichtung

1. **Preview zuerst**: Teste mit Preview ob die Verbindung funktioniert
2. **Sync durchführen**: Vollständiger Sync aller Artists
3. **Prüfen**: Sind die richtigen Artists da?
4. **Bulk-Watchlists**: Erstelle Watchlists für alle oder ausgewählte Artists

### Regelmäßige Wartung

1. **Wöchentlicher Sync**: Neue Artists werden erkannt
2. **Watchlists für neue Artists**: Nur für neue Artists erstellen
3. **Cleanup**: Nicht mehr benötigte Watchlists deaktivieren

### Performance-Tipps

- Nutze "Preview" für schnelle Tests
- Erstelle Watchlists in Batches, nicht einzeln
- Background-Worker übernimmt die eigentliche Arbeit

---

## Verwandte Features

- [Automation & Watchlists](./automation-watchlists.md) - Watchlist-Details und Filter
- [Authentication](../api/auth-api.md) - Spotify OAuth
- [Download Management](./download-management.md) - Download-Queue
