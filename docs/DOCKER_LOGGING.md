# Docker Logging Guide

## Log-Format verstehen

### Standard Log-Format
```
09:33:37 │ ERROR   │ soulspot.application.services.spotify_sync_service:142 │ Error syncing followed artists: 'SpotifySyncService' object has no attribute '_spotify_plugin'
```

**Format-Erklärung:**
- `09:33:37` - Timestamp (HH:MM:SS)
- `ERROR` - Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `soulspot.application.services.spotify_sync_service:142` - Modul und Zeile
- Rest - Log-Nachricht

### Exception Formatting (NEU seit v1.0)

**Kompakte Exception-Chains** - Keine verbose Python-Boilerplate mehr!

**Vorher (verbose):**
```
ERROR: Sync cycle failed: All connection attempts failed
Traceback (most recent call last):
  File "httpcore/_async/connection.py", line 124
    stream = await self._network_backend.connect_tcp(**kwargs)
httpcore.ConnectError: All connection attempts failed

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "download_status_sync_worker.py", line 185
    slskd_downloads = await self._get_slskd_downloads()
httpx.ConnectError: All connection attempts failed
```

**Jetzt (kompakt):**
```
ERROR: Sync cycle failed: All connection attempts failed
╰─► httpcore.ConnectError: All connection attempts failed
    File "httpcore/_async/connection.py", line 124, in _connect
      stream = await self._network_backend.connect_tcp(**kwargs)
╰─► httpx.ConnectError: All connection attempts failed
    File "download_status_sync_worker.py", line 185, in _sync_cycle
      slskd_downloads = await self._get_slskd_downloads()
```

**Vorteile:**
- ✅ 60% weniger Log-Zeilen
- ✅ Klare visuelle Hierarchie mit `╰─►` Markern
- ✅ Root cause zuerst (von unten nach oben lesen)
- ✅ Keine "The above exception was the direct cause..." Boilerplate
- ✅ Alle relevanten Stack-Frames bleiben erhalten

### Log-Levels

| Level | Bedeutung | Beispiel |
|-------|-----------|----------|
| **DEBUG** | Detaillierte Entwickler-Infos | `Found track by spotify_id: ...` |
| **INFO** | Normale Operationen | `Download completed: track_123` |
| **WARNING** | Potenzielle Probleme | `Failed to cancel in slskd (will retry)` |
| **ERROR** | Kritische Fehler | `Failed to sync followed artists` |
| **CRITICAL** | App-Breaking Fehler | `Database connection lost` |

## Docker Logs ansehen

### Alle Logs anzeigen
```bash
docker compose logs -f soulspot
```

### Nur Errors
```bash
docker compose logs -f soulspot | grep ERROR
```

### Nur einen bestimmten Worker
```bash
docker compose logs -f soulspot | grep spotify_sync_worker
```

### Mit Timestamps
```bash
docker compose logs -f --timestamps soulspot
```

### Letzte 100 Zeilen
```bash
docker compose logs --tail 100 soulspot
```

## Häufige Fehler-Patterns

### 1. **AttributeError**
```
ERROR │ 'SpotifySyncService' object has no attribute '_spotify_plugin'
```
**Was es bedeutet:** Code versucht auf nicht-existierendes Attribut zuzugreifen
**Lösung:** Refactoring-Fehler - Attributname hat sich geändert

### 2. **Import Errors**
```
ERROR │ ModuleNotFoundError: No module named 'sse_starlette'
```
**Was es bedeutet:** Python-Paket fehlt in Dependencies
**Lösung:** `poetry install` oder Dependency zu `pyproject.toml` hinzufügen

### 3. **Connection Errors**
```
WARNING │ Failed to initialize slskd provider: Connection refused
```
**Was es bedeutet:** Externe Service nicht erreichbar
**Lösung:** Prüfe ob slskd läuft, Netzwerk-Config checken

### 4. **Authentication Errors**
```
WARNING │ Spotify not authenticated, skipping artists sync
```
**Was es bedeutet:** User hat sich nicht mit Spotify eingeloggt
**Lösung:** Normal - User muss sich erst authentifizieren

### 5. **Database Errors**
```
ERROR │ IntegrityError: UNIQUE constraint failed: tracks.spotify_id
```
**Was es bedeutet:** Versuch duplizierte Daten zu speichern
**Lösung:** Prüfe Daten-Validierung, eventuell Migration nötig

### 6. **Filesystem Errors (NEU - Verbesserte Messages!)**

#### Read-Only Filesystem (Errno 30):
```
ERROR │ spotify_image_service:495 │ Failed to save artist image '/config/images/artists/abc123.jpg': Read-only filesystem (Errno 30 / EROFS) [url=https://..., size=45231 bytes]
ℹ️  HINT: Docker volume might be mounted read-only. Check docker-compose.yml for ':ro' flags. Run: mount | grep <path> to check mount options.
```

#### Permission Denied (Errno 13):
```
ERROR │ library_scanner:365 │ Failed to scan directory '/music/Private': Permission denied (Errno 13 / EACCES)
ℹ️  HINT: Check file permissions and PUID/PGID in Docker. Run: ls -la <path> to see permissions.
🐳 Docker Fix: Set PUID=$(id -u) PGID=$(id -g) in docker-compose.yml. Run: docker compose exec soulspot ls -la <path> to check ownership.
```

#### No Space Left (Errno 28):
```
ERROR │ renaming_service:486 │ Failed to move/rename file '/music/track.mp3': No space left on device (Errno 28 / ENOSPC) [destination=/music/Artist/Album/track.mp3]
ℹ️  HINT: Disk is full! Check available space with 'df -h'. Clean up old files or increase disk size.
```

#### Cross-Device Move (Errno 18):
```
INFO  │ renaming_service:489 │ Cross-filesystem move detected, using copy+delete fallback: /downloads/track.mp3 -> /music/track.mp3
```
(This one auto-recovers, so only INFO level)

## Stack-Traces verstehen

Ab sofort enthalten **alle ERROR-Logs vollständige Stack-Traces:**

```
09:33:37 │ ERROR   │ soulspot.application.services.spotify_sync_service:142 │ Error syncing: 'SpotifySyncService' object has no attribute '_spotify_plugin'
Traceback (most recent call last):
  File "/app/src/soulspot/application/services/spotify_sync_service.py", line 138, in sync_followed_artists
    if not self._spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
                ^^^^^^^^^^^^^^^^^^^^
AttributeError: 'SpotifySyncService' object has no attribute '_spotify_plugin'. Did you mean: 'spotify_plugin'?
```

**Stack-Trace lesen:**
1. **Unten anfangen** - Die unterste Zeile ist der tatsächliche Fehler
2. **Nach oben arbeiten** - Zeigt den Aufruf-Stack
3. **Dateinamen + Zeilen** - Exakte Position im Code
4. **Fehlertyp** - `AttributeError`, `KeyError`, `ValueError`, etc.

## Logging-Level ändern

### Zur Laufzeit (über API)
```bash
curl -X PUT http://localhost:5030/api/settings/log-level \
  -H "Content-Type: application/json" \
  -d '{"level": "DEBUG"}'
```

### Per Environment Variable
```yaml
# docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Für spezifische Module (Code-Edit)
```python
# In main.py oder lifecycle.py
import logging
logging.getLogger("soulspot.application.workers").setLevel(logging.DEBUG)
```

## Production vs Development Logs

### Development (Human-Readable)
```
09:33:37 │ ERROR   │ spotify_sync:142 │ Error syncing artists
```

### Production (JSON für Log-Aggregation)
```json
{
  "timestamp": "2025-12-14 09:33:37",
  "level": "ERROR",
  "logger": "soulspot.application.services.spotify_sync_service",
  "module": "spotify_sync_service",
  "function": "sync_followed_artists",
  "line": 142,
  "correlation_id": "a3f8b2d1-4c5e-6f7g-8h9i-0j1k2l3m4n5o",
  "message": "Error syncing followed artists",
  "exc_info": "Traceback (most recent call last)..."
}
```

**Production-Modus aktivieren:**
```python
# In main.py
from soulspot.infrastructure.observability.logging import configure_logging
configure_logging(log_level="INFO", json_format=True)
```

## Correlation-IDs

Jede HTTP-Request bekommt eine eindeutige `correlation_id`:

```
09:33:37 │ INFO    │ middleware:45 │ [a3f8] GET /api/artists/sync
09:33:38 │ ERROR   │ spotify_sync:142 │ [a3f8] Error syncing artists
09:33:38 │ INFO    │ middleware:67 │ [a3f8] Response 500 (1.2s)
```

**Alle Logs einer Request finden:**
```bash
docker compose logs soulspot | grep "a3f8"
```

## Best Practices

### ✅ DO:
- Schaue auf **Log-Level** (ERROR vs WARNING)
- Lese **Stack-Traces von unten nach oben**
- Nutze **Correlation-IDs** für Request-Tracing
- Filtere Logs nach **Worker/Modul**
- Prüfe **Timestamps** für Timing-Issues

### ❌ DON'T:
- Ignoriere WARNINGS nicht - sie zeigen oft Probleme
- Übersehe nicht die **Zeile + Datei** im Log
- Verwechsle nicht DEBUG (normal) mit ERROR (Problem)
- Suche nicht nur nach "error" - auch "exception", "failed", "traceback"

## Troubleshooting-Workflow

1. **Fehler reproduzieren** und Timestamp notieren
2. **Logs filtern** auf den Zeitraum
3. **Stack-Trace lesen** von unten nach oben
4. **Correlation-ID** finden und alle zugehörigen Logs anzeigen
5. **Modul-Kontext** verstehen (welcher Worker/Service?)
6. **Code-Stelle** im Repo finden (Datei:Zeile)
7. **Root-Cause** identifizieren
8. **Fix verifizieren** durch erneutes Testen

## Logging-Verbessungen (Dezember 2025)

### Neu hinzugefügt:
- ✅ **Stack-Traces** bei allen ERROR-Logs (`exc_info=True`)
- ✅ **Modul:Zeile** im Log-Format für exakte Code-Position
- ✅ **Erweiterte Worker-Logs** (alle Background-Jobs)
- ✅ **API-Router Stack-Traces** bei allen Fehlern

### Betroffene Module:
- `application/workers/*` - Alle Worker (Sync, Download, Cleanup, etc.)
- `api/routers/*` - Alle API-Endpunkte
- `infrastructure/observability/logging.py` - Core Logging-Setup

### Migration von alten Logs:
**Vorher:**
```
09:33:37 │ ERROR │ Error syncing followed artists: AttributeError
```

**Nachher:**
```
09:33:37 │ ERROR   │ soulspot.application.services.spotify_sync_service:142 │ Error syncing followed artists: 'SpotifySyncService' object has no attribute '_spotify_plugin'
Traceback (most recent call last):
  File "/app/src/soulspot/application/services/spotify_sync_service.py", line 138, in sync_followed_artists
    if not self._spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
                ^^^^^^^^^^^^^^^^^^^^
AttributeError: 'SpotifySyncService' object has no attribute '_spotify_plugin'. Did you mean: 'spotify_plugin'?
```

## Weiterführende Links

- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Structured Logging with JSON](https://github.com/madzak/python-json-logger)
- [Docker Compose Logs](https://docs.docker.com/compose/reference/logs/)
