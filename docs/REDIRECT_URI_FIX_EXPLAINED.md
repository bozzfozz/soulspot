# Redirect URI Fix - Vollständige Erklärung

## Warum wurde `settings.py` geändert?

### Das Problem

Es gab einen **Konflikt zwischen dem Default-Wert und der tatsächlichen API-Route**!

#### Vorher (FALSCH):
```python
# settings.py
redirect_uri: str = Field(
    default="http://localhost:8000/auth/spotify/callback",  # ❌ FALSCH!
    ...
)
```

#### Die tatsächliche FastAPI-Route:
```python
# src/soulspot/main.py (Zeile 525)
app.include_router(api_router, prefix="/api")

# src/soulspot/api/routers/__init__.py (Zeile 32)
api_router.include_router(auth.router, prefix="/auth")

# src/soulspot/api/routers/auth.py (Zeile 79)
@router.get("/callback")
async def callback(...):
    ...
```

**Ergebnis der Route-Struktur:**
- `/api` (von main.py)
- + `/auth` (von __init__.py)
- + `/callback` (von auth.py)
- = `/api/auth/callback` ✅

Der alte Default `http://localhost:8000/auth/spotify/callback` zeigt auf `/auth/spotify/callback`, aber diese Route **existiert gar nicht**!

### Die Korrektur

```python
# settings.py (JETZT KORREKT)
redirect_uri: str = Field(
    default="http://localhost:8000/api/auth/callback",  # ✅ KORREKT!
    ...
)
```

## Wichtig: Default vs. Deine Konfiguration

### Der Default ist nur ein Fallback!

Der Default in `settings.py` wird **NUR** verwendet, wenn:
- Keine `.env` Datei existiert, ODER
- `SPOTIFY_REDIRECT_URI` nicht in der `.env` gesetzt ist

### Für Docker (Port 8765):

⚠️ **WICHTIG: Spotify erfordert localhost oder HTTPS!**

Du **MUSST** `127.0.0.1` verwenden:

```env
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback
```

**NICHT verwenden:**

```env
# ❌ FALSCH - Spotify lehnt LAN-IPs ohne HTTPS ab!
SPOTIFY_REDIRECT_URI=http://192.168.178.100:8765/api/auth/callback
```

**Zugriff von anderen Geräten:**

Wenn du von einem anderen Gerät zugreifen möchtest, nutze einen SSH-Tunnel:

```bash
# Auf deinem Client-Gerät (Laptop, Tablet, etc.):
ssh -L 8765:localhost:8765 benutzer@192.168.178.100

# Dann im Browser öffnen:
# http://127.0.0.1:8765
```

So erscheint der Zugriff für Spotify als `localhost`, auch wenn du remote bist!

## Die vollständige Fix-Historie

### Problem 1: Veralteter Pfad in settings.py
- ❌ Alt: `/auth/spotify/callback`
- ✅ Neu: `/api/auth/callback`

### Problem 2: Veralteter Pfad mit `/api/v1/` in Docker-Dateien
Die Anwendung wurde früher unter `/api/v1/` laufen, wurde aber auf `/api/` umgestellt.
Viele Dokumente und Konfigurationsdateien enthielten noch den alten Pfad.

- ❌ Alt: `http://127.0.0.1:8765/api/v1/auth/callback`
- ✅ Neu: `http://127.0.0.1:8765/api/auth/callback`

### Korrigierte Dateien:
1. ✅ `src/soulspot/config/settings.py` - Default redirect_uri
2. ✅ `.env.example` - Beispiel-Konfiguration
3. ✅ `docker/docker-compose.yml` - Docker Default
4. ✅ `docker/README.md` - Docker-Dokumentation
5. ✅ `tests/unit/config/test_settings.py` - Unit-Test

## Was musst DU jetzt tun?

### Schritt 1: Überprüfe deine .env Datei

```bash
cat .env | grep SPOTIFY_REDIRECT_URI
```

### Schritt 2: Setze die korrekte redirect_uri

Füge in deiner `.env` Datei hinzu oder aktualisiere:

```env
# Für Docker (Port 8765) - IMMER 127.0.0.1 verwenden!
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/auth/callback

# Für lokale Entwicklung (Port 8000):
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

⚠️ **WICHTIG:** Verwende NIEMALS LAN-IP-Adressen (wie `192.168.x.x`) ohne HTTPS! Spotify lehnt diese ab.

### Schritt 3: Registriere in Spotify Developer Dashboard

1. Gehe zu https://developer.spotify.com/dashboard
2. Wähle deine App aus
3. Klicke "Edit Settings"
4. Unter "Redirect URIs", füge hinzu:
   - `http://localhost:8765/api/auth/callback` (für Docker)
   - `http://127.0.0.1:8765/api/auth/callback` (für Docker)
   - `http://localhost:8000/api/auth/callback` (für lokale Entwicklung)
   
   **NICHT hinzufügen:**
   - ❌ `http://192.168.178.100:8765/...` (wird abgelehnt!)

5. Klicke "Add" und dann "Save"

### Schritt 4: Starte die Anwendung neu

```bash
# Docker
docker-compose restart

# Oder neu bauen
docker-compose down
docker-compose up -d
```

### Schritt 5: Teste

1. Öffne: `http://127.0.0.1:8765/auth` (wenn direkt auf Docker-Host)
2. ODER nutze SSH-Tunnel von anderem Gerät (siehe unten)
3. Klicke "Connect Spotify"
4. Du wirst zu Spotify weitergeleitet
5. Nach der Autorisierung kommst du zurück zur App

## Fehlersuche

### Fehler: "INVALID_CLIENT: Insecure redirect URI"

**Bedeutung:** Die `redirect_uri` in deiner Anfrage stimmt nicht mit Spotify Dashboard überein.

**Lösung:**
1. Kopiere die `redirect_uri` aus der Fehlermeldung (URL-dekodiert)
2. Füge **EXAKT** diese URI im Spotify Dashboard hinzu
3. Warte 30 Sekunden (Spotify braucht Zeit zum Aktualisieren)
4. Versuche es erneut

### Fehler: Alte redirect_uri wird noch verwendet

**Ursache:** `.env` Datei überschreibt die neuen Defaults

**Lösung:**
```bash
# Überprüfe deine aktuelle Konfiguration
grep SPOTIFY_REDIRECT_URI .env

# Korrigiere falls nötig
# Entferne /api/v1/ → verwende /api/
# FALSCH: http://....:8765/api/v1/auth/callback
# RICHTIG: http://....:8765/api/auth/callback
```

## Zusammenfassung

### Der korrekte Pfad ist IMMER: `/api/auth/callback`

❌ **Nicht verwenden:**
- `/auth/spotify/callback` (alte Route, existiert nicht mehr)
- `/api/v1/auth/callback` (veraltete Version)

✅ **Korrekt:**
- `/api/auth/callback`

### Port hängt von deinem Setup ab:
- Lokale Entwicklung: `:8000`
- Docker (Standard): `:8765`
- Deine Konfiguration: prüfe `docker-compose.yml` ports

### Vollständige URLs für Port 8765:
- `http://localhost:8765/api/auth/callback`
- `http://127.0.0.1:8765/api/auth/callback`
- `http://192.168.178.100:8765/api/auth/callback` (deine LAN-IP)
