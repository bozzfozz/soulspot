# Log Design System - Verständliche und konsistente Logs

## 🎯 Ziel

**Problem**: Logs wie "Error: All connection attempts failed" sind kryptisch und nicht hilfreich.  
**Lösung**: Strukturierte, visuelle und actionable Log-Meldungen mit Kontext und Troubleshooting-Hinweisen.

## 📐 Design-Prinzipien

### 1. **Icon First** - Visuelle Marker für schnelles Scannen

| Icon | Level | Bedeutung | Beispiel |
|------|-------|-----------|----------|
| 🔴 | ERROR | Kritischer Fehler | Connection failed |
| ❌ | ERROR | Operation failed | Sync failed |
| ⚠️ | WARNING | Warnung, aber fortfahren | Token expires soon |
| ⏱️ | WARNING | Timeout | Request took too long |
| ✅ | INFO | Erfolg | Download complete |
| 🔄 | INFO | In Bearbeitung | Syncing data |
| 💡 | DEBUG | Hinweis/Tipp | Check settings |
| 🔑 | WARNING | Auth-Problem | Authentication required |
| 📥 | INFO | Import | File imported |
| ⏭️ | INFO | Übersprungen | File skipped |
| ⬇️ | INFO | Download | Download started |
| ⚙️ | WARNING | Config-Problem | Invalid setting |

### 2. **Strukturierte Ausgabe** - Tree-Format für Kontext

```
🔴 slskd Connection Failed
├─ Service: slskd
├─ Target: http://slskd:5030/api/v0/transfers/downloads
├─ Reason: All connection attempts failed
└─ 💡 Check: Is slskd container running? docker ps | grep slskd
```

**Vorteile:**
- ✅ Alle relevanten Infos auf einen Blick
- ✅ Visuell leicht zu parsen (Tree-Struktur)
- ✅ Actionable hints unten (💡)

### 3. **Kontext > Nur Error Message**

**❌ SCHLECHT:**
```
ERROR: Connection failed
```

**✅ GUT:**
```
🔴 slskd Connection Failed
├─ Service: slskd
├─ Target: http://slskd:5030
└─ 💡 Check if slskd container is running: docker ps | grep slskd
```

### 4. **Actionable Hints** - Immer Lösungsvorschlag

Jeder Error/Warning MUSS einen `💡 Hint` haben:

```python
logger.error(LogMessages.connection_failed(
    service="slskd",
    target="http://slskd:5030",
    error="Connection timeout",
    hint="Check if slskd container is running: docker ps | grep slskd"
))
```

## 🛠️ Verwendung

### Basic Usage

```python
from soulspot.infrastructure.observability.log_messages import LogMessages

# Connection Error
logger.error(LogMessages.connection_failed(
    service="Spotify",
    target="https://api.spotify.com/v1/me",
    error="401 Unauthorized",
    hint="Token expired - re-authenticate in Settings → Providers → Spotify"
))

# Worker Start
logger.info(LogMessages.worker_started(
    worker="Spotify Sync",
    interval=60,
    config={"check_followed": True, "check_playlists": True}
))

# Sync Operations
logger.info(LogMessages.sync_started(
    entity="Followed Artists",
    source="Spotify",
    count=42
))

logger.info(LogMessages.sync_completed(
    entity="Followed Artists",
    added=3,
    updated=5,
    removed=1,
    errors=0
))

# File Operations
logger.info(LogMessages.file_imported(
    filename="track.mp3",
    source="/downloads/track.mp3",
    destination="/music/Artist/Album/01 - Track.mp3"
))

logger.warning(LogMessages.file_skipped(
    filename="track.mp3",
    reason="no matching track in database",
    hint="File may not be from a completed download"
))

# Downloads
logger.info(LogMessages.download_started(
    track="Bohemian Rhapsody",
    artist="Queen",
    quality="FLAC"
))

logger.info(LogMessages.download_completed(
    track="Bohemian Rhapsody",
    artist="Queen",
    file_path="/downloads/Queen - Bohemian Rhapsody.flac",
    duration=42.5
))

# Auth
logger.warning(LogMessages.auth_required(
    service="Spotify",
    feature="Followed Artists Sync",
    hint="Go to Settings → Providers → Spotify → Connect"
))

logger.warning(LogMessages.token_expired(
    service="Spotify",
    expires_at="2025-12-14 11:24:08",
    hint="Token refresh worker will automatically renew"
))
```

### Output Beispiele

**Connection Error:**
```
11:24:08 │ ERROR │ slskd_client:246 │ 🔴 slskd Connection Failed
├─ Service: slskd
├─ Target: http://slskd:5030/api/v0/transfers/downloads
├─ Reason: All connection attempts failed
└─ 💡 Check if slskd container is running: docker ps | grep slskd
```

**Worker Start:**
```
11:24:08 │ INFO │ spotify_sync_worker:118 │ ✅ Spotify Sync Started
├─ Interval: 60s
├─ check_followed: True
└─ check_playlists: True
```

**Sync Complete:**
```
11:24:12 │ INFO │ followed_artists_service:132 │ ✅ Followed Artists Sync Complete
├─ Added: 3
├─ Updated: 5
├─ Removed: 1
└─ Errors: 0
```

**File Import:**
```
11:24:15 │ INFO │ auto_import:178 │ 📥 File Imported
├─ File: Queen - Bohemian Rhapsody.flac
├─ From: /downloads/Queen - Bohemian Rhapsody.flac
└─ To: /music/Queen/A Night at the Opera/01 - Bohemian Rhapsody.flac
```

**File Skipped:**
```
11:24:16 │ INFO │ auto_import:165 │ ⏭️ File Skipped
├─ File: random_song.mp3
├─ Reason: no matching track in database
└─ 💡 File may not be from a completed download
```

**Auth Required:**
```
11:24:20 │ WARNING │ spotify_plugin:142 │ 🔑 Spotify Authentication Required
├─ Feature: Followed Artists Sync
└─ 💡 Go to Settings → Providers → Spotify → Connect
```

**Download Complete:**
```
11:24:45 │ INFO │ download_worker:234 │ ✅ Download Complete
├─ Track: Bohemian Rhapsody
├─ Artist: Queen
├─ Path: /downloads/Queen - Bohemian Rhapsody.flac
└─ Duration: 42.5s
```

## 📊 Template-Kategorien

### 1. Connection Errors
- `connection_failed()` - Connection fehlgeschlagen
- `connection_timeout()` - Connection timeout

### 2. Worker Lifecycle
- `worker_started()` - Worker gestartet
- `worker_failed()` - Worker fehlgeschlagen

### 3. Data Sync
- `sync_started()` - Sync begonnen
- `sync_completed()` - Sync abgeschlossen
- `sync_failed()` - Sync fehlgeschlagen

### 4. File Operations
- `file_imported()` - Datei importiert
- `file_skipped()` - Datei übersprungen
- `file_operation_failed()` - File-Operation fehlgeschlagen

### 5. Authentication
- `auth_required()` - Authentifizierung erforderlich
- `token_expired()` - Token abgelaufen

### 6. Download Operations
- `download_started()` - Download gestartet
- `download_completed()` - Download abgeschlossen
- `download_failed()` - Download fehlgeschlagen

### 7. Configuration
- `config_invalid()` - Ungültige Konfiguration

## 🔄 Migration Guide

### Vorher (Alt)

```python
logger.error(f"Failed to sync followed artists: {e}", exc_info=True)
```

**Probleme:**
- ❌ Keine Struktur
- ❌ Kein Kontext (welcher Service?)
- ❌ Keine Hints
- ❌ Schwer zu parsen

### Nachher (Neu)

```python
logger.error(
    LogMessages.sync_failed(
        entity="Followed Artists",
        source="Spotify",
        error=str(e),
        hint="Check Spotify authentication in Settings → Providers"
    ),
    exc_info=True
)
```

**Vorteile:**
- ✅ Strukturiert (Tree-Format)
- ✅ Kontext (Entity + Source)
- ✅ Actionable Hint
- ✅ Visuell (Icon 🔴)
- ✅ Stack trace bleibt (exc_info=True)

### Migration Pattern

1. **Identifiziere Log-Kategorie:**
   - Connection? → `connection_failed()`
   - Sync? → `sync_started()` / `sync_completed()` / `sync_failed()`
   - File? → `file_imported()` / `file_skipped()`
   - Download? → `download_started()` / `download_completed()`
   - Auth? → `auth_required()` / `token_expired()`

2. **Extrahiere Kontext:**
   - Was ist fehlgeschlagen? (entity, operation)
   - Wer/Was ist betroffen? (service, filename, track)
   - Warum? (error message)

3. **Füge Hint hinzu:**
   - Was kann der User tun?
   - Wo findet er mehr Infos?
   - Welche Settings prüfen?

4. **Verwende Template:**
   ```python
   logger.error(LogMessages.<template>(
       # Required fields
       entity=...,
       source=...,
       error=...,
       # Optional hint
       hint="Check X in Y → Z"
   ), exc_info=True)  # Keep stack trace!
   ```

## 📈 Rollout-Plan

### Phase 1: Critical Paths (sofort)
- ✅ Connection errors (slskd, Spotify, Deezer)
- ✅ Worker failures
- ✅ Auth errors

### Phase 2: User-Facing (Woche 1)
- File import/skip messages
- Download status updates
- Sync operations

### Phase 3: Internal (Woche 2-3)
- Database operations
- Background jobs
- Cleanup/maintenance

### Phase 4: Polish (Woche 4)
- Alle remaining logs
- Consistency check
- Documentation finalize

## 🎓 Best Practices

### DO ✅

```python
# GOOD: Strukturiert, Kontext, Hint
logger.error(LogMessages.connection_failed(
    service="slskd",
    target=self.base_url,
    error=str(e),
    hint="Check if slskd is running: docker ps | grep slskd"
), exc_info=True)
```

### DON'T ❌

```python
# BAD: Kein Kontext, kein Hint
logger.error(f"Connection failed: {e}")

# BAD: Zu generisch
logger.error("Error")

# BAD: Kein exc_info bei Exceptions
logger.error(LogMessages.sync_failed(...))  # Missing exc_info=True!
```

### Guidelines

1. **Immer** `exc_info=True` bei Exceptions
2. **Immer** Hint bei Errors/Warnings
3. **Nie** leere/generische Messages
4. **Immer** Kontext (service, entity, file, track)
5. **Nutze** Icons konsequent
6. **Teste** Output im Docker-Log (lesbar?)

## 🧪 Testing

### Log Output testen

```python
import logging
from soulspot.infrastructure.observability.log_messages import LogMessages
from soulspot.infrastructure.observability.logging import configure_logging

# Configure logging
configure_logging(log_level="INFO", json_format=False)
logger = logging.getLogger(__name__)

# Test messages
logger.error(LogMessages.connection_failed(
    service="Test Service",
    target="http://localhost:1234",
    error="Connection refused",
    hint="Start the service first"
))

logger.info(LogMessages.sync_completed(
    entity="Test Data",
    added=10,
    updated=5,
    removed=2,
    errors=0
))
```

### Expected Output

```
11:30:45 │ ERROR │ __main__:12 │ 🔴 Test Service Connection Failed
├─ Service: Test Service
├─ Target: http://localhost:1234
├─ Reason: Connection refused
└─ 💡 Start the service first

11:30:45 │ INFO │ __main__:20 │ ✅ Test Data Sync Complete
├─ Added: 10
├─ Updated: 5
├─ Removed: 2
└─ Errors: 0
```

## 📚 Weitere Templates

Wenn du einen neuen Log-Type brauchst:

1. **Füge Template zu `LogMessages` hinzu:**
   ```python
   @staticmethod
   def your_template(
       field1: str,
       field2: str,
       hint: str | None = None
   ) -> str:
       template = LogTemplate(
           icon="🔴",  # Choose appropriate icon
           title="Your Title",
           fields={"Field1": field1, "Field2": field2},
           hint=hint or "Default hint"
       )
       return template.format()
   ```

2. **Dokumentiere hier:**
   - Kategorie
   - Use Case
   - Beispiel

3. **Teste Output:**
   ```python
   logger.error(LogMessages.your_template(
       field1="value1",
       field2="value2"
   ))
   ```

## 🔍 Troubleshooting

**Problem**: Templates funktionieren nicht?  
**Lösung**: `from soulspot.infrastructure.observability.log_messages import LogMessages` importieren

**Problem**: Icons werden nicht angezeigt?  
**Lösung**: Docker-Terminal unterstützt UTF-8 (sollte automatisch funktionieren)

**Problem**: Zu viele Zeilen?  
**Lösung**: Nutze `logger.setLevel(logging.WARNING)` für weniger Output

**Problem**: Hint fehlt?  
**Lösung**: Immer `hint=` Parameter angeben!

## 📖 Siehe auch

- `infrastructure/observability/logging.py` - Logging-Konfiguration
- `infrastructure/observability/error_formatting.py` - OSError-Formatierung
- `docs/DOCKER_LOGGING.md` - Docker-Log-Guide
- `docs/development/STARTUP_VALIDATION.md` - Validation Protocol

---

**Erstellt:** 2025-12-14  
**Version:** 1.0  
**Status:** ✅ Production Ready
